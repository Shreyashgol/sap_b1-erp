import json
from typing import Any, Dict, TypedDict

from langgraph.graph import END, StateGraph

from app.agents.supervisor.fetch_agent import decide
from app.operations.llm_client import chat_completion

CLASSIFIER_PROMPT_TEMPLATE = """
You are the Supervisor Router for a SAP B1 Multi-Agent System.
Your job is to read the user's request and classify the action and the target document type.

Return ONLY raw JSON - no markdown, no explanation.

Rules for Document Type:
1. "purchase_order": if the user mentions purchase order, PO, order.
2. "ap_invoice": if the user mentions AP invoice, purchase invoice, invoice, bill.
3. "purchase_return": if the user mentions purchase return, goods return, vendor return, or returning goods.
If ambiguous, default to "purchase_order".

Rules for Action:
1. "create": create, place, make, add, new
2. "update": update, modify, change, edit
3. "fetch": get, fetch, show, find, lookup, query, tell me, how many, total, give, list, display, retrieve
4. "cancel": cancel, void, reverse, delete, abort
5. "close": close, complete, finish, mark as done
6. "reopen": reopen, open again, reactivate
If ambiguous, default to "create".

Output format exactly like this:
{{
    "document_type": "...",
    "action": "...",
    "reason": "Brief reason for this classification"
}}

User request: {user_prompt}
"""


class SupervisorState(TypedDict, total=False):
    prompt: str
    document_type: str
    action: str
    reason: str
    routing_decision: Dict[str, Any]
    error: str


def classifier_node(state: SupervisorState) -> SupervisorState:
    formatted_prompt = CLASSIFIER_PROMPT_TEMPLATE.format(user_prompt=state["prompt"])

    try:
        raw = chat_completion(
            [{"role": "user", "content": formatted_prompt}],
            temperature=0.1,
            max_tokens=2048,
            timeout=120,
        )

        if "```" in raw:
            for block in raw.split("```"):
                block = block.strip().lstrip("json").strip()
                if block.startswith("{"):
                    raw = block
                    break

        parsed = json.loads(raw)

        doc_type = parsed.get("document_type", "purchase_order")
        action = parsed.get("action", "create")
        reason = parsed.get("reason", "Inferred from prompt")

        if doc_type not in ["purchase_order", "ap_invoice", "purchase_return"]:
            doc_type = "purchase_order"
        if action not in ["create", "update", "fetch", "cancel", "close", "reopen"]:
            action = "create"

        return {"document_type": doc_type, "action": action, "reason": reason, "error": ""}
    except Exception as exc:
        fallback = decide(state["prompt"])
        return {
            "document_type": fallback["documentType"],
            "action": fallback["action"],
            "reason": f"Routed with local keyword fallback after Ollama classifier failure: {exc}",
            "error": "",
        }


def router_node(state: SupervisorState) -> SupervisorState:
    if state.get("error"):
        return state

    action = state.get("action", "create")
    document_type = state.get("document_type", "purchase_order")

    document_agent = {
        "purchase_order": "purchase_order_agent",
        "ap_invoice": "ap_invoice_agent",
        "purchase_return": "purchase_return_agent",
    }.get(document_type, "purchase_order_agent")

    routing_decision = {
        "action": action,
        "documentType": document_type,
        "documentAgent": document_agent,
        "subagent": f"{document_agent}.{action}_agent",
        "reason": state.get("reason", ""),
        "conditions": [
            "Supervisor must choose document type before document action",
            "Fetch actions must use text-to-SQL and read-only database execution",
            "Create/update/close/cancel actions require document-agent validation before SAP call",
        ],
    }
    return {"routing_decision": routing_decision}


workflow = StateGraph(SupervisorState)
workflow.add_node("classifier", classifier_node)
workflow.add_node("router", router_node)

workflow.set_entry_point("classifier")
workflow.add_edge("classifier", "router")
workflow.add_edge("router", END)

supervisor_app = workflow.compile()
