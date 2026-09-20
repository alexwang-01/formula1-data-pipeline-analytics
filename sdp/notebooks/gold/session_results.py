# Databricks notebook source
# MAGIC %md
# MAGIC # Gold: session_results

# COMMAND ----------
from pyspark import pipelines as dp

catalog = spark.conf.get("f1.catalog")
release_tag = spark.conf.get("f1.release_tag")
release_seq = int(spark.conf.get("f1.release_seq"))
min_season = int(spark.conf.get("f1.min_season"))
bronze = f"{catalog}.f1pa_sdp_bronze"
silver = f"{catalog}.f1pa_sdp_silver"
gold = f"{catalog}.f1pa_sdp_gold"


@dp.materialized_view(name=f"{gold}.session_results")
@dp.expect_or_fail("required_fields", "race_id IS NOT NULL AND session_type IS NOT NULL AND driver_id IS NOT NULL AND constructor_id IS NOT NULL AND engine_manufacturer_id IS NOT NULL AND car_number IS NOT NULL AND driver_name IS NOT NULL AND constructor_name IS NOT NULL")
def gold_session_results():
    return spark.sql(f"""
WITH sessions AS (
    SELECT race_id, season, round, driver_id, constructor_id, engine_manufacturer_id, car_number,
           grid_position, grid_status, finish_position, finish_status, points,
           completed_laps, retirement_reason, 'RACE' AS session_type
    FROM {silver}.race_results
    UNION ALL
    SELECT race_id, season, round, driver_id, constructor_id, engine_manufacturer_id, car_number,
           grid_position, grid_status, finish_position, finish_status, points,
           completed_laps, retirement_reason, 'SPRINT' AS session_type
    FROM {silver}.sprint_results
), results AS (
SELECT race_id, season, round, session_type, driver_id, constructor_id, engine_manufacturer_id, car_number,
       grid_position, grid_status, finish_position, finish_status,
       COALESCE(points, CAST(0 AS DECIMAL(10,2))) AS points,
       completed_laps, retirement_reason,
       COALESCE(session_type = 'RACE' AND finish_position = 1, FALSE) AS is_race_win,
       COALESCE(session_type = 'RACE' AND finish_position BETWEEN 1 AND 3, FALSE) AS is_race_podium,
       COALESCE(points > 0, FALSE) AS has_points,
       CASE WHEN grid_position > 0 AND finish_position > 0 AND retirement_reason IS NULL
            THEN grid_position - finish_position END AS positions_gained,
       {release_seq} AS _release_seq
FROM sessions
)
SELECT f.*, d.driver_name, c.constructor_name
FROM results f
JOIN {silver}.drivers d ON f.driver_id = d.driver_id
JOIN {silver}.constructors c ON f.constructor_id = c.constructor_id
""")
