SELECT 'driver' AS entity_type, season, driver_id AS entity_id,
       source_points, calculated_points, points_difference
FROM analytics.v_driver_season WHERE points_difference <> 0
UNION ALL
SELECT 'constructor', season, constructor_id, source_points, calculated_points, points_difference
FROM analytics.v_constructor_season WHERE points_difference <> 0
ORDER BY season, entity_type, entity_id;
