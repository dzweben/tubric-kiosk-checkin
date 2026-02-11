import tkinter as tk
from tkinter import messagebox
from datetime import datetime
import os
import re
import uuid
import csv

APP_TITLE = "TUBRIC Check-In"
SITE_NAME = "TUBRIC"

# Visual Theme
COLORS = {
    'primary': '#111827',      # Charcoal
    'primary_dark': '#0b1220',
    'primary_light': '#e5e7eb',
    'success': '#16a34a',
    'background': '#f4f6fb',
    'card': '#ffffff',
    'text': '#0f172a',
    'text_light': '#475569',
    'border': '#e5e7eb',
    'accent': '#9d2235',       # Temple red
    'accent_light': '#f8e5e9',
    'shadow': '#d7dde7',
}

FONT_DISPLAY = ("Helvetica Neue", 30, "bold")
FONT_TITLE = ("Helvetica Neue", 22, "bold")
FONT_SUBTITLE = ("Helvetica Neue", 16)
FONT_BODY = ("Helvetica Neue", 14)
FONT_LABEL = ("Helvetica Neue", 13, "bold")
FONT_BUTTON = ("Helvetica Neue", 15, "bold")
FONT_SMALL = ("Helvetica Neue", 12)

LEGACY_DATA_FILE = os.path.join(os.path.dirname(__file__), "tubric_profiles.json")

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))  # /.../TUBRIC/Database
PRIVATE_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "ID-data"))     # /.../TUBRIC/ID-data
LOGO_PATH = os.path.join(BASE_DIR, "sourcephoto", "logo.png")
SHOW_LOGO = False

FULL_EXPORT_DIR = os.path.join(PRIVATE_DIR, "db_exports")
DEID_EXPORT_DIR = os.path.join(BASE_DIR, "db_exports")

GUID_PEOPLE_CSV = os.path.join(FULL_EXPORT_DIR, "guid_people.csv")
GUID_CONTACT_UPDATES_CSV = os.path.join(FULL_EXPORT_DIR, "guid_contact_updates.csv")
PARTICIPANTS_CSV = os.path.join(FULL_EXPORT_DIR, "participants.csv")
PARTICIPANT_VISITS_CSV = os.path.join(FULL_EXPORT_DIR, "participant_visits.csv")
PARTICIPANT_CONTACT_UPDATES_CSV = os.path.join(FULL_EXPORT_DIR, "participant_contact_updates.csv")

DEID_EXPORT_FILE = os.path.join(DEID_EXPORT_DIR, "deidentified_visits.csv")

## CODE COMPLETE!

# ----------------------------
# Helpers
# ----------------------------
def now_iso():
    return datetime.now().isoformat(timespec="seconds")


def today_str():
    return datetime.now().strftime("%Y-%m-%d")


def normalize_email(s: str) -> str:
    return (s or "").strip().lower()


def normalize_phone(s: str) -> str:
    """
    Accepts ONLY valid US phone numbers with exactly 10 digits
    (optionally entered with formatting characters).
    Returns 10-digit string or "" if invalid.
    """
    digits = re.sub(r"\D+", "", s or "")
    return digits if len(digits) == 10 else ""


def normalize_name(s: str) -> str:
    s = (s or "").strip().lower()
    s = re.sub(r"\s+", " ", s)
    return s


def normalize_dob(s: str) -> str:
    """
    STRICT: Accepts ONLY MM-DD-YYYY entered by the user.
    Returns canonical YYYY-MM-DD for storage/matching, or "" if invalid.

    Example accepted: 03-14-2007
    """
    raw = (s or "").strip()
    if not raw:
        return ""

    try:
        dt = datetime.strptime(raw, "%m-%d-%Y")
        return dt.strftime("%Y-%m-%d")
    except ValueError:
        return ""


def read_csv(path):
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", newline="", encoding="utf-8") as f:
            return list(csv.DictReader(f))
    except Exception:
        return []


def write_csv(path, fieldnames, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for r in rows:
            writer.writerow(r)


def load_logo(max_width=520, max_height=120):
    if not SHOW_LOGO or not os.path.exists(LOGO_PATH):
        return None
    try:
        img = tk.PhotoImage(file=LOGO_PATH)
        w, h = img.width(), img.height()
        if w == 0 or h == 0:
            return None
        scale = max(1, int(max(w / max_width, h / max_height)))
        if scale > 1:
            img = img.subsample(scale, scale)
        return img
    except Exception:
        return None


def _split_list(value: str):
    if not value:
        return []
    return [v for v in value.split("|") if v]


def _int_or_blank(value):
    try:
        return int(value)
    except Exception:
        return ""


def load_guid_db():
    people_rows = read_csv(GUID_PEOPLE_CSV)
    contact_rows = read_csv(GUID_CONTACT_UPDATES_CSV)

    contact_by_guid = {}
    for c in contact_rows:
        contact_by_guid.setdefault(c.get("guid", ""), []).append(
            {
                "type": c.get("type", ""),
                "value": c.get("value", ""),
                "added_at": c.get("added_at", ""),
                "visit_number": _int_or_blank(c.get("visit_number", "")),
                "visit_datetime": c.get("visit_datetime", ""),
            }
        )

    people = []
    for p in people_rows:
        guid = p.get("guid", "")
        people.append(
            {
                "guid": guid,
                "first_name": p.get("first_name", ""),
                "last_name": p.get("last_name", ""),
                "dob": p.get("dob", ""),
                "primary_email": p.get("primary_email", ""),
                "primary_phone": p.get("primary_phone", ""),
                "secondary_emails": _split_list(p.get("secondary_emails", "")),
                "secondary_phones": _split_list(p.get("secondary_phones", "")),
                "newsletter_emails": _split_list(p.get("newsletter_emails", "")),
                "newsletter_phones": _split_list(p.get("newsletter_phones", "")),
                "created_at": p.get("created_at", ""),
                "last_seen_at": p.get("last_seen_at", ""),
                "contact_updates": contact_by_guid.get(guid, []),
            }
        )
    return {"people": people}


def load_participants_db():
    participant_rows = read_csv(PARTICIPANTS_CSV)
    visit_rows = read_csv(PARTICIPANT_VISITS_CSV)
    contact_rows = read_csv(PARTICIPANT_CONTACT_UPDATES_CSV)

    visits_by_guid = {}
    for v in visit_rows:
        visits_by_guid.setdefault(v.get("guid", ""), []).append(
            {
                "visit_number": _int_or_blank(v.get("visit_number", "")),
                "visit_datetime": v.get("visit_datetime", ""),
                "visit_date": v.get("visit_date", ""),
                "visit_time": v.get("visit_time", ""),
                "tubric_study_code": v.get("tubric_study_code", ""),
                "consent_contact": v.get("consent_contact", ""),
                "entered_by": v.get("entered_by", ""),
            }
        )

    contacts_by_guid = {}
    for c in contact_rows:
        contacts_by_guid.setdefault(c.get("guid", ""), []).append(
            {
                "type": c.get("type", ""),
                "value": c.get("value", ""),
                "added_at": c.get("added_at", ""),
                "visit_number": _int_or_blank(c.get("visit_number", "")),
                "visit_datetime": c.get("visit_datetime", ""),
            }
        )

    participants = []
    for p in participant_rows:
        guid = p.get("guid", "")
        participants.append(
            {
                "guid": guid,
                "first_name": p.get("first_name", ""),
                "last_name": p.get("last_name", ""),
                "dob": p.get("dob", ""),
                "email": p.get("email", ""),
                "phone": p.get("phone", ""),
                "secondary_emails": _split_list(p.get("secondary_emails", "")),
                "secondary_phones": _split_list(p.get("secondary_phones", "")),
                "newsletter_emails": _split_list(p.get("newsletter_emails", "")),
                "newsletter_phones": _split_list(p.get("newsletter_phones", "")),
                "consent_contact": p.get("consent_contact", ""),
                "created_at": p.get("created_at", ""),
                "visits": visits_by_guid.get(guid, []),
                "contact_updates": contacts_by_guid.get(guid, []),
            }
        )
    return {"participants": participants}


def maybe_migrate_legacy_to_csv():
    """
    One-time migration from legacy JSON to CSV source-of-truth.
    Only runs if CSVs don't exist and legacy file does.
    """
    if os.path.exists(GUID_PEOPLE_CSV) or os.path.exists(PARTICIPANTS_CSV):
        return
    if not os.path.exists(LEGACY_DATA_FILE):
        return
    try:
        import json
        with open(LEGACY_DATA_FILE, "r", encoding="utf-8") as f:
            legacy = json.load(f)
    except Exception:
        return

    people = []
    participants = []

    for p in legacy.get("profiles", []):
        guid = p.get("guid") or new_guid()
        created_at = p.get("created_at") or now_iso()

        visits = []
        for idx, v in enumerate(p.get("visits", []), start=1):
            visit_dt = v.get("visit_datetime") or now_iso()
            visit_date = visit_dt.split("T")[0]
            visit_time = visit_dt.split("T")[1] if "T" in visit_dt else ""
            visits.append(
                {
                    "visit_number": idx,
                    "visit_datetime": visit_dt,
                    "visit_date": visit_date,
                    "visit_time": visit_time,
                    "tubric_study_code": v.get("tubric_study_code", ""),
                    "consent_contact": v.get("consent_contact"),
                    "entered_by": v.get("entered_by"),
                }
            )

        person = {
            "guid": guid,
            "first_name": p.get("first_name", ""),
            "last_name": p.get("last_name", ""),
            "dob": p.get("dob", ""),
            "primary_email": normalize_email(p.get("email", "")),
            "primary_phone": normalize_phone(p.get("phone", "")),
            "secondary_emails": [],
            "secondary_phones": [],
            "created_at": created_at,
            "last_seen_at": p.get("created_at", ""),
            "contact_updates": [],
        }
        people.append(person)

        participant = {
            "guid": guid,
            "first_name": p.get("first_name", ""),
            "last_name": p.get("last_name", ""),
            "dob": p.get("dob", ""),
            "email": normalize_email(p.get("email", "")),
            "phone": normalize_phone(p.get("phone", "")),
            "secondary_emails": [],
            "secondary_phones": [],
            "contact_updates": [],
            "consent_contact": p.get("consent_contact"),
            "created_at": created_at,
            "visits": visits,
        }
        participants.append(participant)

    export_guid_csv({"people": people})
    export_participants_csv({"participants": participants})

def export_guid_csv(guid_db):
    people_rows = []
    contact_rows = []

    for p in guid_db.get("people", []):
        people_rows.append(
            {
                "guid": p.get("guid", ""),
                "first_name": p.get("first_name", ""),
                "last_name": p.get("last_name", ""),
                "dob": p.get("dob", ""),
                "primary_email": p.get("primary_email", ""),
                "primary_phone": p.get("primary_phone", ""),
                "secondary_emails": "|".join(p.get("secondary_emails", [])),
                "secondary_phones": "|".join(p.get("secondary_phones", [])),
                "newsletter_emails": "|".join(p.get("newsletter_emails", [])),
                "newsletter_phones": "|".join(p.get("newsletter_phones", [])),
                "created_at": p.get("created_at", ""),
                "last_seen_at": p.get("last_seen_at", ""),
            }
        )

        for cu in p.get("contact_updates", []):
            contact_rows.append(
                {
                    "guid": p.get("guid", ""),
                    "type": cu.get("type", ""),
                    "value": cu.get("value", ""),
                    "added_at": cu.get("added_at", ""),
                    "visit_number": cu.get("visit_number", ""),
                    "visit_datetime": cu.get("visit_datetime", ""),
                }
            )

    write_csv(
        GUID_PEOPLE_CSV,
        [
            "guid",
            "first_name",
            "last_name",
            "dob",
            "primary_email",
            "primary_phone",
            "secondary_emails",
            "secondary_phones",
            "newsletter_emails",
            "newsletter_phones",
            "created_at",
            "last_seen_at",
        ],
        people_rows,
    )
    write_csv(
        GUID_CONTACT_UPDATES_CSV,
        ["guid", "type", "value", "added_at", "visit_number", "visit_datetime"],
        contact_rows,
    )


def export_participants_csv(participants_db):
    participant_rows = []
    visit_rows = []
    contact_rows = []

    for p in participants_db.get("participants", []):
        participant_rows.append(
            {
                "guid": p.get("guid", ""),
                "first_name": p.get("first_name", ""),
                "last_name": p.get("last_name", ""),
                "dob": p.get("dob", ""),
                "email": p.get("email", ""),
                "phone": p.get("phone", ""),
                "secondary_emails": "|".join(p.get("secondary_emails", [])),
                "secondary_phones": "|".join(p.get("secondary_phones", [])),
                "newsletter_emails": "|".join(p.get("newsletter_emails", [])),
                "newsletter_phones": "|".join(p.get("newsletter_phones", [])),
                "consent_contact": p.get("consent_contact", ""),
                "created_at": p.get("created_at", ""),
            }
        )

        for v in p.get("visits", []):
            visit_rows.append(
                {
                    "guid": p.get("guid", ""),
                    "visit_number": v.get("visit_number", ""),
                    "visit_datetime": v.get("visit_datetime", ""),
                    "visit_date": v.get("visit_date", ""),
                    "visit_time": v.get("visit_time", ""),
                    "tubric_study_code": v.get("tubric_study_code", ""),
                    "consent_contact": v.get("consent_contact", ""),
                    "entered_by": v.get("entered_by", ""),
                }
            )

        for cu in p.get("contact_updates", []):
            contact_rows.append(
                {
                    "guid": p.get("guid", ""),
                    "type": cu.get("type", ""),
                    "value": cu.get("value", ""),
                    "added_at": cu.get("added_at", ""),
                    "visit_number": cu.get("visit_number", ""),
                    "visit_datetime": cu.get("visit_datetime", ""),
                }
            )

    write_csv(
        PARTICIPANTS_CSV,
        [
            "guid",
            "first_name",
            "last_name",
            "dob",
            "email",
            "phone",
            "secondary_emails",
            "secondary_phones",
            "newsletter_emails",
            "newsletter_phones",
            "consent_contact",
            "created_at",
        ],
        participant_rows,
    )
    write_csv(
        PARTICIPANT_VISITS_CSV,
        [
            "guid",
            "visit_number",
            "visit_datetime",
            "visit_date",
            "visit_time",
            "tubric_study_code",
            "consent_contact",
            "entered_by",
        ],
        visit_rows,
    )
    write_csv(
        PARTICIPANT_CONTACT_UPDATES_CSV,
        ["guid", "type", "value", "added_at", "visit_number", "visit_datetime"],
        contact_rows,
    )


def export_deidentified_visits(participants_db):
    rows = []
    for p in participants_db.get("participants", []):
        for v in p.get("visits", []):
            rows.append(
                {
                    "guid": p.get("guid", ""),
                    "visit_number": v.get("visit_number", ""),
                    "visit_datetime": v.get("visit_datetime", ""),
                    "visit_date": v.get("visit_date", ""),
                    "visit_time": v.get("visit_time", ""),
                    "tubric_study_code": v.get("tubric_study_code", ""),
                }
            )
    write_csv(
        DEID_EXPORT_FILE,
        ["guid", "visit_number", "visit_datetime", "visit_date", "visit_time", "tubric_study_code"],
        rows,
    )


def _python_executable():
    exe = os.environ.get("VIRTUAL_ENV")
    if exe:
        candidate = os.path.join(exe, "bin", "python")
        if os.path.exists(candidate):
            return candidate
    return "python3"


def auto_push_deidentified():
    """
    Pushes de-identified CSV to the Git repo at BASE_DIR.
    Safe to ignore failures (e.g., no remote, auth not set).
    """
    try:
        import subprocess
        script = os.path.join(os.path.dirname(__file__), "push_deidentified_to_git.py")
        subprocess.run(
            [_python_executable(), script, BASE_DIR, "--file", DEID_EXPORT_FILE],
            check=False,
            capture_output=True,
            text=True,
        )
    except Exception:
        pass


def submit_checkin(state, guid_db=None, participants_db=None):
    """
    Core save path used by both Tk UI and Electron.
    Returns (guid, action, guid_db, participants_db).
    """
    if guid_db is None or participants_db is None:
        maybe_migrate_legacy_to_csv()
        guid_db = load_guid_db()
        participants_db = load_participants_db()

    s = state

    dob = s.get("dob", "")
    email = s.get("email", "")
    phone = s.get("phone", "")
    newsletter_email = s.get("newsletter_email", "")
    newsletter_phone = s.get("newsletter_phone", "")

    existing = find_person(
        guid_db["people"],
        dob=dob,
        first_name=s.get("first_name", ""),
        last_name=s.get("last_name", ""),
        email=email,
        phone=phone,
    )

    visit_datetime = now_iso()
    visit_date = visit_datetime.split("T")[0]
    visit_time = visit_datetime.split("T")[1] if "T" in visit_datetime else ""

    visit = {
        "visit_number": 1,
        "visit_datetime": visit_datetime,
        "visit_date": visit_date,
        "visit_time": visit_time,
        "tubric_study_code": s.get("tubric_study_code", ""),
        "consent_contact": s.get("consent_contact"),
        "entered_by": s.get("is_guardian"),
    }

    if existing:
        guid = existing["guid"]
        existing["last_seen_at"] = visit_datetime

        participant = find_participant_by_guid(participants_db["participants"], guid)
        if participant:
            visit_number = len(participant.get("visits", [])) + 1
        else:
            visit_number = 1

        # Update primary contact info if missing, otherwise track secondary changes
        if email:
            if not existing.get("primary_email"):
                existing["primary_email"] = normalize_email(email)
            elif normalize_email(email) != normalize_email(existing.get("primary_email", "")):
                add_secondary_email(existing, email, visit_number, visit_datetime)

        if phone:
            if not existing.get("primary_phone"):
                existing["primary_phone"] = normalize_phone(phone)
            elif normalize_phone(phone) != normalize_phone(existing.get("primary_phone", "")):
                add_secondary_phone(existing, phone, visit_number, visit_datetime)

            if participant:
                if email:
                    if not participant.get("email"):
                        participant["email"] = normalize_email(email)
                    elif normalize_email(email) != normalize_email(participant.get("email", "")):
                        add_secondary_email(participant, email, visit_number, visit_datetime)

                if phone:
                    if not participant.get("phone"):
                        participant["phone"] = normalize_phone(phone)
                    elif normalize_phone(phone) != normalize_phone(participant.get("phone", "")):
                        add_secondary_phone(participant, phone, visit_number, visit_datetime)

                if newsletter_email:
                    add_newsletter_email(participant, newsletter_email, visit_number, visit_datetime)
                if newsletter_phone:
                    add_newsletter_phone(participant, newsletter_phone, visit_number, visit_datetime)

                visit["visit_number"] = visit_number
                participant.setdefault("visits", []).append(visit)
            else:
                visit["visit_number"] = 1
                participant = {
                "guid": guid,
                "first_name": s.get("first_name", "").strip(),
                "last_name": s.get("last_name", "").strip(),
                "dob": dob,
                "email": normalize_email(email),
                "phone": normalize_phone(phone),
                    "secondary_emails": [],
                    "secondary_phones": [],
                    "newsletter_emails": [],
                    "newsletter_phones": [],
                    "contact_updates": [],
                    "consent_contact": s.get("consent_contact"),
                    "created_at": now_iso(),
                    "visits": [visit],
                }
                if newsletter_email:
                    add_newsletter_email(participant, newsletter_email, visit_number, visit_datetime)
                if newsletter_phone:
                    add_newsletter_phone(participant, newsletter_phone, visit_number, visit_datetime)
                participants_db["participants"].append(participant)
            action = "matched_existing"
    else:
        guid = new_guid()
        person = {
            "guid": guid,
            "first_name": s.get("first_name", "").strip(),
            "last_name": s.get("last_name", "").strip(),
            "dob": dob,
            "primary_email": normalize_email(email),
            "primary_phone": normalize_phone(phone),
            "secondary_emails": [],
            "secondary_phones": [],
            "newsletter_emails": [],
            "newsletter_phones": [],
            "created_at": now_iso(),
            "last_seen_at": visit_datetime,
            "contact_updates": [],
        }
        if newsletter_email:
            add_newsletter_email(person, newsletter_email, 1, visit_datetime)
        if newsletter_phone:
            add_newsletter_phone(person, newsletter_phone, 1, visit_datetime)
        guid_db["people"].append(person)

        visit["visit_number"] = 1
        participant = {
            "guid": guid,
            "first_name": s.get("first_name", "").strip(),
            "last_name": s.get("last_name", "").strip(),
            "dob": dob,
            "email": normalize_email(email),
            "phone": normalize_phone(phone),
            "secondary_emails": [],
            "secondary_phones": [],
            "newsletter_emails": [],
            "newsletter_phones": [],
            "contact_updates": [],
            "consent_contact": s.get("consent_contact"),
            "created_at": now_iso(),
            "visits": [visit],
        }
        if newsletter_email:
            add_newsletter_email(participant, newsletter_email, 1, visit_datetime)
        if newsletter_phone:
            add_newsletter_phone(participant, newsletter_phone, 1, visit_datetime)
        participants_db["participants"].append(participant)
        action = "created_new"

    export_guid_csv(guid_db)
    export_participants_csv(participants_db)
    export_deidentified_visits(participants_db)
    auto_push_deidentified()

    return guid, action, guid_db, participants_db


def names_match(p, first_name: str, last_name: str) -> bool:
    return (
        normalize_name(p.get("first_name", "")) == normalize_name(first_name)
        and normalize_name(p.get("last_name", "")) == normalize_name(last_name)
    )


def _email_matches(person, email_n: str) -> bool:
    if not email_n:
        return False
    primary = normalize_email(person.get("primary_email", ""))
    if primary and primary == email_n:
        return True
    for e in person.get("secondary_emails", []):
        if normalize_email(e) == email_n:
            return True
    return False


def _phone_matches(person, phone_n: str) -> bool:
    if not phone_n:
        return False
    primary = normalize_phone(person.get("primary_phone", ""))
    if primary and primary == phone_n:
        return True
    for p in person.get("secondary_phones", []):
        if normalize_phone(p) == phone_n:
            return True
    return False


def find_person(people, dob, first_name, last_name, email, phone):
    """
    DOB-first matching:
      - Step 1: candidates = exact DOB match (canonical YYYY-MM-DD)
      - Step 2: confirm identity using name/email/phone
      - Accept the best candidate only if confirmation score >= 2

    Scoring:
      +2 name match (first+last)
      +1 email match
      +1 phone match
    """
    email_n = normalize_email(email)
    phone_n = normalize_phone(phone)  # will be "" if invalid (we validate earlier)

    candidates = [p for p in people if p.get("dob") == dob]
    if not candidates:
        return None

    best = None
    best_score = -1

    for p in candidates:
        score = 0

        if names_match(p, first_name, last_name):
            score += 2

        if _email_matches(p, email_n):
            score += 1

        if _phone_matches(p, phone_n):
            score += 1

        if score > best_score:
            best_score = score
            best = p

    return best if best_score >= 2 else None


def new_guid():
    return str(uuid.uuid4())


def find_participant_by_guid(participants, guid: str):
    for p in participants:
        if p.get("guid") == guid:
            return p
    return None


def add_contact_update(person, contact_type: str, value: str, visit_number: int, visit_datetime: str):
    person.setdefault("contact_updates", []).append(
        {
            "type": contact_type,
            "value": value,
            "added_at": now_iso(),
            "visit_number": visit_number,
            "visit_datetime": visit_datetime,
        }
    )


def add_secondary_email(person, email: str, visit_number: int, visit_datetime: str):
    email_n = normalize_email(email)
    if not email_n:
        return False
    existing = [normalize_email(e) for e in person.get("secondary_emails", [])]
    if email_n in existing:
        return False
    person.setdefault("secondary_emails", []).append(email_n)
    add_contact_update(person, "email", email_n, visit_number, visit_datetime)
    return True


def add_secondary_phone(person, phone: str, visit_number: int, visit_datetime: str):
    phone_n = normalize_phone(phone)
    if not phone_n:
        return False
    existing = [normalize_phone(p) for p in person.get("secondary_phones", [])]
    if phone_n in existing:
        return False
    person.setdefault("secondary_phones", []).append(phone_n)
    add_contact_update(person, "phone", phone_n, visit_number, visit_datetime)
    return True


def add_newsletter_email(person, email: str, visit_number: int, visit_datetime: str):
    email_n = normalize_email(email)
    if not email_n:
        return False
    existing = [normalize_email(e) for e in person.get("newsletter_emails", [])]
    if email_n in existing:
        return False
    person.setdefault("newsletter_emails", []).append(email_n)
    add_contact_update(person, "newsletter_email", email_n, visit_number, visit_datetime)
    return True


def add_newsletter_phone(person, phone: str, visit_number: int, visit_datetime: str):
    phone_n = normalize_phone(phone)
    if not phone_n:
        return False
    existing = [normalize_phone(p) for p in person.get("newsletter_phones", [])]
    if phone_n in existing:
        return False
    person.setdefault("newsletter_phones", []).append(phone_n)
    add_contact_update(person, "newsletter_phone", phone_n, visit_number, visit_datetime)
    return True


# ----------------------------
# Custom Styled Widgets
# ----------------------------
class StyledButton(tk.Button):
    def __init__(self, parent, text, command, style="primary", **kwargs):
        if style == "primary":
            bg = COLORS['primary']
            fg = "white"
            active_bg = COLORS['primary_dark']
        elif style == "secondary":
            bg = COLORS['card']
            fg = COLORS['text']
            active_bg = COLORS['primary_light']
        elif style == "ghost":
            bg = COLORS['card']
            fg = COLORS['text_light']
            active_bg = COLORS['card']
        else:
            bg = COLORS['primary']
            fg = "black"
            active_bg = COLORS['primary_dark']
        
        super().__init__(
            parent,
            text=text,
            command=command,
            font=FONT_BUTTON,
            bg=bg,
            fg=fg,
            activebackground=active_bg,
            activeforeground=fg,
            relief="flat",
            padx=40,
            pady=16,
            cursor="hand2",
            borderwidth=1 if style == "secondary" else 0,
            highlightthickness=0,
            **kwargs
        )
        
        self.bind("<Enter>", lambda e: self.config(bg=active_bg))
        self.bind("<Leave>", lambda e: self.config(bg=bg))


class StyledEntry(tk.Entry):
    def __init__(self, parent, **kwargs):
        # Set defaults but allow them to be overridden
        defaults = {
            'font': ("Helvetica Neue", 14),
            'bg': COLORS['card'],
            'fg': COLORS['text'],
            'insertbackground': COLORS['primary'],
            'relief': "solid",
            'borderwidth': 1,
            'highlightthickness': 1,
            'highlightcolor': COLORS['accent'],
            'highlightbackground': COLORS['border'],
        }
        # Merge defaults with kwargs (kwargs take precedence)
        defaults.update(kwargs)
        super().__init__(parent, **defaults)


# ----------------------------
# UI Frames
# ----------------------------
class BaseFrame(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, bg=COLORS['background'])
        self.controller = controller
        
        # Create centered container with max width
        self.content = tk.Frame(self, bg=COLORS['background'])
        self.content.place(relx=0.5, rely=0.5, anchor="center")

    def on_show(self):
        pass


def build_card(parent, inner_padx=80, inner_pady=60, width=920, height=620):
    card = tk.Frame(parent, bg=COLORS['card'], relief="flat", borderwidth=0, width=width, height=height)
    card.pack(padx=60, pady=40)
    card.pack_propagate(False)

    # Subtle drop shadow
    shadow = tk.Frame(card, bg=COLORS['shadow'], relief="flat")
    shadow.place(x=5, y=5, relwidth=1, relheight=1)
    card.lift()

    # Accent top bar
    accent = tk.Frame(card, bg=COLORS['accent'], height=5)
    accent.pack(fill="x", side="top")

    inner = tk.Frame(card, bg=COLORS['card'], padx=inner_padx, pady=inner_pady)
    inner.pack()
    return inner


def add_brand_header(parent, controller, subtitle=None):
    header = tk.Frame(parent, bg=COLORS['card'])
    header.pack(pady=(0, 18))

    if controller.logo_image:
        tk.Label(
            header,
            image=controller.logo_image,
            bg=COLORS['card'],
        ).pack(pady=(0, 8))

    tk.Label(
        header,
        text="TUBRIC Check-In",
        bg=COLORS['card'],
        fg=COLORS['text'],
        font=FONT_TITLE,
    ).pack()

    if subtitle:
        tk.Label(
            header,
            text=subtitle,
            bg=COLORS['card'],
            fg=COLORS['text_light'],
            font=FONT_BODY,
        ).pack(pady=(6, 0))


class WelcomeFrame(BaseFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, controller)
        inner = build_card(self.content, inner_padx=80, inner_pady=60)

        # Header with icon
        header_frame = tk.Frame(inner, bg=COLORS['card'])
        header_frame.pack(pady=(0, 20))

        if controller.logo_image:
            tk.Label(
                header_frame,
                image=controller.logo_image,
                bg=COLORS['card'],
            ).pack(pady=(0, 8))
        
        tk.Label(
            header_frame,
            text=f"Welcome to {SITE_NAME}",
            bg=COLORS['card'],
            fg=COLORS['text'],
            font=FONT_DISPLAY,
        ).pack(pady=(10, 0))

        tk.Label(
            header_frame,
            text="Temple University Brain Research Imaging Center",
            bg=COLORS['card'],
            fg=COLORS['text_light'],
            font=FONT_BODY,
        ).pack(pady=(6, 0))

        # Subtitle
        tk.Label(
            inner,
            text="Please follow the prompts to check in for your visit today.",
            bg=COLORS['card'],
            fg=COLORS['text'],
            font=FONT_SUBTITLE,
            wraplength=720,
            justify="center"
        ).pack(pady=(0, 10))
        
        tk.Label(
            inner,
            text="If you are a parent/guardian completing this,\nplease enter the PARTICIPANT'S information.",
            bg=COLORS['card'],
            fg=COLORS['text_light'],
            font=FONT_BODY,
            justify="center"
        ).pack(pady=(0, 30))

        StyledButton(inner, "Start Check-In", lambda: controller.show("ConsentFrame")).pack(pady=(4, 0))


class ConsentFrame(BaseFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, controller)

        card = build_card(self.content, inner_padx=80, inner_pady=60)
        add_brand_header(card, controller)

        tk.Label(
            card,
            text="Contact Permission",
            bg=COLORS['card'],
            fg=COLORS['text'],
            font=FONT_TITLE,
        ).pack(pady=(0, 20))

        tk.Label(
            card,
            text="May we contact you about future research opportunities?",
            bg=COLORS['card'],
            fg=COLORS['text'],
            font=FONT_SUBTITLE,
            justify="center"
        ).pack(pady=(0, 10))
        
        tk.Label(
            card,
            text='We will save your information regardless of your choice.',
            bg=COLORS['card'],
            fg=COLORS['text_light'],
            font=FONT_BODY,
            justify="center"
        ).pack(pady=(0, 30))

        btn_row = tk.Frame(card, bg=COLORS['card'])
        btn_row.pack(pady=10)

        StyledButton(
            btn_row, 
            "Yes, contact me", 
            lambda: self._set_consent(True),
            width=22
        ).grid(row=0, column=0, padx=10)

        StyledButton(
            btn_row, 
            "No, do not contact me", 
            lambda: self._set_consent(False),
            style="secondary",
            width=22
        ).grid(row=0, column=1, padx=10)

        tk.Button(
            card, 
            text="← Back", 
            font=FONT_BODY,
            bg=COLORS['card'],
            fg=COLORS['text_light'],
            relief="flat",
            cursor="hand2",
            command=lambda: controller.show("WelcomeFrame")
        ).pack(pady=(30, 0))

    def _set_consent(self, consent):
        self.controller.state["consent_contact"] = "Yes" if consent else "No"
        self.controller.show("RoleFrame")


class NoConsentFrame(BaseFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, controller)

        card = build_card(self.content, inner_padx=80, inner_pady=60)
        add_brand_header(card, controller)

        tk.Label(
            card,
            text="All Set",
            bg=COLORS['card'],
            fg=COLORS['text'],
            font=FONT_TITLE,
        ).pack(pady=(0, 20))

        tk.Label(
            card,
            text="No problem — we won't contact you about research opportunities.",
            bg=COLORS['card'],
            fg=COLORS['text'],
            font=FONT_SUBTITLE,
            justify="center"
        ).pack(pady=(0, 10))
        
        tk.Label(
            card,
            text="Please let the research assistant know\nyou have checked in.",
            bg=COLORS['card'],
            fg=COLORS['text_light'],
            font=FONT_BODY,
            justify="center"
        ).pack(pady=(0, 30))

        StyledButton(card, "Finish", controller.reset).pack()


class RoleFrame(BaseFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, controller)

        card = build_card(self.content, inner_padx=80, inner_pady=60)
        add_brand_header(card, controller)

        tk.Label(
            card,
            text="Who is checking in?",
            bg=COLORS['card'],
            fg=COLORS['text'],
            font=FONT_TITLE,
        ).pack(pady=(0, 20))

        tk.Label(
            card,
            text="Please select who is completing this form.",
            bg=COLORS['card'],
            fg=COLORS['text'],
            font=FONT_SUBTITLE,
            justify="center"
        ).pack(pady=(0, 10))
        
        tk.Label(
            card,
            text="If you are a parent/guardian, enter the\nPARTICIPANT'S information on the next screen.",
            bg=COLORS['card'],
            fg=COLORS['text_light'],
            font=FONT_BODY,
            justify="center"
        ).pack(pady=(0, 30))

        StyledButton(card, "I am the participant", lambda: self._set_role("participant")).pack(pady=8)
        StyledButton(card, "I am a parent/guardian", lambda: self._set_role("guardian")).pack(pady=8)

        tk.Button(
            card, 
            text="← Back", 
            font=FONT_BODY,
            bg=COLORS['card'],
            fg=COLORS['text_light'],
            relief="flat",
            cursor="hand2",
            command=lambda: controller.show("ConsentFrame")
        ).pack(pady=(30, 0))

    def _set_role(self, role):
        self.controller.state["is_guardian"] = role
        self.controller.show("ParticipantInfoFrame")


class ParticipantInfoFrame(BaseFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, controller)

        card = build_card(self.content, inner_padx=70, inner_pady=50)
        add_brand_header(card, controller)

        tk.Label(
            card,
            text="Participant Information",
            bg=COLORS['card'],
            fg=COLORS['text'],
            font=FONT_TITLE,
        ).pack(pady=(0, 15))

        self.sub = tk.Label(
            card,
            text="Please enter your information below.",
            bg=COLORS['card'],
            fg=COLORS['text_light'],
            font=FONT_BODY,
            justify="center",
        )
        self.sub.pack(pady=(0, 25))

        # Form fields container
        form_frame = tk.Frame(card, bg=COLORS['card'])
        form_frame.pack(pady=10)

        def field(row, label_text, format_example=""):
            field_container = tk.Frame(form_frame, bg=COLORS['card'])
            field_container.grid(row=row, column=0, pady=10, sticky="ew")
            
            # Label with optional format example
            label_frame = tk.Frame(field_container, bg=COLORS['card'])
            label_frame.pack(anchor="w", pady=(0, 5))
            
            tk.Label(
                label_frame,
                text=label_text,
                bg=COLORS['card'],
                fg=COLORS['text'],
                font=FONT_LABEL,
                anchor="w"
            ).pack(side="left")
            
            if format_example:
                tk.Label(
                    label_frame,
                    text=f" ({format_example})",
                    bg=COLORS['card'],
                    fg=COLORS['text_light'],
                    font=FONT_SMALL,
                    anchor="w"
                ).pack(side="left")

            ent = StyledEntry(field_container, width=45)
            ent.pack(fill="x", ipady=8)
            
            return ent

        self.first = field(0, "First Name")
        self.last  = field(1, "Last Name")
        self.dob   = field(2, "Date of Birth", "MM-DD-YYYY")
        self.email = field(3, "Email Address")
        self.phone = field(4, "Phone Number", "555-555-5555")
        
        # Auto-format DOB as user types
        def format_dob(event):
            content = self.dob.get().replace("-", "")  # Remove existing dashes
            # Only keep digits
            content = ''.join(c for c in content if c.isdigit())
            
            # Limit to 8 digits
            content = content[:8]
            
            # Add dashes at appropriate positions
            if len(content) >= 5:
                formatted = f"{content[:2]}-{content[2:4]}-{content[4:]}"
            elif len(content) >= 3:
                formatted = f"{content[:2]}-{content[2:]}"
            else:
                formatted = content
            
            # Update the field
            self.dob.delete(0, tk.END)
            self.dob.insert(0, formatted)
        
        self.dob.bind("<KeyRelease>", format_dob)
        
        # Auto-format phone as user types
        def format_phone(event):
            content = self.phone.get().replace("-", "")  # Remove existing dashes
            # Only keep digits
            content = ''.join(c for c in content if c.isdigit())
            
            # Limit to 10 digits
            content = content[:10]
            
            # Add dashes at appropriate positions (XXX-XXX-XXXX)
            if len(content) >= 7:
                formatted = f"{content[:3]}-{content[3:6]}-{content[6:]}"
            elif len(content) >= 4:
                formatted = f"{content[:3]}-{content[3:]}"
            else:
                formatted = content
            
            # Update the field
            self.phone.delete(0, tk.END)
            self.phone.insert(0, formatted)
        
        self.phone.bind("<KeyRelease>", format_phone)

        self.phone.bind("<Return>", lambda e: self._continue())

        # Note
        note_frame = tk.Frame(card, bg=COLORS['accent_light'], padx=15, pady=12)
        note_frame.pack(pady=(20, 20), fill="x")
        
        tk.Label(
            note_frame,
            text="Please provide both email and phone number.",
            bg=COLORS['accent_light'],
            fg=COLORS['text'],
            font=FONT_SMALL,
            justify="center"
        ).pack()

        # Buttons
        button_frame = tk.Frame(card, bg=COLORS['card'])
        button_frame.pack(pady=(10, 0))

        StyledButton(button_frame, "Continue", self._continue).pack(pady=5)

        tk.Button(
            button_frame,
            text="← Back",
            font=FONT_BODY,
            bg=COLORS['card'],
            fg=COLORS['text_light'],
            relief="flat",
            cursor="hand2",
            command=lambda: controller.show("RoleFrame"),
        ).pack(pady=10)

    def on_show(self):
        role = self.controller.state.get("is_guardian")
        if role == "guardian":
            self.sub.config(
                text="You indicated you are a parent/guardian.\nPlease enter the PARTICIPANT'S information below."
            )
        else:
            self.sub.config(text="Please enter your information below.")

        for ent in (self.first, self.last, self.dob, self.email, self.phone):
            ent.delete(0, tk.END)
        self.first.focus_set()

    def _continue(self):
        first = self.first.get().strip()
        last = self.last.get().strip()
        dob_raw = self.dob.get().strip()
        email = self.email.get().strip()
        phone = self.phone.get().strip()

        if not first or not last:
            messagebox.showinfo("Missing Information", "Please enter the participant's first and last name.")
            return

        dob = normalize_dob(dob_raw)
        if not dob:
            messagebox.showinfo(
                "Date of Birth Required",
                "Please enter date of birth as MM-DD-YYYY\n(example: 03-14-2007)",
            )
            return

        if not email:
            messagebox.showinfo("Email Required", "Please enter an email address.")
            return
            
        if not phone:
            messagebox.showinfo("Phone Required", "Please enter a phone number.")
            return

        if not normalize_phone(phone):
            messagebox.showinfo(
                "Invalid Phone Number",
                "Please enter a valid 10-digit phone number\n(e.g., 215-555-1234)",
            )
            return

        self.controller.state.update(
            {
                "first_name": first,
                "last_name": last,
                "dob": dob,
                "email": email,
                "phone": phone,
            }
        )

        self.controller.show("StudyCodeFrame")


class StudyCodeFrame(BaseFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, controller)

        card = build_card(self.content, inner_padx=80, inner_pady=60)
        add_brand_header(card, controller)

        tk.Label(
            card,
            text="Today's Visit",
            bg=COLORS['card'],
            fg=COLORS['text'],
            font=FONT_TITLE,
        ).pack(pady=(0, 15))

        tk.Label(
            card,
            text="TUBRIC Study Code",
            bg=COLORS['card'],
            fg=COLORS['text'],
            font=FONT_SUBTITLE,
        ).pack(pady=(0, 10))
        
        tk.Label(
            card,
            text="Please have the research assistant\nfill in this information.",
            bg=COLORS['card'],
            fg=COLORS['text_light'],
            font=FONT_BODY,
            justify="center"
        ).pack(pady=(0, 25))

        self.code = StyledEntry(card, width=35, justify="center", font=("Helvetica Neue", 18))
        self.code.pack(pady=15, ipady=10)
        self.code.bind("<Return>", lambda e: self._finish())

        StyledButton(card, "Finish Check-In", self._finish).pack(pady=(10, 0))

        tk.Button(
            card,
            text="← Back",
            font=FONT_BODY,
            bg=COLORS['card'],
            fg=COLORS['text_light'],
            relief="flat",
            cursor="hand2",
            command=lambda: controller.show("ParticipantInfoFrame"),
        ).pack(pady=(25, 0))

    def on_show(self):
        self.code.delete(0, tk.END)
        self.code.focus_set()

    def _finish(self):
        code = self.code.get().strip()
        if not code:
            messagebox.showinfo(
                "Study Code Required",
                "Please enter the TUBRIC Study Code\n(ask the research assistant)",
            )
            return

        self.controller.state["tubric_study_code"] = code

        self.controller.submit_silently()
        self.controller.show("DoneFrame")


class DoneFrame(BaseFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, controller)

        card = build_card(self.content, inner_padx=80, inner_pady=60)
        add_brand_header(card, controller)

        tk.Label(
            card,
            text="You're All Set!",
            bg=COLORS['card'],
            fg=COLORS['text'],
            font=FONT_TITLE,
        ).pack(pady=(0, 20))

        tk.Label(
            card,
            text="Thank you for checking in.",
            bg=COLORS['card'],
            fg=COLORS['text'],
            font=FONT_SUBTITLE,
            justify="center"
        ).pack(pady=(0, 10))
        
        tk.Label(
            card,
            text="Please let the research assistant know\nyou have completed the check-in process.",
            bg=COLORS['card'],
            fg=COLORS['text_light'],
            font=FONT_BODY,
            justify="center"
        ).pack(pady=(0, 30))

        StyledButton(card, "Done", controller.reset).pack()


# ----------------------------
# Main App
# ----------------------------
class KioskApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.configure(bg=COLORS['background'])

        self.attributes("-fullscreen", True)
        self.bind("<Escape>", lambda e: self._confirm_exit())

        self.logo_image = load_logo()

        maybe_migrate_legacy_to_csv()
        self.guid_db = load_guid_db()
        self.participants_db = load_participants_db()

        self.state = {
            "date": today_str(),
            "is_guardian": None,
            "consent_contact": None,
            "first_name": "",
            "last_name": "",
            "dob": "",
            "email": "",
            "phone": "",
            "tubric_study_code": "",
        }

        self.container = tk.Frame(self, bg=COLORS['background'])
        self.container.pack(fill="both", expand=True)

        self.frames = {}
        for F in (
            WelcomeFrame,
            ConsentFrame,
            RoleFrame,
            ParticipantInfoFrame,
            StudyCodeFrame,
            DoneFrame,
            NoConsentFrame,
        ):
            frame = F(parent=self.container, controller=self)
            self.frames[F.__name__] = frame
            frame.grid(row=0, column=0, sticky="nsew")

        self.container.grid_rowconfigure(0, weight=1)
        self.container.grid_columnconfigure(0, weight=1)

        self.show("WelcomeFrame")

    def show(self, frame_name: str):
        frame = self.frames[frame_name]
        frame.tkraise()
        frame.on_show()

    def _confirm_exit(self):
        if messagebox.askyesno("Exit Kiosk", "Are you sure you want to exit the kiosk?"):
            self.destroy()

    def reset(self):
        self.state.update(
            {
                "date": today_str(),
                "is_guardian": None,
                "consent_contact": None,
                "first_name": "",
                "last_name": "",
                "dob": "",
                "email": "",
                "phone": "",
                "tubric_study_code": "",
            }
        )
        self.show("WelcomeFrame")

    def submit_silently(self):
        """
        Silent save + DOB-first matching. Participant never sees matching details.
        """
        guid, action, self.guid_db, self.participants_db = submit_checkin(
            self.state,
            self.guid_db,
            self.participants_db,
        )

        # DEV log (remove later)
        print("\n--- CHECK-IN SAVED ---")
        print("Action:", action)
        print("GUID:", guid)
        print("State:", dict(self.state))
        print("--- END ---\n")

        return guid, action


if __name__ == "__main__":
    app = KioskApp()
    app.mainloop()
