"""Thin wrapper around Ollama's REST API."""
import os
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv()

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
MODEL = os.getenv("OLLAMA_MODEL", "llama3.1:8b")


def _pick_num_ctx(text_length_chars: int) -> int:
    # Ollama defaults num_ctx to a small window (historically 2048) unless
    # told otherwise, which silently truncates long prompts (e.g. a
    # full-month rollup) instead of erroring. Size it to the prompt,
    # rounded up to the next power-of-two-ish bucket most models support.
    approx_tokens = text_length_chars // 3 + 1024  # + headroom for the response
    for bucket in (2048, 4096, 8192, 16384, 32768):
        if approx_tokens <= bucket:
            return bucket
    return 32768


def generate(
    prompt: str,
    model: str | None = None,
    system: str | None = None,
    timeout: float = 300.0,
    format: dict | str | None = None,
) -> str:
    """Single-shot generation (no streaming). Returns the raw text response.

    `format` is passed straight through to Ollama's `format` field — either
    the string "json" (valid JSON, any shape) or a JSON schema dict, which
    Ollama grammar-constrains token sampling against so the output is
    guaranteed to match the schema, not just be valid JSON.
    """
    payload = {
        "model": model or MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {"num_ctx": _pick_num_ctx(len(prompt) + len(system or ""))},
    }
    if system:
        payload["system"] = system
    if format is not None:
        payload["format"] = format

    with httpx.Client(timeout=timeout) as client:
        resp = client.post(f"{OLLAMA_HOST}/api/generate", json=payload)
        resp.raise_for_status()
        data = resp.json()
        return data.get("response", "").strip()
