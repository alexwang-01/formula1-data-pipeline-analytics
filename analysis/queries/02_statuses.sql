SELECT finish_status, retirement_reason, finished, started, COUNT(*) AS entries
FROM explore.recent GROUP BY ALL ORDER BY entries DESC;
