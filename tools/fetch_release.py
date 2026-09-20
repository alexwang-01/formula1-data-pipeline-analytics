"""Download a pinned F1DB release into this project's ignored local landing area."""
import argparse
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("f1pa_source", ROOT / "notebooks/00-common/source.py")
source = importlib.util.module_from_spec(spec)
spec.loader.exec_module(source)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("release", choices=source.PINNED_RELEASES)
    args = parser.parse_args()
    manifest = source.download_release(args.release, ROOT / "local/landing")
    print(f"{args.release}: verified original CSV files")
    for name, item in manifest["tables"].items():
        print(f"  {name}: {item['rows']:,} source rows")
