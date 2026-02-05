# TUBRIC Kiosk Backend (Storage + Matching)

This document describes the backend storage and matching logic used by the kiosk app in `survey.py`. The UI is unchanged; all changes are in the save/match layer.

## Overview
The kiosk uses **CSV as the source of truth**:
- Full, identifiable data is written to a private folder outside the Git repo.
- De-identified exports are written inside the Git repo for safe syncing.

## Files
- `tubric_kiosk/survey.py`: UI + backend logic (matching, GUID creation, visit tracking)
- `/Users/dannyzweben/Desktop/TUBRIC/ID-data/db_exports/`: private CSVs (full data)
- `db_exports/`: de-identified CSVs in the repo
- `tubric_kiosk/tubric_profiles.json`: legacy file (auto-migrated once if present)

## GUID CSV Schema (`guid_people.csv`)
Root:
- One row per person

Person record:
- `guid`: UUID string
- `first_name`, `last_name`
- `dob`: `YYYY-MM-DD`
- `primary_email`, `primary_phone`
- `secondary_emails`: list of strings
- `secondary_phones`: list of strings
- `contact_updates`: list of updates with visit context
- `created_at`: ISO datetime
- `last_seen_at`: ISO datetime

Contact update entry:
- `type`: `email` or `phone`
- `value`: normalized value
- `added_at`: ISO datetime
- `visit_number`: integer
- `visit_datetime`: ISO datetime

## Participants CSV Schema (`participants.csv`)
Root:
- `participants`: list of participant records

Participant record:
- `guid`: UUID string
- `first_name`, `last_name`
- `dob`: `YYYY-MM-DD`
- `email`, `phone` (primary)
- `secondary_emails`: list of strings
- `secondary_phones`: list of strings
- `contact_updates`: list (same shape as GUID DB)
- `consent_contact`: `Yes` / `No`
- `created_at`: ISO datetime
- `visits`: list of visit objects

Visit object:
- `visit_number`: integer (1, 2, 3...)
- `visit_datetime`: ISO datetime
- `visit_date`: `YYYY-MM-DD`
- `visit_time`: `HH:MM:SS`
- `tubric_study_code`: string
- `consent_contact`: `Yes` / `No`
- `entered_by`: `participant` or `guardian`

## Matching Logic
Match is **DOB-first**, then validated by name/email/phone.

Scoring:
- +2 if first+last name match
- +1 if email matches
- +1 if phone matches

The best candidate is accepted if score >= 2.
Secondary emails/phones are also checked for matches.

## Visit Handling
On every check-in:
- `visit_datetime` is captured automatically
- `visit_date` / `visit_time` are derived from it
- `visit_number` increments per person
- Study code is saved with the visit

If a person is matched:
- New visit is appended
- `last_seen_at` is updated
- New email/phone gets added to secondary contact lists if different

If no match:
- A new GUID is created
- New person and participant records are created

## Migration (Legacy File)
If `tubric_profiles.json` exists and the new DB files do not, the app performs a **one-time migration** on startup. It converts the legacy profiles into the two new databases and preserves visit history.

## Notes
- **CSV is the source of truth.** The kiosk reads/writes CSV directly.
- Private CSV exports (full data):
  - `/Users/dannyzweben/Desktop/TUBRIC/ID-data/db_exports/guid_people.csv`
  - `/Users/dannyzweben/Desktop/TUBRIC/ID-data/db_exports/guid_contact_updates.csv`
  - `/Users/dannyzweben/Desktop/TUBRIC/ID-data/db_exports/participants.csv`
  - `/Users/dannyzweben/Desktop/TUBRIC/ID-data/db_exports/participant_visits.csv`
  - `/Users/dannyzweben/Desktop/TUBRIC/ID-data/db_exports/participant_contact_updates.csv`
- De-identified CSV export (safe for Git):
  - `db_exports/deidentified_visits.csv`
- De-identified Git push helper:
  - `push_deidentified_to_git.py` copies `deidentified_visits.csv` into the repo and runs `git add/commit/push`.
