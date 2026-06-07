# huntproxy

Инструмент поиска, проверки и управления пулом прокси с Web UI.

**Суть:** скачивает списки прокси из открытых источников, проверяет их на доступность и скорость, фильтрует по стране (US), и предоставляет Web-панель для мониторинга и управления пулом. Поддерживает настройку HTTP/SOCKS5/transparent прокси через `config.yaml`.

## Быстрый старт

```bash
# 1. Запуск Web UI (foreground)
./hunt.sh

# 2. Или как демонона
./daemon.sh start

# 3. Открыть Web-панель
# http://127.0.0.1:17177/
```

## Команды (daemon.sh)

| Команда | Описание |
|---|---|
| `./daemon.sh start` | Запустить hunt-демон |
| `./daemon.sh stop` | Остановить демон |
| `./daemon.sh restart` | Перезапустить демон |
| `./daemon.sh status` | Показать состояние демона |
| `./daemon.sh log [N]` | Показать последние N строк лога (по умолчанию 20) |

Управление пулом прокси (список, refresh, blacklist) — через Web-панель на `http://127.0.0.1:17177/`.

## Порты (по умолчанию)

| Порт | Тип | Назначение |
|---|---|---|
| `17177` | Web UI | Панель управления пулом прокси |
| `17277` | HTTP proxy | HTTP CONNECT прокси |
| `17377` | SOCKS5 proxy | SOCKS5 прокси |
| `17477` | Transparent | Для iptables-редиректа (выключен по умолчанию) |

## Прозрачный режим

Перенаправляет ВЕСЬ TCP-трафик на портах 80/443 через прокси. Приложения не нужно настраивать.

```bash
# Включить (нужен root)
sudo ./setup_iptables.sh start

# Проверить правила
sudo ./setup_iptables.sh status

# Выключить
sudo ./setup_iptables.sh stop
```

**Перед включением:** установи `transparent_enabled: true` в `config.yaml`.

Исключаются из редиректа: локальные сети (10.x, 192.168.x, 172.16.x), localhost, мультикаст.

Если используешь VPN — задай `OWN_IP` чтобы не зациклить трафик:

```bash
sudo OWN_IP=10.8.0.2 ./setup_iptables.sh start
```

## Как работает пул прокси

1. `hunt.py` скачивает списки с GitHub (8 источников) и проверяет каждый прокси — оставляет только живые US.
2. Периодически (раз в 5 минут) запускает refresh пула и (раз в 2 минуты) делает health-check живых прокси.
3. 3 фейла подряд → прокси уходит в blacklist. Cooldown — 5 минут.
4. Выбор прокси — round-robin по живому пулу.

## Установка как сервис

```bash
sudo ./install.sh
systemctl status huntproxy
journalctl -u huntproxy -f
```

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
  validate_interval: 300          # Интервал обновления пула (сек)
  health_interval: 120            # Интервал health-check (сек)
  strategy: round_robin           # round_robin | random
  max_failures: 3                 # Фейлов до blacklist
  cooldown: 300                   # Cooldown после фейла (сек)
```

## Файлы состояния

| Файл | Описание |
|---|---|
| `data/working.txt` | Живые US-прокси (IP:PORT COUNTRY) |
| `data/blacklist.txt` | Заблокированные прокси |
| `data/ratings.json` | Рейтинги и статистика по каждому прокси |
| `data/huntproxy.log` | Логи |
