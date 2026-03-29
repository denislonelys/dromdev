# ============================================================================
# IIStudio — Логгер (loguru)
# ============================================================================

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

from loguru import logger as _logger

# Экспортируем настроенный логгер
logger = _logger

_configured = False


def setup_logger(
    level: str = "INFO",
    log_file: Optional[Path] = None,
    rotation: str = "50 MB",
    retention: str = "7 days",
    colorize: bool = True,
    serialize: bool = False,
) -> None:
    """Настроить loguru логгер.

    Args:
        level: уровень логирования (DEBUG/INFO/WARNING/ERROR/CRITICAL)
        log_file: путь к файлу логов (None = только консоль)
        rotation: ротация файла ("50 MB" / "1 day")
        retention: хранение логов ("7 days" / "1 week")
        colorize: цветной вывод в консоль
        serialize: JSON-формат (для production)
    """
    global _configured

    _logger.remove()  # убрать дефолтный обработчик

    # ── Консольный вывод ────────────────────────────────────────────────────
    fmt_console = (
        "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
        "<level>{message}</level>"
    )
    fmt_plain = (
        "{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | "
        "{name}:{function}:{line} | {message}"
    )

    _logger.add(
        sys.stderr,
        level=level,
        format=fmt_console if colorize else fmt_plain,
        colorize=colorize,
        backtrace=True,
        diagnose=True,
    )

    # ── Файловый вывод ──────────────────────────────────────────────────────
    if log_file is not None:
        log_file = Path(log_file)
        log_file.parent.mkdir(parents=True, exist_ok=True)
        _logger.add(
            str(log_file),
            level=level,
            format=fmt_plain,
            rotation=rotation,
            retention=retention,
            compression="zip",
            backtrace=True,
            diagnose=False,
            serialize=serialize,
            encoding="utf-8",
        )

    _configured = True
    _logger.debug("Логгер инициализирован: level={}, file={}", level, log_file)


def get_logger(name: str) -> "_logger.__class__":
    """Получить именованный логгер для модуля."""
    return _logger.bind(module=name)


# Автонастройка при импорте (минимальная, без файла)
def _auto_setup() -> None:
    if not _configured:
        try:
            from config import settings
            setup_logger(level=settings.iistudio_log_level)
        except Exception:
            setup_logger(level="INFO")


_auto_setup()
