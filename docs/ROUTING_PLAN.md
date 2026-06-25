# План: Маршрутизация прокси по доменным спискам

## Суть проблемы

Сейчас `ProxyRunner._connect_upstream()` (`hunt.py:1615`) работает в 3 режимах:
1. `direct_mode=True` — **весь** трафик напрямую
2. `active_proxy_addr` задан — **весь** трафик через один upstream-прокси
3. fallback — **весь** трафик через лучший прокси из пула

Нет возможности разделить трафик: «эти домены через прокси, остальные напрямую».

## Решение: Domain Routing Rules

### 1. Модель данных

```
DomainList:
  id: str                    # уникальный идентификатор (slug)
  name: str                  # человекочитаемое название
  domains: list[str]         # список доменов/паттернов
  route: str                 # "direct" | "proxy:<addr>" | "pool"
  enabled: bool              # вкл/выкл

  # Паттерны доменов:
  #   "example.com"          — точное совпадение + поддомены (*.example.com)
  #   ".example.com"         — только поддомены
  #   "exact:example.com"    — строго точное совпадение (без поддоменов)
  #   "*.example.com"        — то же что .example.com

DefaultRoute: str            # маршрут для доменов не попавших ни в один список
                              # "direct" | "proxy:<addr>" | "pool"
```

**Приоритет правил**: первый подходящий список (порядок = приоритет). Более специфичные правила ставь выше.

### 2. Хранение

**SQLite** (постепенный переход с JSON-файлов, списки будут крупные — Роскомнадзор ~5M записей):

```sql
CREATE TABLE domain_lists (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT 'manual',  -- manual | url
    url TEXT DEFAULT '',                     -- source URL (Phase 2)
    route TEXT NOT NULL DEFAULT '',          -- direct | pool | proxy:addr
    enabled INTEGER NOT NULL DEFAULT 1,
    priority INTEGER NOT NULL DEFAULT 0,     -- 0 = highest, порядок правил
    created_at REAL NOT NULL DEFAULT 0,
    updated_at REAL NOT NULL DEFAULT 0
);

CREATE TABLE domain_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    list_id TEXT NOT NULL REFERENCES domain_lists(id) ON DELETE CASCADE,
    pattern TEXT NOT NULL,                   -- example.com | .example.com | exact:example.com | *.example.com
    UNIQUE(list_id, pattern)
);
CREATE INDEX idx_domain_entries_list ON domain_entries(list_id);
CREATE INDEX idx_domain_entries_pattern ON domain_entries(pattern);

CREATE TABLE routing_config (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
-- keys: routing_enabled (true/false), default_route (direct/pool/proxy:addr)
```

**Почему SQLite, не JSON:**
- Роскомнадзор-листы: миллионы записей, JSON будет тормозить на чтение/запись
- Индексы на pattern → быстрый поиск
- Каскадное удаление: удалил список → все entries ушли
- Atomic writes — нет частично записанных файлов
- Одна БД `data/stats.db` уже используется — расширяем её

### 3. Логика маршрутизации (ядро)

Модификация `ProxyRunner._connect_upstream(host, port)`:

```python
async def _connect_upstream(self, host, port):
    route = self._resolve_route(host)    # <-- новый метод
    return await self._connect_by_route(route, host, port)

def _resolve_route(self, host: str) -> str:
    if not self._routing_enabled:
        # старое поведение: direct_mode или active_proxy
        if self.direct_mode:
            return "direct"
        if self.active_proxy_addr:
            return f"proxy:{self.active_proxy_addr}"
        return "pool"
    
    for dlist in self._domain_lists:
        if not dlist["enabled"]:
            continue
        if self._domain_matches(host, dlist["domains"]):
            return dlist["route"]
    
    return self._default_route  # default из domain_lists.json

def _domain_matches(self, host: str, patterns: list) -> bool:
    host_lower = host.lower()
    for pattern in patterns:
        p = pattern.lower().strip()
        if p.startswith("exact:"):
            if host_lower == p[6:]:
                return True
        elif p.startswith("."):
            if host_lower.endswith(p) or host_lower == p[1:]:
                return True
        elif p.startswith("*."):
            suffix = p[1:]  # .example.com
            if host_lower.endswith(suffix) or host_lower == p[2:]:
                return True
        else:
            if host_lower == p or host_lower.endswith("." + p):
                return True
    return False
```

### 4. API endpoints

| Endpoint | Method | Описание |
|----------|--------|----------|
| `/api/routing/status` | GET | Статус маршрутизации + default_route + lists |
| `/api/routing/enable` | POST | Включить маршрутизацию по спискам |
| `/api/routing/disable` | POST | Отключить (вернуть к direct/active_proxy) |
| `/api/routing/default` | POST | Установить default_route |
| `/api/routing/lists` | GET | Все списки доменов |
| `/api/routing/lists` | POST | Создать новый список |
| `/api/routing/lists/<id>` | GET | Получить список по ID |
| `/api/routing/lists/<id>` | POST | Обновить список |
| `/api/routing/lists/<id>` | DELETE | Удалить список |
| `/api/routing/lists/<id>/toggle` | POST | Включить/выключить список |
| `/api/routing/reorder` | POST | Изменить порядок списков (priority) |
| `/api/routing/test` | POST | Тест: какой маршрут для данного домена? |

### 5. UI — две вкладки: Routes + Domain Lists

Разделяем UI на **две самостоятельные вкладки** в сайдбаре:

#### Вкладка 1: Routes (Маршруты) — `routes.js`

Управление логикой маршрутизации — какой трафик куда направляется.

**Секция 1: Routing Mode**
- Переключатель: Off / On
- Default route: dropdown (Direct / Pool / Выбранный прокси)
- Индикатор текущего режима

**Секция 2: Active Rules (таблица маршрутов)**
| Priority | Domain List | Route | Enabled | Actions |
|----------|-------------|-------|---------|---------|
| 1 | Blocked Sites | Pool | ✓ | ↑ ↓ ✕ |
| 2 | Corporate | proxy:1.2.3.4:80 | ✓ | ↑ ↓ ✕ |

- Каждая строка — привязка доменного списка к маршруту
- Кнопки ↑↓ для приоритета
- Клик на Domain List → переход на вкладку Domain Lists
- Кнопка "+ Add Route" → выбор списка + выбор маршрута

**Секция 3: Test Route**
- Поле ввода домена + кнопка "Test"
- Результат: "twitter.com → Pool (via list: Blocked Sites)"

**Секция 4: Quick Templates**
- Кнопки-шаблоны: "Social media", "Streaming", "Corporate"

#### Вкладка 2: Domain Lists (Листы доменов) — `domain-lists.js`

Управление списками доменов — сущностями, которые потом привязываются к маршрутам.

**Секция 1: Списки (таблица)**
| Name | Domains | Source | Used In Routes | Actions |
|------|---------|--------|----------------|---------|
| Blocked Sites | 3 domains | manual | 1 route | ✏ ✕ |
| Corporate | 2 domains | manual | 1 route | ✏ ✕ |

- Кнопка "+ Add List" → модалка с полями: name + textarea для доменов
- Source: `manual` (сейчас) / `url` (Phase 2 — автозагрузка)
- "Used In Routes" — сколько маршрутов ссылаются на этот список

**Секция 2: Создание/редактирование списка (inline или модалка)**
- Name: текстовое поле
- Domains: textarea (один домен на строку)
- Подсказка по паттернам: `example.com`, `.example.com`, `exact:example.com`, `*.example.com`

**Phase 2 — Source: URL**
- Поле URL для автозагрузки списка
- Интервал обновления
- Кнопка "Fetch Now"
- Статус последней загрузки

### 6. Интеграция с ProxyRunner

Модификации в `hunt.py`:

1. **ProxyRunner** — добавить поля:
   - `_routing_enabled: bool = False`
   - `_domain_lists: list[dict] = []`
   - `_default_route: str = "direct"`

2. **Загрузка при старте**: `HuntState.__init__` → `_load_domain_lists()`

3. **Сохранение состояния**: `_save_state` → сохранять routing-конфигурацию

4. **Метод `_resolve_route`**: вызывается из `_connect_upstream` для определения маршрута

5. **Метод `_connect_by_route`**: роутит трафик по маршруту:
   - `"direct"` → прямое подключение
   - `"pool"` → выбор из пула (существующая логика failover)
   - `"proxy:addr"` → через конкретный прокси (существующая логика single proxy)

6. **Логирование**: `_log()` расширить полем `route` — чтобы видеть в client log какой маршрут был выбран

### 7. Порядок реализации

| Шаг | Что | Файлы | Статус |
|-----|-----|-------|--------|
| 1 | Модель данных + SQLite-таблицы domain_lists/domain_entries/routing_config | `hunt.py` (_init_db) | ✅ |
| 2 | HuntState: CRUD списков + routing config + _resolve_route + _domain_matches | `hunt.py` (HuntState) | ✅ |
| 3 | ProxyRunner: _connect_by_route, интеграция с _connect_upstream | `hunt.py` (ProxyRunner) | ✅ |
| 4 | API endpoints /api/routing/* + /api/domain-lists/* | `hunt.py` (HuntServer._route) | ✅ |
| 5 | API-методы в api.js | `web/js/api.js` | ✅ |
| 6 | UI вкладка Routes | `web/js/pages/routes.js` | ✅ |
| 7 | UI вкладка Domain Lists | `web/js/pages/domain-lists.js` | ✅ |
| 8 | Навигация: 2 новых пункта в сайдбаре + иконки | `web/index.html` | ✅ |
| 9 | XSS-исправления: escHtml, event delegation, textContent | `routes.js`, `domain-lists.js`, `components.js` | ✅ |
| 10 | Бизнес-логика: preserve route/enabled, clone objects, loading guard | `routes.js`, `domain-lists.js` | ✅ |
| 11 | Мёртвый код удалён: rules.js | — | ✅ |
| 12 | Логирование маршрута в traffic_log | `hunt.py` (ProxyRunner._log) | ⬜ Phase 2 |
| 13 | Интеграция с прозрачным режимом (iptables) | `setup_iptables.sh` | ⬜ Phase 2 |

### 8. Обратная совместимость

- При `_routing_enabled=False` поведение **идентично текущему** (direct_mode / active_proxy / pool)
- Существующие API `/api/proxy/direct`, `/api/proxy/select` продолжают работать
- `domain_lists.json` опционален — при отсутствии routing просто выключен
- Страница Routes показывает текущий режим (routing off) и предлагает включить
- Существующая заглушка Rules заменяется на две вкладки: Routes + Domain Lists

---

## Часть 2: Custom Proxies — специализированные прокси для маршрутизации

### Проблема

Сейчас маршрутизация поддерживает route_type `proxy:addr` где addr — просто `host:port`.
Но на практике нужны **именованные** прокси с разными протоколами и авторизацией:
- Корпоративный HTTP-прокси с логином/паролем → для corp.example.com
- Tor SOCKS5-прокси (127.0.0.1:9050) → для .onion и специфичных доменов
- Антибан-прокси HTTPS → для заблокированных соцсетей
- Любой другой named прокси с авторизацией

Нужно: CRUD прокси, проверка связи, интеграция с Routes через dropdown по имени.

### 1. Модель данных

```
CustomProxy:
  id: str                    # уникальный slug (auto из name)
  name: str                  # человекочитаемое: "Корпоративный", "Tor", "Антибан"
  protocol: str              # "socks5" | "http" | "https"
  host: str                  # адрес прокси
  port: int                  # порт
  username: str              # логин (может быть пустым)
  password: str              # пароль (хранится в БД, маскируется в UI)
  test_url: str              # проверочный URL для теста (напр. corp.example.com)
  last_check_at: float       # UNIX timestamp последней проверки
  last_check_status: str     # "ok" | "fail" | "timeout" | ""
  last_check_latency: int    # мс, -1 если fail
  enabled: bool              # вкл/выкл (выключенный не участвует в маршрутизации)
  created_at: float
  updated_at: float
```

**Route ref**: вместо `proxy:1.2.3.4:8080` используем `custom:<id>` — маршрутизация
разрезолвит id → (protocol, host, port, username, password) и подключится.

### 2. SQLite

```sql
CREATE TABLE custom_proxies (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    protocol TEXT NOT NULL DEFAULT 'socks5',  -- socks5 | http | https
    host TEXT NOT NULL,
    port INTEGER NOT NULL,
    username TEXT NOT NULL DEFAULT '',
    password TEXT NOT NULL DEFAULT '',
    test_url TEXT NOT NULL DEFAULT '',
    last_check_at REAL NOT NULL DEFAULT 0,
    last_check_status TEXT NOT NULL DEFAULT '',
    last_check_latency INTEGER NOT NULL DEFAULT -1,
    enabled INTEGER NOT NULL DEFAULT 1,
    created_at REAL NOT NULL DEFAULT 0,
    updated_at REAL NOT NULL DEFAULT 0
);
```

### 3. API endpoints

| Endpoint | Method | Описание |
|----------|--------|----------|
| `/api/custom-proxies` | GET | Список всех прокси (пароли замаскированы `****`) |
| `/api/custom-proxies` | POST | Создать прокси |
| `/api/custom-proxies/<id>` | GET | Получить прокси по ID (пароль замаскирован) |
| `/api/custom-proxies/<id>` | POST | Обновить прокси |
| `/api/custom-proxies/<id>` | DELETE | Удалить прокси |
| `/api/custom-proxies/<id>/toggle` | POST | Включить/выключить |
| `/api/custom-proxies/<id>/test` | POST | Проверить прокси: HTTP-запрос через него к test_url |

**POST/PUT body**:
```json
{
  "id": "corporate",
  "name": "Корпоративный прокси",
  "protocol": "http",
  "host": "proxy.corp.local",
  "port": 8080,
  "username": "user123",
  "password": "pass456",
  "test_url": "http://intraweb.corp.local/"
}
```

**GET ответ** — пароль всегда замаскирован:
```json
{
  "id": "corporate",
  "name": "Корпоративный прокси",
  "protocol": "http",
  "host": "proxy.corp.local",
  "port": 8080,
  "username": "user123",
  "password": "****",
  "test_url": "http://intraweb.corp.local/",
  "last_check_status": "ok",
  "last_check_latency": 145,
  "last_check_at": 1718000000,
  "enabled": true
}
```

**POST /custom-proxies/<id>/test ответ**:
```json
{
  "status": "ok",        // ok | fail | timeout | auth_fail
  "http_code": 200,
  "latency_ms": 145,
  "error": ""
}
```

### 4. Логика проверки прокси (`_test_custom_proxy`)

```python
async def _test_custom_proxy(proxy_id):
    proxy = get_custom_proxy(proxy_id)
    url = proxy["test_url"] or "http://httpbin.org/ip"
    
    start = time.monotonic()
    try:
        # Через прокси делаем HTTP GET к test_url
        # socks5 → aiohttp_socks, http/https → обычный CONNECT-туннель
        connector = make_connector(proxy)  # protocol, host, port, auth
        async with aiohttp.ClientSession(connector=connector) as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                latency = int((time.monotonic() - start) * 1000)
                status = "ok" if resp.status < 400 else "fail"
                return {"status": status, "http_code": resp.status, "latency_ms": latency}
    except asyncio.TimeoutError:
        return {"status": "timeout", "http_code": 0, "latency_ms": -1, "error": "timeout"}
    except aiohttp.ClientProxyConnectionError:
        return {"status": "fail", "http_code": 0, "latency_ms": -1, "error": "connection refused"}
    except aiohttp.ClientHttpProxyError:
        return {"status": "auth_fail", "http_code": 407, "latency_ms": -1, "error": "proxy auth required"}
```

Результат записывается в `last_check_*` поля прокси.

### 5. Интеграция с маршрутизацией

**Изменение route_type**: расширяем формат маршрутов:
- `direct` — напрямую
- `pool` — через пул
- `proxy:<host>:<port>` — **legacy**, оставляем для совместимости
- `custom:<proxy_id>` — через именованный кастомный прокси ← **НОВОЕ**

**`_connect_by_route`** — новый ветвление:
```python
if route.startswith("custom:"):
    proxy_id = route[7:]
    proxy = self._get_custom_proxy(proxy_id)
    if not proxy or not proxy["enabled"]:
        return await self._connect_by_route(self._default_route, host, port)
    return await self._connect_via_proxy(proxy, host, port)
```

**`_connect_via_proxy(proxy, host, port)`** — универсальный метод:
```python
async def _connect_via_proxy(self, proxy, host, port):
    protocol = proxy["protocol"]
    p_host, p_port = proxy["host"], proxy["port"]
    auth = (proxy["username"], proxy["password"]) if proxy["username"] else None
    
    if protocol == "socks5":
        return await self._connect_socks5(p_host, p_port, auth, host, port)
    elif protocol in ("http", "https"):
        return await self._connect_http_proxy(p_host, p_port, auth, host, port, tls=(protocol == "https"))
```

**Routes UI — dropdown маршрута**: при выборе route_type = "Custom Proxy" показываем
dropdown с именами кастомных прокси из `/api/custom-proxies`. Выбор записывает `custom:<id>`.

### 6. UI — вкладка Custom Proxies — `custom-proxies.js`

**Навигация**: новый пункт в сайдбаре с иконкой (shield/server).

**Секция 1: Таблица прокси**
| Name | Protocol | Address | Test URL | Status | Latency | Enabled | Actions |
|------|----------|---------|----------|--------|---------|---------|---------|
| Корпоративный | HTTP | proxy.corp.local:8080 | intraweb.corp.local/ | ✓ | 145ms | ✓ | ✏ 🔍 ✕ |
| Tor | SOCKS5 | 127.0.0.1:9050 | check.torproject.org | ✓ | 320ms | ✓ | ✏ 🔍 ✕ |
| Антибан | HTTPS | antiban.io:443 | twitter.com | ✗ fail | — | ✓ | ✏ 🔍 ✕ |

- 🔍 = кнопка теста (вызывает `/api/custom-proxies/<id>/test`)
- Status цвет: зелёный (ok), красный (fail/timeout), жёлтый (auth_fail), серый (не проверен)

**Секция 2: Редактор прокси (inline)**
- Name: текстовое поле → автогенерация slug в ID
- Protocol: dropdown (SOCKS5 / HTTP / HTTPS)
- Host + Port: два поля рядом
- Username + Password: два поля рядом
  - Password: `<input type="password">` + кнопка-глаз (toggle visibility)
- Test URL: текстовое поле с placeholder "http://example.com/" — **пользователь указывает
  конкретный проверочный URL**, который имеет смысл именно для этого прокси
  (напр. для корпоративного — intraweb.corp.local, для Tor — check.torproject.org)
- Кнопка "Save" + кнопка "Test"

**Секция 3: Подсказки**
- SOCKS5: для Tor, локальных SOCKS-прокси
- HTTP: для корпоративных прокси (часто с авторизацией)
- HTTPS: для прокси с TLS-обёрткой (антибан-сервисы)

### 7. Порядок реализации

| Шаг | Что | Файлы | Статус |
|-----|-----|-------|--------|
| 1 | SQLite-таблица custom_proxies | `hunt.py` (_init_db) | ✅ |
| 2 | HuntState: CRUD custom_proxies + _test_custom_proxy + _get_custom_proxy | `hunt.py` (HuntState) | ✅ |
| 3 | ProxyRunner: _connect_via_proxy (socks5/http/https + auth), route custom:<id> в _connect_by_route | `hunt.py` (ProxyRunner) | ✅ |
| 4 | API endpoints /api/custom-proxies/* | `hunt.py` (HuntServer._route) | ✅ |
| 5 | API-методы в api.js | `web/js/api.js` | ✅ |
| 6 | UI вкладка Custom Proxies | `web/js/pages/custom-proxies.js` | ✅ |
| 7 | Навигация: пункт Custom Proxies в сайдбаре + иконка | `web/index.html` | ✅ |
| 8 | Интеграция с Routes: dropdown custom proxy при выборе маршрута | `routes.js`, `components.js` | ✅ |
| 9 | Password mask/unmask в UI | `custom-proxies.js` | ✅ |

### 8. Зависимости

- **aiohttp-socks** или **python-socks** — для SOCKS5-подключений (проверить наличие в проекте)
- HTTP/HTTPS-прокси: CONNECT-туннель через существующий `aiohttp` (уже есть в проекте)
- Авторизация: Proxy-Authorization header для HTTP, username/password для SOCKS5

### 9. Расширения (Phase 2)

- Поддержка IP-адресов в списках (не только домены)
- Регулярные выражения для паттернов
- Импорт списков из URL (автообновление)
- Временные правила (TTL)
- Статистика по маршрутам (сколько трафика пошло через каждый)
- Интеграция с iptables: генерация правил исключений на основе списков
- Периодическая авто-проверка прокси (health check) с интервалом
- PAC/WPAD автоконфигурация корпоративных прокси
