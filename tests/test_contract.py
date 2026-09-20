import ast
from pathlib import Path
import re
import unittest
import yaml

from support import ROOT, source


class ProjectContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        config = yaml.safe_load((ROOT / "resources/manual.job.yml").read_text())
        cls.job = config["resources"]["jobs"]["formula1_manual"]
        cls.tasks = cls.job["tasks"]

    def test_python_syntax(self):
        paths = list((ROOT / "notebooks").rglob("*.py")) + list((ROOT / "tools").glob("*.py"))
        for path in paths:
            with self.subTest(path=path.name):
                ast.parse(path.read_text(encoding="utf-8"))

    def test_each_executable_notebook_has_one_task(self):
        task_paths = [(ROOT / "resources" / t["notebook_task"]["notebook_path"]).resolve()
                      for t in self.tasks]
        notebooks = set((ROOT / "notebooks").rglob("*.py"))
        notebooks -= set((ROOT / "notebooks/00-common").glob("*.py"))
        self.assertEqual(set(task_paths), notebooks)
        self.assertEqual(len(task_paths), len(set(task_paths)))
        self.assertEqual(len(self.tasks), 22)

    def test_dag_is_acyclic_and_only_real_dependencies_remain(self):
        pending = {t["task_key"]: {d["task_key"] for d in t.get("depends_on", [])}
                   for t in self.tasks}
        self.assertEqual(len(pending), len(self.tasks))
        completed = set()
        while pending:
            ready = {key for key, deps in pending.items() if deps <= completed}
            self.assertTrue(ready, f"Cycle or missing dependency: {pending}")
            for key in ready:
                pending.pop(key)
            completed |= ready
        deps = {t["task_key"]: {d["task_key"] for d in t.get("depends_on", [])} for t in self.tasks}
        self.assertEqual(deps["gold_race_dimension"], {"silver_races"})
        self.assertEqual(deps["gold_session_results"], {"silver_race_results", "silver_sprint_results"})
        self.assertEqual(deps["gold_driver_season"], {"gold_session_results", "silver_driver_standings"})
        self.assertEqual(deps["gold_constructor_season"], {"gold_session_results", "silver_constructor_standings"})
        self.assertFalse(any(k.startswith(("analytics_", "validate_", "publish_")) for k in deps))

        # Every table directly read must be an ancestor, even if its direct edge is redundant.
        def ancestors(key):
            return deps[key] | set().union(*(ancestors(d) for d in deps[key]))
        for task in self.tasks:
            key = task["task_key"]
            if key == "prepare_source":
                continue
            path = ROOT / "resources" / task["notebook_task"]["notebook_path"]
            reads = set(re.findall(r'\{(silver|gold)\}\.([a-z_]+)', path.read_text()))
            for layer, table in reads:
                parent = f"{layer}_{table}"
                if parent != key:
                    self.assertIn(parent, ancestors(key), (key, parent))

    def test_no_schedule_cluster_or_retry_loop(self):
        self.assertNotIn("schedule", self.job)
        self.assertNotIn("continuous", self.job)
        self.assertNotIn("job_clusters", self.job)
        self.assertEqual(self.job["max_concurrent_runs"], 1)
        self.assertFalse(self.job["queue"]["enabled"])
        for task in self.tasks:
            self.assertEqual(task["max_retries"], 1 if task["task_key"].startswith("bronze_") else 0)
            self.assertTrue(task["disable_auto_optimization"])
            if task["task_key"].startswith("bronze_"):
                self.assertEqual(task["min_retry_interval_millis"], 10000)
            self.assertNotIn("existing_cluster_id", task)
            self.assertNotIn("new_cluster", task)
            self.assertLessEqual(task["timeout_seconds"], 900)

    def test_bronze_is_autoloader_available_now(self):
        for name in source.FILES:
            text = (ROOT / f"notebooks/02-bronze/{name}.py").read_text()
            for expected in ['format("cloudFiles")', '"csv"', "writeStream",
                             "checkpointLocation", "availableNow=True", "awaitTermination"]:
                self.assertIn(expected, text)

    def test_silver_uses_complete_release_and_explicit_merge(self):
        for name in source.FILES:
            text = (ROOT / f"notebooks/03-silver/{name}.py").read_text()
            self.assertIn(f'current_input("{name}")', text)
            self.assertIn("MERGE INTO", text)
            self.assertIn("WHEN NOT MATCHED BY SOURCE THEN DELETE", text)
            self.assertNotIn("foreachBatch", text)

    def test_paths_are_project_owned(self):
        for folder in ["notebooks", "resources"]:
            for path in (ROOT / folder).rglob("*"):
                if path.suffix in [".py", ".yml"]:
                    text = path.read_text()
                    self.assertNotIn("formula1-databricks-incremental-pipeline", text)
                    self.assertNotIn("lakehouse-v2-tools", text)
        bundle = yaml.safe_load((ROOT / "databricks.yml").read_text())
        self.assertEqual(bundle["bundle"]["name"], "formula1-data-pipeline-analytics")

    def test_processing_notebooks_require_prepared_release(self):
        for task in self.tasks:
            if task["task_key"] != "prepare_source":
                path = ROOT / "resources" / task["notebook_task"]["notebook_path"]
                self.assertIn("require_candidate()", path.read_text())

    def test_gold_has_four_materialized_outputs(self):
        paths = list((ROOT / "notebooks/04-gold").glob("*.py"))
        self.assertEqual({p.stem for p in paths},
                         {"race_dimension", "session_results", "driver_season", "constructor_season"})
        for path in paths:
            text = path.read_text()
            self.assertIn('.mode("overwrite")', text)
            self.assertIn(f'saveAsTable(f"{{gold}}.{path.stem}")', text)
            self.assertIn(f'mark_complete("gold_{path.stem}")', text)
            self.assertNotIn("published_releases", text)
            self.assertNotIn("check_reference", text)

    def test_no_analytics_or_publication_notebooks(self):
        self.assertFalse(list((ROOT / "notebooks/05-analytics").glob("*.py")))
        self.assertFalse(list((ROOT / "notebooks/06-control").glob("*.py")))
        text = (ROOT / "notebooks/01-source/prepare_release.py").read_text()
        self.assertIn("attempt_id = str(uuid4())", text)
        self.assertIn("check_release_order(", text)
        self.assertNotIn("published_releases", text)

    def test_generated_files_and_agent_notes_are_ignored(self):
        patterns = (ROOT / ".gitignore").read_text().splitlines()
        for pattern in ["local/", ".databricks/", "__pycache__/", "AGENTS.md", ".env"]:
            self.assertIn(pattern, patterns)

    def test_documentation_links_exist(self):
        for path in [ROOT / "README.md", *sorted((ROOT / "docs").glob("*.md"))]:
            for target in re.findall(r"\]\(([^)]+)\)", path.read_text()):
                if "://" not in target and not target.startswith("#"):
                    self.assertTrue((path.parent / target.split("#")[0]).exists(), (path.name, target))
