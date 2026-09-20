# Databricks notebook source
# MAGIC %md
# MAGIC # Silver: constructor_standings

# COMMAND ----------
# MAGIC %run ../00-common/context

# COMMAND ----------
require_candidate()

# COMMAND ----------
# MAGIC %md
# MAGIC Validate the complete selected source snapshot before reconciling current rows.

# COMMAND ----------
current_input("constructor_standings").createOrReplaceTempView("source_rows")
clean = spark.sql(f"""
SELECT
    CAST(NULLIF(`year`, '') AS BIGINT) AS season,
    NULLIF(`constructorId`, '') AS constructor_id,
    NULLIF(`engineManufacturerId`, '') AS engine_manufacturer_id,
    CAST(NULLIF(`positionNumber`, '') AS BIGINT) AS standing,
    NULLIF(`positionText`, '') AS standing_status,
    CAST(NULLIF(`points`, '') AS DECIMAL(10,2)) AS points,
    CAST(NULLIF(`championshipWon`, '') AS BOOLEAN) AS championship_won,
    CASE WHEN NULLIF(positionNumber, '') IS NOT NULL THEN 'RANKED' ELSE positionText END AS entry_category,
    {release_seq} AS _release_seq
FROM source_rows
WHERE CAST(year AS BIGINT) >= {min_season}
""")
check_rows(clean, ["season","constructor_id","engine_manufacturer_id","entry_category"], ["season","constructor_id","engine_manufacturer_id","standing_status","championship_won"])
if clean.filter(f"season > {year}").limit(1).count():
    raise ValueError("Unexpected future season")
require_current(f"{silver}.constructors")
check_reference(clean, spark.table(f"{silver}.constructors"), ["constructor_id"])

# COMMAND ----------
# MAGIC %md
# MAGIC MERGE is batch-based here. Deletion is safe only after the full-snapshot checks above.

# COMMAND ----------
clean.createOrReplaceTempView("clean_rows")
spark.sql(f"""
CREATE TABLE IF NOT EXISTS {silver}.constructor_standings USING DELTA
AS SELECT * FROM clean_rows WHERE 1 = 0
""")
spark.sql(f"""
MERGE INTO {silver}.constructor_standings t
USING clean_rows s
ON t.season = s.season AND t.constructor_id = s.constructor_id
AND t.engine_manufacturer_id = s.engine_manufacturer_id AND t.entry_category = s.entry_category
WHEN MATCHED THEN UPDATE SET *
WHEN NOT MATCHED THEN INSERT *
WHEN NOT MATCHED BY SOURCE THEN DELETE
""")
check_rows(spark.table(f"{silver}.constructor_standings"), ["season","constructor_id","engine_manufacturer_id","entry_category"], ["season","constructor_id","engine_manufacturer_id","standing_status","championship_won"], clean.count())
