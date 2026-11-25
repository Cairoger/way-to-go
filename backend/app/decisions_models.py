from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from .models import Base, uid, utcnow


class Poll(Base):
    __tablename__ = "polls"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    trip_id: Mapped[str] = mapped_column(ForeignKey("trips.id", ondelete="CASCADE"), index=True)
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    editable_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    version: Mapped[int] = mapped_column(Integer, default=1)


class PollRound(Base):
    __tablename__ = "poll_rounds"
    __table_args__ = (
        UniqueConstraint("poll_id", "number"),
        CheckConstraint("kind IN ('place', 'date')"),
        CheckConstraint(
            "mode IN ('single','multiple','rating','ranked')", name="ck_poll_round_mode"
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    poll_id: Mapped[str] = mapped_column(ForeignKey("polls.id", ondelete="CASCADE"))
    number: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(180))
    kind: Mapped[str] = mapped_column(String(12))
    mode: Mapped[str] = mapped_column(String(12))
    deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    options_version: Mapped[int] = mapped_column(Integer, default=1)


class PollOption(Base):
    __tablename__ = "poll_options"
    __table_args__ = (UniqueConstraint("round_id", "option_text"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    round_id: Mapped[str] = mapped_column(ForeignKey("poll_rounds.id", ondelete="CASCADE"))
    option_text: Mapped[str] = mapped_column(String(180))
    place_id: Mapped[str | None] = mapped_column(ForeignKey("places.id"))
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    ordinal: Mapped[int] = mapped_column(Integer)


class Ballot(Base):
    __tablename__ = "ballots"
    __table_args__ = (UniqueConstraint("round_id", "user_id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    round_id: Mapped[str] = mapped_column(ForeignKey("poll_rounds.id", ondelete="CASCADE"))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    version: Mapped[int] = mapped_column(Integer, default=1)
    options_version: Mapped[int] = mapped_column(Integer)


class BallotChoice(Base):
    __tablename__ = "ballot_choices"
    __table_args__ = (
        UniqueConstraint("ballot_id", "option_id"),
        CheckConstraint("value BETWEEN 1 AND 5", name="ck_ballot_choice_value"),
        CheckConstraint("rank BETWEEN 1 AND 60", name="ck_ballot_choice_rank"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    ballot_id: Mapped[str] = mapped_column(ForeignKey("ballots.id", ondelete="CASCADE"))
    option_id: Mapped[str] = mapped_column(ForeignKey("poll_options.id", ondelete="CASCADE"))
    value: Mapped[int | None]
    rank: Mapped[int | None]


class PollAdoption(Base):
    __tablename__ = "poll_adoptions"
    __table_args__ = (UniqueConstraint("option_id", "day_id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    option_id: Mapped[str] = mapped_column(ForeignKey("poll_options.id", ondelete="CASCADE"))
    day_id: Mapped[str] = mapped_column(ForeignKey("trip_days.id", ondelete="CASCADE"))
    item_id: Mapped[str | None] = mapped_column(
        ForeignKey("itinerary_items.id", ondelete="SET NULL")
    )


class Comment(Base):
    __tablename__ = "comments"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    trip_id: Mapped[str] = mapped_column(ForeignKey("trips.id", ondelete="CASCADE"), index=True)
    author_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    parent_id: Mapped[str | None] = mapped_column(ForeignKey("comments.id", ondelete="CASCADE"))
    content: Mapped[str] = mapped_column(Text)
    deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(Integer, default=1)
