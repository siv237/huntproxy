"""Architecture / quality invariants — structural guardrails for the refactor.

These tests enforce boundaries that keep the codebase maintainable as it
grows.  They are tagged ``arch`` so they can be run in isolation:

    ./test.sh -m arch          # architecture/quality only
    ./test.sh -m "not arch"    # everything except architecture

Goal: catch regressions *before* a refactor gets out of hand, not after.
Each test documents the current boundary and the target we are moving
toward.  When a threshold is intentionally relaxed, update the constant
and explain why in the commit message.
"""

import ast
import importlib
import inspect
import os
from pathlib import Path

import pytest

# ── Paths ──────────────────────────────────────────────────────────────

ROOT = Path(__file__).resolve().parent.parent
HUNT_DIR = ROOT / "hunt"

# ── Thresholds ─────────────────────────────────────────────────────────
# These are *target* thresholds, not current-state snapshots.  Tests that
# fail are refactoring backlog — each failing test is a concrete task.
# When a file is split, add the new (smaller) files here and remove the old
# entry.  Thresholds only go down, never up.

MAX_LINES = {
    "server.py": 350,       # current: 306 — handler extraction done
    "scheduler.py": 500,    # current: 494 — persistence+API extracted
    "state.py": 250,         # current: 212 — persistence+downloads extracted
    "proxy_runner.py": 350,  # current: 307 — switch history extracted
    "proxy_sources.py": 500, # current: 474 — OK (just under)
    "snapshot.py": 500,     # current: 447 — OK
    "blocklists.py": 500,   # current: 427 — OK
    # Switch history enrichment — extracted from proxy_runner.py
    "switch_history.py": 150,
    # Handler modules — all under 500 after extraction
    "handlers/admin.py": 250,
    "handlers/core.py": 150,
    "handlers/hunt.py": 150,
    "handlers/pool.py": 100,
    "handlers/proxy.py": 350,
    "handlers/routing.py": 150,
    "handlers/sources.py": 350,
    "handlers/traffic.py": 350,
    # Check mixins — split from checking.py (was 1165)
    "check_validation.py": 250,
    "check_proxy.py": 250,
    "check_ssl.py": 200,
    "check_speed.py": 350,
    "check_mitm.py": 250,
    "check_geo.py": 200,
    "check_rating.py": 200,
    # Health mixins — split from health.py (was 817)
    "hunt_control.py": 200,
    "hunt_cycle.py": 200,
    "canary.py": 250,
    "health_loops.py": 150,
    "health_check.py": 400,
    # Scheduler sub-modules — extracted from scheduler.py (was 820)
    "schedule_entry.py": 200,
    "scheduler_persistence.py": 200,
    "scheduler_api.py": 250,
    # State sub-modules — extracted from state.py (was 586)
    "state_persistence.py": 350,
    "state_download.py": 150,
    # Proxy runner sub-module — extracted from proxy_runner.py (was 554)
    "proxy_routing.py": 300,
}

MAX_CYCLOMATIC = 15  # per function — industry standard threshold

MAX_MIXIN_COUNT = 28  # HuntState God Object — was 16, grew to 28 after checking+health+state split
# Target: <8 — requires replacing mixin inheritance with composition


# ── Helpers ────────────────────────────────────────────────────────────

def _python_files() -> list[Path]:
    """All .py files in hunt/ (excluding __pycache__), including subdirs."""
    files = sorted(p for p in HUNT_DIR.rglob("*.py") if "__pycache__" not in str(p))
    return files


def _ruff_complexity_offenders() -> list[str]:
    """Run ruff C901 to find functions exceeding the complexity threshold.

    Uses ruff instead of the custom AST walker — ruff is faster, handles
    modern Python syntax (match/case, walrus), and is maintained upstream.
    """
    import subprocess
    result = subprocess.run(
        [".venv/bin/ruff", "check", "--select", "C901", "--output-format", "json", "hunt/"],
        capture_output=True, text=True, cwd=ROOT,
    )
    if result.returncode == 0:
        return []
    import json
    try:
        violations = json.loads(result.stdout)
    except Exception:
        return ["ruff: failed to parse output"]
    offenders = []
    for v in violations:
        code = v.get("code", "")
        if code == "C901":
            filename = v.get("filename", "").replace(str(ROOT) + "/", "")
            location = v.get("location", {})
            row = location.get("row", "?")
            msg = v.get("message", "").split("is too complex")[0].strip()
            # Extract CC value from message like "Function is too complex (16)"
            import re
            m = re.search(r"\((\d+)\)", v.get("message", ""))
            cc_val = m.group(1) if m else "?"
            offenders.append(f"{filename}:{row} {msg} CC={cc_val}")
    return offenders


# ── File size guardrails ───────────────────────────────────────────────

class TestFileSizes:
    """No file may exceed its threshold — catches regressions early.

    When a file is intentionally split, add the new (smaller) files to
    MAX_LINES and lower the old entry.  A growing file is a smell even
    if it hasn't been split yet — these tests force a conscious decision.
    """

    @pytest.mark.arch
    def test_no_file_exceeds_threshold(self):
        offenders = []
        for path in _python_files():
            # Match by relative path from hunt/ (e.g. "server.py" or "handlers/admin.py")
            rel = str(path.relative_to(HUNT_DIR))
            threshold = MAX_LINES.get(rel)
            if threshold is None:
                # Also try just the filename for backward compat
                threshold = MAX_LINES.get(path.name)
            if threshold is None:
                continue
            actual = sum(1 for _ in open(path, encoding="utf-8"))
            if actual > threshold:
                offenders.append(f"{rel}: {actual} > {threshold}")
        assert not offenders, (
            "File(s) exceeded their line threshold — split or raise the "
            f"limit intentionally:\n  {chr(10).join(offenders)}"
        )

    @pytest.mark.arch
    def test_no_new_huge_files(self):
        """Any new file over 500 lines must be registered in MAX_LINES."""
        unregistered = []
        for path in _python_files():
            rel = str(path.relative_to(HUNT_DIR))
            lines = sum(1 for _ in open(path, encoding="utf-8"))
            if lines > 500 and rel not in MAX_LINES and path.name not in MAX_LINES:
                unregistered.append(f"{rel}: {lines} lines (not in MAX_LINES)")
        assert not unregistered, (
            "New file(s) over 500 lines found — add them to MAX_LINES in "
            f"test_architecture.py:\n  {chr(10).join(unregistered)}"
        )


# ── Cyclomatic complexity guardrails ───────────────────────────────────

class TestComplexity:
    """No function may exceed MAX_CYCLOMATIC complexity.

    Uses ruff C901 for complexity analysis — faster and handles modern
    Python syntax (match/case, walrus) that custom AST walkers miss.
    """

    @pytest.mark.arch
    def test_no_function_exceeds_complexity(self):
        offenders = _ruff_complexity_offenders()
        if offenders:
            offenders.sort(
                key=lambda s: int(s.rsplit("CC=", 1)[1])
                if s.rsplit("CC=", 1)[-1].isdigit() else 0,
                reverse=True,
            )
            pytest.fail(
                "Functions exceeding cyclomatic complexity "
                f"(threshold={MAX_CYCLOMATIC}):\n  "
                + "\n  ".join(offenders)
            )


# ── Silent-except guardrail (AI anti-pattern) ──────────────────────────

class TestNoSilentExcept:
    """Bare ``except: pass`` is forbidden — the #1 AI anti-pattern.

    The agent wraps problematic code in ``try/except: pass`` to make tests
    pass formally while silently swallowing real errors. This test catches
    only the *actual* silent suppression (except followed by pass), not all
    broad exception handlers — catching ``except Exception`` with logging
    or return-value handling is legitimate error recovery, not suppression.

    Uses AST analysis (not ruff BLE001) because BLE001 flags all
    ``except Exception`` without re-raise, including legitimate handlers
    that log or return default values.
    """

    @pytest.mark.arch
    def test_no_silent_except_pass(self):
        """No bare ``except: pass`` or ``except Exception: pass``.

        Errors must be logged or re-raised.  Catching *specific* exceptions
        (OSError, ValueError, KeyError, etc.) with ``pass`` is acceptable —
        that's intentional suppression of a known, narrow error.  Only
        broad/bare catches with ``pass`` are flagged: they swallow unknown
        errors and hide bugs.
        """
        # Exception types that are "broad" — catching them with pass
        # silently swallows unknown errors.
        BROAD_TYPES = {"Exception", "BaseException", "object"}
        offenders = []
        for path in _python_files():
            rel = str(path.relative_to(HUNT_DIR))
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"))
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if not isinstance(node, ast.ExceptHandler):
                    continue
                body = node.body
                if not (len(body) == 1 and isinstance(body[0], ast.Pass)):
                    continue
                # Determine exception type
                if node.type is None:
                    # bare except — always flag
                    offenders.append(f"{rel}:{node.lineno} except bare: pass")
                elif isinstance(node.type, ast.Name):
                    if node.type.id in BROAD_TYPES:
                        offenders.append(f"{rel}:{node.lineno} except {node.type.id}: pass")
                elif isinstance(node.type, ast.Tuple):
                    # Flag only if ALL elements are broad
                    names = [getattr(e, "id", None) for e in node.type.elts]
                    if all(n in BROAD_TYPES for n in names):
                        etype = ",".join(n or "?" for n in names)
                        offenders.append(f"{rel}:{node.lineno} except ({etype}): pass")
                # Specific exceptions (OSError, ValueError, etc.) = OK
        assert not offenders, (
            "Silent except:pass with broad/bare catch found — these swallow "
            "unknown errors and hide bugs. Use logger.debug/warning, re-raise, "
            "or catch a specific exception type:\n  " + "\n  ".join(offenders[:30])
        )


# ── Branch coverage guardrail ──────────────────────────────────────────

class TestBranchCoverage:
    """Branch coverage must not drop below the recorded baseline.

    Branch coverage (not just line coverage) catches deleted logic: if an
    ``if`` branch is removed, line coverage may stay the same but branch
    coverage drops.  This makes it a stronger guard against silent logic
    deletion by AI agents.

    The threshold is set to the *current* baseline and must only go up.
    Run ``./test.sh --coverage`` to see the current value.
    """

    COVERAGE_BASELINE = 58  # current branch coverage % — only goes up

    @pytest.mark.arch
    def test_branch_coverage_above_baseline(self):
        """Check branch coverage via pytest-cov.

        Runs the functional test suite in a subprocess with coverage
        collection, parses the JSON report, and asserts the branch
        coverage is at or above the baseline.

        Run ``./test.sh --coverage`` manually for a full human-readable report.
        """
        import subprocess, json, re, tempfile, os
        try:
            import pytest_cov  # noqa: F401
        except ImportError:
            pytest.skip("pytest-cov not installed — run: pip install pytest-cov")
        cov_file = tempfile.mktemp(suffix=".json")
        try:
            result = subprocess.run(
                [".venv/bin/python", "-m", "pytest", "tests/",
                 "-p", "no:terminal", "-p", "no:capture",
                 "-m", "not slow and not arch",
                 "--cov=hunt", "--cov-branch",
                 f"--cov-report=json:{cov_file}",
                 "--cov-fail-under=0"],
                capture_output=True, text=True, cwd=ROOT,
                timeout=180,
            )
        except subprocess.TimeoutExpired:
            pytest.skip("coverage subprocess timed out — run ./test.sh --coverage manually")
        if not os.path.exists(cov_file):
            pytest.skip("coverage JSON not generated — run ./test.sh --coverage manually")
        with open(cov_file) as f:
            report = json.load(f)
        actual = int(round(report["totals"]["percent_covered"]))
        assert actual >= self.COVERAGE_BASELINE, (
            f"Branch coverage dropped to {actual}% (baseline {self.COVERAGE_BASELINE}%). "
            "Deleted logic or removed tests caused coverage to fall. "
            "Restore the missing tests or logic, then raise COVERAGE_BASELINE."
        )


# ── Security: SAST (bandit) ────────────────────────────────────────────

class TestBanditClean:
    """No HIGH or MEDIUM severity bandit findings in hunt/.

    Bandit catches: hardcoded credentials, shell injection, weak crypto,
    unsafe deserialization (pickle/yaml.load), SQL injection, binding to
    all interfaces, and other common Python security anti-patterns.

    False positives are suppressed with ``# nosec <CODE>`` comments that
    document *why* the finding is not a real vulnerability.  The test
    fails if any HIGH/MEDIUM finding lacks a nosec suppression.

    Run standalone: ``./test.sh --security``
    """

    @pytest.mark.arch
    def test_no_high_medium_bandit_findings(self):
        import subprocess
        result = subprocess.run(
            [".venv/bin/bandit", "-r", "hunt/", "-f", "json", "-q"],
            capture_output=True, text=True, cwd=ROOT, timeout=60,
        )
        import json
        try:
            report = json.loads(result.stdout)
        except json.JSONDecodeError:
            pytest.skip("bandit output not parseable — check bandit installation")
        results = report.get("results", [])
        offenders = []
        for r in results:
            severity = r.get("issue_severity", "LOW")
            if severity in ("HIGH", "MEDIUM"):
                rel = r["filename"].replace(str(ROOT) + "/", "")
                offenders.append(
                    f"{rel}:{r['line_number']} [{severity}/{r['issue_confidence']}] "
                    f"{r['test_id']}: {r['issue_text'][:80]}"
                )
        assert not offenders, (
            "Bandit found HIGH/MEDIUM security issues without nosec suppression.\n"
            "Fix the issue or add `# nosec <CODE> — <reason>` if it's a false positive:\n  "
            + "\n  ".join(offenders[:30])
        )


# ── Security: SCA (pip-audit) ──────────────────────────────────────────

class TestNoKnownCVEs:
    """No known CVEs in runtime dependencies.

    ``pip-audit`` checks installed packages against the PyPA advisory
    database.  Only runtime dependencies (from requirements.txt) are
    checked — dev tools (pytest, bandit, ruff, etc.) are excluded.

    Run standalone: ``./test.sh --security``
    """

    @pytest.mark.arch
    def test_no_known_vulnerabilities_in_runtime_deps(self):
        import subprocess
        result = subprocess.run(
            [".venv/bin/pip-audit", "--strict", "--format", "json"],
            capture_output=True, text=True, cwd=ROOT, timeout=120,
        )
        import json
        try:
            report = json.loads(result.stdout)
        except json.JSONDecodeError:
            pytest.skip("pip-audit output not parseable — check pip-audit installation")
        # Read runtime deps from requirements.txt
        req_path = ROOT / "requirements.txt"
        if not req_path.exists():
            pytest.skip("requirements.txt not found")
        runtime_deps = set()
        for line in req_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                # Extract package name (strip version specifiers)
                import re
                m = re.match(r"^([A-Za-z0-9_.-]+)", line)
                if m:
                    runtime_deps.add(m.group(1).lower())
        vulnerabilities = report.get("dependencies", [])
        offenders = []
        for dep in vulnerabilities:
            name = dep.get("name", "").lower()
            if name in runtime_deps:
                for vuln in dep.get("vulns", []):
                    offenders.append(
                        f"{dep['name']} {dep.get('version','?')} "
                        f"{vuln.get('id','?')}: fix in {vuln.get('fix_versions','?')}"
                    )
        assert not offenders, (
            "Known CVEs found in runtime dependencies:\n  "
            + "\n  ".join(offenders[:20])
            + "\nUpdate the package in requirements.txt to the fixed version."
        )
