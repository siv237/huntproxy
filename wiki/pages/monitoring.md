---
updated: 2026-09-17
commit: 8b0c0c0
tags: [entity]
---

# Мониторинг: снапшот, connectivity, события, трафик

## Снапшот дашборда (`hunt/snapshot.py`)

`SnapshotMixin.get_snapshot()` собирает данные Overview в один ответ:
счётчики пула (working/new/confirmed/grace), топ-страны, ресурсы системы,
история, checks/heatmap, live-трафик. Отдаётся `GET /api/snapshot`
(`hunt/handlers/core.py:43`) с TTL 1.5с и single-flight.

Производительность снапшота — серия коммитов `7e64c8a`, `04b3fab`,
`b4d1bf9` (TTL-кэш, вынос трафик-ручек из снапшота).

## Connectivity / canary (`hunt/canary.py`)

Назначение — отличать падение провайдера от мёртвых прокси и автоматически
ставить/снимать паузу hunt.

- `_canary_loop` (`:9-21`) — каждые 15с `_check_canary`; мертво →
  `pause_hunt(manual=False)`, ожило и пауза не ручная → `resume_hunt`.
- `_check_canary` (`:23-38`) — хосты `canary_hosts` (дефолт
  `["ya.ru","google.com","2ip.ru"]`), alive = больше половины прошли.
- `_canary_probe_hosts` (`:40-57`) — TCP :443, timeout 25 при канале иначе 8.
- `_canary_direct_info` (`:65-101`) — HTTP ip-api, детект смены IP/ISP.
- `_canary_record` (`:103-115`) — `canary_history`.
- `is_internet_alive` (`:119-123`) — кэш 30с.

Цикл canary живёт внутри `_hunt_cycle` (`hunt/hunt_cycle.py:10`), т.е. вне hunt
канарейка не опрашивается; `get_canary_status` умеет запускать проверку
принудительно (`hunt/handlers/admin.py:196`). API: `/api/canary/status|history|hosts`.

**Известные шероховатости:** в `except`-ветке `_canary_record` (`canary.py:114-117`)
присваивается неопределённая `result` (потенциальный `NameError`);
`_canary_cache` нигде не заполняется, поэтому `get_canary_status` всегда идёт
во fallback-ветку (`canary.py:126`).

## События (`hunt/events.py`)

`_emit` (`:10-39`) — буфер в памяти (обрезка 500→300), запись в `stats.db`,
пробуждение long-poll через `asyncio.Condition`. `GET /api/events?since=`
ждёт до 0.5с новых событий. Фронт слушает `CustomEvent('hunt-events')`
(`web/js/app.js:240-251`).

## Действия оператора (`hunt/actions.py`)

`_log_action` (`:19-46`) пишет в таблицу `actions` со снапшотом счётчиков hunt
— для диагностики рассинхрона счётчиков (коммит `b161c25`). Чтение — `:48-68`,
API `GET /api/actions?limit=`. UI — страница `actions.js`.

## Трафик (`hunt/handlers/traffic.py`, `hunt/traffic_stats.py`)

- `TrafficStats` (`hunt/traffic_stats.py`) — in-memory часовой роллап
  `_hours[hour][upstream]`, окно 35 суток, `prune`/`totals`/`by_upstream`/
  `load_from_db`. Обновляется O(1) из `_queue_traffic_log`
  (`hunt/db.py:18-25`), грузится при старте (`hunt/state.py:211-215`).
- Логирование запросов — `traffic_log`, кольцевой буфер в раннерах.
- API: `/api/traffic/live`, `/api/traffic`, `/api/requests`, `/api/clients`
  (+rDNS), `/api/domains`, `/api/errors`, `/api/traffic/routes`,
  `/api/traffic/search`, `/api/bandwidth`, `/api/traffic/summary` (TTL 10с).
- Тяжёлые SQL-ручки вынесены из event loop, live-фильтр ищет по всему
  `traffic_log` в выбранном окне (`907b4ba`, `5815e8b`).
- Страницы UI: `proxy-control.js` (монитор трафика), `traffic-flow.js`
  (визуализация пути), `analytics.js` (heatmap, история).

## Прокси-пинг (`hunt/proxy_ping.py`)

`ProxyPingMixin` — секундный пинг клиентского маршрута для бейджа в шапке
(спарклайн задержек + гео, коммит `118e07d`). API `GET /api/proxy/ping`;
опрос на фронте каждую 1с (`web/js/app.js:281`).

Основной источник (`_ping_source`, `hunt/proxy_ping.py:75`) — **активный
прокси клиентского трафика** (`_proxy_active_addr`), иначе direct. Канал
(вышестоящий прокси движка) намеренно не является основным источником: бейдж
обязан показывать итоговый пинг клиентского пути, а не пинг канала.

Пинг канала (`_ping_channel_once`, `hunt/proxy_ping.py:179`) измеряется
**параллельно** тем же секундным циклом, когда канал задан
(`_channel_is_set`), и отдаётся в `proxy/ping.channel`
(`_channel_ping_status`, `hunt/proxy_ping.py:214`). Дублирующее измерение
для чипа канала: `GET /api/channel/status` → `ping`
(`hunt/channel.py:201`), фронт показывает «Канал: host:port · Nms»
в `web/js/app.js:269` (`pollChannel` каждые 3с).

## История (`hunt/snapshot.py`, `hunt/switch_history.py`)

- `_push_history` — снапшот размера пула по времени (таблица `history`),
  чистка retention задачей `history`.
- `switch_history.py` — история переключений прокси: `record_switch` (`:21`),
  `enrich_switch_history` (`:29`) со схлопыванием одинаковых action, метаданными
  rating и трафиком за период (`_traffic_by_period`,
  `hunt/switch_history_stats.py:22`), TTL-мемоизация 10с.

## См. также

- [state](state.md) — `TrafficStats` и буферы событий.
- [api](api.md) — трафик- и snapshot-эндпоинты.
- [checks](checks.md) — автопауза по canary и `switch_history` при проверках.
