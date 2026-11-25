from datetime import date

from sqlalchemy import CheckConstraint, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from .models import Base, uid


class AvailabilityEntry(Base):
    __tablename__ = "availability_entries"
    __table_args__ = (
        CheckConstraint("end_date >= start_date", name="ck_availability_order"),
        CheckConstraint("status IN ('yes','maybe','no')", name="ck_availability_status"),
        CheckConstraint("version >= 1", name="ck_availability_version"),
        Index("ix_availability_member_dates", "trip_id", "user_id", "start_date", "end_date"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    trip_id: Mapped[str] = mapped_column(ForeignKey("trips.id", ondelete="CASCADE"))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    start_date: Mapped[date]
    end_date: Mapped[date]
    status: Mapped[str] = mapped_column(String(8))
    version: Mapped[int] = mapped_column(default=1)
