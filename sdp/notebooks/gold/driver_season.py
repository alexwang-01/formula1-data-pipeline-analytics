# Databricks notebook source
# MAGIC %md
# MAGIC # Gold: driver_season

# COMMAND ----------
from pyspark import pipelines as dp

catalog = spark.conf.get("f1.catalog")
release_tag = spark.conf.get("f1.release_tag")
release_seq = int(spark.conf.get("f1.release_seq"))
min_season = int(spark.conf.get("f1.min_season"))
bronze = f"{catalog}.f1pa_sdp_bronze"
silver = f"{catalog}.f1pa_sdp_silver"
gold = f"{catalog}.f1pa_sdp_gold"


@dp.materialized_view(name=f"{gold}.driver_season")
@dp.expect_or_fail("required_fields", "season IS NOT NULL AND driver_id IS NOT NULL AND source_points IS NOT NULL")
def gold_driver_season():
    return spark.sql(f"""
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
