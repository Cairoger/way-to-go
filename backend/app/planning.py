from datetime import timedelta
from decimal import Decimal
from typing import Annotated, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Header, Query, Request
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    StringConstraints,
    TypeAdapter,
    ValidationError,
    field_validator,
    model_validator,
)
from sqlalchemy import delete, func, select, update

from app.core import DB, Actor, audit, digest, fail, require_member
from app.models import AuditLog, CreationKey, User, as_utc, utcnow
from app.place_search import search_public_places
from app.planning_models import Candidate, EditLease, ItineraryItem, Place, TripDay
from app.realtime import hub

router = APIRouter(tags=["行程與景點"])
Key = Annotated[str | None, Header(alias="Idempotency-Key", max_length=128)]
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=150)]
ItemType = Literal["place", "food", "transit", "stay", "flight", "custom"]
Status = Literal["must", "want", "maybe", "skip"]
Clock = Annotated[str, StringConstraints(pattern=r"^(?:[01][0-9]|2[0-3]):[0-5][0-9]$")]
Duration = Annotated[int, Field(gt=0, le=1440)]


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class DayInput(Input):
    title: str = Field("", max_length=150)
    timezone: str = Field("Asia/Taipei", max_length=64)

    @field_validator("timezone")
    @classmethod
    def valid_zone(cls, value):
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError):
            raise ValueError("請使用有效的 IANA 時區。")
        return value


class PlaceFields(Input):
    address: str = Field("", max_length=800)
    latitude: float | None = Field(None, ge=-90, le=90)
    longitude: float | None = Field(None, ge=-180, le=180)
    country: str = Field("", max_length=100)
    city: str = Field("", max_length=100)
    category: ItemType = "place"
    status: Status = "want"
    tags: list[Annotated[str, StringConstraints(min_length=1, max_length=40)]] = Field(
        default_factory=list, max_length=20
    )
    duration: Duration | None = None
    cost: Decimal | None = Field(None, ge=0, max_digits=14, decimal_places=2)
    opening_hours: str = Field("", max_length=400)
    website: str = Field("", max_length=2000)
    photo_url: str = Field("", max_length=2000)
    notes: str = Field("", max_length=4000)

    @field_validator("website", "photo_url")
    @classmethod
    def valid_url(cls, value):
        if value:
            TypeAdapter(HttpUrl).validate_python(value)
        return value


class PlaceInput(PlaceFields):
    name: Name

    @model_validator(mode="after")
    def coordinate_pair(self):
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("請一起填寫經度與緯度。")
        return self


class Mutation(Input):
    version: int = Field(gt=0)
    lease_id: str = Field(min_length=1, max_length=36)


class PlaceEdit(PlaceFields, Mutation):
    name: Name | None = None


class CandidateRestore(Mutation):
    place_id: str


class ItemFields(Input):
    item_type: ItemType = "custom"
    place_id: str | None = None
    start_time: Clock | None = None
    end_time: Clock | None = None
    duration: Duration | None = None
    notes: str = Field("", max_length=4000)


class ItemInput(ItemFields):
    title: Name

    @model_validator(mode="after")
    def time_range(self):
        if (self.end_time or self.duration) and not self.start_time:
            raise ValueError("設定結束或停留時間時，請先填寫開始時間。")
        if self.end_time and (self.duration or self.end_time <= self.start_time):
            raise ValueError("結束時間須晚於開始時間，請擇一填寫結束或停留時間。")
        return self


class ItemEdit(ItemFields, Mutation):
    title: Name | None = None


class ItemMove(Mutation):
    day_id: str
    position: int = Field(ge=0)


class LeaseInput(Input):
    resource_type: Literal["place", "item"]
    resource_id: str


def transfer_edits(db, trip_id, from_user_id, to_user_id):
    for model in (ItineraryItem, Place):
        db.execute(
            update(model)
            .where(model.trip_id == trip_id, model.editable_by == from_user_id)
            .values(editable_by=to_user_id, version=model.version + 1)
        )
    db.execute(
        delete(EditLease).where(EditLease.trip_id == trip_id, EditLease.user_id == from_user_id)
    )


def access(db, model, resource_id, user_id, lock=False):
    trip_id = db.scalar(select(model.trip_id).where(model.id == resource_id))
    if not trip_id:
        fail(404, "not_found", "找不到這筆旅程資料。")
    require_member(db, trip_id, user_id, lock=lock)
    row = db.get(model, resource_id, populate_existing=True)
    if row is None:
        fail(404, "not_found", "這筆資料已移除。")
    return row


def require_editor(row, user_id):
    if row.editable_by != user_id:
        fail(403, "not_editor", "只有目前的編輯權持有人可以修改這筆資料。")


async def finish(db, trip_id, event, actor, kind, entity_id, changes=None):
    audit(db, trip_id, actor, kind, entity_id, event, changes)
    db.commit()
    await hub.publish(trip_id, {"type": event, "resource_id": entity_id})


def creation_request(db, model, user_id, parent_id, key, payload):
    """Call only after locking the parent trip. Persist the key with the created object."""
    if not key:
        return None, None
    operation = model.__tablename__
    fingerprint = digest(parent_id + payload.model_dump_json())
    previous = db.scalar(
        select(CreationKey).where(
            CreationKey.user_id == user_id,
            CreationKey.operation == operation,
            CreationKey.key == key,
        )
    )
    if previous:
        if previous.request_hash != fingerprint:
            fail(409, "idempotency_conflict", "相同請求識別碼已用於其他資料。")
        row = db.get(model, previous.resource_id)
        if row is None:
            fail(409, "resource_removed", "該請求建立的資料已被移除。")
        return row, None
    return None, CreationKey(
        user_id=user_id, operation=operation, key=key, request_hash=fingerprint
    )


def record_creation(db, key, resource_id):
    if key is not None:
        key.resource_id = resource_id
        db.add(key)


def merge_patch(schema, original, patch):
    supplied = patch.model_dump(exclude_unset=True, exclude={"lease_id", "version"})
    try:
        return schema.model_validate(original | supplied).model_dump()
    except ValidationError as exc:
        message = exc.errors()[0]["msg"].removeprefix("Value error, ")
        fail(
            422,
            "invalid_edit",
            message if any("\u4e00" <= c <= "\u9fff" for c in message) else "請檢查修改的欄位。",
        )


def lease_for(db, kind, resource_id):
    return db.scalar(
        select(EditLease).where(
            EditLease.resource_type == kind, EditLease.resource_id == resource_id
        )
    )


def active(lease):
    return lease is not None and as_utc(lease.expires_at) > utcnow()


def authorize_write(db, request, row, kind, user_id, mutation):
    require_editor(row, user_id)
    if row.version != mutation.version:
        fail(409, "stale_version", "資料已更新，請重新開啟最新內容。")
    lease = lease_for(db, kind, row.id)
    if not active(lease) or (lease.id, lease.user_id, lease.session_id) != (
        mutation.lease_id,
        user_id,
        request.state.session_id,
    ):
        fail(423, "lease_required", "編輯鎖定已失效，請重新開啟編輯。")
    db.delete(lease)


@router.post("/edit-leases")
async def acquire_lease(payload: LeaseInput, request: Request, db: DB, user: Actor):
    model = Place if payload.resource_type == "place" else ItineraryItem
    resource = access(db, model, payload.resource_id, user.id, lock=True)
    require_editor(resource, user.id)
    previous = lease_for(db, payload.resource_type, resource.id)
    if active(previous):
        editor = db.get(User, previous.user_id)
        fail(423, "already_editing", f"{editor.nickname} 正在編輯這筆資料。")
    if previous:
        db.delete(previous)
        db.flush()
    lease = EditLease(
        trip_id=resource.trip_id,
        resource_id=resource.id,
        resource_type=payload.resource_type,
        user_id=user.id,
        session_id=request.state.session_id,
        expires_at=utcnow() + timedelta(seconds=90),
    )
    db.add(lease)
    db.commit()
    await hub.publish(resource.trip_id, {"type": "locks"})
    return {"id": lease.id, "expires_at": lease.expires_at, "version": resource.version}


def owned_lease(db, lease_id, request, user):
    lease = access(db, EditLease, lease_id, user.id, lock=True)
    if (lease.user_id, lease.session_id) != (user.id, request.state.session_id):
        fail(403, "not_editor", "這個編輯鎖定屬於其他工作階段。")
    return lease


@router.post("/edit-leases/{lease_id}/renew")
def renew_lease(lease_id: str, request: Request, db: DB, user: Actor):
    lease = owned_lease(db, lease_id, request, user)
    if not active(lease):
        fail(423, "lease_expired", "鎖定已到期，請重新開啟編輯。")
    lease.expires_at = utcnow() + timedelta(seconds=90)
    db.commit()
    return {"expires_at": lease.expires_at}


@router.delete("/edit-leases/{lease_id}")
async def release_lease(lease_id: str, request: Request, db: DB, user: Actor):
    lease = owned_lease(db, lease_id, request, user)
    trip_id = lease.trip_id
    db.delete(lease)
    db.commit()
    await hub.publish(trip_id, {"type": "locks"})
    return {"released": True}


def editors(db, trip_id):
    return dict(
        db.execute(
            select(EditLease.resource_id, User.nickname)
            .join(User, User.id == EditLease.user_id)
            .where(EditLease.trip_id == trip_id, EditLease.expires_at > utcnow())
        ).all()
    )


def fields(row, names):
    return {name: getattr(row, name) for name in names}


def place_dict(place, candidate, editing_by=None):
    data = fields(
        place,
        (set(PlaceInput.model_fields) - {"status"})
        | {
            "id",
            "created_by",
            "editable_by",
            "version",
            "created_at",
            "updated_at",
        },
    )
    data.update(
        candidate=not candidate.removed_at,
        status=candidate.status,
        candidate_id=candidate.id,
        editing_by=editing_by,
    )
    return data


@router.get("/trips/{trip_id}/places")
def list_places(trip_id: str, db: DB, user: Actor):
    require_member(db, trip_id, user.id)
    editing = editors(db, trip_id)
    rows = db.execute(
        select(Place, Candidate)
        .join(Candidate, Candidate.place_id == Place.id)
        .where(Place.trip_id == trip_id)
        .order_by(Place.created_at, Place.id)
    )
    return [place_dict(place, candidate, editing.get(place.id)) for place, candidate in rows]


@router.get("/trips/{trip_id}/place-search")
async def search_places(
    trip_id: str, db: DB, user: Actor, q: Annotated[str, Query(min_length=1, max_length=120)]
):
    require_member(db, trip_id, user.id)
    return await search_public_places(q, user.id)


@router.get("/places/{place_id}/history")
def place_history(place_id: str, db: DB, user: Actor):
    place = access(db, Place, place_id, user.id)
    rows = db.execute(
        select(AuditLog, User.nickname)
        .join(User, User.id == AuditLog.actor_id)
        .where(
            AuditLog.trip_id == place.trip_id,
            AuditLog.entity_type == "place",
            AuditLog.entity_id == place_id,
        )
        .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
    )
    return [
        {
            "actor": nickname,
            "action": entry.action,
            "changes": entry.changes,
            "created_at": as_utc(entry.created_at),
        }
        for entry, nickname in rows
    ]


@router.post("/trips/{trip_id}/places", status_code=201)
async def create_place(trip_id: str, payload: PlaceInput, db: DB, user: Actor, key: Key = None):
    require_member(db, trip_id, user.id, lock=True)
    previous, record = creation_request(db, Place, user.id, trip_id, key, payload)
    if previous:
        return place_dict(
            previous, db.scalar(select(Candidate).where(Candidate.place_id == previous.id))
        )
    place = Place(
        trip_id=trip_id,
        created_by=user.id,
        editable_by=user.id,
        **payload.model_dump(exclude={"status"}),
    )
    db.add(place)
    db.flush()
    candidate = Candidate(trip_id=trip_id, place_id=place.id, status=payload.status)
    db.add(candidate)
    record_creation(db, record, place.id)
    await finish(db, trip_id, "place.created", user.id, "place", place.id)
    return place_dict(place, candidate)


@router.patch("/places/{place_id}")
async def edit_place(place_id: str, payload: PlaceEdit, request: Request, db: DB, user: Actor):
    place = access(db, Place, place_id, user.id, lock=True)
    authorize_write(db, request, place, "place", user.id, payload)
    candidate = db.scalar(select(Candidate).where(Candidate.place_id == place_id))
    delta = {}
    original = fields(place, set(PlaceInput.model_fields) - {"status"}) | {
        "status": candidate.status
    }
    for key, value in merge_patch(PlaceInput, original, payload).items():
        target = candidate if key == "status" else place
        if getattr(target, key) != value:
            delta[key] = {"before": str(getattr(target, key)), "after": str(value)}
            setattr(target, key, value)
    place.version += 1
    place.updated_at = utcnow()
    await finish(db, place.trip_id, "place.updated", user.id, "place", place.id, delta)
    return place_dict(place, candidate)


async def update_candidate(trip_id, place_id, payload, request, db, user, restore):
    require_member(db, trip_id, user.id, lock=True)
    place = db.get(Place, place_id)
    if not place or place.trip_id != trip_id:
        fail(404, "not_found", "找不到景點。")
    authorize_write(db, request, place, "place", user.id, payload)
    candidate = db.scalar(select(Candidate).where(Candidate.place_id == place.id))
    candidate.removed_at = None if restore else utcnow()
    place.updated_at = utcnow()
    place.version += 1
    event = "candidate.restored" if restore else "candidate.removed"
    await finish(db, trip_id, event, user.id, "place", place.id)
    return place_dict(place, candidate)


@router.post("/trips/{trip_id}/candidates")
async def restore_candidate(
    trip_id: str, payload: CandidateRestore, request: Request, db: DB, user: Actor
):
    return await update_candidate(trip_id, payload.place_id, payload, request, db, user, True)


@router.delete("/trips/{trip_id}/candidates/{candidate_id}")
async def remove_candidate(
    trip_id: str, candidate_id: str, payload: Mutation, request: Request, db: DB, user: Actor
):
    require_member(db, trip_id, user.id, lock=True)
    candidate = db.get(Candidate, candidate_id)
    if not candidate or candidate.trip_id != trip_id:
        fail(404, "not_found", "找不到這筆候選景點。")
    return await update_candidate(trip_id, candidate.place_id, payload, request, db, user, False)


def item_dict(item, editing_by=None):
    return {
        **fields(
            item,
            set(ItemInput.model_fields)
            | {
                "id",
                "day_id",
                "created_by",
                "editable_by",
                "position",
                "version",
            },
        ),
        "editing_by": editing_by,
    }


def minutes(clock):
    hour, minute = map(int, clock.split(":"))
    return hour * 60 + minute


def mark_overlaps(items):
    intervals = []
    for item in items:
        item["overlap"] = False
        if item["start_time"]:
            start = minutes(item["start_time"])
            end = minutes(item["end_time"]) if item["end_time"] else start + (item["duration"] or 1)
            for other_start, other_end, other in intervals:
                if start < other_end and other_start < end:
                    other["overlap"] = item["overlap"] = True
            intervals.append((start, end, item))


def day_dict(day, trip, items):
    date = trip.start_date + timedelta(days=day.day_number - 1) if trip.start_date else None
    return {**fields(day, ("id", "day_number", "title", "timezone")), "date": date, "items": items}


@router.get("/trips/{trip_id}/days")
def list_days(trip_id: str, db: DB, user: Actor):
    trip = require_member(db, trip_id, user.id)
    days = db.scalars(
        select(TripDay).where(TripDay.trip_id == trip_id).order_by(TripDay.day_number)
    )
    editing = editors(db, trip_id)
    grouped = {}
    for item in db.scalars(
        select(ItineraryItem)
        .where(ItineraryItem.trip_id == trip_id)
        .order_by(ItineraryItem.position, ItineraryItem.id)
    ):
        grouped.setdefault(item.day_id, []).append(item_dict(item, editing.get(item.id)))
    for items in grouped.values():
        mark_overlaps(items)
    return [day_dict(day, trip, grouped.get(day.id, [])) for day in days]


@router.post("/trips/{trip_id}/days", status_code=201)
async def add_day(trip_id: str, payload: DayInput, db: DB, user: Actor, key: Key = None):
    trip = require_member(db, trip_id, user.id, lock=True)
    previous, record = creation_request(db, TripDay, user.id, trip_id, key, payload)
    if previous:
        items = [item_dict(row) for row in day_items(db, previous.id, "")]
        mark_overlaps(items)
        return day_dict(previous, trip, items)
    highest = db.scalar(select(func.max(TripDay.day_number)).where(TripDay.trip_id == trip_id)) or 0
    day = TripDay(trip_id=trip_id, day_number=highest + 1, **payload.model_dump())
    db.add(day)
    db.flush()
    record_creation(db, record, day.id)
    await finish(db, trip_id, "day.created", user.id, "day", day.id)
    return day_dict(day, trip, [])


def validate_place(db, trip_id, place_id):
    if place_id:
        place = db.get(Place, place_id)
        if not place or place.trip_id != trip_id:
            fail(404, "not_found", "找不到旅程中的景點。")


def append_item(db, trip_id, user_id, day_id, title, item_type="custom", place_id=None):
    """Append to a day within the caller's locked trip transaction."""
    day = db.get(TripDay, day_id)
    if not day or day.trip_id != trip_id:
        fail(404, "not_found", "找不到旅程中的日期。")
    validate_place(db, trip_id, place_id)
    last = db.scalar(select(func.max(ItineraryItem.position)).where(ItineraryItem.day_id == day_id))
    item = ItineraryItem(
        trip_id=trip_id,
        day_id=day_id,
        title=title,
        item_type=item_type,
        place_id=place_id,
        created_by=user_id,
        editable_by=user_id,
        position=0 if last is None else last + 1,
    )
    db.add(item)
    db.flush()
    return item


@router.post("/days/{day_id}/items", status_code=201)
async def add_item(day_id: str, payload: ItemInput, db: DB, user: Actor, key: Key = None):
    day = access(db, TripDay, day_id, user.id, lock=True)
    previous, record = creation_request(db, ItineraryItem, user.id, day_id, key, payload)
    if previous:
        return item_dict(previous)
    item = append_item(
        db, day.trip_id, user.id, day_id, payload.title, payload.item_type, payload.place_id
    )
    record_creation(db, record, item.id)
    for field in ("start_time", "end_time", "duration", "notes"):
        setattr(item, field, getattr(payload, field))
    await finish(db, day.trip_id, "item.created", user.id, "item", item.id)
    return item_dict(item)


@router.patch("/itinerary-items/{item_id}")
async def edit_item(item_id: str, payload: ItemEdit, request: Request, db: DB, user: Actor):
    item = access(db, ItineraryItem, item_id, user.id, lock=True)
    authorize_write(db, request, item, "item", user.id, payload)
    merged = merge_patch(ItemInput, fields(item, ItemInput.model_fields), payload)
    validate_place(db, item.trip_id, merged["place_id"])
    for key, value in merged.items():
        setattr(item, key, value)
    item.version += 1
    await finish(db, item.trip_id, "item.updated", user.id, "item", item.id)
    return item_dict(item)


def day_items(db, day_id, exclude_id):
    return list(
        db.scalars(
            select(ItineraryItem)
            .where(ItineraryItem.day_id == day_id, ItineraryItem.id != exclude_id)
            .order_by(ItineraryItem.position, ItineraryItem.id)
        )
    )


def renumber(items):
    for position, item in enumerate(items):
        item.position = position


@router.post("/itinerary-items/{item_id}/move")
async def move_item(item_id: str, payload: ItemMove, request: Request, db: DB, user: Actor):
    item = access(db, ItineraryItem, item_id, user.id, lock=True)
    authorize_write(db, request, item, "item", user.id, payload)
    destination = db.get(TripDay, payload.day_id)
    if not destination or destination.trip_id != item.trip_id:
        fail(404, "not_found", "目的日期不在這趟旅程中。")
    if item.day_id != destination.id:
        renumber(day_items(db, item.day_id, item.id))
    ordered = day_items(db, destination.id, item.id)
    ordered.insert(min(payload.position, len(ordered)), item)
    item.day_id = destination.id
    renumber(ordered)
    item.version += 1
    await finish(db, item.trip_id, "item.moved", user.id, "item", item.id)
    return item_dict(item)


@router.delete("/itinerary-items/{item_id}")
async def delete_item(item_id: str, payload: Mutation, request: Request, db: DB, user: Actor):
    item = access(db, ItineraryItem, item_id, user.id, lock=True)
    authorize_write(db, request, item, "item", user.id, payload)
    renumber(day_items(db, item.day_id, item.id))
    db.delete(item)
    await finish(db, item.trip_id, "item.deleted", user.id, "item", item_id)
    return {"deleted": True}
