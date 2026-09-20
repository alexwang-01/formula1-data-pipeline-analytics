# Manual Job Task Map

The [Job YAML](../resources/manual.job.yml) defines 22 tasks. All dependencies use ALL_SUCCESS; there are no layout-only barriers.

| Task | Direct prerequisites |
| --- | --- |
| prepare_source | None |
| Each of eight bronze_* tasks | prepare_source |
| silver_drivers | bronze_drivers |
| silver_constructors | bronze_constructors |
| silver_circuits | bronze_circuits |
| silver_races | bronze_races, silver_circuits |
| silver_race_results | bronze_race_results, silver_races, silver_drivers, silver_constructors |
| silver_sprint_results | bronze_sprint_results, silver_races, silver_drivers, silver_constructors |
| silver_driver_standings | bronze_driver_standings, silver_drivers |
| silver_constructor_standings | bronze_constructor_standings, silver_constructors |
| silver_drivers_history | silver_drivers |
| gold_race_dimension | silver_races |
| gold_session_results | silver_race_results, silver_sprint_results |
| gold_driver_season | silver_driver_standings, gold_session_results |
| gold_constructor_season | silver_constructor_standings, gold_session_results |

## Reading the Graph

Silver races checks circuit IDs. Silver results check race, driver and constructor IDs. Silver standings check the corresponding identity IDs. These necessary validation-only dependencies remain; Databricks does not visually distinguish them with the Obsidian dashed-line convention.

Gold race dimension also reads circuits, already guaranteed by Silver races. Gold season tables read identity tables already guaranteed by their Silver standings task. Redundant direct edges are omitted without changing readiness.

Gold season tasks depend on Gold session results because they aggregate its points, wins and podiums. This is an actual calculation dependency, not a layout choice. Gold therefore has two execution depths even though it is one conceptual layer.

Gold session results also joins Silver driver and constructor names. Its Silver result prerequisites already guarantee those identity tasks have succeeded, so no redundant direct edges are added. Season standings are not used as name lookups: four result entries in the 2010+ baseline have no matching driver-season standings row, and earlier seasons add more gaps.

Driver history is a separate terminal branch. Its completion is checked before advancing to a later release; it does not gate unrelated Gold transformations.

There are no driver/constructor copy dimensions, analytics-view tasks, validate_release or publish_release tasks. Obsidian is a conceptual diagram; Databricks controls the exact graph layout.
