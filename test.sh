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

# Run all pytest tests with verbose output and any warnings shown.
.venv/bin/python -m pytest tests/ -v "$@"
