"""Tests for Stage 2 LLM guard."""

import json
from unittest.mock import patch, MagicMock

import pytest

from guard.stage2_llm import (
    Stage2LLMGuard,
    CLASSIFICATION_USER_TEMPLATE,
    CONTENT_DELIMITER_START,
    CONTENT_DELIMITER_END,
)


class TestParseResponse:
    def _guard(self, **kwargs):
        return Stage2LLMGuard(kwargs)

    def test_parse_response_valid_json(self):
        guard = self._guard()
        raw = '{"is_injection": true, "confidence": 0.9, "reason": "injection detected"}'
        result = guard._parse_response(raw, 100.0)
        assert result.is_injection is True
        assert result.confidence == 0.9
        assert result.reason == "injection detected"

    def test_parse_response_markdown_fences(self):
        guard = self._guard()
        raw = '```json\n{"is_injection": false, "confidence": 0.1, "reason": "clean"}\n```'
        result = guard._parse_response(raw, 50.0)
        assert result.is_injection is False
        assert result.confidence == 0.1

    def test_parse_response_invalid_json_fails_open(self):
        guard = self._guard()
        result = guard._parse_response("not json at all", 50.0)
        assert result.is_injection is False
        assert result.confidence == 0.0
        assert "Failed to parse" in result.reason

    def test_confidence_below_threshold_passes(self):
        guard = self._guard(confidence_threshold=0.75)
        raw = '{"is_injection": true, "confidence": 0.5, "reason": "low confidence"}'
        result = guard._parse_response(raw, 50.0)
        assert result.is_injection is False  # below threshold


class TestBackendCalls:
    def _mock_urlopen(self, response_data: dict):
        """Create a mock urlopen that returns the given JSON response."""
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(response_data).encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        return mock_resp

    def test_ollama_backend_call(self):
        guard = Stage2LLMGuard({"backend": "ollama", "endpoint": "http://localhost:11434"})
        response_data = {
            "message": {
                "content": '{"is_injection": false, "confidence": 0.1, "reason": "clean"}'
            }
        }
        with patch("urllib.request.urlopen", return_value=self._mock_urlopen(response_data)):
            result = guard.classify("some content", context={"url": "https://example.com"})
        assert result.is_injection is False

    def test_openai_compatible_backend_call(self):
        guard = Stage2LLMGuard({
            "backend": "openai_compatible",
            "endpoint": "http://localhost:8080",
        })
        response_data = {
            "choices": [{
                "message": {
                    "content": '{"is_injection": true, "confidence": 0.95, "reason": "attack"}'
                }
            }]
        }
        with patch("urllib.request.urlopen", return_value=self._mock_urlopen(response_data)):
            result = guard.classify("evil content", context={"url": "https://evil.com"})
        assert result.is_injection is True

    def test_unknown_backend_raises(self):
        guard = Stage2LLMGuard({"backend": "nonexistent"})
        with pytest.raises(ValueError, match="Unknown backend"):
            guard.classify("content")


class TestDelimiterHardening:
    """B-6 regression: verify delimiters are unique boundary strings, not ---."""

    def test_delimiters_in_template(self):
        assert "<<<CONTENT_START_a7f3>>>" in CLASSIFICATION_USER_TEMPLATE
        assert "<<<CONTENT_END_a7f3>>>" in CLASSIFICATION_USER_TEMPLATE

    def test_old_delimiter_not_in_template(self):
        # The old `---` delimiters should no longer frame the content
        lines = CLASSIFICATION_USER_TEMPLATE.strip().split("\n")
        # Check that no line is exactly "---"
        assert "---" not in lines

    def test_delimiter_constants_exported(self):
        assert CONTENT_DELIMITER_START == "<<<CONTENT_START_a7f3>>>"
        assert CONTENT_DELIMITER_END == "<<<CONTENT_END_a7f3>>>"
