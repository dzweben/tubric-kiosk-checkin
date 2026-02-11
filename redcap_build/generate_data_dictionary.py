"""
Generate REDCap data dictionary CSVs for the TUBRIC kiosk project.

Notes:
- This script does NOT call the REDCap API.
- Each dictionary includes a required `source_code` field to satisfy provenance requirements.
- Output files are written to redcap_build/output/.
"""

from __future__ import annotations

import csv
import os

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")

# Standard REDCap data dictionary column order.
COLUMNS = [
    "Variable / Field Name",
    "Form Name",
    "Section Header",
    "Field Type",
    "Field Label",
    "Choices, Calculations, OR Slider Labels",
    "Field Note",
    "Text Validation Type OR Show Slider Number",
    "Text Validation Min",
    "Text Validation Max",
    "Identifier?",
    "Branching Logic",
    "Required Field?",
    "Custom Alignment",
    "Question Number (surveys only)",
    "Matrix Group Name",
    "Matrix Ranking?",
    "Field Annotation",
]

RECORD_ID_FIELD = "sub_id"
GUID_FIELD = "guid"


def _row(
    name: str,
    form: str,
    label: str,
    field_type: str,
    *,
    choices: str = "",
    note: str = "",
    validation: str = "",
    validation_min: str = "",
    validation_max: str = "",
    identifier: str = "",
    branching: str = "",
    required: str = "",
    alignment: str = "",
    question_number: str = "",
    matrix_group: str = "",
    matrix_ranking: str = "",
    annotation: str = "",
    section_header: str = "",
) -> dict:
    return {
        "Variable / Field Name": name,
        "Form Name": form,
        "Section Header": section_header,
        "Field Type": field_type,
        "Field Label": label,
        "Choices, Calculations, OR Slider Labels": choices,
        "Field Note": note,
        "Text Validation Type OR Show Slider Number": validation,
        "Text Validation Min": validation_min,
        "Text Validation Max": validation_max,
        "Identifier?": identifier,
        "Branching Logic": branching,
        "Required Field?": required,
        "Custom Alignment": alignment,
        "Question Number (surveys only)": question_number,
        "Matrix Group Name": matrix_group,
        "Matrix Ranking?": matrix_ranking,
        "Field Annotation": annotation,
    }


def build_full_dictionary() -> list[dict]:
    rows: list[dict] = []

    # Participant instrument (non-repeating)
    form = "participant"
    rows.append(
        _row(
            RECORD_ID_FIELD,
            form,
            "Record ID",
            "text",
            required="y",
            note="REDCap record identifier.",
        )
    )
    rows.append(
        _row(
            GUID_FIELD,
            form,
            "GUID",
            "text",
            required="y",
            identifier="y",
            note="Global unique identifier for the participant.",
        )
    )
    rows.append(_row("first_name", form, "First name", "text", identifier="y", required="y"))
    rows.append(_row("last_name", form, "Last name", "text", identifier="y", required="y"))
    rows.append(
        _row(
            "dob",
            form,
            "Date of birth",
            "text",
            validation="date_ymd",
            identifier="y",
            required="y",
        )
    )
    rows.append(_row("primary_email", form, "Primary email", "text", validation="email", identifier="y"))
    rows.append(_row("primary_phone", form, "Primary phone", "text", validation="phone", identifier="y"))
    rows.append(_row("newsletter_email", form, "Newsletter email", "text", validation="email"))
    rows.append(_row("newsletter_phone", form, "Newsletter phone", "text", validation="phone"))
    rows.append(
        _row(
            "newsletter_pref",
            form,
            "Newsletter preference",
            "dropdown",
            choices="participant_only, Participant only | guardian_only, Guardian only | both, Both (guardian + participant)",
        )
    )
    rows.append(_row("consent_participant", form, "Consent to be contacted", "yesno"))
    rows.append(_row("created_at", form, "Created at", "text", validation="datetime_ymd"))
    rows.append(_row("last_seen_at", form, "Last seen at", "text", validation="datetime_ymd"))

    # Visits instrument (repeating)
    form = "visits"
    rows.append(_row("visit_number", form, "Visit number", "text", validation="integer", required="y"))
    rows.append(_row("visit_datetime", form, "Visit datetime", "text", validation="datetime_ymd", required="y"))
    rows.append(_row("visit_date", form, "Visit date", "text", validation="date_ymd", required="y"))
    rows.append(_row("visit_time", form, "Visit time", "text", validation="time", required="y"))
    rows.append(_row("tubric_study_code", form, "TUBRIC study code", "text", required="y"))
    rows.append(_row("consent_contact_visit", form, "Consent to be contacted (visit)", "yesno"))
    rows.append(
        _row(
            "entered_by",
            form,
            "Entered by",
            "dropdown",
            choices="participant, participant | guardian, guardian",
        )
    )

    # Contact updates instrument (repeating)
    form = "contact_updates"
    rows.append(
        _row(
            "contact_type",
            form,
            "Contact type",
            "dropdown",
            choices="email, email | phone, phone | newsletter_email, newsletter email | newsletter_phone, newsletter phone",
            required="y",
        )
    )
    rows.append(_row("contact_value", form, "Contact value", "text", required="y"))
    rows.append(_row("added_at", form, "Added at", "text", validation="datetime_ymd"))
    rows.append(_row("contact_visit_number", form, "Visit number", "text", validation="integer"))
    rows.append(_row("contact_visit_datetime", form, "Visit datetime", "text", validation="datetime_ymd"))

    return rows


def build_deidentified_dictionary() -> list[dict]:
    rows: list[dict] = []

    form = "deidentified_visits"
    rows.append(
        _row(
            RECORD_ID_FIELD,
            form,
            "Record ID",
            "text",
            required="y",
            note="REDCap record identifier.",
        )
    )
    rows.append(
        _row(
            GUID_FIELD,
            form,
            "GUID",
            "text",
            required="y",
            identifier="y",
            note="Global unique identifier for the participant.",
        )
    )
    rows.append(_row("visit_number", form, "Visit number", "text", validation="integer", required="y"))
    rows.append(_row("visit_datetime", form, "Visit datetime", "text", validation="datetime_ymd", required="y"))
    rows.append(_row("visit_date", form, "Visit date", "text", validation="date_ymd", required="y"))
    rows.append(_row("visit_time", form, "Visit time", "text", validation="time", required="y"))
    rows.append(_row("tubric_study_code", form, "TUBRIC study code", "text", required="y"))

    return rows


def write_dictionary(path: str, rows: list[dict]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def main() -> None:
    full_path = os.path.join(OUTPUT_DIR, "tubric_redcap_data_dictionary.csv")
    deid_path = os.path.join(OUTPUT_DIR, "tubric_redcap_deidentified_dictionary.csv")

    write_dictionary(full_path, build_full_dictionary())
    write_dictionary(deid_path, build_deidentified_dictionary())

    print(f"Wrote: {full_path}")
    print(f"Wrote: {deid_path}")


if __name__ == "__main__":
    main()
