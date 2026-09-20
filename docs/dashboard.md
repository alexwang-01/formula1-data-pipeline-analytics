# Formula 1 Dashboard

The native Databricks AI/BI Dashboard reads the four Manual Gold tables through seven saved SQL datasets. It does not add reporting tables, views, or Job tasks.

## Pages and Sources

| Page | Content | Gold source |
| --- | --- | --- |
| Driver Championship | Annual standings, Grand Prix win share, and points | `driver_season`, `session_results` |
| Constructor Championship | Engine-aware annual standings, win share, and points | `constructor_season`, `session_results` |
| Driver Career | Titles, Grand Prix wins, podiums, and independent Top 10 comparisons | `driver_season`, `session_results` |
| Constructor Career | Titles, Grand Prix wins, podiums, and independent Top 10 comparisons | `constructor_season`, `session_results` |
| Race Results | Season, Grand Prix, and Race/Sprint filters with classification and points | `race_dimension`, `session_results` |

The default season is 2025. Coverage and release limitations are defined once in [Data Scope](data-scope.md).

## Metric Contract

- Championship position, status, and source points come from annual source standings. Calculated event points remain a separate field.
- Race and Sprint points contribute to season totals. Grand Prix wins and podiums use Race sessions only.
- Career titles use `championship_won`; a current first-place position in a partial season does not create a title.
- Annual constructor grain is season, constructor, and engine. Multiple engine entries are displayed separately rather than summed into a new official rank.
- Driver career wins and podiums count distinct races. Constructor career results count each race/car once so shared drivers do not duplicate a car.
- Annual standings are not a complete participant list, so career race results are aggregated from `session_results` before championship totals are joined.
- Race entries and race weekends are not labelled as actual starts. Positions gained is grid position minus finish position, not a count of overtakes.
- Names use the selected current identity rather than inferred event-time SCD2 history. There is no custom Greatness Score.

## Dataset Contract

The Race Results dataset joins `session_results` to `race_dimension` on release sequence and race ID. Driver and constructor names are already materialized in `session_results`; annual standings are not used as identity lookup tables.

Four result entries in the original 2010-onward comparison lack corresponding driver-season standings rows. Earlier history adds more such cases. The left-side race result must remain visible, which is why the Dashboard does not join results through annual standings. [The diagnostic query](../tools/diagnose_standings_coverage.sql) preserves this check.

The two career datasets aggregate race facts and source championships separately before joining at driver or constructor grain. Different grains are not forced into one wide Dashboard table.

## Editing and Verification

The draft remains editable in the Databricks UI. Before a future bundle deployment, export the current draft back to `dashboards/formula1.lvdash.json`; otherwise a stale local export can replace UI edits.

- `dashboards/formula1.lvdash.json`: authoritative native layout and embedded dataset SQL.
- `dashboards/sql/`: readable annual and career dataset queries.
- `tools/dashboard_race_results.sql`: readable Race Results dataset query.
- `resources/analytics.dashboard.yml`: bundle deployment metadata.
- `tests/test_dashboard.py`: dataset, filter, field, grain, and layout checks.
- `tools/verify_dashboard.py`: seven source-backed cloud checks and warehouse cleanup.

Seven cloud dataset checks passed on 19 September 2026: 1,681 driver-season rows, 720 constructor/engine-season rows, 28,189 session entries, 860 driver career rows, and 186 constructor career rows. The current 47-test local suite also covers shared cars, historical engine splits, excluded entries, missing annual-standing participants, and Race/Sprint separation.
