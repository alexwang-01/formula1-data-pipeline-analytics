# Databricks notebook source
"""Download and preserve selected CSV members without rewriting their bytes."""
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import re
import tempfile
import urllib.request
import zipfile

FILES = {
    "drivers": "f1db-drivers.csv",
    "constructors": "f1db-constructors.csv",
    "circuits": "f1db-circuits.csv",
    "races": "f1db-races.csv",
    "race_results": "f1db-races-race-results.csv",
    "sprint_results": "f1db-races-sprint-race-results.csv",
    "driver_standings": "f1db-seasons-driver-standings.csv",
    "constructor_standings": "f1db-seasons-constructor-standings.csv",
}
REQUIRED_COLUMNS = {
    "drivers": [
        "id",
        "name",
        "fullName",
        "nationalityCountryId",
        "dateOfBirth"
    ],
    "constructors": [
        "id",
        "name",
        "countryId"
    ],
    "circuits": [
        "id",
        "name",
        "countryId",
        "type"
    ],
    "races": [
        "id",
        "year",
        "round",
        "date",
        "grandPrixId",
        "officialName",
        "circuitId"
    ],
    "race_results": [
        "raceId",
        "year",
        "round",
        "driverId",
        "constructorId",
        "driverNumber",
        "positionNumber",
        "positionText",
        "gridPositionNumber",
        "gridPositionText",
        "points",
        "laps",
        "reasonRetired"
    ],
    "sprint_results": [
        "raceId",
        "year",
        "round",
        "driverId",
        "constructorId",
        "driverNumber",
        "positionNumber",
        "positionText",
        "gridPositionNumber",
        "gridPositionText",
        "points",
        "laps",
        "reasonRetired"
    ],
    "driver_standings": [
        "year",
        "driverId",
        "positionNumber",
        "positionText",
        "points",
        "championshipWon"
    ],
    "constructor_standings": [
        "year",
        "constructorId",
        "positionNumber",
        "positionText",
        "points",
        "championshipWon"
    ]
}

PINNED_RELEASES = {
    "v2026.8.1": "db367c6bdb43b2cdf25000b6f6253a846941619f128f78ad44ff92940c57f097",
    "v2026.8.2": "06332d37419b8605afc73cb1590cdf5452d9fdae50fb530407634897fc3afd0d",
    "v2026.12.0": "76a0fa960eccdfeb759c78da16da6099cdc98424ed9457821248e763c75db05a",
    "v2026.13.0": "82a5102e1157a4096cd38bae72e581aaa52083d2ceca7942acfe7744e214c9a6",
    "v2026.14.0": "8a92b898bc237bd3b0a86fe5665ebe0e8f8328f126e2422ca9946d175d66dfb4",
}


def release_number(tag):
    match = re.fullmatch(r"v(\d{4})\.(\d{1,3})\.(\d{1,3})", tag)
    if not match:
        raise ValueError("Use a release tag such as v2026.8.1")
    year, release, patch = map(int, match.groups())
    if tag != f"v{year}.{release}.{patch}":
        raise ValueError("Release tag must use canonical numeric components")
    return year * 1000000 + release * 1000 + patch


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def immutable_file(path, data, staging):
    path = Path(path)
    if path.exists():
        if path.read_bytes() != data:
            raise ValueError(f"Immutable file changed: {path.name}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    Path(staging).mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=staging, delete=False) as stream:
        temporary = Path(stream.name)
        stream.write(data)
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def prepare_release(payload, expected_hash, tag, landing):
    seq = release_number(tag)
    if sha256(payload) != expected_hash:
        raise ValueError("Archive checksum mismatch")
    landing = Path(landing)
    manifest = {"release_tag": tag, "release_seq": seq, "archive_sha256": expected_hash,
                "source_url": f"https://github.com/f1db/f1db/releases/download/{tag}/f1db-csv.zip",
                "tables": {}}
    extracted = {}
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        members = archive.infolist()
        names = [entry.filename for entry in members]
        if len(names) != len(set(names)) or len(names) > 200:
            raise ValueError("Duplicate or excessive ZIP members")
        if sum(entry.file_size for entry in members) > 250000000:
            raise ValueError("Archive expands beyond the source size limit")
        for table, filename in FILES.items():
            data = archive.read(filename)
            reader = csv.DictReader(io.StringIO(data.decode("utf-8-sig"), newline=""), strict=True)
            headers = reader.fieldnames or []
            if not headers or any(not h for h in headers) or len({h.lower() for h in headers}) != len(headers):
                raise ValueError(f"{table}: missing or duplicate headers")
            if not set(REQUIRED_COLUMNS[table]).issubset(headers):
                raise ValueError(f"{table}: required source columns are missing")
            if any(h.startswith("_") or h == "release_tag" for h in headers):
                raise ValueError(f"{table}: reserved metadata column")
            count = 0
            for row in reader:
                if None in row or any(value is None for value in row.values()):
                    raise ValueError(f"{table}: malformed CSV row")
                count += 1
            if count == 0 and table != "sprint_results":
                raise ValueError(f"{table}: unexpectedly empty source")
            relative = f"csv/{table}/release_tag={tag}/{filename}"
            extracted[relative] = data
            manifest["tables"][table] = {"file": relative, "sha256": sha256(data),
                                        "rows": count, "columns": headers}
    staging = landing / "_staging"
    immutable_file(landing / "archives" / tag / "source.zip", payload, staging)
    for relative, data in extracted.items():
        immutable_file(landing / relative, data, staging)
    ready = json.dumps(manifest, indent=2, sort_keys=True).encode("utf-8")
    immutable_file(landing / "manifests" / tag / "READY.json", ready, staging)
    return manifest


def verify_release(landing, tag):
    release_number(tag)
    landing = Path(landing)
    manifest = json.loads((landing / "manifests" / tag / "READY.json").read_text())
    if manifest["release_tag"] != tag or manifest["release_seq"] != release_number(tag):
        raise ValueError("Manifest identity mismatch")
    if set(manifest["tables"]) != set(FILES):
        raise ValueError("Incomplete manifest")
    archived = (landing / "archives" / tag / "source.zip").read_bytes()
    if sha256(archived) != manifest["archive_sha256"]:
        raise ValueError("Stored archive changed")
    archive = zipfile.ZipFile(io.BytesIO(archived))
    for table, filename in FILES.items():
        entry = manifest["tables"][table]
        relative = f"csv/{table}/release_tag={tag}/{filename}"
        if entry["file"] != relative or sha256((landing / relative).read_bytes()) != entry["sha256"]:
            raise ValueError(f"{table}: source file changed")
        if entry["sha256"] != sha256(archive.read(filename)):
            raise ValueError(f"{table}: file no longer matches the original archive")
        reader = csv.DictReader(io.StringIO((landing / relative).read_bytes().decode("utf-8-sig"), newline=""), strict=True)
        if reader.fieldnames != entry["columns"] or sum(1 for _ in reader) != entry["rows"]:
            raise ValueError(f"{table}: manifest schema or count changed")
    archive.close()
    return manifest


def download_release(tag, landing):
    if tag not in PINNED_RELEASES:
        raise ValueError("Review and pin the source checksum before adding a release")
    if (Path(landing) / "manifests" / tag / "READY.json").exists():
        manifest = verify_release(landing, tag)
        if manifest["archive_sha256"] != PINNED_RELEASES[tag]:
            raise ValueError("Manifest does not match the pinned release")
        return manifest
    url = f"https://github.com/f1db/f1db/releases/download/{tag}/f1db-csv.zip"
    request = urllib.request.Request(url, headers={"User-Agent": "formula1-data-pipeline-analytics"})
    with urllib.request.urlopen(request, timeout=120) as response:
        payload = response.read(100000001)
    if len(payload) > 100000000:
        raise ValueError("Archive exceeds the download size limit")
    return prepare_release(payload, PINNED_RELEASES[tag], tag, landing)
