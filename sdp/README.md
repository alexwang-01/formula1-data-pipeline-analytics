# Formula 1 - SDP Implementation

This directory implements the same transformations as Manual with Lakeflow Spark Declarative Pipelines. It is an alternative engineering implementation, not a second analytical model or Dashboard.

[Read the recorded validation results](validation.md).

## Manual and SDP

| Layer | Manual | SDP |
| --- | --- | --- |
| Bronze | Auto Loader, `writeStream`, checkpoint, AvailableNow | Auto Loader streaming tables; SDP manages writes and checkpoints |
| Current Silver | Complete-snapshot Delta `MERGE` | Materialized views of the selected snapshot |
| Driver history | Explicit SCD2 close and insert logic | `AUTO CDC FROM SNAPSHOT`, SCD Type 2 |
| Gold | SQL followed by Delta overwrite | The same SQL in materialized views |
| Dependencies | YAML `depends_on` between Job tasks | Table reads form the managed pipeline graph |

The Manual Job graph contains 22 notebook tasks. SDP instead contains 21 dataset notebooks: eight Bronze, eight current Silver, one driver-history table, and four Gold materialized views. These nodes appear inside the **pipeline graph**, not as 21 Job tasks.

The surrounding SDP Job has three procedural tasks:

1. Prepare and verify the pinned source snapshot.
2. Start one complete SDP update.
3. Check the resulting Gold and current history before recording completion.

A Job task can start an entire managed pipeline but cannot independently run one table notebook inside it. Splitting these datasets into separate pipelines would duplicate orchestration and managed state.

## Declarative Code

Each dataset notebook uses standard SQL or PySpark and returns a DataFrame:

- `@dp.table` defines an Auto Loader streaming table.
- `@dp.materialized_view` defines a stored query result.
- `@dp.expect_or_fail` rejects invalid required fields or rescued CSV data.
- `dp.create_auto_cdc_from_snapshot_flow` maintains driver SCD2 from ordered snapshots.

There is no custom transformation framework, UDF, manual writer, or manual SCD2 `MERGE` in the SDP dataset notebooks. Gold materialized views store query results, although SDP may fully recompute a view when required; the project does not claim every refresh is incremental.

Driver history reads the verified immutable driver CSV directly with the same five conversions used by current Silver. This avoids asking the first pipeline analysis to read a Silver table that does not exist yet. SDP exposes the resulting release bounds as `__START_AT` and `__END_AT`.

## Boundaries

- Manual and SDP use separate schemas, landing storage, and managed state. See [Storage Map](../docs/storage-map.md).
- Source releases must be processed in ascending order when building history. Repeating the latest release is allowed; rollback is blocked.
- Do not use full refresh on driver history because that clears managed history state.
- The existing Dashboard continues to read Manual Gold. A duplicate SDP Dashboard is unnecessary because the outputs have been compared row by row.
- Deployment and recovery commands are centralized in the [Runbook](../docs/runbook.md).
- Snapshot roles and historical coverage are centralized in [Data Scope](../docs/data-scope.md).

## Verification

Local tests compare every current Silver and Gold row with Manual SQL for all three pinned snapshots. Cloud runs additionally verified native Auto Loader, schema evolution restart, snapshot CDC, same-release replay, checkpoints, keys, references, and SCD2 validity intervals. Exact runs and counts are recorded in [SDP Validation](validation.md).

## References

- [Python pipeline definitions](https://docs.databricks.com/aws/en/ldp/developer/python-dev)
- [AUTO CDC FROM SNAPSHOT](https://docs.databricks.com/aws/en/ldp/developer/ldp-python-ref-apply-changes-from-snapshot)
