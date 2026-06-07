# huntproxy

Локальный каскадный прокси-сервер с прозрачным режимом.

**Суть:** поднимает HTTP/SOCKS5 прокси на `127.0.0.1`, который ходит наружу через живые US-прокси из пула. Умеет прозрачно перехватывать трафик через iptables.

## Быстрый старт

```bash
# 1. Запуск
./huntproxy start

# 2. Проверить, что работает
curl --proxy http://127.0.0.1:8080 http://httpbin.org/ip

# 3. Или через SOCKS5
curl --socks5 127.0.0.1:1080 http://httpbin.org/ip
```

В системе выставить прокси `127.0.0.1:8080` (HTTP) или `127.0.0.1:1080` (SOCKS5).

## Команды

| Команда | Описание |
|---|---|
| `./huntproxy start` | Запустить сервер + менеджер пула |
| `./huntproxy status` | Показать состояние пула |
| `./huntproxy list` | Список живых прокси |
| `./huntproxy refresh` | Принудительно обновить пул прокси |
| `./huntproxy blacklist` | Показать заблокированные прокси |
| `./huntproxy blacklist --add IP:PORT --reason "медленный"` | Заблокировать прокси |
| `./huntproxy blacklist --remove IP:PORT` | Разблокировать |

## Порты (по умолчанию)

| Порт | Тип | Назначение |
|---|---|---|
| `8080` | HTTP proxy | Для браузера / curl |
| `1080` | SOCKS5 proxy | Для приложений с SOCKS |
| `9090` | Transparent | Для iptables-редиректа (выключен по умолчанию) |

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

**Перед включением:** раскомментируй `transparent` → `enabled: true` в `config.yaml`.

Исключаются из редиректа: локальные сети (10.x, 192.168.x, 172.16.x), localhost, мультикаст.

Если используешь VPN — задай `OWN_IP` чтобы не зациклить трафик:

```bash
sudo OWN_IP=10.8.0.2 ./setup_iptables.sh start
```

## Как работает пул прокси

1. `proxy_refresh.sh` скачивает списки с GitHub (8 источников) и проверяет каждый прокси — оставляет только живые US.
2. `proxy_manager.py` переодически (раз в 10 минут) запускает refresh и (раз в 2 минуты) делает health-check всего пула.
3. 3 фейла подряд → прокси уходит в blacklist на 5 минут. После 3-го фейла остаётся в blacklist-файле навсегда.
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
  http:
    listen: "127.0.0.1:8080"    # Поменять порт если занят
  transparent:
    enabled: true                # Включить прозрачный режим

proxies:
  refresh:
    interval: 600                # Интервал обновления пула (сек)
  health_check:
    interval: 120                # Интервал проверки живых прокси (сек)
  selection:
    strategy: round_robin        # round_robin | random
    max_failures: 3              # Фейлов до blacklist
    cooldown: 300                # Время доступа после фейла (сек)
```

## Файлы состояния

| Файл | Описание |
|---|---|
| `~/proxychain/proxies/working.txt` | Живые US-прокси (IP:PORT COUNTRY) |
| `~/proxychain/proxies/blacklist.txt` | Заблокированные прокси |
| `~/proxychain/proxies/stats.json` | Статистика по каждому прокси |
| `~/.local/share/huntproxy/huntproxy.log` | Логи |
