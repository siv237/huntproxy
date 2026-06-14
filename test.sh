#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

# Run all pytest tests with verbose output and any warnings shown.
python3 -m pytest tests/ -v "$@"
