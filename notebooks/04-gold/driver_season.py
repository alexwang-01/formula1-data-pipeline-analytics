# Databricks notebook source
# MAGIC %md
# MAGIC # Gold: driver season
# MAGIC Join driver identity and source standings with computed Race/Sprint totals.
# MAGIC Source points remain separate from earned points; differences are not silently corrected.
# MAGIC Entries and podiums count distinct races, including historical shared-car results.

# COMMAND ----------
# MAGIC %run ../00-common/context

# COMMAND ----------
require_candidate()
require_current(f"{silver}.drivers", f"{silver}.driver_standings", f"{gold}.session_results")
output = spark.sql(f"""
WITH totals AS (
    SELECT season, driver_id,
           SUM(CASE WHEN session_type = 'RACE' THEN points ELSE 0 END) AS race_points,
           SUM(CASE WHEN session_type = 'SPRINT' THEN points ELSE 0 END) AS sprint_points,
           SUM(points) AS calculated_points,
           COUNT(DISTINCT CASE WHEN session_type = 'RACE' THEN race_id END) AS race_entries,
           COUNT(DISTINCT CASE WHEN is_race_win THEN race_id END) AS race_wins,
           COUNT(DISTINCT CASE WHEN is_race_podium THEN race_id END) AS race_podiums
    FROM {gold}.session_results
    GROUP BY season, driver_id
)
SELECT {release_seq} AS _release_seq, s.season, s.driver_id, d.driver_name,
       d.nationality_country_id, s.standing AS source_position, s.standing_status,
       s.points AS source_points, s.championship_won,
       COALESCE(t.calculated_points, 0) AS calculated_points,
       COALESCE(t.calculated_points, 0) - s.points AS points_difference,
       COALESCE(t.race_points, 0) AS race_points,
       COALESCE(t.sprint_points, 0) AS sprint_points,
       COALESCE(t.race_entries, 0) AS race_entries,
       COALESCE(t.race_wins, 0) AS race_wins,
       COALESCE(t.race_podiums, 0) AS race_podiums
FROM {silver}.driver_standings s
JOIN {silver}.drivers d ON s.driver_id = d.driver_id
LEFT JOIN totals t ON s.season = t.season AND s.driver_id = t.driver_id
""")
expected = spark.table(f"{silver}.driver_standings").count()
check_rows(output, ["season", "driver_id"], ["season", "driver_id", "source_points"], expected)

# COMMAND ----------
(output.write.format("delta").mode("overwrite")
    .saveAsTable(f"{gold}.driver_season"))
check_rows(spark.table(f"{gold}.driver_season"), ["season", "driver_id"],
           ["season", "driver_id"], expected)
display(output.filter("points_difference <> 0"))
mark_complete("gold_driver_season")
