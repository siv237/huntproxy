# Agent Guide

## CRITICAL RULES

- **NEVER commit without explicit user permission.** No exceptions. Wait for "commit" / "пиши в гит".
- **One bug = one commit.** If you re-fix the same bug, the previous fix was wrong. Find the root cause first, verify it actually works, then commit once.
- **Verify for real, not just with tests.** Tests passing ≠ bug fixed. Use curl, logs, profiler to confirm the actual problem is gone.

## Running tests

Always use the project test runner instead of invoking `pytest` directly:

```bash
./test.sh                # functional + contract (excludes slow + arch)
./test.sh -x             # stop on first failure
./test.sh -k rating      # run tests matching "rating"
./test.sh --arch         # architecture invariants (file sizes, complexity, silent-except, bandit, coverage)
./test.sh --security     # SAST (bandit) + SCA (pip-audit) + HTTP fuzzing (hypothesis)
./test.sh --quality      # arch + router + executor contracts
./test.sh --coverage     # functional + branch coverage report
./test.sh --map          # regenerate MODULES.md from source
./test.sh --all          # everything including slow + arch
```

**Never pipe test output through `head`/`tail`/`grep`** — run `./test.sh` raw
so the full output (every test group, every failure, ESLint warnings) is
visible.

The pre-commit hook (`.git/hooks/pre-commit`, installed via
`./install-hooks.sh`) runs `./test.sh` automatically — commits are blocked
if any functional or contract test fails. Architecture and security tests
do **not** block commits (run via `--arch` / `--security` separately).

ESLint runs on `web/js/` before pytest (when Node.js is available):

```bash
npx eslint web/js/     # lint only; 0 errors expected
```

## Quality thresholds (enforced by tests)

- **Cyclomatic complexity:** CC ≤ 15 (ruff C901). Threshold of 8 is unrealistic for async retry/timeout patterns.
- **File size:** ≤ 500 lines per module (architecture test). New oversized files must be registered in the test.
- **Silent except:** `except: pass` / `except Exception: pass` → forbidden. Use `logger.debug("suppressed", exc_info=True)`. Caught by AST-based `TestNoSilentExcept` (not ruff BLE001 — too many false positives).
- **Unused imports/vars:** ruff F401/F841 — 0 violations.
- **Bare except:** ruff E722 — 0 violations.
- **Branch coverage:** baseline 58%, only goes up.
- **Bandit SAST:** 0 HIGH/MEDIUM without `# nosec <CODE> — reason`.
- **pip-audit SCA:** 0 CVEs in runtime deps (`requirements.txt` only).
- **HTTP fuzzing:** server must never return status 0 (connection drop) or 500 on arbitrary input.

Thresholds only move one direction: complexity/file-size/coupling **down**, coverage **up**. Reversing requires an explicit commit with justification.

## Project structure

`MODULES.md` (auto-generated, run `./test.sh --map` to refresh) has the full live map: 58 modules, line counts, public APIs, import coupling. Read it first when looking for where something lives.

Key facts not obvious from filenames:

- `hunt.py` — thin entry point; re-exports from `hunt` package, runs `main()`.
- `hunt/state.py` — `HuntState` class, composed from ~20 mixins (db, events, snapshot, blacklist, checking, etc.). Each mixin is its own file (`hunt/db.py`, `hunt/events.py`, `hunt/check_*.py`, `hunt/health_*.py`, etc.).
- `hunt/server.py` (306 lines) — `HuntServer` + route registration. Actual dispatch via `hunt/router.py` (75 lines, zero deps). Handlers split into `hunt/handlers/*.py` (8 domain modules).
- `hunt/task_executor.py` — separates task planning from execution via registry.
- `hunt/check_*.py` (7 files) — proxy checking pipeline, split from former `checking.py` monolith.
- `hunt/hunt_*.py`, `hunt/health_*.py` — hunt cycle and health loop logic, split from former `health.py`.
- `hunt/scheduler*.py`, `hunt/schedule_entry.py` — scheduler engine + persistence + API.
- `hunt/conn.py` — low-level SOCKS5/SOCKS4/HTTP connect functions. Leaf module, no hunt deps.
- `hunt/models.py` — `ProxyRating` dataclass. Leaf module, no hunt deps.
- `web/` — static frontend (`index.html`, `css/`, `js/`, `locales/`).
- `data/` — runtime state, logs, downloaded lists (gitignored).
- `hunt.sh` / `daemon.sh` — foreground and daemon launch scripts.

## Key backend conventions

- `HuntState` is the single source of truth for proxy ratings, blacklists, and downloaded IP blacklist data.
- `ProxyRating.score` is the main ranking metric; keep it deterministic and non-negative.
- Manual blacklists (`in_blacklist`) are hard exclusions. Downloaded IP blacklist matches only lower the score (more matching lists → heavier penalty).
- IP blacklist entries can match multiple sources; `ip_blacklist_hits` counts distinct matching sources.
- All state changes that affect the pool should call `self._save_state()` and `self._save_working_file()` when appropriate.

## HTTP handler conventions

- Use `_int_param(qs, key, default)` and `_json_body(body)` from `hunt/handlers/__init__.py` for query/JSON input — never bare `int(qs.get())` or `json.loads(body).get()`. The helpers return safe defaults on invalid input, preventing server crashes (enforced by fuzz tests).
- New endpoints: `router.add("GET", "/api/...", handler)` in `hunt/server.py::_register_routes`. Add to `tests/test_router_contract.py` so the contract test covers it.
- Handlers are async `(self, raw_path, body) -> (response, status, content_type)`.

## Frontend conventions

- Pages registered in `web/js/pages/*.js`, mounted via `router.register(name, factory)`.
- Use `ui.el()` and `ui.table()` from `web/js/components.js` instead of raw DOM construction.
- Translations in `web/locales/*.json`. Add new keys to at least `en.json` and `ru.json`.

## When making changes

1. Update affected tests (or add new ones) in `tests/`.
2. Run `./test.sh` before finishing — pre-commit will block if it fails.
3. If you added/removed modules, run `./test.sh --map` to refresh `MODULES.md`.
4. If you touched security-sensitive code, run `./test.sh --security`.
5. Keep changes minimal and consistent with existing style. No comments unless asked.

## Decision log (why these choices)

- **CC threshold 15, not 8:** async retry/timeout patterns inflate CC artificially — 3 `if` + 2 `except` + 1 `for` = CC 7.
- **AST silent-except test, not ruff BLE001:** BLE001 flags all `except Exception` (277 false positives) including legitimate handlers with logging. AST test catches only the real anti-pattern: broad/bare `except` with bare `pass`.
- **Coverage baseline 58%, not 90%:** 90% would block all commits on a project at 58%. Threshold = current state, raised monotonically.
- **Architecture tests non-blocking:** would block all commits at current state. Run via `--arch` / `--quality` to track backlog.
- **No docstring control:** AI generates meaningless comments to pass automated docstring checks. Documentation quality is enforced at code review, not CI.
- **`except OSError` → `except Exception` for DB files:** `sqlite3.OperationalError` is not caught by `OSError`. Use `except Exception` with `logger.debug` for DB operations.
