# Agent Guide

## Running tests

Always use the project test runner instead of invoking `pytest` directly:

```bash
./test.sh
```

This script ensures the local `.venv` exists, installs `pytest` and `pytest-asyncio` if needed, and runs the suite with verbose output. Pass extra pytest arguments as usual:

```bash
./test.sh -x          # stop on first failure
./test.sh -k rating   # run tests matching "rating"
```

## Project structure

- `hunt.py` — thin backward-compatible entry point; it re-exports the public API from the `hunt` package and runs `main()`.
- `hunt/` — functional backend package split from the former `hunt.py` monolith:
  - `state.py` — `HuntState` class, composed from focused mixins.
  - `db.py`, `events.py`, `snapshot.py`, `health.py`, `checking.py`, `blacklist.py`, `ip_blacklist.py`, `proxy_sources.py`, `ip_blacklist_sources.py`, `routing.py`, `custom_proxies.py` — mixin modules that make up `HuntState`.
  - `models.py` — `ProxyRating` dataclass.
  - `proxy_runner.py` / `socks5_runner.py` — local proxy servers.
  - `server.py` — `HuntServer` and HTTP routing.
  - `constants.py`, `geo.py`, `logging_config.py`, `main.py` — shared helpers and entry logic.
- `web/` — static frontend (`index.html`, `css/`, `js/`, `locales/`).
- `tests/` — pytest suite. Fixtures are in `tests/conftest.py`.
- `data/` — runtime state, logs, and downloaded lists.
- `test.sh` — entry point for running tests.
- `hunt.sh` / `daemon.sh` — foreground and daemon launch scripts.

## Key backend conventions

- `HuntState` is the single source of truth for proxy ratings, blacklists, and downloaded IP blacklist data.
- `ProxyRating` stores per-proxy stats. Its `score` property is the main ranking metric; keep it deterministic and non-negative.
- Manual blacklists (`in_blacklist`) are hard exclusions. Downloaded IP blacklist matches only lower the score (more matching lists → heavier penalty).
- IP blacklist entries can match multiple sources; `ip_blacklist_hits` counts the number of distinct matching sources.
- All state changes that affect the pool should call `self._save_state()` and `self._save_working_file()` when appropriate.

## Frontend conventions

- Pages are registered in `web/js/pages/*.js` and mounted via `router.register(name, factory)`.
- Use `ui.el()` and `ui.table()` helpers from `web/js/components.js` instead of raw DOM construction.
- Translations live in `web/locales/*.json`. Add new keys to at least `en.json` and `ru.json`.

## When making changes

1. Update the affected tests (or add new ones) in `tests/`.
2. Run `./test.sh` before finishing.
3. Keep changes minimal and consistent with the existing style.
