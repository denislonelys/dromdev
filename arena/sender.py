# ============================================================================
# IIStudio — Отправитель запросов на arena.ai
# ============================================================================

from __future__ import annotations

import asyncio
from typing import Any, AsyncGenerator, Dict, Optional

from arena.models import AIModel, get_default_model, get_model
from arena.parser import ArenaParser
from utils.logger import logger


class ArenaSender:
    """Высокоуровневый интерфейс для отправки запросов на arena.ai."""

    def __init__(self, parser: ArenaParser, email: str, password: str) -> None:
        self.parser = parser
        self.email = email
        self.password = password

    async def send(
        self,
        message: str,
        mode: str = "text",
        model_id: Optional[str] = None,
        stream: bool = False,
        timeout: int = 120,
    ) -> Dict[str, Any]:
        """Отправить запрос и вернуть ответ.

        Args:
            message: текст запроса
            mode: режим (text/images/video/coding)
            model_id: ID модели (None = default для режима)
            stream: возвращать ли стрим (нет в этом методе — используй send_stream)
            timeout: таймаут ожидания ответа в секундах

        Returns:
            dict с ключами: success, response, model, mode, error
        """
        result: Dict[str, Any] = {
            "success": False,
            "response": None,
            "model": model_id,
            "mode": mode,
            "error": None,
        }

        try:
            # Убедиться что залогинены (только если ещё нет)
            if not self.parser._logged_in:
                if not await self.parser.ensure_logged_in(self.email, self.password):
                    result["error"] = "Не удалось авторизоваться на arena.ai"
                    return result

            # Выбрать модель (пропускаем если не удаётся — дефолтная модель arena.ai)
            model = _resolve_model(model_id, mode)
            if model:
                try:
                    await self.parser.select_model(model)
                except Exception:
                    pass  # не критично — arena.ai использует свою дефолтную
                result["model"] = model.id

            # Отправить сообщение с retry при rate limit
            max_attempts = 3
            for attempt in range(1, max_attempts + 1):
                if not await self.parser.send_message(message):
                    result["error"] = "Не удалось отправить сообщение"
                    return result

                response = await self.parser.wait_for_response(timeout=timeout)
                if response:
                    result["success"] = True
                    result["response"] = response
                    break
                else:
                    if attempt < max_attempts:
                        logger.warning("Попытка {}/{} не дала ответа — ждём 30с", attempt, max_attempts)
                        await asyncio.sleep(30)
                    else:
                        result["error"] = "Нет ответа после {} попыток".format(max_attempts)

        except Exception as e:
            logger.error("Ошибка при отправке запроса: {}", e)
            result["error"] = str(e)

        return result

    async def send_stream(
        self,
        message: str,
        mode: str = "text",
        model_id: Optional[str] = None,
        timeout: int = 120,
    ) -> AsyncGenerator[str, None]:
        """Стриминг ответа по мере поступления.

        Yields:
            дельты текста ответа
        """
        if not await self.parser.ensure_logged_in(self.email, self.password):
            yield "[ERROR] Не удалось авторизоваться"
            return

        if not await self.parser.switch_mode(mode):
            yield f"[ERROR] Не удалось переключить режим: {mode}"
            return

        model = _resolve_model(model_id, mode)
        if model:
            await self.parser.select_model(model)

        if not await self.parser.send_message(message):
            yield "[ERROR] Не удалось отправить сообщение"
            return

        async for delta in self.parser.stream_response(timeout=timeout):
            yield delta

    async def send_to_all_models(
        self,
        message: str,
        mode: str = "text",
        timeout: int = 60,
    ) -> Dict[str, Dict[str, Any]]:
        """Отправить запрос во все модели текущего режима (compare mode).

        Returns:
            dict: model_id → result dict
        """
        from arena.models import get_models_for_mode
        models = get_models_for_mode(mode)
        results: Dict[str, Dict[str, Any]] = {}

        for model in models[:5]:  # ограничиваем 5 моделями
            logger.info("Compare: отправка в {}", model.name)
            res = await self.send(message, mode=mode, model_id=model.id, timeout=timeout)
            results[model.id] = {
                "model_name": model.name,
                "provider": model.provider,
                **res,
            }
            await asyncio.sleep(1)  # пауза между запросами

        return results


def _resolve_model(model_id: Optional[str], mode: str) -> Optional[AIModel]:
    """Найти модель по ID или вернуть дефолтную для режима."""
    if model_id:
        m = get_model(model_id)
        if m:
            return m
    return get_default_model(mode)
