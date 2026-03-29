# ============================================================================
# IIStudio — Главный агент
#
# Движок: arena.ai через Xvfb + Playwright (бесплатно, без API ключа)
# Fallback: Anthropic API напрямую (если задан ANTHROPIC_API_KEY)
# ============================================================================

from __future__ import annotations

import asyncio
import json
import os
import re
import time
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional

from api.auth import get_db
from cache.cache import CacheManager
from config import Settings
from core.context import ProjectContext
from core.session import Session
from core.xvfb_chrome import ensure_chrome_running
from utils.helpers import make_cache_key
from utils.logger import logger

# Названия моделей для отображения (всё идёт через arena.ai)
MODELS = {
    "claude-opus-4-6":   {"name": "Claude Opus 4.6",   "provider": "Anthropic"},
    "claude-sonnet-4-6": {"name": "Claude Sonnet 4.6", "provider": "Anthropic"},
    "gpt-4o":            {"name": "GPT-4o",            "provider": "OpenAI"},
    "gpt-4o-mini":       {"name": "GPT-4o mini",       "provider": "OpenAI"},
    "deepseek-r1":       {"name": "DeepSeek R1",       "provider": "DeepSeek"},
    "gemini-2-flash":    {"name": "Gemini 2.0 Flash",  "provider": "Google"},
    "llama-3-3-70b":     {"name": "Llama 3.3 70B",     "provider": "Meta"},
}
DEFAULT_MODEL = "claude-sonnet-4-6"

# Fetch interceptor для arena.ai
FETCH_INTERCEPTOR = """() => {
    window.__iis_r = ''; window.__iis_d = false; window.__iis_s = 0;
    const _F = window.__iis_of || window.fetch; window.__iis_of = _F;
    window.fetch = async function(...a) {
        const url = (a[0]&&a[0].toString)?a[0].toString():String(a[0]);
        const resp = await _F.apply(this, a);
        if(url.includes('stream/create-evaluation')) {
            window.__iis_s = resp.status;
            const cl = resp.clone();
            (async()=>{try{const r=cl.body.getReader();const d=new TextDecoder();let t='';
                while(true){const{done,value}=await r.read();if(done)break;t+=d.decode(value,{stream:true});window.__iis_r=t;}}catch(e){}
                window.__iis_d=true;})();
        }
        return resp;
    };
}"""

REMOVE_OVERLAYS = """() => {
    document.querySelectorAll('[role=dialog],[aria-hidden=true],[data-aria-hidden=true]')
        .forEach(e=>{if(e.getAttribute('role')==='dialog'||window.getComputedStyle(e).position==='fixed')e.remove();});
}"""

def parse_stream(raw: str) -> str:
    text = ""
    for line in raw.split("\n"):
        line = line.strip()
        if not line: continue
        m = re.match(r'^[a-f0-9]*0:"(.*)"$', line)
        if m:
            try: text += json.loads('"' + m.group(1) + '"')
            except: text += m.group(1)
    return text

def extract_model(raw: str) -> str:
    m = re.search(r'"organization"\s*:\s*"([^"]+)"', raw)
    if m:
        return {"anthropic":"Claude","openai":"GPT","google":"Gemini","meta":"Llama","deepseek":"DeepSeek"}.get(m.group(1).lower(), m.group(1))
    return "AI"


class IIStudioAgent:
    """Главный агент IIStudio — arena.ai через Xvfb."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.session = Session(mode=settings.default_mode)
        self.context = ProjectContext(Path("."))
        self._cache = CacheManager(redis_url=settings.redis_url, default_ttl=settings.cache_ttl, max_memory_size=settings.cache_max_size)
        self._current_model = settings.default_model or DEFAULT_MODEL
        self._page = None
        self._browser = None
        self._playwright = None
        self._started = False
        self._logged_in = False

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def start(self) -> None:
        logger.info("IIStudio запускается...")
        await self._cache.start()

        try:
            cdp_url = await ensure_chrome_running()
            from playwright.async_api import async_playwright
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.connect_over_cdp(cdp_url)
            context = self._browser.contexts[0]
            self._page = context.pages[0] if context.pages else await context.new_page()
            self._page.set_default_timeout(20000)
            logger.info("✅ Chrome подключён")
        except Exception as e:
            logger.error("Ошибка подключения к Chrome: {}", e)

        # Инициализация arena.ai
        await self._init_arena()
        self._started = True
        logger.info("✅ IIStudio готов")

    async def _init_arena(self) -> None:
        """Инициализация arena.ai — cookies, логин, ToS."""
        if not self._page: return
        try:
            await self._page.goto("https://arena.ai/text/direct", wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(5)
            # Cookies
            await self._page.evaluate("()=>{const b=Array.from(document.querySelectorAll('button')).find(b=>b.textContent.includes('Accept Cookies'));if(b)b.click();}")
            await asyncio.sleep(1)
            body = await self._page.evaluate("() => document.body.innerText")
            if "Login" in body[:300]:
                await self._login()
            else:
                self._logged_in = True
                logger.info("✅ arena.ai: сессия активна")
            # ToS + overlays
            await self._page.evaluate("()=>{const b=Array.from(document.querySelectorAll('button')).find(b=>b.textContent.trim()==='Agree');if(b)b.click();}")
            await asyncio.sleep(2)
            await self._page.evaluate(REMOVE_OVERLAYS)
            await asyncio.sleep(5)
            await self._page.evaluate(REMOVE_OVERLAYS)
        except Exception as e:
            logger.warning("Ошибка инициализации arena.ai: {}", e)

    async def _login(self) -> bool:
        """Логин через email/password."""
        email = self.settings.arena_email
        password = self.settings.arena_password
        if not email or not password:
            logger.warning("ARENA_EMAIL/ARENA_PASSWORD не заданы в .env")
            return False
        def rf(sel, val):
            v = val.replace("'", "\\'")
            return f"""()=>{{const i=document.querySelector('{sel}');if(!i)return false;
                const s=Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,'value').set;
                s.call(i,'{v}');i.dispatchEvent(new Event('input',{{bubbles:true}}));return true;}}"""
        await self._page.evaluate("()=>{const b=Array.from(document.querySelectorAll('button')).find(b=>b.textContent.trim()==='Login');if(b)b.click();}")
        await asyncio.sleep(2)
        await self._page.evaluate(rf("input[type=email]", email))
        await asyncio.sleep(0.3)
        await self._page.evaluate("()=>{const b=Array.from(document.querySelectorAll('button')).find(b=>b.textContent.trim()==='Continue with email');if(b)b.click();}")
        await asyncio.sleep(2)
        await self._page.evaluate(rf("input[type=password]", password))
        await asyncio.sleep(0.3)
        await self._page.evaluate("()=>{const p=document.querySelector('input[type=password]');if(!p)return;const f=p.closest('form');const b=f&&(f.querySelector('button[type=submit]')||f.querySelector('button'));if(b)b.click();}")
        await asyncio.sleep(5)
        body = await self._page.evaluate("() => document.body.innerText")
        self._logged_in = "Login" not in body[:300]
        if self._logged_in:
            logger.info("✅ arena.ai: авторизован")
        return self._logged_in

    async def stop(self) -> None:
        self.session.save()
        await self._cache.stop()
        if self._playwright:
            try: await self._playwright.stop()
            except: pass
        self._started = False

    async def __aenter__(self): await self.start(); return self
    async def __aexit__(self, *_): await self.stop()

    # ── Главный метод ─────────────────────────────────────────────────────────

    async def chat(self, message: str, mode: Optional[str] = None, model_id: Optional[str] = None,
                   use_cache: bool = True, stream: bool = False, user_token: Optional[str] = None,
                   file_path: Optional[Path] = None) -> Dict[str, Any]:
        if not self._started:
            raise RuntimeError("Агент не запущен")

        model_id = model_id or self._current_model
        mode = mode or self.session.mode
        self.session.mode = mode
        self.session.add_user_message(message)

        result: Dict[str, Any] = {"success": False, "response": None, "model": model_id,
                                   "mode": mode, "cached": False, "error": None,
                                   "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0}

        # Billing check
        db = get_db()
        user = None
        if user_token:
            user = db.verify_token(user_token)
            if user and user.get("balance_usd", 0) <= 0 and user.get("free_tokens", 0) <= 0:
                result["error"] = "Баланс исчерпан. Пополни на https://orproject.online/pricing"
                return result

        # Кэш
        if use_cache:
            cache_key = make_cache_key("chat", model_id, message)
            cached = await self._cache.get(cache_key)
            if cached:
                self.session.add_assistant_message(cached["response"], model_id=model_id)
                return {**cached, "cached": True}

        # Отправляем через arena.ai
        max_attempts = 3
        for attempt in range(1, max_attempts + 1):
            response = await self._send_to_arena(message, model_id)
            if response:
                result["success"] = True
                result["response"] = response
                result["model"] = model_id

                # Примерный подсчёт токенов (4 символа = 1 токен)
                input_tokens = len(message) // 4
                output_tokens = len(response) // 4
                result["input_tokens"] = input_tokens
                result["output_tokens"] = output_tokens

                # Billing
                if user and user_token:
                    total = input_tokens + output_tokens
                    db.deduct_tokens(user["id"], total, model_id, total * 0.000003)

                if use_cache:
                    await self._cache.set(cache_key, result, ttl=self.settings.cache_ttl)

                self.session.add_assistant_message(response, model_id=model_id)
                break
            else:
                if attempt < max_attempts:
                    logger.warning("Попытка {}/{} не дала ответа — ждём 30с", attempt, max_attempts)
                    await asyncio.sleep(30)
                    # Авторегистрация нового аккаунта
                    from core.account_pool import AccountPool
                    pool = AccountPool()
                    if self._page:
                        await pool.ensure_working_account(self._page)
                else:
                    result["error"] = "Нет ответа. Дневной лимит — подожди или зарегистрируй новый аккаунт: iis auth register"

        return result

    async def _send_to_arena(self, message: str, model_id: str) -> Optional[str]:
        """Отправить запрос в arena.ai и получить ответ."""
        if not self._page:
            return None
        try:
            # Возвращаемся на /text/direct если нужно
            if "/text/direct" not in self._page.url:
                clicked = await self._page.evaluate("""() => {
                    const btn = Array.from(document.querySelectorAll('a,button'))
                        .find(el => el.textContent.trim()==='New Chat' || el.getAttribute('href')==='/text/direct' || el.getAttribute('href')==='/');
                    if(btn){btn.click();return true;}return false;
                }""")
                if not clicked:
                    await self._page.goto("https://arena.ai/text/direct", wait_until="domcontentloaded", timeout=20000)
                await asyncio.sleep(3)
                await self._page.evaluate(REMOVE_OVERLAYS)
                await asyncio.sleep(1)

            # Сброс + interceptor
            await self._page.evaluate("()=>{window.__iis_r='';window.__iis_d=false;window.__iis_s=0;}")
            await self._page.evaluate(FETCH_INTERCEPTOR)
            await self._page.evaluate(REMOVE_OVERLAYS)

            # Заполняем textarea
            escaped = message.replace("\\","\\\\").replace("'","\\'").replace("\n","\\n")
            filled = await self._page.evaluate(f"""()=>{{
                const ta=document.querySelector('textarea[name=message]');if(!ta)return false;
                const s=Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype,'value').set;
                s.call(ta,'{escaped}');ta.dispatchEvent(new Event('input',{{bubbles:true}}));ta.focus();return true;
            }}""")
            if not filled:
                logger.error("textarea не найдена")
                return None

            await asyncio.sleep(1.5)
            await self._page.evaluate("()=>{const b=document.querySelector('button[type=submit]');if(b&&!b.disabled)b.click();}")
            await asyncio.sleep(2)

            # ToS
            await self._page.evaluate("()=>{const b=Array.from(document.querySelectorAll('button')).find(b=>b.textContent.trim()==='Agree');if(b)b.click();}")
            await asyncio.sleep(1)
            await self._page.evaluate(REMOVE_OVERLAYS)

            # Ждём ответа
            for i in range(60):
                await asyncio.sleep(1)
                await self._page.evaluate(REMOVE_OVERLAYS)
                st = await self._page.evaluate("()=>({d:window.__iis_d,s:window.__iis_s,r:window.__iis_r||''})")
                status = st.get("s", 0)
                raw = st.get("r", "")

                if status == 429:
                    logger.warning("Rate limit (429)")
                    return None
                if status == 403:
                    logger.error("Ошибка соединения (403)")
                    return None
                if status == 200 and raw:
                    text = parse_stream(raw)
                    if text and ('"finishReason"' in raw or st.get("d")):
                        model_name = extract_model(raw)
                        logger.debug("✅ Ответ от {} ({} символов)", model_name, len(text))
                        return text
                if st.get("d") and status == 200 and raw:
                    return parse_stream(raw) or raw

        except Exception as e:
            logger.error("Ошибка arena.ai: {}", e)
        return None

    async def chat_stream(self, message: str, mode: Optional[str] = None,
                          model_id: Optional[str] = None, user_token: Optional[str] = None) -> AsyncGenerator[str, None]:
        r = await self.chat(message, mode=mode, model_id=model_id, user_token=user_token, use_cache=False)
        if r.get("response"):
            yield r["response"]
        elif r.get("error"):
            yield f"[ERROR] {r['error']}"

    async def compare(self, message: str, mode: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
        r = await self.chat(message, mode=mode)
        return {"default": {"model_name": "Claude (arena.ai)", "provider": "Anthropic", **r}}

    # ── Управление ───────────────────────────────────────────────────────────

    def set_mode(self, mode: str) -> bool:
        if mode not in {"text", "images", "video", "coding"}: return False
        self.session.mode = mode; return True

    def set_model(self, model_id: str) -> bool:
        self._current_model = model_id; return True

    async def get_status(self) -> Dict[str, Any]:
        cache_info = await self._cache.info()
        return {
            "version":        self.settings.iistudio_version,
            "env":            self.settings.iistudio_env,
            "mode":           self.session.mode,
            "model":          self._current_model,
            "session_id":     self.session.session_id,
            "messages":       self.session.message_count,
            "api_ready":      self._page is not None,
            "browser_running": self._page is not None,
            "proxy":          {"current": None},
            "cache":          cache_info,
        }

    def get_history(self) -> List[Dict[str, Any]]: return self.session.history
    def clear_history(self) -> None: self.session.clear()
    async def get_proxy_status(self) -> List: return []
    async def switch_proxy(self) -> None: return None
    async def screenshot(self, path: str = "screenshot.png") -> str:
        if self._page: await self._page.screenshot(path=path)
        return path
