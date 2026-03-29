# ============================================================================
# IIStudio — Менеджер прокси (пул, ротация, health-check)
# ============================================================================

from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from proxy.checker import check_proxies_bulk
from proxy.tunnel import MTProtoTunnel
from utils.helpers import load_proxies
from utils.logger import logger


class ProxyManager:
    """Управление пулом прокси с автоматической ротацией и health-check."""

    def __init__(
        self,
        proxy_file: Path,
        check_interval: int = 300,
        max_failures: int = 3,
        mtproto_local_host: str = "127.0.0.1",
        mtproto_local_port: int = 11080,
    ) -> None:
        self.proxy_file = proxy_file
        self.check_interval = check_interval
        self.max_failures = max_failures
        self.mtproto_local_host = mtproto_local_host
        self.mtproto_local_port = mtproto_local_port

        self._proxies: List[Dict[str, Any]] = []
        self._current_idx: int = 0
        self._failures: Dict[str, int] = {}  # proxy_id → failure count
        self._tunnel: Optional[MTProtoTunnel] = None
        self._check_task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()

    # ── Инициализация ────────────────────────────────────────────────────────

    async def start(self) -> None:
        """Загрузить прокси, проверить и запустить фоновый health-check."""
        await self._load_and_check()
        self._check_task = asyncio.create_task(self._health_loop())
        logger.info("ProxyManager запущен. Прокси: {}", len(self._proxies))

    async def stop(self) -> None:
        if self._check_task:
            self._check_task.cancel()
            try:
                await self._check_task
            except asyncio.CancelledError:
                pass
        if self._tunnel:
            await self._tunnel.stop()
        logger.info("ProxyManager остановлен")

    # ── Публичный интерфейс ──────────────────────────────────────────────────

    def get_current(self) -> Optional[Dict[str, Any]]:
        """Вернуть текущий активный прокси (или None если нет живых)."""
        alive = self._alive_proxies()
        if not alive:
            return None
        return alive[self._current_idx % len(alive)]

    def get_socks5_url(self) -> Optional[str]:
        """URL для использования в Playwright / aiohttp."""
        proxy = self.get_current()
        if proxy is None:
            return None

        ptype = proxy.get("type")
        if ptype == "socks5":
            user = proxy.get("username", "")
            pwd = proxy.get("password", "")
            host = proxy["host"]
            port = proxy["port"]
            if user and pwd:
                return f"socks5://{user}:{pwd}@{host}:{port}"
            return f"socks5://{host}:{port}"

        if ptype == "mtproto":
            # MTProto даёт локальный SOCKS5 через туннель
            if self._tunnel and self._tunnel.is_running:
                return self._tunnel.socks5_url

        return None

    async def switch(self) -> Optional[Dict[str, Any]]:
        """Принудительно переключить на следующий прокси."""
        async with self._lock:
            alive = self._alive_proxies()
            if not alive:
                logger.warning("Нет живых прокси для переключения")
                return None
            self._current_idx = (self._current_idx + 1) % len(alive)
            proxy = alive[self._current_idx]
            logger.info(
                "Переключен прокси → {}:{} ({})",
                proxy["host"], proxy["port"], proxy["type"],
            )
            await self._start_tunnel_if_needed(proxy)
            return proxy

    def report_failure(self, proxy: Optional[Dict[str, Any]] = None) -> None:
        """Сообщить об ошибке текущего прокси."""
        if proxy is None:
            proxy = self.get_current()
        if proxy is None:
            return
        key = self._proxy_id(proxy)
        self._failures[key] = self._failures.get(key, 0) + 1
        failures = self._failures[key]
        logger.warning(
            "Прокси {}:{} — ошибка #{}", proxy["host"], proxy["port"], failures
        )
        if failures >= self.max_failures:
            proxy["alive"] = False
            logger.error(
                "Прокси {}:{} отключён после {} ошибок",
                proxy["host"], proxy["port"], failures,
            )

    def get_status(self) -> List[Dict[str, Any]]:
        """Статус всех прокси."""
        result = []
        for p in self._proxies:
            result.append({
                "type": p.get("type"),
                "host": p.get("host"),
                "port": p.get("port"),
                "alive": p.get("alive", False),
                "latency_ms": p.get("latency_ms"),
                "failures": self._failures.get(self._proxy_id(p), 0),
                "checked_at": p.get("checked_at"),
            })
        return result

    # ── Внутренние методы ────────────────────────────────────────────────────

    async def _load_and_check(self) -> None:
        raw = load_proxies(self.proxy_file)
        if not raw:
            logger.warning("Прокси не загружены — работаем без прокси")
            self._proxies = []
            return

        logger.info("Проверяем {} прокси...", len(raw))
        checked = await check_proxies_bulk(raw, concurrency=10, timeout=15)
        self._proxies = checked
        self._current_idx = 0

        # Запустить MTProto туннель для первого живого MTProto прокси
        alive = self._alive_proxies()
        if alive:
            await self._start_tunnel_if_needed(alive[0])

    async def _health_loop(self) -> None:
        """Фоновый цикл проверки прокси."""
        while True:
            try:
                await asyncio.sleep(self.check_interval)
                logger.debug("Health-check прокси...")
                await self._load_and_check()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Ошибка health-check прокси: {}", e)

    async def _start_tunnel_if_needed(self, proxy: Dict[str, Any]) -> None:
        if proxy.get("type") != "mtproto":
            return
        if self._tunnel and self._tunnel.is_running:
            # Проверяем, тот же ли прокси
            if (
                self._tunnel.proxy.get("host") == proxy.get("host")
                and self._tunnel.proxy.get("port") == proxy.get("port")
            ):
                return
            await self._tunnel.stop()

        self._tunnel = MTProtoTunnel(
            proxy,
            local_host=self.mtproto_local_host,
            local_port=self.mtproto_local_port,
        )
        await self._tunnel.start()

    def _alive_proxies(self) -> List[Dict[str, Any]]:
        return [p for p in self._proxies if p.get("alive", False)]

    @staticmethod
    def _proxy_id(proxy: Dict[str, Any]) -> str:
        return f"{proxy.get('host')}:{proxy.get('port')}"
