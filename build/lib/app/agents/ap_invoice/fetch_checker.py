class FetchDecision:
    def __init__(self, subagent: str, reason: str, conditions: list[str]):
        self.subagent = subagent
        self.reason = reason
        self.conditions = conditions


def decide(fetch_query: str) -> FetchDecision:
    query = (fetch_query or "").lower()
    conditions: list[str] = ["Use read-only SQL only", "Fetch from AP invoice header/line tables"]

    if any(token in query for token in ("line", "lines", "item", "items", "product", "products", "details")):
        conditions.append("Line-level request: include ap_invoice_lines through the invoice summary")
        return FetchDecision(
            subagent="ap_invoice_line_fetch",
            reason="The request asks for invoice line/item information.",
            conditions=conditions,
        )

    if any(token in query for token in ("open", "closed", "cancelled", "canceled", "paid", "balance", "due")):
        conditions.append("Status/payment request: use status, paid_sum, paid_to_date, and balance_due")
        return FetchDecision(
            subagent="ap_invoice_status_fetch",
            reason="The request includes invoice status or payment state.",
            conditions=conditions,
        )

    if any(token in query for token in ("vendor", "supplier", "cardcode")) or " v" in f" {query}":
        conditions.append("Vendor request: filter by card_code when present")
        return FetchDecision(
            subagent="ap_invoice_vendor_fetch",
            reason="The request targets a vendor/supplier invoice view.",
            conditions=conditions,
        )

    if any(token in query for token in ("total", "amount", "value", "tax")):
        conditions.append("Amount request: include doc_total, vat_sum, paid, and balance fields")
        return FetchDecision(
            subagent="ap_invoice_amount_fetch",
            reason="The request asks for invoice amount information.",
            conditions=conditions,
        )

    conditions.append("Header request: use ap_invoices and default to latest invoices")
    return FetchDecision(
        subagent="ap_invoice_header_fetch",
        reason="Default AP invoice header fetch.",
        conditions=conditions,
    )
