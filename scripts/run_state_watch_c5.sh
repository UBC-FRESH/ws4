#!/usr/bin/env bash
# Run the live c5 resident-state watcher.
#
# Usage:
#   bash scripts/run_state_watch_c5.sh
#   ITERATIONS=20000 REFRESH=1 bash scripts/run_state_watch_c5.sh
#   PLAIN=1 bash scripts/run_state_watch_c5.sh
#
# Environment:
#   ITERATIONS   Search iterations (default: 100000)
#   REFRESH      Live repaint seconds (default: 2)
#   PLAIN=1      Print one final frame instead of the live TUI
#   C5_ROOT      c5 fixture root (default: /srv/shared-data/gep/ws4/ws4/tmp/parity2025)
#   WORK         cache directory (default: <repo>/tmp/state-watch)
#   TARGETS      override the target YAML
#   SEED         override the initial schedule CSV
#   PYTHON       Python executable (default: python3)
#
# The candidate index and seeded resident pages are built once and then reused.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="${PYTHON:-python3}"
C5_ROOT="${C5_ROOT:-/srv/shared-data/gep/ws4/ws4/tmp/parity2025}"
WORK="${WORK:-$ROOT/tmp/state-watch}"
DATASET="$C5_ROOT/c5_compiled"
TARGETS="${TARGETS:-$C5_ROOT/scenarios/c5-base/targets_balanced_stock79.yaml}"
SEED="${SEED:-$C5_ROOT/scenarios/c5-base/seed_stage1.csv}"
INDEX="$WORK/c5-candidates.npz"
SEED_STATE="$WORK/c5-seed-state.npz"
ITERATIONS="${ITERATIONS:-100000}"
REFRESH="${REFRESH:-2}"

export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
mkdir -p "$WORK"

if [[ ! -d "$DATASET" ]]; then
  echo "missing compiled c5 dataset: $DATASET" >&2
  exit 1
fi
if [[ ! -f "$TARGETS" ]]; then
  echo "missing c5 targets: $TARGETS" >&2
  exit 1
fi
if [[ ! -f "$SEED" ]]; then
  echo "missing c5 initial schedule: $SEED" >&2
  exit 1
fi

if [[ ! -f "$INDEX" ]]; then
  echo "building compact candidate index: $INDEX"
  "$PYTHON" - "$DATASET" "$TARGETS" "$INDEX" <<'PY'
import sys
from pathlib import Path

from ws4.opt.engine import OptimizeConfig, Optimizer
from ws4.opt.model2_index import CandidateIndex

dataset, targets, destination = map(Path, sys.argv[1:4])
optimizer = Optimizer.from_dataset(
    dataset,
    OptimizeConfig(
        years=200,
        targets_path=str(targets),
        iterations=1,
        threads=1,
    ),
)
CandidateIndex.build(optimizer.candidates()).save(destination)
PY
fi

if [[ ! -f "$SEED_STATE" ]]; then
  echo "building seeded resident pages: $SEED_STATE"
  "$PYTHON" -m ws4.cli state-watch \
    --dataset "$DATASET" \
    --targets "$TARGETS" \
    --candidate-index "$INDEX" \
    --initial-schedule "$SEED" \
    --write-seed-state "$SEED_STATE" \
    --years 200 \
    --period-width 10 \
    --iterations 0 \
    --plain >/dev/null
fi

args=(
  state-watch
  --dataset "$DATASET"
  --targets "$TARGETS"
  --candidate-index "$INDEX"
  --initial-schedule "$SEED"
  --seed-state "$SEED_STATE"
  --years 200
  --period-width 10
  --iterations "$ITERATIONS"
  --refresh "$REFRESH"
  --lns-weight 0.2
  --lns-destroy 0.1
  --lns-max-destroy 64
)

if [[ "${PLAIN:-0}" == "1" ]]; then
  args+=(--plain)
fi

exec "$PYTHON" -m ws4.cli "${args[@]}" "$@"
