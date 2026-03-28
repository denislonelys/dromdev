# ============================================================================
# IIStudio — Dockerfile
# Multi-stage build для минимального размера образа
# Базовый образ: Python 3.11 slim + Chromium + MTProto поддержка
# ============================================================================

# ─────────────────────────────────────────────────────────────────────────────
# STAGE 1: Builder — устанавливаем Python зависимости
# ─────────────────────────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /build

# Системные зависимости для сборки Python пакетов
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libpq-dev \
    libffi-dev \
    libssl-dev \
    cargo \
    && rm -rf /var/lib/apt/lists/*

# Копировать только requirements для кэширования слоёв
COPY requirements.txt .

# Установить Python зависимости в отдельную директорию
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ─────────────────────────────────────────────────────────────────────────────
# STAGE 2: Runtime — финальный образ
# ─────────────────────────────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

LABEL maintainer="IIStudio Team"
LABEL version="1.0.0"
LABEL description="IIStudio AI Orchestrator — arena.ai parser with MTProto proxy support"

# Переменные окружения
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app \
    PLAYWRIGHT_BROWSERS_PATH=/app/.playwright \
    DISPLAY=:99 \
    PATH="/app/venv/bin:$PATH"

WORKDIR /app

# ── Системные зависимости для Playwright/Chromium и MTProto ──────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Chromium зависимости
    chromium \
    chromium-driver \
    fonts-liberation \
    fonts-noto-color-emoji \
    fonts-noto-cjk \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libgbm1 \
    libgdk-pixbuf2.0-0 \
    libglib2.0-0 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libx11-6 \
    libx11-xcb1 \
    libxcb1 \
    libxcomposite1 \
    libxcursor1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxi6 \
    libxrandr2 \
    libxrender1 \
    libxss1 \
    libxtst6 \
    xdg-utils \
    # Виртуальный дисплей (для headless режима)
    xvfb \
    x11-utils \
    # Сетевые утилиты
    curl \
    wget \
    ca-certificates \
    # PostgreSQL клиент
    libpq5 \
    # Процессы и мониторинг
    procps \
    # MTProto: wget для скачивания mtg
    && wget -q https://github.com/9seconds/mtg/releases/download/v2.1.7/mtg-2.1.7-linux-amd64.tar.gz \
       -O /tmp/mtg.tar.gz \
    && tar -xzf /tmp/mtg.tar.gz -C /tmp \
    && mv /tmp/mtg-2.1.7-linux-amd64/mtg /usr/local/bin/mtg \
    && chmod +x /usr/local/bin/mtg \
    && rm -rf /tmp/mtg* \
    # Очистить кэш apt
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# ── Скопировать Python пакеты из builder стадии ──────────────────────────────
COPY --from=builder /install /usr/local

# ── Установить Playwright и Chromium ─────────────────────────────────────────
RUN pip install playwright==1.44.0 \
    && playwright install chromium \
    && playwright install-deps chromium

# ── Создать непривилегированного пользователя ────────────────────────────────
RUN groupadd -r iistudio && useradd -r -g iistudio -d /app -s /sbin/nologin iistudio

# ── Создать необходимые директории ───────────────────────────────────────────
RUN mkdir -p \
    /app/logs \
    /app/screenshots \
    /app/data \
    /tmp/iistudio \
    && chown -R iistudio:iistudio /app /tmp/iistudio

# ── Копировать исходный код проекта ──────────────────────────────────────────
COPY --chown=iistudio:iistudio . /app/

# ── Скрипт точки входа ───────────────────────────────────────────────────────
COPY --chown=iistudio:iistudio docker-entrypoint.sh /app/docker-entrypoint.sh
RUN chmod +x /app/docker-entrypoint.sh

# ── Переключиться на непривилегированного пользователя ───────────────────────
USER iistudio

# ── Порты ────────────────────────────────────────────────────────────────────
EXPOSE 8080   
# API сервер
EXPOSE 9090   
# Prometheus метрики

# ── Healthcheck ───────────────────────────────────────────────────────────────
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# ── Тома для персистентных данных ────────────────────────────────────────────
VOLUME ["/app/logs", "/app/data"]

# ── Точка входа ──────────────────────────────────────────────────────────────
ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["--mode", "api"]
