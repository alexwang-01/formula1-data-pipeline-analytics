"""Full-history checks using the production SQL and original pinned CSV files."""
import unittest

from support import ROOT, source
import test_sql


class HistoryTests(unittest.TestCase):
    def setUp(self):
        self.fixture = test_sql.SQLDataTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.fixture.values["min_season"] = 1950
        self.silver_counts = self.fixture.apply_silver("v2026.14.0")
        self.gold_counts = self.fixture.apply_gold()
        self.db = self.fixture.db

    def test_full_history_counts_keys_and_idempotency(self):
        self.assertEqual(self.gold_counts, {
            "race_dimension": 1172, "session_results": 28189,
            "driver_season": 1681, "constructor_season": 720,
        })
        self.assertEqual(self.db.execute(
            "SELECT MIN(season), MAX(season) FROM gold.race_dimension").fetchone(), (1950, 2026))
        self.assertEqual(self.fixture.apply_silver("v2026.14.0"), self.silver_counts)
        self.assertEqual(self.fixture.apply_gold(), self.gold_counts)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM silver.drivers_history").fetchone()[0], 917)
        for table, parent, keys in [
            ("races", "circuits", ["circuit_id"]),
            ("race_results", "races", ["race_id", "season", "round"]),
            ("sprint_results", "races", ["race_id", "season", "round"]),
            ("race_results", "drivers", ["driver_id"]),
            ("race_results", "constructors", ["constructor_id"]),
            ("driver_standings", "drivers", ["driver_id"]),
            ("constructor_standings", "constructors", ["constructor_id"]),
        ]:
            self.assertEqual(self.db.execute(f"""
                SELECT COUNT(*) FROM silver.{table} ANTI JOIN silver.{parent}
                USING ({', '.join(keys)})
            """).fetchone()[0], 0, (table, parent))

    def test_historical_championship_grain_and_exclusions(self):
        self.assertEqual(self.db.execute("""
            SELECT engine_manufacturer_id, source_points, race_wins
            FROM gold.constructor_season WHERE season=1966 AND constructor_id='brabham'
            ORDER BY engine_manufacturer_id
        """).fetchall(), [("brm", 1, 0), ("climax", 1, 0), ("repco", 42, 4)])
        self.assertEqual(self.db.execute("""
            SELECT source_points, race_wins, championship_won FROM gold.constructor_season
            WHERE season=2007 AND constructor_id='mclaren'
        """).fetchone(), (0, 8, False))
        self.assertEqual(self.db.execute("""
            SELECT COUNT(*) FROM gold.constructor_season
            WHERE season=2018 AND constructor_id='force-india'
        """).fetchone()[0], 1)
        self.assertEqual(self.db.execute("""
            SELECT SUM(race_wins), SUM(race_podiums), SUM(CASE WHEN championship_won THEN 1 ELSE 0 END)
            FROM gold.driver_season WHERE driver_id='michael-schumacher'
        """).fetchone(), (91, 155, 7))

    def test_shared_cars_and_source_career_totals(self):
        manifest = source.verify_release(ROOT / "local/landing", "v2026.14.0")
        for entity in ["driver", "constructor"]:
            path = (ROOT / "local/landing" / manifest["tables"][entity + "s"]["file"]).as_posix()
            self.db.execute(f"CREATE OR REPLACE VIEW raw_identity AS SELECT * FROM read_csv('{path}', all_varchar=true)")
            # Car-level aggregation prevents counting a shared car more than once for its team.
            grain = "driver_id, race_id" if entity == "driver" else "constructor_id, race_id, car_number"
            self.db.execute(f"""CREATE OR REPLACE VIEW race_metrics AS
                SELECT {grain}, MAX(CAST(is_race_win AS INT)) wins,
                       MAX(CAST(is_race_podium AS INT)) podiums
                FROM gold.session_results WHERE session_type='RACE' GROUP BY {grain}
            """)
            self.assertEqual(self.db.execute(f"""
                SELECT s.id FROM raw_identity s LEFT JOIN (
                    SELECT {entity}_id, SUM(wins) wins, SUM(podiums) podiums
                    FROM race_metrics GROUP BY {entity}_id
                ) t ON s.id=t.{entity}_id
                WHERE CAST(s.totalRaceWins AS INT) <> COALESCE(t.wins,0)
                   OR CAST(s.totalPodiums AS INT) <> COALESCE(t.podiums,0)
            """).fetchall(), [])
        self.assertEqual(self.db.execute("""
            SELECT SUM(race_podiums) FROM gold.driver_season WHERE driver_id='nino-farina'
        """).fetchone()[0], 19)
        # Annual standings do not cover every participant. Career results must use the fact table.
        self.assertEqual(self.db.execute("""
            SELECT COUNT(DISTINCT CASE WHEN is_race_podium THEN race_id END)
            FROM gold.session_results WHERE driver_id='maurice-trintignant'
        """).fetchone()[0], 9)

    def test_cloud_history_sql_on_real_source(self):
        self.db.execute("CREATE SCHEMA bronze")
        manifest = source.verify_release(ROOT / "local/landing", "v2026.14.0")
        for name in ["drivers", "constructors"]:
            path = (ROOT / "local/landing" / manifest["tables"][name]["file"]).as_posix()
            self.db.execute(f"CREATE VIEW bronze.{name} AS SELECT * FROM read_csv('{path}', all_varchar=true)")
        self.db.execute("CREATE TABLE ops.release_state(release_seq BIGINT, attempt_id STRING, min_season INT)")
        self.db.execute("INSERT INTO ops.release_state VALUES (2026014000, 'history', 1950)")
        self.db.execute("CREATE TABLE ops.task_completions(release_seq BIGINT, attempt_id STRING, task_key STRING)")
        for name in ["silver_drivers_history", "gold_race_dimension", "gold_session_results",
                     "gold_driver_season", "gold_constructor_season"]:
            self.db.execute("INSERT INTO ops.task_completions VALUES (2026014000, 'history', ?)", [name])
        sql = (ROOT / "tools/verify_history.sql").read_text()
        for schema in ["bronze", "silver", "gold", "ops"]:
            sql = sql.replace(f"f1pa_{schema}.", schema + ".")
        rows = self.fixture.run_sql(sql).fetchall()
        self.assertEqual(len(rows), 14)
        self.assertTrue(all(row[-1] == "PASS" for row in rows), rows)
        self.db.execute("DELETE FROM gold.race_dimension WHERE race_id=1")
        states = {row[0]: row[-1] for row in self.fixture.run_sql(sql).fetchall()}
        self.assertEqual(states["race_join_coverage"], "FAIL")
