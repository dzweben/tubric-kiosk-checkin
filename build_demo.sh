#!/bin/bash
# Build the static GitHub Pages demo of the kiosk UI into ./demo (no backend).
set -e
cd "$(dirname "$0")"
rm -rf demo && mkdir -p demo/consent
cp electron_app/styles.css electron_app/renderer.js electron_app/demo-backend.js demo/
cp electron_app/consent/*.pdf demo/consent/
# Inject the browser stand-in for the backend ahead of the real renderer.
sed 's#<script src="./renderer.js"></script>#<script src="./demo-backend.js"></script>\n    <script src="./renderer.js"></script>#' electron_app/index.html > demo/index.html
cat >> demo/styles.css <<'CSS'

#demo-badge {
  position: fixed;
  top: 10px;
  right: 12px;
  z-index: 50;
  background: #0b1220;
  color: #fff;
  font-size: 13px;
  font-weight: 650;
  letter-spacing: 0.04em;
  padding: 8px 12px;
  border-radius: 999px;
  display: flex;
  gap: 10px;
  align-items: center;
  opacity: 0.85;
}
#demo-badge button {
  border: 1px solid rgba(255, 255, 255, 0.4);
  background: transparent;
  color: #fff;
  border-radius: 999px;
  padding: 3px 10px;
  font-size: 12px;
  cursor: pointer;
}
CSS
touch demo/.nojekyll
echo "demo built in ./demo"
