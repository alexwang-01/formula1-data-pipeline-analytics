-- Race-results dashboard dataset; this SELECT creates no persistent view.
-- Wait for the entire Job to succeed before reading multiple Gold tables.
SELECT f._release_seq, f.season, f.round, f.race_id,
       CONCAT(LPAD(CAST(f.round AS STRING), 2, '0'), ' - ',
              UPPER(REPLACE(r.grand_prix_id, '-', ' '))) AS grand_prix,
       r.race_name, r.race_date, r.circuit_id, r.circuit_name, r.country_id,
       f.session_type, f.driver_id, f.driver_name,
       f.constructor_id, f.constructor_name, f.car_number,
       f.grid_position, f.grid_status, f.finish_position, f.finish_status,
       COALESCE(f.finish_position, 9999) AS classification_order,
       CASE WHEN f.finish_position IS NOT NULL THEN 'Classified'
            ELSE f.finish_status END AS result_status,
       f.points, f.completed_laps, f.retirement_reason, f.positions_gained,
       f.is_race_win, f.is_race_podium, f.has_points
FROM f1pa_gold.session_results f
LEFT JOIN f1pa_gold.race_dimension r
  ON f._release_seq = r._release_seq AND f.race_id = r.race_id
