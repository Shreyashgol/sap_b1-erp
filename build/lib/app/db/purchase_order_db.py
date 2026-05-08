import logging
from collections.abc import Sequence
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import delete, select, text
from sqlalchemy.dialects.postgresql import insert

from app.config import DATABASE_CONNECTION_STRING
from app.db.purchase_order_models import Base, PurchaseOrderLineRecord, PurchaseOrderRecord
from shared.db.runtime import DatabaseRuntime

logger = logging.getLogger(__name__)

db_runtime = DatabaseRuntime(
    database_url=DATABASE_CONNECTION_STRING,
    metadata=Base.metadata,
    logger_name=__name__,
)


def get_database_connection_string() -> str:
    return DATABASE_CONNECTION_STRING


def init_db_pool():
    engine = db_runtime.init()
    if engine is not None:
        ensure_purchase_order_schema(engine)
    return engine


def get_db_session():
    return db_runtime.session_scope()


def _to_decimal(value) -> Decimal:
    if value is None or value == "":
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


def _derive_doc_status(po_data: dict[str, Any]) -> str:
    raw_status = str(_first_present(po_data, "DocStatus", "Status") or "").upper()
    if raw_status in {"C", "CLOSED", "CLOSE"}:
        return "C"
    return "O"


def _derive_canceled(po_data: dict[str, Any]) -> str:
    canceled = str(po_data.get("CANCELED") or "").upper()
    if canceled in {"Y", "YES", "TRUE", "T", "1"}:
        return "Y"
    if str(po_data.get("Status") or "").lower() in {"cancelled", "canceled"}:
        return "Y"
    return "N"


def _build_purchase_order_row(po_data: dict[str, Any]) -> dict[str, Any]:
    return {
        "doc_entry": po_data.get("DocEntry"),
        "doc_num": po_data.get("DocNum"),
        "doc_date": _to_date(po_data.get("DocDate")),
        "doc_due_date": _to_date(_first_present(po_data, "DocDueDate", "DueDate")),
        "doc_status": _derive_doc_status(po_data),
        "canceled": _derive_canceled(po_data),
        "card_code": po_data.get("CardCode") or "",
        "card_name": po_data.get("CardName") or "",
        "doc_cur": po_data.get("DocCur"),
        "doc_rate": _to_decimal(po_data.get("DocRate", 0)),
        "doc_total": _to_decimal(po_data.get("DocTotal", 0)),
        "doc_total_fc": _to_decimal(po_data.get("DocTotalFC", 0)),
        "paid_to_date": _to_decimal(po_data.get("PaidToDate", 0)),
        "vat_sum": _to_decimal(po_data.get("VatSum", 0)),
        "disc_sum": _to_decimal(po_data.get("DiscSum", 0)),
        "group_num": po_data.get("GroupNum"),
        "payment_ref": po_data.get("PaymentRef"),
        "pay_method": po_data.get("PeyMethod"),
        "pay_block": po_data.get("PayBlock"),
        "invnt_sttus": po_data.get("InvntSttus"),
        "transfered": po_data.get("Transfered"),
        "pick_status": po_data.get("PickStatus"),
        "confirmed": po_data.get("Confirmed"),
        "address": po_data.get("Address"),
        "ship_to_code": po_data.get("ShipToCode"),
        "trnsp_code": po_data.get("TrnspCode"),
        "req_date": _to_date(po_data.get("ReqDate")),
        "create_date": _to_date(po_data.get("CreateDate")),
        "update_date": _to_date(po_data.get("UpdateDate")),
        "user_sign": po_data.get("UserSign"),
        "owner_code": po_data.get("OwnerCode"),
        "comments": po_data.get("Comments"),
        "jrnl_memo": po_data.get("JrnlMemo"),
        "sap_payload": po_data,
    }


def _build_purchase_order_line_row(
    po_id: int,
    header: dict[str, Any],
    idx: int,
    item: dict[str, Any],
) -> dict[str, Any]:
    quantity = _to_decimal(item.get("Quantity", 0))
    price = _to_decimal(_first_present(item, "Price", "UnitPrice", "GrossBuyPr") or 0)
    delivered = _to_decimal(item.get("DelivrdQty", 0))
    open_qty = _to_decimal(_first_present(item, "OpenQty", "OpenCreQty") or max(quantity - delivered, Decimal("0")))
    line_total = item.get("LineTotal")
    if line_total is None:
        line_total = quantity * price

    return {
        "po_id": po_id,
        "doc_entry": header["doc_entry"],
        "line_num": item.get("LineNum", idx),
        "item_code": item.get("ItemCode"),
        "dscription": item.get("Dscription") or item.get("ItemDescription", ""),
        "quantity": quantity,
        "open_qty": open_qty,
        "open_cre_qty": _to_decimal(_first_present(item, "OpenCreQty", "OpenQty") or open_qty),
        "delivrd_qty": delivered,
        "ship_date": _to_date(_first_present(item, "ShipDate", "DocDueDate", "DueDate")),
        "price": price,
        "disc_prcnt": _to_decimal(item.get("DiscPrcnt", 0)),
        "line_total": _to_decimal(line_total),
        "currency": item.get("Currency") or header.get("doc_cur"),
        "rate": _to_decimal(item.get("Rate", 0)),
        "vat_prcnt": _to_decimal(item.get("VatPrcnt", 0)),
        "vat_sum": _to_decimal(item.get("VatSum", 0)),
        "tax_code": item.get("TaxCode"),
        "vendor_num": item.get("VendorNum"),
        "base_card": item.get("BaseCard") or header.get("card_code"),
        "whs_code": item.get("WhsCode"),
        "invnt_sttus": item.get("InvntSttus"),
        "stock_price": _to_decimal(item.get("StockPrice", 0)),
        "line_status": item.get("LineStatus", "O"),
        "target_type": item.get("TargetType"),
        "trget_entry": item.get("TrgetEntry"),
        "gross_buy_pr": _to_decimal(_first_present(item, "GrossBuyPr", "Price", "UnitPrice") or 0),
        "g_total": _to_decimal(item.get("GTotal", line_total)),
        "ship_to_code": item.get("ShipToCode") or header.get("ship_to_code"),
        "trns_code": item.get("TrnsCode"),
        "project": item.get("Project"),
        "owner_code": item.get("OwnerCode"),
        "free_txt": item.get("FreeTxt"),
        "acct_code": item.get("AcctCode"),
    }


def ensure_purchase_order_schema(engine):
    statements = [
        "ALTER TABLE opor ADD COLUMN IF NOT EXISTS docdate DATE",
        "ALTER TABLE opor ADD COLUMN IF NOT EXISTS docduedate DATE",
        "ALTER TABLE opor ADD COLUMN IF NOT EXISTS docstatus VARCHAR",
        "ALTER TABLE opor ADD COLUMN IF NOT EXISTS canceled VARCHAR",
        "ALTER TABLE opor ADD COLUMN IF NOT EXISTS cardcode VARCHAR",
        "ALTER TABLE opor ADD COLUMN IF NOT EXISTS cardname VARCHAR",
        "ALTER TABLE opor ADD COLUMN IF NOT EXISTS doccur VARCHAR",
        "ALTER TABLE opor ADD COLUMN IF NOT EXISTS docrate NUMERIC(18, 6) DEFAULT 0",
        "ALTER TABLE opor ADD COLUMN IF NOT EXISTS doctotal NUMERIC(18, 2) DEFAULT 0",
        "ALTER TABLE opor ADD COLUMN IF NOT EXISTS doctotalfc NUMERIC(18, 2) DEFAULT 0",
        "ALTER TABLE opor ADD COLUMN IF NOT EXISTS paidtodate NUMERIC(18, 2) DEFAULT 0",
        "ALTER TABLE opor ADD COLUMN IF NOT EXISTS vatsum NUMERIC(18, 2) DEFAULT 0",
        "ALTER TABLE opor ADD COLUMN IF NOT EXISTS discsum NUMERIC(18, 2) DEFAULT 0",
        "ALTER TABLE opor ADD COLUMN IF NOT EXISTS groupnum INTEGER",
        "ALTER TABLE opor ADD COLUMN IF NOT EXISTS paymentref VARCHAR",
        "ALTER TABLE opor ADD COLUMN IF NOT EXISTS peymethod VARCHAR",
        "ALTER TABLE opor ADD COLUMN IF NOT EXISTS payblock VARCHAR",
        "ALTER TABLE opor ADD COLUMN IF NOT EXISTS invntsttus VARCHAR",
        "ALTER TABLE opor ADD COLUMN IF NOT EXISTS transfered VARCHAR",
        "ALTER TABLE opor ADD COLUMN IF NOT EXISTS pickstatus VARCHAR",
        "ALTER TABLE opor ADD COLUMN IF NOT EXISTS confirmed VARCHAR",
        "ALTER TABLE opor ADD COLUMN IF NOT EXISTS address VARCHAR",
        "ALTER TABLE opor ADD COLUMN IF NOT EXISTS shiptocode VARCHAR",
        "ALTER TABLE opor ADD COLUMN IF NOT EXISTS trnspcode INTEGER",
        "ALTER TABLE opor ADD COLUMN IF NOT EXISTS reqdate DATE",
        "ALTER TABLE opor ADD COLUMN IF NOT EXISTS createdate DATE",
        "ALTER TABLE opor ADD COLUMN IF NOT EXISTS updatedate DATE",
        "ALTER TABLE opor ADD COLUMN IF NOT EXISTS usersign INTEGER",
        "ALTER TABLE opor ADD COLUMN IF NOT EXISTS ownercode INTEGER",
        "ALTER TABLE opor ADD COLUMN IF NOT EXISTS comments VARCHAR",
        "ALTER TABLE opor ADD COLUMN IF NOT EXISTS jrnlmemo VARCHAR",
        "ALTER TABLE opor ADD COLUMN IF NOT EXISTS sap_payload JSONB",
        "ALTER TABLE por1 ADD COLUMN IF NOT EXISTS docentry INTEGER",
        "ALTER TABLE por1 ADD COLUMN IF NOT EXISTS linenum INTEGER",
        "ALTER TABLE por1 ADD COLUMN IF NOT EXISTS itemcode VARCHAR",
        "ALTER TABLE por1 ADD COLUMN IF NOT EXISTS dscription VARCHAR",
        "ALTER TABLE por1 ADD COLUMN IF NOT EXISTS quantity NUMERIC(18, 2) DEFAULT 0",
        "ALTER TABLE por1 ADD COLUMN IF NOT EXISTS openqty NUMERIC(18, 2) DEFAULT 0",
        "ALTER TABLE por1 ADD COLUMN IF NOT EXISTS opencreqty NUMERIC(18, 2) DEFAULT 0",
        "ALTER TABLE por1 ADD COLUMN IF NOT EXISTS delivrdqty NUMERIC(18, 2) DEFAULT 0",
        "ALTER TABLE por1 ADD COLUMN IF NOT EXISTS shipdate DATE",
        "ALTER TABLE por1 ADD COLUMN IF NOT EXISTS price NUMERIC(18, 2) DEFAULT 0",
        "ALTER TABLE por1 ADD COLUMN IF NOT EXISTS discprcnt NUMERIC(18, 6) DEFAULT 0",
        "ALTER TABLE por1 ADD COLUMN IF NOT EXISTS linetotal NUMERIC(18, 2) DEFAULT 0",
        "ALTER TABLE por1 ADD COLUMN IF NOT EXISTS currency VARCHAR",
        "ALTER TABLE por1 ADD COLUMN IF NOT EXISTS rate NUMERIC(18, 6) DEFAULT 0",
        "ALTER TABLE por1 ADD COLUMN IF NOT EXISTS vatprcnt NUMERIC(18, 6) DEFAULT 0",
        "ALTER TABLE por1 ADD COLUMN IF NOT EXISTS vatsum NUMERIC(18, 2) DEFAULT 0",
        "ALTER TABLE por1 ADD COLUMN IF NOT EXISTS taxcode VARCHAR",
        "ALTER TABLE por1 ADD COLUMN IF NOT EXISTS vendornum VARCHAR",
        "ALTER TABLE por1 ADD COLUMN IF NOT EXISTS basecard VARCHAR",
        "ALTER TABLE por1 ADD COLUMN IF NOT EXISTS whscode VARCHAR",
        "ALTER TABLE por1 ADD COLUMN IF NOT EXISTS invntsttus VARCHAR",
        "ALTER TABLE por1 ADD COLUMN IF NOT EXISTS stockprice NUMERIC(18, 2) DEFAULT 0",
        "ALTER TABLE por1 ADD COLUMN IF NOT EXISTS linestatus VARCHAR",
        "ALTER TABLE por1 ADD COLUMN IF NOT EXISTS targettype INTEGER",
        "ALTER TABLE por1 ADD COLUMN IF NOT EXISTS trgetentry INTEGER",
        "ALTER TABLE por1 ADD COLUMN IF NOT EXISTS grossbuypr NUMERIC(18, 2) DEFAULT 0",
        "ALTER TABLE por1 ADD COLUMN IF NOT EXISTS gtotal NUMERIC(18, 2) DEFAULT 0",
        "ALTER TABLE por1 ADD COLUMN IF NOT EXISTS shiptocode VARCHAR",
        "ALTER TABLE por1 ADD COLUMN IF NOT EXISTS trnscode VARCHAR",
        "ALTER TABLE por1 ADD COLUMN IF NOT EXISTS project VARCHAR",
        "ALTER TABLE por1 ADD COLUMN IF NOT EXISTS ownercode INTEGER",
        "ALTER TABLE por1 ADD COLUMN IF NOT EXISTS freetxt VARCHAR",
        "ALTER TABLE por1 ADD COLUMN IF NOT EXISTS acctcode VARCHAR",
    ]

    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))


def _serialize_purchase_order(record: PurchaseOrderRecord) -> dict:
    return {
        "DocEntry": record.doc_entry,
        "DocNum": record.doc_num,
        "DocDate": record.doc_date.isoformat() if record.doc_date else None,
        "DocDueDate": record.doc_due_date.isoformat() if record.doc_due_date else None,
        "DocStatus": record.doc_status,
        "CANCELED": record.canceled,
        "CardCode": record.card_code,
        "CardName": record.card_name,
        "DocCur": record.doc_cur,
        "DocRate": float(record.doc_rate or 0),
        "DocTotal": float(record.doc_total or 0),
        "DocTotalFC": float(record.doc_total_fc or 0),
        "PaidToDate": float(record.paid_to_date or 0),
        "VatSum": float(record.vat_sum or 0),
        "DiscSum": float(record.disc_sum or 0),
        "GroupNum": record.group_num,
        "PaymentRef": record.payment_ref,
        "PeyMethod": record.pay_method,
        "PayBlock": record.pay_block,
        "InvntSttus": record.invnt_sttus,
        "Transfered": record.transfered,
        "PickStatus": record.pick_status,
        "Confirmed": record.confirmed,
        "Address": record.address,
        "ShipToCode": record.ship_to_code,
        "TrnspCode": record.trnsp_code,
        "ReqDate": record.req_date.isoformat() if record.req_date else None,
        "CreateDate": record.create_date.isoformat() if record.create_date else None,
        "UpdateDate": record.update_date.isoformat() if record.update_date else None,
        "UserSign": record.user_sign,
        "OwnerCode": record.owner_code,
        "Comments": record.comments,
        "JrnlMemo": record.jrnl_memo,
        "DocumentLines": [
            _serialize_purchase_order_line(line)
            for line in sorted(record.line_items, key=lambda item: item.line_num)
        ],
    }


def _serialize_purchase_order_line(line: PurchaseOrderLineRecord) -> dict:
    return {
        "DocEntry": line.doc_entry,
        "LineNum": line.line_num,
        "ItemCode": line.item_code,
        "Dscription": line.dscription,
        "Quantity": float(line.quantity or 0),
        "OpenQty": float(line.open_qty or 0),
        "OpenCreQty": float(line.open_cre_qty or 0),
        "DelivrdQty": float(line.delivrd_qty or 0),
        "ShipDate": line.ship_date.isoformat() if line.ship_date else None,
        "Price": float(line.price or 0),
        "DiscPrcnt": float(line.disc_prcnt or 0),
        "LineTotal": float(line.line_total or 0),
        "Currency": line.currency,
        "Rate": float(line.rate or 0),
        "VatPrcnt": float(line.vat_prcnt or 0),
        "VatSum": float(line.vat_sum or 0),
        "TaxCode": line.tax_code,
        "VendorNum": line.vendor_num,
        "BaseCard": line.base_card,
        "WhsCode": line.whs_code,
        "InvntSttus": line.invnt_sttus,
        "StockPrice": float(line.stock_price or 0),
        "LineStatus": line.line_status,
        "TargetType": line.target_type,
        "TrgetEntry": line.trget_entry,
        "GrossBuyPr": float(line.gross_buy_pr or 0),
        "GTotal": float(line.g_total or 0),
        "ShipToCode": line.ship_to_code,
        "TrnsCode": line.trns_code,
        "Project": line.project,
        "OwnerCode": line.owner_code,
        "FreeTxt": line.free_txt,
        "AcctCode": line.acct_code,
    }


def _serialize_purchase_orders(records: Sequence[PurchaseOrderRecord]) -> list[dict]:
    return [_serialize_purchase_order(record) for record in records]


def save_purchase_order(po_data: dict, line_items: list | None = None) -> int:
    purchase_order_row = _build_purchase_order_row(po_data)

    with get_db_session() as session:
        update_dict = {
            getattr(PurchaseOrderRecord, k).name: v
            for k, v in purchase_order_row.items()
        }
        purchase_order_stmt = (
            insert(PurchaseOrderRecord)
            .values(**purchase_order_row)
            .on_conflict_do_update(
                index_elements=[PurchaseOrderRecord.doc_entry],
                set_=update_dict,
            )
            .returning(PurchaseOrderRecord.id)
        )

        po_id = session.execute(purchase_order_stmt).scalar_one()
        session.execute(delete(PurchaseOrderLineRecord).where(PurchaseOrderLineRecord.po_id == po_id))

        for idx, item in enumerate(line_items or []):
            session.add(
                PurchaseOrderLineRecord(
                    **_build_purchase_order_line_row(
                        po_id=po_id,
                        header=purchase_order_row,
                        idx=idx,
                        item=item,
                    )
                )
            )

        session.flush()
        return po_id


def fetch_po_by_doc_num(doc_num: int) -> dict | None:
    with get_db_session() as session:
        statement = select(PurchaseOrderRecord).where(PurchaseOrderRecord.doc_num == doc_num)
        record = session.execute(statement).scalar_one_or_none()
        if record is None:
            return None
        return _serialize_purchase_order(record)


def fetch_po_by_doc_entry(doc_entry: int) -> dict | None:
    with get_db_session() as session:
        statement = select(PurchaseOrderRecord).where(PurchaseOrderRecord.doc_entry == doc_entry)
        record = session.execute(statement).scalar_one_or_none()
        if record is None:
            return None
        return _serialize_purchase_order(record)


def fetch_pos_by_card_code(card_code: str, limit: int = 20) -> list[dict]:
    with get_db_session() as session:
        statement = (
            select(PurchaseOrderRecord)
            .where(PurchaseOrderRecord.card_code == card_code)
            .order_by(PurchaseOrderRecord.created_at.desc())
            .limit(limit)
        )
        records = session.execute(statement).scalars().all()
        return _serialize_purchase_orders(records)


def update_po_status_by_doc_entry(doc_entry: int, status: str):
    with get_db_session() as session:
        statement = select(PurchaseOrderRecord).where(PurchaseOrderRecord.doc_entry == doc_entry)
        record = session.execute(statement).scalar_one_or_none()
        if record is None:
            return

        lowered = status.lower()
        if lowered in {"cancelled", "canceled"}:
            record.canceled = "Y"
        if lowered == "closed":
            record.doc_status = "C"
        elif lowered == "open":
            record.doc_status = "O"

        session.add(record)
