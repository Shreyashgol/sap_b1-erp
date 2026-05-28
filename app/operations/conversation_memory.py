from typing import Any


MAX_HISTORY_MESSAGES = 12
MAX_HISTORY_CHARS = 6000


def normalize_conversation_history(history: list[dict[str, Any]] | None) -> list[dict[str, str]]:
    normalized: list[dict[str, str]] = []
    for message in (history or [])[-MAX_HISTORY_MESSAGES:]:
        role = str(message.get("role", "")).lower()
        if role not in {"user", "assistant"}:
            continue
        content = str(message.get("content", "")).strip()
        if not content:
            continue
        normalized.append({"role": role, "content": content[:1200]})
    return normalized


def conversation_context_block(history: list[dict[str, Any]] | None) -> str:
    normalized = normalize_conversation_history(history)
    if not normalized:
        return ""

    lines = ["Previous conversation context:"]
    for index, message in enumerate(normalized, start=1):
        speaker = "User" if message["role"] == "user" else "Shera"
        lines.append(f"{index}. {speaker}: {message['content']}")

    text = "\n".join(lines)
    if len(text) <= MAX_HISTORY_CHARS:
        return text
    return text[-MAX_HISTORY_CHARS:]


def build_contextual_prompt(prompt: str, history: list[dict[str, Any]] | None) -> str:
    context = conversation_context_block(history)
    if not context:
        return prompt
    return (
        f"{context}\n\n"
        "Current user request:\n"
        f"{prompt}\n\n"
        "Use the previous conversation only to resolve references, follow-up wording, omitted document type, "
        "vendor/customer/item names, date ranges, and continuation requests."
    )
