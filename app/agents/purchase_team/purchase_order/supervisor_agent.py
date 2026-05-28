from app.agents.purchase_team.langgraph_workflow import (
    build_purchase_document_workflow,
    purchase_order_create_rules,
)
from app.agents.purchase_team.purchase_order import cancel_agent, close_agent, create_po_agent, fetch_agent, update_agent


ACTION_AGENT_MAP = {
    "cancel": "cancel_agent",
    "close": "close_agent",
    "update": "update_agent",
    "fetch": "fetch_agent",
    "create": "create_po_agent",
}

ACTION_TOOLS = {
    "cancel_agent": cancel_agent.execute,
    "close_agent": close_agent.execute,
    "update_agent": update_agent.execute,
    "fetch_agent": fetch_agent.execute,
    "create_po_agent": create_po_agent.execute,
}


execute = build_purchase_document_workflow(
    agent_folder="purchase_team/purchase_order",
    action_agent_map=ACTION_AGENT_MAP,
    action_tools=ACTION_TOOLS,
    default_action="create",
    default_agent="create_po_agent",
    validation_rules=purchase_order_create_rules,
)
