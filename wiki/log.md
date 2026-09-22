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

## [2026-09-22] ingest | Выборочный перехват: вкладка, ресурсы, ipset, сверка

- Страница `#/interception` стала вкладочной (`ui.tabs`): вкладка «Общий»
  сохраняет прежний whole-machine-контент, добавлена вкладка «Выборочный».
- Backend: новые модули `hunt/interception_selective.py` (CRUD ресурсов,
  DNS-резолв в state.db), `hunt/interception_reconcile.py` (реальное состояние
  iptables/ipset, reconcile при старте, resolver-loop),
  `hunt/handlers/interception_selective.py` (API). Таблицы внесены в
  `_init_state_db` (`hunt/db.py`) и в `BACKUP_GROUPS` (`hunt/backup.py`).
- `setup_iptables.sh`: режим `--selective` (цепочка `HUNTPROXY_SELECTIVE`,
  ipset `huntproxy_selective`), `--drop-quic` (`filter/OUTPUT` UDP/443),
  `--redirect-ports`, fallback без ipset; общий `stop`.
- Общий и индивидуальный выключатели; сверка с ядром после рестарта
  (`reconcile_on_startup` из `hunt/main.py`).
- Frontend: `web/js/pages/interception.js` (табы + UI ресурсов), методы в
  `web/js/api.js`, локали 6 языков. Тесты: `tests/test_interception_selective.py`,
  дополнены `test_api.py`/`test_router_contract.py`.
- Прогоны: `./test.sh` 666/666, `--quality` 101/101, ESLint 0 ошибок, ruff
  по изменённым файлам чисто. Бандл и `MODULES.md` пересобраны.
- Не закоммичено; боевой сервис не рестартился (по правилу AGENTS.md).

## [2026-09-22] ingest | Деплой фичи в прод ad-hoc и заметка об обновлении

- По явному подтверждению пользователя фича выборочного перехвата скопирована
  из dev в `/opt/huntproxy` выборочно (`install` изменённых/новых файлов, без
  `config.yaml`/`data`/`.venv`), бэкап кода —
  `/tmp/kilo/prod-backup/huntproxy-code-20260922-101935.tar.gz`.
- `systemctl restart huntproxy`: active, ошибок в журнале нет; живые ручки
  `/api/interception/selective` (root/ready, правил нет) и
  `/api/interception/resources` отвечают 200, snapshot ок.
- Прод-дерево теперь грязное относительно `HEAD ae6e94b` (ad-hoc).
- Заведена страница [deploy](pages/deploy.md): два независимых клона, штатный
  `update.sh` (commit+push → fetch → reset --hard → restart) и ad-hoc-путь с
  рисками, шаблон копирования, проверки, текущее состояние прода.

## [2026-09-22] ingest | Триггер «обнови прод для тестирования» зафиксирован

- В `AGENTS.md` добавлен раздел «Обновление прод-среды для тестирования»:
  фраза «обнови прод для тестирования» = ad-hoc-перенос dev → `/opt` + рестарт
  по подтверждению; «коммить» = commit+push и приведение прода через
  `update.sh`; БД прода не теряется.
- В [deploy](pages/deploy.md) добавлен раздел «Триггер и что он значит» и
  явный инвариант сохранности БД (`data/`, `config.yaml` в `.gitignore`).
- Обе правки синхронизированы в прод для паритета.
- Уточнено: фраза «обнови прод для тестирования» **сама является** явным
  разрешением на ad-hoc-копирование и рестарт для теста (рестарт без такой
  команды запрещён).

## [2026-09-22] ingest | Фикс резолва ресурсов + повторный ad-hoc деплой

- Баг прод-теста: добавленный ресурс оставался `pending`/0 IP, `apply` отдавал
  409 «no resolved addresses». Причина — резолв не инициировался при создании
  (фоновая задача срабатывает раз в `resolve_interval_sec`).
- Фикс: резолв запускается при создании/изменении ресурса
  (`asyncio.create_task`), `apply` при нуле адресов сам зовёт
  `resolve_all_enabled`, у резолва таймаут 10с на адрес. Обновлены
  [interception](pages/interception.md).
- По команде пользователя повторён ad-hoc-деплой dev → `/opt` + рестарт
  (бэкап кода `huntproxy-code-20260922-105823.tar.gz`). Проверено живьём:
  `2ip.io` → `188.40.167.81` (ok), ручки 200, ошибок в журнале нет.

## [2026-09-22] ingest | Разбор «пустого ответа»: порт 80, iface, cgroup

- Тест пользователя: при включённом перехвате `curl 2ip.io` → «Empty reply».
  Причина: дефолт «весь TCP» перехватывал HTTP/80, а Squid апстрим отвечает
  `403 ERR_ACCESS_DENIED` на `CONNECT host:80` (443 — 200); строгий режим без
  fallback → `502 no upstream` → transparent закрывал соединение.
- Фикс: дефолт `ports=443`; `--iface` (автодетект `enp3s0`) в
  `setup_iptables.sh` для REDIRECT и QUIC-drop; исключение cgroup прокси в
  селективной цепочке; конфиг+UI поле `iface`.
- Тесты 667/667; повторный ad-hoc-деплой в `/opt` + рестарт (бэкап
  `huntproxy-code-20260922-110816.tar.gz`), служба active, статус отдаёт
  `ports=443`, `iface` авто, ресурс `2ip.io` резолвнут.
