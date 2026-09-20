SELECT circuit_name, circuit_type, COUNT(DISTINCT race_id) AS races,
       COUNT(*) FILTER (WHERE started) AS starts,
       COUNT(*) FILTER (WHERE started AND NOT finished) AS non_finishes,
       ROUND(100.0 * COUNT(*) FILTER (WHERE started AND NOT finished) / NULLIF(COUNT(*) FILTER (WHERE started), 0), 1) AS non_finish_pct,
       COUNT(*) FILTER (WHERE grid_position = 1 AND started) AS p1_starts,
       COUNT(*) FILTER (WHERE grid_position = 1 AND finish_position = 1 AND started) AS p1_wins,
       COUNT(*) FILTER (WHERE grid_position > 0 AND finished AND started) AS valid_position_changes,
       ROUND(AVG(grid_position - finish_position) FILTER (WHERE grid_position > 0 AND finished AND started), 2) AS mean_net_gain_finishers
FROM explore.recent GROUP BY ALL ORDER BY circuit_name;
