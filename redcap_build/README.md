# TUBRIC REDCap Build (No API Calls)

This folder contains **local-only** tooling to prepare REDCap data dictionaries and import-ready CSVs for the TUBRIC kiosk dataset. Nothing here connects to REDCap or calls the API.

## Outputs
- `redcap_build/output/tubric_redcap_data_dictionary.csv`
  - Full identifiable project dictionary (Participant + Visits + Contact Updates).
- `redcap_build/output/tubric_redcap_deidentified_dictionary.csv`
  - Optional de-identified project dictionary (Visits only).
- `redcap_build/output/redcap_import_participant.csv`
- `redcap_build/output/redcap_import_visits.csv`
- `redcap_build/output/redcap_import_contact_updates.csv`
- `redcap_build/output/redcap_import_deidentified_visits.csv`

## Provenance Requirement (Source Code)
Every dictionary and import file includes a required `source_code` field. The import builder populates it with `tubric_kiosk_csv` by default. Update `SOURCE_CODE_VALUE` in `redcap_build/build_import_payloads.py` if you want a different value.

## Record Structure
- One REDCap record per participant.
- `sub_id` is the REDCap record identifier and is required.
- `guid` is a separate required field stored on the Participant instrument.
- Visits and contact updates are modeled as **repeating instruments**.

## Running Locally
Generate dictionaries:
```bash
python3 /Users/dannyzweben/Desktop/TUBRIC/Database/redcap_build/generate_data_dictionary.py
```

Generate import-ready CSVs (reads local CSV exports if present, otherwise writes headers only):
```bash
python3 /Users/dannyzweben/Desktop/TUBRIC/Database/redcap_build/build_import_payloads.py
```

Optional: if you have a `guid` → `record_id` mapping, set `TUBRIC_RECORD_ID_MAP` to a CSV with headers `guid,record_id` before running:
```bash
export TUBRIC_RECORD_ID_MAP=/path/to/guid_record_id_map.csv
python3 /Users/dannyzweben/Desktop/TUBRIC/Database/redcap_build/build_import_payloads.py
```

## Source Data Mapping
Identifiable CSV sources (private):
- `/Users/dannyzweben/Desktop/TUBRIC/ID-data/db_exports/participants.csv`
- `/Users/dannyzweben/Desktop/TUBRIC/ID-data/db_exports/participant_visits.csv`
- `/Users/dannyzweben/Desktop/TUBRIC/ID-data/db_exports/participant_contact_updates.csv`
- `/Users/dannyzweben/Desktop/TUBRIC/ID-data/db_exports/guid_people.csv` (used for `last_seen_at`)

De-identified source (repo-safe):
- `/Users/dannyzweben/Desktop/TUBRIC/Database/db_exports/deidentified_visits.csv`

## Notes
- No REDCap API calls are made unless you run the push scripts.
- `redcap_repeat_instrument` and `redcap_repeat_instance` are included in repeating import files.
- If you decide to use the API later, ensure every payload row includes `source_code`.
 - Newsletter fields are stored as single values: `newsletter_email`, `newsletter_phone`, and `newsletter_pref`.

## API Push Scripts (Optional)
All REDCap pushes are scripted and saved locally (no direct UI or manual calls).

Dry-run (no network call):
```bash
python3 /Users/dannyzweben/Desktop/TUBRIC/Database/redcap_build/push_to_redcap.py \\
  --api-url https://your.redcap/api/ \\
  --dictionary /Users/dannyzweben/Desktop/TUBRIC/Database/redcap_build/output/tubric_redcap_data_dictionary.csv \\
  --data /Users/dannyzweben/Desktop/TUBRIC/Database/redcap_build/output/redcap_import_participant.csv
```

Execute (perform API calls):
```bash
python3 /Users/dannyzweben/Desktop/TUBRIC/Database/redcap_build/push_to_redcap.py \\
  --api-url https://your.redcap/api/ \\
  --dictionary /Users/dannyzweben/Desktop/TUBRIC/Database/redcap_build/output/tubric_redcap_data_dictionary.csv \\
  --data /Users/dannyzweben/Desktop/TUBRIC/Database/redcap_build/output/redcap_import_participant.csv \\
  --execute
```

End-to-end build and push (full project):
```bash
python3 /Users/dannyzweben/Desktop/TUBRIC/Database/redcap_build/run_build_and_push.py \\
  --api-url https://your.redcap/api/ \\
  --push-full \\
  --execute
```
