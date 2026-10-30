#!/usr/bin/env bash
# Watch the c5 even-flow stage-2 scenario.
#
# Usage:
#   bash run_watch_evenflow.sh [iterations]
#
# Environment:
#   PLAIN=1        print a final frame after the run
#   REFRESH=N      seconds between live repaints (default 5)
#   SEED=path      override the stage-1 seed schedule
#
# The default 100000 iterations is intentionally long: the SA search needs time
# to stabilize the ±5% even-flow target after the stage-1 harvest pull.

set -euo pipefail

ROOT="/srv/shared-data/gep/ws4/ws4/tmp/parity2025"
ITERATIONS="${1:-100000}"
REFRESH="${REFRESH:-5}"
SEED="${SEED:-$ROOT/scenarios/c5-base/seed_stage1.csv}"
TARGETS="${TARGETS:-$ROOT/scenarios/c5-base/targets_stage2.yaml}"
LNS_WEIGHT="${LNS_WEIGHT:-0}"
LNS_MAX_DESTROY="${LNS_MAX_DESTROY:-64}"

if [[ ! -f "$SEED" ]]; then
  echo "missing stage-1 seed: $SEED" >&2
  echo "run the stage-1 optimize command in README.md first" >&2
  exit 1
fi

if [[ ! -f "$TARGETS" ]]; then
  echo "missing targets file: $TARGETS" >&2
  exit 1
fi

args=(
  watch
  --dataset "$ROOT/c5_compiled"
  --targets "$TARGETS"
  --account product.Yield.managed.Conif
  --account product.Yield.managed.Decid
  --account feature.total.Yield
  --years 200
  --period-width 10
  --iterations "$ITERATIONS"
  --seed 1
  --refresh "$REFRESH"
  --islands 0
  --lns-weight "$LNS_WEIGHT"
  --lns-max-destroy "$LNS_MAX_DESTROY"
  --initial-schedule "$SEED"
)

if [[ "${PLAIN:-0}" == "1" ]]; then
  args+=(--plain)
fi

exec ws4 "${args[@]}"
