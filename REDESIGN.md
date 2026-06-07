# Huntproxy UI Redesign — Integration Plan

> Источник: дизайн-макеты от 07.06.2026 (Overview + дополнительные экраны: Proxies, Proxy Details, Blacklist, Settings, Quick Actions, Logs).  
> Цель: полностью заменить текущий inline-HTML в `hunt.py` на модульный SPA-фронтенд с раздачей статики, сохранив Python-only бэкенд.

---

## 1. Общая архитектура

| Уровень | Текущее состояние | Целевое состояние |
|---|---|---|
| **Frontend** | Inline HTML + CSS + JS внутри `hunt.py` | Отдельная директория `web/` (index.html, CSS, JS) |
| **Backend** | Raw HTTP-сервер на asyncio, 2 таба (Hunt/Proxy) | Тот же сервер + раздача статики + новые API endpoints + SSE (опционально) |
| **Data** | `ratings.json`, `working.txt`, `blacklist.txt` | Те же файлы + кольцевой буфер истории (`history.json`) |
| **Stack** | Zero dependencies | `psutil` (опционально, для System Resources) |

**Принцип:** не добавлять сборщики (Webpack/Vite), не использовать фреймворки (React/Vue). Vanilla JS + CSS-переменные. Минимальное усложнение бэкенда.

---

## 2. Дизайн-система

### 2.1 Темы
- **Light** (по умолчанию): фон `#F8F9FA`, карточки `#FFFFFF`, текст `#1A1D1F`, акцент `#4F46E5` (indigo).
- **Dark**: фон `#0F1115`, карточки `#1A1D24`, текст `#F0F0F5`, акцент `#6366F1`.
- Переключатель внизу Sidebar (солнышко/луна). Сохранение в `localStorage`.

### 2.2 Типографика
- Шрифт: `Inter` (Google Fonts) или системный `-apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif`.
- Размеры: заголовок страницы `24px/600`, заголовок карточки `12px/600 uppercase tracking-wide`, метрика `32px/700`, лейбл `11px/500`.

### 2.3 Компоненты (повторяющиеся)
- **Card**: `border-radius: 12px`, `border: 1px solid var(--border)`, `padding: 20px`, `box-shadow: 0 1px 2px rgba(0,0,0,0.04)`.
- **Button variants**: `primary` (indigo), `secondary` (white/gray border), `danger` (red), `ghost` (text only).
- **Badge**: `border-radius: 6px`, `padding: 2px 8px`, цвета по статусам (`alive` — зеленый, `dead` — красный, `blacklist` — фиолетовый).
- **Table**: `font-size: 12px`, `border-bottom: 1px solid var(--border)`, hover `background: var(--hover)`.
- **Progress Bar / Circle**: CSS-анимации (`transition: width 0.4s ease`).
- **Tooltip**: CSS-only на `data-tooltip`.

---

## 3. Страницы и компоненты (по макетам)

### 3.1 Layout (общий для всех страниц)
- **Sidebar** (фиксированный, `width: 240px`):
  - Логотип `huntproxy` + иконка.
  - Навигация: Overview, Proxies, Proxy Control, Proxy Pool, Blacklist, Analytics, Logs, Settings, Rules, Downloads, API.
  - Нижняя секция: Theme toggle (Light/Dark), System Status (All Systems Operational / версия / uptime).
- **Topbar** (`height: 64px`, `position: sticky`):
  - Глобальный поиск (Search proxies, IPs, countries...).
  - Quick Actions dropdown.
  - Иконка уведомлений (колокольчик).
  - Профиль пользователя (Admin / Administrator).
- **Main Content Area**: адаптивная сетка.

### 3.2 Overview (Dashboard) — приоритет: **P0**
**Верхний ряд (Stats Cards)** — 4 карточки:
- Total Proxies: `3,944` (+134 today)
- Alive: `404` (10.2% of total) + sparkline (зеленый)
- Dead: `3,540` (89.8% of total) + sparkline (красный)
- Blacklisted: `5` (0 blocked) + sparkline (фиолетовый)
- **Бэкенд:** расширить `get_snapshot()` счётчиком `new_today` (сравнивать с `first_seen` за последние 24ч). Sparkline — массив из 7 точек (для начала статичный или агрегировать по часам).

**Второй ряд** — 2 карточки:
- **Pool Progress** (слева):
  - Круговой прогресс `71%` (SVG `stroke-dasharray`).
  - Линейный прогресс "Validating proxies".
  - Текст: `Checked 3,667 / 5,152`, `Working 302`.
  - Последний прокси: `98.191.0.47:4145 United States`.
- **Top Countries** (справа):
  - Горизонтальные бар-чарты (CSS flex).
  - Страны + флаги + количество + процент.
  - Кнопка `View all`.
  - **Бэкенд:** новый endpoint `GET /api/countries`.

**Третий ряд** — 3 карточки:
- **Top Rated Proxies** (таблица):
  - Колонки: `#`, PROXY, COUNTRY, LATENCY, SCORE, UPTIME, LAST CHECK.
  - Кнопка `View all proxies` → роутинг на страницу Proxies.
  - **Бэкенд:** данные уже есть в `top_proxies`, добавить `uptime` (формат `checks_ok/checks_total` или `success_rate` в %).
- **System Resources** (3 progress bars):
  - CPU Usage, Memory Usage, Disk Usage.
  - **Бэкенд:** новый endpoint `GET /api/system` (через `psutil` или `/proc` fallback).
- **Quick Actions** (сетка 2×3 или 3×2):
  - Refresh Pool, Health Check, Clear Dead, Export, Import, Settings.
  - Каждая кнопка с иконкой + подписью + кратким описанием.
  - **Бэкенд:** реализовать соответствующие POST endpoints (см. раздел 4).

**Четвертый ряд** — 2 карточки:
- **Live Performance** (график):
  - Линейный график Requests + Success Rate (%) за последний час.
  - Дропдаун `Last 1 hour` / `Last 6 hours` / `Last 24 hours`.
  - **Бэкенд:** кольцевой буфер `history` в `HuntState` + endpoint `GET /api/history`.
- **Current Proxy** (карточка):
  - IP + флаг + бейдж `Alive`.
  - Метрики: Latency, Success Rate, Uptime, Last Check.
  - **Бэкенд:** данные из `proxy/status` + `selected_proxy`.

**Боковая панель (внизу Overview)**:
- **Recent Activity** — лента событий с иконками (validated, added, health check, removed, updated, failed).
- **Бэкенд:** новый endpoint `GET /api/activity` (форматирование `events` в типизированные объекты).

### 3.3 Proxies — приоритет: **P1**
- Таблица со всеми прокси.
- Табы-фильтры: `All (3,944)`, `Alive (404)`, `Dead (3,540)`, `Blacklisted (5)`.
- Кнопки: `Filter`, `Refresh`, `Export`, `Add Proxy`.
- Колонки: PROXY, COUNTRY, TYPE, LATENCY, SCORE, STATUS, LAST CHECK.
- Пагинация (по 20/50/100 строк).
- Клик по строке → открытие **Proxy Details**.
- **Бэкенд:** endpoint `GET /api/proxies?status=&page=&limit=` (пагинация на бэкенде или клиенте).

### 3.4 Proxy Control — приоритет: **P1**
Страница мониторинга и управления активным upstream-прокси (ранее вкладка Proxy). Дизайн — полноценный дашборд в реальном времени.

**Верхний ряд (KPI Cards)** — 6 метрик с мини-графиками (SVG sparklines):
- Active Proxy: IP + флаг + статус (`Healthy` / `Unhealthy` / `Blacklisted`).
- Proxy Type: `HTTP`, `SOCKS5`, `SOCKS4`, `CONNECT`.
- Uptime: время с момента выбора прокси.
- Requests (24h): счётчик запросов через этот прокси.
- Success Rate: % успешных соединений.
- Avg Response Time: среднее время ответа.
- **Бэкенд:** расширить `ProxyRunner.get_status()` счётчиками `requests_24h`, `success_rate`, `avg_response_time`, `uptime_seconds`, `proxy_health`. Sparkline — массив последних 20 точек (кольцевой буфер `proxy_stats` в `ProxyRunner`).

**Второй ряд** — 3 колонки:
- **Traffic Overview** (широкая, ~60%):
  - Табы: `Requests`, `Bandwidth`, `Response Time`, `Errors`.
  - Линейный график (SVG) за `Last 2 hours` / `24h` / `7d`.
  - Summary справа: Total Requests, Successful, Failed, Bandwidth In/Out.
  - **Бэкенд:** расширить `history` в `ProxyRunner` (или `HuntState`) полями `requests`, `bytes_in`, `bytes_out`, `errors`, `response_time`. Endpoint `GET /api/traffic`.
- **Current Proxy** (карточка):
  - IP + флаг + статус + бейдж.
  - Метрики: Status, Latency, Response Time (avg), Success Rate, Last Check, Fails, Speed, Protocol.
  - Кнопка `Change Proxy` → роутинг на Proxy Pool.
  - **Бэкенд:** данные из `proxy/status` + `selected_proxy`.
- **Connected Clients** (таблица):
  - Колонки: IP Address, Country, Requests, Last Seen.
  - Индикатор `Live` (зелёная точка) + счётчик `163`.
  - Кнопка `View all`.
  - **Бэкенд:** endpoint `GET /api/clients` (данные из `ProxyRunner.log` — агрегация по уникальным `client` IP). Для начала можно отдавать top 5 из `self.log`.

**Третий ряд** — 3 карточки:
- **Top Requested Domains** (таблица):
  - Колонки: Domain (с favicon/эмодзи), Requests, % of Total, Avg Response, Status.
  - **Бэкенд:** endpoint `GET /api/domains` (требует парсинга `target` из `ProxyRunner.log` на домен). Для MVP — агрегация по `urlparse(target).hostname`.
- **Error Breakdown** (donut chart + легенда):
  - Категории: `Timeout`, `Connection Failed`, `HTTP 4xx`, `HTTP 5xx`.
  - Центр: Total Errors.
  - **Бэкенд:** endpoint `GET /api/errors` (анализ статусов из `ProxyRunner.log`). Для MVP — маппинг `status` строки на категории.
- **Bandwidth Usage** (2 мини-графика + метрики):
  - Incoming / Outgoing с трендами (%).
  - Общие объёмы: `1.23 GB` / `3.45 GB`.
  - **Бэкенд:** данные из `GET /api/traffic` (последняя точка).

**Четвёртый ряд** — 2 карточки:
- **Recent Requests** (таблица):
  - Колонки: Time, Client IP, Method, URL, Status, Response Time, Size, Proxy, Actions (глаз / ссылка).
  - **Бэкенд:** endpoint `GET /api/requests` — последние 50 записей из `ProxyRunner.log` с доп. полями (method, url, size — для MVP можно захардкодить `GET` / `CONNECT` и размер `—`).
- **Proxy Health (24h)** (график + метрики):
  - Линейный график Health Score за 24h (0–100%).
  - Метрики: Health Score, Failures, Avg Latency, Checks.
  - **Бэкенд:** данные из `ratings` (score, latency, checks_total) + endpoint `GET /api/history` с фильтром по `active_proxy`.

**Важно:** большая часть данных (домены, клиенты, bandwidth, request log) требует расширения `ProxyRunner._log()` и/или хранения `request_log`. Для MVP можно:
- агрегировать `ProxyRunner.log` на лету (медленно, но без новых структур),
- или добавить кольцевой буфер `request_log: deque(maxlen=200)` в `ProxyRunner` с полями `{ts, client, method, url, status, response_time, size, proxy}`.

### 3.5 Proxy Details (модалка / страница) — приоритет: **P1**
- Шапка: IP + флаг + статус + Score.
- Табы: Overview, Performance, History, Checks, Raw Data.
- **Overview**: General Information (IP, Port, Country, Type, Added, Last Check), Performance (Latency, Success Rate, Uptime, Avg Response).
- **Performance**: график (24h) + Recent Checks (таблица: Time, Result).
- **History**: timeline событий по прокси.
- **Checks**: результаты последних проверок.
- **Raw Data**: JSON dump из `ratings.json` для этого прокси.
- **Бэкенд:** endpoint `GET /api/proxy/{address}` (детальная информация + история по конкретному прокси).

### 3.6 Blacklist — приоритет: **P1**
- Таблица: PROXY, COUNTRY, REASON, BLACKLISTED (время), ACTIONS (Remove).
- Фильтры: по причине (Reason), по стране.
- Кнопка `Refresh`.
- **Бэкенд:** endpoint уже есть (`/api/blacklist/add`, `/api/blacklist/remove`), нужен `GET /api/blacklist` (для пагинации/фильтров).

### 3.7 Analytics — приоритет: **P2**
- Графики: Success Rate over time, Latency distribution, Top Countries pie chart, Proxy type distribution.
- Использует данные из `/api/history` и `/api/countries`.

### 3.8 Logs — приоритет: **P2**
- Фильтры: All Levels (Info, Warn, Error), Live toggle, Clear, Export.
- Таблица: TIME, LEVEL, PROXY, MESSAGE.
- **Бэкенд:** endpoint `GET /api/logs` (чтение `huntproxy.log` или streaming из `events`).

### 3.9 Settings — приоритет: **P2**
- Табы: General, Proxies, Sources, Validation, Advanced.
- **General**: Web UI Listen Address, HTTP Proxy Listen Address, SOCKS5 Proxy Listen Address, Transparent Proxy Listen Address.
- **Proxies**: Health Check Interval, Validation Interval, Max Failures, Cooldown, Strategy (round_robin / random).
- **Sources**: список источников с чекбоксами + возможность добавить URL.
- **Validation**: Timeout, Parallel, Country Filter (US/ALL).
- **Advanced**: Clear Cache, Reset Ratings, Export/Import Config.
- **Бэкенд:** endpoint `GET /api/settings` (чтение `config.yaml`), `POST /api/settings` (запись + reload). Валидация полей.

### 3.10 Downloads — приоритет: **P2**
- Ссылки на скачивание: `working.txt`, `blacklist.txt`, `ratings.json`, `config.yaml`.
- **Бэкенд:** `GET /api/download/{filename}`.

### 3.11 API — приоритет: **P2**
- Автоматически сгенерированная документация (таблица: Method, Endpoint, Description, Parameters).
- **Бэкенд:** endpoint `GET /api/docs` (можно захардкодить или генерировать из `_route`).

### 3.12 Rules — приоритет: **P3**
- Заглушка/страница с описанием iptables-правил.
- Ссылка на `setup_iptables.sh`.

---

## 4. Новые API Endpoints (бэкенд)

| Endpoint | Method | Описание | Статус |
|---|---|---|---|
| `/` | GET | Раздача `web/index.html` | Новый |
| `/css/*`, `/js/*` | GET | Статические файлы | Новый |
| `/api/snapshot` | GET | Общий snapshot (счётчики, top прокси, прогресс) | Существует |
| `/api/countries` | GET | Топ стран по alive-прокси | **Новый** |
| `/api/activity` | GET | Лента событий (форматированные) | **Новый** |
| `/api/system` | GET | CPU, Memory, Disk usage | **Новый** |
| `/api/history` | GET | График `requests/success_rate` за период | **Новый** |
| `/api/proxies` | GET | Пагинированный список всех прокси | **Новый** |
| `/api/proxy/{addr}` | GET | Детали одного прокси | **Новый** |
| `/api/traffic` | GET | График трафика (Requests/Bandwidth/Response Time/Errors) | **Новый** |
| `/api/requests` | GET | Recent Requests (last 50) | **Новый** |
| `/api/clients` | GET | Connected Clients (агрегация по IP) | **Новый** |
| `/api/domains` | GET | Top Requested Domains | **Новый** |
| `/api/errors` | GET | Error Breakdown (timeout, 4xx, 5xx, connect failed) | **Новый** |
| `/api/bandwidth` | GET | Bandwidth Usage (in/out) | **Новый** |
| `/api/blacklist` | GET | Пагинированный blacklist | **Новый** |
| `/api/settings` | GET/POST | Чтение/запись `config.yaml` | **Новый** |
| `/api/logs` | GET | Логи системы | **Новый** |
| `/api/download/{file}` | GET | Скачивание файлов из `data/` | **Новый** |
| `/api/health/start` | POST | Ручной запуск health-check | **Новый** |
| `/api/clear_dead` | POST | Удаление всех dead из `ratings` | **Новый** |
| `/api/export` | POST | Экспорт `working.txt` | **Новый** |
| `/api/import` | POST | Импорт списка прокси | **Новый** |
| `/api/events` | GET | Long-polling events (существует) | Существует |

---

## 5. Изменения в `hunt.py` (Backend Tasks)

### 5.1 Раздача статики
- Создать `HuntServer._serve_static(path)`.
- Если `web/` существует — читать файлы с диска.
- Если `web/` не существует — fallback на `WEB_HTML` (legacy).

### 5.2 История (History Ring Buffer)
- В `HuntState.__init__` добавить `self.history = deque(maxlen=360)` (1 точка каждые 10 сек = 1 час).
- При каждом health-check и validate добавлять точку: `{ts, requests, success_rate, alive_count, dead_count}`.
- Endpoint `/api/history?last=1h` отдаёт срез.

### 5.3 Top Countries
- Агрегация `Counter` по `country_code` из alive-прокси.
- Сортировка по убыванию, топ 10.

### 5.4 System Resources
- Попытка `import psutil`.
- Fallback: парсинг `/proc/stat`, `/proc/meminfo`, `df` (Linux-only).
- Если не доступно — вернуть `null` и скрыть блок на фронтенде.

### 5.5 Activity Feed
- Маппинг `events` на типы:
  - `validated` → зеленая галочка
  - `added` → плюс
  - `removed` → корзина
  - `failed` → красный крест
  - `health check completed` → сердце
  - `blacklist updated` → щит

### 5.6 Uptime сервера
- Зафиксировать `self.started_at = time.time()` в `HuntState`.
- Отдавать в `snapshot` как `uptime_seconds`.

### 5.7 Settings API
- Чтение `config.yaml` через `yaml.safe_load`.
- Запись: валидировать, сохранить, опционально перезапустить health-loop (применить `interval` без рестарта процесса).

### 5.8 Proxy Details API
- `GET /api/proxy/{address}` → `ratings[address].to_dict()` + история по этому прокси (если будем хранить per-proxy history).

### 5.9 Proxy Control / Traffic Stats
- В `ProxyRunner.__init__` добавить кольцевой буфер:
  - `self.request_log = deque(maxlen=200)` — полные записи запросов.
  - `self.traffic_history = deque(maxlen=120)` — точки для графика (каждые 30 сек).
- Расширить `_log()` полями: `method`, `url`, `size`, `response_time` (где возможно).
- Агрегация для `GET /api/clients`: группировка по `client` IP из `request_log`, подсчёт `requests` и `last_seen`.
- Агрегация для `GET /api/domains`: извлечение hostname из `target` (или `url`), подсчёт частоты и среднего `response_time`.
- Агрегация для `GET /api/errors`: маппинг `status` строк на категории (`timeout`, `connect_failed`, `4xx`, `5xx`).
- Для `Bandwidth` и `Traffic Overview`: если реальный подсчёт байтов невозможен без middleware, использовать `len(data)` из `_relay()` (опционально, сложно) или **mock/fallback** для MVP.
- **MVP-стратегия:** на первом этапе `request_log` заполняется из существующего `self.log` (client, target, status, upstream), а поля `method`, `url`, `size` заполняются placeholder'ами (`GET`, `target`, `—`). Графики рисуются по `traffic_history` с синтетическими/агрегированными данными (count запросов за интервал).

---

## 6. Фронтенд-архитектура

### 6.1 Структура файлов
```
web/
├── index.html              # Layout (sidebar + topbar + router-view)
├── css/
│   ├── theme.css           # CSS-переменные (light/dark)
│   ├── layout.css          # Sidebar, Topbar, Grid
│   ├── components.css      # Cards, Buttons, Tables, Badges, Progress
│   └── pages.css           # Overview, Proxies, Details, Settings...
├── js/
│   ├── app.js              # Инициализация, роутер, тема
│   ├── api.js              # Обёртка fetch для всех endpoints
│   ├── router.js           # Hash-based routing (#/overview, #/proxies)
│   ├── components.js       # Функции-генераторы DOM (createCard, createTable)
│   ├── charts.js           # SVG sparklines + line chart (vanilla)
│   └── pages/
│       ├── overview.js     # Dashboard page logic
│       ├── proxies.js      # Proxies table + filters
│       ├── proxy-control.js # Proxy Control dashboard (active proxy)
│       ├── proxy-detail.js # Proxy Details page
│       ├── blacklist.js    # Blacklist table
│       ├── analytics.js    # Analytics charts
│       ├── logs.js         # Logs viewer
│       ├── settings.js     # Settings form
│       ├── downloads.js    # Download links
│       └── api-docs.js     # API documentation
```

### 6.2 Роутинг
- Hash-based: `http://localhost:17177/#/overview`.
- `router.js` слушает `hashchange`.
- При загрузке страницы: определять `window.location.hash` или default `#/overview`.

### 6.3 Поллинг vs SSE
- **Поллинг** (текущий подход): `setInterval(poll, 1000)` для `/api/snapshot` и `/api/events`.
- **SSE** (опционально, Phase 3): `EventSource` для `/api/stream` — меньше задержек для логов и активности.
- На первом этапе оставляем поллинг для совместимости.

### 6.4 Тема
- Переключатель меняет `data-theme` на `<html>`.
- CSS-переменные переключаются через `[data-theme="dark"]`.

---

## 7. Подзадачи по фазам (Roadmap)

### Фаза 0. Фундамент (Базовый layout + сервер)
- [ ] **B0.1** Создать директорию `web/` и файловую структуру.
- [ ] **B0.2** Добавить в `HuntServer._route()` раздачу статики (`index.html`, `.css`, `.js`).
- [ ] **B0.3** Создать `web/index.html` с layout: Sidebar (9 пунктов), Topbar, Main Content Area.
- [ ] **B0.4** Создать `css/theme.css` с CSS-переменными (light) и `data-theme="dark"`.
- [ ] **B0.5** Создать `css/layout.css` — sidebar, topbar, grid, responsive breakpoints.
- [ ] **F0.1** Реализовать `js/router.js` — hash-based routing с заглушками страниц.
- [ ] **F0.2** Реализовать `js/api.js` — базовый fetch-обёртку с error handling.
- [ ] **F0.3** Реализовать theme toggle в sidebar + сохранение в `localStorage`.

**Критерий приёмки:** сервер стартует, открывается новый layout, работает навигация по hash, переключается тема. Fallback на старый `WEB_HTML` работает при отсутствии `web/`.

---

### Фаза 1. Overview Dashboard (P0)
- [ ] **B1.1** Расширить `get_snapshot()` полями: `new_today`, `uptime_seconds`, `last_proxy_details`.
- [ ] **B1.2** Создать endpoint `GET /api/countries` — агрегация топ-10 стран.
- [ ] **B1.3** Создать endpoint `GET /api/system` — CPU/RAM/Disk (psutil или fallback).
- [ ] **B1.4** Создать endpoint `GET /api/activity` — форматированная лента событий (10 штук).
- [ ] **B1.5** Создать кольцевой буфер `history` в `HuntState` + endpoint `GET /api/history`.
- [ ] **B1.6** Добавить endpoint `GET /api/proxy/status` в snapshot (уже есть, проверить полноту данных).

- [ ] **F1.1** Верстка Stats Cards (4 шт.) с sparklines (SVG).
- [ ] **F1.2** Верстка Pool Progress — круговой + линейный прогресс.
- [ ] **F1.3** Верстка Top Countries — горизонтальные бары с флагами.
- [ ] **F1.4** Верстка Top Rated Proxies — таблица с сортировкой.
- [ ] **F1.5** Верстка System Resources — 3 progress bars.
- [ ] **F1.6** Верстка Quick Actions — сетка кнопок (пока заглушки/alert).
- [ ] **F1.7** Верстка Live Performance — SVG line chart (Requests + Success Rate).
- [ ] **F1.8** Верстка Current Proxy — карточка с метриками.
- [ ] **F1.9** Верстка Recent Activity — лента с иконками и timestamp.
- [ ] **F1.10** Подключить поллинг (`setInterval`) для обновления всех виджетов Overview.

**Критерий приёмки:** Dashboard отображает реальные данные из бэкенда, обновляется каждые 1-2 секунды, все 4 ряда виджетов работают.

---

### Фаза 2. Proxies + Proxy Control + Blacklist (P1)
- [ ] **B2.1** Endpoint `GET /api/proxies?status=&page=&limit=` — пагинация, фильтрация по статусу.
- [ ] **B2.2** Endpoint `GET /api/proxy/{address}` — детали прокси (для модалки/страницы).
- [ ] **B2.3** Endpoint `GET /api/blacklist` — пагинированный список с фильтрами.
- [ ] **B2.4** Реализовать `POST /api/clear_dead` — удаление dead прокси из `ratings`.
- [ ] **B2.5** Реализовать `POST /api/export` — отдача `working.txt` как downloadable.
- [ ] **B2.6** Реализовать `POST /api/import` — загрузка списка прокси (multipart form или JSON).
- [ ] **B2.7** Расширить `ProxyRunner._log()` полями `method`, `url`, `response_time`, `size`. Добавить `request_log` (deque maxlen=200) и `traffic_history` (deque maxlen=120).
- [ ] **B2.8** Endpoint `GET /api/traffic` — точки для графика трафика.
- [ ] **B2.9** Endpoint `GET /api/requests` — последние 50 записей из `request_log`.
- [ ] **B2.10** Endpoint `GET /api/clients` — агрегация подключённых клиентов.
- [ ] **B2.11** Endpoint `GET /api/domains` — топ запрашиваемых доменов.
- [ ] **B2.12** Endpoint `GET /api/errors` — агрегация ошибок по категориям.
- [ ] **B2.13** Endpoint `GET /api/bandwidth` — incoming/outgoing (MVP: счётчик из `request_log` или placeholder).

- [ ] **F2.1** Страница `Proxies` — таблица с табами (All/Alive/Dead/Blacklisted), фильтрами, пагинацией.
- [ ] **F2.2** Клик по строке → открытие `Proxy Details` (страница или модалка).
- [ ] **F2.3** Страница `Proxy Details` — табы Overview, Performance, History, Checks, Raw Data.
- [ ] **F2.4** Страница `Proxy Control` — полноценный дашборд:
  - KPI Cards (6 шт.) с sparklines.
  - Traffic Overview (график + summary).
  - Current Proxy (карточка + Change Proxy).
  - Connected Clients (таблица + Live).
  - Top Requested Domains (таблица).
  - Error Breakdown (donut chart).
  - Bandwidth Usage (2 мини-графика).
  - Recent Requests (таблица).
  - Proxy Health (24h) график + метрики.
- [ ] **F2.5** Страница `Blacklist` — таблица с фильтрами, кнопкой Remove.
- [ ] **F2.6** Quick Actions — подключить реальные POST-запросы (Refresh Pool, Health Check, Clear Dead, Export, Import).

**Критерий приёмки:** Можно просматривать все прокси, фильтровать, открывать детали. Страница Proxy Control отображает текущий активный прокси, график трафика, список клиентов, домены, ошибки, recent requests. Blacklist управляется. Quick Actions работают.

---

### Фаза 3. Logs + Settings + Analytics (P2)
- [ ] **B3.1** Endpoint `GET /api/logs` — чтение последних N строк `huntproxy.log` или streaming events.
- [ ] **B3.2** Endpoint `GET /api/settings` — чтение `config.yaml`.
- [ ] **B3.3** Endpoint `POST /api/settings` — валидация и запись `config.yaml`.
- [ ] **B3.4** Endpoint `GET /api/download/{file}` — безопасная раздача файлов из `data/`.
- [ ] **B3.5** Endpoint `GET /api/docs` — список всех API endpoints (хардкод или рефлексия).

- [ ] **F3.1** Страница `Logs` — таблица с фильтрами по уровню, live toggle, clear, export.
- [ ] **F3.2** Страница `Settings` — формы с табами (General, Proxies, Sources, Validation, Advanced), кнопка Save.
- [ ] **F3.3** Страница `Analytics` — графики (Success Rate, Latency, Countries pie) на основе `/api/history`.
- [ ] **F3.4** Страница `Downloads` — кнопки скачивания файлов.
- [ ] **F3.5** Страница `API` — документация endpoints.
- [ ] **F3.6** Страница `Rules` — заглушка с описанием transparent mode.

**Критерий приёмки:** Все страницы sidebar работают, настройки можно редактировать и сохранять, логи читаются, аналитика строит графики.

---

### Фаза 4. Полировка и оптимизация (P3)
- [ ] **F4.1** Адаптивная вёрстка: sidebar → hamburger на `< 1024px`, карточки в 1 колонку на `< 768px`.
- [ ] **F4.2** CSS-анимации: fade-in карточек, pulse индикаторов, transition прогресс-баров.
- [ ] **F4.3** Оптимизация поллинга: разные интервалы для разных виджетов (snapshot — 1с, system — 5с, history — 30с).
- [ ] **F4.4** Обработка ошибок сети: retry, toast-уведомления, offline-индикатор.
- [ ] **F4.5** Кэширование фронтенда: ETag для статики, gzip (если Python поддерживает).
- [ ] **F4.6** Удаление legacy `WEB_HTML` из `hunt.py` (или оставить как emergency fallback).
- [ ] **F4.7** Финальное тестирование: проверка всех endpoints, переключение тем, работа на мобильном устройстве (dev tools).

**Критерий приёмки:** UI выглядит как на макете, работает быстро, стабильно, адаптивно. Legacy-код не мешает.

---

## 8. Риски и ограничения

1. **Zero-dependency constraint.** Фронтенд не использует React/Vue/Chart.js. Все графики — ручной SVG/Canvas. Это увеличивает объём работы по фазе 1 (графики) и фазе 3 (Analytics).
2. **Бэкенд — raw asyncio HTTP.** Нет middleware, CORS, gzip. Нужно аккуратно добавлять заголовки и обработку больших файлов (`config.yaml` / `ratings.json`).
3. **Совместимость со старым UI.** `WEB_HTML` должен оставаться fallback до полной готовности фазы 4.
4. **psutil.** Может не быть установлен в окружении пользователя. Нужен fallback через `/proc` или graceful degradation.
5. **Settings reload.** Изменение `config.yaml` требует перезапуска health-loop или всего процесса. Нужно сделать runtime-apply для ключевых параметров (`interval`, `timeout`, `country_filter`).

---

## 9. Заметки по реализации

- **Соглашение о коде:**
  - Python: PEP 8, типизация `-> dict` / `-> list` там, где уже есть.
  - JS: camelCase, `const/let`, стрелочные функции. Без `var`.
  - CSS: BEM-подобный нейминг (`.card`, `.card--dark`, `.card__title`).
- **Флаги:** Использовать существующую `country_flag()` (Unicode regional indicators). На фронтенде — функция `flag(code)` уже есть.
- **Цвета:**
  - Light primary: `#4F46E5` (indigo-600)
  - Light success: `#10B981` (emerald-500)
  - Light danger: `#EF4444` (red-500)
  - Light warning: `#F59E0B` (amber-500)
  - Light border: `#E5E7EB` (gray-200)
  - Dark primary: `#6366F1` (indigo-500)
  - Dark surface: `#1A1D24` (gray-900)
- **Иконки:** Встроенные SVG-спрайты в `index.html` (symbol/use). 16×16 и 24×24. Не подключать внешние библиотеки иконок.

---

*Документ составлен на основе макетов от 07.06.2026. Для начала работы рекомендуется запустить Фазу 0.*
