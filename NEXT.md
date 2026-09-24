# Next Steps

1. ~~Matching: new records are still being created when names should match.~~ Done 2026-09-24: root cause was the PII scrub blanking the DOB that matching filtered on. Matching now runs on a salted hashed identity index (see tubric_kiosk/BACKEND.md).
2. ~~Ask for full name explicitly on TUBRIC screens.~~ Done: both UIs now ask for legal first/last name "as on previous visits".
3. Confirm the REDCap project has `consent_name` (text), `consent_date` (date Y-M-D) and `consent_signature` (file, signature) on the participant instrument and that the API token can import files; `redcap_build/generate_data_dictionary.py` now includes them.
4. RedCap push: ensure the API push + verification flow is robust before local PII scrubbing.
5. The four rows currently in ID-data were scrubbed before the index existed and have no hashes, so they can never match again. They are test records; delete them (and their REDCap records) before real use, or re-enter them once to re-index.
6. ~~Tk app~~ removed 2026-09-24; the Electron kiosk is the only UI.
7. Rebuild tubric_kiosk/.venv: its python symlinks to a removed FSL install. Launchers now fall back to system python3, but the venv should be recreated.
