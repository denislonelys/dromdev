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
        allow_origins=["*"],  # Открыто для веб-интерфейса
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

    # Аутентификация + токены + баланс + цены
    from api.routes.auth_routes import router as auth_router, tokens_router, balance_router, user_router
    from api.routes.pricing import router as pricing_router
    app.include_router(auth_router, prefix="/api")
    app.include_router(tokens_router, prefix="/api")
    app.include_router(balance_router, prefix="/api")
    app.include_router(user_router, prefix="/api")
    app.include_router(pricing_router, prefix="/api")

    # ── Веб-интерфейс ─────────────────────────────────────────────────────────
    import os
    from pathlib import Path
    templates_dir = Path(__file__).parent.parent / "web" / "templates"
    static_dir = Path(__file__).parent.parent / "web" / "static"

    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    if templates_dir.exists():
        templates = Jinja2Templates(directory=str(templates_dir))

        def _safe_status(agent) -> dict:
            """Безопасно получить статус, сериализовать в простые типы."""
            import json as _j
            try:
                import asyncio
                loop = asyncio.get_event_loop()
                raw = loop.run_until_complete(agent.get_status()) if not asyncio.iscoroutinefunction(agent.get_status) else None
            except Exception:
                raw = None
            if raw is None:
                return {"mode": "text", "browser_running": False, "proxy": {}, "cache": {}}
            return _j.loads(_j.dumps(raw, default=str))

        @app.get("/", include_in_schema=False)
        async def web_index(request: Request):
            import json as _json
            from fastapi.responses import HTMLResponse
            status_data = {"mode": "text", "browser_running": False, "proxy": {}, "cache": {}, "version": settings.iistudio_version}
            try:
                agent = request.app.state.agent
                raw_status = await agent.get_status()
                status_data = _json.loads(_json.dumps(raw_status, default=str))
            except Exception:
                pass
            try:
                return templates.TemplateResponse(
                    "index.html",
                    {
                        "request": request,
                        "status": status_data,
                        "version": settings.iistudio_version,
                        "mode": str(status_data.get("mode", "text")),
                        "browser_running": bool(status_data.get("browser_running", False)),
                    },
                )
            except Exception as e:
                logger.error("Template render error: {}", e)
                return HTMLResponse(f"""<!DOCTYPE html><html><head><title>IIStudio</title>
<meta charset=utf-8><style>body{{background:#0d0d14;color:#e2e8f0;font-family:Inter,sans-serif;display:flex;flex-direction:column;align-items:center;justify-content:center;height:100vh;gap:1rem}}.logo{{font-size:3rem;color:#6c63ff}}.version{{color:#64748b;font-size:.9rem}}</style></head>
<body><div class=logo>◈</div><h1>IIStudio v{settings.iistudio_version}</h1>
<p>AI Orchestrator — arena.ai</p>
<div class=version>API: <a href=/docs style=color:#6c63ff>/docs</a> | Файлы: <a href=/files/ style=color:#6c63ff>/files/</a></div>
</body></html>""", status_code=200)

        @app.get("/models", include_in_schema=False)
        async def web_models(request: Request):
            from arena.models import ALL_MODELS, get_models_for_mode, MODES
            agent: IIStudioAgent = request.app.state.agent
            try:
                status_data = await agent.get_status()
            except Exception:
                status_data = {"mode": "text", "browser_running": False}
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
                    "mode": status_data.get("mode", "text"),
                    "browser_running": status_data.get("browser_running", False),
                    "by_mode": by_mode,
                    "total": len(ALL_MODELS),
                },
            )

        def _tmpl(name: str, ctx: dict, request: Request):
            """Безопасный рендер шаблона через Jinja2 напрямую."""
            from jinja2 import Environment, FileSystemLoader
            from fastapi.responses import HTMLResponse
            env = Environment(loader=FileSystemLoader(str(templates_dir)))
            tmpl = env.get_template(name)
            html = tmpl.render(request=request, **ctx)
            return HTMLResponse(html)

        @app.get("/login", include_in_schema=False)
        async def web_login(request: Request):
            return _tmpl("login.html", {
                "version": settings.iistudio_version,
                "mode": "text", "browser_running": False, "status": {},
            }, request)

        @app.get("/dashboard", include_in_schema=False)
        async def web_dashboard(request: Request):
            return _tmpl("dashboard.html", {
                "version": settings.iistudio_version,
                "mode": "text", "browser_running": False, "status": {},
                "user": {"username": "User", "email": "", "plan": "free",
                         "balance_usd": 0.0, "free_tokens": 0, "total_spent": 0.0, "requests_count": 0},
            }, request)

        @app.get("/install", include_in_schema=False)
        async def web_install(request: Request):
            return _tmpl("install.html", {
                "version": settings.iistudio_version,
                "mode": "text", "browser_running": False, "status": {},
            }, request)

        @app.get("/pricing", include_in_schema=False)
        async def web_pricing(request: Request):
            from api.routes.pricing import PRICING, PLANS
            by_mode: dict = {"text": [], "images": [], "video": []}
            for p in PRICING:
                m = p["mode"]
                if m in by_mode:
                    by_mode[m].append({
                        "name": p["name"], "provider": p["provider"],
                        "input_per_1m_usd": p["input"], "output_per_1m_usd": p["output"],
                        "is_free": p["free"], "context_k": p.get("context_k", 0),
                    })
            return _tmpl("pricing.html", {
                "version": settings.iistudio_version,
                "mode": "text", "browser_running": False, "status": {},
                "plans": PLANS, "pricing": by_mode,
            }, request)

        @app.get("/status", include_in_schema=False)
        async def web_status(request: Request):
            agent: IIStudioAgent = request.app.state.agent
            try:
                system = await agent.get_status()
                proxies = agent._proxy_manager.get_status()
            except Exception:
                system = {"mode": "text", "browser_running": False}
                proxies = []
            return templates.TemplateResponse(
                "status.html",
                {
                    "request": request,
                    "status": system,
                    "version": settings.iistudio_version,
                    "mode": system.get("mode", "text"),
                    "browser_running": system.get("browser_running", False),
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
