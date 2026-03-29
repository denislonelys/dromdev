# ============================================================================
# IIStudio — Xvfb + Chrome менеджер
#
# Запускает виртуальный дисплей Xvfb и реальный Chrome с remote debugging.
# Chrome через Xvfb получает высокий reCAPTCHA v3 score (0.7+) vs headless (0.1).
# ============================================================================

from __future__ import annotations

import asyncio
import os
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Optional

from utils.logger import logger

XVFB_DISPLAY = ":99"
CDP_PORT = 9222
CDP_URL = f"http://localhost:{CDP_PORT}"

# Пути к Chromium
CHROME_PATHS = [
    "/root/.cache/ms-playwright/chromium-1208/chrome-linux64/chrome",
    "/usr/bin/chromium-browser",
    "/usr/bin/chromium",
    "/usr/bin/google-chrome",
    shutil.which("chromium") or "",
    shutil.which("google-chrome") or "",
]


class XvfbChromeManager:
    """
    Запускает Xvfb + Chrome в режиме remote debugging.
    Playwright подключается через CDP к уже запущенному Chrome.
    """

    def __init__(
        self,
        display: str = XVFB_DISPLAY,
        cdp_port: int = CDP_PORT,
        user_data_dir: str = "/tmp/iistudio-chrome",
    ) -> None:
        self.display = display
        self.cdp_port = cdp_port
        self.cdp_url = f"http://localhost:{cdp_port}"
        self.user_data_dir = user_data_dir

        self._xvfb_proc: Optional[subprocess.Popen] = None
        self._chrome_proc: Optional[subprocess.Popen] = None

    # ── Запуск ───────────────────────────────────────────────────────────────

    def start(self) -> bool:
        """Запустить Xvfb и Chrome. Возвращает True если успешно."""
        # Проверяем что всё не уже запущено
        if self._is_chrome_running():
            logger.info("Chrome уже запущен на CDP port {}", self.cdp_port)
            return True

        # 1. Запускаем Xvfb
        if not self._start_xvfb():
            logger.warning("Xvfb не запустился — пробуем без него (headless fallback)")

        # 2. Запускаем Chrome
        return self._start_chrome()

    def stop(self) -> None:
        """Остановить Chrome и Xvfb."""
        if self._chrome_proc and self._chrome_proc.poll() is None:
            self._chrome_proc.terminate()
            try:
                self._chrome_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._chrome_proc.kill()
            self._chrome_proc = None
            logger.info("Chrome остановлен")

        if self._xvfb_proc and self._xvfb_proc.poll() is None:
            self._xvfb_proc.terminate()
            try:
                self._xvfb_proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self._xvfb_proc.kill()
            self._xvfb_proc = None
            logger.info("Xvfb остановлен")

    def _start_xvfb(self) -> bool:
        xvfb = shutil.which("Xvfb")
        if not xvfb:
            logger.warning("Xvfb не найден")
            return False

        try:
            self._xvfb_proc = subprocess.Popen(
                [xvfb, self.display, "-screen", "0", "1920x1080x24", "-nolisten", "tcp"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            time.sleep(2)
            if self._xvfb_proc.poll() is None:
                os.environ["DISPLAY"] = self.display
                logger.info("Xvfb запущен на {} (PID={})", self.display, self._xvfb_proc.pid)
                return True
            logger.warning("Xvfb завершился сразу")
            return False
        except Exception as e:
            logger.warning("Ошибка Xvfb: {}", e)
            return False

    def _start_chrome(self) -> bool:
        # Находим Chromium
        chrome_bin = None
        for path in CHROME_PATHS:
            if path and Path(path).exists():
                chrome_bin = path
                break

        if not chrome_bin:
            logger.error("Chromium не найден! Установи: playwright install chromium")
            return False

        env = os.environ.copy()
        if self.display:
            env["DISPLAY"] = self.display

        Path(self.user_data_dir).mkdir(parents=True, exist_ok=True)

        cmd = [
            chrome_bin,
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--disable-blink-features=AutomationControlled",
            f"--remote-debugging-port={self.cdp_port}",
            f"--user-data-dir={self.user_data_dir}",
            "--window-size=1920,1080",
            "--no-first-run",
            "--disable-infobars",
            "--disable-notifications",
            "--disable-popup-blocking",
            "about:blank",
        ]

        try:
            self._chrome_proc = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                env=env,
            )
            # Ждём пока Chrome поднимет CDP
            for _ in range(15):
                time.sleep(1)
                if self._is_chrome_running():
                    logger.info(
                        "Chrome запущен (PID={}) на CDP port {}",
                        self._chrome_proc.pid,
                        self.cdp_port,
                    )
                    return True

            logger.error("Chrome не запустился за 15 секунд")
            return False
        except Exception as e:
            logger.error("Ошибка запуска Chrome: {}", e)
            return False

    def _is_chrome_running(self) -> bool:
        """Проверить что Chrome запущен и CDP доступен."""
        import urllib.request
        try:
            req = urllib.request.urlopen(f"{self.cdp_url}/json/version", timeout=2)
            return req.status == 200
        except Exception:
            return False

    @property
    def is_running(self) -> bool:
        return self._is_chrome_running()


# Singleton для использования в агенте
_manager: Optional[XvfbChromeManager] = None


def get_xvfb_chrome_manager() -> XvfbChromeManager:
    global _manager
    if _manager is None:
        _manager = XvfbChromeManager()
    return _manager


async def ensure_chrome_running() -> str:
    """Убедиться что Chrome запущен и вернуть CDP URL."""
    manager = get_xvfb_chrome_manager()
    if not manager.is_running:
        logger.info("Запускаем Chrome через Xvfb...")
        loop = asyncio.get_event_loop()
        ok = await loop.run_in_executor(None, manager.start)
        if not ok:
            raise RuntimeError(
                "Не удалось запустить Chrome. Убедись что установлен Xvfb и Chromium."
            )
    return manager.cdp_url
