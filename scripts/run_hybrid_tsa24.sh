#!/usr/bin/env bash
# Run one GPU-GA -> resident-state refinement pass on TSA24.
#
# Usage:
#   bash scripts/run_hybrid_tsa24.sh [gpu_generations] [state_iterations]
#
# Defaults:
#   gpu_generations  20000
#   state_iterations  2000
#
# The GPU run is headless and saves its elite schedule.  The resident-state run then
# starts from that schedule and performs a short exact LNS/toggle/swap refinement.
#
# Environment:
#   GPU_SEED=7
#   POPULATION=64
#   WORK=<TSA24>/runtime/hybrid
#   PLAIN=1       also make the state refinement headless
#   TSA24_ROOT=/srv/shared-data/gep/ws4/femic/external/femic-tsa24-instance

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TSA24_ROOT="${TSA24_ROOT:-/srv/shared-data/gep/ws4/femic/external/femic-tsa24-instance}"
WORK="${WORK:-$TSA24_ROOT/runtime/hybrid}"
GPU_GENERATIONS="${1:-${GPU_GENERATIONS:-20000}}"
STATE_ITERATIONS="${2:-${STATE_ITERATIONS:-2000}}"
GPU_SEED="${GPU_SEED:-7}"
POPULATION="${POPULATION:-64}"
GPU_SCHEDULE="$WORK/gpu-elite.csv"
STATE_SCHEDULE="$WORK/state-refined.csv"

mkdir -p "$WORK"
if [[ ! -f "$TSA24_ROOT/scripts/run_gpu_watch_tsa24_100k.sh" ]]; then
  echo "missing TSA24 GPU watcher script" >&2
  exit 2
fi

echo "1/2 GPU-GA: generations=$GPU_GENERATIONS population=$POPULATION seed=$GPU_SEED"
GENERATIONS="$GPU_GENERATIONS" \
POPULATION="$POPULATION" \
SEED="$GPU_SEED" \
PLAIN=1 \
SCHEDULE_OUT="$GPU_SCHEDULE" \
bash "$TSA24_ROOT/scripts/run_gpu_watch_tsa24_100k.sh"

if [[ ! -f "$GPU_SCHEDULE" ]]; then
  echo "GPU run did not write a schedule: $GPU_SCHEDULE" >&2
  exit 2
fi

HASH="$(sha256sum "$GPU_SCHEDULE" | cut -c1-12)"
SEED_STATE="$WORK/state-seed-$HASH.npz"

echo "2/2 resident state: iterations=$STATE_ITERATIONS initial=$GPU_SCHEDULE"
INITIAL="$GPU_SCHEDULE" \
WORK="$WORK" \
SEED_STATE="$SEED_STATE" \
ITERATIONS="$STATE_ITERATIONS" \
SCHEDULE_OUT="$STATE_SCHEDULE" \
bash "$ROOT/scripts/run_state_watch_tsa24.sh"

cp "$STATE_SCHEDULE" "$WORK/gpu-next-seed.csv"
echo "GPU elite:       $GPU_SCHEDULE"
echo "State-refined:   $STATE_SCHEDULE"
echo "Next GPU seed:   $WORK/gpu-next-seed.csv"
