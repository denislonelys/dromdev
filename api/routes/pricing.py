# ============================================================================
# IIStudio — Цены на модели
# ============================================================================

from __future__ import annotations
from typing import Dict, List
from fastapi import APIRouter

router = APIRouter(prefix="/pricing", tags=["pricing"])

# Цены в USD за 1M токенов (input/output)
PRICING = [
    # Бесплатно (через бесплатные токены)
    {"model_id": "llama-3-3-70b",     "name": "Llama 3.3 70B",         "provider": "Meta",       "mode": "text",   "input": 0.00,   "output": 0.00,   "free": True,  "context_k": 128},
    {"model_id": "deepseek-v3",       "name": "DeepSeek V3",           "provider": "DeepSeek",   "mode": "text",   "input": 0.14,   "output": 0.28,   "free": False, "context_k": 64},
    {"model_id": "deepseek-r1",       "name": "DeepSeek R1",           "provider": "DeepSeek",   "mode": "text",   "input": 0.55,   "output": 2.19,   "free": False, "context_k": 64},
    # Дешёвые
    {"model_id": "gpt-4o-mini",       "name": "GPT-4o mini",           "provider": "OpenAI",     "mode": "text",   "input": 0.15,   "output": 0.60,   "free": False, "context_k": 128},
    {"model_id": "claude-3-5-haiku",  "name": "Claude 3.5 Haiku",      "provider": "Anthropic",  "mode": "text",   "input": 0.80,   "output": 4.00,   "free": False, "context_k": 200},
    {"model_id": "gemini-2-flash",    "name": "Gemini 2.0 Flash",      "provider": "Google",     "mode": "text",   "input": 0.10,   "output": 0.40,   "free": False, "context_k": 1000},
    # Средние
    {"model_id": "gpt-4o",            "name": "GPT-4o",                "provider": "OpenAI",     "mode": "text",   "input": 2.50,   "output": 10.00,  "free": False, "context_k": 128},
    {"model_id": "claude-3-5-sonnet", "name": "Claude 3.5 Sonnet",     "provider": "Anthropic",  "mode": "text",   "input": 3.00,   "output": 15.00,  "free": False, "context_k": 200},
    {"model_id": "gemini-1-5-pro",    "name": "Gemini 1.5 Pro",        "provider": "Google",     "mode": "text",   "input": 1.25,   "output": 5.00,   "free": False, "context_k": 2000},
    {"model_id": "mistral-large",     "name": "Mistral Large",         "provider": "Mistral",    "mode": "text",   "input": 2.00,   "output": 6.00,   "free": False, "context_k": 128},
    {"model_id": "grok-2",            "name": "Grok 2",                "provider": "xAI",        "mode": "text",   "input": 2.00,   "output": 10.00,  "free": False, "context_k": 131},
    # Дорогие (рассуждения)
    {"model_id": "o1-mini",           "name": "o1-mini",               "provider": "OpenAI",     "mode": "text",   "input": 1.10,   "output": 4.40,   "free": False, "context_k": 128},
    {"model_id": "o1",                "name": "o1",                    "provider": "OpenAI",     "mode": "text",   "input": 15.00,  "output": 60.00,  "free": False, "context_k": 200},
    {"model_id": "claude-3-opus",     "name": "Claude 3 Opus",         "provider": "Anthropic",  "mode": "text",   "input": 15.00,  "output": 75.00,  "free": False, "context_k": 200},
    # Изображения (цена за 1 изображение в поле output, input=0)
    {"model_id": "dall-e-3",          "name": "DALL-E 3",              "provider": "OpenAI",     "mode": "images", "input": 0.00,   "output": 40.00,  "free": False, "context_k": 0},
    {"model_id": "flux-1-1-pro",      "name": "FLUX 1.1 Pro",          "provider": "Black Forest","mode": "images", "input": 0.00,   "output": 4.00,   "free": False, "context_k": 0},
    # Видео
    {"model_id": "sora",              "name": "Sora",                  "provider": "OpenAI",     "mode": "video",  "input": 0.00,   "output": 150.00, "free": False, "context_k": 0},
    {"model_id": "runway-gen3",       "name": "Runway Gen-3",          "provider": "Runway",     "mode": "video",  "input": 0.00,   "output": 50.00,  "free": False, "context_k": 0},
]

PLANS = {
    "free": {
        "name": "Free",
        "price_usd": 0,
        "free_tokens": 50000,
        "rate_limit": "10 req/min",
        "features": ["50K токенов при регистрации", "Все текстовые модели", "API доступ", "CLI инструмент"],
    },
    "pro": {
        "name": "Pro",
        "price_usd": 10,
        "free_tokens": 500000,
        "rate_limit": "60 req/min",
        "features": ["500K токенов/мес", "Приоритетная очередь", "Все модели включая изображения", "Стриминг", "История запросов"],
    },
    "enterprise": {
        "name": "Enterprise",
        "price_usd": 50,
        "free_tokens": 5000000,
        "rate_limit": "Неограничено",
        "features": ["5M токенов/мес", "Выделенный сервер", "SLA 99.9%", "Поддержка 24/7", "Кастомные модели"],
    },
}


@router.get("", summary="Цены на все модели")
async def get_pricing() -> Dict:
    """Получить актуальные цены на все AI модели."""
    by_mode: Dict[str, List] = {"text": [], "images": [], "video": [], "coding": []}
    for p in PRICING:
        mode = p["mode"]
        entry = {
            "model_id": p["model_id"],
            "name": p["name"],
            "provider": p["provider"],
            "context_k": p.get("context_k", 0),
            "input_per_1m_usd": p["input"],
            "output_per_1m_usd": p["output"],
            "is_free": p["free"],
            # Удобный расчёт
            "cost_per_1k_tokens": round((p["input"] + p["output"]) / 2000, 6),
            "note": "Первые 50 000 токенов бесплатно" if p["free"] else (
                "$0 за вход, цена за 1 картинку" if mode == "images" else ""
            ),
        }
        if mode in by_mode:
            by_mode[mode].append(entry)
        # Coding = те же что text
        if mode == "text":
            by_mode["coding"].append(entry)

    return {
        "currency": "USD",
        "note": "Цены за 1 миллион токенов. При регистрации — 50 000 бесплатных токенов.",
        "free_on_register": "50 000 токенов",
        "models": by_mode,
        "total_models": len(PRICING),
    }


@router.get("/plans", summary="Тарифные планы")
async def get_plans() -> Dict:
    """Тарифные планы IIStudio."""
    return {
        "currency": "USD",
        "billing": "monthly",
        "plans": PLANS,
        "topup": {
            "min_usd": 5,
            "note": "Пополни баланс через личный кабинет. 1$ = ~1M токенов (зависит от модели).",
            "methods": ["Crypto (TON, USDT)", "Card (скоро)"],
        }
    }
