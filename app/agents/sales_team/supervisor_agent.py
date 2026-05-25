from fastapi import HTTPException

from app.operations.utils import load_agent_module


ACTION_AGENT_MAP = {
    "create": "create_agent",
    "update": "update_agent",
    "cancel": "cancel_agent",
    "close": "close_agent",
    "fetch": "fetch_agent",
}

DOCUMENT_FOLDER_MAP = {
    "sales_order": "sales_order",
    "ar_invoice": "sales_invoice",
    "sales_return": "sales_return",
}


def routing_decision(intent) -> dict:
    agent_name = ACTION_AGENT_MAP.get((intent.action or "fetch").lower(), "fetch_agent")
    document_folder = DOCUMENT_FOLDER_MAP.get(intent.documentType, "sales_order")
    return {
        "action": intent.action,
        "documentType": intent.documentType,
        "documentAgent": "sales_team",
        "subagent": f"sales_team.{document_folder}.{agent_name}",
        "team": "sales",
        "reason": f"Sales Team routed {intent.action} {intent.documentType} to {agent_name}.",
    }


def execute(intent, repository):
    action = (intent.action or "fetch").lower()
    agent_name = ACTION_AGENT_MAP.get(action, "fetch_agent")
    document_folder = DOCUMENT_FOLDER_MAP.get(intent.documentType, "sales_order")

    if action in {"update", "cancel", "close"} and not intent.docEntry:
        raise HTTPException(status_code=400, detail=f"DocEntry is required before calling {agent_name}.")

    agent_module = load_agent_module(agent_name, f"sales_team/{document_folder}")
    response = agent_module.execute(intent, repository)

    data = response.data or {}
    data["supervisor"] = {
        "decision": f"Routing to {agent_name}",
        "action": action,
        "agent": agent_name,
        "documentType": intent.documentType,
    }
    if action != "fetch" and hasattr(repository, "table_names"):
        data["postgresql"] = {
            "database": "shared SAP agents PostgreSQL URL",
            "tableNames": repository.table_names(),
        }
    response.data = data
    return response
