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
