#!/usr/bin/env python3
"""
Matching / duplicate-handling tests for the TUBRIC kiosk backend.

Runs fully offline against a temporary private-data folder. Run with:
    tubric_kiosk/.venv/bin/python tubric_kiosk/test_matching.py
"""
import os
import sys
import tempfile
import unittest

TMP = tempfile.mkdtemp(prefix="tubric_test_")
os.environ["TUBRIC_PRIVATE_DIR"] = os.path.join(TMP, "ID-data")
os.environ["TUBRIC_DEID_DIR"] = os.path.join(TMP, "deid")
os.environ["TUBRIC_GIT_AUTOPUSH"] = "0"
os.environ.pop("TUBRIC_REDCAP_AUTOPUSH", None)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import survey  # noqa: E402


def state(**kw):
    base = {
        "consent_contact": "Yes",
        "is_guardian": "participant",
        "first_name": "Maria",
        "last_name": "Gonzalez",
        "dob": "2010-03-14",
        "email": "maria@example.com",
        "phone": "215-555-0100",
        "tubric_study_code": "TEST",
    }
    base.update(kw)
    return base


def checkin(**kw):
    guid, action, _, _ = survey.submit_checkin(state(**kw))
    return guid, action


class NormalizationTests(unittest.TestCase):
    def test_name_variants_collapse(self):
        for v in ("Mary-Ann", "Mary Ann", "MARYANN", " maryann ", "Mary–Ann"):
            self.assertEqual(survey.normalize_name(v), "maryann", v)
        self.assertEqual(survey.normalize_name("O'Brien"), "obrien")
        self.assertEqual(survey.normalize_name("José"), "jose")
        self.assertEqual(survey.normalize_name("Smith Jr."), "smith")
        self.assertEqual(survey.normalize_name("Smith III"), "smith")
        self.assertEqual(survey.normalize_first_token("Mary Ann"), "mary")

    def test_identity_hash_is_stable_and_salted(self):
        a = survey.identity_hash("dob", "2010-03-14")
        b = survey.identity_hash("dob", "2010-03-14")
        self.assertEqual(a, b)
        self.assertNotEqual(a, survey.identity_hash("last", "2010-03-14"))
        self.assertEqual(len(a), 64)
        self.assertTrue(os.path.exists(survey.IDENTITY_SALT_PATH))


class ScoreTests(unittest.TestCase):
    def person(self, first="Maria", last="Gonzalez", dob="2010-03-14",
               email="maria@example.com", phone="2155550100"):
        p = {"guid": "x", "last_seen_at": "2026-01-01T00:00:00"}
        survey.record_identity(p, dob, first, last, email, phone)
        return p

    def score(self, p, **kw):
        s = state(**kw)
        keys = survey.identity_keys(s["dob"], s["first_name"], s["last_name"], s["email"], s["phone"])
        return survey.score_person(p, keys)

    def test_exact(self):
        self.assertEqual(self.score(self.person()), 6)

    def test_name_and_dob_only(self):
        self.assertEqual(self.score(self.person(), email="other@x.com", phone="2155559999"), 4)

    def test_dob_typo_with_contacts(self):
        self.assertEqual(self.score(self.person(), dob="2010-03-15"), 4)

    def test_twins_not_merged(self):
        twin = self.person(first="Lucia")
        self.assertEqual(self.score(twin), 3)

    def test_unrelated_same_dob(self):
        other = self.person(first="Ahmed", last="Khan", email="a@k.com", phone="2155550001")
        self.assertEqual(self.score(other), 0)

    def test_married_name_change(self):
        p = self.person()
        self.assertEqual(self.score(p, last_name="Rivera", phone="2155559999"), 4)

    def test_middle_name_in_first_box(self):
        p = self.person(first="Maria")
        self.assertEqual(self.score(p, first_name="Maria Elena"), 6)


class SubmitFlowTests(unittest.TestCase):
    def setUp(self):
        for path in (
            survey.GUID_PEOPLE_CSV, survey.GUID_CONTACT_UPDATES_CSV, survey.PARTICIPANTS_CSV,
            survey.PARTICIPANT_VISITS_CSV, survey.PARTICIPANT_CONTACT_UPDATES_CSV, survey.DEID_EXPORT_FILE,
        ):
            if os.path.exists(path):
                os.remove(path)

    def test_new_then_exact_return(self):
        g1, a1 = checkin()
        g2, a2 = checkin(tubric_study_code="TEST2")
        self.assertEqual(a1, "created_new")
        self.assertEqual(a2, "matched_existing")
        self.assertEqual(g1, g2)
        visits = survey.read_csv(survey.PARTICIPANT_VISITS_CSV)
        self.assertEqual([v["visit_number"] for v in visits], ["1", "2"])

    def test_return_with_messy_spelling(self):
        g1, _ = checkin(first_name="Mary-Ann", last_name="O'Brien")
        g2, a2 = checkin(first_name="MARYANN", last_name="OBrien")
        self.assertEqual((g1, "matched_existing"), (g2, a2))

    def test_return_with_dob_typo(self):
        g1, _ = checkin()
        g2, a2 = checkin(dob="2010-03-15")
        self.assertEqual((g1, "matched_existing"), (g2, a2))

    def test_guardian_uses_own_contact(self):
        g1, _ = checkin()
        g2, a2 = checkin(is_guardian="guardian", email="parent@example.com", phone="215-555-0200")
        self.assertEqual((g1, "matched_existing"), (g2, a2))
        people = survey.load_guid_db()["people"]
        self.assertIn("parent@example.com", people[0]["secondary_emails"])
        self.assertEqual(len(people[0]["email_hashes"]), 2)

    def test_twins_get_separate_records(self):
        g1, _ = checkin(first_name="Maria")
        g2, a2 = checkin(first_name="Lucia")
        self.assertEqual(a2, "created_new")
        self.assertNotEqual(g1, g2)
        # and each twin keeps matching themselves afterwards
        g3, a3 = checkin(first_name="Lucia", tubric_study_code="X")
        self.assertEqual((g2, "matched_existing"), (g3, a3))

    def test_unrelated_same_dob_not_merged(self):
        g1, _ = checkin()
        g2, a2 = checkin(first_name="Ahmed", last_name="Khan", email="a@k.com", phone="215-555-0001")
        self.assertEqual(a2, "created_new")
        self.assertNotEqual(g1, g2)

    def test_matching_survives_pii_scrub(self):
        """The bug that caused the Feb 17 duplicates: scrub then return."""
        g1, _ = checkin()
        guid_db = survey.load_guid_db()
        participants_db = survey.load_participants_db()
        survey._scrub_local_pii(g1, guid_db, participants_db)

        rows = survey.read_csv(survey.GUID_PEOPLE_CSV)
        self.assertEqual(rows[0]["first_name"], "")
        self.assertEqual(rows[0]["dob"], "")
        self.assertEqual(rows[0]["primary_email"], "")
        self.assertTrue(rows[0]["dob_hash"])
        self.assertTrue(rows[0]["first_hashes"])

        g2, a2 = checkin(tubric_study_code="AFTER")
        self.assertEqual((g1, "matched_existing"), (g2, a2))
        visits = survey.read_csv(survey.PARTICIPANT_VISITS_CSV)
        self.assertEqual(len(visits), 2)
        self.assertEqual(visits[1]["visit_number"], "2")

        # A new email typed after the scrub is learned (name+DOB+phone = 5)...
        g3, a3 = checkin(email="new@example.com")
        self.assertEqual((g1, "matched_existing"), (g3, a3))
        # ...and counts on the next visit, here carrying a DOB typo (name+email+phone = 4).
        g4, a4 = checkin(email="new@example.com", dob="2010-03-15")
        self.assertEqual((g1, "matched_existing"), (g4, a4))
        # Plaintext stays scrubbed for the fields that were blanked; only hashes grew.
        rows = survey.read_csv(survey.GUID_PEOPLE_CSV)
        self.assertEqual(rows[0]["first_name"], "")
        self.assertEqual(rows[0]["dob"], "")
        self.assertEqual(len(rows[0]["email_hashes"].split("|")), 2)

    def test_legacy_rows_get_backfilled_hashes(self):
        # Simulate a pre-index row: plaintext present, no hash columns.
        survey.write_csv(
            survey.GUID_PEOPLE_CSV,
            ["guid", "first_name", "last_name", "dob", "primary_email", "primary_phone",
             "secondary_emails", "secondary_phones", "created_at", "last_seen_at"],
            [{"guid": "legacy-1", "first_name": "Maria", "last_name": "Gonzalez", "dob": "2010-03-14",
              "primary_email": "maria@example.com", "primary_phone": "2155550100",
              "secondary_emails": "", "secondary_phones": "",
              "created_at": "2026-01-01T00:00:00", "last_seen_at": "2026-01-01T00:00:00"}],
        )
        g, a = checkin()
        self.assertEqual((g, a), ("legacy-1", "matched_existing"))
        rows = survey.read_csv(survey.GUID_PEOPLE_CSV)
        self.assertTrue(rows[0]["dob_hash"])

    def test_visit_recorded_even_without_phone(self):
        g1, _ = checkin()
        g2, a2 = checkin(phone="")
        self.assertEqual((g1, "matched_existing"), (g2, a2))
        visits = survey.read_csv(survey.PARTICIPANT_VISITS_CSV)
        self.assertEqual(len(visits), 2)

    def test_autopush_disabled_without_env(self):
        self.assertFalse(survey.auto_push_redcap({"guid": "x"}))


if __name__ == "__main__":
    unittest.main(verbosity=2)
