#!/usr/bin/env bash
# ============================================================================
# IIStudio — Установка на новый сервер (Ubuntu 22.04/24.04)
#
# Использование:
#   curl -fsSL https://raw.githubusercontent.com/iistudio/iistudio/main/install.sh | bash
# или:
#   git clone https://github.com/iistudio/iistudio /root/IIStudio && cd /root/IIStudio && bash install.sh
#
# После установки:
#   iis ask "твой вопрос"
#   http://IP/          — веб-интерфейс
#   http://IP/files/    — твои файлы (видео, изображения, документы)
#   http://IP/docs      — API документация
# ============================================================================

set -e

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'
info()  { echo -e "${CYAN}[INFO]${NC}  $*"; }
ok()    { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }
step()  { echo -e "\n${BOLD}▶ $*${NC}"; }

IISTUDIO_DIR="${IISTUDIO_DIR:-/root/IIStudio}"
REPO_URL="https://github.com/iistudio/iistudio"

echo -e "${CYAN}"
echo "╔══════════════════════════════════════════════════════════╗"
echo "║   ◈ IIStudio — AI Dev Tool Installer                    ║"
echo "║   arena.ai • proxy • cache • CLI • web UI • files       ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# ── Проверка ─────────────────────────────────────────────────────────────────
[[ $EUID -ne 0 ]] && error "Нужен root. Запусти: sudo bash install.sh"
[[ "$(uname -s)" != "Linux" ]] && error "Только Linux (Ubuntu 22.04/24.04)"

step "Проверка Python 3.10+"
PY=$(python3 --version 2>/dev/null | grep -oP '\d+\.\d+' | head -1)
MAJOR=$(echo $PY | cut -d. -f1); MINOR=$(echo $PY | cut -d. -f2)
[[ $MAJOR -ge 3 && $MINOR -ge 10 ]] || error "Нужен Python 3.10+, найден $PY"
ok "Python $PY"

# ── Системные зависимости ─────────────────────────────────────────────────────
step "Установка системных зависимостей..."
apt-get update -qq
apt-get install -y -qq \
    git curl wget nginx xvfb \
    libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 \
    libxcomposite1 libxdamage1 libxfixes3 libxrandr2 \
    libgbm1 libxkbcommon0 libpango-1.0-0 libcairo2 \
    libasound2t64 libnspr4 libnss3 libxtst6 \
    fonts-liberation libappindicator3-1 xdg-utils \
    python3-pip python3-venv
ok "Системные зависимости установлены"

# ── Клонирование ─────────────────────────────────────────────────────────────
step "Клонирование IIStudio в $IISTUDIO_DIR..."
if [[ ! -f "$IISTUDIO_DIR/pyproject.toml" ]]; then
    git clone "$REPO_URL" "$IISTUDIO_DIR" || error "Не удалось клонировать"
    ok "Репозиторий клонирован"
else
    info "Директория уже существует — обновляем"
    cd "$IISTUDIO_DIR" && git pull --ff-only || warn "git pull не удался"
fi
cd "$IISTUDIO_DIR"

# ── Python зависимости ────────────────────────────────────────────────────────
step "Установка Python зависимостей..."
pip3 install -e "." --break-system-packages -q
ok "Python пакеты установлены"

# ── Playwright + Chromium ─────────────────────────────────────────────────────
step "Установка Playwright + Chromium..."
python3 -m playwright install chromium --with-deps 2>&1 | tail -5
ok "Playwright + Chromium готов"

# ── Конфигурация ─────────────────────────────────────────────────────────────
step "Настройка конфигурации..."
if [[ ! -f "$IISTUDIO_DIR/.env" ]]; then
    cp "$IISTUDIO_DIR/.env.example" "$IISTUDIO_DIR/.env"
    warn "Создан .env — заполни ARENA_EMAIL и ARENA_PASSWORD:"
    warn "  nano $IISTUDIO_DIR/.env"
else
    ok ".env уже существует"
fi

# ── Папки для файлов пользователя ─────────────────────────────────────────────
step "Создание папок для файлов..."
mkdir -p "$IISTUDIO_DIR/userfiles"/{videos,images,documents,uploads,audio}
ok "Папки созданы:"
echo "   $IISTUDIO_DIR/userfiles/videos/    — твои видео"
echo "   $IISTUDIO_DIR/userfiles/images/    — картинки"
echo "   $IISTUDIO_DIR/userfiles/documents/ — документы"
echo "   $IISTUDIO_DIR/userfiles/uploads/   — всё остальное"

# ── Nginx ────────────────────────────────────────────────────────────────────
step "Настройка Nginx..."
cp "$IISTUDIO_DIR/docker/nginx/conf.d/iistudio.conf" /etc/nginx/sites-available/iistudio
ln -sf /etc/nginx/sites-available/iistudio /etc/nginx/sites-enabled/iistudio
rm -f /etc/nginx/sites-enabled/default 2>/dev/null || true
nginx -t 2>/dev/null && (nginx -s reload 2>/dev/null || systemctl reload nginx 2>/dev/null || true)
ok "Nginx настроен"

# ── Systemd сервисы ───────────────────────────────────────────────────────────
step "Установка и запуск systemd сервисов..."

# Обновляем пути в сервисах
CHROME_BIN=$(find /root/.cache/ms-playwright -name "chrome" -type f 2>/dev/null | head -1)
[[ -z "$CHROME_BIN" ]] && CHROME_BIN="/usr/bin/chromium"

for svc in iistudio-xvfb iistudio-chrome iistudio iistudio-watcher; do
    sed "s|/root/IIStudio|$IISTUDIO_DIR|g" "$IISTUDIO_DIR/deploy/${svc}.service" > "/etc/systemd/system/${svc}.service"
    # Обновляем путь к chrome
    [[ -n "$CHROME_BIN" ]] && sed -i "s|chrome-linux64/chrome|$CHROME_BIN|g" "/etc/systemd/system/${svc}.service" || true
done

systemctl daemon-reload

info "Запускаем сервисы (это займёт ~30 секунд)..."
for svc in iistudio-xvfb iistudio-chrome; do
    systemctl enable "$svc" >/dev/null 2>&1
    systemctl restart "$svc" || warn "Не удалось запустить $svc"
    sleep 5
done

sleep 10  # Ждём Chrome

for svc in iistudio iistudio-watcher; do
    systemctl enable "$svc" >/dev/null 2>&1
    systemctl restart "$svc" || warn "Не удалось запустить $svc"
    sleep 3
done

# ── Команда iis ──────────────────────────────────────────────────────────────
step "Проверка команды 'iis'..."
which iis >/dev/null 2>&1 && ok "Команда 'iis' доступна" || warn "Команда 'iis' не найдена в PATH"

# ── Финальный статус ─────────────────────────────────────────────────────────
IP=$(hostname -I | awk '{print $1}')
echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║   ✅ IIStudio успешно установлен!                           ║${NC}"
echo -e "${GREEN}╠══════════════════════════════════════════════════════════════╣${NC}"
echo -e "${GREEN}║                                                              ║${NC}"
echo -e "${GREEN}║   🌐 Веб-интерфейс:  http://${IP}                    ║${NC}"
echo -e "${GREEN}║   📁 Твои файлы:     http://${IP}/files/              ║${NC}"
echo -e "${GREEN}║   📚 API docs:       http://${IP}/docs                ║${NC}"
echo -e "${GREEN}║                                                              ║${NC}"
echo -e "${GREEN}║   💻 CLI команды:                                            ║${NC}"
echo -e "${GREEN}║      iis ask \"твой вопрос\"      — запрос к AI               ║${NC}"
echo -e "${GREEN}║      iis chat                   — интерактивный чат         ║${NC}"
echo -e "${GREEN}║      iis tasks                  — доска задач               ║${NC}"
echo -e "${GREEN}║      iis plan \"задача\"           — план от AI               ║${NC}"
echo -e "${GREEN}║                                                              ║${NC}"
echo -e "${GREEN}║   📂 Добавляй файлы в:                                       ║${NC}"
echo -e "${GREEN}║      ${IISTUDIO_DIR}/userfiles/videos/   ║${NC}"
echo -e "${GREEN}║      ${IISTUDIO_DIR}/userfiles/images/   ║${NC}"
echo -e "${GREEN}║      ${IISTUDIO_DIR}/userfiles/documents/║${NC}"
echo -e "${GREEN}║   Они автоматически появятся на http://${IP}/files/  ║${NC}"
echo -e "${GREEN}║                                                              ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${YELLOW}  ⚠  Заполни .env если ещё не сделал:${NC}"
echo -e "${YELLOW}     nano $IISTUDIO_DIR/.env${NC}"
echo -e "${YELLOW}     (ARENA_EMAIL и ARENA_PASSWORD)${NC}"
echo ""
echo -e "${CYAN}  Статус:  systemctl status iistudio${NC}"
echo -e "${CYAN}  Логи:    journalctl -u iistudio -f${NC}"
echo -e "${CYAN}  Restart: systemctl restart iistudio${NC}"
