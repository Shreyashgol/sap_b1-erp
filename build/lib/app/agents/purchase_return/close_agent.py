from fastapi import HTTPException

from app.operations.error_handler import translate_sap_error
from app.schema.response import PurchaseReturnActionResponse


def execute(intent, repository) -> PurchaseReturnActionResponse:
    if not intent.docEntry:
        raise HTTPException(status_code=400, detail="DocEntry is required to close a purchase return")
    try:
        repository.close_purchase_return(intent.docEntry)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=translate_sap_error(str(exc))) from exc
    return PurchaseReturnActionResponse(status="closed", message=f"🔒 All done! Purchase Return **{intent.docEntry}** is now closed.", docEntry=intent.docEntry)
