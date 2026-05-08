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
        r"\bap\s+invoice\s*[:#-]?\s*(\d+)\b",
        r"\bpurchase\s+invoice\s*[:#-]?\s*(\d+)\b",
        r"\binvoice\s*[:#-]?\s*(\d+)\b",
    ]:
        match = re.search(pattern, fetch_query, flags=re.IGNORECASE)
        if match:
            return int(match.group(1))
    return None


def _extract_card_code(fetch_query: str) -> str | None:
    match = re.search(r"\b[CV]\d+\b", fetch_query, flags=re.IGNORECASE)
    return match.group(0).upper() if match else None


def _extract_item_code(fetch_query: str) -> str | None:
    match = re.search(r"\b(?:ITEM(?=[\d_-])|RM(?=[\d_-])|I(?=\d))[\w-]*\b", fetch_query, flags=re.IGNORECASE)
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


def _append_filters(
    where_clauses: list[str],
    params: dict[str, Any],
    filters: dict[str, Any],
    doc_number: int | None,
    card_code: str | None,
    item_code: str | None,
    status: str | None,
):
    if doc_number is not None:
        where_clauses.append("(api.DocEntry = :doc_number OR api.DocNum = :doc_number)")
        params["doc_number"] = doc_number
        filters["docNumber"] = doc_number

    if card_code:
        where_clauses.append("api.CardCode = :card_code")
        params["card_code"] = card_code
        filters["cardCode"] = card_code

    if status == "Cancelled":
        where_clauses.append("api.CANCELED = 'Y'")
        filters["status"] = status
    elif status == "Closed":
        where_clauses.append("api.DocStatus = 'C'")
        filters["status"] = status
    elif status == "Open":
        where_clauses.append("api.DocStatus = 'O'")
        where_clauses.append("(api.CANCELED IS NULL OR api.CANCELED <> 'Y')")
        filters["status"] = status

    if item_code:
        where_clauses.append(
            """
            EXISTS (
                SELECT 1
                FROM PCH1 ail_filter
                WHERE ail_filter.DocEntry = api.DocEntry
                  AND ail_filter.ItemCode = :item_code
            )
            """.strip()
        )
        params["item_code"] = item_code
        filters["itemCode"] = item_code


def build_ap_invoice_fetch_sql(
    fetch_query: str,
    intent_card_code: str | None = None,
    intent_doc_entry: int | None = None,
) -> dict[str, Any]:
    query_text = fetch_query.strip()
    if not query_text and intent_card_code is None and intent_doc_entry is None:
        raise ValueError("Fetch query is empty")

    doc_number = intent_doc_entry if intent_doc_entry is not None else _extract_doc_number(query_text)
    card_code = intent_card_code or _extract_card_code(query_text)
    item_code = _extract_item_code(query_text)
    status = _extract_status(query_text)
    limit = 1 if doc_number is not None else _extract_limit(query_text)

    where_clauses: list[str] = []
    params: dict[str, Any] = {"limit": limit}
    filters: dict[str, Any] = {"limit": limit, "resultType": "apInvoices"}
    _append_filters(where_clauses, params, filters, doc_number, card_code, item_code, status)

    sql = """
        SELECT
            api.DocEntry,
            api.DocNum,
            api.Series,
            api.NumAtCard,
            api.CardCode,
            api.CardName,
            api.DocDate,
            api.DocDueDate,
            api.TaxDate,
            api.CreateDate,
            api.UpdateDate,
            api.DocCur,
            api.DocRate,
            api.DocTotal,
            api.VatSum,
            api.DiscSum,
            api.PaidToDate,
            api.PaidToDate AS PaidSum,
            (api.DocTotal - COALESCE(api.PaidToDate, 0)) AS BalanceDue,
            api.DocStatus,
            api.CANCELED,
            api.Comments,
            COALESCE(line_summary.line_count, 0) AS line_count,
            COALESCE(line_summary.item_codes, '') AS item_codes,
            COALESCE(line_summary.lines, '[]'::json) AS lines
        FROM OPCH api
        LEFT JOIN (
            SELECT
                ail.DocEntry,
                COUNT(*) AS line_count,
                STRING_AGG(ail.ItemCode, ', ' ORDER BY ail.LineNum) AS item_codes,
                JSON_AGG(
                    JSON_BUILD_OBJECT(
                        'doc_entry', ail.DocEntry,
                        'line_number', ail.LineNum,
                        'item_code', ail.ItemCode,
                        'item_description', ail.Dscription,
                        'quantity', ail.Quantity,
                        'open_qty', ail.OpenQty,
                        'open_inv_qty', ail.OpenInvQty,
                        'price', ail.Price,
                        'unit_price', ail.Price,
                        'line_total', ail.LineTotal,
                        'currency', ail.Currency,
                        'vat_prcnt', ail.VatPrcnt,
                        'vat_sum', ail.VatSum,
                        'tax_code', ail.TaxCode,
                        'whs_code', ail.WhsCode,
                        'line_status', ail.LineStatus,
                        'base_entry', ail.BaseEntry,
                        'base_line', ail.BaseLine
                    )
                    ORDER BY ail.LineNum
                ) AS lines
            FROM PCH1 ail
            GROUP BY ail.DocEntry
        ) AS line_summary
            ON line_summary.DocEntry = api.DocEntry
    """.strip()

    if where_clauses:
        sql += "\nWHERE " + "\n  AND ".join(where_clauses)

    order_by = "api.CreateDate DESC, api.DocEntry DESC"
    if re.search(r"\b(oldest|earliest)\b", query_text, flags=re.IGNORECASE):
        order_by = "api.CreateDate ASC, api.DocEntry ASC"

    sql += f"\nORDER BY {order_by}\nLIMIT :limit"
    return {"sql": sql, "params": params, "filters": filters}
