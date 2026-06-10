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

### 9. Расширения (Phase 2)

- Поддержка IP-адресов в списках (не только домены)
- Регулярные выражения для паттернов
- Импорт списков из URL (автообновление)
- Временные правила (TTL)
- Статистика по маршрутам (сколько трафика пошло через каждый)
- Интеграция с iptables: генерация правил исключений на основе списков
