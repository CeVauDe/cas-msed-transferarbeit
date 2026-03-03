"""Download raw Jahresbericht Excel files from the project's GitHub Release.

Usage (from poc/):
    uv run --package mcp-server python apps/mcp_server/src/tools/download_data.py

The files are extracted into apps/mcp_server/data/raw/.
Pass --release-url to override the default download URL.
"""

import argparse
import shutil
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

DEFAULT_RELEASE_URL = (
    "https://github.com/CeVauDe/cas-msed-transferarbeit/releases/download/"
    "data-v1/jahresberichte-raw-data.zip"
)

EXPECTED_FILE_COUNT = 24


def download_and_extract(release_url: str, raw_dir: Path) -> None:
    raw_dir.mkdir(parents=True, exist_ok=True)

    print(f"Downloading: {release_url}")
    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
        tmp_path = Path(tmp.name)

    try:
        urllib.request.urlretrieve(release_url, tmp_path)  # noqa: S310
        print(f"Downloaded to temporary file ({tmp_path.stat().st_size / 1024:.1f} KB)")

        with zipfile.ZipFile(tmp_path) as zf:
            members = zf.namelist()
            xlsx_members = [m for m in members if m.endswith(".xlsx")]
            print(f"Archive contains {len(members)} entries, {len(xlsx_members)} .xlsx files")

            for member in members:
                # Strip any leading directory component so files land directly in raw_dir.
                member_path = Path(member)
                target = raw_dir / member_path.name
                if member_path.name == "" or member_path.name == member_path.parent.name:
                    continue  # skip directory entries
                with zf.open(member) as src, open(target, "wb") as dst:
                    shutil.copyfileobj(src, dst)

    finally:
        tmp_path.unlink(missing_ok=True)

    xlsx_files = sorted(raw_dir.glob("Jahresbericht*.xlsx"))
    print(f"\nExtracted {len(xlsx_files)} Jahresbericht*.xlsx files to: {raw_dir}")
    for f in xlsx_files:
        print(f"  {f.name}")

    if len(xlsx_files) < EXPECTED_FILE_COUNT:
        print(
            f"\nWARNING: expected {EXPECTED_FILE_COUNT} files, found {len(xlsx_files)}.",
            file=sys.stderr,
        )
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--release-url",
        default=DEFAULT_RELEASE_URL,
        help="Direct download URL for the zip archive (default: GitHub Release data-v1)",
    )
    args = parser.parse_args()

    raw_dir = Path(__file__).parent.parent.parent / "data" / "raw"
    download_and_extract(args.release_url, raw_dir)
    print("\nDone. Run load_jahresbericht.py next to generate the consolidated Parquet file.")


if __name__ == "__main__":
    main()
