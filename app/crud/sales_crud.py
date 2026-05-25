from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import select

from app.db.sales_db import get_db_session
from app.db.sales_models import (
    SalesCustomerRecord,
    SalesInvoiceLineRecord,
    SalesInvoiceRecord,
    SalesOrderLineRecord,
    SalesOrderRecord,
    SalesReturnLineRecord,
    SalesReturnRecord,
)


DOCUMENT_MODELS = {
    "sales_order": (SalesOrderRecord, SalesOrderLineRecord, "line_items"),
    "ar_invoice": (SalesInvoiceRecord, SalesInvoiceLineRecord, "line_items"),
    "sales_return": (SalesReturnRecord, SalesReturnLineRecord, "line_items"),
}

PRODUCTION_TABLES = {
    "customer": SalesCustomerRecord.__tablename__,
    "sales_order": SalesOrderRecord.__tablename__,
    "sales_order_line": SalesOrderLineRecord.__tablename__,
    "ar_invoice": SalesInvoiceRecord.__tablename__,
    "ar_invoice_line": SalesInvoiceLineRecord.__tablename__,
    "sales_return": SalesReturnRecord.__tablename__,
    "sales_return_line": SalesReturnLineRecord.__tablename__,
}


def _to_date(value: str | date | None) -> date | None:
    if value in (None, ""):
        return None
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def _line_payload(line: Any, index: int) -> dict[str, Any]:
    return {
        "line_num": index,
        "item_code": line.itemCode,
        "quantity": line.quantity,
        "unit_price": Decimal(str(line.unitPrice or 0)),
        "tax_code": line.taxCode,
    }


def _serialize_line(line) -> dict[str, Any]:
    return {
        "lineNum": line.line_num,
        "itemCode": line.item_code,
        "quantity": line.quantity,
        "unitPrice": float(line.unit_price or 0),
        "taxCode": line.tax_code,
    }


def _serialize_record(document_type: str, record) -> dict[str, Any]:
    return {
        "documentType": document_type,
        "docEntry": record.id,
        "docNum": record.doc_num,
        "cardCode": record.card_code,
        "docDate": getattr(record, "doc_date", None).isoformat() if getattr(record, "doc_date", None) else None,
        "docDueDate": getattr(record, "doc_due_date", None).isoformat() if getattr(record, "doc_due_date", None) else None,
        "comments": record.comments,
        "status": record.status,
        "lines": [_serialize_line(line) for line in record.line_items],
    }


def _serialize_customer(record: SalesCustomerRecord) -> dict[str, Any]:
    return {
        "cardCode": record.card_code,
        "cardName": record.card_name,
        "phone": record.phone,
        "email": record.email,
        "billingAddress": record.billing_address,
        "status": record.status,
    }


class SalesRepository:
    def table_names(self) -> dict[str, str]:
        return PRODUCTION_TABLES.copy()

    def get_customer(self, card_code: str) -> dict[str, Any] | None:
        with get_db_session() as session:
            record = session.scalars(
                select(SalesCustomerRecord).where(SalesCustomerRecord.card_code == card_code)
            ).first()
            return _serialize_customer(record) if record else None

    def list_customers(self, limit: int = 50) -> list[dict[str, Any]]:
        with get_db_session() as session:
            records = session.scalars(
                select(SalesCustomerRecord).order_by(SalesCustomerRecord.card_name.asc()).limit(limit)
            ).all()
            return [_serialize_customer(record) for record in records]

    def create_document(self, intent) -> dict[str, Any]:
        header_model, line_model, relationship_name = DOCUMENT_MODELS[intent.documentType]
        if intent.documentType == "sales_order":
            record = header_model(
                card_code=intent.cardCode,
                doc_date=_to_date(intent.docDate),
                doc_due_date=_to_date(intent.docDueDate),
                comments=intent.comments,
                status="open",
            )
        else:
            record = header_model(card_code=intent.cardCode, comments=intent.comments, status="open")

        lines = [line_model(**_line_payload(line, index)) for index, line in enumerate(intent.items or [])]
        setattr(record, relationship_name, lines)

        with get_db_session() as session:
            session.add(record)
            session.flush()
            record.doc_num = record.id
            session.flush()
            session.refresh(record)
            return _serialize_record(intent.documentType, record)

    def get_document(self, document_type: str, doc_entry: int) -> dict[str, Any] | None:
        header_model = DOCUMENT_MODELS[document_type][0]
        with get_db_session() as session:
            record = session.get(header_model, doc_entry)
            return _serialize_record(document_type, record) if record else None

    def list_documents(self, document_type: str, limit: int = 20) -> list[dict[str, Any]]:
        header_model = DOCUMENT_MODELS[document_type][0]
        with get_db_session() as session:
            records = session.scalars(select(header_model).order_by(header_model.id.desc()).limit(limit)).all()
            return [_serialize_record(document_type, record) for record in records]

    def update_document(self, intent) -> dict[str, Any] | None:
        header_model = DOCUMENT_MODELS[intent.documentType][0]
        with get_db_session() as session:
            record = session.get(header_model, intent.docEntry)
            if not record:
                return None
            if intent.comments is not None:
                record.comments = intent.comments
            session.flush()
            session.refresh(record)
            return _serialize_record(intent.documentType, record)

    def set_status(self, document_type: str, doc_entry: int, status: str) -> dict[str, Any] | None:
        header_model = DOCUMENT_MODELS[document_type][0]
        with get_db_session() as session:
            record = session.get(header_model, doc_entry)
            if not record:
                return None
            record.status = status
            session.flush()
            session.refresh(record)
            return _serialize_record(document_type, record)
