# ============================================================================
# IIStudio — Главный агент (оркестратор)
# ============================================================================

from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional

from arena.models import get_default_model, get_model, get_models_for_mode
from arena.parser import ArenaParser
from arena.receiver import ResponseProcessor
from arena.sender import ArenaSender
from cache.cache import CacheManager
from core.account_pool import AccountPool
from config import Settings
from core.browser import BrowserManager
from core.context import ProjectContext
from core.session import Session
from core.xvfb_chrome import ensure_chrome_running
from proxy.manager import ProxyManager
from utils.helpers import make_cache_key
from utils.logger import logger


class IIStudioAgent:
    """Главный агент IIStudio — объединяет браузер, прокси, кэш, сессии."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.session = Session(mode=settings.default_mode, model_id=settings.default_model)
        self.context = ProjectContext(Path("."))

        # Компоненты
        self._proxy_manager = ProxyManager(
            proxy_file=settings.proxy_file_path,
            check_interval=settings.proxy_check_interval,
            max_failures=settings.proxy_max_failures,
            mtproto_local_host=settings.mtproto_socks5_host,
            mtproto_local_port=settings.mtproto_socks5_port,
        )
        self._cache = CacheManager(
            redis_url=settings.redis_url,
            default_ttl=settings.cache_ttl,
            max_memory_size=settings.cache_max_size,
        )
        self._browser: Optional[BrowserManager] = None
        self._sender: Optional[ArenaSender] = None
        self._started = False

    # ── Lifecycle ────────────────────────────────────────────────────────────

    async def start(self) -> None:
        """Инициализировать все компоненты."""
        logger.info("IIStudio запускается...")

        # Кэш
        await self._cache.start()

        # Прокси
        await self._proxy_manager.start()
        proxy_url = self._proxy_manager.get_socks5_url()

        # Браузер через Xvfb+Chrome (обход reCAPTCHA) или CDP подключение
        try:
            cdp_url = await ensure_chrome_running()
            self._browser = BrowserManager(
                headless=False,
                proxy_url=proxy_url,
                user_agent=self.settings.browser_user_agent,
                viewport_width=self.settings.browser_viewport_width,
                viewport_height=self.settings.browser_viewport_height,
                timeout=self.settings.browser_timeout,
                cdp_url=cdp_url,
            )
        except Exception as e:
            logger.warning("Xvfb/Chrome недоступен ({}), используем headless", e)
            self._browser = BrowserManager(
                headless=True,
                proxy_url=proxy_url,
                user_agent=self.settings.browser_user_agent,
                viewport_width=self.settings.browser_viewport_width,
                viewport_height=self.settings.browser_viewport_height,
                timeout=self.settings.browser_timeout,
            )
        page = await self._browser.start()

        # Пул аккаунтов (авто-смена при rate limit)
        account_pool = AccountPool()
        # Добавляем основной аккаунт из .env если его ещё нет
        if self.settings.arena_email and not any(
            a["email"] == self.settings.arena_email for a in account_pool._accounts
        ):
            account_pool.add_account(self.settings.arena_email, self.settings.arena_password)
            account_pool._current_idx = len(account_pool._accounts) - 1

        # Парсер + отправитель
        parser = ArenaParser(page, base_url=self.settings.arena_base_url)
        self._sender = ArenaSender(
            parser=parser,
            email=account_pool.current_email or self.settings.arena_email,
            password=account_pool.current_password or self.settings.arena_password,
        )
        self._sender._account_pool = account_pool  # type: ignore

        # Инициализация: загрузка страницы, cookies, логин (один раз!)
        init_ok = await self._sender.parser.initialize(
            email=self.settings.arena_email,
            password=self.settings.arena_password,
        )
        if not init_ok:
            logger.warning("Инициализация arena.ai не завершена — проверь email/password в .env")

        self._started = True
        logger.info("✅ IIStudio готов к работе")

    async def stop(self) -> None:
        """Корректно завершить все компоненты."""
        self.session.save()
        await self._cache.stop()
        await self._proxy_manager.stop()
        if self._browser:
            await self._browser.stop()
        self._started = False
        logger.info("IIStudio остановлен")

    async def __aenter__(self) -> "IIStudioAgent":
        await self.start()
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self.stop()

    # ── Главный метод ────────────────────────────────────────────────────────

    async def chat(
        self,
        message: str,
        mode: Optional[str] = None,
        model_id: Optional[str] = None,
        use_cache: bool = True,
        stream: bool = False,
    ) -> Dict[str, Any]:
        """Отправить запрос и получить ответ.

        Args:
            message: текст запроса
            mode: режим (text/images/video/coding), по умолчанию из сессии
            model_id: модель, по умолчанию из сессии
            use_cache: проверять кэш перед отправкой
            stream: стриминг (используй chat_stream для этого)

        Returns:
            dict с ключами: success, response, model, mode, cached, latency_ms
        """
        if not self._started:
            raise RuntimeError("Агент не запущен. Вызови await agent.start()")

        mode = mode or self.session.mode
        model_id = model_id or self.session.model_id

        # Обновить сессию
        self.session.mode = mode
        if model_id:
            self.session.model_id = model_id
        self.session.add_user_message(message)

        # Проверить кэш
        if use_cache:
            cache_key = make_cache_key("chat", mode, model_id or "", message)
            cached = await self._cache.get(cache_key)
            if cached:
                logger.debug("Ответ из кэша")
                self.session.add_assistant_message(cached["response"], model_id=cached.get("model"))
                return {**cached, "cached": True}

        # Отправить запрос
        start_time = time.perf_counter()
        result = await self._sender.send(
            message=message,
            mode=mode,
            model_id=model_id,
            timeout=self.settings.request_timeout,
        )
        latency_ms = (time.perf_counter() - start_time) * 1000
        result["latency_ms"] = round(latency_ms, 1)
        result["cached"] = False

        # Защита от None response
        if result is None:
            result = {"success": False, "response": None, "error": "Нет ответа от агента", "model": model_id, "mode": mode}

        # Сохранить в кэш если успешно
        if result.get("success") and use_cache:
            await self._cache.set(cache_key, result, ttl=self.settings.cache_ttl)

        # Добавить в историю
        if result.get("response"):
            self.session.add_assistant_message(
                result["response"],
                model_id=result.get("model"),
                latency_ms=latency_ms,
            )

        # При ошибке прокси — пробуем переключить
        if not result.get("success"):
            self._proxy_manager.report_failure()
            new_proxy = await self._proxy_manager.switch()
            if new_proxy and self._browser:
                await self._browser.update_proxy(self._proxy_manager.get_socks5_url())

        return result

    async def chat_stream(
        self,
        message: str,
        mode: Optional[str] = None,
        model_id: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        """Стриминг ответа по мере поступления."""
        if not self._started:
            raise RuntimeError("Агент не запущен")

        mode = mode or self.session.mode
        model_id = model_id or self.session.model_id
        self.session.add_user_message(message)

        full_response = ""
        async for delta in self._sender.send_stream(
            message=message, mode=mode, model_id=model_id,
            timeout=self.settings.request_timeout,
        ):
            full_response += delta
            yield delta

        if full_response:
            self.session.add_assistant_message(full_response, model_id=model_id)

    async def compare(
        self,
        message: str,
        mode: Optional[str] = None,
    ) -> Dict[str, Dict[str, Any]]:
        """Сравнить ответы нескольких моделей."""
        mode = mode or self.session.mode
        return await self._sender.send_to_all_models(
            message=message,
            mode=mode,
            timeout=self.settings.request_timeout,
        )

    # ── Управление режимом/моделью ────────────────────────────────────────────

    def set_mode(self, mode: str) -> bool:
        valid = {"text", "images", "video", "coding"}
        if mode not in valid:
            return False
        self.session.mode = mode
        logger.info("Режим: {}", mode)
        return True

    def set_model(self, model_id: str) -> bool:
        model = get_model(model_id)
        if not model:
            return False
        self.session.model_id = model.id
        logger.info("Модель: {}", model.name)
        return True

    # ── Статус ────────────────────────────────────────────────────────────────

    async def get_status(self) -> Dict[str, Any]:
        proxy = self._proxy_manager.get_current()
        cache_info = await self._cache.info()
        return {
            "version": self.settings.iistudio_version,
            "env": self.settings.iistudio_env,
            "mode": self.session.mode,
            "model": self.session.model_id,
            "session_id": self.session.session_id,
            "messages": self.session.message_count,
            "proxy": {
                "current": f"{proxy['host']}:{proxy['port']}" if proxy else None,
                "type": proxy.get("type") if proxy else None,
                "latency_ms": proxy.get("latency_ms") if proxy else None,
            },
            "cache": cache_info,
            "browser_running": self._browser is not None,
        }

    async def screenshot(self, path: str = "screenshot.png") -> str:
        if self._browser:
            return await self._browser.screenshot(path)
        raise RuntimeError("Браузер не запущен")

    # ── История ───────────────────────────────────────────────────────────────

    def get_history(self) -> List[Dict[str, Any]]:
        return self.session.history

    def clear_history(self) -> None:
        self.session.clear()

    async def get_proxy_status(self) -> List[Dict[str, Any]]:
        return self._proxy_manager.get_status()

    async def switch_proxy(self) -> Optional[Dict[str, Any]]:
        proxy = await self._proxy_manager.switch()
        if proxy and self._browser:
            await self._browser.update_proxy(self._proxy_manager.get_socks5_url())
        return proxy
