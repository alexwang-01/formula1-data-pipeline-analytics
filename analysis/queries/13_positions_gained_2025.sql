SELECT driver_name, COUNT(*) FILTER (WHERE started) AS starts,
       COUNT(*) FILTER (WHERE started AND finished AND grid_position > 0) AS comparable_finishes,
       ROUND(AVG(grid_position - finish_position) FILTER (WHERE started AND finished AND grid_position > 0), 2) AS mean_net_gain,
       MEDIAN(grid_position - finish_position) FILTER (WHERE started AND finished AND grid_position > 0) AS median_net_gain,
       COUNT(*) FILTER (WHERE NOT finished AND started) AS non_finishes,
       COUNT(*) FILTER (WHERE grid_position IS NULL OR grid_position <= 0) AS missing_or_special_grid
FROM explore.recent WHERE season = 2025 GROUP BY driver_name ORDER BY mean_net_gain DESC;
