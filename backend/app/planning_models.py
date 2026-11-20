from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base, uid, utcnow


class TripDay(Base):
    __tablename__ = "trip_days"
    __table_args__ = (UniqueConstraint("trip_id", "day_number"), CheckConstraint("day_number >= 1"))
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    trip_id: Mapped[str] = mapped_column(ForeignKey("trips.id", ondelete="CASCADE"), index=True)
    day_number: Mapped[int]
    title: Mapped[str] = mapped_column(String(150), default="")
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Taipei")


class Place(Base):
    __tablename__ = "places"
    __table_args__ = (
        CheckConstraint("version > 0"),
        CheckConstraint("latitude BETWEEN -90 AND 90 AND longitude BETWEEN -180 AND 180"),
        CheckConstraint("(latitude IS NULL) = (longitude IS NULL)"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    trip_id: Mapped[str] = mapped_column(ForeignKey("trips.id", ondelete="CASCADE"), index=True)
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    editable_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    name: Mapped[str] = mapped_column(String(150))
    address: Mapped[str] = mapped_column(default="")
    latitude: Mapped[float | None]
    longitude: Mapped[float | None]
    country: Mapped[str] = mapped_column(default="")
    city: Mapped[str] = mapped_column(default="")
    category: Mapped[str] = mapped_column(default="place")
    tags: Mapped[list] = mapped_column(JSON, default=list)
    duration: Mapped[int | None]
    cost: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    opening_hours: Mapped[str] = mapped_column(default="")
    website: Mapped[str] = mapped_column(default="")
    photo_url: Mapped[str] = mapped_column(default="")
    notes: Mapped[str] = mapped_column(default="")
    version: Mapped[int] = mapped_column(default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Candidate(Base):
    __tablename__ = "trip_candidates"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    trip_id: Mapped[str] = mapped_column(ForeignKey("trips.id", ondelete="CASCADE"), index=True)
    place_id: Mapped[str] = mapped_column(ForeignKey("places.id", ondelete="CASCADE"), unique=True)
    status: Mapped[str] = mapped_column(default="want")
    removed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ItineraryItem(Base):
    __tablename__ = "itinerary_items"
    __table_args__ = (CheckConstraint("version > 0"), CheckConstraint("position >= 0"))
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    trip_id: Mapped[str] = mapped_column(ForeignKey("trips.id", ondelete="CASCADE"), index=True)
    day_id: Mapped[str] = mapped_column(ForeignKey("trip_days.id", ondelete="CASCADE"), index=True)
    place_id: Mapped[str | None] = mapped_column(ForeignKey("places.id"))
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    editable_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    title: Mapped[str] = mapped_column(String(150))
    item_type: Mapped[str] = mapped_column(default="custom")
    position: Mapped[int]
    start_time: Mapped[str | None] = mapped_column(String(5))
    end_time: Mapped[str | None] = mapped_column(String(5))
    duration: Mapped[int | None]
    notes: Mapped[str] = mapped_column(default="")
    version: Mapped[int] = mapped_column(default=1)


class EditLease(Base):
    __tablename__ = "edit_leases"
    __table_args__ = (UniqueConstraint("resource_type", "resource_id"),)
    # Only the tab that acquired the lease receives this identifier.
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    trip_id: Mapped[str] = mapped_column(ForeignKey("trips.id", ondelete="CASCADE"), index=True)
    resource_type: Mapped[str] = mapped_column(String(16))
    resource_id: Mapped[str] = mapped_column(String(36))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id", ondelete="CASCADE"))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
