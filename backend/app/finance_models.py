from datetime import date, datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .models import Base, uid, utcnow


class FinanceLedger(Base):
    __tablename__ = "finance_ledgers"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    trip_id: Mapped[str] = mapped_column(ForeignKey("trips.id", ondelete="CASCADE"), unique=True)
    currency: Mapped[str] = mapped_column(String(3))
    version: Mapped[int] = mapped_column(default=1)


class Budget(Base):
    __tablename__ = "budgets"
    __table_args__ = (
        UniqueConstraint("trip_id", "scope", "target"),
        CheckConstraint("scope IN ('trip','personal','category')"),
        CheckConstraint("amount_minor > 0"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    trip_id: Mapped[str] = mapped_column(ForeignKey("trips.id", ondelete="CASCADE"), index=True)
    scope: Mapped[str] = mapped_column(String(12))
    target: Mapped[str] = mapped_column(String(80))
    amount_minor: Mapped[int] = mapped_column(BigInteger)
    version: Mapped[int] = mapped_column(default=1)


class ExchangeRateSnapshot(Base):
    __tablename__ = "exchange_rate_snapshots"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    trip_id: Mapped[str] = mapped_column(ForeignKey("trips.id", ondelete="CASCADE"), index=True)
    source_currency: Mapped[str] = mapped_column(String(3))
    base_currency: Mapped[str] = mapped_column(String(3))
    rate: Mapped[str] = mapped_column(String(40))
    provider: Mapped[str] = mapped_column(String(16))
    rate_date: Mapped[date]
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Expense(Base):
    __tablename__ = "expenses"
    __table_args__ = (
        CheckConstraint("kind IN ('actual','estimate')"),
        CheckConstraint("split_mode IN ('equal','custom','ratio')"),
        CheckConstraint("amount_minor > 0 AND base_minor >= 0"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    trip_id: Mapped[str] = mapped_column(ForeignKey("trips.id", ondelete="CASCADE"), index=True)
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    title: Mapped[str] = mapped_column(String(160))
    category: Mapped[str] = mapped_column(String(80))
    kind: Mapped[str] = mapped_column(String(10))
    split_mode: Mapped[str] = mapped_column(String(10))
    currency: Mapped[str] = mapped_column(String(3))
    amount_minor: Mapped[int] = mapped_column(BigInteger)
    base_minor: Mapped[int] = mapped_column(BigInteger)
    rate_id: Mapped[str] = mapped_column(ForeignKey("exchange_rate_snapshots.id"))
    incurred_on: Mapped[date]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    version: Mapped[int] = mapped_column(default=1)


class ExpensePayer(Base):
    __tablename__ = "expense_payers"
    __table_args__ = (UniqueConstraint("expense_id", "user_id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    expense_id: Mapped[str] = mapped_column(
        ForeignKey("expenses.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    amount_minor: Mapped[int] = mapped_column(BigInteger)
    base_minor: Mapped[int] = mapped_column(BigInteger)


class ExpenseSplit(Base):
    __tablename__ = "expense_splits"
    __table_args__ = (UniqueConstraint("expense_id", "user_id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    expense_id: Mapped[str] = mapped_column(
        ForeignKey("expenses.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    amount_minor: Mapped[int] = mapped_column(BigInteger)
    base_minor: Mapped[int] = mapped_column(BigInteger)
    weight: Mapped[str] = mapped_column(String(32))


class Settlement(Base):
    __tablename__ = "settlements"
    __table_args__ = (CheckConstraint("amount_minor > 0 AND from_user_id <> to_user_id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    trip_id: Mapped[str] = mapped_column(ForeignKey("trips.id", ondelete="CASCADE"), index=True)
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    from_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    to_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    amount_minor: Mapped[int] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    version: Mapped[int] = mapped_column(default=1)
