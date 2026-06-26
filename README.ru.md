<p align="center">
  <img src="web/assets/biglogo.png" alt="huntproxy" width="760">
</p>

# huntproxy

🌐 [EN](README.md) · [RU](README.ru.md) · [DE](README.de.md) · [ES](README.es.md) · [FR](README.fr.md) · [ZH](README.zh.md)

Инструмент поиска, проверки и управления пулом прокси с Web UI.

**Суть:** скачивает списки прокси из 24 открытых источников, проверяет каждый на доступность, скорость и геолокацию, фильтрует по стране, ведёт рейтинги и блэклисты, и предоставляет HTTP/SOCKS5/transparent прокси-сервер с балансировкой и маршрутизацией по доменам. Всем можно управлять через Web-панель.

## Быстрый старт

```bash
curl -fsSL https://raw.githubusercontent.com/siv237/huntproxy/main/install.sh | bash
```

Инсталлятор установит зависимости, клонирует репозиторий в `/opt/huntproxy`, создаст venv и зарегистрирует systemd-сервис `huntproxy.service`.

После установки:

```bash
sudo systemctl enable --now huntproxy   # автозапуск + старт
# Web UI: http://127.0.0.1:17177/
```

## Возможности

### Поиск и проверка прокси (Hunt)

- Скачивает прокси из **24 открытых источников** (GitHub-репозитории) — HTTP, HTTPS, SOCKS4, SOCKS5.
- Валидация каждого прокси: доступность, задержка, скорость скачивания, поддержка HTTPS/CONNECT, страна и ISP (GeoIP через ip-api.com).
- Детект **MITM**-подозрительных узлов (подмена SSL/заголовков).
- Фильтр по стране (по умолчанию US, переключается в один клик).
- Конвейер параллельной проверки (`parallel` потоков) с живым прогрессом.
- Периодический refresh пула и health-check живых прокси.

### Рейтинги и блэклисты

- Каждый прокси получает **рейтинг 0–100** на основе задержки, скорости, SSL/CONNECT-бонусов, штрафа за MITM и провалы speed-тестов.
- **IP-блэклисты** (Emerging Threats, FireHOL, IPsum, Blocklist.de): egress-IP прокси сверяется со скачанными списками — чем больше попаданий, тем ниже рейтинг.
- **Ручной блэклист** — жёсткое исключение прокси (3 фейла подряд → авто-блэклист с cooldown).
- Избранное (Favorites) — защищённые от авто-очистки прокси.

### Прокси-сервер и балансировка

- **HTTP CONNECT** (порт `17277`) — обычный HTTP-прокси.
- **SOCKS5** (порт `17377`).
- **Transparent** (порт `17477`) — для iptables-редиректа всего TCP-трафика.
- Выбор upstream: прямой (Direct), конкретный прокси, или **пул** (round-robin / random по лучшему рейтингу).
- Cascade-режимы: пул, конкретный прокси или custom-прокси.

### Маршрутизация по доменам

- **Domain Lists** — списки доменов с шаблонами (`example.com`, `.example.com`, `exact:`, `*.example.com`).
- **Routes** — привязка доменных списков к маршруту (Direct / Proxy / Pool / Custom).
- **Traffic Flow** — визуализация текущего пути трафика через движок маршрутизации.
- **Custom Proxies** — корпоративные, Tor (`127.0.0.1:9050`), anti-ban сервисы с тестом соединения.

### Прозрачный режим

Перенаправляет ВЕСЬ TCP-трафик на портах 80/443 через прокси — приложения настраивать не нужно.

```bash
sudo ./setup_iptables.sh start    # включить (нужен root и transparent_enabled: true в config.yaml)
sudo ./setup_iptables.sh status   # проверить правила
sudo ./setup_iptables.sh stop     # выключить
```

Исключаются локальные сети (10.x, 192.168.x, 172.16.x), localhost, мультикаст. При использовании VPN задай `OWN_IP`, чтобы не зациклить трафик:

```bash
sudo OWN_IP=10.8.0.2 ./setup_iptables.sh start
```

### Блоклисты для обхода цензуры

- **Country Blocklists** — IP/CIDR и доменные списки заблокированного внутри/снаружи страны.
- Встроены российские списки (РКН-блокировки, геоблок иностранных сервисов) — трафик к заблокированным ресурсам автоматически идёт через прокси.
- Скачивание списков можно пускать через прокси (`via proxy`).

### Мониторинг и аналитика

- **Overview** — дашборд с метриками пула, загрузкой CPU/RAM/disk, топ-странами и живой производительностью.
- **Traffic Monitor** — живой поток запросов, success-rate, топ-направлений, распределение по маршрутам.
- **Analytics** — размер пула во времени, трафик, средняя задержка, тепловая карта проверок (72ч).
- **Connectivity** — мониторинг интернет-соединения с canary-хостами, детект падения и смены IP.
- **Logs / Actions** — системные логи и журнал действий оператора со снапшотами счётчиков.

### Планировщик (Schedules)

Единый движок фоновых задач: hunt-цикл, refresh IP-блэклистов, refresh блоклистов, health-check, запись истории, очистка мёртвых прокси, бэкап БД. Каждую задачу можно включать/выключать, менять интервал и запускать вручную.

### Прочее

- Тёмная/светлая тема Web UI, мультиязычность (EN / RU).
- Экспорт/импорт прокси, бэкап и восстановление БД.
- API для интеграции (документация в разделе API).

## Команды

### Запуск вручную

```bash
./hunt.sh                  # foreground, http://127.0.0.1:17177/
./hunt.sh --public         # слушать на всех интерфейсах
./hunt.sh --kill           # остановить запущенный экземпляр на порту
```

### systemd

```bash
sudo systemctl start huntproxy
sudo systemctl enable huntproxy      # автозапуск
sudo systemctl status huntproxy
journalctl -u huntproxy -f
sudo systemctl stop huntproxy
sudo systemctl restart huntproxy
```

### daemon.sh (альтернатива systemd)

| Команда | Описание |
|---|---|
| `./daemon.sh start` | Запустить демон |
| `./daemon.sh stop` | Остановить демон |
| `./daemon.sh restart` | Перезапустить демон |
| `./daemon.sh status` | Состояние демона |
| `./daemon.sh log [N]` | Последние N строк лога (по умолч. 20) |

## Порты (по умолчанию)

| Порт | Тип | Назначение |
|---|---|---|
| `17177` | Web UI | Панель управления пулом прокси |
| `17277` | HTTP proxy | HTTP CONNECT прокси |
| `17377` | SOCKS5 proxy | SOCKS5 прокси |
| `17477` | Transparent | Для iptables-редиректа (выключен по умолчанию) |

## Конфигурация

Всё в `config.yaml`. Основные настройки:

```yaml
server:
  web_listen: "127.0.0.1:17177"
  http_listen: "127.0.0.1:17277"
  socks5_listen: "127.0.0.1:17377"
  transparent_listen: "127.0.0.1:17477"
  transparent_enabled: false

proxies:
  validate_interval: 300          # интервал обновления пула (сек)
  validate_parallel: 100          # параллельных проверок при refresh
  health_interval: 120            # интервал health-check (сек)
  health_parallel: 30
  strategy: round_robin           # round_robin | random
  max_failures: 3                 # фейлов до блэклиста
  cooldown: 300                   # cooldown после фейла (сек)
  us_only: true                   # фильтр по стране
```

Источники прокси, IP-блэклисты и блоклисты редактируются в `sources/default.ini` (выживает при сбросе `data/`) или через Web-панель.

## Файлы состояния

| Файл | Описание |
|---|---|
| `data/state.db` | SQLite — рейтинги, события, история, настройки |
| `data/working.txt` | Живые прокси (IP:PORT COUNTRY) |
| `data/blacklist.txt` | Заблокированные прокси |
| `data/ratings.json` | Рейтинги и статистика по каждому прокси |
| `data/huntproxy.log` | Логи |

## Технологии

- **Backend:** Python 3, asyncio, SQLite
- **Web UI:** Vanilla JS, CSS custom properties, Chart.js
- **Протоколы:** HTTP CONNECT, SOCKS4, SOCKS5, transparent proxy
- **Данные:** GeoIP (ip-api.com), speed test, MITM-детекция

## Тесты

```bash
./test.sh
```

## Лицензия

MIT
