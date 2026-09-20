-- Use race facts, not annual standings, which omit some historical participants.
WITH results AS (
    SELECT driver_id, MAX(driver_name) AS driver_name,
           MIN(season) AS first_season, MAX(season) AS last_season,
           COUNT(DISTINCT race_id) AS race_entries,
           COUNT(DISTINCT CASE WHEN is_race_win THEN race_id END) AS race_wins,
           COUNT(DISTINCT CASE WHEN is_race_podium THEN race_id END) AS race_podiums
    FROM f1pa_gold.session_results
    WHERE session_type = 'RACE'
    GROUP BY driver_id
), titles AS (
    SELECT driver_id, SUM(CASE WHEN championship_won THEN 1 ELSE 0 END) AS championships
    FROM f1pa_gold.driver_season
    GROUP BY driver_id
), career AS (
    SELECT r.*, COALESCE(t.championships, 0) AS championships
    FROM results r LEFT JOIN titles t ON r.driver_id = t.driver_id
)
SELECT *,
       ROW_NUMBER() OVER (ORDER BY championships DESC, race_wins DESC, driver_id) AS titles_rank,
       ROW_NUMBER() OVER (ORDER BY race_wins DESC, race_podiums DESC, driver_id) AS wins_rank,
       ROW_NUMBER() OVER (ORDER BY race_podiums DESC, race_wins DESC, driver_id) AS podiums_rank
FROM career
ORDER BY championships DESC, race_wins DESC, driver_name
