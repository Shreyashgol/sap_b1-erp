from fastapi import HTTPException

from app.operations.error_handler import translate_sap_error
from app.schema.response import PurchaseOrderActionResponse


def execute(intent, repository) -> PurchaseOrderActionResponse:
    if intent.mobileNumber:
        raise HTTPException(
            status_code=400,
            detail="Cancel by mobile number not yet implemented. Please provide DocEntry directly.",
        )

    if not intent.docEntry:
        raise HTTPException(
            status_code=400,
            detail="DocEntry is required to cancel a purchase order. Example: 'Cancel purchase order 12345'",
        )

    try:
        repository.cancel_purchase_order(intent.docEntry)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=translate_sap_error(str(exc))) from exc

    return PurchaseOrderActionResponse(
        status="cancelled",
        message=f"✅ Got it! Purchase Order **{intent.docEntry}** has been successfully cancelled in the system.",
        docEntry=intent.docEntry,
    )
