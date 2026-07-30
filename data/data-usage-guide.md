# Data Usage Guide

## Project Context

This project was developed as a hands-on learning implementation based on the Udemy course *Azure Databricks & Spark for Data Engineers: Hands-on Project*. The landing files are used to practise incremental ingestion, Delta Lake processing, medallion architecture, and Lakeflow Jobs orchestration.

## Batch Layout

The practice data is organized into 24 batch folders named `2025-01` through `2025-24`. The first batch establishes the historical baseline and the first 2025 race round. The remaining folders simulate new race batches arriving over time.

Each batch follows this general layout:

```text
landing/
+-- 2025-01/
|   +-- circuits.csv
|   +-- races.csv
|   +-- constructors.json
|   +-- drivers.json
|   +-- results/
|   |   +-- results_<season>.json
|   +-- sprints/
|       +-- sprints_<season>.json
+-- 2025-02/
+-- ...
+-- 2025-24/
```

The files are uploaded to the ADLS landing path exposed through the Unity Catalog volume:

```text
/Volumes/formula1_incr/landing/files/
```

## How the Pipeline Uses the Data

1. The orchestration job lists the landing folders.
2. The batch control table identifies which folders are already `in_progress` or `completed`.
3. The earliest unprocessed folder becomes the next `p_batch_id`.
4. Bronze reads only that batch and records its source metadata.
5. Silver and Gold merge the batch into the accumulated analytical tables.
6. The batch is marked `completed` after the incremental refresh succeeds.

Repeated orchestration runs gradually process all available folders. The standings views and AI/BI dashboard read the accumulated Gold tables rather than a single raw batch.
