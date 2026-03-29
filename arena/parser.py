# ============================================================================
# IIStudio — Парсер arena.ai (минимальный надёжный flow)
#
# Единственный рабочий метод:
# 1. Chrome запущен через Xvfb (реальный, не headless)
# 2. Заполняем textarea, нажимаем submit
# 3. Перехватываем streaming ответ через fetch interceptor
# 4. Парсим Next.js AI SDK формат: a0:"text"
# ============================================================================

from __future__ import annotations

import asyncio
import json
import re
import time
from typing import Any, AsyncGenerator, Dict, List, Optional

from playwright.async_api import Page, TimeoutError as PWTimeout

from arena import selectors as S
from arena.models import AIModel
from utils.logger import logger

DIRECT_URL = "https://arena.ai/text/direct"

FETCH_INTERCEPTOR = """() => {
    window.__iis_r = '';
    window.__iis_d = false;
    window.__iis_s = 0;
    const _F = window.__iis_orig_fetch || window.fetch;
    window.__iis_orig_fetch = _F;
    window.fetch = async function(...a) {
        const url = (a[0] && a[0].toString) ? a[0].toString() : String(a[0]);
        const resp = await _F.apply(this, a);
        if (url.includes('stream/create-evaluation')) {
            window.__iis_s = resp.status;
            const clone = resp.clone();
            (async () => {
                try {
                    const r = clone.body.getReader();
                    const d = new TextDecoder();
                    let t = '';
                    while (true) {
                        const { done, value } = await r.read();
                        if (done) break;
                        t += d.decode(value, { stream: true });
                        window.__iis_r = t;
                    }
                } catch (e) {}
                window.__iis_d = true;
            })();
        }
        return resp;
    };
}"""

REMOVE_OVERLAYS = """() => {
    document.querySelectorAll('[role=dialog],[aria-hidden=true],[data-aria-hidden=true]')
        .forEach(e => {
            if (e.getAttribute('role') === 'dialog' ||
                window.getComputedStyle(e).position === 'fixed')
                e.remove();
        });
}"""

CLICK_AGREE = """() => {
    const btn = Array.from(document.querySelectorAll('button'))
        .find(b => b.textContent.trim() === 'Agree');
    if (btn) { btn.click(); return true; }
    return false;
}"""


def parse_stream(raw: str) -> str:
    """Парсит Next.js AI SDK streaming.
    Формат: a0:"text" — текст ответа
             a2:[...] — метаданные (игнорируем)
             ad:{...} — конец стрима (игнорируем)
    """
    text = ""
    for line in raw.split("\n"):
        line = line.strip()
        if not line:
            continue
        # Только строки с текстом: a0:"..." или 0:"..."
        m = re.match(r'^[a-f0-9]*0:"(.*)"$', line)
        if m:
            try:
                text += json.loads('"' + m.group(1) + '"')
            except Exception:
                text += m.group(1)
    return text


def is_stream_done(raw: str) -> bool:
    """Проверить что стрим завершён (есть finishReason)."""
    return '"finishReason"' in raw or '"finish_reason"' in raw


def extract_model_from_stream(raw: str) -> str:
    """Извлечь провайдера модели из метаданных стрима."""
    m = re.search(r'"organization"\s*:\s*"([^"]+)"', raw)
    if m:
        org_map = {
            "anthropic": "Claude",
            "openai": "GPT",
            "google": "Gemini",
            "meta": "Llama",
            "deepseek": "DeepSeek",
            "mistral": "Mistral",
            "xai": "Grok",
        }
        return org_map.get(m.group(1).lower(), m.group(1).capitalize())
    return "AI"


def fill_textarea_js(text: str) -> str:
    escaped = text.replace("\\", "\\\\").replace("'", "\\'").replace("\n", "\\n")
    return f"""() => {{
        const ta = document.querySelector('textarea[name=message]');
        if (!ta) return false;
        const setter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value').set;
        setter.call(ta, '{escaped}');
        ta.dispatchEvent(new Event('input', {{ bubbles: true }}));
        ta.focus();
        return true;
    }}"""


def fill_input_js(selector: str, value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace("'", "\\'")
    return f"""() => {{
        const inp = document.querySelector('{selector}');
        if (!inp) return false;
        const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
        setter.call(inp, '{escaped}');
        inp.dispatchEvent(new Event('input', {{ bubbles: true }}));
        return true;
    }}"""


class ArenaParser:
    """Парсер arena.ai — минимальный надёжный flow."""

    def __init__(self, page: Page, base_url: str = "https://arena.ai") -> None:
        self.page = page
        self.base_url = base_url.rstrip("/")
        self._logged_in: bool = False
        self._tos_agreed: bool = False
        self._current_mode: Optional[str] = None
        self._current_model: Optional[str] = None

    # ── Инициализация ────────────────────────────────────────────────────────

    async def initialize(self, email: str = "", password: str = "") -> bool:
        """Инициализация: загрузка страницы, cookies, логин."""
        logger.info("Инициализация AI движка...")
        try:
            await self.page.goto(DIRECT_URL, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(5)

            body = await self.page.evaluate("() => document.body.innerText")
            if "security verification" in body.lower() or "just a moment" in body.lower():
                logger.warning("Инициализация соединения — ждём...")
                await asyncio.sleep(8)
                body = await self.page.evaluate("() => document.body.innerText")

            if "security verification" in body.lower():
                logger.error("Ошибка подключения. Попробуй перезапустить: systemctl restart iistudio")
                return False

            # Cookies
            await self.page.evaluate("""() => {
                const b = Array.from(document.querySelectorAll('button'))
                    .find(b => b.textContent.includes('Accept Cookies'));
                if (b) b.click();
            }""")
            await asyncio.sleep(1)

            # Уже залогинены?
            if "Login" not in body[:300]:
                logger.info("✅ AI система готова")
                self._logged_in = True
                await self.page.evaluate(CLICK_AGREE)
                await asyncio.sleep(2)
                await self.page.evaluate(REMOVE_OVERLAYS)
                return True

            # Логин
            if email and password:
                return await self.login(email, password)

            logger.warning("Заполни ARENA_EMAIL и ARENA_PASSWORD в .env")
            return False

        except Exception as e:
            logger.error("Ошибка инициализации: {}", e)
            return False

    async def ensure_logged_in(self, email: str, password: str) -> bool:
        if self._logged_in:
            return True
        return await self.login(email, password)

    async def login(self, email: str, password: str) -> bool:
        """Email/password логин через JS (обходим overlay)."""
        if not email or not password:
            return False
        logger.info("Авторизация как {}", email)
        try:
            await self.page.evaluate("""() => {
                const b = Array.from(document.querySelectorAll('button'))
                    .find(b => b.textContent.trim() === 'Login');
                if (b) b.click();
            }""")
            await asyncio.sleep(2)
            await self.page.evaluate(fill_input_js("input[type=email]", email))
            await asyncio.sleep(0.3)
            await self.page.evaluate("""() => {
                const b = Array.from(document.querySelectorAll('button'))
                    .find(b => b.textContent.trim() === 'Continue with email');
                if (b) b.click();
            }""")
            await asyncio.sleep(2.5)
            await self.page.evaluate(fill_input_js("input[type=password]", password))
            await asyncio.sleep(0.3)
            await self.page.evaluate("""() => {
                const pwd = document.querySelector('input[type=password]');
                if (!pwd) return;
                const form = pwd.closest('form');
                const btn = form && (form.querySelector('button[type=submit]') || form.querySelector('button'));
                if (btn) btn.click();
            }""")
            await asyncio.sleep(5)

            body = await self.page.evaluate("() => document.body.innerText")
            if "Login" not in body[:300]:
                logger.info("✅ AI готов к работе!")
                self._logged_in = True
                await self.page.evaluate(CLICK_AGREE)
                await asyncio.sleep(2)
                await self.page.evaluate(REMOVE_OVERLAYS)
                await asyncio.sleep(6)  # reCAPTCHA v3 init
                await self.page.evaluate(REMOVE_OVERLAYS)
                return True

            logger.error("Авторизация не удалась")
            return False
        except Exception as e:
            logger.error("Ошибка логина: {}", e)
            return False

    # ── Отправка и получение ─────────────────────────────────────────────────

    async def send_message(self, text: str) -> bool:
        """Заполнить textarea и нажать Submit. Минимум действий."""
        logger.debug("Отправка ({} символов)", len(text))
        try:
            # Если мы на /c/ID — возвращаемся через кнопку New Chat
            if "/text/direct" not in self.page.url:
                clicked = await self.page.evaluate("""() => {
                    const items = Array.from(document.querySelectorAll('a, button'));
                    const btn = items.find(el =>
                        el.textContent.trim() === 'New Chat' ||
                        el.getAttribute('href') === '/text/direct' ||
                        el.getAttribute('href') === '/'
                    );
                    if (btn) { btn.click(); return true; }
                    return false;
                }""")
                if not clicked:
                    await self.page.goto(DIRECT_URL, wait_until="domcontentloaded", timeout=20000)
                await asyncio.sleep(3)
                await self.page.evaluate(REMOVE_OVERLAYS)
                await asyncio.sleep(1)

            # Сбрасываем interceptor state
            await self.page.evaluate("""() => {
                window.__iis_r = '';
                window.__iis_d = false;
                window.__iis_s = 0;
            }""")
            # Устанавливаем interceptor
            await self.page.evaluate(FETCH_INTERCEPTOR)

            # Убираем оверлеи
            await self.page.evaluate(REMOVE_OVERLAYS)
            await asyncio.sleep(0.5)

            # Заполняем textarea
            ok = await self.page.evaluate(fill_textarea_js(text))
            if not ok:
                logger.error("textarea[name=message] не найдена")
                return False
            await asyncio.sleep(1.5)  # Важно: reCAPTCHA v3 нужно время

            # Нажимаем Submit
            await self.page.evaluate("""() => {
                const btn = document.querySelector('button[type=submit]');
                if (btn && !btn.disabled) btn.click();
            }""")
            await asyncio.sleep(2)

            # Обрабатываем ToS
            await self.page.evaluate(CLICK_AGREE)
            await asyncio.sleep(1)
            await self.page.evaluate(REMOVE_OVERLAYS)

            return True
        except Exception as e:
            logger.error("Ошибка отправки: {}", e)
            return False

    async def wait_for_response(self, timeout: int = 90) -> Optional[str]:
        """Ждать ответа через fetch interceptor.
        
        Оптимизация: не ждём done=True, читаем как только есть finishReason.
        Это убирает задержку от heartbeat пакетов.
        """
        logger.debug("Ожидание ответа...")
        start = time.time()

        while time.time() - start < timeout:
            await asyncio.sleep(0.5)  # Проверяем чаще — быстрее реагируем
            await self.page.evaluate(REMOVE_OVERLAYS)

            state = await self.page.evaluate("""() => ({
                done: window.__iis_d,
                status: window.__iis_s,
                len: (window.__iis_r || '').length,
                raw: window.__iis_r || ''
            })""")

            status = state.get("status", 0)
            raw = state.get("raw", "")
            length = state.get("len", 0)

            # Как только статус известен и ответ не 200
            if status == 429:
                logger.warning("Rate limit (429) — ждём 30с...")
                await asyncio.sleep(30)
                return None
            elif status == 403:
                logger.error("Ошибка соединения (403)")
                return None
            elif status not in (0, 200) and status > 0:
                logger.error("Ошибка status={}", status)
                return None

            # Читаем текст СРАЗУ как появляется — не ждём done
            if status == 200 and length > 0:
                text = parse_stream(raw)
                if text:
                    # Проверяем завершён ли стрим (finishReason) или done=True
                    if is_stream_done(raw) or state.get("done"):
                        model = extract_model_from_stream(raw)
                        logger.debug("✅ Ответ от {} ({} символов)", model, len(text))
                        return text
                    # Стрим ещё идёт — продолжаем накапливать
                    # Но если прошло достаточно времени и есть текст — возвращаем
                    elapsed = time.time() - start
                    if elapsed > 3 and state.get("done"):
                        return text

            # Fallback: если done=True но нет text (пустой parse)
            if state.get("done") and length > 0 and status == 200:
                return raw  # Возвращаем raw если parse пустой

        logger.warning("Timeout {}с", timeout)
        return None

    async def stream_response(self, timeout: int = 90) -> AsyncGenerator[str, None]:
        """Стриминг ответа по дельтам."""
        start = time.time()
        prev_text = ""

        while time.time() - start < timeout:
            await asyncio.sleep(0.5)

            state = await self.page.evaluate("""() => ({
                done: window.__iis_d,
                status: window.__iis_s,
                len: (window.__iis_r || '').length
            })""")

            if state.get("len", 0) > 0:
                raw = await self.page.evaluate("() => window.__iis_r || ''")
                current_text = parse_stream(raw)
                if len(current_text) > len(prev_text):
                    delta = current_text[len(prev_text):]
                    prev_text = current_text
                    if delta:
                        yield delta

            if state.get("done"):
                break

    # ── Stub методы (для совместимости) ──────────────────────────────────────

    async def switch_mode(self, mode_id: str) -> bool:
        """Переключение режима — не используем, arena.ai сам определяет."""
        self._current_mode = mode_id
        return True

    async def select_model(self, model: AIModel) -> bool:
        """Выбор модели — не используем, arena.ai использует дефолтную."""
        self._current_model = model.id
        return True

    async def take_screenshot(self, path: str = "screenshot.png") -> str:
        await self.page.screenshot(path=path)
        return path

    async def get_available_models(self) -> List[str]:
        return []
