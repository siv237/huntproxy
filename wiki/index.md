# Индекс вики huntproxy

Каталог всех страниц. Обновляется агентом при каждом ingest. Формат:
`[Название](pages/имя.md) — назначение · updated`. Схема и правила ведения —
раздел «LLM Wiki» в [AGENTS.md](../AGENTS.md). Читать каталог первым делом
при вопросе об устройстве проекта.

## Обзор

- [Обзор huntproxy](pages/overview.md) — назначение, стек, порты, карта
  подсистем и архитектура кода · 2026-09-17.

## Сущности (entities)

Классы, модули, сервисы, компоненты.

- [Состояние: HuntState и хранилище](pages/state.md) — композиция миксинов,
  две базы SQLite, события, действия, TrafficStats · 2026-09-17.
- [HTTP-сервер, роутер и API](pages/api.md) — HuntServer, Router, хелперы,
  полный каталог endpoints, кэши · 2026-09-17.
- [Планировщик задач](pages/scheduler.md) — SchedulerEngine, типы задач,
  дефолтные расписания, TaskExecutor, API · 2026-09-17.
- [Источники данных, загрузка и бэкап](pages/data-sources.md) —
  proxy-sources, IP-ЧС, блоклисты, stall-detection, backup/restore · 2026-09-17.
- [Мониторинг: снапшот, connectivity, события, трафик](pages/monitoring.md) —
  snapshot, canary, events/actions, TrafficStats, switch history · 2026-09-17.
- [Перехват трафика (interception)](pages/interception.md) — общий и выборочный
  перехват, ресурсы, ipset, сверка реального состояния · 2026-09-22.
- [Web UI (frontend)](pages/frontend.md) — структура `web/`, ядро, страницы,
  локали, бандл · 2026-09-17.

## Понятия (concepts)

Архитектурные решения, паттерны, механики.

- [Модель ProxyRating и формула рейтинга](pages/rating.md) — поля, формула
  score, EWMA, антифрод v3, grace · 2026-09-17.
- [Конвейер проверки прокси](pages/checks.md) — hunt-цикл, validate,
  health-check, MITM, speed, fraud, canary · 2026-09-17.
- [Прокси-серверы и выбор upstream](pages/proxy-server.md) — раннеры, пул,
  строгий fallback, канал, PAC, кастомные прокси, transparent · 2026-09-17.
- [Маршрутизация по доменам](pages/routing.md) — хранение, алгоритм
  `_resolve_route`, паттерны · 2026-09-17.
- [Инфраструктура и скрипты](pages/infra.md) — install/update/uninstall,
  daemon/hunt, iptables, конфигурация · 2026-09-17.
- [Тесты и контроль качества](pages/quality.md) — test.sh, уровни тестов,
  пороги, pre-commit · 2026-09-17.

## Источники (sources)

- [Источники проекта (что где читать)](pages/sources-docs.md) —
  README, MODULES.md, `docs/*.md`, `sources/default.ini`, `llm-wiki.md` · 2026-09-17.

## Сравнения и аналитика (analyses)

- [История разработки (восстановленный changelog по git)](pages/changelog.md) —
  267 коммитов, вехи по месяцам, ключевые архитектурные решения · 2026-09-17.
- [Открытые дефекты](pages/wip.md) — единый список незакрытого со ссылками на
  профильные страницы; незакоммиченного нет · 2026-09-17.

## Прочее

- [raw/](raw/README.md) — инвентарь исходников вики (только читать).
- [log.md](log.md) — журнал операций вики (append-only).
