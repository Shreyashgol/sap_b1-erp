from fastapi import HTTPException

from app.operations.error_handler import translate_sap_error
from app.schema.response import APInvoiceActionResponse


def execute(intent, repository) -> APInvoiceActionResponse:
    if not intent.docEntry:
        raise HTTPException(
            status_code=400,
            detail="DocEntry is required to close an AP invoice. Example: 'Close AP invoice 5001'",
        )

    try:
        repository.close_ap_invoice(intent.docEntry)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=translate_sap_error(str(exc))) from exc

    return APInvoiceActionResponse(
        status="closed",
        message=f"🔒 All done! AP Invoice **{intent.docEntry}** is now closed.",
        docEntry=intent.docEntry,
    )
