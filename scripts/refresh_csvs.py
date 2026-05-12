"""
Refresh the EDINET code list and fund code list CSVs shipped with edinet-tools.

The FSA publishes both files at:
    https://disclosure2.edinet-fsa.go.jp/weee0020.aspx

This script downloads the two ZIPs, extracts the CSVs, and writes them into
``edinet_tools/data/`` with a ``_YYYYMMDD`` date suffix so that
``EntityClassifier._find_latest_file`` picks them up automatically.

Run before cutting a release:

    python scripts/refresh_csvs.py

Existing dated CSVs are kept (older snapshots may be useful for debugging
historical classifications). To prune, delete them manually.
"""
from __future__ import annotations

import argparse
import datetime as dt
import io
import sys
import urllib.request
import zipfile
from pathlib import Path

EDINET_CODE_URL = "https://disclosure2dl.edinet-fsa.go.jp/searchdocument/codelist/Edinetcode.zip"
FUND_CODE_URL = "https://disclosure2dl.edinet-fsa.go.jp/searchdocument/codelist/Fundcode.zip"

DATA_DIR = Path(__file__).resolve().parent.parent / "edinet_tools" / "data"


def download_and_extract(url: str, expected_csv_name: str, out_path: Path) -> int:
    """Download a ZIP from ``url``, extract ``expected_csv_name``, write to ``out_path``.

    Returns the number of bytes written.
    """
    print(f"  fetching {url}", flush=True)
    with urllib.request.urlopen(url, timeout=60) as resp:
        zip_bytes = resp.read()

    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        names = zf.namelist()
        if expected_csv_name not in names:
            raise RuntimeError(
                f"Expected {expected_csv_name!r} in zip but found {names!r}"
            )
        csv_bytes = zf.read(expected_csv_name)

    out_path.write_bytes(csv_bytes)
    return len(csv_bytes)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--date",
        default=dt.date.today().strftime("%Y%m%d"),
        help="Date suffix to use, YYYYMMDD (default: today)",
    )
    args = parser.parse_args()

    if not DATA_DIR.exists():
        print(f"data directory not found: {DATA_DIR}", file=sys.stderr)
        return 1

    date_suffix = args.date
    print(f"Refreshing EDINET CSVs into {DATA_DIR} (date suffix: {date_suffix})")

    targets = [
        (EDINET_CODE_URL, "EdinetcodeDlInfo.csv", DATA_DIR / f"EdinetcodeDlInfo_{date_suffix}.csv"),
        (FUND_CODE_URL, "FundcodeDlInfo.csv", DATA_DIR / f"FundcodeDlInfo_{date_suffix}.csv"),
    ]

    for url, csv_name, out_path in targets:
        if out_path.exists():
            print(f"  {out_path.name} already exists, overwriting")
        n_bytes = download_and_extract(url, csv_name, out_path)
        print(f"  wrote {out_path.name} ({n_bytes:,} bytes)")

    print("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
