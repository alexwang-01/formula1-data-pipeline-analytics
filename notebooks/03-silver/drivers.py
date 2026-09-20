# Databricks notebook source
# MAGIC %md
# MAGIC # Silver: drivers

# COMMAND ----------
# MAGIC %run ../00-common/context

# COMMAND ----------
require_candidate()

# COMMAND ----------
# MAGIC %md
# MAGIC Validate the complete selected source snapshot before reconciling current rows.

# COMMAND ----------
current_input("drivers").createOrReplaceTempView("source_rows")
clean = spark.sql(f"""
SELECT
    NULLIF(`id`, '') AS driver_id,
    NULLIF(`name`, '') AS driver_name,
    NULLIF(`fullName`, '') AS full_name,
    NULLIF(`nationalityCountryId`, '') AS nationality_country_id,
    CAST(NULLIF(`dateOfBirth`, '') AS DATE) AS date_of_birth,
    {release_seq} AS _release_seq
FROM source_rows

""")
check_rows(clean, ["driver_id"], ["driver_id","driver_name"])

# COMMAND ----------
# MAGIC %md
# MAGIC MERGE is batch-based here. Deletion is safe only after the full-snapshot checks above.

# COMMAND ----------
clean.createOrReplaceTempView("clean_rows")
spark.sql(f"""
CREATE TABLE IF NOT EXISTS {silver}.drivers USING DELTA
AS SELECT * FROM clean_rows WHERE 1 = 0
""")
spark.sql(f"""
MERGE INTO {silver}.drivers t
USING clean_rows s
ON t.driver_id = s.driver_id
WHEN MATCHED THEN UPDATE SET *
WHEN NOT MATCHED THEN INSERT *
WHEN NOT MATCHED BY SOURCE THEN DELETE
""")
check_rows(spark.table(f"{silver}.drivers"), ["driver_id"], ["driver_id","driver_name"], clean.count())
