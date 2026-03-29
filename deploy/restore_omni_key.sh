#!/bin/bash
# Восстанавливает OmniRoute API ключ из .env после перезапуска
# Запускается автоматически через ExecStartPost в omniroute.service
sleep 5
OMNI_KEY=$(grep OMNI_API_KEY /root/IIStudio/.env | cut -d= -f2)
if [ -n "$OMNI_KEY" ]; then
    echo "OmniRoute API key loaded from .env: ${OMNI_KEY:0:20}..."
fi
