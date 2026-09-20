# Databricks notebook source
# MAGIC %md
# MAGIC # Prepare one immutable source release

# COMMAND ----------
# MAGIC %run ../00-common/context

# COMMAND ----------
# MAGIC %run ../00-common/source

# COMMAND ----------
# MAGIC %md
# MAGIC ## 1. Create this project's namespaces and volumes

# COMMAND ----------
for schema in ("f1pa_files", "f1pa_ops", "f1pa_bronze", "f1pa_silver", "f1pa_gold"):
    spark.sql(f"CREATE SCHEMA IF NOT EXISTS {catalog}.{schema}")
    spark.sql(f"ALTER SCHEMA {catalog}.{schema} DISABLE PREDICTIVE OPTIMIZATION")
spark.sql(f"CREATE VOLUME IF NOT EXISTS {catalog}.f1pa_files.landing")
spark.sql(f"CREATE VOLUME IF NOT EXISTS {catalog}.f1pa_files.state")
spark.sql(f"""
CREATE TABLE IF NOT EXISTS {ops}.release_state (
    release_seq BIGINT, release_tag STRING, archive_sha256 STRING,
    min_season INT, status STRING, published_at TIMESTAMP, attempt_id STRING
) USING DELTA
""")
if "attempt_id" not in spark.table(f"{ops}.release_state").columns:
    spark.sql(f"ALTER TABLE {ops}.release_state ADD COLUMNS (attempt_id STRING)")
spark.sql(f"""
CREATE TABLE IF NOT EXISTS {ops}.task_completions (
    release_seq BIGINT, attempt_id STRING, task_key STRING
) USING DELTA
""")

# COMMAND ----------
# MAGIC %md
# MAGIC ## 2. Keep release order and recovery explicit
# MAGIC Only this Job owns these schemas. Do not run standalone writers concurrently.

# COMMAND ----------
from uuid import uuid4

dbutils.widgets.dropdown("allow_scope_expansion", "false", ["false", "true"])
allow_scope_expansion = dbutils.widgets.get("allow_scope_expansion") == "true"
previous = spark.table(f"{ops}.release_state").collect()
if release_tag not in PINNED_RELEASES:
    raise ValueError("Pin and review this release before running")
expected_hash = PINNED_RELEASES[release_tag]
check_release_order(previous, spark.table(f"{ops}.task_completions").collect(),
                    release_seq, min_season, expected_hash, allow_scope_expansion)

attempt_id = str(uuid4())
# Preserve the old scope and attempt before updating the latest release in place.
latest = max(previous, key=lambda row: row.release_seq) if previous else None
if latest and latest.min_season != min_season:
    (spark.createDataFrame(
        [(release_seq, latest.min_season, min_season, latest.attempt_id, attempt_id)],
        "release_seq long, previous_min_season int, min_season int, previous_attempt_id string, attempt_id string")
        .withColumn("requested_at", F.current_timestamp())
        .write.format("delta").mode("append").saveAsTable(f"{ops}.scope_expansions"))
spark.sql(f"""
MERGE INTO {ops}.release_state t
USING (SELECT {release_seq} AS release_seq, '{release_tag}' AS release_tag,
              '{expected_hash}' AS archive_sha256, {min_season} AS min_season,
              '{attempt_id}' AS attempt_id) s
ON t.release_seq = s.release_seq
WHEN MATCHED THEN UPDATE SET status = 'RUNNING', attempt_id = s.attempt_id,
  min_season = s.min_season, published_at = NULL
WHEN NOT MATCHED THEN INSERT
  (release_seq, release_tag, archive_sha256, min_season, status, published_at, attempt_id)
  VALUES (s.release_seq, s.release_tag, s.archive_sha256, s.min_season, 'RUNNING', NULL, s.attempt_id)
""")

# COMMAND ----------
# MAGIC %md
# MAGIC ## 3. Download the pinned ZIP and extract original CSV bytes
# MAGIC READY is written only after every required CSV has passed the file checks.

# COMMAND ----------
manifest = download_release(release_tag, landing)
display(spark.createDataFrame([
    (name, item["rows"], item["sha256"])
    for name, item in manifest["tables"].items()
], "dataset string, source_rows long, sha256 string"))
