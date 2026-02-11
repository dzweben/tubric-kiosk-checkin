# REDCap Reference (TUBRIC Kiosk)

This file defines the minimal REDCap structure and variables that match the kiosk CSV source-of-truth.

**Record Structure**
- One REDCap record per participant.
- `record_id` is required and distinct from `guid`.
- Use repeating instruments for visits and contact updates.

**Instrument: Participant (non-repeating)**
Fields:
- `sub_id` (text, required; REDCap record ID field)
- `guid` (text, unique, required)
- `first_name` (text)
- `last_name` (text)
- `dob` (date, format `YYYY-MM-DD`)
- `primary_email` (email)
- `primary_phone` (text, 10 digits)
- `newsletter_email` (email; newsletter contact email)
- `newsletter_phone` (text; newsletter contact phone)
- `newsletter_pref` (enum: `participant_only`, `guardian_only`, `both`)
- `consent_participant` (yes/no)
- `created_at` (datetime)
- `last_seen_at` (datetime)

Notes:
- Secondary emails/phones are captured as rows in the contact updates instrument below (no pipe-delimited fields in REDCap).
- `newsletter_email` / `newsletter_phone` are captured from the guardian popup when provided. If the popup is skipped, set them to the participant’s primary email/phone.
- `newsletter_pref` indicates whether the newsletter should go only to the guardian contact info, only to the participant contact info, or to both.

**Instrument: Visits (repeating)**
Fields:
- `visit_number` (integer)
- `visit_datetime` (datetime)
- `visit_date` (date)
- `visit_time` (time)
- `tubric_study_code` (text)
- `consent_contact_visit` (yes/no, per-visit)
- `entered_by` (enum: `participant`, `guardian`)

**Instrument: Contact Updates (repeating)**
Fields:
- `contact_type` (enum: `email`, `phone`, `newsletter_email`, `newsletter_phone`)
- `contact_value` (text)
- `added_at` (datetime)
- `contact_visit_number` (integer)
- `contact_visit_datetime` (datetime)

**Optional: De-identified Project or Instrument**
Source file: `/Users/dannyzweben/Desktop/TUBRIC/Database/db_exports/deidentified_visits.csv`
Fields:
- `sub_id` (text, required; REDCap record ID field)
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
