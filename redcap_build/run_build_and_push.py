"""
End-to-end build for REDCap artifacts.

This script:
- Generates data dictionaries.
- Builds import-ready CSVs.
- Optionally pushes to REDCap via API (only with --execute).
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys

BASE_DIR = os.path.dirname(__file__)
OUTPUT_DIR = os.path.join(BASE_DIR, "output")

DICT_FULL = os.path.join(OUTPUT_DIR, "tubric_redcap_data_dictionary.csv")
DICT_DEID = os.path.join(OUTPUT_DIR, "tubric_redcap_deidentified_dictionary.csv")

IMPORT_PARTICIPANT = os.path.join(OUTPUT_DIR, "redcap_import_participant.csv")
IMPORT_VISITS = os.path.join(OUTPUT_DIR, "redcap_import_visits.csv")
IMPORT_CONTACTS = os.path.join(OUTPUT_DIR, "redcap_import_contact_updates.csv")
IMPORT_DEID = os.path.join(OUTPUT_DIR, "redcap_import_deidentified_visits.csv")


def run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build REDCap dictionaries/import files and optionally push.")
    parser.add_argument("--api-url", help="Base REDCap API URL (ends with /api/).")
    parser.add_argument("--push-full", action="store_true", help="Push full (identifiable) project files.")
    parser.add_argument("--push-deid", action="store_true", help="Push de-identified project files.")
    parser.add_argument("--execute", action="store_true", help="Actually perform API calls when pushing.")

    args = parser.parse_args()

    run(["python3", os.path.join(BASE_DIR, "generate_data_dictionary.py")])
    run(["python3", os.path.join(BASE_DIR, "build_import_payloads.py")])

    if not (args.push_full or args.push_deid):
        return 0

    if not args.api_url:
        print("--api-url is required when pushing.")
        return 1

    push_script = os.path.join(BASE_DIR, "push_to_redcap.py")

    if args.push_full:
        cmd = [
            "python3",
            push_script,
            "--api-url",
            args.api_url,
            "--dictionary",
            DICT_FULL,
            "--data",
            IMPORT_PARTICIPANT,
            "--data",
            IMPORT_VISITS,
            "--data",
            IMPORT_CONTACTS,
        ]
        if args.execute:
            cmd.append("--execute")
        run(cmd)

    if args.push_deid:
        cmd = [
            "python3",
            push_script,
            "--api-url",
            args.api_url,
            "--dictionary",
            DICT_DEID,
            "--data",
            IMPORT_DEID,
        ]
        if args.execute:
            cmd.append("--execute")
        run(cmd)

    return 0


if __name__ == "__main__":
    sys.exit(main())
