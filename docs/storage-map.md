# Storage Map

The repository contains two isolated implementations of the same transformations. Manual and SDP use separate schemas, volumes, checkpoints, and bundle roots. The existing Dashboard reads Manual Gold.

## Repository

| Location | Content | Git |
| --- | --- | --- |
| `notebooks/` | Manual source, Bronze, Silver, SCD2, and Gold notebooks | Included |
| `resources/` | Manual Job and Dashboard bundle definitions | Included |
| `dashboards/` | Exported AI/BI Dashboard and readable dataset SQL | Included |
| `sdp/` | Isolated SDP bundle and 21 dataset notebooks | Included |
| `tests/`, `tools/`, `docs/` | Reproducible checks and documentation | Included |
| `analysis/` | Offline exploration; excluded from bundle sync | Included |
| `local/` | Downloads, credentials, CLI, dependencies, and run evidence | Ignored |
| `.databricks/`, `**/__pycache__/` | Generated deployment and Python caches | Ignored |

The downloaded ZIP and CSV files are reproducible local test inputs. Cloud source tasks download and verify their own copies from the pinned public releases.

## Workspace Code

Manual bundle root:

```text
/Workspace/Users/<workspace-user>/.bundle/formula1-data-pipeline-analytics/dev
```

SDP bundle root:

```text
/Workspace/Users/<workspace-user>/.bundle/formula1-data-pipeline-analytics-sdp/dev
```

These paths store deployed code and bundle metadata. Business data is stored in Unity Catalog managed tables and volumes.

## Manual Objects

| Schema | Active objects |
| --- | --- |
| `<catalog>.f1pa_files` | Landing and state volumes |
| `<catalog>.f1pa_bronze` | Eight append-only source tables |
| `<catalog>.f1pa_silver` | Eight current tables and `drivers_history` |
| `<catalog>.f1pa_gold` | Four Dashboard-ready tables |
| `<catalog>.f1pa_ops` | Release and task-completion state |

Manual Auto Loader state is under:

```text
/Volumes/<catalog>/f1pa_files/state/manual/
```

## SDP Objects

| Schema | Active objects |
| --- | --- |
| `<catalog>.f1pa_sdp_files` | Separate landing volume |
| `<catalog>.f1pa_sdp_bronze` | Eight managed streaming tables |
| `<catalog>.f1pa_sdp_silver` | Eight materialized views and native driver SCD2 |
| `<catalog>.f1pa_sdp_gold` | Four materialized views |
| `<catalog>.f1pa_sdp_ops` | Snapshot execution markers |

SDP manages streaming checkpoints and table storage. Do not manually delete or reuse them for Manual.

## Safety Boundaries

- Reuse checkpoints only with their corresponding tables.
- Run source releases in ascending order when building driver history.
- Use a separate target and separate schemas for experiments with another season scope.
- Do not store Databricks credentials, downloaded archives, generated evidence, or bundle state in Git.
- Deployment changes definitions but does not itself execute the Manual Job. The SDP Job should be used to coordinate source preparation and each pipeline update.
