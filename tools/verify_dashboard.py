"""Read-only checks of the exact dashboard datasets on the SQL warehouse."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog", default=os.environ.get("DATABRICKS_CATALOG"), required=not os.environ.get("DATABRICKS_CATALOG"))
    parser.add_argument("--warehouse", default=os.environ.get("DATABRICKS_WAREHOUSE_ID"), required=not os.environ.get("DATABRICKS_WAREHOUSE_ID"))
    parser.add_argument("--profile", default=os.environ.get("DATABRICKS_PROFILE", "DEFAULT"))
    parser.add_argument("--keep-running", action="store_true", help="Leave warehouse available for UI checks")
    args = parser.parse_args()
    env = os.environ.copy()
    env["DATABRICKS_CONFIG_FILE"] = str(ROOT / "local/databrickscfg")
    evidence = ROOT / "local/validation/dashboard"
    evidence.mkdir(parents=True, exist_ok=True)

    def api(method, path, request=None):
        command = [str(ROOT / "local/databricks.exe"), "api", method, path,
                   "--profile", args.profile, "-o", "json"]
        if request is not None:
            request_path = evidence / "request.json"
            request_path.write_text(json.dumps(request), encoding="utf-8")
            command += ["--json", "@" + str(request_path)]
        result = subprocess.run(command, env=env, capture_output=True, text=True,
                                encoding="utf-8", timeout=180)
        if result.returncode:
            raise RuntimeError(result.stderr)
        return json.loads(result.stdout) if result.stdout.strip() else {}

    active = None
    report = {}
    try:
        dashboard = json.loads((ROOT / "dashboards/formula1.lvdash.json").read_text())
        for dataset in dashboard["datasets"]:
            sql = "".join(dataset["queryLines"]).rstrip().rstrip(";")
            name = dataset["name"]
            if name.endswith("_career"):
                identity = name.removesuffix("_career")
                summary = f"""SELECT COUNT(*) AS rows,
                    COUNT(DISTINCT {identity}_id) AS identities,
                    COUNT_IF({identity}_name IS NULL) AS missing_names,
                    SUM(championships) AS titles, SUM(race_wins) AS wins,
                    COUNT_IF(titles_rank <= 10 AND championships > 0) AS top_titles,
                    COUNT_IF(wins_rank <= 10 AND race_wins > 0) AS top_wins,
                    COUNT_IF(podiums_rank <= 10 AND race_podiums > 0) AS top_podiums
                    FROM dataset"""
            elif name.endswith("_wins"):
                summary = """SELECT season, COUNT(*) AS rows, SUM(race_wins) AS race_wins,
                    COUNT_IF(race_wins <= 0) AS invalid_winners
                    FROM dataset GROUP BY season ORDER BY season"""
            elif name == "results":
                summary = """SELECT season, session_type, COUNT(*) AS rows, SUM(points) AS points,
                    COUNT_IF(driver_name IS NULL OR constructor_name IS NULL OR race_name IS NULL) AS missing_names
                    FROM dataset GROUP BY season, session_type ORDER BY season, session_type"""
            else:
                identity = "driver_name" if name == "drivers" else "constructor_name"
                summary = f"""SELECT season, COUNT(*) AS rows, SUM(source_points) AS source_points,
                    SUM(calculated_points) AS calculated_points, SUM(points_difference) AS difference,
                    COUNT_IF({identity} IS NULL) AS missing_names,
                    MAX(CASE WHEN source_position = 1 THEN {identity} END) AS leader,
                    MAX(CASE WHEN source_position = 1 THEN source_points END) AS leader_points
                    FROM dataset GROUP BY season ORDER BY season"""
            response = api("post", "/api/2.0/sql/statements", {
                "warehouse_id": args.warehouse, "catalog": args.catalog,
                "statement": "WITH dataset AS (\n" + sql + "\n) " + summary,
                "wait_timeout": "10s", "on_wait_timeout": "CONTINUE", "row_limit": 1000})
            active = response["statement_id"]
            deadline = time.monotonic() + 600
            while response["status"]["state"] in ("PENDING", "RUNNING"):
                if time.monotonic() > deadline:
                    raise TimeoutError(name)
                time.sleep(3)
                response = api("get", "/api/2.0/sql/statements/" + active)
            (evidence / f"{name}.json").write_text(json.dumps(response, indent=2), encoding="utf-8")
            if response["status"]["state"] != "SUCCEEDED":
                raise RuntimeError(response["status"])
            active = None
            if response["manifest"].get("truncated") or response.get("result", {}).get("next_chunk_index"):
                raise ValueError("Incomplete result")
            columns = [c["name"] for c in response["manifest"]["schema"]["columns"]]
            rows = [dict(zip(columns, r)) for r in response["result"]["data_array"]]
            total = sum(int(r["rows"]) for r in rows)
            expected = {"drivers": 1681, "constructors": 720, "results": 28189}.get(name, total)
            assert total == expected and total > 0, name
            if name.endswith("_career"):
                assert int(rows[0]["identities"]) == total and int(rows[0]["missing_names"]) == 0
                assert all(int(rows[0][k]) == 10 for k in ["top_titles", "top_wins", "top_podiums"])
                assert int(rows[0]["titles"]) == (76 if name == "driver_career" else 68)
            elif name.endswith("_wins"):
                assert all(int(r["invalid_winners"]) == 0 for r in rows), name
                assert next(int(r["race_wins"]) for r in rows if r["season"] == "2025") == 24, name
            else:
                assert all(int(r["missing_names"]) == 0 for r in rows), name
            report[name] = {"rows": expected, "seasons": len(set(r.get("season") for r in rows)),
                            "sample": rows if name.endswith("_career") else [r for r in rows if r["season"] == "2025"]}
            print(name, json.dumps(report[name]), flush=True)
        report["status"] = "PASS"
    except Exception as error:
        report["status"] = "FAIL"
        report["error"] = str(error)
        raise
    finally:
        try:
            if active:
                api("post", f"/api/2.0/sql/statements/{active}/cancel")
        finally:
            try:
                if not args.keep_running or report.get("status") != "PASS":
                    api("post", f"/api/2.0/sql/warehouses/{args.warehouse}/stop")
            finally:
                (evidence / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
