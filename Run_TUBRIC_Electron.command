#!/bin/bash
set -e

cd "/Users/dannyzweben/Desktop/TUBRIC/Database/electron_app"
export TUBRIC_REDCAP_AUTOPUSH=1
export TUBRIC_REDCAP_API_URL="https://cphapps.temple.edu/redcap/api/"
export TUBRIC_REDCAP_TOKEN_PATH="/Users/dannyzweben/Desktop/TUBRIC/Database/RDCAPI/key.txt"

if [ ! -d "node_modules" ]; then
  npm install
fi

npm start
