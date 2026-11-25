from collections import Counter, defaultdict
from datetime import date
from itertools import pairwise
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header, Query
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from .availability_models import AvailabilityEntry
from .core import audit, check_version, current_user, fail, get_db, require_member
from .decisions import creation_id
from .models import Membership, User
from .realtime import hub

router = APIRouter(prefix="/trips/{trip_id}/availability", tags=["日期協調"])
Db = Annotated[Session, Depends(get_db)]
Actor = Annotated[User, Depends(current_user)]


class EntryInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    start_date: date
    end_date: date | None = None
    status: Literal["yes", "maybe", "no"]

    @model_validator(mode="after")
    def validate_interval(self):
        if self.end_date is None:
            self.end_date = self.start_date
        if self.end_date < self.start_date:
            raise ValueError("結束日期不能早於開始日期。")
        return self


class EntryEdit(EntryInput):
    version: int = Field(ge=1)


def entry_view(entry: AvailabilityEntry):
    return {
        field: getattr(entry, field)
        for field in ("id", "user_id", "start_date", "end_date", "status", "version")
    }


def recommend(rows: list[AvailabilityEntry], member_count: int):
    # Use interval boundaries so even widely separated dates never expand into daily rows.
    boundaries = defaultdict(Counter)
    for row in rows:
        boundaries[row.start_date.toordinal()][row.user_id, row.status] += 1
        boundaries[row.end_date.toordinal() + 1][row.user_id, row.status] -= 1
    dates = sorted(day for day, changes in boundaries.items() if any(changes.values()))
    counts = Counter()
    segments = []
    for start, end in pairwise(dates):
        for (_, status), delta in boundaries[start].items():
            counts[status] += delta
        yes, maybe, no = counts["yes"], counts["maybe"], counts["no"]
        if yes + maybe == 0:
            continue
        item = {
            "start_date": date.fromordinal(start),
            "end_date": date.fromordinal(end - 1),
            "yes": yes,
            "maybe": maybe,
            "no": no,
            "unknown": member_count - yes - maybe - no,
        }
        segments.append(item)
    return sorted(
        segments,
        key=lambda interval: (
            -interval["yes"],
            interval["no"],
            -interval["maybe"],
            -(interval["end_date"] - interval["start_date"]).days,
            interval["start_date"],
        ),
    )


@router.get("")
def availability(trip_id: str, db: Db, actor: Actor):
    require_member(db, trip_id, actor.id)
    active = list(
        db.scalars(
            select(Membership.user_id).where(
                Membership.trip_id == trip_id, Membership.left_at.is_(None)
            )
        )
    )
    rows = list(
        db.scalars(
            select(AvailabilityEntry)
            .where(AvailabilityEntry.trip_id == trip_id, AvailabilityEntry.user_id.in_(active))
            .order_by(
                AvailabilityEntry.start_date, AvailabilityEntry.end_date, AvailabilityEntry.id
            )
        )
    )
    members = len(active)
    return {
        "entries": [entry_view(e) for e in rows],
        "recommendations": recommend(rows, members),
        "member_count": members,
    }


def ensure_no_overlap(db, trip_id, user_id, body, entry_id):
    duplicate = db.scalar(
        select(AvailabilityEntry.id)
        .where(
            AvailabilityEntry.trip_id == trip_id,
            AvailabilityEntry.user_id == user_id,
            AvailabilityEntry.id != entry_id,
            AvailabilityEntry.start_date <= body.end_date,
            AvailabilityEntry.end_date >= body.start_date,
        )
        .limit(1)
    )
    if duplicate:
        fail(409, "AVAILABILITY_OVERLAP", "日期與你現有的標記重疊，請修改原標記或選擇其他日期。")


def editable(db, trip_id, entry_id, actor, version):
    require_member(db, trip_id, actor.id, lock=True)
    entry = db.get(AvailabilityEntry, entry_id)
    if not entry or entry.trip_id != trip_id:
        fail(404, "AVAILABILITY_NOT_FOUND", "找不到這筆日期標記。")
    if entry.user_id != actor.id:
        fail(403, "AVAILABILITY_FORBIDDEN", "只能修改自己的日期標記。")
    check_version(entry, version)
    return entry


async def finish(db, entry, actor, action):
    db.flush()
    trip_id, entry_id = entry.trip_id, entry.id
    audit(db, trip_id, actor.id, "availability", entry_id, action)
    db.commit()
    await hub.publish(trip_id, {"type": "availability." + action, "id": entry_id})


@router.post("", status_code=201)
async def create_entry(
    trip_id: str,
    body: EntryInput,
    db: Db,
    actor: Actor,
    idempotency_key: Annotated[str | None, Header(max_length=128)] = None,
):
    require_member(db, trip_id, actor.id, lock=True)
    entry_id, existing = creation_id(db, AvailabilityEntry, actor, trip_id, body, idempotency_key)
    if existing:
        return entry_view(existing)
    ensure_no_overlap(db, trip_id, actor.id, body, entry_id)
    entry = AvailabilityEntry(id=entry_id, trip_id=trip_id, user_id=actor.id, **body.model_dump())
    db.add(entry)
    await finish(db, entry, actor, "created")
    return entry_view(entry)


@router.patch("/{entry_id}")
async def edit_entry(trip_id: str, entry_id: str, body: EntryEdit, db: Db, actor: Actor):
    entry = editable(db, trip_id, entry_id, actor, body.version)
    ensure_no_overlap(db, trip_id, actor.id, body, entry_id)
    entry.start_date, entry.end_date, entry.status = body.start_date, body.end_date, body.status
    entry.version += 1
    await finish(db, entry, actor, "updated")
    return entry_view(entry)


@router.delete("/{entry_id}", status_code=204)
async def delete_entry(
    trip_id: str, entry_id: str, db: Db, actor: Actor, version: Annotated[int, Query(ge=1)]
):
    entry = editable(db, trip_id, entry_id, actor, version)
    db.delete(entry)
    await finish(db, entry, actor, "deleted")
