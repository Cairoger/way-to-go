from typing import Annotated

from fastapi import APIRouter, Header
from pydantic import Field
from sqlalchemy import or_, select

from .core import DB, Actor, audit, check_version, fail, require_member
from .decisions import creation_id
from .models import Membership, Trip, uid, utcnow
from .planning import fields
from .planning_models import Candidate, ItineraryItem, Place, TripDay
from .preparation_models import Booking, Task
from .trips import NonemptyTitle, Payload, summary

router = APIRouter(tags=["旅程及邀請"])


class CopyTrip(Payload):
    title: NonemptyTitle | None = None
    version: int | None = Field(default=None, ge=1)


def copy_arrangements(db, source, target, user_id, places, items):
    for task in db.scalars(select(Task).where(Task.trip_id == source, Task.scope == "shared")):
        if task.place_id in places or task.item_id in items:
            db.add(
                Task(
                    trip_id=target,
                    created_by=user_id,
                    scope="shared",
                    item_id=items.get(task.item_id),
                    place_id=places.get(task.place_id),
                    **fields(task, ("title", "description", "due_date", "priority")),
                )
            )
    for booking in db.scalars(
        select(Booking).where(Booking.trip_id == source, Booking.item_id.in_(items))
    ):
        if booking.status == "cancelled":
            continue
        public_leg = (
            "airline",
            "number",
            "origin",
            "destination",
            "departure",
            "arrival",
            "departure_terminal",
            "arrival_terminal",
        )
        legs = [
            {**{k: leg[k] for k in public_leg if k in leg}, "passengers": []}
            for leg in booking.segments
        ]
        stay = booking.stay
        if stay:
            stay = {
                **{k: stay[k] for k in ("address", "room", "check_in", "check_out") if k in stay},
                "guests": [],
            }
        db.add(
            Booking(
                trip_id=target,
                created_by=user_id,
                item_id=items[booking.item_id],
                status="planned",
                segments=legs,
                stay=stay,
                reference="",
                website="",
                **fields(booking, ("kind", "title", "currency")),
            )
        )


@router.post("/trips/{trip_id}/copy", status_code=201)
def copy_trip(
    trip_id: str,
    db: DB,
    actor: Actor,
    body: CopyTrip | None = None,
    idempotency_key: Annotated[str | None, Header(max_length=128)] = None,
):
    source = require_member(db, trip_id, actor.id, lock=True)
    if actor.account_type not in {"google", "local_test"}:
        fail(403, "ACCOUNT_REQUIRED", "請先登入可建立旅程的帳號，再複製這趟旅程。")
    options = body or CopyTrip()
    destination_id, prior = creation_id(db, Trip, actor, trip_id, options, idempotency_key)
    if prior:
        return summary(db, require_member(db, prior.id, actor.id))
    if options.version is not None:
        check_version(source, options.version)
    destination = Trip(
        id=destination_id,
        owner_id=actor.id,
        title=options.title or source.title[:156] + "（複本）",
        **fields(
            source, ("description", "destinations", "currency", "start_date", "end_date", "cover")
        ),
    )
    db.add(destination)
    db.flush()
    db.add(Membership(trip_id=destination_id, user_id=actor.id, role="owner"))
    day_ids = {}
    for day in db.scalars(select(TripDay).where(TripDay.trip_id == trip_id)):
        day_ids[day.id] = uid()
        db.add(
            TripDay(
                id=day_ids[day.id],
                trip_id=destination_id,
                **fields(day, ("day_number", "title", "timezone")),
            )
        )
    # A removed candidate can still be referenced by several scheduled activities.
    active_items = select(ItineraryItem).where(
        ItineraryItem.trip_id == trip_id, ItineraryItem.deleted_at.is_(None)
    )
    used_places = active_items.with_only_columns(ItineraryItem.place_id)
    pairs = list(
        db.execute(
            select(Place, Candidate)
            .join(Candidate, Candidate.place_id == Place.id)
            .where(
                Place.trip_id == trip_id,
                Candidate.trip_id == trip_id,
                or_(Candidate.removed_at.is_(None), Place.id.in_(used_places)),
            )
        )
    )
    place_ids = {}
    authorship = {"trip_id": destination_id, "created_by": actor.id, "editable_by": actor.id}
    for place, _ in pairs:
        place_ids[place.id] = uid()
        db.add(
            Place(
                id=place_ids[place.id],
                deleted_at=utcnow() if place.deleted_at else None,
                **authorship,
                **fields(
                    place,
                    (
                        "name",
                        "address",
                        "latitude",
                        "longitude",
                        "country",
                        "city",
                        "category",
                        "tags",
                        "duration",
                        "cost",
                        "opening_hours",
                        "website",
                        "photo_url",
                        "notes",
                    ),
                ),
            )
        )
    db.flush()
    for place, candidate in pairs:
        db.add(
            Candidate(
                trip_id=destination_id,
                place_id=place_ids[place.id],
                status=candidate.status,
                removed_at=utcnow() if candidate.removed_at else None,
            )
        )
    item_ids = {}
    for item in db.scalars(active_items):
        if item.day_id not in day_ids or (item.place_id and item.place_id not in place_ids):
            fail(409, "INVALID_SOURCE_PLAN", "來源行程有無法對應的日期或景點。")
        item_ids[item.id] = uid()
        db.add(
            ItineraryItem(
                id=item_ids[item.id],
                day_id=day_ids[item.day_id],
                place_id=place_ids.get(item.place_id),
                **authorship,
                **fields(
                    item,
                    (
                        "title",
                        "item_type",
                        "position",
                        "start_time",
                        "end_time",
                        "duration",
                        "timezone",
                        "notes",
                    ),
                ),
            )
        )
    db.flush()
    copy_arrangements(db, source.id, destination_id, actor.id, place_ids, item_ids)
    audit(db, destination_id, actor.id, "trip", destination_id, "trip.copied")
    db.commit()
    return summary(db, destination)
