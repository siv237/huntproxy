---
updated: 2026-09-22
commit: f2f2dd9
tags: [entity]
---

# Перехват трафика (interception)

Страница `#/interception` — четыре вкладки: **Общий** (редирект всей машины),
**Выборочный** (только выбранные ресурсы), **Журнал** (перехваченные соединения)
и **Активные правила** (реальное состояние ядра).

## Два режима — альтернативы

Режимы **взаимоисключающие**, потому что полный перехват поглощает выборочный
(выбранные адреса — подмножество всего трафика):

- при включённом **«Общем»** вкладка «Выборочный» **скрывается**;
- включение «Общего» **автоматически** выключает выборочный; ресурсы и настройки
  выборочного при этом сохраняются;
- при включённом **«Выборочном»** вкладка «Общий» остаётся доступной;
- включить выборочный при активном «Общем» нельзя (`POST /api/interception/
  selective/apply` → 409).

## Общий режим (whole-machine)

- Хендлер `hunt/handlers/interception.py`: `GET /api/interception`,
  `POST /api/interception/apply|stop`.
- `_interception_readiness` — root, iptables-legacy/iptables, cgroup v2,
  исполняемый `setup_iptables.sh`, запущенный transparent и его порт.
- `_handle_interception_apply` — hard gate по `ready` (409), затем
  `setup_iptables.sh start`, connectivity-probe (8.8.8.8:53 / 1.1.1.1:443) и
  авто-`stop` при потере связи.
- Статус отдаётся через `_interception_status()`: при `mode == "selective"` в
  файле состояния флаг `active` **маскируется** в `false`, чтобы включение
  выборочного не зажигало «Общий».
- Цепочка `HUNTPROXY_REDIRECT` в `nat/OUTPUT`, исключения по uid/cgroup/
  локальным сетям/`OWN_IP`. Состояние — `data/transparent_state.json`.
- `stop` снимает правила и, если выборочный был включён, сбрасывает
  `selective_enabled` (иначе остался бы «включён, но правил нет»).

## Выборочный режим (selective)

- **Домен-модуль** `hunt/interception_selective.py` (не миксин — бюджет
  миксинов фиксирован): таблицы `interception_resources`, `interception_entries`,
  `interception_config` в `state.db`; CRUD, нормализация адресов, DNS-резолв
  (`socket.getaddrinfo`, только IPv4), агрегат активных адресов, запись
  per-policy spec-файла.
- **Ядро/сверка** `hunt/interception_reconcile.py`: чтение реального состояния
  iptables/ipset (`actual_state`), дамп правил (`active_rules`), запуск
  `setup_iptables.sh`, connectivity-probe, `reconcile_on_startup`, фоновый
  `resolver_loop`.
- **Хендлер** `hunt/handlers/interception_selective.py`: статус, конфиг,
  CRUD ресурсов, apply/stop/reconcile. POST-действия идут через
  `_handle_selective_post` (dispatch по суффиксу пути).

### Модель

Ресурс — именованная группа адресов (домены/субдомены `*.x`/IP) с флагом
`enabled` и политикой:

- `auto = true` (по умолчанию): перехватывается весь TCP к IP ресурса, транспорт
  определяется автоматически;
- `auto = false` + `ports`: только указанные порты, обычный CONNECT.

Эффективно: `selective_enabled AND resource.enabled`. Домен резолвится в IP и
перепроверяется по `resolve_interval_sec` (дефолт 300с, мин. 30). Резолв
запускается сразу при создании/изменении ресурса, а `apply` при нулевом числе
адресов сам вызывает `resolve_all_enabled`; таймаут резолва 10с на адрес.

### Правила

- `setup_iptables.sh start --selective --ipset-spec FILE [--iface IFACE]
  [--drop-quic]` — цепочка `HUNTPROXY_SELECTIVE` в `nat/OUTPUT`. Спека: строки
  `auto <ip>` (весь TCP) или `<port> <ip>` (только порт). На каждую политику
  свой ipset: `huntproxy_sel_auto` / `huntproxy_sel_p<port>`; объединённый
  `huntproxy_sel_all` — для QUIC-дропа.
- **HTTP/80 через прокси работает только в режиме `auto`**: транспарент
  распознаёт plaintext HTTP и отправляет forward-запрос без CONNECT
  (стандартный Squid запрещает `CONNECT host:80` → `403`).
- `--iface IFACE` (или автодетект из default-route) ограничивает перехват
  исходящим интерфейсом. Пишется в state.
- Исключение прокси-трафика по cgroup (`--exclude-cgroup huntproxy
  --cgroup-pid PID`) — защита от петли.
- `--drop-quic` — цепочка `HUNTPROXY_SELECTIVE_QUIC` в `filter/OUTPUT`, дропает
  UDP/443 для выбранных адресов.
- `stop` снимает обе цепочки, jump’ы и уничтожает все наборы `huntproxy_sel_*`
  (и легаси `huntproxy_selective`).

### Transparent-раннер

`hunt/transparent_runner.py`: для dst из авто-ресурсов подглядывает первые байты
(TLS/иное → CONNECT, HTTP → forward без CONNECT); для ручных ресурсов — CONNECT.
При отказе upstream и включённом `fallback_direct` пускает напрямую; в журнал
пишет сработавшее правило и имя ресурса.

### Сверка реального состояния

Источник истины — ядро: `actual_state()` парсит `iptables -C/-S` и `ipset list`.
`reconcile_on_startup` (из `hunt/main.py`) снимает остатки, если режим выключен, и
помечает `pending`, если включён, но правил нет. Остановка transparent-прокси
(`POST /api/transparent/stop`) снимает все правила и наборы и сбрасывает
`selective_enabled`.

## Рестарт и самозащита (loop prevention)

Правила перехвата переживают рестарт службы, а исключение самого прокси держится
на cgroup `huntproxy`, куда при apply кладётся **PID** процесса. После рестарта PID
новый, и без переприменения исходящие самого прокси тоже заворачивались бы на
17477 — петля, 100% CPU, «отвалился интернет».

`reenforce_on_startup()` (вызывается из `hunt/main.py` после
`reconcile_on_startup`) при старте:
- если прозрачный прокси запущен и режим включён (общий `active` в
  `transparent_state.json` либо `selective_enabled`) — заново применяет правила с
  **текущим** PID: пересобирает цепочки и возвращает самоисключение;
- если применение не удалось — снимает правила (машина не остаётся без сети);
- если прозрачный прокси не поднялся, а правила есть — снимает их, чтобы не было
  «чёрной дыры».

## Журнал перехвата

Таблица: Время · Клиент · **Приложение** · Ресурс · Правило · Назначение · Статус
· Маршрут · Трафик.

- **Приложение** — для локального трафика: по исходному `ip:port` ищется сокет в
  `/proc/net/tcp`, через inode → PID берётся имя процесса (`transparent_runner.
  _local_process`, кэш ~2 c). Для удалённых (шлюзовых) клиентов процесса нет —
  прочерк.
- **Назначение** — к IP в скобках добавляется обратный DNS (PTR), если он есть
  (`_ptr_lookup`, асинхронно, кэш, таймаут 2 c; при отсутствии — без скобок).

## Вкладка «Активные правила»

`GET /api/interception/selective/rules` → `active_rules()` показывает **реальное**
состояние ядра, а не только наши правила: все правила таблиц `nat` и `filter` в
обоих бэкендах (`iptables-legacy` и `iptables`/nft — на этой машине наши цепочки
в legacy, а DOCKER/Multipass в nft) и все ipset-наборы с членами. Возвращает
список `[line, ours]`; `ours = true` только для строк, внесённых системой
(`HUNTPROXY*`, наборы `huntproxy_*` и их адреса). Фронтенд подсвечивает `ours`,
остальное показывает как есть — поэтому вкладка честно отражает состояние при
включённом и выключенном перехвате. Если правил нет — показывается «нет».

## API (см. [api](api.md))

`GET /api/interception/selective`, `GET /api/interception/selective/rules`,
`POST /api/interception/selective/{config,apply,stop,reconcile}`,
`GET|POST /api/interception/resources`,
`POST|DELETE /api/interception/resources/<id>`,
`POST .../<id>/toggle|resolve`.

## Frontend

`web/js/pages/interception.js` (табы через `ui.tabs`):

- «Общий» — прежние карточки (readiness, команды, toggle). Вкладка «Выборочный»
  скрывается, когда активен «Общий».
- «Выборочный» — master-статус, конфиг, добавление/список ресурсов.
- «Журнал» — таблица с фильтрами по ресурсу и статусу.
- «Активные правила» — дамп правил с подсветкой наших строк.

Скрытие/показ вкладки — `applyModeVisibility()` по данным `/api/interception`.
Методы — `web/js/api.js` (`interception*`). Локали — 6 языков.

## См. также

- [proxy-server](proxy-server.md) — TransparentRunner и маршрутизация.
- [api](api.md) — каталог эндпоинтов.
- [frontend](frontend.md) — устройство страниц и `ui.tabs`.
