#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

# Run all pytest tests with verbose output and any warnings shown.
.venv/bin/python -m pytest tests/ -v "$@"
