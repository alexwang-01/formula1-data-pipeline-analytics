WITH last_round AS (
 SELECT MAX(round) AS round FROM gold.fact_session_results WHERE season = 2026
), last_points AS (
 SELECT constructor_id, SUM(points) AS last_weekend_points
 FROM gold.fact_session_results WHERE season = 2026 AND round = (SELECT round FROM last_round)
 GROUP BY constructor_id
)
SELECT s.constructor_name, s.source_points, s.calculated_points, s.points_difference,
       (SELECT round FROM last_round) AS last_round,
       p.last_weekend_points, s.calculated_points - p.last_weekend_points AS points_before_last_weekend,
       s.points_difference = p.last_weekend_points AS difference_matches_last_weekend
FROM analytics.v_constructor_season s JOIN last_points p USING (constructor_id)
WHERE season = 2026 ORDER BY s.source_position;
