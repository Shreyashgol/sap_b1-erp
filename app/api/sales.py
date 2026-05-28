from fastapi import APIRouter, Depends, HTTPException

from app.crud.sales_crud import SalesRepository
from app.agents.sales_team.supervisor_agent import execute as execute_sales_workflow
from app.operations.sales_intent_parser import parse_sales_intent
from app.operations.utils import verify_jwt_token
from app.schema.purchase_order import PromptRequest
from app.schema.response import SalesActionResponse

router = APIRouter()


@router.post("/parse-and-execute", response_model=SalesActionResponse)
def sales_parse_and_execute(request: PromptRequest, user: str = Depends(verify_jwt_token)):
    del user

    try:
        intent = parse_sales_intent(request.prompt)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Sales intent parsing failed: {str(exc)}") from exc

    try:
        repository = SalesRepository()
        return execute_sales_workflow(intent, repository)
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Sales execution failed: {str(exc)}") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Sales execution error: {str(exc)}") from exc
