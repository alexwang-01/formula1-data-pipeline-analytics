# Databricks notebook source
# MAGIC %md
# MAGIC # Silver: constructors

# COMMAND ----------
from pyspark import pipelines as dp

catalog = spark.conf.get("f1.catalog")
release_tag = spark.conf.get("f1.release_tag")
release_seq = int(spark.conf.get("f1.release_seq"))
min_season = int(spark.conf.get("f1.min_season"))
bronze = f"{catalog}.f1pa_sdp_bronze"
silver = f"{catalog}.f1pa_sdp_silver"
gold = f"{catalog}.f1pa_sdp_gold"


@dp.materialized_view(name=f"{silver}.constructors")
@dp.expect_or_fail("required_fields", "constructor_id IS NOT NULL AND constructor_name IS NOT NULL")
def silver_constructors():
    return spark.sql(f"""
SELECT
    NULLIF(`id`, '') AS constructor_id,
    NULLIF(`name`, '') AS constructor_name,
    NULLIF(`countryId`, '') AS country_id,
    {release_seq} AS _release_seq
FROM (SELECT * FROM {bronze}.constructors WHERE release_tag = '{release_tag}') source_rows

""")
