WITH weekends AS (
    SELECT season, race_id, constructor_name, COUNT(*) AS entries,
           COUNT(*) FILTER (WHERE started) AS starters,
           COUNT(*) FILTER (WHERE started AND finished) AS finishers,
           COUNT(*) FILTER (WHERE started AND points > 0) AS scorers
    FROM explore.recent GROUP BY ALL
)
SELECT season, constructor_name, COUNT(*) AS weekends,
       COUNT(*) FILTER (WHERE entries = 2 AND starters = 2) AS two_start_weekends,
       COUNT(*) FILTER (WHERE entries = 2 AND starters = 2 AND finishers = 2) AS both_finished,
       COUNT(*) FILTER (WHERE entries = 2 AND starters = 2 AND scorers = 2) AS both_scored,
       ROUND(100.0 * COUNT(*) FILTER (WHERE entries = 2 AND starters = 2 AND scorers = 2) /
             NULLIF(COUNT(*) FILTER (WHERE entries = 2 AND starters = 2), 0), 1) AS double_score_pct
FROM weekends GROUP BY season, constructor_name ORDER BY season DESC, double_score_pct DESC;
