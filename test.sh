#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

# --- Static lint of the vanilla-JS frontend -------------------------------
# Catches runtime bugs (undefined variables, typos) that pytest can't see
# because the test suite is Python-only.  Requires Node.js + eslint; skipped
# silently if unavailable so CI without Node isn't blocked.
if command -v npx >/dev/null 2>&1 && [[ -f eslint.config.js ]]; then
    if ! npx --no-install eslint web/js/ > /tmp/kilo_jslint.log 2>&1; then
        cat /tmp/kilo_jslint.log
        echo "✗ ESLint found errors in web/js/ — fix them before committing."
        exit 1
    fi
fi

# Ensure a virtual environment exists and test dependencies are installed.
if [[ ! -d .venv ]]; then
    python3 -m venv .venv
fi

if ! .venv/bin/python -c "import pytest, pytest_asyncio" 2>/dev/null; then
    .venv/bin/pip install pytest pytest-asyncio
fi

# ── Run modes ────────────────────────────────────────────────────────────
#
#   ./test.sh                # default: all tests except slow
#   ./test.sh --all          # everything including slow
#   ./test.sh --arch         # architecture/quality invariants only
#   ./test.sh --router       # router contract (API endpoints) only
#   ./test.sh --executor     # task executor contract only
#   ./test.sh --quality      # arch + router + executor (all guardrails)
#   ./test.sh -k rating      # pass-through to pytest -k
#
# The --arch / --router / --executor / --quality modes skip ESLint and
# the slow-test filter so they run as fast as possible.

QUALITY_MARKERS='arch or router or executor'

if [[ "$#" -gt 0 ]]; then
    case "$1" in
        --all)
            shift
            MARKER=""
            ;;
        --arch)
            shift
            MARKER='-m "arch"'
            ;;
        --router)
            shift
            MARKER='-m "router"'
            ;;
        --executor)
            shift
            MARKER='-m "executor"'
            ;;
        --quality)
            shift
            MARKER="-m \"$QUALITY_MARKERS\""
            ;;
        *)
            # Unknown flag or pytest argument (e.g. -k, -x) — pass through.
            MARKER='-m "not slow"'
            ;;
    esac
else
    MARKER='-m "not slow"'
fi

# Run pytest: live grouped report via os.write (bypasses all pytest output).
eval ".venv/bin/python -m pytest tests/ -p no:terminal -p no:capture $MARKER \"\$@\"" 2>/dev/null
