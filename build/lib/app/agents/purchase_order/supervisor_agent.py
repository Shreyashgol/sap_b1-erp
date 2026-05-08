from fastapi import HTTPException

from app.operations.utils import load_agent_module


ACTION_AGENT_MAP = {
    "cancel": "cancel_agent",
    "close": "close_agent",
    "update": "update_agent",
    "fetch": "fetch_agent",
    "create": "create_po_agent",
}


def _resolve_agent_name(action: str) -> str:
    return ACTION_AGENT_MAP.get((action or "create").lower(), "create_po_agent")


def execute(intent, repository):
    action = (intent.action or "create").lower()
    agent_name = _resolve_agent_name(action)

    if action in {"cancel", "close", "update"} and not intent.docEntry and not getattr(intent, "mobileNumber", None):
        raise HTTPException(
            status_code=400,
            detail=f"Supervisor blocked {action}: DocEntry is required before calling {agent_name}.",
        )

    if action == "create" and not intent.cardCode:
        raise HTTPException(
            status_code=400,
            detail="Supervisor blocked create: vendor CardCode is required. Example: create a purchase order for vendor V100 with 10 units of ITEM001 at 50 each.",
        )

    if action == "create" and not intent.items:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Supervisor blocked create: at least one item with quantity is required for vendor {intent.cardCode}. "
                "Example: create a purchase order for vendor V100 with 10 units of APPLE at 50 each with tax code T1."
            ),
        )

    agent_module = load_agent_module(agent_name, "purchase_order")
    response = agent_module.execute(intent, repository)

    data = response.data or {}
    data["supervisor"] = {
        "decision": f"Routing to {agent_name}",
        "action": action,
        "agent": agent_name,
    }
    response.data = data
    return response
