from fastapi import HTTPException

from app.operations.error_handler import translate_sap_error
from app.schema.response import PurchaseOrderActionResponse


def execute(intent, repository) -> PurchaseOrderActionResponse:
    if not intent.docEntry:
        raise HTTPException(
            status_code=400,
            detail="DocEntry is required to close a purchase order. Example: 'Close purchase order 12345'",
        )

    try:
        repository.close_purchase_order(intent.docEntry)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=translate_sap_error(str(exc))) from exc

    from app.operations.write_rag import generate_write_sql
    sql = generate_write_sql("purchase_order", "close", {"DocEntry": intent.docEntry})

    return PurchaseOrderActionResponse(
        status="closed",
        message=f"🔒 All done! Purchase Order **{intent.docEntry}** is now closed.",
        docEntry=intent.docEntry,
        data={"sql": sql},
    )
