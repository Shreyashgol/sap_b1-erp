from fastapi import APIRouter, Depends, HTTPException

from app.crud.purchase_return_crud import PurchaseReturnRepository
from app.operations.purchase_return_intent_parser import parse_purchase_return_intent
from app.operations.utils import load_agent_module, verify_jwt_token
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
    return load_agent_module("supervisor_agent", "purchase_return").execute(intent, repository)
