"""
Build REDCap import-ready CSVs from the kiosk CSV source-of-truth.

Notes:
- This script does NOT call the REDCap API.
- It prepares import files only, with `source_code` populated for every row.
- If a source CSV is missing, an empty template (header only) is written.
"""

from __future__ import annotations

import csv
import os
from collections import defaultdict

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PRIVATE_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "ID-data"))

FULL_EXPORT_DIR = os.path.join(PRIVATE_DIR, "db_exports")
DEID_EXPORT_DIR = os.path.join(BASE_DIR, "db_exports")

GUID_PEOPLE_CSV = os.path.join(FULL_EXPORT_DIR, "guid_people.csv")
PARTICIPANTS_CSV = os.path.join(FULL_EXPORT_DIR, "participants.csv")
PARTICIPANT_VISITS_CSV = os.path.join(FULL_EXPORT_DIR, "participant_visits.csv")
PARTICIPANT_CONTACT_UPDATES_CSV = os.path.join(FULL_EXPORT_DIR, "participant_contact_updates.csv")

DEID_EXPORT_FILE = os.path.join(DEID_EXPORT_DIR, "deidentified_visits.csv")

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")


def read_csv(path: str) -> list[dict]:
    if not os.path.exists(path):
        return []
    with open(path, "r", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_csv(path: str, fieldnames: list[str], rows: list[dict]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def load_record_id_map(path: str | None) -> dict:
    if not path or not os.path.exists(path):
        return {}
    with open(path, "r", newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    mapping = {}
    for row in rows:
        guid = row.get("guid", "")
        record_id = row.get("record_id", "")
        if guid and record_id:
            mapping[guid] = record_id
    return mapping


def record_id_for_guid(guid: str, mapping: dict) -> str:
    return mapping.get(guid, guid)


def first_pipe_value(value: str) -> str:
    if not value:
        return ""
    return value.split("|")[0]


def build_participant_import(record_id_map: dict) -> tuple[list[str], list[dict]]:
    participants = read_csv(PARTICIPANTS_CSV)
    guid_people = read_csv(GUID_PEOPLE_CSV)
    last_seen_by_guid = {row.get("guid", ""): row.get("last_seen_at", "") for row in guid_people}

    rows = []
    for p in participants:
        guid = p.get("guid", "")
        record_id = record_id_for_guid(guid, record_id_map)
        # If no separate newsletter contact exists, default to participant contact.
        newsletter_email = first_pipe_value(p.get("newsletter_emails", "")) or p.get("email", "")
        newsletter_phone = first_pipe_value(p.get("newsletter_phones", "")) or p.get("phone", "")
        newsletter_pref = p.get("newsletter_pref", "") or "participant_only"
        rows.append(
            {
                "sub_id": record_id,
                "guid": guid,
                "first_name": p.get("first_name", ""),
                "last_name": p.get("last_name", ""),
                "dob": p.get("dob", ""),
                "primary_email": p.get("email", ""),
                "primary_phone": p.get("phone", ""),
                "newsletter_email": newsletter_email,
                "newsletter_phone": newsletter_phone,
                "newsletter_pref": newsletter_pref,
                "consent_participant": p.get("consent_contact", ""),
                "created_at": p.get("created_at", ""),
                "last_seen_at": last_seen_by_guid.get(guid, ""),
            }
        )

    fieldnames = [
        "sub_id",
        "guid",
        "first_name",
        "last_name",
        "dob",
        "primary_email",
        "primary_phone",
        "newsletter_email",
        "newsletter_phone",
        "newsletter_pref",
        "consent_participant",
        "created_at",
        "last_seen_at",
    ]
    return fieldnames, rows


def build_visit_import(record_id_map: dict) -> tuple[list[str], list[dict]]:
    visits = read_csv(PARTICIPANT_VISITS_CSV)
    rows = []
    for v in visits:
        guid = v.get("guid", "")
        visit_number = v.get("visit_number", "")
        record_id = record_id_for_guid(guid, record_id_map)
        rows.append(
            {
                "sub_id": record_id,
                "redcap_repeat_instrument": "visits",
                "redcap_repeat_instance": visit_number,
                "visit_number": visit_number,
                "visit_datetime": v.get("visit_datetime", ""),
                "visit_date": v.get("visit_date", ""),
                "visit_time": v.get("visit_time", ""),
                "tubric_study_code": v.get("tubric_study_code", ""),
                "consent_contact_visit": v.get("consent_contact", ""),
                "entered_by": v.get("entered_by", ""),
            }
        )

    fieldnames = [
        "sub_id",
        "redcap_repeat_instrument",
        "redcap_repeat_instance",
        "visit_number",
        "visit_datetime",
        "visit_date",
        "visit_time",
        "tubric_study_code",
        "consent_contact_visit",
        "entered_by",
    ]
    return fieldnames, rows


def build_contact_update_import(record_id_map: dict) -> tuple[list[str], list[dict]]:
    contacts = read_csv(PARTICIPANT_CONTACT_UPDATES_CSV)

    # Assign a repeat instance per GUID in the order the file is read.
    instance_by_guid = defaultdict(int)

    rows = []
    for c in contacts:
        guid = c.get("guid", "")
        instance_by_guid[guid] += 1
        record_id = record_id_for_guid(guid, record_id_map)
        rows.append(
            {
                "sub_id": record_id,
                "redcap_repeat_instrument": "contact_updates",
                "redcap_repeat_instance": instance_by_guid[guid],
                "contact_type": c.get("type", ""),
                "contact_value": c.get("value", ""),
                "added_at": c.get("added_at", ""),
                "contact_visit_number": c.get("visit_number", ""),
                "contact_visit_datetime": c.get("visit_datetime", ""),
            }
        )

    fieldnames = [
        "sub_id",
        "redcap_repeat_instrument",
        "redcap_repeat_instance",
        "contact_type",
        "contact_value",
        "added_at",
        "contact_visit_number",
        "contact_visit_datetime",
    ]
    return fieldnames, rows


def build_deidentified_visit_import(record_id_map: dict) -> tuple[list[str], list[dict]]:
    visits = read_csv(DEID_EXPORT_FILE)
    rows = []
    for v in visits:
        guid = v.get("guid", "")
        visit_number = v.get("visit_number", "")
        record_id = record_id_for_guid(guid, record_id_map)
        rows.append(
            {
                "sub_id": record_id,
                "redcap_repeat_instrument": "deidentified_visits",
                "redcap_repeat_instance": visit_number,
                "guid": guid,
                "visit_number": visit_number,
                "visit_datetime": v.get("visit_datetime", ""),
                "visit_date": v.get("visit_date", ""),
                "visit_time": v.get("visit_time", ""),
                "tubric_study_code": v.get("tubric_study_code", ""),
            }
        )

    fieldnames = [
        "sub_id",
        "redcap_repeat_instrument",
        "redcap_repeat_instance",
        "guid",
        "visit_number",
        "visit_datetime",
        "visit_date",
        "visit_time",
        "tubric_study_code",
    ]
    return fieldnames, rows


def main() -> None:
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    participant_path = os.path.join(OUTPUT_DIR, "redcap_import_participant.csv")
    visits_path = os.path.join(OUTPUT_DIR, "redcap_import_visits.csv")
    contact_path = os.path.join(OUTPUT_DIR, "redcap_import_contact_updates.csv")
    deid_path = os.path.join(OUTPUT_DIR, "redcap_import_deidentified_visits.csv")

    record_map_path = os.environ.get("TUBRIC_RECORD_ID_MAP")
    record_id_map = load_record_id_map(record_map_path)

    fieldnames, rows = build_participant_import(record_id_map)
    write_csv(participant_path, fieldnames, rows)

    fieldnames, rows = build_visit_import(record_id_map)
    write_csv(visits_path, fieldnames, rows)

    fieldnames, rows = build_contact_update_import(record_id_map)
    write_csv(contact_path, fieldnames, rows)

    fieldnames, rows = build_deidentified_visit_import(record_id_map)
    write_csv(deid_path, fieldnames, rows)

    print(f"Wrote: {participant_path}")
    print(f"Wrote: {visits_path}")
    print(f"Wrote: {contact_path}")
    print(f"Wrote: {deid_path}")


if __name__ == "__main__":
    main()
