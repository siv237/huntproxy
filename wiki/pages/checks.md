---
updated: 2026-09-17
commit: b028d67
tags: [concept]
---

# Конвейер проверки прокси

## Hunt-цикл

`_hunt_cycle` (`hunt/hunt_cycle.py:8-29`) последовательно проходит фазы
(`hunt/state.py:47-59`): `downloading → blacklists → validating → health → done`,
плюс `paused`/`idle`. Параллельно крутится `_canary_loop`.

- `_hunt_download_phase` (`hunt/hunt_cycle.py:31-38`) — скачать источники прокси.
- `_hunt_blacklist_phase` (`:40-67`) — IP-ЧС и блоклисты.
- `_hunt_validate_phase` (`:69-85`) — `_validate_all(raw)`, затем фаза health.
- `_auto_pause_if_internet_down` (`:87-106`) — canary-проверка, пауза/сброс.

Управление: `start_hunt/stop_hunt/pause_hunt/resume_hunt/skip_phase`
(`hunt/hunt_control.py:8-90`), `_gather_skip_aware` (`:110-134`) умеет
прерывать gather и убивать download-подпроцессы.

## `_validate_all` (`hunt/check_validation.py:71-144`)

Очередь + фиксированный пул воркеров `max(1, parallel)`, семафор `parallel`,
глобальный таймаут `total*(effective_timeout+10)//parallel+60`, поддержка skip
и отмены. В конце `_save_state`, `_save_working_file`, `_push_history`.

## `_check_one` — шаги (`hunt/check_validation.py:146-193`)

1. `_detect_protocol` (`:25-34`): порт 1080/10808/9050 → socks5, 4145 → socks4,
   иначе http.
2. Blacklist → `_handle_blacklisted` (`:155-157`).
3. Ожидание `_pause_event` при `_internet_suspect`.
4. Параллельно `_check_proxy` и `_check_ssl` через `asyncio.gather(...,
   return_exceptions=True)` (`:164-168`).
5. `_merge_check_results` (`:36-69`): HTTP — индекс 0, SSL — 1, fraud — 2;
   при падении HTTP берётся SSL-результат; для не-SOCKS без CONNECT `ok=False`.
6. Fast-fail при `fast_fail and not ok and not ssl_ok` (`:170-176`), авто-пауза.
7. `_measure_check_speed` при успехе (`:183`).
8. `_record_check_result` (`:243-282`): счётчики, `_update_rating`, прогресс.

## Пробы

### HTTP/SOCKS — `_check_proxy` (`hunt/check_proxy.py:11-45`)
- `_outbound_connect` (через канал, если активен) → `_check_socks_proxy`
  (`:47-80`) или `_check_http_proxy` (`:82-126`).
- SOCKS: `_socks4_test`/`_socks5_test` + `_socks_egress` (отдельный туннель к
  `ip-api.com:80`, `hunt/check_geo.py:83-131`).
- HTTP: `GET http://ip-api.com/json/?fields=query,city,isp,country,hosting,proxy,mobile`
  абсолютным URI.
- `_authoritative_egress` (`hunt/check_geo.py:60-81`): прямой lookup заявленного
  IP; при противоречии страны `ok=False` (защита от geo-spoofing), fail-open.

### TLS-прокси — `_check_ssl` (`hunt/check_ssl.py:10-61`)
Подключение с `start_tls` к самому прокси, `CONNECT ip-api.com:80` либо plain
GET; префикс `CONNECT_OK` выставляет `supports_connect`. Контекст без проверки
сертификата (`_make_ssl_ctx`, `:132-140`); проверочный — `_ssl_ctx_verified`.

### MITM — `_check_mitm_via` (`hunt/check_mitm.py:97-145`)
Свежее соединение к прокси, туннель на :443 к каждому из
`MITM_TEST_HOSTS = ("www.google.com","www.wikipedia.org","ya.ru")`
(`check_mitm.py:21`), TLS-апгрейд с верификацией: `clean` / `mitm` /
`None`. Флаг ставится только при `reached>=2 and bad==reached` (`:141`) с
проверкой доверия канала (`_channel_tls_baseline_trusted`, `:151-187`).
Коммит `8496c53` заменил старую проверку через curl к 2ip.ru.

**Fix (коммит `f18b8b5`):** раньше все цели шли по одной сессии, и провал TLS-
верификации рвал туннель — последующие цели становились недостижимы, `reached`
не доходил до 2, и MITM-прокси никогда не помечались. Теперь при известном
`host` каждая цель получает свежее соединение (`owns=True`,
`hunt/check_mitm.py:119-127`).

### Скорость — `check_speed.py`
Серверы `SPEED_SERVERS` (`hunt/state.py:231`), семафор `speed_parallel`, общий
дедлайн 45с. Три способа: plain GET, CONNECT :80, CONNECT :443+TLS
(`_speed_single`, `:69-82`). Чтение чанками 64 КиБ с ранним выходом при
throughput < 5 KB/s после grace 3с (`_read_speed_stream`, `:193-238`).

### Fraud — `hunt/fraudscore.py`
proxycheck.io, raw-скор 0–100. Используется как справочная величина;
рейтинг строит флаги ip-api. Ручная проба — `/api/proxy/fraud?addr=&force=`
(`hunt/handlers/proxy.py:187`).

## Health-check

`_health_check` (`hunt/health_check.py:18-42`): guard `_health_running`, при
активном hunt ставит ручную паузу, кандидаты — `pool_eligible`. Параллелизм
`health_parallel` (дефолт 20), общий таймаут, затем save и `_push_history`
(`_run_health_checks`, `:67-110`). Состояние hunt сохраняется/восстанавливается
через `_save_health_state`/`_restore_health_state` (`:44-65`, `:112-144`), в
`finally` — авто-резюм.

`_revalidate_stale_proxies` (`:227-304`) — ре-чек живых прокси с `last_check`
старше часа.

## Автопауза и канал

- Canary: каждые 15с TCP-проба `canary_hosts` (`hunt/canary.py:9-57`), alive =
  больше половины. Пишет `canary_history`, детектит смену IP/ISP.
- `effective_timeout` (`hunt/channel.py:94-104`): при активном канале
  `max(base, 25)` — Tor строит цепочку 8–20с.
- Fast-fail: обрыв коннекта <0.3с трактуется как «провайдер/сеть», не как
  мёртвый прокси (`hunt/check_proxy.py:22-25`).

## ⚠ Найденный дефект: отсутствуют `_socks4_test`/`_socks5_test`

Вызовы есть в `hunt/check_proxy.py:49,51` и `hunt/check_speed.py:56,58`, но
определений в репозитории нет (`hasattr(HuntState, '_socks5_test') == False`).
Определения жили в `hunt/check_mitm.py` и были удалены коммитом `8496c53`,
а вызовы остались. Эффект: `AttributeError`, который в
`asyncio.gather(..., return_exceptions=True)` (`hunt/check_validation.py:164-168`)
поглощается и трактуется как неуспех — **SOCKS-прокси систематически не
проходят проверку**. Требует подтверждения и отдельного фикса.

## Мёртвый код (наблюдения)

- `run_startup_cycle` (`hunt/health_check.py:306-362`) не вызывается —
  `main.py` запускает только планировщик (`hunt/main.py:63-66`).
- Legacy-циклы `_health_loop`, `_ip_blacklist_loop`, `_history_loop`
  (`hunt/health_loops.py`) не запускаются — заменены планировщиком.
