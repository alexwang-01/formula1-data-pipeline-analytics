SELECT season, race_id, race_date, circuit_layout_id,
       MAX(CASE WHEN finish_position = 1 THEN driver_name END) AS winner,
       MAX(CASE WHEN finish_position = 1 THEN grid_position END) AS winner_grid,
       COUNT(*) FILTER (WHERE started) AS starts,
       COUNT(*) FILTER (WHERE started AND NOT finished) AS non_finishes,
       COUNT(*) FILTER (WHERE finished AND started AND grid_position > 0) AS valid_position_changes,
       ROUND(AVG(grid_position - finish_position) FILTER (WHERE finished AND started AND grid_position > 0), 2) AS mean_net_gain_finishers
FROM explore.races WHERE country_id = 'singapore' AND season <= 2025
GROUP BY ALL ORDER BY season;
