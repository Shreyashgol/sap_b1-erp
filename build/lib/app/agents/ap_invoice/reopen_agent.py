from fastapi import HTTPException

from app.operations.error_handler import translate_sap_error
from app.schema.response import APInvoiceActionResponse


def execute(intent, repository) -> APInvoiceActionResponse:
    if not intent.docEntry:
        raise HTTPException(
            status_code=400,
            detail="DocEntry is required to reopen an AP invoice. Example: 'Reopen AP invoice 5001'",
        )

    try:
        repository.reopen_ap_invoice(intent.docEntry)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=translate_sap_error(str(exc))) from exc

    return APInvoiceActionResponse(
        status="reopened",
        message=f"🔓 Done! AP Invoice **{intent.docEntry}** has been reopened and is ready for further action.",
        docEntry=intent.docEntry,
    )
