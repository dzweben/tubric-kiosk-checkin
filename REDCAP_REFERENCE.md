# REDCap Reference (TUBRIC Kiosk)

This file defines the minimal REDCap structure and variables that match the kiosk CSV source-of-truth.

**Record Structure**
- One REDCap record per `guid`.
- Use repeating instruments for visits and contact updates.
- Recommended record_id: set `record_id` = `guid` (text). If you require numeric IDs, keep `guid` as a required field and use auto-numbering for `record_id`.

**Instrument: Participant (non-repeating)**
Fields:
- `guid` (text, unique)
- `first_name` (text)
- `last_name` (text)
- `dob` (date, format `YYYY-MM-DD`)
- `primary_email` (email)
- `primary_phone` (text, 10 digits)
- `consent_contact` (yes/no)
- `created_at` (datetime)
- `last_seen_at` (datetime)

Notes:
- `secondary_emails` and `secondary_phones` are captured in the contact updates instrument below. Avoid pipe-delimited text in REDCap if you can.

**Instrument: Visits (repeating)**
Fields:
- `visit_number` (integer)
- `visit_datetime` (datetime)
- `visit_date` (date)
- `visit_time` (time)
- `tubric_study_code` (text)
- `consent_contact` (yes/no, per-visit)
- `entered_by` (enum: `participant`, `guardian`)

**Instrument: Contact Updates (repeating)**
Fields:
- `contact_type` (enum: `email`, `phone`)
- `contact_value` (text)
- `added_at` (datetime)
- `visit_number` (integer)
- `visit_datetime` (datetime)

**Optional: De-identified Project or Instrument**
Source file: `/Users/dannyzweben/Desktop/TUBRIC/Database/db_exports/deidentified_visits.csv`
Fields:
- `guid`
- `visit_number`
- `visit_datetime`
- `visit_date`
- `visit_time`
- `tubric_study_code`

**CSV Source Mapping**
Full identifiable data (private):
- `/Users/dannyzweben/Desktop/TUBRIC/ID-data/db_exports/participants.csv`
- `/Users/dannyzweben/Desktop/TUBRIC/ID-data/db_exports/participant_visits.csv`
- `/Users/dannyzweben/Desktop/TUBRIC/ID-data/db_exports/participant_contact_updates.csv`
- `/Users/dannyzweben/Desktop/TUBRIC/ID-data/db_exports/guid_people.csv`
- `/Users/dannyzweben/Desktop/TUBRIC/ID-data/db_exports/guid_contact_updates.csv`

De-identified data (repo-safe):
- `/Users/dannyzweben/Desktop/TUBRIC/Database/db_exports/deidentified_visits.csv`
