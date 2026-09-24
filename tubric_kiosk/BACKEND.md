# TUBRIC Kiosk Backend (Storage + Matching)

This document describes the backend storage and matching logic in `survey.py`, used by the Electron kiosk through `kiosk_backend_cli.py`.

## Check-in flow (Electron kiosk)
1. **Sign in**: who is filling it in, then legal name, DOB, email, phone.
   - *Participant*: must be 18+. A DOB under 18 shows the "parent or
     guardian needed" screen: hand the screen to the parent (switches to
     guardian mode with cleared fields) or stop here (nothing saved).
   - *Parent/guardian*: enters **their own** information, not the child's
     (banner + "Your ..." labels). Their DOB must be 18+, which catches a
     parent who types the child's DOB by mistake. The pool record is the
     parent; the study code records the visit.
2. **Lookup** (`lookup_person`, CLI `{"action": "lookup"}`): hashed-index match.
   If the person exists and has already signed consent (local
   `consent_signed_at`, confirmed against REDCap `consent_date` /
   `consent_name` / `consent_signature` when the API is reachable) they go
   straight to the study code.
3. **Consent** (only when not matched or not yet consented): the IRB-approved
   protocol 31285 consent form is shown as the actual PDF
   (`electron_app/consent/31285_consent_03252024.pdf`, converted from the
   IRB docx kept in `docs/consent/`; never retyped). The participant prints
   their name, the date is filled automatically, and they draw a signature.
   To update the form, replace the docx and re-run
   `soffice --headless --convert-to pdf --outdir electron_app/consent <docx>`. Joining
   the pool and agreeing to be contacted are one consent. Declining ends the
   session and nothing is saved.
4. **Study code** entered by the RA, then `submit_checkin`.

Consent is stored as `consent_name`, `consent_date`, `consent_signed_at` on
the participant row and the signature PNG at
`ID-data/signatures/<guid>.png`. On REDCap push the name and date go on the
`consent_form` instrument (`consent_name`, `consent_date`,
`consent_form_complete`=2) and the PNG is uploaded to the `consent_signature`
**plain file** field. REDCap refuses API imports into "signature"-type
fields, so that field must stay a plain file upload. If the upload fails the
PNG is kept and retried on the person's next check-in. After verification the
local name (and the PNG, once uploaded) are scrubbed; `consent_date` and
`consent_signed_at` are kept so the person is not asked to consent again.

Every push result and failure is appended to `ID-data/kiosk.log`.

Launch the kiosk with `Run_TUBRIC_Electron.command`.

## Overview
The kiosk uses **CSV as the source of truth**:
- Full, identifiable data is written to a private folder outside the Git repo.
- De-identified exports are written inside the Git repo for safe syncing.

## Files
- `tubric_kiosk/survey.py`: backend logic (matching, consent, GUID creation, visit tracking, REDCap push)
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

## Matching Logic (hashed identity index)
Plaintext PII is blanked locally as soon as a check-in is verified in REDCap
(`_scrub_local_pii`). Matching therefore never relies on plaintext. Each
person row carries salted SHA-256 hashes of their normalized identity fields,
and those hashes survive the scrub:

- `dob_hash`
- `first_hashes` (whole first name and its first token, every spelling ever entered)
- `last_hash`
- `email_hashes` (every email ever entered for this person)
- `phone_hashes` (every phone ever entered for this person)

The salt is `/Users/dannyzweben/Desktop/TUBRIC/ID-data/identity_salt.txt`,
created on first run. It must stay with the private data and out of Git; if it
is lost, every existing row becomes unmatchable.

Name normalization strips accents, case, punctuation, hyphens, spaces and
generational suffixes, so `Mary-Ann O'Brien Jr.` and `maryann obrien` compare
equal.

Scoring (`score_person`):
- +2 date of birth matches
- +1 first name matches
- +1 last name matches
- +1 email matches
- +1 phone matches
- -2 first name known on both sides and different

Threshold is 4 (`MATCH_THRESHOLD`). No field is a hard gate, so a DOB typo or
a hyphen in a name no longer creates a duplicate. The first-name penalty keeps
twins apart (same DOB, last name, guardian email and phone).

| Scenario | Score | Result |
|---|---|---|
| exact name + DOB | 4 | match |
| DOB typo, name + email + phone | 4 | match |
| guardian typed own contact, name + DOB | 4 | match |
| married name change, DOB + first + email | 4 | match |
| twin: DOB + last + email + phone, first differs | 3 | new person |
| same DOB only | 2 | new person |

Ties at or above the threshold go to the most recently seen person. Hashes are
added on every match (never removed), so a contact learned at one visit counts
at the next. Rows written before the index existed are backfilled from
plaintext on load; rows that were already scrubbed with no hashes cannot be
recovered and will never match.

Tests: `python3 tubric_kiosk/test_matching.py` (offline, uses a temp folder).

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

## REDCap Autopush (Optional)
If enabled, each completed check-in will push a matching participant update, new visit instance, and any new contact updates to REDCap.

Configuration (environment variables):
- `TUBRIC_REDCAP_AUTOPUSH=1` to enable (nothing is pushed without it)
- `TUBRIC_GIT_AUTOPUSH=0` to skip the de-identified git commit/push
- `TUBRIC_PRIVATE_DIR` / `TUBRIC_DEID_DIR` to relocate the data folders (used by tests)
- `TUBRIC_REDCAP_API_URL=https://cphapps.temple.edu/redcap/api/`
- `TUBRIC_REDCAP_TOKEN_PATH=/Users/dannyzweben/Desktop/TUBRIC/Database/RDCAPI/key.txt`

Script used:
- `redcap_build/push_checkin_to_redcap.py`
