class FetchDecision:
    def __init__(self, subagent: str, reason: str, conditions: list[str]):
        self.subagent = subagent
        self.reason = reason
        self.conditions = conditions


def decide(fetch_query: str) -> FetchDecision:
    query = (fetch_query or "").lower()
    conditions = ["Use read-only SQL only", "Fetch from purchase return header/line tables"]

    if any(token in query for token in ("line", "lines", "item", "items", "product", "products", "details")):
        conditions.append("Line-level request: use RPD1 fields")
        return FetchDecision("purchase_return_line_fetch", "The request asks for return line/item details.", conditions)
    if any(token in query for token in ("open", "closed", "cancelled", "canceled")):
        conditions.append("Status request: map Open=DocStatus O, Closed=DocStatus C, Cancelled=CANCELED Y")
        return FetchDecision("purchase_return_status_fetch", "The request includes return status.", conditions)
    if any(token in query for token in ("vendor", "supplier", "cardcode")) or " v" in f" {query}":
        conditions.append("Vendor request: filter by CardCode when present")
        return FetchDecision("purchase_return_vendor_fetch", "The request targets a vendor/supplier return view.", conditions)
    if any(token in query for token in ("total", "amount", "value", "tax")):
        conditions.append("Amount request: include DocTotal and VatSum")
        return FetchDecision("purchase_return_amount_fetch", "The request asks for return amount information.", conditions)

    conditions.append("Header request: use ORPD and default to latest returns")
    return FetchDecision("purchase_return_header_fetch", "Default purchase return header fetch.", conditions)
