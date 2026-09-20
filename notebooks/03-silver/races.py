# Databricks notebook source
# MAGIC %md
# MAGIC # Silver: races

# COMMAND ----------
# MAGIC %run ../00-common/context

# COMMAND ----------
require_candidate()

# COMMAND ----------
# MAGIC %md
# MAGIC Validate the complete selected source snapshot before reconciling current rows.

# COMMAND ----------
current_input("races").createOrReplaceTempView("source_rows")
clean = spark.sql(f"""
SELECT
    CAST(NULLIF(`id`, '') AS BIGINT) AS race_id,
    CAST(NULLIF(`year`, '') AS BIGINT) AS season,
    CAST(NULLIF(`round`, '') AS BIGINT) AS round,
    CAST(NULLIF(`date`, '') AS DATE) AS race_date,
    NULLIF(`grandPrixId`, '') AS grand_prix_id,
    NULLIF(`officialName`, '') AS race_name,
    NULLIF(`circuitId`, '') AS circuit_id,
    {release_seq} AS _release_seq
FROM source_rows
WHERE CAST(year AS BIGINT) >= {min_season}
""")
check_rows(clean, ["race_id"], ["race_id","season","round","race_date","circuit_id"])
if clean.filter(f"season > {year}").limit(1).count():
    raise ValueError("Unexpected future season")
require_current(f"{silver}.circuits")
check_reference(clean, spark.table(f"{silver}.circuits"), ["circuit_id"])

# COMMAND ----------
# MAGIC %md
# MAGIC MERGE is batch-based here. Deletion is safe only after the full-snapshot checks above.

# COMMAND ----------
clean.createOrReplaceTempView("clean_rows")
spark.sql(f"""
CREATE TABLE IF NOT EXISTS {silver}.races USING DELTA
AS SELECT * FROM clean_rows WHERE 1 = 0
""")
spark.sql(f"""
MERGE INTO {silver}.races t
USING clean_rows s
ON t.race_id = s.race_id
WHEN MATCHED THEN UPDATE SET *
WHEN NOT MATCHED THEN INSERT *
WHEN NOT MATCHED BY SOURCE THEN DELETE
""")
check_rows(spark.table(f"{silver}.races"), ["race_id"], ["race_id","season","round","race_date","circuit_id"], clean.count())
