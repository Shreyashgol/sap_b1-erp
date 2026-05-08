ACTION_KEYWORDS = {
    "cancel": ("cancel", "void", "reverse", "delete", "abort"),
    "close": ("close", "complete", "finish", "mark as done", "fulfill"),
    "reopen": ("reopen", "open again", "reactivate"),
    "update": ("update", "modify", "change", "edit"),
    "fetch": ("get", "fetch", "show", "find", "lookup", "query", "tell me", "how many", "total", "give", "list", "display", "retrieve"),
}


def _detect_action(prompt: str) -> str:
    lowered = prompt.lower()
    for action, keywords in ACTION_KEYWORDS.items():
        if any(keyword in lowered for keyword in keywords):
            return action
    return "create"


def _detect_document_type(prompt: str) -> str:
    lowered = prompt.lower()
    if any(token in lowered for token in ("ap invoice", "purchase invoice", "invoice", "bill")):
        return "ap_invoice"
    if any(token in lowered for token in ("purchase return", "return", "goods return", "vendor return")):
        return "purchase_return"
    return "purchase_order"


def decide(prompt: str) -> dict:
    action = _detect_action(prompt)
    document_type = _detect_document_type(prompt)
    document_agent = {
        "purchase_order": "purchase_order_agent",
        "ap_invoice": "ap_invoice_agent",
        "purchase_return": "purchase_return_agent",
    }[document_type]

    return {
        "action": action,
        "documentType": document_type,
        "documentAgent": document_agent,
        "subagent": f"{document_agent}.{action}_agent",
        "conditions": [
            "Supervisor must choose document type before document action",
            "Fetch actions must use text-to-SQL and read-only database execution",
            "Create/update/close/cancel actions require document-agent validation before SAP call",
        ],
    }
