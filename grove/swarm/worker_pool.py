"""
worker_pool.py — Pre-warmed pool of LocalReActAgent instances.

Manages a fixed set of agents, distributes tasks round-robin, and supports
parallel execution via asyncio.gather. Pool size and model are configured at
construction; agents are pre-assigned worker IDs for tracing.

Public API:
  WorkerPool(model, size, max_steps, temperature)
  pool.map(subtasks, context)        -> list[AgentResult]   (async)
  pool.run_one(subtask, context)     -> AgentResult          (async)

Inputs : list of subtask strings, shared context string
Outputs: list[AgentResult]
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from grove.swarm.local_react_agent import AgentResult, LocalReActAgent
from grove.swarm.ollama_client import health_check, list_models, pull_if_missing


@dataclass
class PoolConfig:
    model: str = "qwen3:8b"
    size: int = 3
    max_steps: int = 6
    temperature: float = 0.3


class WorkerPool:
    """
    Pre-warmed pool of LocalReActAgent instances.

    All agents share the same model and config. Tasks are dispatched
    concurrently via asyncio — one coroutine per agent slot.
    """

    def __init__(
        self,
        model: str = "qwen3:8b",
        size: int = 3,
        max_steps: int = 6,
        temperature: float = 0.3,
    ) -> None:
        self.config = PoolConfig(model=model, size=size, max_steps=max_steps, temperature=temperature)
        self._agents: list[LocalReActAgent] = [
            LocalReActAgent(model=model, worker_id=i, max_steps=max_steps, temperature=temperature)
            for i in range(size)
        ]

    def warm(self) -> None:
        """
        Verify Ollama is reachable and the model is available.
        Pulls the model if not present. Call once before map().
        """
        if not health_check():
            raise RuntimeError("Ollama is not reachable. Is it running?")
        available = list_models()
        if self.config.model not in available:
            pull_if_missing(self.config.model)

    async def run_one(self, subtask: str, context: str = "", worker_id: int = 0) -> AgentResult:
        """Run a single subtask on the specified agent slot."""
        agent = self._agents[worker_id % len(self._agents)]
        return await agent.arun(subtask, context)

    async def map(self, subtasks: list[str], context: str = "") -> list[AgentResult]:
        """
        Dispatch all subtasks concurrently, assigning agents round-robin.
        Returns results in the same order as subtasks.
        """
        if not subtasks:
            return []

        async def _run(i: int, subtask: str) -> AgentResult:
            agent = self._agents[i % len(self._agents)]
            return await agent.arun(subtask, context)

        coros = [_run(i, task) for i, task in enumerate(subtasks)]
        return list(await asyncio.gather(*coros))

    def map_sync(self, subtasks: list[str], context: str = "") -> list[AgentResult]:
        """Synchronous wrapper around map() for non-async callers."""
        return asyncio.run(self.map(subtasks, context))

    @property
    def size(self) -> int:
        return len(self._agents)

    @property
    def model(self) -> str:
        return self.config.model


# ── CLI smoke test ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import json
    import sys

    model = sys.argv[1] if len(sys.argv) > 1 else "qwen3:8b"
    size = int(sys.argv[2]) if len(sys.argv) > 2 else 2

    context = (
        "Rayleigh scattering causes blue wavelengths to scatter more in the atmosphere. "
        "Sunsets appear red because blue light is scattered away over long atmospheric paths."
    )
    subtasks = [
        "Why is the sky blue during the day?",
        "Why does the sky turn red at sunset?",
    ]

    pool = WorkerPool(model=model, size=size)
    pool.warm()
    print(f"Pool ready: {pool.size} workers, model={pool.model}\n")

    results = pool.map_sync(subtasks, context)
    for r in results:
        print(json.dumps(r.to_dict(), indent=2))
        print(f"Answer [{r.worker_id}]: {r.answer}\n")
