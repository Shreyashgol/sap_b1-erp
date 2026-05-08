import logging
from collections.abc import Sequence
from decimal import Decimal
from typing import Any

from sqlalchemy import delete, select, text
from sqlalchemy.dialects.postgresql import insert

from app.config import DATABASE_CONNECTION_STRING
from app.db.ap_invoice_models import APInvoiceLineRecord, APInvoiceRecord, Base
from shared.db.runtime import DatabaseRuntime

logger = logging.getLogger(__name__)

db_runtime = DatabaseRuntime(
    database_url=DATABASE_CONNECTION_STRING,
    metadata=Base.metadata,
    logger_name=__name__,
)


def init_db_pool():
    engine = db_runtime.init()
    if engine is not None:
        ensure_ap_invoice_schema(engine)
    return engine


def get_db_session():
    return db_runtime.session_scope()


def _to_decimal(value) -> Decimal:
    if value is None:
        return Decimal("0")
    return Decimal(str(value))


def _first_present(*values):
    for value in values:
        if value is not None:
            return value
    return None


def _derive_status(invoice_data: dict[str, Any]) -> str:
    canceled = str(invoice_data.get("CANCELED") or "").upper()
    if canceled in {"Y", "YES", "TRUE", "T", "1"}:
        return "Cancelled"

    doc_status = str(invoice_data.get("DocStatus") or invoice_data.get("Status") or "").upper()
    if doc_status in {"C", "CLOSED"}:
        return "Closed"
    if doc_status in {"O", "OPEN"}:
        return "Open"

    return invoice_data.get("Status") or "Open"


def _build_invoice_row(invoice_data: dict[str, Any]) -> dict[str, Any]:
    doc_total = _to_decimal(invoice_data.get("DocTotal", 0))
    paid_sum = _to_decimal(invoice_data.get("PaidSum", 0))
    balance_due = invoice_data.get("BalanceDue")
    if balance_due is None:
        balance_due = doc_total - paid_sum

    return {
        "doc_entry": invoice_data.get("DocEntry"),
        "doc_num": invoice_data.get("DocNum"),
        "series": invoice_data.get("Series"),
        "num_at_card": invoice_data.get("NumAtCard"),
        "card_code": invoice_data.get("CardCode") or "",
        "card_name": invoice_data.get("CardName") or "",
        "lic_trad_num": invoice_data.get("LicTradNum"),
        "cntct_code": invoice_data.get("CntctCode"),
        "doc_date": invoice_data.get("DocDate"),
        "doc_due_date": invoice_data.get("DocDueDate"),
        "tax_date": invoice_data.get("TaxDate"),
        "create_date": invoice_data.get("CreateDate"),
        "update_date": invoice_data.get("UpdateDate"),
        "doc_cur": invoice_data.get("DocCur"),
        "doc_rate": _to_decimal(invoice_data.get("DocRate", 0)),
        "doc_total": doc_total,
        "vat_sum": _to_decimal(invoice_data.get("VatSum", 0)),
        "disc_sum": _to_decimal(invoice_data.get("DiscSum", 0)),
        "round_dif": _to_decimal(invoice_data.get("RoundDif", 0)),
        "paid_to_date": _to_decimal(invoice_data.get("PaidToDate", 0)),
        "paid_sum": paid_sum,
        "balance_due": _to_decimal(balance_due),
        "pay_method": invoice_data.get("PeyMethod"),
        "pay_block": invoice_data.get("PayBlock"),
        "ctl_account": invoice_data.get("CtlAccount"),
        "status": _derive_status(invoice_data),
        "doc_status": invoice_data.get("DocStatus"),
        "canceled": invoice_data.get("CANCELED"),
        "confirmed": invoice_data.get("Confirmed"),
        "wdd_status": invoice_data.get("WddStatus"),
        "base_entry": invoice_data.get("BaseEntry"),
        "base_type": invoice_data.get("BaseType"),
        "receipt_num": invoice_data.get("ReceiptNum"),
        "trans_id": invoice_data.get("TransId"),
        "vat_percent": _to_decimal(invoice_data.get("VatPercent", 0)),
        "vat_paid": _to_decimal(invoice_data.get("VatPaid", 0)),
        "wt_details": invoice_data.get("WTDetails"),
        "gst_tran_typ": invoice_data.get("GSTTranTyp"),
        "tax_inv_no": invoice_data.get("TaxInvNo"),
        "ship_to_code": invoice_data.get("ShipToCode"),
        "project": invoice_data.get("Project"),
        "slp_code": invoice_data.get("SlpCode"),
        "comments": invoice_data.get("Comments"),
        "owner_code": invoice_data.get("OwnerCode"),
        "attachment": invoice_data.get("Attachment"),
        "sap_payload": invoice_data,
    }


def _build_line_row(invoice_id: int, doc_entry: int, idx: int, item: dict[str, Any]) -> dict[str, Any]:
    quantity = _to_decimal(item.get("Quantity", 0) or 0)
    price = _to_decimal(_first_present(item.get("Price"), item.get("UnitPrice"), 0) or 0)
    line_total = item.get("LineTotal")
    if line_total is None:
        line_total = quantity * price
    else:
        line_total = _to_decimal(line_total)

    return {
        "invoice_id": invoice_id,
        "doc_entry": doc_entry,
        "line_number": item.get("LineNum", idx),
        "item_code": item.get("ItemCode"),
        "item_description": item.get("Dscription") or item.get("ItemDescription", ""),
        "base_qty": _to_decimal(item.get("BaseQty", 0)),
        "open_qty": _to_decimal(item.get("OpenQty", 0)),
        "open_inv_qty": _to_decimal(item.get("OpenInvQty", 0)),
        "quantity": quantity,
        "price": price,
        "price_bef_di": _to_decimal(item.get("PriceBefDi", 0)),
        "disc_prcnt": _to_decimal(item.get("DiscPrcnt", 0)),
        "line_total": line_total,
        "currency": item.get("Currency"),
        "rate": _to_decimal(item.get("Rate", 0)),
        "stock_price": _to_decimal(item.get("StockPrice", 0)),
        "gross_buy_pr": _to_decimal(item.get("GrossBuyPr", 0)),
        "g_total": _to_decimal(item.get("GTotal", 0)),
        "vat_prcnt": _to_decimal(item.get("VatPrcnt", 0)),
        "vat_sum": _to_decimal(item.get("VatSum", 0)),
        "tax_code": item.get("TaxCode", ""),
        "tax_type": item.get("TaxType"),
        "line_vat": _to_decimal(item.get("LineVat", 0)),
        "base_type": item.get("BaseType"),
        "base_entry": item.get("BaseEntry"),
        "base_line": item.get("BaseLine"),
        "po_trg_entry": item.get("PoTrgEntry"),
        "trget_entry": item.get("TrgetEntry"),
        "whs_code": item.get("WhsCode"),
        "invnt_sttus": item.get("InvntSttus"),
        "stock_value": _to_decimal(item.get("StockValue", 0)),
        "acct_code": item.get("AcctCode"),
        "ocr_code": item.get("OcrCode"),
        "project": item.get("Project"),
        "ship_to_code": item.get("ShipToCode"),
        "ship_to_desc": item.get("ShipToDesc"),
        "trns_code": item.get("TrnsCode"),
        "line_status": item.get("LineStatus"),
        "free_txt": item.get("FreeTxt"),
        "owner_code": item.get("OwnerCode"),
    }


def ensure_ap_invoice_schema(engine):
    statements = [
        "ALTER TABLE opch ADD COLUMN IF NOT EXISTS docentry INTEGER",
        "ALTER TABLE opch ADD COLUMN IF NOT EXISTS docnum INTEGER",
        "ALTER TABLE opch ADD COLUMN IF NOT EXISTS series INTEGER",
        "ALTER TABLE opch ADD COLUMN IF NOT EXISTS numatcard VARCHAR",
        "ALTER TABLE opch ADD COLUMN IF NOT EXISTS cardcode VARCHAR",
        "ALTER TABLE opch ADD COLUMN IF NOT EXISTS cardname VARCHAR",
        "ALTER TABLE opch ADD COLUMN IF NOT EXISTS docdate DATE",
        "ALTER TABLE opch ADD COLUMN IF NOT EXISTS docduedate DATE",
        "ALTER TABLE opch ADD COLUMN IF NOT EXISTS taxdate DATE",
        "ALTER TABLE opch ADD COLUMN IF NOT EXISTS createdate DATE",
        "ALTER TABLE opch ADD COLUMN IF NOT EXISTS updatedate DATE",
        "ALTER TABLE opch ADD COLUMN IF NOT EXISTS doccur VARCHAR",
        "ALTER TABLE opch ADD COLUMN IF NOT EXISTS docrate NUMERIC(18, 6) DEFAULT 0",
        "ALTER TABLE opch ADD COLUMN IF NOT EXISTS doctotal NUMERIC(18, 2) DEFAULT 0",
        "ALTER TABLE opch ADD COLUMN IF NOT EXISTS vatsum NUMERIC(18, 2) DEFAULT 0",
        "ALTER TABLE opch ADD COLUMN IF NOT EXISTS discsum NUMERIC(18, 2) DEFAULT 0",
        "ALTER TABLE opch ADD COLUMN IF NOT EXISTS paidtodate NUMERIC(18, 2) DEFAULT 0",
        "ALTER TABLE opch ADD COLUMN IF NOT EXISTS paidsum NUMERIC(18, 2) DEFAULT 0",
        "ALTER TABLE opch ADD COLUMN IF NOT EXISTS balancedue NUMERIC(18, 2) DEFAULT 0",
        "ALTER TABLE opch ADD COLUMN IF NOT EXISTS docstatus VARCHAR",
        "ALTER TABLE opch ADD COLUMN IF NOT EXISTS canceled VARCHAR",
        "ALTER TABLE opch ADD COLUMN IF NOT EXISTS comments VARCHAR",
        "ALTER TABLE opch ADD COLUMN IF NOT EXISTS sap_payload JSONB",
        "ALTER TABLE pch1 ADD COLUMN IF NOT EXISTS docentry INTEGER",
        "ALTER TABLE pch1 ADD COLUMN IF NOT EXISTS linenum INTEGER",
        "ALTER TABLE pch1 ADD COLUMN IF NOT EXISTS itemcode VARCHAR",
        "ALTER TABLE pch1 ADD COLUMN IF NOT EXISTS dscription VARCHAR",
        "ALTER TABLE pch1 ADD COLUMN IF NOT EXISTS quantity NUMERIC(18, 2) DEFAULT 0",
        "ALTER TABLE pch1 ADD COLUMN IF NOT EXISTS openqty NUMERIC(18, 2) DEFAULT 0",
        "ALTER TABLE pch1 ADD COLUMN IF NOT EXISTS openinvqty NUMERIC(18, 2) DEFAULT 0",
        "ALTER TABLE pch1 ADD COLUMN IF NOT EXISTS price NUMERIC(18, 2) DEFAULT 0",
        "ALTER TABLE pch1 ADD COLUMN IF NOT EXISTS pricebefdi NUMERIC(18, 2) DEFAULT 0",
        "ALTER TABLE pch1 ADD COLUMN IF NOT EXISTS discprcnt NUMERIC(18, 6) DEFAULT 0",
        "ALTER TABLE pch1 ADD COLUMN IF NOT EXISTS linetotal NUMERIC(18, 2) DEFAULT 0",
        "ALTER TABLE pch1 ADD COLUMN IF NOT EXISTS currency VARCHAR",
        "ALTER TABLE pch1 ADD COLUMN IF NOT EXISTS vatprcnt NUMERIC(18, 6) DEFAULT 0",
        "ALTER TABLE pch1 ADD COLUMN IF NOT EXISTS vatsum NUMERIC(18, 2) DEFAULT 0",
        "ALTER TABLE pch1 ADD COLUMN IF NOT EXISTS taxcode VARCHAR",
        "ALTER TABLE pch1 ADD COLUMN IF NOT EXISTS whscode VARCHAR",
        "ALTER TABLE pch1 ADD COLUMN IF NOT EXISTS linestatus VARCHAR",
        "ALTER TABLE pch1 ADD COLUMN IF NOT EXISTS baseentry INTEGER",
        "ALTER TABLE pch1 ADD COLUMN IF NOT EXISTS baseline INTEGER",
    ]

    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))


def _serialize_ap_invoice(record: APInvoiceRecord) -> dict:
    return {
        "id": record.id,
        "doc_entry": record.doc_entry,
        "doc_num": record.doc_num,
        "series": record.series,
        "num_at_card": record.num_at_card,
        "card_code": record.card_code,
        "card_name": record.card_name,
        "lic_trad_num": record.lic_trad_num,
        "cntct_code": record.cntct_code,
        "doc_date": record.doc_date.isoformat() if record.doc_date else None,
        "doc_due_date": record.doc_due_date.isoformat() if record.doc_due_date else None,
        "tax_date": record.tax_date.isoformat() if record.tax_date else None,
        "create_date": record.create_date.isoformat() if record.create_date else None,
        "update_date": record.update_date.isoformat() if record.update_date else None,
        "doc_cur": record.doc_cur,
        "doc_rate": float(record.doc_rate or 0),
        "doc_total": float(record.doc_total or 0),
        "vat_sum": float(record.vat_sum or 0),
        "disc_sum": float(record.disc_sum or 0),
        "round_dif": float(record.round_dif or 0),
        "paid_to_date": float(record.paid_to_date or 0),
        "paid_sum": float(record.paid_sum or 0),
        "balance_due": float(record.balance_due or 0),
        "pay_method": record.pay_method,
        "pay_block": record.pay_block,
        "ctl_account": record.ctl_account,
        "status": record.status,
        "doc_status": record.doc_status,
        "canceled": record.canceled,
        "confirmed": record.confirmed,
        "wdd_status": record.wdd_status,
        "base_entry": record.base_entry,
        "base_type": record.base_type,
        "receipt_num": record.receipt_num,
        "trans_id": record.trans_id,
        "vat_percent": float(record.vat_percent or 0),
        "vat_paid": float(record.vat_paid or 0),
        "wt_details": record.wt_details,
        "gst_tran_typ": record.gst_tran_typ,
        "tax_inv_no": record.tax_inv_no,
        "ship_to_code": record.ship_to_code,
        "project": record.project,
        "slp_code": record.slp_code,
        "comments": record.comments,
        "owner_code": record.owner_code,
        "attachment": record.attachment,
        "sap_payload": record.sap_payload,
        "created_at": record.created_at.isoformat() if record.created_at else None,
        "updated_at": record.updated_at.isoformat() if record.updated_at else None,
        "line_items": [
            {
                "doc_entry": record.doc_entry,
                "line_number": line.line_number,
                "item_code": line.item_code,
                "item_description": line.item_description,
                "base_qty": float(line.base_qty or 0),
                "open_qty": float(line.open_qty or 0),
                "open_inv_qty": float(line.open_inv_qty or 0),
                "quantity": float(line.quantity or 0),
                "price": float(line.price or 0),
                "unit_price": float(line.price or 0),
                "price_bef_di": float(line.price_bef_di or 0),
                "disc_prcnt": float(line.disc_prcnt or 0),
                "tax_code": line.tax_code,
                "line_total": float(line.line_total or 0),
                "currency": line.currency,
                "rate": float(line.rate or 0),
                "stock_price": float(line.stock_price or 0),
                "gross_buy_pr": float(line.gross_buy_pr or 0),
                "g_total": float(line.g_total or 0),
                "vat_prcnt": float(line.vat_prcnt or 0),
                "vat_sum": float(line.vat_sum or 0),
                "tax_type": line.tax_type,
                "line_vat": float(line.line_vat or 0),
                "base_type": line.base_type,
                "base_entry": line.base_entry,
                "base_line": line.base_line,
                "po_trg_entry": line.po_trg_entry,
                "trget_entry": line.trget_entry,
                "whs_code": line.whs_code,
                "invnt_sttus": line.invnt_sttus,
                "stock_value": float(line.stock_value or 0),
                "acct_code": line.acct_code,
                "ocr_code": line.ocr_code,
                "project": line.project,
                "ship_to_code": line.ship_to_code,
                "ship_to_desc": line.ship_to_desc,
                "trns_code": line.trns_code,
                "line_status": line.line_status,
                "free_txt": line.free_txt,
                "owner_code": line.owner_code,
            }
            for line in sorted(record.line_items, key=lambda item: item.line_number)
        ],
    }


def _serialize_ap_invoices(records: Sequence[APInvoiceRecord]) -> list[dict]:
    return [_serialize_ap_invoice(record) for record in records]


def save_ap_invoice(invoice_data: dict, line_items: list | None = None) -> int:
    invoice_row = _build_invoice_row(invoice_data)

    with get_db_session() as session:
        update_dict = {
            getattr(APInvoiceRecord, k).name: v
            for k, v in invoice_row.items()
        }
        invoice_stmt = (
            insert(APInvoiceRecord)
            .values(**invoice_row)
            .on_conflict_do_update(
                index_elements=[APInvoiceRecord.doc_entry],
                set_=update_dict,
            )
            .returning(APInvoiceRecord.id)
        )

        invoice_id = session.execute(invoice_stmt).scalar_one()
        session.execute(delete(APInvoiceLineRecord).where(APInvoiceLineRecord.invoice_id == invoice_id))

        for idx, item in enumerate(line_items or []):
            session.add(APInvoiceLineRecord(**_build_line_row(invoice_id, invoice_row["doc_entry"], idx, item)))

        session.flush()
        return invoice_id


def fetch_ap_invoice_by_doc_num(doc_num: int) -> dict | None:
    with get_db_session() as session:
        statement = select(APInvoiceRecord).where(APInvoiceRecord.doc_num == doc_num)
        record = session.execute(statement).scalar_one_or_none()
        if record is None:
            return None
        return _serialize_ap_invoice(record)


def fetch_ap_invoice_by_doc_entry(doc_entry: int) -> dict | None:
    with get_db_session() as session:
        statement = select(APInvoiceRecord).where(APInvoiceRecord.doc_entry == doc_entry)
        record = session.execute(statement).scalar_one_or_none()
        if record is None:
            return None
        return _serialize_ap_invoice(record)


def fetch_ap_invoices_by_card_code(card_code: str, limit: int = 20) -> list[dict]:
    with get_db_session() as session:
        statement = (
            select(APInvoiceRecord)
            .where(APInvoiceRecord.card_code == card_code)
            .order_by(APInvoiceRecord.created_at.desc())
            .limit(limit)
        )
        records = session.execute(statement).scalars().all()
        return _serialize_ap_invoices(records)
