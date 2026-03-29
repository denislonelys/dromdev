#!/usr/bin/env python3
# ============================================================================
# IIStudio — File Watcher
# Следит за папкой userfiles/ и автоматически обновляет индекс.
# Поддерживает: видео, изображения, документы, любые файлы.
# ============================================================================

import asyncio
import hashlib
import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any

WATCH_DIR = Path("/root/IIStudio/userfiles")
INDEX_FILE = Path("/root/IIStudio/userfiles/.index.json")
CHECK_INTERVAL = 10  # секунд

# Расширения файлов по категориям
CATEGORIES = {
    "videos": {".mp4", ".webm", ".avi", ".mov", ".mkv", ".flv", ".wmv", ".m4v", ".3gp"},
    "images": {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".svg", ".ico"},
    "audio":  {".mp3", ".ogg", ".wav", ".flac", ".aac", ".m4a", ".opus"},
    "documents": {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".txt", ".md"},
    "archives": {".zip", ".tar", ".gz", ".bz2", ".7z", ".rar"},
    "code":   {".py", ".js", ".ts", ".go", ".rs", ".java", ".c", ".cpp", ".sh"},
}


def get_category(suffix: str) -> str:
    suffix = suffix.lower()
    for cat, exts in CATEGORIES.items():
        if suffix in exts:
            return cat
    return "other"


def format_size(size: int) -> str:
    for unit in ("Б", "КБ", "МБ", "ГБ"):
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} ТБ"


def scan_directory(watch_dir: Path) -> Dict[str, Any]:
    """Сканировать директорию и построить индекс."""
    index = {
        "updated_at": datetime.now().isoformat(),
        "total_files": 0,
        "total_size": 0,
        "categories": {},
        "files": [],
    }

    if not watch_dir.exists():
        watch_dir.mkdir(parents=True, exist_ok=True)
        return index

    for path in sorted(watch_dir.rglob("*")):
        if path.is_file() and not path.name.startswith("."):
            stat = path.stat()
            size = stat.st_size
            mtime = datetime.fromtimestamp(stat.st_mtime).isoformat()
            suffix = path.suffix
            category = get_category(suffix)
            rel_path = str(path.relative_to(watch_dir))

            file_info = {
                "name": path.name,
                "path": rel_path,
                "url": f"/files/{rel_path}",
                "category": category,
                "size": size,
                "size_human": format_size(size),
                "extension": suffix.lower(),
                "modified": mtime,
            }

            index["files"].append(file_info)
            index["total_files"] += 1
            index["total_size"] += size

            if category not in index["categories"]:
                index["categories"][category] = {"count": 0, "size": 0}
            index["categories"][category]["count"] += 1
            index["categories"][category]["size"] += size

    index["total_size_human"] = format_size(index["total_size"])
    return index


def save_index(index: Dict) -> None:
    """Сохранить индекс в JSON файл."""
    INDEX_FILE.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")


def get_dir_hash(watch_dir: Path) -> str:
    """Получить хэш состояния директории (для детекции изменений)."""
    h = hashlib.md5()
    try:
        for path in sorted(watch_dir.rglob("*")):
            if path.is_file() and not path.name.startswith("."):
                stat = path.stat()
                h.update(f"{path}:{stat.st_size}:{stat.st_mtime}".encode())
    except Exception:
        pass
    return h.hexdigest()


async def watch_files():
    """Основной цикл наблюдения за файлами."""
    print(f"[FileWatcher] Watching: {WATCH_DIR}")
    print(f"[FileWatcher] Index: {INDEX_FILE}")

    WATCH_DIR.mkdir(parents=True, exist_ok=True)
    for sub in ("videos", "images", "documents", "uploads", "audio"):
        (WATCH_DIR / sub).mkdir(exist_ok=True)

    prev_hash = ""
    while True:
        try:
            current_hash = get_dir_hash(WATCH_DIR)
            if current_hash != prev_hash:
                print(f"[FileWatcher] Changes detected, rebuilding index...")
                index = scan_directory(WATCH_DIR)
                save_index(index)
                prev_hash = current_hash
                print(
                    f"[FileWatcher] Index updated: {index['total_files']} files, "
                    f"{index['total_size_human']}"
                )
        except Exception as e:
            print(f"[FileWatcher] Error: {e}")

        await asyncio.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    asyncio.run(watch_files())
