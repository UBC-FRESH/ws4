#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
export PYTHONPATH=.
exec "${PYTHON:-python}" -m uvicorn portal_app:app --host "${HOST:-127.0.0.1}" --port "${PORT:-8790}"
