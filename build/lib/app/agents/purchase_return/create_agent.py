from fastapi import HTTPException

from app.operations.error_handler import translate_sap_error
from app.schema.response import PurchaseReturnActionResponse


def execute(intent, repository) -> PurchaseReturnActionResponse:
    if not intent.cardCode:
        raise HTTPException(status_code=400, detail="Vendor code (CardCode) is required to create a purchase return")
    if not intent.items:
        raise HTTPException(status_code=400, detail="At least one item is required to create a purchase return")

    payload = {
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
                "BaseEntry": item.baseEntry,
                "BaseLine": item.baseLine,
            }
            for item in intent.items
        ],
    }

    try:
        result = repository.create_purchase_return(payload)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=translate_sap_error(str(exc))) from exc

    return PurchaseReturnActionResponse(
        status="created",
        message=f"🎉 Success! I've created a new Purchase Return for vendor **{intent.cardCode}**. The new document entry is **{result.get('DocEntry')}**.",
        docEntry=result.get("DocEntry"),
    )
