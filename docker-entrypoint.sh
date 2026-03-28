#!/bin/bash
# ============================================================================
# IIStudio — Docker Entrypoint Script
# Запускает MTProto туннели, проверяет сервисы и стартует IIStudio
# ============================================================================

set -e

echo ""
echo "╔══════════════════════════════════════════════════════════════════════╗"
echo "║          IIStudio AI Orchestrator — Starting up...                 ║"
echo "║          Server: Amsterdam | Engine: Claude                         ║"
echo "╚══════════════════════════════════════════════════════════════════════╝"
echo ""

# ── Цвета для вывода ────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info()    { echo -e "${GREEN}[INFO]${NC}  $1"; }
log_warn()    { echo -e "${YELLOW}[WARN]${NC}  $1"; }
log_error()   { echo -e "${RED}[ERROR]${NC} $1"; }
log_step()    { echo -e "${BLUE}[STEP]${NC}  $1"; }

# ── Функция ожидания сервиса ────────────────────────────────────────────────
wait_for_service() {
    local host=$1
    local port=$2
    local name=$3
    local retries=${4:-30}
    local wait=${5:-2}

    log_step "Ожидание $name ($host:$port)..."
    for i in $(seq 1 $retries); do
        if nc -z "$host" "$port" 2>/dev/null; then
            log_info "✅ $name доступен!"
            return 0
        fi
        echo -n "."
        sleep $wait
    done
    log_error "❌ $name недоступен после $((retries * wait)) секунд"
    return 1
}

# ── Шаг 1: Виртуальный дисплей для Chromium ────────────────────────────────
log_step "Запуск виртуального дисплея (Xvfb)..."
if [ "${BROWSER_HEADLESS:-true}" = "false" ]; then
    Xvfb :99 -screen 0 1920x1080x24 -ac +extension GLX +render -noreset &
    export DISPLAY=:99
    sleep 1
    log_info "✅ Xvfb запущен (DISPLAY=:99)"
else
    log_info "ℹ️  Headless режим (Xvfb не нужен)"
fi

# ── Шаг 2: Проверка PostgreSQL ─────────────────────────────────────────────
if [ -n "${DATABASE_URL:-}" ]; then
    DB_HOST=$(echo "$DATABASE_URL" | sed -n 's/.*@\([^:\/]*\).*/\1/p')
    DB_PORT=$(echo "$DATABASE_URL" | sed -n 's/.*:\([0-9]*\)\/.*/\1/p')
    DB_PORT=${DB_PORT:-5432}
    wait_for_service "$DB_HOST" "$DB_PORT" "PostgreSQL" 30 2
else
    log_warn "⚠️  DATABASE_URL не задан, пропускаю проверку PostgreSQL"
fi

# ── Шаг 3: Проверка Redis ──────────────────────────────────────────────────
if [ -n "${REDIS_URL:-}" ]; then
    REDIS_HOST=$(echo "$REDIS_URL" | sed -n 's/.*@\([^:\/]*\).*/\1/p')
    if [ -z "$REDIS_HOST" ]; then
        REDIS_HOST=$(echo "$REDIS_URL" | sed -n 's/redis:\/\/\([^:\/]*\).*/\1/p')
    fi
    REDIS_PORT=$(echo "$REDIS_URL" | sed -n 's/.*:\([0-9]*\)\/.*/\1/p')
    REDIS_PORT=${REDIS_PORT:-6379}
    wait_for_service "$REDIS_HOST" "$REDIS_PORT" "Redis" 20 2
else
    log_warn "⚠️  REDIS_URL не задан, пропускаю проверку Redis"
fi

# ── Шаг 4: Запуск локальных MTProto туннелей из proxy.txt ─────────────────
log_step "Инициализация MTProto прокси туннелей..."
PROXY_FILE="${PROXY_FILE:-/app/proxy.txt}"
MTG_RUNNING=0

if [ -f "$PROXY_FILE" ] && command -v mtg &>/dev/null; then
    LOCAL_PORT=11080
    while IFS= read -r line; do
        # Пропускать комментарии и пустые строки
        [[ -z "$line" || "$line" =~ ^# || "$line" =~ ^socks5 ]] && continue

        # Парсить HOST:PORT:SECRET
        HOST=$(echo "$line" | cut -d: -f1)
        PORT=$(echo "$line" | cut -d: -f2)
        SECRET=$(echo "$line" | cut -d: -f3)

        if [ -n "$HOST" ] && [ -n "$PORT" ] && [ -n "$SECRET" ]; then
            log_info "  🔗 Туннель: $HOST:$PORT → 127.0.0.1:$LOCAL_PORT"
            mtg run --bind-to "127.0.0.1:$LOCAL_PORT" \
                "$HOST:$PORT" "$SECRET" \
                >> /app/logs/mtg_${LOCAL_PORT}.log 2>&1 &
            LOCAL_PORT=$((LOCAL_PORT + 1))
            MTG_RUNNING=$((MTG_RUNNING + 1))
            sleep 0.3
        fi
    done < "$PROXY_FILE"

    if [ $MTG_RUNNING -gt 0 ]; then
        log_info "✅ Запущено MTProto туннелей: $MTG_RUNNING"
        log_info "   Локальные SOCKS5 порты: 11080 - $((11080 + MTG_RUNNING - 1))"
        sleep 2  # Дать туннелям время подняться
    else
        log_warn "⚠️  MTProto прокси в proxy.txt не найдены"
    fi
else
    if [ ! -f "$PROXY_FILE" ]; then
        log_warn "⚠️  Файл прокси не найден: $PROXY_FILE"
    fi
    if ! command -v mtg &>/dev/null; then
        log_warn "⚠️  mtg не установлен, MTProto туннели недоступны"
    fi

    # Проверить если задан внешний SOCKS5 (от mtproto-tunnel контейнера)
    if [ -n "${MTPROTO_SOCKS5_HOST:-}" ] && [ -n "${MTPROTO_SOCKS5_PORT:-}" ]; then
        wait_for_service "$MTPROTO_SOCKS5_HOST" "$MTPROTO_SOCKS5_PORT" \
            "MTProto SOCKS5" 15 2 || true
    fi
fi

# ── Шаг 5: Проверка Playwright/Chromium ────────────────────────────────────
log_step "Проверка Playwright/Chromium..."
if python3 -c "from playwright.sync_api import sync_playwright; p = sync_playwright().start(); b = p.chromium.launch(headless=True); b.close(); p.stop()" 2>/dev/null; then
    log_info "✅ Chromium работает корректно"
else
    log_warn "⚠️  Проблема с Chromium, попробую исправить..."
    playwright install chromium 2>/dev/null || true
fi

# ── Шаг 6: Миграция базы данных ────────────────────────────────────────────
log_step "Применение миграций базы данных..."
if [ -f "/app/alembic.ini" ]; then
    python3 -m alembic upgrade head && log_info "✅ Миграции применены" \
        || log_warn "⚠️  Ошибка миграций (продолжаю...)"
else
    log_warn "ℹ️  alembic.ini не найден, пропускаю миграции"
fi

# ── Шаг 7: Создание директорий ─────────────────────────────────────────────
mkdir -p /app/logs /app/screenshots /app/data
log_info "✅ Директории созданы"

# ── Финальный вывод ────────────────────────────────────────────────────────
echo ""
echo "┌──────────────────────────────────────────────────────────────────┐"
echo "│  IIStudio готов к запуску!                                       │"
echo "│  API:     http://0.0.0.0:${API_PORT:-8080}                              │"
echo "│  Metrics: http://0.0.0.0:${METRICS_PORT:-9090}                          │"
echo "│  Docs:    http://0.0.0.0:${API_PORT:-8080}/docs                         │"
echo "│  Прокси:  $MTG_RUNNING MTProto туннелей активно                         │"
echo "└──────────────────────────────────────────────────────────────────┘"
echo ""

# ── Запустить IIStudio с переданными аргументами ───────────────────────────
log_info "🚀 Запуск: python3 main.py $@"
exec python3 /app/main.py "$@"
