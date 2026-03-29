#!/usr/bin/env bash
# ============================================================================
# IIStudio — Установка (Ubuntu 20.04/22.04/24.04)
#
#   curl -fsSL https://raw.githubusercontent.com/denislonelys/dromdev/main/install.sh | bash
# или:
#   git clone https://github.com/denislonelys/dromdev IIStudio && cd IIStudio && bash install.sh
# ============================================================================

set -e

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'
info()  { echo -e "${CYAN}[INFO]${NC}  $*"; }
ok()    { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }
step()  { echo -e "\n${BOLD}▶ $*${NC}"; }

IISTUDIO_DIR="${IISTUDIO_DIR:-/root/IIStudio}"
REPO_URL="https://github.com/denislonelys/dromdev"
SERVER_URL="https://orproject.online"

echo -e "${CYAN}"
echo "╔══════════════════════════════════════════════════════════╗"
echo "║   ◈ IIStudio — AI Dev Tool                              ║"
echo "║   Установка...                                           ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# ── Проверки ──────────────────────────────────────────────────────────────────
[[ $EUID -ne 0 ]] && error "Нужен root. Запусти: sudo bash install.sh"
[[ "$(uname -s)" != "Linux" ]] && error "Только Linux (Ubuntu/Debian)"

step "Python 3.10+"
PY_VER=$(python3 --version 2>/dev/null | grep -oP '\d+\.\d+' | head -1)
MAJOR=$(echo $PY_VER | cut -d. -f1); MINOR=$(echo $PY_VER | cut -d. -f2)
[[ $MAJOR -ge 3 && $MINOR -ge 10 ]] || error "Нужен Python 3.10+, найден $PY_VER"
ok "Python $PY_VER"

# ── Системные зависимости ─────────────────────────────────────────────────────
step "Системные зависимости..."
apt-get update -qq 2>/dev/null
apt-get install -y -qq git curl wget nginx xvfb \
    libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 \
    libxcomposite1 libxdamage1 libxfixes3 libxrandr2 \
    libgbm1 libxkbcommon0 libpango-1.0-0 libcairo2 \
    libasound2t64 libnspr4 libnss3 \
    python3-pip python3-venv 2>/dev/null || \
apt-get install -y -qq git curl wget nginx xvfb \
    libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 \
    libxcomposite1 libxdamage1 libxfixes3 libxrandr2 \
    libgbm1 libxkbcommon0 libpango-1.0-0 libcairo2 \
    libasound2 libnspr4 libnss3 \
    python3-pip python3-venv 2>/dev/null || true
ok "Зависимости установлены"

# ── Клонирование ─────────────────────────────────────────────────────────────
step "Загрузка IIStudio..."
if [[ -d "$IISTUDIO_DIR/.git" ]]; then
    info "Уже установлен — обновляем..."
    cd "$IISTUDIO_DIR" && git pull origin main 2>/dev/null || warn "Не удалось обновить — используем текущую версию"
    ok "Обновлён"
elif [[ -d "$IISTUDIO_DIR" ]] && [[ "$(ls -A $IISTUDIO_DIR 2>/dev/null)" ]]; then
    warn "Папка $IISTUDIO_DIR занята. Клонируем в /opt/IIStudio..."
    IISTUDIO_DIR="/opt/IIStudio"
    git clone "$REPO_URL" "$IISTUDIO_DIR" 2>/dev/null || error "Ошибка загрузки"
    ok "Загружен в $IISTUDIO_DIR"
else
    git clone "$REPO_URL" "$IISTUDIO_DIR" 2>/dev/null || error "Ошибка загрузки"
    ok "Загружен"
fi
cd "$IISTUDIO_DIR"

# ── Python зависимости ────────────────────────────────────────────────────────
step "Python зависимости..."
pip3 install -e "." --break-system-packages -q 2>/dev/null || pip3 install -e "." -q
ok "Установлены"

# ── Playwright (браузер для AI запросов) ─────────────────────────────────────
step "Браузерный движок..."
python3 -m playwright install chromium --with-deps 2>&1 | grep -E "download|✓|error" | tail -5
ok "Готов"

# ── Папки для файлов ──────────────────────────────────────────────────────────
step "Создание папок..."
mkdir -p "$IISTUDIO_DIR/userfiles"/{videos,images,documents,uploads,audio}
ok "Папки созданы: $IISTUDIO_DIR/userfiles/"

# ── Nginx ────────────────────────────────────────────────────────────────────
step "Nginx..."
cp "$IISTUDIO_DIR/docker/nginx/conf.d/iistudio.conf" /etc/nginx/sites-available/iistudio 2>/dev/null || true
ln -sf /etc/nginx/sites-available/iistudio /etc/nginx/sites-enabled/iistudio 2>/dev/null || true
nginx -t 2>/dev/null && (nginx -s reload 2>/dev/null || systemctl reload nginx 2>/dev/null || true) || true
ok "Nginx настроен"

# ── Systemd автозапуск ────────────────────────────────────────────────────────
step "Автозапуск..."
CHROME_BIN=$(find /root/.cache/ms-playwright -name "chrome" -type f 2>/dev/null | head -1 || echo "")
for svc in iistudio-xvfb iistudio-chrome iistudio iistudio-watcher; do
    SVC_FILE="$IISTUDIO_DIR/deploy/${svc}.service"
    [[ -f "$SVC_FILE" ]] || continue
    sed "s|/root/IIStudio|$IISTUDIO_DIR|g" "$SVC_FILE" > "/etc/systemd/system/${svc}.service"
    systemctl enable "$svc" >/dev/null 2>&1 || true
done
systemctl daemon-reload 2>/dev/null || true
for svc in iistudio-xvfb iistudio-chrome; do
    systemctl restart "$svc" 2>/dev/null || true; sleep 3
done
sleep 8
for svc in iistudio iistudio-watcher; do
    systemctl restart "$svc" 2>/dev/null || true; sleep 2
done
ok "Автозапуск настроен"

IP=$(hostname -I 2>/dev/null | awk '{print $1}' || echo "localhost")

echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║   ✅ IIStudio установлен!                                   ║${NC}"
echo -e "${GREEN}╠══════════════════════════════════════════════════════════════╣${NC}"
echo -e "${GREEN}║                                                              ║${NC}"
echo -e "${GREEN}║  Шаг 1. Зарегистрируйся или войди:                          ║${NC}"
echo -e "${GREEN}║    iis auth register        — создать аккаунт               ║${NC}"
echo -e "${GREEN}║    iis auth login           — войти                         ║${NC}"
echo -e "${GREEN}║                                                              ║${NC}"
echo -e "${GREEN}║  Шаг 2. Используй AI:                                       ║${NC}"
echo -e "${GREEN}║    iis ask \"твой вопрос\"                                    ║${NC}"
echo -e "${GREEN}║    iis chat                 — интерактивный режим            ║${NC}"
echo -e "${GREEN}║                                                              ║${NC}"
echo -e "${GREEN}║  Сайт:    http://${IP}:8888                          ║${NC}"
echo -e "${GREEN}║  Файлы:   http://${IP}:8888/files/                  ║${NC}"
echo -e "${GREEN}║  Аккаунт: ${SERVER_URL}/login              ║${NC}"
echo -e "${GREEN}║                                                              ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════════════╝${NC}"
