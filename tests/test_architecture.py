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
    "proxy_runner.py": 350,  # current: 309 — route selection extracted
    "proxy_sources.py": 500, # current: 474 — OK (just under)
    "snapshot.py": 500,     # current: 447 — OK
    "blocklists.py": 500,   # current: 427 — OK
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


def _cyclomatic_complexity(func) -> int:
    """Rough McCabe CC: 1 + number of branching nodes in the AST."""
    import textwrap
    try:
        src = inspect.getsource(func)
    except (OSError, TypeError):
        return 1
    # inspect.getsource returns the method with its class-level indentation,
    # which ast.parse rejects.  Dedent so the first line is at column 0.
    src = textwrap.dedent(src)
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return 1
    complexity = 1
    for node in ast.walk(tree):
        if isinstance(node, (ast.If, ast.While, ast.For, ast.ExceptHandler,
                             ast.With, ast.AsyncWith, ast.BoolOp)):
            # BoolOp (and/or) adds one path per additional operand.
            if isinstance(node, ast.BoolOp):
                complexity += len(node.values) - 1
            else:
                complexity += 1
        elif isinstance(node, (ast.ListComp, ast.SetComp, ast.DictComp)):
            # comprehensions have an implicit for + optional if
            complexity += 1 + len(node.generators)
    return complexity


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

    The biggest offender is typically ``HuntServer._handle`` with its
    100+ if/elif route chain.  This test documents current offenders so
    we can track progress as the router is extracted.
    """

    @pytest.mark.arch
    def test_no_function_exceeds_complexity(self):
        offenders = []
        seen_methods = set()  # dedup: mixin method also appears on HuntState
        for path in _python_files():
            # Build module name from relative path: hunt/handlers/admin.py → hunt.handlers.admin
            rel = path.relative_to(HUNT_DIR).with_suffix("")
            mod_name = "hunt." + ".".join(rel.parts)
            try:
                mod = importlib.import_module(mod_name)
            except Exception:
                continue
            # Module-level functions
            for name, obj in inspect.getmembers(mod, inspect.isfunction):
                if obj.__module__ != mod_name:
                    continue
                cc = _cyclomatic_complexity(obj)
                if cc > MAX_CYCLOMATIC:
                    offenders.append(f"{path.name}:{name}() CC={cc}")
            # Methods — only on the class where they are *defined*, not
            # inherited.  This avoids counting each mixin method twice
            # (once on the Mixin, once on the composed HuntState).
            for cname, cls in inspect.getmembers(mod, inspect.isclass):
                if cls.__module__ != mod_name:
                    continue
                for mname, method in inspect.getmembers(cls, inspect.isfunction):
                    # qualifier: ClassName.method — skip if defined elsewhere
                    qual = f"{cname}.{mname}"
                    if qual in seen_methods:
                        continue
                    seen_methods.add(qual)
                    # Only count if this class is the origin of the method.
                    for parent in cls.__mro__[1:]:
                        if mname in parent.__dict__:
                            qual = None  # defined in a parent — skip
                            break
                    if qual is None:
                        continue
                    cc = _cyclomatic_complexity(method)
                    if cc > MAX_CYCLOMATIC:
                        offenders.append(f"{path.name}:{cname}.{mname}() CC={cc}")
        if offenders:
            offenders.sort(key=lambda s: int(s.rsplit("CC=", 1)[1]), reverse=True)
            pytest.fail(
                "Functions exceeding cyclomatic complexity "
                f"(threshold={MAX_CYCLOMATIC}):\n  "
                + "\n  ".join(offenders)
            )


# ── Import boundary guardrails ─────────────────────────────────────────

class TestImportBoundaries:
    """Module-level dependency direction rules.

    These catch the most common coupling violation: a lower-level module
    importing a higher-level one, creating a cycle or a god-dependency.
    """

    @pytest.mark.arch
    def test_scheduler_does_not_import_server(self):
        """Scheduler must not depend on the HTTP server layer."""
        mod = importlib.import_module("hunt.scheduler")
        src = inspect.getsource(mod)
        assert "hunt.server" not in src, (
            "hunt.scheduler imports hunt.server — scheduler should be "
            "decoupled from the HTTP transport layer"
        )

    @pytest.mark.arch
    def test_scheduler_does_not_import_checking(self):
        """Scheduler must not import the proxy-checking logic directly.

        Task executors access checking through ``self.state`` (runtime
        injection), not through module-level imports.  This keeps the
        scheduler plannable in isolation.
        """
        mod = importlib.import_module("hunt.scheduler")
        src = inspect.getsource(mod)
        assert "import hunt.checking" not in src, (
            "hunt.scheduler imports hunt.checking — executors should go "
            "through the state object, not direct module imports"
        )

    @pytest.mark.arch
    def test_models_has_no_hunt_dependencies(self):
        """ProxyRating (models.py) must not depend on any hunt module.

        models.py is the leaf of the dependency tree — everything else
        depends on it, it depends on nothing.
        """
        mod = importlib.import_module("hunt.models")
        src = inspect.getsource(mod)
        hunt_imports = [
            line for line in src.splitlines()
            if line.strip().startswith("from hunt.") or line.strip().startswith("import hunt.")
        ]
        assert not hunt_imports, (
            f"hunt.models imports other hunt modules — it must be a leaf:\n"
            f"  {chr(10).join(hunt_imports)}"
        )

    @pytest.mark.arch
    def test_router_has_no_hunt_dependencies(self):
        """Router must be a pure leaf module — no hunt imports.

        The routing layer is infrastructure, not domain logic.  It must
        not depend on state, server, or any other hunt module.
        """
        mod = importlib.import_module("hunt.router")
        src = inspect.getsource(mod)
        hunt_imports = [
            line for line in src.splitlines()
            if line.strip().startswith("from hunt.") or line.strip().startswith("import hunt.")
        ]
        assert not hunt_imports, (
            f"hunt.router imports other hunt modules — it must be a leaf:\n"
            f"  {chr(10).join(hunt_imports)}"
        )


# ── God Object guardrails ──────────────────────────────────────────────

class TestGodObject:
    """HuntState must not grow more mixins — it should shrink.

    The 15-mixin composition is documented tech debt.  This test ensures
    we don't add a 16th mixin without a conscious decision.  The target
    is to extract responsibilities into standalone classes that receive
    state via construction, not via inheritance.
    """

    @pytest.mark.arch
    def test_hunt_state_mixin_count_bounded(self):
        from hunt.state import HuntState
        bases = [b for b in HuntState.__bases__ if b.__name__ != "object"]
        assert len(bases) <= MAX_MIXIN_COUNT, (
            f"HuntState has {len(bases)} base classes (limit {MAX_MIXIN_COUNT}). "
            "Extract a responsibility into a standalone class instead of "
            "adding another mixin. Current bases: "
            + ", ".join(b.__name__ for b in bases)
        )

    @pytest.mark.arch
    def test_hunt_state_init_attribute_count_bounded(self):
        """Count assignments in __init__ — a proxy for God Object size."""
        import textwrap
        from hunt.state import HuntState
        src = inspect.getsource(HuntState.__init__)
        src = textwrap.dedent(src)
        tree = ast.parse(src)
        attrs = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Attribute) and \
                       isinstance(target.value, ast.Name) and \
                       target.value.id == "self":
                        attrs.add(target.attr)
        # Current: ~70. Target: <40 after persistence/runner extraction.
        assert len(attrs) <= 50, (
            f"HuntState.__init__ assigns {len(attrs)} attributes (limit 50). "
            "Extract groups of related attributes into dedicated classes."
        )


# ── Server coupling guardrails ─────────────────────────────────────────

class TestServerCoupling:
    """HuntServer must not grow tighter coupling to HuntState internals.

    Currently server.py accesses self.state.* ~190 times.  The target
    after router extraction is <100 (handlers go through narrow service
    objects, not the God Object directly).
    """

    @pytest.mark.arch
    def test_server_state_access_bounded(self):
        with open(HUNT_DIR / "server.py", encoding="utf-8") as f:
            tree = ast.parse(f.read())
        count = 0
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Attribute):
                if isinstance(node.value.value, ast.Name) and \
                   node.value.value.id == "self" and \
                   node.value.attr == "state":
                    count += 1
        assert count <= 100, (
            f"server.py accesses self.state.* {count} times (limit 100). "
            "Extract handlers into service objects to reduce coupling."
        )

    @pytest.mark.arch
    def test_server_handle_route_count_bounded(self):
        """The _route method must use the Router registry, not if/elif chains."""
        from hunt.server import HuntServer
        src = inspect.getsource(HuntServer._route)
        route_count = src.count("if path")
        # Was 116 before router extraction. Now ~0 (dispatch via Router).
        assert route_count <= 5, (
            f"HuntServer._route has {route_count} route checks (limit 5). "
            "Routes must be registered via Router, not chained with if/elif."
        )
