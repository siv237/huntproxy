---
updated: 2026-09-18
commit: 8b0c0c0
tags: [entity]
---

# Планировщик задач

Единый движок фоновых задач заменил разрозненные циклы (`docs/SCHEDULER_PLAN.md`).
Реализация: `hunt/scheduler.py`, `hunt/scheduler_api.py`,
`hunt/scheduler_persistence.py`, `hunt/scheduler_guard.py`,
`hunt/schedule_entry.py`, `hunt/task_executor.py`.

## Устройство

`SchedulerEngine(SchedulerPersistenceMixin, SchedulerApiMixin, SchedulerGuardMixin)`
(`hunt/scheduler.py:21`):
- `_running_tasks: dict[task_type, Task]` — по одному экземпляру типа задачи;
- `_queue: dict[sid, queued_at]`, `_paused`, `_stopped`, `_lock`, `_schedules`;
- `_launch_lock` — атомарность решения о запуске (см. ниже);
- `_paused_by_internet` — пауза, выставленная интернет-гейтом;
- `executor = TaskExecutor(state)`;
- тик `_TICK_INTERVAL=5` секунд (`:18`).

> **_launch_lock (2026-09-18, незакоммичено):** проверка «task_type уже
> запущен» и регистрация в `_running_tasks` выполняются под `_launch_lock`.
> Раньше между ними был `await is_internet_alive()`, поэтому два
> одновременных `_drain_queue` (тик + `finally` завершившейся задачи)
> запускали одну задачу дважды. Два параллельных `proxy_check` по одному пулу
> писали в общий `checked`/`checking_total` → 200% (доказано по
> `stats.db.actions/events`: запуски `proxy_check` в 08:08:09 и 08:08:10,
> `checked`=162336 при `checking_total`=81351).

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
| `health_check` | ре-валидация живых | proxy_check | нет | да | `_hunt_running` |
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

## Отмена всех задач и интернет-гейт (`hunt/scheduler_guard.py`, незакоммичено)

- `cancel_all(reason)` — отменяет все `_running_tasks`, чистит `_queue`,
  помечает расписания `cancelled`. Возвращает список типов.
- `_cancel_check_tasks()` — отменяет только задачи с `respect_internet`.
- `_internet_gate()` вызывается каждый тик `_run_loop` перед проверкой
  `_paused`. Если canary сообщает «интернета нет» — планировщик встаёт на
  паузу (`_paused_by_internet=True`) и отменяет запущенные проверки; при
  восстановлении связи автоматически возобновляется. Ручную паузу не трогает.
  Это исключает накопление ошибок, когда сервер сутки стоит без сети.
- `_is_busy_flag_stale`/`_check_busy_flag` перенесены сюда из `scheduler.py`
  (лимит 500 строк).

## Ручной Hunt (exclusive, `hunt/manual_hunt.py`, незакоммичено)

`hunt/handlers/hunt.py::_handle_hunt_start` (`POST /api/hunt/start`) вызывает
`HuntState.manual_start_hunt()` (`hunt/manual_hunt.py`), а не `start_hunt()`:

- отказывает, если нет интернета;
- отменяет ручной/шедулерный health-check и ждёт его завершения;
- отменяет предыдущий Hunt и ждёт его `finally`;
- `scheduler.pause_all()` + `scheduler.cancel_all()` — планировщик встаёт на
  паузу на всё время ручного Hunt;
- `_reset_progress()` обнуляет `checked`/`checking_total`/`working`/`failed`/
  `downloaded`/`bl_*` и `_active_checks`;
- `start_hunt()`; по завершении `_hunt_cycle` вызывает `_end_manual_hunt()`,
  который возобновляет планировщик.

Кнопка «Старт Hunt» на фронте (`web/js/pages/hunt.js:114,154`) уже бьёт в этот
эндпоинт — изменения только на бэкенде.

## Замечание

`SchedulerPersistenceMixin` содержит те же методы, что `SchedulerEngine`
определяет в собственном теле, поэтому методы миксина затенены (фактически
мёртвый код). Тест `tests/test_scheduler.py:15-23` следит за отсутствием дублей
внутри класса.
