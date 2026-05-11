"""
orchestrator.py — Claude-orchestrated map-reduce over a LocalReActAgent pool.

Flow:
  1. claude_plan()      → decompose task into subtasks
  2. pool.map()         → run subtasks in parallel on local Ollama workers
  3. sampling_layer     → decide which results go to the judge
  4. claude_judge       → score sampled results (async-friendly, sequential)
  5. claude_synthesize()→ produce final answer from all results

Public API:
  OrchestratorConfig(model, pool_size, max_steps, sampling, judge_db_path)
  Orchestrator(config)
  orchestrator.run(task, context) -> OrchestratorResult  (async)
  orchestrator.run_sync(task, context) -> OrchestratorResult

Inputs : task str, context str
Outputs: OrchestratorResult(task, answer, subtasks, results, scores, elapsed_s)
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from grove.swarm.claude_judge import ClaudeJudge, JudgeScore
from grove.swarm.claude_ops import claude_plan, claude_synthesize
from grove.swarm.local_react_agent import AgentResult
from grove.swarm.sampling_layer import SamplingConfig, SamplingLayer
from grove.swarm.worker_pool import WorkerPool


# ── Config ────────────────────────────────────────────────────────────────────

@dataclass
class OrchestratorConfig:
    # Worker pool
    model: str = "qwen3:8b"
    pool_size: int = 3
    max_steps: int = 6
    temperature: float = 0.3

    # Sampling
    sampling_strategy: str = "rate"   # rate | reservoir | stratified
    sampling_rate: float = 0.5        # fraction of results to judge
    reservoir_size: int = 50

    # Judge
    judge_db_path: Optional[str] = None  # path to grow.db; None = don't persist

    # Claude ops model (plan + synthesize)
    claude_model: str = "claude-3-5-haiku-20241022"


# ── Result ────────────────────────────────────────────────────────────────────

@dataclass
class OrchestratorResult:
    task: str
    answer: str
    subtasks: list[str]
    worker_results: list[AgentResult]
    judge_scores: list[JudgeScore]
    elapsed_s: float
    error: str = ""

    @property
    def avg_score(self) -> float:
        if not self.judge_scores:
            return 0.0
        return sum(s.overall for s in self.judge_scores) / len(self.judge_scores)

    def to_dict(self) -> dict:
        return {
            "task": self.task,
            "answer": self.answer,
            "subtasks": self.subtasks,
            "worker_results": [r.to_dict() for r in self.worker_results],
            "judge_scores": [s.to_dict() for s in self.judge_scores],
            "avg_judge_score": round(self.avg_score, 2),
            "elapsed_s": round(self.elapsed_s, 2),
            "error": self.error,
        }


# ── Orchestrator ──────────────────────────────────────────────────────────────

class Orchestrator:
    """
    Coordinates Claude (plan + synthesize) with a LocalReActAgent pool.
    Uses asyncio for parallel worker dispatch.
    """

    def __init__(self, config: OrchestratorConfig | None = None) -> None:
        self.config = config or OrchestratorConfig()
        self._pool: WorkerPool | None = None
        self._sampler: SamplingLayer | None = None
        self._judge: ClaudeJudge | None = None

    def _get_pool(self) -> WorkerPool:
        if self._pool is None:
            self._pool = WorkerPool(
                model=self.config.model,
                size=self.config.pool_size,
                max_steps=self.config.max_steps,
                temperature=self.config.temperature,
            )
        return self._pool

    def _get_sampler(self) -> SamplingLayer:
        if self._sampler is None:
            sc = SamplingConfig(
                strategy=self.config.sampling_strategy,
                rate=self.config.sampling_rate,
                reservoir_size=self.config.reservoir_size,
            )
            self._sampler = SamplingLayer(sc)
        return self._sampler

    def _get_judge(self) -> ClaudeJudge:
        if self._judge is None:
            self._judge = ClaudeJudge(
                db_path=self.config.judge_db_path,
            )
        return self._judge

    def warm(self) -> None:
        """Verify Ollama is reachable and model is available. Call before run()."""
        self._get_pool().warm()

    async def run(self, task: str, context: str = "") -> OrchestratorResult:
        """Full pipeline: plan → map → sample → judge → synthesize."""
        t0 = time.monotonic()
        pool = self._get_pool()
        sampler = self._get_sampler()
        judge = self._get_judge()

        try:
            # 1. Plan
            subtasks = await asyncio.get_event_loop().run_in_executor(
                None, lambda: claude_plan(task, context, n_workers=self.config.pool_size)
            )

            # 2. Map — parallel worker execution
            worker_results: list[AgentResult] = await pool.map(subtasks, context)

            # 3. Sample + Judge
            scores: list[JudgeScore] = []
            for result, subtask in zip(worker_results, subtasks):
                if sampler.should_sample(result):
                    sampler.record(result)
                    score = await asyncio.get_event_loop().run_in_executor(
                        None, lambda r=result, st=subtask: judge.score(r, st, context)
                    )
                    scores.append(score)

            # 4. Synthesize
            answer = await asyncio.get_event_loop().run_in_executor(
                None, lambda: claude_synthesize(task, worker_results)
            )

            return OrchestratorResult(
                task=task,
                answer=answer,
                subtasks=subtasks,
                worker_results=worker_results,
                judge_scores=scores,
                elapsed_s=time.monotonic() - t0,
            )

        except Exception as e:
            return OrchestratorResult(
                task=task,
                answer=f"[orchestrator error] {e}",
                subtasks=[],
                worker_results=[],
                judge_scores=[],
                elapsed_s=time.monotonic() - t0,
                error=str(e),
            )

    def run_sync(self, task: str, context: str = "") -> OrchestratorResult:
        """Synchronous wrapper for non-async callers (e.g. Flask routes)."""
        return asyncio.run(self.run(task, context))


# ── CLI smoke test ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import json
    import sys

    task = sys.argv[1] if len(sys.argv) > 1 else (
        "Explain the key differences between Rayleigh and Mie scattering "
        "and their effects on sky color."
    )
    context = (
        "Rayleigh scattering: affects particles much smaller than wavelength (gas molecules). "
        "Scattering intensity ∝ 1/λ^4, so blue scatters ~5x more than red. "
        "Mie scattering: affects particles comparable to wavelength (aerosols, water droplets). "
        "Less wavelength-dependent, causes white/grey haze near the horizon."
    )

    cfg = OrchestratorConfig(
        model="qwen3:8b",
        pool_size=2,
        max_steps=4,
        sampling_rate=1.0,   # judge everything in smoke test
    )
    orch = Orchestrator(cfg)
    orch.warm()

    print(f"Running task: {task}\n")
    result = orch.run_sync(task, context)
    print(json.dumps(result.to_dict(), indent=2))
    print(f"\n=== FINAL ANSWER ===\n{result.answer}")
