WITH season_baseline AS (
    SELECT season, driver_id, AVG(points) AS mean_other_race_points,
           COUNT(*) AS other_races
    FROM explore.recent WHERE started AND country_id <> 'singapore' GROUP BY ALL
)
SELECT r.season, r.driver_name, r.constructor_name, r.grid_position, r.finish_position,
       r.finish_status, r.retirement_reason, r.points AS singapore_points,
       b.other_races, ROUND(b.mean_other_race_points, 2) AS mean_other_race_points,
       ROUND(r.points - b.mean_other_race_points, 2) AS difference_from_other_races
FROM explore.recent r JOIN season_baseline b USING (season, driver_id)
WHERE r.country_id = 'singapore' AND r.started
ORDER BY r.season DESC, difference_from_other_races DESC;
