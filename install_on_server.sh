#!/bin/bash
# ============================================================================
# IIStudio Setup Script для нового сервера
# Использование: bash install_on_server.sh
# ============================================================================

echo "🚀 IIStudio Installation Script"
echo "=============================="
echo ""

# Переменные
INSTALL_DIR="/opt/iistudio"
REPO="https://github.com/denislonelys/dromdev.git"

# 1. Проверяем зависимости
echo "1️⃣  Проверяю зависимости..."
command -v git >/dev/null 2>&1 || { echo "❌ git не установлен. Установи: apt-get install git"; exit 1; }
command -v python3 >/dev/null 2>&1 || { echo "❌ python3 не установлен. Установи: apt-get install python3"; exit 1; }
command -v pip >/dev/null 2>&1 || { echo "❌ pip не установлен. Установи: apt-get install python3-pip"; exit 1; }
echo "✅ Все зависимости есть"
echo ""

# 2. Клонируем репозиторий
echo "2️⃣  Клонирую репозиторий..."
if [ -d "$INSTALL_DIR" ]; then
    echo "   Директория существует, обновляю..."
    cd "$INSTALL_DIR"
    git pull origin main
else
    echo "   Создаю новую установку..."
    git clone "$REPO" "$INSTALL_DIR"
    cd "$INSTALL_DIR"
fi
echo "✅ Репозиторий готов"
echo ""

# 3. Устанавливаем зависимости Python
echo "3️⃣  Устанавливаю зависимости Python..."
pip install -q -r requirements.txt
echo "✅ Зависимости установлены"
echo ""

# 4. Устанавливаем iis CLI
echo "4️⃣  Устанавливаю iis CLI..."
pip install -q -e .
echo "✅ iis CLI установлен"
echo ""

# 5. Проверяем установку
echo "5️⃣  Проверяю установку..."
if iis --help >/dev/null 2>&1; then
    echo "✅ iis рабо��ает!"
else
    echo "⚠️  iis может не работать, но можешь использовать python3 iistudio.py"
fi
echo ""

# 6. Завершение
echo "=============================="
echo "✅ УСТАНОВКА ЗАВЕРШЕНА!"
echo ""
echo "🚀 КАК ЗАПУСТИТЬ:"
echo ""
echo "Вариант 1 (рекомендуется):"
echo "  iis dromdev run"
echo ""
echo "Вариант 2 (если iis не работает):"
echo "  python3 $INSTALL_DIR/iistudio.py chat"
echo ""
echo "=============================="
