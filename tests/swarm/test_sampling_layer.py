"""Tests: SamplingLayer — rate, reservoir, stratified strategies."""

import pytest

from grove.swarm.local_react_agent import AgentResult
from grove.swarm.sampling_layer import SamplingConfig, SamplingLayer


def _result(worker_id=0, model="qwen3:8b") -> AgentResult:
    return AgentResult(
        worker_id=worker_id, answer="ans", steps=[], model=model, elapsed_s=1.0
    )


# ── Rate sampling ─────────────────────────────────────────────────────────────

def test_rate_1_always_samples():
    layer = SamplingLayer(SamplingConfig(strategy="rate", rate=1.0))
    assert layer.should_sample(_result()) is True


def test_rate_0_never_samples():
    layer = SamplingLayer(SamplingConfig(strategy="rate", rate=0.0))
    assert layer.should_sample(_result()) is False


def test_rate_partial_samples_roughly_correct():
    layer = SamplingLayer(SamplingConfig(strategy="rate", rate=0.5))
    sampled = sum(layer.should_sample(_result()) for _ in range(1000))
    assert 350 < sampled < 650  # within ±15% of 50%


# ── Reservoir sampling ────────────────────────────────────────────────────────

def test_reservoir_fills_to_capacity():
    layer = SamplingLayer(SamplingConfig(strategy="reservoir", reservoir_size=5))
    for i in range(5):
        r = _result(worker_id=i)
        assert layer.should_sample(r) is True
        layer.record(r)
    assert layer.stats()["reservoir_size"] == 5


def test_reservoir_samples_after_full():
    """After reservoir is full, some items are still accepted (probabilistic)."""
    layer = SamplingLayer(SamplingConfig(strategy="reservoir", reservoir_size=3))
    # Fill reservoir
    for i in range(3):
        r = _result(worker_id=i)
        layer.record(r)
    # Additional items have decreasing probability — over 100 tries, some should pass
    accepted = sum(layer.should_sample(_result()) for _ in range(100))
    assert accepted > 0


# ── Stratified sampling ───────────────────────────────────────────────────────

def test_stratified_samples_all_models():
    layer = SamplingLayer(SamplingConfig(strategy="stratified", rate=1.0))
    for model in ("qwen3:8b", "gemma4:latest", "llama3.2:latest"):
        assert layer.should_sample(_result(model=model)) is True


def test_stratified_tracks_by_model():
    layer = SamplingLayer(SamplingConfig(strategy="stratified", rate=1.0))
    layer.should_sample(_result(model="qwen3:8b"))
    layer.should_sample(_result(model="gemma4:latest"))
    stats = layer.stats()
    assert "qwen3:8b" in stats["by_model"]
    assert "gemma4:latest" in stats["by_model"]


# ── Invalid config ────────────────────────────────────────────────────────────

def test_invalid_strategy_raises():
    with pytest.raises((ValueError, KeyError)):
        SamplingConfig(strategy="unknown", rate=0.5)
