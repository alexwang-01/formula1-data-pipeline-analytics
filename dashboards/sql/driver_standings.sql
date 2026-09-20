SELECT season, driver_id, driver_name, nationality_country_id,
       COALESCE(CAST(source_position AS STRING), standing_status) AS position_label,
       source_position, COALESCE(source_position, 9999) AS standing_order, standing_status, source_points,
       calculated_points, points_difference,
       race_points, sprint_points, race_entries, race_wins, race_podiums
FROM f1pa_gold.driver_season
ORDER BY season DESC, source_position NULLS LAST, driver_name
