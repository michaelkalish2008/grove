"""Tests: ollama_client — health check, generate, error handling."""

import json
from unittest.mock import MagicMock, patch

import pytest

from grove.swarm.ollama_client import OllamaError, generate, health_check, list_models


def _mock_response(body: dict):
    mock = MagicMock()
    mock.read.return_value = json.dumps(body).encode()
    mock.__enter__ = lambda s: s
    mock.__exit__ = MagicMock(return_value=False)
    return mock


def test_health_check_true():
    with patch("urllib.request.urlopen", return_value=_mock_response({"models": []})):
        assert health_check() is True


def test_health_check_false_on_error():
    with patch("urllib.request.urlopen", side_effect=OSError("refused")):
        assert health_check() is False


def test_list_models():
    body = {"models": [{"name": "qwen3:8b"}, {"name": "gemma4:latest"}]}
    with patch("urllib.request.urlopen", return_value=_mock_response(body)):
        models = list_models()
    assert "qwen3:8b" in models
    assert "gemma4:latest" in models


def test_generate_returns_text():
    body = {"response": "The answer is 42."}
    with patch("urllib.request.urlopen", return_value=_mock_response(body)):
        result = generate("qwen3:8b", "What is the answer?")
    assert result == "The answer is 42."


def test_generate_raises_on_empty_response():
    with patch("urllib.request.urlopen", return_value=_mock_response({"response": ""})):
        with pytest.raises(OllamaError, match="Empty response"):
            generate("qwen3:8b", "prompt")


def test_generate_raises_on_http_error():
    import urllib.error
    err = urllib.error.HTTPError(url="x", code=500, msg="err", hdrs={}, fp=None)
    err.read = lambda: b"internal error"
    with patch("urllib.request.urlopen", side_effect=err):
        with pytest.raises(OllamaError, match="HTTP 500"):
            generate("qwen3:8b", "prompt")


def test_generate_raises_on_connection_error():
    with patch("urllib.request.urlopen", side_effect=OSError("connection refused")):
        with pytest.raises(OllamaError, match="Cannot reach"):
            generate("qwen3:8b", "prompt")
