---
updated: 2026-09-17
commit: b028d67
tags: [entity]
---

# Планировщик задач

Единый движок фоновых задач заменил разрозненные циклы (`docs/SCHEDULER_PLAN.md`).
Реализация: `hunt/scheduler.py`, `hunt/scheduler_api.py`,
`hunt/scheduler_persistence.py`, `hunt/schedule_entry.py`,
`hunt/task_executor.py`.

## Устройство

`SchedulerEngine(SchedulerPersistenceMixin, SchedulerApiMixin)` (`hunt/scheduler.py:21`):
- `_running_tasks: dict[task_type, Task]` — по одному экземпляру типа задачи;
- `_queue: dict[sid, queued_at]`, `_paused`, `_stopped`, `_lock`, `_schedules`;
- `executor = TaskExecutor(state)`;
- тик `_TICK_INTERVAL=5` секунд (`:18`).

`start()` = `prepare()` + `start_loop()` (`:39-42`); `prepare()` грузит
расписания, сидит дефолты, `restore_defaults()` (`:44-55`).

`_run_loop` (`:190-218`): каждые 5с проходит enabled-расписания и ставит в
очередь due (`entry.is_due(now)`), затем `_drain_queue`.

**Триггер по `last_ok`**: due, когда `now - last_ok >= interval_sec`
(`schedule_entry.py:180-187`). То есть отсчёт от времени успешного завершения, а
не запуска. Коммит `49a9d00` («scheduler запускает задачи по last_ok»).

Ограничения запуска в `_try_launch` (`:274-343`): mutex `mutex_with`, busy-флаг
(с детектом staleness), `respect_pause`, `respect_internet` (через canary).
`_run_with_tracking` (`:353-391`) записывает `last_status/last_error/last_ok/
last_duration_s`.

`trigger_now(sid)` (`:407-469`) — ручной «Run Now», обходит очередь/due/busy, но
чтит mutex. `cancel_running(sid)` (`:471-492`).

## Типы задач (`hunt/schedule_entry.py:6-65`)

| task_type | Описание | mutex_with | respect_pause | respect_internet | busy_flag |
|---|---|---|---|---|---|
| `proxy_check` | ре-валидация всех прокси без сбора | health_check | нет | да | `_hunt_running` |
| `source_refresh` | скачать источники, поставить новые в очередь | — | нет | да | `_hunt_running` |
| `ip_blacklist` | скачать IP-ЧС | — | нет | да | `_fetching_ip_blacklists` |
| `blocklist` | скачать страновые блоклисты | — | нет | да | `_fetching_blocklists` |
| `health_check` | ре-валидация живых | proxy_check | нет | да | — |
| `history` | снапшот истории + retention | — | нет | нет | — |
| `clear_dead` | удалить мёртвых | proxy_check, health_check | нет | нет | — |
| `backup` | бэкап БД | — | нет | нет | — |
| `db_maintenance` | WAL checkpoint + retention + vacuum | — | нет | нет | — |

## Дефолтные расписания (`hunt/schedule_entry.py:68-125`)

| id | task_type | interval_sec |
|---|---|---|
| `history` | history | 60 |
| `ip_blacklist_refresh` | ip_blacklist | 3600 |
| `blocklist_refresh` | blocklist | 3600 |
| `health_check` | health_check | 180 |
| `proxy_check` | proxy_check | 1800 |
| `source_refresh` | source_refresh | 3600 |
| `db_maintenance` | db_maintenance | 3600 |

`backup` и `clear_dead` в дефолтах отсутствуют.

## ScheduleEntry (`hunt/schedule_entry.py:128-178`)

Поля: `last_run` (старт), `last_ok` (успешное завершение), `next_run`
(косметическая подсказка UI), `last_status` (`ok|failed|running|queued|skipped|never`),
`last_duration_s`, `last_error`. `to_dict`/`from_row` — `:143-178`.

## TaskExecutor (`hunt/task_executor.py`)

Реестр `_executors: {task_type: async fn}` (`:29-51`), регистрация дефолтов
(`:55-64`). Реализации:

- `_execute_proxy_check` (`:72-98`) — ре-валидация всех не-ЧС, новейшие первыми.
- `_execute_source_refresh` (`:101-123`) — новые адреса как untested в `ratings`.
- `_execute_ip_blacklist` / `_execute_blocklist` (`:126-143`).
- `_execute_health_check` (`:146-150`) — `state._health_check(manual=False)`.
- `_execute_history` (`:153-177`) — `_push_history` + чистка `traffic_log`
  (7 дней, hard cap 2M), `events`/`actions` (30 дней).
- `_execute_clear_dead` (`:180-191`).
- `_execute_backup` (`:194-209`) — JSON в `data/backups/backup_<ts>.json`.
- `_execute_db_maintenance` (`:212-269`) — retention `proxy_checks`/
  `canary_history`, checkpoint+vacuum через `_maintain_db` (`:272-318`).

`_maintain_db`: `wal_checkpoint(TRUNCATE)`, `VACUUM` при freelist-ratio ≥ порога
и `now-last_vacuum >= vacuum_hours*3600`, маркеры в `state.db`.
Коммит `680b249`.

## API (`hunt/scheduler_api.py`)

`list_schedules` (live countdown), `get_schedule`, `add_schedule` (валидация,
ValueError при дубле), `update_schedule`, `delete_schedule`, `toggle_schedule`,
`pause_all`/`resume_all`/`is_paused`, `get_running_task_types`, `get_status`,
`get_log` (`:6-175`).

HTTP: `/api/schedules` CRUD, `/toggle`, `/run`, `/stop`, `/status`, `/log`,
`/pause`, `/resume`, `/restore-defaults` (`hunt/handlers/admin.py:72-192`).

## Замечание

`SchedulerPersistenceMixin` содержит те же методы, что `SchedulerEngine`
определяет в собственном теле, поэтому методы миксина затенены (фактически
мёртвый код). Тест `tests/test_scheduler.py:15-23` следит за отсутствием дублей
внутри класса.
