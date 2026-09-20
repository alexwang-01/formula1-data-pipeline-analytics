# Databricks notebook source
# MAGIC %md
# MAGIC # Silver: races

# COMMAND ----------
from pyspark import pipelines as dp

catalog = spark.conf.get("f1.catalog")
release_tag = spark.conf.get("f1.release_tag")
release_seq = int(spark.conf.get("f1.release_seq"))
min_season = int(spark.conf.get("f1.min_season"))
bronze = f"{catalog}.f1pa_sdp_bronze"
silver = f"{catalog}.f1pa_sdp_silver"
gold = f"{catalog}.f1pa_sdp_gold"


@dp.materialized_view(name=f"{silver}.races")
@dp.expect_or_fail("required_fields", "race_id IS NOT NULL AND season IS NOT NULL AND round IS NOT NULL AND race_date IS NOT NULL AND circuit_id IS NOT NULL")
def silver_races():
    return spark.sql(f"""
SELECT
    CAST(NULLIF(`id`, '') AS BIGINT) AS race_id,
    CAST(NULLIF(`year`, '') AS BIGINT) AS season,
    CAST(NULLIF(`round`, '') AS BIGINT) AS round,
    CAST(NULLIF(`date`, '') AS DATE) AS race_date,
    NULLIF(`grandPrixId`, '') AS grand_prix_id,
    NULLIF(`officialName`, '') AS race_name,
    NULLIF(`circuitId`, '') AS circuit_id,
    {release_seq} AS _release_seq
FROM (SELECT * FROM {bronze}.races WHERE release_tag = '{release_tag}') source_rows
WHERE CAST(year AS BIGINT) >= {min_season}
""")
