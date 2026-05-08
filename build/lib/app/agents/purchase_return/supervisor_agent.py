from fastapi import HTTPException

from app.operations.utils import load_agent_module


ACTION_AGENT_MAP = {
    "cancel": "cancel_agent",
    "close": "close_agent",
    "reopen": "reopen_agent",
    "update": "update_agent",
    "fetch": "fetch_agent",
    "create": "create_agent",
}


def execute(intent, repository):
    action = (intent.action or "create").lower()
    agent_name = ACTION_AGENT_MAP.get(action, "create_agent")

    if action in {"cancel", "close", "reopen", "update"} and not intent.docEntry:
        raise HTTPException(status_code=400, detail=f"Supervisor blocked {action}: DocEntry is required.")
    if action == "create" and (not intent.cardCode or not intent.items):
        raise HTTPException(status_code=400, detail="Supervisor blocked create: vendor CardCode and at least one item are required.")

    response = load_agent_module(agent_name, "purchase_return").execute(intent, repository)
    data = response.data or {}
    data["supervisor"] = {"decision": f"Routing to {agent_name}", "action": action, "agent": agent_name}
    response.data = data
    return response
