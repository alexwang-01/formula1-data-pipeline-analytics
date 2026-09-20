"""Small Databricks CLI helpers shared by read-only verification scripts."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
WAREHOUSE = os.environ.get("DATABRICKS_WAREHOUSE_ID")
CATALOG = os.environ.get("DATABRICKS_CATALOG")
PROFILE = os.environ.get("DATABRICKS_PROFILE", "DEFAULT")


def require_setting(value, name):
    if not value:
        raise RuntimeError(f"Set {name} before running cloud verification")
    return value


def command(*args):
    env = dict(os.environ)
    config = ROOT / "local/databrickscfg"
    if config.exists():
        env["DATABRICKS_CONFIG_FILE"] = str(config)
    local_cli = ROOT / "local/databricks.exe"
    cli = str(local_cli) if local_cli.exists() else shutil.which("databricks")
    if not cli:
        raise RuntimeError("Install the Databricks CLI or place it under local/databricks.exe")
    result = subprocess.run(
        [cli, *args, "--profile", PROFILE, "-o", "json"],
        env=env,
        text=True,
        encoding="utf-8",
        capture_output=True,
        timeout=180,
    )
    if result.returncode:
        raise RuntimeError(result.stderr or result.stdout)
    return json.loads(result.stdout) if result.stdout.strip() else {}


def query(sql):
    warehouse = require_setting(WAREHOUSE, "DATABRICKS_WAREHOUSE_ID")
    catalog = require_setting(CATALOG, "DATABRICKS_CATALOG")
    response = command("api", "post", "/api/2.0/sql/statements", "--json", json.dumps({
        "warehouse_id": warehouse,
        "catalog": catalog,
        "statement": sql,
        "wait_timeout": "10s",
        "row_limit": 1000,
        "byte_limit": 1000000,
    }))
    statement_id = response["statement_id"]
    deadline = time.monotonic() + 300
    try:
        while response["status"]["state"] in ("PENDING", "RUNNING"):
            if time.monotonic() > deadline:
                raise TimeoutError("Databricks verification SQL timed out")
            time.sleep(3)
            response = command("api", "get", f"/api/2.0/sql/statements/{statement_id}")
        if response["status"]["state"] != "SUCCEEDED":
            raise RuntimeError(response["status"])
        if response.get("manifest", {}).get("truncated") or response.get("result", {}).get("next_chunk_index"):
            raise ValueError("Incomplete SQL result")
        return response.get("result", {}).get("data_array", [])
    finally:
        if response["status"]["state"] in ("PENDING", "RUNNING"):
            command("api", "post", f"/api/2.0/sql/statements/{statement_id}/cancel")
