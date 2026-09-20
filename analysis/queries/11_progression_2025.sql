WITH all_rounds AS (
    SELECT DISTINCT season, round, race_id FROM explore.races WHERE season = 2025
), drivers AS (
    SELECT driver_id, driver_name FROM analytics.v_driver_season WHERE season = 2025
), points AS (
    SELECT a.season, a.round, a.race_id, d.driver_id, d.driver_name,
           COALESCE(p.weekend_points, 0) AS weekend_points
    FROM all_rounds a CROSS JOIN drivers d
    LEFT JOIN analytics.v_season_progression p USING (season, round, race_id, driver_id)
), cumulative AS (
    SELECT *, SUM(weekend_points) OVER (PARTITION BY driver_id ORDER BY round) AS calculated_points
    FROM points
)
SELECT *, MAX(calculated_points) OVER (PARTITION BY round) - calculated_points AS gap_to_calculated_leader
FROM cumulative ORDER BY round, calculated_points DESC, driver_id;
