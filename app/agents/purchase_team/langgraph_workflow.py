from typing import Any, Callable, Dict, Iterable, Optional, TypedDict

from fastapi import HTTPException
from langchain_core.tools import StructuredTool
from langgraph.graph import END, StateGraph


class PurchaseWorkflowState(TypedDict, total=False):
    intent: Any
    repository: Any
    action: str
    agent_name: str
    response: Any


ValidationRule = Callable[[Any, str, str], Optional[str]]
AgentTool = Callable[[Any, Any], Any]


def _requires_doc_entry(actions: Iterable[str]) -> ValidationRule:
    required_actions = set(actions)

    def validate(intent: Any, action: str, agent_name: str) -> Optional[str]:
        if action in required_actions and not getattr(intent, "docEntry", None):
            return f"Supervisor blocked {action}: DocEntry is required before calling {agent_name}."
        return None

    return validate


def _requires_doc_entry_or_mobile(actions: Iterable[str]) -> ValidationRule:
    required_actions = set(actions)

    def validate(intent: Any, action: str, agent_name: str) -> Optional[str]:
        if action in required_actions and not getattr(intent, "docEntry", None) and not getattr(intent, "mobileNumber", None):
            return f"Supervisor blocked {action}: DocEntry is required before calling {agent_name}."
        return None

    return validate


def _requires_vendor_and_items(message: str) -> ValidationRule:
    def validate(intent: Any, action: str, agent_name: str) -> Optional[str]:
        if action == "create" and (not getattr(intent, "cardCode", None) or not getattr(intent, "items", None)):
            return message
        return None

    return validate


def _requires_purchase_order_create_fields(intent: Any, action: str, agent_name: str) -> Optional[str]:
    if action != "create":
        return None
    if not getattr(intent, "cardCode", None):
        return (
            "Supervisor blocked create: vendor CardCode is required. Example: create a purchase order "
            "for vendor V100 with 10 units of ITEM001 at 50 each."
        )
    if not getattr(intent, "items", None):
        return (
            f"Supervisor blocked create: at least one item with quantity is required for vendor {intent.cardCode}. "
            "Example: create a purchase order for vendor V100 with 10 units of APPLE at 50 each with tax code T1."
        )
    return None


def _build_agent_tool(
    agent_name: str,
    agent_folder: str,
    tool_fn: AgentTool,
    intent: Any,
    repository: Any,
) -> StructuredTool:
    def run_agent() -> Any:
        return tool_fn(intent, repository)

    tool_name = f"{agent_folder.replace('/', '_')}_{agent_name}"
    return StructuredTool.from_function(
        func=run_agent,
        name=tool_name,
        description=f"Execute the SAP B1 {agent_folder} {agent_name} tool.",
    )


def build_purchase_document_workflow(
    *,
    agent_folder: str,
    action_agent_map: Dict[str, str],
    action_tools: Dict[str, AgentTool],
    default_action: str,
    default_agent: str,
    validation_rules: Iterable[ValidationRule],
):
    def resolve_agent_name(action: str) -> str:
        return action_agent_map.get((action or default_action).lower(), default_agent)

    def select_tool(state: PurchaseWorkflowState) -> PurchaseWorkflowState:
        intent = state["intent"]
        action = (getattr(intent, "action", None) or default_action).lower()
        return {**state, "action": action, "agent_name": resolve_agent_name(action)}

    def validate(state: PurchaseWorkflowState) -> PurchaseWorkflowState:
        intent = state["intent"]
        action = state["action"]
        agent_name = state["agent_name"]
        for rule in validation_rules:
            message = rule(intent, action, agent_name)
            if message:
                raise HTTPException(status_code=400, detail=message)
        return state

    def call_tool(state: PurchaseWorkflowState) -> PurchaseWorkflowState:
        tool = _build_agent_tool(
            state["agent_name"],
            agent_folder,
            action_tools[state["agent_name"]],
            state["intent"],
            state["repository"],
        )
        return {**state, "response": tool.invoke({})}

    workflow = StateGraph(PurchaseWorkflowState)
    workflow.add_node("select_tool", select_tool)
    workflow.add_node("validate", validate)
    workflow.add_node("call_langchain_tool", call_tool)
    workflow.set_entry_point("select_tool")
    workflow.add_edge("select_tool", "validate")
    workflow.add_edge("validate", "call_langchain_tool")
    workflow.add_edge("call_langchain_tool", END)

    graph = workflow.compile()

    def execute(intent: Any, repository: Any) -> Any:
        state = graph.invoke({"intent": intent, "repository": repository})
        response = state["response"]
        data = response.data or {}
        data["supervisor"] = {
            "decision": f"Routing to {state['agent_name']}",
            "action": state["action"],
            "agent": state["agent_name"],
            "workflow": "langgraph",
            "tool": f"{agent_folder.replace('/', '_')}_{state['agent_name']}",
        }
        response.data = data
        return response

    return execute


purchase_order_create_rules = (
    _requires_doc_entry_or_mobile({"cancel", "close", "update"}),
    _requires_purchase_order_create_fields,
)

purchase_invoice_create_rules = (
    _requires_doc_entry({"cancel", "close", "reopen", "update"}),
    _requires_vendor_and_items("Supervisor blocked create: vendor CardCode and at least one item are required."),
)

purchase_return_create_rules = (
    _requires_doc_entry({"cancel", "close", "reopen", "update"}),
    _requires_vendor_and_items("Supervisor blocked create: vendor CardCode and at least one item are required."),
)
