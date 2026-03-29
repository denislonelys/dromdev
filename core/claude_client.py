# ============================================================================
# IIStudio — Anthropic Claude API клиент (прямые запросы)
#
# Модели: claude-opus-4-6, claude-sonnet-4-6
# Возможности: текст, изображения, PDF, видео (Files API)
# Billing: считаем токены и вычитаем баланс пользователя
# ============================================================================

from __future__ import annotations

import asyncio
import base64
import json
import mimetypes
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional

import httpx

from utils.logger import logger

# ── Конфиг ───────────────────────────────────────────────────────────────────

ANTHROPIC_API_URL = "https://api.anthropic.com"
ANTHROPIC_VERSION = "2023-06-01"
ANTHROPIC_BETA    = "files-api-2025-04-14"  # Beta для Files API

# Актуальные модели (2025)
MODELS = {
    "claude-opus-4-6": {
        "id":              "claude-opus-4-5",  # текущее имя в API
        "name":            "Claude Opus 4.6",
        "provider":        "Anthropic",
        "context_k":       200,
        "input_per_1m":    15.00,   # USD
        "output_per_1m":   75.00,   # USD
        "supports_files":  True,
        "description":     "Самая мощная модель для сложных задач",
    },
    "claude-sonnet-4-6": {
        "id":              "claude-sonnet-4-5",  # текущее имя в API
        "name":            "Claude Sonnet 4.6",
        "provider":        "Anthropic",
        "context_k":       200,
        "input_per_1m":    3.00,    # USD
        "output_per_1m":   15.00,   # USD
        "supports_files":  True,
        "description":     "Баланс скорости и интеллекта",
    },
}

DEFAULT_MODEL = "claude-sonnet-4-6"


def calc_cost(input_tokens: int, output_tokens: int, model_id: str) -> float:
    """Рассчитать стоимость запроса в USD."""
    m = MODELS.get(model_id, MODELS[DEFAULT_MODEL])
    input_cost  = (input_tokens  / 1_000_000) * m["input_per_1m"]
    output_cost = (output_tokens / 1_000_000) * m["output_per_1m"]
    return round(input_cost + output_cost, 8)


# ── Клиент ────────────────────────────────────────────────────────────────────

class ClaudeClient:
    """Клиент для Anthropic Claude API с Files API поддержкой."""

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key
        self._headers = {
            "x-api-key":         api_key,
            "anthropic-version": ANTHROPIC_VERSION,
            "anthropic-beta":    ANTHROPIC_BETA,
            "content-type":      "application/json",
        }

    # ── Текстовый запрос ──────────────────────────────────────────────────────

    async def chat(
        self,
        messages: List[Dict[str, Any]],
        model_id: str = DEFAULT_MODEL,
        max_tokens: int = 4096,
        system: Optional[str] = None,
        stream: bool = False,
    ) -> Dict[str, Any]:
        """Отправить запрос Claude и получить ответ.

        Args:
            messages: список сообщений [{"role": "user", "content": "..."}]
            model_id: claude-opus-4-6 или claude-sonnet-4-6
            max_tokens: максимум токенов в ответе
            system: системный промпт
            stream: стриминг ответа

        Returns:
            dict с: text, input_tokens, output_tokens, cost_usd, model
        """
        model_info = MODELS.get(model_id, MODELS[DEFAULT_MODEL])
        api_model_id = model_info["id"]

        payload: Dict[str, Any] = {
            "model":      api_model_id,
            "max_tokens": max_tokens,
            "messages":   messages,
            "stream":     stream,
        }
        if system:
            payload["system"] = system

        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                f"{ANTHROPIC_API_URL}/v1/messages",
                headers=self._headers,
                json=payload,
            )
            if resp.status_code != 200:
                error = resp.text
                logger.error("Anthropic API error {}: {}", resp.status_code, error[:200])
                return {
                    "success": False,
                    "error": f"API error {resp.status_code}: {error[:200]}",
                    "text": None,
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "cost_usd": 0.0,
                }

            data = resp.json()
            text = ""
            for block in data.get("content", []):
                if block.get("type") == "text":
                    text += block.get("text", "")

            usage = data.get("usage", {})
            input_tokens  = usage.get("input_tokens", 0)
            output_tokens = usage.get("output_tokens", 0)
            cost = calc_cost(input_tokens, output_tokens, model_id)

            logger.debug(
                "✅ Claude: {} → {} токенов (${:.6f})",
                model_info["name"], input_tokens + output_tokens, cost,
            )

            return {
                "success":       True,
                "text":          text,
                "model":         model_id,
                "model_name":    model_info["name"],
                "input_tokens":  input_tokens,
                "output_tokens": output_tokens,
                "total_tokens":  input_tokens + output_tokens,
                "cost_usd":      cost,
            }

    async def stream_chat(
        self,
        messages: List[Dict[str, Any]],
        model_id: str = DEFAULT_MODEL,
        max_tokens: int = 4096,
        system: Optional[str] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Стриминг ответа Claude.

        Yields:
            dict с delta текстом и финальной статистикой
        """
        model_info = MODELS.get(model_id, MODELS[DEFAULT_MODEL])
        api_model_id = model_info["id"]

        payload = {
            "model":      api_model_id,
            "max_tokens": max_tokens,
            "messages":   messages,
            "stream":     True,
        }
        if system:
            payload["system"] = system

        input_tokens = 0
        output_tokens = 0

        async with httpx.AsyncClient(timeout=120) as client:
            async with client.stream(
                "POST",
                f"{ANTHROPIC_API_URL}/v1/messages",
                headers=self._headers,
                json=payload,
            ) as resp:
                if resp.status_code != 200:
                    error = await resp.aread()
                    yield {"type": "error", "error": f"API {resp.status_code}: {error[:200]}"}
                    return

                async for line in resp.aiter_lines():
                    if not line or not line.startswith("data:"):
                        continue
                    data_str = line[5:].strip()
                    if data_str == "[DONE]":
                        break
                    try:
                        event = json.loads(data_str)
                    except Exception:
                        continue

                    etype = event.get("type", "")

                    if etype == "content_block_delta":
                        delta = event.get("delta", {})
                        if delta.get("type") == "text_delta":
                            text = delta.get("text", "")
                            if text:
                                yield {"type": "delta", "text": text}

                    elif etype == "message_delta":
                        usage = event.get("usage", {})
                        output_tokens = usage.get("output_tokens", 0)

                    elif etype == "message_start":
                        usage = event.get("message", {}).get("usage", {})
                        input_tokens = usage.get("input_tokens", 0)

                    elif etype == "message_stop":
                        cost = calc_cost(input_tokens, output_tokens, model_id)
                        yield {
                            "type":          "done",
                            "input_tokens":  input_tokens,
                            "output_tokens": output_tokens,
                            "total_tokens":  input_tokens + output_tokens,
                            "cost_usd":      cost,
                            "model":         model_id,
                            "model_name":    model_info["name"],
                        }

    # ── Files API ─────────────────────────────────────────────────────────────

    async def upload_file(self, file_path: Path) -> Optional[str]:
        """Загрузить файл через Files API и вернуть file_id.

        Поддерживает: PDF, JPEG, PNG, GIF, WEBP, текст.
        """
        if not file_path.exists():
            logger.error("Файл не найден: {}", file_path)
            return None

        mime_type, _ = mimetypes.guess_type(str(file_path))
        if not mime_type:
            mime_type = "application/octet-stream"

        file_content = file_path.read_bytes()
        logger.debug("Загрузка файла: {} ({}, {} байт)", file_path.name, mime_type, len(file_content))

        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{ANTHROPIC_API_URL}/v1/files",
                headers={
                    "x-api-key":         self.api_key,
                    "anthropic-version": ANTHROPIC_VERSION,
                    "anthropic-beta":    ANTHROPIC_BETA,
                },
                files={"file": (file_path.name, file_content, mime_type)},
            )
            if resp.status_code != 200:
                logger.error("Ошибка загрузки файла: {} {}", resp.status_code, resp.text[:200])
                return None

            file_id = resp.json().get("id")
            logger.info("Файл загружен: {} → {}", file_path.name, file_id)
            return file_id

    async def chat_with_file(
        self,
        message: str,
        file_path: Path,
        model_id: str = DEFAULT_MODEL,
        max_tokens: int = 4096,
        system: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Отправить запрос с файлом (PDF, изображение).

        Автоматически определяет тип файла и формирует правильный контент.
        """
        mime_type, _ = mimetypes.guess_type(str(file_path))
        mime_type = mime_type or "application/octet-stream"

        # Изображения — base64 inline (не нужен Files API)
        if mime_type.startswith("image/"):
            file_content = file_path.read_bytes()
            b64 = base64.standard_b64encode(file_content).decode("utf-8")
            messages = [{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type":       "base64",
                            "media_type": mime_type,
                            "data":       b64,
                        },
                    },
                    {"type": "text", "text": message},
                ],
            }]
            return await self.chat(messages, model_id=model_id, max_tokens=max_tokens, system=system)

        # PDF и другие файлы — через Files API
        file_id = await self.upload_file(file_path)
        if not file_id:
            # Fallback: читаем как текст
            try:
                text_content = file_path.read_text(encoding="utf-8", errors="replace")[:50000]
                messages = [{"role": "user", "content": f"Файл {file_path.name}:\n\n{text_content}\n\n{message}"}]
                return await self.chat(messages, model_id=model_id, max_tokens=max_tokens, system=system)
            except Exception as e:
                return {"success": False, "error": str(e), "text": None, "cost_usd": 0}

        messages = [{
            "role": "user",
            "content": [
                {
                    "type": "document",
                    "source": {
                        "type":    "file",
                        "file_id": file_id,
                    },
                },
                {"type": "text", "text": message},
            ],
        }]
        return await self.chat(messages, model_id=model_id, max_tokens=max_tokens, system=system)

    async def list_files(self) -> List[Dict[str, Any]]:
        """Список загруженных файлов."""
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{ANTHROPIC_API_URL}/v1/files",
                headers={
                    "x-api-key":         self.api_key,
                    "anthropic-version": ANTHROPIC_VERSION,
                    "anthropic-beta":    ANTHROPIC_BETA,
                },
            )
            if resp.status_code == 200:
                return resp.json().get("data", [])
        return []

    async def delete_file(self, file_id: str) -> bool:
        """Удалить файл из Files API."""
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.delete(
                f"{ANTHROPIC_API_URL}/v1/files/{file_id}",
                headers={
                    "x-api-key":         self.api_key,
                    "anthropic-version": ANTHROPIC_VERSION,
                    "anthropic-beta":    ANTHROPIC_BETA,
                },
            )
            return resp.status_code == 200
