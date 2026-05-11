"""
conftest.py — shared fixtures for grove[swarm] tests.

No real Ollama calls. HTTP is intercepted via unittest.mock.
No real Claude API calls. anthropic.Anthropic is patched where needed.
"""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

REPO_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))


@pytest.fixture
def fake_ollama_response():
    """Factory: returns a mock urllib response for a given text."""
    def _make(text: str = "FINAL_ANSWER: test answer") -> MagicMock:
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({"response": text}).encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        return mock_resp
    return _make


@pytest.fixture
def patch_ollama(fake_ollama_response):
    """Patch urllib.request.urlopen to return a canned Ollama response."""
    with patch("urllib.request.urlopen", return_value=fake_ollama_response()) as mock:
        yield mock


@pytest.fixture
def fake_agent_result():
    """A pre-built AgentResult for use without running Ollama."""
    from grove.swarm.local_react_agent import AgentResult
    return AgentResult(
        worker_id=0,
        answer="The sky is blue due to Rayleigh scattering.",
        steps=[],
        model="qwen3:8b",
        elapsed_s=1.5,
        truncated=False,
    )
