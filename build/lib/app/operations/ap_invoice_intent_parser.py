import json

import requests

from app.model.ap_invoice_intent import APInvoiceIntent
from app.operations.llm_client import chat_completion


PARSE_PROMPT_TEMPLATE = """
You are a SAP B1 AP invoice assistant. Parse the user request into a JSON object.
Return ONLY raw JSON - no markdown, no explanation.

Rules:
1. action must be exactly one of: create / cancel / close / reopen / update / fetch
2. "fetch" means the user wants invoice details, lookup, show, get, fetch, give, list, display, or retrieve
   "cancel" means cancel, void, reverse, delete, abort
   "close" means close, complete, finish, mark as done
   "reopen" means reopen, open again, reactivate
   "update" means update, modify, change, edit
3. Extract these keys and use null when unknown:
   - action
   - docEntry
   - cardCode
   - items: list of objects with itemCode, quantity, unitPrice, taxCode
   - fetchQuery
4. For create/update, focus on this schema:
   - cardCode
   - items[].itemCode
   - items[].quantity
   - items[].taxCode
   - items[].unitPrice
5. For fetch, set items to null and preserve the original text in fetchQuery
6. For cancel/close/reopen/update, docEntry is required when present in text.

User request: {user_prompt}
"""


def _extract_json(raw: str) -> dict:
    if "```" in raw:
        for block in raw.split("```"):
            block = block.strip().lstrip("json").strip()
            if block.startswith("{"):
                raw = block
                break

    candidates = []
    for start in range(len(raw)):
        if raw[start] != "{":
            continue
        depth = 0
        for end in range(start, len(raw)):
            if raw[end] == "{":
                depth += 1
            elif raw[end] == "}":
                depth -= 1
                if depth == 0:
                    candidates.append(raw[start : end + 1])
                    break

    for candidate in sorted(candidates, key=len, reverse=True):
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue
    raise json.JSONDecodeError("No valid JSON object found in API output", raw, 0)


def parse_ap_invoice_intent(user_prompt: str) -> APInvoiceIntent:
    formatted_prompt = PARSE_PROMPT_TEMPLATE.format(user_prompt=user_prompt)

    try:
        raw = chat_completion(
            [{"role": "user", "content": formatted_prompt}],
            temperature=0.1,
            max_tokens=2048,
            timeout=120,
        )
    except requests.exceptions.RequestException as exc:
        raise Exception(f"Ollama request failed: {str(exc)}") from exc

    parsed = _extract_json(raw)
    if isinstance(parsed.get("items"), list) and len(parsed["items"]) == 0:
        parsed["items"] = None

    if parsed.get("docEntry") is not None:
        try:
            parsed["docEntry"] = int(parsed["docEntry"])
        except (ValueError, TypeError):
            parsed["docEntry"] = None

    if not parsed.get("action"):
        parsed["action"] = "create"

    return APInvoiceIntent(**parsed)
