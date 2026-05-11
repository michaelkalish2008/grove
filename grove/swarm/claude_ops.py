"""
claude_ops.py — Claude API operations for the orchestrator.

Two roles:
  claude_plan(task, context, n_workers)   -> list[str]  (subtask decomposition)
  claude_synthesize(task, results)        -> str         (final answer synthesis)

Uses the Anthropic SDK with prompt caching on the context block.
Model defaults to claude-3-5-haiku-20241022 for cost efficiency;
override with CLAUDE_OPS_MODEL env var.

Inputs : task str, context str, list[AgentResult]
Outputs: list[str] subtasks  |  str synthesis
"""

from __future__ import annotations

import json
import os
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from grove.swarm.local_react_agent import AgentResult

MODEL = os.getenv("CLAUDE_OPS_MODEL", "claude-3-5-haiku-20241022")
MAX_SUBTASKS = 8

PLAN_SYSTEM = """\
You are a task decomposition specialist. Given a complex task and context, \
break it into independent, parallelizable subtasks for local AI workers.

Rules:
- Output ONLY a JSON array of subtask strings, nothing else.
- Each subtask must be self-contained and answerable from the context alone.
- Aim for {n} subtasks, maximum {max}.
- Each subtask should be 1-2 sentences.
- Do not include subtasks that require external tools or internet access.
"""

SYNTHESIZE_SYSTEM = """\
You are a synthesis specialist. Given a task and the outputs from multiple \
parallel AI workers, produce a single coherent, high-quality final answer.

Rules:
- Integrate insights from all worker results.
- Resolve contradictions by reasoning, not by choosing sides blindly.
- Be concise — do not pad the answer.
- Output only the final answer, no preamble.
"""


def _client():
    """Lazy import of anthropic to avoid import errors when SDK not installed."""
    try:
        import anthropic
        return anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    except ImportError as e:
        raise RuntimeError("anthropic SDK not installed. Run: pip install anthropic") from e


def claude_plan(task: str, context: str, n_workers: int = 3) -> list[str]:
    """
    Use Claude to decompose *task* into *n_workers* parallel subtasks.
    Returns a list of subtask strings.
    """
    client = _client()
    n = min(n_workers, MAX_SUBTASKS)

    response = client.messages.create(
        model=MODEL,
        max_tokens=512,
        system=PLAN_SYSTEM.format(n=n, max=MAX_SUBTASKS),
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": context,
                        "cache_control": {"type": "ephemeral"},  # cache the context
                    },
                    {
                        "type": "text",
                        "text": f"Task: {task}\n\nDecompose into {n} subtasks. Output JSON array only.",
                    },
                ],
            }
        ],
    )

    raw = response.content[0].text.strip()

    # Extract JSON array — strip any markdown fences
    raw = re.sub(r"^```[a-z]*\n?", "", raw, flags=re.MULTILINE)
    raw = re.sub(r"\n?```$", "", raw, flags=re.MULTILINE)

    try:
        subtasks = json.loads(raw)
        if not isinstance(subtasks, list):
            raise ValueError("Expected JSON array")
        return [str(s) for s in subtasks]
    except (json.JSONDecodeError, ValueError):
        # Fallback: treat the whole task as a single subtask
        return [task]


def claude_synthesize(task: str, results: list["AgentResult"]) -> str:
    """
    Use Claude to synthesize worker results into a final answer.
    Returns the synthesized answer string.
    """
    client = _client()

    worker_outputs = "\n\n".join(
        f"Worker {r.worker_id} ({r.model}):\n{r.answer}"
        for r in results
        if not r.truncated
    )
    if not worker_outputs:
        worker_outputs = "\n\n".join(
            f"Worker {r.worker_id} (truncated):\n{r.answer}" for r in results
        )

    response = client.messages.create(
        model=MODEL,
        max_tokens=1024,
        system=SYNTHESIZE_SYSTEM,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": worker_outputs,
                        "cache_control": {"type": "ephemeral"},
                    },
                    {
                        "type": "text",
                        "text": f"Original task: {task}\n\nSynthesize the worker outputs into a final answer.",
                    },
                ],
            }
        ],
    )
    return response.content[0].text.strip()


# ── CLI smoke test ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    task = sys.argv[1] if len(sys.argv) > 1 else "Explain how transformer attention works."
    context = sys.argv[2] if len(sys.argv) > 2 else (
        "Transformers use self-attention to weigh token relationships. "
        "The attention score is computed as softmax(QK^T/sqrt(d_k))V."
    )
    print("Planning subtasks...")
    subtasks = claude_plan(task, context, n_workers=3)
    print(f"Subtasks: {json.dumps(subtasks, indent=2)}")
