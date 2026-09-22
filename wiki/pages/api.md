---
updated: 2026-09-17
commit: 8b0c0c0
tags: [entity]
---

# HTTP-сервер, роутер и API

## HuntServer (`hunt/server.py`)

Единый asyncio-сервер: web UI + API. В конструкторе создаёт три раннера
(`hunt/server.py:36-38`) и 11 handler-классов (`:32-60`), запускается
`asyncio.start_server` + `serve_forever` (`:62-68`), гасит раннеры при
остановке (`:70-76`).

`_handle` (`:78-135`) — ручной HTTP/1.1 парсер с keep-alive: request-line
(timeout 120с), заголовки (5с), body по `content-length` (10с), затем `_route`.
`_route` (`:180-184`): `router.match` → handler, иначе JSON 404.
`_write` (`:137-160`): статус, Content-Type/Length, Cache-Control.
`_serve_static` (`:162-178`): защита от `..`, MIME из `STATIC_MIME`.
Замечание: строка статуса всегда `HTTP/1.1 {status} OK` (`:150`), т.е. 404
отдаётся как «404 OK».

`web_legacy.py::WEB_HTML` — inline-фолбэк старого дашборда, отдаётся на
`/legacy` и на `/`, если `web/index.html` отсутствует
(`hunt/handlers/core.py:32-41`).

## Router (`hunt/router.py`)

Паттерн-диспетчер без зависимостей. `_exact: dict[(method,path)]` и
`_prefix: list[(method,prefix,handler)]` (`:37-39`).
- `add` (`:41`) — точный роут;
- `add_prefix` (`:45`) — префиксный, сортировка по убыванию длины (длинные
  раньше);
- `add_static` (`:50`) — префиксы с методом `*` (статика первая);
- `match` (`:58`) — exact → prefix.

Приоритет: exact > самый длинный prefix. Пример: `/api/schedules/status`
(exact) выигрывает у `/api/schedules/` (prefix).

## Хелперы (`hunt/handlers/__init__.py`)

- `_qs(path)` (`:12-19`) — query-строка в dict с `unquote`;
- `_int_param(qs, key, default)` (`:22-30`) — int с безопасным дефолтом;
- `_json_body(body)` (`:33-41`) — `json.loads`, при ошибке/не-dict → `{}`.

Правило проекта: никогда не вызывать `int(qs.get())` или `json.loads(body).get()`
напрямую — эти хелперы защищают сервер от краша (проверяется fuzz-тестами).

## Каталог endpoints

Регистрация — `hunt/server.py:186-346`. Формат: метод, путь, назначение.

### Core / статика (`handlers/core.py`)

| Метод | Путь | Назначение |
|---|---|---|
| GET | `/css/ /js/ /img/ /assets/ /locales/` | статика |
| GET | `/legacy` | legacy HTML |
| GET | `/favicon.ico` | иконка |
| GET | `/` , `/index` | index.html или fallback |
| GET | `/api/snapshot` | снапшот дашборда (TTL 1.5с + single-flight) |
| GET | `/api/events?since=` | long-poll событий (до 0.5с) |
| GET | `/api/countries` | список стран |
| GET | `/api/system` | системные метрики |
| GET | `/api/activity?limit=` | активность |
| GET | `/api/actions?limit=` | аудит-лог |
| GET | `/api/history?last=` | история |
| GET/POST | `/api/settings` | чтение/запись config.yaml |
| GET | `/api/logs?limit&type` | события |
| GET | `/api/downloads/count` | счётчики скачиваний |
| GET | `/api/download/<file>` | выгрузка (whitelist) |

### Hunt (`handlers/hunt.py`)

`POST /api/hunt/start|stop|pause|resume|skip`,
`POST /api/clear_dead`, `POST /api/export`, `POST /api/import`,
`POST /api/health/start|stop`.

### Pool (`handlers/pool.py`)

`POST /api/blacklist/add|remove`, `POST /api/favorites/add|remove`,
`GET /api/favorites`, `GET /api/blacklist` (пагинация).

### Proxy / SOCKS5 / Transparent (`handlers/proxy.py`)

`GET /api/proxy/status` (TTL 2с), `GET /api/proxy/alive`,
`GET /api/proxy/ping` (итоговый пинг клиентского пути + `channel`),
`GET|POST /api/proxy/start|stop|select|next|recheck|direct|fraud`,
`GET /api/socks5/status`, `GET|POST /api/socks5/start|stop`,
`GET /api/transparent/status`, `GET|POST /api/transparent/start|stop`,
`GET /api/proxy/<addr>` (карточка), `GET /api/proxies` (список/группы),
`GET /api/proxy-checks/<addr>` (история), `GET /api/proxy-heatmap`.

### Interception (`handlers/interception.py`, `handlers/interception_selective.py`)

`GET /api/interception`, `POST /api/interception/apply|stop`.
Выборочный режим: `GET /api/interception/selective`,
`GET /api/interception/selective/rules`,
`POST /api/interception/selective/{config,apply,stop,reconcile}`,
`GET|POST /api/interception/resources`, `POST|DELETE /api/interception/resources/<id>`,
`POST /api/interception/resources/<id>/toggle|resolve`. См. [interception](interception.md).

### Admin (`handlers/admin.py`)

`GET /api/channel/status` (вкл. `ping` канала), `POST /api/channel/select`,
`POST /api/settings/country_filter`, `GET /api/backup/groups`,
`POST /api/backup`, `POST /api/restore`,
`GET|POST /api/schedules`, `/status`, `/log`, `/pause`, `/resume`,
`/restore-defaults`, `/api/schedules/<id>[/toggle|/run|/stop]`,
`DELETE /api/schedules/<id>`, `GET /api/canary/status`, `/history`,
`POST /api/canary/hosts`.

### Routing / domain-lists (`handlers/routing.py`)

`GET /api/routing/status`, `POST /api/routing/enable|disable|default|fallback|reorder|test`,
CRUD `/api/domain-lists[/<id>]`.

### Sources (`handlers/sources.py`)

CRUD `/api/proxy-sources`, `/api/ip-blacklists`, `/api/blocklists`,
`/api/custom-proxies`; fetch/progress; `GET /api/ip-blacklist/entries`,
`GET /api/ip-blacklist/matches`.

### Traffic (`handlers/traffic.py`)

`GET /api/traffic/live`, `/api/traffic`, `/api/requests`, `/api/clients`,
`/api/clients/<client>`, `/api/domains`, `/api/errors`, `/api/traffic/routes`,
`/api/traffic/search`, `/api/bandwidth`, `/api/traffic/summary` (TTL 10с).

### Version / PAC

`GET /api/version`, `GET /pac.js`, `GET|POST /api/pac/config`,
`POST /api/pac/detect-ip`, `GET /api/pac/ips`.

## Кэши

TTL/single-flight у snapshot (1.5с), proxy/status (2с), traffic/summary (10с),
traffic/search (5с + stale-while-revalidate).

## См. также

- [state](state.md) — что отдают ручки снапшота/истории.
- [proxy-server](proxy-server.md) — раннеры за `/api/proxy/*`, `/api/socks5/*`.
- [monitoring](monitoring.md) — трафик-ручки и события.
- [data-sources](data-sources.md) — CRUD источников и backup/restore.
