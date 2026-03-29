# ============================================================================
# IIStudio — MTProto SOCKS5 туннель (через mtg / mtproto-proxy)
# ============================================================================

from __future__ import annotations

import asyncio
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional

from utils.logger import logger


class MTProtoTunnel:
    """Управление MTProto → SOCKS5 туннелем через mtg."""

    def __init__(
        self,
        proxy: Dict[str, Any],
        local_host: str = "127.0.0.1",
        local_port: int = 11080,
    ) -> None:
        self.proxy = proxy
        self.local_host = local_host
        self.local_port = local_port
        self._process: Optional[subprocess.Popen] = None  # type: ignore
        self._task: Optional[asyncio.Task] = None

    @property
    def socks5_url(self) -> str:
        return f"socks5://{self.local_host}:{self.local_port}"

    @property
    def is_running(self) -> bool:
        if self._process is None:
            return False
        return self._process.poll() is None

    async def start(self) -> bool:
        """Запустить MTProto туннель. Возвращает True если успешно."""
        if self.proxy.get("type") != "mtproto":
            logger.warning("Туннель: прокси не MTProto типа")
            return False

        mtg_bin = shutil.which("mtg")
        if not mtg_bin:
            logger.warning(
                "mtg не найден в PATH — MTProto туннель недоступен. "
                "Установи: https://github.com/9seconds/mtg"
            )
            return False

        host = self.proxy["host"]
        port = self.proxy["port"]
        secret = self.proxy["secret"]

        cmd = [
            mtg_bin,
            "run",
            "--bind", f"{self.local_host}:{self.local_port}",
            f"{host}:{port}:{secret}",
        ]

        logger.info(
            "Запуск MTProto туннеля: {}:{} → {}:{}",
            host, port, self.local_host, self.local_port,
        )
        try:
            self._process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            await asyncio.sleep(1.5)  # дать время стартовать
            if self.is_running:
                logger.info("MTProto туннель запущен (PID={})", self._process.pid)
                return True
            else:
                logger.error("MTProto туннель упал при старте")
                return False
        except Exception as e:
            logger.error("Ошибка запуска MTProto туннеля: {}", e)
            return False

    async def stop(self) -> None:
        """Остановить туннель."""
        if self._process and self.is_running:
            logger.info("Остановка MTProto туннеля (PID={})", self._process.pid)
            self._process.terminate()
            try:
                await asyncio.wait_for(
                    asyncio.get_event_loop().run_in_executor(None, self._process.wait),
                    timeout=5.0,
                )
            except asyncio.TimeoutError:
                self._process.kill()
            self._process = None

    async def restart(self) -> bool:
        await self.stop()
        return await self.start()
