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

# By default skip slow tests (cert generation, real TLS, etc.).
# Use ./test.sh --all to run everything including slow tests.
if [[ "$#" -gt 0 && "$1" == "--all" ]]; then
    shift
    MARKER=""
else
    MARKER='-m "not slow"'
fi

# Run pytest: live grouped report via os.write (bypasses all pytest output).
eval ".venv/bin/python -m pytest tests/ -p no:terminal -p no:capture $MARKER \"\$@\"" 2>/dev/null
