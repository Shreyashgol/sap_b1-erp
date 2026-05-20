from fastapi import HTTPException

from app.operations.sql_executor import execute_read_only_sql
from app.operations.purchase_rag import build_purchase_rag_fetch_sql
from app.schema.response import PurchaseReturnActionResponse


def execute(intent, repository) -> PurchaseReturnActionResponse:
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
        raise HTTPException(status_code=404, detail="No purchase returns matched the fetch query")

    count = len(rows)
    return PurchaseReturnActionResponse(
        status="fetched",
        message="✅ Here is the Purchase Return you requested." if count == 1 else f"✅ I found {count} Purchase Returns matching your criteria.",
        docEntry=rows[0].get("docentry") or rows[0].get("DocEntry"),
        data={
            "filters": query_spec["filters"],
            "rowCount": count,
            "sql": query_spec["sql"],
            "strategy": "rag",
            "rows": rows,
        },
    )
