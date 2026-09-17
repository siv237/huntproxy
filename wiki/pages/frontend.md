---
updated: 2026-09-17
commit: b028d67
tags: [entity]
---

# Web UI (frontend)

SPA на vanilla JS без фреймворка и сборщика. Вся раздача — свой HTTP-сервер
(`hunt/server.py`), статика из `web/`.

## Структура `web/`

| Путь | Содержимое |
|---|---|
| `web/index.html` | SVG-спрайт иконок, sidebar, topbar, `#router-view` |
| `web/css/theme.css` | CSS-переменные светлой/тёмной темы |
| `web/css/layout.css` | каркас (sidebar/topbar/content) |
| `web/css/components.css` | компоненты |
| `web/js/i18n.js` | переводы, плюрализация |
| `web/js/api.js` | тонкая обёртка над fetch (~150 методов) |
| `web/js/router.js` | hash-навигация `#/page` |
| `web/js/charts.js` | самописные SVG-графики |
| `web/js/components.js` | `ui`-хелперы (`el`, `table`, `card`, `badge`, форматтеры) |
| `web/js/pages/*.js` | 28 страниц + 2 карточки-компонента |
| `web/js/pages.bundle.js` | конкатенация страниц (генерируется) |
| `web/locales/` | `index.json` + 6 языков |

Порядок загрузки: i18n → api → router → charts → components → pages.bundle →
app (`web/index.html:318-324`).

## Ядро

- **router.js**: `router.register(name, factory)`, `navigate` → `#/page`,
  `resolve()` перерисовывает контейнер и чистит `window._pageIntervals`
  (`web/js/router.js:37-78`). Карта заголовков `titles` — 26 записей.
- **i18n.js**: языки en/de/es/fr/ru/zh (`web/js/i18n.js:21`), fallback en;
  prefetch всех локалей (`_startPrefetch`, `:15-27`); `t(key, params)` и
  `tp(key, count)` с русской плюрализацией (`:94-139`).
- **components.js**: `ui.el`, `ui.card`, `ui.table` (сортировка), `ui.badge`,
  `ui.sparkline`-форматтеры, `escHtml`, `routeBadge`, `statusPill`, `viaBadge`.
  Делегированный клик по `.route-badge[data-addr]` открывает карточку прокси
  (`web/js/components.js:360-365`).
- **app.js**: тема (`data-theme`, localStorage), секции sidebar, глобальные
  поллеры (`startPollers`, `:150-164`): events 2с, traffic 2с, ping 1с,
  direct/channel 3с, canary 30с, version 60с. `pollEvents` рассылает
  `CustomEvent('hunt-events')`.

## Кэширование

SWR-кэша нет. Локально: интервалы страниц через `window._pageIntervals`,
`perfCache` в памяти и `localStorage['overview.counts']` с TTL 5 мин
(`web/js/pages/overview.js:625-659`), `historyCache`
(`web/js/pages/proxy-control.js:8`). Серверная сторона даёт TTL/single-flight
для snapshot (1.5с), proxy/status (2с), traffic/summary (10с),
traffic/search (5с + stale-while-revalidate).

## Страницы

28 навигируемых: overview, hunt, server, proxy-control, connectivity,
interception, routes, traffic-flow, pac, proxy-pool, proxies, favorites,
analytics, custom-proxies, proxy-sources, blacklist, ip-blacklists, blocklists,
domain-lists, logs, actions, settings, schedules, downloads, api, about.
Компоненты: `proxy-card.js` (`window.proxyCard.show`), `client-card.js`.

Секции sidebar: overview, engine, proxies, lists, insights, system
(`web/index.html:66-223`).

## Локали

6 языков, ~1094 ключа на язык. Тесты полноты
(`tests/test_locales.py:79-131`) проверяют наличие каждого используемого ключа
во всех языках и запрещают хардкод кириллицы в JS.

## Бандл страниц

`scripts/build_js_bundle.py` конкатенирует `web/js/pages/*.js` в
`pages.bundle.js` (сортировка для детерминизма). `--check` возвращает 1 при
устаревшем бандле; проверяется тестом `tests/test_js_bundle.py`. Коммит
`ca68131` («бандл страниц, prefetch локалей»).
