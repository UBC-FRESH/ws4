#!/usr/bin/env bash
# Run the c5 balanced even-flow scenario with the latest WS4 LNS path.
#
# Usage:
#   bash run_watch_c5_fast_lns.sh [iterations]
#
# Environment:
#   WS4_REPO=/tmp/opencode/ws4-p83   latest WS4 source (default)
#   TARGETS=path                     override targets (default stock79 policy)
#   PLAIN=1                          print one final frame instead of the live TUI
#   ISLANDS=N                        parallel islands (0 = one search)
#   REFRESH=N                        seconds between live repaints (default 2)
#   INITIAL=path                     override the starting schedule
#   NO_SEED=1                        start empty instead of seed_stage1.csv
#   LNS_WEIGHT=0.2                   LNS operator weight
#   LNS_DESTROY=0.1                  fraction of the schedule destroyed
#   LNS_MAX_DESTROY=64               hard cap on blocks destroyed per move
#   SEED=1                           search seed
#
# Examples:
#   bash run_watch_c5_fast_lns.sh
#   bash run_watch_c5_fast_lns.sh 100000
#   PLAIN=1 bash run_watch_c5_fast_lns.sh
#   LNS_MAX_DESTROY=64 bash run_watch_c5_fast_lns.sh 250000
#   ISLANDS=8 bash run_watch_c5_fast_lns.sh 100000

set -euo pipefail

ROOT="/srv/shared-data/gep/ws4/ws4/tmp/parity2025"
BASE="$ROOT/scenarios/c5-base"
ITERATIONS="${1:-100000}"
ISLANDS="${ISLANDS:-0}"
REFRESH="${REFRESH:-2}"
SEED="${SEED:-1}"
LNS_WEIGHT="${LNS_WEIGHT:-0.2}"
LNS_DESTROY="${LNS_DESTROY:-0.1}"
LNS_MAX_DESTROY="${LNS_MAX_DESTROY:-64}"
WS4_REPO="${WS4_REPO:-/tmp/opencode/ws4-p83}"

DATASET="$ROOT/c5_compiled"
TARGETS="${TARGETS:-$BASE/targets_balanced_stock79.yaml}"
DEFAULT_SEED="$BASE/seed_stage1.csv"

if [[ ! -d "$DATASET" ]]; then
  echo "missing dataset: $DATASET" >&2
  exit 2
fi
if [[ ! -f "$TARGETS" ]]; then
  echo "missing targets: $TARGETS" >&2
  exit 2
fi

# The installed ws4 may predate the LNS short-chain fast path and max-destroy cap.
if [[ -d "$WS4_REPO/ws4" ]]; then
  export PYTHONPATH="$WS4_REPO${PYTHONPATH:+:$PYTHONPATH}"
  WS4=(python3 -m ws4.cli)
else
  WS4=(ws4)
fi

if ! "${WS4[@]}" watch --help 2>&1 | grep -q -- '--lns-max-destroy'; then
  echo "this WS4 does not support --lns-max-destroy; set WS4_REPO to the latest WS4 checkout" >&2
  exit 2
fi

args=(
  watch
  --dataset "$DATASET"
  --targets "$TARGETS"
  --account product.Yield.managed.Conif
  --account product.Yield.managed.Decid
  --account feature.total.Yield
  --years 200
  --period-width 10
  --iterations "$ITERATIONS"
  --seed "$SEED"
  --refresh "$REFRESH"
  --islands "$ISLANDS"
  --lns-weight "$LNS_WEIGHT"
  --lns-destroy "$LNS_DESTROY"
  --lns-max-destroy "$LNS_MAX_DESTROY"
)

if [[ "${PLAIN:-0}" == "1" ]]; then
  args+=(--plain)
fi

if [[ -n "${INITIAL:-}" ]]; then
  args+=(--initial-schedule "$INITIAL")
elif [[ "${NO_SEED:-0}" != "1" && -f "$DEFAULT_SEED" ]]; then
  args+=(--initial-schedule "$DEFAULT_SEED")
fi

echo "dataset=$DATASET targets=$TARGETS"
echo "iterations=$ITERATIONS lns_weight=$LNS_WEIGHT lns_destroy=$LNS_DESTROY lns_max_destroy=$LNS_MAX_DESTROY"
echo "ws4=${WS4[*]}"

exec "${WS4[@]}" "${args[@]}"
