# План: Единый планировщик задач (Scheduler)

## Часть 1. Концепция простыми словами

### Проблема

Сейчас в системе несколько фоновых задач, которые работают «сами по себе»:

- Каждые 60 секунд записывается история и чистятся старые данные.
- Каждый час скачиваются списки заблокированных IP-адресов.
- Каждый час скачиваются списки блокировок по странам (причём интервал общий с IP-списками — нельзя настроить раздельно).
- Каждые 3 минуты перепроверяются «живые» прокси — но только после ручного запуска охоты.
- Полный цикл охоты (скачать → проверить заблокированные → валидировать прокси) запускается только вручную кнопкой.

У каждой задачи — свой собственный кусок кода, который спит нужное количество секунд и потом что-то делает. Интервалы захардкожены или лежат в конфиг-файле, который требует перезапуска приложения для применения изменений. В интерфейсе нет страницы, где можно посмотреть, что и когда запускалось, и изменить расписание без перезапуска.

**Кратко:** фоновые задачи есть, но они разбросаны по коду, интервалы нельзя менять на лету, и нет единого места управления.

### Решение

Создать **единый планировщик** — один модуль, который:

1. **Хранит все расписания в базе данных** — не в коде и не в конфиг-файле. Можно редактировать через интерфейс, изменения применяются сразу без перезапуска.

2. **Запускает задачи по расписанию** — один главный цикл проверяет «пора ли?» для каждого расписания и запускает нужную задачу.

3. **Защищает от конфликтов** — если задача уже выполняется, повторный запуск пропускается. Если идёт охота — цикл охоты не запускается поверх.

4. **Ведёт журнал** — для каждого расписания видно: когда запускалось в последний раз, когда запустится в следующий раз, сколько длилось, успешно или с ошибкой.

5. **Позволяет запустить задачу вручную** — кнопка «Выполнить сейчас» запускает задачу вне расписания.

### Что получит пользователь

В интерфейсе появится новая страница **«Расписания»** (в разделе «Система», рядом с Настройками). На ней:

- **Таблица всех задач** с интервалами, статусами, временем последнего и следующего запуска.
- **Переключатели вкл/выкл** для каждой задачи прямо в таблице.
- **Редактирование интервала** — задаётся числом и единицей (минуты / часы / дни).
- **Кнопка «Запустить сейчас»** для каждой задачи.
- **Создание новых расписаний** и удаление существующих.
- **Пауза всего планировщика** — если нужно временно остановить все фоновые задачи.

### Какие задачи можно будет планировать

| Задача | Что делает | Сейчас | После внедрения |
|---|---|---|---|
| Цикл охоты | Скачать списки → проверить блэклисты → валидировать прокси | Только вручную | По расписанию или вручную |
| Обновление IP-блэклистов | Скачать списки заблокированных IP | Каждый час, hardcoded | Настраиваемый интервал |
| Обновление country-блоклистов | Скачать списки блокировок по странам | Каждый час (общий с IP) | Независимый интервал |
| Перепроверка прокси | Перепроверить живые прокси | Каждые 3 мин, после охоты | Настраиваемый, всегда работает |
| Запись истории | Сохранить снимок состояния + удалить старые данные | Каждую минуту, hardcoded | Настраиваемый интервал |
| Очистка мёртвых | Удалить прокси, которые давно не отвечают | Только вручную | По расписанию или вручную |
| Резервная копия | Сохранить бэкап базы данных | Нет | По расписанию или вручную |

### Что не меняется

- Canary-цикл (проверка доступности интернета каждые 15 секунд) остаётся как есть — он привязан к циклу охоты и не является независимой задачей.
- Ручной запуск охоты, пауза, resume, skip — работают как прежде.
- Существующее поведение при первом запуске после обновления **не изменится** — дефолтные расписания посеются с текущими hardcoded-интервалами (60с, 3600с, 180с).

---

## Часть 2. Технические детали реализации

### 2.1. Архитектура

```
                    ┌─────────────────────────────────┐
                    │       SchedulerEngine            │
                    │       (hunt/scheduler.py)        │
                    │                                  │
                    │  run()  ── главный asyncio-цикл   │
                    │  ├── проверяет schedules из DB   │
                    │  ├── для due-задач → _run_task()  │
                    │  └── mutex per task_type          │
                    │                                  │
                    │  CRUD: add/update/delete/toggle  │
                    │  trigger_now(id)                 │
                    │  pause() / resume()              │
                    └──────────┬───────────────────────┘
                               │ вызывает
                    ┌──────────▼───────────────────────┐
                    │  Task executors (обёртки)         │
                    │  ├── hunt_cycle → start_hunt()    │
                    │  ├── ip_blacklist → _download_*   │
                    │  ├── blocklist → _download_*      │
                    │  ├── health_check → _health_*     │
                    │  ├── history → _push_history()    │
                    │  ├── clear_dead → _clear_dead()   │
                    │  └── backup → _create_backup()    │
                    └──────────────────────────────────┘
```

### 2.2. Модель данных

#### Таблица `schedules` (новая, в `state.db`)

```sql
CREATE TABLE IF NOT EXISTS schedules (
  id              TEXT PRIMARY KEY,        -- 'hunt_cycle', 'ip_blacklist_refresh', ...
  name            TEXT NOT NULL,           -- человекочитаемое название
  task_type       TEXT NOT NULL,           -- enum (см. 2.3)
  enabled         INTEGER DEFAULT 1,       -- 0/1
  interval_sec    INTEGER NOT NULL,        -- секунды между запусками
  config          TEXT DEFAULT '{}',       -- JSON: доп. параметры
  last_run        REAL DEFAULT 0,          -- Unix timestamp последнего запуска
  next_run        REAL DEFAULT 0,          -- Unix timestamp следующего запуска
  last_status     TEXT DEFAULT 'never',    -- 'ok'|'failed'|'running'|'skipped'|'never'
  last_duration_s REAL DEFAULT 0,          -- длительность последнего запуска
  last_error      TEXT DEFAULT ''          -- текст ошибки (если failed)
);
```

Хранится в `state.db`, инициализируется в `db.py:_init_state_db` (`db.py:185-318`).

#### Seed дефолтных расписаний

При первом запуске (таблица пуста) — посеять 5 стандартных расписаний:

| id | task_type | interval_sec | Соответствует сейчас |
|---|---|---|---|
| `history` | `history` | 60 | `health.py:437` _history_loop |
| `ip_blacklist_refresh` | `ip_blacklist` | 3600 | `health.py:261` _ip_blacklist_loop |
| `blocklist_refresh` | `blocklist` | 3600 | `blocklists.py:408` _blocklist_loop |
| `health_check` | `health_check` | 180 | `health.py:244` _health_loop |
| `hunt_cycle` | `hunt_cycle` | 0 (disabled) | ручной запуск, не было авто |

`clear_dead` и `backup` — не сеются по умолчанию (disabled), пользователь создаёт при необходимости.

### 2.3. Типы задач (task_type)

```python
TASK_TYPES = {
    "hunt_cycle": {
        "description": "Full download → blacklist → validate cycle",
        "executor": "_execute_hunt_cycle",
        "mutex_with": ["health_check"],   # не запускать одновременно с health
        "respect_pause": True,            # уважает hunt pause
        "respect_internet": True,         # проверяет is_internet_alive()
    },
    "ip_blacklist": {
        "description": "Download IP blacklist sources",
        "executor": "_execute_ip_blacklist",
        "mutex_with": [],
        "respect_pause": False,
        "respect_internet": True,
    },
    "blocklist": {
        "description": "Download country blocklists",
        "executor": "_execute_blocklist",
        "mutex_with": [],
        "respect_pause": False,
        "respect_internet": True,
    },
    "health_check": {
        "description": "Re-validate alive proxies",
        "executor": "_execute_health_check",
        "mutex_with": ["hunt_cycle"],
        "respect_pause": False,           # health-check работает независимо от hunt pause
        "respect_internet": True,
    },
    "history": {
        "description": "Record history snapshot + retention cleanup",
        "executor": "_execute_history",
        "mutex_with": [],
        "respect_pause": False,
        "respect_internet": False,        # история пишется всегда
    },
    "clear_dead": {
        "description": "Remove dead proxies from pool",
        "executor": "_execute_clear_dead",
        "mutex_with": ["hunt_cycle", "health_check"],
        "respect_pause": False,
        "respect_internet": False,
    },
    "backup": {
        "description": "Create database backup",
        "executor": "_execute_backup",
        "mutex_with": [],
        "respect_pause": False,
        "respect_internet": False,
    },
}
```

### 2.4. SchedulerEngine — класс

Файл: `hunt/scheduler.py`

```python
class SchedulerEngine:
    """Unified asyncio scheduler for periodic maintenance tasks."""

    def __init__(self, state: HuntState):
        self.state = state
        self._task: asyncio.Task | None = None    # главный цикл
        self._running_tasks: dict[str, asyncio.Task] = {}  # task_type → running task
        self._paused: bool = False
        self._lock = asyncio.Lock()               # защита CRUD-операций
        self._schedules: dict[str, ScheduleEntry] = {}     # id → entry (in-memory cache)

    # --- Lifecycle ---
    async def start(self):
        """Загрузить расписания из DB, посеять дефолты, запустить главный цикл."""
        await self._load_schedules()
        await self._seed_defaults_if_empty()
        self._task = asyncio.create_task(self._run_loop())

    async def stop(self):
        """Остановить главный цикл + все running tasks."""
        if self._task:
            self._task.cancel()
        for t in self._running_tasks.values():
            t.cancel()
        await asyncio.gather(*self._running_tasks.values(), return_exceptions=True)

    # --- Main loop ---
    async def _run_loop(self):
        """Проверяет каждые 5с: какие расписания due → запускает."""
        while True:
            await asyncio.sleep(5)
            if self._paused:
                continue
            now = time.time()
            for sid, entry in list(self._schedules.items()):
                if not entry.enabled:
                    continue
                if entry.next_run == 0:
                    entry.next_run = now + entry.interval_sec
                    self._persist(entry)
                if now >= entry.next_run:
                    await self._trigger(sid)

    # --- Task execution ---
    async def _trigger(self, sid: str):
        """Запустить задачу (с mutex-проверкой). Обновляет last_run/next_run/status."""
        entry = self._schedules[sid]
        task_def = TASK_TYPES[entry.task_type]

        # Проверка mutex — не запускать если конфликтующая задача уже running
        for conflict_type in task_def["mutex_with"]:
            if conflict_type in self._running_tasks:
                entry.last_status = "skipped"
                entry.next_run = time.time() + entry.interval_sec
                self._persist(entry)
                return

        # Проверка что сам этот task_type не running
        if entry.task_type in self._running_tasks:
            entry.last_status = "skipped"
            entry.next_run = time.time() + entry.interval_sec
            self._persist(entry)
            return

        # Проверки окружения
        if task_def["respect_pause"] and self.state._paused:
            entry.last_status = "skipped"
            entry.next_run = time.time() + entry.interval_sec
            self._persist(entry)
            return
        if task_def["respect_internet"] and not await self.state.is_internet_alive():
            entry.last_status = "skipped"
            entry.next_run = time.time() + entry.interval_sec
            self._persist(entry)
            return

        # Запуск
        entry.last_status = "running"
        entry.last_run = time.time()
        self._persist(entry)

        executor = getattr(self, task_def["executor"])
        task = asyncio.create_task(self._run_with_tracking(sid, executor))
        self._running_tasks[entry.task_type] = task

    async def _run_with_tracking(self, sid: str, executor):
        """Обёртка: выполняет задачу, обновляет status/duration/error."""
        entry = self._schedules[sid]
        t0 = time.time()
        try:
            await executor(entry)
            entry.last_status = "ok"
            entry.last_error = ""
        except Exception as e:
            entry.last_status = "failed"
            entry.last_error = str(e)
            logger.error(f"Schedule {sid} failed: {e}")
        finally:
            entry.last_duration_s = time.time() - t0
            entry.next_run = time.time() + entry.interval_sec
            self._running_tasks.pop(entry.task_type, None)
            self._persist(entry)

    # --- Manual trigger ---
    async def trigger_now(self, sid: str):
        """Запустить задачу сейчас, вне расписания. Не сдвигает next_run."""
        await self._trigger(sid)

    # --- CRUD ---
    async def add_schedule(self, entry: ScheduleEntry):
        async with self._lock:
            self._schedules[entry.id] = entry
            self._persist(entry)

    async def update_schedule(self, sid: str, **fields):
        async with self._lock:
            entry = self._schedules[sid]
            for k, v in fields.items():
                setattr(entry, k, v)
            # Пересчитать next_run если interval изменился
            if "interval_sec" in fields:
                entry.next_run = entry.last_run + entry.interval_sec
            self._persist(entry)

    async def delete_schedule(self, sid: str):
        async with self._lock:
            self._schedules.pop(sid, None)
            self._db_delete(sid)

    async def toggle_schedule(self, sid: str):
        async with self._lock:
            entry = self._schedules[sid]
            entry.enabled = not entry.enabled
            if entry.enabled:
                entry.next_run = time.time() + entry.interval_sec
            self._persist(entry)

    async def pause_all(self):
        self._paused = True

    async def resume_all(self):
        self._paused = False
```

### 2.5. Executor-методы

Каждый executor — тонкая обёртка над существующим методом `HuntState`:

```python
# --- Executors ---

async def _execute_hunt_cycle(self, entry):
    """Запускает полный цикл охоты (download → blacklist → validate)."""
    # Не запускается если уже идёт hunt
    if self.state._hunt_running:
        raise RuntimeError("Hunt already running")
    self.state.start_hunt()
    # Ждём завершения (health_loop запустится внутри, но нас интересует цикл)
    while self.state._hunt_running and self.state.phase not in ("done", "idle"):
        await asyncio.sleep(1)

async def _execute_ip_blacklist(self, entry):
    """Скачивает IP-blacklist списки."""
    if self.state._fetching_ip_blacklists:
        raise RuntimeError("IP blacklist fetch already in progress")
    await self.state._download_ip_blacklists()

async def _execute_blocklist(self, entry):
    """Скачивает country blocklists."""
    if self.state._fetching_blocklists:
        raise RuntimeError("Blocklist fetch already in progress")
    await self.state._download_blocklists()

async def _execute_health_check(self, entry):
    """Перепроверка живых прокси."""
    if self.state._health_task and not self.state._health_task.done():
        raise RuntimeError("Health check already running")
    await self.state._health_check(manual=False)

async def _execute_history(self, entry):
    """Запись истории + retention cleanup."""
    await self.state._push_history()
    await self.state._cleanup_retention()

async def _execute_clear_dead(self, entry):
    """Удаление мёртвых прокси."""
    await self.state._clear_dead_proxies()

async def _execute_backup(self, entry):
    """Создание резервной копии."""
    await self.state._create_backup(groups=entry.config.get("groups", "all"))
```

### 2.6. Миграция существующих циклов

#### Что заменяется

| Существующий код | Локация | Замена |
|---|---|---|
| `_history_loop()` | `health.py:435-451`, запускается `main.py:45` | Scheduler task `history` |
| `_ip_blacklist_loop()` | `health.py:261-283`, запускается `main.py:49` | Scheduler task `ip_blacklist_refresh` |
| `_blocklist_loop()` | `blocklists.py:408-428`, запускается `main.py:52` | Scheduler task `blocklist_refresh` |
| `_health_loop()` | `health.py:244-259`, запускается `health.py:206` | Scheduler task `health_check` |

#### Что НЕ заменяется

| Код | Причина |
|---|---|
| `_canary_loop()` (`health.py:229`) | Привязан к hunt cycle, не independent задача |
| `_hunt_cycle()` (`health.py:138`) | Запускается scheduler'ом как executor, не заменяется |
| `_revalidate_stale_proxies()` (`main.py:22`) | One-shot при старте, не periodic |

#### Изменения в `main.py:amain()`

Было:
```python
asyncio.create_task(state._history_loop())
if state.ip_blacklist_enabled:
    asyncio.create_task(state._ip_blacklist_loop())
asyncio.create_task(state._blocklist_loop())
```

Станет:
```python
scheduler = SchedulerEngine(state)
state.scheduler = scheduler
await scheduler.start()
```

#### Изменения в `health.py`

- `_health_loop()` — метод остаётся, но больше не запускается как independent task в конце `_hunt_cycle`. Вместо этого scheduler запускает `health_check` периодически.
- `_hunt_cycle()` — в конце больше не `asyncio.create_task(self._health_loop())`, так как scheduler этим управляет.
- Методы `_history_loop`, `_ip_blacklist_loop`, `_blocklist_loop` можно оставить как deprecated-обёртки или удалить. Рекомендуется удалить и перенести логику retention-cleanup в executor.

#### Порядок миграции (обратно-совместимый)

1. Добавить `SchedulerEngine` + DB-таблицу.
2. Seed дефолтных расписаний.
3. Запустить scheduler **параллельно** с существующими loops (для тестирования).
4. Проверить что нет двойного выполнения (mutex-флаги защитят).
5. Убрать старые `create_task` вызовы из `main.py`.
6. Удалить старые loop-методы.

### 2.7. API эндпоинты

Новые маршруты в `server.py:_route()` (следуя существующей if/elif конвенции):

```
GET    /api/schedules
  → { schedules: [{ id, name, task_type, enabled, interval_sec, config,
                     last_run, next_run, last_status, last_duration_s, last_error }] }

POST   /api/schedules
  body: { id, name, task_type, interval_sec, config? }
  → { ok: true, schedule: {...} }

POST   /api/schedules/<id>
  body: { name?, interval_sec?, config?, enabled? }
  → { ok: true, schedule: {...} }

DELETE /api/schedules/<id>
  → { ok: true }

POST   /api/schedules/<id>/toggle
  → { ok: true, enabled: bool }

POST   /api/schedules/<id>/run
  → { ok: true }   # запускает trigger_now, не блокирует ответ

GET    /api/schedules/status
  → { running: bool, paused: bool, running_tasks: ["health_check", ...] }

POST   /api/schedules/pause
POST   /api/schedules/resume
```

Расширение snapshot (`/api/snapshot`, `snapshot.py`):
```python
# Добавить в progress-секцию:
"schedules": [
    { "id": ..., "name": ..., "task_type": ..., "enabled": ...,
      "last_run": ..., "next_run": ..., "last_status": ... }
    for s in state.scheduler.list_schedules()
]
```

### 2.8. Frontend — страница «Расписания»

#### Регистрация

- Файл: `web/js/pages/schedules.js`
- `router.register('schedules', (container) => { ... })`
- Nav: раздел `system` в `index.html` (после Settings, перед Downloads)
- Иконка: новый `<symbol id="icon-schedules">` (часы с шестерёнкой) или reuse `icon-actions`
- `router.titles`: `schedules: ['page.schedules.title', 'page.schedules.subtitle']`
- `app._sectionOf`: `schedules: 'system'`

#### Layout страницы

```
┌─────────────────────────────────────────────────────────┐
│  Планировщик: ● Запущен          [⏸ Пауза]              │  ← header card
├─────────────────────────────────────────────────────────┤
│  Активных задач: 4   Выполнено сегодня: 87              │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│  Расписания                           [+ Новое расписание]│  ← list card
├──────────┬──────────┬────────┬──────┬──────┬──────┬─────┤
│ Задача   │ Интервал │ Вкл    │ Посл.│ След.│ Стат.│ Действия│
├──────────┼──────────┼────────┼──────┼──────┼──────┼─────┤
│ История  │ 1 мин    │ [ON]   │ 5с   │ 55с  │ ● ok │ ▶ ✎ 🗑│
│ IP-блэк. │ 1 час    │ [ON]   │ 12м  │ 48м  │ ● ok │ ▶ ✎ 🗓│
│ Блоклисты│ 1 час    │ [ON]   │ 12м  │ 48м  │ ● ok │ ▶ ✎ 🗓│
│ Health   │ 3 мин    │ [ON]   │ 30с  │ 2:30 │ ● ok │ ▶ ✎ 🗓│
│ Охота    │ —        │ [OFF]  │ 2ч   │ —    │ ○    │ ▶ ✎ 🗓│
└──────────┴──────────┴────────┴──────┴──────┴──────┴─────┘
```

#### Компоненты

- **Toggle switch** — reuse CSS из `routes.js` (`.route-toggle`, `components.css`)
- **Status badge** — `ui.badge(text, variant)`:
  - `ok` → green
  - `failed` → red
  - `running` → blue (с пульсирующей анимацией)
  - `skipped` → yellow
  - `never` → gray
- **Interval display** — форматирование: `60s` → «1 мин», `3600s` → «1 час», `86400s` → «1 день»
- **Relative time** — `ui.ago(ts)` для last_run, next_run

#### Modal редактирования (по паттерну `routes.js:showAddRouteModal`)

```
┌────────────────────────────────────┐
│  Редактирование расписания         │
├────────────────────────────────────┤
│  Название: [____________________]  │
│  Тип задачи: [Цикл охоты      ▾]  │
│  Интервал:  [__] [минут ▾]        │
│  Включено:  [✓]                    │
│                                    │
│              [Отмена]  [Сохранить] │
└────────────────────────────────────┘
```

Поля:
- `name` — text input
- `task_type` — select (enum из `TASK_TYPES`)
- `interval_sec` — number input + unit select (секунды/минуты/часы/дни → конвертация в секунды)
- `config` — скрытое JSON-поле, раскрывается только для task_type с доп. параметрами (backup: groups select)
- `enabled` — checkbox

#### Polling

```javascript
const id = setInterval(load, 3000);
if (window._pageIntervals) window._pageIntervals.push(id);
else window._pageIntervals = [id];
```

Polling обновляет last_run / next_run / last_status / running-индикаторы.

### 2.9. Локализация

Новые ключи во всех 6 файлах (`en.json`, `ru.json`, `es.json`, `fr.json`, `de.json`, `zh.json`):

```json
{
  "nav": {
    "schedules": "Расписания"
  },
  "page": {
    "schedules": {
      "title": "Расписания",
      "subtitle": "Управление фоновыми задачами",
      "schedulerRunning": "Запущен",
      "schedulerPaused": "На паузе",
      "pauseAll": "Пауза всех",
      "resumeAll": "Возобновить",
      "newSchedule": "Новое расписание",
      "editSchedule": "Редактирование расписания",
      "taskName": "Название",
      "taskType": "Тип задачи",
      "interval": "Интервал",
      "enabled": "Включено",
      "lastRun": "Последний запуск",
      "nextRun": "Следующий запуск",
      "status": "Статус",
      "actions": "Действия",
      "runNow": "Запустить сейчас",
      "edit": "Редактировать",
      "delete": "Удалить",
      "statusOk": "OK",
      "statusFailed": "Ошибка",
      "statusRunning": "Выполняется",
      "statusSkipped": "Пропущено",
      "statusNever": "Не запускалось",
      "taskHuntCycle": "Цикл охоты",
      "taskIpBlacklist": "Обновление IP-блэклистов",
      "taskBlocklist": "Обновление блоклистов",
      "taskHealthCheck": "Перепроверка прокси",
      "taskHistory": "Запись истории",
      "taskClearDead": "Очистка мёртвых",
      "taskBackup": "Резервная копия",
      "unitSeconds": "секунд",
      "unitMinutes": "минут",
      "unitHours": "часов",
      "unitDays": "дней",
      "deleteConfirm": "Удалить расписание?",
      "noSchedules": "Нет расписаний",
      "activeTasks": "Активных задач",
      "runsToday": "Запусков сегодня"
    }
  }
}
```

### 2.10. Cache-bust

В `index.html` bump версий:
- `api.js?v=20` (новые методы)
- `schedules.js?v=1` (новый файл)
- `app.js?v=N+1` если меняется `_sectionOf`

### 2.11. Тесты

Файл: `tests/test_scheduler.py`

| Тест | Описание |
|---|---|
| `test_seed_defaults` | При пустой DB — сеются 5 дефолтных расписаний |
| `test_load_schedules` | Расписания загружаются из DB в in-memory cache |
| `test_trigger_due_task` | Задача с `next_run < now` — запускается |
| `test_skip_not_due` | Задача с `next_run > now` — не запускается |
| `test_skip_disabled` | Disabled задача — не запускается |
| `test_mutex_same_type` | Два запуска одного task_type одновременно — второй skipped |
| `test_mutex_conflict_type` | hunt_cycle + health_check одновременно — второй skipped |
| `test_respect_pause` | hunt_cycle при `_paused=True` — skipped |
| `test_respect_internet_down` | Задача с `respect_internet` при internet down — skipped |
| `test_trigger_now` | `trigger_now()` запускает задачу вне расписания |
| `test_crud_add_update_delete` | Добавить, обновить interval, удалить — persist в DB |
| `test_toggle_schedule` | Toggle меняет enabled + пересчитывает next_run |
| `test_pause_resume_all` | `pause_all()` → задачи не запускаются, `resume_all()` → запускаются |
| `test_last_status_tracking` | После запуска: last_status=ok/failed, last_duration_s>0 |
| `test_migration_no_regression` | History/blacklist/health работают через scheduler с теми же интервалами |

API-тесты (в `tests/test_api.py`):
| Тест | Описание |
|---|---|
| `test_api_schedules_list` | GET /api/schedules возвращает список |
| `test_api_schedule_create` | POST /api/schedules создаёт + persist |
| `test_api_schedule_update` | POST /api/schedules/<id> обновляет interval |
| `test_api_schedule_delete` | DELETE /api/schedules/<id> удаляет |
| `test_api_schedule_toggle` | POST /api/schedules/<id>/toggle меняет enabled |
| `test_api_schedule_run_now` | POST /api/schedules/<id>/run запускает задачу |
| `test_api_schedules_status` | GET /api/schedules/status возвращает running/paused |
| `test_api_schedules_pause_resume` | POST pause/resume меняет глобальную паузу |

### 2.12. План реализации по фазам

#### Фаза 1 — Backend: Scheduler engine + DB (1 файл + правки)

1. Создать `hunt/scheduler.py` — `SchedulerEngine` класс + `ScheduleEntry` dataclass
2. Добавить таблицу `schedules` в `db.py:_init_state_db`
3. Реализовать CRUD + persist методы в `SchedulerEngine`
4. Реализовать executors (обёртки над существующими методами `HuntState`)
5. Реализовать `_run_loop` с mutex/pause/internet-проверками
6. Seed дефолтных расписаний

**Файлы:** `hunt/scheduler.py` (новый), `hunt/db.py` (правка)

#### Фаза 2 — Backend: Интеграция + миграция

7. Добавить `state.scheduler = SchedulerEngine(state)` в `main.py:amain()`
8. Запустить `await scheduler.start()` вместо отдельных `create_task` вызовов
9. Убрать `_history_loop`, `_ip_blacklist_loop`, `_blocklist_loop` из `main.py`
10. Убрать `_health_loop` запуск из `_hunt_cycle` (scheduler управляет)
11. Добавить `scheduler.stop()` в `shutdown()`

**Файлы:** `hunt/main.py` (правка), `hunt/health.py` (правка), `hunt/blocklists.py` (правка)

#### Фаза 3 — Backend: API

12. CRUD эндпоинты `/api/schedules*` в `server.py:_route`
13. `trigger_now` эндпоинт
14. `status` / `pause` / `resume` эндпоинты
15. Расширить snapshot (`snapshot.py`) секцией `schedules`

**Файлы:** `hunt/server.py` (правка), `hunt/snapshot.py` (правка)

#### Фаза 4 — Backend: Тесты

16. `tests/test_scheduler.py` — все тесты из 2.11
17. API-тесты в `tests/test_api.py`
18. `./test.sh` — все тесты проходят

**Файлы:** `tests/test_scheduler.py` (новый), `tests/test_api.py` (правка)

#### Фаза 5 — Frontend: API + страница

19. Методы `api.schedules*()` в `web/js/api.js`
20. Создать `web/js/pages/schedules.js` — build/load/render
21. Header card со статусом планировщика + пауза
22. Таблица расписаний с toggle/badge/relative-time
23. Modal редактирования
24. Polling 3с

**Файлы:** `web/js/api.js` (правка), `web/js/pages/schedules.js` (новый)

#### Фаза 6 — Frontend: Регистрация + локали

25. Script tag в `index.html` + cache-bust версий
26. Nav item в `index.html` (раздел system)
27. Новый SVG `<symbol>` для иконки
28. `router.titles` — добавить `schedules`
29. `app._sectionOf` — добавить `schedules: 'system'`
30. Локали — `page.schedules.*` и `nav.schedules` во всех 6 языках

**Файлы:** `web/index.html` (правка), `web/js/router.js` (правка), `web/js/app.js` (правка), `web/locales/*.json` (6 файлов)

#### Фаза 7 — Финальная проверка

31. `./test.sh` — все тесты (включая новые)
32. Проверка через UI: создание/редактирование/toggle/run-now расписаний
33. Проверка через curl: API-эндпоинты
34. Проверка миграции: существующие циклы работают через scheduler
35. Коммит в git

### 2.13. Риски и меры

| Риск | Мера |
|---|---|
| Двойное выполнение при миграции | Mutex-флаги + параллельный запуск на этапе тестирования |
| Регрессия существующих циклов | Seed дефолтов с теми же интервалами; тест `test_migration_no_regression` |
| Scheduler падает → все фоновые задачи останавливаются | Try/except в `_run_loop` + restart-логика; логирование |
| `hunt_cycle` executor блокирует scheduler-loop | Запуск в `create_task` (не await), scheduler-loop продолжает проверять другие расписания |
| Ручной запуск hunt конфликтует с scheduled hunt | Mutex `hunt_cycle` в scheduler + существующий guard `_hunt_running` в `start_hunt()` |
| DB-блокировка при persist | `_persist` использует существующий `_state_conn` (WAL mode, неблокирующий) |
