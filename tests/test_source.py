import csv
import io
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from support import source


def fixture(changes=None, omit=None):
    stream = io.BytesIO()
    contents = {}
    with zipfile.ZipFile(stream, "w") as archive:
        for table, filename in source.FILES.items():
            if table == omit:
                continue
            row = io.StringIO(newline="")
            writer = csv.writer(row, lineterminator="\r\n")
            writer.writerow(source.REQUIRED_COLUMNS[table])
            writer.writerow(["1"] * len(source.REQUIRED_COLUMNS[table]))
            data = row.getvalue().encode()
            data = (changes or {}).get(table, data)
            archive.writestr(filename, data)
            contents[table] = data
    return stream.getvalue(), contents


class SourceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def prepare(self, data):
        return source.prepare_release(data, source.sha256(data), "v2026.8.1", self.root)

    def test_preserves_original_bytes_and_replay(self):
        payload, contents = fixture()
        first = self.prepare(payload)
        self.assertEqual(first, self.prepare(payload))
        self.assertEqual(first, source.verify_release(self.root, "v2026.8.1"))
        for table, data in contents.items():
            self.assertEqual(data, (self.root / first["tables"][table]["file"]).read_bytes())

    def test_bad_checksum_writes_nothing(self):
        payload, _ = fixture()
        with self.assertRaises(ValueError):
            source.prepare_release(payload, "bad", "v2026.8.1", self.root)
        self.assertEqual(list(self.root.iterdir()), [])

    def test_missing_csv_blocks_ready(self):
        payload, _ = fixture(omit="drivers")
        with self.assertRaises(KeyError):
            self.prepare(payload)
        self.assertFalse((self.root / "manifests").exists())

    def test_missing_required_column(self):
        payload, _ = fixture({"drivers": b"id,name\n1,A\n"})
        with self.assertRaisesRegex(ValueError, "required"):
            self.prepare(payload)

    def test_duplicate_header(self):
        payload, _ = fixture({"drivers": b"id,ID\n1,2\n"})
        with self.assertRaisesRegex(ValueError, "duplicate"):
            self.prepare(payload)

    def test_malformed_csv(self):
        headers = ",".join(source.REQUIRED_COLUMNS["drivers"])
        payload, _ = fixture({"drivers": (headers + "\n1,2\n").encode()})
        with self.assertRaisesRegex(ValueError, "malformed"):
            self.prepare(payload)

    def test_mutated_landing_detected(self):
        payload, _ = fixture()
        manifest = self.prepare(payload)
        path = self.root / manifest["tables"]["drivers"]["file"]
        path.write_bytes(b"changed")
        with self.assertRaises(ValueError):
            source.verify_release(self.root, "v2026.8.1")
        with self.assertRaises(ValueError):
            self.prepare(payload)

    def test_manifest_count_tampering(self):
        payload, _ = fixture()
        manifest = self.prepare(payload)
        manifest["tables"]["drivers"]["rows"] = 999
        (self.root / "manifests/v2026.8.1/READY.json").write_text(json.dumps(manifest))
        with self.assertRaisesRegex(ValueError, "manifest"):
            source.verify_release(self.root, "v2026.8.1")

    def test_bad_release_tags(self):
        for tag in ["../escape", "v2026.08.1", "latest", "v2026.1.1/evil"]:
            with self.subTest(tag=tag), self.assertRaises(ValueError):
                source.release_number(tag)

    def test_release_order_is_numeric(self):
        self.assertLess(source.release_number("v2026.8.2"), source.release_number("v2026.12.0"))

    def test_csv_and_manifest_cannot_disagree_with_zip(self):
        payload, _ = fixture()
        manifest = self.prepare(payload)
        entry = manifest["tables"]["drivers"]
        changed = (self.root / entry["file"]).read_bytes().replace(b"1", b"2")
        (self.root / entry["file"]).write_bytes(changed)
        entry["sha256"] = source.sha256(changed)
        (self.root / "manifests/v2026.8.1/READY.json").write_text(json.dumps(manifest))
        with self.assertRaisesRegex(ValueError, "original archive"):
            source.verify_release(self.root, "v2026.8.1")

    def test_reserved_source_metadata_is_rejected(self):
        headers = source.REQUIRED_COLUMNS["drivers"] + ["_source_file"]
        content = (",".join(headers) + "\n" + ",".join(["1"] * len(headers)) + "\n").encode()
        payload, _ = fixture({"drivers": content})
        with self.assertRaisesRegex(ValueError, "reserved"):
            self.prepare(payload)

    def test_unpinned_download_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "pin"):
            source.download_release("v2026.99.0", self.root)
