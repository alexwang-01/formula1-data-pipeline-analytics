SELECT 'race_profile_join_row_delta' AS check_name,
 (SELECT COUNT(*) FROM explore.races) - (SELECT COUNT(*) FROM silver.race_results) AS failures
UNION ALL SELECT 'race_profile_duplicate_grain', COUNT(*) FROM (
 SELECT race_id, driver_id, car_number FROM explore.races GROUP BY ALL HAVING COUNT(*) > 1)
UNION ALL SELECT 'circuits_missing_for_races', COUNT(*)
 FROM silver.races r ANTI JOIN silver.circuits c USING (circuit_id)
UNION ALL SELECT 'drivers_missing_for_race_results', COUNT(*)
 FROM silver.race_results r ANTI JOIN silver.drivers d USING (driver_id)
UNION ALL SELECT 'constructors_missing_for_race_results', COUNT(*)
 FROM silver.race_results r ANTI JOIN silver.constructors c USING (constructor_id)
UNION ALL SELECT 'races_missing_for_race_results', COUNT(*)
 FROM silver.race_results r ANTI JOIN silver.races d USING (race_id, season, round)
UNION ALL SELECT 'drivers_missing_for_sprint_results', COUNT(*)
 FROM silver.sprint_results r ANTI JOIN silver.drivers d USING (driver_id)
UNION ALL SELECT 'constructors_missing_for_sprint_results', COUNT(*)
 FROM silver.sprint_results r ANTI JOIN silver.constructors c USING (constructor_id)
UNION ALL SELECT 'races_missing_for_sprint_results', COUNT(*)
 FROM silver.sprint_results r ANTI JOIN silver.races d USING (race_id, season, round)
UNION ALL SELECT 'drivers_missing_for_standings', COUNT(*)
 FROM silver.driver_standings r ANTI JOIN silver.drivers d USING (driver_id)
UNION ALL SELECT 'constructors_missing_for_standings', COUNT(*)
 FROM silver.constructor_standings r ANTI JOIN silver.constructors c USING (constructor_id)
UNION ALL SELECT 'more_than_two_recent_team_entries', COUNT(*) FROM (
 SELECT race_id, constructor_id FROM explore.recent GROUP BY ALL HAVING COUNT(*) > 2)
UNION ALL SELECT 'future_dated_results', COUNT(*) FROM explore.races WHERE race_date > DATE '2026-09-16'
UNION ALL SELECT 'non_finishers_with_points_recent', COUNT(*) FROM explore.recent WHERE NOT finished AND points > 0
UNION ALL SELECT 'driver_points_mismatches_2023_2025', COUNT(*) FROM analytics.v_driver_season
 WHERE season BETWEEN 2023 AND 2025 AND source_points <> calculated_points
UNION ALL SELECT 'constructor_points_mismatches_2023_2025', COUNT(*) FROM analytics.v_constructor_season
 WHERE season BETWEEN 2023 AND 2025 AND source_points <> calculated_points
UNION ALL SELECT 'missing_recent_race_results', COUNT(*) FROM silver.races r
 ANTI JOIN silver.race_results f USING (race_id) WHERE r.season BETWEEN 2023 AND 2025;
