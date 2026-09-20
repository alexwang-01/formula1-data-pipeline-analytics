# SDP Validation

Verified on 20 September 2026 (Singapore time). Manual tables and the existing Dashboard were not changed.

## Cloud Runs

| Input | Result |
| --- | --- |
| v2026.8.1 | Passed after repairing initial table-resolution handling |
| v2026.8.2 | Passed, including automatic schema-change restart |
| v2026.14.0 | Passed |
| v2026.14.0 repeated | Passed; no duplicate snapshot or history rows |

All runs used the same three-task SDP snapshot workflow.
The first-run fix makes the SCD2 callback read the verified driver CSV instead of a Silver table that does not exist during initial graph analysis.

## Results

- All 24 Bronze table/snapshot counts match the original source manifests. Repeating the latest snapshot does not increase them.
- Eight current Silver tables and four Gold tables match Manual in both directions using `EXCEPT ALL`, aligned by column name. No missing rows, extra rows, or duplicate keys were found.
- Driver SCD2 matches Manual's attributes and validity intervals: 1,147 versions, including 917 current versions. Repeating the latest snapshot leaves these unchanged.
- All nine checked Silver references have zero missing parent keys.
- Four added Sprint-related columns in Bronze races match the source CSV values' non-empty counts for each release. SDP automatically restarted the v2026.8.2 update after detecting the schema change.
- All three release markers are COMPLETE. The current local regression suite has 47 passing tests.

| Gold table | Rows |
| --- | ---: |
| race_dimension | 1,172 |
| session_results | 28,189 |
| driver_season | 1,681 |
| constructor_season | 720 |

## Evidence and Boundaries

Local evidence is kept in the ignored `local/sdp-validation/` directory: run records, before/after repeat comparisons, schema-change events, local test output, and the final idle check.
The reusable cloud checker is [verify_sdp.py](../tools/verify_sdp.py). Run it only after the complete SDP Job succeeds and Manual still contains the same latest release.

These checks establish equivalence for the three pinned snapshots, not every possible future source change. Materialized views can recompute their results; not every transformation is claimed to refresh incrementally.
This implementation uses a triggered pipeline with no schedule. At completion, the pipeline was IDLE, the SQL warehouse was STOPPED, and no active Job runs or clusters remained.
