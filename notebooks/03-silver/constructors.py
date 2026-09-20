# Databricks notebook source
# MAGIC %md
# MAGIC # Silver: constructors

# COMMAND ----------
# MAGIC %run ../00-common/context

# COMMAND ----------
require_candidate()

# COMMAND ----------
# MAGIC %md
# MAGIC Validate the complete selected source snapshot before reconciling current rows.

# COMMAND ----------
current_input("constructors").createOrReplaceTempView("source_rows")
clean = spark.sql(f"""
SELECT
    NULLIF(`id`, '') AS constructor_id,
    NULLIF(`name`, '') AS constructor_name,
    NULLIF(`countryId`, '') AS country_id,
    {release_seq} AS _release_seq
FROM source_rows

""")
check_rows(clean, ["constructor_id"], ["constructor_id","constructor_name"])

# COMMAND ----------
# MAGIC %md
# MAGIC MERGE is batch-based here. Deletion is safe only after the full-snapshot checks above.

# COMMAND ----------
clean.createOrReplaceTempView("clean_rows")
spark.sql(f"""
CREATE TABLE IF NOT EXISTS {silver}.constructors USING DELTA
AS SELECT * FROM clean_rows WHERE 1 = 0
""")
spark.sql(f"""
MERGE INTO {silver}.constructors t
USING clean_rows s
ON t.constructor_id = s.constructor_id
WHEN MATCHED THEN UPDATE SET *
WHEN NOT MATCHED THEN INSERT *
WHEN NOT MATCHED BY SOURCE THEN DELETE
""")
check_rows(spark.table(f"{silver}.constructors"), ["constructor_id"], ["constructor_id","constructor_name"], clean.count())
