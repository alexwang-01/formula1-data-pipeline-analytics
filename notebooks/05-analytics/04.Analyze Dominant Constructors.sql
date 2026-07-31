-- Databricks notebook source
-- MAGIC %md
-- MAGIC # Analyze Dominant Constructors
-- MAGIC
-- MAGIC Aggregate each championship-winning constructor's results across
-- MAGIC seasons and calculate a project-defined greatness score:
-- MAGIC
-- MAGIC `championships * 100 + wins * 10 + podiums * 3`

-- COMMAND ----------

WITH constructor_metrics AS
(
    SELECT
        constructor_name,
        SUM(race_starts) AS race_starts,
        SUM(number_of_wins) AS total_wins,
        SUM(number_of_podiums) AS total_podiums,
        SUM(CASE WHEN standing = 1 THEN 1 ELSE 0 END) AS total_championships
    FROM formula1_incr.gold.v_constructor_standing
    GROUP BY constructor_name
    HAVING SUM(CASE WHEN standing = 1 THEN 1 ELSE 0 END) > 0
)
SELECT
    constructor_name,
    total_wins,
    total_podiums,
    total_championships,
    race_starts,
    (total_championships * 100)
        + (total_wins * 10)
        + (total_podiums * 3) AS greatness_score
FROM constructor_metrics
ORDER BY greatness_score DESC;
