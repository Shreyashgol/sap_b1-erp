from datetime import date
from decimal import Decimal
from typing import Any

from fastapi import HTTPException

from app.operations.sql_executor import execute_read_only_sql
from app.operations.purchase_rag import build_purchase_rag_fetch_sql
from app.schema.response import PurchaseOrderActionResponse


def _get(row: dict[str, Any], *keys: str):
    lowered = {str(key).lower(): value for key, value in row.items()}
    for key in keys:
        if key in row:
            return row[key]
        value = lowered.get(key.lower())
        if value is not None:
            return value
    return None


def _number(value, default: float = 0) -> float:
    if value is None:
        return default
    if isinstance(value, Decimal):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _clean_number(value):
    number = _number(value)
    return int(number) if number.is_integer() else number


def _date_text(value) -> str | None:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _parse_date(value) -> date | None:
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return None
    return None


def _percent_text(value) -> str:
    number = _clean_number(value)
    return f"{number}%"


def _format_variance(value) -> str:
    number = _number(value)
    prefix = "+" if number > 0 else ""
    clean = int(number) if number.is_integer() else round(number, 2)
    return f"{prefix}{clean}"


def _purchase_order_status(row: dict[str, Any]) -> str:
    canceled = str(_get(row, "CANCELED", "canceled") or "").upper()
    if canceled == "Y":
        return "Cancelled"

    doc_status = str(_get(row, "DocStatus", "doc_status") or "").upper()
    if doc_status == "O":
        return "Open"
    if doc_status == "C":
        return "Closed"
    return doc_status or "Unknown"


def _line_status(row: dict[str, Any], ordered: float, received: float, pending: float) -> str:
    raw_status = str(_get(row, "LineStatus", "line_status") or "").upper()
    if raw_status == "C" or pending <= 0:
        return "Closed"
    if received > 0 and pending > 0:
        return "Partially Received"
    if raw_status == "O":
        return "Open"
    return "Pending"


def _is_overdue(due_date: date | None, status: str) -> bool:
    return bool(due_date and due_date < date.today() and status == "Open")


def _risk(status: str, pending: float, overdue: bool) -> str:
    if status == "Cancelled":
        return "High"
    if overdue and pending > 0:
        return "High"
    if pending > 0:
        return "Medium"
    return "Low"


def _line_insights(status: str, pending: float, variance: float, delayed: bool) -> list[str]:
    insights: list[str] = []
    if status == "Partially Received":
        insights.append("Partial goods received")
    if pending > 0:
        insights.append("Remaining quantity pending from vendor")
    if variance > 0:
        insights.append("Purchase cost slightly higher than standard")
    elif variance < 0:
        insights.append("Purchase cost below standard")
    if delayed:
        insights.append("Expected delivery date has passed")
    return insights


def _normalize_purchase_order(row: dict[str, Any]) -> dict[str, Any]:
    total = _number(_get(row, "DocTotal", "doc_total"))
    paid = _number(_get(row, "PaidToDate", "paid_to_date"))
    pending = max(total - paid, 0)
    due_date = _parse_date(_get(row, "DocDueDate", "doc_due_date"))
    status = _purchase_order_status(row)
    overdue = _is_overdue(due_date, status)

    return {
        "po_number": str(_get(row, "DocNum", "doc_num") or _get(row, "DocEntry", "doc_entry") or ""),
        "date": _date_text(_get(row, "DocDate", "doc_date")),
        "vendor": {
            "code": _get(row, "CardCode", "card_code"),
            "name": _get(row, "CardName", "card_name"),
        },
        "amount": {
            "total": _clean_number(total),
            "paid": _clean_number(paid),
            "pending": _clean_number(pending),
            "currency": _get(row, "DocCur", "doc_cur"),
        },
        "status": status,
        "delivery": {
            "due_date": _date_text(_get(row, "DocDueDate", "doc_due_date")),
            "is_overdue": overdue,
        },
        "risk": _risk(status, pending, overdue),
        "remarks": _get(row, "Comments", "comments"),
    }


def _normalize_purchase_order_line(row: dict[str, Any]) -> dict[str, Any]:
    ordered = _number(_get(row, "Quantity", "quantity"))
    received = _number(_get(row, "DelivrdQty", "delivrd_qty"))
    pending = _number(_get(row, "OpenQty", "open_qty", "OpenCreQty", "open_cre_qty"), max(ordered - received, 0))
    unit_price = _number(_get(row, "Price", "price"))
    stock_price = _number(_get(row, "StockPrice", "stock_price"))
    variance = unit_price - stock_price
    expected_date = _parse_date(_get(row, "ShipDate", "ship_date"))
    delayed = bool(expected_date and expected_date < date.today() and pending > 0)
    status = _line_status(row, ordered, received, pending)

    return {
        "item": {
            "code": _get(row, "ItemCode", "item_code"),
            "name": _get(row, "Dscription", "dscription"),
        },
        "quantity": {
            "ordered": _clean_number(ordered),
            "received": _clean_number(received),
            "pending": _clean_number(pending),
        },
        "pricing": {
            "unit_price": _clean_number(unit_price),
            "discount": _percent_text(_get(row, "DiscPrcnt", "disc_prcnt")),
            "total": _clean_number(_get(row, "LineTotal", "line_total")),
            "currency": _get(row, "Currency", "currency"),
        },
        "tax": {
            "percent": _percent_text(_get(row, "VatPrcnt", "vat_prcnt")),
            "amount": _clean_number(_get(row, "VatSum", "vat_sum")),
        },
        "status": status,
        "delivery": {
            "expected_date": _date_text(_get(row, "ShipDate", "ship_date")),
            "is_delayed": delayed,
        },
        "warehouse": _get(row, "WhsCode", "whs_code"),
        "cost": {
            "purchase_price": _clean_number(_get(row, "GrossBuyPr", "gross_buy_pr", "Price", "price")),
            "standard_cost": _clean_number(stock_price),
            "variance": _format_variance(variance),
        },
        "insights": _line_insights(status, pending, variance, delayed),
    }


def _normalize_rows(rows: list[dict[str, Any]], result_type: str) -> list[dict[str, Any]]:
    if result_type == "purchaseOrderLines":
        return [_normalize_purchase_order_line(row) for row in rows]
    return [_normalize_purchase_order(row) for row in rows]


def execute(intent, repository):
    del repository

    fetch_query = intent.fetchQuery or ""

    try:
        query_spec = build_purchase_rag_fetch_sql(fetch_query=fetch_query)
        rows = execute_read_only_sql(query_spec["sql"], query_spec["params"])
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Fetch execution failed: {str(exc)}") from exc

    if not rows:
        raise HTTPException(status_code=404, detail="No purchase orders matched the fetch query")

    filters = query_spec["filters"]
    result_type = filters.get("resultType", "purchaseOrders")
    normalized_rows = rows if result_type == "ragQuery" else _normalize_rows(rows, result_type)
    count = len(normalized_rows)
    doc_entry = _get(rows[0], "DocEntry", "doc_entry")

    if result_type == "ragQuery":
        message = "✅ I ran the purchase RAG fetch and found 1 result." if count == 1 else f"✅ I ran the purchase RAG fetch and found {count} results."
    elif count == 1:
        message = "✅ Here is the purchase order line you requested." if result_type == "purchaseOrderLines" else "✅ Here is the Purchase Order you requested."
    else:
        noun = "purchase order lines" if result_type == "purchaseOrderLines" else "purchase orders"
        message = f"✅ I found {count} {noun} matching your criteria."

    return PurchaseOrderActionResponse(
        status="fetched",
        message=message,
        docEntry=doc_entry,
        data={
            "filters": filters,
            "rowCount": count,
            "sql": query_spec["sql"],
            "strategy": "rag",
            "results": normalized_rows,
        },
    )
