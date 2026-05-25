from app.agents.purchase_team.supervisor_agent import execute as purchase_team_execute
from app.agents.sales_team.supervisor_agent import routing_decision as sales_routing_decision
from app.config import BIG_SUPERVISOR_CLAUDE_API_KEY, BIG_SUPERVISOR_CLAUDE_MODEL
from app.operations.claude_client import claude_chat_completion
from app.operations.sales_intent_parser import parse_sales_intent
from app.schema.response import PurchaseTeamRoutingResponse


_BIG_SUPERVISOR_SYSTEM = """You are the Executive ERP Supervisor at Techative Pvt Ltd Solutions.
You oversee the Sales Team and the Purchase Team for SAP B1.

Your job is to classify the user request into ONE word only: sales OR purchase

SALES = sales orders, customers, AR invoices, sales returns, revenue, dispatch
PURCHASE = purchase orders, vendors, AP invoices, purchase returns, procurement

Reply with ONLY one word: sales OR purchase

"""


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
