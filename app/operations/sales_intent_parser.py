import json
import re

import requests

from app.config import SALES_TEAM_CLAUDE_API_KEY, SALES_TEAM_CLAUDE_MODEL
from app.model.sales_intent import SalesDocumentLine, SalesIntent
from app.operations.claude_client import claude_chat_completion


PARSE_PROMPT_TEMPLATE = """
You are a SAP B1 sales-team supervisor. Parse the request into JSON only.

Allowed actions: create, update, cancel, close, fetch.
Allowed documentType values:
- sales_order for customer orders
- ar_invoice for customer invoices / AR invoices / sales invoices
- sales_return for customer returns / returns

Return keys:
action, documentType, cardCode, docEntry, docDate, docDueDate, comments, items, fetchQuery.
Use null when missing. items must be a list of objects with itemCode, quantity, unitPrice, taxCode.
For fetch requests set fetchQuery to the original request.

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


def _parse_locally(user_prompt: str) -> SalesIntent:
    lowered = user_prompt.lower()
    action = "create"
    if any(word in lowered for word in ("cancel", "void", "reverse", "delete", "abort")):
        action = "cancel"
    elif any(word in lowered for word in ("close", "complete", "finish", "mark as done")):
        action = "close"
    elif any(word in lowered for word in ("update", "modify", "change", "edit")):
        action = "update"
    elif any(word in lowered for word in ("get", "fetch", "show", "find", "lookup", "query", "give", "list", "display", "retrieve", "top", "total", "how many")):
        action = "fetch"

    if any(word in lowered for word in ("return", "rma")):
        document_type = "sales_return"
    elif any(word in lowered for word in ("invoice", "ar invoice", "receivable", "billing")):
        document_type = "ar_invoice"
    else:
        document_type = "sales_order"

    doc_entry = None
    doc_match = re.search(r"(?:doc(?:ument)?\s*(?:entry|number|num|no)?|order|invoice|return)\s*#?\s*(\d+)", lowered)
    if doc_match:
        doc_entry = int(doc_match.group(1))

    card_code = None
    customer_match = re.search(
        r"(?:customer|card\s*code|cardcode|client)\s+([a-z][a-z0-9_-]*)",
        user_prompt,
        re.IGNORECASE,
    ) or re.search(r"\bfor\s+([cC]\d+)\b", user_prompt)
    if customer_match:
        card_code = customer_match.group(1).upper()

    comments = None
    comment_match = re.search(r"(?:comment|comments|remark|remarks)\s+(?:to|as)?\s*['\"]?([^'\"]+)", user_prompt, re.IGNORECASE)
    if comment_match:
        comments = comment_match.group(1).strip()

    items = None
    if action != "fetch":
        item_match = re.search(
            r"\b(?P<quantity>\d+)\s*(?:units?|pcs?|pieces?)\s*(?:of\s+)?(?P<item>[a-z][a-z0-9_-]*)",
            user_prompt,
            re.IGNORECASE,
        ) or re.search(
            r"\b(?P<item>[a-z][a-z0-9_-]*)\s*(?:x|qty|quantity)\s*(?P<quantity>\d+)\b",
            user_prompt,
            re.IGNORECASE,
        )
        if item_match:
            item_code = item_match.group("item").upper()
            if item_code not in {"SALES", "ORDER", "CUSTOMER", "CLIENT", "INVOICE", "RETURN", "WITH", "FOR"}:
                price_match = re.search(r"(?:at|price|unit\s*price)\s*(?:rs\.?|inr|\$)?\s*(\d+(?:\.\d+)?)", user_prompt, re.IGNORECASE)
                tax_match = re.search(r"tax\s*(?:code)?\s*([a-z0-9_-]+)", user_prompt, re.IGNORECASE)
                items = [
                    SalesDocumentLine(
                        itemCode=item_code,
                        quantity=int(item_match.group("quantity")),
                        unitPrice=float(price_match.group(1)) if price_match else None,
                        taxCode=tax_match.group(1).upper() if tax_match else None,
                    )
                ]

    return SalesIntent(
        action=action,
        documentType=document_type,
        cardCode=card_code,
        docEntry=doc_entry,
        comments=comments,
        items=items,
        fetchQuery=user_prompt if action == "fetch" else None,
    )


def parse_sales_intent(user_prompt: str) -> SalesIntent:
    try:
        raw = claude_chat_completion(
            [{"role": "user", "content": PARSE_PROMPT_TEMPLATE.format(user_prompt=user_prompt)}],
            temperature=0.1,
            max_tokens=1024,
            timeout=60,
            api_key=SALES_TEAM_CLAUDE_API_KEY,
            model=SALES_TEAM_CLAUDE_MODEL,
        )
        parsed = _extract_json(raw)
    except (requests.exceptions.RequestException, RuntimeError, json.JSONDecodeError):
        return _parse_locally(user_prompt)

    if parsed.get("items") == []:
        parsed["items"] = None
    if parsed.get("docEntry") is not None:
        try:
            parsed["docEntry"] = int(parsed["docEntry"])
        except (TypeError, ValueError):
            parsed["docEntry"] = None
    if not parsed.get("action"):
        parsed["action"] = "fetch"
    if not parsed.get("documentType"):
        parsed["documentType"] = "sales_order"
    if parsed["action"] == "fetch" and not parsed.get("fetchQuery"):
        parsed["fetchQuery"] = user_prompt
        parsed["items"] = None
    if parsed["action"] != "fetch":
        bad_item_codes = {"SALES", "ORDER", "CUSTOMER", "CLIENT", "INVOICE", "RETURN", "WITH", "FOR"}
        parsed_items = parsed.get("items") or []
        if not parsed_items or any(str(item.get("itemCode", "")).upper() in bad_item_codes for item in parsed_items):
            local_intent = _parse_locally(user_prompt)
            if local_intent.items:
                parsed["items"] = [item.model_dump() for item in local_intent.items]
    return SalesIntent(**parsed)
