# ============================================================================
# IIStudio — Тесты: arena.models
# ============================================================================

import pytest
from arena.models import (
    ALL_MODELS,
    get_default_model,
    get_model,
    get_models_for_mode,
    TEXT_MODELS,
    IMAGE_MODELS,
    VIDEO_MODELS,
    CODING_MODELS,
    MODES,
)


class TestModelRegistry:
    def test_all_models_not_empty(self):
        assert len(ALL_MODELS) > 0

    def test_text_models_exist(self):
        assert len(TEXT_MODELS) > 0

    def test_image_models_exist(self):
        assert len(IMAGE_MODELS) > 0

    def test_video_models_exist(self):
        assert len(VIDEO_MODELS) > 0

    def test_coding_models_exist(self):
        assert len(CODING_MODELS) > 0

    def test_modes_list(self):
        assert set(MODES) == {"text", "images", "video", "coding"}

    def test_each_mode_has_default(self):
        for mode in MODES:
            default = get_default_model(mode)
            assert default is not None, f"Нет дефолтной модели для режима {mode}"
            assert default.is_default is True

    def test_model_ids_unique(self):
        # ID уникальны в рамках режима
        for mode in MODES:
            models = get_models_for_mode(mode)
            ids = [m.id for m in models]
            assert len(ids) == len(set(ids)), f"Дублирующиеся ID в режиме {mode}"

    def test_all_models_have_required_fields(self):
        for m in ALL_MODELS:
            assert m.id, f"Пустой ID у модели: {m}"
            assert m.name, f"Пустое имя у модели {m.id}"
            assert m.provider, f"Пустой провайдер у модели {m.id}"
            assert m.mode in MODES, f"Неизвестный режим у модели {m.id}: {m.mode}"


class TestGetModel:
    def test_get_by_exact_id(self):
        m = get_model("gpt-4o")
        assert m is not None
        assert m.id == "gpt-4o"

    def test_get_by_partial_name(self):
        m = get_model("claude")
        assert m is not None
        assert "claude" in m.id.lower() or "claude" in m.name.lower()

    def test_get_nonexistent(self):
        m = get_model("totally-nonexistent-model-xyz-123")
        assert m is None

    def test_get_models_for_text(self):
        models = get_models_for_mode("text")
        assert len(models) >= 5

    def test_get_models_for_images(self):
        models = get_models_for_mode("images")
        assert len(models) >= 3

    def test_get_models_for_unknown_mode(self):
        models = get_models_for_mode("unknown_mode")
        assert models == []

    def test_default_model_for_coding(self):
        m = get_default_model("coding")
        assert m is not None
        assert m.mode == "coding"


class TestModelProperties:
    def test_gpt4o_context(self):
        m = get_model("gpt-4o")
        assert m is not None
        assert m.context_k == 128

    def test_gemini_large_context(self):
        m = get_model("gemini-1-5-pro")
        assert m is not None
        assert m.context_k >= 1000

    def test_model_mode_matches_category(self):
        for m in TEXT_MODELS:
            assert m.mode == "text"
        for m in IMAGE_MODELS:
            assert m.mode == "images"
        for m in VIDEO_MODELS:
            assert m.mode == "video"
        for m in CODING_MODELS:
            assert m.mode == "coding"
