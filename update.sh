#!/usr/bin/env bash
#
# huntproxy updater — обновляет код, зависимости и фронтенд, не трогая
# настройки службы (data/, config.yaml, systemd-юнит, локальные правки).
#
# Поведение:
#   1. проверяет на удалённом репозитории наличие новой версии;
#   2. если новая версия найдена — показывает, что изменилось, и спрашивает
#      подтверждение (обновить или нет);
#   3. при подтверждении: бэкап локальных правок -> git pull -> зависимости
#      (если изменились) -> пересборка JS-бандла -> тесты -> перезапуск службы.
#
# Использование:
#   ./update.sh               обычное обновление с подтверждением
#   ./update.sh -y            без запроса подтверждения
#   ./update.sh -f            принудительно, даже если версия та же
#   ./update.sh --no-test     пропустить ./test.sh
#   ./update.sh --no-restart  не перезапускать службу
#
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE="huntproxy"
BRANCH="${HUNT_UPDATE_BRANCH:-main}"
UNIT="/etc/systemd/system/$SERVICE.service"

ASSUME_YES=false
FORCE=false
RUN_TESTS=true
DO_RESTART=true

for arg in "$@"; do
    case "$arg" in
        -y|--yes)          ASSUME_YES=true ;;
        -f|--force)        FORCE=true ;;
        --no-test)         RUN_TESTS=false ;;
        --no-restart)      DO_RESTART=false ;;
        -h|--help)
            sed -n '2,22p' "$0" | sed 's/^# \{0,1\}//'
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
    read -r -p "  $1 [${def^^}/${def^^}-противоположное] " ans
    case "${ans,,}" in
        y|yes|д|да|"") [ "$def" = "y" ] ;;
        *)             [ "$def" = "n" ] && [ -z "${ans:-}" ] ;;
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

if [ "$LOCAL" = "$REMOTE" ] && ! $FORCE; then
    if git diff --quiet HEAD && [ -z "$(git diff --name-only HEAD)" ]; then
        c_ok "Уже установлена последняя версия: $LOCAL_DATE ($LOCAL_SHORT)"
        echo ""
        echo "  Для принудительной переустановки: ./update.sh -f"
        echo ""
        exit 0
    fi
    c_ok "Установлена последняя версия: $LOCAL_DATE ($LOCAL_SHORT)"
    c_info "Есть локальные незакоммиченные правки — они не будут затронуты."
    echo ""
    exit 0
fi

echo ""
echo "  Текущая версия:  $LOCAL_DATE ($LOCAL_SHORT)"
if [ "$LOCAL" != "$REMOTE" ]; then
    echo "  Найдена новая:   $REMOTE_DATE ($REMOTE_SHORT)"
    echo ""
    echo "  Новые коммиты:"
    git log --oneline "$LOCAL..origin/$BRANCH" | sed 's/^/    /' | head -25
    echo ""
else
    echo "  Новая версия не найдена (принудительная переустановка -f)."
    echo ""
fi

if ! confirm "Найдена новая версия — обновить?" "y"; then
    echo ""
    c_info "Обновление отменено. Установленная версия не изменена."
    echo ""
    exit 0
fi

# --- предупреждение о незакоммиченных правках -------------------------------
UNCOMMITTED=$(git diff --name-only HEAD 2>/dev/null || true)
if [ -n "$UNCOMMITTED" ]; then
    c_warn "Найдены незакоммиченные правки — обновление их удалит:"
    echo "$UNCOMMITTED" | sed 's/^/      /'
    if ! confirm "Сначала закоммитьте их, затем обновитесь. Продолжить обновление (правки будут удалены)?" "n"; then
        echo ""
        c_info "Обновление отменено. Закоммитьте изменения и запустите ./update.sh снова."
        echo ""
        exit 0
    fi
fi

OLD_REQ_HASH=$(git show HEAD:requirements.txt 2>/dev/null | sha256sum | cut -d' ' -f1)
NEW_REQ_HASH=$(git show "origin/$BRANCH:requirements.txt" 2>/dev/null | sha256sum | cut -d' ' -f1)

# --- обновление кода --------------------------------------------------------
c_info "Обновляю код до origin/$BRANCH..."
git reset --hard "origin/$BRANCH" >/dev/null
c_ok "Код обновлён"

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

# --- тесты --------------------------------------------------------------------
if $RUN_TESTS; then
    c_info "Запускаю тесты (./test.sh)..."
    if ./test.sh; then
        c_ok "Тесты пройдены"
    else
        c_err "Тесты не прошли!"
        if ! confirm "Перезапустить службу всё равно (возможно, тесты не блокирующие)?" "n"; then
            echo ""
            c_info "Служба не перезапущена. Новый код установлен, но не активен до перезапуска."
            echo ""
            exit 1
        fi
    fi
fi

# --- перезапуск службы ----------------------------------------------------------
RESTART_NEEDED=false
[ "$LOCAL" != "$REMOTE" ] && RESTART_NEEDED=true
$FORCE && RESTART_NEEDED=true
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
