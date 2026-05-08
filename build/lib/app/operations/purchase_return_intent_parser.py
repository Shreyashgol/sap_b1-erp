import json

from app.model.purchase_return_intent import PurchaseReturnIntent
from app.operations.llm_client import chat_completion


PARSE_PROMPT_TEMPLATE = """
You are a SAP B1 purchase return assistant. Parse the user request into a JSON object.
Return ONLY raw JSON - no markdown, no explanation.

Rules:
1. action must be exactly one of: create / cancel / close / reopen / update / fetch
2. Detect action:
   - cancel: cancel, void, reverse, delete, abort
   - close: close, complete, finish, mark as done
   - reopen: reopen, open again, reactivate
   - create: create, make, add, new purchase return, return goods
   - update: update, modify, change, edit
   - fetch: get, fetch, show, find, lookup, query, give, list, display, retrieve
3. Extract keys: action, docEntry, cardCode, docDate, docDueDate, taxDate, items, fetchQuery.
4. items are objects with itemCode, quantity, unitPrice, taxCode, baseEntry, baseLine.
5. For fetch, set fetchQuery to the original user request and items to null.

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


def parse_purchase_return_intent(user_prompt: str) -> PurchaseReturnIntent:
    formatted_prompt = PARSE_PROMPT_TEMPLATE.format(user_prompt=user_prompt)
    raw = chat_completion(
        [{"role": "user", "content": formatted_prompt}],
        temperature=0.1,
        max_tokens=2048,
        timeout=120,
    )
    parsed = _extract_json(raw)
    if isinstance(parsed.get("items"), list) and len(parsed["items"]) == 0:
        parsed["items"] = None
    if parsed.get("docEntry") is not None:
        try:
            parsed["docEntry"] = int(parsed["docEntry"])
        except (ValueError, TypeError):
            parsed["docEntry"] = None
    if not parsed.get("taxDate") and parsed.get("docDueDate"):
        parsed["taxDate"] = parsed["docDueDate"]
    if not parsed.get("action"):
        parsed["action"] = "create"
    return PurchaseReturnIntent(**parsed)
