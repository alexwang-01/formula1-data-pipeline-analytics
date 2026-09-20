"""Check native dashboard layout, fields, defaults, and Gold-backed SQL."""
import json
import unittest

from support import ROOT
import test_sql

def dashboard_export():
    return json.loads((ROOT / "dashboards/formula1.lvdash.json").read_text(encoding="utf-8"))


class DashboardTests(unittest.TestCase):
    def test_exported_artifact_and_layout(self):
        dashboard = dashboard_export()
        self.assertEqual(len(dashboard["datasets"]), 7)
        self.assertEqual(len(dashboard["pages"]), 5)
        names = set()
        for page in dashboard["pages"]:
            for index, item in enumerate(page["layout"]):
                name = item["widget"]["name"]
                self.assertNotIn(name, names)
                names.add(name)
                a = item["position"]
                self.assertGreater(a["width"], 0)
                self.assertGreater(a["height"], 0)
                self.assertLessEqual(a["x"] + a["width"], 12)
                for other in page["layout"][index + 1:]:
                    b = other["position"]
                    overlap = (a["x"] < b["x"] + b["width"] and b["x"] < a["x"] + a["width"]
                               and a["y"] < b["y"] + b["height"] and b["y"] < a["y"] + a["height"])
                    self.assertFalse(overlap, name)

    def test_queries_and_filter_populations(self):
        fixture = test_sql.SQLDataTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        fixture.values["min_season"] = 1950
        fixture.apply_silver("v2026.14.0")
        fixture.apply_gold()
        dashboard = dashboard_export()
        expected_counts = {"drivers": 1681, "constructors": 720, "results": 28189}
        for dataset in dashboard["datasets"]:
            sql = "".join(dataset["queryLines"]).replace("f1pa_gold.", "gold.")
            fixture.run_sql(f"CREATE VIEW ds_{dataset['name']} AS " + sql)
            count = fixture.db.execute(f"SELECT COUNT(*) FROM ds_{dataset['name']}").fetchone()[0]
            if dataset["name"] in expected_counts:
                self.assertEqual(count, expected_counts[dataset["name"]])
            elif dataset["name"].endswith("_wins"):
                self.assertGreater(count, 0)
                self.assertEqual(fixture.db.execute(
                    f"SELECT COUNT(*) FROM ds_{dataset['name']} WHERE race_wins <= 0"
                ).fetchone()[0], 0)
        for page in dashboard["pages"]:
            for item in page["layout"]:
                widget = item["widget"]
                for q in widget.get("queries", []):
                    query = q["query"]
                    fields = query["fields"]
                    expressions = [f["expression"] for f in fields]
                    group = [e for e in expressions if not e.startswith("SUM(")]
                    sql = "SELECT " + ", ".join(expressions) + " FROM ds_" + query["datasetName"]
                    if query.get("filters"):
                        sql += " WHERE " + " AND ".join(f["expression"] for f in query["filters"])
                    if not query["disaggregated"]:
                        sql += " GROUP BY " + ", ".join(group)
                    fixture.run_sql(sql).fetchall()
                    if widget["spec"]["widgetType"] == "filter-single-select":
                        default = widget["spec"]["selection"]["defaultSelection"]["values"]["values"][0]["value"]
                        col = fields[0]["name"]
                        count = fixture.db.execute(
                            f'SELECT COUNT(*) FROM ds_{query["datasetName"]} WHERE "{col}" = ?', [default]
                        ).fetchone()[0]
                        self.assertGreater(count, 0)
        for season in (2021, 2025, 2026):
            for ds in expected_counts:
                self.assertGreater(fixture.db.execute(
                    f"SELECT COUNT(*) FROM ds_{ds} WHERE season = ?", [season]).fetchone()[0], 0)
        for session in ("RACE", "SPRINT"):
            self.assertGreater(fixture.db.execute(
                "SELECT COUNT(*) FROM ds_results WHERE season = 2025 AND round = 2 AND session_type = ?",
                [session]).fetchone()[0], 0)
        self.assertEqual(fixture.db.execute(
            "SELECT COUNT(*) FROM ds_results WHERE season = 2025 AND round = 1 AND session_type = 'SPRINT'"
        ).fetchone()[0], 0)
        winner = fixture.db.execute("""SELECT driver_name, result_status FROM ds_results
            WHERE season = 2025 AND round = 1 AND session_type = 'RACE'
            ORDER BY classification_order LIMIT 1""").fetchone()
        self.assertEqual(winner, ("Lando Norris", "Classified"))
        self.assertEqual(fixture.db.execute("""SELECT COUNT(*) FROM ds_results
            WHERE finish_position IS NULL AND classification_order <> 9999""").fetchone()[0], 0)
        for dataset, winners in [("drivers_wins", 4), ("constructors_wins", 3)]:
            self.assertEqual(fixture.db.execute(
                f"SELECT COUNT(*), SUM(race_wins) FROM ds_{dataset} WHERE season=2025"
            ).fetchone(), (winners, 24))
        self.assertEqual(fixture.db.execute("""SELECT DISTINCT grand_prix FROM ds_results
            WHERE season=2025 AND round=1""").fetchall(), [("01 - AUSTRALIA",)])
        self.assertEqual(fixture.db.execute("""SELECT COUNT(*) FROM (
            SELECT season, grand_prix FROM ds_results
            GROUP BY season, grand_prix HAVING COUNT(DISTINCT race_id) > 1)""").fetchone()[0], 0)
        self.assertEqual(fixture.db.execute("""SELECT championships,race_wins,race_podiums
            FROM ds_driver_career WHERE driver_id='michael-schumacher'""").fetchone(), (7, 91, 155))
        self.assertEqual(fixture.db.execute("""SELECT race_podiums FROM ds_driver_career
            WHERE driver_id='maurice-trintignant'""").fetchone()[0], 9)
        self.assertEqual(fixture.db.execute("""SELECT race_podiums FROM ds_driver_career
            WHERE driver_id='nino-farina'""").fetchone()[0], 19)
        self.assertEqual(fixture.db.execute("""SELECT COUNT(DISTINCT team_entry), SUM(source_points)
            FROM ds_constructors WHERE season=1966 AND constructor_id='brabham'""").fetchone(), (3, 44))
        self.assertEqual(fixture.db.execute("""SELECT source_points, standing_status FROM ds_constructors
            WHERE season=2007 AND constructor_id='mclaren'""").fetchone(), (0, 'EX'))
        for ds in ["driver_career", "constructor_career"]:
            for metric, rank in [("championships", "titles_rank"), ("race_wins", "wins_rank"), ("race_podiums", "podiums_rank")]:
                self.assertEqual(fixture.db.execute(f"SELECT COUNT(*) FROM ds_{ds} WHERE {rank}<=10 AND {metric}>0").fetchone()[0], 10)

    def test_clear_layout_and_linked_filters(self):
        dashboard = dashboard_export()
        for page in dashboard["pages"]:
            widgets = {item["widget"]["name"]: item["widget"] for item in page["layout"]}
            self.assertFalse(any("reconciliation" in name for name in widgets))
            for widget in widgets.values():
                spec = widget.get("spec", {})
                if spec.get("widgetType") in ("bar", "pie"):
                    scale = spec["encodings"]["color"]["scale"]
                    self.assertTrue(len(scale.get("mappings", [])) > 5 or "colorRamp" in scale)
        for ds, page in zip(("drivers", "constructors"), dashboard["pages"][:2]):
            widgets = {item["widget"]["name"]: item["widget"] for item in page["layout"]}
            season = widgets[ds + "_season_filter"]
            self.assertEqual({q["query"]["datasetName"] for q in season["queries"]}, {ds, ds + "_wins"})
            self.assertEqual(len(season["spec"]["encodings"]["fields"]), 2)
            donut = widgets[ds + "_wins_donut"]
            points = widgets[ds + "_points"]
            self.assertNotEqual(points["spec"]["encodings"]["color"]["fieldName"], "sum(calculated_points)")
