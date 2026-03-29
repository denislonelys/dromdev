# ============================================================================
# IIStudio — Главный агент (KiroAI через OmniRoute)
#
# Движок: KiroAI (Claude Opus 4.6) через OmniRoute на localhost:20128
# Бесплатно, без API ключа Anthropic, скорость ~2с
# Endpoint: http://localhost:20128/v1 (OpenAI-совместимый)
# ============================================================================

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional

import httpx
from pathlib import Path as _Path

# Загружаем .env напрямую если переменные не в окружении
def _load_env():
    env_file = _Path(__file__).parent.parent / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, val = line.partition("=")
                if key.strip() not in os.environ:
                    os.environ[key.strip()] = val.strip()

_load_env()

from api.auth import get_db
from cache.cache import CacheManager
from config import Settings
from core.context import ProjectContext
from core.session import Session
from utils.helpers import make_cache_key
from utils.logger import logger

# OmniRoute конфиг
OMNI_URL     = os.environ.get("OMNI_URL", "http://localhost:20128/v1")
OMNI_API_KEY = os.environ.get("OMNI_API_KEY", "sk-fb8573e9682d98eb-s6c8zf-386b858c")
OMNI_MODEL   = os.environ.get("OMNI_MODEL", "kr/claude-sonnet-4.5")

MODELS = {
    "claude-opus-4-6":   {"name": "Claude Opus 4.6",   "provider": "Anthropic", "model_id": "kr/claude-sonnet-4.5"},  # маппинг на доступную модель
    "claude-sonnet-4-6": {"name": "Claude Sonnet 4.6", "provider": "Anthropic", "model_id": "kr/claude-sonnet-4.5"},
}
DEFAULT_MODEL = "claude-opus-4-6"  # По умолчанию Opus

from core.tools import AgentTools, SYSTEM_PROMPT_WITH_TOOLS

SYSTEM_PROMPT = SYSTEM_PROMPT_WITH_TOOLS


def _process_tool_calls(response: str, tools: "AgentTools") -> tuple[str, list[str]]:
    """Обрабатывает tool-вызовы в ответе агента и выполняет их."""
    import re as _re
    actions = []
    
    # write_file
    for m in _re.finditer(r'<tool:write_file path="([^"]+)">([\s\S]*?)</tool:write_file>', response):
        path, content = m.group(1), m.group(2).strip()
        result = tools.write_file(path, content)
        actions.append(f"  Записан файл: {path}" if result.success else f"  Ошибка записи {path}: {result.error}")
        response = response.replace(m.group(0), f"```\n# Записан файл: {path}\n```")
    
    # read_file
    for m in _re.finditer(r'<tool:read_file path="([^"]+)"\s*/>', response):
        path = m.group(1)
        result = tools.read_file(path)
        if result.success:
            actions.append(f"  Прочитан файл: {path}")
            response = response.replace(m.group(0), f"```\n{result.output[:2000]}\n```")
        else:
            response = response.replace(m.group(0), f"[Ошибка: {result.error}]")
    
    # bash
    for m in _re.finditer(r'<tool:bash cmd="([^"]+)"\s*/>', response):
        cmd = m.group(1)
        result = tools.bash(cmd)
        actions.append(f"  $ {cmd}")
        if result.output:
            actions.append(f"    {result.output[:200]}")
        response = response.replace(m.group(0), f"```bash\n$ {cmd}\n{result.output[:500]}\n```")
    
    # list_files
    for m in _re.finditer(r'<tool:list_files path="([^"]+)"\s*/>', response):
        path = m.group(1)
        result = tools.list_files(path)
        response = response.replace(m.group(0), f"```\n{result.output}\n```")
    
    # search
    for m in _re.finditer(r'<tool:search query="([^"]+)"\s*/>', response):
        query = m.group(1)
        result = tools.search_files(query)
        response = response.replace(m.group(0), f"```\n{result.output[:1000]}\n```")
    
    return response, actions


class IIStudioAgent:
    """Главный агент IIStudio — KiroAI через OmniRoute."""

    def __init__(self, settings: Settings, workdir: Optional[Path] = None) -> None:
        self.settings = settings
        self.session = Session(mode=settings.default_mode)
        self.context = ProjectContext(workdir or Path("."))
        self._cache = CacheManager(
            redis_url=settings.redis_url,
            default_ttl=settings.cache_ttl,
            max_memory_size=settings.cache_max_size,
        )
        self._current_model = DEFAULT_MODEL
        self._started = False
        self.tools = AgentTools(workdir or Path("."))

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def start(self) -> None:
        logger.info("IIStudio запускается...")
        await self._cache.start()
        # Проверяем OmniRoute
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(
                    f"{OMNI_URL.rstrip('/v1')}/v1/models",
                    headers={"Authorization": f"Bearer {OMNI_API_KEY}"},
                )
                if r.status_code == 200:
                    models = [m.get("id") for m in r.json().get("data", [])]
                    logger.info("✅ KiroAI готов. Модели: {}", models[:4])
                else:
                    logger.warning("OmniRoute ответил: {}", r.status_code)
        except Exception as e:
            logger.warning("OmniRoute недоступен: {}. Запусти: omniroute", e)
        self._started = True
        logger.info("✅ IIStudio готов")

        # Запускаем фоновый health check KiroAI
        asyncio.create_task(self._kiro_health_loop())

    async def stop(self) -> None:
        self.session.save()
        await self._cache.stop()
        self._started = False

    async def __aenter__(self): await self.start(); return self
    async def __aexit__(self, *_): await self.stop()

    # ── Главный метод ─────────────────────────────────────────────────────────

    async def chat(
        self,
        message: str,
        mode: Optional[str] = None,
        model_id: Optional[str] = None,
        use_cache: bool = True,
        stream: bool = False,
        user_token: Optional[str] = None,
        file_path: Optional[Path] = None,
    ) -> Dict[str, Any]:
        if not self._started:
            raise RuntimeError("Агент не запущен. Вызови await agent.start()")

        model_id = model_id or self._current_model
        mode = mode or self.session.mode
        model_info = MODELS.get(model_id, MODELS[DEFAULT_MODEL])
        api_model = model_info["model_id"]

        result: Dict[str, Any] = {
            "success": False, "response": None, "model": model_id,
            "mode": mode, "cached": False, "error": None,
            "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0,
        }

        # Billing check
        db = get_db()
        user = None
        if user_token:
            user = db.verify_token(user_token)
            if user and user.get("balance_usd", 0) <= 0 and user.get("free_tokens", 0) <= 0:
                result["error"] = "Баланс исчерпан. Пополни на https://orproject.online/pricing"
                return result

        # Кэш (отключаем для вопросов о версии/модели/себе)
        skip_cache = any(q in message.lower() for q in [
            "какая ты модель", "какая версия", "кто ты", "что ты", "какой ты", 
            "я помощник", "я claude", "версия", "модель", "kiro"
        ])
        
        if use_cache and not skip_cache:
            cache_key = make_cache_key("chat", model_id, message)
            cached = await self._cache.get(cache_key)
            if cached:
                self.session.add_user_message(message)
                self.session.add_assistant_message(cached["response"], model_id=model_id)
                return {**cached, "cached": True}

        self.session.mode = mode
        self.session.add_user_message(message)

        # Строим messages
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        for msg in self.session.messages[-20:]:
            if msg.role in ("user", "assistant"):
                messages.append({"role": msg.role, "content": msg.content})
        if not messages or messages[-1]["content"] != message:
            messages.append({"role": "user", "content": message})

        # Отправляем в KiroAI через OmniRoute
        try:
            async with httpx.AsyncClient(timeout=120) as client:
                resp = await client.post(
                    f"{OMNI_URL.rstrip('/').rstrip('/v1')}/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {OMNI_API_KEY}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model":      api_model,
                        "messages":   messages,
                        "max_tokens": 4096,
                        "stream":     True,  # OmniRoute возвращает SSE стриминг
                    },
                )

                if resp.status_code != 200:
                    result["error"] = f"API error {resp.status_code}: {resp.text[:200]}"
                    return result

                # Читаем SSE стриминг
                import json as _json
                text = ""
                input_tokens = 0
                output_tokens = 0
                for line in resp.text.split("\n"):
                    line = line.strip()
                    if not line or not line.startswith("data:"):
                        continue
                    data_str = line[5:].strip()
                    if data_str == "[DONE]":
                        break
                    try:
                        chunk = _json.loads(data_str)
                        delta = chunk.get("choices",[{}])[0].get("delta",{}).get("content","")
                        if delta:
                            text += delta
                        usage_chunk = chunk.get("usage", {})
                        if usage_chunk:
                            input_tokens = usage_chunk.get("prompt_tokens", input_tokens)
                            output_tokens = usage_chunk.get("completion_tokens", output_tokens)
                    except Exception:
                        pass
                data = {}
                usage = {"prompt_tokens": input_tokens or len(text)//4, "completion_tokens": output_tokens or len(text)//4}
                input_tokens  = usage.get("prompt_tokens", 0)
                output_tokens = usage.get("completion_tokens", 0)
                # KiroAI бесплатный — cost = 0
                cost = 0.0

                if text:
                    # Обрабатываем tool-вызовы (write_file, bash, etc.)
                    text, actions = _process_tool_calls(text, self.tools)
                    result.update({
                        "success":       True,
                        "response":      text,
                        "model":         model_id,
                        "model_name":    model_info["name"],
                        "input_tokens":  input_tokens,
                        "output_tokens": output_tokens,
                        "cost_usd":      cost,
                        "actions":       actions,  # Список выполненных действий
                    })

                    # Billing (бесплатные токены только считаем)
                    if user and user_token:
                        total = input_tokens + output_tokens
                        db.deduct_tokens(user["id"], total, model_id, 0.0)

                    # Кэш
                    if use_cache:
                        await self._cache.set(cache_key, result, ttl=self.settings.cache_ttl)

                    self.session.add_assistant_message(text, model_id=model_id)
                    logger.debug("✅ KiroAI ответ: {} токенов", input_tokens + output_tokens)
                else:
                    result["error"] = data.get("error", {}).get("message", "Пустой ответ")

        except httpx.TimeoutException:
            result["error"] = "Timeout. Проверь что OmniRoute запущен: omniroute"
        except Exception as e:
            logger.error("Ошибка KiroAI: {}", e)
            result["error"] = str(e)

        return result

    async def chat_stream(
        self,
        message: str,
        mode: Optional[str] = None,
        model_id: Optional[str] = None,
        user_token: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        """Стриминг через KiroAI."""
        model_id = model_id or self._current_model
        model_info = MODELS.get(model_id, MODELS[DEFAULT_MODEL])
        api_model = model_info["model_id"]

        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        for msg in self.session.messages[-20:]:
            if msg.role in ("user", "assistant"):
                messages.append({"role": msg.role, "content": msg.content})
        messages.append({"role": "user", "content": message})
        self.session.add_user_message(message)

        full_text = ""
        try:
            async with httpx.AsyncClient(timeout=120) as client:
                async with client.stream(
                    "POST",
                    f"{OMNI_URL.rstrip('/').rstrip('/v1')}/v1/chat/completions",
                    headers={"Authorization": f"Bearer {OMNI_API_KEY}", "Content-Type": "application/json"},
                    json={"model": api_model, "messages": messages, "max_tokens": 4096, "stream": True},
                ) as resp:
                    if resp.status_code != 200:
                        yield f"[ERROR] API {resp.status_code}"
                        return
                    import json
                    async for line in resp.aiter_lines():
                        if not line or not line.startswith("data:"):
                            continue
                        data = line[5:].strip()
                        if data == "[DONE]":
                            break
                        try:
                            obj = json.loads(data)
                            delta = obj.get("choices",[{}])[0].get("delta",{}).get("content","")
                            if delta:
                                full_text += delta
                                yield delta
                        except Exception:
                            pass
        except Exception as e:
            yield f"[ERROR] {e}"

        if full_text:
            self.session.add_assistant_message(full_text, model_id=model_id)

    # ── Управление ───────────────────────────────────────────────────────────

    def set_mode(self, mode: str) -> bool:
        if mode not in {"text","images","video","coding"}: return False
        self.session.mode = mode; return True

    def set_model(self, model_id: str) -> bool:
        if model_id in MODELS:
            self._current_model = model_id
            logger.info("Модель: {}", MODELS[model_id]["name"])
            return True
        return False

    async def compare(self, message: str, mode: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
        results = {}
        for mid, info in MODELS.items():
            r = await self.chat(message, model_id=mid)
            results[mid] = {"model_name": info["name"], "provider": info["provider"], **r}
            await asyncio.sleep(0.5)
        return results

    async def get_status(self) -> Dict[str, Any]:
        cache_info = await self._cache.info()
        return {
            "version":         self.settings.iistudio_version,
            "env":             self.settings.iistudio_env,
            "mode":            self.session.mode,
            "model":           self._current_model,
            "model_name":      MODELS.get(self._current_model, {}).get("name", self._current_model),
            "session_id":      self.session.session_id,
            "messages":        self.session.message_count,
            "api_ready":       True,
            "browser_running": False,
            "proxy":           {"current": None},
            "cache":           cache_info,
        }

    async def _kiro_health_loop(self) -> None:
        """Фоновый health check + авто-переподключение KiroAI."""
        await asyncio.sleep(60)  # Первая проверка через 60с
        fail = 0
        while self._started:
            try:
                async with httpx.AsyncClient(timeout=20) as client:
                    r = await client.post(
                        f"http://localhost:20128/v1/chat/completions",
                        headers={"Authorization": f"Bearer {OMNI_API_KEY}", "Content-Type": "application/json"},
                        json={"model": OMNI_MODEL, "messages": [{"role": "user", "content": "ping"}], "max_tokens": 3},
                    )
                    if r.status_code == 200:
                        fail = 0
                    else:
                        fail += 1
                        logger.warning("KiroAI check fail {}/3: status={}", fail, r.status_code)
            except Exception as e:
                fail += 1
                logger.warning("KiroAI check fail {}/3: {}", fail, e)

            if fail >= 3:
                logger.warning("KiroAI недоступен — пробуем переподключить...")
                try:
                    from core.kiro_reconnect import reconnect_kiro
                    ok = await reconnect_kiro()
                    logger.info("Переподключение KiroAI: {}", "✅ OK" if ok else "❌ Failed")
                except Exception as e:
                    logger.error("Ошибка переподключения: {}", e)
                fail = 0

            await asyncio.sleep(120)  # Проверяем каждые 2 минуты

    def get_history(self) -> List[Dict[str, Any]]: return self.session.history
    def clear_history(self) -> None: self.session.clear()
    async def get_proxy_status(self) -> List: return []
    async def switch_proxy(self) -> None: return None
    async def screenshot(self, path: str = "screenshot.png") -> str: return path
