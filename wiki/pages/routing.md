---
updated: 2026-09-23
commit: 8b0c0c0
tags: [concept]
---

# Маршрутизация по доменам

Подсистема привязывает доменные списки к маршрутам (Direct / Proxy / Pool /
Custom). Реализация — `hunt/routing.py` (миксин `RoutingMixin`) плюс
`hunt/proxy_routing.py` (применение при соединении). Проектные решения —
`docs/ROUTING_PLAN.md`.

## Хранение (SQLite, `state.db`)

| Таблица | Поля |
|---|---|
| `routing_config` | key/value: `routing_enabled`, `default_route`, `fallback_pool`, `pool_country_policy`, `channel_route` |
| `domain_lists` | id, name, source, url, route, enabled, priority, created_at, updated_at |
| `domain_entries` | list_id, pattern |

Схема — `hunt/routing.py:91-95`, создание — `:135-143`, вставка записей — `:300-303`.
SQLite выбран из-за миллионов записей РКН-списков (а не JSON).

Публичные методы: `get_routing_status` (`:26`), `routing_enable/disable`
(`:38,:43`), `routing_set_default` (`:48`), `routing_set_fallback` (`:53`),
`routing_test` (`:60`), CRUD `get/create/update/delete/toggle/reorder_domain_list`
(`:88-238`). Все мутации инвалидируют кэш (`_route_cache_invalidate`, `:238`).

## Алгоритм `_resolve_route(host)` (`hunt/routing.py:293`)

Вызывается на **каждое** соединение, поэтому есть кэш `_ROUTE_CACHE_TTL=30`
(`:236-284`).

- Кэш строится только для enabled-списков с непустым route, `ORDER BY priority ASC`
  (`:256-259`). Побеждает первый совпавший список.
- Паттерны компилируются в `exact` (set) и `suffixes` (set):
  - `exact:` → только точное;
  - `*.x` / `.x` → exact(x) + suffix(.x);
  - голое `p` → exact(p) + suffix(.p).
- Routing выключен (`:295-301`): `direct_mode` → `direct`;
  `active_proxy_addr` → `proxy:<addr>`; иначе `pool`.
- Routing включён (`:303-311`): точное совпадение, затем все dot-suffixes,
  иначе `default`.

`routing_test(domain)` (`:60-86`) — отдельный честный путь (сканирует БД,
`_domain_matches`, `:314`), не через кэш.

## Производительность

Старый вариант сканировал БД синхронно на каждое соединение и «замораживал»
event loop (`:230-235`). Текущий — in-memory кэш с TTL 30с.

## Паттерны доменов (нормализация)

`normalize_domain_pattern` (`hunt/domain_parser.py:18`) поддерживает форматы:
- Clash: `DOMAIN`, `DOMAIN-SUFFIX`, `DOMAIN-KEYWORD`, `DOMAIN-REGEXP`,
  `IP-CIDR`, `IP6-CIDR`;
- v2fly: `domain`, `domain-suffix`, `domain-keyword`, `domain-regexp`, `full`.

Пропускает комментарии (`#`, `;`, `//`), чистит схему и порт
(`_clean_plain_domain`, `:54-64`). `DOMAIN-SUFFIX` → `*.`,
`IP-CIDR`/`IP6-CIDR` → `None`. Замечание: `DOMAIN-KEYWORD`/`DOMAIN-REGEXP` не
имеют спец-семантики и уходят в обычный паттерн (`:44-51`).

## Связь с блоклистами

Доменные blocklist-источники автоматически создают `domain_lists`
(id = source id, `source="blocklist"`) с route из `_route_for_source`
(white → direct, block → pool, `hunt/blocklists.py:255,269`). Коммит `0597133`
добавил RU domestic whitelist и разделение pool на selected/best.

## Использование при соединении

`ProxyRunner._connect_upstream` → `state._resolve_route(host)` →
`_connect_by_route` (`hunt/proxy_routing.py:26-77`). Строгий режим без
фолбэка описан в [proxy-server](proxy-server.md).
