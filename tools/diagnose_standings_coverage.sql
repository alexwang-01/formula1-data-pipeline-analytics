-- Diagnostic only: annual standings are not a complete driver-name lookup.
SELECT f.season, f.race_id, r.race_name, f.driver_id, f.driver_name,
       f.constructor_name, f.finish_status, f.points
FROM f1pa_gold.session_results f
JOIN f1pa_gold.race_dimension r ON f._release_seq = r._release_seq AND f.race_id = r.race_id
LEFT JOIN f1pa_gold.driver_season d
  ON f._release_seq = d._release_seq AND f.season = d.season AND f.driver_id = d.driver_id
WHERE d.driver_id IS NULL
ORDER BY f.season, f.race_id, f.driver_id
