-- A shared car counts once for the constructor, even with multiple drivers.
WITH cars AS (
    SELECT constructor_id, race_id, car_number, MAX(constructor_name) AS constructor_name,
           MIN(season) AS season,
           MAX(CASE WHEN is_race_win THEN 1 ELSE 0 END) AS race_win,
           MAX(CASE WHEN is_race_podium THEN 1 ELSE 0 END) AS race_podium
    FROM f1pa_gold.session_results
    WHERE session_type = 'RACE'
    GROUP BY constructor_id, race_id, car_number
), results AS (
    SELECT constructor_id, MAX(constructor_name) AS constructor_name,
           MIN(season) AS first_season, MAX(season) AS last_season,
           COUNT(DISTINCT race_id) AS race_weekends,
           SUM(race_win) AS race_wins, SUM(race_podium) AS race_podiums
    FROM cars GROUP BY constructor_id
), titles AS (
    SELECT constructor_id, SUM(CASE WHEN championship_won THEN 1 ELSE 0 END) AS championships
    FROM f1pa_gold.constructor_season GROUP BY constructor_id
), career AS (
    SELECT r.*, COALESCE(t.championships, 0) AS championships
    FROM results r LEFT JOIN titles t ON r.constructor_id = t.constructor_id
)
SELECT *,
       ROW_NUMBER() OVER (ORDER BY championships DESC, race_wins DESC, constructor_id) AS titles_rank,
       ROW_NUMBER() OVER (ORDER BY race_wins DESC, race_podiums DESC, constructor_id) AS wins_rank,
       ROW_NUMBER() OVER (ORDER BY race_podiums DESC, race_wins DESC, constructor_id) AS podiums_rank
FROM career
ORDER BY championships DESC, race_wins DESC, constructor_name
