from fastapi import HTTPException

from app.operations.error_handler import translate_sap_error
from app.schema.response import PurchaseOrderActionResponse


def execute(intent, repository) -> PurchaseOrderActionResponse:
    if not intent.cardCode:
        raise HTTPException(status_code=400, detail="Vendor code (CardCode) is required to create a purchase order")
    if not intent.items:
        raise HTTPException(
            status_code=400,
            detail=(
                "At least one line item is required to create a purchase order. "
                "Example: create a purchase order for vendor V100 with 10 units of ITEM001 at 50 each with tax code T1"
            ),
        )

    po_payload = {
        "CardCode": intent.cardCode,
        "DocDate": intent.docDate,
        "DocDueDate": intent.docDueDate,
        "TaxDate": intent.taxDate or intent.docDueDate,
        "DocumentLines": [
            {
                "ItemCode": item.itemCode,
                "Quantity": item.quantity,
                "UnitPrice": item.unitPrice,
                "TaxCode": item.taxCode,
            }
            for item in (intent.items or [])
        ],
    }

    try:
        result = repository.create_purchase_order(po_payload)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=translate_sap_error(str(exc))) from exc

    return PurchaseOrderActionResponse(
        status="created",
        message=f"🎉 Awesome! I've successfully created a new Purchase Order for vendor **{intent.cardCode}**. The new document entry is **{result.get('DocEntry')}**.",
        docEntry=result.get("DocEntry"),
    )
