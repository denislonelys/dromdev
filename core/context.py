# ============================================================================
# IIStudio — Контекст проекта (анализ файлов и структуры)
# ============================================================================

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from utils.logger import logger

# Расширения файлов которые читаем для контекста
TEXT_EXTENSIONS: Set[str] = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".go", ".rs", ".java", ".c", ".cpp",
    ".h", ".hpp", ".cs", ".rb", ".php", ".swift", ".kt", ".scala", ".lua",
    ".sh", ".bash", ".zsh", ".fish", ".sql", ".md", ".txt", ".yaml", ".yml",
    ".json", ".toml", ".ini", ".cfg", ".env", ".example", ".dockerfile",
    ".gitignore", ".html", ".css", ".scss", ".sass", ".vue", ".svelte",
}

IGNORE_DIRS: Set[str] = {
    ".git", "__pycache__", "node_modules", "venv", ".venv", "env",
    ".env", "dist", "build", ".next", ".nuxt", ".iistudio", "coverage",
    ".pytest_cache", ".mypy_cache", ".ruff_cache", "target", "vendor",
}

MAX_FILE_SIZE_BYTES = 100_000  # 100 KB — не читаем огромные файлы
MAX_CONTEXT_CHARS = 50_000    # ограничение контекста для AI


class ProjectContext:
    """Анализ структуры и содержимого проекта."""

    def __init__(self, root: Path = Path(".")) -> None:
        self.root = root.resolve()

    def get_file_tree(self, max_depth: int = 4) -> str:
        """Построить дерево файлов проекта (как tree команда)."""
        lines: List[str] = [f"{self.root.name}/"]
        self._tree_recursive(self.root, lines, prefix="", depth=0, max_depth=max_depth)
        return "\n".join(lines)

    def _tree_recursive(
        self, path: Path, lines: List[str], prefix: str, depth: int, max_depth: int
    ) -> None:
        if depth >= max_depth:
            return
        try:
            items = sorted(path.iterdir(), key=lambda p: (p.is_file(), p.name))
        except PermissionError:
            return

        for i, item in enumerate(items):
            if item.name in IGNORE_DIRS or item.name.startswith("."):
                continue
            is_last = i == len(items) - 1
            connector = "└── " if is_last else "├── "
            lines.append(f"{prefix}{connector}{item.name}")
            if item.is_dir():
                extension = "    " if is_last else "│   "
                self._tree_recursive(item, lines, prefix + extension, depth + 1, max_depth)

    def read_file(self, path: Path) -> Optional[str]:
        """Прочитать файл если он текстовый и не слишком большой."""
        if not path.exists() or not path.is_file():
            return None
        if path.suffix.lower() not in TEXT_EXTENSIONS:
            return None
        if path.stat().st_size > MAX_FILE_SIZE_BYTES:
            return f"[Файл слишком большой: {path.stat().st_size} байт]"
        try:
            return path.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            return f"[Ошибка чтения: {e}]"

    def get_relevant_files(self, query: str) -> List[Dict[str, Any]]:
        """Найти файлы релевантные запросу (простой текстовый поиск)."""
        results: List[Dict[str, Any]] = []
        query_lower = query.lower()

        for path in self.root.rglob("*"):
            if any(part in IGNORE_DIRS for part in path.parts):
                continue
            if not path.is_file():
                continue
            if path.suffix.lower() not in TEXT_EXTENSIONS:
                continue

            content = self.read_file(path)
            if content and query_lower in content.lower():
                results.append({
                    "path": str(path.relative_to(self.root)),
                    "size": path.stat().st_size,
                    "content": content[:5000],  # первые 5000 символов
                })

        return results[:10]  # ограничиваем количество файлов

    def build_context_for_ai(
        self,
        include_files: Optional[List[str]] = None,
        max_chars: int = MAX_CONTEXT_CHARS,
    ) -> str:
        """Собрать контекст проекта для передачи в AI."""
        parts: List[str] = []
        total_chars = 0

        # Дерево файлов
        tree = self.get_file_tree()
        parts.append(f"# Структура проекта\n```\n{tree}\n```\n")
        total_chars += len(tree)

        # Конкретные файлы
        if include_files:
            for file_path_str in include_files:
                if total_chars >= max_chars:
                    break
                path = self.root / file_path_str
                content = self.read_file(path)
                if content:
                    section = f"\n# {file_path_str}\n```\n{content}\n```\n"
                    parts.append(section)
                    total_chars += len(section)
        else:
            # Читать ключевые файлы
            key_files = self._find_key_files()
            for path in key_files:
                if total_chars >= max_chars:
                    parts.append("\n[Контекст обрезан — слишком много файлов]")
                    break
                content = self.read_file(path)
                if content:
                    rel = str(path.relative_to(self.root))
                    section = f"\n# {rel}\n```\n{content[:3000]}\n```\n"
                    parts.append(section)
                    total_chars += len(section)

        return "".join(parts)

    def _find_key_files(self) -> List[Path]:
        """Найти наиболее важные файлы проекта."""
        priority_names = [
            "README.md", "main.py", "app.py", "index.py", "server.py",
            "requirements.txt", "pyproject.toml", "package.json",
            "Dockerfile", "docker-compose.yml", ".env.example",
        ]
        result: List[Path] = []

        # Сначала приоритетные файлы
        for name in priority_names:
            path = self.root / name
            if path.exists():
                result.append(path)

        # Потом остальные .py файлы
        for path in sorted(self.root.rglob("*.py")):
            if any(part in IGNORE_DIRS for part in path.parts):
                continue
            if path not in result and len(result) < 20:
                result.append(path)

        return result

    def get_summary(self) -> Dict[str, Any]:
        """Краткая сводка о проекте."""
        file_counts: Dict[str, int] = {}
        total_files = 0
        total_lines = 0

        for path in self.root.rglob("*"):
            if any(part in IGNORE_DIRS for part in path.parts):
                continue
            if not path.is_file():
                continue
            total_files += 1
            ext = path.suffix.lower() or "no_ext"
            file_counts[ext] = file_counts.get(ext, 0) + 1
            if ext in TEXT_EXTENSIONS and path.stat().st_size < MAX_FILE_SIZE_BYTES:
                try:
                    content = path.read_text(encoding="utf-8", errors="replace")
                    total_lines += content.count("\n")
                except Exception:
                    pass

        return {
            "root": str(self.root),
            "total_files": total_files,
            "total_lines": total_lines,
            "extensions": dict(sorted(file_counts.items(), key=lambda x: -x[1])[:10]),
        }
