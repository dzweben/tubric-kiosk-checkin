"""
Push a single kiosk check-in to REDCap.

This script expects a JSON payload on stdin with:
- guid
- participant
- visit
- contact_updates (list)

It will:
- Look up an existing record by guid.
- If found, append the new visit/contact updates to that record.
- If not found, create a new record (sub_id defaults to guid).

No API calls happen unless --execute is provided.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import os
import sys

from redcap_api_client import (
    RedcapApiError,
    export_records,
    import_records,
    read_token,
    summarize_response,
)

DEFAULT_TOKEN_PATH = "/Users/dannyzweben/Desktop/TUBRIC/Database/RDCAPI/key.txt"
RECORD_ID_FIELD = "sub_id"


def _read_payload() -> dict:
    raw = sys.stdin.read()
    if not raw.strip():
        raise ValueError("No JSON payload provided on stdin.")
    return json.loads(raw)


def _escape_filter_value(value: str) -> str:
    return value.replace("'", "\\'")


def find_record_id(api_url: str, token: str, guid: str) -> str | None:
    filter_logic = f"[guid] = '{_escape_filter_value(guid)}'"
    raw = export_records(api_url, token, fields=[RECORD_ID_FIELD, "guid"], filter_logic=filter_logic)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not data:
        return None
    return data[0].get(RECORD_ID_FIELD)


def get_repeat_instance_max(api_url: str, token: str, guid: str) -> dict:
    filter_logic = f"[guid] = '{_escape_filter_value(guid)}'"
    raw = export_records(api_url, token, filter_logic=filter_logic, export_repeating=True)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {"visits": 0, "contact_updates": 0}

    max_by = {"visits": 0, "contact_updates": 0}
    for row in data:
        instrument = row.get("redcap_repeat_instrument")
        instance = row.get("redcap_repeat_instance")
        if not instrument or instrument not in max_by:
            continue
        try:
            instance_num = int(instance)
        except (TypeError, ValueError):
            continue
        if instance_num > max_by[instrument]:
            max_by[instrument] = instance_num
    return max_by


def build_import_rows(payload: dict, record_id: str, repeat_max: dict) -> list[dict]:
    participant = payload.get("participant", {})
    visit = payload.get("visit", {})
    contact_updates = payload.get("contact_updates", [])

    rows: list[dict] = []

    # Participant (non-repeating)
    rows.append(
        {
            RECORD_ID_FIELD: record_id,
            "guid": payload.get("guid", ""),
            "first_name": participant.get("first_name", ""),
            "last_name": participant.get("last_name", ""),
            "dob": participant.get("dob", ""),
            "primary_email": participant.get("primary_email", ""),
            "primary_phone": participant.get("primary_phone", ""),
            "newsletter_email": participant.get("newsletter_email", ""),
            "newsletter_phone": participant.get("newsletter_phone", ""),
            "newsletter_pref": participant.get("newsletter_pref", ""),
            "consent_participant": participant.get("consent_participant", ""),
            "created_at": participant.get("created_at", ""),
            "last_seen_at": participant.get("last_seen_at", ""),
        }
    )

    # Visit (repeating)
    if visit:
        visit_instance = repeat_max.get("visits", 0) + 1
        visit_number = visit.get("visit_number", "")
        try:
            visit_number_int = int(visit_number)
        except (TypeError, ValueError):
            visit_number_int = None
        if not visit_number_int or visit_number_int <= repeat_max.get("visits", 0):
            visit_number = visit_instance
        rows.append(
            {
                RECORD_ID_FIELD: record_id,
                "redcap_repeat_instrument": "visits",
                "redcap_repeat_instance": visit_instance,
                "visit_number": visit_number,
                "visit_datetime": visit.get("visit_datetime", ""),
                "visit_date": visit.get("visit_date", ""),
                "visit_time": visit.get("visit_time", ""),
                "tubric_study_code": visit.get("tubric_study_code", ""),
                "consent_contact_visit": visit.get("consent_contact_visit", ""),
                "entered_by": visit.get("entered_by", ""),
            }
        )

    # Contact updates (repeating)
    contact_instance = repeat_max.get("contact_updates", 0)
    for cu in contact_updates:
        contact_instance += 1
        rows.append(
            {
                RECORD_ID_FIELD: record_id,
                "redcap_repeat_instrument": "contact_updates",
                "redcap_repeat_instance": contact_instance,
                "contact_type": cu.get("contact_type", ""),
                "contact_value": cu.get("contact_value", ""),
                "added_at": cu.get("added_at", ""),
                "contact_visit_number": cu.get("contact_visit_number", ""),
                "contact_visit_datetime": cu.get("contact_visit_datetime", ""),
            }
        )

    return rows


def rows_to_csv(rows: list[dict]) -> str:
    if not rows:
        return ""
    fieldnames = list({k for row in rows for k in row.keys()})
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    return output.getvalue()


def main() -> int:
    parser = argparse.ArgumentParser(description="Push a single check-in to REDCap.")
    parser.add_argument("--api-url", required=True, help="Base REDCap API URL (ends with /api/).")
    parser.add_argument("--token-path", default=DEFAULT_TOKEN_PATH, help="Path to API token file.")
    parser.add_argument("--execute", action="store_true", help="Actually perform the API call.")
    parser.add_argument(
        "--new-record-id",
        default="guid",
        choices=["guid"],
        help="Strategy for new records (default: use guid as sub_id).",
    )

    args = parser.parse_args()

    try:
        payload = _read_payload()
    except Exception as exc:
        print(f"Invalid payload: {exc}")
        return 1

    guid = payload.get("guid", "")
    if not guid:
        print("Missing guid in payload.")
        return 1

    try:
        token = read_token(args.token_path)
    except (OSError, RedcapApiError) as exc:
        print(f"Token error: {exc}")
        return 1

    record_id = None
    try:
        record_id = find_record_id(args.api_url, token, guid)
    except RedcapApiError as exc:
        print(f"REDCap API error during lookup: {exc}")
        return 1

    if not record_id:
        if args.new_record_id == "guid":
            record_id = guid

    if record_id:
        repeat_max = get_repeat_instance_max(args.api_url, token, guid)
    else:
        repeat_max = {"visits": 0, "contact_updates": 0}

    rows = build_import_rows(payload, record_id, repeat_max)
    csv_text = rows_to_csv(rows)

    print(f"Planned record_id: {record_id}")
    print(f"Rows to import: {len(rows)}")

    if not args.execute:
        print("Dry-run only. Re-run with --execute to perform the API call.")
        return 0

    try:
        resp = import_records(args.api_url, token, csv_text)
        print(summarize_response(resp))
    except RedcapApiError as exc:
        print(f"REDCap API error: {exc}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
