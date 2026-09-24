#!/bin/bash
# Build the static demo and publish it to the gh-pages branch (GitHub Pages).
set -e
cd "$(dirname "$0")"
./build_demo.sh
WT=$(mktemp -d)
git fetch -q origin gh-pages 2>/dev/null || true
if git show-ref --verify --quiet refs/remotes/origin/gh-pages; then
  git worktree add -q "$WT" origin/gh-pages
  (cd "$WT" && git checkout -q -B gh-pages)
else
  git worktree add -q --detach "$WT"
  (cd "$WT" && git checkout -q --orphan gh-pages && git rm -rfq . >/dev/null 2>&1 || true)
fi
rsync -a --delete --exclude .git demo/ "$WT"/
(cd "$WT" && git add -A && (git commit -q -m "Publish demo $(date '+%Y-%m-%d %H:%M')" || echo "nothing to publish") && git push -q -f origin gh-pages)
git worktree remove --force "$WT"
echo "published: https://dzweben.github.io/tubric-kiosk-checkin/"
