<div align="center">

```
╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║   ██╗██╗███████╗████████╗██╗   ██╗██████╗ ██╗ ██████╗                      ║
║    ██║██║██╔════╝╚══██╔══╝██║   ██║██╔══██╗██║██╔═══██╗                    ║
║    ██║██║███████╗   ██║   ██║   ██║██║  ██║██║██║   ██║                    ║
║    ██║██║╚════██║   ██║   ██║   ██║██║  ██║██║██║   ██║                    ║
║    ██║██║███████║   ██║   ╚██████╔╝██████╔╝██║╚██████╔╝                    ║
║    ╚═╝╚═╝╚══════╝   ╚═╝    ╚═════╝ ╚═════╝ ╚═╝ ╚═════╝                    ║
║                                                                              ║
║              AI Orchestrator — Один инструмент, все нейросети               ║
║                    🌐 Amsterdam Server | 🤖 Powered by Claude                ║
╚══════════════════════════════════════════════════════════════════════════════╝
```

[![Python](https://img.shields.io/badge/Python-3.11+-blue?logo=python)](https://python.org)
[![Claude](https://img.shields.io/badge/Engine-Claude%20Anthropic-orange)](https://anthropic.com)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?logo=docker)](https://docker.com)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)
[![Server](https://img.shields.io/badge/Server-Amsterdam-red?logo=digitalocean)](https://amsterdam.nl)
[![Proxy](https://img.shields.io/badge/Proxy-MTProto%20%2B%20SOCKS5-blueviolet)](proxy.txt)

**DromDev** — мощный AI-оркестратор нового поколения для работы с `arena.ai`.  
Управляй 24+ нейросетями через единый интерфейс. Текст, изображения, видео, код.

[🚀 Быстрый старт](#быстрый-старт) • [📖 Документация](#документация) • [🐳 Docker](#docker) • [🌐 Прокси](#прокси) • [📡 API](#api)

</div>

---

## ✨ Возможности

| Возможность | Описание |
|------------|----------|
| 🤖 **24+ AI моделей** | GPT-4o, Claude 3.5, Gemini 1.5 Pro, Llama 3, Mistral, DeepSeek и др. |
| 🎨 **4 режима работы** | Text, Images, Video, Coding — всё через один интерфейс |
| 🌐 **MTProto + SOCKS5** | Поддержка прокси для обхода блокировок |
| ⚡ **Параллельные запросы** | Отправляй запрос во все модели одновременно и сравнивай |
| 💾 **Умный кэш** | Redis-кэш с семантическим поиском — не трать время на повторные запросы |
| 🔄 **Автовыбор модели** | Агент сам выбирает лучшую модель для твоей задачи |
| 📊 **REST API** | Полноценный FastAPI сервер для интеграции |
| 🔔 **Уведомления** | Telegram-бот сообщает когда задача завершена |
| 🛡️ **Безопасность** | API-ключи, rate limiting, шифрование данных |
| 🐳 **Docker** | Запуск всего стека одной командой |
| 📈 **Метрики** | Prometheus + Grafana дашборд |
| 🔁 **Авторестарт** | pm2 или Docker автоматически перезапустят при сбое |

---

## 🚀 Быстрый старт

### ✅ Вариант 1: IIS CLI (рекомендуется)

```bash
# 1. Клонировать репозиторий
git clone https://github.com/denislonelys/dromdev.git
cd dromdev

# 2. Установить зависимости
pip install -r requirements.txt

# 3. Запустить интерактивный режим
iis dromdev run
```

**При регистрации получите:**
- ✅ **$2000 USD** приветственный бонус
- ✅ **500,000 токенов** для траты
- ✅ **Claude Opus 4.6** по умолчанию
- ✅ **28 интерактивных команд**

**Команды в интерактиве:**
```
You > /help                  ← все 28 команд
You > /prune                 ← сжать контекст (200k budget)
You > /yolo создай API       ← YOLO режим (AI делает всё)
You > /plan задача           ← план от AI
You > /ask вопрос?           ← read-only запрос
You > /model                 ← выбрать модель (Sonnet/Opus)
You > /sessions              ← управление сессиями
You > /exit                  ← выход
```

### Вариант 2: Docker (для изоляции)

```bash
git clone https://github.com/denislonelys/dromdev.git
cd dromdev
docker build -t iistudio .
docker run -it iistudio iis dromdev run
```

### Вариант 3: PM2 (для постоянной работы на сервере)

```bash
npm install -g pm2  # если не установлен
git clone https://github.com/denislonelys/dromdev.git
cd dromdev
pip install -r requirements.txt
pm2 start iistudio.py --name=iistudio --interpreter=python3 -- chat
pm2 save && pm2 startup
```

### Вариант 4: Systemd (автозапуск при перезагрузке)

```bash
git clone https://github.com/denislonelys/dromdev.git
cd dromdev
pip install -r requirements.txt
sudo systemctl enable iistudio
sudo systemctl start iistudio
```

---

## 📋 Требования

### Системные

| Компонент | Минимум | Рекомендуется |
|-----------|---------|---------------|
| CPU | 4 ядра | 8+ ядер |
| RAM | 8 GB | 16+ GB |
| Диск | 50 GB SSD | 100+ GB SSD |
| ОС | Ubuntu 20.04+ | Ubuntu 22.04 LTS |
| Python | 3.11+ | 3.11+ |

### Программные зависимости

```
Python 3.11+        — основной язык
PostgreSQL 14+      — база данных
Redis 7+            — кэш и очереди
Chromium            — браузер для парсинга (устанавливается через playwright)
mtg                 — MTProto прокси клиент (опционально)
Docker 24+          — для контейнерного деплоя (опционально)
pm2                 — менеджер процессов (опционально)
```

---

## 🐳 Docker

### Полный стек через docker-compose

```bash
# Запустить всё (DromDev + PostgreSQL + Redis + Nginx)
docker-compose up -d

# Проверить статус
docker-compose ps

# Посмотреть логи
docker-compose logs -f dromdev

# Остановить
docker-compose down

# Обновить
git pull && docker-compose build && docker-compose up -d
```

### Отдельные команды Docker

```bash
# Собрать образ
docker build -t dromdev:latest .

# Запустить только DromDev (если PostgreSQL и Redis уже есть)
docker run -d \
  --name dromdev \
  -p 8080:8080 \
  -v $(pwd)/.env:/app/.env \
  -v $(pwd)/proxy.txt:/app/proxy.txt \
  -v $(pwd)/logs:/app/logs \
  --restart unless-stopped \
  dromdev:latest

# Войти в контейнер
docker exec -it dromdev bash

# Просмотр логов
docker logs -f dromdev
```

### Переменные окружения для Docker

```bash
# Передать через флаг -e
docker run -d \
  -e ARENA_EMAIL=your@email.com \
  -e ARENA_PASSWORD=yourpass \
  -e DATABASE_URL=postgresql+asyncpg://user:pass@db:5432/dromdev \
  -e REDIS_URL=redis://redis:6379/0 \
  dromdev:latest
```

---

## 🌐 Прокси

DromDev поддерживает два типа прокси: **MTProto** и **SOCKS5**.

### Формат proxy.txt

```
# MTProto прокси (формат: HOST:PORT:SECRET)
tg.atomic-vpn.com:443:dd3f087f3f403449a2a9446de22b5bc3d1
eu.mt-proxy.org:443:eec6c206c4d429f36d13af11fbd3c35e786d742d70726f78792e6f7267

# SOCKS5 прокси (формат: socks5://USER:PASS@HOST:PORT)
socks5://tguser:12345@95.81.99.82:1089
```

### Как работает система прокси

```
┌─────────────────────────────────────────────────────────────┐
│                    PROXY MANAGER                            │
│                                                             │
│  proxy.txt → [проверка всех] → сортировка по latency       │
│                                                             │
│  Прокси 1 (45мс)  ──┐                                      │
│  Прокси 2 (78мс)  ──┼──→  активный прокси → arena.ai      │
│  Прокси 3 (dead)  ──┘                                      │
│                                                             │
│  При ошибке → автоматически следующий прокси               │
│  Каждые 5 мин → проверка здоровья всех прокси             │
└─────────────────────────────────────────────────────────────┘
```

### Получить бесплатные прокси

- [@MTProxyBot](https://t.me/MTProxyBot) — официальный бот Telegram
- [@proxyme](https://t.me/proxyme) — канал с прокси
- [mtpro.xyz](https://mtpro.xyz) — веб-каталог
- [@ShadowsocksR_bot](https://t.me/ShadowsocksR_bot) — SOCKS5 прокси

---

## 🤖 AI Модели

### Text — языковые модели

| Модель | Провайдер | Контекст | Лучше всего для |
|--------|-----------|---------|-----------------|
| GPT-4o | OpenAI | 128K | Общие задачи, скорость |
| Claude 3.5 Sonnet | Anthropic | 200K | Анализ, код, длинные тексты |
| Gemini 1.5 Pro | Google | **1M** | Огромные документы |
| Gemini 2.0 Flash | Google | 1M | Скорость + мультимодальность |
| o1 | OpenAI | 200K | Сложный reasoning, математика |
| DeepSeek R1 | DeepSeek | 128K | Reasoning, наука |
| Llama 3.1 405B | Meta | 128K | Open source, мощный |
| Grok-2 | xAI | 131K | Актуальные новости, юмор |

### Images — генерация изображений

| Модель | Провайдер | Разрешение | Стиль |
|--------|-----------|----------|-------|
| Flux 1.1 Pro | Black Forest | до 2048px | Фотореализм, топ 2024 |
| Midjourney v6 | Midjourney | до 2048px | Арт, кинематограф |
| DALL-E 3 | OpenAI | до 1024px | Универсальный |
| Stable Diffusion 3 | Stability AI | до 1536px | Художественный |
| Ideogram 2.0 | Ideogram | до 2048px | Текст в изображениях |

### Video — генерация видео

| Модель | Провайдер | Макс длина | Особенности |
|--------|-----------|-----------|-------------|
| Sora | OpenAI | 60 сек | Физика реального мира |
| Runway Gen-3 | Runway | 10 сек | Киношный стиль |
| Kling 1.5 | Kuaishou | 30 сек | Реализм движений |
| Pika 2.0 | Pika Labs | 10 сек | Быстрая генерация |

### Coding — программирование

| Модель | Провайдер | Особенности |
|--------|-----------|-------------|
| Claude 3.5 Sonnet | Anthropic | #1 для кода в 2024 |
| DeepSeek Coder V2 | DeepSeek | 338 языков программирования |
| Qwen 2.5 Coder 32B | Alibaba | Топ open source |
| Codestral | Mistral | Автодополнение, 80+ языков |

---

## 📡 API

После запуска API доступен на `http://localhost:8080`.

### Основные эндпоинты

```http
GET  /health                    — проверка работоспособности
GET  /api/v1/status             — подробный статус системы
GET  /api/v1/models             — список всех моделей
GET  /docs                      — Swagger UI документация
```

### Отправить сообщение

```bash
curl -X POST http://localhost:8080/api/v1/chat \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Напиши функцию сортировки на Python",
    "mode": "coding",
    "model": "claude-3-5-sonnet"
  }'
```

Ответ:
```json
{
  "response": "```python\ndef sort_list(lst):\n    return sorted(lst)\n```",
  "model": "claude-3-5-sonnet",
  "mode": "coding",
  "latency_ms": 1240,
  "cached": false
}
```

### Сравнить модели

```bash
curl -X POST http://localhost:8080/api/v1/chat/compare \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Что такое блокчейн?",
    "models": ["gpt-4o", "claude-3-5-sonnet", "gemini-1-5-pro"]
  }'
```

### Стриминг ответа (SSE)

```bash
curl -N http://localhost:8080/api/v1/chat/stream \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"message": "Расскажи историю про робота", "mode": "text"}'
```

### Статус задачи (для видео/изображений)

```bash
# Создать задачу
curl -X POST http://localhost:8080/api/v1/tasks \
  -d '{"type": "generate_video", "prompt": "Закат над океаном", "model": "sora"}'
# → {"task_id": "task_xyz789", "status": "queued"}

# Проверить статус
curl http://localhost:8080/api/v1/tasks/task_xyz789
# → {"status": "completed", "result": {"url": "https://..."}}
```

---

## 💻 CLI Режим

```
╔══════════════════════════════════════════════════════════════╗
║          DromDev — AI Orchestrator v1.0                    ║
║          Сервер: Amsterdam | Движок: Claude                  ║
╚══════════════════════════════════════════════════════════════╝

Доступные команды:
  /models           — список всех моделей
  /mode <name>      — переключить режим (text/images/video/coding)
  /model <name>     — переключить модель
  /compare <prompt> — сравнить ответы всех моделей
  /history          — история разговора
  /status           — статус системы
  /proxy            — статус прокси
  /exit             — выход
```

### Примеры команд

```
You > /mode coding
DromDev > ✅ Режим переключён на: Coding

You > /model deepseek-coder-v2
DromDev > ✅ Модель изменена: DeepSeek Coder V2

You > Напиши парсер JSON на Rust
DromDev > 🔄 Отправляю в DeepSeek Coder V2...
           [код через 1.8 сек]

You > /compare Объясни TCP за 2 предложения
DromDev > 🚀 Сравниваю 3 модели параллельно...
           [таблица результатов]
```

---

## ⚙️ Конфигурация (.env)

```env
# === ОСНОВНЫЕ ===
IISTUDIO_ENV=production
API_HOST=0.0.0.0
API_PORT=8080
API_SECRET_KEY=your-very-secret-key-here

# === ARENA.AI ===
ARENA_EMAIL=your@email.com
ARENA_PASSWORD=yourpassword
ARENA_BASE_URL=https://arena.ai

# === БАЗА ДАННЫХ ===
DATABASE_URL=postgresql+asyncpg://dromdev:password@localhost:5432/dromdev
REDIS_URL=redis://localhost:6379/0

# === ПРОКСИ ===
PROXY_FILE=proxy.txt
PROXY_CHECK_INTERVAL=300

# === БРАУЗЕР ===
BROWSER_HEADLESS=true
BROWSER_TIMEOUT=60000

# === КЭШ ===
CACHE_TTL=3600

# === УВЕДОМЛЕНИЯ (опционально) ===
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
```

---

## 📊 Мониторинг

### Prometheus метрики

```bash
# Доступны на:
curl http://localhost:9090/metrics
```

Доступные метрики:
- `dromdev_requests_total` — общее количество запросов
- `dromdev_response_time_seconds` — время ответа
- `dromdev_cache_hit_rate` — процент попаданий в кэш
- `dromdev_proxy_latency_ms` — задержка прокси
- `dromdev_model_errors_total` — ошибки по моделям

### Grafana дашборд

```bash
# Импортировать готовый дашборд
docker-compose -f docker-compose.monitoring.yml up -d
# Открыть: http://localhost:3000
# Login: admin / admin
```

---

## 🏗️ Архитектура

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          DromDev ARCHITECTURE                              │
├─────────────────────────────────────────────────────────────────────────────┤
│  [USER LAYER]                                                               │
│   CLI  |  REST API  |  Telegram Bot  |  Web Dashboard                      │
├─────────────────────────────────────────────────────────────────────────────┤
│  [ORCHESTRATION] ← Claude Agent (prompt.txt)                               │
│   Task Router  |  Model Selector  |  Priority Queue  |  Context Manager    │
├─────────────────────────────────────────────────────────────────────────────┤
│  [PARSING LAYER]                                                            │
│   Playwright Browser  |  Proxy Manager  |  Session Manager                 │
├─────────────────────────────────────────────────────────────────────────────┤
│  [MODEL LAYER] — arena.ai                                                  │
│   GPT-4o | Claude 3.5 | Gemini 1.5 | Llama 3 | DALL-E | Sora | ...       │
├─────────────────────────────────────────────────────────────────────────────┤
│  [INFRASTRUCTURE]                                                           │
│   PostgreSQL  |  Redis  |  MTProto Proxy  |  Amsterdam VPS                 │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 🗂️ Структура проекта

```
dromdev/
├── main.py                    # Точка входа
├── config.py                  # Конфигурация
├── requirements.txt           # Зависимости
├── proxy.txt                  # MTProto/SOCKS5 прокси (не в git!)
├── prompt.txt                 # Системный промт для Claude
├── .env                       # Конфигурация (не в git!)
├── .env.example               # Пример конфигурации
├── Dockerfile                 # Docker образ
├── docker-compose.yml         # Docker стек
├── ecosystem.config.js        # pm2 конфиг
│
├── core/                      # Ядро системы
│   ├── agent.py               # Главный агент
│   ├── orchestrator.py        # Оркестратор
│   └── context.py             # Контекст диалога
│
├── parsers/                   # Парсинг arena.ai
│   ├── arena_parser.py        # Основной парсер
│   ├── browser_manager.py     # Управление браузером
│   └── selectors.py           # CSS/XPath селекторы
│
├── models/                    # Управление AI моделями
│   ├── model_manager.py       # Реестр моделей
│   ├── model_selector.py      # Умный выбор модели
│   └── definitions.py         # Определения моделей
│
├── proxy/                     # Прокси менеджер
│   ├── proxy_manager.py       # Управление пулом
│   ├── mtproto_tunnel.py      # MTProto туннель
│   └── health_checker.py      # Проверка прокси
│
├── api/                       # REST API (FastAPI)
│   ├── server.py
│   └── routes/
│       ├── chat.py
│       ├── models.py
│       └── tasks.py
│
├── cache/                     # Кэширование
│   └── cache_manager.py
│
├── storage/                   # База данных
│   ├── database.py
│   └── models/
│
├── utils/                     # Утилиты
│   ├── logger.py
│   └── helpers.py
│
└── tests/                     # Тесты
    ├── test_parser.py
    └── test_proxy.py
```

---

## 🔒 Безопасность

- ✅ Все API запросы аутентифицированы через Bearer токен
- ✅ Пароли хранятся как bcrypt хэш
- ✅ Все соединения через TLS 1.3
- ✅ Rate limiting: 60 запросов/мин по умолчанию
- ✅ Защита от Prompt Injection
- ✅ Логи не содержат чувствительных данных
- ✅ `.env` и `proxy.txt` в `.gitignore`

---

## 🤝 Вклад в проект

```bash
# Fork → Clone → Branch → Commit → PR
git checkout -b feature/my-feature
git commit -m "feat: добавил поддержку новой модели"
git push origin feature/my-feature
```

---

## 📜 Лицензия

MIT License — используй свободно, упоминай авторство.

---

<div align="center">

**◈ DromDev — Один инструмент, все нейросети мира ◈**

*Сервер: Amsterdam | Движок: Claude | Цель: доступ к любому AI*

</div>
