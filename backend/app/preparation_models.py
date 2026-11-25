from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from .models import Base, uid, utcnow


class Task(Base):
    __tablename__ = "tasks"
    __table_args__ = (
        CheckConstraint("scope IN ('shared','personal')"),
        CheckConstraint("priority IN ('low','normal','high')"),
        CheckConstraint("version >= 1"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    trip_id: Mapped[str] = mapped_column(ForeignKey("trips.id", ondelete="CASCADE"), index=True)
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    scope: Mapped[str] = mapped_column(String(10))
    recurrence: Mapped[str] = mapped_column(String(12), default="none", server_default="none")
    period: Mapped[int] = mapped_column(default=1, server_default="1")
    priority: Mapped[str] = mapped_column(String(10))
    title: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(Text)
    due_date: Mapped[date | None] = mapped_column(Date)
    place_id: Mapped[str | None] = mapped_column(ForeignKey("places.id", ondelete="SET NULL"))
    item_id: Mapped[str | None] = mapped_column(
        ForeignKey("itinerary_items.id", ondelete="SET NULL")
    )
    version: Mapped[int] = mapped_column(default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class TaskAssignee(Base):
    __tablename__ = "task_assignees"
    __table_args__ = (
        UniqueConstraint("task_id", "user_id"),
        CheckConstraint("state IN ('todo','doing','done')"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    state: Mapped[str] = mapped_column(String(8), default="todo")


class TaskOccurrence(Base):
    __tablename__ = "task_occurrences"
    __table_args__ = (UniqueConstraint("task_id", "period"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), index=True)
    period: Mapped[int]
    due_date: Mapped[date] = mapped_column(Date)
    progress: Mapped[list] = mapped_column(JSON)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Booking(Base):
    __tablename__ = "bookings"
    __table_args__ = (
        CheckConstraint("kind IN ('flight','stay')"),
        CheckConstraint("price IS NULL OR price >= 0"),
        CheckConstraint("status IN ('planned','booked','cancelled')"),
        CheckConstraint("version >= 1"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    trip_id: Mapped[str] = mapped_column(ForeignKey("trips.id", ondelete="CASCADE"), index=True)
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    kind: Mapped[str] = mapped_column(String(8))
    title: Mapped[str] = mapped_column(String(160))
    status: Mapped[str] = mapped_column(String(12))
    currency: Mapped[str] = mapped_column(String(3))
    price: Mapped[Decimal | None] = mapped_column(Numeric(16, 4))
    reference: Mapped[str] = mapped_column(String(100))
    website: Mapped[str] = mapped_column(Text)
    # Each public leg records its own passengers and timestamps. Seat/baggage details are filtered at read time.
    segments: Mapped[list] = mapped_column(JSON)
    stay: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    item_id: Mapped[str | None] = mapped_column(
        ForeignKey("itinerary_items.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    version: Mapped[int] = mapped_column(default=1)
