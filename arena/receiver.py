# ============================================================================
# IIStudio — Получение и обработка ответов от arena.ai
# ============================================================================

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional


@dataclass
class ArenaResponse:
    """Структурированный ответ от arena.ai."""

    text: str
    model_id: str
    model_name: str
    mode: str
    prompt: str
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    latency_ms: Optional[float] = None
    tokens_estimate: Optional[int] = None
    image_urls: List[str] = field(default_factory=list)
    error: Optional[str] = None
    success: bool = True

    # ── Свойства ─────────────────────────────────────────────────────────────

    @property
    def word_count(self) -> int:
        return len(self.text.split())

    @property
    def char_count(self) -> int:
        return len(self.text)

    @property
    def has_code(self) -> bool:
        return bool(re.search(r"```[\w]*\n", self.text))

    @property
    def code_blocks(self) -> List[str]:
        """Извлечь все блоки кода из ответа."""
        return re.findall(r"```(?:\w+)?\n([\s\S]+?)```", self.text)

    @property
    def has_images(self) -> bool:
        return len(self.image_urls) > 0

    # ── Форматирование ────────────────────────────────────────────────────────

    def to_dict(self) -> dict:
        return {
            "text": self.text,
            "model_id": self.model_id,
            "model_name": self.model_name,
            "mode": self.mode,
            "prompt": self.prompt,
            "created_at": self.created_at.isoformat(),
            "latency_ms": self.latency_ms,
            "tokens_estimate": self.tokens_estimate,
            "image_urls": self.image_urls,
            "error": self.error,
            "success": self.success,
            "word_count": self.word_count,
            "char_count": self.char_count,
        }

    def format_for_cli(self) -> str:
        """Форматировать для вывода в CLI."""
        lines = []
        latency = f" ({self.latency_ms:.0f}мс)" if self.latency_ms else ""
        lines.append(f"\n🤖 [{self.model_name}]{latency}")
        lines.append("─" * 60)
        lines.append(self.text)
        lines.append("─" * 60)
        if self.image_urls:
            for url in self.image_urls:
                lines.append(f"🖼  {url}")
        return "\n".join(lines)


class ResponseProcessor:
    """Постобработка ответов от arena.ai."""

    @staticmethod
    def extract_image_urls(html_or_text: str) -> List[str]:
        """Найти URL изображений в тексте/HTML."""
        urls = re.findall(
            r'(?:src|href)=["\']?(https?://[^\s"\'><]+\.(?:png|jpg|jpeg|webp|gif))["\']?',
            html_or_text,
            re.IGNORECASE,
        )
        # Также ищем прямые URL
        direct = re.findall(
            r'https?://[^\s"\'><]+\.(?:png|jpg|jpeg|webp|gif)',
            html_or_text,
            re.IGNORECASE,
        )
        all_urls = list(dict.fromkeys(urls + direct))
        return all_urls

    @staticmethod
    def clean_text(text: str) -> str:
        """Очистить текст ответа от лишних пробелов."""
        # Убрать множественные пробельные строки
        text = re.sub(r"\n{3,}", "\n\n", text)
        # Убрать leading/trailing пробелы
        text = text.strip()
        return text

    @staticmethod
    def estimate_tokens(text: str) -> int:
        """Примерная оценка количества токенов (1 токен ≈ 4 символа)."""
        return max(1, len(text) // 4)

    @classmethod
    def process(
        cls,
        raw_text: str,
        prompt: str,
        model_id: str,
        model_name: str,
        mode: str,
        latency_ms: Optional[float] = None,
    ) -> ArenaResponse:
        """Создать ArenaResponse из сырого текста ответа."""
        text = cls.clean_text(raw_text)
        image_urls = cls.extract_image_urls(raw_text) if mode == "images" else []
        tokens = cls.estimate_tokens(text)

        return ArenaResponse(
            text=text,
            model_id=model_id,
            model_name=model_name,
            mode=mode,
            prompt=prompt,
            latency_ms=latency_ms,
            tokens_estimate=tokens,
            image_urls=image_urls,
            success=bool(text),
            error=None if text else "Пустой ответ",
        )
