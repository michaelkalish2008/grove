"""
ollama_client.py — Thin async wrapper around the Ollama REST API.

Public API:
  health_check()               -> bool
  pull_if_missing(model)       -> None
  generate(model, prompt, **kw) -> str
  generate_stream(model, prompt, **kw) -> AsyncIterator[str]

Raises OllamaError on any failure.

Inputs : OLLAMA_HOST env var (default http://localhost:11434)
Outputs: str (generated text)
"""

from __future__ import annotations

import asyncio
import json
import os
import urllib.error
import urllib.request
from typing import AsyncIterator

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
DEFAULT_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "120"))


class OllamaError(RuntimeError):
    """Raised when the Ollama API returns an error or is unreachable."""


# ── Sync helpers (used by blocking callers and tests) ─────────────────────────

def _post(path: str, payload: dict, timeout: int = DEFAULT_TIMEOUT) -> dict:
    url = f"{OLLAMA_HOST}{path}"
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        raise OllamaError(f"HTTP {e.code} from {url}: {body}") from e
    except OSError as e:
        raise OllamaError(f"Cannot reach Ollama at {url}: {e}") from e


def _get(path: str, timeout: int = 10) -> dict:
    url = f"{OLLAMA_HOST}{path}"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return json.loads(resp.read())
    except OSError as e:
        raise OllamaError(f"Cannot reach Ollama at {url}: {e}") from e


# ── Public sync API ────────────────────────────────────────────────────────────

def health_check() -> bool:
    """Return True if Ollama is reachable, False otherwise."""
    try:
        _get("/api/tags", timeout=5)
        return True
    except OllamaError:
        return False


def list_models() -> list[str]:
    """Return names of locally available models."""
    data = _get("/api/tags")
    return [m["name"] for m in data.get("models", [])]


def pull_if_missing(model: str) -> None:
    """Pull *model* if it is not already present locally."""
    available = list_models()
    if model in available:
        return
    print(f"[ollama] pulling {model} …")
    _post("/api/pull", {"name": model, "stream": False}, timeout=600)
    print(f"[ollama] {model} ready")


def generate(
    model: str,
    prompt: str,
    system: str | None = None,
    context: list[int] | None = None,
    temperature: float = 0.7,
    timeout: int = DEFAULT_TIMEOUT,
) -> str:
    """Generate a completion synchronously. Returns the response text."""
    payload: dict = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": temperature},
    }
    if system:
        payload["system"] = system
    if context:
        payload["context"] = context

    result = _post("/api/generate", payload, timeout=timeout)
    text = result.get("response", "")
    if not text:
        raise OllamaError(f"Empty response from model {model}")
    return text


def chat(
    model: str,
    messages: list[dict],
    temperature: float = 0.7,
    timeout: int = DEFAULT_TIMEOUT,
) -> str:
    """Chat completion (messages format). Returns assistant message text."""
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "options": {"temperature": temperature},
    }
    result = _post("/api/chat", payload, timeout=timeout)
    return result.get("message", {}).get("content", "")


# ── Public async API ───────────────────────────────────────────────────────────

async def agenerate(
    model: str,
    prompt: str,
    system: str | None = None,
    temperature: float = 0.7,
    timeout: int = DEFAULT_TIMEOUT,
) -> str:
    """Async wrapper around generate() — runs in a thread pool."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        None, lambda: generate(model, prompt, system=system, temperature=temperature, timeout=timeout)
    )


async def achat(
    model: str,
    messages: list[dict],
    temperature: float = 0.7,
    timeout: int = DEFAULT_TIMEOUT,
) -> str:
    """Async wrapper around chat()."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        None, lambda: chat(model, messages, temperature=temperature, timeout=timeout)
    )


# ── CLI smoke test ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    model = sys.argv[1] if len(sys.argv) > 1 else "qwen3:8b"
    prompt = sys.argv[2] if len(sys.argv) > 2 else "Say hello in one sentence."

    print(f"Health: {health_check()}")
    print(f"Models: {list_models()}")
    print(f"\nGenerating with {model}…")
    print(generate(model, prompt))
