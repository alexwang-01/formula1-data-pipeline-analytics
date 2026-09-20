SELECT season, COUNT(*) AS race_entries, COUNT(DISTINCT race_id) AS races,
       MIN(race_date) AS first_race, MAX(race_date) AS last_race,
       COUNT(*) FILTER (WHERE race_date > DATE '2026-09-16') AS future_dated_entries,
       COUNT(*) FILTER (WHERE qualifying_position IS NOT NULL) AS with_qualifying_position,
       COUNT(*) FILTER (WHERE pit_stops IS NOT NULL) AS with_pit_stop_count,
       COUNT(*) FILTER (WHERE gap_ms IS NOT NULL) AS with_gap_ms,
       COUNT(*) FILTER (WHERE finished) AS finishers,
       COUNT(*) FILTER (WHERE NOT started) AS non_starters
FROM explore.races GROUP BY season ORDER BY season;
