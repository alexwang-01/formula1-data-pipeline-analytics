# Databricks notebook source
# MAGIC %md
# MAGIC # Shared parameters and small data checks
# MAGIC No transformation or MERGE is hidden in this notebook.

# COMMAND ----------
import json
from pathlib import Path
import re
from pyspark.sql import functions as F

spark.conf.set("spark.sql.ansi.enabled", "true")

dbutils.widgets.text("catalog", "")
dbutils.widgets.text("release_tag", "v2026.8.1")
dbutils.widgets.text("min_season", "1950")
catalog = dbutils.widgets.get("catalog")
release_tag = dbutils.widgets.get("release_tag")
min_season = int(dbutils.widgets.get("min_season"))
if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", catalog):
    raise ValueError("Supply an existing catalog with project create/use permissions")
match = re.fullmatch(r"v(\d{4})\.(\d{1,3})\.(\d{1,3})", release_tag)
if not match:
    raise ValueError("Invalid release tag")
year, release, patch = map(int, match.groups())
if release_tag != f"v{year}.{release}.{patch}" or not 1950 <= min_season <= year:
    raise ValueError("Invalid release or season scope")
release_seq = year * 1000000 + release * 1000 + patch
bronze = f"{catalog}.f1pa_bronze"
silver = f"{catalog}.f1pa_silver"
gold = f"{catalog}.f1pa_gold"
ops = f"{catalog}.f1pa_ops"
landing = f"/Volumes/{catalog}/f1pa_files/landing"
state_root = f"/Volumes/{catalog}/f1pa_files/state/manual"

# COMMAND ----------
def ready_manifest():
    path = Path(landing) / "manifests" / release_tag / "READY.json"
    manifest = json.loads(path.read_text())
    if manifest["release_tag"] != release_tag or manifest["release_seq"] != release_seq:
        raise ValueError("Manifest does not match this run")
    return manifest


def require_candidate():
    rows = spark.table(f"{ops}.release_state").filter(F.col("release_seq") == release_seq).collect()
    if len(rows) != 1 or rows[0].status != "RUNNING" or rows[0].min_season != min_season:
        raise ValueError("Run prepare_source for this release and scope first")
    if not rows[0].attempt_id:
        raise ValueError("Run the updated prepare_source before using these notebooks")


def mark_complete(task_key):
    # Only terminal table tasks record completion, after their writes and checks.
    require_candidate()
    attempt = spark.table(f"{ops}.release_state").filter(F.col("release_seq") == release_seq).first().attempt_id
    (spark.createDataFrame([(release_seq, attempt, task_key)],
                          "release_seq long, attempt_id string, task_key string")
        .write.format("delta").mode("append").saveAsTable(f"{ops}.task_completions"))


def check_release_order(previous, completions, sequence, scope, archive_hash, allow_scope_expansion=False):
    required = {"silver_drivers_history", "gold_race_dimension", "gold_session_results",
                "gold_driver_season", "gold_constructor_season"}
    if previous:
        latest = max(previous, key=lambda row: row.release_seq)
        if latest.min_season != scope:
            if not allow_scope_expansion or scope >= latest.min_season or sequence != latest.release_seq:
                raise ValueError("Changing season scope requires an explicit latest-release history expansion")
            completed = {item.task_key for item in completions
                         if item.release_seq == latest.release_seq and item.attempt_id == latest.attempt_id}
            legacy_complete = latest.status == "PUBLISHED" and latest.attempt_id is None
            if not legacy_complete and (not latest.attempt_id or not required <= completed):
                raise ValueError("Repair the unfinished latest release before expanding history")
    for row in previous:
        if row.release_seq > sequence:
            raise ValueError("An older release cannot overwrite newer data")
        if row.release_seq == sequence:
            if row.archive_sha256 != archive_hash:
                raise ValueError("Release identity changed")
            continue  # The latest release can be rebuilt or repaired.
        if row.status == "PUBLISHED" and row.attempt_id is None:
            continue  # A completed run from the previous architecture.
        completed = {item.task_key for item in completions
                     if item.release_seq == row.release_seq and item.attempt_id == row.attempt_id}
        if not row.attempt_id or not required <= completed:
            raise ValueError("Repair the unfinished earlier release first")


def check_rows(frame, keys, required, expected_count=None):
    count = frame.count()
    if expected_count is not None and count != expected_count:
        raise ValueError(f"Expected {expected_count} rows, found {count}")
    for column in required:
        if frame.filter(F.col(column).isNull()).limit(1).count():
            raise ValueError(f"Required column is null: {column}")
    if frame.groupBy(*keys).count().filter("count > 1").limit(1).count():
        raise ValueError(f"Duplicate key: {keys}")
    return count


def current_input(table):
    expected = ready_manifest()["tables"][table]["rows"]
    frame = spark.table(f"{bronze}.{table}").filter(F.col("release_tag") == release_tag)
    if frame.count() != expected:
        raise ValueError(f"{table}: incomplete release; MERGE is blocked")
    if "_rescued_data" in frame.columns and frame.filter("_rescued_data IS NOT NULL").limit(1).count():
        raise ValueError(f"{table}: review rescued data before Silver processing")
    if "year" in frame.columns and frame.filter(
        F.col("year").isNull() | (F.trim(F.col("year")) == "")
    ).limit(1).count():
        raise ValueError(f"{table}: missing season would bypass the analysis scope filter")
    return frame


def require_current(*tables):
    for table in tables:
        if spark.table(table).filter(F.col("_release_seq").isNull() | (F.col("_release_seq") != release_seq)).limit(1).count():
            raise ValueError(f"{table}: mixed or stale release")


def check_reference(frame, parent, keys):
    if frame.join(parent.select(*keys).distinct(), keys, "left_anti").limit(1).count():
        raise ValueError(f"Missing reference: {keys}")
