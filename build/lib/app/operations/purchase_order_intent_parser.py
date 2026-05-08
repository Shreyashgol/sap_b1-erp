import json
import re

import requests

from app.model.purchase_order_intent import PurchaseOrderIntent, PurchaseOrderItem
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


def _parse_purchase_order_intent_locally(user_prompt: str) -> PurchaseOrderIntent:
    lowered = user_prompt.lower()
    action = "create"
    if any(word in lowered for word in ("cancel", "void", "reverse", "delete", "abort")):
        action = "cancel"
    elif any(word in lowered for word in ("close", "complete", "finish", "mark as done", "fulfill")):
        action = "close"
    elif any(word in lowered for word in ("update", "modify", "change", "edit")):
        action = "update"
    elif any(word in lowered for word in ("get", "fetch", "show", "find", "lookup", "query", "give", "list", "display", "retrieve")):
        action = "fetch"

    doc_entry = None
    doc_match = re.search(r"(?:doc(?:ument)?\s*(?:entry|number|num|no)?|po)\s*#?\s*(\d+)", lowered)
    if doc_match:
        doc_entry = int(doc_match.group(1))

    card_code = None
    vendor_match = re.search(
        r"(?:vendor|vendr|card\s*code|cardcode)\s+([a-z][a-z0-9_-]*)",
        user_prompt,
        re.IGNORECASE,
    ) or re.search(
        r"(?:for|forn)\s+(?:vendor|vendr)?\s*([a-z][a-z0-9_-]*)",
        user_prompt,
        re.IGNORECASE,
    )
    if vendor_match:
        card_code = vendor_match.group(1).upper()

    items = None
    item_patterns = [
        r"(?:with|and)\s+(?P<quantity>\d+)\s*(?:units?|pcs?|pieces?)?\s*(?:of\s+)?(?P<item>[a-z][a-z0-9_-]*)",
        r"(?P<item>[a-z][a-z0-9_-]*)\s*(?:x|qty|quantity)\s*(?P<quantity>\d+)",
    ]
    for pattern in item_patterns:
        item_match = re.search(pattern, user_prompt, re.IGNORECASE)
        if not item_match:
            continue
        item_code = item_match.group("item").upper()
        if item_code in {"CREATE", "PURCHASE", "ORDER", "VENDOR", "VENDR", "FOR", "FORN", "WITH", "AND"}:
            continue
        unit_price = None
        price_match = re.search(r"(?:at|price|unit\s*price)\s*(?:rs\.?|inr|\$)?\s*(\d+(?:\.\d+)?)", user_prompt, re.IGNORECASE)
        if price_match:
            unit_price = float(price_match.group(1))
        tax_code = None
        tax_match = re.search(r"tax\s*(?:code)?\s*([a-z0-9_-]+)", user_prompt, re.IGNORECASE)
        if tax_match:
            tax_code = tax_match.group(1).upper()
        items = [
            PurchaseOrderItem(
                itemCode=item_code,
                quantity=int(item_match.group("quantity")),
                unitPrice=unit_price,
                taxCode=tax_code,
            )
        ]
        break

    return PurchaseOrderIntent(
        action=action,
        docEntry=doc_entry,
        cardCode=card_code,
        items=items,
        fetchQuery=user_prompt if action == "fetch" else None,
    )


def parse_purchase_order_intent(user_prompt: str) -> PurchaseOrderIntent:
    formatted_prompt = PARSE_PROMPT_TEMPLATE.format(user_prompt=user_prompt)

    try:
        raw = chat_completion(
            [{"role": "user", "content": formatted_prompt}],
            temperature=0.1,
            max_tokens=2048,
            timeout=120,
        )
    except requests.exceptions.RequestException as exc:
        return _parse_purchase_order_intent_locally(user_prompt)

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
