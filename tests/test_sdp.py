"""Validate SDP source and SQL locally; native CDC still needs Databricks."""
import ast
import unittest

import yaml

from support import ROOT, source, render, duck_sql
import test_sql


def sdp_query(layer, name, values):
    path = ROOT / "sdp/notebooks" / layer / (name + ".py")
    tree = ast.parse(path.read_text())
    calls = [node for node in ast.walk(tree)
             if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
             and node.func.attr == "sql"]
    return render(calls[0].args[0], values)


class SDPTests(unittest.TestCase):
    def test_declarative_notebooks_and_isolation(self):
        paths = list((ROOT / "sdp/notebooks").glob("*/*.py"))
        self.assertEqual(len(paths), 21)
        for path in paths:
            text = path.read_text()
            ast.parse(text)
            for prohibited in [".writeStream", ".saveAsTable", ".collect(", ".count(",
                               "MERGE INTO", "dbutils.", "f1pa_bronze", "f1pa_silver", "f1pa_gold"]:
                self.assertNotIn(prohibited, text, str(path))
        config = yaml.safe_load((ROOT / "sdp/resources/pipeline.yml").read_text())
        pipeline = config["resources"]["pipelines"]["formula1_sdp"]
        self.assertTrue(pipeline["serverless"])
        self.assertFalse(pipeline["continuous"])
        self.assertFalse(pipeline["development"])
        bundle = yaml.safe_load((ROOT / "sdp/databricks.yml").read_text())
        self.assertFalse(bundle["targets"]["dev"]["presets"]["pipelines_development"])
        manual_bundle = yaml.safe_load((ROOT / "databricks.yml").read_text())
        self.assertIn("sdp/**", manual_bundle["sync"]["exclude"])
        self.assertEqual(len(pipeline["libraries"]), 21)
        job = config["resources"]["jobs"]["formula1_sdp_job"]
        self.assertEqual(job["max_concurrent_runs"], 1)
        self.assertNotIn("schedule", job)
        self.assertFalse(job["tasks"][1]["pipeline_task"]["full_refresh"])

    def test_sql_matches_manual_on_three_complete_snapshots(self):
        fixture = test_sql.SQLDataTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        fixture.values["min_season"] = 1950
        db = fixture.db
        for schema in ["sdp_bronze", "sdp_silver", "sdp_gold"]:
            db.execute(f"CREATE SCHEMA {schema}")
        for tag in ["v2026.8.1", "v2026.8.2", "v2026.14.0"]:
            fixture.apply_silver(tag)
            fixture.apply_gold()
            manifest = source.verify_release(ROOT / "local/landing", tag)
            values = dict(fixture.values, bronze="sdp_bronze", silver="sdp_silver",
                          gold="sdp_gold", release_tag=tag)
            for name, entry in manifest["tables"].items():
                path = (ROOT / "local/landing" / entry["file"]).as_posix().replace("'", "''")
                # Add one irrelevant snapshot row: Silver must use only the selected tag.
                db.execute(f"""CREATE OR REPLACE TABLE sdp_bronze.{name} AS
                    SELECT *, '{tag}' AS release_tag FROM read_csv('{path}', all_varchar=true)""")
                db.execute(f"""INSERT INTO sdp_bronze.{name}
                    SELECT * REPLACE ('v1900.1.0' AS release_tag)
                    FROM sdp_bronze.{name} LIMIT 1""")
                query = sdp_query("silver", name, values)
                db.execute(f"CREATE OR REPLACE TABLE sdp_silver.{name} AS " + duck_sql(query))
                self.assert_same(db, f"silver.{name}", f"sdp_silver.{name}")
            history_tree = ast.parse((ROOT / "sdp/notebooks/silver/drivers_history.py").read_text())
            projection = next(node for node in ast.walk(history_tree)
                              if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                              and node.func.attr == "selectExpr")
            expressions = [ast.literal_eval(arg) for arg in projection.args]
            db.execute("CREATE OR REPLACE VIEW history_snapshot AS SELECT " + ", ".join(expressions)
                       + f" FROM sdp_bronze.drivers WHERE release_tag='{tag}'")
            db.execute("CREATE OR REPLACE VIEW driver_snapshot AS SELECT * EXCLUDE (_release_seq) FROM silver.drivers")
            self.assert_same(db, "driver_snapshot", "history_snapshot")
            for name in ["race_dimension", "session_results", "driver_season", "constructor_season"]:
                query = sdp_query("gold", name, values)
                db.execute(f"CREATE OR REPLACE TABLE sdp_gold.{name} AS " + duck_sql(query))
                self.assert_same(db, f"gold.{name}", f"sdp_gold.{name}")

    def assert_same(self, db, left, right):
        self.assertEqual(db.execute(f"SELECT * FROM {left} EXCEPT ALL SELECT * FROM {right}").fetchall(), [], right)
        self.assertEqual(db.execute(f"SELECT * FROM {right} EXCEPT ALL SELECT * FROM {left}").fetchall(), [], right)

    def test_history_callback_skips_already_processed_release(self):
        tree = ast.parse((ROOT / "sdp/notebooks/silver/drivers_history.py").read_text())
        function = next(node for node in tree.body if isinstance(node, ast.FunctionDef))

        class Frame:
            def selectExpr(self, *columns):
                return self

        class Reader:
            def format(self, name):
                return self

            def option(self, key, value):
                return self

            def load(self, path):
                self.path = path
                return Frame()

        class Spark:
            read = Reader()

        context = {"spark": Spark(), "landing": "/test/landing", "release_tag": "v2026.8.2",
                   "release_seq": 2026008002}
        exec(compile(ast.Module(body=[function], type_ignores=[]), "<callback>", "exec"), context)
        callback = context["next_driver_snapshot"]
        self.assertEqual(callback(None)[1], 2026008002)
        self.assertEqual(callback(2026008001)[1], 2026008002)
        self.assertIsNone(callback(2026008002))
        self.assertIsNone(callback(2026014000))
