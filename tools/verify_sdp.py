"""Cloud parity checks for the isolated SDP implementation. No pipeline writes."""
import argparse
import csv
import json
import os
import time
from pathlib import Path

from databricks_client import command, query, WAREHOUSE, CATALOG

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "local/sdp-validation"
PIPELINE = os.environ.get("DATABRICKS_PIPELINE_ID")
JOB = os.environ.get("DATABRICKS_JOB_ID")
TAGS = ["v2026.8.1", "v2026.8.2", "v2026.14.0"]
SILVER_KEYS = {
    "drivers": ["driver_id"], "constructors": ["constructor_id"],
    "circuits": ["circuit_id"], "races": ["race_id"],
    "race_results": ["race_id", "driver_id", "car_number"],
    "sprint_results": ["race_id", "driver_id", "car_number"],
    "driver_standings": ["season", "driver_id"],
    "constructor_standings": ["season", "constructor_id", "engine_manufacturer_id", "entry_category"],
}
GOLD_KEYS = {
    "race_dimension": ["race_id"],
    "session_results": ["race_id", "session_type", "driver_id", "car_number"],
    "driver_season": ["season", "driver_id"],
    "constructor_season": ["season", "constructor_id", "engine_manufacturer_id"],
}


def save(name, value):
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    (EVIDENCE / (name + ".json")).write_text(json.dumps(value, indent=2), encoding="utf-8")


def status(run_id):
    run = command("jobs", "get-run", run_id)
    save("run-" + run_id, run)
    print(json.dumps({"run": run_id, "state": run["state"], "tasks": [
        {"task": task["task_key"], "state": task["state"], "run_id": task["run_id"]}
        for task in run["tasks"]]}, indent=2))
    if not PIPELINE:
        raise RuntimeError("Set DATABRICKS_PIPELINE_ID before checking pipeline status")
    pipeline = command("pipelines", "get", PIPELINE)
    save("pipeline", pipeline)
    print("Pipeline:", pipeline["state"])
    return run


def verify(label):
    if not WAREHOUSE or not CATALOG:
        raise RuntimeError("Set DATABRICKS_WAREHOUSE_ID and DATABRICKS_CATALOG before verification")
    report = {}
    try:
        names = list(SILVER_KEYS)
        actual = query(" UNION ALL ".join(
            f"SELECT '{name}', release_tag, COUNT(*), COUNT(DISTINCT _source_file) "
            f"FROM f1pa_sdp_bronze.{name} GROUP BY release_tag" for name in names))
        expected = {}
        for tag in TAGS:
            manifest = json.loads((ROOT / "local/landing/manifests" / tag / "READY.json").read_text())
            for name, entry in manifest["tables"].items():
                expected[(name, tag)] = entry["rows"]
        assert {(r[0], r[1]): int(r[2]) for r in actual} == expected, actual
        assert all(int(r[3]) == 1 for r in actual), actual
        report["bronze"] = actual

        columns = query("SELECT table_schema, table_name, column_name, ordinal_position, data_type "
                        "FROM information_schema.columns WHERE table_schema IN "
                        "('f1pa_silver', 'f1pa_gold', 'f1pa_sdp_silver', 'f1pa_sdp_gold') "
                        "ORDER BY table_schema, table_name, ordinal_position")
        report["columns"] = columns
        checks = []
        for layer, tables in [("silver", SILVER_KEYS), ("gold", GOLD_KEYS)]:
            for name, keys in tables.items():
                manual, sdp = f"f1pa_{layer}.{name}", f"f1pa_sdp_{layer}.{name}"
                manual_columns = {r[2]: r[4] for r in columns if r[0] == f"f1pa_{layer}" and r[1] == name}
                sdp_columns = {r[2]: r[4] for r in columns if r[0] == f"f1pa_sdp_{layer}" and r[1] == name}
                assert manual_columns and manual_columns == sdp_columns, (manual, manual_columns, sdp_columns)
                # Manual schema migrations can append columns in a different physical order.
                selected = ", ".join(f"`{column}`" for column in manual_columns)
                checks.append(f"""SELECT '{layer}.{name}' AS dataset,
                    (SELECT COUNT(*) FROM (SELECT {selected} FROM {manual} EXCEPT ALL SELECT {selected} FROM {sdp})) AS missing,
                    (SELECT COUNT(*) FROM (SELECT {selected} FROM {sdp} EXCEPT ALL SELECT {selected} FROM {manual})) AS extra,
                    (SELECT COUNT(*) FROM {sdp}) AS rows,
                    (SELECT COUNT(*) FROM (SELECT {', '.join(keys)} FROM {sdp}
                     GROUP BY {', '.join(keys)} HAVING COUNT(*) > 1)) AS duplicate_keys""")
        results = query(" UNION ALL ".join(checks))
        report["parity"] = results
        assert len(results) == 12 and all(int(r[1]) == int(r[2]) == int(r[4]) == 0 for r in results), results

        columns = "driver_id, driver_name, full_name, nationality_country_id, date_of_birth"
        manual = f"SELECT {columns}, valid_from_release, valid_to_release FROM f1pa_silver.drivers_history"
        sdp = f"SELECT {columns}, __START_AT AS valid_from_release, __END_AT AS valid_to_release FROM f1pa_sdp_silver.drivers_history"
        history = query(f"""SELECT
            (SELECT COUNT(*) FROM (({manual}) EXCEPT ALL ({sdp}))) AS missing,
            (SELECT COUNT(*) FROM (({sdp}) EXCEPT ALL ({manual}))) AS extra,
            COUNT(*) AS versions, COUNT_IF(__END_AT IS NULL) AS current_versions,
            COUNT_IF(__END_AT <= __START_AT) AS invalid_intervals
            FROM f1pa_sdp_silver.drivers_history""")
        report["history"] = history
        assert history == [["0", "0", "1147", "917", "0"]], history

        references = [
            ("races", "circuits", ["circuit_id"]),
            ("race_results", "races", ["race_id", "season", "round"]),
            ("race_results", "drivers", ["driver_id"]),
            ("race_results", "constructors", ["constructor_id"]),
            ("sprint_results", "races", ["race_id", "season", "round"]),
            ("sprint_results", "drivers", ["driver_id"]),
            ("sprint_results", "constructors", ["constructor_id"]),
            ("driver_standings", "drivers", ["driver_id"]),
            ("constructor_standings", "constructors", ["constructor_id"]),
        ]
        checks = [f"""SELECT '{child} -> {parent}', COUNT(*)
            FROM f1pa_sdp_silver.{child} c LEFT ANTI JOIN f1pa_sdp_silver.{parent} p
            ON {' AND '.join('c.' + key + ' = p.' + key for key in keys)}"""
            for child, parent, keys in references]
        report["references"] = query(" UNION ALL ".join(checks))
        assert all(int(r[1]) == 0 for r in report["references"]), report["references"]

        fields = ["sprintRaceLaps", "sprintRaceDistance", "sprintRaceScheduledLaps", "sprintRaceScheduledDistance"]
        report["evolved_columns"] = query("SELECT release_tag, " + ", ".join(
            f"COUNT(NULLIF({name}, ''))" for name in fields) + " FROM f1pa_sdp_bronze.races GROUP BY release_tag")
        expected_fields = {}
        for tag in TAGS:
            manifest = json.loads((ROOT / "local/landing/manifests" / tag / "READY.json").read_text())
            with (ROOT / "local/landing" / manifest["tables"]["races"]["file"]).open(encoding="utf-8-sig", newline="") as stream:
                rows = list(csv.DictReader(stream))
            expected_fields[tag] = [sum(bool(row.get(name)) for row in rows) for name in fields]
        assert {r[0]: list(map(int, r[1:])) for r in report["evolved_columns"]} == expected_fields
        report["releases"] = query("SELECT release_tag, status FROM f1pa_sdp_ops.releases ORDER BY release_seq")
        assert report["releases"] == [[tag, "COMPLETE"] for tag in TAGS]
        report["status"] = "PASS"
    except Exception as error:
        report["status"] = "FAIL"
        report["error"] = str(error)
        raise
    finally:
        command("warehouses", "stop", WAREHOUSE)
        report["warehouse"] = command("warehouses", "get", WAREHOUSE)["state"]
        save(label, report)
        print(json.dumps(report, indent=2))
    assert report["warehouse"] == "STOPPED"


def wait_for_run(run_id):
    deadline = time.monotonic() + 3600
    previous = None
    while time.monotonic() < deadline:
        run = command("jobs", "get-run", run_id)
        summary = [(task["task_key"], task["state"]["life_cycle_state"],
                    task["state"].get("result_state")) for task in run["tasks"]]
        if summary != previous:
            print(json.dumps(summary), flush=True)
            previous = summary
        if run["state"]["life_cycle_state"] in ("TERMINATED", "SKIPPED", "INTERNAL_ERROR"):
            save("run-" + run_id, run)
            if run["state"].get("result_state") != "SUCCESS":
                for task in run["tasks"]:
                    if task["state"].get("result_state") in ("FAILED", "TIMEDOUT"):
                        output = command("jobs", "get-run-output", str(task["run_id"]))
                        save("error-" + str(task["run_id"]), output)
                        print(json.dumps(output), flush=True)
                raise RuntimeError(run["state"])
            print("Run succeeded: " + run_id, flush=True)
            return
        time.sleep(20)
    command("jobs", "cancel-run", run_id, "--no-wait")
    raise TimeoutError("SDP verification run exceeded its wait budget; cancellation requested")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["status", "wait", "verify", "idle"])
    parser.add_argument("--run-id")
    parser.add_argument("--label", default="final")
    args = parser.parse_args()
    if args.action == "status":
        status(args.run_id)
    elif args.action == "wait":
        wait_for_run(args.run_id)
    elif args.action == "verify":
        verify(args.label)
    else:
        if not JOB or not PIPELINE or not WAREHOUSE:
            raise RuntimeError("Set DATABRICKS_JOB_ID, DATABRICKS_PIPELINE_ID, and DATABRICKS_WAREHOUSE_ID before idle checks")
        runs = command("jobs", "list-runs", "--job-id", JOB, "--active-only")
        pipeline = command("pipelines", "get", PIPELINE)
        warehouse = command("warehouses", "get", WAREHOUSE)
        clusters = command("clusters", "list")
        state = {"active_runs": runs, "pipeline": pipeline["state"], "warehouse": warehouse["state"],
                 "active_clusters": [c["cluster_id"] for c in clusters
                                     if c["state"] not in ("TERMINATED", "ERROR", "UNKNOWN")]}
        save("idle", state)
        print(json.dumps(state))
