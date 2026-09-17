---
updated: 2026-09-17
commit: 8b0c0c0
tags: [concept]
---

# Инфраструктура и скрипты

## Жизненный цикл

| Скрипт | Назначение |
|---|---|
| `install.sh` | установка/обновление под Ubuntu 24.04, root |
| `update.sh` | обновление без потери настроек |
| `uninstall.sh` | удаление службы, iptables-цепи, cgroup, каталога |
| `daemon.sh` | менеджер фонового демона (start/stop/restart/status/log) |
| `hunt.sh` | foreground-запуск |
| `setup_iptables.sh` | transparent redirect через iptables nat |
| `test.sh` | раннер тестов + ESLint + ruff |

### install.sh

- Ставит apt-зависимости (`python3`, `python3-venv`, `python3-pip`, `git`,
  `curl`, `:37-42`).
- Режим: есть `.git` → UPDATE (бэкап локальных правок в `data/pre-update-*`,
  `git fetch` + `reset --hard origin/main`, `:47-103`), иначе CLEAN INSTALL
  (`git clone -b main`, `:104-114`).
- venv один раз, зависимости через хэш `requirements.txt`, проверка
  `import yaml` (`:116-137`).
- Создаёт `huntproxy.service` (`ExecStart .venv/bin/python hunt.py`,
  Restart on-failure, `:147-165`), но не запускает.

### update.sh

- Флаги: `-y` (авто-подтверждение), `-f` (форс), `--test` (прогон тестов),
  `--no-restart` (`:32-47`).
- Сравнивает HEAD, показывает новые коммиты (`:92-135`), при локальных
  правках предупреждает (`:137-148`).
- `git reset --hard origin/main`; зависимости только при смене хэша
  (`:150-173`).
- Пересобирает JS-бандл и инкрементит `?v=` в `index.html` (`:175-186`),
  переустанавливает pre-commit hook (`:188-191`).

### daemon.sh / hunt.sh

- `daemon.sh` хранит `.hunt.pid`, лог `data/daemon.log`, HOST/PORT из
  `HUNT_HOST`/`HUNT_PORT` (дефолт 127.0.0.1:17177).
- `hunt.sh`: `--public|--listen-all|-P` (0.0.0.0), `--kill|-K`, поднимает
  `ulimit -n 65535` (`:115`), пишет PID, `exec python hunt.py`.

### setup_iptables.sh

Цепочка `HUNTPROXY_REDIRECT`, предпочитает `iptables-legacy`. Исключения:
`--uid-owner`, cgroup v2 (`--exclude-cgroup`/`--cgroup-pid`), локальные сети,
`OWN_IP`. Дефолт — redirect всего outbound TCP на 17477. Пишет состояние в
`data/transparent_state.json`. Коммиты `99efc3e`, `0387835`.

## Конфигурация

`config.example.yaml` (трекery, локальный `config.yaml` в .gitignore):
- `server`: web/http/socks5/transparent listen, таймауты;
- `proxies`: `validate_interval`, `validate_parallel`, `health_*`, `speed_parallel`,
  `max_failures`, `cooldown`, `strategy`, `us_only`;
- `ip_blacklists`: enabled, fetch_interval, 4 дефолтных фида;
- `logging`; `hunt`: `parallel=300`, `timeout=8`, `us_only`, `health_*`.

`sources/default.ini` — фабричные источники: `[proxy]` (23 списка),
`[ip_blacklist]` (4 фида), `[blocklist:<id>]` (страновые, поля
name/country/direction/type/url). Парсится `hunt/constants.py:39-101`.
Коммит `541d27b`.

## Скрипты разработки (`scripts/`)

- `module_map.py` — генерирует `MODULES.md` (строки, публичные API, импорты,
  связность). Запуск `./test.sh --map`.
- `build_js_bundle.py` — конкатенация страниц в `pages.bundle.js`, `--check`.

## Тесты

`test.sh` перед pytest гоняет ESLint по `web/js/` и ruff. Группы:
`./test.sh` (functional+contract), `--all`, `--arch`, `--router`, `--executor`,
`--quality`, `--security` (bandit + pip-audit + hypothesis), `--coverage`,
`--map`. Маркеры: `slow`, `arch`, `router`, `executor`, `fuzz` (`pyproject.toml:12-18`).

38 тест-модулей (`tests/test_*.py`); ключевые контрактные — `test_router_contract.py`,
`test_executor_contract.py`, `test_api_consistency.py`; архитектурные —
`test_architecture.py`; frontend — `test_locales.py`, `test_navigation.py`,
`test_js_bundle.py`.

## Pre-commit

`hooks/pre-commit` и `install-hooks.sh`. **Замечание:** в `hooks/pre-commit`
строка `./test.sh` закомментирована (`hooks/pre-commit:8`), поэтому заявленная
в `AGENTS.md` блокировка коммитов тестами фактически не работает. Требует
сверки.
