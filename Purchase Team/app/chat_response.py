import json
from typing import Any

import requests

from app.config import GROQ_API_KEY, GROQ_MODEL


SYSTEM_PROMPT = """
You are a helpful SAP Business One purchase assistant inside a chatbot.
Answer like a practical business assistant, not like a raw API logger.

Your job:
- Explain what happened in plain language.
- Mention the routed document type and action only if useful.
- If the backend failed, explain what information is missing or what the user should fix.
- Generate the next 2-4 useful suggestions from the user's prompt, routing decision, and backend response.
- Keep answers concise, specific, and interactive.
- Do not invent SAP document numbers, vendor names, item names, prices, or database records.
- If suggesting prompts, use placeholders only when the needed value is unknown.
- Do not expose raw tokens, secrets, stack traces, or internal implementation details.
"""


def _json_preview(value: Any, max_chars: int = 5000) -> str:
    try:
        text = json.dumps(value, indent=2, default=str)
    except TypeError:
        text = str(value)
    if len(text) <= max_chars:
        return text
    return f"{text[:max_chars]}\n...truncated..."


def _fallback_response(
    prompt: str,
    routing_decision: dict[str, Any],
    api_response: dict[str, Any],
    status_code: int | None,
) -> str:
    action = routing_decision.get("action", "request")
    document_type = routing_decision.get("documentType", "purchase document").replace("_", " ")
    detail = api_response.get("detail") or api_response.get("message") or "No detailed backend message was returned."

    if status_code and 200 <= status_code < 300:
        message = api_response.get("message", "The request completed successfully.")
        return (
            f"{message}\n\n"
            f"I handled this as a **{document_type}** `{action}` request. "
            "The LLM suggestion service is currently unavailable, so I am not generating follow-up suggestions."
        )

    return (
        f"I understood your request as a **{document_type}** `{action}` request, but I could not complete it yet.\n\n"
        f"**What needs attention:** {detail}\n\n"
        "Please send the missing or corrected details in one message, and I will try again. "
        "The LLM suggestion service is currently unavailable, so I am not generating follow-up suggestions."
    )


def generate_chat_response(
    prompt: str,
    routing_decision: dict[str, Any],
    api_response: dict[str, Any],
    status_code: int | None,
) -> str:
    if not GROQ_API_KEY:
        return _fallback_response(prompt, routing_decision, api_response, status_code)

    user_payload = {
        "userPrompt": prompt,
        "routingDecision": routing_decision,
        "backendStatusCode": status_code,
        "backendResponse": api_response,
    }

    try:
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": GROQ_MODEL,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": (
                            "Create the final chatbot reply for this SAP request.\n\n"
                            f"{_json_preview(user_payload)}"
                        ),
                    },
                ],
                "temperature": 0.3,
                "max_tokens": 700,
            },
            timeout=30,
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"].strip()
    except Exception:
        return _fallback_response(prompt, routing_decision, api_response, status_code)
