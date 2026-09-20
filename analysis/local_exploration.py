"""Offline analysis of pinned CSVs; no Databricks or network connection."""
# %% Setup
from datetime import date, datetime, timezone
import csv
import hashlib
import io
import json
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "local/python-deps"))
sys.path.insert(0, str(ROOT / "tests"))
import duckdb
from support import source, queries, duck_sql, row_contract

RELEASE = "v2026.14.0"
AS_OF = date(2026, 9, 16)
OUT = ROOT / "local/analysis" / RELEASE


def build_database():
    manifest = source.verify_release(ROOT / "local/landing", RELEASE)
    archive = ROOT / "local/landing/archives" / RELEASE / "source.zip"
    assert hashlib.sha256(archive.read_bytes()).hexdigest() == manifest["archive_sha256"]
    db = duckdb.connect()
    for schema in ("raw", "silver", "gold", "ops", "analytics", "explore"):
        db.execute(f"CREATE SCHEMA {schema}")
    values = dict(silver="silver", gold="gold", ops="ops", analytics="analytics",
                  release_seq=manifest["release_seq"], min_season=2010)
    audit = []
    for name, item in manifest["tables"].items():
        path = ROOT / "local/landing" / item["file"]
        escaped = path.as_posix().replace("'", "''")
        db.execute(f"CREATE TABLE raw.{name} AS SELECT * FROM read_csv('{escaped}', header=true, all_varchar=true)")
        count = db.execute(f"SELECT COUNT(*) FROM raw.{name}").fetchone()[0]
        assert count == item["rows"], name
        db.execute(f"CREATE OR REPLACE VIEW source_rows AS SELECT * FROM raw.{name}")
        sql = duck_sql(queries(f"03-silver/{name}.py", values)[0])
        db.execute(f"CREATE TABLE silver.{name} AS {sql}")
        keys, required = row_contract(f"03-silver/{name}.py")
        key_sql = ", ".join(keys)
        duplicates = db.execute(f"SELECT COUNT(*) FROM (SELECT {key_sql} FROM silver.{name} GROUP BY {key_sql} HAVING COUNT(*) > 1)").fetchone()[0]
        null_sql = " OR ".join(f"{col} IS NULL" for col in required)
        nulls = db.execute(f"SELECT COUNT(*) FROM silver.{name} WHERE {null_sql}").fetchone()[0]
        assert duplicates == nulls == 0, (name, duplicates, nulls)
        audit.append(dict(table=name, raw_rows=count, silver_rows=db.execute(f"SELECT COUNT(*) FROM silver.{name}").fetchone()[0], duplicate_keys=duplicates, missing_required=nulls, sha256=item["sha256"]))
    baseline = json.loads((ROOT / "analysis/baseline_queries.json").read_text())
    for name, sql in baseline["gold"].items():
        db.execute(f"CREATE TABLE gold.{name} AS " + duck_sql(sql))
    db.execute("CREATE TABLE ops.published_releases(release_seq BIGINT)")
    db.execute("INSERT INTO ops.published_releases VALUES (?)", [manifest["release_seq"]])
    for sql in baseline["analytics"].values():
        db.execute(duck_sql(sql))
    expected = db.execute("SELECT COUNT(*) FROM silver.race_results").fetchone()[0] + db.execute("SELECT COUNT(*) FROM silver.sprint_results").fetchone()[0]
    assert db.execute("SELECT COUNT(*) FROM analytics.v_race_performance").fetchone()[0] == expected
    with zipfile.ZipFile(archive) as z:
        archive_members = [n for n in z.namelist() if n.endswith(".csv")]
        extra_coverage = []
        for member in ("f1db-races-driver-standings.csv", "f1db-races-constructor-standings.csv",
                       "f1db-races-qualifying-results.csv", "f1db-races-pit-stops.csv"):
            with z.open(member) as stream:
                reader = csv.DictReader(io.TextIOWrapper(stream, encoding="utf-8-sig"))
                columns = reader.fieldnames
                years = {}
                count = 0
                for row in reader:
                    count += 1
                    if row.get("year") in ("2023", "2024", "2025", "2026"):
                        years[row["year"]] = years.get(row["year"], 0) + 1
                extra_coverage.append(dict(file=member, rows=count, columns=columns, recent_rows=years))
    provenance = dict(release=RELEASE, source_url=manifest["source_url"], archive_sha256=manifest["archive_sha256"], as_of=AS_OF.isoformat(), executed_at=datetime.now(timezone.utc).isoformat(), engine="DuckDB local; production transformation SQL reused; no cloud execution", source_audit=audit, available_archive_csvs=archive_members)
    provenance["extra_csv_coverage"] = extra_coverage
    return db, provenance


def export_query(db, name, sql):
    result = db.execute(sql)
    columns = [d[0] for d in result.description]
    rows = result.fetchall()
    with (OUT / f"{name}.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(columns)
        writer.writerows(rows)
    return [dict(zip(columns, row)) for row in rows]


# %% Execute saved SQL and preserve inspectable evidence
def main():
    OUT.mkdir(parents=True, exist_ok=True)
    db, provenance = build_database()
    try:
        db.execute((ROOT / "analysis/setup.sql").read_text(encoding="utf-8"))
        results = {}
        for path in sorted((ROOT / "analysis/queries").glob("*.sql")):
            results[path.stem] = export_query(db, path.stem, path.read_text(encoding="utf-8"))
        assert all(row["failures"] == 0 for row in results["15_quality_checks"])
        assert all(row["race_wins_a"] + row["race_wins_b"] == row["comparable_finishes"]
                   for row in results["06_teammate_comparison"])
        assert all(row["qualifying_wins_a"] + row["qualifying_wins_b"] == row["comparable_qualifying"]
                   for row in results["06_teammate_comparison"])
        assert all(row["calculated_points"] == next(d["source_points"] for d in results["03_driver_season_2025"]
                   if d["driver_name"] == row["driver_name"])
                   for row in results["11_progression_2025"] if row["round"] == 24)
        (OUT / "provenance.json").write_text(json.dumps(provenance, indent=2, default=str), encoding="utf-8")
        (OUT / "results.json").write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")
        print(json.dumps({"source_audit": provenance["source_audit"], "query_rows": {k: len(v) for k, v in results.items()}}, indent=2))
    finally:
        db.close()


if __name__ == "__main__":
    main()
