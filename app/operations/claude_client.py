import requests
from typing import Any

from app.config import (
    CLAUDE_API_KEY,
    CLAUDE_API_VERSION,
    CLAUDE_BASE_URL,
    CLAUDE_MODEL,
    CLAUDE_PROMPT_CACHE,
)


def _strip_cache_control(value):
    if isinstance(value, list):
        return [_strip_cache_control(item) for item in value]
    if isinstance(value, dict):
        return {key: _strip_cache_control(item) for key, item in value.items() if key != "cache_control"}
    return value


def _without_keys(value, keys: set[str]):
    if isinstance(value, list):
        return [_without_keys(item, keys) for item in value]
    if isinstance(value, dict):
        return {key: _without_keys(item, keys) for key, item in value.items() if key not in keys}
    return value


def _as_content_blocks(content: Any, *, cache: bool = False) -> list[dict[str, Any]]:
    if isinstance(content, list):
        blocks = content
    else:
        blocks = [{"type": "text", "text": str(content)}]

    normalized: list[dict[str, Any]] = []
    for block in blocks:
        if isinstance(block, dict):
            normalized.append(block.copy())
        else:
            normalized.append({"type": "text", "text": str(block)})

    if CLAUDE_PROMPT_CACHE and cache and normalized:
        normalized[-1]["cache_control"] = {"type": "ephemeral"}
    return normalized


def _system_blocks(system_parts: list[dict[str, Any]]) -> list[dict] | None:
    if not system_parts:
        return None

    blocks: list[dict[str, Any]] = []
    for part in system_parts:
        blocks.extend(_as_content_blocks(part.get("content", ""), cache=bool(part.get("cache"))))
    if CLAUDE_PROMPT_CACHE and blocks and not any("cache_control" in block for block in blocks):
        blocks[-1]["cache_control"] = {"type": "ephemeral"}
    return blocks


def _split_system_messages(messages: list[dict[str, Any]]) -> tuple[list[dict] | None, list[dict[str, Any]]]:
    system_parts: list[dict[str, Any]] = []
    claude_messages: list[dict[str, Any]] = []

    for message in messages:
        role = message.get("role", "user")
        content = message.get("content", "")
        cache = bool(message.get("cache"))

        if role == "system":
            system_parts.append({"content": content, "cache": cache})
            continue

        claude_messages.append(
            {
                "role": role if role in {"user", "assistant"} else "user",
                "content": _as_content_blocks(content, cache=cache),
            }
        )

    return _system_blocks(system_parts), claude_messages


def claude_chat_completion(
    messages: list[dict[str, Any]],
    *,
    temperature: float = 0,
    max_tokens: int = 1024,
    timeout: int = 120,
    api_key: str | None = None,
    model: str | None = None,
) -> str:
    resolved_api_key = api_key or CLAUDE_API_KEY
    resolved_model = model or CLAUDE_MODEL
    if not resolved_api_key:
        raise RuntimeError("CLAUDE_API_KEY or ANTHROPIC_API_KEY is required for LLM calls")

    system, claude_messages = _split_system_messages(messages)
    payload = {
        "model": resolved_model,
        "messages": claude_messages,
        "max_tokens": max_tokens,
    }
    if temperature is not None:
        payload["temperature"] = temperature
    if system:
        payload["system"] = system

    url = f"{CLAUDE_BASE_URL.rstrip('/')}/messages"
    headers = {
        "x-api-key": resolved_api_key,
        "anthropic-version": CLAUDE_API_VERSION,
        "Content-Type": "application/json",
    }

    response = requests.post(url, headers=headers, json=payload, timeout=timeout)
    if response.status_code == 400:
        error_text = response.text.lower()
        retry_payload = payload
        if CLAUDE_PROMPT_CACHE:
            retry_payload = _strip_cache_control(retry_payload)
        if "temperature" in error_text:
            retry_payload = _without_keys(retry_payload, {"temperature"})

        if retry_payload != payload:
            payload = retry_payload
            response = requests.post(url, headers=headers, json=payload, timeout=timeout)

    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        raise RuntimeError(f"Claude API request failed: {response.status_code} {response.text}") from exc

    content_blocks = response.json().get("content", [])
    text_blocks = [block.get("text", "") for block in content_blocks if block.get("type") == "text"]
    return "\n".join(text_blocks).strip()
