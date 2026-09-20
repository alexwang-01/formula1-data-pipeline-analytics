SELECT season, constructor_id, constructor_name, country_id, engine_manufacturer_id,
       COALESCE(CAST(source_position AS STRING), standing_status) AS position_label,
       CASE WHEN COUNT(*) OVER (PARTITION BY season, constructor_id) > 1
            THEN CONCAT(constructor_name, ' / ', UPPER(engine_manufacturer_id))
            ELSE constructor_name END AS team_entry,
       source_position, COALESCE(source_position, 9999) AS standing_order, standing_status, source_points,
       calculated_points, points_difference,
       race_weekends, race_car_entries, race_wins, race_podiums
FROM f1pa_gold.constructor_season
ORDER BY season DESC, source_position NULLS LAST, constructor_name
