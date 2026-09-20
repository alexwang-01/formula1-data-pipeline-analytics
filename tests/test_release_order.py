"""Test the notebook's pure release guard without importing Spark."""
import ast
from types import SimpleNamespace as Row
import unittest
from support import ROOT

tree = ast.parse((ROOT / "notebooks/00-common/context.py").read_text())
function = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                and node.name == "check_release_order")
namespace = {}
exec(compile(ast.Module(body=[function], type_ignores=[]), "context.py", "exec"), namespace)
check = namespace["check_release_order"]
TASKS = ["silver_drivers_history", "gold_race_dimension", "gold_session_results",
         "gold_driver_season", "gold_constructor_season"]


def release(seq=1, attempt="a", status="RUNNING", scope=2010, digest="hash"):
    return Row(release_seq=seq, attempt_id=attempt, status=status,
               min_season=scope, archive_sha256=digest)


def completed(attempt="a", tasks=TASKS):
    return [Row(release_seq=1, attempt_id=attempt, task_key=name) for name in tasks]


class ReleaseOrderTests(unittest.TestCase):
    def test_first_run_and_latest_retry(self):
        check([], [], 1, 2010, "hash")
        check([release()], [], 1, 2010, "hash")
        check([release(attempt=None, status="PUBLISHED")], [], 1, 2010, "hash")

    def test_later_run_requires_all_terminal_tasks(self):
        check([release()], completed(), 2, 2010, "next-hash")
        for missing in TASKS:
            with self.subTest(missing=missing), self.assertRaisesRegex(ValueError, "unfinished"):
                check([release()], completed(tasks=[n for n in TASKS if n != missing]), 2, 2010, "hash")

    def test_previous_attempt_and_duplicate_markers_do_not_complete_new_attempt(self):
        with self.assertRaisesRegex(ValueError, "unfinished"):
            check([release(attempt="b")], completed(), 2, 2010, "hash")
        with self.assertRaisesRegex(ValueError, "unfinished"):
            check([release()], completed(tasks=[TASKS[0]] * 5), 2, 2010, "hash")

    def test_legacy_completed_run_is_accepted_but_unfinished_is_not(self):
        check([release(attempt=None, status="PUBLISHED")], [], 2, 2010, "hash")
        with self.assertRaisesRegex(ValueError, "unfinished"):
            check([release(attempt=None)], [], 2, 2010, "hash")

    def test_rollback_scope_change_and_source_mutation_are_blocked(self):
        for previous, seq, scope, digest in [([release(seq=2)], 1, 2010, "hash"),
                                            ([release()], 1, 2015, "hash"),
                                            ([release()], 1, 2010, "changed")]:
            with self.assertRaises(ValueError):
                check(previous, [], seq, scope, digest)

    def test_history_expansion_requires_opt_in_and_completed_latest_release(self):
        check([release()], completed(), 1, 1950, "hash", True)
        for markers, seq, scope, digest, allow in [
            (completed(), 1, 1950, "hash", False),
            ([], 1, 1950, "hash", True),
            (completed(), 2, 1950, "next", True),
            (completed(), 1, 2020, "hash", True),
            (completed(), 1, 1950, "changed", True),
        ]:
            with self.subTest(seq=seq, scope=scope, allow=allow), self.assertRaises(ValueError):
                check([release()], markers, seq, scope, digest, allow)

    def test_old_scopes_remain_recorded_after_expansion(self):
        old = release(attempt=None, status="PUBLISHED")
        latest = release(seq=2, scope=1950)
        check([old, latest], [], 2, 1950, "hash")  # Repair an interrupted expanded run.
        markers = [Row(release_seq=2, attempt_id="a", task_key=name) for name in TASKS]
        check([old, latest], markers, 3, 1950, "next")
        with self.assertRaises(ValueError):
            check([old, latest], markers, 2, 2010, "hash", True)
