"""Tests: LocalReActAgent — step parsing, final answer detection, step limit."""

import json
from unittest.mock import patch

import pytest

from grove.swarm.local_react_agent import AgentResult, LocalReActAgent


def _patch_generate(text: str):
    return patch("grove.swarm.local_react_agent.generate", return_value=text)


def test_direct_final_answer():
    """Agent gets FINAL_ANSWER on first step — 0 intermediate steps."""
    with _patch_generate("FINAL_ANSWER: Blue due to Rayleigh scattering."):
        agent = LocalReActAgent(model="qwen3:8b", worker_id=0, max_steps=4)
        result = agent.run("Why is the sky blue?", "Rayleigh scattering context.")
    assert result.answer == "Blue due to Rayleigh scattering."
    assert len(result.steps) == 0
    assert not result.truncated


def test_intermediate_steps_then_answer():
    """Agent goes through one thought/action step before final answer."""
    responses = [
        "Thought: I need to reason.\nAction: Analyze\nObservation: Rayleigh scattering.",
        "FINAL_ANSWER: The sky is blue.",
    ]
    with patch("grove.swarm.local_react_agent.generate", side_effect=responses):
        agent = LocalReActAgent(model="qwen3:8b", worker_id=1, max_steps=4)
        result = agent.run("Why blue?", "context")
    assert result.answer == "The sky is blue."
    assert len(result.steps) == 1
    assert not result.truncated


def test_step_limit_truncates():
    """Agent hits max_steps without FINAL_ANSWER — returns truncated result."""
    with _patch_generate("Thought: thinking.\nAction: Analyze\nObservation: still thinking."):
        agent = LocalReActAgent(model="qwen3:8b", worker_id=0, max_steps=2)
        result = agent.run("Hard question", "context")
    assert result.truncated is True
    assert len(result.steps) == 2


def test_ollama_error_returns_truncated(fake_agent_result):
    """OllamaError during generation returns a truncated result, not an exception."""
    from grove.swarm.ollama_client import OllamaError
    with patch("grove.swarm.local_react_agent.generate", side_effect=OllamaError("timeout")):
        agent = LocalReActAgent(model="qwen3:8b", worker_id=0, max_steps=3)
        result = agent.run("task", "context")
    assert result.truncated is True
    assert "OllamaError" in result.answer


def test_result_to_dict(fake_agent_result):
    d = fake_agent_result.to_dict()
    assert d["worker_id"] == 0
    assert d["model"] == "qwen3:8b"
    assert "elapsed_s" in d
    assert d["truncated"] is False
