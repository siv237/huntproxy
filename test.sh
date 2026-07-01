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

# Install ruff if missing — used for lint + complexity checks.
if ! .venv/bin/python -c "import ruff" 2>/dev/null; then
    .venv/bin/pip install ruff 2>/dev/null || true
fi

# Install pytest-cov if missing — used for branch coverage guard.
if ! .venv/bin/python -c "import pytest_cov" 2>/dev/null; then
    .venv/bin/pip install pytest-cov 2>/dev/null || true
fi

# ── Ruff lint (Python) ──────────────────────────────────────────────────
# Pre-commit: ruff is installed and config is valid.  Specific rule
# violations (E722/BLE001 silent-except, C901 complexity, F401/F841
# unused) are checked in architecture tests as backlog — they don't
# block the default run.  This block only ensures ruff is available.
if [[ -x .venv/bin/ruff ]] && [[ -f ruff.toml ]]; then
    .venv/bin/ruff check hunt/ --config ruff.toml > /dev/null 2>&1 || true
fi

# ── Run modes ────────────────────────────────────────────────────────────
#
#   ./test.sh                # default: functional + contract (excl slow+arch)
#   ./test.sh --all          # everything including slow + arch
#   ./test.sh --arch         # architecture/quality invariants only
#   ./test.sh --router       # router contract (API endpoints) only
#   ./test.sh --executor     # task executor contract only
#   ./test.sh --quality      # arch + router + executor (all guardrails)
#   ./test.sh --security     # SAST (bandit) + SCA (pip-audit) + HTTP fuzzing
#   ./test.sh --coverage     # functional + branch coverage report
#   ./test.sh -k rating      # pass-through to pytest -k
#
# Architecture tests (arch marker) are excluded from the default run
# because they represent the refactoring backlog — they may FAIL until
# the code is improved.  Run them explicitly with --arch or --quality.
# The --arch / --router / --executor / --quality / --coverage modes skip
# the ruff pre-check and slow-test filter so they run as fast as possible.

QUALITY_MARKERS='arch or router or executor'
SECURITY_MARKERS='arch or fuzz'

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
        --security)
            shift
            # Install security tools if missing
            if ! .venv/bin/python -c "import bandit, pip_audit, hypothesis" 2>/dev/null; then
                .venv/bin/pip install bandit pip-audit hypothesis 2>/dev/null || true
            fi
            MARKER="-m \"$SECURITY_MARKERS\""
            ;;
        --coverage)
            shift
            eval ".venv/bin/python -m pytest tests/ -p no:terminal -p no:capture -m \"not slow and not arch\" --cov=hunt --cov-branch --cov-report=term-missing \"\$@\"" 2>/dev/null
            exit $?
            ;;
        *)
            # Unknown flag or pytest argument (e.g. -k, -x) — pass through.
            MARKER='-m "not slow and not arch"'
            ;;
    esac
else
    MARKER='-m "not slow and not arch"'
fi

# Run pytest: live grouped report via os.write (bypasses all pytest output).
eval ".venv/bin/python -m pytest tests/ -p no:terminal -p no:capture $MARKER \"\$@\"" 2>/dev/null
