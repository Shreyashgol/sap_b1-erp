from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class SalesCustomerRecord(Base):
    __tablename__ = "sales_customers"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    card_code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    card_name: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    phone: Mapped[Optional[str]] = mapped_column(String(30))
    email: Mapped[Optional[str]] = mapped_column(String(150))
    billing_address: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class SalesOrderRecord(Base):
    __tablename__ = "sales_orders"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    doc_num: Mapped[Optional[int]] = mapped_column(index=True)
    card_code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    doc_date: Mapped[Optional[date]] = mapped_column(Date)
    doc_due_date: Mapped[Optional[date]] = mapped_column(Date)
    comments: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="open", nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    line_items: Mapped[List["SalesOrderLineRecord"]] = relationship(back_populates="sales_order", cascade="all, delete-orphan")


class SalesOrderLineRecord(Base):
    __tablename__ = "sales_order_lines"
    __table_args__ = (UniqueConstraint("order_id", "line_num", name="uq_sales_order_lines_order_id_line_num"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("sales_orders.id", ondelete="CASCADE"), nullable=False)
    line_num: Mapped[int] = mapped_column(Integer, nullable=False)
    item_code: Mapped[str] = mapped_column(String(50), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"), nullable=False)
    tax_code: Mapped[Optional[str]] = mapped_column(String(20))

    sales_order: Mapped[SalesOrderRecord] = relationship(back_populates="line_items")


class SalesInvoiceRecord(Base):
    __tablename__ = "sales_invoices"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    doc_num: Mapped[Optional[int]] = mapped_column(index=True)
    card_code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    comments: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="open", nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    line_items: Mapped[List["SalesInvoiceLineRecord"]] = relationship(back_populates="sales_invoice", cascade="all, delete-orphan")


class SalesInvoiceLineRecord(Base):
    __tablename__ = "sales_invoice_lines"
    __table_args__ = (UniqueConstraint("invoice_id", "line_num", name="uq_sales_invoice_lines_invoice_id_line_num"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    invoice_id: Mapped[int] = mapped_column(ForeignKey("sales_invoices.id", ondelete="CASCADE"), nullable=False)
    line_num: Mapped[int] = mapped_column(Integer, nullable=False)
    item_code: Mapped[str] = mapped_column(String(50), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"), nullable=False)
    tax_code: Mapped[Optional[str]] = mapped_column(String(20))

    sales_invoice: Mapped[SalesInvoiceRecord] = relationship(back_populates="line_items")


class SalesReturnRecord(Base):
    __tablename__ = "sales_returns"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    doc_num: Mapped[Optional[int]] = mapped_column(index=True)
    card_code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    comments: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="open", nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    line_items: Mapped[List["SalesReturnLineRecord"]] = relationship(back_populates="sales_return", cascade="all, delete-orphan")


class SalesReturnLineRecord(Base):
    __tablename__ = "sales_return_lines"
    __table_args__ = (UniqueConstraint("return_id", "line_num", name="uq_sales_return_lines_return_id_line_num"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    return_id: Mapped[int] = mapped_column(ForeignKey("sales_returns.id", ondelete="CASCADE"), nullable=False)
    line_num: Mapped[int] = mapped_column(Integer, nullable=False)
    item_code: Mapped[str] = mapped_column(String(50), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"), nullable=False)
    tax_code: Mapped[Optional[str]] = mapped_column(String(20))

    sales_return: Mapped[SalesReturnRecord] = relationship(back_populates="line_items")
