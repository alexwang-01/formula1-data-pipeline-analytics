SELECT season, constructor_id, COUNT(*) AS categories,
       STRING_AGG(entry_category, ', ' ORDER BY entry_category) AS category_list
FROM silver.constructor_standings GROUP BY ALL HAVING COUNT(*) > 1 ORDER BY season, constructor_id;
