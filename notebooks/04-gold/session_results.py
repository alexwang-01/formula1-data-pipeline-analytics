# Databricks notebook source
# MAGIC %md
# MAGIC # Gold: session results
# MAGIC Combine Race and Sprint entries and join driver/team names at the result grain.

# COMMAND ----------
# MAGIC %run ../00-common/context

# COMMAND ----------
require_candidate()
require_current(f"{silver}.race_results", f"{silver}.sprint_results",
                f"{silver}.drivers", f"{silver}.constructors")
output = spark.sql(f"""
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
expected = spark.table(f"{silver}.race_results").count() + spark.table(f"{silver}.sprint_results").count()
check_rows(output, ["race_id", "session_type", "driver_id", "car_number"],
           ["race_id", "session_type", "driver_id", "constructor_id", "engine_manufacturer_id", "car_number",
            "driver_name", "constructor_name"], expected)
if expected == 0 or output.filter("points < 0").limit(1).count():
    raise ValueError("Session results must be nonempty and have nonnegative points")

# COMMAND ----------
# MAGIC %md
# MAGIC Silver already checked references. The row-count/key checks above protect the new name joins.

# COMMAND ----------
(output.write.format("delta").mode("overwrite")
    .option("overwriteSchema", "true")
    .saveAsTable(f"{gold}.session_results"))
check_rows(spark.table(f"{gold}.session_results"),
           ["race_id", "session_type", "driver_id", "car_number"],
           ["race_id", "session_type", "driver_id", "car_number"], expected)
mark_complete("gold_session_results")
