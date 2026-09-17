---
updated: 2026-09-17
commit: 06630a5
tags: [concept]
---

# Тесты и контроль качества

## Раннер `test.sh`

Перед pytest:
1. ESLint по `web/js/` (при наличии Node; ошибки блокируют, `test.sh:10-16`).
2. venv + pytest/pytest-asyncio/ruff/pytest-cov при отсутствии.
3. Ruff-чек запускается, но **не блокирует** дефолтный прогон (`:42-44`) —
   конкретные правила проверяются arch-тестами как backlog.

Режимы (`:65-114`):

| Флаг | Маркер |
|---|---|
| (без флага) | `not slow and not arch` |
| `--all` | без маркера |
| `--arch` | `arch and not slow` |
| `--router` | `router` |
| `--executor` | `executor` |
| `--quality` | `(arch and not slow) or router or executor` |
| `--security` | `(arch and not slow) or fuzz` (доставляет bandit/pip-audit/hypothesis) |
| `--coverage` | pytest + `--cov=hunt --cov-branch --cov-fail-under=58` |
| `--map` | `scripts/module_map.py` |
| `-k`, `-x` | pass-through в pytest |

Маркеры объявлены в `pyproject.toml:12-18`: `slow`, `arch`, `router`,
`executor`, `fuzz`; `asyncio_mode = "auto"`.

## Уровни тестов (`docs/quality-control-report.md:69-85`)

- **Функциональные + контрактные — блокируют коммит.**
- **Архитектурные + безопасности — backlog, не блокируют.**

Контрактные:
- `tests/test_router_contract.py` — каждый зарегистрированный endpoint
  резолвится (`router`).
- `tests/test_executor_contract.py` — разделение планирования/исполнения
  (`executor`).
- `tests/test_api_consistency.py` — согласованность API.

Архитектурные (`tests/test_architecture.py`, маркер `arch`): размер файлов
(≤500 строк), CC≤15 (ruff C901), God Object/coupling, границы импортов,
модули-листья, запрет silent-except.

- `TestBranchCoverage` (baseline 58%) помечен ещё и `slow`: он запускает
  **вложенный** прогон всего функционала под coverage (минуты), поэтому исключён
  из `--arch`/`--quality`/`--security`. Реальный контроль порога — в
  `./test.sh --coverage` (`--cov-fail-under=58`).
- `TestBanditClean`/`TestNoKnownCVEs` скипаются, если `bandit`/`pip-audit` не
  установлены в `.venv` (а не падают `FileNotFoundError`).

Безопасность (`tests/test_http_fuzz.py`, `fuzz`): сервер не должен отдавать
status 0 (drop) или 500 на произвольный ввод.

Frontend-тесты: `test_locales.py` (полнота переводов + запрет хардкода
кириллицы), `test_navigation.py` (nav ↔ route ↔ titles),
`test_js_bundle.py` (свежесть бандла через `build_js_bundle.py --check`).

Медленные — `test_scheduler.py`, `test_speed.py` (маркер `slow`).

## Пороги (enforced)

- CC ≤ 15 (ruff C901);
- файл ≤ 500 строк (arch-тест; новые oversized регистрируются);
- `except: pass` / `except Exception: pass` запрещены (AST-тест
  `TestNoSilentExcept`), вместо них `logger.debug(..., exc_info=True)`;
- ruff F401/F841, E722 — 0;
- branch coverage baseline 58%, только вверх;
- bandit — 0 HIGH/MEDIUM без `# nosec <CODE> — reason`;
- pip-audit — 0 CVE в runtime-deps (`requirements.txt`);
- HTTP-фаззинг — без status 0/500.

Пороги двигаются в одну сторону: сложность/размер/связность — вниз,
покрытие — вверх.

## Pre-commit

`hooks/pre-commit` копируется в `.git/hooks/` через `install-hooks.sh`
(вызывается из `update.sh:188-191`). **Важно:** строка `./test.sh`
закомментирована (`hooks/pre-commit:8`), поэтому фактической блокировки
коммитов тестами сейчас нет, хотя `AGENTS.md` это заявляет. Скрипт лишь
печатает сообщения и завершается успешно (`set -euo pipefail` не помогает —
`exit 0` подразумевается).

## Инструменты

pytest, pytest-asyncio, pytest-cov (`--cov-branch`), ruff (C901/E722),
bandit (SAST), pip-audit (SCA), hypothesis (фаззинг), ESLint (JS), AST-анализ
(God Object, coupling, silent-except).

## Почему так (decision log)

- **CC ≤ 15, а не 8:** async retry/timeout раздувают CC — 3 `if` + 2 `except` + 1 `for` = CC 7.
- **AST-тест вместо ruff BLE001:** BLE001 ловит все `except Exception` (277 ложных),
  AST-тест — только `except: pass`.
- **Baseline покрытия 58%, а не 90%:** 90% заблокировал бы все коммиты; порог = текущее
  состояние и растёт монотонно.
- **Arch-тесты не блокируют:** на текущем состоянии блокировали бы всё; запуск через
  `--arch`/`--quality` как backlog.
- **Без контроля docstring:** AI генерирует бессмысленные комментарии ради проверки;
  качество документации — на ревью.
- **`except OSError` → `except Exception` для БД:** `sqlite3.OperationalError` не
  ловится `OSError`; использовать `except Exception` с `logger.debug`.

## См. также

- [infra](infra.md) — `test.sh`, pre-commit hook, скрипты.
- [frontend](frontend.md) — что проверяют `test_locales`/`test_js_bundle`.
- [wip](wip.md) — незакоммиченный фикс и его тест.
