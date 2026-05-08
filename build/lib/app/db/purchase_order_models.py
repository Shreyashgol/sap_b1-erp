from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class PurchaseOrderRecord(Base):
    __tablename__ = "opor"

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
    doc_rate: Mapped[Decimal] = mapped_column("docrate", Numeric(18, 6), default=Decimal("0"))
    doc_total: Mapped[Decimal] = mapped_column("doctotal", Numeric(18, 2), default=Decimal("0"))
    doc_total_fc: Mapped[Decimal] = mapped_column("doctotalfc", Numeric(18, 2), default=Decimal("0"))
    paid_to_date: Mapped[Decimal] = mapped_column("paidtodate", Numeric(18, 2), default=Decimal("0"))
    vat_sum: Mapped[Decimal] = mapped_column("vatsum", Numeric(18, 2), default=Decimal("0"))
    disc_sum: Mapped[Decimal] = mapped_column("discsum", Numeric(18, 2), default=Decimal("0"))
    group_num: Mapped[Optional[int]] = mapped_column("groupnum", Integer)
    payment_ref: Mapped[Optional[str]] = mapped_column("paymentref", String)
    pay_method: Mapped[Optional[str]] = mapped_column("peymethod", String)
    pay_block: Mapped[Optional[str]] = mapped_column("payblock", String)
    invnt_sttus: Mapped[Optional[str]] = mapped_column("invntsttus", String)
    transfered: Mapped[Optional[str]] = mapped_column("transfered", String)
    pick_status: Mapped[Optional[str]] = mapped_column("pickstatus", String)
    confirmed: Mapped[Optional[str]] = mapped_column("confirmed", String)
    address: Mapped[Optional[str]] = mapped_column("address", String)
    ship_to_code: Mapped[Optional[str]] = mapped_column("shiptocode", String)
    trnsp_code: Mapped[Optional[int]] = mapped_column("trnspcode", Integer)
    req_date: Mapped[Optional[date]] = mapped_column("reqdate", Date)
    create_date: Mapped[Optional[date]] = mapped_column("createdate", Date)
    update_date: Mapped[Optional[date]] = mapped_column("updatedate", Date)
    user_sign: Mapped[Optional[int]] = mapped_column("usersign", Integer)
    owner_code: Mapped[Optional[int]] = mapped_column("ownercode", Integer)
    comments: Mapped[Optional[str]] = mapped_column("comments", String)
    jrnl_memo: Mapped[Optional[str]] = mapped_column("jrnlmemo", String)
    sap_payload: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    line_items: Mapped[List["PurchaseOrderLineRecord"]] = relationship(
        back_populates="purchase_order",
        cascade="all, delete-orphan",
    )


class PurchaseOrderLineRecord(Base):
    __tablename__ = "por1"
    __table_args__ = (UniqueConstraint("po_id", "linenum", name="uq_por1_po_id_linenum"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    po_id: Mapped[int] = mapped_column(ForeignKey("opor.id", ondelete="CASCADE"), nullable=False)
    doc_entry: Mapped[int] = mapped_column("docentry", nullable=False, index=True)
    line_num: Mapped[int] = mapped_column("linenum", nullable=False)
    item_code: Mapped[str] = mapped_column("itemcode", String, nullable=False)
    dscription: Mapped[str] = mapped_column("dscription", String, default="")
    quantity: Mapped[Decimal] = mapped_column("quantity", Numeric(18, 2), nullable=False)
    open_qty: Mapped[Decimal] = mapped_column("openqty", Numeric(18, 2), default=Decimal("0"))
    open_cre_qty: Mapped[Decimal] = mapped_column("opencreqty", Numeric(18, 2), default=Decimal("0"))
    delivrd_qty: Mapped[Decimal] = mapped_column("delivrdqty", Numeric(18, 2), default=Decimal("0"))
    ship_date: Mapped[Optional[date]] = mapped_column("shipdate", Date)
    price: Mapped[Decimal] = mapped_column("price", Numeric(18, 2), default=Decimal("0"))
    disc_prcnt: Mapped[Decimal] = mapped_column("discprcnt", Numeric(18, 6), default=Decimal("0"))
    line_total: Mapped[Decimal] = mapped_column("linetotal", Numeric(18, 2), default=Decimal("0"))
    currency: Mapped[Optional[str]] = mapped_column("currency", String)
    rate: Mapped[Decimal] = mapped_column("rate", Numeric(18, 6), default=Decimal("0"))
    vat_prcnt: Mapped[Decimal] = mapped_column("vatprcnt", Numeric(18, 6), default=Decimal("0"))
    vat_sum: Mapped[Decimal] = mapped_column("vatsum", Numeric(18, 2), default=Decimal("0"))
    tax_code: Mapped[Optional[str]] = mapped_column("taxcode", String)
    vendor_num: Mapped[Optional[str]] = mapped_column("vendornum", String)
    base_card: Mapped[Optional[str]] = mapped_column("basecard", String)
    whs_code: Mapped[Optional[str]] = mapped_column("whscode", String)
    invnt_sttus: Mapped[Optional[str]] = mapped_column("invntsttus", String)
    stock_price: Mapped[Decimal] = mapped_column("stockprice", Numeric(18, 2), default=Decimal("0"))
    line_status: Mapped[Optional[str]] = mapped_column("linestatus", String)
    target_type: Mapped[Optional[int]] = mapped_column("targettype", Integer)
    trget_entry: Mapped[Optional[int]] = mapped_column("trgetentry", Integer)
    gross_buy_pr: Mapped[Decimal] = mapped_column("grossbuypr", Numeric(18, 2), default=Decimal("0"))
    g_total: Mapped[Decimal] = mapped_column("gtotal", Numeric(18, 2), default=Decimal("0"))
    ship_to_code: Mapped[Optional[str]] = mapped_column("shiptocode", String)
    trns_code: Mapped[Optional[str]] = mapped_column("trnscode", String)
    project: Mapped[Optional[str]] = mapped_column("project", String)
    owner_code: Mapped[Optional[int]] = mapped_column("ownercode", Integer)
    free_txt: Mapped[Optional[str]] = mapped_column("freetxt", String)
    acct_code: Mapped[Optional[str]] = mapped_column("acctcode", String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    purchase_order: Mapped[PurchaseOrderRecord] = relationship(back_populates="line_items")
