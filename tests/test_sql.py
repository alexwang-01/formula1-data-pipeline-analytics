"""Execute the notebooks' transformation SQL locally against pinned original CSV.
DuckDB validates SQL/data semantics, not Spark execution, Auto Loader, or Delta I/O.
"""
from decimal import Decimal
import json
import unittest
import duckdb

from support import ROOT, source, queries, duck_sql, row_contract

SILVER = list(source.FILES)
GOLD = ["race_dimension", "session_results", "driver_season", "constructor_season"]
TAGS = list(source.PINNED_RELEASES)


class SQLDataTests(unittest.TestCase):
    def setUp(self):
        self.db = duckdb.connect()
        self.addCleanup(self.db.close)
        for schema in ["silver", "gold", "ops", "analytics"]:
            self.db.execute(f"CREATE SCHEMA {schema}")
        self.db.execute("CREATE TABLE ops.published_releases(release_seq BIGINT)")
        self.values = {"silver": "silver", "gold": "gold", "ops": "ops",
                       "analytics": "analytics", "release_seq": 1, "min_season": 2010}

    def run_sql(self, sql):
        return self.db.execute(duck_sql(sql))

    def assert_contract(self, table, keys, required):
        columns = ", ".join(keys)
        self.assertEqual(self.db.execute(
            f"SELECT COUNT(*) FROM (SELECT {columns} FROM {table} GROUP BY {columns} HAVING COUNT(*) > 1)"
        ).fetchone()[0], 0, table)
        for column in required:
            self.assertEqual(self.db.execute(
                f'SELECT COUNT(*) FROM {table} WHERE "{column}" IS NULL'
            ).fetchone()[0], 0, f"{table}.{column}")

    def apply_silver(self, tag):
        manifest = source.verify_release(ROOT / "local/landing", tag)
        self.values["release_seq"] = source.release_number(tag)
        counts = {}
        for name in SILVER:
            path = ROOT / "local/landing" / manifest["tables"][name]["file"]
            escaped = path.as_posix().replace("'", "''")
            self.db.execute(f"""CREATE OR REPLACE VIEW source_rows AS
                SELECT * FROM read_csv('{escaped}', header=true, all_varchar=true)""")
            self.assertEqual(self.db.execute("SELECT COUNT(*) FROM source_rows").fetchone()[0],
                             manifest["tables"][name]["rows"])
            sql = queries(f"03-silver/{name}.py", self.values)
            self.run_sql("CREATE OR REPLACE TABLE clean_rows AS " + sql[0])
            self.assert_contract("clean_rows", *row_contract(f"03-silver/{name}.py"))
            for statement in sql[1:]:
                self.run_sql(statement)
            self.assert_contract(f"silver.{name}", *row_contract(f"03-silver/{name}.py"))
            counts[name] = self.db.execute(f"SELECT COUNT(*) FROM silver.{name}").fetchone()[0]
        for statement in queries("03-silver/drivers_history.py", self.values):
            if statement.lstrip().startswith("CREATE"):
                self.run_sql(statement)
        self.db.execute("CREATE OR REPLACE VIEW current_drivers AS SELECT * FROM silver.drivers")
        for statement in queries("03-silver/drivers_history.py", self.values):
            if not statement.lstrip().startswith("CREATE"):
                self.run_sql(statement)
        return counts

    def apply_gold(self):
        counts = {}
        for name in GOLD:
            sql = queries(f"04-gold/{name}.py", self.values)[0]
            self.run_sql("CREATE OR REPLACE TABLE candidate AS " + sql)
            keys, required = row_contract(f"04-gold/{name}.py")
            self.assert_contract("candidate", keys, required)
            self.db.execute(f"CREATE OR REPLACE TABLE gold.{name} AS SELECT * FROM candidate")
            counts[name] = self.db.execute("SELECT COUNT(*) FROM candidate").fetchone()[0]
        return counts

    def assert_previous_metrics_unchanged(self):
        baseline = json.loads((ROOT / "analysis/baseline_queries.json").read_text())
        self.db.execute("CREATE SCHEMA IF NOT EXISTS baseline_gold")
        self.db.execute("CREATE SCHEMA IF NOT EXISTS baseline_analytics")
        self.db.execute("DELETE FROM ops.published_releases")
        self.db.execute("INSERT INTO ops.published_releases VALUES (?)", [self.values["release_seq"]])
        for name, sql in baseline["gold"].items():
            sql = sql.replace("2026014000", str(self.values["release_seq"]))
            self.run_sql(f"CREATE OR REPLACE TABLE baseline_gold.{name} AS " + sql)
        for sql in baseline["analytics"].values():
            self.run_sql(sql.replace("gold.", "baseline_gold.").replace("analytics.", "baseline_analytics."))
        for entity in ["driver", "constructor"]:
            columns = ", ".join(d[0] for d in self.db.execute(
                f"SELECT * FROM baseline_analytics.v_{entity}_season LIMIT 0").description)
            old = f"SELECT {columns} FROM baseline_analytics.v_{entity}_season"
            new = f"SELECT {columns} FROM gold.{entity}_season"
            self.assertEqual(self.db.execute(f"({old}) EXCEPT ALL ({new})").fetchall(), [])
            self.assertEqual(self.db.execute(f"({new}) EXCEPT ALL ({old})").fetchall(), [])
        for old, new in [("dim_races", "race_dimension"), ("fact_session_results", "session_results")]:
            columns = ", ".join(d[0] for d in self.db.execute(
                f"SELECT * FROM baseline_gold.{old} LIMIT 0").description)
            self.assertEqual(self.db.execute(
                f"SELECT {columns} FROM baseline_gold.{old} EXCEPT ALL SELECT {columns} FROM gold.{new}"
            ).fetchall(), [])
            self.assertEqual(self.db.execute(
                f"SELECT {columns} FROM gold.{new} EXCEPT ALL SELECT {columns} FROM baseline_gold.{old}"
            ).fetchall(), [])
        self.assertEqual(self.db.execute("""
            SELECT COUNT(*) FROM gold.driver_season g JOIN silver.drivers s USING (driver_id)
            WHERE g.nationality_country_id IS DISTINCT FROM s.nationality_country_id
        """).fetchone()[0], 0)
        self.assertEqual(self.db.execute("""
            SELECT COUNT(*) FROM gold.constructor_season g JOIN silver.constructors s USING (constructor_id)
            WHERE g.country_id IS DISTINCT FROM s.country_id
        """).fetchone()[0], 0)

    def test_real_releases_and_analytics(self):
        report = {"engine": "DuckDB local SQL checks; not Databricks runtime validation",
                  "min_season": 2010, "releases": []}
        for tag in TAGS:
            with self.subTest(release=tag):
                counts = self.apply_silver(tag)
                before = dict(counts)
                # Retry the exact same snapshot through the actual MERGE SQL.
                self.assertEqual(self.apply_silver(tag), before)
                gold_counts = self.apply_gold()
                self.assert_previous_metrics_unchanged()
                checks = self.db.execute((ROOT / "tools/verify_dashboard_joins.sql").read_text()
                                         .replace("f1pa_gold.", "gold.")).fetchall()
                self.assertTrue(all(row[-1] == "PASS" for row in checks), checks)
                dataset = (ROOT / "tools/dashboard_race_results.sql").read_text().replace("f1pa_gold.", "gold.")
                self.db.execute("CREATE OR REPLACE VIEW dashboard_dataset AS " + dataset)
                self.assert_contract("dashboard_dataset", ["race_id", "session_type", "driver_id", "car_number"],
                                     ["race_name", "driver_name", "constructor_name"])
                self.assertEqual(self.db.execute("SELECT COUNT(*) FROM dashboard_dataset").fetchone()[0],
                                 gold_counts["session_results"])
                missing_standings = self.db.execute((ROOT / "tools/diagnose_standings_coverage.sql").read_text()
                                                   .replace("f1pa_gold.", "gold.")).fetchall()
                self.assertEqual(len(missing_standings), 4)
                self.assertTrue(all(row[4] for row in missing_standings))
                seq = self.values["release_seq"]
                self.assertEqual(self.apply_gold(), gold_counts)
                for name in GOLD:
                    self.assertEqual(self.db.execute(f"SELECT DISTINCT _release_seq FROM gold.{name}").fetchall(), [(seq,)])
                self.assertEqual(gold_counts["session_results"],
                                 counts["race_results"] + counts["sprint_results"])
                self.assertEqual(gold_counts["race_dimension"], counts["races"])
                self.assertEqual(gold_counts["driver_season"], counts["driver_standings"])
                self.assertEqual(gold_counts["constructor_season"], self.db.execute(
                    "SELECT COUNT(*) FROM silver.constructor_standings WHERE entry_category='RANKED'"
                ).fetchone()[0])
                for dimension, key in [("drivers", "driver_id"),
                                       ("constructors", "constructor_id"),
                                       ("races", "race_id")]:
                    self.assertEqual(self.db.execute(f"""
                        SELECT COUNT(*) FROM gold.session_results f
                        ANTI JOIN silver.{dimension} d
                        ON f._release_seq = d._release_seq AND f.{key} = d.{key}
                        WHERE f._release_seq = {seq}
                    """).fetchone()[0], 0, dimension)
                # SCD2 active identities must match the complete current source.
                self.assertEqual(self.db.execute(
                    "SELECT COUNT(*) FROM silver.drivers_history WHERE valid_to_release IS NULL"
                ).fetchone()[0], counts["drivers"])
                self.assert_contract("silver.drivers_history", ["driver_id", "valid_from_release"],
                                     ["driver_id", "valid_from_release"])
                self.assertEqual(self.db.execute(
                    "SELECT COUNT(*) FROM silver.drivers_history WHERE valid_to_release <= valid_from_release"
                ).fetchone()[0], 0)
                # Race wins/podiums must exclude Sprint rows.
                expected_wins = self.db.execute("SELECT COUNT(*) FROM silver.race_results WHERE finish_position=1").fetchone()[0]
                expected_podiums = self.db.execute("SELECT COUNT(*) FROM silver.race_results WHERE finish_position BETWEEN 1 AND 3").fetchone()[0]
                self.assertEqual(self.db.execute("SELECT SUM(race_wins), SUM(race_podiums) FROM gold.driver_season").fetchone(),
                                 (expected_wins, expected_podiums))
                self.assertEqual(self.db.execute("""
                    SELECT COUNT(*) FROM (
                        SELECT season, driver_id, SUM(points) AS final_points
                        FROM gold.session_results GROUP BY season, driver_id
                    ) p JOIN gold.driver_season s USING (season, driver_id)
                    WHERE p.final_points <> s.calculated_points
                """).fetchone()[0], 0)
                differences = {}
                for entity in ["driver", "constructor"]:
                    rows = self.db.execute(f"""
                        SELECT season, {entity}_id, source_points, calculated_points, points_difference
                        FROM gold.{entity}_season WHERE points_difference <> 0
                        ORDER BY season, {entity}_id
                    """).fetchall()
                    differences[entity] = [list(row) for row in rows]
                report["releases"].append({"tag": tag, "silver_rows": counts, "gold_rows": gold_counts,
                                           "points_differences": differences})
        output = ROOT / "local/validation"
        output.mkdir(parents=True, exist_ok=True)
        (output / "data-report.json").write_text(json.dumps(report, indent=2, default=str))
        print("\nReal-source SQL validation:", json.dumps(
            [{"tag": r["tag"], "session_rows": r["gold_rows"]["session_results"],
              "driver_points_differences": len(r["points_differences"]["driver"]),
              "constructor_points_differences": len(r["points_differences"]["constructor"])}
             for r in report["releases"]]))

    def test_scd2_changes_nulls_deletes_and_retry(self):
        self.db.execute("""CREATE TABLE silver.drivers (
            driver_id STRING, driver_name STRING, full_name STRING,
            nationality_country_id STRING, date_of_birth DATE, _release_seq BIGINT)""")
        self.db.execute("INSERT INTO silver.drivers VALUES ('a', 'A', 'Alpha', NULL, '2000-01-01', 1)")
        self.db.execute("CREATE VIEW current_drivers AS SELECT * FROM silver.drivers")

        def apply(seq):
            self.values["release_seq"] = seq
            for sql in queries("03-silver/drivers_history.py", self.values):
                self.run_sql(sql)

        apply(1)
        apply(1)
        self.db.execute("UPDATE silver.drivers SET nationality_country_id='xx', _release_seq=2")
        self.values["release_seq"] = 2
        # Simulate interruption after closing the old row, before inserting its replacement.
        self.run_sql(queries("03-silver/drivers_history.py", self.values)[1])
        apply(2)
        apply(2)
        self.assertEqual(self.db.execute("""
            SELECT valid_from_release, valid_to_release FROM silver.drivers_history ORDER BY valid_from_release
        """).fetchall(), [(1, 2), (2, None)])
        self.db.execute("DELETE FROM silver.drivers")
        apply(3)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM silver.drivers_history WHERE valid_to_release IS NULL").fetchone()[0], 0)
        self.db.execute("INSERT INTO silver.drivers VALUES ('a', 'A', 'Alpha', NULL, '2000-01-01', 4)")
        apply(4)
        apply(4)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM silver.drivers_history").fetchone()[0], 3)

    def test_full_snapshot_merge_inserts_updates_and_removals(self):
        values = self.values
        self.db.execute("CREATE TABLE clean_rows(driver_id STRING, driver_name STRING, _release_seq BIGINT)")
        statements = queries("03-silver/drivers.py", values)[1:]
        self.db.execute("INSERT INTO clean_rows VALUES ('a', 'Before', 1), ('removed', 'Old', 1)")
        for sql in statements:
            self.run_sql(sql)
        self.db.execute("DELETE FROM clean_rows")
        self.db.execute("INSERT INTO clean_rows VALUES ('a', 'After', 2), ('new', 'Added', 2)")
        for _ in range(2):
            for sql in statements:
                self.run_sql(sql)
        self.assertEqual(self.db.execute("SELECT driver_id, driver_name FROM silver.drivers ORDER BY driver_id").fetchall(),
                         [('a', 'After'), ('new', 'Added')])

    def test_dashboard_checks_detect_missing_and_duplicate_races(self):
        self.apply_silver(TAGS[-1])
        self.apply_gold()
        sql = (ROOT / "tools/verify_dashboard_joins.sql").read_text().replace("f1pa_gold.", "gold.")
        race_id = self.db.execute("SELECT race_id FROM gold.session_results LIMIT 1").fetchone()[0]
        self.db.execute("DELETE FROM gold.race_dimension WHERE race_id = ?", [race_id])
        statuses = {row[0]: row[-1] for row in self.db.execute(sql).fetchall()}
        self.assertEqual(statuses["missing_races"], "FAIL")
        self.assertEqual(statuses["joined_rows"], "PASS")  # LEFT JOIN retains unmatched results.
        self.apply_gold()
        self.db.execute("INSERT INTO gold.race_dimension SELECT * FROM gold.race_dimension WHERE race_id = ?", [race_id])
        statuses = {row[0]: row[-1] for row in self.db.execute(sql).fetchall()}
        self.assertEqual(statuses["duplicate_joined_keys"], "FAIL")
        self.assertEqual(statuses["joined_rows"], "FAIL")

    def test_invalid_cast_blocks_transform(self):
        self.db.execute('CREATE TABLE source_rows (id STRING, name STRING, fullName STRING, nationalityCountryId STRING, dateOfBirth STRING)')
        self.db.execute("INSERT INTO source_rows VALUES ('a', 'A', 'A', 'xx', 'not-a-date')")
        sql = queries("03-silver/drivers.py", self.values)[0]
        with self.assertRaises(duckdb.ConversionException):
            self.run_sql(sql)
