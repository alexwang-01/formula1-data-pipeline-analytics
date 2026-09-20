# Databricks notebook source
# MAGIC %md
# MAGIC # Gold: race_dimension

# COMMAND ----------
from pyspark import pipelines as dp

catalog = spark.conf.get("f1.catalog")
release_tag = spark.conf.get("f1.release_tag")
release_seq = int(spark.conf.get("f1.release_seq"))
min_season = int(spark.conf.get("f1.min_season"))
bronze = f"{catalog}.f1pa_sdp_bronze"
silver = f"{catalog}.f1pa_sdp_silver"
gold = f"{catalog}.f1pa_sdp_gold"


@dp.materialized_view(name=f"{gold}.race_dimension")
@dp.expect_or_fail("required_fields", "race_id IS NOT NULL AND season IS NOT NULL AND round IS NOT NULL")
def gold_race_dimension():
    return spark.sql(f"""
SELECT r.race_id, r.season, r.round, r.race_date, r.race_name,
       r.grand_prix_id, r.circuit_id, c.circuit_name, c.country_id, c.circuit_type,
       {release_seq} AS _release_seq
FROM {silver}.races r
JOIN {silver}.circuits c ON r.circuit_id = c.circuit_id
""")
