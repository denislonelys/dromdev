# ============================================================================
# IIStudio — Менеджер браузера (Playwright + Xvfb для обхода reCAPTCHA)
#
# КЛЮЧЕВОЕ ОТКРЫТИЕ: arena.ai требует reCAPTCHA v3 с высоким score.
# Headless браузер получает score ~0.1 (datacenter IP), что недостаточно.
# Решение: запускаем РЕАЛЬНЫЙ Chrome через виртуальный дисплей Xvfb.
# Это даёт score ~0.7+ и запросы проходят.
# ============================================================================

from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, Optional

from playwright.async_api import (
    Browser,
    BrowserContext,
    Page,
    Playwright,
    async_playwright,
)

from utils.logger import logger

SESSION_DIR = Path(".iistudio/browser_session")
XVFB_DISPLAY = ":99"


class XvfbManager:
    """Управление виртуальным дисплеем Xvfb."""

    def __init__(self, display: str = XVFB_DISPLAY) -> None:
        self.display = display
        self._process: Optional[subprocess.Popen] = None

    @property
    def is_running(self) -> bool:
        return self._process is not None and self._process.poll() is None

    def start(self) -> bool:
        if self.is_running:
            return True
        
        xvfb_bin = shutil.which("Xvfb")
        if not xvfb_bin:
            logger.warning("Xvfb не найден — будет использован headless режим (может блокироваться reCAPTCHA)")
            return False

        try:
            self._process = subprocess.Popen(
                [xvfb_bin, self.display, "-screen", "0", "1920x1080x24", "-nolisten", "tcp"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            time.sleep(2)
            if self.is_running:
                logger.info("Xvfb запущен на дисплее {} (PID={})", self.display, self._process.pid)
                os.environ["DISPLAY"] = self.display
                return True
            else:
                logger.warning("Xvfb не запустился")
                return False
        except Exception as e:
            logger.warning("Ошибка запуска Xvfb: {}", e)
            return False

    def stop(self) -> None:
        if self._process and self.is_running:
            self._process.terminate()
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()
            self._process = None
            logger.debug("Xvfb остановлен")


class BrowserManager:
    """
    Менеджер браузера Playwright.
    
    Стратегия запуска:
    1. Пытаемся запустить Xvfb + реальный Chrome (лучший reCAPTCHA score)
    2. Если Xvfb недоступен — подключаемся к уже запущенному Chrome (CDP)
    3. Fallback: headless (низкий score, может блокироваться)
    """

    def __init__(
        self,
        headless: bool = False,  # False = через Xvfb, лучше для reCAPTCHA
        proxy_url: Optional[str] = None,
        user_agent: Optional[str] = None,
        viewport_width: int = 1920,
        viewport_height: int = 1080,
        timeout: int = 60000,
        session_dir: Path = SESSION_DIR,
        cdp_url: Optional[str] = None,  # подключиться к существующему Chrome
        xvfb_display: str = XVFB_DISPLAY,
    ) -> None:
        self.headless = headless
        self.proxy_url = proxy_url
        self.user_agent = user_agent or (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        self.viewport_width = viewport_width
        self.viewport_height = viewport_height
        self.timeout = timeout
        self.session_dir = session_dir
        self.cdp_url = cdp_url
        self.xvfb_display = xvfb_display

        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None
        self._xvfb = XvfbManager(xvfb_display)
        self._using_xvfb = False
        self._using_cdp = False

    # ── Lifecycle ────────────────────────────────────────────────────────────

    async def start(self) -> Page:
        """Запустить браузер и вернуть страницу."""
        self._playwright = await async_playwright().start()

        # Способ 1: Подключиться к существующему Chrome через CDP
        if self.cdp_url:
            return await self._connect_cdp()

        # Способ 2: Запустить Xvfb + реальный Chrome
        xvfb_ok = self._xvfb.start()
        if xvfb_ok:
            logger.info("Запуск Chrome через Xvfb (режим обхода reCAPTCHA)")
            return await self._start_with_xvfb()

        # Способ 3: Headless (fallback)
        logger.warning("Xvfb недоступен — запускаем headless (reCAPTCHA может блокировать)")
        return await self._start_headless()

    async def _connect_cdp(self) -> Page:
        """Подключиться к уже запущенному Chrome через remote debugging."""
        logger.info("Подключаемся к Chrome CDP: {}", self.cdp_url)
        self._browser = await self._playwright.chromium.connect_over_cdp(self.cdp_url)
        contexts = self._browser.contexts
        self._context = contexts[0] if contexts else await self._browser.new_context()
        pages = self._context.pages
        self._page = pages[0] if pages else await self._context.new_page()
        self._page.set_default_timeout(self.timeout)
        self._using_cdp = True
        logger.info("Подключён к Chrome CDP")
        return self._page

    async def _start_with_xvfb(self) -> Page:
        """Запустить Chrome через Xvfb (НЕ headless)."""
        os.environ["DISPLAY"] = self.xvfb_display
        self._using_xvfb = True

        launch_kwargs: Dict[str, Any] = {
            "headless": False,  # Важно! Не headless через Xvfb
            "args": [
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
                "--disable-features=IsolateOrigins",
                "--window-size=1920,1080",
                "--start-maximized",
                "--no-first-run",
                "--disable-infobars",
                f"--display={self.xvfb_display}",
            ],
            "env": {**os.environ, "DISPLAY": self.xvfb_display},
        }

        if self.proxy_url:
            launch_kwargs["proxy"] = {"server": self.proxy_url}

        self._browser = await self._playwright.chromium.launch(**launch_kwargs)
        return await self._setup_context()

    async def _start_headless(self) -> Page:
        """Запустить в headless режиме (fallback)."""
        launch_kwargs: Dict[str, Any] = {
            "headless": True,
            "args": [
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
            ],
        }
        if self.proxy_url:
            launch_kwargs["proxy"] = {"server": self.proxy_url}

        self._browser = await self._playwright.chromium.launch(**launch_kwargs)
        return await self._setup_context()

    async def _setup_context(self) -> Page:
        """Настроить контекст браузера."""
        context_kwargs: Dict[str, Any] = {
            "viewport": {"width": self.viewport_width, "height": self.viewport_height},
            "user_agent": self.user_agent,
            "locale": "en-US",
            "timezone_id": "Europe/Amsterdam",
            "accept_downloads": True,
        }

        storage_state = self._get_storage_state_path()
        if storage_state.exists():
            logger.debug("Загружаю сохранённую сессию из {}", storage_state)
            context_kwargs["storage_state"] = str(storage_state)

        if self.proxy_url:
            context_kwargs["proxy"] = {"server": self.proxy_url}

        self._context = await self._browser.new_context(**context_kwargs)

        # Anti-detection script
        await self._context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            Object.defineProperty(navigator, 'plugins', {get: () => [
                {name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer'},
                {name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai'},
            ]});
            Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
            window.chrome = {runtime: {}, loadTimes: function(){}, csi: function(){}, app: {}};
        """)

        self._page = await self._context.new_page()
        self._page.set_default_timeout(self.timeout)
        self._page.set_default_navigation_timeout(self.timeout)

        mode = "Xvfb" if self._using_xvfb else "headless"
        logger.info("Браузер запущен ({})", mode)
        return self._page

    async def stop(self) -> None:
        """Сохранить сессию и закрыть браузер."""
        await self._save_session()
        if self._context and not self._using_cdp:
            try:
                await self._context.close()
            except Exception:
                pass
        if self._browser:
            try:
                await self._browser.close()
            except Exception:
                pass
        if self._playwright:
            try:
                await self._playwright.stop()
            except Exception:
                pass
        if self._using_xvfb:
            self._xvfb.stop()

        self._page = None
        self._context = None
        self._browser = None
        self._playwright = None
        logger.info("Браузер закрыт")

    async def restart(self, proxy_url: Optional[str] = None) -> Page:
        await self.stop()
        if proxy_url is not None:
            self.proxy_url = proxy_url
        return await self.start()

    # ── Сессия ───────────────────────────────────────────────────────────────

    async def _save_session(self) -> None:
        if self._context and not self._using_cdp:
            try:
                storage_state = self._get_storage_state_path()
                storage_state.parent.mkdir(parents=True, exist_ok=True)
                await self._context.storage_state(path=str(storage_state))
                logger.debug("Сессия сохранена в {}", storage_state)
            except Exception as e:
                logger.warning("Не удалось сохранить сессию: {}", str(e)[:100])

    async def clear_session(self) -> None:
        storage_state = self._get_storage_state_path()
        if storage_state.exists():
            storage_state.unlink()
        if self._context:
            await self._context.clear_cookies()
        logger.info("Сессия браузера очищена")

    def _get_storage_state_path(self) -> Path:
        return self.session_dir / "storage_state.json"

    # ── Утилиты ──────────────────────────────────────────────────────────────

    @property
    def page(self) -> Optional[Page]:
        return self._page

    async def new_page(self) -> Page:
        if not self._context:
            raise RuntimeError("Браузер не запущен")
        page = await self._context.new_page()
        page.set_default_timeout(self.timeout)
        return page

    async def screenshot(self, path: str = "screenshot.png") -> str:
        if self._page:
            await self._page.screenshot(path=path)
        return path

    async def update_proxy(self, proxy_url: Optional[str]) -> None:
        if self.proxy_url != proxy_url:
            logger.info("Смена прокси → {}", proxy_url)
            await self.restart(proxy_url=proxy_url)
