#!/bin/bash
set -e

cd "/Users/dannyzweben/Desktop/TUBRIC/Database"
export TUBRIC_REDCAP_AUTOPUSH=1
export TUBRIC_REDCAP_API_URL="https://cphapps.temple.edu/redcap/api/"
export TUBRIC_REDCAP_TOKEN_PATH="/Users/dannyzweben/Desktop/TUBRIC/Database/RDCAPI/key.txt"
PY="/Users/dannyzweben/Desktop/TUBRIC/Database/tubric_kiosk/.venv/bin/python"
if [ ! -x "$PY" ] || ! "$PY" -c "import tkinter" 2>/dev/null; then
  PY="$(command -v python3)"
fi
exec "$PY" "/Users/dannyzweben/Desktop/TUBRIC/Database/tubric_kiosk/survey.py"
