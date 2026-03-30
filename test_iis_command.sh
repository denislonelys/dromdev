#!/bin/bash
echo "🧪 Тестирование iis команды..."
echo ""

# Проверяем где находится iis
echo "1️⃣ Где находится iis:"
which iis
echo ""

# Проверяем версию
echo "2️⃣ Версия iis:"
iis --version 2>&1 || echo "⚠️ Версия не показана"
echo ""

# Проверяем help
echo "3️⃣ Доступные команды:"
iis --help 2>&1 | grep -E "Commands:|dromdev"
echo ""

# Проверяем dromdev
echo "4️⃣ Подкоманды dromdev:"
iis dromdev --help 2>&1 | head -20
echo ""

# Проверяем Python путь
echo "5️⃣ Python путь:"
which python3
python3 --version
echo ""

# Проверяем iistudio.py
echo "6️⃣ iistudio.py существует:"
ls -la iistudio.py | head -1
echo ""

echo "=============================="
echo "✅ Диагностика завершена!"
