SELECT season, round, race_name, driver_name, constructor_name,
       grid_position, finish_position, finish_status, retirement_reason, points
FROM explore.races WHERE season = 2025 ORDER BY round, driver_id LIMIT 5;
