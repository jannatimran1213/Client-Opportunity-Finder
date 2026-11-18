"""
Module 5 - LLM client (OpenAI-compatible chat completions over HTTP).

Provider is chosen by env: LLM_PROVIDER=auto picks Groq (GROQ_API_KEY), then OpenAI (OPENAI_API_KEY), then Gemini (GEMINI_API_KEY);
LLM_PROVIDER=custom uses LLM_BASE_URL + LLM_API_KEY (any OpenAI-compatible server, e.g. Together, Ollama).
When no key is configured `available()` is False and the copywriter uses its template engine instead.
"""
import json
import re
from typing import List, Optional, Tuple

import httpx

from app.core.config import settings

DEFAULT_MODELS = {"groq": "openai/gpt-oss-120b", "openai": "gpt-4o-mini", "gemini": "gemini-2.0-flash", "custom": "default"}
BASE_URLS = {"groq": "https://api.groq.com/openai/v1", "openai": "https://api.openai.com/v1",
             "gemini": "https://generativelanguage.googleapis.com/v1beta/openai"}  # Gemini's OpenAI-compatible endpoint


def _resolve() -> Optional[Tuple[str, str, str, str]]:
    p = (settings.LLM_PROVIDER or "auto").lower()
    if p == "custom" and settings.LLM_BASE_URL:
        return "custom", settings.LLM_BASE_URL.rstrip("/"), settings.LLM_API_KEY or "", settings.LLM_MODEL or DEFAULT_MODELS["custom"]
    if p in ("auto", "groq") and settings.GROQ_API_KEY:
        return "groq", BASE_URLS["groq"], settings.GROQ_API_KEY, settings.LLM_MODEL or DEFAULT_MODELS["groq"]
    if p in ("auto", "openai") and settings.OPENAI_API_KEY:
        return "openai", BASE_URLS["openai"], settings.OPENAI_API_KEY, settings.LLM_MODEL or DEFAULT_MODELS["openai"]
    if p in ("auto", "gemini") and settings.GEMINI_API_KEY:
        return "gemini", BASE_URLS["gemini"], settings.GEMINI_API_KEY, settings.LLM_MODEL or DEFAULT_MODELS["gemini"]
    return None


def available() -> bool:
    return _resolve() is not None


def provider_name() -> str:
    r = _resolve()
    return f"{r[0]}:{r[3]}" if r else "template"


async def chat(system: str, user: str, temperature: float = 0.7, max_tokens: int = 900) -> str:
    r = _resolve()
    if not r:
        raise RuntimeError("No LLM configured")
    _, base, key, model = r
    async with httpx.AsyncClient(timeout=60) as c:
        resp = await c.post(f"{base}/chat/completions", headers={"Authorization": f"Bearer {key}"},
                            json={"model": model, "temperature": temperature, "max_tokens": max_tokens,
                                  "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]})
    if resp.status_code >= 400:
        raise RuntimeError(f"LLM error {resp.status_code}: {resp.text[:200]}")
    return resp.json()["choices"][0]["message"]["content"].strip()


async def chat_json(system: str, user: str, temperature: float = 0.7) -> dict:
    text = await chat(system + "\nRespond with valid JSON only, no markdown.", user, temperature)
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise RuntimeError("LLM did not return JSON")
    return json.loads(m.group(0))

