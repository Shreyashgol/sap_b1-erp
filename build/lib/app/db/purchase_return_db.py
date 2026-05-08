from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import delete, text
from sqlalchemy.dialects.postgresql import insert

from app.config import DATABASE_CONNECTION_STRING
from app.db.purchase_return_models import Base, PurchaseReturnLineRecord, PurchaseReturnRecord
from shared.db.runtime import DatabaseRuntime


db_runtime = DatabaseRuntime(database_url=DATABASE_CONNECTION_STRING, metadata=Base.metadata, logger_name=__name__)


def init_db_pool():
    engine = db_runtime.init()
    if engine is not None:
        ensure_purchase_return_schema(engine)
    return engine


def get_db_session():
    return db_runtime.session_scope()


def _to_decimal(value) -> Decimal:
    if value in (None, ""):
        return Decimal("0")
    return Decimal(str(value))


def _to_date(value) -> date | None:
    if value in (None, ""):
        return None
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def _first_present(data: dict[str, Any], *keys: str):
    for key in keys:
        value = data.get(key)
        if value is not None:
            return value
    return None


def ensure_purchase_return_schema(engine):
    with engine.begin() as connection:
        for statement in [
            "ALTER TABLE orpd ADD COLUMN IF NOT EXISTS docdate DATE",
            "ALTER TABLE orpd ADD COLUMN IF NOT EXISTS docduedate DATE",
            "ALTER TABLE orpd ADD COLUMN IF NOT EXISTS docstatus VARCHAR",
            "ALTER TABLE orpd ADD COLUMN IF NOT EXISTS canceled VARCHAR",
            "ALTER TABLE orpd ADD COLUMN IF NOT EXISTS cardcode VARCHAR",
            "ALTER TABLE orpd ADD COLUMN IF NOT EXISTS cardname VARCHAR",
            "ALTER TABLE orpd ADD COLUMN IF NOT EXISTS doccur VARCHAR",
            "ALTER TABLE orpd ADD COLUMN IF NOT EXISTS doctotal NUMERIC(18, 2) DEFAULT 0",
            "ALTER TABLE orpd ADD COLUMN IF NOT EXISTS vatsum NUMERIC(18, 2) DEFAULT 0",
            "ALTER TABLE orpd ADD COLUMN IF NOT EXISTS comments VARCHAR",
            "ALTER TABLE orpd ADD COLUMN IF NOT EXISTS sap_payload JSONB",
            "ALTER TABLE rpd1 ADD COLUMN IF NOT EXISTS docentry INTEGER",
            "ALTER TABLE rpd1 ADD COLUMN IF NOT EXISTS linenum INTEGER",
            "ALTER TABLE rpd1 ADD COLUMN IF NOT EXISTS itemcode VARCHAR",
            "ALTER TABLE rpd1 ADD COLUMN IF NOT EXISTS dscription VARCHAR",
            "ALTER TABLE rpd1 ADD COLUMN IF NOT EXISTS quantity NUMERIC(18, 2) DEFAULT 0",
            "ALTER TABLE rpd1 ADD COLUMN IF NOT EXISTS openqty NUMERIC(18, 2) DEFAULT 0",
            "ALTER TABLE rpd1 ADD COLUMN IF NOT EXISTS price NUMERIC(18, 2) DEFAULT 0",
            "ALTER TABLE rpd1 ADD COLUMN IF NOT EXISTS linetotal NUMERIC(18, 2) DEFAULT 0",
            "ALTER TABLE rpd1 ADD COLUMN IF NOT EXISTS currency VARCHAR",
            "ALTER TABLE rpd1 ADD COLUMN IF NOT EXISTS vatprcnt NUMERIC(18, 6) DEFAULT 0",
            "ALTER TABLE rpd1 ADD COLUMN IF NOT EXISTS vatsum NUMERIC(18, 2) DEFAULT 0",
            "ALTER TABLE rpd1 ADD COLUMN IF NOT EXISTS taxcode VARCHAR",
            "ALTER TABLE rpd1 ADD COLUMN IF NOT EXISTS whscode VARCHAR",
            "ALTER TABLE rpd1 ADD COLUMN IF NOT EXISTS linestatus VARCHAR",
            "ALTER TABLE rpd1 ADD COLUMN IF NOT EXISTS basetype INTEGER",
            "ALTER TABLE rpd1 ADD COLUMN IF NOT EXISTS baseentry INTEGER",
            "ALTER TABLE rpd1 ADD COLUMN IF NOT EXISTS baseline INTEGER",
        ]:
            connection.execute(text(statement))


def save_purchase_return(return_data: dict, line_items: list | None = None) -> int:
    row = {
        "doc_entry": return_data.get("DocEntry"),
        "doc_num": return_data.get("DocNum"),
        "doc_date": _to_date(return_data.get("DocDate")),
        "doc_due_date": _to_date(return_data.get("DocDueDate")),
        "doc_status": return_data.get("DocStatus", "O"),
        "canceled": return_data.get("CANCELED", "N"),
        "card_code": return_data.get("CardCode") or "",
        "card_name": return_data.get("CardName") or "",
        "doc_cur": return_data.get("DocCur"),
        "doc_total": _to_decimal(return_data.get("DocTotal", 0)),
        "vat_sum": _to_decimal(return_data.get("VatSum", 0)),
        "comments": return_data.get("Comments"),
        "sap_payload": return_data,
    }

    with get_db_session() as session:
        update_dict = {
            getattr(PurchaseReturnRecord, k).name: v
            for k, v in row.items()
        }
        stmt = (
            insert(PurchaseReturnRecord)
            .values(**row)
            .on_conflict_do_update(index_elements=[PurchaseReturnRecord.doc_entry], set_=update_dict)
            .returning(PurchaseReturnRecord.id)
        )
        return_id = session.execute(stmt).scalar_one()
        session.execute(delete(PurchaseReturnLineRecord).where(PurchaseReturnLineRecord.return_id == return_id))

        for idx, item in enumerate(line_items or []):
            quantity = _to_decimal(item.get("Quantity", 0))
            price = _to_decimal(_first_present(item, "Price", "UnitPrice") or 0)
            line_total = _to_decimal(item.get("LineTotal") or quantity * price)
            session.add(
                PurchaseReturnLineRecord(
                    return_id=return_id,
                    doc_entry=row["doc_entry"],
                    line_num=item.get("LineNum", idx),
                    item_code=item.get("ItemCode"),
                    dscription=item.get("Dscription") or item.get("ItemDescription", ""),
                    quantity=quantity,
                    open_qty=_to_decimal(item.get("OpenQty", 0)),
                    price=price,
                    line_total=line_total,
                    currency=item.get("Currency") or row.get("doc_cur"),
                    vat_prcnt=_to_decimal(item.get("VatPrcnt", 0)),
                    vat_sum=_to_decimal(item.get("VatSum", 0)),
                    tax_code=item.get("TaxCode"),
                    whs_code=item.get("WhsCode"),
                    line_status=item.get("LineStatus", "O"),
                    base_type=item.get("BaseType"),
                    base_entry=item.get("BaseEntry"),
                    base_line=item.get("BaseLine"),
                )
            )
        session.flush()
        return return_id
