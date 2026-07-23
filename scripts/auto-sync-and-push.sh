#!/usr/bin/env bash
set -euo pipefail
cd /home/said

python3 scripts/sync-activity.py

if git diff --quiet -- data/activity.json; then
  printf '%s\n' 'No activity changes; nothing to push.'
  exit 0
fi

git add data/activity.json
git commit -m 'chore: refresh activity snapshot'
git push origin main
git ls-remote origin refs/heads/main
