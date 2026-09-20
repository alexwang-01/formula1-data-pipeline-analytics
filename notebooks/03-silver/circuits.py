# Databricks notebook source
# MAGIC %md
# MAGIC # Silver: circuits

# COMMAND ----------
# MAGIC %run ../00-common/context

# COMMAND ----------
require_candidate()

# COMMAND ----------
# MAGIC %md
# MAGIC Validate the complete selected source snapshot before reconciling current rows.

# COMMAND ----------
current_input("circuits").createOrReplaceTempView("source_rows")
clean = spark.sql(f"""
SELECT
    NULLIF(`id`, '') AS circuit_id,
    NULLIF(`name`, '') AS circuit_name,
    NULLIF(`countryId`, '') AS country_id,
    NULLIF(`type`, '') AS circuit_type,
    {release_seq} AS _release_seq
FROM source_rows

""")
check_rows(clean, ["circuit_id"], ["circuit_id","circuit_name"])

# COMMAND ----------
# MAGIC %md
# MAGIC MERGE is batch-based here. Deletion is safe only after the full-snapshot checks above.

# COMMAND ----------
clean.createOrReplaceTempView("clean_rows")
spark.sql(f"""
CREATE TABLE IF NOT EXISTS {silver}.circuits USING DELTA
AS SELECT * FROM clean_rows WHERE 1 = 0
""")
spark.sql(f"""
MERGE INTO {silver}.circuits t
USING clean_rows s
ON t.circuit_id = s.circuit_id
WHEN MATCHED THEN UPDATE SET *
WHEN NOT MATCHED THEN INSERT *
WHEN NOT MATCHED BY SOURCE THEN DELETE
""")
check_rows(spark.table(f"{silver}.circuits"), ["circuit_id"], ["circuit_id","circuit_name"], clean.count())
