# Databricks notebook source
# MAGIC %md
# MAGIC # Prepare an independent SDP source snapshot

# COMMAND ----------
# MAGIC %run ../../notebooks/00-common/source

# COMMAND ----------
dbutils.widgets.text("catalog", "")
dbutils.widgets.text("release_tag", "v2026.8.1")
dbutils.widgets.text("release_seq", "2026008001")
dbutils.widgets.text("min_season", "1950")
catalog = dbutils.widgets.get("catalog")
release_tag = dbutils.widgets.get("release_tag")
release_seq = int(dbutils.widgets.get("release_seq"))
min_season = int(dbutils.widgets.get("min_season"))
if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", catalog):
    raise ValueError("Invalid catalog")
if release_number(release_tag) != release_seq or not 1950 <= min_season <= release_seq // 1000000:
    raise ValueError("Release parameters or season scope do not match")

for schema in ["f1pa_sdp_files", "f1pa_sdp_ops", "f1pa_sdp_bronze", "f1pa_sdp_silver", "f1pa_sdp_gold"]:
    spark.sql(f"CREATE SCHEMA IF NOT EXISTS {catalog}.{schema}")
    spark.sql(f"ALTER SCHEMA {catalog}.{schema} DISABLE PREDICTIVE OPTIMIZATION")
spark.sql(f"CREATE VOLUME IF NOT EXISTS {catalog}.f1pa_sdp_files.landing")
spark.sql(f"""CREATE TABLE IF NOT EXISTS {catalog}.f1pa_sdp_ops.releases (
    release_seq BIGINT, release_tag STRING, min_season BIGINT, status STRING
) USING DELTA""")

# COMMAND ----------
previous = spark.table(f"{catalog}.f1pa_sdp_ops.releases").collect()
for row in previous:
    if row.release_seq > release_seq:
        raise ValueError("Do not replay an older release into the existing SDP history")
    if row.release_seq < release_seq and row.status != "COMPLETE":
        raise ValueError("Complete the previous SDP release before advancing")
    if row.min_season != min_season:
        raise ValueError("Keep the same season scope for this SDP pipeline")

landing = f"/Volumes/{catalog}/f1pa_sdp_files/landing"
manifest = download_release(release_tag, landing)
spark.sql(f"""MERGE INTO {catalog}.f1pa_sdp_ops.releases t
USING (SELECT {release_seq} AS release_seq, '{release_tag}' AS release_tag,
              {min_season} AS min_season, 'PREPARED' AS status) s
ON t.release_seq = s.release_seq
WHEN MATCHED THEN UPDATE SET status = s.status
WHEN NOT MATCHED THEN INSERT *""")
print(f"Verified {release_tag}: {len(manifest['tables'])} original CSV files")
