WITH contribution AS (
    SELECT season, constructor_id, constructor_name, driver_id, driver_name,
           SUM(points) AS earned_points,
           COUNT(*) FILTER (WHERE session_type = 'RACE') AS race_entries
    FROM analytics.v_race_performance WHERE season BETWEEN 2023 AND 2025
    GROUP BY ALL
)
SELECT *, ROUND(100.0 * earned_points /
    NULLIF(SUM(earned_points) OVER (PARTITION BY season, constructor_id), 0), 1) AS share_of_earned_team_points
FROM contribution ORDER BY season DESC, constructor_name, earned_points DESC;
