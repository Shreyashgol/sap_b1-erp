from typing import Any, TypedDict

from langchain_core.tools import StructuredTool
from langgraph.graph import END, StateGraph

from app.agents.purchase_team.purchase_invoice.supervisor_agent import execute as execute_ap_invoice
from app.agents.purchase_team.purchase_order.supervisor_agent import execute as execute_purchase_order
from app.agents.purchase_team.purchase_return.supervisor_agent import execute as execute_purchase_return
from app.agents.purchase_team.supervisor_agent import execute as purchase_team_execute
from app.agents.sales_team.supervisor_agent import execute as execute_sales
from app.agents.sales_team.supervisor_agent import routing_decision as sales_routing_decision
from app.config import BIG_SUPERVISOR_CLAUDE_API_KEY, BIG_SUPERVISOR_CLAUDE_MODEL
from app.crud.ap_invoice_crud import APInvoiceRepository
from app.crud.purchase_order_crud import PurchaseOrderRepository
from app.crud.purchase_return_crud import PurchaseReturnRepository
from app.crud.sales_crud import SalesRepository
from app.operations.ap_invoice_intent_parser import parse_ap_invoice_intent
from app.operations.claude_client import claude_chat_completion
from app.operations.conversation_memory import build_contextual_prompt
from app.operations.purchase_order_intent_parser import parse_purchase_order_intent
from app.operations.purchase_return_intent_parser import parse_purchase_return_intent
from app.operations.sales_intent_parser import parse_sales_intent
from app.schema.response import PurchaseTeamRoutingResponse


_BIG_SUPERVISOR_SYSTEM = """You are the Executive ERP Supervisor at Techative Pvt Ltd Solutions.
You oversee the Sales Team and the Purchase Team for SAP B1.

Your job is to classify the user request into ONE word only: sales OR purchase

SALES = sales orders, customers, AR invoices, sales returns, revenue, dispatch
PURCHASE = purchase orders, vendors, AP invoices, purchase returns, procurement

Reply with ONLY one word: sales OR purchase

"""


class BigSupervisorState(TypedDict, total=False):
    prompt: str
    conversation_history: list[dict[str, Any]]
    contextual_prompt: str
    team: str
    route_result: dict[str, Any]
    routing_decision: dict[str, Any]
    agent_response: Any
    api_response: dict[str, Any]
    status_code: int


def decide_team(prompt: str) -> str:
    if BIG_SUPERVISOR_CLAUDE_API_KEY:
        try:
            result = claude_chat_completion(
                [
                    {"role": "system", "content": _BIG_SUPERVISOR_SYSTEM},
                    {"role": "user", "content": prompt},
                ],
                temperature=0,
                max_tokens=5,
                timeout=30,
                api_key=BIG_SUPERVISOR_CLAUDE_API_KEY,
                model=BIG_SUPERVISOR_CLAUDE_MODEL,
            )
            team = result.strip().lower().split()[0]
            if team in {"purchase", "sales"}:
                return team
        except Exception:
            pass

    lowered = prompt.lower()
    sales_terms = ("sales", "customer", "ar invoice", "receivable", "sales order", "sales return", "revenue")
    purchase_terms = ("purchase", "vendor", "ap invoice", "payable", "purchase order", "purchase return", "supplier")
    sales_score = sum(term in lowered for term in sales_terms)
    purchase_score = sum(term in lowered for term in purchase_terms)
    return "sales" if sales_score > purchase_score else "purchase"


def _team_edge(state: BigSupervisorState) -> str:
    return state["team"]


def _purchase_document_edge(state: BigSupervisorState) -> str:
    return state["routing_decision"].get("documentType", "purchase_order")


def _normalize_response(response: Any) -> dict[str, Any]:
    if hasattr(response, "model_dump"):
        return response.model_dump()
    return dict(response)


def _prepare_context(state: BigSupervisorState) -> BigSupervisorState:
    return {
        **state,
        "contextual_prompt": build_contextual_prompt(
            state["prompt"],
            state.get("conversation_history"),
        ),
    }


def _classify_team(state: BigSupervisorState) -> BigSupervisorState:
    tool = StructuredTool.from_function(
        func=decide_team,
        name="big_supervisor_classify_team",
        description="Classify an SAP B1 prompt as a sales or purchase team request.",
    )
    return {**state, "team": tool.invoke({"prompt": state.get("contextual_prompt", state["prompt"])})}


def _route_sales(state: BigSupervisorState) -> BigSupervisorState:
    intent = parse_sales_intent(state.get("contextual_prompt", state["prompt"]))
    routing = sales_routing_decision(intent)
    return {
        **state,
        "route_result": {
            "team": "sales",
            "team_label": "Sales Team",
            "endpoint": "/sales/parse-and-execute",
            "routing_decision": routing,
        },
        "routing_decision": routing,
    }


def _route_purchase(state: BigSupervisorState) -> BigSupervisorState:
    purchase_response: PurchaseTeamRoutingResponse = purchase_team_execute(state.get("contextual_prompt", state["prompt"]))
    response_data = purchase_response.model_dump()["data"]
    routing = response_data["fetchAgent"]
    endpoints = {
        "purchase_order": "/purchase-orders/parse-and-execute",
        "ap_invoice": "/ap-invoices/parse-and-execute",
        "purchase_return": "/purchase-returns/parse-and-execute",
    }
    doc_type = routing.get("documentType", "purchase_order")
    return {
        **state,
        "route_result": {
            "team": "purchase",
            "team_label": "Purchase Team",
            "endpoint": endpoints.get(doc_type, "/purchase-orders/parse-and-execute"),
            "routing_decision": routing,
        },
        "routing_decision": routing,
    }


def _execute_sales(state: BigSupervisorState) -> BigSupervisorState:
    try:
        intent = parse_sales_intent(state.get("contextual_prompt", state["prompt"]))
        response = execute_sales(intent, SalesRepository())
        return {**state, "agent_response": response, "api_response": _normalize_response(response), "status_code": 200}
    except Exception as exc:
        return _capture_execution_error(state, exc)


def _execute_purchase_order(state: BigSupervisorState) -> BigSupervisorState:
    try:
        intent = parse_purchase_order_intent(state.get("contextual_prompt", state["prompt"]))
        response = execute_purchase_order(intent, PurchaseOrderRepository())
        return {**state, "agent_response": response, "api_response": _normalize_response(response), "status_code": 200}
    except Exception as exc:
        return _capture_execution_error(state, exc)


def _execute_ap_invoice(state: BigSupervisorState) -> BigSupervisorState:
    try:
        intent = parse_ap_invoice_intent(state.get("contextual_prompt", state["prompt"]))
        response = execute_ap_invoice(intent, APInvoiceRepository())
        return {**state, "agent_response": response, "api_response": _normalize_response(response), "status_code": 200}
    except Exception as exc:
        return _capture_execution_error(state, exc)


def _execute_purchase_return(state: BigSupervisorState) -> BigSupervisorState:
    try:
        intent = parse_purchase_return_intent(state.get("contextual_prompt", state["prompt"]))
        response = execute_purchase_return(intent, PurchaseReturnRepository())
        return {**state, "agent_response": response, "api_response": _normalize_response(response), "status_code": 200}
    except Exception as exc:
        return _capture_execution_error(state, exc)


def _capture_execution_error(state: BigSupervisorState, exc: Exception) -> BigSupervisorState:
    status_code = getattr(exc, "status_code", 500)
    detail = getattr(exc, "detail", f"Sub-agent execution error: {str(exc)}")
    return {**state, "status_code": status_code, "api_response": {"detail": detail}}


def _build_routing_graph():
    workflow = StateGraph(BigSupervisorState)
    workflow.add_node("prepare_context", _prepare_context)
    workflow.add_node("classify_team", _classify_team)
    workflow.add_node("route_sales", _route_sales)
    workflow.add_node("route_purchase", _route_purchase)
    workflow.set_entry_point("prepare_context")
    workflow.add_edge("prepare_context", "classify_team")
    workflow.add_conditional_edges("classify_team", _team_edge, {"sales": "route_sales", "purchase": "route_purchase"})
    workflow.add_edge("route_sales", END)
    workflow.add_edge("route_purchase", END)
    return workflow.compile()


def _build_execution_graph():
    workflow = StateGraph(BigSupervisorState)
    workflow.add_node("prepare_context", _prepare_context)
    workflow.add_node("classify_team", _classify_team)
    workflow.add_node("route_sales", _route_sales)
    workflow.add_node("route_purchase", _route_purchase)
    workflow.add_node("execute_sales", _execute_sales)
    workflow.add_node("execute_purchase_order", _execute_purchase_order)
    workflow.add_node("execute_ap_invoice", _execute_ap_invoice)
    workflow.add_node("execute_purchase_return", _execute_purchase_return)
    workflow.set_entry_point("prepare_context")
    workflow.add_edge("prepare_context", "classify_team")
    workflow.add_conditional_edges("classify_team", _team_edge, {"sales": "route_sales", "purchase": "route_purchase"})
    workflow.add_edge("route_sales", "execute_sales")
    workflow.add_conditional_edges(
        "route_purchase",
        _purchase_document_edge,
        {
            "purchase_order": "execute_purchase_order",
            "ap_invoice": "execute_ap_invoice",
            "purchase_return": "execute_purchase_return",
        },
    )
    workflow.add_edge("execute_sales", END)
    workflow.add_edge("execute_purchase_order", END)
    workflow.add_edge("execute_ap_invoice", END)
    workflow.add_edge("execute_purchase_return", END)
    return workflow.compile()


_ROUTING_GRAPH = _build_routing_graph()
_EXECUTION_GRAPH = _build_execution_graph()


def route(prompt: str, conversation_history: list[dict[str, Any]] | None = None) -> dict:
    state = _ROUTING_GRAPH.invoke({"prompt": prompt, "conversation_history": conversation_history or []})
    return state["route_result"]


def execute_prompt(prompt: str, conversation_history: list[dict[str, Any]] | None = None) -> BigSupervisorState:
    return _EXECUTION_GRAPH.invoke({"prompt": prompt, "conversation_history": conversation_history or []})
