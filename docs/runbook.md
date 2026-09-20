# Runbook

## Local Checks

Install the two development dependencies from `requirements-dev.txt`, then run:

```powershell
python tools/validate_local.py
```

The local suite uses ignored files under `local/landing/`. Use `tools/fetch_release.py` when the pinned snapshots need to be downloaded again.

## Manual Deployment

The root bundle deploys the 22-task Manual Job and the exported AI/BI Dashboard definition:

```powershell
$catalog = "<catalog-name>"
$warehouseId = "<sql-warehouse-id>"
databricks bundle validate -t dev --profile <profile-name> --var "catalog=$catalog,warehouse_id=$warehouseId"
databricks bundle deploy -t dev --profile <profile-name> --var "catalog=$catalog,warehouse_id=$warehouseId"
```

Deployment updates definitions; it does not execute the Job. A normal run uses `release_tag=v2026.14.0` and `min_season=1950`. Confirm there is no active project run before deployment or execution.

## SDP Deployment

SDP is an isolated bundle with its own schemas and landing volume. Run bundle commands from `sdp/` and keep `release_tag` paired with `release_seq`:

```powershell
databricks bundle validate --profile <profile-name> --var "catalog=$catalog,release_tag=v2026.14.0,release_seq=2026014000"
databricks bundle deploy --profile <profile-name> --var "catalog=$catalog,release_tag=v2026.14.0,release_seq=2026014000"
```

For a fresh SCD2 history, process the three documented snapshots in ascending order. Use the surrounding SDP Job rather than starting the pipeline directly. Do not use full refresh on driver history. See the [SDP guide](../sdp/README.md).

## Dashboard Updates

The Databricks draft is editable in the UI. Before a later bundle deployment, export the latest draft back to `dashboards/formula1.lvdash.json`; otherwise an older local export could replace UI edits.

```powershell
python -m unittest discover -s tests -p test_dashboard.py -v
$env:DATABRICKS_CATALOG = "<catalog-name>"
$env:DATABRICKS_WAREHOUSE_ID = "<sql-warehouse-id>"
$env:DATABRICKS_PROFILE = "<profile-name>"
python tools/verify_dashboard.py
```

Dashboard verification can start the configured SQL warehouse and requests that it stop afterwards. Use `--keep-running` only during an active visual review, then stop it explicitly.

## Recovery

- Manual Bronze retries once for Auto Loader schema evolution; other Manual tasks have no automatic retry.
- Repair failed and dependent tasks with the same release parameters. Do not mix task attempts from different release attempts.
- SDP may restart an update after Auto Loader adds columns. This is expected; the surrounding Job remains the execution boundary.
- Do not delete checkpoints while retaining the corresponding Bronze tables.
- Gold tables update independently. Refresh consumers only after the complete Manual Job succeeds.

No schedule, continuous processing, refresh subscription, or always-on cluster is configured. After cloud checks, confirm Job runs are terminated, SDP is IDLE, and SQL warehouses and clusters are stopped.
