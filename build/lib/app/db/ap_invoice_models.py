from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class APInvoiceRecord(Base):
    __tablename__ = "opch"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    doc_entry: Mapped[int] = mapped_column("docentry", unique=True, nullable=False, index=True)
    doc_num: Mapped[Optional[int]] = mapped_column("docnum", index=True)
    series: Mapped[Optional[int]] = mapped_column("series", Integer)
    num_at_card: Mapped[Optional[str]] = mapped_column("numatcard", String)
    card_code: Mapped[str] = mapped_column("cardcode", String, nullable=False)
    card_name: Mapped[str] = mapped_column("cardname", String, default="")
    lic_trad_num: Mapped[Optional[str]] = mapped_column("lictradnum", String)
    cntct_code: Mapped[Optional[int]] = mapped_column("cntctcode", Integer)
    doc_date: Mapped[Optional[date]] = mapped_column("docdate", Date)
    doc_due_date: Mapped[Optional[date]] = mapped_column("docduedate", Date)
    tax_date: Mapped[Optional[date]] = mapped_column("taxdate", Date)
    create_date: Mapped[Optional[date]] = mapped_column("createdate", Date)
    update_date: Mapped[Optional[date]] = mapped_column("updatedate", Date)
    doc_cur: Mapped[Optional[str]] = mapped_column("doccur", String)
    doc_rate: Mapped[Decimal] = mapped_column("docrate", Numeric(18, 6), default=Decimal("0"))
    doc_total: Mapped[Decimal] = mapped_column("doctotal", Numeric(18, 2), default=Decimal("0"))
    vat_sum: Mapped[Decimal] = mapped_column("vatsum", Numeric(18, 2), default=Decimal("0"))
    disc_sum: Mapped[Decimal] = mapped_column("discsum", Numeric(18, 2), default=Decimal("0"))
    round_dif: Mapped[Decimal] = mapped_column("rounddif", Numeric(18, 2), default=Decimal("0"))
    paid_to_date: Mapped[Decimal] = mapped_column("paidtodate", Numeric(18, 2), default=Decimal("0"))
    paid_sum: Mapped[Decimal] = mapped_column("paidsum", Numeric(18, 2), default=Decimal("0"))
    balance_due: Mapped[Decimal] = mapped_column("balancedue", Numeric(18, 2), default=Decimal("0"))
    pay_method: Mapped[Optional[str]] = mapped_column("peymethod", String)
    pay_block: Mapped[Optional[str]] = mapped_column("payblock", String)
    ctl_account: Mapped[Optional[str]] = mapped_column("ctlaccount", String)
    status: Mapped[str] = mapped_column("status", String, default="Open", nullable=False)
    doc_status: Mapped[Optional[str]] = mapped_column("docstatus", String)
    canceled: Mapped[Optional[str]] = mapped_column("canceled", String)
    confirmed: Mapped[Optional[str]] = mapped_column("confirmed", String)
    wdd_status: Mapped[Optional[str]] = mapped_column("wddstatus", String)
    base_entry: Mapped[Optional[int]] = mapped_column("baseentry", Integer)
    base_type: Mapped[Optional[int]] = mapped_column("basetype", Integer)
    receipt_num: Mapped[Optional[int]] = mapped_column("receiptnum", Integer)
    trans_id: Mapped[Optional[int]] = mapped_column("transid", Integer)
    vat_percent: Mapped[Decimal] = mapped_column("vatpercent", Numeric(18, 6), default=Decimal("0"))
    vat_paid: Mapped[Decimal] = mapped_column("vatpaid", Numeric(18, 2), default=Decimal("0"))
    wt_details: Mapped[Optional[Any]] = mapped_column("wtdetails", JSONB)
    gst_tran_typ: Mapped[Optional[str]] = mapped_column("gsttrantyp", String)
    tax_inv_no: Mapped[Optional[str]] = mapped_column("taxinvno", String)
    ship_to_code: Mapped[Optional[str]] = mapped_column("shiptocode", String)
    project: Mapped[Optional[str]] = mapped_column("project", String)
    slp_code: Mapped[Optional[int]] = mapped_column("slpcode", Integer)
    comments: Mapped[Optional[str]] = mapped_column("comments", String)
    owner_code: Mapped[Optional[int]] = mapped_column("ownercode", Integer)
    attachment: Mapped[Optional[str]] = mapped_column("attachment", String)
    sap_payload: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    line_items: Mapped[List["APInvoiceLineRecord"]] = relationship(
        back_populates="ap_invoice",
        cascade="all, delete-orphan",
    )


class APInvoiceLineRecord(Base):
    __tablename__ = "pch1"
    __table_args__ = (UniqueConstraint("invoice_id", "linenum", name="uq_pch1_invoice_id_linenum"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    invoice_id: Mapped[int] = mapped_column(ForeignKey("opch.id", ondelete="CASCADE"), nullable=False)
    doc_entry: Mapped[int] = mapped_column("docentry", nullable=False, index=True)
    line_number: Mapped[int] = mapped_column("linenum", nullable=False)
    item_code: Mapped[str] = mapped_column("itemcode", String, nullable=False)
    item_description: Mapped[str] = mapped_column("dscription", String, default="")
    base_qty: Mapped[Decimal] = mapped_column("baseqty", Numeric(18, 2), default=Decimal("0"))
    open_qty: Mapped[Decimal] = mapped_column("openqty", Numeric(18, 2), default=Decimal("0"))
    open_inv_qty: Mapped[Decimal] = mapped_column("openinvqty", Numeric(18, 2), default=Decimal("0"))
    quantity: Mapped[Decimal] = mapped_column("quantity", Numeric(18, 2), nullable=False)
    price: Mapped[Decimal] = mapped_column("price", Numeric(18, 2), default=Decimal("0"))
    price_bef_di: Mapped[Decimal] = mapped_column("pricebefdi", Numeric(18, 2), default=Decimal("0"))
    disc_prcnt: Mapped[Decimal] = mapped_column("discprcnt", Numeric(18, 6), default=Decimal("0"))
    line_total: Mapped[Decimal] = mapped_column("linetotal", Numeric(18, 2), default=Decimal("0"))
    currency: Mapped[Optional[str]] = mapped_column("currency", String)
    rate: Mapped[Decimal] = mapped_column("rate", Numeric(18, 6), default=Decimal("0"))
    stock_price: Mapped[Decimal] = mapped_column("stockprice", Numeric(18, 2), default=Decimal("0"))
    gross_buy_pr: Mapped[Decimal] = mapped_column("grossbuypr", Numeric(18, 2), default=Decimal("0"))
    g_total: Mapped[Decimal] = mapped_column("gtotal", Numeric(18, 2), default=Decimal("0"))
    vat_prcnt: Mapped[Decimal] = mapped_column("vatprcnt", Numeric(18, 6), default=Decimal("0"))
    vat_sum: Mapped[Decimal] = mapped_column("vatsum", Numeric(18, 2), default=Decimal("0"))
    tax_code: Mapped[str] = mapped_column("taxcode", String, default="")
    tax_type: Mapped[Optional[str]] = mapped_column(String)
    line_vat: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))
    base_type: Mapped[Optional[int]] = mapped_column(Integer)
    base_entry: Mapped[Optional[int]] = mapped_column(Integer)
    base_line: Mapped[Optional[int]] = mapped_column(Integer)
    po_trg_entry: Mapped[Optional[int]] = mapped_column(Integer)
    trget_entry: Mapped[Optional[int]] = mapped_column(Integer)
    whs_code: Mapped[Optional[str]] = mapped_column(String)
    invnt_sttus: Mapped[Optional[str]] = mapped_column(String)
    stock_value: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))
    acct_code: Mapped[Optional[str]] = mapped_column(String)
    ocr_code: Mapped[Optional[str]] = mapped_column(String)
    project: Mapped[Optional[str]] = mapped_column(String)
    ship_to_code: Mapped[Optional[str]] = mapped_column(String)
    ship_to_desc: Mapped[Optional[str]] = mapped_column(String)
    trns_code: Mapped[Optional[str]] = mapped_column(String)
    line_status: Mapped[Optional[str]] = mapped_column(String)
    free_txt: Mapped[Optional[str]] = mapped_column(String)
    owner_code: Mapped[Optional[int]] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    ap_invoice: Mapped[APInvoiceRecord] = relationship(back_populates="line_items")
