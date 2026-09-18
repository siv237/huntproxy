# Журнал вики (log)

Append-only журнал **операций вики** (ingest / query / lint), не история кода.
История разработки проекта — [pages/changelog.md](pages/changelog.md).
Формат: `## [ГГГГ-ММ-ДД] <ingest|query|lint> | <тема>` + пункты; парсится
`grep "^## \[" log.md | tail -5`. Только дописывать, прошлые записи не править.

## [2026-09-17] ingest | Bootstrap вики

- Восстановлен changelog по `git` (267 коммитов) → [pages/changelog.md](pages/changelog.md).
- Созданы страницы: overview, state, api, scheduler, data-sources, monitoring,
  frontend, rating, checks, proxy-server, routing, infra, quality, sources-docs.
- Схема ведения вики перенесена в `AGENTS.md`; `index.md` оставлен чистым
  каталогом; `log.md` отведён под журнал операций — устранено дублирование
  истории (`log.md` ↔ `changelog.md` ↔ `git`).
- Зафиксирован незакоммиченный MITM-reconnect fix и список открытых дефектов →
  [pages/wip.md](pages/wip.md).

## [2026-09-17] ingest | MITM-reconnect fix и синхронизация ревизии

- Коммит `f18b8b5` (свежее соединение на каждую MITM-цель) влит в вики →
  [checks](pages/checks.md), [changelog](pages/changelog.md); из
  [wip](pages/wip.md) убран как закрытый.
- `.gitignore` поглотил `dataN/` (коммит `b028d67`); `data0/` больше не
  числится незакоммиченным.
- `commit` во frontmatter всех страниц поднят до `b028d67`; исправлены
  расхождения (источников 23, тест-модулей 38) и stale-утверждения в `AGENTS.md`
  (66 модулей, ~30 миксинов, 11 handler-модулей, no-op pre-commit).

## [2026-09-17] ingest | Разбиение модулей по arch-тестам + security

- Устранены нарушения arch-тестов: разбиты `handlers/traffic.py` (808→240, на
  `traffic_common/_detail/_report/_summary.py`), `handlers/proxy.py` (groups),
  `check_validation.py` (helpers), `check_rating.py` (apply), `state_persistence.py`
  (working), `db.py` (writer), `proxy_runner.py` (http), `switch_history.py`
  (stats); новые миксины внесены в [state](pages/state.md).
- `_summary_payload` разбит на хелперы — CC в норме; writer-классы — в `db_writer.py`.
- Security: добавлены `# nosec` с обоснованиями (B608/B104); `bandit`/`pip-audit`
  скипаются при отсутствии. `--coverage` теперь enforced (`--cov-fail-under=58`),
  coverage-arch-тест помечен `slow` (устранено «зависание»). Детали —
  [quality](pages/quality.md).
- `MODULES.md` пересобран: **78 модулей** (`./test.sh --map`).
- Прогоны: `./test.sh` 620/620, `--quality` 90/90, `--security` 16/16,
  покрытие 62% (baseline 58); сервис перезапущен `systemctl restart huntproxy`,
  все эндпоинты живы.
- Ревизии кода: `dda115f` (тест-инфра), `06630a5` (рефакторинг); frontmatter
  страниц поднят до `06630a5`.

## [2026-09-17] ingest | Пинг: итоговый маршрут vs пинг канала

- Основной пинг в шапке больше не переключается на канал: `_ping_source`
  (`hunt/proxy_ping.py:75`) отдаёт приоритет активному прокси клиентского
  трафика, канал исключён из основного источника.
- Пинг канала измеряется параллельно (`_ping_channel_once`, `:179`) и отдаётся
  в `proxy/ping.channel` (`_channel_ping_status`, `:214`) и в
  `GET /api/channel/status.ping` (`hunt/channel.py:201`); фронт показывает его
  в чипе канала «Канал: host:port · Nms» (`web/js/app.js:269`).
- Обновлены [monitoring](pages/monitoring.md), [data-sources](pages/data-sources.md),
  [state](pages/state.md), [frontend](pages/frontend.md), [api](pages/api.md).
- Проверка на живом сервисе: `proxy/ping.source=pool` (107.167.18.122:443) при
  канале `custom:tor` (192.168.237.2:9050), `channel.latency=336ms`;
  `./test.sh` 623/623. Незакоммичено; `commit` frontmatter — при коммите.

## [2026-09-17] ingest | Достроены arch-тесты: God Object и границы импортов

- `TestMixinCount` (`tests/test_architecture.py`) — бюджет числа прямых баз
  `HuntState` (`MAX_MIXIN_COUNT`, стало 31; константа раньше не использовалась).
- `TestImportBoundaries` — `test_no_circular_imports` (ацикличность графа
  `hunt/`, включая lazy-импорты) и `test_leaf_modules_have_no_hunt_dependencies`
  (`LEAF_MODULES`: conn/models/router/constants/geo/domain_parser).
- Найден и устранён реальный цикл `hunt.scheduler → hunt.task_executor →
  hunt.scheduler`: `task_executor` импортирует `ScheduleEntry` из
  `hunt/schedule_entry.py`, а не из `hunt/scheduler.py`.
- [quality](pages/quality.md): список arch-проверок и пороги приведены к факту;
  снят устаревший тезис «arch блокировали бы всё» (в `AGENTS.md` тоже);
  зафиксировано, что F401/F841/E722 пока не enforced (2× F401 backlog).
- Прогоны: `./test.sh --arch` 9/9, `./test.sh` 623/623. Незакоммичено.

## [2026-09-17] ingest | Мёртвый код и монолиты закрыты тестами

- Мёртвый код: убраны 10 неиспользуемых импортов (`handlers/interception.py`,
  `handlers/proxy.py`, `state.py`, `state_persistence.py`); ruff F401/F841/E722
  теперь 0 и enforced тестом `TestNoDeadCode`.
- Монолиты: `MAX_FILE_LINES = 500` — глобальный потолок **для любого** файла
  `hunt/` (`test_no_file_exceeds_global_limit`), а не только зарегистрированных;
  `MAX_LINES` остаётся персональными лимитами без «гниющих» цифр в комментариях.
- Прогоны: `./test.sh --arch` 10/10, `./test.sh` 623/623. Незакоммичено.

## [2026-09-17] ingest | Пропущенные тесты стали видимыми

- `_LiveReporter` (`tests/conftest.py`) теперь печатает блок «Skipped» с причиной
  каждого пропуска (включая команду установки: `pip install bandit` и т.п.),
  а не только счётчик. Молчаливый «зелёный» прогон при отсутствии инструмента
  исключён.
- Учитываются скипы на фазе `setup` (`skipif`/`importorskip`) и падения setup —
  раньше они не попадали в отчёт вовсе.
- Проверено: синтетический прогон репортёра выводит причины; `./test.sh`
  623/623. [quality](pages/quality.md) дополнена. Незакоммичено.
## [2026-09-18] ingest | Прогресс >100%: двойной запуск, ручной Hunt, интернет-гейт

- Диагностика по боевым `stats.db` (`/opt/huntproxy/data`): `checked` 162336
  при `checking_total` 81351 = ровно 2×; в событиях два запуска
  `proxy_check` с интервалом 1с (08:08:09/08:08:10), а также наложение
  scheduler `proxy_check` и ручного Hunt (`hunt.start` 19:37:00 при
  активном proxy_check с 19:31:11). Причина — неатомарный `_try_launch`
  (await `is_internet_alive` между проверкой и регистрацией в
  `_running_tasks`) и общие счётчики `_validate_all`.
- Правки (в рабочем дереве, незакоммичено):
  - `_launch_lock` — атомарный запуск; `_drain_queue` не запускает при паузе;
  - `hunt/scheduler_guard.py` — `cancel_all`, `_cancel_check_tasks`,
    `_internet_gate` (пауза и остановка проверок без интернета);
  - `hunt/manual_hunt.py` — `manual_start_hunt` (кнопка Start прерывает все
    задачи, сбрасывает счётчики, держит планировщик на паузе на время Hunt);
  - `health_check` получил `busy_flag=_hunt_running`; ручной `/api/health/start`
    блокируется при активном Hunt;
  - `check_validation._check_one` пробрасывает `counted=True` на retry-пути
    fast_fail.
- Обновлены [scheduler](pages/scheduler.md), [wip](pages/wip.md); `MODULES.md`
  пересобран (**80 модулей**). Прогоны: `./test.sh` 630/630, `--quality` 90/90.
- Живой сервис не трогался (правки только в dev-копии); `commit` frontmatter
  страниц — при коммите.

## [2026-09-18] ingest | Деплой правок в прод (без коммита)

- По явной команде пользователя (`/opt/huntproxy`) синхронизированы только
  изменённые runtime-файлы: `check_validation.py`, `handlers/hunt.py`,
  `hunt_control.py`, `hunt_cycle.py`, `schedule_entry.py`, `scheduler.py`,
  `state.py`, новые `manual_hunt.py`/`scheduler_guard.py`. Свои незакоммиченные
  правки прода (удалённые неиспользуемые импорты, импорт `ScheduleEntry` из
  `schedule_entry`, улучшения live-репортера тестов) сохранены; в `state.py`
  отличие — только отсутствие неиспользуемого `import ipaddress`.
- Бэкап кода: `/tmp/kilo/prod-huntproxy-20260918-104518/hunt-code.tar.gz`.
- `systemctl restart huntproxy` (PID 81359) — служба active, ошибок в журнале
  нет; snapshot: phase=health, счётчики сброшены; далее один `proxy_check`
  (checked растёт линейно, 2% при total 81983, без переполнения).
- В git не коммитилось (по указанию — до теста прода).
