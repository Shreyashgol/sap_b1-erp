from typing import Any, TypedDict

from langchain_core.tools import StructuredTool
from langgraph.graph import END, StateGraph

from app.agents.purchase_team.fetch_agent import decide
from app.schema.response import PurchaseTeamRoutingResponse


class PurchaseTeamRouterState(TypedDict, total=False):
    prompt: str
    decision: dict[str, Any]


def _build_purchase_router_graph():
    def call_router_tool(state: PurchaseTeamRouterState) -> PurchaseTeamRouterState:
        tool = StructuredTool.from_function(
            func=decide,
            name="purchase_team_route_request",
            description="Route a purchase request to the correct SAP B1 purchase document agent and action.",
        )
        return {**state, "decision": tool.invoke({"prompt": state["prompt"]})}

    workflow = StateGraph(PurchaseTeamRouterState)
    workflow.add_node("call_langchain_router_tool", call_router_tool)
    workflow.set_entry_point("call_langchain_router_tool")
    workflow.add_edge("call_langchain_router_tool", END)
    return workflow.compile()


_PURCHASE_ROUTER_GRAPH = _build_purchase_router_graph()


def execute(prompt: str) -> PurchaseTeamRoutingResponse:
    state = _PURCHASE_ROUTER_GRAPH.invoke({"prompt": prompt})
    decision = state["decision"]

    return PurchaseTeamRoutingResponse(
        status="routed",
        message=f"Supervisor routed request to {decision['subagent']}.",
        data={
            "supervisor": {
                "decision": f"Routing to {decision['subagent']}",
                "agent": "purchase_team_router",
                "documentType": decision["documentType"],
                "action": decision["action"],
                "workflow": "langgraph",
                "tool": "purchase_team_route_request",
            },
            "fetchAgent": decision,
        },
    )
