#!/bin/bash
# Build the static GitHub Pages demo of the kiosk UI into ./demo (no backend).
set -e
cd "$(dirname "$0")"
rm -rf demo && mkdir -p demo/consent
cp electron_app/styles.css electron_app/renderer.js electron_app/demo-backend.js demo/
cp electron_app/consent/*.pdf demo/consent/
# Inject the browser stand-in for the backend ahead of the real renderer.
V=$(date +%s)
sed -e "s#<script src=\"./renderer.js\"></script>#<script src=\"./demo-backend.js?v=$V\"></script>\n    <script src=\"./renderer.js?v=$V\"></script>#" \
    -e "s#styles.css?v=[0-9]*#styles.css?v=$V#" electron_app/index.html > demo/index.html
touch demo/.nojekyll
echo "demo built in ./demo"
