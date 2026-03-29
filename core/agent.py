# ============================================================================
# IIStudio — Главный агент (Anthropic Claude API напрямую)
# Без Playwright, без arena.ai — чистый API
# ============================================================================

from __future__ import annotations

import asyncio
import os
import time
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional

from api.auth import get_db
from cache.cache import CacheManager
from config import Settings
from core.claude_client import ClaudeClient, MODELS, DEFAULT_MODEL, calc_cost
from core.context import ProjectContext
from core.session import Session
from utils.helpers import make_cache_key
from utils.logger import logger

# Системный промпт для IIStudio
SYSTEM_PROMPT = """Ты — IIStudio AI, мощный ИИ-ассистент для разработчиков.
Ты помогаешь с кодом, планированием, анализом, объяснениями.
Отвечай чётко и по делу. При написании кода — используй блоки кода с синтаксисом.
Отвечай на том языке на котором спрашивают."""


class IIStudioAgent:
    """Главный агент IIStudio — Anthropic Claude API."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.session = Session(mode=settings.default_mode)
        self.context = ProjectContext(Path("."))

        # Кэш
        self._cache = CacheManager(
            redis_url=settings.redis_url,
            default_ttl=settings.cache_ttl,
            max_memory_size=settings.cache_max_size,
        )

        # Клиент Anthropic (ключ берём из env или из DB по токену пользователя)
        self._api_key: Optional[str] = os.environ.get("ANTHROPIC_API_KEY", "")
        self._client: Optional[ClaudeClient] = None
        self._current_model = settings.default_model or DEFAULT_MODEL
        self._started = False

        # Прокси (не используем для Anthropic API — он доступен напрямую)
        from proxy.manager import ProxyManager
        self._proxy_manager = ProxyManager(
            proxy_file=settings.proxy_file_path,
            check_interval=settings.proxy_check_interval,
            max_failures=settings.proxy_max_failures,
        )

    # ── Lifecycle ────────────────────────────────────────────────────────────

    async def start(self) -> None:
        """Инициализировать агента."""
        logger.info("IIStudio запускается...")

        await self._cache.start()

        # Инициализируем Claude клиент
        if self._api_key:
            self._client = ClaudeClient(self._api_key)
            logger.info("✅ Claude API готов ({})", self._current_model)
        else:
            logger.warning(
                "ANTHROPIC_API_KEY не задан. "
                "Установи: export ANTHROPIC_API_KEY=sk-ant-... "
                "или получи ключ на console.anthropic.com"
            )

        self._started = True
        logger.info("✅ IIStudio готов")

    async def stop(self) -> None:
        """Завершить работу."""
        self.session.save()
        await self._cache.stop()
        self._started = False
        logger.info("IIStudio остановлен")

    async def __aenter__(self) -> "IIStudioAgent":
        await self.start()
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self.stop()

    # ── Настройка API ключа из токена пользователя ────────────────────────────

    def set_api_key(self, api_key: str) -> None:
        """Установить Anthropic API ключ (из аккаунта пользователя)."""
        self._api_key = api_key
        self._client = ClaudeClient(api_key)

    def set_api_key_from_user_token(self, user_token: str) -> bool:
        """Найти API ключ пользователя по его IIStudio токену и установить."""
        db = get_db()
        user = db.verify_token(user_token)
        if not user:
            return False
        # У пользователя может быть свой Anthropic ключ в профиле
        anthropic_key = user.get("anthropic_api_key", "")
        if anthropic_key:
            self.set_api_key(anthropic_key)
            return True
        # Используем общий ключ из env
        if self._api_key:
            self._client = ClaudeClient(self._api_key)
            return True
        return False

    # ── Главный метод chat ────────────────────────────────────────────────────

    async def chat(
        self,
        message: str,
        mode: Optional[str] = None,
        model_id: Optional[str] = None,
        use_cache: bool = True,
        stream: bool = False,
        user_token: Optional[str] = None,  # IIStudio токен для billing
        file_path: Optional[Path] = None,   # файл для анализа
    ) -> Dict[str, Any]:
        """Отправить запрос и получить ответ.

        Returns:
            dict: success, response, model, input_tokens, output_tokens, cost_usd, cached
        """
        if not self._started:
            raise RuntimeError("Агент не запущен. Вызови await agent.start()")

        model_id = model_id or self._current_model or DEFAULT_MODEL
        mode = mode or self.session.mode

        result: Dict[str, Any] = {
            "success": False,
            "response": None,
            "model": model_id,
            "mode": mode,
            "input_tokens": 0,
            "output_tokens": 0,
            "cost_usd": 0.0,
            "cached": False,
            "error": None,
        }

        # Проверяем клиент
        if not self._client:
            result["error"] = (
                "ANTHROPIC_API_KEY не настроен. "
                "Установи: export ANTHROPIC_API_KEY=sk-ant-... "
                "Получи ключ: https://console.anthropic.com"
            )
            return result

        # Billing: проверяем баланс пользователя
        db = get_db()
        user = None
        if user_token:
            user = db.verify_token(user_token)
            if user:
                balance = user.get("balance_usd", 0.0)
                free_tokens = user.get("free_tokens", 0)
                if balance <= 0 and free_tokens <= 0:
                    result["error"] = (
                        "Баланс исчерпан. Пополни на https://orproject.online/pricing"
                    )
                    return result

        # Проверяем кэш
        if use_cache:
            cache_key = make_cache_key("chat", model_id, message)
            cached = await self._cache.get(cache_key)
            if cached:
                logger.debug("Ответ из кэша")
                self.session.add_user_message(message)
                self.session.add_assistant_message(cached["response"], model_id=model_id)
                return {**cached, "cached": True}

        # Обновляем сессию
        self.session.mode = mode
        self.session.add_user_message(message)

        # Строим messages для Claude
        messages = self._build_messages(message)

        # Отправляем запрос
        try:
            if file_path:
                api_result = await self._client.chat_with_file(
                    message=message,
                    file_path=file_path,
                    model_id=model_id,
                    max_tokens=4096,
                    system=SYSTEM_PROMPT,
                )
            else:
                api_result = await self._client.chat(
                    messages=messages,
                    model_id=model_id,
                    max_tokens=4096,
                    system=SYSTEM_PROMPT,
                )

            if api_result.get("success"):
                text = api_result["text"]
                result.update({
                    "success": True,
                    "response": text,
                    "model": model_id,
                    "input_tokens": api_result.get("input_tokens", 0),
                    "output_tokens": api_result.get("output_tokens", 0),
                    "cost_usd": api_result.get("cost_usd", 0.0),
                    "latency_ms": 0,
                })

                # Billing: вычитаем токены у пользователя
                if user and user_token:
                    total_tokens = api_result.get("input_tokens", 0) + api_result.get("output_tokens", 0)
                    cost = api_result.get("cost_usd", 0.0)
                    db.deduct_tokens(user["id"], total_tokens, model_id, cost)

                # Кэшируем
                if use_cache:
                    await self._cache.set(cache_key, result, ttl=self.settings.cache_ttl)

                # История
                self.session.add_assistant_message(text, model_id=model_id)
            else:
                result["error"] = api_result.get("error", "Неизвестная ошибка API")

        except Exception as e:
            logger.error("Ошибка запроса к Claude: {}", e)
            result["error"] = str(e)

        return result

    async def chat_stream(
        self,
        message: str,
        mode: Optional[str] = None,
        model_id: Optional[str] = None,
        user_token: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        """Стриминг ответа."""
        if not self._client:
            yield "[ERROR] ANTHROPIC_API_KEY не настроен"
            return

        model_id = model_id or self._current_model or DEFAULT_MODEL
        messages = self._build_messages(message)
        self.session.add_user_message(message)

        full_text = ""
        input_tokens = 0
        output_tokens = 0

        async for event in self._client.stream_chat(
            messages=messages,
            model_id=model_id,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
        ):
            if event["type"] == "delta":
                text = event["text"]
                full_text += text
                yield text
            elif event["type"] == "done":
                input_tokens = event.get("input_tokens", 0)
                output_tokens = event.get("output_tokens", 0)
                cost = event.get("cost_usd", 0.0)
                # Billing
                if user_token:
                    db = get_db()
                    user = db.verify_token(user_token)
                    if user:
                        db.deduct_tokens(user["id"], input_tokens + output_tokens, model_id, cost)
            elif event["type"] == "error":
                yield f"[ERROR] {event['error']}"
                return

        if full_text:
            self.session.add_assistant_message(full_text, model_id=model_id)

    # ── Режим и модель ────────────────────────────────────────────────────────

    def set_mode(self, mode: str) -> bool:
        valid = {"text", "images", "video", "coding"}
        if mode not in valid:
            return False
        self.session.mode = mode
        return True

    def set_model(self, model_id: str) -> bool:
        if model_id in MODELS:
            self._current_model = model_id
            logger.info("Модель: {}", MODELS[model_id]["name"])
            return True
        return False

    # ── Вспомогательные ──────────────────────────────────────────────────────

    def _build_messages(self, new_message: str) -> List[Dict[str, Any]]:
        """Построить список сообщений для Claude из истории сессии."""
        messages = []
        # История (последние 20 сообщений)
        for msg in self.session.messages[-20:]:
            if msg.role in ("user", "assistant"):
                messages.append({"role": msg.role, "content": msg.content})
        # Добавляем новое сообщение если его ещё нет
        if not messages or messages[-1]["content"] != new_message:
            messages.append({"role": "user", "content": new_message})
        return messages

    async def get_status(self) -> Dict[str, Any]:
        cache_info = await self._cache.info()
        return {
            "version":        self.settings.iistudio_version,
            "env":            self.settings.iistudio_env,
            "mode":           self.session.mode,
            "model":          self._current_model,
            "model_name":     MODELS.get(self._current_model, {}).get("name", self._current_model),
            "session_id":     self.session.session_id,
            "messages":       self.session.message_count,
            "api_ready":      self._client is not None,
            "browser_running": False,  # Playwright больше не используем
            "proxy":          {"current": None},
            "cache":          cache_info,
        }

    # ── История ───────────────────────────────────────────────────────────────

    def get_history(self) -> List[Dict[str, Any]]:
        return self.session.history

    def clear_history(self) -> None:
        self.session.clear()

    async def get_proxy_status(self) -> List[Dict[str, Any]]:
        return []

    async def switch_proxy(self) -> Optional[Dict[str, Any]]:
        return None

    async def screenshot(self, path: str = "screenshot.png") -> str:
        raise RuntimeError("Браузер не используется в этой версии")

    # ── Сравнение моделей ─────────────────────────────────────────────────────

    async def compare(
        self, message: str, mode: Optional[str] = None
    ) -> Dict[str, Dict[str, Any]]:
        """Сравнить ответы всех моделей."""
        results: Dict[str, Dict[str, Any]] = {}
        for model_id, info in MODELS.items():
            logger.info("Compare: {}", info["name"])
            r = await self.chat(message, model_id=model_id)
            results[model_id] = {
                "model_name": info["name"],
                "provider": info["provider"],
                **r,
            }
            await asyncio.sleep(0.5)
        return results
