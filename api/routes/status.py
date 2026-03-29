# ============================================================================
# IIStudio — API роуты: /api/status, /api/proxy, /api/models
# ============================================================================

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request

from arena.models import ALL_MODELS, MODES, get_models_for_mode
from core.agent import IIStudioAgent
from utils.logger import logger

router = APIRouter()


def get_agent(request: Request) -> IIStudioAgent:
    agent = getattr(request.app.state, "agent", None)
    if agent is None:
        raise HTTPException(status_code=503, detail="Агент не инициализирован")
    return agent


# ── Статус ────────────────────────────────────────────────────────────────────

@router.get("/status", summary="Статус системы")
async def get_status(agent: IIStudioAgent = Depends(get_agent)) -> Dict[str, Any]:
    """Полный статус: прокси, кэш, режим, модель, сессия."""
    return await agent.get_status()


@router.get("/proxy", summary="Статус прокси")
async def get_proxy_status(agent: IIStudioAgent = Depends(get_agent)) -> Dict[str, Any]:
    """Список всех прокси и их статус."""
    proxies = await agent.get_proxy_status()
    alive = sum(1 for p in proxies if p.get("alive"))
    return {
        "total": len(proxies),
        "alive": alive,
        "dead": len(proxies) - alive,
        "proxies": proxies,
    }


@router.post("/proxy/switch", summary="Переключить прокси")
async def switch_proxy(agent: IIStudioAgent = Depends(get_agent)) -> Dict[str, Any]:
    """Принудительно переключить на следующий прокси."""
    proxy = await agent.switch_proxy()
    if proxy:
        return {
            "status": "switched",
            "proxy": f"{proxy['host']}:{proxy['port']}",
            "type": proxy.get("type"),
        }
    return {"status": "no_alive_proxies"}


# ── Модели ────────────────────────────────────────────────────────────────────

@router.get("/models", summary="Все доступные модели")
async def get_models(mode: Optional[str] = None) -> Dict[str, Any]:
    """Список всех AI моделей (опционально фильтр по режиму)."""
    if mode:
        models = get_models_for_mode(mode)
        return {
            "mode": mode,
            "total": len(models),
            "models": [
                {
                    "id": m.id,
                    "name": m.name,
                    "provider": m.provider,
                    "context_k": m.context_k,
                    "description": m.description,
                    "is_default": m.is_default,
                }
                for m in models
            ],
        }

    result = {}
    for m_mode in MODES:
        models = get_models_for_mode(m_mode)
        result[m_mode] = [
            {
                "id": m.id,
                "name": m.name,
                "provider": m.provider,
                "context_k": m.context_k,
                "description": m.description,
                "is_default": m.is_default,
            }
            for m in models
        ]
    return {
        "total": len(ALL_MODELS),
        "modes": list(MODES),
        "by_mode": result,
    }


# ── Скриншот ──────────────────────────────────────────────────────────────────

@router.post("/screenshot", summary="Скриншот браузера")
async def take_screenshot(
    path: str = "screenshot.png",
    agent: IIStudioAgent = Depends(get_agent),
) -> Dict[str, str]:
    """Сохранить скриншот текущего состояния браузера."""
    try:
        saved_path = await agent.screenshot(path)
        return {"status": "ok", "path": saved_path}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
