#!/usr/bin/env bash
# Oct 28 + Oct 29 in one command: a real guide and its highlighted keyframes.
#
#   bash scripts/run_capture.sh                                  # the Ego-Exo4D test clip
#   bash scripts/run_capture.sh path/to/scooter.mp4 air-filter two-wheeler
#
# Spends credits: one Wonder call (~1 min) and ~10 SAM images per step.
# Re-check a saved answer for free:  python -m backend.expert.extract_guide <video> --id <id> --from-raw
set -euo pipefail
cd "$(dirname "$0")/.."

VIDEO=${1:-fixtures/egoexo_repair_ego.mp4}
ID=${2:-$(basename "${VIDEO%.*}")}
DOMAIN=${3:-bicycle}

echo "== 1/4 tests (no API calls)"
python -m pytest -q

echo "== 2/4 guide from $VIDEO (Wonder)"
t0=$(date +%s)
python -m backend.expert.extract_guide "$VIDEO" --id "$ID" --domain "$DOMAIN"
t1=$(date +%s)

echo "== 3/4 keyframes (SAM)"
python -m backend.expert.keyframes "$ID"
t2=$(date +%s)

echo "== 4/4 the real guide passes its checks"
python -m pytest -q tests/test_guide.py

line="- $(date +%F): real capture of $ID: guide $((t1 - t0)) s, keyframes $((t2 - t1)) s (token counts: see the [meta] lines above)"
sed -i.bak "4a\\
$line
" docs/LOG.md && rm -f docs/LOG.md.bak
echo
echo "Logged: $line"
echo "Look at the keyframes:  open data/guides/$ID/"
echo "Or in the app:          uvicorn backend.app:app  ->  http://localhost:8000/#/guides/$ID/review"
