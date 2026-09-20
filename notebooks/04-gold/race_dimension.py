# Databricks notebook source
# MAGIC %md
# MAGIC # Gold: race dimension
# MAGIC One row per race, enriched with circuit information.

# COMMAND ----------
# MAGIC %run ../00-common/context

# COMMAND ----------
require_candidate()
require_current(f"{silver}.races", f"{silver}.circuits")
output = spark.sql(f"""
SELECT r.race_id, r.season, r.round, r.race_date, r.race_name,
       r.grand_prix_id, r.circuit_id, c.circuit_name, c.country_id, c.circuit_type,
       {release_seq} AS _release_seq
FROM {silver}.races r
JOIN {silver}.circuits c ON r.circuit_id = c.circuit_id
""")
check_rows(output, ["race_id"], ["race_id", "season", "round"],
           spark.table(f"{silver}.races").count())

# COMMAND ----------
# MAGIC %md
# MAGIC Store the current snapshot as a Delta table; do not create reporting views.

# COMMAND ----------
(output.write.format("delta").mode("overwrite")
    .saveAsTable(f"{gold}.race_dimension"))
check_rows(spark.table(f"{gold}.race_dimension"), ["race_id"], ["race_id"], output.count())
mark_complete("gold_race_dimension")
