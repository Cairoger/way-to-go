from datetime import datetime

from sqlalchemy import JSON, CheckConstraint, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from .models import Base, uid, utcnow


class GuestMerge(Base):
    __tablename__ = "account_merges"
    __table_args__ = (CheckConstraint("guest_id <> account_id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    guest_id: Mapped[str] = mapped_column(ForeignKey("users.id"), unique=True)
    account_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    # Private records of conflicting submissions and changed authorship. No trip API exposes this.
    history: Mapped[dict] = mapped_column(JSON)
