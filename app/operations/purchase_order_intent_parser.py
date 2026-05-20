import json

from app.model.purchase_order_intent import PurchaseOrderIntent
from app.operations.llm_client import chat_completion

PARSE_PROMPT_TEMPLATE = """
You are a SAP B1 purchase order assistant. Parse the user request into a JSON object.
Return ONLY raw JSON - no backticks, no markdown, no explanation.

Rules:
1. Detect the action carefully:
   - "cancel" -> user says: cancel, void, reverse, delete, abort
   - "close"  -> user says: close, complete, finish, mark as done, fulfill
   - "create" -> user says: create, place, make, add, new purchase order
   - "update" -> user says: update, modify, change, edit
   - "fetch"  -> user says: get, fetch, show, find, lookup, query, give, list, display, retrieve

2. Extract these keys (use null for anything not mentioned):
   - action       : exactly one of: create / cancel / close / update / fetch
   - docEntry     : integer - the SAP document number; null if not present
   - cardCode     : string - SAP vendor code; null if not present
   - docDate      : string YYYY-MM-DD - document/order date; null if not present
   - docDueDate   : string YYYY-MM-DD - due/delivery date; null if not present
   - taxDate      : string YYYY-MM-DD - same as docDueDate if not specified; null if docDueDate also null
   - items        : list of objects with itemCode, quantity, unitPrice, taxCode; null if none mentioned
   - mobileNumber : string - mobile number for cancel operations; null if not present
   - fetchQuery   : string - the original query for fetch operations; null if not fetch action

3. For cancel and close: docEntry or mobileNumber is required.
   Set cardCode, docDate, docDueDate, taxDate, items to null.

4. For fetch: set fetchQuery to the user's query text.

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

    candidates.sort(key=len, reverse=True)

    for candidate in candidates:
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue

    raise json.JSONDecodeError("No valid JSON object found in API output", raw, 0)


def parse_purchase_order_intent(user_prompt: str) -> PurchaseOrderIntent:
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

    return PurchaseOrderIntent(**parsed)
