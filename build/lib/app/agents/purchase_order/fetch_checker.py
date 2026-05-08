class FetchDecision:
    def __init__(self, subagent: str, reason: str, conditions: list[str]):
        self.subagent = subagent
        self.reason = reason
        self.conditions = conditions


def decide(fetch_query: str) -> FetchDecision:
    query = (fetch_query or "").lower()
    conditions: list[str] = ["Use read-only SQL only", "Fetch from purchase order header/line tables"]

    if any(token in query for token in ("line", "lines", "item", "items", "product", "products", "details")):
        conditions.append("Line-level request: use POR1 fields and preserve DocEntry/LineNum order")
        return FetchDecision(
            subagent="purchase_order_line_fetch",
            reason="The request asks for purchase order line/item details.",
            conditions=conditions,
        )

    if any(token in query for token in ("open", "closed", "cancelled", "canceled")):
        conditions.append("Status request: map Open=DocStatus O, Closed=DocStatus C, Cancelled=CANCELED Y")
        return FetchDecision(
            subagent="purchase_order_status_fetch",
            reason="The request includes a purchase order status condition.",
            conditions=conditions,
        )

    if any(token in query for token in ("vendor", "supplier", "cardcode")) or " v" in f" {query}":
        conditions.append("Vendor request: filter by CardCode when present")
        return FetchDecision(
            subagent="purchase_order_vendor_fetch",
            reason="The request targets a vendor/supplier purchase order view.",
            conditions=conditions,
        )

    if any(token in query for token in ("total", "amount", "value", "spend")):
        conditions.append("Amount request: return DocTotal/PaidToDate/Pending values from OPOR")
        return FetchDecision(
            subagent="purchase_order_amount_fetch",
            reason="The request asks for purchase order amount information.",
            conditions=conditions,
        )

    conditions.append("Header request: use OPOR and default to latest purchase orders")
    return FetchDecision(
        subagent="purchase_order_header_fetch",
        reason="Default purchase order header fetch.",
        conditions=conditions,
    )
