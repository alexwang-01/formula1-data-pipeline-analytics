# Databricks notebook source
# MAGIC %md
# MAGIC # Silver: driver identity history (SCD Type 2)

# COMMAND ----------
# MAGIC %run ../00-common/context

# COMMAND ----------
require_candidate()

# COMMAND ----------
# MAGIC %md
# MAGIC Validity is measured in source release sequence, not historical race time.
# MAGIC Career statistics are intentionally excluded from identity history.

# COMMAND ----------
require_current(f"{silver}.drivers")
spark.table(f"{silver}.drivers").createOrReplaceTempView("current_drivers")
spark.sql(f"""
CREATE TABLE IF NOT EXISTS {silver}.drivers_history (
    driver_id STRING, driver_name STRING, full_name STRING,
    nationality_country_id STRING, date_of_birth DATE,
    valid_from_release BIGINT, valid_to_release BIGINT
) USING DELTA
""")

# COMMAND ----------
# MAGIC %md
# MAGIC 1. Close changed or removed identities. Null-safe equality also detects null changes.

# COMMAND ----------
spark.sql(f"""
MERGE INTO {silver}.drivers_history t
USING current_drivers s
ON t.driver_id = s.driver_id AND t.valid_to_release IS NULL
WHEN MATCHED AND NOT (
    t.driver_name <=> s.driver_name AND t.full_name <=> s.full_name
    AND t.nationality_country_id <=> s.nationality_country_id
    AND t.date_of_birth <=> s.date_of_birth
) THEN UPDATE SET valid_to_release = {release_seq}
WHEN NOT MATCHED BY SOURCE AND t.valid_to_release IS NULL
THEN UPDATE SET valid_to_release = {release_seq}
""")

# COMMAND ----------
# MAGIC %md
# MAGIC 2. Insert identities without a current version. Retrying this step does not duplicate them.

# COMMAND ----------
spark.sql(f"""
INSERT INTO {silver}.drivers_history
SELECT s.driver_id, s.driver_name, s.full_name, s.nationality_country_id,
       s.date_of_birth, {release_seq}, CAST(NULL AS BIGINT)
FROM current_drivers s
LEFT ANTI JOIN {silver}.drivers_history t
ON s.driver_id = t.driver_id AND t.valid_to_release IS NULL
""")
history = spark.table(f"{silver}.drivers_history")
check_rows(history, ["driver_id", "valid_from_release"], ["driver_id", "valid_from_release"])
check_rows(history.filter("valid_to_release IS NULL"), ["driver_id"], ["driver_id"],
           spark.table(f"{silver}.drivers").count())
if history.filter("valid_to_release <= valid_from_release").limit(1).count():
    raise ValueError("Invalid history interval")
mark_complete("silver_drivers_history")
