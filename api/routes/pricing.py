# ============================================================================
# IIStudio — Цены (только Claude Anthropic)
# ============================================================================

from __future__ import annotations
from typing import Dict, List
from fastapi import APIRouter

router = APIRouter(prefix="/pricing", tags=["pricing"])

# Только Claude модели
PRICING = [
    {
        "model_id":   "claude-opus-4-6",
        "name":       "Claude Opus 4.6",
        "provider":   "Anthropic",
        "mode":       "text",
        "input":      15.00,   # USD за 1M input токенов
        "output":     75.00,   # USD за 1M output токенов
        "free":       False,
        "context_k":  200,
        "description": "Самая мощная модель — сложные задачи, анализ, код",
    },
    {
        "model_id":   "claude-sonnet-4-6",
        "name":       "Claude Sonnet 4.6",
        "provider":   "Anthropic",
        "mode":       "text",
        "input":      3.00,
        "output":     15.00,
        "free":       False,
        "context_k":  200,
        "description": "Баланс скорости и интеллекта — ежедневные задачи",
    },
]

PLANS = {
    "free": {
        "name":        "Free",
        "price_usd":   0,
        "free_tokens": 50000,
        "rate_limit":  "10 req/min",
        "features":    [
            "50 000 токенов при регистрации (~25 больших запросов)",
            "Claude Sonnet 4.6 и Claude Opus 4.6",
            "Files API: PDF, изображения",
            "API доступ (sk-iis-...)",
            "CLI инструмент",
        ],
    },
    "pro": {
        "name":        "Pro",
        "price_usd":   10,
        "free_tokens": 500000,
        "rate_limit":  "60 req/min",
        "features":    [
            "500 000 токенов/мес",
            "Обе модели без ограничений",
            "Стриминг ответов",
            "История запросов",
            "Приоритетная обработка",
        ],
    },
    "enterprise": {
        "name":        "Enterprise",
        "price_usd":   50,
        "free_tokens": 5000000,
        "rate_limit":  "Неограничено",
        "features":    [
            "5 000 000 токенов/мес",
            "Выделенные ресурсы",
            "SLA 99.9%",
            "Поддержка 24/7",
            "Кастомный системный промпт",
        ],
    },
}

# Цена за 1 токен в USD
def get_token_price(model_id: str, token_type: str = "output") -> float:
    for p in PRICING:
        if p["model_id"] == model_id:
            price_per_1m = p["output"] if token_type == "output" else p["input"]
            return price_per_1m / 1_000_000
    return 0.000015  # дефолт (sonnet output)


@router.get("", summary="Цены на модели")
async def get_pricing() -> Dict:
    by_mode: Dict[str, List] = {"text": [], "coding": []}
    for p in PRICING:
        entry = {
            "model_id":          p["model_id"],
            "name":              p["name"],
            "provider":          p["provider"],
            "context_k":         p["context_k"],
            "input_per_1m_usd":  p["input"],
            "output_per_1m_usd": p["output"],
            "is_free":           p["free"],
            "description":       p.get("description", ""),
            "note":              f"Первые 50 000 токенов бесплатно при регистрации",
        }
        by_mode["text"].append(entry)
        by_mode["coding"].append(entry)

    return {
        "currency":        "USD",
        "note":            "Цены за 1 миллион токенов. 50 000 токенов бесплатно при регистрации.",
        "free_on_register":"50 000 токенов (~25 больших запросов)",
        "models":          by_mode,
        "total_models":    len(PRICING),
    }


@router.get("/plans", summary="Тарифные планы")
async def get_plans() -> Dict:
    return {
        "currency": "USD",
        "billing":  "monthly",
        "plans":    PLANS,
        "topup": {
            "min_usd": 5,
            "note":    "Пополни баланс. $1 ≈ 13 000 токенов Sonnet / 2 600 токенов Opus",
            "methods": ["TON", "USDT TRC20", "Crypto"],
        },
    }
