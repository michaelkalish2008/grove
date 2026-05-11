"""
claude_judge.py — Claude-as-Judge for scoring LocalReActAgent outputs.

Scores each sampled AgentResult on 5 dimensions (0-10 each):
  accuracy, conciseness, hallucination_risk, tone, style_match

Supports prompt versioning so score trends can be attributed to prompt changes.
Writes scores to the judge_scores table (see schema/board.sql).

Public API:
  JudgePrompt(version, system, user_template)
  ClaudeJudge(db_path, model, prompt_version)
  judge.score(result, subtask, context) -> JudgeScore
  judge.score_batch(results, subtask, context) -> list[JudgeScore]

Inputs : AgentResult, subtask str, context str
Outputs: JudgeScore(worker_id, model, scores dict, prompt_version, raw_response)
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from grove.swarm.local_react_agent import AgentResult

JUDGE_MODEL = os.getenv("CLAUDE_JUDGE_MODEL", "claude-3-5-haiku-20241022")

# ── Prompt versioning ─────────────────────────────────────────────────────────

@dataclass
class JudgePrompt:
    version: str
    system: str
    user_template: str  # receives {subtask}, {context}, {answer}

    def render_user(self, subtask: str, context: str, answer: str) -> str:
        return self.user_template.format(subtask=subtask, context=context, answer=answer)


PROMPT_V1 = JudgePrompt(
    version="v1",
    system="""\
You are an objective evaluator of AI-generated answers. Score the answer \
on 5 dimensions, each from 0 to 10. Output ONLY a JSON object with these keys:
  accuracy, conciseness, hallucination_risk, tone, style_match
No explanation. No preamble. JSON only.

Scoring rubric:
  accuracy         : 10 = fully correct, 0 = factually wrong
  conciseness      : 10 = tight and precise, 0 = bloated or repetitive
  hallucination_risk: 10 = well-grounded, 0 = unsupported claims
  tone             : 10 = professional and clear, 0 = inappropriate or unclear
  style_match      : 10 = matches expected output style, 0 = off-format
""",
    user_template="""\
Subtask: {subtask}

Context provided to the agent:
{context}

Agent answer:
{answer}

Score the answer. JSON only.""",
)

PROMPTS: dict[str, JudgePrompt] = {"v1": PROMPT_V1}
CURRENT_PROMPT = "v1"


# ── Score data class ──────────────────────────────────────────────────────────

@dataclass
class JudgeScore:
    worker_id: int
    model: str
    subtask: str
    scores: dict[str, int]  # {dimension: 0-10}
    prompt_version: str
    elapsed_s: float
    raw_response: str = ""
    error: str = ""

    @property
    def overall(self) -> float:
        if not self.scores:
            return 0.0
        return sum(self.scores.values()) / len(self.scores)

    def to_dict(self) -> dict:
        return {
            "worker_id": self.worker_id,
            "model": self.model,
            "subtask": self.subtask[:120],
            "scores": self.scores,
            "overall": round(self.overall, 2),
            "prompt_version": self.prompt_version,
            "elapsed_s": round(self.elapsed_s, 2),
            "error": self.error,
        }


# ── Judge ─────────────────────────────────────────────────────────────────────

class ClaudeJudge:
    """Score AgentResults using Claude. Persists scores to DB."""

    def __init__(
        self,
        db_path: str | Path | None = None,
        model: str = JUDGE_MODEL,
        prompt_version: str = CURRENT_PROMPT,
    ) -> None:
        self.model = model
        self.prompt = PROMPTS[prompt_version]
        self.db_path = Path(db_path) if db_path else None
        self._ensure_table()

    def _client(self):
        try:
            import anthropic
            return anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        except ImportError as e:
            raise RuntimeError("anthropic SDK not installed. Run: pip install anthropic") from e

    def _ensure_table(self) -> None:
        if not self.db_path or not self.db_path.exists():
            return
        db = sqlite3.connect(str(self.db_path))
        db.execute("""
            CREATE TABLE IF NOT EXISTS judge_scores (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                scored_at      TEXT DEFAULT (datetime('now')),
                worker_id      INTEGER,
                worker_model   TEXT,
                subtask        TEXT,
                prompt_version TEXT,
                accuracy       INTEGER,
                conciseness    INTEGER,
                hallucination_risk INTEGER,
                tone           INTEGER,
                style_match    INTEGER,
                overall        REAL,
                elapsed_s      REAL,
                raw_response   TEXT
            )
        """)
        db.commit()
        db.close()

    def _parse_scores(self, raw: str) -> dict[str, int]:
        """Extract JSON scores from Claude response."""
        raw = re.sub(r"^```[a-z]*\n?", "", raw.strip(), flags=re.MULTILINE)
        raw = re.sub(r"\n?```$", "", raw, flags=re.MULTILINE)
        data = json.loads(raw)
        dims = ["accuracy", "conciseness", "hallucination_risk", "tone", "style_match"]
        return {d: max(0, min(10, int(data.get(d, 5)))) for d in dims}

    def _persist(self, score: JudgeScore) -> None:
        if not self.db_path or not self.db_path.exists():
            return
        db = sqlite3.connect(str(self.db_path))
        db.execute("""
            INSERT INTO judge_scores
              (worker_id, worker_model, subtask, prompt_version,
               accuracy, conciseness, hallucination_risk, tone, style_match,
               overall, elapsed_s, raw_response)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            score.worker_id,
            score.model,
            score.subtask[:500],
            score.prompt_version,
            score.scores.get("accuracy"),
            score.scores.get("conciseness"),
            score.scores.get("hallucination_risk"),
            score.scores.get("tone"),
            score.scores.get("style_match"),
            round(score.overall, 2),
            round(score.elapsed_s, 2),
            score.raw_response[:2000],
        ))
        db.commit()
        db.close()

    def score(self, result: "AgentResult", subtask: str, context: str = "") -> JudgeScore:
        """Score a single AgentResult. Persists to DB if db_path is set."""
        t0 = time.monotonic()
        client = self._client()
        user_msg = self.prompt.render_user(subtask, context[:2000], result.answer)

        raw = ""
        error = ""
        scores: dict[str, int] = {}

        try:
            resp = client.messages.create(
                model=self.model,
                max_tokens=128,
                system=self.prompt.system,
                messages=[{"role": "user", "content": user_msg}],
            )
            raw = resp.content[0].text.strip()
            scores = self._parse_scores(raw)
        except Exception as e:
            error = str(e)

        js = JudgeScore(
            worker_id=result.worker_id,
            model=result.model,
            subtask=subtask,
            scores=scores,
            prompt_version=self.prompt.version,
            elapsed_s=time.monotonic() - t0,
            raw_response=raw,
            error=error,
        )
        if not error:
            self._persist(js)
        return js

    def score_batch(
        self, results: list["AgentResult"], subtask: str, context: str = ""
    ) -> list[JudgeScore]:
        """Score multiple results sequentially (judge calls are cheap, no need to parallelize)."""
        return [self.score(r, subtask, context) for r in results]


# ── CLI smoke test ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    from grove.swarm.local_react_agent import AgentResult, ReActStep

    # Fake result — no Ollama needed for this test
    fake = AgentResult(
        worker_id=0,
        answer="The sky is blue due to Rayleigh scattering of sunlight.",
        steps=[],
        model="qwen3:8b",
        elapsed_s=2.1,
    )
    subtask = "Why is the sky blue?"
    context = "Rayleigh scattering preferentially scatters shorter wavelengths."

    judge = ClaudeJudge()  # no db_path → scores not persisted
    score = judge.score(fake, subtask, context)
    print(json.dumps(score.to_dict(), indent=2))
    print(f"Overall: {score.overall:.1f}/10")
