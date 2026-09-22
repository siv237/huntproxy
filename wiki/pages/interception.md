---
updated: 2026-09-22
commit: ae6e94b
tags: [entity]
---

# Перехват трафика (interception)

Две вкладки страницы `#/interception`: **общий** перехват всей машины (был
раньше) и **выборочный** — по списку ресурсов. Оба режима взаимоисключающие по
смыслу (общий REDIRECT ловит всё), но управляются отдельно; выборочный —
основной.

## Общий режим (whole-machine)

- Хендлер `hunt/handlers/interception.py`: `GET /api/interception`,
  `POST /api/interception/apply|stop`.
- `_interception_readiness` — root, iptables-legacy/iptables, cgroup v2,
  исполняемый `setup_iptables.sh`, запущенный transparent и его порт.
- `_handle_interception_apply` — hard gate по `ready` (409), затем
  `setup_iptables.sh start`, connectivity-probe (8.8.8.8:53 / 1.1.1.1:443) и
  авто-`stop` при потере связи. Состояние — `data/transparent_state.json`.
- Цепочка `HUNTPROXY_REDIRECT` в `nat/OUTPUT`, исключения по uid/cgroup/
  локальным сетям/`OWN_IP`, дефолт — redirect всего outbound TCP на 17477.

## Выборочный режим (selective)

- **Домен-модуль** `hunt/interception_selective.py` (не миксин — бюджет
  миксинов фиксирован): таблицы `interception_resources`, `interception_entries`,
  `interception_config` в `state.db`; CRUD, нормализация адресов, DNS-резолв
  (`socket.getaddrinfo`, только IPv4), агрегат активных адресов, запись
  ipset-файла.
- **Ядро/сверка** `hunt/interception_reconcile.py`: чтение реального состояния
  iptables/ipset (`actual_state`), запуск `setup_iptables.sh`,
  reconnect-probe, `reconcile_on_startup`, фоновый `resolver_loop`.
- **Хендлер** `hunt/handlers/interception_selective.py`: статус, конфиг,
  CRUD ресурсов, apply/stop/panic/reconcile. POST-действия идут через
  `_handle_selective_post` (dispatch по суффиксу пути).

### Модель

Ресурс — именованная группа адресов (домены/субдомены `*.x`/IP), с флагом
`enabled`. **Общий выключатель** (`selective_enabled`) применяет/снимает правила
целиком; **индивидуальный** переключатель ресурса меняет состав набора.
Эффективно: `master AND resource.enabled`. Адрес, заданный доменом, резолвится в
IP и перепроверяется фоновой задачей по `resolve_interval_sec` (дефолт 300с,
мин. 30). Резолв запускается **сразу при создании/изменении** ресурса, а
`apply` при нулевом числе адресов сам вызывает `resolve_all_enabled` — чтобы
свежедобавленный ресурс не отдавал 409 «no resolved addresses». У резолва
таймаут 10с на адрес.

### Правила

- `setup_iptables.sh start --selective --ipset-file FILE [--iface IFACE]
  [--drop-quic] [--redirect-ports P1,P2]` — цепочка `HUNTPROXY_SELECTIVE` в
  `nat/OUTPUT`: по умолчанию `RETURN`, `REDIRECT` для адресов из ipset
  `huntproxy_selective`. Без ipset — fallback на одиночные правила по `-d`.
- **Дефолт портов — `443`**, а не «весь TCP»: многие апстрим-прокси (напр.
  Squid) отвечают `403 ERR_ACCESS_DENIED` на `CONNECT host:80`, из-за чего
  перехваченный HTTP даёт пустой ответ и `502 no upstream`. Для 443 CONNECT
  проходит.
- `--iface IFACE` (или автодетект из default-route) ограничивает перехват
  исходящим интерфейсом — как в рабочем примере `-o eth0`. Пишется в state.
- Исключение прокси-трафика по cgroup (`--exclude-cgroup huntproxy
  --cgroup-pid PID`) — защита от петли, когда route ведёт напрямую к цели.
- `--drop-quic` — цепочка `HUNTPROXY_SELECTIVE_QUIC` в `filter/OUTPUT`, дропает
  UDP/443 для выбранных адресов.
- `stop` снимает обе цепочки и уничтожает ipset.

### Сверка реального состояния

Источник истины — ядро, а не state-файл: `actual_state()` парсит
`iptables -C/-S` и `ipset list`. `reconcile_on_startup` (вызывается из
`hunt/main.py` после восстановления раннеров) убирает остаточные правила, если
режим выключен (иначе при незапущенном transparent порвётся сеть), и помечает
`pending`, если включён, но правил нет. UI показывает `mismatch`
(`leftover`/`pending`) и кнопку сверки.

### Планировщик и бэкап

- Отдельного `task_type` нет: `resolver_loop` стартует из `main.py`
  (`start_resolver`), интервал — из конфига.
- Таблицы ресурсов внесены в группу `interception` в `BACKUP_GROUPS`
  (`hunt/backup.py`).

## API (см. [api](api.md))

`GET /api/interception/selective`, `POST /api/interception/selective/{config,
apply,stop,panic,reconcile}`, `GET|POST /api/interception/resources`,
`POST|DELETE /api/interception/resources/<id>`, `POST .../<id>/toggle|resolve`.

## Frontend

`web/js/pages/interception.js` — табы через `ui.tabs` (`web/js/components.js`).
Вкладка «Общий» сохраняет прежние карточки; «Выборочный» — master-статус,
конфиг, добавление ресурса, список с toggle/резолвом/редактированием/удалением.
Методы — `web/js/api.js` (`interception*`). Локали — 6 языков.

## См. также

- [proxy-server](proxy-server.md) — TransparentRunner и маршрутизация.
- [api](api.md) — каталог эндпоинтов.
- [frontend](frontend.md) — устройство страниц и `ui.tabs`.
