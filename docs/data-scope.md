# Data Scope

The active snapshot is F1DB `v2026.14.0`, processed from season 1950 onward. It covers 1950-2026; 2026 is partial and is not a live results feed. Constructor championship records begin with the source's available championship history rather than 1950.

Three pinned releases are retained to demonstrate source revisions, Auto Loader schema evolution, replay safety, and driver identity SCD2:

| Release | Role |
| --- | --- |
| `v2026.8.1` | Initial snapshot |
| `v2026.8.2` | Revised snapshot and added race columns |
| `v2026.14.0` | Current project snapshot with later event results |

Bronze retains all three source snapshots. Current Silver and Gold represent only the configured latest complete snapshot. Driver history is the exception: it records identity changes observed while processing releases in order.

Constructor standings use season, constructor, and engine grain. A constructor can therefore have multiple engine entries in one season. Excluded-only entries such as McLaren 2007 are retained with their source status. Driver and constructor career wins and podiums come from detailed Race results, while championships come from source annual standings.

Source standings and calculated event totals are intentionally separate. Historical scoring adjustments and an incomplete source update can make them differ; the pipeline does not silently replace one with the other.
