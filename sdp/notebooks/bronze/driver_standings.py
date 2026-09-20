# Databricks notebook source
# MAGIC %md
# MAGIC # Bronze: driver_standings

# COMMAND ----------
from pyspark import pipelines as dp
from pyspark.sql import functions as F

catalog = spark.conf.get("f1.catalog")
landing = f"/Volumes/{catalog}/f1pa_sdp_files/landing"


@dp.table(name=f"{catalog}.f1pa_sdp_bronze.driver_standings")
@dp.expect_or_fail("valid_csv", "_rescued_data IS NULL")
@dp.expect_or_fail("release_present", "release_tag IS NOT NULL")
def bronze_driver_standings():
    return (
        spark.readStream.format("cloudFiles")
        .option("cloudFiles.format", "csv")
        .option("header", "true")
        .option("multiLine", "true")
        .option("escape", '"')
        .option("mode", "FAILFAST")
        .option("cloudFiles.inferColumnTypes", "false")
        .option("cloudFiles.schemaEvolutionMode", "addNewColumns")
        .option("cloudFiles.partitionColumns", "release_tag")
        .option("rescuedDataColumn", "_rescued_data")
        .load(f"{landing}/csv/driver_standings")
        .select("*", F.col("_metadata.file_path").alias("_source_file"),
                F.current_timestamp().alias("_ingested_at"))
    )
