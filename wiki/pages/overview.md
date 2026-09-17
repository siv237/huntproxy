---
updated: 2026-09-17
commit: b028d67
tags: [concept]
---

# Обзор huntproxy

huntproxy — инструмент поиска, проверки и управления пулом прокси с Web UI.
Ведёт пул из открытых источников, оценивает качество каждого прокси,
маршрутизирует трафик и поднимает HTTP/SOCKS5/transparent прокси-серверы.

## Что делает

- Скачивает списки прокси из 23 открытых источников (HTTP/HTTPS/SOCKS4/SOCKS5)
  (`sources/default.ini:32-55`, парсинг `hunt/constants.py:39-101`).
- Проверяет каждый прокси: доступность, задержка, скорость, HTTPS/CONNECT,
  страна/ISP через ip-api.com, детект MITM, антифрод-флаги.
- Считает рейтинг 0–100 и ведёт блэклисты (ручной + скачанные IP-списки).
- Поднимает HTTP CONNECT, SOCKS5 и transparent прокси с выбором upstream,
  пулом и маршрутизацией по доменам.
- Показывает всё через SPA Web UI (vanilla JS) и REST API.

## Порты по умолчанию

| Порт | Сервис |
|---|---|
| `17177` | Web UI / API (`hunt/main.py:20`) |
| `17277` | HTTP CONNECT прокси (`hunt/proxy_runner.py:28`) |
| `17278` | SOCKS5 прокси (`hunt/socks5_runner.py:20`) |
| `17477` | Transparent прокси (`hunt/transparent_runner.py:36`) |

## Стек

- **Backend:** Python 3, asyncio, без веб-фреймворка — свой HTTP-сервер и роутер.
- **Хранилище:** SQLite (`state.db` — конфигурация/рейтинги, `stats.db` — события/трафик).
- **Frontend:** vanilla JS, CSS-переменные, самописные SVG-графики, i18n на 6 языков.
- **Внешние данные:** ip-api.com (гео/флаги), proxycheck.io (справочный fraud-скор).

## Архитектура кода

`hunt.py` — тонкая точка входа, весь код в пакете `hunt/`.

Ключевой приём — **`HuntState` собирается из ~30 миксинов**
(`hunt/state.py:46`). Каждая подсистема — отдельный файл-миксин
(`hunt/db.py`, `hunt/check_*.py`, `hunt/health_*.py`, `hunt/routing.py` и т.д.),
что позволяет держать файлы под лимитом 500 строк и изолировать домены.

Отдельно стоят:
- `hunt/models.py` — `ProxyRating` (лист, без зависимостей от hunt).
- `hunt/conn.py` — низкоуровневые SOCKS5/SOCKS4/HTTP CONNECT.
- `hunt/router.py` — реестр HTTP-роутов (лист).
- `hunt/server.py` — `HuntServer` + регистрация роутов.
- `hunt/handlers/*.py` — 11 доменных модулей HTTP-обработчиков.
- `hunt/scheduler*.py` + `hunt/task_executor.py` — планировщик и реестр задач.

Автогенерируемая карта модулей — `MODULES.md` (`scripts/module_map.py`).
В вики она не дублируется, см. там полный список из 66 модулей и связность.

## Основные подсистемы (страницы вики)

- [rating](rating.md) — модель `ProxyRating`, формула рейтинга, EWMA, антифрод v3.
- [checks](checks.md) — конвейер hunt, validate, health-check, MITM, speed, fraud.
- [state](state.md) — `HuntState`, миксины, две базы SQLite, события, действия.
- [proxy-server](proxy-server.md) — раннеры, выбор upstream, пул, строгий fallback, канал, PAC.
- [routing](routing.md) — доменные списки и выбор маршрута.
- [scheduler](scheduler.md) — единый планировщик и реестр задач.
- [changelog](changelog.md) — восстановленная история разработки по git.
- [frontend](frontend.md) — Web UI.
- [infra](infra.md) — установка, обновление, сервисы.

## Источники

- `README.ru.md` — пользовательское описание.
- `MODULES.md` — карта модулей (авто).
- `docs/proxy-check-workflow.md` — детальный рабочий процесс проверки.
- `docs/quality-control-report.md` — манифест качества.
- `docs/ROUTING_PLAN.md`, `docs/SCHEDULER_PLAN.md` — проектирование подсистем.
