"""
sampling_layer.py — Decide whether an AgentResult should be sent to the Claude judge.

Inputs:
  AgentResult  (imported from grove.swarm.local_react_agent)
  SamplingConfig(strategy, rate, reservoir_size)

Outputs:
  SamplingLayer.should_sample(result) -> bool
  SamplingLayer.record(result)        -> None   (update internal state after sampling)
  SamplingLayer.stats()               -> dict   (counts by strategy/model)

Strategies:
  rate        — accept result with probability `rate` (0.0–1.0); default 0.1
  reservoir   — maintain a fixed-size reservoir (Vitter's Algorithm R); reservoir_size results kept
  stratified  — sample proportionally by model name so every model is represented

stdlib only. No external dependencies.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Literal

from grove.swarm.local_react_agent import AgentResult

# ── Config ─────────────────────────────────────────────────────────────────────

Strategy = Literal["rate", "reservoir", "stratified"]


@dataclass
class SamplingConfig:
    strategy: Strategy = "rate"
    rate: float = 0.1              # used by "rate" and "stratified"
    reservoir_size: int = 100      # used by "reservoir"

    def __post_init__(self) -> None:
        if self.strategy not in ("rate", "reservoir", "stratified"):
            raise ValueError(f"Unknown strategy: {self.strategy!r}")
        if not (0.0 <= self.rate <= 1.0):
            raise ValueError(f"rate must be in [0, 1], got {self.rate}")
        if self.reservoir_size < 1:
            raise ValueError(f"reservoir_size must be >= 1, got {self.reservoir_size}")


# ── Layer ──────────────────────────────────────────────────────────────────────

class SamplingLayer:
    """Stateful sampling gate for AgentResults.

    Usage:
        layer = SamplingLayer(SamplingConfig(strategy="rate", rate=0.2))
        if layer.should_sample(result):
            layer.record(result)
            send_to_judge(result)
    """

    def __init__(self, config: SamplingConfig) -> None:
        self.config = config

        # shared counters
        self._seen: int = 0                          # total results evaluated
        self._sampled: int = 0                       # total results accepted
        self._model_seen: dict[str, int] = {}        # model → total seen
        self._model_sampled: dict[str, int] = {}     # model → total sampled

        # reservoir state (strategy="reservoir")
        self._reservoir: list[AgentResult] = []
        self._reservoir_count: int = 0               # items considered so far

    # ── Public API ─────────────────────────────────────────────────────────────

    def should_sample(self, result: AgentResult) -> bool:
        """Return True if this result should be sent to the judge."""
        self._seen += 1
        self._model_seen[result.model] = self._model_seen.get(result.model, 0) + 1

        strategy = self.config.strategy
        if strategy == "rate":
            return random.random() < self.config.rate
        elif strategy == "reservoir":
            return self._reservoir_decision(result)
        elif strategy == "stratified":
            return self._stratified_decision(result)
        return False  # unreachable

    def record(self, result: AgentResult) -> None:
        """Call after should_sample returns True to update internal state."""
        self._sampled += 1
        self._model_sampled[result.model] = self._model_sampled.get(result.model, 0) + 1

        if self.config.strategy == "reservoir":
            self._reservoir_count += 1
            k = self._reservoir_count
            n = self.config.reservoir_size
            if len(self._reservoir) < n:
                self._reservoir.append(result)
            else:
                # Vitter's Algorithm R: replace a random element
                j = random.randint(0, k - 1)
                if j < n:
                    self._reservoir[j] = result

    def stats(self) -> dict:
        """Return sampling statistics keyed by strategy and model."""
        return {
            "strategy": self.config.strategy,
            "seen": self._seen,
            "sampled": self._sampled,
            "sample_rate_actual": round(self._sampled / self._seen, 4) if self._seen else 0.0,
            "reservoir_size": len(self._reservoir) if self.config.strategy == "reservoir" else None,
            "by_model": {
                model: {
                    "seen": self._model_seen.get(model, 0),
                    "sampled": self._model_sampled.get(model, 0),
                }
                for model in self._model_seen
            },
        }

    # ── Strategy helpers ───────────────────────────────────────────────────────

    def _reservoir_decision(self, result: AgentResult) -> bool:
        """Accept unconditionally until reservoir is full; then probabilistically."""
        k = self._reservoir_count + 1   # prospective count after this item
        n = self.config.reservoir_size
        if k <= n:
            return True
        # probability of inclusion = n / k
        return random.random() < (n / k)

    def _stratified_decision(self, result: AgentResult) -> bool:
        """Sample at `rate` per model, so every model is proportionally represented."""
        return random.random() < self.config.rate


# ── CLI smoke test ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import json

    def _fake(worker_id: int, model: str) -> AgentResult:
        return AgentResult(
            worker_id=worker_id,
            answer="42",
            steps=[],
            model=model,
            elapsed_s=0.5,
            truncated=False,
        )

    models = ["qwen3:8b", "llama3:8b", "mistral:7b"]
    results = [_fake(i, models[i % len(models)]) for i in range(200)]

    for strategy, kwargs in [
        ("rate",       {"rate": 0.25}),
        ("reservoir",  {"reservoir_size": 30}),
        ("stratified", {"rate": 0.33}),
    ]:
        cfg = SamplingConfig(strategy=strategy, **kwargs)
        layer = SamplingLayer(cfg)
        for r in results:
            if layer.should_sample(r):
                layer.record(r)
        s = layer.stats()
        print(f"\n[{strategy}]")
        print(json.dumps(s, indent=2))
