# Databricks notebook source
# MAGIC %md
# MAGIC # Bronze: constructor_standings

# COMMAND ----------
# MAGIC %run ../00-common/context

# COMMAND ----------
require_candidate()

# COMMAND ----------
# MAGIC %md
# MAGIC ## 1. Read new original CSV files with Auto Loader
# MAGIC All source columns stay as strings. Each release has its own immutable folder.

# COMMAND ----------
manifest = ready_manifest()
source_path = f"{landing}/csv/constructor_standings"
raw = (
    spark.readStream.format("cloudFiles")
    .option("cloudFiles.format", "csv")
    .option("header", "true")
    .option("multiLine", "true")
    .option("escape", '"')
    .option("mode", "FAILFAST")
    .option("cloudFiles.inferColumnTypes", "false")
    .option("cloudFiles.schemaLocation", f"{state_root}/schema/constructor_standings")
    .option("cloudFiles.schemaEvolutionMode", "addNewColumns")
    .option("cloudFiles.partitionColumns", "release_tag")
    .option("rescuedDataColumn", "_rescued_data")
    .load(source_path)
)
with_metadata = raw.select(
    "*", F.col("_metadata.file_path").alias("_source_file"),
    F.current_timestamp().alias("_ingested_at")
)

# COMMAND ----------
# MAGIC %md
# MAGIC ## 2. Append to one Bronze table and wait for AvailableNow to finish
# MAGIC Checkpoints are persistent and unique per table. Never replace them on a normal retry.
# MAGIC One Job retry resumes after a schema addition; review and repair if it still fails.

# COMMAND ----------
query = (
    with_metadata.writeStream.format("delta")
    .outputMode("append")
    .option("checkpointLocation", f"{state_root}/checkpoints/constructor_standings")
    .option("mergeSchema", "true")
    .trigger(availableNow=True)
    .toTable(f"{bronze}.constructor_standings")
)
query.awaitTermination()

# COMMAND ----------
# MAGIC %md
# MAGIC ## 3. Verify the selected release is complete before Silver can start

# COMMAND ----------
selected = current_input("constructor_standings")
print(f"constructor_standings: {selected.count()} rows available for {release_tag}")
