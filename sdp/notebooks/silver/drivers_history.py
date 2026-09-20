# Databricks notebook source
# MAGIC %md
# MAGIC # Silver: driver revision history

# COMMAND ----------
from pyspark import pipelines as dp

catalog = spark.conf.get("f1.catalog")
release_tag = spark.conf.get("f1.release_tag")
release_seq = int(spark.conf.get("f1.release_seq"))
silver = f"{catalog}.f1pa_sdp_silver"
landing = f"/Volumes/{catalog}/f1pa_sdp_files/landing"


def next_driver_snapshot(latest_snapshot_version):
    if latest_snapshot_version is None or latest_snapshot_version < release_seq:
        # The versioned snapshot is immutable and verified before this pipeline starts.
        snapshot = (
            spark.read.format("csv")
            .option("header", "true")
            .option("multiLine", "true")
            .option("escape", '"')
            .option("mode", "FAILFAST")
            .load(f"{landing}/csv/drivers/release_tag={release_tag}/f1db-drivers.csv")
            .selectExpr(
                "NULLIF(id, '') AS driver_id",
                "NULLIF(name, '') AS driver_name",
                "NULLIF(fullName, '') AS full_name",
                "NULLIF(nationalityCountryId, '') AS nationality_country_id",
                "CAST(NULLIF(dateOfBirth, '') AS DATE) AS date_of_birth",
            )
        )
        return snapshot, release_seq
    return None


dp.create_streaming_table(name=f"{silver}.drivers_history")
dp.create_auto_cdc_from_snapshot_flow(
    target=f"{silver}.drivers_history",
    source=next_driver_snapshot,
    keys=["driver_id"],
    stored_as_scd_type=2,
    track_history_column_list=["driver_name", "full_name", "nationality_country_id", "date_of_birth"],
)
