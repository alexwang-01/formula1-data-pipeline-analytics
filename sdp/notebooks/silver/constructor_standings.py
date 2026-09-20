# Databricks notebook source
# MAGIC %md
# MAGIC # Silver: constructor_standings

# COMMAND ----------
from pyspark import pipelines as dp

catalog = spark.conf.get("f1.catalog")
release_tag = spark.conf.get("f1.release_tag")
release_seq = int(spark.conf.get("f1.release_seq"))
min_season = int(spark.conf.get("f1.min_season"))
bronze = f"{catalog}.f1pa_sdp_bronze"
silver = f"{catalog}.f1pa_sdp_silver"
gold = f"{catalog}.f1pa_sdp_gold"


@dp.materialized_view(name=f"{silver}.constructor_standings")
@dp.expect_or_fail("required_fields", "season IS NOT NULL AND constructor_id IS NOT NULL AND engine_manufacturer_id IS NOT NULL AND standing_status IS NOT NULL AND championship_won IS NOT NULL")
def silver_constructor_standings():
    return spark.sql(f"""
SELECT
    CAST(NULLIF(`year`, '') AS BIGINT) AS season,
    NULLIF(`constructorId`, '') AS constructor_id,
    NULLIF(`engineManufacturerId`, '') AS engine_manufacturer_id,
    CAST(NULLIF(`positionNumber`, '') AS BIGINT) AS standing,
    NULLIF(`positionText`, '') AS standing_status,
    CAST(NULLIF(`points`, '') AS DECIMAL(10,2)) AS points,
    CAST(NULLIF(`championshipWon`, '') AS BOOLEAN) AS championship_won,
    CASE WHEN NULLIF(positionNumber, '') IS NOT NULL THEN 'RANKED' ELSE positionText END AS entry_category,
    {release_seq} AS _release_seq
FROM (SELECT * FROM {bronze}.constructor_standings WHERE release_tag = '{release_tag}') source_rows
WHERE CAST(year AS BIGINT) >= {min_season}
""")
