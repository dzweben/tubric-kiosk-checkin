#!/bin/bash
set -e

cd "/Users/dannyzweben/Desktop/TUBRIC/Database/electron_app"

if [ ! -d "node_modules" ]; then
  npm install
fi

npm start
