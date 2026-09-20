# Databricks notebook source
# MAGIC %md
# MAGIC # Silver: race_results

# COMMAND ----------
# MAGIC %run ../00-common/context

# COMMAND ----------
require_candidate()

# COMMAND ----------
# MAGIC %md
# MAGIC Validate the complete selected source snapshot before reconciling current rows.

# COMMAND ----------
current_input("race_results").createOrReplaceTempView("source_rows")
clean = spark.sql(f"""
SELECT
    CAST(NULLIF(`raceId`, '') AS BIGINT) AS race_id,
    CAST(NULLIF(`year`, '') AS BIGINT) AS season,
    CAST(NULLIF(`round`, '') AS BIGINT) AS round,
    NULLIF(`driverId`, '') AS driver_id,
    NULLIF(`constructorId`, '') AS constructor_id,
    NULLIF(`engineManufacturerId`, '') AS engine_manufacturer_id,
    NULLIF(`driverNumber`, '') AS car_number,
    CAST(NULLIF(`positionNumber`, '') AS BIGINT) AS finish_position,
    NULLIF(`positionText`, '') AS finish_status,
    CAST(NULLIF(`gridPositionNumber`, '') AS BIGINT) AS grid_position,
    NULLIF(`gridPositionText`, '') AS grid_status,
    CAST(NULLIF(`points`, '') AS DECIMAL(10,2)) AS points,
    CAST(NULLIF(`laps`, '') AS BIGINT) AS completed_laps,
    NULLIF(`reasonRetired`, '') AS retirement_reason,
    {release_seq} AS _release_seq
FROM source_rows
WHERE CAST(year AS BIGINT) >= {min_season}
""")
check_rows(clean, ["race_id","driver_id","car_number"], ["race_id","season","round","driver_id","constructor_id","engine_manufacturer_id","car_number","finish_status"])
if clean.filter(f"season > {year}").limit(1).count():
    raise ValueError("Unexpected future season")
require_current(f"{silver}.races")
check_reference(clean, spark.table(f"{silver}.races"), ["race_id","season","round"])
require_current(f"{silver}.drivers")
check_reference(clean, spark.table(f"{silver}.drivers"), ["driver_id"])
require_current(f"{silver}.constructors")
check_reference(clean, spark.table(f"{silver}.constructors"), ["constructor_id"])

# COMMAND ----------
# MAGIC %md
# MAGIC MERGE is batch-based here. Deletion is safe only after the full-snapshot checks above.

# COMMAND ----------
clean.createOrReplaceTempView("clean_rows")
spark.sql(f"""
CREATE TABLE IF NOT EXISTS {silver}.race_results USING DELTA
AS SELECT * FROM clean_rows WHERE 1 = 0
""")
spark.sql(f"""
MERGE INTO {silver}.race_results t
USING clean_rows s
ON t.race_id = s.race_id AND t.driver_id = s.driver_id AND t.car_number = s.car_number
WHEN MATCHED THEN UPDATE SET *
WHEN NOT MATCHED THEN INSERT *
WHEN NOT MATCHED BY SOURCE THEN DELETE
""")
check_rows(spark.table(f"{silver}.race_results"), ["race_id","driver_id","car_number"], ["race_id","season","round","driver_id","constructor_id","car_number","finish_status"], clean.count())
