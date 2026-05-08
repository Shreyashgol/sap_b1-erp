from fastapi import HTTPException

from app.operations.error_handler import translate_sap_error
from app.schema.response import PurchaseReturnActionResponse


def execute(intent, repository) -> PurchaseReturnActionResponse:
    if not intent.docEntry:
        raise HTTPException(status_code=400, detail="DocEntry is required to cancel a purchase return")
    try:
        repository.cancel_purchase_return(intent.docEntry)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=translate_sap_error(str(exc))) from exc
    return PurchaseReturnActionResponse(status="cancelled", message=f"✅ Got it! Purchase Return **{intent.docEntry}** has been successfully cancelled in the system.", docEntry=intent.docEntry)
