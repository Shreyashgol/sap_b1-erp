from fastapi import HTTPException

from app.operations.error_handler import translate_sap_error
from app.schema.response import APInvoiceActionResponse


def execute(intent, repository) -> APInvoiceActionResponse:
    if not intent.docEntry:
        raise HTTPException(
            status_code=400,
            detail="DocEntry is required to update an AP invoice. Example: 'Update AP invoice 5001'",
        )

    payload = {}
    if intent.cardCode:
        payload["CardCode"] = intent.cardCode
    if intent.items:
        payload["DocumentLines"] = [
            {
                "ItemCode": item.itemCode,
                "Quantity": item.quantity,
                "UnitPrice": item.unitPrice,
                "TaxCode": item.taxCode,
            }
            for item in intent.items
        ]

    if not payload:
        raise HTTPException(status_code=400, detail="No AP invoice fields were provided for update")

    try:
        repository.update_ap_invoice(intent.docEntry, payload)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=translate_sap_error(str(exc))) from exc

    return APInvoiceActionResponse(
        status="updated",
        message=f"✏️ Success! I've updated the details for AP Invoice **{intent.docEntry}**.",
        docEntry=intent.docEntry,
    )
