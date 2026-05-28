from typing import Any, Callable, TypedDict

from fastapi import HTTPException
from langchain_core.tools import StructuredTool
from langgraph.graph import END, StateGraph

from app.agents.sales_team.sales_invoice import cancel_agent as invoice_cancel_agent
from app.agents.sales_team.sales_invoice import close_agent as invoice_close_agent
from app.agents.sales_team.sales_invoice import create_agent as invoice_create_agent
from app.agents.sales_team.sales_invoice import fetch_agent as invoice_fetch_agent
from app.agents.sales_team.sales_invoice import update_agent as invoice_update_agent
from app.agents.sales_team.sales_order import cancel_agent as order_cancel_agent
from app.agents.sales_team.sales_order import close_agent as order_close_agent
from app.agents.sales_team.sales_order import create_agent as order_create_agent
from app.agents.sales_team.sales_order import fetch_agent as order_fetch_agent
from app.agents.sales_team.sales_order import update_agent as order_update_agent
from app.agents.sales_team.sales_return import cancel_agent as return_cancel_agent
from app.agents.sales_team.sales_return import close_agent as return_close_agent
from app.agents.sales_team.sales_return import create_agent as return_create_agent
from app.agents.sales_team.sales_return import fetch_agent as return_fetch_agent
from app.agents.sales_team.sales_return import update_agent as return_update_agent


class SalesWorkflowState(TypedDict, total=False):
    intent: Any
    repository: Any
    action: str
    document_type: str
    agent_name: str
    document_folder: str
    tool_name: str
    tool_fn: Callable[[Any, Any], Any]
    response: Any


SALES_AGENT_REGISTRY = {
    "sales_order": {
        "folder": "sales_order",
        "actions": {
            "create": ("create_agent", order_create_agent.execute),
            "update": ("update_agent", order_update_agent.execute),
            "cancel": ("cancel_agent", order_cancel_agent.execute),
            "close": ("close_agent", order_close_agent.execute),
            "fetch": ("fetch_agent", order_fetch_agent.execute),
        },
    },
    "ar_invoice": {
        "folder": "sales_invoice",
        "actions": {
            "create": ("create_agent", invoice_create_agent.execute),
            "update": ("update_agent", invoice_update_agent.execute),
            "cancel": ("cancel_agent", invoice_cancel_agent.execute),
            "close": ("close_agent", invoice_close_agent.execute),
            "fetch": ("fetch_agent", invoice_fetch_agent.execute),
        },
    },
    "sales_return": {
        "folder": "sales_return",
        "actions": {
            "create": ("create_agent", return_create_agent.execute),
            "update": ("update_agent", return_update_agent.execute),
            "cancel": ("cancel_agent", return_cancel_agent.execute),
            "close": ("close_agent", return_close_agent.execute),
            "fetch": ("fetch_agent", return_fetch_agent.execute),
        },
    },
}


def _select_tool(state: SalesWorkflowState) -> SalesWorkflowState:
    intent = state["intent"]
    action = (getattr(intent, "action", None) or "fetch").lower()
    document_type = getattr(intent, "documentType", None) or "sales_order"
    document_spec = SALES_AGENT_REGISTRY.get(document_type, SALES_AGENT_REGISTRY["sales_order"])
    agent_name, tool_fn = document_spec["actions"].get(action, document_spec["actions"]["fetch"])
    return {
        **state,
        "action": action,
        "document_type": document_type,
        "agent_name": agent_name,
        "document_folder": document_spec["folder"],
        "tool_name": f"sales_team_{document_spec['folder']}_{agent_name}",
        "tool_fn": tool_fn,
    }


def _validate(state: SalesWorkflowState) -> SalesWorkflowState:
    if state["action"] in {"update", "cancel", "close"} and not getattr(state["intent"], "docEntry", None):
        raise HTTPException(status_code=400, detail=f"DocEntry is required before calling {state['agent_name']}.")
    return state


def _call_tool(state: SalesWorkflowState) -> SalesWorkflowState:
    def run_agent():
        return state["tool_fn"](state["intent"], state["repository"])

    tool = StructuredTool.from_function(
        func=run_agent,
        name=state["tool_name"],
        description=f"Execute the SAP B1 sales {state['document_folder']} {state['agent_name']} tool.",
    )
    return {**state, "response": tool.invoke({})}


def _build_sales_workflow():
    workflow = StateGraph(SalesWorkflowState)
    workflow.add_node("select_tool", _select_tool)
    workflow.add_node("validate", _validate)
    workflow.add_node("call_langchain_tool", _call_tool)
    workflow.set_entry_point("select_tool")
    workflow.add_edge("select_tool", "validate")
    workflow.add_edge("validate", "call_langchain_tool")
    workflow.add_edge("call_langchain_tool", END)
    return workflow.compile()


_SALES_WORKFLOW = _build_sales_workflow()


def routing_decision(intent) -> dict:
    state = _select_tool({"intent": intent, "repository": None})
    return {
        "action": state["action"],
        "documentType": state["document_type"],
        "documentAgent": "sales_team",
        "subagent": f"sales_team.{state['document_folder']}.{state['agent_name']}",
        "team": "sales",
        "workflow": "langgraph",
        "tool": state["tool_name"],
        "reason": f"Sales Team routed {state['action']} {state['document_type']} to {state['agent_name']}.",
    }


def execute(intent, repository):
    state = _SALES_WORKFLOW.invoke({"intent": intent, "repository": repository})
    response = state["response"]

    data = response.data or {}
    data["supervisor"] = {
        "decision": f"Routing to {state['agent_name']}",
        "action": state["action"],
        "agent": state["agent_name"],
        "documentType": state["document_type"],
        "workflow": "langgraph",
        "tool": state["tool_name"],
    }
    if state["action"] != "fetch" and hasattr(repository, "table_names"):
        data["postgresql"] = {
            "database": "shared SAP agents PostgreSQL URL",
            "tableNames": repository.table_names(),
        }
    response.data = data
    return response
