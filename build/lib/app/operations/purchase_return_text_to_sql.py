import re
from typing import Any


DEFAULT_LIMIT = 10
MAX_LIMIT = 50


def _extract_limit(fetch_query: str) -> int:
    for pattern in [r"\btop\s+(\d+)\b", r"\blatest\s+(\d+)\b", r"\blast\s+(\d+)\b", r"\bfirst\s+(\d+)\b"]:
        match = re.search(pattern, fetch_query, flags=re.IGNORECASE)
        if match:
            return max(1, min(int(match.group(1)), MAX_LIMIT))
    return DEFAULT_LIMIT


def _extract_doc_number(fetch_query: str) -> int | None:
    for pattern in [
        r"\bdoc(?:ument)?\s*(?:entry|number|num)?\s*[:#-]?\s*(\d+)\b",
        r"\bpurchase\s+return\s*[:#-]?\s*(\d+)\b",
        r"\breturn\s*[:#-]?\s*(\d+)\b",
    ]:
        match = re.search(pattern, fetch_query, flags=re.IGNORECASE)
        if match:
            return int(match.group(1))
    return None


def _extract_card_code(fetch_query: str) -> str | None:
    match = re.search(r"\bV\d+\b", fetch_query, flags=re.IGNORECASE)
    return match.group(0).upper() if match else None


def _extract_item_code(fetch_query: str) -> str | None:
    match = re.search(r"\b(?:ITEM(?=[\d_-])|RM(?=[\d_-]))[\w-]*\b", fetch_query, flags=re.IGNORECASE)
    return match.group(0).upper() if match else None


def _extract_status(fetch_query: str) -> str | None:
    lowered = fetch_query.lower()
    if "cancelled" in lowered or "canceled" in lowered:
        return "Cancelled"
    if "closed" in lowered:
        return "Closed"
    if "open" in lowered:
        return "Open"
    return None


def _is_line_search(fetch_query: str) -> bool:
    return bool(re.search(r"\b(line|lines|line\s+items?|items?|products?|details?)\b", fetch_query, flags=re.IGNORECASE))


def _append_header_filters(where_clauses, params, filters, doc_number, card_code, status):
    if doc_number is not None:
        where_clauses.append("(DocEntry = :doc_number OR DocNum = :doc_number)")
        params["doc_number"] = doc_number
        filters["docNumber"] = doc_number
    if card_code:
        where_clauses.append("CardCode = :card_code")
        params["card_code"] = card_code
        filters["cardCode"] = card_code
    if status == "Cancelled":
        where_clauses.append("CANCELED = 'Y'")
        filters["status"] = status
    elif status == "Closed":
        where_clauses.append("DocStatus = 'C'")
        filters["status"] = status
    elif status == "Open":
        where_clauses.append("DocStatus = 'O'")
        where_clauses.append("(CANCELED IS NULL OR CANCELED <> 'Y')")
        filters["status"] = status


def _build_line_sql(query_text, doc_number, card_code, item_code, status, limit) -> dict[str, Any]:
    where_clauses = []
    params = {"limit": limit}
    filters = {"limit": limit, "resultType": "purchaseReturnLines"}
    if doc_number is not None:
        where_clauses.append("DocEntry = :doc_number")
        params["doc_number"] = doc_number
        filters["docNumber"] = doc_number
    if card_code:
        where_clauses.append("BaseCard = :card_code")
        params["card_code"] = card_code
        filters["cardCode"] = card_code
    if item_code:
        where_clauses.append("ItemCode = :item_code")
        params["item_code"] = item_code
        filters["itemCode"] = item_code
    if status == "Closed":
        where_clauses.append("LineStatus = 'C'")
        filters["status"] = status
    elif status == "Open":
        where_clauses.append("LineStatus = 'O'")
        filters["status"] = status

    sql = """
        SELECT DocEntry, LineNum, ItemCode, Dscription, Quantity, OpenQty, Price, LineTotal,
               Currency, VatPrcnt, VatSum, TaxCode, WhsCode, LineStatus, BaseType, BaseEntry, BaseLine
        FROM RPD1
    """.strip()
    if where_clauses:
        sql += "\nWHERE " + "\n  AND ".join(where_clauses)
    order_by = "DocEntry DESC, LineNum ASC"
    if re.search(r"\b(oldest|earliest)\b", query_text, flags=re.IGNORECASE):
        order_by = "DocEntry ASC, LineNum ASC"
    sql += f"\nORDER BY {order_by}\nLIMIT :limit"
    return {"sql": sql, "params": params, "filters": filters}


def build_purchase_return_fetch_sql(fetch_query: str, intent_card_code: str | None = None, intent_doc_entry: int | None = None) -> dict[str, Any]:
    query_text = fetch_query.strip()
    if not query_text and intent_card_code is None and intent_doc_entry is None:
        raise ValueError("Fetch query is empty")

    doc_number = intent_doc_entry if intent_doc_entry is not None else _extract_doc_number(query_text)
    card_code = intent_card_code or _extract_card_code(query_text)
    item_code = _extract_item_code(query_text)
    status = _extract_status(query_text)
    line_search = _is_line_search(query_text)
    limit = _extract_limit(query_text) if line_search else (1 if doc_number is not None else _extract_limit(query_text))

    if line_search:
        return _build_line_sql(query_text, doc_number, card_code, item_code, status, limit)

    where_clauses = []
    params = {"limit": limit}
    filters = {"limit": limit, "resultType": "purchaseReturns"}
    _append_header_filters(where_clauses, params, filters, doc_number, card_code, status)

    sql = """
        SELECT DocEntry, DocNum, DocDate, DocDueDate, DocStatus, CANCELED, CardCode, CardName,
               DocCur, DocTotal, VatSum, Comments
        FROM ORPD
    """.strip()
    if where_clauses:
        sql += "\nWHERE " + "\n  AND ".join(where_clauses)
    order_by = "DocEntry DESC"
    if re.search(r"\b(oldest|earliest)\b", query_text, flags=re.IGNORECASE):
        order_by = "DocEntry ASC"
    sql += f"\nORDER BY {order_by}\nLIMIT :limit"
    return {"sql": sql, "params": params, "filters": filters}
