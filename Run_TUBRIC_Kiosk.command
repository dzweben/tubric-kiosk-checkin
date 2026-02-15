#!/bin/bash
set -e

cd "/Users/dannyzweben/Desktop/TUBRIC/Database"
export TUBRIC_REDCAP_AUTOPUSH=1
export TUBRIC_REDCAP_API_URL="https://cphapps.temple.edu/redcap/api/"
export TUBRIC_REDCAP_TOKEN_PATH="/Users/dannyzweben/Desktop/TUBRIC/Database/RDCAPI/key.txt"
"/Users/dannyzweben/Desktop/TUBRIC/Database/tubric_kiosk/.venv/bin/python" "/Users/dannyzweben/Desktop/TUBRIC/Database/tubric_kiosk/survey.py"
