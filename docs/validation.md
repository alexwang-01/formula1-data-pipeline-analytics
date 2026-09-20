# Validation

The repository separates local transformation tests from Databricks runtime checks. Passing local SQL does not by itself prove Spark, Auto Loader, Delta, or SDP behavior.

## Local Suite

Run from the repository root:

```powershell
python tools/validate_local.py
```

The suite reads the notebook SQL, uses the pinned original CSV snapshots, and checks:

- source checksums, required columns, row counts, and immutable replay;
- complete-snapshot MERGE inserts, updates, deletions, and same-release retries;
- SCD2 changes, null handling, intervals, and current rows;
- table keys, required fields, Silver references, and Gold grains;
- full 1950-onward history, engine-level constructor standings, shared cars, and excluded entries;
- Manual and SDP SQL parity for all three cloud-tested snapshots;
- the five-page Dashboard datasets, filters, metrics, and non-overlapping layout.

The current suite has 47 tests. It does not start cloud compute.

## Databricks Results

The 22-task Manual Job completed `v2026.14.0` with a 1950 season boundary. The four Gold tables contain:

| Table | Rows |
| --- | ---: |
| `race_dimension` | 1,172 |
| `session_results` | 28,189 |
| `driver_season` | 1,681 |
| `constructor_season` | 720 |

The SDP implementation processed `v2026.8.1`, `v2026.8.2`, and `v2026.14.0`, followed by a repeat of the latest snapshot. Eight current Silver tables and four Gold tables matched Manual in both directions. Driver history matched at 1,147 versions with 917 current rows. See [SDP validation](../sdp/validation.md).

Seven Dashboard dataset checks passed against the same Gold data. See [Dashboard](dashboard.md).

Generated run responses and SQL evidence stay under ignored `local/` directories. Git contains the validation code and summarized results, not credentials, downloaded data, or machine-specific execution logs.

## Boundaries

- The source is pinned F1DB data, not a live feed or an independent audit of official results.
- The 2026 snapshot is partial. Source championship points and calculated event points remain separate when they differ.
- Performance and cost were not benchmarked.
- Cloud resources are triggered on demand; no schedule or continuous pipeline is configured.
