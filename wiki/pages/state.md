---
updated: 2026-09-17
commit: 06630a5
tags: [entity]
---

# Состояние: HuntState и хранилище

## `HuntState` — композиция миксинов

`HuntState` (`hunt/state.py:46`) собирается множественным наследованием из 31
миксина. Это главный приём архитектуры: один объект-фасад, но каждая
подсистема живёт в своём файле. Полный список миксинов и их назначение:

| Файл | Миксин | Отвечает за |
|---|---|---|
| `hunt/db.py` | `DbMixin` | SQLite-соединения, `_init_db`; writer-классы — `hunt/db_writer.py` |
| `hunt/events.py` | `EventsMixin` | `_emit`, ring-буфер, long-poll |
| `hunt/snapshot.py` | `SnapshotMixin` | `get_snapshot`, страны, история, heatmap |
| `hunt/hunt_control.py` | `HuntControlMixin` | start/stop/pause/resume/skip |
| `hunt/hunt_cycle.py` | `HuntCycleMixin` | цикл hunt: download→blacklist→validate→health |
| `hunt/canary.py` | `CanaryMixin` | проверка живости интернета |
| `hunt/health_loops.py` | `HealthLoopsMixin` | legacy-циклы (не запускаются) |
| `hunt/health_check.py` | `HealthCheckMixin` | health-check живых, revalidate |
| `hunt/check_validation.py` | `CheckValidationMixin` | `_validate_all`, `_check_one`, merge/fast-fail |
| `hunt/check_validation_helpers.py` | `CheckValidationHelpersMixin` | `_record_check_result`, fast-fail, speed-замер |
| `hunt/check_proxy.py` | `CheckProxyMixin` | HTTP/SOCKS-пробы |
| `hunt/check_ssl.py` | `CheckSslMixin` | TLS-прокси |
| `hunt/check_speed.py` | `CheckSpeedMixin` | замер скорости |
| `hunt/check_mitm.py` | `CheckMitmMixin` | multi-target TLS-верификация MITM |
| `hunt/check_geo.py` | `CheckGeoMixin` | `_resolve_geo`, `_authoritative_egress` |
| `hunt/fraudscore.py` | `FraudScoreMixin` | proxycheck.io |
| `hunt/check_rating.py` | `CheckRatingMixin` | `_update_rating`, `_record_traffic_fail`, `_create_rating` |
| `hunt/check_rating_apply.py` | `CheckRatingApplyMixin` | `_apply_ok_result/egress/listen/fraud` |
| `hunt/blacklist.py` | `BlacklistMixin` | ручной чёрный список |
| `hunt/ip_blacklist.py` | `IPBlacklistMixin` | матчинг egress-IP по скачанным спискам |
| `hunt/proxy_sources.py` | `ProxySourcesMixin` | источники прокси (CRUD) |
| `hunt/ip_blacklist_sources.py` | `IPBlacklistSourcesMixin` | источники IP-ЧС |
| `hunt/blocklists.py` | `BlocklistsMixin` | страновые блоклисты |
| `hunt/routing.py` | `RoutingMixin` | доменная маршрутизация |
| `hunt/custom_proxies.py` | `CustomProxiesMixin` | кастомные прокси |
| `hunt/channel.py` | `ChannelMixin` | outbound-канал движка |
| `hunt/actions.py` | `ActionsMixin` | аудит-лог действий |
| `hunt/backup.py` | `BackupMixin` | backup/restore по группам |
| `hunt/favorites.py` | `FavoritesMixin` | избранное |
| `hunt/state_persistence.py` | `StatePersistenceMixin` | `_save_state`, `_load_state`, рейтинги/ЧС runtime |
| `hunt/state_working.py` | `StateWorkingMixin` | working-set: `_load/_save_working_file`, миграция |
| `hunt/state_download.py` | `StateDownloadMixin` | экспорт рабочих списков |
| `hunt/pac.py` | `PacMixin` | генерация PAC |
| `hunt/proxy_ping.py` | `ProxyPingMixin` | пинг активного маршрута |

`__init__` задаёт контейнеры: `ratings: dict[str, ProxyRating]`, `blacklist`,
`favorites`, `_geo_cache`, счётчики фаз и прогресса, буферы
`_dirty_ratings` / `_proxy_check_buffer` (`hunt/state.py:61-225`).

## Две базы SQLite

`DbMixin` держит два соединения (`hunt/db.py`):
- **`state.db`** — конфигурация и состояние: рейтинги, блэклисты, источники,
  маршруты, расписания, runtime-флаги.
- **`stats.db`** — статистика: `events`, `actions`, `traffic_log`,
  `proxy_checks`, `canary_history`, `history`.

Разделение сделано коммитом `1805951` («Разнесения статистики и списков на
разные базы») — чтобы тяжёлый трафик-лог не конкурировал за блокировки с
состоянием пула.

Запись идёт через фоновые writer'ы (`_DbWriter`/`_SharedConn`), есть очередь
`_queue_traffic_log`, которая попутно кормит `TrafficStats` (`hunt/db.py:18-25`).

## События и действия

- `_emit` (`hunt/events.py:10-39`) — буфер в памяти, обрезка 500→300, запись в
  `stats.db`, пробуждение long-poll через `asyncio.Condition`.
- `_log_action` (`hunt/actions.py:19-46`) — таблица `actions` со снапшотом
  счётчиков hunt для диагностики рассинхрона (коммит `b161c25`).

## Нормализация состояния

- `_save_state()` / `_save_dirty_ratings()` — инкрементальное сохранение: полное
  каждые ≥200 изменений, dirty-save каждые 50 (`hunt/check_rating.py:63-67`).
  Введено коммитом `1e861c2` для устранения 90% CPU при валидации.
- `_load_state` разбит на `_load_ratings`/`blacklist`/`favorites`/`runtime`
  (`ffe1a3e`).
- Настройки читаются из `config["hunt"]` (`hunt/state.py:162-179`): `parallel`,
  `timeout`, `us_only`, `country_filter`, `health_*`, `speed_parallel`,
  `canary_hosts`, `mitm_hosts`, `ip_blacklists.*`.

## `TrafficStats` — часовой роллап

`hunt/traffic_stats.py` — in-memory агрегат `_hours[hour_start][upstream]`,
обновляется O(1) при записи трафика, окно 35 суток, `load_from_db` при старте
(`hunt/state.py:211-215`). Нужен, чтобы dashboard-ручки не сканировали
миллионную `traffic_log` (коммит `04b3fab`).

## См. также

- [api](api.md) — ручки, читающие состояние.
- [scheduler](scheduler.md) — фоновые задачи, меняющие состояние.
- [monitoring](monitoring.md) — снапшот/события/трафик.
