from app.agents.purchase_team.supervisor_agent import execute as purchase_team_execute
from app.agents.sales_team.supervisor_agent import routing_decision as sales_routing_decision
from app.config import BIG_SUPERVISOR_GROQ_API_KEY, BIG_SUPERVISOR_GROQ_MODEL
from app.operations.groq_client import groq_chat_completion
from app.operations.sales_intent_parser import parse_sales_intent
from app.schema.response import PurchaseTeamRoutingResponse


_BIG_SUPERVISOR_SYSTEM = """You are the top-level SAP ERP supervisor.

Choose the correct team for the user request:
- purchase: vendor-side buying documents, purchase orders, AP invoices, purchase invoices, purchase returns.
- sales: customer-side selling documents, sales orders, AR invoices, sales invoices, sales returns, customers, revenue.

Reply with one lowercase word only: purchase or sales.
"""


def decide_team(prompt: str) -> str:
    result = groq_chat_completion(
        [
            {"role": "system", "content": _BIG_SUPERVISOR_SYSTEM},
            {"role": "user", "content": prompt},
        ],
        temperature=0,
        max_tokens=5,
        timeout=30,
        api_key=BIG_SUPERVISOR_GROQ_API_KEY,
        model=BIG_SUPERVISOR_GROQ_MODEL,
    )
    team = result.strip().lower().split()[0]
    if team not in {"purchase", "sales"}:
        raise ValueError(f"Big supervisor returned invalid team: {result}")
    return team


def route(prompt: str) -> dict:
    team = decide_team(prompt)

    if team == "sales":
        intent = parse_sales_intent(prompt)
        return {
            "team": "sales",
            "team_label": "Sales Team",
            "endpoint": "/sales/parse-and-execute",
            "routing_decision": sales_routing_decision(intent),
        }

    purchase_response: PurchaseTeamRoutingResponse = purchase_team_execute(prompt)
    response_data = purchase_response.model_dump()["data"]
    routing_decision = response_data["fetchAgent"]

    endpoints = {
        "purchase_order": "/purchase-orders/parse-and-execute",
        "ap_invoice": "/ap-invoices/parse-and-execute",
        "purchase_return": "/purchase-returns/parse-and-execute",
    }
    doc_type = routing_decision.get("documentType", "purchase_order")
    return {
        "team": "purchase",
        "team_label": "Purchase Team",
        "endpoint": endpoints.get(doc_type, "/purchase-orders/parse-and-execute"),
        "routing_decision": routing_decision,
    }
