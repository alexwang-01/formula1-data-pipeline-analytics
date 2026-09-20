# Databricks notebook source
# MAGIC %md
# MAGIC # Silver: race_results

# COMMAND ----------
from pyspark import pipelines as dp

catalog = spark.conf.get("f1.catalog")
release_tag = spark.conf.get("f1.release_tag")
release_seq = int(spark.conf.get("f1.release_seq"))
min_season = int(spark.conf.get("f1.min_season"))
bronze = f"{catalog}.f1pa_sdp_bronze"
silver = f"{catalog}.f1pa_sdp_silver"
gold = f"{catalog}.f1pa_sdp_gold"


@dp.materialized_view(name=f"{silver}.race_results")
@dp.expect_or_fail("required_fields", "race_id IS NOT NULL AND season IS NOT NULL AND round IS NOT NULL AND driver_id IS NOT NULL AND constructor_id IS NOT NULL AND engine_manufacturer_id IS NOT NULL AND car_number IS NOT NULL AND finish_status IS NOT NULL")
def silver_race_results():
    return spark.sql(f"""
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
FROM (SELECT * FROM {bronze}.race_results WHERE release_tag = '{release_tag}') source_rows
WHERE CAST(year AS BIGINT) >= {min_season}
""")
