from fastapi import HTTPException

from app.operations.error_handler import translate_sap_error
from app.schema.response import PurchaseReturnActionResponse


def execute(intent, repository) -> PurchaseReturnActionResponse:
    if not intent.docEntry:
        raise HTTPException(status_code=400, detail="DocEntry is required to update a purchase return")

    payload = {}
    if getattr(intent, "comments", None):
        payload["Comments"] = intent.comments
    if intent.cardCode:
        payload["CardCode"] = intent.cardCode
    if intent.items:
        payload["DocumentLines"] = [
            {
                "ItemCode": item.itemCode,
                "Quantity": item.quantity,
                "UnitPrice": item.unitPrice,
                "TaxCode": item.taxCode,
                "BaseEntry": item.baseEntry,
                "BaseLine": item.baseLine,
            }
            for item in intent.items
        ]
    if not payload:
        raise HTTPException(status_code=400, detail="No purchase return fields were provided for update")
    try:
        repository.update_purchase_return(intent.docEntry, payload)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=translate_sap_error(str(exc))) from exc
    return PurchaseReturnActionResponse(status="updated", message=f"✏️ Success! I've updated the details for Purchase Return **{intent.docEntry}**.", docEntry=intent.docEntry)
