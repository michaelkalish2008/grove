"""
local_react_agent.py — Stateless ReAct loop backed by a local Ollama model.

Each agent instance is assigned a worker_id at construction. Agents are
stateless across tasks — no memory between run() calls. Each run() executes
a Thought → Action → Observation loop until the agent emits FINAL_ANSWER
or the step limit is hit.

Public API:
  LocalReActAgent(model, worker_id, max_steps, temperature)
  agent.run(subtask, context) -> AgentResult

Inputs : subtask str, context str
Outputs: AgentResult(worker_id, answer, steps, model, elapsed_s, truncated)
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field

import sys as _sys, pathlib as _pathlib
from grove.swarm.ollama_client import OllamaError, agenerate, generate

# ── Prompts ───────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """\
You are a focused analytical agent. You receive a subtask and relevant context.
Work through the problem using the ReAct format:

Thought: <reason about what to do next>
Action: <one of: Analyze | Summarize | Extract | Compare | Calculate | Answer>
Observation: <result of the action>

Repeat Thought/Action/Observation until you have enough to answer, then output:
FINAL_ANSWER: <your complete answer to the subtask>

Rules:
- Be concise. Do not repeat yourself.
- Base all reasoning on the provided context only.
- If the context is insufficient, say so in FINAL_ANSWER.
- You have at most {max_steps} reasoning steps.
"""

STEP_TEMPLATE = """\
Subtask: {subtask}

Context:
{context}

Previous steps:
{history}

Continue from where you left off. If you have enough information, output FINAL_ANSWER.
"""

FINAL_ANSWER_RE = re.compile(r"FINAL_ANSWER\s*:\s*(.+)", re.DOTALL | re.IGNORECASE)


# ── Data classes ──────────────────────────────────────────────────────────────

@dataclass
class ReActStep:
    thought: str = ""
    action: str = ""
    observation: str = ""

    def format(self) -> str:
        parts = []
        if self.thought:
            parts.append(f"Thought: {self.thought}")
        if self.action:
            parts.append(f"Action: {self.action}")
        if self.observation:
            parts.append(f"Observation: {self.observation}")
        return "\n".join(parts)


@dataclass
class AgentResult:
    worker_id: int
    answer: str
    steps: list[ReActStep]
    model: str
    elapsed_s: float
    truncated: bool = False  # True if hit step limit without FINAL_ANSWER

    def to_dict(self) -> dict:
        return {
            "worker_id": self.worker_id,
            "answer": self.answer,
            "model": self.model,
            "steps": len(self.steps),
            "elapsed_s": round(self.elapsed_s, 2),
            "truncated": self.truncated,
        }


# ── Agent ─────────────────────────────────────────────────────────────────────

class LocalReActAgent:
    """Stateless ReAct agent. worker_id is for logging/tracing only."""

    def __init__(
        self,
        model: str = "qwen3:8b",
        worker_id: int = 0,
        max_steps: int = 6,
        temperature: float = 0.3,
    ) -> None:
        self.model = model
        self.worker_id = worker_id
        self.max_steps = max_steps
        self.temperature = temperature

    def _system(self) -> str:
        return SYSTEM_PROMPT.format(max_steps=self.max_steps)

    def _build_prompt(self, subtask: str, context: str, steps: list[ReActStep]) -> str:
        history = "\n\n".join(s.format() for s in steps) if steps else "(none yet)"
        return STEP_TEMPLATE.format(subtask=subtask, context=context[:4000], history=history)

    def _parse_step(self, text: str) -> tuple[ReActStep, str | None]:
        """Parse one model output. Returns (step, final_answer_or_None)."""
        # Check for final answer first
        m = FINAL_ANSWER_RE.search(text)
        if m:
            return ReActStep(), m.group(1).strip()

        step = ReActStep()
        for line in text.splitlines():
            low = line.strip()
            if low.startswith("Thought:"):
                step.thought = line.split(":", 1)[1].strip()
            elif low.startswith("Action:"):
                step.action = line.split(":", 1)[1].strip()
            elif low.startswith("Observation:"):
                step.observation = line.split(":", 1)[1].strip()
        return step, None

    def run(self, subtask: str, context: str = "") -> AgentResult:
        """Run the ReAct loop synchronously. Returns AgentResult."""
        t0 = time.monotonic()
        steps: list[ReActStep] = []
        system = self._system()

        for _ in range(self.max_steps):
            prompt = self._build_prompt(subtask, context, steps)
            try:
                raw = generate(
                    self.model, prompt,
                    system=system,
                    temperature=self.temperature,
                )
            except OllamaError as e:
                return AgentResult(
                    worker_id=self.worker_id,
                    answer=f"[OllamaError] {e}",
                    steps=steps,
                    model=self.model,
                    elapsed_s=time.monotonic() - t0,
                    truncated=True,
                )

            step, final = self._parse_step(raw)
            if final:
                return AgentResult(
                    worker_id=self.worker_id,
                    answer=final,
                    steps=steps,
                    model=self.model,
                    elapsed_s=time.monotonic() - t0,
                )
            steps.append(step)

        # Step limit hit — return best effort from last raw output
        return AgentResult(
            worker_id=self.worker_id,
            answer=f"[step limit] Last output: {steps[-1].format() if steps else '(none)'}",
            steps=steps,
            model=self.model,
            elapsed_s=time.monotonic() - t0,
            truncated=True,
        )

    async def arun(self, subtask: str, context: str = "") -> AgentResult:
        """Async version — runs generate in executor, same logic as run()."""
        t0 = time.monotonic()
        steps: list[ReActStep] = []
        system = self._system()

        for _ in range(self.max_steps):
            prompt = self._build_prompt(subtask, context, steps)
            try:
                raw = await agenerate(
                    self.model, prompt,
                    system=system,
                    temperature=self.temperature,
                )
            except OllamaError as e:
                return AgentResult(
                    worker_id=self.worker_id,
                    answer=f"[OllamaError] {e}",
                    steps=steps,
                    model=self.model,
                    elapsed_s=time.monotonic() - t0,
                    truncated=True,
                )

            step, final = self._parse_step(raw)
            if final:
                return AgentResult(
                    worker_id=self.worker_id,
                    answer=final,
                    steps=steps,
                    model=self.model,
                    elapsed_s=time.monotonic() - t0,
                )
            steps.append(step)

        return AgentResult(
            worker_id=self.worker_id,
            answer=f"[step limit] Last output: {steps[-1].format() if steps else '(none)'}",
            steps=steps,
            model=self.model,
            elapsed_s=time.monotonic() - t0,
            truncated=True,
        )


# ── CLI smoke test ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import json
    import sys

    model = sys.argv[1] if len(sys.argv) > 1 else "qwen3:8b"
    subtask = sys.argv[2] if len(sys.argv) > 2 else "Summarize the key idea."
    context = sys.argv[3] if len(sys.argv) > 3 else "The sky is blue because of Rayleigh scattering of sunlight."

    agent = LocalReActAgent(model=model, worker_id=0, max_steps=4)
    result = agent.run(subtask, context)
    print(json.dumps(result.to_dict(), indent=2))
    print(f"\nAnswer: {result.answer}")
