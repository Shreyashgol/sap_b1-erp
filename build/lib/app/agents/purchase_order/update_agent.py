from fastapi import HTTPException

from app.operations.error_handler import translate_sap_error
from app.schema.response import PurchaseOrderActionResponse


def execute(intent, repository) -> PurchaseOrderActionResponse:
    if not intent.docEntry:
        raise HTTPException(
            status_code=400,
            detail="DocEntry is required to update a purchase order. Example: 'Update purchase order 12345'",
        )

    po_payload = {}
    if intent.docDate:
        po_payload["DocDate"] = intent.docDate
    if intent.docDueDate:
        po_payload["DocDueDate"] = intent.docDueDate
    if intent.taxDate:
        po_payload["TaxDate"] = intent.taxDate
        
    if not po_payload:
        raise HTTPException(
            status_code=400, 
            detail="No valid fields provided to update for the purchase order."
        )

    try:
        repository.update_purchase_order(intent.docEntry, po_payload)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=translate_sap_error(str(exc))) from exc

    return PurchaseOrderActionResponse(
        status="updated",
        message=f"✏️ Success! I've updated the details for Purchase Order **{intent.docEntry}**.",
        docEntry=intent.docEntry,
    )
