#!/usr/bin/env bash
# ============================================================================
# IIStudio — Deploy script (на текущем сервере)
# Запускать: bash /root/IIStudio/deploy/deploy.sh
# ============================================================================

set -e

IISTUDIO_DIR="/root/IIStudio"
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
NC='\033[0m'

info()  { echo -e "${CYAN}[INFO]${NC}  $*"; }
ok()    { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }

echo -e "${CYAN}"
echo "╔══════════════════════════════════════════╗"
echo "║   ◈ IIStudio — Deploy                   ║"
echo "╚══════════════════════════════════════════╝"
echo -e "${NC}"

# ── 1. Nginx конфиг ──────────────────────────────────────────────────────────
info "Настройка Nginx..."
cp "$IISTUDIO_DIR/docker/nginx/conf.d/iistudio.conf" /etc/nginx/sites-available/iistudio
ln -sf /etc/nginx/sites-available/iistudio /etc/nginx/sites-enabled/iistudio
nginx -t && nginx -s reload || systemctl reload nginx
ok "Nginx настроен"

# ── 2. Создание папок для файлов пользователя ─────────────────────────────────
info "Создание папок для файлов..."
mkdir -p "$IISTUDIO_DIR/userfiles"/{videos,images,documents,uploads,audio}
ok "Папки созданы: $IISTUDIO_DIR/userfiles/"

# ── 3. Systemd сервисы ────────────────────────────────────────────────────────
info "Установка systemd сервисов..."
for svc in iistudio-xvfb iistudio-chrome iistudio iistudio-watcher; do
    cp "$IISTUDIO_DIR/deploy/${svc}.service" /etc/systemd/system/
    ok "Установлен: ${svc}.service"
done

systemctl daemon-reload

# Запускаем в правильном порядке
for svc in iistudio-xvfb iistudio-chrome iistudio iistudio-watcher; do
    systemctl enable "$svc"
    systemctl restart "$svc" || warn "Не удалось запустить $svc"
    sleep 3
    if systemctl is-active --quiet "$svc"; then
        ok "$svc — запущен ✅"
    else
        warn "$svc — не запустился (проверь: journalctl -u $svc -n 20)"
    fi
done

ok "Все сервисы настроены"

echo ""
echo -e "${GREEN}╔══════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║   ✅ Deploy завершён!                   ║${NC}"
echo -e "${GREEN}╠══════════════════════════════════════════╣${NC}"
echo -e "${GREEN}║   Веб-интерфейс: http://$(hostname -I | awk '{print $1}')  ║${NC}"
echo -e "${GREEN}║   Файлы:  http://$(hostname -I | awk '{print $1}')/files/  ║${NC}"
echo -e "${GREEN}║   API:    http://$(hostname -I | awk '{print $1}')/api/    ║${NC}"
echo -e "${GREEN}║   Docs:   http://$(hostname -I | awk '{print $1}')/docs    ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════╝${NC}"
echo ""
info "Статус сервисов: systemctl status iistudio"
info "Логи API:        journalctl -u iistudio -f"
info "Файлы:           ls $IISTUDIO_DIR/userfiles/"
