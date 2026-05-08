from fastapi import APIRouter, Depends, HTTPException

from app.crud.purchase_order_crud import PurchaseOrderRepository
from app.operations.bulk_upload import execute_bulk_purchase_orders
from app.operations.document_reader import extract_document_text
from app.operations.purchase_order_intent_parser import parse_purchase_order_intent
from app.operations.utils import load_agent_module, verify_jwt_token
from app.schema.purchase_order import BulkPurchaseOrderUploadRequest, OCRDocumentRequest, PromptRequest
from app.schema.response import PurchaseOrderActionResponse

router = APIRouter()


def _resolve_agent_name(action: str) -> str:
    action_map = {
        "cancel": "cancel_agent",
        "close": "close_agent",
        "update": "update_agent",
        "fetch": "fetch_agent",
    }
    return action_map.get(action, "create_po_agent")


@router.post("/parse-and-execute", response_model=PurchaseOrderActionResponse)
def parse_and_act_on_purchase_order(request: PromptRequest,user: str = Depends(verify_jwt_token)):
    del user

    try:
        intent = parse_purchase_order_intent(request.prompt)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Intent parsing failed: {str(exc)}") from exc

    repository = PurchaseOrderRepository()
    agent_module = load_agent_module("supervisor_agent", "purchase_order")
    return agent_module.execute(intent, repository)


@router.post("/ocr-read", response_model=PurchaseOrderActionResponse)
def ocr_read_document(request: OCRDocumentRequest, user: str = Depends(verify_jwt_token)):
    del user

    try:
        extracted_text = extract_document_text(request.filename, request.content_base64)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Document OCR failed: {str(exc)}") from exc

    return PurchaseOrderActionResponse(
        status="success",
        message="Document text extracted successfully.",
        data={
            "filename": request.filename,
            "extractedText": extracted_text,
        },
    )


@router.post("/bulk-upload", response_model=PurchaseOrderActionResponse)
def bulk_upload_purchase_orders(request: BulkPurchaseOrderUploadRequest, user: str = Depends(verify_jwt_token)):
    del user

    repository = PurchaseOrderRepository()
    try:
        result = execute_bulk_purchase_orders(
            repository,
            filename=request.filename,
            content_base64=request.content_base64,
            dry_run=request.dryRun,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Bulk purchase order upload failed: {str(exc)}") from exc

    mode_text = "validated" if request.dryRun else "processed"
    return PurchaseOrderActionResponse(
        status="success",
        message=f"Bulk purchase order file {mode_text} successfully.",
        data=result,
    )
