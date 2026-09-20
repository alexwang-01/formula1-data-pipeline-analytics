# Databricks notebook source
# MAGIC %md
# MAGIC # Gold: constructor_season

# COMMAND ----------
from pyspark import pipelines as dp

catalog = spark.conf.get("f1.catalog")
release_tag = spark.conf.get("f1.release_tag")
release_seq = int(spark.conf.get("f1.release_seq"))
min_season = int(spark.conf.get("f1.min_season"))
bronze = f"{catalog}.f1pa_sdp_bronze"
silver = f"{catalog}.f1pa_sdp_silver"
gold = f"{catalog}.f1pa_sdp_gold"


@dp.materialized_view(name=f"{gold}.constructor_season")
@dp.expect_or_fail("required_fields", "season IS NOT NULL AND constructor_id IS NOT NULL AND engine_manufacturer_id IS NOT NULL AND source_points IS NOT NULL")
def gold_constructor_season():
    return spark.sql(f"""
WITH car_results AS (
    SELECT season, constructor_id, engine_manufacturer_id, race_id, session_type, car_number,
           SUM(points) AS points,
           MAX(CASE WHEN is_race_win THEN 1 ELSE 0 END) AS race_win,
           MAX(CASE WHEN is_race_podium THEN 1 ELSE 0 END) AS race_podium
    FROM {gold}.session_results
    GROUP BY season, constructor_id, engine_manufacturer_id, race_id, session_type, car_number
), totals AS (
    SELECT season, constructor_id, engine_manufacturer_id, SUM(points) AS calculated_points,
           COUNT(DISTINCT CASE WHEN session_type = 'RACE' THEN race_id END) AS race_weekends,
           SUM(CASE WHEN session_type = 'RACE' THEN 1 ELSE 0 END) AS race_car_entries,
           SUM(race_win) AS race_wins,
           SUM(race_podium) AS race_podiums
    FROM car_results
    GROUP BY season, constructor_id, engine_manufacturer_id
), standings AS (
    SELECT s.* FROM {silver}.constructor_standings s
    WHERE s.entry_category = 'RANKED' OR NOT EXISTS (
        SELECT 1 FROM {silver}.constructor_standings ranked
        WHERE ranked.season = s.season AND ranked.constructor_id = s.constructor_id
          AND ranked.engine_manufacturer_id = s.engine_manufacturer_id
          AND ranked.entry_category = 'RANKED'
    )
)
SELECT {release_seq} AS _release_seq, s.season, s.constructor_id, d.constructor_name,
       d.country_id, s.engine_manufacturer_id, s.entry_category, s.standing AS source_position, s.standing_status,
       s.points AS source_points, s.championship_won,
       COALESCE(t.calculated_points, 0) AS calculated_points,
       COALESCE(t.calculated_points, 0) - s.points AS points_difference,
       COALESCE(t.race_weekends, 0) AS race_weekends,
       COALESCE(t.race_car_entries, 0) AS race_car_entries,
       COALESCE(t.race_wins, 0) AS race_wins,
       COALESCE(t.race_podiums, 0) AS race_podiums
FROM standings s
JOIN {silver}.constructors d ON s.constructor_id = d.constructor_id
LEFT JOIN totals t ON s.season = t.season AND s.constructor_id = t.constructor_id
    AND s.engine_manufacturer_id = t.engine_manufacturer_id
""")
