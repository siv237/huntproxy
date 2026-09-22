#!/usr/bin/env bash
#
# huntproxy updater — жёстко приводит прод к origin, не трогая настройки
# и данные (data/, config.yaml, .venv — в .gitignore).
#
# Поведение:
#   1. git fetch origin/<branch>;
#   2. git reset --hard origin/<branch> + git clean -fd — прод не хранит
#      собственных изменений, лишние (не игнорируемые) файлы удаляются;
#   3. зависимости (если изменился requirements.txt), пересборка JS-бандла,
#      проверка на месте ли настройки, перезапуск службы.
#
# Использование:
#   ./update.sh               жёстко привести прод к origin и перезапустить
#   ./update.sh --test        прогнать ./test.sh перед перезапуском
#   ./update.sh --no-restart  не перезапускать службу
#
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE="huntproxy"
BRANCH="${HUNT_UPDATE_BRANCH:-main}"
UNIT="/etc/systemd/system/$SERVICE.service"

ASSUME_YES=false
FORCE=false
RUN_TESTS=false
DO_RESTART=true

for arg in "$@"; do
    case "$arg" in
        -y|--yes)          ASSUME_YES=true ;;
        -f|--force)        FORCE=true ;;
        --test)            RUN_TESTS=true ;;
        --no-restart)      DO_RESTART=false ;;
        -h|--help)
            sed -n '2,24p' "$0" | sed 's/^# \{0,1\}//'
            exit 0
            ;;
        *)
            echo "Неизвестный аргумент: $arg (см. ./update.sh --help)" >&2
            exit 1
            ;;
    esac
done

c_ok()   { echo -e "  \033[32m✓\033[0m $*"; }
c_info() { echo -e "  \033[36m→\033[0m $*"; }
c_err()  { echo -e "  \033[31m✗\033[0m $*" >&2; }
c_warn() { echo -e "  \033[33m!\033[0m $*"; }

confirm() {
    # $1 — вопрос, $2 — значение по умолчанию (y/n)
    local def="$2" ans
    if $ASSUME_YES; then
        echo "  $1 (авто-подтверждение -y) — да"
        return 0
    fi
    if [ "$def" = "y" ]; then
        read -r -p "  $1 [Y/n] " ans
    else
        read -r -p "  $1 [y/N] " ans
    fi
    case "${ans,,}" in
        y|yes|д|да) return 0 ;;
        n|no|н|нет) return 1 ;;
        *) [ "$def" = "y" ] ;;
    esac
}

cd "$DIR"

# --- проверка окружения ---------------------------------------------------
if [ ! -d "$DIR/.git" ]; then
    c_err "Каталог $DIR — не git-репозиторий. Запускайте скрипт из установленного huntproxy."
    exit 1
fi

if [ "$(id -u)" -ne 0 ]; then
    c_warn "Скрипт запущен не от root — перезапуск службы будет пропущен (выполните его сами: systemctl restart $SERVICE)."
    DO_RESTART=false
fi

echo ""
echo "  ╔══════════════════════════════════════╗"
echo "  ║        huntproxy updater              ║"
echo "  ╚══════════════════════════════════════╝"
echo ""

# --- проверка новой версии -------------------------------------------------
c_info "Проверяю наличие новой версии (origin/$BRANCH)..."
git fetch --quiet origin "$BRANCH"

LOCAL=$(git rev-parse HEAD)
REMOTE=$(git rev-parse "origin/$BRANCH")
LOCAL_SHORT=$(git rev-parse --short HEAD)
REMOTE_SHORT=$(git rev-parse --short "origin/$BRANCH")
LOCAL_DATE=$(git show -s --format=%cs "$LOCAL" 2>/dev/null || echo "?")
REMOTE_DATE=$(git show -s --format=%cs "$REMOTE" 2>/dev/null || echo "?")

echo ""
echo "  Текущая версия:  $LOCAL_DATE ($LOCAL_SHORT)"
echo "  Версия в git:    $REMOTE_DATE ($REMOTE_SHORT)"
if [ "$LOCAL" != "$REMOTE" ]; then
    echo ""
    echo "  Новые коммиты:"
    git log --oneline "$LOCAL..origin/$BRANCH" | sed 's/^/    /' | head -25
fi
echo ""

OLD_REQ_HASH=$(git show HEAD:requirements.txt 2>/dev/null | sha256sum | cut -d' ' -f1)
NEW_REQ_HASH=$(git show "origin/$BRANCH:requirements.txt" 2>/dev/null | sha256sum | cut -d' ' -f1)

# --- жёсткое приведение к origin -------------------------------------------
# Прод не хранит собственных изменений: сбрасываем tracked-файлы к origin и
# удаляем лишние untracked-файлы. Исключения (.gitignore: data/, config.yaml,
# .venv, node_modules, логи) остаются на месте — git clean без -x их не трогает.
c_info "Жёстко привожу код к origin/$BRANCH (reset + удаление лишних файлов)..."
git clean -fd >/dev/null
git reset --hard "origin/$BRANCH" >/dev/null
c_ok "Код приведён к origin; свои изменения и лишние файлы удалены"

# --- зависимости ------------------------------------------------------------
if [ ! -d .venv ]; then
    c_info "Создаю виртуальное окружение..."
    python3 -m venv .venv
fi
if [ "$OLD_REQ_HASH" != "$NEW_REQ_HASH" ]; then
    c_info "requirements.txt изменился — обновляю зависимости..."
else
    c_info "requirements.txt не изменился — зависимости не трогаю"
fi
.venv/bin/pip install --upgrade pip setuptools wheel >/dev/null 2>&1 || true
if [ "$OLD_REQ_HASH" != "$NEW_REQ_HASH" ]; then
    .venv/bin/pip install -r requirements.txt
fi
touch .venv/installed.flag
c_ok "Зависимости готовы"

# --- JS-бандл (пересборка + сброс кэша браузера) ----------------------------
if ! .venv/bin/python scripts/build_js_bundle.py --check; then
    c_info "Фронтенд изменился — пересобираю бандл..."
    .venv/bin/python scripts/build_js_bundle.py
    V=$(grep -o 'pages\.bundle\.js?v=[0-9]*' web/index.html 2>/dev/null | grep -o '[0-9]*' | head -1 || echo "")
    if [ -n "$V" ]; then
        V=$((V + 1))
        sed -i "s/pages\.bundle\.js?v=[0-9]*/pages.bundle.js?v=$V/" web/index.html
        c_ok "Версия бандла поднята до v=$V (браузеры подтянут новый JS)"
    fi
    c_ok "JS-бандл пересобран"
fi

# --- pre-commit hook ----------------------------------------------------------
if [ -f install-hooks.sh ]; then
    ./install-hooks.sh >/dev/null 2>&1 || true
fi

# --- тесты (только по явному флагу --test) ---------------------------------
if $RUN_TESTS; then
    c_info "Запускаю тесты (./test.sh)..."
    if ! ./test.sh; then
        c_err "Тесты не прошли!"
        if ! confirm "Перезапустить службу всё равно?" "n"; then
            echo ""
            c_info "Служба не перезапущена. Новый код установлен, но не активен до перезапуска."
            echo ""
            exit 1
        fi
    else
        c_ok "Тесты пройдены"
    fi
fi

# --- перезапуск службы ----------------------------------------------------------
# После жёсткого reset к origin служба всегда перезапускается (кроме --no-restart).
RESTART_NEEDED=true
if [ "$OLD_REQ_HASH" != "$NEW_REQ_HASH" ]; then RESTART_NEEDED=true; fi
if ! .venv/bin/python scripts/build_js_bundle.py --check; then RESTART_NEEDED=true; fi

if $DO_RESTART && $RESTART_NEEDED; then
    if [ -f "$UNIT" ]; then
        c_info "Перезапускаю службу $SERVICE..."
        systemctl restart "$SERVICE"
        c_ok "Служба перезапущена"
    else
        c_warn "systemd-служба не установлена — перезапустите вручную: ./hunt.sh"
    fi
elif [ "$LOCAL" = "$REMOTE" ] && ! $FORCE; then
    c_info "Код не изменился — перезапуск не требуется"
else
    c_info "Перезапуск пропущен по флагу --no-restart или не-от root"
fi

# --- итог -----------------------------------------------------------------------
echo ""
DEPLOYED=$(git rev-parse --short HEAD 2>/dev/null)
DEPLOY_DATE=$(git show -s --format=%cs HEAD 2>/dev/null)
echo "  ╔══════════════════════════════════════════╗"
echo "  ║          Обновление завершено             ║"
echo "  ╚══════════════════════════════════════════╝"
echo ""
echo "  Установлена версия: $DEPLOY_DATE ($DEPLOYED)"
echo "  Web UI:             http://<хост>:17177/  (служебный: http://127.0.0.1:17177/)"
echo "  Логи:               journalctl -u $SERVICE -f"
echo ""
if grep -q -- "--host 127.0.0.1" "$UNIT" 2>/dev/null; then
    c_warn "systemd-юнит слушает только 127.0.0.1. Для доступа из сети отредактируйте юнит"
    c_warn "(ExecStart: --host 0.0.0.0) или запустите: ./hunt.sh --public"
fi
echo ""
