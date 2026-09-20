-- Upstream checks only. No dashboard definition, query, or publication is changed.
WITH driver_career AS (
    SELECT driver_id,
           COUNT(DISTINCT CASE WHEN is_race_win THEN race_id END) AS wins,
           COUNT(DISTINCT CASE WHEN is_race_podium THEN race_id END) AS podiums
    FROM f1pa_gold.session_results GROUP BY driver_id
), car_results AS (
    SELECT constructor_id, race_id, car_number,
           MAX(CASE WHEN is_race_win THEN 1 ELSE 0 END) AS wins,
           MAX(CASE WHEN is_race_podium THEN 1 ELSE 0 END) AS podiums
    FROM f1pa_gold.session_results WHERE session_type='RACE'
    GROUP BY constructor_id, race_id, car_number
), constructor_career AS (
    SELECT constructor_id, SUM(wins) AS wins, SUM(podiums) AS podiums
    FROM car_results GROUP BY constructor_id
), checks AS (
    SELECT 'driver_career_vs_source' AS check_name, COUNT(*) AS failures
    FROM f1pa_bronze.drivers b LEFT JOIN driver_career g ON b.id=g.driver_id
    WHERE b.release_tag='v2026.14.0'
      AND (CAST(b.totalRaceWins AS BIGINT) <> COALESCE(g.wins,0)
        OR CAST(b.totalPodiums AS BIGINT) <> COALESCE(g.podiums,0))
    UNION ALL
    SELECT 'constructor_career_vs_source', COUNT(*)
    FROM f1pa_bronze.constructors b LEFT JOIN constructor_career g ON b.id=g.constructor_id
    WHERE b.release_tag='v2026.14.0'
      AND (CAST(b.totalRaceWins AS BIGINT) <> COALESCE(g.wins,0)
        OR CAST(b.totalPodiums AS BIGINT) <> COALESCE(g.podiums,0))
    UNION ALL
    SELECT 'driver_titles_vs_source', COUNT(*)
    FROM f1pa_bronze.drivers b LEFT JOIN (
        SELECT driver_id, SUM(CASE WHEN championship_won THEN 1 ELSE 0 END) AS titles
        FROM f1pa_gold.driver_season GROUP BY driver_id
    ) g ON b.id=g.driver_id
    WHERE b.release_tag='v2026.14.0'
      AND CAST(b.totalChampionshipWins AS BIGINT) <> COALESCE(g.titles,0)
    UNION ALL
    SELECT 'constructor_titles_vs_source', COUNT(*)
    FROM f1pa_bronze.constructors b LEFT JOIN (
        SELECT constructor_id, SUM(CASE WHEN championship_won THEN 1 ELSE 0 END) AS titles
        FROM f1pa_gold.constructor_season GROUP BY constructor_id
    ) g ON b.id=g.constructor_id
    WHERE b.release_tag='v2026.14.0'
      AND CAST(b.totalChampionshipWins AS BIGINT) <> COALESCE(g.titles,0)
    UNION ALL
    SELECT 'session_unique_key', COUNT(*) FROM (
        SELECT race_id,session_type,driver_id,car_number FROM f1pa_gold.session_results
        GROUP BY race_id,session_type,driver_id,car_number HAVING COUNT(*) > 1
    )
    UNION ALL
    SELECT 'constructor_engine_unique_key', COUNT(*) FROM (
        SELECT season,constructor_id,engine_manufacturer_id FROM f1pa_gold.constructor_season
        GROUP BY season,constructor_id,engine_manufacturer_id HAVING COUNT(*) > 1
    )
    UNION ALL
    SELECT 'race_join_coverage', COUNT(*) FROM f1pa_gold.session_results s
    LEFT ANTI JOIN f1pa_gold.race_dimension r
      ON s.race_id=r.race_id AND s.season=r.season AND s.round=r.round
    UNION ALL
    SELECT 'modern_session_coverage', ABS(COUNT(*) - 7814)
    FROM f1pa_gold.session_results WHERE season >= 2010
    UNION ALL
    SELECT 'modern_driver_standings_coverage', ABS(COUNT(*) - 390)
    FROM f1pa_gold.driver_season WHERE season >= 2010
    UNION ALL
    SELECT 'modern_constructor_standings_coverage', ABS(COUNT(*) - 180)
    FROM f1pa_gold.constructor_season WHERE season >= 2010
    UNION ALL
    SELECT 'driver_champions', ABS(
      (SELECT COUNT(*) FROM f1pa_silver.driver_standings WHERE championship_won)
      - (SELECT COUNT(*) FROM f1pa_gold.driver_season WHERE championship_won))
    UNION ALL
    SELECT 'constructor_champions', ABS(
      (SELECT COUNT(*) FROM f1pa_silver.constructor_standings WHERE championship_won)
      - (SELECT COUNT(*) FROM f1pa_gold.constructor_season WHERE championship_won))
    UNION ALL
    SELECT 'latest_release_only', COUNT(*) FROM (
      SELECT _release_seq FROM f1pa_gold.race_dimension UNION ALL
      SELECT _release_seq FROM f1pa_gold.session_results UNION ALL
      SELECT _release_seq FROM f1pa_gold.driver_season UNION ALL
      SELECT _release_seq FROM f1pa_gold.constructor_season
    ) WHERE _release_seq IS NULL OR _release_seq <> 2026014000
    UNION ALL
    SELECT 'completed_expansion', ABS(COUNT(DISTINCT c.task_key) - 5)
    FROM f1pa_ops.release_state r JOIN f1pa_ops.task_completions c
      ON r.release_seq=c.release_seq AND r.attempt_id=c.attempt_id
    WHERE r.release_seq=2026014000 AND r.min_season=1950
      AND c.task_key IN ('silver_drivers_history','gold_race_dimension','gold_session_results',
                        'gold_driver_season','gold_constructor_season')
)
SELECT check_name, failures, CASE WHEN failures=0 THEN 'PASS' ELSE 'FAIL' END AS status
FROM checks ORDER BY check_name;
