# ============================================================================
# IIStudio — Режимы работы arena.ai
# ============================================================================

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional


@dataclass
class Mode:
    id: str           # text / images / video / coding
    label: str        # Отображаемое имя
    emoji: str        # Иконка
    tab_selector: str # CSS селектор таба на arena.ai
    description: str  # Описание


MODES: Dict[str, Mode] = {
    "text": Mode(
        id="text",
        label="Text",
        emoji="💬",
        tab_selector='button[data-mode="text"], a[href*="text"], [aria-label*="Text"]',
        description="Текстовые запросы к AI моделям",
    ),
    "images": Mode(
        id="images",
        label="Images",
        emoji="🎨",
        tab_selector='button[data-mode="images"], a[href*="image"], [aria-label*="Image"]',
        description="Генерация изображений",
    ),
    "video": Mode(
        id="video",
        label="Video",
        emoji="🎬",
        tab_selector='button[data-mode="video"], a[href*="video"], [aria-label*="Video"]',
        description="Генерация видео",
    ),
    "coding": Mode(
        id="coding",
        label="Coding",
        emoji="💻",
        tab_selector='button[data-mode="coding"], a[href*="coding"], [aria-label*="Code"]',
        description="Помощь с кодом",
    ),
}


def get_mode(mode_id: str) -> Optional[Mode]:
    return MODES.get(mode_id.lower())


def list_modes() -> list[Mode]:
    return list(MODES.values())
