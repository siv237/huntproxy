# Карта модулей
Автоматически сгенерировано из исходного кода. Не редактировать руками.
Запуск: `python scripts/module_map.py`
Всего модулей: 80 | Всего строк: 13139
---
## Сводка
| Модуль | Строк | Публичные классы/функции | Импортирует из hunt |
|--------|-------|--------------------------|---------------------|
| `hunt/__init__.py` | 14 | — | hunt.constants, hunt.geo, hunt.logging_config, hunt.main +6 |
| `hunt/actions.py` | 61 | `ActionsMixin` | hunt.constants |
| `hunt/backup.py` | 171 | `BackupMixin` | hunt.constants |
| `hunt/blacklist.py` | 54 | `BlacklistMixin` | hunt.constants |
| `hunt/blocklists.py` | 433 | `BlocklistsMixin` | hunt.constants, hunt.domain_parser, hunt.download |
| `hunt/canary.py` | 159 | `CanaryMixin` | hunt.constants |
| `hunt/channel.py` | 210 | `ChannelMixin` | hunt.conn |
| `hunt/check_geo.py` | 157 | `CheckGeoMixin` | hunt.constants |
| `hunt/check_mitm.py` | 168 | `CheckMitmMixin` | hunt.conn, hunt.constants |
| `hunt/check_proxy.py` | 154 | `CheckProxyMixin` | hunt.constants, hunt.geo |
| `hunt/check_rating.py` | 103 | `CheckRatingMixin` | hunt.check_rating_apply, hunt.constants, hunt.geo, hunt.models |
| `hunt/check_rating_apply.py` | 89 | `CheckRatingApplyMixin` | hunt.geo, hunt.models |
| `hunt/check_speed.py` | 209 | `CheckSpeedMixin` | hunt.constants |
| `hunt/check_ssl.py` | 141 | `CheckSslMixin` | hunt.constants |
| `hunt/check_validation.py` | 175 | `CheckValidationMixin` | hunt.check_validation_helpers, hunt.constants |
| `hunt/check_validation_helpers.py` | 87 | `CheckValidationHelpersMixin` | — |
| `hunt/conn.py` | 135 | `socks5_connect`, `socks4_connect`, `http_connect` | — |
| `hunt/constants.py` | 118 | — | — |
| `hunt/custom_proxies.py` | 311 | `CustomProxiesMixin` | hunt.conn, hunt.constants |
| `hunt/db.py` | 422 | `DbMixin` | hunt.db_writer |
| `hunt/db_writer.py` | 94 | — | — |
| `hunt/domain_parser.py` | 58 | `normalize_domain_pattern` | — |
| `hunt/download.py` | 62 | `curl_args`, `stream_download` | — |
| `hunt/events.py` | 35 | `EventsMixin` | — |
| `hunt/favorites.py` | 32 | `FavoritesMixin` | hunt.constants |
| `hunt/fraudscore.py` | 200 | `FraudScoreMixin` | hunt.conn, hunt.constants |
| `hunt/geo.py` | 96 | `country_flag`, `country_code_from_name`, `country_name_from_code` | — |
| `hunt/handlers/__init__.py` | 33 | — | — |
| `hunt/handlers/admin.py` | 180 | `AdminHandlers` | hunt.handlers |
| `hunt/handlers/core.py` | 118 | `CoreHandlers` | hunt.constants, hunt.handlers, hunt.web_legacy |
| `hunt/handlers/hunt.py` | 104 | `HuntHandlers` | hunt.models |
| `hunt/handlers/interception.py` | 219 | `InterceptionHandlers` | hunt.constants |
| `hunt/handlers/pac.py` | 20 | `PacHandlers` | hunt.handlers |
| `hunt/handlers/pool.py` | 49 | `PoolHandlers` | hunt.handlers |
| `hunt/handlers/proxy.py` | 251 | `ProxyHandlers` | hunt.handlers, hunt.handlers.proxy_groups |
| `hunt/handlers/proxy_groups.py` | 112 | `ProxyGroupMixin` | hunt.geo, hunt.handlers |
| `hunt/handlers/routing.py` | 80 | `RoutingHandlers` | hunt.handlers |
| `hunt/handlers/sources.py` | 260 | `SourceHandlers` | hunt.constants, hunt.handlers |
| `hunt/handlers/traffic.py` | 216 | `TrafficHandlers` | hunt.constants, hunt.handlers, hunt.handlers.traffic_common, hunt.handlers.traffic_detail +2 |
| `hunt/handlers/traffic_common.py` | 24 | — | — |
| `hunt/handlers/traffic_detail.py` | 176 | `TrafficDetailMixin` | hunt.constants, hunt.handlers, hunt.handlers.traffic_common |
| `hunt/handlers/traffic_report.py` | 176 | `TrafficReportMixin` | — |
| `hunt/handlers/traffic_summary.py` | 155 | `TrafficSummaryMixin` | hunt.constants, hunt.handlers.traffic_common |
| `hunt/handlers/version.py` | 42 | `VersionHandlers` | hunt.constants |
| `hunt/health_check.py` | 324 | `HealthCheckMixin` | hunt.constants, hunt.models |
| `hunt/health_loops.py` | 62 | `HealthLoopsMixin` | hunt.constants |
| `hunt/hunt_control.py` | 124 | `HuntControlMixin` | hunt.constants, hunt.manual_hunt |
| `hunt/hunt_cycle.py` | 96 | `HuntCycleMixin` | hunt.constants |
| `hunt/ip_blacklist.py` | 229 | `IPBlacklistMixin` | hunt.constants |
| `hunt/ip_blacklist_sources.py` | 291 | `IPBlacklistSourcesMixin` | hunt.constants, hunt.download |
| `hunt/logging_config.py` | 38 | `setup_logging` | — |
| `hunt/main.py` | 116 | `amain`, `main` | hunt.constants, hunt.logging_config, hunt.scheduler, hunt.server +1 |
| `hunt/manual_hunt.py` | 79 | `ManualHuntMixin` | hunt.constants |
| `hunt/models.py` | 391 | `ProxyRating` | — |
| `hunt/pac.py` | 208 | `render_pac`, `PacMixin` | hunt.constants |
| `hunt/proxy_http.py` | 56 | `ProxyHttpMixin` | — |
| `hunt/proxy_ping.py` | 227 | `ProxyPingMixin` | hunt.conn, hunt.constants |
| `hunt/proxy_routing.py` | 213 | `ProxyRouteMixin` | hunt.models |
| `hunt/proxy_runner.py` | 269 | `ProxyRunner` | hunt.conn, hunt.models, hunt.proxy_http, hunt.proxy_routing +1 |
| `hunt/proxy_sources.py` | 415 | `ProxySourcesMixin` | hunt.constants, hunt.download |
| `hunt/router.py` | 53 | `Router` | — |
| `hunt/routing.py` | 302 | `RoutingMixin` | hunt.constants |
| `hunt/schedule_entry.py` | 178 | `ScheduleEntry` | — |
| `hunt/scheduler.py` | 383 | `SchedulerEngine` | hunt.constants, hunt.schedule_entry, hunt.scheduler_api, hunt.scheduler_guard +2 |
| `hunt/scheduler_api.py` | 156 | `SchedulerApiMixin` | hunt.schedule_entry |
| `hunt/scheduler_guard.py` | 114 | `SchedulerGuardMixin` | hunt.schedule_entry |
| `hunt/scheduler_persistence.py` | 104 | `SchedulerPersistenceMixin` | hunt.constants, hunt.schedule_entry |
| `hunt/server.py` | 301 | `HuntServer` | hunt.constants, hunt.handlers, hunt.handlers.admin, hunt.handlers.core +15 |
| `hunt/snapshot.py` | 433 | `SnapshotMixin` | hunt.constants, hunt.models |
| `hunt/socks5_runner.py` | 160 | `Socks5Runner` | hunt.models |
| `hunt/state.py` | 185 | `HuntState` | hunt.actions, hunt.backup, hunt.blacklist, hunt.blocklists +30 |
| `hunt/state_download.py` | 84 | `StateDownloadMixin` | hunt.constants |
| `hunt/state_persistence.py` | 237 | `StatePersistenceMixin` | hunt.constants, hunt.geo, hunt.models, hunt.state_working |
| `hunt/state_working.py` | 101 | `StateWorkingMixin` | hunt.constants, hunt.geo, hunt.models |
| `hunt/switch_history.py` | 75 | `record_switch`, `enrich_switch_history` | hunt.switch_history_stats |
| `hunt/switch_history_stats.py` | 73 | — | — |
| `hunt/task_executor.py` | 264 | `TaskExecutor` | hunt.constants, hunt.schedule_entry |
| `hunt/traffic_stats.py` | 111 | `TrafficStats` | — |
| `hunt/transparent_runner.py` | 176 | `TransparentRunner` | — |
| `hunt/web_legacy.py` | 348 | — | — |

---
## hunt/
### `hunt/__init__.py` (14 строк)
*Functional split of the huntproxy backend.*
**Зависимости:** `hunt.constants`, `hunt.geo`, `hunt.logging_config`, `hunt.main`, `hunt.models`, `hunt.proxy_runner`, `hunt.server`, `hunt.socks5_runner`, `hunt.state`, `hunt.transparent_runner`

### `hunt/actions.py` (61 строк)
*Functional split of the huntproxy backend.*
**Публичные:**
- `ActionsMixin` (class)

**Зависимости:** `hunt.constants`

### `hunt/backup.py` (171 строк)
*Functional split of the huntproxy backend.*
**Публичные:**
- `BackupMixin` (class)

**Зависимости:** `hunt.constants`

### `hunt/blacklist.py` (54 строк)
*Functional split of the huntproxy backend.*
**Публичные:**
- `BlacklistMixin` (class)

**Зависимости:** `hunt.constants`

### `hunt/blocklists.py` (433 строк)
*Country blocklist sources — downloads IP and domain blocklists organized*
**Публичные:**
- `BlocklistsMixin` (class)

**Зависимости:** `hunt.constants`, `hunt.domain_parser`, `hunt.download`

### `hunt/canary.py` (159 строк)
*Functional split of the huntproxy backend.*
**Публичные:**
- `CanaryMixin` (class)

**Зависимости:** `hunt.constants`

### `hunt/channel.py` (210 строк)
*Channel mixin — route the engine's own internet access through an upstream*
**Публичные:**
- `ChannelMixin` (class)

**Зависимости:** `hunt.conn`

### `hunt/check_geo.py` (157 строк)
*Functional split of the huntproxy backend.*
**Публичные:**
- `CheckGeoMixin` (class)

**Зависимости:** `hunt.constants`

### `hunt/check_mitm.py` (168 строк)
*Multi-target MITM detection via certificate verification over tunnels.*
**Публичные:**
- `CheckMitmMixin` (class)

**Зависимости:** `hunt.conn`, `hunt.constants`

### `hunt/check_proxy.py` (154 строк)
*Functional split of the huntproxy backend.*
**Публичные:**
- `CheckProxyMixin` (class)

**Зависимости:** `hunt.constants`, `hunt.geo`

### `hunt/check_rating.py` (103 строк)
*Functional split of the huntproxy backend.*
**Публичные:**
- `CheckRatingMixin` (class)

**Зависимости:** `hunt.check_rating_apply`, `hunt.constants`, `hunt.geo`, `hunt.models`

### `hunt/check_rating_apply.py` (89 строк)
*Rating-result application helpers — extracted from check_rating.py.*
**Публичные:**
- `CheckRatingApplyMixin` (class)

**Зависимости:** `hunt.geo`, `hunt.models`

### `hunt/check_speed.py` (209 строк)
*Functional split of the huntproxy backend.*
**Публичные:**
- `CheckSpeedMixin` (class)

**Зависимости:** `hunt.constants`

### `hunt/check_ssl.py` (141 строк)
*Functional split of the huntproxy backend.*
**Публичные:**
- `CheckSslMixin` (class)

**Зависимости:** `hunt.constants`

### `hunt/check_validation.py` (175 строк)
*Functional split of the huntproxy backend.*
**Публичные:**
- `CheckValidationMixin` (class)

**Зависимости:** `hunt.check_validation_helpers`, `hunt.constants`

### `hunt/check_validation_helpers.py` (87 строк)
*Per-check helpers for the validation pipeline, extracted from check_validation.p*
**Публичные:**
- `CheckValidationHelpersMixin` (class)


### `hunt/conn.py` (135 строк)
*Shared upstream-proxy protocol helpers.*
**Публичные:**
- `socks5_connect` (async)
- `socks4_connect` (async)
- `http_connect` (async)


### `hunt/constants.py` (118 строк)
*Functional split of the huntproxy backend.*

### `hunt/custom_proxies.py` (311 строк)
*Functional split of the huntproxy backend.*
**Публичные:**
- `CustomProxiesMixin` (class)

**Зависимости:** `hunt.conn`, `hunt.constants`

### `hunt/db.py` (422 строк)
*Functional split of the huntproxy backend.*
**Публичные:**
- `DbMixin` (class)

**Зависимости:** `hunt.db_writer`

### `hunt/db_writer.py` (94 строк)
*SQLite connection helpers for hunt — extracted from db.py.*

### `hunt/domain_parser.py` (58 строк)
*Domain blocklist text parsing — normalizes upstream rule formats*
**Публичные:**
- `normalize_domain_pattern` (def)


### `hunt/download.py` (62 строк)
*Shared download helpers — stall-detection streaming reader for curl.*
**Публичные:**
- `curl_args` (def)
- `stream_download` (async)


### `hunt/events.py` (35 строк)
*Functional split of the huntproxy backend.*
**Публичные:**
- `EventsMixin` (class)


### `hunt/favorites.py` (32 строк)
*Functional split of the huntproxy backend.*
**Публичные:**
- `FavoritesMixin` (class)

**Зависимости:** `hunt.constants`

### `hunt/fraudscore.py` (200 строк)
*Full 0-100 fraud/risk score for a proxy's egress IP via proxycheck.io.*
**Публичные:**
- `FraudScoreMixin` (class)

**Зависимости:** `hunt.conn`, `hunt.constants`

### `hunt/geo.py` (96 строк)
*Functional split of the huntproxy backend.*
**Публичные:**
- `country_flag` (def)
- `country_code_from_name` (def)
- `country_name_from_code` (def)


### `hunt/health_check.py` (324 строк)
*Functional split of the huntproxy backend.*
**Публичные:**
- `HealthCheckMixin` (class)

**Зависимости:** `hunt.constants`, `hunt.models`

### `hunt/health_loops.py` (62 строк)
*Functional split of the huntproxy backend.*
**Публичные:**
- `HealthLoopsMixin` (class)

**Зависимости:** `hunt.constants`

### `hunt/hunt_control.py` (124 строк)
*Functional split of the huntproxy backend.*
**Публичные:**
- `HuntControlMixin` (class)

**Зависимости:** `hunt.constants`, `hunt.manual_hunt`

### `hunt/hunt_cycle.py` (96 строк)
*Functional split of the huntproxy backend.*
**Публичные:**
- `HuntCycleMixin` (class)

**Зависимости:** `hunt.constants`

### `hunt/ip_blacklist.py` (229 строк)
*Functional split of the huntproxy backend.*
**Публичные:**
- `IPBlacklistMixin` (class)

**Зависимости:** `hunt.constants`

### `hunt/ip_blacklist_sources.py` (291 строк)
*Functional split of the huntproxy backend.*
**Публичные:**
- `IPBlacklistSourcesMixin` (class)

**Зависимости:** `hunt.constants`, `hunt.download`

### `hunt/logging_config.py` (38 строк)
*Functional split of the huntproxy backend.*
**Публичные:**
- `setup_logging` (def)


### `hunt/main.py` (116 строк)
*Functional split of the huntproxy backend.*
**Публичные:**
- `amain` (async)
- `main` (def)

**Зависимости:** `hunt.constants`, `hunt.logging_config`, `hunt.scheduler`, `hunt.server`, `hunt.state`

### `hunt/manual_hunt.py` (79 строк)
*Manual (operator-driven) Hunt start — strict interrupt-and-restart.*
**Публичные:**
- `ManualHuntMixin` (class)

**Зависимости:** `hunt.constants`

### `hunt/models.py` (391 строк)
*Functional split of the huntproxy backend.*
**Публичные:**
- `ProxyRating` (class)


### `hunt/pac.py` (208 строк)
*Functional split of the huntproxy backend.*
**Публичные:**
- `render_pac` (def)
- `PacMixin` (class)

**Зависимости:** `hunt.constants`

### `hunt/proxy_http.py` (56 строк)
*HTTP request/response parsing helpers for the proxy runner.*
**Публичные:**
- `ProxyHttpMixin` (class)


### `hunt/proxy_ping.py` (227 строк)
*Continuous proxy ping — measures latency through the currently active*
**Публичные:**
- `ProxyPingMixin` (class)

**Зависимости:** `hunt.conn`, `hunt.constants`

### `hunt/proxy_routing.py` (213 строк)
*Proxy route selection — extracted from proxy_runner.py.*
**Публичные:**
- `ProxyRouteMixin` (class)

**Зависимости:** `hunt.models`

### `hunt/proxy_runner.py` (269 строк)
*Functional split of the huntproxy backend.*
**Публичные:**
- `ProxyRunner` (class)

**Зависимости:** `hunt.conn`, `hunt.models`, `hunt.proxy_http`, `hunt.proxy_routing`, `hunt.switch_history`

### `hunt/proxy_sources.py` (415 строк)
*Functional split of the huntproxy backend.*
**Публичные:**
- `ProxySourcesMixin` (class)

**Зависимости:** `hunt.constants`, `hunt.download`

### `hunt/router.py` (53 строк)
*HTTP route registry — replaces the monolithic if/elif dispatch in HuntServer.*
**Публичные:**
- `Router` (class)


### `hunt/routing.py` (302 строк)
*Functional split of the huntproxy backend.*
**Публичные:**
- `RoutingMixin` (class)

**Зависимости:** `hunt.constants`

### `hunt/schedule_entry.py` (178 строк)
*Schedule entry dataclass, task types, and default schedules — extracted from sch*
**Публичные:**
- `ScheduleEntry` (class)


### `hunt/scheduler.py` (383 строк)
*Unified asyncio scheduler for periodic maintenance tasks.*
**Публичные:**
- `SchedulerEngine` (class)

**Зависимости:** `hunt.constants`, `hunt.schedule_entry`, `hunt.scheduler_api`, `hunt.scheduler_guard`, `hunt.scheduler_persistence`, `hunt.task_executor`

### `hunt/scheduler_api.py` (156 строк)
*Scheduler API methods — extracted from scheduler.py.*
**Публичные:**
- `SchedulerApiMixin` (class)

**Зависимости:** `hunt.schedule_entry`

### `hunt/scheduler_guard.py` (114 строк)
*Bulk task cancellation and the scheduler internet gate.*
**Публичные:**
- `SchedulerGuardMixin` (class)

**Зависимости:** `hunt.schedule_entry`

### `hunt/scheduler_persistence.py` (104 строк)
*Scheduler persistence methods — extracted from scheduler.py.*
**Публичные:**
- `SchedulerPersistenceMixin` (class)

**Зависимости:** `hunt.constants`, `hunt.schedule_entry`

### `hunt/server.py` (301 строк)
*Functional split of the huntproxy backend.*
**Публичные:**
- `HuntServer` (class)

**Зависимости:** `hunt.constants`, `hunt.handlers`, `hunt.handlers.admin`, `hunt.handlers.core`, `hunt.handlers.hunt`, `hunt.handlers.interception`, `hunt.handlers.pac`, `hunt.handlers.pool`, `hunt.handlers.proxy`, `hunt.handlers.routing`, `hunt.handlers.sources`, `hunt.handlers.traffic`, `hunt.handlers.version`, `hunt.proxy_runner`, `hunt.router`, `hunt.socks5_runner`, `hunt.state`, `hunt.transparent_runner`, `hunt.web_legacy`

### `hunt/snapshot.py` (433 строк)
*Functional split of the huntproxy backend.*
**Публичные:**
- `SnapshotMixin` (class)

**Зависимости:** `hunt.constants`, `hunt.models`

### `hunt/socks5_runner.py` (160 строк)
*Functional split of the huntproxy backend.*
**Публичные:**
- `Socks5Runner` (class)

**Зависимости:** `hunt.models`

### `hunt/state.py` (185 строк)
*Functional split of the huntproxy backend.*
**Публичные:**
- `HuntState` (class)

**Зависимости:** `hunt.actions`, `hunt.backup`, `hunt.blacklist`, `hunt.blocklists`, `hunt.canary`, `hunt.channel`, `hunt.check_geo`, `hunt.check_mitm`, `hunt.check_proxy`, `hunt.check_rating`, `hunt.check_speed`, `hunt.check_ssl`, `hunt.check_validation`, `hunt.constants`, `hunt.custom_proxies`, `hunt.db`, `hunt.events`, `hunt.favorites`, `hunt.fraudscore`, `hunt.health_check`, `hunt.health_loops`, `hunt.hunt_control`, `hunt.hunt_cycle`, `hunt.ip_blacklist`, `hunt.ip_blacklist_sources`, `hunt.models`, `hunt.pac`, `hunt.proxy_ping`, `hunt.proxy_sources`, `hunt.routing`, `hunt.snapshot`, `hunt.state_download`, `hunt.state_persistence`, `hunt.traffic_stats`

### `hunt/state_download.py` (84 строк)
*State download/export methods — extracted from state.py.*
**Публичные:**
- `StateDownloadMixin` (class)

**Зависимости:** `hunt.constants`

### `hunt/state_persistence.py` (237 строк)
*State persistence methods — extracted from state.py.*
**Публичные:**
- `StatePersistenceMixin` (class)

**Зависимости:** `hunt.constants`, `hunt.geo`, `hunt.models`, `hunt.state_working`

### `hunt/state_working.py` (101 строк)
*Working-set persistence — extracted from state_persistence.py.*
**Публичные:**
- `StateWorkingMixin` (class)

**Зависимости:** `hunt.constants`, `hunt.geo`, `hunt.models`

### `hunt/switch_history.py` (75 строк)
*Proxy switch history enrichment — extracted from proxy_runner.py.*
**Публичные:**
- `record_switch` (def)
- `enrich_switch_history` (def)

**Зависимости:** `hunt.switch_history_stats`

### `hunt/switch_history_stats.py` (73 строк)
*Traffic/duration aggregation for proxy switch history.*

### `hunt/task_executor.py` (264 строк)
*Task executor — runs scheduled tasks, decoupled from the scheduler's*
**Публичные:**
- `TaskExecutor` (class)

**Зависимости:** `hunt.constants`, `hunt.schedule_entry`

### `hunt/traffic_stats.py` (111 строк)
*In-memory hourly rollup of proxied traffic.*
**Публичные:**
- `TrafficStats` (class)


### `hunt/transparent_runner.py` (176 строк)
*Transparent proxy runner.*
**Публичные:**
- `TransparentRunner` (class)


### `hunt/web_legacy.py` (348 строк)
*Legacy inline HTML fallback served when ``web/index.html`` is absent.*

## hunt/handlers/
### `hunt/handlers/__init__.py` (33 строк)
*HTTP handler domain modules — split from the former HuntServer monolith.*

### `hunt/handlers/admin.py` (180 строк)
*Admin handlers — schedules, backup/restore, canary, channel, country filter.*
**Публичные:**
- `AdminHandlers` (class)

**Зависимости:** `hunt.handlers`

### `hunt/handlers/core.py` (118 строк)
*Core handlers — static assets, pages, snapshot/events, dashboard, settings.*
**Публичные:**
- `CoreHandlers` (class)

**Зависимости:** `hunt.constants`, `hunt.handlers`, `hunt.web_legacy`

### `hunt/handlers/hunt.py` (104 строк)
*Hunt control handlers — start/stop/pause/resume/skip, health, clear/export/impor*
**Публичные:**
- `HuntHandlers` (class)

**Зависимости:** `hunt.models`

### `hunt/handlers/interception.py` (219 строк)
*Interception handlers — whole-machine transparent redirect control.*
**Публичные:**
- `InterceptionHandlers` (class)

**Зависимости:** `hunt.constants`

### `hunt/handlers/pac.py` (20 строк)
*Functional split of the huntproxy backend.*
**Публичные:**
- `PacHandlers` (class)

**Зависимости:** `hunt.handlers`

### `hunt/handlers/pool.py` (49 строк)
*Pool handlers — manual blacklist and favorites management.*
**Публичные:**
- `PoolHandlers` (class)

**Зависимости:** `hunt.handlers`

### `hunt/handlers/proxy.py` (251 строк)
*Proxy handlers — proxy/socks5/transparent runner control, selection, detail view*
**Публичные:**
- `ProxyHandlers` (class)

**Зависимости:** `hunt.handlers`, `hunt.handlers.proxy_groups`

### `hunt/handlers/proxy_groups.py` (112 строк)
*Proxy list/grouping handlers — extracted from handlers/proxy.py.*
**Публичные:**
- `ProxyGroupMixin` (class)

**Зависимости:** `hunt.geo`, `hunt.handlers`

### `hunt/handlers/routing.py` (80 строк)
*Routing handlers — routing status/enable/disable/default/reorder/test, domain-li*
**Публичные:**
- `RoutingHandlers` (class)

**Зависимости:** `hunt.handlers`

### `hunt/handlers/sources.py` (260 строк)
*Source handlers — proxy-sources, ip-blacklists, blocklists, custom-proxies CRUD.*
**Публичные:**
- `SourceHandlers` (class)

**Зависимости:** `hunt.constants`, `hunt.handlers`

### `hunt/handlers/traffic.py` (216 строк)
*Traffic handlers — live traffic, requests/clients, full-text search.*
**Публичные:**
- `TrafficHandlers` (class)

**Зависимости:** `hunt.constants`, `hunt.handlers`, `hunt.handlers.traffic_common`, `hunt.handlers.traffic_detail`, `hunt.handlers.traffic_report`, `hunt.handlers.traffic_summary`

### `hunt/handlers/traffic_common.py` (24 строк)
*Shared constants and helpers for the split traffic handlers.*

### `hunt/handlers/traffic_detail.py` (176 строк)
*Per-client traffic detail handlers — extracted from handlers/traffic.py.*
**Публичные:**
- `TrafficDetailMixin` (class)

**Зависимости:** `hunt.constants`, `hunt.handlers`, `hunt.handlers.traffic_common`

### `hunt/handlers/traffic_report.py` (176 строк)
*Traffic report handlers (domains/errors/routes/bandwidth) — split from traffic.p*
**Публичные:**
- `TrafficReportMixin` (class)


### `hunt/handlers/traffic_summary.py` (155 строк)
*Dashboard traffic summary — extracted from handlers/traffic.py.*
**Публичные:**
- `TrafficSummaryMixin` (class)

**Зависимости:** `hunt.constants`, `hunt.handlers.traffic_common`

### `hunt/handlers/version.py` (42 строк)
*Version handler — expose the deployed git commit as a clickable build tag.*
**Публичные:**
- `VersionHandlers` (class)

**Зависимости:** `hunt.constants`

---
## Связанность (кто импортирует кого)
| Модуль | Импортирует |
|--------|-------------|
| `hunt/__init__.py` | `hunt.constants`, `hunt.geo`, `hunt.logging_config`, `hunt.main`, `hunt.models`, `hunt.proxy_runner`, `hunt.server`, `hunt.socks5_runner`, `hunt.state`, `hunt.transparent_runner` |
| `hunt/actions.py` | `hunt.constants` |
| `hunt/backup.py` | `hunt.constants` |
| `hunt/blacklist.py` | `hunt.constants` |
| `hunt/blocklists.py` | `hunt.constants`, `hunt.domain_parser`, `hunt.download` |
| `hunt/canary.py` | `hunt.constants` |
| `hunt/channel.py` | `hunt.conn` |
| `hunt/check_geo.py` | `hunt.constants` |
| `hunt/check_mitm.py` | `hunt.conn`, `hunt.constants` |
| `hunt/check_proxy.py` | `hunt.constants`, `hunt.geo` |
| `hunt/check_rating.py` | `hunt.check_rating_apply`, `hunt.constants`, `hunt.geo`, `hunt.models` |
| `hunt/check_rating_apply.py` | `hunt.geo`, `hunt.models` |
| `hunt/check_speed.py` | `hunt.constants` |
| `hunt/check_ssl.py` | `hunt.constants` |
| `hunt/check_validation.py` | `hunt.check_validation_helpers`, `hunt.constants` |
| `hunt/custom_proxies.py` | `hunt.conn`, `hunt.constants` |
| `hunt/db.py` | `hunt.db_writer` |
| `hunt/favorites.py` | `hunt.constants` |
| `hunt/fraudscore.py` | `hunt.conn`, `hunt.constants` |
| `hunt/handlers/admin.py` | `hunt.handlers` |
| `hunt/handlers/core.py` | `hunt.constants`, `hunt.handlers`, `hunt.web_legacy` |
| `hunt/handlers/hunt.py` | `hunt.models` |
| `hunt/handlers/interception.py` | `hunt.constants` |
| `hunt/handlers/pac.py` | `hunt.handlers` |
| `hunt/handlers/pool.py` | `hunt.handlers` |
| `hunt/handlers/proxy.py` | `hunt.handlers`, `hunt.handlers.proxy_groups` |
| `hunt/handlers/proxy_groups.py` | `hunt.geo`, `hunt.handlers` |
| `hunt/handlers/routing.py` | `hunt.handlers` |
| `hunt/handlers/sources.py` | `hunt.constants`, `hunt.handlers` |
| `hunt/handlers/traffic.py` | `hunt.constants`, `hunt.handlers`, `hunt.handlers.traffic_common`, `hunt.handlers.traffic_detail`, `hunt.handlers.traffic_report`, `hunt.handlers.traffic_summary` |
| `hunt/handlers/traffic_detail.py` | `hunt.constants`, `hunt.handlers`, `hunt.handlers.traffic_common` |
| `hunt/handlers/traffic_summary.py` | `hunt.constants`, `hunt.handlers.traffic_common` |
| `hunt/handlers/version.py` | `hunt.constants` |
| `hunt/health_check.py` | `hunt.constants`, `hunt.models` |
| `hunt/health_loops.py` | `hunt.constants` |
| `hunt/hunt_control.py` | `hunt.constants`, `hunt.manual_hunt` |
| `hunt/hunt_cycle.py` | `hunt.constants` |
| `hunt/ip_blacklist.py` | `hunt.constants` |
| `hunt/ip_blacklist_sources.py` | `hunt.constants`, `hunt.download` |
| `hunt/main.py` | `hunt.constants`, `hunt.logging_config`, `hunt.scheduler`, `hunt.server`, `hunt.state` |
| `hunt/manual_hunt.py` | `hunt.constants` |
| `hunt/pac.py` | `hunt.constants` |
| `hunt/proxy_ping.py` | `hunt.conn`, `hunt.constants` |
| `hunt/proxy_routing.py` | `hunt.models` |
| `hunt/proxy_runner.py` | `hunt.conn`, `hunt.models`, `hunt.proxy_http`, `hunt.proxy_routing`, `hunt.switch_history` |
| `hunt/proxy_sources.py` | `hunt.constants`, `hunt.download` |
| `hunt/routing.py` | `hunt.constants` |
| `hunt/scheduler.py` | `hunt.constants`, `hunt.schedule_entry`, `hunt.scheduler_api`, `hunt.scheduler_guard`, `hunt.scheduler_persistence`, `hunt.task_executor` |
| `hunt/scheduler_api.py` | `hunt.schedule_entry` |
| `hunt/scheduler_guard.py` | `hunt.schedule_entry` |
| `hunt/scheduler_persistence.py` | `hunt.constants`, `hunt.schedule_entry` |
| `hunt/server.py` | `hunt.constants`, `hunt.handlers`, `hunt.handlers.admin`, `hunt.handlers.core`, `hunt.handlers.hunt`, `hunt.handlers.interception`, `hunt.handlers.pac`, `hunt.handlers.pool`, `hunt.handlers.proxy`, `hunt.handlers.routing`, `hunt.handlers.sources`, `hunt.handlers.traffic`, `hunt.handlers.version`, `hunt.proxy_runner`, `hunt.router`, `hunt.socks5_runner`, `hunt.state`, `hunt.transparent_runner`, `hunt.web_legacy` |
| `hunt/snapshot.py` | `hunt.constants`, `hunt.models` |
| `hunt/socks5_runner.py` | `hunt.models` |
| `hunt/state.py` | `hunt.actions`, `hunt.backup`, `hunt.blacklist`, `hunt.blocklists`, `hunt.canary`, `hunt.channel`, `hunt.check_geo`, `hunt.check_mitm`, `hunt.check_proxy`, `hunt.check_rating`, `hunt.check_speed`, `hunt.check_ssl`, `hunt.check_validation`, `hunt.constants`, `hunt.custom_proxies`, `hunt.db`, `hunt.events`, `hunt.favorites`, `hunt.fraudscore`, `hunt.health_check`, `hunt.health_loops`, `hunt.hunt_control`, `hunt.hunt_cycle`, `hunt.ip_blacklist`, `hunt.ip_blacklist_sources`, `hunt.models`, `hunt.pac`, `hunt.proxy_ping`, `hunt.proxy_sources`, `hunt.routing`, `hunt.snapshot`, `hunt.state_download`, `hunt.state_persistence`, `hunt.traffic_stats` |
| `hunt/state_download.py` | `hunt.constants` |
| `hunt/state_persistence.py` | `hunt.constants`, `hunt.geo`, `hunt.models`, `hunt.state_working` |
| `hunt/state_working.py` | `hunt.constants`, `hunt.geo`, `hunt.models` |
| `hunt/switch_history.py` | `hunt.switch_history_stats` |
| `hunt/task_executor.py` | `hunt.constants`, `hunt.schedule_entry` |

