---
updated: 2026-09-23
commit: 469f857
tags: [analysis]
---

# Открытые дефекты

Единый список незавершённого — чтобы перед правкой кода сразу видеть, что уже
известно и не закрыто. Детали и ссылки `файл:строка` — на профильных страницах.
Если список пуст — открытых дефектов нет.

## Открытые дефекты (pre-existing)

1. **`_socks4_test`/`_socks5_test` были не определены** — закрыто (см. ниже).
2. **`DOMAIN-KEYWORD`/`DOMAIN-REGEXP` без спец-семантики** — уходят в обычный
   паттерн. См. [routing](routing.md).
3. **Кастомный `https`-прокси не оборачивается в TLS** —
   `hunt/proxy_routing.py._connect_via_custom`. См. [proxy-server](proxy-server.md).
4. **`_failover_idx` не используется** — round-robin пула отсутствует, порядок
   детерминирован. См. [proxy-server](proxy-server.md).
5. **`hooks/pre-commit` не запускает тесты** (строка закомментирована). См.
   [quality](quality.md), [infra](infra.md).
6. **`docs/ANALYSIS.md` хранит устаревшую формулу рейтинга**. См.
   [sources-docs](sources-docs.md), [rating](rating.md).

## Закрыто в рабочем дереве (2026-09-23)

- **SOCKS-прокси не проходили проверку / не попадали в пул** — восстановлены
  `_socks4_test`/`_socks5_test` (`hunt/check_proxy.py`, обёртки над
  `hunt/conn.py`), исправлена длина домена в `_socks5_egress_handshake`
  (`hunt/check_geo.py`, 9→10), замер скорости SOCKS туннелируется на
  speed-сервер (`hunt/check_speed.py`). См. [checks](checks.md).

## Закрыто в рабочем дереве (незакоммичено, 2026-09-18)

- **Прогресс пула >100% (200%/1000%)** — устранено. Причины и правки:
  двойной запуск одной task_type планировщиком (`_launch_lock` в
  `hunt/scheduler.py`); ручной Hunt не прерывал чужие задачи
  (`hunt/manual_hunt.py`, `POST /api/hunt/start`); проверки не вставали на
  паузу без интернета (`hunt/scheduler_guard.py::_internet_gate`);
  потеря `counted` на retry fast_fail (`hunt/check_validation.py:171-179`).
  Детали — [scheduler](scheduler.md). Доказательства — `data*` прода.

## Закрыто в этой ревизии

- MITM-детектор не срабатывал из-за переиспользования соединения — исправлено
  (коммит `f18b8b5`, см. [checks](checks.md)).
- Runtime-каталоги `dataN/` (в т.ч. `data0/`, ~5.5 ГБ) добавлены в `.gitignore`.
