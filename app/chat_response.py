import json
from typing import Any

from app.config import CHAT_RESPONSE_CLAUDE_API_KEY, CHAT_RESPONSE_CLAUDE_MODEL
from app.operations.claude_client import claude_chat_completion
from app.operations.llm_client import chat_completion


SYSTEM_PROMPT = """
You are a helpful SAP Business One ERP assistant inside a chatbot named Shera.
Answer like a practical business assistant, not like a raw API logger.

Your job:
- Explain what happened in plain language.
- Mention the routed document type and action only if useful.
- If the backend failed, explain what information is missing or what the user should fix.
- If the backend detail says the HANA SQL API rejected the generated SELECT query, describe it as a query-generation issue, not a permissions issue.
- Only describe a backend failure as authentication/permission related when the backend explicitly says Unauthorized, Forbidden, token, credential, or API key.
- Generate the next 2-4 useful suggestions from the user's prompt, routing decision, and backend response.
- For fetch results, mention the specific result shape: row count, key totals, top rows, or the entity asked about.
- If the user asks for a graph, chart, plot, trend, or visualization, explain that the interface will render a chart when the result contains tabular numeric data. Still summarize the answer in text.
- If backendResponse.data.strategy is rag, explain the answer as an analytical fetch without exposing implementation details.
- Keep answers concise, specific, and interactive. Prefer a friendly "Here is what I found" style, then give 2-4 next-step suggestions phrased as clickable follow-up prompts.
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
        data = api_response.get("data") or {}
        rows = data.get("results") or data.get("rows") or []
        row_count = data.get("rowCount", len(rows) if isinstance(rows, list) else 0)
        strategy = data.get("strategy")
        summary = _rows_summary(rows) if isinstance(rows, list) else ""
        suggestions = _suggestions(prompt, document_type)
        analysis_note = " I handled this as an analytical fetch." if strategy == "rag" else ""
        chart_note = (
            "\n\nI also prepared the chart view for this result."
            if _wants_chart(prompt) and rows
            else ""
        )
        return (
            f"{message}\n\n"
            f"I handled this as a **{document_type}** `{action}` request and found **{row_count}** matching result(s).{analysis_note}"
            f"{summary}{chart_note}\n\n"
            f"**You can ask next:**\n{suggestions}"
        )

    return (
        f"I understood your request as a **{document_type}** `{action}` request, but I could not complete it yet.\n\n"
        f"**What needs attention:** {detail}\n\n"
        "Please send the missing or corrected details in one message, and I will try again."
    )


def _rows_summary(rows: list[Any], limit: int = 3) -> str:
    if not rows:
        return ""

    lines = []
    for row in rows[:limit]:
        if not isinstance(row, dict):
            continue
        useful_items = []
        for key, value in row.items():
            if value is None or isinstance(value, (dict, list)):
                continue
            useful_items.append(f"{key}: {value}")
            if len(useful_items) == 4:
                break
        if useful_items:
            lines.append("- " + ", ".join(useful_items))

    if not lines:
        return ""
    return "\n\n**Key results:**\n" + "\n".join(lines)


def _suggestions(prompt: str, document_type: str) -> str:
    lowered = prompt.lower()
    if "sales order" in document_type:
        suggestions = [
            "Show overdue open sales orders",
            "Which customers have the highest sales order value?",
            "Which products have the most pending sales order quantity?",
        ]
    elif "ar invoice" in document_type or "sales invoice" in document_type:
        suggestions = [
            "What is the total AR invoice balance receivable?",
            "Which customers have bought the most?",
            "Which products are selling the most?",
        ]
    elif "sales return" in document_type:
        suggestions = [
            "Show latest sales returns",
            "Which customers have the most sales returns?",
            "Which items are returned most by customers?",
        ]
    elif "purchase order" in document_type:
        suggestions = [
            "Show overdue open purchase orders",
            "Which vendors have the highest pending purchase order value?",
            "Which items have the most pending PO quantity?",
        ]
    elif "invoice" in document_type:
        suggestions = [
            "What is the total AP invoice balance due?",
            "Which vendors have the highest AP invoice amount?",
            "Which items have the highest invoiced quantity?",
        ]
    else:
        suggestions = [
            "What is the total purchase return value?",
            "Which vendors have the highest purchase return amount?",
            "Which items are returned the most?",
        ]

    if "vendor" in lowered:
        suggestions.append("Show the latest documents for vendor <vendor code>")

    return "\n".join(f"- {suggestion}" for suggestion in suggestions[:4])


def _wants_chart(prompt: str) -> bool:
    lowered = prompt.lower()
    return any(term in lowered for term in ("chart", "graph", "plot", "visualize", "visualise", "trend", "dashboard"))


def generate_chat_response(
    prompt: str,
    routing_decision: dict[str, Any],
    api_response: dict[str, Any],
    status_code: int | None,
) -> str:
    user_payload = {
        "userPrompt": prompt,
        "routingDecision": routing_decision,
        "backendStatusCode": status_code,
        "backendResponse": api_response,
    }

    try:
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    "Create the final chatbot reply for this SAP request.\n\n"
                    f"{_json_preview(user_payload)}"
                ),
            },
        ]
        if CHAT_RESPONSE_CLAUDE_API_KEY:
            return claude_chat_completion(
                messages,
                temperature=0.2,
                max_tokens=2048,
                timeout=120,
                api_key=CHAT_RESPONSE_CLAUDE_API_KEY,
                model=CHAT_RESPONSE_CLAUDE_MODEL,
            )
        return chat_completion(messages, temperature=0.3, max_tokens=2048, timeout=120)
    except Exception:
        return _fallback_response(prompt, routing_decision, api_response, status_code)
