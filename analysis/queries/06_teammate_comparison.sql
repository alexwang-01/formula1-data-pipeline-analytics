WITH pairs AS (
    SELECT a.season, a.constructor_name, a.driver_name AS driver_a, b.driver_name AS driver_b,
           a.race_id, a.started AND b.started AS both_started,
           a.started AND b.started AND a.finished AND b.finished AS both_finished,
           a.finish_position AS finish_a, b.finish_position AS finish_b,
           a.qualifying_position AS qualifying_a, b.qualifying_position AS qualifying_b
    FROM explore.recent a JOIN explore.recent b
      ON a.race_id = b.race_id AND a.constructor_id = b.constructor_id AND a.driver_id < b.driver_id
)
SELECT season, constructor_name, driver_a, driver_b, COUNT(*) AS paired_entries,
       COUNT(*) FILTER (WHERE both_started) AS both_started,
       COUNT(*) FILTER (WHERE both_finished) AS comparable_finishes,
       COUNT(*) FILTER (WHERE both_finished AND finish_a < finish_b) AS race_wins_a,
       COUNT(*) FILTER (WHERE both_finished AND finish_b < finish_a) AS race_wins_b,
       COUNT(*) FILTER (WHERE qualifying_a IS NOT NULL AND qualifying_b IS NOT NULL) AS comparable_qualifying,
       COUNT(*) FILTER (WHERE qualifying_a < qualifying_b) AS qualifying_wins_a,
       COUNT(*) FILTER (WHERE qualifying_b < qualifying_a) AS qualifying_wins_b
FROM pairs GROUP BY ALL ORDER BY season DESC, constructor_name, paired_entries DESC;
