from fastapi import APIRouter, Depends, HTTPException

from app.agents.purchase_team.purchase_order.supervisor_agent import execute as execute_purchase_order_workflow
from app.crud.purchase_order_crud import PurchaseOrderRepository
from app.operations.purchase_order_intent_parser import parse_purchase_order_intent
from app.operations.utils import verify_jwt_token
from app.schema.purchase_order import PromptRequest
from app.schema.response import PurchaseOrderActionResponse

router = APIRouter()


@router.post("/parse-and-execute", response_model=PurchaseOrderActionResponse)
def parse_and_act_on_purchase_order(request: PromptRequest,user: str = Depends(verify_jwt_token)):
    del user

    try:
        intent = parse_purchase_order_intent(request.prompt)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Intent parsing failed: {str(exc)}") from exc

    repository = PurchaseOrderRepository()
    return execute_purchase_order_workflow(intent, repository)
