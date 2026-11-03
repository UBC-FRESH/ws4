#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
export PYTHONPATH=.
PYTHON="${PYTHON:-/home/gep/.venv/bin/python}"
HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8790}"
exec "$PYTHON" -m uvicorn portal_app:app --host "$HOST" --port "$PORT"
