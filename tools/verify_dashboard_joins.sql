-- Validate the proposed Race Results dataset without creating a cloud object.
WITH joined AS (
    SELECT f.*, r.race_id AS matched_race, r.race_name, r.circuit_name
    FROM f1pa_gold.session_results f
    LEFT JOIN f1pa_gold.race_dimension r
      ON f._release_seq = r._release_seq AND f.race_id = r.race_id
), checks AS (
    SELECT 'joined_rows' AS check_name, COUNT(*) AS actual,
           (SELECT COUNT(*) FROM f1pa_gold.session_results) AS expected FROM joined
    UNION ALL SELECT 'missing_races', COUNT(*), 0 FROM joined WHERE matched_race IS NULL
    UNION ALL SELECT 'missing_display_names', COUNT(*), 0 FROM joined
        WHERE NULLIF(TRIM(driver_name), '') IS NULL OR NULLIF(TRIM(constructor_name), '') IS NULL
           OR NULLIF(TRIM(race_name), '') IS NULL OR NULLIF(TRIM(circuit_name), '') IS NULL
    UNION ALL SELECT 'duplicate_joined_keys', COUNT(*), 0 FROM (
        SELECT race_id, session_type, driver_id, car_number FROM joined
        GROUP BY race_id, session_type, driver_id, car_number HAVING COUNT(*) > 1
    ) duplicates
    UNION ALL SELECT 'race_points_preserved', COALESCE(SUM(points), 0),
        (SELECT COALESCE(SUM(points), 0) FROM f1pa_gold.session_results WHERE session_type = 'RACE')
        FROM joined WHERE session_type = 'RACE'
    UNION ALL SELECT 'sprint_points_preserved', COALESCE(SUM(points), 0),
        (SELECT COALESCE(SUM(points), 0) FROM f1pa_gold.session_results WHERE session_type = 'SPRINT')
        FROM joined WHERE session_type = 'SPRINT'
)
SELECT check_name, actual, expected,
       CASE WHEN actual = expected THEN 'PASS' ELSE 'FAIL' END AS status
FROM checks ORDER BY check_name
