---
updated: 2026-09-17
commit: 06630a5
tags: [concept]
---

# Модель ProxyRating и формула рейтинга

## `ProxyRating`

Датакласс в `hunt/models.py:54-103` — ядро ранжирования, лист без зависимостей
от hunt. Ключевые поля:

| Поле | Смысл |
|---|---|
| `address`, `protocol` | `host:port`, http/https/socks4/socks5 |
| `checks_total`, `checks_ok`, `last_status` | статистика проверок |
| `latency_sum/count`, `last_latency` | задержки |
| `speed_sum/count`, `speed_fails` | агрегаты скорости (KB/s) |
| `consecutive_fails` | фейлы подряд (grace-период) |
| `in_blacklist`, `blacklist_reason` | ручной ЧС — жёсткое исключение |
| `ip_blacklist_reason/hits/sources` | совпадения egress-IP |
| `is_favorite` | защита от авто-очистки |
| `supports_connect`, `ssl_supported`, `mitm_suspect` | возможности/подозрения |
| `egress_*`, `listen_*` | гео/ISP выхода и самого узла |
| `fraud_hosting/proxy/mobile`, `fraud_score_raw` | антифрод-флаги и справочный скор |
| `fraud_checked_ts`, `fraud_raw_ts`, `fraud_attempt_ts` | свежесть fraud-данных |
| `sr_ewma`, `latency_ewma`, `speed_ewma` | сглаженные значения (EWMA) |
| `source_ids` | источники, откуда пришёл прокси |

Методы: `update_reliability`, `update_latency`, `update_speed`,
`record_traffic_fail` (троттлинг), `score`, `score_breakdown`, `to_dict`,
`to_pool_dict` (`hunt/models.py:205-434`).

## Формула score (актуальная, v2 + антифрод v3)

Реализация — `score()` (`hunt/models.py:236-251`):

```
checks_total == 0  -> 0.0
in_blacklist       -> 0.0

base     = _base_points()          # 0..75, аддитивно
speed_f  = _speed_factor()         # 0..1, мультипликативно
modifier = _modifier_factor()      # 0.10..1.35 (антифрод×MITM×IP-ЧС)

ok:
    score = clamp(base * speed_f * modifier, 0, 100)
failed:
    если не in_grace -> 0.0
    grace_ratio = max(0, 1 - consecutive_fails / GRACE_FAILS)
    score = clamp(base * speed_f * modifier * 0.3 * grace_ratio, 0, 100)
```

### База — `_base_points()` (`hunt/models.py:299-310`), максимум 75

- `sr * 40` — надёжность (`sr_ewma`, иначе `success_rate`);
- `20 * max(0, 1 - lat/10)` — задержка (`latency_ewma`, иначе `latency_avg`);
- `+5` за `ssl_supported`;
- `+5` за `supports_connect`;
- `+5` за SOCKS-порт/протокол.

### Скорость — `_speed_factor()` (`hunt/models.py:277-297`)

- `sp = speed_ewma` (если ≥0, иначе `speed_avg`), норма `SPEED_FACTOR_NORM=150 KB/s`;
- `sp>0`: `min(1, sp/150)`, при `speed_fails>0` дополнительно `× max(0.25, 1-0.35*fails)`;
- `sp==0`: SOCKS → `0.5`; при фейлах → `0`; `<5 ok` → `0.5`; иначе `0`.

### Множитель — `_modifier_factor()` (`hunt/models.py:312-319`)

```
f = 1 - 0.01 * (fraud_score - 30)      # FRAUD_PENALTY_PER_POINT, BOOST_CENTER
f = clamp(f, 0.10, 1.35)
if mitm_suspect:       f *= 0.5
if ip_blacklist_hits:  f *= max(0.25, 0.75 ** hits)
```

Антифрод-шкала (`fraud_score`, `hunt/models.py:113-128`): `+20 mobile`,
`+40 hosting`, `+70 proxy`, cap 100. Отсюда: clean resident ×1.30, DC ×0.90,
proxy ×0.60, 100 → ×0.30.

`fraud_failcheck` (`hunt/models.py:130-137`): флагов нет или они старше
`FRAUD_FRESH_SECONDS = 6ч` → множитель 0.30 (fail-closed). `fraud_score_raw`
от proxycheck.io информационный — в формулу не входит, пишется только в
`fraud_score_raw` (`hunt/check_rating_apply.py:42-52`).

### Grace-период

`GRACE_FAILS = 50` (`hunt/models.py`). Прокси, который уже работал и словил
менее 50 фейлов подряд, не обнуляется, а получает `×0.3×grace_ratio`
(коммит `f577308` — «grace период для проверенных прокси»).

## EWMA

`EWMA_ALPHA = 0.25` для успеха, задержки и скорости (`update_*`,
`hunt/models.py:205-220`). Значения `<0` означают «не инициализировано», и
формула откатывается на средние. Переход на EWMA и множители вместо вычитаний —
коммит `7b5623c` («Рейтинг v2»).

## Разбор для UI

`score_breakdown()` (`hunt/models.py:321-359`) отдаёт компоненты формулы, а
`/api/proxy/<addr>` (`hunt/handlers/proxy.py:257`) возвращает их во фронт —
карточка прокси рисует разбор как есть, без дублирования формулы в JS.

## Эволюция формулы (важно для истории)

- `docs/ANALYSIS.md:171-180` хранит **устаревшую** аддитивную формулу
  (`sr*50 + ...`) — это первый вариант.
- Актуальная описана в `docs/proxy-check-workflow.md:160-184` и `:463-502`.
- Расхождение `ANALYSIS.md` с кодом — известное противоречие документации;
  верить коду `hunt/models.py`.
