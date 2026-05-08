from fastapi import HTTPException

from app.operations.error_handler import translate_sap_error
from app.schema.response import PurchaseReturnActionResponse


def execute(intent, repository) -> PurchaseReturnActionResponse:
    if not intent.docEntry:
        raise HTTPException(status_code=400, detail="DocEntry is required to reopen a purchase return")
    try:
        repository.reopen_purchase_return(intent.docEntry)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=translate_sap_error(str(exc))) from exc
    return PurchaseReturnActionResponse(
        status="reopened",
        message=f"🔓 Done! Purchase Return **{intent.docEntry}** has been reopened and is ready for further action.",
        docEntry=intent.docEntry,
    )
