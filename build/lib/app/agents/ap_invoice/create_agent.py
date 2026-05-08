from fastapi import HTTPException

from app.operations.error_handler import translate_sap_error
from app.schema.ap_invoice import APInvoiceCreatePayload
from app.schema.response import APInvoiceActionResponse


def execute(intent, repository) -> APInvoiceActionResponse:
    if not intent.cardCode:
        raise HTTPException(status_code=400, detail="Vendor code (CardCode) is required to create an AP invoice")

    if not intent.items:
        raise HTTPException(status_code=400, detail="At least one invoice line item is required")

    invoice_payload = APInvoiceCreatePayload(
        CardCode=intent.cardCode,
        DocumentLines=[
            {
                "ItemCode": item.itemCode,
                "Quantity": item.quantity,
                "UnitPrice": item.unitPrice,
                "TaxCode": item.taxCode,
            }
            for item in intent.items
        ],
    ).model_dump(exclude_none=True)

    try:
        result = repository.create_ap_invoice(invoice_payload)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=translate_sap_error(str(exc))) from exc

    return APInvoiceActionResponse(
        status="created",
        message=f"🎉 Success! I've created a new AP Invoice for vendor **{intent.cardCode}**. The new document entry is **{result.get('DocEntry')}**.",
        docEntry=result.get("DocEntry"),
        data=result,
    )
