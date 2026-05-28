from typing import Any

import requests

from app.config import GROQ_API_KEY, GROQ_BASE_URL, GROQ_MODEL, GROQ_TIMEOUT


def groq_chat_completion(
    messages: list[dict[str, Any]],
    *,
    temperature: float = 0.1,
    max_tokens: int = 2048,
    timeout: int | None = None,
    api_key: str | None = None,
    model: str | None = None,
) -> str:
    """Dormant Groq-compatible chat client for future provider switching."""
    resolved_api_key = api_key or GROQ_API_KEY
    if not resolved_api_key:
        raise RuntimeError("GROQ_API_KEY is required for Groq LLM calls")

    payload = {
        "model": model or GROQ_MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    headers = {
        "Authorization": f"Bearer {resolved_api_key}",
        "Content-Type": "application/json",
    }
    response = requests.post(
        f"{GROQ_BASE_URL.rstrip('/')}/chat/completions",
        headers=headers,
        json=payload,
        timeout=timeout or GROQ_TIMEOUT,
    )
    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        raise RuntimeError(f"Groq API request failed: {response.status_code} {response.text}") from exc

    choices = response.json().get("choices", [])
    if not choices:
        return ""
    return choices[0].get("message", {}).get("content", "").strip()
