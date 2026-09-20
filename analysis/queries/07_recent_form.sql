WITH windows AS (
    SELECT *, MAX(round) OVER (PARTITION BY season) AS last_round FROM explore.recent
)
SELECT season, driver_name,
       CASE WHEN round > last_round - 5 THEN 'Last 5 rounds' ELSE 'Earlier rounds' END AS period,
       COUNT(*) FILTER (WHERE started) AS starts,
       SUM(points) AS race_points,
       ROUND(SUM(points) / NULLIF(COUNT(*) FILTER (WHERE started), 0), 2) AS race_points_per_start,
       ROUND(100.0 * COUNT(*) FILTER (WHERE started AND points > 0) / NULLIF(COUNT(*) FILTER (WHERE started), 0), 1) AS scoring_pct
FROM windows GROUP BY ALL ORDER BY season DESC, driver_name, period;
