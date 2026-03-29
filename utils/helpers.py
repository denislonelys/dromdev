# ============================================================================
# IIStudio — Вспомогательные утилиты
# ============================================================================

from __future__ import annotations

import asyncio
import hashlib
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, TypeVar
from urllib.parse import urlparse

from utils.logger import logger

T = TypeVar("T")


# ── Время ────────────────────────────────────────────────────────────────────

def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def timestamp_ms() -> int:
    return int(time.time() * 1000)


def format_duration(seconds: float) -> str:
    """Форматировать длительность: 1h 23m 4s / 45ms"""
    if seconds < 1:
        return f"{seconds * 1000:.0f}мс"
    if seconds < 60:
        return f"{seconds:.1f}с"
    if seconds < 3600:
        m, s = divmod(int(seconds), 60)
        return f"{m}м {s}с"
    h, rem = divmod(int(seconds), 3600)
    m, s = divmod(rem, 60)
    return f"{h}ч {m}м {s}с"


# ── Строки ───────────────────────────────────────────────────────────────────

def truncate(text: str, max_len: int = 100, suffix: str = "…") -> str:
    """Обрезать строку до max_len символов."""
    if len(text) <= max_len:
        return text
    return text[: max_len - len(suffix)] + suffix


def slugify(text: str) -> str:
    """Превратить текст в slug (URL-безопасный)."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    text = re.sub(r"^-+|-+$", "", text)
    return text


def sanitize_filename(name: str) -> str:
    """Убрать опасные символы из имени файла."""
    return re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name)


def extract_json(text: str) -> Optional[Any]:
    """Извлечь первый JSON-объект/массив из текста."""
    patterns = [
        r"```json\s*([\s\S]+?)\s*```",
        r"```\s*([\s\S]+?)\s*```",
        r"(\{[\s\S]+\})",
        r"(\[[\s\S]+\])",
    ]
    for pat in patterns:
        m = re.search(pat, text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(1))
            except json.JSONDecodeError:
                continue
    return None


# ── Хеши и ID ─────────────────────────────────────────────────────────────────

def md5(text: str) -> str:
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def make_cache_key(*parts: Any) -> str:
    """Создать ключ кэша из произвольных частей."""
    raw = ":".join(str(p) for p in parts)
    return md5(raw)


# ── Сеть ─────────────────────────────────────────────────────────────────────

def is_valid_url(url: str) -> bool:
    try:
        r = urlparse(url)
        return all([r.scheme in ("http", "https"), r.netloc])
    except Exception:
        return False


def parse_proxy(line: str) -> Optional[Dict[str, Any]]:
    """Парсить строку прокси.

    Форматы:
      MTProto:  HOST:PORT:SECRET
      SOCKS5:   socks5://USER:PASS@HOST:PORT
               socks5://HOST:PORT
    """
    line = line.strip()
    if not line or line.startswith("#"):
        return None

    # SOCKS5
    if line.startswith("socks5://"):
        try:
            parsed = urlparse(line)
            result: Dict[str, Any] = {
                "type": "socks5",
                "host": parsed.hostname,
                "port": parsed.port,
            }
            if parsed.username:
                result["username"] = parsed.username
            if parsed.password:
                result["password"] = parsed.password
            return result
        except Exception:
            logger.warning("Не удалось парсить SOCKS5 прокси: {}", line)
            return None

    # MTProto: host:port:secret
    parts = line.split(":")
    if len(parts) == 3:
        host, port_str, secret = parts
        try:
            return {
                "type": "mtproto",
                "host": host.strip(),
                "port": int(port_str.strip()),
                "secret": secret.strip(),
            }
        except ValueError:
            pass

    logger.warning("Неизвестный формат прокси: {}", line)
    return None


def load_proxies(file_path: Path) -> List[Dict[str, Any]]:
    """Загрузить список прокси из файла."""
    if not file_path.exists():
        logger.warning("Файл прокси не найден: {}", file_path)
        return []
    proxies = []
    with open(file_path, encoding="utf-8") as f:
        for line in f:
            p = parse_proxy(line)
            if p:
                proxies.append(p)
    logger.info("Загружено {} прокси из {}", len(proxies), file_path)
    return proxies


# ── Retry ─────────────────────────────────────────────────────────────────────

async def retry_async(
    func: Callable,
    *args: Any,
    retries: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple = (Exception,),
    **kwargs: Any,
) -> Any:
    """Повторять асинхронный вызов при ошибке с экспоненциальным backoff."""
    last_exc: Optional[Exception] = None
    current_delay = delay
    for attempt in range(1, retries + 1):
        try:
            return await func(*args, **kwargs)
        except exceptions as e:
            last_exc = e
            if attempt == retries:
                break
            logger.warning(
                "Попытка {}/{} не удалась: {}. Повтор через {:.1f}с",
                attempt,
                retries,
                e,
                current_delay,
            )
            await asyncio.sleep(current_delay)
            current_delay *= backoff
    raise last_exc  # type: ignore


# ── Файлы ─────────────────────────────────────────────────────────────────────

def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def read_text_safe(path: Path, default: str = "") -> str:
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return default


def write_json(path: Path, data: Any, indent: int = 2) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=indent), encoding="utf-8")


def read_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


# ── Форматирование ────────────────────────────────────────────────────────────

def format_bytes(size: int) -> str:
    for unit in ("Б", "КБ", "МБ", "ГБ", "ТБ"):
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024  # type: ignore
    return f"{size:.1f} ПБ"


def format_number(n: int | float) -> str:
    """1234567 → '1 234 567'"""
    return f"{n:,.0f}".replace(",", " ")


def strip_ansi(text: str) -> str:
    """Убрать ANSI-коды из строки."""
    return re.sub(r"\x1b\[[0-9;]*m", "", text)
