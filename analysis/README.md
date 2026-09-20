# Offline F1 Analysis

This directory records the broader local exploration that informed the final Dashboard. It is intentionally excluded from Databricks bundle sync and does not create cloud tables, Job tasks, or Dashboard pages.

## Method

- Source: pinned F1DB `v2026.14.0` CSV archive.
- Engine: local DuckDB using the repository's Silver transformations and frozen earlier analytical SQL where needed.
- Main periods: completed 2025 season, recent 2023-2025 comparisons, and 2010-2025 Singapore history.
- Evidence: 18 saved SQL queries plus independent CSV checks for headline values.

Generated CSV and JSON results stay under ignored `local/analysis/v2026.14.0/`. The analysis does not claim that the pinned release is live or that every source field has been independently audited.

## Selected Findings

| Question | Observed result | Qualification |
| --- | --- | --- |
| How did the 2025 title fight develop? | Verstappen was 104 points behind the leader after round 15 and finished two points behind Norris, 421 to 423. | Reconstructed from Race and Sprint points in the snapshot. |
| How balanced was team scoring? | McLaren was almost even between Norris and Piastri; Verstappen contributed most of Red Bull's points. | Points are attributed to the constructor represented at each event. |
| How often did both cars score? | McLaren scored with both cars in 20 of 24 Grand Prix weekends; Red Bull did so in 7 of 24. | Race sessions only, with two-starter denominators. |
| How important was pole in Singapore? | P1 starters won 10 of 14 Singapore races from 2010-2025. | Descriptive history, not a predictive probability; circuit layouts changed. |

Supporting queries include `04_team_contribution`, `05_team_consistency`, `06_teammate_comparison`, `09_singapore_history`, and `11_progression_2025`.

## Important Source Finding

The snapshot's 2026 constructor standings lag the available event totals by one round for several teams. Historical differences also occur where championship adjustments make official standings differ from raw earned points. The production model therefore retains source standings, calculated event totals, and their difference as separate fields.

The final Dashboard defaults to the completed 2025 season and labels 2026 as partial rather than silently replacing source values. Shared metric definitions are centralized in [Dashboard](../docs/dashboard.md), and release boundaries are centralized in [Data Scope](../docs/data-scope.md).

## Reproduce

Run from the repository root after the pinned local files and development dependencies are available:

```powershell
python analysis/local_exploration.py
python analysis/verify_results.py
```

The runner writes only to `local/analysis/v2026.14.0/`. It does not call Databricks or download a newer source release.

- `queries/`: the 18 exploratory SQL questions.
- `baseline_queries.json`: frozen earlier transformations required by the exploration runner.
- `setup.sql`: local schemas and setup.
- `local_exploration.py`: executes the complete exploration.
- `verify_results.py`: independently checks selected findings against CSV values.
