---
updated: 2026-09-22
commit: ae6e94b
tags: [concept]
---

# Синхронизация прод ← dev

## Правило (без вариаций)

- Код правит агент **только в dev**: `/home/user/prj/huntproxy`.
- Прод — `/opt/huntproxy`; **руками в его файлы не лезем**.
- **«обнови прод» / «деплой»** = одна команда из dev:
  `sudo .venv/bin/python scripts/compare_env.py --sync`
- Готово, если **`RESULT: IDENTICAL`**. Нет — показать отличия и остановиться.
- **«коммить»** = `git add -A && git commit && git push origin main` в dev, затем
  прод приводится к origin штатным `/opt/huntproxy/update.sh`.
- Не трогать `data/`, `config.yaml`, `.venv`, `.git`; не запускать `uninstall.sh`.

## `scripts/compare_env.py` — один инструмент сверки и синхронизации

Без флагов — read-only сверка двух деревьев (пофайлово, sha256), рантайм
игнорируется (`.git`, `data*`, `.venv`, `node_modules`, кэши, `config.yaml`,
логи, `.tmp`, `package-lock.json`). Вывод: `identical`, `only in DEV`,
`only in PROD`, `different content`; exit 0 — идентично, 1 — различия.

С флагом `--sync` (нужен root):

1. сравнивает dev и prod;
2. копирует изменённые и новые файлы dev → prod (`*.sh` — 0755, остальное 0644);
3. удаляет из прода файлы, которых нет в dev (только проектные, рантайм не
   трогается);
4. `systemctl restart huntproxy`;
5. сверяет заново и печатает `RESULT`.

Полезные варианты:

```
python scripts/compare_env.py                      # только сверка
sudo python scripts/compare_env.py --sync          # привести прод к dev + рестарт
sudo python scripts/compare_env.py --sync --no-restart
python scripts/compare_env.py --json
```

## Почему это не ломает работу прода с git

Скрипт никогда не касается `.git`, `data/`, `config.yaml`, `.venv`. Обновление
через origin (`/opt/huntproxy/update.sh`: fetch → `git reset --hard origin/main` →
бандл → рестарт) продолжает работать; перед этим полезно закоммитить и запушить
dev, тогда после `update.sh` прод = origin.

## БД прода

`/opt/huntproxy/data/` (`state.db`, `stats.db` + WAL/SHM) исключена из git
(`.gitignore`) и скриптом не трогается. Бэкап при необходимости:

```bash
sudo sqlite3 /opt/huntproxy/data/state.db ".backup '/tmp/kilo/state.db.bak'"
sudo sqlite3 /opt/huntproxy/data/stats.db ".backup '/tmp/kilo/stats.db.bak'"
```

## Проверка после синхронизации

```bash
systemctl is-active huntproxy
.venv/bin/python scripts/compare_env.py            # ожидаем RESULT: IDENTICAL
```
