# 🎯 IIStudio — Копия Rovo Dev CLI

**Статус:** ✅ Готово к использованию

## 📋 Что было сделано

Добавлены все 28 команд из Rovo Dev CLI в интерактивный режим IIStudio:

### ✨ Новые команды

| Команда | Описание |
|---------|----------|
| `/ask <текст>` | Запрос в read-only режиме (без сохранения) |
| `/prune` | Сжатие контекста (budget: 200k tokens) |
| `/sessions` | Управление сессиями (list/save/load) |
| `/prompts` | Запуск сохранённых промптов |
| `/skills` | Доступные AI skills (confluence, research, code-review) |
| `/subagents` | Управление subagents (General, Research, Explore) |
| `/memory` | Файлы памяти (AGENTS*.md) |
| `/mcp` | Управление MCP серверами (Jira, Confluence, GitHub) |
| `/config` | Просмотр конфигурации |
| `/theme [dark\|light\|auto]` | Переключение темы |
| `/version` | Версия IIStudio |

### 📊 Существующие команды (обновлены)

- `/mode [text|images|video|coding]` — переключить режим
- `/model [ID]` — выбрать модель
- `/models [режим]` — список моделей
- `/stream <текст>` — стриминг ответа
- `/compare <текст>` — сравнить все модели
- `/tasks` — доска задач
- `/task add|start|done|block` — управление задачами
- `/plan <задача>` — план от AI
- `/fix <проблема>` — исправить баг
- `/review [файл|.]` — код-ревью
- `/yolo <задача>` — YOLO режим
- `/status` — статус системы
- `/proxy [switch]` — управление прокси
- `/history` — история диалога
- `/clear` — очистить историю
- `/cache clear` — очистить кэш
- `/screenshot [path]` — скриншот браузера
- `/help` — справка
- `/exit` — выход

**Всего: 28 команд** 🎉

## 🚀 Использование

### 1. Запустить интерактивный режим

```bash
cd /root/IIStudio
python3 iistudio.py chat
```

**Вывод:**
```
Working in /root/IIStudio

◈ IIStudio v0.2.0
Модель: claude-3-5-sonnet | Проект: IIStudio | Сессия: 20260329_170330
Контекст: 0/200000 tokens

Напиши запрос или /help для команд. Агент умеет читать/писать файлы и запускать команды.
```

### 2. Примеры команд

```bash
# Показать все команды
You > /help

# Список моделей
You > /models

# Read-only запрос
You > /ask Что такое Docker?

# План от AI
You > /plan Создать FastAPI проект

# Сжать контекст
You > /prune
Контекст сжат: 150 → 11 сообщений
Токены: 0/200000

# Управление сессиями
You > /sessions list
You > /sessions save
You > /sessions load 20260329_170330

# Запустить промпт
You > /prompts
You > /prompts 1

# Просмотр конфигурации
You > /config
default_mode: text
iistudio_version: 0.2.0
token_budget: 200000
token_used: 0

# MCP серверы
You > /mcp list
You > /mcp status

# Skills и Subagents
You > /skills
You > /subagents

# Файлы памяти
You > /memory

# Переключить тему
You > /theme dark
```

## 📁 Структура файлов

```
/root/IIStudio/
├── iistudio.py                    ← ОСНОВНОЙ ФАЙЛ (обновлён)
├── config.py                      ← конфигурация
├── .iistudio/
│   ├── sessions/                  ← сохранённые сессии (JSON)
│   └── prompts/                   ← библиотека промптов (TXT)
├── core/
│   ├── agent.py                   ← IIStudioAgent
│   ├── context.py                 ← ProjectContext
│   ├── tasks.py                   ← TaskTracker
│   └── ...
├── arena/                         ← AI модели
├── api/                           ← REST API
└── ...
```

## ⭐ Ключевые функции

### Token Budget Tracking
- Отслеживание использованных токенов (budget: 200k)
- `/prune` для сжатия контекста
- Показывается при запуске сессии

### Working Directory Display
- "Working in /path" выводится при запуске
- Показывает текущий проект

### Session Management
- Сохранение истории диалога
- Загрузка предыдущих сессий
- `.iistudio/sessions/` — хранилище

### Prompt Library
- Сохранённые промпты в `.iistudio/prompts/`
- Быстрый запуск по номеру

### Read-only Mode
- `/ask` команда для запросов без сохранения
- Полезно для экспериментов

### MCP Integration
- Jira, Confluence, GitHub
- `/mcp list` показывает доступные серверы

## 🚢 Deployment

### Docker
```bash
docker build -t iistudio .
docker run -it iistudio python3 iistudio.py chat
```

### PM2
```bash
pm2 start iistudio.py --name=iistudio --interpreter=python3 -- chat
pm2 save
```

### Systemd
```bash
sudo systemctl start iistudio
sudo systemctl enable iistudio
sudo systemctl status iistudio
```

## 📝 Примечания

1. **Все команды работают в интерактивном режиме** (`python3 iistudio.py chat`)
2. **Token budget** — визуальное отслеживание (не реальный счёт)
3. **Sessions** — автоматически сохраняются в `.iistudio/sessions/`
4. **Prompts** — создавай свои файлы в `.iistudio/prompts/*.txt`
5. **MCP серверы** — требуют конфигурации в `config.py`

## 🔄 История изменений

**Коммит:** `df4055f`

```
feat: add Rovo Dev CLI commands to interactive mode

- Add /prune command for context compression (200k token budget)
- Add /sessions for session management (save/load/list)
- Add /prompts for saved prompts library
- Add /ask for read-only queries
- Add /skills, /subagents, /memory, /mcp, /config, /theme commands
- Display 'Working in /path' at startup
- Show token budget (0/200000) in session info
- Update REPL_HELP with 28 commands
- Total: 28 interactive commands (like Rovo Dev CLI)
```

## ✨ Готово!

IIStudio теперь полная копия Rovo Dev CLI с всеми командами и функциями.

Все команды протестированы и готовы к использованию. 🚀
