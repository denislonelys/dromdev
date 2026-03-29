# ============================================================================
# IIStudio — Инструменты агента (как у RovoDev)
# read_file, write_file, bash, search, list_files
# ============================================================================

from __future__ import annotations

import asyncio
import os
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional


class ToolResult:
    def __init__(self, output: str, error: str = "", success: bool = True) -> None:
        self.output = output
        self.error = error
        self.success = success

    def __str__(self) -> str:
        if self.error:
            return f"ERROR: {self.error}"
        return self.output


class AgentTools:
    """Инструменты для работы с файловой системой и терминалом."""

    def __init__(self, workdir: Path = Path(".")) -> None:
        self.workdir = workdir.resolve()

    # ── Файлы ────────────────────────────────────────────────────────────────

    def read_file(self, path: str) -> ToolResult:
        """Прочитать файл."""
        try:
            p = (self.workdir / path).resolve()
            if not str(p).startswith(str(self.workdir)):
                return ToolResult("", "Доступ запрещён (за пределами проекта)", False)
            if not p.exists():
                return ToolResult("", f"Файл не найден: {path}", False)
            content = p.read_text(encoding="utf-8", errors="replace")
            return ToolResult(content)
        except Exception as e:
            return ToolResult("", str(e), False)

    def write_file(self, path: str, content: str) -> ToolResult:
        """Записать файл."""
        try:
            p = (self.workdir / path).resolve()
            if not str(p).startswith(str(self.workdir)):
                return ToolResult("", "Доступ запрещён (за пределами проекта)", False)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
            return ToolResult(f"Файл записан: {path} ({len(content)} символов)")
        except Exception as e:
            return ToolResult("", str(e), False)

    def list_files(self, path: str = ".") -> ToolResult:
        """Список файлов в директории."""
        try:
            p = (self.workdir / path).resolve()
            lines = []
            for item in sorted(p.iterdir()):
                if item.name.startswith("."):
                    continue
                prefix = "D" if item.is_dir() else "F"
                size = "" if item.is_dir() else f" ({item.stat().st_size} B)"
                lines.append(f"  [{prefix}] {item.name}{size}")
            return ToolResult("\n".join(lines) if lines else "(пусто)")
        except Exception as e:
            return ToolResult("", str(e), False)

    def search_files(self, query: str, path: str = ".") -> ToolResult:
        """Поиск в файлах."""
        try:
            p = (self.workdir / path).resolve()
            results = []
            for file_path in p.rglob("*"):
                if file_path.is_file() and not any(
                    part.startswith(".") for part in file_path.parts
                ):
                    try:
                        content = file_path.read_text(encoding="utf-8", errors="ignore")
                        if query.lower() in content.lower():
                            lines = content.split("\n")
                            for i, line in enumerate(lines):
                                if query.lower() in line.lower():
                                    rel = file_path.relative_to(self.workdir)
                                    results.append(f"{rel}:{i+1}: {line.strip()}")
                    except Exception:
                        pass
            return ToolResult("\n".join(results[:50]) if results else "Не найдено")
        except Exception as e:
            return ToolResult("", str(e), False)

    def bash(self, command: str, timeout: int = 30) -> ToolResult:
        """Выполнить bash команду."""
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=str(self.workdir),
            )
            output = result.stdout.strip()
            error = result.stderr.strip()
            if result.returncode != 0 and not output:
                return ToolResult(error or "Команда завершилась с ошибкой", error, False)
            return ToolResult(output + ("\n" + error if error else ""))
        except subprocess.TimeoutExpired:
            return ToolResult("", f"Timeout ({timeout}с)", False)
        except Exception as e:
            return ToolResult("", str(e), False)

    def get_project_tree(self, max_depth: int = 3) -> str:
        """Дерево файлов проекта."""
        lines = [f"{self.workdir.name}/"]
        self._tree(self.workdir, lines, "", 0, max_depth)
        return "\n".join(lines)

    def _tree(self, path: Path, lines: list, prefix: str, depth: int, max_depth: int) -> None:
        if depth >= max_depth:
            return
        IGNORE = {".git", "__pycache__", "node_modules", "venv", ".venv", ".iistudio", "dist", "build"}
        try:
            items = sorted(path.iterdir(), key=lambda p: (p.is_file(), p.name))
        except PermissionError:
            return
        for i, item in enumerate(items):
            if item.name in IGNORE or item.name.startswith("."):
                continue
            is_last = i == len(items) - 1
            connector = "└── " if is_last else "├── "
            lines.append(f"{prefix}{connector}{item.name}")
            if item.is_dir():
                ext = "    " if is_last else "│   "
                self._tree(item, lines, prefix + ext, depth + 1, max_depth)


# Системный промпт с описанием инструментов
SYSTEM_PROMPT_WITH_TOOLS = """Ты — IIStudio AI, мощный ИИ-ассистент для разработчиков. 

У тебя есть инструменты для работы с проектом. Когда нужно работать с файлами — используй их.

Доступные инструменты (вызывай в своём ответе в специальном формате):

<tool:read_file path="путь/к/файлу" />
<tool:write_file path="путь/к/файлу">
содержимое файла
</tool:write_file>
<tool:bash cmd="команда" />
<tool:list_files path="." />
<tool:search query="текст" />

Правила:
- При создании/изменении файлов ВСЕГДА используй tool:write_file
- При запуске тестов/команд — tool:bash
- Пиши полный рабочий код, не заглушки
- Отвечай на языке пользователя
- После использования инструментов — объясни что сделал"""
