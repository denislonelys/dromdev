# ============================================================================
# IIStudio — FastAPI сервер
# ============================================================================

from __future__ import annotations

import time
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from api.routes import chat, status
from config import settings
from core.agent import IIStudioAgent
from utils.logger import logger, setup_logger

# Настройка логгера
setup_logger(level=settings.iistudio_log_level)

# Глобальный экземпляр агента (shared между воркерами)
_agent: IIStudioAgent = IIStudioAgent(settings)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Жизненный цикл FastAPI приложения."""
    logger.info("Запуск IIStudio API v{}", settings.iistudio_version)
    await _agent.start()
    app.state.agent = _agent
    yield
    logger.info("Остановка IIStudio API...")
    await _agent.stop()


def create_app() -> FastAPI:
    app = FastAPI(
        title="IIStudio API",
        description="AI Orchestrator for arena.ai — REST API",
        version=settings.iistudio_version,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # ── CORS ─────────────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if settings.is_development else ["https://arena.ai"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Middleware: логирование запросов ──────────────────────────────────────
    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        ms = (time.perf_counter() - start) * 1000
        logger.info(
            "{} {} → {} ({:.0f}мс)",
            request.method,
            request.url.path,
            response.status_code,
            ms,
        )
        return response

    # ── Роуты ────────────────────────────────────────────────────────────────
    app.include_router(chat.router, prefix="/api", tags=["chat"])
    app.include_router(status.router, prefix="/api", tags=["status"])

    # ── Веб-интерфейс ─────────────────────────────────────────────────────────
    import os
    from pathlib import Path
    templates_dir = Path(__file__).parent.parent / "web" / "templates"
    static_dir = Path(__file__).parent.parent / "web" / "static"

    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    if templates_dir.exists():
        templates = Jinja2Templates(directory=str(templates_dir))

        @app.get("/", include_in_schema=False)
        async def web_index(request: Request):
            agent: IIStudioAgent = request.app.state.agent
            status_data = await agent.get_status()
            return templates.TemplateResponse(
                "index.html",
                {"request": request, "status": status_data, "version": settings.iistudio_version},
            )

        @app.get("/models", include_in_schema=False)
        async def web_models(request: Request):
            from arena.models import ALL_MODELS, get_models_for_mode, MODES
            agent: IIStudioAgent = request.app.state.agent
            status_data = await agent.get_status()
            by_mode = {}
            for m in MODES:
                by_mode[m] = [
                    {"id": mo.id, "name": mo.name, "provider": mo.provider,
                     "context_k": mo.context_k, "description": mo.description,
                     "is_default": mo.is_default}
                    for mo in get_models_for_mode(m)
                ]
            return templates.TemplateResponse(
                "models.html",
                {
                    "request": request,
                    "status": status_data,
                    "version": settings.iistudio_version,
                    "by_mode": by_mode,
                    "total": len(ALL_MODELS),
                },
            )

        @app.get("/status", include_in_schema=False)
        async def web_status(request: Request):
            agent: IIStudioAgent = request.app.state.agent
            system = await agent.get_status()
            proxies = agent._proxy_manager.get_status()
            return templates.TemplateResponse(
                "status.html",
                {
                    "request": request,
                    "status": system,
                    "version": settings.iistudio_version,
                    "system": system,
                    "proxies": proxies,
                },
            )

    # ── Healthcheck ───────────────────────────────────────────────────────────
    @app.get("/health", tags=["system"])
    async def health():
        return {"status": "ok", "version": settings.iistudio_version}

    # ── Глобальный обработчик ошибок ─────────────────────────────────────────
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.error("Необработанная ошибка: {}", exc)
        return JSONResponse(
            status_code=500,
            content={"error": str(exc), "path": str(request.url.path)},
        )

    return app


app = create_app()


def run() -> None:
    import uvicorn
    uvicorn.run(
        "api.server:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.is_development,
        log_level=settings.iistudio_log_level.lower(),
        workers=1,  # 1 воркер т.к. браузер не thread-safe
    )
