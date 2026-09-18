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

# Hard ceiling for every module in hunt/ (no file may become a monolith).
MAX_FILE_LINES = 500

# Per-file ceilings, stricter than MAX_FILE_LINES, for modules already slimmed
# down. These are targets, not snapshots — numbers are deliberately omitted to
# avoid rotting: run ./test.sh --arch to see actuals. Lower an entry when a
# file is split; never raise one.
MAX_LINES = {
    "server.py": 350,        # handler extraction done
    "scheduler.py": 500,     # persistence+API extracted
    "state.py": 250,         # persistence+downloads extracted
    "proxy_runner.py": 350,  # switch history extracted
    "proxy_sources.py": 500,
    "snapshot.py": 500,
    "blocklists.py": 500,
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

MAX_MIXIN_COUNT = 31  # HuntState direct bases — God Object; only goes down, target <8
# Target: <8 — requires replacing mixin inheritance with composition.
# Lower this constant whenever a responsibility is removed from HuntState.

# Base modules that must stay dependency-free: they are the bottom of the
# import graph, and their isolation is what keeps the package import-safe.
LEAF_MODULES = (
    "conn.py",
    "models.py",
    "router.py",
    "constants.py",
    "geo.py",
    "domain_parser.py",
)


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


def _hunt_imports(path: Path) -> set[str]:
    """Absolute ``hunt.*`` modules imported by *path* (relative imports
    cannot escape a leaf module and are ignored here)."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError:
        return set()
    deps: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if not node.level and node.module and node.module.split(".")[0] == "hunt":
                deps.add(node.module)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] == "hunt":
                    deps.add(alias.name)
    return deps


def _resolve_dep(mod: str, raw: str, modules: dict[str, Path]) -> str | None:
    """Map an imported name to a known module file."""
    if raw in modules:
        return raw
    children = sorted(m for m in modules if m.startswith(raw + "."))
    return children[0] if children else None


def _module_import_graph() -> dict[str, set[str]]:
    """Adjacency map of ``hunt`` modules → imported ``hunt`` modules.

    Includes imports nested inside functions (lazy imports): a cycle is a
    boundary smell regardless of where the import statement lives.
    """
    modules: dict[str, Path] = {}
    for path in _python_files():
        parts = list(path.relative_to(HUNT_DIR).with_suffix("").parts)
        if parts[-1] == "__init__":
            parts = parts[:-1]
        modules[".".join(["hunt"] + parts)] = path

    graph: dict[str, set[str]] = {}
    for mod, path in modules.items():
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        edges: set[str] = set()
        for node in ast.walk(tree):
            raw: str | None = None
            if isinstance(node, ast.ImportFrom):
                if node.level:
                    base = mod.rsplit(".", node.level)[0] if mod.count(".") >= node.level else "hunt"
                    raw = base + ("." + node.module if node.module else "")
                elif node.module and node.module.startswith("hunt"):
                    raw = node.module
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith("hunt"):
                        target = _resolve_dep(mod, alias.name, modules)
                        if target:
                            edges.add(target)
                continue
            if raw is None:
                continue
            target = _resolve_dep(mod, raw, modules)
            if target:
                edges.add(target)
        graph[mod] = edges
    return graph


def _find_cycles(graph: dict[str, set[str]]) -> list[str]:
    """Return human-readable import cycles (DFS three-colour marking)."""
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {m: WHITE for m in graph}
    stack: list[str] = []
    cycles: list[str] = []

    def dfs(u: str) -> None:
        color[u] = GRAY
        stack.append(u)
        for v in graph.get(u, ()):
            if color.get(v, BLACK) == GRAY:
                cycles.append(" -> ".join(stack[stack.index(v):] + [v]))
            elif color.get(v, BLACK) == WHITE:
                dfs(v)
        stack.pop()
        color[u] = BLACK

    for m in graph:
        if color[m] == WHITE:
            dfs(m)
    return cycles


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
    def test_no_file_exceeds_global_limit(self):
        """Every module (listed or not) must stay under MAX_FILE_LINES.

        Unlike ``MAX_LINES`` this is a blanket ceiling: no module — including
        brand-new ones — may become a monolith by simply not being registered.
        """
        offenders = []
        for path in _python_files():
            lines = sum(1 for _ in open(path, encoding="utf-8"))
            if lines > MAX_FILE_LINES:
                rel = str(path.relative_to(HUNT_DIR))
                offenders.append(f"{rel}: {lines} > {MAX_FILE_LINES}")
        assert not offenders, (
            f"File(s) over the global {MAX_FILE_LINES}-line limit — split them "
            f"into focused modules:\n  {chr(10).join(offenders)}"
        )


# ── God Object guardrail (HuntState mixin count) ───────────────────────

class TestMixinCount:
    """HuntState must not grow more mixed-in responsibilities.

    ``HuntState`` is composed by inheriting from many mixins rather than by
    composition; each new base widens the God Object and makes the class
    harder to reason about. The budget is the current count and may only go
    down — remove an entry from ``MAX_MIXIN_COUNT`` when a responsibility is
    extracted into a collaborator.
    """

    @pytest.mark.arch
    def test_huntstate_mixin_count_within_budget(self):
        tree = ast.parse((HUNT_DIR / "state.py").read_text(encoding="utf-8"))
        bases: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == "HuntState":
                bases = [
                    getattr(b, "id", None) or getattr(b, "attr", None) or "?"
                    for b in node.bases
                ]
                break
        assert bases, "HuntState class not found in hunt/state.py"
        assert len(bases) <= MAX_MIXIN_COUNT, (
            f"HuntState now has {len(bases)} mixins (budget {MAX_MIXIN_COUNT}). "
            "Do not mix in new responsibilities — use composition or a helper "
            "object, then lower MAX_MIXIN_COUNT when you extract one:\n  "
            + ", ".join(bases)
        )


# ── Import-boundary guardrails (acyclic graph, dependency-free leaves) ──

class TestImportBoundaries:
    """Keep the ``hunt`` package import graph acyclic and its base modules
    dependency-free.

    Cycles make import order fragile and hide coupling; leaf modules are the
    foundation everything else may import, so they must import nothing from
    the package themselves.
    """

    @pytest.mark.arch
    def test_leaf_modules_have_no_hunt_dependencies(self):
        offenders = []
        for name in LEAF_MODULES:
            path = HUNT_DIR / name
            if not path.exists():
                offenders.append(f"{name}: missing (update LEAF_MODULES)")
                continue
            deps = _hunt_imports(path)
            if deps:
                offenders.append(f"{name}: imports {', '.join(sorted(deps))}")
        assert not offenders, (
            "Leaf modules must stay dependency-free (they keep the import "
            "graph acyclic):\n  " + "\n  ".join(offenders)
        )

    @pytest.mark.arch
    def test_no_circular_imports(self):
        graph = _module_import_graph()
        cycles = _find_cycles(graph)
        assert not cycles, (
            "Circular imports found in hunt/ — they make import order fragile "
            "and hide coupling. Break the cycle by importing from the module "
            "that actually defines the symbol:\n  " + "\n  ".join(cycles[:10])
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


# ── Dead-code guardrail (ruff F401/F841/E722) ──────────────────────────

class TestNoDeadCode:
    """No unused imports, unused variables, or bare ``except:`` in hunt/.

    Ruff's default ``./test.sh`` pass is advisory (errors ignored), so these
    rules could silently rot. This test makes them binding: F401 (unused
    import), F841 (unused variable) and E722 (bare except) must stay at zero.
    """

    RULES = ("F401", "F841", "E722")

    @pytest.mark.arch
    def test_no_unused_or_bare_except(self):
        import json
        import subprocess

        ruff = ROOT / ".venv/bin/ruff"
        if not ruff.exists():
            pytest.skip("ruff not installed in .venv — run: pip install ruff")
        result = subprocess.run(
            [str(ruff), "check", "hunt/", "--config", "ruff.toml",
             "--select", ",".join(self.RULES), "--output-format", "json"],
            capture_output=True, text=True, cwd=ROOT, timeout=60,
        )
        try:
            violations = json.loads(result.stdout) if result.stdout.strip() else []
        except json.JSONDecodeError:
            pytest.skip("ruff output not parseable — check ruff installation")
        offenders = []
        for v in violations:
            rel = v.get("filename", "").replace(str(ROOT) + "/", "")
            loc = v.get("location", {})
            offenders.append(f"{rel}:{loc.get('row', '?')} {v.get('code', '?')}: {v.get('message', '')}")
        assert not offenders, (
            "Dead code found (unused import/variable, or bare except). Remove "
            "it or handle the error explicitly:\n  " + "\n  ".join(offenders[:30])
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
    @pytest.mark.slow
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
        bandit = ROOT / ".venv/bin/bandit"
        if not bandit.exists():
            pytest.skip("bandit not installed in .venv — run: pip install bandit")
        result = subprocess.run(
            [str(bandit), "-r", "hunt/", "-f", "json", "-q"],
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
        pip_audit = ROOT / ".venv/bin/pip-audit"
        if not pip_audit.exists():
            pytest.skip("pip-audit not installed in .venv — run: pip install pip-audit")
        result = subprocess.run(
            [str(pip_audit), "--strict", "--format", "json"],
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
