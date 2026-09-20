# Databricks notebook source
# MAGIC %md
# MAGIC # Record a completed SDP update

# COMMAND ----------
import re

dbutils.widgets.text("catalog", "")
dbutils.widgets.text("release_seq", "")
catalog = dbutils.widgets.get("catalog")
release_seq = int(dbutils.widgets.get("release_seq"))
if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", catalog):
    raise ValueError("Invalid catalog")
for name in ["race_dimension", "session_results", "driver_season", "constructor_season"]:
    table = spark.table(f"{catalog}.f1pa_sdp_gold.{name}")
    if table.count() == 0 or table.filter(f"_release_seq IS NULL OR _release_seq <> {release_seq}").limit(1).count():
        raise ValueError(f"Incomplete Gold snapshot: {name}")
columns = ["driver_id", "driver_name", "full_name", "nationality_country_id", "date_of_birth"]
drivers = spark.table(f"{catalog}.f1pa_sdp_silver.drivers").select(*columns)
current_history = spark.table(f"{catalog}.f1pa_sdp_silver.drivers_history").filter(
    "__END_AT IS NULL").select(*columns)
if drivers.exceptAll(current_history).limit(1).count() or current_history.exceptAll(drivers).limit(1).count():
    raise ValueError("Current driver history must match the selected Silver snapshot")
spark.sql(f"""UPDATE {catalog}.f1pa_sdp_ops.releases
SET status = 'COMPLETE' WHERE release_seq = {release_seq}""")
