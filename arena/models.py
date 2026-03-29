# ============================================================================
# IIStudio — Реестр AI моделей arena.ai
# ============================================================================

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class AIModel:
    """Описание одной AI модели."""
    id: str                    # уникальный ID (используется при выборе)
    name: str                  # отображаемое имя
    provider: str              # OpenAI / Anthropic / Google / Meta / ...
    mode: str                  # text / images / video / coding
    context_k: int             # контекстное окно в тысячах токенов
    description: str = ""      # для чего лучше
    selector_value: str = ""   # значение <option> на сайте arena.ai
    is_default: bool = False   # модель по умолчанию для этого режима


# ── Текстовые модели ──────────────────────────────────────────────────────────

TEXT_MODELS: List[AIModel] = [
    AIModel("gpt-4o",            "GPT-4o",                 "OpenAI",    "text", 128, "Общие задачи",              "gpt-4o",                 True),
    AIModel("gpt-4o-mini",       "GPT-4o mini",            "OpenAI",    "text", 128, "Быстро и дёшево",           "gpt-4o-mini"),
    AIModel("o1",                "o1",                     "OpenAI",    "text", 200, "Глубокое рассуждение",      "o1"),
    AIModel("o1-mini",           "o1-mini",                "OpenAI",    "text", 128, "Быстрые рассуждения",       "o1-mini"),
    AIModel("o3-mini",           "o3-mini",                "OpenAI",    "text", 200, "Кодирование, математика",   "o3-mini"),
    AIModel("claude-3-5-sonnet", "Claude 3.5 Sonnet",      "Anthropic", "text", 200, "Лучший баланс",             "claude-3-5-sonnet-20241022"),
    AIModel("claude-3-5-haiku",  "Claude 3.5 Haiku",       "Anthropic", "text", 200, "Скорость",                  "claude-3-5-haiku-20241022"),
    AIModel("claude-3-opus",     "Claude 3 Opus",          "Anthropic", "text", 200, "Сложные задачи",            "claude-3-opus-20240229"),
    AIModel("gemini-2-flash",    "Gemini 2.0 Flash",       "Google",    "text", 1000,"Мультимодальность",         "gemini-2.0-flash"),
    AIModel("gemini-2-pro",      "Gemini 2.0 Pro",         "Google",    "text", 2000,"Большой контекст",          "gemini-2.0-pro"),
    AIModel("gemini-1-5-pro",    "Gemini 1.5 Pro",         "Google",    "text", 2000,"Огромный контекст",         "gemini-1.5-pro"),
    AIModel("llama-3-3-70b",     "Llama 3.3 70B",          "Meta",      "text", 128, "Open-source мощный",        "llama-3.3-70b-instruct"),
    AIModel("llama-3-1-405b",    "Llama 3.1 405B",         "Meta",      "text", 128, "Самый большой Llama",       "llama-3.1-405b-instruct"),
    AIModel("deepseek-r1",       "DeepSeek R1",            "DeepSeek",  "text", 64,  "Рассуждения, математика",   "deepseek-r1"),
    AIModel("deepseek-v3",       "DeepSeek V3",            "DeepSeek",  "text", 64,  "Общие задачи",              "deepseek-v3"),
    AIModel("grok-2",            "Grok 2",                 "xAI",       "text", 131, "Актуальная информация",     "grok-2"),
    AIModel("mistral-large",     "Mistral Large",          "Mistral",   "text", 128, "Европейский провайдер",     "mistral-large-latest"),
    AIModel("qwen-2-5-72b",      "Qwen 2.5 72B",           "Alibaba",   "text", 128, "Мультиязычность",           "qwen-2.5-72b-instruct"),
    AIModel("nova-pro",          "Amazon Nova Pro",        "Amazon",    "text", 300, "AWS интеграция",            "amazon.nova-pro-v1:0"),
    AIModel("command-r-plus",    "Command R+",             "Cohere",    "text", 128, "RAG задачи",                "command-r-plus"),
    AIModel("phi-4",             "Phi-4",                  "Microsoft", "text", 16,  "Компактный, мощный",        "phi-4"),
    AIModel("nemotron-70b",      "Nemotron 70B",           "NVIDIA",    "text", 128, "NVIDIA оптимизация",        "nvidia/llama-3.1-nemotron-70b-instruct"),
    AIModel("reka-flash",        "Reka Flash",             "Reka",      "text", 128, "Мультимодальный",           "reka-flash-3"),
]

# ── Модели изображений ────────────────────────────────────────────────────────

IMAGE_MODELS: List[AIModel] = [
    AIModel("dall-e-3",          "DALL-E 3",               "OpenAI",    "images", 0, "Фотореализм",               "dall-e-3",               True),
    AIModel("flux-1-1-pro",      "FLUX 1.1 Pro",           "Black Forest","images",0,"Высокое качество",          "flux-1.1-pro"),
    AIModel("flux-schnell",      "FLUX Schnell",           "Black Forest","images",0,"Скорость",                  "flux-schnell"),
    AIModel("stable-diff-3-5",   "Stable Diffusion 3.5",   "Stability", "images", 0, "Open-source генерация",     "stable-diffusion-3-5-large"),
    AIModel("ideogram-v3",       "Ideogram V3",            "Ideogram",  "images", 0, "Текст на изображениях",     "ideogram-v3"),
    AIModel("recraft-v3",        "Recraft V3",             "Recraft",   "images", 0, "Векторная графика",         "recraft-v3"),
    AIModel("imagen-3",          "Imagen 3",               "Google",    "images", 0, "Google генерация",          "imagen-3"),
]

# ── Видео модели ──────────────────────────────────────────────────────────────

VIDEO_MODELS: List[AIModel] = [
    AIModel("sora",              "Sora",                   "OpenAI",    "video",  0, "Видео OpenAI",              "sora",                   True),
    AIModel("runway-gen3",       "Runway Gen-3 Alpha",     "Runway",    "video",  0, "Кинематографичность",       "gen3a_turbo"),
    AIModel("kling-1-6-pro",     "Kling 1.6 Pro",          "Kuaishou",  "video",  0, "Высокое качество",          "kling-v1-6-pro"),
    AIModel("minimax-video-01",  "MiniMax Video-01",       "MiniMax",   "video",  0, "Анимация",                  "video-01"),
    AIModel("luma-ray2",         "Luma Ray2",              "Luma",      "video",  0, "Фотореализм",               "ray2"),
    AIModel("haiper-2",          "Haiper 2.0",             "Haiper",    "video",  0, "Движение",                  "haiper-video-v2"),
]

# ── Coding модели ─────────────────────────────────────────────────────────────

CODING_MODELS: List[AIModel] = [
    AIModel("claude-3-5-sonnet", "Claude 3.5 Sonnet",      "Anthropic", "coding", 200,"Лучший для кода",          "claude-3-5-sonnet-20241022", True),
    AIModel("o3-mini",           "o3-mini",                "OpenAI",    "coding", 200,"Рассуждения + код",        "o3-mini"),
    AIModel("deepseek-r1",       "DeepSeek R1",            "DeepSeek",  "coding", 64, "Математика + код",         "deepseek-r1"),
    AIModel("gpt-4o",            "GPT-4o",                 "OpenAI",    "coding", 128,"Универсальный",            "gpt-4o"),
    AIModel("gemini-2-flash",    "Gemini 2.0 Flash",       "Google",    "coding", 1000,"Быстрый",                 "gemini-2.0-flash"),
]

# ── Реестр ────────────────────────────────────────────────────────────────────

ALL_MODELS: List[AIModel] = TEXT_MODELS + IMAGE_MODELS + VIDEO_MODELS + CODING_MODELS

MODES: List[str] = ["text", "images", "video", "coding"]

_BY_ID: Dict[str, AIModel] = {m.id: m for m in ALL_MODELS}
_BY_MODE: Dict[str, List[AIModel]] = {
    "text":   TEXT_MODELS,
    "images": IMAGE_MODELS,
    "video":  VIDEO_MODELS,
    "coding": CODING_MODELS,
}


def get_model(model_id: str) -> Optional[AIModel]:
    """Найти модель по ID (точное совпадение или fuzzy по имени)."""
    if model_id in _BY_ID:
        return _BY_ID[model_id]
    # fuzzy: ищем по частичному совпадению имени или ID
    query = model_id.lower()
    for m in ALL_MODELS:
        if query in m.id.lower() or query in m.name.lower():
            return m
    return None


def get_models_for_mode(mode: str) -> List[AIModel]:
    """Все модели для данного режима."""
    return _BY_MODE.get(mode.lower(), [])


def get_default_model(mode: str) -> Optional[AIModel]:
    """Дефолтная модель для режима."""
    for m in get_models_for_mode(mode):
        if m.is_default:
            return m
    models = get_models_for_mode(mode)
    return models[0] if models else None
