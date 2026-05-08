from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class PurchaseReturnRecord(Base):
    __tablename__ = "orpd"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    doc_entry: Mapped[int] = mapped_column("docentry", unique=True, nullable=False, index=True)
    doc_num: Mapped[Optional[int]] = mapped_column("docnum", index=True)
    doc_date: Mapped[Optional[date]] = mapped_column("docdate", Date)
    doc_due_date: Mapped[Optional[date]] = mapped_column("docduedate", Date)
    doc_status: Mapped[Optional[str]] = mapped_column("docstatus", String)
    canceled: Mapped[Optional[str]] = mapped_column("canceled", String)
    card_code: Mapped[str] = mapped_column("cardcode", String, nullable=False)
    card_name: Mapped[str] = mapped_column("cardname", String, default="")
    doc_cur: Mapped[Optional[str]] = mapped_column("doccur", String)
    doc_total: Mapped[Decimal] = mapped_column("doctotal", Numeric(18, 2), default=Decimal("0"))
    vat_sum: Mapped[Decimal] = mapped_column("vatsum", Numeric(18, 2), default=Decimal("0"))
    comments: Mapped[Optional[str]] = mapped_column("comments", String)
    sap_payload: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    line_items: Mapped[List["PurchaseReturnLineRecord"]] = relationship(
        back_populates="purchase_return",
        cascade="all, delete-orphan",
    )


class PurchaseReturnLineRecord(Base):
    __tablename__ = "rpd1"
    __table_args__ = (UniqueConstraint("return_id", "linenum", name="uq_rpd1_return_id_linenum"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    return_id: Mapped[int] = mapped_column(ForeignKey("orpd.id", ondelete="CASCADE"), nullable=False)
    doc_entry: Mapped[int] = mapped_column("docentry", nullable=False, index=True)
    line_num: Mapped[int] = mapped_column("linenum", nullable=False)
    item_code: Mapped[str] = mapped_column("itemcode", String, nullable=False)
    dscription: Mapped[str] = mapped_column("dscription", String, default="")
    quantity: Mapped[Decimal] = mapped_column("quantity", Numeric(18, 2), nullable=False)
    open_qty: Mapped[Decimal] = mapped_column("openqty", Numeric(18, 2), default=Decimal("0"))
    price: Mapped[Decimal] = mapped_column("price", Numeric(18, 2), default=Decimal("0"))
    line_total: Mapped[Decimal] = mapped_column("linetotal", Numeric(18, 2), default=Decimal("0"))
    currency: Mapped[Optional[str]] = mapped_column("currency", String)
    vat_prcnt: Mapped[Decimal] = mapped_column("vatprcnt", Numeric(18, 6), default=Decimal("0"))
    vat_sum: Mapped[Decimal] = mapped_column("vatsum", Numeric(18, 2), default=Decimal("0"))
    tax_code: Mapped[Optional[str]] = mapped_column("taxcode", String)
    whs_code: Mapped[Optional[str]] = mapped_column("whscode", String)
    line_status: Mapped[Optional[str]] = mapped_column("linestatus", String)
    base_type: Mapped[Optional[int]] = mapped_column("basetype", Integer)
    base_entry: Mapped[Optional[int]] = mapped_column("baseentry", Integer)
    base_line: Mapped[Optional[int]] = mapped_column("baseline", Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    purchase_return: Mapped[PurchaseReturnRecord] = relationship(back_populates="line_items")
