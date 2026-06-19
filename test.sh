#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

# Ensure a virtual environment exists and test dependencies are installed.
if [[ ! -d .venv ]]; then
    python3 -m venv .venv
fi

if ! .venv/bin/python -c "import pytest, pytest_asyncio" 2>/dev/null; then
    .venv/bin/pip install pytest pytest-asyncio
fi

# Run pytest: live grouped report via os.write (bypasses all pytest output).
.venv/bin/python -m pytest tests/ -p no:terminal -p no:capture "$@" 2>/dev/null
