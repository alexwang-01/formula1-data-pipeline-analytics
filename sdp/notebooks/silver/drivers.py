# Databricks notebook source
# MAGIC %md
# MAGIC # Silver: drivers

# COMMAND ----------
from pyspark import pipelines as dp

catalog = spark.conf.get("f1.catalog")
release_tag = spark.conf.get("f1.release_tag")
release_seq = int(spark.conf.get("f1.release_seq"))
min_season = int(spark.conf.get("f1.min_season"))
bronze = f"{catalog}.f1pa_sdp_bronze"
silver = f"{catalog}.f1pa_sdp_silver"
gold = f"{catalog}.f1pa_sdp_gold"


@dp.materialized_view(name=f"{silver}.drivers")
@dp.expect_or_fail("required_fields", "driver_id IS NOT NULL AND driver_name IS NOT NULL")
def silver_drivers():
    return spark.sql(f"""
SELECT
    NULLIF(`id`, '') AS driver_id,
    NULLIF(`name`, '') AS driver_name,
    NULLIF(`fullName`, '') AS full_name,
    NULLIF(`nationalityCountryId`, '') AS nationality_country_id,
    CAST(NULLIF(`dateOfBirth`, '') AS DATE) AS date_of_birth,
    {release_seq} AS _release_seq
FROM (SELECT * FROM {bronze}.drivers WHERE release_tag = '{release_tag}') source_rows

""")
