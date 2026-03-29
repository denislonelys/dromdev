# ============================================================================
# IIStudio — Тесты: arena.parser и arena.receiver
# ============================================================================

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from arena.receiver import ArenaResponse, ResponseProcessor
from arena.modes import get_mode, list_modes, MODES
from arena.selectors import MODE_TAB_MAP


class TestResponseProcessor:
    def test_clean_text_removes_extra_newlines(self):
        raw = "Привет\n\n\n\nМир\n\n\n"
        result = ResponseProcessor.clean_text(raw)
        assert "\n\n\n" not in result
        assert result.strip() == result

    def test_clean_text_strips(self):
        result = ResponseProcessor.clean_text("  hello  ")
        assert result == "hello"

    def test_estimate_tokens(self):
        text = "a" * 400
        assert ResponseProcessor.estimate_tokens(text) == 100

    def test_estimate_tokens_minimum(self):
        assert ResponseProcessor.estimate_tokens("") == 1

    def test_extract_image_urls_from_html(self):
        html = '<img src="https://example.com/image.png" />'
        urls = ResponseProcessor.extract_image_urls(html)
        assert "https://example.com/image.png" in urls

    def test_extract_image_urls_from_text(self):
        text = "Вот изображение: https://cdn.example.com/photo.jpg"
        urls = ResponseProcessor.extract_image_urls(text)
        assert any("photo.jpg" in u for u in urls)

    def test_extract_image_urls_empty(self):
        urls = ResponseProcessor.extract_image_urls("Обычный текст без картинок")
        assert urls == []

    def test_process_creates_response(self):
        resp = ResponseProcessor.process(
            raw_text="Отличный вопрос!",
            prompt="Тест",
            model_id="gpt-4o",
            model_name="GPT-4o",
            mode="text",
            latency_ms=250.0,
        )
        assert isinstance(resp, ArenaResponse)
        assert resp.success is True
        assert resp.text == "Отличный вопрос!"
        assert resp.model_id == "gpt-4o"
        assert resp.latency_ms == 250.0

    def test_process_empty_response(self):
        resp = ResponseProcessor.process(
            raw_text="",
            prompt="Тест",
            model_id="gpt-4o",
            model_name="GPT-4o",
            mode="text",
        )
        assert resp.success is False
        assert resp.error is not None


class TestArenaResponse:
    def setup_method(self):
        self.resp = ArenaResponse(
            text="Вот код:\n```python\ndef hello():\n    print('hi')\n```\nГотово.",
            model_id="gpt-4o",
            model_name="GPT-4o",
            mode="coding",
            prompt="Напиши hello",
            latency_ms=300.0,
        )

    def test_has_code(self):
        assert self.resp.has_code is True

    def test_code_blocks(self):
        blocks = self.resp.code_blocks
        assert len(blocks) == 1
        assert "def hello" in blocks[0]

    def test_word_count(self):
        assert self.resp.word_count > 0

    def test_char_count(self):
        assert self.resp.char_count == len(self.resp.text)

    def test_to_dict(self):
        d = self.resp.to_dict()
        assert d["model_id"] == "gpt-4o"
        assert d["success"] is True
        assert "word_count" in d

    def test_format_for_cli(self):
        output = self.resp.format_for_cli()
        assert "GPT-4o" in output
        assert "300мс" in output

    def test_no_images(self):
        assert self.resp.has_images is False


class TestModes:
    def test_all_modes_exist(self):
        for mode_id in ["text", "images", "video", "coding"]:
            m = get_mode(mode_id)
            assert m is not None
            assert m.id == mode_id

    def test_get_unknown_mode(self):
        assert get_mode("unknown") is None

    def test_list_modes(self):
        modes = list_modes()
        assert len(modes) == 4

    def test_mode_has_selector(self):
        for mode_id in ["text", "images", "video", "coding"]:
            assert mode_id in MODE_TAB_MAP
            assert MODE_TAB_MAP[mode_id]


class TestSelectors:
    def test_all_selectors_non_empty(self):
        from arena import selectors as S
        for attr in dir(S):
            if attr.startswith("_") or attr == "MODE_TAB_MAP":
                continue
            val = getattr(S, attr)
            if isinstance(val, str):
                assert len(val) > 0, f"Пустой селектор: {attr}"

    def test_mode_tab_map_complete(self):
        assert set(MODE_TAB_MAP.keys()) == {"text", "images", "video", "coding"}
