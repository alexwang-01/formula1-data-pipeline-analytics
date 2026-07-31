# Project Guide

## Purpose

This guide is the implementation reference for recreating the pipeline in Azure Databricks. It preserves the notebook-per-task structure used by Lakeflow Jobs and records the runtime objects, parameters, dependencies, and execution order behind the workflow.

## Runtime Objects

| Object | Name |
| --- | --- |
| Unity Catalog catalog | `formula1_incr` |
| Landing schema and volume | `formula1_incr.landing.files` |
| Bronze schema | `formula1_incr.bronze` |
| Silver schema | `formula1_incr.silver` |
| Gold schema | `formula1_incr.gold` |
| Control schema | `formula1_incr.control` |
| Control table | `formula1_incr.control.batch_control` |
| Job parameter | `p_batch_id` |

Environment-specific Azure values are kept in `notebooks/01-setup/01.Setup Project Environment.sql`. Review the storage account and storage credential before running that notebook in another workspace.

## One-Time Setup

| Order | Notebook | Result |
| --- | --- | --- |
| 1 | `01-setup/01.Setup Project Environment.sql` | External location, catalog, schemas, and landing volume |
| 2 | `06-orchestration/00.Create Control Tables.py` | Batch control table |

## Incremental Refresh Job

Create a Lakeflow Job parameter named `p_batch_id`. Pass `{{job.parameters.p_batch_id}}` to each Bronze, Silver, and Gold notebook task.

### Bronze Tasks

These six tasks may run in parallel.

| Task | Notebook | Target table |
| --- | --- | --- |
| `01_ingest_circuits_file` | `02-bronze/01.Ingest Circuits File.py` | `bronze.circuits` |
| `02_ingest_races_file` | `02-bronze/02.Ingest Races File.py` | `bronze.races` |
| `03_ingest_constructors_file` | `02-bronze/03.Ingest Constructors File.py` | `bronze.constructors` |
| `04_ingest_drivers_file` | `02-bronze/04.Ingest Drivers File.py` | `bronze.drivers` |
| `05_ingest_results_file` | `02-bronze/05.Ingest Results File.py` | `bronze.results` |
| `06_ingest_sprints_file` | `02-bronze/06.Ingest Sprints File.py` | `bronze.sprints` |

### Silver Tasks

Each Silver task depends on its matching Bronze task.

| Task | Notebook | Depends on |
| --- | --- | --- |
| `01_transform_circuits_data` | `03-silver/01.Transform Circuits Data.py` | `01_ingest_circuits_file` |
| `02_transform_races_data` | `03-silver/02.Transform Races Data.py` | `02_ingest_races_file` |
| `03_transform_constructors_data` | `03-silver/03.Transform Constructors Data.py` | `03_ingest_constructors_file` |
| `04_transform_drivers_data` | `03-silver/04.Transform Drivers Data.py` | `04_ingest_drivers_file` |
| `05_transform_results_data` | `03-silver/05.Transform Results Data.py` | `05_ingest_results_file` |
| `06_transform_sprints_data` | `03-silver/06.Transform Sprints Data.py` | `06_ingest_sprints_file` |

### Gold Tasks

| Task | Notebook | Depends on |
| --- | --- | --- |
| `91_build_nationality_region_reference` | `04-gold/91.Build Nationality Region Reference.py` | Independent reference task |
| `01_build_races_dimension` | `04-gold/01.Build Races Dimension.py` | Circuits and races Silver tasks |
| `02_build_constructor_dimension` | `04-gold/02.Build Constructors Dimension.py` | Constructors Silver task and nationality reference |
| `03_build_drivers_dimension` | `04-gold/03.Build Drivers Dimension.py` | Drivers Silver task and nationality reference |
| `04_build_result_fact` | `04-gold/04.Build Results Fact.py` | Results and sprints Silver tasks |

The resulting model contains `dim_races`, `dim_constructors`, `dim_drivers`, and `fact_session_results`.

![Successful incremental refresh task graph](Screenshots/Lakeflow_Jobs/incremental_refresh_success.png)

## Batch Orchestration Job

The orchestration job discovers the earliest unprocessed landing folder and invokes the incremental refresh job with that folder name as `p_batch_id`.

| Order | Task type | Notebook or action |
| --- | --- | --- |
| 1 | Notebook | `06-orchestration/01.Identify Next Batch.py` |
| 2 | If/else condition | Continue only when task value `has_batch` equals `true` |
| 3 | Notebook | `06-orchestration/02.Create New Batch.py` |
| 4 | Run Job | Invoke the incremental refresh job with task value `p_batch_id` |
| 5 | Notebook | `06-orchestration/03.Complete Batch.py` |

Use the following dynamic values in the orchestration job:

| Setting | Value |
| --- | --- |
| If/else left operand | `{{tasks.01_identify_next_batch.values.has_batch}}` |
| If/else operator | `==` |
| If/else right operand | `true` |
| Create New Batch `p_batch_id` | `{{tasks.01_identify_next_batch.values.p_batch_id}}` |
| Incremental Refresh job `p_batch_id` | `{{tasks.01_identify_next_batch.values.p_batch_id}}` |
| Complete Batch `p_batch_id` | `{{tasks.01_identify_next_batch.values.p_batch_id}}` |

The control table records `in_progress` and `completed` status. If no unprocessed folder exists, the condition ends the workflow without launching the refresh job.

![Successful batch orchestration task graph](Screenshots/Lakeflow_Jobs/batch_orchestration_success.png)

## Analytics

Run these notebooks after the Gold model has been built:

| Notebook | Output |
| --- | --- |
| `05-analytics/01.Build Driver Standings View.sql` | `formula1_incr.gold.v_driver_standing` |
| `05-analytics/02.Build Constructor Standings View.sql` | `formula1_incr.gold.v_constructor_standing` |
| `05-analytics/03.Analyze Dominant Drivers.sql` | All-time driver comparison result set |
| `05-analytics/04.Analyze Dominant Constructors.sql` | All-time constructor comparison result set |

The views aggregate championship points from race and sprint sessions. Race starts, wins, and podiums use race sessions only, and a window function calculates each season's standings.

The two all-time analyses aggregate the standings views across seasons and keep
drivers or constructors that have finished a season in first place. They use a
project-defined comparison score:

`greatness_score = championships * 100 + wins * 10 + podiums * 3`

The score supports dashboard comparison and is not an official Formula 1
ranking.

## AI/BI Dashboard

Create the dashboard from the accumulated Gold model and the two standings views.

| Dashboard page | Primary source | Presentation |
| --- | --- | --- |
| Driver Championship Standings | `v_driver_standing` | Season filter, standing, points, wins, and podiums by driver |
| Constructor Championship Standings | `v_constructor_standing` | Season filter, standing, points, wins, and podiums by constructor |
| Dominant Drivers of All Time | `03.Analyze Dominant Drivers.sql` | Wins, podiums, championships, races, and greatness score |
| Dominant Teams of All Time | `04.Analyze Dominant Constructors.sql` | Wins, podiums, championships, races, and greatness score |

The season pages use the ranked views directly. The all-time SQL files
aggregate those same views across seasons to create career-level comparisons.

### Dashboard Screenshots

![Driver championship standings](Screenshots/Dashboard/driver_championship_standings.png)

![Constructor championship standings](Screenshots/Dashboard/constructor_championship_standings.png)

![Dominant drivers of all time](Screenshots/Dashboard/dominant_drivers_all_time.png)

![Dominant teams of all time](Screenshots/Dashboard/dominant_teams_all_time.png)
