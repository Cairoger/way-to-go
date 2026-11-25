from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    LargeBinary,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from .models import Base, uid, utcnow


class TripFile(Base):
    __tablename__ = "files"
    __table_args__ = (CheckConstraint("size > 0 AND version >= 1"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    trip_id: Mapped[str] = mapped_column(ForeignKey("trips.id", ondelete="CASCADE"), index=True)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    filename: Mapped[str] = mapped_column(String(180))
    mime: Mapped[str] = mapped_column(String(127))
    category: Mapped[str] = mapped_column(String(64), default="其他")
    size: Mapped[int]
    private: Mapped[bool] = mapped_column(Boolean, default=False)
    data: Mapped[bytes] = mapped_column(LargeBinary, deferred=True)
    preview_text: Mapped[str] = mapped_column(default="", deferred=True)
    version: Mapped[int] = mapped_column(default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    removed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class FilePermission(Base):
    __tablename__ = "file_permissions"
    __table_args__ = (UniqueConstraint("file_id", "user_id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    file_id: Mapped[str] = mapped_column(ForeignKey("files.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))


class FileLink(Base):
    __tablename__ = "file_links"
    __table_args__ = (UniqueConstraint("file_id", "kind", "target_id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    file_id: Mapped[str] = mapped_column(ForeignKey("files.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(16))
    target_id: Mapped[str] = mapped_column(String(36), index=True)
