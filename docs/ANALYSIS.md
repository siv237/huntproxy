# huntproxy — система анализа проксей

## 1. Источники проксей

Прокси скачиваются из публичных GitHub-репозиториев (8 источников в `DEFAULT_SOURCES`):

```
monosans/proxy-list     — socks5, socks4, http
TheSpeedX/PROXY-List    — socks5, socks4, http
roosterkid/openproxylist — HTTPS
hookzof/socks5_list     — socks5
```

Каждый источник — plain-text файл со строками `ip:port`. После загрузки списки дедуплицируются.

---

## 2. Конфигурация

`config.yaml`, секция `hunt`:

| Параметр | Значение | Описание |
|----------|----------|----------|
| `parallel` | 30 | Одновременных проверок во время охоты |
| `timeout` | 8с | Таймаут подключения/ответа на одну проксю |
| `us_only` | true | Фильтр только US |
| `health_interval` | 180с | Интервал health-check живых проксей |
| `health_parallel` | 20 | Одновременных health-check'ов |

---

## 3. Этапы проверки одной прокси (`_check_proxy`)

### 3.1. TCP-коннект
```
asyncio.open_connection(host, port), timeout=8s
```
Не удался → `FAIL`. Удался → продолжаем.

### 3.2. Протокольный тест

**HTTP-прокси** (все порты кроме SOCKS-специфичных):
```
GET http://ip-api.com/json/ HTTP/1.0
Host: ip-api.com
```
Ответ парсится как JSON. Извлекаются:
- `country` — страна egress-IP
- `countryCode`
- `query` — egress IP
- `city`, `isp`

Условие успеха: JSON распарсился, есть поле `country`.

**SOCKS5** (порты 1080, 10808, 9050):
1. SOCKS5 handshake (no-auth: `\x05\x01\x00`)
2. SOCKS5 CONNECT `httpbin.org:443`
3. Проверка ответа от сервера

**SOCKS4** (порт 4145):
1. SOCKS4 CONNECT `httpbin.org:80`
2. Проверка ответа

Условие успеха для SOCKS: handshake + CONNECT прошли.
После успеха — отдельный запрос `_socks_egress()` для определения exit IP через SOCKS-туннель к `ip-api.com`.

### 3.3. Замер HTTP-latency (`http_latency`)

Время от начала TCP-коннекта до окончания парсинга ответа (НЕ включает CONNECT/MITM тесты). Для HTTP: после `json.loads()`, для SOCKS: после egress-запроса.

### 3.4. Геолокация сервера (`_resolve_geo`)

Параллельный асинхронный запрос к `http://ip-api.com/json/{host}` — определение страны/города/ISP самого прокси-сервера (не egress).

### 3.5. Фильтр по стране

Если `us_only=true` и страна egress ≠ `"United States"` → `FAIL`.
Если задан `country_filter` и не совпадает → `FAIL`.

### 3.6. CONNECT/HTTPS тест (`_check_proxy_connect`)

**HTTP**: `CONNECT 2ip.ru:443 HTTP/1.1` → проверка ответа `200`.  
**SOCKS**: повторный SOCKS-handshake + CONNECT к httpbin.org (второй раз, для надёжности).

Результат: `supports_connect = True/False`.

### 3.7. MITM-детектор

**HTTP**: `curl -x http://host:port https://2ip.ru -w %{ssl_verify_result}`  
Если curl возвращает ошибку ИЛИ `ssl_verify_result ≠ 0` → прокся подменяет SSL-сертификат → `mitm_suspect = True`.

**SOCKS**: то же самое через `socks5h://` или `socks4a://`.

### 3.8. Итог этапа

`_check_proxy` возвращает кортеж:
```
(ok, country, supports_connect, mitm_suspect, egress_dict, listen_dict, http_latency)
```

---

## 4. Замер скорости (`_measure_speed`)

### 4.1. Сервера (с fallback)

Пробуются по очереди, первый ответивший — результат:

| Сервер | Путь | Ожидаемый размер |
|--------|------|------------------|
| `speedtest.tele2.net` | `/512KB.zip` | 524,288 байт |
| `ipv4.download.thinkbroadband.com` | `/512KB.zip` | 524,288 байт |
| `testdebit.info` | `/1M.iso` | 1,048,576 байт |

### 4.2. Алгоритм одного сервера (`_speed_single`)

1. TCP-коннект к проксе
2. Для SOCKS: handshake
3. `GET http://{host}{path} HTTP/1.0` через проксю
4. Чтение всех данных (чанками по 64KB, таймаут 30с)
5. Остановка когда `total >= expected_size`

### 4.3. Валидация

Скорость засчитывается только если получено **≥ 80% ожидаемого размера**:
```
if total >= expected_size * 0.8:
    return total / elapsed / 1024.0   # KB/s
```
Иначе → 0.0 (переход к следующему серверу).

Если все 3 сервера не ответили → возврат 0.0.

---

## 5. Накопление статистики (`_update_rating`)

Вызывается после каждой проверки (и hunt, и health-check).

```python
r.checks_total += 1          # всего проверок
r.last_latency = latency     # последняя задержка

if ok:
    r.checks_ok += 1          # успешных
    r.latency_sum += latency  # сумма задержек
    r.latency_count += 1      # количество замеров
    r.last_status = "ok"
    
    if speed > 0:
        r.speed_sum += speed       # сумма скоростей
        r.speed_count += 1         # количество замеров
        r.last_speed = speed       # последняя скорость
        r.speed_fails = 0          # сброс счётчика провалов
    else:
        r.speed_fails += 1         # +1 к провалам скорости
else:
    r.last_status = "failed"
```

### Производные метрики

```
latency_avg = speed_sum / speed_count      (0 если нет замеров)
speed_avg   = speed_sum / speed_count      (0 если нет замеров)
success_rate = checks_ok / checks_total    (0 если не проверялась)
```

---

## 6. Формула рейтинга (`score`)

```python
score = max(0, sr * 50                           # п.1: база от success_rate
              + max(0, 100 - latency_avg*10)*0.5  # п.2: бонус за низкую задержку
              + 15 * has_connect                  # п.3: бонус за HTTPS/CONNECT
              - 30 * is_mitm                      # п.4: штраф за MITM
              + min(20, speed_avg/50)             # п.5: бонус за скорость (KB/s)
              - 40 * (speed_fails >= 3))          # п.6: штраф за 3+ провала скорости
```

### Разбор по компонентам

| Компонент | Формула | Диапазон | Описание |
|-----------|---------|----------|----------|
| База | `success_rate × 50` | 0–50 | Чем выше доля успешных проверок, тем больше |
| Задержка | `max(0, 100 - latency × 10) × 0.5` | 0–50 | 0мс → 50, 100мс → 45, 500мс → 25, 2с → 15, 10с → 0 |
| CONNECT | `+15` если `supports_connect` | 0 или 15 | HTTPS-прокси получают бонус |
| MITM | `−30` если `mitm_suspect` | 0 или −30 | Подмена сертификата — жёсткий штраф |
| Скорость | `min(20, speed_avg / 50)` | 0–20 | 50 KB/s → +1, 250 KB/s → +5, 1000 KB/s → +20 |
| Провалы скорости | `−40` если `speed_fails ≥ 3` | 0 или −40 | Три подряд нулевых замера → прокся не тянет трафик |

### Примеры расчёта

**Хорошая прокся** (37.49.224.15:3128):
```
sr=1.0, latency=1.26s, CONNECT, speed=295 KB/s, fails=0
= 50 + (100-12.6)×0.5 + 15 + min(20, 295/50) + 0
= 50 + 43.7 + 15 + 5.9
= 114.6
```

**Медленная с CONNECT** (185.200.188.234:10001):
```
sr=1.0, latency=1.4s, CONNECT, speed=4 KB/s, fails=0
= 50 + 43.0 + 15 + 0.08
= 108.0
```

**Быстрая без CONNECT** (74.176.195.135:80):
```
sr=1.0, latency=0.29s, !CONNECT, speed=?, fails=0
= 50 + 48.55 + 0 + speed_bonus
≈ 98.5 + speed
```

**Мёртвая по трафику** (3 провала скорости подряд):
```
sr=1.0, latency=1.5s, CONNECT, speed_fails=3
= 50 + 42.5 + 15 + 0 - 40
= 67.5
```

---

## 7. Циклы проверки

### 7.1. Охота (hunt cycle)

1. Скачивание списков из 8 источников
2. Дедупликация
3. Параллельная проверка (`parallel=30`) каждой прокси: `_check_proxy` → `_measure_speed` → `_update_rating`
4. Сохранение `ratings.json` + `working.txt`

### 7.2. Health-check

Каждые `health_interval=180с`:
1. Берутся все прокси со статусом `"ok"` и не в blacklist
2. Параллельная перепроверка (`health_parallel=20`): `_check_proxy` → `_measure_speed` → `_update_rating`
3. Сохранение состояния

### 7.3. Recheck (ручной)

По кнопке «recheck» в веб-интерфейсе или через API `/api/proxy/recheck?address=...`:
- Полный цикл `_check_proxy` + `_measure_speed` + `_update_rating` для одной прокси
- Немедленное сохранение

---

## 8. Критерии «прокся работает»

Прокся считается **рабочей** (`last_status == "ok"`) если **все** условия выполнены:

1. ✅ TCP-коннект успешен
2. ✅ Протокольный тест пройден (HTTP GET к ip-api.com / SOCKS handshake)
3. ✅ JSON ответа от ip-api.com распарсился (для HTTP)
4. ✅ Страна egress проходит фильтр (`us_only` / `country_filter`)
5. ✅ CONNECT тест пройден (для SOCKS — обязательно; для HTTP — опционально, но без него `supports_connect=false`)

Прокся **НЕ считается рабочей** если:
- ❌ Таймаут подключения
- ❌ Нет ответа / ответ не парсится
- ❌ Не та страна
- ❌ SOCKS: не прошёл CONNECT
- ❌ В blacklist'е

### Проблема ложных срабатываний

Текущая проверка (`_check_proxy`) тестирует **только один маленький HTTP-запрос** (~500 байт JSON от ip-api.com). Прокся может успешно ответить на этот запрос, но:
- Не пропускать другой трафик (белые списки URL)
- Рвать соединения на больших объёмах
- Быть нестабильной (работает через раз)

Для выявления таких проксей служит **speed test** (`_measure_speed`):
- 512KB–1MB загрузка с реальных speedtest-серверов
- Если 3 проверки подряд дают `speed=0` → штраф −40 к скору
- Прокся с высоким скором но нулевой скоростью быстро теряет позиции

---

## 9. Состояние и персистентность

Хранится в `data/ratings.json`:
```json
{
  "proxies": [{...}],
  "proxy_runner": {"direct_mode": false, "active_proxy_addr": "..."}
}
```

Каждая прокся — полный `to_dict()` объекта `ProxyRating`.

При перезапуске: `_load_state()` восстанавливает все поля, включая накопительные (`speed_sum`, `speed_count`, `speed_fails`, `latency_sum`, `latency_count`).

---

## 10. Веб-интерфейс

**Hunt web UI** (порт 17177):
- Таблица «top rated alive» — топ-30 живых проксей, сортировка по любой колонке
- Таблица «select upstream proxy» — все живые прокси для выбора
- Карточка «selected upstream» — детали выбранной прокси (score, latency, **KB/s**, success rate, checks)
- Кнопка «recheck» — принудительная перепроверка выбранной прокси
- Панель управления proxy-runner'ом (порт 17277)

**Колонки таблиц**: `#`, `proxy`, `country`, `latency`, `avg`, `KB/s`, `success`, `score`, `flags`, `ok`, `action`

---

## 11. API endpoints

| Путь | Описание |
|------|----------|
| `GET /api/snapshot` | Полное состояние охоты + топ-30 |
| `GET /api/proxy/alive` | Все живые прокси (рейтинг по убыванию) |
| `GET /api/proxy/status` | Статус proxy-runner'а |
| `POST /api/proxy/start?port=` | Запуск proxy-runner'а |
| `POST /api/proxy/stop` | Остановка |
| `POST /api/proxy/select?address=` | Выбор upstream-прокси |
| `POST /api/proxy/recheck?address=` | Принудительная перепроверка |
| `POST /api/hunt/start` | Запуск цикла охоты |
| `POST /api/hunt/stop` | Остановка |
| `POST /api/blacklist/add` | Добавить в blacklist |
| `POST /api/blacklist/remove` | Убрать из blacklist |
