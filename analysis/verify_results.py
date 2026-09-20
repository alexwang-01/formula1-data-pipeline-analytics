"""Independently recompute headline findings using CSV + Decimal, not SQL."""
from collections import defaultdict
import csv
from decimal import Decimal
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TAG = "v2026.14.0"
LANDING = ROOT / "local/landing"
OUT = ROOT / "local/analysis" / TAG
manifest = json.loads((LANDING / "manifests" / TAG / "READY.json").read_text())
results = json.loads((OUT / "results.json").read_text())


def read_table(name):
    with (LANDING / manifest["tables"][name]["file"]).open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


races = read_table("race_results")
sprints = read_table("sprint_results")
race_info = {r["id"]: r for r in read_table("races")}
points = defaultdict(Decimal)
contribution = defaultdict(Decimal)
after_round_15 = defaultdict(Decimal)
for row in races + sprints:
    if row["year"] != "2025":
        continue
    value = Decimal(row["points"] or "0")
    points[row["driverId"]] += value
    contribution[(row["constructorId"], row["driverId"])] += value
    if int(row["round"]) <= 15:
        after_round_15[row["driverId"]] += value
standings = {r["driverId"]: Decimal(r["points"]) for r in read_table("driver_standings") if r["year"] == "2025"}
assert dict(points) == standings
assert points["lando-norris"] - points["max-verstappen"] == 2
assert max(after_round_15.values()) - after_round_15["max-verstappen"] == 104
for row in results["04_team_contribution"]:
    if row["season"] == 2025:
        assert contribution[(row["constructor_id"], row["driver_id"]) ] == Decimal(row["earned_points"])

singapore_winners = [r for r in races if 2010 <= int(r["year"]) <= 2025
                     and race_info[r["raceId"]]["grandPrixId"] == "singapore"
                     and r["positionNumber"] == "1"]
assert len(singapore_winners) == 14
assert sum(r["gridPositionNumber"] == "1" for r in singapore_winners) == 10
assert all(r["gridPositionNumber"] == "1" for r in singapore_winners if int(r["year"]) >= 2023)

paired = defaultdict(list)
for row in races:
    if row["year"] == "2025" and row["constructorId"] == "mclaren":
        paired[row["raceId"]].append(row)
double_scores = sum(len(rows) == 2 and all(Decimal(r["points"] or "0") > 0 for r in rows)
                    for rows in paired.values())
assert double_scores == 20 and len(paired) == 24

latest_points = defaultdict(Decimal)
all_2026 = defaultdict(Decimal)
for row in races + sprints:
    if row["year"] == "2026":
        all_2026[row["constructorId"]] += Decimal(row["points"] or "0")
        if row["round"] == "14":
            latest_points[row["constructorId"]] += Decimal(row["points"] or "0")
for row in read_table("constructor_standings"):
    if row["year"] == "2026" and row["positionNumber"]:
        key = row["constructorId"]
        assert all_2026[key] - Decimal(row["points"]) == latest_points[key]

receipt = dict(status="PASS", method="stdlib CSV + Decimal, independent of DuckDB queries",
               checks=["All 2025 driver totals vs source standings", "2025 final title gap: 2",
                       "2025 round-15 Verstappen gap: 104", "All 2025 team contribution amounts",
                       "Singapore: 10/14 P1-start winners; 3/3 since 2023",
                       "McLaren double-score weekends: 20/24",
                       "All 11 constructor 2026 differences equal round-14 earned points"])
(OUT / "independent_checks.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
print(json.dumps(receipt, indent=2))
