from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Any, Dict

from app.agents.big_supervisor_agent import route as big_supervisor_route
from app.chat_response import generate_chat_response
from app.crud.sales_crud import SalesRepository
from app.operations.sales_intent_parser import parse_sales_intent
from app.crud.purchase_order_crud import PurchaseOrderRepository
from app.operations.purchase_order_intent_parser import parse_purchase_order_intent
from app.crud.ap_invoice_crud import APInvoiceRepository
from app.operations.ap_invoice_intent_parser import parse_ap_invoice_intent
from app.crud.purchase_return_crud import PurchaseReturnRepository
from app.operations.purchase_return_intent_parser import parse_purchase_return_intent
from app.operations.utils import load_agent_module

router = APIRouter()


class ChatRequest(BaseModel):
    prompt: str


class ChatResponse(BaseModel):
    reply: str
    team: str
    routing: Dict[str, Any]
    api_response: Dict[str, Any]
    status_code: int


@router.post("", response_model=ChatResponse)
def execute_chat(request: ChatRequest):
    prompt = request.prompt.strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="Prompt is required")

    try:
        # Step 1: Big Supervisor routes the request to sales or purchase team
        big_result = big_supervisor_route(prompt)
        team = big_result["team"]
        routing_decision = big_result["routing_decision"]
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Big Supervisor routing failed: {str(exc)}"
        ) from exc

    status_code = 200
    api_response_data = {}

    try:
        # Step 2: Route and execute the sub-agents
        if team == "sales":
            intent = parse_sales_intent(prompt)
            repository = SalesRepository()
            agent_module = load_agent_module("supervisor_agent", "sales_team")
            agent_response = agent_module.execute(intent, repository)
            if hasattr(agent_response, "model_dump"):
                api_response_data = agent_response.model_dump()
            else:
                api_response_data = dict(agent_response)

        else:  # purchase team
            doc_type = routing_decision.get("documentType", "purchase_order")
            if doc_type == "ap_invoice":
                intent = parse_ap_invoice_intent(prompt)
                repository = APInvoiceRepository()
                agent_module = load_agent_module(
                    "supervisor_agent", "purchase_team/purchase_invoice"
                )
                agent_response = agent_module.execute(intent, repository)
            elif doc_type == "purchase_return":
                intent = parse_purchase_return_intent(prompt)
                repository = PurchaseReturnRepository()
                agent_module = load_agent_module(
                    "supervisor_agent", "purchase_team/purchase_return"
                )
                agent_response = agent_module.execute(intent, repository)
            else:  # default to purchase_order
                intent = parse_purchase_order_intent(prompt)
                repository = PurchaseOrderRepository()
                agent_module = load_agent_module(
                    "supervisor_agent", "purchase_team/purchase_order"
                )
                agent_response = agent_module.execute(intent, repository)

            if hasattr(agent_response, "model_dump"):
                api_response_data = agent_response.model_dump()
            else:
                api_response_data = dict(agent_response)

    except HTTPException as exc:
        # Capture API-level validation errors (e.g. 400 Bad Request, 404 Not Found)
        status_code = exc.status_code
        api_response_data = {"detail": exc.detail}
    except Exception as exc:
        status_code = 500
        api_response_data = {"detail": f"Sub-agent execution error: {str(exc)}"}

    try:
        # Step 3: Generate the final friendly chatbot response (using Claude)
        assistant_reply = generate_chat_response(
            prompt=prompt,
            routing_decision=routing_decision,
            api_response=api_response_data,
            status_code=status_code,
        )
    except Exception as exc:
        # Fallback if final reply synthesis fails
        assistant_reply = (
            f"I encountered an error synthesizing the final response: {str(exc)}.\n\n"
            f"Technical Details: {api_response_data.get('detail', str(api_response_data))}"
        )

    return ChatResponse(
        reply=assistant_reply,
        team=team,
        routing=routing_decision,
        api_response=api_response_data,
        status_code=status_code,
    )
