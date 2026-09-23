---
updated: 2026-09-23
commit: 8b0c0c0
tags: [concept]
---

# Прокси-серверы и выбор upstream

`HuntServer` создаёт три раннера (`hunt/server.py:36-38`), все биндятся на
web-host (обычно `127.0.0.1`, `hunt/main.py:19,23`). SOCKS5 и transparent
делегируют upstream HTTP-раннеру — поэтому роутинг, канал и пул работают
одинаково во всех протоколах.

| Раннер | Порт | Файл |
|---|---|---|
| `ProxyRunner` (HTTP CONNECT) | 17277 | `hunt/proxy_runner.py` |
| `Socks5Runner` | 17278 | `hunt/socks5_runner.py` |
| `TransparentRunner` | 17477 | `hunt/transparent_runner.py` |

## ProxyRunner (`hunt/proxy_runner.py`)

- `asyncio.start_server(self._handle, ...)` (`:95`).
- `_handle` (`:108`): `CONNECT host:port` → туннель + `200 Connection
  Established`; иначе — HTTP forward (`_handle_http_forward`, `:166`).
- Ретраи forward только для запросов без тела (`_FORWARD_RETRIES=2`, `:18-20`),
  голова ответа читается до отправки клиенту (`_read_response_head`, `:224`) —
  точка commit.
- `_relay` (`:292`) — двунаправленный pipe 64КБ, считает `bytes_in/out`.
- `_log` (`:326`) — `traffic_log` через `state._queue_traffic_log`.
- `get_status` (`:338`) — running, порт, active proxy, direct mode, fallback,
  счётчики, последние логи, `switch_history`.
- `select(address)` (`:40`) — выбор upstream, угадывание протокола по порту
  (1080/10808/9050 → socks5, 4145 → socks4), запись в switch-history.

## Socks5Runner (`hunt/socks5_runner.py`)

- Без аутентификации: greeting → `[5,0]` (`:77-83`), разбор atyp 1/3/4
  (`:89-102`). Upstream берётся из `state.proxy_runner.active_proxy_addr`
  (`:23-28`) — единый выбранный прокси на все раннеры.
- Handshake/relay делегируются HTTP-раннеру (`:128-148`), логирование своё
  (`via: "socks5"`).

## TransparentRunner (`hunt/transparent_runner.py`)

- Для iptables REDIRECT/TPROXY; клиент сразу шлёт TLS/HTTP.
- Оригинальный адрес — `SO_ORIGINAL_DST = 80` (`_get_original_dst`, `:107`):
  IPv6 `IPPROTO_IPV6` длина 28, IPv4 `SOL_IP` длина 16.
- Защита от самозацикливания `_is_self_target` (`:85`) — дроп, если dst
  локальный и порт совпадает с любым своим listener-портом.
- Передача — через `ProxyRunner._connect_upstream`/`_relay` (`:151-167`).

## Выбор upstream (`hunt/proxy_routing.py`)

`_connect_upstream` (`:26`): `_is_self_target` → `state._resolve_route(host)` →
`_connect_by_route` (`:46`). Маршрут — строка:

| Route | Поведение |
|---|---|
| `direct` | прямое соединение (или через канал, `:79`) |
| `custom:<id>` | через кастомный прокси (`:92`) |
| `proxy:<addr>` | конкретный прокси (`:132`) |
| `pool_selected` | active_proxy, при провале — fallback/pool |
| `pool` / `""` | пул (`_connect_via_pool`, `:164`) |
| fallback | `_connect_fallback` (`:186`) |

### Пул

`_build_pool` (`:199`): только `pool_eligible`; для CONNECT нужен
`supports_connect` или socks4/5; сортировка `live` и `grace` по score desc.
`_connect_via_pool` пробует **до 8** прокси в порядке пула (`:168`).

### Фильтр стран пула (авто-выбор и фолбэк)

Политика — один ключ `routing_config["pool_country_policy"]` (JSON:
`mode` ∈ `off|only|exclude`, `countries` — ISO-коды; `hunt/routing.py`),
читается через короткий TTL-кеш `_pool_country_policy_cached`, чтобы не
ходить в SQLite на каждое соединение. Проверка
`pool_country_allows_code(code, mode, codes)`: страна выхода —
`egress_country_code or country_code`. В `only` прокси без измеренной страны
выхода отбрасывается (нельзя подтвердить соответствие), в `exclude` —
остаётся. Применяется только к `_build_pool` (авто-пул и переход по отказу
в пул); ручной выбор конкретного прокси не ограничен. Если `only`
не пересекается с доступными странами, API отдаёт `warning`
(`no_proxies_in_selected_countries`) — пул был бы пуст и весь пул-трафик
получал бы 502. API — `/api/pool/countries` (`hunt/handlers/pool.py`).
UI — кнопка в карточке «Выбранный апстрим».

### Строгий режим без фолбэка

`_pool_fallback_enabled()` читает `routing_config["fallback_pool"]`
(отсутствует → `"false"` → strict, `:37-44`). При strict провал конкретного
прокси возвращает `None` (502), без подмены другим прокси (`:59-62`).
Управление — `/api/routing/fallback` (`hunt/routing.py:53-58`).
Введено коммитом `596a1df`.

### Ретраи

`_CONNECT_RETRIES=3`, задержки `(0.1,0.2,0.4)`, `_CONNECT_TIMEOUT=5.0`
(`:8-12`). TCP-отказ и обрыв рукопожатия ретраятся; «прокси ответил, но отказал
в target» — нет (`:159-161`). SSL-прокси оборачиваются TLS при `ssl_supported`
(`_open_proxy_conn`, `:215`).

### Известные особенности

- `_failover_idx` (`:180`) присваивается, но не читается — фактической
  round-robin/random-ротации нет, порядок детерминирован (score desc).
- «Cascade» — только UI-название режимов выбора (`web/js/pages/server.js:108-112`).

## Канал (`hunt/channel.py`)

Весь выход движка (и клиента) через вышестоящий прокси. Route:
`"" | direct | proxy:<addr> | custom:<id>`; `pool` намеренно не поддерживается
(рекурсия проверки пула через сам пул) (`:31-33`).

- `_outbound_connect` (`:106`) — drop-in замена `asyncio.open_connection`,
  **fail-closed**: при заданном route и недоступном прокси бросает `OSError`,
  без молчаливого direct (`:125-129`).
- TLS до прокси для `https`, затем SOCKS5/SOCKS4/HTTP handshake (`:143-159`).
- `_channel_curl_proxy` (`:178`) — строка для `curl --proxy`
  (socks5→socks5h, socks4→socks4a).
- `effective_timeout` (`:95`) — `max(base, 25)` при канале.
- Route персистится в `routing_config.channel_route` (`:221`), API
  `/api/channel/status|select` (`hunt/handlers/admin.py:16-24`).
- Введено коммитом `6483ae2`.

## PAC (`hunt/pac.py`)

`render_pac(config)` (`:10`) — зеркало PHP `autoproxyRenderPac`: сначала DIRECT
(по `shExpMatch`, `isInNet`, `isPlainHostName`), иначе `PROXY host:port`
(failover через `; `). Хранение: `pac_config`, `pac_direct_hosts`,
`pac_internal_nets` (`:47-64`). Кэш `_PAC_CACHE_TTL=5` (`:45`).
`detect_lan_ip` (`:66`) и `list_local_ips` (`:84`).
Эндпоинты `/pac.js`, `/api/pac/*` (`hunt/handlers/pac.py`). Коммиты `b42b3a9`,
`cb029a0`.

## Кастомные прокси (`hunt/custom_proxies.py`)

Таблица `custom_proxies` (`:19-23`), пароль маскируется `****` (`:10-14`).
CRUD + `test_custom_proxy` (`:204`): TCP (10с), handshake, HTTP-код (ok при
2xx/3xx), latency в ms. Дефолтный `test_url = http://httpbin.org/ip`.
Tor/anti-ban — это UI-подсказки, спец-обработки в бэкенде нет.
Замечание: `_connect_via_custom` (`hunt/proxy_routing.py:92`) не оборачивает
кастомный `https`-прокси в TLS, в отличие от канала.

## Прозрачный перехват (`hunt/handlers/interception.py`)

- Состояние — `data/transparent_state.json` (`:26-28`), читается без root.
- `_interception_readiness` (`:73`): root, iptables-legacy/iptables, cgroup v2,
  исполняемый `setup_iptables.sh`, запущенный transparent и его порт.
- `apply` (`:203`) — hard gate по readiness (409), при провале probe
  (8.8.8.8:53 / 1.1.1.1:443) авто-`stop` (rollback), иначе 500.
- `stop` (`:243`).
- Скрипт `setup_iptables.sh`: цепочка `HUNTPROXY_REDIRECT`, исключения по
  uid/cgroup/локальным сетям/`OWN_IP`, дефолт — redirect всего outbound TCP на
  17477. Коммит `99efc3e`.

Дополнительно есть **выборочный режим** (redirect только заданных ресурсов,
ipset + сверка реального состояния ядра) — см.
[interception](interception.md).
