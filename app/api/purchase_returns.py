from fastapi import APIRouter, Depends, HTTPException

from app.agents.purchase_team.purchase_return.supervisor_agent import execute as execute_purchase_return_workflow
from app.crud.purchase_return_crud import PurchaseReturnRepository
from app.operations.purchase_return_intent_parser import parse_purchase_return_intent
from app.operations.utils import verify_jwt_token
from app.schema.purchase_return import PromptRequest
from app.schema.response import PurchaseReturnActionResponse


router = APIRouter()


@router.post("/parse-and-execute", response_model=PurchaseReturnActionResponse)
def parse_and_execute(request: PromptRequest, user: str = Depends(verify_jwt_token)):
    del user
    try:
        intent = parse_purchase_return_intent(request.prompt)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Intent parsing failed: {str(exc)}") from exc

    repository = PurchaseReturnRepository()
    return execute_purchase_return_workflow(intent, repository)
