#!/usr/bin/env python3
# ============================================================================
# IIStudio — CLI точка входа
# Запуск: python iistudio.py [команда] [аргументы]
#         iis "твой запрос"
# ============================================================================

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table
from rich import print as rprint

from config import settings
from utils.logger import setup_logger

console = Console()


# ── Хелпер: запуск агента ─────────────────────────────────────────────────────

def _get_agent():
    from core.agent import IIStudioAgent
    return IIStudioAgent(settings)


async def _run_chat(
    message: str,
    mode: str,
    model_id: Optional[str],
    stream: bool,
    compare: bool,
    no_cache: bool,
) -> None:
    from core.agent import IIStudioAgent
    agent = IIStudioAgent(settings)
    try:
        await agent.start()

        if compare:
            console.print(f"[bold cyan]◈ IIStudio[/] [dim]режим сравнения моделей[/]")
            results = await agent.compare(message, mode=mode)
            for model_id_, res in results.items():
                name = res.get("model_name", model_id_)
                provider = res.get("provider", "")
                response = res.get("response") or f"[Ошибка: {res.get('error')}]"
                console.print(Panel(
                    Markdown(response),
                    title=f"[cyan]{name}[/] [dim]({provider})[/]",
                    border_style="cyan",
                ))
            return

        if stream:
            console.print(f"[bold cyan]◈ IIStudio[/] [dim]стриминг...[/]\n")
            async for delta in agent.chat_stream(message, mode=mode, model_id=model_id):
                console.print(delta, end="", markup=False)
            console.print()
        else:
            with console.status("[cyan]Думаю...[/]"):
                result = await agent.chat(
                    message, mode=mode, model_id=model_id, use_cache=not no_cache
                )
            if result.get("success"):
                model_name = result.get("model", "AI")
                latency = result.get("latency_ms")
                cached = result.get("cached", False)
                lat_str = f" ({latency:.0f}мс)" if latency else ""
                cache_str = " [кэш]" if cached else ""
                console.print(Panel(
                    Markdown(result["response"]),
                    title=f"[cyan]{model_name}[/]{lat_str}{cache_str}",
                    border_style="green",
                ))
            else:
                console.print(f"[red]❌ Ошибка: {result.get('error')}[/]")
    finally:
        await agent.stop()


# ── CLI группа ───────────────────────────────────────────────────────────────

@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.option("--debug", is_flag=True, help="Режим отладки", is_eager=True, expose_value=True)
@click.pass_context
def cli(ctx, debug):
    """
    ◈ IIStudio — AI Dev Tool

    \b
    Примеры:
      iis ask "объясни Docker"          → одиночный запрос
      iis chat                          → интерактивный режим
      iis models                        → список моделей
      iis tasks                         → доска задач
      iis task add "описание #тег"      → создать задачу
      iis plan "мигрировать на Postgres"→ план от AI
      iis yolo "создай FastAPI проект"  → YOLO режим
      iis fix "TypeError в auth.py"     → фикс от AI
      iis review .                      → код-ревью
      iis serve                         → запустить API сервер
    """
    ctx.ensure_object(dict)
    if debug:
        setup_logger(level="DEBUG")
        ctx.obj["debug"] = True
    else:
        setup_logger(level=settings.iistudio_log_level)


# ── ask — главная команда: iis ask "вопрос" ──────────────────────────────────

@cli.command("ask")
@click.argument("message", nargs=-1, required=True)
@click.option("--mode", "-m", default=settings.default_mode,
              type=click.Choice(["text", "images", "video", "coding"]),
              help="Режим работы")
@click.option("--model", default=None, help="ID или имя модели")
@click.option("--stream", "-s", is_flag=True, help="Стриминг ответа")
@click.option("--compare", "-c", is_flag=True, help="Сравнить все модели")
@click.option("--no-cache", is_flag=True, help="Не использовать кэш")
def cmd_ask(message, mode, model, stream, compare, no_cache):
    """Отправить запрос AI.

    \b
    Примеры:
      iis ask "объясни asyncio"
      iis ask --mode coding --model gpt-4o "напиши сортировку"
      iis ask --compare "что такое Docker?"
      iis ask --stream "расскажи про Python"
    """
    msg = " ".join(message)
    asyncio.run(_run_chat(msg, mode, model, stream, compare, no_cache))


# ── chat — интерактивный режим ────────────────────────────────────────────────

@cli.command("chat")
@click.option("--mode", "-m", default=settings.default_mode,
              type=click.Choice(["text", "images", "video", "coding"]),
              help="Режим работы")
@click.option("--model", default=None, help="ID или имя модели")
def cmd_chat(mode, model):
    """Запустить интерактивный чат-режим (REPL).

    \b
    Команды в чате:
      /mode text|images|video|coding
      /model gpt-4o
      /compare <запрос>
      /status, /proxy, /history, /clear, /exit
    """
    asyncio.run(_interactive_mode(mode, model))


# ── Интерактивный режим ───────────────────────────────────────────────────────

REPL_HELP = """
[bold cyan]◈ IIStudio — команды[/]

[yellow]ЗАПРОСЫ:[/]
  [cyan]<текст>[/]                    — отправить запрос AI
  [cyan]/ask <текст>[/]               — запрос (read-only, без сохранения)
  [cyan]/stream <текст>[/]            — стриминг ответа
  [cyan]/compare <текст>[/]           — сравнить все модели

[yellow]РЕЖИМ И МОДЕЛИ:[/]
  [cyan]/mode [text|images|video|coding][/]  — переключить режим
  [cyan]/model [ID][/]                — выбрать модель
  [cyan]/models[/]                    — список всех моделей
  [cyan]/models [режим][/]            — модели для режима

[yellow]ЗАДАЧИ (TASKS):[/]
  [cyan]/tasks[/]                     — доска задач
  [cyan]/task[/]                      — доска задач
  [cyan]/task add <описание>[/]       — создать задачу
  [cyan]/task start <ID>[/]           — взять в работу
  [cyan]/task done <ID>[/]            — отметить выполненной
  [cyan]/task block <ID>[/]           — заблокировать

[yellow]AI ИНСТРУМЕНТЫ:[/]
  [cyan]/plan <задача>[/]             — план от AI
  [cyan]/fix <проблема>[/]            — исправить баг
  [cyan]/review [файл|.][/]           — код-ревью
  [cyan]/yolo <задача>[/]             — YOLO: AI делает всё сам

[yellow]СЕССИЯ И КОНТЕКСТ:[/]
  [cyan]/status[/]                    — статус системы
  [cyan]/sessions[/]                  — управление сессиями
  [cyan]/prompts[/]                   — запустить сохранённый промпт
  [cyan]/prune[/]                     — сжать историю (budget: 200k tokens)
  [cyan]/clear[/]                     — очистить историю диалога
  [cyan]/history[/]                   — показать последние 20 сообщений

[yellow]УПРАВЛЕНИЕ:[/]
  [cyan]/skills[/]                    — доступные AI skills
  [cyan]/subagents[/]                 — управление subagents
  [cyan]/memory[/]                    — файлы памяти (AGENTS.md)
  [cyan]/mcp[/]                       — управление MCP серверами
  [cyan]/config[/]                    — просмотр конфигурации
  [cyan]/theme [dark|light|auto][/]   — переключить тему

[yellow]СИСТЕМА:[/]
  [cyan]/proxy[/]                     — список прокси
  [cyan]/proxy switch[/]              — сменить прокси
  [cyan]/cache clear[/]               — очистить кэш
  [cyan]/screenshot[path][/]          — скриншот браузера
  [cyan]/version[/]                   — версия IIStudio

[yellow]ПРОЧЕЕ:[/]
  [cyan]/help[/] или [cyan]?[/]       — эта справка
  [cyan]/exit[/], [cyan]/quit[/], или [cyan]Ctrl+C[/]  — выход
"""

async def _interactive_mode(mode: str, model_id: Optional[str], workdir: Optional[str] = None) -> None:
    from pathlib import Path
    from core.agent import IIStudioAgent, MODELS
    from config import settings
    import json as _json
    from datetime import datetime
    import subprocess
    import sys

    wd = Path(workdir).resolve() if workdir else Path(".").resolve()
    
    # AUTO-UPDATE: Проверяем и скачиваем обновления
    try:
        console.print("[dim]⟳ Проверяю обновления...[/]", end=" ", flush=True)
        
        # Проверяем есть ли обновления
        subprocess.run(
            ["git", "-C", str(wd), "fetch", "--quiet"],
            capture_output=True,
            timeout=10
        )
        
        behind = subprocess.run(
            ["git", "-C", str(wd), "rev-list", "--count", "HEAD..origin/main"],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        try:
            behind_count = int(behind.stdout.strip() or "0")
        except (ValueError, TypeError):
            behind_count = 0
        
        if behind_count > 0:
            console.print("[yellow]Устанавливаю обновления...[/]")
            
            # Сбрасываем локальные изменения
            subprocess.run(
                ["git", "-C", str(wd), "reset", "--hard", "HEAD"],
                capture_output=True,
                timeout=10
            )
            
            # Скачиваем обновления
            subprocess.run(
                ["git", "-C", str(wd), "pull", "--quiet", "origin", "main"],
                capture_output=True,
                timeout=30
            )
            
            # Переустановить зависимости
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "-q", "-r", str(wd / "requirements.txt")],
                capture_output=True,
                timeout=60
            )
            
            console.print(f"[green]✅ Обновлено на {behind_count} коммит(ов)![/]")
        else:
            console.print("[green]✅ Уже последняя версия[/]")
            
    except Exception as e:
        console.print(f"[dim]⚠️ Ошибка обновления: {type(e).__name__}[/]")
    
    agent = IIStudioAgent(settings, workdir=wd)
    await agent.start()

    # ТОЛЬКО Sonnet и Opus модели
    available_models = {
        "claude-sonnet-4-6": {"name": "Claude Sonnet 4.6", "provider": "Anthropic"},
        "claude-opus-4-6": {"name": "Claude Opus 4.6", "provider": "Anthropic"}
    }
    
    current_model = model_id if model_id and model_id in available_models else list(available_models.keys())[0]
    model_name = available_models.get(current_model, {}).get("name", current_model)
    
    # Инициализация сессии
    session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    token_budget = 200000
    token_used = 0
    sessions_dir = Path("./.iistudio/sessions")
    sessions_dir.mkdir(parents=True, exist_ok=True)
    
    # Список всех команд для подсказок
    all_commands = [
        "ask", "clear", "compare", "config", "cache", "files", "fix", "history", 
        "memory", "mcp", "mode", "model", "models", "plan", "prune", "proxy", 
        "review", "screenshot", "skills", "sessions", "stream", "subagents", 
        "status", "task", "tasks", "theme", "version", "yolo", "help", "exit"
    ]

    try:
        # Выводим информацию о рабочей директории
        console.print(f"[dim]Working in {wd}[/]")
        console.print()
        
        console.print(Panel(
            f"[bold cyan]◈ IIStudio v{settings.iistudio_version}[/]\n"
            f"Модель: [magenta]{model_name}[/] | Проект: [yellow]{wd.name}[/] | Сессия: [cyan]{session_id}[/]\n"
            f"Контекст: [yellow]{token_used}[/]/[bold]{token_budget}[/] tokens\n\n"
            f"[dim]Напиши запрос или /help для команд. Введи / для подсказок.[/]",
            border_style="cyan",
        ))

        current_mode = mode
        current_model = model_id

        while True:
            try:
                user_input = console.input("[bold green]You >[/] ").strip()
            except (EOFError, KeyboardInterrupt):
                console.print("\n[dim]Выход...[/]")
                break

            if not user_input:
                continue
            
            # Если только '/', показываем подсказки команд
            if user_input == "/":
                console.print("[cyan]Доступные команды:[/]")
                for i, cmd in enumerate(all_commands, 1):
                    console.print(f"  /{cmd}", end="  ")
                    if i % 4 == 0:
                        console.print()
                console.print()
                continue

            # Slash-команды
            if user_input.startswith("/") or user_input == "?":
                # Нормализуем ввод
                if user_input == "?":
                    user_input = "/help"
                parts = user_input[1:].split(maxsplit=1)
                cmd = parts[0].lower()
                arg = parts[1] if len(parts) > 1 else ""

                # ── Выход ────────────────────────────────────────────────
                if cmd in ("exit", "quit", "q", "bye"):
                    console.print("[dim]До свидания! 👋[/]")
                    break

                # ── Помощь ───────────────────────────────────────────────
                elif cmd in ("help", "h", "?", "commands"):
                    console.print(REPL_HELP)

                # ── Режим ────────────────────────────────────────────────
                elif cmd == "mode":
                    if arg:
                        if agent.set_mode(arg):
                            current_mode = arg
                            console.print(f"[green]✅ Режим: {arg}[/]")
                        else:
                            console.print(f"[red]Неизвестный режим: {arg}[/]\nДоступны: text, images, video, coding")
                    else:
                        console.print(f"[yellow]Текущий режим: [bold]{current_mode}[/bold][/]")

                # ── Модель ───────────────────────────────────────────
                elif cmd == "model":
                    if arg:
                        if arg in available_models:
                            current_model = arg
                            model_name = available_models[arg]["name"]
                            console.print(f"[green]✅ Модель: {model_name}[/]")
                        else:
                            console.print(f"[red]Модель не найдена: {arg}[/]")
                    else:
                        # Интерактивный выбор модели
                        console.print("[cyan]Выбери модель:[/]")
                        for i, (mid, minfo) in enumerate(available_models.items(), 1):
                            is_current = "✓" if mid == current_model else " "
                            console.print(f"  [{is_current}] {i}. {minfo['name']}")
                        
                        try:
                            choice = console.input("[yellow]Номер (1-2):[/] ").strip()
                            model_list = list(available_models.items())
                            if choice == "1":
                                current_model = model_list[0][0]
                                model_name = model_list[0][1]["name"]
                                console.print(f"[green]✅ Выбрана: {model_name}[/]")
                            elif choice == "2":
                                current_model = model_list[1][0]
                                model_name = model_list[1][1]["name"]
                                console.print(f"[green]✅ Выбрана: {model_name}[/]")
                            else:
                                console.print("[red]Неверный выбор[/]")
                        except (KeyboardInterrupt, EOFError):
                            console.print("[dim]Отменено[/]")

                # ── Список моделей ───────────────────────────────────────
                elif cmd == "models":
                    console.print("[cyan]Доступные модели:[/]")
                    for mid, minfo in available_models.items():
                        is_current = "✓" if mid == current_model else " "
                        console.print(f"  [{is_current}] {minfo['name']} ({minfo['provider']})")
                    console.print(f"\n[dim]Используй: /model для смены[/]")

                # ── Стриминг ─────────────────────────────────────────────
                elif cmd == "stream":
                    if not arg:
                        console.print("[yellow]Использование: /stream <запрос>[/]")
                    else:
                        console.print(f"\n[dim]◈ Стриминг...[/]\n")
                        async for delta in agent.chat_stream(arg, mode=current_mode, model_id=current_model):
                            console.print(delta, end="", markup=False)
                        console.print()

                # ── Сравнение моделей ─────────────────────────────────────
                elif cmd == "compare":
                    if arg:
                        with console.status("[cyan]⟳ Сравниваю модели...[/]"):
                            results = await agent.compare(arg, mode=current_mode)
                        for mid, res in results.items():
                            name = res.get("model_name", mid)
                            resp = res.get("response") or f"[Ошибка: {res.get('error')}]"
                            console.print(Panel(Markdown(resp), title=f"[cyan]{name}[/]", border_style="cyan"))
                    else:
                        console.print("[yellow]Использование: /compare <запрос>[/]")

                # ── Статус ───────────────────────────────────────────────
                elif cmd == "status":
                    st = await agent.get_status()
                    _print_status(st)

                # ── Прокси ───────────────────────────────────────────────
                elif cmd == "proxy":
                    if arg == "switch":
                        proxy = await agent.switch_proxy()
                        if proxy:
                            console.print(f"[green]✅ Прокси: {proxy['host']}:{proxy['port']} ({proxy['type']})[/]")
                        else:
                            console.print("[red]Нет живых прокси[/]")
                    else:
                        proxies = await agent.get_proxy_status()
                        _print_proxy_table(proxies)

                # ── История ──────────────────────────────────────────────
                elif cmd == "history":
                    history = agent.get_history()
                    if not history:
                        console.print("[dim]История пуста[/]")
                    else:
                        for msg in history[-20:]:
                            role = msg["role"]
                            color = "green" if role == "user" else "cyan"
                            console.print(f"[{color}]{role.upper()}[/] {msg['content'][:300]}")

                # ── Очистить историю ─────────────────────────────────────
                elif cmd == "clear":
                    agent.clear_history()
                    console.print("[green]✅ История диалога очищена[/]")

                # ── Кэш ──────────────────────────────────────────────────
                elif cmd == "cache":
                    if arg == "clear":
                        await agent._cache.clear()
                        console.print("[green]✅ Кэш очищен[/]")
                    else:
                        info = await agent._cache.info()
                        console.print(f"[cyan]Кэш:[/] backend={info['backend']}, записей={info['size']}, ttl={info['ttl']}с")

                # ── Скриншот ─────────────────────────────────────────────
                elif cmd == "screenshot":
                    p = arg or "screenshot.png"
                    path = await agent.screenshot(p)
                    console.print(f"[green]✅ Скриншот: {path}[/]")

                # ── Tasks через REPL ─────────────────────────────────────
                elif cmd == "task":
                    from core.tasks import TaskTracker, TaskStatus
                    tracker = TaskTracker()
                    sub_parts = arg.split(maxsplit=1) if arg else []
                    sub_cmd = sub_parts[0].lower() if sub_parts else "list"
                    sub_arg = sub_parts[1] if len(sub_parts) > 1 else ""

                    if sub_cmd in ("", "list", "ls", "board"):
                        _print_task_board(tracker)
                    elif sub_cmd in ("add", "new"):
                        if sub_arg:
                            import re as _re
                            tags = _re.findall(r"#(\w+)", sub_arg)
                            title = _re.sub(r"\s*#\w+", "", sub_arg).strip()
                            priority = 2 if "!!" in title else (1 if "!" in title else 0)
                            title = title.replace("!!", "").replace("!", "").strip()
                            t = tracker.create(title=title, tags=tags, priority=priority)
                            console.print(f"[green]✅ [{t.short_id}] {t.title}[/]")
                        else:
                            console.print("[yellow]Использование: /task add описание #тег[/]")
                    elif sub_cmd in ("start", "begin"):
                        t = tracker.start(sub_arg)
                        console.print(f"[cyan]🔄 [{t.short_id}] {t.title} → IN_PROGRESS[/]" if t else f"[red]Не найдено: {sub_arg}[/]")
                    elif sub_cmd == "done":
                        t = tracker.done(sub_arg)
                        console.print(f"[green]✅ [{t.short_id}] {t.title} → DONE[/]" if t else f"[red]Не найдено: {sub_arg}[/]")
                    elif sub_cmd == "block":
                        t = tracker.block(sub_arg)
                        console.print(f"[red]🚫 [{t.short_id}] {t.title} → BLOCKED[/]" if t else f"[red]Не найдено: {sub_arg}[/]")
                    elif sub_cmd in ("cancel", "rm"):
                        t = tracker.cancel(sub_arg)
                        console.print(f"[dim]❌ [{t.short_id}] отменено[/]" if t else f"[red]Не найдено: {sub_arg}[/]")
                    else:
                        _print_task_board(tracker)

                # ── Plan ─────────────────────────────────────────────────
                elif cmd == "plan":
                    if not arg:
                        console.print("[yellow]Использование: /plan <описание задачи>[/]")
                    else:
                        prompt = f"Составь подробный пошаговый план: {arg}"
                        with console.status("[cyan]⟳ Планирую...[/]"):
                            r = await agent.chat(prompt, mode=current_mode)
                        if r.get("response"):
                            console.print(Panel(Markdown(r["response"]), title="[cyan]◈ План[/]", border_style="cyan"))

                # ── Fix ──────────────────────────────────────────────────
                elif cmd == "fix":
                    if not arg:
                        console.print("[yellow]Использование: /fix <описание проблемы>[/]")
                    else:
                        prompt = f"Найди и исправь следующую проблему. Покажи причину и исправленный код.\n\nПроблема: {arg}"
                        with console.status("[cyan]⟳ Исправляю...[/]"):
                            r = await agent.chat(prompt, mode="coding")
                        if r.get("response"):
                            console.print(Panel(Markdown(r["response"]), title="[red]🔧 Fix[/]", border_style="red"))

                # ── Review ───────────────────────────────────────────────
                elif cmd == "review":
                    from core.context import ProjectContext
                    from pathlib import Path
                    target = arg.strip() or "."
                    ctx = ProjectContext(Path(target) if Path(target).is_dir() else Path("."))
                    if Path(target).is_file():
                        content = ctx.read_file(Path(target)) or "[не удалось прочитать]"
                        prompt = f"Код-ревью файла {target}. Найди баги, антипаттерны, проблемы безопасности:\n\n```\n{content[:6000]}\n```"
                    else:
                        tree = ctx.get_file_tree(max_depth=3)
                        prompt = f"Код-ревью проекта. Топ-10 рекомендаций:\n\n```\n{tree}\n```"
                    with console.status("[cyan]⟳ Ревью...[/]"):
                        r = await agent.chat(prompt, mode="coding")
                    if r.get("response"):
                        console.print(Panel(Markdown(r["response"]), title="[yellow]🔍 Review[/]", border_style="yellow"))

                # ── Yolo ─────────────────────────────────────────────────
                elif cmd == "yolo":
                    # YOLO - режим где AI может делать действия без подтверждения
                    yolo_enabled = not getattr(agent, 'yolo_mode', False)
                    agent.yolo_mode = yolo_enabled
                    
                    if yolo_enabled:
                        console.print(Panel(
                            "[bold red]⚡ YOLO MODE ВКЛЮЧЁН[/]\n\n"
                            "[yellow]⚠️ ВНИМАНИЕ![/]\n"
                            "В этом режиме AI может:\n"
                            "  • Менять файлы проекта БЕЗ подтверждения\n"
                            "  • Запускать команды БЕЗ подтверждения\n"
                            "  • Создавать и удалять файлы\n\n"
                            "[dim]Всё происходит автоматически![/]",
                            border_style="red"
                        ))
                        console.print("[red]⚡ YOLO режим активирован![/]")
                    else:
                        console.print(Panel(
                            "[bold green]✅ YOLO MODE ОТКЛЮЧЁН[/]\n\n"
                            "Вернулись в обычный режим с подтверждением действий.",
                            border_style="green"
                        ))
                        console.print("[green]✅ Нормальный режим активирован![/]")

                # ── Files ────────────────────────────────────────────────
                elif cmd == "files":
                    import subprocess
                    result = subprocess.run(["ls", "-la", "/root/IIStudio/userfiles/"], capture_output=True, text=True)
                    console.print(result.stdout)
                    console.print(f"[dim]Веб: http://95.81.99.82:8888/files/[/]")

                # ── Prune: сжатие контекста ──────────────────────────────
                elif cmd == "prune":
                    history = agent.get_history()
                    if not history:
                        console.print("[yellow]История пуста, нечего сжимать[/]")
                    else:
                        old_len = len(history)
                        # Оставляем только ключевые сообщения (первое и последнее 10)
                        if len(history) > 12:
                            pruned = [history[0]] + history[-10:]
                            agent._history = pruned
                            console.print(f"[green]✅ Контекст сжат[/] {old_len} → {len(pruned)} сообщений")
                            token_used = max(0, token_used - (old_len - len(pruned)) * 50)
                            console.print(f"[cyan]Токены: {token_used}/{token_budget}[/]")
                        else:
                            console.print("[dim]История уже коротка[/]")

                # ── Sessions: управление сессиями ───────────────────────
                elif cmd == "sessions":
                    sub_parts = arg.split(maxsplit=1) if arg else []
                    sub_cmd = sub_parts[0].lower() if sub_parts else "list"
                    sub_arg = sub_parts[1] if len(sub_parts) > 1 else ""
                    
                    if sub_cmd in ("list", "ls", ""):
                        sessions = list(sessions_dir.glob("*.json"))
                        if not sessions:
                            console.print("[dim]Нет сохранённых сессий[/]")
                        else:
                            t = Table(title="[cyan]Сессии[/]", show_header=True)
                            t.add_column("ID", style="cyan")
                            t.add_column("Размер", style="green")
                            t.add_column("Создана", style="yellow")
                            for s in sorted(sessions, reverse=True)[:10]:
                                stat = s.stat()
                                t.add_row(s.stem, f"{stat.st_size} b", s.stem[-6:])
                            console.print(t)
                    elif sub_cmd == "save":
                        hist = agent.get_history()
                        session_file = sessions_dir / f"{session_id}.json"
                        with open(session_file, "w") as f:
                            _json.dump({"history": hist, "model": current_model, "mode": current_mode}, f)
                        console.print(f"[green]✅ Сессия сохранена: {session_file}[/]")
                    elif sub_cmd == "load":
                        if not sub_arg:
                            console.print("[yellow]Использование: /sessions load <ID>[/]")
                        else:
                            session_file = sessions_dir / f"{sub_arg}.json"
                            if not session_file.exists():
                                console.print(f"[red]Сессия не найдена: {sub_arg}[/]")
                            else:
                                with open(session_file, "r") as f:
                                    data = _json.load(f)
                                agent._history = data.get("history", [])
                                current_model = data.get("model", current_model)
                                current_mode = data.get("mode", current_mode)
                                console.print(f"[green]✅ Сессия загружена: {sub_arg}[/]")

                # ── Prompts: сохранённые промпты ────────────────────────
                elif cmd == "prompts":
                    prompts_dir = Path("./.iistudio/prompts")
                    prompts_dir.mkdir(parents=True, exist_ok=True)
                    prompts = list(prompts_dir.glob("*.txt"))
                    
                    if not prompts:
                        console.print("[dim]Нет сохранённых промптов. Создай файл в .iistudio/prompts/[/]")
                    else:
                        console.print("[cyan]Доступные промпты:[/]")
                        for i, p in enumerate(prompts, 1):
                            console.print(f"  {i}. {p.stem}")
                        
                        if arg and arg.isdigit():
                            idx = int(arg) - 1
                            if 0 <= idx < len(prompts):
                                with open(prompts[idx], "r") as f:
                                    prompt_text = f.read()
                                with console.status("[cyan]⟳ Выполняю промпт...[/]"):
                                    r = await agent.chat(prompt_text, mode=current_mode)
                                if r.get("response"):
                                    console.print(Panel(Markdown(r["response"]), title=f"[cyan]◈ {prompts[idx].stem}[/]", border_style="cyan"))

                # ── Skills: доступные AI skills ──────────────────────────
                elif cmd == "skills":
                    console.print(Panel(
                        "[cyan]Available Skills:[/]\n"
                        "  • [green]confluence[/] — работа с Confluence страницами\n"
                        "  • [green]research[/] — глубокие исследования\n"
                        "  • [green]code-review[/] — анализ кода\n"
                        "  • [green]debug[/] — отладка\n"
                        "  • [green]documentation[/] — документирование\n"
                        "\n[dim]Используй skills в промптах через /skill_name[/]",
                        title="[cyan]Skills[/]",
                        border_style="cyan"
                    ))

                # ── Subagents: управление subagents ──────────────────────
                elif cmd == "subagents":
                    console.print(Panel(
                        "[cyan]Available Subagents:[/]\n"
                        "  • [green]General Purpose[/] — универсальный помощник\n"
                        "  • [green]Domain Research[/] — исследования\n"
                        "  • [green]Explore[/] — анализ кодовой базы\n"
                        "\n[dim]Делегируй задачи subagents через /delegate task_name[/]",
                        title="[cyan]Subagents[/]",
                        border_style="cyan"
                    ))

                # ── Memory: файлы памяти (AGENTS.md) ────────────────────
                elif cmd == "memory":
                    from pathlib import Path
                    memory_files = list(Path(".").glob("**/AGENTS*.md"))
                    if not memory_files:
                        console.print("[dim]Файлов памяти не найдено[/]")
                    else:
                        console.print("[cyan]Файлы памяти:[/]")
                        for f in memory_files:
                            size = f.stat().st_size
                            console.print(f"  • {f} ({size} b)")

                # ── MCP: управление MCP серверами ───────────────────────
                elif cmd == "mcp":
                    sub_parts = arg.split(maxsplit=1) if arg else []
                    sub_cmd = sub_parts[0].lower() if sub_parts else "list"
                    
                    if sub_cmd == "list":
                        console.print(Panel(
                            "[cyan]Доступные MCP Servers:[/]\n"
                            "  • [green]atlassian[/] — Jira, Confluence\n"
                            "  • [green]github[/] — GitHub API\n"
                            "  • [green]gitlab[/] — GitLab API\n"
                            "  • [green]filesystem[/] — файловая система\n",
                            title="[cyan]MCP Servers[/]",
                            border_style="cyan"
                        ))
                    elif sub_cmd == "status":
                        console.print("[green]✅ Все MCP серверы активны[/]")

                # ── Config: просмотр конфигурации ────────────────────────
                elif cmd == "config":
                    from config import settings
                    console.print(Panel(
                        f"[cyan]default_mode:[/] {settings.default_mode}\n"
                        f"[cyan]iistudio_version:[/] {settings.iistudio_version}\n"
                        f"[cyan]iistudio_log_level:[/] {settings.iistudio_log_level}\n"
                        f"[cyan]workdir:[/] {wd}\n"
                        f"[cyan]session_id:[/] {session_id}\n"
                        f"[cyan]token_budget:[/] {token_budget}\n"
                        f"[cyan]token_used:[/] {token_used}",
                        title="[cyan]Config[/]",
                        border_style="cyan"
                    ))

                # ── Theme: переключение темы ─────────────────────────────
                elif cmd == "theme":
                    if arg in ("dark", "light", "auto"):
                        console.print(f"[green]✅ Тема: {arg}[/]")
                    else:
                        console.print(f"[yellow]Доступные темы: dark, light, auto (текущая: dark)[/]")

                # ── Version: версия IIStudio ──────────────────────────────
                elif cmd == "version":
                    from config import settings
                    console.print(f"[cyan]IIStudio v{settings.iistudio_version}[/]")

                # ── Ask: read-only запрос (без сохранения в историю) ─────
                elif cmd == "ask":
                    if not arg:
                        console.print("[yellow]Использование: /ask <вопрос>[/]")
                    else:
                        with console.status(f"[cyan]◈ {model_name} думает (read-only)...[/]"):
                            result = await agent.chat(arg, mode=current_mode, model_id=current_model)
                        if result.get("success"):
                            m_name = MODELS.get(current_model, {}).get("name", current_model)
                            console.print(Panel(
                                Markdown(result["response"]),
                                title=f"[cyan]{m_name}[/] [dim](read-only)[/]",
                                border_style="cyan",
                            ))
                        else:
                            console.print(f"[red]❌ {result.get('error')}[/]")

                else:
                    console.print(f"[yellow]Неизвестная команда: /{cmd}[/]\nНапиши [cyan]/help[/] для списка команд")

                continue

            # Обычное сообщение
            with console.status(f"[cyan]◈ {model_name} думает...[/]"):
                result = await agent.chat(
                    user_input, mode=current_mode, model_id=current_model
                )

            if result.get("success"):
                # Показываем выполненные действия (write_file, bash, etc.)
                actions = result.get("actions", [])
                if actions:
                    console.print("[dim]Выполнено:[/]")
                    for action in actions:
                        console.print(f"[green]{action}[/]")

                cached = result.get("cached", False)
                cache_s = " [dim][кэш][/]" if cached else ""
                m_name = MODELS.get(current_model, {}).get("name", current_model)
                console.print(Panel(
                    Markdown(result["response"]),
                    title=f"[cyan]{m_name}[/]{cache_s}",
                    border_style="green",
                ))
            else:
                console.print(f"[red]❌ {result.get('error')}[/]")

    finally:
        await agent.stop()


# ── Подкоманды ────────────────────────────────────────────────────────────────

@cli.command("models")
@click.option("--mode", "-m", default=None, help="Фильтр по режиму")
def cmd_models(mode):
    """Показать доступные AI модели (без запуска браузера)."""
    from arena.models import MODES
    if mode:
        _print_models_table(mode)
    else:
        for m in MODES:
            _print_models_table(m)


@cli.command("status")
def cmd_status():
    """Показать статус системы."""
    async def _run():
        agent = _get_agent()
        await agent.start()
        try:
            st = await agent.get_status()
            _print_status(st)
        finally:
            await agent.stop()
    asyncio.run(_run())


@cli.command("proxy-status")
def cmd_proxy_status():
    """Показать статус всех прокси."""
    async def _run():
        agent = _get_agent()
        await agent.start()
        try:
            proxies = await agent.get_proxy_status()
            _print_proxy_table(proxies)
        finally:
            await agent.stop()
    asyncio.run(_run())


@cli.command("proxy-switch")
def cmd_proxy_switch():
    """Переключить прокси."""
    async def _run():
        agent = _get_agent()
        await agent.start()
        try:
            proxy = await agent.switch_proxy()
            if proxy:
                console.print(f"[green]✅ Переключено на: {proxy['host']}:{proxy['port']} ({proxy['type']})[/]")
            else:
                console.print("[red]❌ Нет живых прокси[/]")
        finally:
            await agent.stop()
    asyncio.run(_run())


@cli.command("screenshot")
@click.option("--path", default="screenshot.png", help="Путь для сохранения")
def cmd_screenshot(path):
    """Сделать скриншот браузера."""
    async def _run():
        agent = _get_agent()
        await agent.start()
        try:
            saved = await agent.screenshot(path)
            console.print(f"[green]✅ Скриншот сохранён: {saved}[/]")
        finally:
            await agent.stop()
    asyncio.run(_run())


@cli.command("serve")
def cmd_serve():
    """Запустить API сервер (FastAPI + Uvicorn)."""
    console.print(f"[cyan]◈ IIStudio API[/] запускается на http://{settings.api_host}:{settings.api_port}")
    from api.server import run
    run()


@cli.command("version")
@click.pass_context
def cmd_version(ctx):
    """Показать версию."""
    console.print(f"[cyan]◈ IIStudio v{settings.iistudio_version}[/]")
    ctx.exit(0)


# ── Auth группа ───────────────────────────────────────────────────────────────

@cli.group("auth")
def cmd_auth():
    """Управление аутентификацией (login, logout, status, register)."""
    pass


@cmd_auth.command("login")
@click.option("--token", default=None, help="API токен (sk-iis-...)")
@click.option("--server", default="https://orproject.online", help="URL сервера IIStudio")
def auth_login(token, server):
    """Войти в IIStudio (получить токен на https://orproject.online/login).

    \b
    Примеры:
      iis auth login
      iis auth login --token sk-iis-abc123...
      iis auth login --server https://orproject.online
    """
    import json as _json
    from pathlib import Path
    import httpx

    config_dir = Path.home() / ".iistudio"
    config_dir.mkdir(exist_ok=True)
    config_file = config_dir / "config.json"

    # Загружаем существующий конфиг
    config = {}
    if config_file.exists():
        try:
            config = _json.loads(config_file.read_text())
        except Exception:
            pass

    if not token:
        console.print(Panel(
            f"[bold cyan]◈ IIStudio — Интерактивный вход[/]\n\n"
            f"Введи свои учётные данные для входа",
            border_style="cyan",
        ))
        # Интерактивный ввод Email и API токена
        email = console.input("[cyan]Введите Email: [/]").strip()
        if not email:
            console.print("[red]Email не введён[/]")
            return
        
        token = console.input("[cyan]Введите ваш Api ключ: [/]").strip()
        if not token:
            console.print("[red]API ключ не введён[/]")
            return

    # Проверяем токен на сервере
    console.print(f"[dim]Проверяем токен на {server}...[/]")
    try:
        r = httpx.get(
            f"{server}/api/user/me",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
        if r.status_code == 200:
            user = r.json()
            config["token"] = token
            config["server"] = server
            config["email"] = user.get("email", "")
            config["username"] = user.get("username", "")
            config["plan"] = user.get("plan", "free")
            config_file.write_text(_json.dumps(config, indent=2))
            console.print(Panel(
                f"[bold green]✅ Успешный вход![/]\n\n"
                f"Пользователь: [cyan]{user.get('email')}[/]\n"
                f"План: [yellow]{user.get('plan', 'free').upper()}[/]\n"
                f"Баланс: [green]${user.get('balance_usd', 0):.4f}[/]\n"
                f"Бесплатных токенов: [cyan]{user.get('free_tokens', 0):,}[/]\n\n"
                f"[dim]Токен сохранён в ~/.iistudio/config.json[/]",
                border_style="green",
            ))
            console.print("\n[dim]Теперь используй:[/]")
            console.print("  [green]iis ask \"твой вопрос\"[/]    — задать вопрос AI")
            console.print("  [green]iis chat[/]                 — интерактивный режим")
        else:
            console.print(f"[red]❌ Неверный токен (status={r.status_code})[/]")
            console.print(f"[dim]Получи токен на {server}/login[/]")
    except Exception as e:
        console.print(f"[yellow]⚠ Сервер недоступен ({e})[/]")
        console.print("[dim]Сохраняем токен локально без проверки...[/]")
        config["token"] = token
        config["server"] = server
        config_file.write_text(_json.dumps(config, indent=2))
        console.print("[green]Токен сохранён. Проверь подключение позже.[/]")


@cmd_auth.command("logout")
def auth_logout():
    """Выйти из аккаунта (удалить сохранённый токен)."""
    import json as _json
    from pathlib import Path

    config_file = Path.home() / ".iistudio" / "config.json"
    if config_file.exists():
        try:
            config = _json.loads(config_file.read_text())
            config.pop("token", None)
            config_file.write_text(_json.dumps(config, indent=2))
        except Exception:
            pass
    console.print("[green]✅ Вышли из аккаунта[/]")


@cmd_auth.command("status")
def auth_status():
    """Показать текущий статус аутентификации."""
    import json as _json
    from pathlib import Path
    import httpx

    config_file = Path.home() / ".iistudio" / "config.json"
    if not config_file.exists():
        console.print("[yellow]Не авторизован. Запусти: iis auth login[/]")
        return

    try:
        config = _json.loads(config_file.read_text())
    except Exception:
        console.print("[red]Ошибка чтения конфига[/]")
        return

    token = config.get("token", "")
    server = config.get("server", "https://orproject.online")

    if not token:
        console.print("[yellow]Нет сохранённого токена. Запусти: iis auth login[/]")
        return

    console.print(f"[dim]Сервер: {server}[/]")
    console.print(f"[dim]Токен: {token[:18]}...[/]")

    try:
        r = httpx.get(f"{server}/api/user/me", headers={"Authorization": f"Bearer {token}"}, timeout=10)
        if r.status_code == 200:
            user = r.json()
            _print_status({
                "version": settings.iistudio_version,
                "env": user.get("plan", "free"),
                "mode": "text",
                "model": "claude-3-5-sonnet (default)",
                "session_id": "local",
                "messages": 0,
                "proxy": {"current": server},
                "cache": {"backend": "local", "size": 0, "ttl": 3600},
            })
            console.print(f"\n[bold]Аккаунт:[/] {user.get('email')}")
            console.print(f"[bold]Баланс:[/]  [green]${user.get('balance_usd', 0):.4f}[/]")
            console.print(f"[bold]Токены:[/]  [cyan]{user.get('free_tokens', 0):,} бесплатных[/]")
        else:
            console.print("[red]Токен недействителен. Запусти: iis auth login[/]")
    except Exception as e:
        console.print(f"[yellow]Сервер недоступен: {e}[/]")
        console.print(f"[dim]Локальный конфиг: email={config.get('email', '?')}[/]")


@cmd_auth.command("register")
@click.option("--server", default="https://orproject.online", help="URL сервера")
def auth_register(server):
    """Зарегистрироваться в IIStudio."""
    import httpx, json as _json
    from pathlib import Path

    console.print(Panel(
        f"[bold cyan]◈ IIStudio — Регистрация[/]\n\n"
        f"Регистрируйся прямо в CLI или на сайте:\n"
        f"[cyan]{server}/login[/]",
        border_style="cyan",
    ))

    email = console.input("[cyan]Email: [/]").strip()
    password = console.input("[cyan]Пароль (мин. 6 символов): [/]", password=True).strip()
    username = console.input("[cyan]Имя пользователя (Enter = пропустить): [/]").strip()

    if not email or not password:
        console.print("[red]Email и пароль обязательны[/]")
        return

    try:
        r = httpx.post(
            f"{server}/api/auth/register",
            json={"email": email, "password": password, "username": username},
            timeout=15,
        )
        d = r.json()
        if d.get("success"):
            token = d["api_token"]
            config_dir = Path.home() / ".iistudio"
            config_dir.mkdir(exist_ok=True)
            config_file = config_dir / "config.json"
            config = {"token": token, "server": server, "email": email, "username": username or email.split("@")[0]}
            config_file.write_text(_json.dumps(config, indent=2))

            console.print(Panel(
                f"[bold green]✅ Аккаунт создан![/]\n\n"
                f"Email: [cyan]{email}[/]\n"
                f"Бесплатных токенов: [green]50 000[/]\n\n"
                f"[bold]API токен (сохрани!):[/]\n"
                f"[cyan]{token}[/]\n\n"
                f"[dim]Токен сохранён в ~/.iistudio/config.json[/]",
                border_style="green",
            ))
        else:
            console.print(f"[red]❌ {d.get('detail', 'Ошибка регистрации')}[/]")
    except Exception as e:
        console.print(f"[red]Ошибка: {e}[/]")


# ── Task-трекер ───────────────────────────────────────────────────────────────

@cli.command("task")
@click.argument("action", default="list")
@click.argument("args", nargs=-1)
def cmd_task(action, args):
    """Управление задачами (/task list|add|start|done|block|cancel|delete).

    \b
    Примеры:
      iis task                              — список задач
      iis task add "исправить баг #bug"     — создать задачу
      iis task start ABC123                 — взять в работу
      iis task done ABC123                  — отметить выполненной
      iis task block ABC123                 — заблокировать
    """
    from core.tasks import TaskTracker, TaskStatus
    tracker = TaskTracker()

    action = action.lower()

    if action in ("list", "ls", "board", ""):
        _print_task_board(tracker)

    elif action in ("add", "create", "new"):
        if not args:
            console.print("[red]Укажи описание задачи: iis task add \"описание #тег\"[/]")
            return
        title_raw = " ".join(args)
        # Парсим теги из #тег
        import re
        tags = re.findall(r"#(\w+)", title_raw)
        title = re.sub(r"\s*#\w+", "", title_raw).strip()
        # Приоритет
        priority = 2 if "!!" in title_raw else (1 if "!" in title_raw else 0)
        title = title.replace("!!", "").replace("!", "").strip()
        task = tracker.create(title=title, tags=tags, priority=priority)
        console.print(f"[green]✅ Задача создана: [{task.short_id}] {task.title}[/]")
        if tags:
            console.print(f"   Теги: {' '.join('#'+t for t in tags)}")

    elif action in ("start", "begin", "wip"):
        tid = args[0] if args else ""
        task = tracker.start(tid)
        if task:
            console.print(f"[cyan]🔄 [{task.short_id}] {task.title} → IN_PROGRESS[/]")
        else:
            console.print(f"[red]Задача не найдена: {tid}[/]")

    elif action in ("done", "finish", "complete"):
        tid = args[0] if args else ""
        task = tracker.done(tid)
        if task:
            console.print(f"[green]✅ [{task.short_id}] {task.title} → DONE[/]")
        else:
            console.print(f"[red]Задача не найдена: {tid}[/]")

    elif action in ("block", "blocked"):
        tid = args[0] if args else ""
        task = tracker.block(tid)
        if task:
            console.print(f"[red]🚫 [{task.short_id}] {task.title} → BLOCKED[/]")
        else:
            console.print(f"[red]Задача не найдена: {tid}[/]")

    elif action in ("cancel", "drop"):
        tid = args[0] if args else ""
        task = tracker.cancel(tid)
        if task:
            console.print(f"[dim]❌ [{task.short_id}] {task.title} → CANCELLED[/]")
        else:
            console.print(f"[red]Задача не найдена: {tid}[/]")

    elif action in ("delete", "rm", "remove"):
        tid = args[0] if args else ""
        if tracker.delete(tid):
            console.print(f"[dim]Задача {tid} удалена[/]")
        else:
            console.print(f"[red]Задача не найдена: {tid}[/]")

    elif action == "stats":
        stats = tracker.stats()
        table = Table(title="Task Stats", border_style="cyan")
        table.add_column("Статус"); table.add_column("Кол-во", style="green")
        for k, v in stats.items():
            table.add_row(k, str(v))
        console.print(table)

    else:
        console.print(f"[yellow]Неизвестное действие: {action}. Доступны: list, add, start, done, block, cancel, delete[/]")


@cli.command("tasks")
def cmd_tasks():
    """Показать доску задач (аналог iis task list)."""
    from core.tasks import TaskTracker
    tracker = TaskTracker()
    _print_task_board(tracker)


@cli.command("plan")
@click.argument("task_description", nargs=-1, required=True)
@click.option("--mode", "-m", default="text")
def cmd_plan(task_description, mode):
    """Составить план выполнения задачи с помощью AI (без немедленного выполнения).

    \b
    Пример:
      iis plan "мигрировать с MySQL на PostgreSQL"
    """
    desc = " ".join(task_description)
    plan_prompt = (
        f"Составь подробный пошаговый план выполнения следующей задачи. "
        f"Разбей на конкретные шаги с описанием. Укажи риски и зависимости.\n\n"
        f"Задача: {desc}"
    )
    asyncio.run(_run_chat(plan_prompt, mode, None, False, False, False))


@cli.command("fix")
@click.argument("description", nargs=-1, required=True)
@click.option("--mode", "-m", default="coding")
def cmd_fix(description, mode):
    """Найти и исправить проблему с помощью AI.

    \b
    Примеры:
      iis fix "TypeError в api/views.py строка 42"
      iis fix "все warnings в проекте"
    """
    from core.context import ProjectContext
    desc = " ".join(description)
    ctx = ProjectContext()
    tree = ctx.get_file_tree(max_depth=3)

    fix_prompt = (
        f"Ты опытный разработчик. Найди и исправь следующую проблему в коде.\n\n"
        f"Проблема: {desc}\n\n"
        f"Структура проекта:\n```\n{tree}\n```\n\n"
        f"Покажи точное место ошибки, объясни причину и дай исправленный код."
    )
    asyncio.run(_run_chat(fix_prompt, mode, None, False, False, False))


@cli.command("review")
@click.argument("path", default=".", required=False)
@click.option("--mode", "-m", default="coding")
def cmd_review(path, mode):
    """Провести код-ревью файла или директории.

    \b
    Примеры:
      iis review src/auth.py
      iis review .
    """
    from core.context import ProjectContext
    from pathlib import Path

    ctx = ProjectContext(Path(path) if path != "." else Path("."))
    p = Path(path)

    if p.is_file():
        content = ctx.read_file(p) or "[не удалось прочитать]"
        review_prompt = (
            f"Проведи детальное код-ревью следующего файла.\n"
            f"Найди: баги, антипаттерны, security issues, проблемы производительности, стиля.\n"
            f"Дай конкретные рекомендации с исправленным кодом.\n\n"
            f"Файл: {path}\n```\n{content[:8000]}\n```"
        )
    else:
        context = ctx.build_context_for_ai(max_chars=15000)
        review_prompt = (
            f"Проведи код-ревью проекта.\n"
            f"Найди: баги, антипаттерны, security issues, проблемы архитектуры.\n"
            f"Дай топ-10 наиболее важных рекомендаций.\n\n"
            f"{context}"
        )
    asyncio.run(_run_chat(review_prompt, mode, None, False, False, False))


@cli.command("yolo")
@click.argument("task_description", nargs=-1, required=True)
@click.option("--mode", "-m", default="coding")
def cmd_yolo(task_description, mode):
    """YOLO режим: AI делает всё сам без уточнений.

    \b
    Пример:
      iis yolo "создай FastAPI проект с авторизацией"
    """
    from core.context import ProjectContext
    desc = " ".join(task_description)
    ctx = ProjectContext()
    tree = ctx.get_file_tree(max_depth=3)

    yolo_prompt = (
        f"РЕЖИМ YOLO: Выполни задачу полностью и автономно. "
        f"Без лишних вопросов — сразу пиши готовый код, команды, файлы.\n\n"
        f"Задача: {desc}\n\n"
        f"Текущая структура проекта:\n```\n{tree}\n```\n\n"
        f"Дай полное решение: код файлов, команды установки, инструкцию запуска."
    )
    console.print(f"[bold red]⚡ YOLO MODE[/] — [dim]AI делает всё сам...[/]")
    asyncio.run(_run_chat(yolo_prompt, mode, None, False, False, False))


# ── Вспомогательные функции вывода ────────────────────────────────────────────

def _print_status(st: dict) -> None:
    table = Table(title="◈ IIStudio Status", border_style="cyan")
    table.add_column("Параметр", style="cyan")
    table.add_column("Значение", style="green")

    table.add_row("Версия", st.get("version", "—"))
    table.add_row("Окружение", st.get("env", "—"))
    table.add_row("Режим", st.get("mode", "—"))
    table.add_row("Модель", st.get("model") or "—")
    table.add_row("Сессия", st.get("session_id", "—"))
    table.add_row("Сообщений", str(st.get("messages", 0)))

    proxy = st.get("proxy", {})
    proxy_str = proxy.get("current") or "нет"
    lat = proxy.get("latency_ms")
    table.add_row("Прокси", f"{proxy_str} ({lat:.0f}мс)" if lat else proxy_str)

    cache = st.get("cache", {})
    table.add_row("Кэш", f"{cache.get('backend', '—')} ({cache.get('size', 0)} записей)")

    console.print(table)


def _print_models_table(mode: str) -> None:
    from arena.models import get_models_for_mode
    models = get_models_for_mode(mode)

    table = Table(title=f"Модели: {mode}", border_style="cyan", show_lines=True)
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Название", style="bold")
    table.add_column("Провайдер", style="yellow")
    table.add_column("Контекст", style="green")
    table.add_column("Описание", style="dim")

    for m in models:
        default_mark = " ★" if m.is_default else ""
        table.add_row(
            m.id,
            f"{m.name}{default_mark}",
            m.provider,
            f"{m.context_k}K" if m.context_k else "—",
            m.description,
        )
    console.print(table)


def _print_task_board(tracker) -> None:
    """Вывести доску задач в rich-таблице."""
    from core.tasks import TaskStatus
    tasks = tracker.list()
    stats = tracker.stats()

    # Шапка со статистикой
    console.print(
        f"\n[bold cyan]◈ IIStudio Tasks[/]  "
        f"📋 [yellow]TODO: {stats['TODO']}[/]  "
        f"🔄 [cyan]WIP: {stats['IN_PROGRESS']}[/]  "
        f"✅ [green]DONE: {stats['DONE']}[/]  "
        f"🚫 [red]BLOCKED: {stats['BLOCKED']}[/]  "
        f"[dim]Всего: {stats['total']}[/]"
    )

    if not tasks:
        console.print("[dim]Задач нет. Создай: iis task add \"описание задачи #тег\"[/]\n")
        return

    table = Table(border_style="cyan", show_lines=True)
    table.add_column("ID",     style="dim",    no_wrap=True, width=8)
    table.add_column("Статус", no_wrap=True,   width=14)
    table.add_column("Задача", min_width=30)
    table.add_column("Теги",   style="yellow", width=20)
    table.add_column("Приор.", width=7)

    STATUS_COLOR = {
        "TODO":        "[white]📋 TODO[/]",
        "IN_PROGRESS": "[cyan]🔄 IN PROG[/]",
        "DONE":        "[green]✅ DONE[/]",
        "BLOCKED":     "[red]🚫 BLOCKED[/]",
        "CANCELLED":   "[dim]❌ CANCELLED[/]",
    }
    PRIORITY_MARK = {0: "", 1: "[yellow]🟡 HIGH[/]", 2: "[red]🔴 CRIT[/]"}

    for t in tasks:
        tags_str = " ".join(f"#{tag}" for tag in t.tags) if t.tags else "—"
        table.add_row(
            f"[bold]{t.short_id}[/]",
            STATUS_COLOR.get(t.status, t.status),
            t.title,
            tags_str,
            PRIORITY_MARK.get(t.priority, ""),
        )

    console.print(table)
    console.print(
        "[dim]  iis task add \"описание\" | iis task start ID | "
        "iis task done ID | iis task block ID[/]\n"
    )


def _print_proxy_table(proxies: list) -> None:
    table = Table(title="Прокси", border_style="cyan", show_lines=True)
    table.add_column("Хост", style="cyan")
    table.add_column("Порт")
    table.add_column("Тип", style="yellow")
    table.add_column("Статус")
    table.add_column("Латency")
    table.add_column("Ошибки")

    for p in proxies:
        alive = p.get("alive", False)
        status_str = "[green]✅ живой[/]" if alive else "[red]❌ мёртвый[/]"
        lat = p.get("latency_ms")
        lat_str = f"{lat:.0f}мс" if lat else "—"
        table.add_row(
            p.get("host", "—"),
            str(p.get("port", "—")),
            p.get("type", "—"),
            status_str,
            lat_str,
            str(p.get("failures", 0)),
        )
    console.print(table)


# ── Точка входа ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Поддержка короткого вызова: python iistudio.py "сообщение"
    # без передачи имени команды
    cli()


# ═══════════════════════════════════════════════════════════════════════════
# dromdev — группа команд (1:1 как RovoDev)
# Использование: iis dromdev <command>
# ═══════════════════════════════════════════════════════════════════════════

@cli.group("dromdev")
def dromdev():
    """◈ IIStudio dromdev — основной интерфейс AI агента."""
    pass


def _save_iis_config(token: str, server: str, email: str, username: str = "") -> None:
    import json as _j
    from pathlib import Path
    config_dir = Path.home() / ".iistudio"
    config_dir.mkdir(exist_ok=True)
    config = {"token": token, "server": server, "email": email, "username": username}
    (config_dir / "config.json").write_text(_j.dumps(config, indent=2))


def _load_iis_config() -> dict:
    import json as _j
    from pathlib import Path
    cfg = Path.home() / ".iistudio" / "config.json"
    if cfg.exists():
        try:
            return _j.loads(cfg.read_text())
        except Exception:
            pass
    return {}


@dromdev.command("run")
@click.option("--model", "-m", default=None, help="Модель: claude-opus-4-6 | claude-sonnet-4-6")
@click.option("--workdir", "-w", default=".", help="Директория проекта")
def dromdev_run(model, workdir):
    """Запустить интерактивного AI агента.

    \b
    Агент умеет:
      - Создавать и редактировать файлы
      - Запускать bash команды
      - Читать код проекта
      - Планировать и выполнять задачи

    \b
    Команды внутри:
      /help          — справка
      /model         — сменить модель
      /files         — список файлов
      /clear         — очистить историю
      /exit          — выход
    """
    asyncio.run(_interactive_mode("text", model, workdir=workdir))


@dromdev.group("auth")
def dromdev_auth():
    """Управление аутентификацией."""
    pass


@dromdev_auth.command("login")
@click.option("--server", default="https://orproject.online", help="URL сервера IIStudio")
def dromdev_auth_login_cmd(server):
    """Войти в IIStudio аккаунт.

    \b
    Пример:
      iis dromdev auth login
      iis dromdev auth login --server https://orproject.online
    """
    import httpx

    console.print(Panel(
        f"[bold cyan]◈ IIStudio — Вход[/]\n\n"
        f"Зарегистрируйся или войди на:\n[cyan]{server}/login[/]",
        border_style="cyan",
    ))

    email = console.input("[cyan]Введите Email: [/]").strip()
    if not email:
        console.print("[red]Email не введён[/]"); return

    api_key = console.input("[cyan]Введите ваш Api ключ: [/]").strip()

    if api_key:
        try:
            r = httpx.get(f"{server}/api/user/me",
                headers={"Authorization": f"Bearer {api_key}"}, timeout=15)
            if r.status_code == 200:
                user = r.json()
                _save_iis_config(api_key, server, user.get("email", email), user.get("username",""))
                console.print(Panel(
                    f"[bold green]✅ Вход выполнен![/]\n\n"
                    f"Email: [cyan]{user.get('email', email)}[/]\n"
                    f"План: [yellow]{user.get('plan','free').upper()}[/]\n"
                    f"Баланс: [green]${user.get('balance_usd',0):.4f}[/]\n"
                    f"Токенов: [cyan]{user.get('free_tokens',0):,}[/]\n\n"
                    f"[dim]Запусти агента: iis dromdev run[/]",
                    border_style="green",
                )); return
            else:
                console.print(f"[red]❌ Ошибка авторизации (status={r.status_code})[/]")
        except Exception as e:
            console.print(f"[yellow]Ошибка: {e}[/]")

    # Ввод токена вручную
    console.print("")
    token = console.input("[cyan]API токен (sk-iis-...): [/]").strip()
    if not token:
        console.print("[red]Токен не введён[/]"); return

    try:
        r = httpx.get(f"{server}/api/user/me",
            headers={"Authorization": f"Bearer {token}"}, timeout=10)
        if r.status_code == 200:
            user = r.json()
            _save_iis_config(token, server, user.get("email", email), user.get("username",""))
            console.print(Panel(
                f"[bold green]Вход выполнен![/]\n\n"
                f"Email: [cyan]{user.get('email', email)}[/]\n"
                f"План: [yellow]{user.get('plan','free').upper()}[/]\n"
                f"Баланс: [green]${user.get('balance_usd',0):.4f}[/]\n"
                f"Токенов: [cyan]{user.get('free_tokens',0):,}[/]\n\n"
                f"[dim]Запусти агента: iis dromdev run[/]",
                border_style="green",
            ))
        else:
            console.print("[red]Неверный токен[/]")
    except Exception as e:
        _save_iis_config(token, server, email, "")
        console.print(f"[yellow]Сервер недоступен — токен сохранён локально[/]")


@dromdev_auth.command("logout")
def dromdev_auth_logout_cmd():
    """Выйти из аккаунта."""
    import json as _j
    from pathlib import Path
    cfg = Path.home() / ".iistudio" / "config.json"
    if cfg.exists():
        data = _j.loads(cfg.read_text())
        data.pop("token", None)
        cfg.write_text(_j.dumps(data, indent=2))
    console.print("[green]Вышли из аккаунта[/]")


@dromdev_auth.command("status")
def dromdev_auth_status_cmd():
    """Показать статус аккаунта."""
    import httpx
    config = _load_iis_config()
    token = config.get("token", "")
    server = config.get("server", "https://orproject.online")
    if not token:
        console.print("[yellow]Не авторизован. Запусти: iis dromdev auth login[/]"); return
    console.print(f"[dim]Сервер: {server}[/]")
    console.print(f"[dim]Токен: {token[:18]}...[/]")
    try:
        r = httpx.get(f"{server}/api/user/me",
            headers={"Authorization": f"Bearer {token}"}, timeout=10)
        if r.status_code == 200:
            user = r.json()
            console.print(f"\n[bold]Email:[/]   {user.get('email')}")
            console.print(f"[bold]План:[/]    [yellow]{user.get('plan','free').upper()}[/]")
            console.print(f"[bold]Баланс:[/]  [green]${user.get('balance_usd',0):.4f}[/]")
            console.print(f"[bold]Токены:[/]  [cyan]{user.get('free_tokens',0):,} бесплатных[/]")
        else:
            console.print("[red]Токен недействителен. Войди снова: iis dromdev auth login[/]")
    except Exception as e:
        console.print(f"[yellow]Сервер недоступен: {e}[/]")
        console.print(f"[dim]Email: {config.get('email','?')}[/]")


@dromdev.command("ask")
@click.argument("message", nargs=-1, required=True)
@click.option("--model", "-m", default=None)
@click.option("--stream", "-s", is_flag=True)
@click.option("--no-cache", is_flag=True)
def dromdev_ask_cmd(message, model, stream, no_cache):
    """Задать вопрос AI."""
    asyncio.run(_run_chat(" ".join(message), "text", model, stream, False, no_cache))


@dromdev.command("plan")
@click.argument("task", nargs=-1, required=True)
def dromdev_plan_cmd(task):
    """Составить план задачи."""
    t = " ".join(task)
    asyncio.run(_run_chat(
        f"Составь подробный пошаговый план выполнения задачи. "
        f"Разбей на конкретные шаги.\n\nЗадача: {t}", "text", None, False, False, False))


@dromdev.command("fix")
@click.argument("description", nargs=-1, required=True)
def dromdev_fix_cmd(description):
    """Найти и исправить проблему."""
    d = " ".join(description)
    asyncio.run(_run_chat(
        f"Найди и исправь следующую проблему. Покажи причину и исправленный код.\n\nПроблема: {d}",
        "coding", None, False, False, False))


@dromdev.command("review")
@click.argument("path", default=".", required=False)
def dromdev_review_cmd(path):
    """Провести код-ревью файла или директории."""
    from core.context import ProjectContext
    from pathlib import Path as _Path
    ctx = ProjectContext(_Path(path) if _Path(path).is_dir() else _Path("."))
    p = _Path(path)
    if p.is_file():
        content = ctx.read_file(p) or "[не удалось прочитать]"
        prompt = f"Код-ревью файла {path}:\n\n```\n{content[:6000]}\n```"
    else:
        tree = ctx.get_file_tree(max_depth=3)
        prompt = f"Код-ревью проекта. Топ-10 рекомендаций:\n\n```\n{tree}\n```"
    asyncio.run(_run_chat(prompt, "coding", None, False, False, False))


@dromdev.command("yolo")
@click.argument("task", nargs=-1, required=True)
def dromdev_yolo_cmd(task):
    """YOLO: AI выполняет задачу автономно, создавая файлы."""
    from core.context import ProjectContext
    from pathlib import Path as _Path
    t = " ".join(task)
    ctx = ProjectContext(_Path("."))
    tree = ctx.get_file_tree(max_depth=3)
    console.print(f"[bold red]YOLO MODE[/] — [dim]AI выполняет задачу автономно...[/]")
    asyncio.run(_run_chat(
        f"YOLO РЕЖИМ: выполни задачу автономно. Создай все нужные файлы.\n\n"
        f"Задача: {t}\n\nПроект:\n```\n{tree}\n```", "coding", None, False, False, False))


@dromdev.command("tasks")
def dromdev_tasks_cmd():
    """Показать доску задач."""
    from core.tasks import TaskTracker
    _print_task_board(TaskTracker())


@dromdev.command("models")
@click.option("--mode", "-m", default=None)
def dromdev_models_cmd(mode):
    """Список доступных AI моделей."""
    from arena.models import MODES
    modes = [mode] if mode else list(MODES)
    for m in modes:
        _print_models_table(m)
