from fastapi import HTTPException

from app.operations.sql_executor import execute_read_only_sql
from app.operations.purchase_rag import build_purchase_rag_fetch_sql
from app.schema.response import APInvoiceActionResponse


def execute(intent, repository) -> APInvoiceActionResponse:
    del repository

    fetch_query = intent.fetchQuery or ""

    try:
        query_spec = build_purchase_rag_fetch_sql(fetch_query=fetch_query)
        rows = execute_read_only_sql(query_spec["sql"], query_spec["params"])
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Fetch execution failed: {str(exc)}") from exc

    if not rows:
        raise HTTPException(status_code=404, detail="No AP invoices matched the fetch query")

    doc_entry = rows[0].get("doc_entry")
    count = len(rows)
    filters = query_spec["filters"]

    if count == 1:
        message = "✅ Here is the AP Invoice you requested."
    else:
        message = f"✅ I found {count} AP invoices matching your criteria."

    return APInvoiceActionResponse(
        status="fetched",
        message=message,
        docEntry=doc_entry,
        data={
            "filters": filters,
            "rowCount": count,
            "sql": query_spec["sql"],
            "strategy": "rag",
            "rows": rows,
        },
    )
