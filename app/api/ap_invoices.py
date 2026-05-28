from fastapi import APIRouter, Depends, HTTPException

from app.agents.purchase_team.purchase_invoice.supervisor_agent import execute as execute_ap_invoice_workflow
from app.crud.ap_invoice_crud import APInvoiceRepository
from app.operations.ap_invoice_intent_parser import parse_ap_invoice_intent
from app.operations.utils import verify_jwt_token
from app.schema.ap_invoice import PromptRequest
from app.schema.response import APInvoiceActionResponse


router = APIRouter()


@router.post("/parse-and-execute", response_model=APInvoiceActionResponse)
def parse_and_execute(request: PromptRequest, user: str = Depends(verify_jwt_token)):
    del user

    try:
        intent = parse_ap_invoice_intent(request.prompt)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Intent parsing failed: {str(exc)}") from exc

    repository = APInvoiceRepository()
    return execute_ap_invoice_workflow(intent, repository)
