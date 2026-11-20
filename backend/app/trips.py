import base64
import io
import secrets
from datetime import date, timedelta
from typing import Annotated, Literal

import qrcode
import qrcode.image.svg
from fastapi import APIRouter, Header, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator
from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import Session

from .auth import issue_session
from .core import (
    COOKIE,
    DB,
    Actor,
    audit,
    check_version,
    digest,
    fail,
    public_origin,
    require_member,
    require_owner,
    valid_session,
)
from .models import CreationKey, Invitation, Membership, Trip, User, utcnow
from .planning_models import Candidate, TripDay
from .realtime import hub

router = APIRouter(tags=["旅程及邀請"])
NonemptyTitle = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=160)
]
Location = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
Status = Literal["planning", "confirmed", "traveling", "completed"]
Currency = Annotated[
    str,
    StringConstraints(strip_whitespace=True, to_upper=True, pattern=r"^[A-Za-z]{3}$"),
]


class Payload(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TripFields(Payload):
    title: NonemptyTitle | None = None
    description: str | None = Field(default=None, max_length=5000)
    destinations: list[Location] | None = Field(default=None, max_length=80)
    start_date: date | None = None
    end_date: date | None = None
    currency: Currency | None = None
    status: Status | None = None
    cover: str | None = Field(default=None, max_length=2048)
    day_count: int | None = Field(default=None, ge=1, le=3660)

    @model_validator(mode="after")
    def non_nullable(self):
        for key in self.model_fields_set - {"start_date", "end_date"}:
            if getattr(self, key) is None:
                raise ValueError("此欄位不可為空值")
        return self


class NewTrip(TripFields):
    title: NonemptyTitle


class EditTrip(TripFields):
    version: int = Field(ge=1)


class Version(Payload):
    version: int = Field(ge=1)


class Archive(Version):
    archived: bool = True


class Transfer(Version):
    user_id: str = Field(min_length=1, max_length=36)


class NewInvite(Payload):
    days: int = Field(default=7, ge=1, le=365)


class Accept(Payload):
    code: str = Field(min_length=1, max_length=100)


class Guest(Accept):
    nickname: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]


def summary(db: Session, trip: Trip):
    members = db.scalar(
        select(func.count())
        .select_from(Membership)
        .where(Membership.trip_id == trip.id, Membership.left_at.is_(None))
    )
    places = db.scalar(
        select(func.count())
        .select_from(Candidate)
        .where(Candidate.trip_id == trip.id, Candidate.removed_at.is_(None))
    )
    days = db.scalar(select(func.count()).select_from(TripDay).where(TripDay.trip_id == trip.id))
    fields = (
        "id",
        "owner_id",
        "title",
        "description",
        "destinations",
        "start_date",
        "end_date",
        "currency",
        "status",
        "cover",
        "created_at",
        "deleted_at",
        "archived",
        "version",
    )
    return {
        **{key: getattr(trip, key) for key in fields},
        "member_count": members,
        "place_count": places,
        "day_count": days,
    }


def extend_days(db: Session, trip: Trip, requested: int | None):
    count = db.scalar(select(func.max(TripDay.day_number)).where(TripDay.trip_id == trip.id)) or 0
    if trip.start_date and trip.end_date:
        span = (trip.end_date - trip.start_date).days + 1
        if not 1 <= span <= 3660:
            fail(
                422,
                "INVALID_DATE_RANGE",
                "結束日期必須在開始日期之後或同日，且範圍須在十年內。",
            )
        requested = max(span, requested or 0)
    for number in range(count + 1, max(1, requested or 0) + 1):
        db.add(TripDay(trip_id=trip.id, day_number=number))


@router.get("/trips")
def list_trips(db: DB, user: Actor):
    cutoff = utcnow() - timedelta(days=30)
    rows = db.scalars(
        select(Trip)
        .join(Membership)
        .where(
            Membership.user_id == user.id,
            Membership.left_at.is_(None),
            or_(
                Trip.deleted_at.is_(None),
                (Trip.owner_id == user.id) & (Trip.deleted_at > cutoff),
            ),
        )
        .order_by(Trip.created_at.desc())
    ).all()
    return [summary(db, trip) for trip in rows]


@router.post("/trips", status_code=201)
def create_trip(
    payload: NewTrip,
    db: DB,
    user: Actor,
    idempotency_key: Annotated[str | None, Header(max_length=128)] = None,
):
    if user.account_type not in {"google", "local_test"}:
        fail(403, "GOOGLE_REQUIRED", "請先使用 Google 登入，再建立自己的旅程。")
    fingerprint = digest(payload.model_dump_json())
    if idempotency_key:
        db.scalar(select(User.id).where(User.id == user.id).with_for_update())
        key = db.scalar(
            select(CreationKey).where(
                CreationKey.user_id == user.id,
                CreationKey.operation == "trip",
                CreationKey.key == idempotency_key,
            )
        )
        if key:
            if key.request_hash != fingerprint:
                fail(409, "IDEMPOTENCY_CONFLICT", "這個請求識別碼已用於不同的資料。")
            return summary(db, require_member(db, key.resource_id, user.id))
    if payload.start_date and payload.end_date and payload.start_date > payload.end_date:
        fail(422, "INVALID_DATE_RANGE", "結束日期必須在開始日期之後或同日。")
    trip = Trip(
        owner_id=user.id,
        **payload.model_dump(exclude_unset=True, exclude={"day_count"}),
    )
    db.add(trip)
    db.flush()
    db.add(Membership(trip_id=trip.id, user_id=user.id, role="owner"))
    extend_days(db, trip, payload.day_count)
    if idempotency_key:
        db.add(
            CreationKey(
                user_id=user.id,
                operation="trip",
                key=idempotency_key,
                request_hash=fingerprint,
                resource_id=trip.id,
            )
        )
    audit(db, trip.id, user.id, "trip", trip.id, "create")
    db.commit()
    return summary(db, trip)


@router.get("/trips/{trip_id}")
def get_trip(trip_id: str, db: DB, user: Actor):
    return summary(db, require_member(db, trip_id, user.id))


async def save_trip(db: Session, trip: Trip, user: User, action: str):
    trip.version += 1
    audit(db, trip.id, user.id, "trip", trip.id, action)
    db.commit()
    await hub.publish(trip.id, {"type": "trip", "action": action})
    return summary(db, trip)


@router.patch("/trips/{trip_id}")
async def edit_trip(trip_id: str, payload: EditTrip, db: DB, user: Actor):
    trip = require_owner(db, trip_id, user.id, lock=True)
    check_version(trip, payload.version)
    for key, value in payload.model_dump(
        exclude_unset=True, exclude={"version", "day_count"}
    ).items():
        setattr(trip, key, value)
    if trip.start_date and trip.end_date and trip.start_date > trip.end_date:
        fail(422, "INVALID_DATE_RANGE", "結束日期必須在開始日期之後或同日。")
    extend_days(db, trip, payload.day_count)
    return await save_trip(db, trip, user, "update")


@router.post("/trips/{trip_id}/archive")
async def archive_trip(trip_id: str, payload: Archive, db: DB, user: Actor):
    trip = require_owner(db, trip_id, user.id, lock=True)
    check_version(trip, payload.version)
    trip.archived = payload.archived
    return await save_trip(db, trip, user, "archive" if payload.archived else "unarchive")


@router.delete("/trips/{trip_id}")
async def remove_trip(trip_id: str, version: Annotated[int, Query(ge=1)], db: DB, user: Actor):
    trip = require_owner(db, trip_id, user.id, lock=True)
    check_version(trip, version)
    trip.deleted_at = utcnow()
    return await save_trip(db, trip, user, "remove")


@router.post("/trips/{trip_id}/restore")
async def restore_trip(trip_id: str, payload: Version, db: DB, user: Actor):
    trip = require_owner(db, trip_id, user.id, lock=True, allow_deleted=True)
    check_version(trip, payload.version)
    trip.deleted_at = None
    return await save_trip(db, trip, user, "restore")


@router.get("/trips/{trip_id}/members")
def list_members(trip_id: str, db: DB, user: Actor):
    require_member(db, trip_id, user.id)
    rows = db.execute(
        select(User, Membership)
        .join(Membership, Membership.user_id == User.id)
        .where(Membership.trip_id == trip_id, Membership.left_at.is_(None))
        .order_by(Membership.joined_at)
    )
    return [
        {
            "id": member.id,
            "nickname": member.nickname,
            "role": participation.role,
            "account_type": member.account_type,
        }
        for member, participation in rows
    ]


@router.post("/trips/{trip_id}/transfer")
async def transfer(trip_id: str, payload: Transfer, db: DB, user: Actor):
    trip = require_owner(db, trip_id, user.id, lock=True)
    check_version(trip, payload.version)
    target = db.scalar(
        select(Membership).where(
            Membership.trip_id == trip_id,
            Membership.user_id == payload.user_id,
            Membership.left_at.is_(None),
        )
    )
    if not target or target.user_id == user.id:
        fail(422, "INVALID_NEW_OWNER", "請選擇另一位目前在旅程中的成員。")
    db.execute(
        update(Membership)
        .where(Membership.trip_id == trip_id, Membership.user_id == user.id)
        .values(role="member")
    )
    target.role = "owner"
    trip.owner_id = target.user_id
    return await save_trip(db, trip, user, "owner_transfer")


@router.delete("/trips/{trip_id}/members/{member_id}", status_code=204)
async def remove_member(trip_id: str, member_id: str, db: DB, user: Actor):
    trip = require_member(db, trip_id, user.id, lock=True)
    if member_id != user.id and trip.owner_id != user.id:
        fail(403, "OWNER_REQUIRED", "只有旅程擁有者可以移除其他成員。")
    if member_id == trip.owner_id:
        fail(409, "TRANSFER_REQUIRED", "旅程擁有者須先轉移所有權才能退出。")
    member = db.scalar(
        select(Membership).where(
            Membership.trip_id == trip_id,
            Membership.user_id == member_id,
            Membership.left_at.is_(None),
        )
    )
    if not member:
        fail(404, "MEMBER_ABSENT", "找不到這位旅程成員。")
    from .decisions import transfer_poll_edits
    from .planning import transfer_edits

    member.left_at = utcnow()
    transfer_edits(db, trip_id, member_id, trip.owner_id)
    transfer_poll_edits(db, trip_id, member_id, trip.owner_id)
    audit(db, trip_id, user.id, "membership", member.id, "remove", {"user_id": member_id})
    db.commit()
    await hub.publish(trip_id, {"type": "members"})


def invite_metadata(invite: Invitation):
    return {
        "id": invite.id,
        "expires_at": invite.expires_at,
        "revoked_at": invite.revoked_at,
    }


@router.get("/trips/{trip_id}/invitations")
def invitations(trip_id: str, db: DB, user: Actor):
    require_owner(db, trip_id, user.id)
    return [
        invite_metadata(invite)
        for invite in db.scalars(
            select(Invitation)
            .where(Invitation.trip_id == trip_id)
            .order_by(Invitation.expires_at.desc())
        )
    ]


@router.post("/trips/{trip_id}/invitations", status_code=201)
def invite(trip_id: str, db: DB, user: Actor, payload: NewInvite | None = None):
    require_owner(db, trip_id, user.id, lock=True)
    code = "".join(secrets.choice("23456789ABCDEFGHJKLMNPQRSTUVWXYZ") for _ in range(12))
    invitation = Invitation(
        trip_id=trip_id,
        token_hash=digest(code),
        expires_at=utcnow() + timedelta(days=payload.days if payload else 7),
    )
    db.add(invitation)
    db.flush()
    audit(db, trip_id, user.id, "invitation", invitation.id, "create")
    url = public_origin() + "/?invite=" + code
    buf = io.BytesIO()
    qrcode.make(url, image_factory=qrcode.image.svg.SvgPathImage).save(buf)
    db.commit()
    return {
        **invite_metadata(invitation),
        "code": code,
        "url": url,
        "qr_data_url": "data:image/svg+xml;base64,"
        + base64.b64encode(buf.getvalue()).decode("ascii"),
    }


@router.delete("/trips/{trip_id}/invitations/{invite_id}", status_code=204)
def revoke(trip_id: str, invite_id: str, db: DB, user: Actor):
    require_owner(db, trip_id, user.id, lock=True)
    invitation = db.scalar(
        select(Invitation).where(Invitation.id == invite_id, Invitation.trip_id == trip_id)
    )
    if not invitation:
        fail(404, "INVITE_NOT_FOUND", "找不到這筆邀請。")
    invitation.revoked_at = utcnow()
    audit(db, trip_id, user.id, "invitation", invitation.id, "revoke")
    db.commit()


def invited_trip(db: Session, code: str):
    hashed = digest(code.strip().upper())
    trip = db.scalar(
        select(Trip)
        .join(Invitation)
        .where(Invitation.token_hash == hashed)
        .with_for_update(of=Trip)
    )
    # Re-check after acquiring the trip lock, shared with revoke and archive.
    active = db.scalar(
        select(Invitation.id).where(
            Invitation.token_hash == hashed,
            Invitation.expires_at > utcnow(),
            Invitation.revoked_at.is_(None),
        )
    )
    if not trip or trip.deleted_at or not active:
        fail(
            403,
            "INVITE_INVALID",
            "邀請碼無效、已過期或已撤銷，請向旅程擁有者索取新邀請。",
        )
    return trip


def join(db: Session, trip: Trip, user: User):
    member = db.scalar(
        select(Membership).where(Membership.trip_id == trip.id, Membership.user_id == user.id)
    )
    if member is None:
        member = Membership(trip_id=trip.id, user_id=user.id, role="member")
        db.add(member)
    elif member.left_at:
        member.left_at = None
        member.joined_at = utcnow()
        member.role = "member"
    else:
        return
    db.flush()
    audit(db, trip.id, user.id, "membership", member.id, "join")


@router.post("/auth/guest")
async def guest(payload: Guest, request: Request, response: Response, db: DB):
    trip = invited_trip(db, payload.code)
    login = valid_session(db, request.cookies.get(COOKIE))
    if login:
        user = db.get(User, login.user_id)
    else:
        user = User(account_type="guest", nickname=payload.nickname)
        db.add(user)
        db.flush()
        issue_session(db, response, user)
    join(db, trip, user)
    db.commit()
    await hub.publish(trip.id, {"type": "members"})
    return summary(db, trip)


@router.post("/invitations/accept")
async def accept(payload: Accept, db: DB, user: Actor):
    trip = invited_trip(db, payload.code)
    join(db, trip, user)
    db.commit()
    await hub.publish(trip.id, {"type": "members"})
    return summary(db, trip)
