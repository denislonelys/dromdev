# ============================================================================
# IIStudio — API роуты: /api/chat
# ============================================================================

from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from core.agent import IIStudioAgent
from utils.logger import logger

router = APIRouter()


# ── Модели запросов/ответов ───────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=50000, description="Текст запроса")
    mode: str = Field("text", description="Режим: text/images/video/coding")
    model_id: Optional[str] = Field(None, description="ID модели (None = по умолчанию)")
    use_cache: bool = Field(True, description="Использовать кэш")
    stream: bool = Field(False, description="Стриминг ответа")

    class Config:
        json_schema_extra = {
            "example": {
                "message": "Объясни разницу между TCP и UDP",
                "mode": "text",
                "model_id": "gpt-4o",
                "use_cache": True,
                "stream": False,
            }
        }


class ChatResponse(BaseModel):
    success: bool
    response: Optional[str]
    model: Optional[str]
    mode: str
    cached: bool = False
    latency_ms: Optional[float]
    error: Optional[str]


class CompareRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=10000)
    mode: str = Field("text")


class HistoryResponse(BaseModel):
    messages: List[Dict[str, Any]]
    session_id: str
    total: int


# ── Dependency ────────────────────────────────────────────────────────────────

def get_agent(request: Request) -> IIStudioAgent:
    agent = getattr(request.app.state, "agent", None)
    if agent is None:
        raise HTTPException(status_code=503, detail="Агент не инициализирован")
    return agent


# ── Эндпоинты ─────────────────────────────────────────────────────────────────

@router.post("/chat", response_model=ChatResponse, summary="Отправить сообщение AI")
async def chat(
    body: ChatRequest,
    agent: IIStudioAgent = Depends(get_agent),
) -> ChatResponse:
    """Отправить запрос на arena.ai и получить ответ."""
    if body.stream:
        raise HTTPException(
            status_code=400,
            detail="Для стриминга используй GET /api/chat/stream",
        )

    result = await agent.chat(
        message=body.message,
        mode=body.mode,
        model_id=body.model_id,
        use_cache=body.use_cache,
    )
    return ChatResponse(**result)


@router.get("/chat/stream", summary="Стриминг ответа AI (SSE)")
async def chat_stream(
    message: str,
    mode: str = "text",
    model_id: Optional[str] = None,
    request: Request = None,
    agent: IIStudioAgent = Depends(get_agent),
) -> StreamingResponse:
    """Server-Sent Events стриминг ответа."""

    async def event_generator():
        try:
            async for delta in agent.chat_stream(
                message=message, mode=mode, model_id=model_id
            ):
                # SSE формат
                escaped = delta.replace("\n", "\\n")
                yield f"data: {escaped}\n\n"
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error("Ошибка стриминга: {}", e)
            yield f"data: [ERROR] {e}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@router.post("/chat/compare", summary="Сравнить ответы всех моделей")
async def compare(
    body: CompareRequest,
    agent: IIStudioAgent = Depends(get_agent),
) -> Dict[str, Any]:
    """Отправить один запрос во все доступные модели и вернуть все ответы."""
    results = await agent.compare(message=body.message, mode=body.mode)
    return {"mode": body.mode, "results": results, "total": len(results)}


@router.get("/chat/history", response_model=HistoryResponse, summary="История диалога")
async def get_history(agent: IIStudioAgent = Depends(get_agent)) -> HistoryResponse:
    history = agent.get_history()
    return HistoryResponse(
        messages=history,
        session_id=agent.session.session_id,
        total=len(history),
    )


@router.delete("/chat/history", summary="Очистить историю")
async def clear_history(agent: IIStudioAgent = Depends(get_agent)) -> Dict[str, str]:
    agent.clear_history()
    return {"status": "cleared"}


@router.post("/chat/mode", summary="Переключить режим")
async def set_mode(
    mode: str,
    agent: IIStudioAgent = Depends(get_agent),
) -> Dict[str, Any]:
    if not agent.set_mode(mode):
        raise HTTPException(status_code=400, detail=f"Неизвестный режим: {mode}")
    return {"mode": mode, "status": "ok"}


@router.post("/chat/model", summary="Переключить модель")
async def set_model(
    model_id: str,
    agent: IIStudioAgent = Depends(get_agent),
) -> Dict[str, Any]:
    if not agent.set_model(model_id):
        raise HTTPException(status_code=404, detail=f"Модель не найдена: {model_id}")
    return {"model_id": model_id, "status": "ok"}
