from calendar import monthrange
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Annotated, Literal

from fastapi import APIRouter, Header
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    StringConstraints,
    TypeAdapter,
    model_validator,
)
from sqlalchemy import or_, select

from .core import DB, Actor, audit, check_version, fail, require_member
from .file_access import bind_files, bound_files
from .models import Membership, User
from .planning import creation_request, record_creation
from .planning_models import ItineraryItem, Place
from .preparation_models import Booking, Task, TaskAssignee, TaskOccurrence
from .realtime import hub

router = APIRouter(tags=["行前清單與預訂"])
IdKey = Annotated[str | None, Header(alias="Idempotency-Key", max_length=128)]
Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=160)]
UserId = Annotated[str, Field(min_length=1, max_length=36)]
State = Literal["todo", "doing", "done"]


class Payload(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Version(Payload):
    version: int = Field(ge=1)


class TaskInput(Payload):
    scope: Literal["shared", "personal"] = "shared"
    title: Title
    description: str = Field(default="", max_length=4000)
    priority: Literal["low", "normal", "high"] = "normal"
    due_date: date | None = None
    assignees: list[UserId] = Field(default_factory=list, max_length=200)
    place_id: UserId | None = None
    item_id: UserId | None = None
    recurrence: Literal["none", "daily", "weekly", "monthly"] = "none"
    attachment_ids: list[UserId] | None = Field(None, max_length=30)

    @model_validator(mode="after")
    def validate_recurrence(self):
        if self.recurrence != "none" and not self.due_date:
            raise ValueError("重複任務需要本期截止日期。")
        return self


class TaskEdit(TaskInput, Version):
    pass


class Progress(Version):
    state: State


def check_links(db, trip_id, item_id, place_id=None, *, existing_item=None, existing_place=None):
    if item_id:
        item = db.get(ItineraryItem, item_id)
        if (
            not item
            or item.trip_id != trip_id
            or (item.deleted_at is not None and item_id != existing_item)
        ):
            fail(422, "INVALID_ITEM", "請選擇這個旅程中的活動。")
    if place_id:
        place = db.get(Place, place_id)
        if (
            not place
            or place.trip_id != trip_id
            or (place.deleted_at and place_id != existing_place)
        ):
            fail(422, "INVALID_PLACE", "請選擇這個旅程中的景點。")


def active_members(db, trip_id, ids):
    if not ids:
        return
    active = set(
        db.scalars(
            select(Membership.user_id).where(
                Membership.trip_id == trip_id,
                Membership.left_at.is_(None),
                Membership.user_id.in_(ids),
            )
        )
    )
    if set(ids) != active:
        fail(422, "INVALID_MEMBERS", "請選擇仍在旅程中的旅伴。")


def assignments(db, task_id):
    return db.scalars(select(TaskAssignee).where(TaskAssignee.task_id == task_id)).all()


def task_json(db, row, user_id, linked=None):
    people = db.execute(
        select(TaskAssignee, User.nickname)
        .join(User, User.id == TaskAssignee.user_id)
        .where(TaskAssignee.task_id == row.id)
        .order_by(User.nickname, User.id)
    ).all()
    states = [a.state for a, _ in people]
    return {
        **{
            k: getattr(row, k)
            for k in (
                "id",
                "title",
                "description",
                "scope",
                "priority",
                "due_date",
                "recurrence",
                "period",
                "place_id",
                "item_id",
                "version",
                "created_by",
            )
        },
        "assignees": [
            {"user_id": a.user_id, "nickname": name, "state": a.state} for a, name in people
        ],
        "attachment_ids": [
            f["id"]
            for f in (
                linked
                if linked is not None
                else bound_files(db, row.trip_id, "task", user_id, [row.id])[row.id]
            )
        ],
        "completed_periods": [
            {
                "period": entry.period,
                "due_date": entry.due_date,
                "completed_at": entry.completed_at,
                "progress": entry.progress,
            }
            for entry in db.scalars(
                select(TaskOccurrence)
                .where(TaskOccurrence.task_id == row.id)
                .order_by(TaskOccurrence.period)
            )
        ],
        "state": "done"
        if states and all(s == "done" for s in states)
        else "doing"
        if any(s != "todo" for s in states)
        else "todo",
    }


def task_for_write(db, trip_id, task_id, actor, version, *, editing=False):
    trip = require_member(db, trip_id, actor.id, lock=True)
    row = db.get(Task, task_id)
    if (
        not row
        or row.trip_id != trip_id
        or (row.scope == "personal" and row.created_by != actor.id)
    ):
        fail(404, "TASK_NOT_FOUND", "找不到這項任務。")
    if editing and row.created_by != actor.id and trip.owner_id != actor.id:
        fail(403, "TASK_EDITOR", "僅建立者或旅程擁有者可管理共用任務。")
    check_version(row, version)
    return row


def save_assignees(db, row, ids):
    required = set(ids)
    if row.scope == "personal":
        if required - {row.created_by}:
            fail(422, "PERSONAL_TASK", "個人任務只能指派給自己。")
        required = {row.created_by}
    existing = {a.user_id: a for a in assignments(db, row.id)}
    active_members(db, row.trip_id, required - existing.keys())
    for user_id in required - existing.keys():
        db.add(TaskAssignee(task_id=row.id, user_id=user_id))
    for user_id in existing.keys() - required:
        db.delete(existing[user_id])


async def finish_task(db, row, actor, action):
    audit(db, row.trip_id, actor.id, "task", row.id, action)
    db.commit()
    event = {"type": "tasks.changed"}
    if row.scope == "shared":
        await hub.publish(row.trip_id, event)
    else:
        await hub.publish_to(row.trip_id, row.created_by, event)


@router.get("/trips/{trip_id}/tasks")
def list_tasks(trip_id: str, db: DB, user: Actor):
    require_member(db, trip_id, user.id)
    query = (
        select(Task)
        .where(Task.trip_id == trip_id, or_(Task.scope == "shared", Task.created_by == user.id))
        .order_by(Task.due_date.asc().nulls_last(), Task.created_at, Task.id)
    )
    linked = bound_files(db, trip_id, "task", user.id)
    return [task_json(db, row, user.id, linked[row.id]) for row in db.scalars(query)]


@router.post("/trips/{trip_id}/tasks", status_code=201)
async def create_task(trip_id: str, body: TaskInput, db: DB, user: Actor, key: IdKey = None):
    require_member(db, trip_id, user.id, lock=True)
    existing, record = creation_request(db, Task, user.id, trip_id, key, body)
    if existing:
        return task_json(db, existing, user.id)
    check_links(db, trip_id, body.item_id, body.place_id)
    row = Task(
        trip_id=trip_id,
        created_by=user.id,
        **body.model_dump(exclude={"assignees", "attachment_ids"}),
    )
    db.add(row)
    db.flush()
    save_assignees(db, row, body.assignees)
    if body.attachment_ids:
        bind_files(db, trip_id, "task", row.id, body.attachment_ids, user.id)
    record_creation(db, record, row.id)
    await finish_task(db, row, user, "create")
    return task_json(db, row, user.id)


@router.put("/trips/{trip_id}/tasks/{task_id}")
async def edit_task(trip_id: str, task_id: str, body: TaskEdit, db: DB, user: Actor):
    row = task_for_write(db, trip_id, task_id, user, body.version, editing=True)
    if row.scope != body.scope:
        fail(422, "TASK_SCOPE", "建立後無法變更清單的可見範圍。")
    check_links(
        db,
        trip_id,
        body.item_id,
        body.place_id,
        existing_item=row.item_id,
        existing_place=row.place_id,
    )
    excluded = {"assignees", "scope", "version", "attachment_ids"}
    if "recurrence" not in body.model_fields_set:
        excluded.add("recurrence")
        if row.recurrence != "none" and not body.due_date:
            fail(422, "TASK_RECURRING_DATE", "重複任務需要本期截止日期。")
    for field, value in body.model_dump(exclude=excluded).items():
        setattr(row, field, value)
    save_assignees(db, row, body.assignees)
    if body.attachment_ids is not None:
        bind_files(db, trip_id, "task", row.id, body.attachment_ids, user.id)
    row.version += 1
    await finish_task(db, row, user, "update")
    return task_json(db, row, user.id)


@router.put("/trips/{trip_id}/tasks/{task_id}/progress")
async def change_progress(trip_id: str, task_id: str, body: Progress, db: DB, user: Actor):
    row = task_for_write(db, trip_id, task_id, user, body.version)
    person = db.scalar(
        select(TaskAssignee).where(TaskAssignee.task_id == row.id, TaskAssignee.user_id == user.id)
    )
    if not person:
        fail(403, "TASK_ASSIGNEE", "只有負責人可更新自己的完成狀態。")
    person.state = body.state
    if row.recurrence != "none" and body.state == "done":
        people = assignments(db, row.id)
        if all(a.state == "done" for a in people):
            db.add(
                TaskOccurrence(
                    task_id=row.id,
                    period=row.period,
                    due_date=row.due_date,
                    progress=[{"user_id": a.user_id, "state": a.state} for a in people],
                )
            )
            if row.recurrence == "monthly":
                month = row.due_date.month % 12 + 1
                year = row.due_date.year + (month == 1)
                anchor = db.scalar(
                    select(TaskOccurrence.due_date).where(
                        TaskOccurrence.task_id == row.id, TaskOccurrence.period == 1
                    )
                )
                row.due_date = date(
                    year, month, min((anchor or row.due_date).day, monthrange(year, month)[1])
                )
            else:
                row.due_date += timedelta(days=1 if row.recurrence == "daily" else 7)
            row.period += 1
            for a in people:
                a.state = "todo"
    row.version += 1
    await finish_task(db, row, user, "progress")
    return task_json(db, row, user.id)


@router.delete("/trips/{trip_id}/tasks/{task_id}", status_code=204)
async def delete_task(trip_id: str, task_id: str, body: Version, db: DB, user: Actor):
    row = task_for_write(db, trip_id, task_id, user, body.version, editing=True)
    db.delete(row)
    await finish_task(db, row, user, "delete")


class Passenger(Payload):
    user_id: UserId
    seat: str = Field(default="", max_length=30)
    baggage: str = Field(default="", max_length=180)


class PublicFlightSegment(Payload):
    airline: str = Field(default="", max_length=100)
    number: Title
    origin: Title
    destination: Title
    departure: datetime
    arrival: datetime
    departure_terminal: str = Field(default="", max_length=60)
    arrival_terminal: str = Field(default="", max_length=60)

    @model_validator(mode="after")
    def valid_leg(self):
        if (
            self.departure.tzinfo is None
            or self.arrival.tzinfo is None
            or self.arrival <= self.departure
        ):
            raise ValueError("航班時間須包含時差，且抵達時間須晚於起飛時間。")
        return self


class FlightSegment(PublicFlightSegment):
    passengers: list[Passenger] = Field(default_factory=list, max_length=200)

    @model_validator(mode="after")
    def unique_passengers(self):
        if len({p.user_id for p in self.passengers}) != len(self.passengers):
            raise ValueError("每航段的旅客不可重複。")
        return self


class PublicStay(Payload):
    address: str = Field(default="", max_length=500)
    room: str = Field(default="", max_length=120)
    check_in: date
    check_out: date

    @model_validator(mode="after")
    def valid_stay(self):
        if self.check_out <= self.check_in:
            raise ValueError("退房日期須晚於入住日期。")
        return self


class Stay(PublicStay):
    guests: list[UserId] = Field(default_factory=list, max_length=200)

    @model_validator(mode="after")
    def unique_guests(self):
        if len(set(self.guests)) != len(self.guests):
            raise ValueError("同一筆住宿的住客不可重複。")
        return self


class PublicBooking(Payload):
    kind: Literal["flight", "stay"]
    title: Title
    status: Literal["planned", "booked", "cancelled"] = "planned"
    price: Decimal | None = Field(default=None, ge=0, max_digits=16, decimal_places=4)
    currency: str = Field(default="TWD", pattern="^[A-Z]{3}$")
    website: str = Field(default="", max_length=1000)
    item_id: UserId | None = None
    segments: list[PublicFlightSegment] = Field(default_factory=list, max_length=30)
    stay: PublicStay | None = None

    @model_validator(mode="after")
    def valid(self):
        if (
            self.kind == "flight"
            and (not self.segments or self.stay)
            or self.kind == "stay"
            and (not self.stay or self.segments)
        ):
            raise ValueError("請填寫航段或住宿的完整資訊。")
        if self.website:
            self.website = str(TypeAdapter(HttpUrl).validate_python(self.website))
        return self


class BookingInput(PublicBooking):
    reference: str = Field(default="", max_length=100)
    segments: list[FlightSegment] = Field(default_factory=list, max_length=30)
    stay: Stay | None = None


class PublicBookingEdit(PublicBooking, Version):
    pass


class BookingEdit(BookingInput, Version):
    pass


def traveller_ids(segments, stay):
    return {p["user_id"] for leg in segments for p in leg["passengers"]} | set(
        (stay or {}).get("guests", [])
    )


def booking_json(row, user_id, *, public_editor=False):
    authorized = user_id == row.created_by or user_id in traveller_ids(row.segments, row.stay)
    segments = []
    for leg in row.segments:
        people = [
            p
            if (p["user_id"] == user_id or row.created_by == user_id)
            else {"user_id": p["user_id"]}
            for p in leg["passengers"]
        ]
        segments.append({**leg, "passengers": people})
    result = {
        **{
            k: getattr(row, k)
            for k in (
                "id",
                "kind",
                "title",
                "status",
                "currency",
                "website",
                "item_id",
                "created_by",
                "version",
                "stay",
            )
        },
        "segments": segments,
        "can_edit_public": public_editor,
        "price": str(row.price) if row.price is not None else None,
    }
    if authorized:
        result["reference"] = row.reference
    return result


@router.get("/trips/{trip_id}/bookings")
def list_bookings(trip_id: str, db: DB, user: Actor):
    trip = require_member(db, trip_id, user.id)
    author_active = (
        select(Membership.id)
        .where(
            Membership.trip_id == Booking.trip_id,
            Membership.user_id == Booking.created_by,
            Membership.left_at.is_(None),
        )
        .exists()
    )
    return [
        booking_json(row, user.id, public_editor=user.id == trip.owner_id and not active)
        for row, active in db.execute(
            select(Booking, author_active)
            .where(Booking.trip_id == trip_id)
            .order_by(Booking.created_at, Booking.id)
        )
    ]


def booking_for_write(db, trip_id, booking_id, user, version, *, public_only=False):
    trip = require_member(db, trip_id, user.id, lock=True)
    row = db.get(Booking, booking_id)
    if not row or row.trip_id != trip_id:
        fail(404, "BOOKING_ABSENT", "找不到這筆預訂。")
    if public_only:
        creator_active = db.scalar(
            select(Membership.id).where(
                Membership.trip_id == trip_id,
                Membership.user_id == row.created_by,
                Membership.left_at.is_(None),
            )
        )
        if user.id != trip.owner_id or creator_active:
            fail(403, "PUBLIC_BOOKING_EDITOR", "建立者退出旅程後，擁有者才可維護預訂的公開資料。")
    elif row.created_by != user.id:
        fail(403, "BOOKING_EDITOR", "只有建立者可以編輯預訂。")
    check_version(row, version)
    return row


def set_booking(db, row, body):
    check_links(db, row.trip_id, body.item_id, existing_item=row.item_id)
    data = body.model_dump(mode="json", exclude={"version"})
    known = traveller_ids(row.segments or [], row.stay)
    active_members(db, row.trip_id, traveller_ids(data["segments"], data["stay"]) - known)
    for field, value in data.items():
        setattr(row, field, body.price if field == "price" else value)


async def finish_booking(db, row, user, action):
    audit(db, row.trip_id, user.id, "booking", row.id, action)
    db.commit()
    await hub.publish(row.trip_id, {"type": "booking.changed"})


@router.post("/trips/{trip_id}/bookings", status_code=201)
async def create_booking(trip_id: str, body: BookingInput, db: DB, user: Actor, key: IdKey = None):
    require_member(db, trip_id, user.id, lock=True)
    existing, record = creation_request(db, Booking, user.id, trip_id, key, body)
    if existing:
        return booking_json(existing, user.id)
    row = Booking(trip_id=trip_id, created_by=user.id)
    set_booking(db, row, body)
    db.add(row)
    db.flush()
    record_creation(db, record, row.id)
    await finish_booking(db, row, user, "create")
    return booking_json(row, user.id)


@router.put("/trips/{trip_id}/bookings/{booking_id}")
async def edit_booking(trip_id: str, booking_id: str, body: BookingEdit, db: DB, user: Actor):
    row = booking_for_write(db, trip_id, booking_id, user, body.version)
    set_booking(db, row, body)
    row.version += 1
    await finish_booking(db, row, user, "update")
    return booking_json(row, user.id)


@router.delete("/trips/{trip_id}/bookings/{booking_id}", status_code=204)
async def delete_booking(trip_id: str, booking_id: str, body: Version, db: DB, user: Actor):
    row = booking_for_write(db, trip_id, booking_id, user, body.version)
    db.delete(row)
    await finish_booking(db, row, user, "delete")


@router.put("/trips/{trip_id}/bookings/{booking_id}/public")
async def update_public_booking(
    trip_id: str, booking_id: str, body: PublicBookingEdit, db: DB, user: Actor
):
    row = booking_for_write(db, trip_id, booking_id, user, body.version, public_only=True)
    if row.kind != body.kind or len(row.segments) != len(body.segments):
        fail(422, "BOOKING_STRUCTURE", "請保留既有預訂類型與航段數量。")
    check_links(db, trip_id, body.item_id, existing_item=row.item_id)
    for field in ("title", "status", "price", "currency", "website", "item_id"):
        setattr(row, field, getattr(body, field))
    # The input models reject all traveller identities, seats, baggage and booking references.
    row.segments = [
        old | leg.model_dump(mode="json")
        for old, leg in zip(row.segments, body.segments, strict=True)
    ]
    if body.stay:
        row.stay = row.stay | body.stay.model_dump(mode="json")
    row.version += 1
    await finish_booking(db, row, user, "update_public")
    return booking_json(row, user.id, public_editor=True)
