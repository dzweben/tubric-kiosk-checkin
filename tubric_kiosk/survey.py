from datetime import datetime
import os
import re
import uuid
import csv
import json
import sys
import hashlib
import secrets
import unicodedata
import base64

"""
Temple Participant Pool kiosk backend: matching, consent, CSV storage,
de-identified export and REDCap push. The UI is the Electron app in
electron_app/, which calls this module through kiosk_backend_cli.py.
"""

LEGACY_DATA_FILE = os.path.join(os.path.dirname(__file__), "tubric_profiles.json")

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))  # /.../TUBRIC/Database
PRIVATE_DIR = os.environ.get("TUBRIC_PRIVATE_DIR") or os.path.abspath(os.path.join(BASE_DIR, "..", "ID-data"))  # /.../TUBRIC/ID-data

FULL_EXPORT_DIR = os.path.join(PRIVATE_DIR, "db_exports")
DEID_EXPORT_DIR = os.environ.get("TUBRIC_DEID_DIR") or os.path.join(BASE_DIR, "db_exports")

# Salt for the hashed identity index. Lives with the private data, never in the repo.
IDENTITY_SALT_PATH = os.path.join(PRIVATE_DIR, "identity_salt.txt")

# Drawn consent signatures wait here (PNG per GUID) until pushed to REDCap.
SIGNATURE_DIR = os.path.join(PRIVATE_DIR, "signatures")

# Matching threshold (see find_person for the scoring table).
MATCH_THRESHOLD = 4

GUID_PEOPLE_CSV = os.path.join(FULL_EXPORT_DIR, "guid_people.csv")
GUID_CONTACT_UPDATES_CSV = os.path.join(FULL_EXPORT_DIR, "guid_contact_updates.csv")
PARTICIPANTS_CSV = os.path.join(FULL_EXPORT_DIR, "participants.csv")
PARTICIPANT_VISITS_CSV = os.path.join(FULL_EXPORT_DIR, "participant_visits.csv")
PARTICIPANT_CONTACT_UPDATES_CSV = os.path.join(FULL_EXPORT_DIR, "participant_contact_updates.csv")

DEID_EXPORT_FILE = os.path.join(DEID_EXPORT_DIR, "deidentified_visits.csv")

REDCAP_BUILD_DIR = os.path.join(BASE_DIR, "redcap_build")
REDCAP_DEFAULT_TOKEN_PATH = os.path.join(BASE_DIR, "RDCAPI", "key.txt")
REDCAP_DEFAULT_API_URL = "https://cphapps.temple.edu/redcap/api/"
REDCAP_API_URL_PATH = os.path.join(BASE_DIR, "RDCAPI", "api_url.txt")
REDCAP_DEFAULT_REPORT_ID = "10034"
REDCAP_REPORT_ID_PATH = os.path.join(BASE_DIR, "RDCAPI", "report_id.txt")


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


_NAME_SUFFIXES = {"jr", "sr", "ii", "iii", "iv", "v"}


def _name_tokens(s: str):
    """
    Lowercase, strip accents, split on whitespace and hyphens, drop punctuation
    and generational suffixes. "Mary-Ann O'Brien Jr." -> ["mary", "ann", "obrien"].
    """
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    s = re.sub(r"[-_/]+", " ", s)
    tokens = [re.sub(r"[^a-z0-9]", "", t) for t in s.split()]
    return [t for t in tokens if t and t not in _NAME_SUFFIXES]


def normalize_name(s: str) -> str:
    """
    Canonical comparison form: accents, case, spaces and punctuation removed.
    "Mary-Ann", "Mary Ann", "MARYANN" and "Maryann" all -> "maryann".
    """
    return "".join(_name_tokens(s))


def normalize_first_token(s: str) -> str:
    """First word of a first name ("Mary Ann" -> "mary") so a middle name
    typed into the first-name box still gets credit."""
    tokens = _name_tokens(s)
    return tokens[0] if tokens else ""


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


# ----------------------------
# Hashed identity index
# ----------------------------
# Plaintext PII is scrubbed locally once a check-in is verified in REDCap.
# Matching therefore runs on salted SHA-256 hashes of the normalized identity
# fields, which survive the scrub. The salt lives in the private data folder.
_IDENTITY_SALT = None


def _identity_salt() -> str:
    global _IDENTITY_SALT
    if _IDENTITY_SALT:
        return _IDENTITY_SALT
    try:
        if os.path.exists(IDENTITY_SALT_PATH):
            with open(IDENTITY_SALT_PATH, "r", encoding="utf-8") as f:
                value = f.read().strip()
            if value:
                _IDENTITY_SALT = value
                return value
        value = secrets.token_hex(32)
        os.makedirs(os.path.dirname(IDENTITY_SALT_PATH), exist_ok=True)
        with open(IDENTITY_SALT_PATH, "w", encoding="utf-8") as f:
            f.write(value + "\n")
        _IDENTITY_SALT = value
        return value
    except Exception:
        # Fall back to an in-process salt so the kiosk keeps working; hashes
        # written this way won't match across restarts, which only degrades
        # to "new participant" rather than crashing.
        _IDENTITY_SALT = _IDENTITY_SALT or secrets.token_hex(32)
        return _IDENTITY_SALT


def identity_hash(kind: str, value: str) -> str:
    if not value:
        return ""
    msg = f"{_identity_salt()}:{kind}:{value}".encode("utf-8")
    return hashlib.sha256(msg).hexdigest()


def identity_keys(dob: str, first_name: str, last_name: str, email: str = "", phone: str = "") -> dict:
    """
    Compute the hashed identity keys for one set of entered values.
    first_hashes covers both the whole first name and its first token so
    "Mary Ann" / "Mary-Ann" / "Maryann" cross-match.
    """
    first_full = normalize_name(first_name)
    first_tok = normalize_first_token(first_name)
    first_hashes = []
    for v in (first_full, first_tok):
        h = identity_hash("first", v)
        if h and h not in first_hashes:
            first_hashes.append(h)
    email_n = normalize_email(email)
    phone_n = normalize_phone(phone)
    return {
        "dob_hash": identity_hash("dob", dob or ""),
        "first_hashes": first_hashes,
        "last_hash": identity_hash("last", normalize_name(last_name)),
        "email_hashes": [identity_hash("email", email_n)] if email_n else [],
        "phone_hashes": [identity_hash("phone", phone_n)] if phone_n else [],
    }


def _merge_unique(target: list, values) -> None:
    for v in values or []:
        if v and v not in target:
            target.append(v)


def record_identity(person: dict, dob: str, first_name: str, last_name: str, email: str = "", phone: str = "") -> None:
    """
    Add the hashes for the values entered at this check-in to a person's
    identity index. Idempotent. Never removes a hash, so a person whose
    name was mistyped once still matches on the correct spelling later.
    """
    keys = identity_keys(dob, first_name, last_name, email, phone)
    if keys["dob_hash"] and not person.get("dob_hash"):
        person["dob_hash"] = keys["dob_hash"]
    if keys["last_hash"] and not person.get("last_hash"):
        person["last_hash"] = keys["last_hash"]
    _merge_unique(person.setdefault("first_hashes", []), keys["first_hashes"])
    _merge_unique(person.setdefault("email_hashes", []), keys["email_hashes"])
    _merge_unique(person.setdefault("phone_hashes", []), keys["phone_hashes"])


def ensure_identity_hashes(person: dict) -> None:
    """
    Backfill hashes from plaintext for rows written before the identity index
    existed. Rows that were already scrubbed and have no hashes cannot be
    recovered and will simply never match.
    """
    if not (person.get("dob") or person.get("first_name") or person.get("last_name")
            or person.get("primary_email") or person.get("primary_phone")):
        return
    record_identity(
        person,
        person.get("dob", ""),
        person.get("first_name", ""),
        person.get("last_name", ""),
        person.get("primary_email", ""),
        person.get("primary_phone", ""),
    )
    for e in person.get("secondary_emails", []):
        _merge_unique(person["email_hashes"], [identity_hash("email", normalize_email(e))])
    for p in person.get("secondary_phones", []):
        _merge_unique(person["phone_hashes"], [identity_hash("phone", normalize_phone(p))])


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
                "newsletter_pref": p.get("newsletter_pref", ""),
                "created_at": p.get("created_at", ""),
                "last_seen_at": p.get("last_seen_at", ""),
                "contact_updates": contact_by_guid.get(guid, []),
                "consent_date": p.get("consent_date", "") or "",
                "consent_signed_at": p.get("consent_signed_at", "") or "",
                "dob_hash": p.get("dob_hash", "") or "",
                "first_hashes": _split_list(p.get("first_hashes", "")),
                "last_hash": p.get("last_hash", "") or "",
                "email_hashes": _split_list(p.get("email_hashes", "")),
                "phone_hashes": _split_list(p.get("phone_hashes", "")),
            }
        )
    for person in people:
        ensure_identity_hashes(person)
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
                "newsletter_pref": p.get("newsletter_pref", ""),
                "consent_contact": p.get("consent_contact", ""),
                "consent_name": p.get("consent_name", "") or "",
                "consent_date": p.get("consent_date", "") or "",
                "consent_signed_at": p.get("consent_signed_at", "") or "",
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
                "newsletter_pref": p.get("newsletter_pref", ""),
                "created_at": p.get("created_at", ""),
                "last_seen_at": p.get("last_seen_at", ""),
                "consent_date": p.get("consent_date", ""),
                "consent_signed_at": p.get("consent_signed_at", ""),
                "dob_hash": p.get("dob_hash", ""),
                "first_hashes": "|".join(p.get("first_hashes", [])),
                "last_hash": p.get("last_hash", ""),
                "email_hashes": "|".join(p.get("email_hashes", [])),
                "phone_hashes": "|".join(p.get("phone_hashes", [])),
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
            "newsletter_pref",
            "created_at",
            "last_seen_at",
            "consent_date",
            "consent_signed_at",
            "dob_hash",
            "first_hashes",
            "last_hash",
            "email_hashes",
            "phone_hashes",
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
                "newsletter_pref": p.get("newsletter_pref", ""),
                "consent_contact": p.get("consent_contact", ""),
                "consent_name": p.get("consent_name", ""),
                "consent_date": p.get("consent_date", ""),
                "consent_signed_at": p.get("consent_signed_at", ""),
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
            "newsletter_pref",
            "consent_contact",
            "consent_name",
            "consent_date",
            "consent_signed_at",
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
    Disable with TUBRIC_GIT_AUTOPUSH=0.
    """
    if os.environ.get("TUBRIC_GIT_AUTOPUSH", "1").strip().lower() in ("0", "false", "no"):
        return
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


def _build_redcap_payload(guid, person, participant, visit, visit_datetime):
    primary_email = ""
    primary_phone = ""
    if participant:
        primary_email = participant.get("email", "") or ""
        primary_phone = participant.get("phone", "") or ""
    if not primary_email:
        primary_email = person.get("primary_email", "")
    if not primary_phone:
        primary_phone = person.get("primary_phone", "")

    newsletter_email = ""
    newsletter_phone = ""
    newsletter_pref = ""
    if participant:
        newsletter_emails = participant.get("newsletter_emails", [])
        newsletter_phones = participant.get("newsletter_phones", [])
        newsletter_email = newsletter_emails[0] if newsletter_emails else ""
        newsletter_phone = newsletter_phones[0] if newsletter_phones else ""
        newsletter_pref = participant.get("newsletter_pref", "")
    if not newsletter_email:
        newsletter_email = primary_email
    if not newsletter_phone:
        newsletter_phone = primary_phone
    if not newsletter_pref:
        newsletter_pref = "participant_only"

    consent_participant = participant.get("consent_contact", "") if participant else ""
    created_at = participant.get("created_at", "") if participant else ""
    last_seen_at = person.get("last_seen_at", "")

    contact_updates_source = []
    if participant:
        contact_updates_source = participant.get("contact_updates", []) or []
    if not contact_updates_source:
        contact_updates_source = person.get("contact_updates", []) or []

    contact_updates = []
    for idx, cu in enumerate(contact_updates_source, start=1):
        if cu.get("visit_datetime") != visit_datetime:
            continue
        contact_updates.append(
            {
                "instance": idx,
                "contact_type": cu.get("type", ""),
                "contact_value": cu.get("value", ""),
                "added_at": cu.get("added_at", ""),
                "contact_visit_number": cu.get("visit_number", ""),
                "contact_visit_datetime": cu.get("visit_datetime", ""),
            }
        )

    payload = {
        "guid": guid,
        "participant": {
            "first_name": person.get("first_name", ""),
            "last_name": person.get("last_name", ""),
            "dob": person.get("dob", ""),
            "primary_email": primary_email,
            "primary_phone": primary_phone,
            "newsletter_email": newsletter_email,
            "newsletter_phone": newsletter_phone,
            "newsletter_pref": newsletter_pref,
            "consent_participant": _yesno_to_redcap(consent_participant),
            "consent_name": (participant or {}).get("consent_name", "") or "",
            "consent_date": (participant or {}).get("consent_date", "") or person.get("consent_date", ""),
            "created_at": created_at,
            "last_seen_at": last_seen_at,
        },
        "signature_path": signature_path(guid) if os.path.exists(signature_path(guid)) else "",
        "visit": {
            "visit_number": visit.get("visit_number", ""),
            "visit_datetime": visit.get("visit_datetime", ""),
            "visit_date": visit.get("visit_date", ""),
            "visit_time": _format_redcap_time(visit.get("visit_time", "")),
            "tubric_study_code": visit.get("tubric_study_code", ""),
            "consent_contact_visit": _yesno_to_redcap(visit.get("consent_contact", "")),
            "entered_by": visit.get("entered_by", ""),
        },
        "contact_updates": contact_updates,
    }
    return payload


def _yesno_to_redcap(value: str) -> str:
    v = (value or "").strip().lower()
    if v in ("yes", "y", "1", "true"):
        return "1"
    if v in ("no", "n", "0", "false"):
        return "0"
    return ""


def _format_redcap_time(value: str) -> str:
    if not value:
        return ""
    # Accept HH:MM or HH:MM:SS
    parts = value.split(":")
    if len(parts) >= 2:
        return f"{parts[0].zfill(2)}:{parts[1].zfill(2)}"
    return value


def auto_push_redcap(payload, guid_db=None, participants_db=None):
    """
    Push a single check-in to REDCap if autopush is enabled.
    If push + verification succeed, scrub local PII and keep GUID + visits.
    Only runs when TUBRIC_REDCAP_AUTOPUSH is set (the launcher scripts set it).
    """
    if os.environ.get("TUBRIC_REDCAP_AUTOPUSH", "").strip().lower() not in ("1", "true", "yes"):
        return False
    api_url = _read_redcap_api_url()
    if not api_url:
        return False

    token_path = REDCAP_DEFAULT_TOKEN_PATH
    try:
        if REDCAP_BUILD_DIR not in sys.path:
            sys.path.insert(0, REDCAP_BUILD_DIR)
        from redcap_api_client import read_token, export_records, import_records
        from push_checkin_to_redcap import build_import_rows, rows_to_csv

        token = read_token(token_path)
        guid = payload.get("guid", "")
        if not guid:
            return False

        # Use GUID as record_id (sub_id) to avoid export-permission issues on guid field.
        record_id = guid
        repeat_max = _get_repeat_instance_max(api_url, token, record_id)
        rows = build_import_rows(payload, record_id, repeat_max)
        csv_text = rows_to_csv(rows)

        import_records(api_url, token, csv_text)

        sig_path = payload.get("signature_path", "")
        if sig_path and os.path.exists(sig_path):
            from redcap_api_client import import_file
            import_file(api_url, token, record_id, "consent_signature", sig_path)

        if not _verify_redcap_insert(api_url, token, guid, payload):
            return False

        _scrub_local_pii(guid, guid_db, participants_db)
        return True
    except Exception:
        return False


def _get_repeat_instance_max(api_url: str, token: str, record_id: str) -> dict:
    """
    Compute max repeat instance numbers for a record using sub_id filter
    (avoids guid export permissions).
    """
    try:
        if REDCAP_BUILD_DIR not in sys.path:
            sys.path.insert(0, REDCAP_BUILD_DIR)
        from redcap_api_client import export_records
    except Exception:
        return {"visits": 0, "contact_updates": 0}

    filter_logic = f"[sub_id] = '{record_id}'"
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


def _read_redcap_api_url() -> str:
    if os.path.exists(REDCAP_API_URL_PATH):
        try:
            with open(REDCAP_API_URL_PATH, "r", encoding="utf-8") as f:
                value = f.read().strip()
            if value:
                return value
        except Exception:
            pass
    return REDCAP_DEFAULT_API_URL


def _verify_redcap_insert(api_url: str, token: str, guid: str, payload: dict) -> bool:
    try:
        if REDCAP_BUILD_DIR not in sys.path:
            sys.path.insert(0, REDCAP_BUILD_DIR)
        from redcap_api_client import export_records, export_report
    except Exception:
        return False

    report_id = _read_redcap_report_id()
    raw = ""
    report_columns = set()
    if report_id:
        try:
            raw = export_report(api_url, token, report_id, export_repeating=True)
            try:
                sample = json.loads(raw)
                if isinstance(sample, list) and sample:
                    report_columns = set(sample[0].keys())
            except Exception:
                report_columns = set()
        except Exception:
            raw = ""

        # Require the report to expose GUID + visit fields for verification.
        required_any = {"visit_number", "visit_datetime", "tubric_study_code"}
        if not report_columns or "guid" not in report_columns or report_columns.isdisjoint(required_any):
            return False

    if not raw:
        # No report configured; fallback to sub_id export verification.
        filter_logic = f"[sub_id] = '{guid}'"
        raw = export_records(api_url, token, filter_logic=filter_logic, export_repeating=True)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return False
    if not data:
        return False

    # Verification by GUID + visit details from report export.
    visit = payload.get("visit", {})
    visit_number = str(visit.get("visit_number", "")).strip()
    visit_dt = visit.get("visit_datetime", "")
    visit_code = visit.get("tubric_study_code", "")

    # If report export includes guid/visit fields, verify directly.
    for row in data:
        row_guid = row.get("guid", "")
        if row_guid and row_guid != guid:
            continue
        row_visit_number = str(row.get("visit_number", "")).strip()
        row_visit_dt = row.get("visit_datetime", "")
        row_visit_code = row.get("tubric_study_code", "")

        guid_ok = (row_guid == guid) if row_guid else True
        visit_ok = False
        if visit_number and row_visit_number and row_visit_number == visit_number:
            visit_ok = True
        if visit_dt and row_visit_dt and row_visit_dt == visit_dt:
            visit_ok = True
        if visit_code and row_visit_code and row_visit_code == visit_code:
            visit_ok = True if visit_ok or (row_visit_number or row_visit_dt) else True

        if guid_ok and visit_ok:
            return True

    # Fallback to limited export checks.
    base = None
    for row in data:
        if not row.get("redcap_repeat_instrument"):
            base = row
            break
    if not base:
        return False
    if base.get("guid") and base.get("guid") != guid:
        return False

    # Only validate fields that are actually returned by export (API rights may hide identifiers).
    expected = payload.get("participant", {})
    for field in ("first_name", "last_name", "dob", "primary_email", "primary_phone"):
        if field not in base or base.get(field, "") == "":
            continue
        expected_val = expected.get(field, "")
        if expected_val and base.get(field, "") != expected_val:
            return False

    if visit_dt:
        any_visit_field = any("visit_datetime" in row or "tubric_study_code" in row for row in data)
        if any_visit_field:
            for row in data:
                if row.get("redcap_repeat_instrument") != "visits":
                    continue
                if row.get("visit_datetime") == visit_dt and row.get("tubric_study_code") == visit_code:
                    return True
            return False

    return True


def _read_redcap_report_id() -> str:
    if os.path.exists(REDCAP_REPORT_ID_PATH):
        try:
            with open(REDCAP_REPORT_ID_PATH, "r", encoding="utf-8") as f:
                value = f.read().strip()
            if value:
                return value
        except Exception:
            pass
    return REDCAP_DEFAULT_REPORT_ID


def _scrub_local_pii(guid: str, guid_db=None, participants_db=None) -> None:
    """
    Blank plaintext PII for one GUID. The hashed identity index (dob_hash,
    first_hashes, last_hash, email_hashes, phone_hashes) is deliberately kept
    so the person still matches on their next visit.
    """
    if guid_db is None or participants_db is None:
        try:
            guid_db = load_guid_db()
            participants_db = load_participants_db()
        except Exception:
            return

    for person in guid_db.get("people", []):
        if person.get("guid") != guid:
            continue
        person["first_name"] = ""
        person["last_name"] = ""
        person["dob"] = ""
        person["primary_email"] = ""
        person["primary_phone"] = ""
        person["secondary_emails"] = []
        person["secondary_phones"] = []
        person["newsletter_emails"] = []
        person["newsletter_phones"] = []
        person["contact_updates"] = []

    for participant in participants_db.get("participants", []):
        if participant.get("guid") != guid:
            continue
        participant["first_name"] = ""
        participant["last_name"] = ""
        participant["dob"] = ""
        participant["email"] = ""
        participant["phone"] = ""
        participant["secondary_emails"] = []
        participant["secondary_phones"] = []
        participant["newsletter_emails"] = []
        participant["newsletter_phones"] = []
        participant["contact_updates"] = []
        participant["consent_name"] = ""

    try:
        if os.path.exists(signature_path(guid)):
            os.remove(signature_path(guid))
    except Exception:
        pass

    export_guid_csv(guid_db)
    export_participants_csv(participants_db)
    export_deidentified_visits(participants_db)


def signature_path(guid: str) -> str:
    return os.path.join(SIGNATURE_DIR, f"{guid}.png")


def save_signature(guid: str, data_url: str) -> bool:
    """Persist a data:image/png;base64 signature for a GUID. Returns True if written."""
    if not data_url:
        return False
    try:
        b64 = data_url.split(",", 1)[1] if "," in data_url else data_url
        raw = base64.b64decode(b64)
        if not raw.startswith(b"\x89PNG"):
            return False
        os.makedirs(SIGNATURE_DIR, exist_ok=True)
        with open(signature_path(guid), "wb") as f:
            f.write(raw)
        return True
    except Exception:
        return False


def _redcap_has_consent(guid: str) -> bool:
    """
    Ask REDCap whether this record already has the consent fields filled.
    Only runs when autopush is enabled; any failure means "unknown" (False).
    """
    if os.environ.get("TUBRIC_REDCAP_AUTOPUSH", "").strip().lower() not in ("1", "true", "yes"):
        return False
    try:
        if REDCAP_BUILD_DIR not in sys.path:
            sys.path.insert(0, REDCAP_BUILD_DIR)
        from redcap_api_client import read_token, export_records
        token = read_token(REDCAP_DEFAULT_TOKEN_PATH)
        raw = export_records(
            _read_redcap_api_url(), token,
            fields=["sub_id", "consent_date", "consent_name", "consent_signature"],
            filter_logic=f"[sub_id] = '{guid}'", export_repeating=False,
        )
        for row in json.loads(raw) or []:
            if row.get("consent_date") or row.get("consent_name") or row.get("consent_signature"):
                return True
    except Exception:
        pass
    return False


def lookup_person(state, guid_db=None, participants_db=None):
    """
    Sign-in step: does this person already exist, and have they already signed
    the participant-pool consent? Consent is known locally via
    consent_signed_at (kept through the PII scrub) and confirmed against
    REDCap when the API is reachable.
    Returns {"matched": bool, "guid": str, "consented": bool}.
    """
    if guid_db is None or participants_db is None:
        maybe_migrate_legacy_to_csv()
        guid_db = load_guid_db()
        participants_db = load_participants_db()
    s = state
    existing = find_person(
        guid_db["people"],
        dob=s.get("dob", ""),
        first_name=s.get("first_name", ""),
        last_name=s.get("last_name", ""),
        email=s.get("email", ""),
        phone=s.get("phone", ""),
    )
    if not existing:
        return {"matched": False, "guid": "", "consented": False}
    guid = existing["guid"]
    consented = bool(existing.get("consent_signed_at"))
    if not consented:
        participant = find_participant_by_guid(participants_db["participants"], guid)
        consented = bool(participant and participant.get("consent_signed_at"))
    if not consented:
        consented = _redcap_has_consent(guid)
        if consented:
            existing["consent_signed_at"] = existing.get("consent_signed_at") or now_iso()
            export_guid_csv(guid_db)
    return {"matched": True, "guid": guid, "consented": consented}


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
    newsletter_pref = s.get("newsletter_pref", "")

    consent_name = (s.get("consent_name", "") or "").strip()
    consent_date = (s.get("consent_date", "") or "").strip()
    consent_signature = s.get("consent_signature", "") or ""
    signing_now = bool(consent_name and consent_signature)

    # Joining the pool and agreeing to be contacted are one consent. Anyone
    # who signs now, or signed before, is contactable.
    if signing_now:
        s["consent_contact"] = "Yes"

    # No contact consent means no contact information is stored, regardless
    # of what a front end sent. Matching then rests on name + DOB.
    if _yesno_to_redcap(s.get("consent_contact", "")) != "1":
        email = phone = newsletter_email = newsletter_phone = newsletter_pref = ""

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
        record_identity(existing, dob, s.get("first_name", ""), s.get("last_name", ""), email, phone)
        if signing_now:
            existing["consent_date"] = consent_date or visit_date
            existing["consent_signed_at"] = visit_datetime

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
            if newsletter_pref:
                participant["newsletter_pref"] = newsletter_pref

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
            if newsletter_pref:
                participant["newsletter_pref"] = newsletter_pref
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
        record_identity(person, dob, s.get("first_name", ""), s.get("last_name", ""), email, phone)
        if signing_now:
            person["consent_date"] = consent_date or visit_date
            person["consent_signed_at"] = visit_datetime
        if newsletter_email:
            add_newsletter_email(person, newsletter_email, 1, visit_datetime)
        if newsletter_phone:
            add_newsletter_phone(person, newsletter_phone, 1, visit_datetime)
        if newsletter_pref:
            person["newsletter_pref"] = newsletter_pref
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
        if newsletter_pref:
            participant["newsletter_pref"] = newsletter_pref
        participants_db["participants"].append(participant)
        action = "created_new"

    if signing_now:
        participant["consent_name"] = consent_name
        participant["consent_date"] = consent_date or visit_date
        participant["consent_signed_at"] = visit_datetime
        participant["consent_contact"] = "Yes"
        save_signature(guid, consent_signature)

    export_guid_csv(guid_db)
    export_participants_csv(participants_db)
    export_deidentified_visits(participants_db)
    auto_push_deidentified()

    person_ref = existing if existing else person
    payload = _build_redcap_payload(guid, person_ref, participant, visit, visit_datetime)
    auto_push_redcap(payload, guid_db, participants_db)

    return guid, action, guid_db, participants_db


def score_person(person: dict, keys: dict) -> int:
    """
    Score one stored person against the hashed keys of the entered values.

      +2  date of birth matches
      +1  first name matches (whole name or first token, any spelling seen before)
      +1  last name matches
      +1  email matches any email ever seen for this person
      +1  phone matches any phone ever seen for this person
      -2  first name is known on both sides and does not match

    The first-name penalty is what keeps twins apart: they share DOB, last
    name, and usually a guardian's email and phone, which would otherwise
    reach the threshold on their own.
    """
    score = 0
    if keys["dob_hash"] and keys["dob_hash"] == person.get("dob_hash", ""):
        score += 2

    stored_first = person.get("first_hashes", []) or []
    entered_first = keys["first_hashes"]
    if entered_first and stored_first:
        if any(h in stored_first for h in entered_first):
            score += 1
        else:
            score -= 2

    if keys["last_hash"] and keys["last_hash"] == person.get("last_hash", ""):
        score += 1

    if any(h in (person.get("email_hashes", []) or []) for h in keys["email_hashes"]):
        score += 1
    if any(h in (person.get("phone_hashes", []) or []) for h in keys["phone_hashes"]):
        score += 1
    return score


def find_person(people, dob, first_name, last_name, email, phone):
    """
    Weighted matching over the hashed identity index (see score_person).
    No single field is a hard gate, so one mistyped DOB digit or a hyphen in
    a name no longer creates a duplicate participant, while an unrelated
    person who merely shares a DOB is never merged.

    Worked examples against the threshold of 4:
      exact name + DOB                          2+1+1     = 4  match
      DOB typo, name + email + phone            1+1+1+1   = 4  match
      guardian typed own contact, name + DOB    2+1+1     = 4  match
      married name change, DOB + first + email  2+1+1     = 4  match
      twin: DOB + last + email + phone, first differs  2-2+1+1+1 = 3  no match
      same DOB, different person                2         = 2  no match

    Ties at or above the threshold go to the most recently seen person.
    """
    keys = identity_keys(dob, first_name, last_name, email, phone)
    best = None
    best_score = MATCH_THRESHOLD - 1
    for p in people:
        score = score_person(p, keys)
        if score > best_score or (
            score == best_score and best is not None
            and (p.get("last_seen_at", "") or "") > (best.get("last_seen_at", "") or "")
        ):
            best_score = score
            best = p
    return best


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
