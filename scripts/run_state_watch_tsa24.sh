#!/usr/bin/env bash
# Run the live TSA24 resident-state watcher.
#
# Usage:
#   bash scripts/run_state_watch_tsa24.sh [iterations]
#   bash scripts/run_state_watch_tsa24.sh 100000
#   REFRESH=1 PLAIN=1 bash scripts/run_state_watch_tsa24.sh 2000
#
# The TSA24 candidate cache and seeded resident pages are built once and reused.
#
# Environment:
#   ITERATIONS      Default iterations when no positional value is given
#                   (default: 100000)
#   REFRESH         Live repaint seconds (default: 2)
#   PLAIN=1         Print one final frame
#   TSA24_ROOT      TSA24 instance root
#   WS4_REPO        WS4 source checkout (default: this checkout)
#   DATASET         compiled dataset
#   TARGETS         even-flow targets YAML
#   INITIAL         initial schedule CSV
#   CANDIDATE_CACHE candidate pickle cache
#   WORK            seed-state cache directory

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WS4_REPO="${WS4_REPO:-$ROOT}"
TSA24_ROOT="${TSA24_ROOT:-/srv/shared-data/gep/ws4/femic/external/femic-tsa24-instance}"
DATASET="${DATASET:-$TSA24_ROOT/build/compiled}"
TARGETS="${TARGETS:-$TSA24_ROOT/config/ws4/targets/evenflow_tsa24.yaml}"
INITIAL="${INITIAL:-$TSA24_ROOT/runtime/seed_area_control_tsa24.csv}"
CANDIDATE_CACHE="${CANDIDATE_CACHE:-$TSA24_ROOT/runtime/gpu-cache/candidates.pkl}"
WORK="${WORK:-$TSA24_ROOT/runtime/state-watch}"
SEED_STATE="$WORK/tsa24-seed-state.npz"
ITERATIONS="${ITERATIONS:-100000}"
if [[ $# -gt 0 && "$1" =~ ^[0-9]+$ ]]; then
  ITERATIONS="$1"
  shift
fi
REFRESH="${REFRESH:-2}"
LNS_WEIGHT="${LNS_WEIGHT:-0.2}"
LNS_DESTROY="${LNS_DESTROY:-0.1}"
LNS_MAX_DESTROY="${LNS_MAX_DESTROY:-64}"
ACCOUNTS="${ACCOUNTS:-product.HarvestedVolume.managed.Total.CC,feature.Yield.managed.Total}"
PYTHON="${PYTHON:-python3}"

if [[ ! -d "$DATASET" ]]; then
  echo "missing TSA24 dataset: $DATASET" >&2
  exit 2
fi
if [[ ! -f "$TARGETS" ]]; then
  echo "missing TSA24 targets: $TARGETS" >&2
  exit 2
fi
if [[ ! -f "$INITIAL" ]]; then
  echo "missing TSA24 initial schedule: $INITIAL" >&2
  exit 2
fi
if [[ ! -f "$CANDIDATE_CACHE" ]]; then
  echo "missing TSA24 candidate cache: $CANDIDATE_CACHE" >&2
  exit 2
fi

export PYTHONPATH="$WS4_REPO${PYTHONPATH:+:$PYTHONPATH}"
mkdir -p "$WORK"

if [[ ! -f "$SEED_STATE" ]]; then
  echo "building TSA24 seeded resident pages (first run only): $SEED_STATE"
  "$PYTHON" -m ws4.cli state-watch \
    --dataset "$DATASET" \
    --targets "$TARGETS" \
    --candidate-cache "$CANDIDATE_CACHE" \
    --initial-schedule "$INITIAL" \
    --write-seed-state "$SEED_STATE" \
    --accounts "$ACCOUNTS" \
    --years 200 \
    --period-width 10 \
    --iterations 0 \
    --plain >/dev/null
fi

args=(
  state-watch
  --dataset "$DATASET"
  --targets "$TARGETS"
  --candidate-cache "$CANDIDATE_CACHE"
  --initial-schedule "$INITIAL"
  --seed-state "$SEED_STATE"
  --accounts "$ACCOUNTS"
  --years 200
  --period-width 10
  --iterations "$ITERATIONS"
  --refresh "$REFRESH"
  --lns-weight "$LNS_WEIGHT"
  --lns-destroy "$LNS_DESTROY"
  --lns-max-destroy "$LNS_MAX_DESTROY"
)

if [[ "${PLAIN:-0}" == "1" ]]; then
  args+=(--plain)
fi

exec "$PYTHON" -m ws4.cli "${args[@]}" "$@"
