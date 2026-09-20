SELECT s.driver_name, s.source_position, s.source_points, s.race_points, s.sprint_points,
       s.race_wins, s.race_podiums, s.points_difference,
       COUNT(*) FILTER (WHERE r.started) AS starts,
       COUNT(*) FILTER (WHERE r.started AND r.finished) AS finishes,
       COUNT(*) FILTER (WHERE r.started AND r.points > 0) AS scoring_races,
       ROUND(100.0 * COUNT(*) FILTER (WHERE r.started AND r.points > 0) /
             NULLIF(COUNT(*) FILTER (WHERE r.started), 0), 1) AS scoring_pct,
       ROUND(AVG(r.finish_position) FILTER (WHERE r.finished AND r.started), 2) AS mean_finish_when_finished
FROM analytics.v_driver_season s
JOIN explore.races r USING (season, driver_id)
WHERE s.season = 2025
GROUP BY ALL ORDER BY s.source_position;
