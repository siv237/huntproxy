---
updated: 2026-09-17
commit: b028d67
tags: [entity]
---

# Источники данных, загрузка и бэкап

## Прокси-источники (`hunt/proxy_sources.py`)

23 открытых GitHub-списка. Фабричный набор — `sources/default.ini` секция
`[proxy]`, парсится в `DEFAULT_SOURCES` (`hunt/constants.py:39-101`).

- `_seed_default_sources` (`:10-28`) — засев в пустую таблицу `proxy_sources`.
- `_parse_source_url` (`:30-53`) — выводит slug/имя/протокол из URL
  (socks5/socks4/https/http/mixed).
- `_migrate_sources` (`:82-112`) — добавляет новые дефолты, не трогая
  пользовательские; правит старый URL monosans.
- `_record_source_fetch` (`:55-80`) — статистика fetch
  (`last_fetched_at/status/count/error`, `total_fetched`).
- `_parse_source_text` (`:114`) — regex `ip:port`, порт 1..65535.
- Хранение адресов — таблица `proxy_source_entries` (коммит `2c8dc9d`).

## IP-блэклисты (`hunt/ip_blacklist_sources.py`, `hunt/ip_blacklist.py`)

Скачанные списки (Emerging Threats, FireHOL, IPsum, Blocklist.de — секция
`[ip_blacklist]`). Парсер `_parse_ip_blacklist` (`hunt/ip_blacklist.py:8`)
поддерживает одиночные IP, CIDR и диапазоны `a-b` (`:46-71`); матчинг —
in-memory exact + интервалы сетей (`:22-28`, `_is_ip_blacklisted`, `:73`).

`_apply_ip_blacklist_to_proxy` (`:104`) снижает score по числу **разных**
источников (`ip_blacklist_hits`), множитель `0.75^hits` (мин `0.25`).
API: `/api/ip-blacklists`, `/api/ip-blacklist/entries|matches`.

## Страновые блоклисты (`hunt/blocklists.py`)

Семантика (`:1-17`): `direction` — `inside`/`outside`/`domestic`;
`class` — `block` (route pool) / `white` (route direct), переопределяется
полем `route`; `list_type` — `ip` (влияет на score) / `domain`
(авто-создание `domain_lists` + `domain_entries` для роутинга).

- Дефолты — секции `[blocklist:<id>]` из `sources/*.ini`, сидятся
  `_seed_default_blocklists` (`:31`).
- `_route_for_source` (`:255`): explicit route > direct для white > pool для block.
- `_download_blocklists` (`:314`): параллельно, curl через `stream_download`,
  прокси скачивания = `download_proxy` источника или канал
  (`_channel_curl_proxy`, `:334-343`).
- `_parse_domain_blocklist` (`:269`) использует `normalize_domain_pattern`.
- Коммиты `8888f12`, `0597133` (RU domestic whitelist + split pool).

## Общий загрузчик (`hunt/download.py`)

Не фиксированный `--max-time`, а **детект застоя**: curl запускается без
`--max-time`, stdout читается чанками 64КБ.
- `CURL_CONNECT_TIMEOUT=15` — в curl;
- `CONNECT_TIMEOUT=30` — питон-таймаут первого байта;
- `STALL_TIMEOUT=45` — таймаут последующих чанков.
При застое процесс убивается. `curl_args` (`:30`) добавляет
`-sS -L --connect-timeout`, опционально `-f`, UA, `--proxy`.
Коммиты `5b464e4` (stall-detection + прогресс), `768d9e8` (разделение connect
и stall), `94469ee`.
Прогресс доступен через `/api/proxy-sources/progress` и аналоги.

## Экспорт/импорт

- `hunt/state_download.py` — `_save_working_file`, экспорт рабочих списков
  (`data/working.txt`, `blacklist.txt`, `ratings.json`).
- `/api/export` (`hunt/handlers/hunt.py:51`), `/api/import` (`:58`).
- `/api/download/<file>` (`hunt/handlers/core.py:125`) — whitelist файлов.

## Бэкап/восстановление (`hunt/backup.py`)

`BACKUP_GROUPS` (`:11-72`) — 15 логических групп, каждая мапится в
`(db_attr, table)` с `db_attr` = `state` или `stats`:

ratings, blacklist, favorites, ip_blacklist, blocklists, proxy_sources, routing,
custom_proxies, runtime_state, history, traffic_log, events, actions,
canary_history, proxy_checks.

- `get_backup_groups` (`:77-94`) — метаданные + живые row-count.
- `create_backup` (`:96-125`) — JSON `{format, version, created_at, groups}`.
- `restore_backup` (`:127-182`) — проверка формата, `DELETE` + `INSERT OR
  REPLACE`, затем перезагрузка in-memory.
- Плановая задача `backup` пишет `data/backups/backup_<ts>.json`
  (`hunt/task_executor.py:194-209`).

## Прокси-пинг (`hunt/proxy_ping.py`)

`ProxyPingMixin` — секундный пинг активного маршрута для бейджа в шапке
(коммит `118e07d`). API `GET /api/proxy/ping`.

## См. также

- [routing](routing.md) — куда попадают доменные блоклисты.
- [checks](checks.md) — как скачанные IP-ЧС влияют на score.
- [api](api.md) — эндпоинты источников, `/api/backup`, `/api/restore`.
