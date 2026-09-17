# Журнал вики (log)

Append-only журнал **операций вики** (ingest / query / lint), не история кода.
История разработки проекта — [pages/changelog.md](pages/changelog.md).
Формат: `## [ГГГГ-ММ-ДД] <ingest|query|lint> | <тема>` + пункты; парсится
`grep "^## \[" log.md | tail -5`. Только дописывать, прошлые записи не править.

## [2026-09-17] ingest | Bootstrap вики

- Восстановлен changelog по `git` (267 коммитов) → [pages/changelog.md](pages/changelog.md).
- Созданы страницы: overview, state, api, scheduler, data-sources, monitoring,
  frontend, rating, checks, proxy-server, routing, infra, quality, sources-docs.
- Схема ведения вики перенесена в `AGENTS.md`; `index.md` оставлен чистым
  каталогом; `log.md` отведён под журнал операций — устранено дублирование
  истории (`log.md` ↔ `changelog.md` ↔ `git`).
- Зафиксирован незакоммиченный MITM-reconnect fix и список открытых дефектов →
  [pages/wip.md](pages/wip.md).

## [2026-09-17] ingest | MITM-reconnect fix и синхронизация ревизии

- Коммит `f18b8b5` (свежее соединение на каждую MITM-цель) влит в вики →
  [checks](pages/checks.md), [changelog](pages/changelog.md); из
  [wip](pages/wip.md) убран как закрытый.
- `.gitignore` поглотил `dataN/` (коммит `b028d67`); `data0/` больше не
  числится незакоммиченным.
- `commit` во frontmatter всех страниц поднят до `b028d67`; исправлены
  расхождения (источников 23, тест-модулей 38) и stale-утверждения в `AGENTS.md`
  (66 модулей, ~30 миксинов, 11 handler-модулей, no-op pre-commit).
