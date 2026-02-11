"""
Push REDCap metadata and/or records via API.

Usage (dry-run by default):
  python3 push_to_redcap.py --api-url https://your.redcap/api/ --dictionary path.csv --data data.csv

Add --execute to perform the network calls.
"""

from __future__ import annotations

import argparse
import os
import sys

from redcap_api_client import import_metadata, import_records, read_token, summarize_response, RedcapApiError

DEFAULT_TOKEN_PATH = "/Users/dannyzweben/Desktop/TUBRIC/Database/RDCAPI/key.txt"


def read_file(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def main() -> int:
    parser = argparse.ArgumentParser(description="Push REDCap metadata and records using the API.")
    parser.add_argument("--api-url", required=True, help="Base REDCap API URL (ends with /api/).")
    parser.add_argument("--token-path", default=DEFAULT_TOKEN_PATH, help="Path to API token file.")
    parser.add_argument("--dictionary", action="append", default=[], help="Data dictionary CSV to import.")
    parser.add_argument("--data", action="append", default=[], help="Record import CSV to upload.")
    parser.add_argument("--execute", action="store_true", help="Actually perform the API calls.")

    args = parser.parse_args()

    if not args.dictionary and not args.data:
        print("Nothing to push: provide --dictionary and/or --data.")
        return 1

    missing = [p for p in (args.dictionary + args.data) if not os.path.exists(p)]
    if missing:
        print("Missing files:")
        for path in missing:
            print(f"- {path}")
        return 1

    try:
        token = read_token(args.token_path)
    except (OSError, RedcapApiError) as exc:
        print(f"Token error: {exc}")
        return 1

    print("Planned actions:")
    for path in args.dictionary:
        print(f"- Import metadata: {path}")
    for path in args.data:
        print(f"- Import records: {path}")

    if not args.execute:
        print("Dry-run only. Re-run with --execute to perform the API calls.")
        return 0

    try:
        for path in args.dictionary:
            csv_text = read_file(path)
            print(f"Importing metadata: {path}")
            resp = import_metadata(args.api_url, token, csv_text)
            print(summarize_response(resp))

        for path in args.data:
            csv_text = read_file(path)
            print(f"Importing records: {path}")
            resp = import_records(args.api_url, token, csv_text)
            print(summarize_response(resp))
    except RedcapApiError as exc:
        print(f"REDCap API error: {exc}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
