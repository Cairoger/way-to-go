from collections import Counter, defaultdict
from datetime import date, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel, Field, StringConstraints
from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from .core import audit, current_user, digest, fail, get_db, require_member
from .decisions_models import (
    Ballot,
    BallotChoice,
    Comment,
    Poll,
    PollAdoption,
    PollOption,
    PollRound,
)
from .models import CreationKey, User, as_utc, uid, utcnow
from .realtime import hub

router = APIRouter(tags=["投票與討論"])
Db = Annotated[Session, Depends(get_db)]
Actor = Annotated[User, Depends(current_user)]
Label = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=180)]
CommentText = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=5000)
]


class Version(BaseModel):
    version: int = Field(ge=1)


class OptionInput(BaseModel):
    text: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=150)]
    place_id: str | None = None


class NewPoll(BaseModel):
    title: Label
    kind: Literal["place", "date"]
    mode: Literal["single", "multiple"]
    options: list[OptionInput] = Field(min_length=2, max_length=60)
    deadline: datetime | None = None


class PollEdit(Version):
    title: Label
    mode: Literal["single", "multiple"]
    deadline: datetime | None = None


class NewOption(Version, OptionInput):
    pass


class Vote(Version):
    ballot_version: int = Field(ge=0)
    option_ids: list[str] = Field(min_length=1, max_length=60)


class Adopt(Version):
    option_id: str
    day_id: str


class NewComment(BaseModel):
    content: CommentText
    parent_id: str | None = None


class CommentEdit(Version):
    content: CommentText


def validate_deadline(deadline: datetime | None):
    if deadline and (deadline.tzinfo is None or deadline <= utcnow()):
        fail(422, "invalid_deadline", "截止時間需含時區，並晚於現在。")
    return as_utc(deadline) if deadline else None


def is_closed(round_: PollRound):
    return bool(round_.closed_at or (round_.deadline and as_utc(round_.deadline) <= utcnow()))


def check_version(current: int, expected: int):
    if current != expected:
        fail(409, "version_conflict", "資料已變更，請重新整理後再試一次。")


def poll_for_write(db: Session, poll_id: str, actor: User, body: Version, *, author=False):
    trip_id = db.scalar(select(Poll.trip_id).where(Poll.id == poll_id))
    if trip_id is None:
        fail(404, "poll_not_found", "找不到這個投票。")
    require_member(db, trip_id, actor.id, lock=True)
    poll = db.get(Poll, poll_id)
    if not poll:
        fail(404, "poll_not_found", "找不到這個投票。")
    if author and poll.editable_by != actor.id:
        fail(403, "poll_author_required", "你沒有管理這個投票的權限。")
    check_version(poll.version, body.version)
    round_ = db.scalar(
        select(PollRound)
        .where(PollRound.poll_id == poll_id)
        .order_by(PollRound.number.desc())
        .limit(1)
    )
    return poll, round_


def require_open(round_: PollRound):
    if is_closed(round_):
        fail(409, "poll_closed", "這一輪投票已結束。")


def get_options(db: Session, round_: PollRound):
    return list(
        db.scalars(
            select(PollOption).where(PollOption.round_id == round_.id).order_by(PollOption.ordinal)
        )
    )


def validate_option(db: Session, trip_id: str, kind: str, option: OptionInput):
    if option.place_id:
        from .planning_models import Place

        if kind != "place" or not db.scalar(
            select(Place.id).where(Place.id == option.place_id, Place.trip_id == trip_id)
        ):
            fail(422, "invalid_place", "請選擇這個旅程中的景點。")
    if kind == "date":
        try:
            parts = [date.fromisoformat(s.strip()) for s in option.text.split("~")]
        except ValueError:
            fail(422, "invalid_date_option", "日期請使用 YYYY-MM-DD，區間以 ~ 連接。")
        if len(parts) > 2 or parts[0] > parts[-1]:
            fail(422, "invalid_date_option", "請確認日期區間的起訖順序。")
        return " ~ ".join(p.isoformat() for p in parts)
    return option.text


def round_view(db: Session, round_: PollRound, viewer: str):
    options = get_options(db, round_)
    closed = is_closed(round_)
    ballots_query = (
        select(Ballot, User.nickname)
        .join(User, User.id == Ballot.user_id)
        .where(Ballot.round_id == round_.id)
    )
    if not closed:
        ballots_query = ballots_query.where(Ballot.user_id == viewer)
    ballots = list(db.execute(ballots_query.order_by(Ballot.submitted_at, Ballot.id)))
    choices = defaultdict(list)
    if ballots:
        ids = [ballot.id for ballot, _ in ballots]
        for ballot_id, option_id in db.execute(
            select(BallotChoice.ballot_id, BallotChoice.option_id).where(
                BallotChoice.ballot_id.in_(ids)
            )
        ):
            choices[ballot_id].append(option_id)
    mine = next((b for b, _ in ballots if b.user_id == viewer), None)
    result = {
        "id": round_.id,
        "number": round_.number,
        "title": round_.title,
        "kind": round_.kind,
        "mode": round_.mode,
        "deadline": as_utc(round_.deadline) if round_.deadline else None,
        "closed": closed,
        "options": [{"id": o.id, "text": o.option_text, "place_id": o.place_id} for o in options],
        "my_choices": choices[mine.id] if mine else [],
        "ballot_version": mine.version if mine else 0,
        "review_needed": bool(
            mine and not closed and mine.options_version != round_.options_version
        ),
    }
    if closed:
        counts = Counter(option for selections in choices.values() for option in selections)
        high = max(counts.values(), default=0)
        result["results"] = {
            "counts": {o.id: counts[o.id] for o in options},
            "winners": [o.id for o in options if high and counts[o.id] == high],
            "ballots": [
                {"user_id": b.user_id, "nickname": nickname, "option_ids": choices[b.id]}
                for b, nickname in ballots
            ],
        }
    return result


def poll_view(db: Session, poll: Poll, viewer: str):
    rounds = db.scalars(
        select(PollRound).where(PollRound.poll_id == poll.id).order_by(PollRound.number.desc())
    )
    return {
        "id": poll.id,
        "created_by": poll.created_by,
        "editable_by": poll.editable_by,
        "version": poll.version,
        "rounds": [round_view(db, r, viewer) for r in rounds],
    }


async def changed(db, poll, actor, action):
    trip_id, poll_id = poll.trip_id, poll.id
    audit(db, trip_id, actor.id, "poll", poll_id, action)
    db.commit()
    await hub.publish(trip_id, {"type": action, "id": poll_id})


@router.get("/trips/{trip_id}/polls")
def list_polls(trip_id: str, db: Db, actor: Actor):
    require_member(db, trip_id, actor.id)
    polls = db.scalars(select(Poll).where(Poll.trip_id == trip_id).order_by(Poll.created_at.desc()))
    return [poll_view(db, p, actor.id) for p in polls]


def creation_id(db: Session, model, actor: User, trip_id: str, body: BaseModel, key: str | None):
    """Reserve an ID in the same transaction as the object and its audit entry."""
    new_id = uid()
    if not key:
        return new_id, None
    kind = model.__tablename__
    fingerprint = digest(trip_id + body.model_dump_json())
    record = db.scalar(
        select(CreationKey).where(
            CreationKey.user_id == actor.id, CreationKey.operation == kind, CreationKey.key == key
        )
    )
    if record:
        if record.request_hash != fingerprint:
            fail(409, "idempotency_conflict", "這個請求識別碼已用於其他資料。")
        existing = db.get(model, record.resource_id)
        if not existing:
            fail(410, "resource_deleted", "先前建立的資料已刪除。")
        return record.resource_id, existing
    db.add(
        CreationKey(
            user_id=actor.id, operation=kind, key=key, request_hash=fingerprint, resource_id=new_id
        )
    )
    return new_id, None


@router.post("/trips/{trip_id}/polls", status_code=201)
async def create_poll(
    trip_id: str,
    body: NewPoll,
    db: Db,
    actor: Actor,
    idempotency_key: Annotated[str | None, Header(max_length=128)] = None,
):
    require_member(db, trip_id, actor.id, lock=True)
    poll_id, existing = creation_id(db, Poll, actor, trip_id, body, idempotency_key)
    if existing:
        return poll_view(db, existing, actor.id)
    deadline = validate_deadline(body.deadline)
    poll = Poll(id=poll_id, trip_id=trip_id, created_by=actor.id, editable_by=actor.id)
    db.add(poll)
    db.flush()
    round_ = PollRound(
        poll_id=poll.id,
        number=1,
        title=body.title,
        kind=body.kind,
        mode=body.mode,
        deadline=deadline,
    )
    db.add(round_)
    db.flush()
    labels = set()
    for i, opt in enumerate(body.options):
        label = validate_option(db, trip_id, body.kind, opt)
        if label.casefold() in labels:
            fail(422, "duplicate_option", "選項不可重複。")
        labels.add(label.casefold())
        db.add(
            PollOption(
                round_id=round_.id,
                created_by=actor.id,
                option_text=label,
                place_id=opt.place_id,
                ordinal=i,
            )
        )
    await changed(db, poll, actor, "poll.created")
    return poll_view(db, poll, actor.id)


@router.patch("/polls/{poll_id}")
async def edit_poll(poll_id: str, body: PollEdit, db: Db, actor: Actor):
    poll, round_ = poll_for_write(db, poll_id, actor, body, author=True)
    require_open(round_)
    if db.scalar(select(Ballot.id).where(Ballot.round_id == round_.id).limit(1)):
        fail(409, "new_round_required", "已有成員投票，請結束本輪並開啟新一輪再修改規則。")
    round_.title, round_.mode, round_.deadline = (
        body.title,
        body.mode,
        validate_deadline(body.deadline),
    )
    poll.version += 1
    await changed(db, poll, actor, "poll.updated")
    return poll_view(db, poll, actor.id)


@router.post("/polls/{poll_id}/options")
async def add_option(poll_id: str, body: NewOption, db: Db, actor: Actor):
    poll, round_ = poll_for_write(db, poll_id, actor, body)
    require_open(round_)
    options = get_options(db, round_)
    label = validate_option(db, poll.trip_id, round_.kind, body)
    if len(options) >= 60 or any(o.option_text.casefold() == label.casefold() for o in options):
        fail(422, "invalid_option", "選項不可重複，每輪最多 60 個。")
    db.add(
        PollOption(
            round_id=round_.id,
            created_by=actor.id,
            option_text=label,
            place_id=body.place_id,
            ordinal=options[-1].ordinal + 1,
        )
    )
    round_.options_version += 1
    poll.version += 1
    await changed(db, poll, actor, "poll.options_added")
    return poll_view(db, poll, actor.id)


@router.put("/polls/{poll_id}/ballot")
def cast_vote(poll_id: str, body: Vote, db: Db, actor: Actor):
    poll, round_ = poll_for_write(db, poll_id, actor, body)
    require_open(round_)
    selected = set(body.option_ids)
    if (
        len(selected) != len(body.option_ids)
        or (round_.mode == "single" and len(selected) != 1)
        or not selected.issubset({o.id for o in get_options(db, round_)})
    ):
        fail(422, "invalid_ballot", "請依照本輪投票方式選擇有效選項。")
    ballot = db.scalar(
        select(Ballot).where(Ballot.round_id == round_.id, Ballot.user_id == actor.id)
    )
    check_version(ballot.version if ballot else 0, body.ballot_version)
    if ballot:
        db.execute(delete(BallotChoice).where(BallotChoice.ballot_id == ballot.id))
        ballot.version += 1
        ballot.submitted_at = utcnow()
    else:
        ballot = Ballot(round_id=round_.id, user_id=actor.id)
        db.add(ballot)
    ballot.options_version = round_.options_version
    db.flush()
    db.add_all([BallotChoice(ballot_id=ballot.id, option_id=oid) for oid in selected])
    # Publishing submissions or incrementing the shared version would leak participation.
    db.commit()
    return poll_view(db, poll, actor.id)


@router.post("/polls/{poll_id}/close")
async def close_poll(poll_id: str, body: Version, db: Db, actor: Actor):
    poll, round_ = poll_for_write(db, poll_id, actor, body, author=True)
    require_open(round_)
    round_.closed_at = utcnow()
    poll.version += 1
    await changed(db, poll, actor, "poll.closed")
    return poll_view(db, poll, actor.id)


@router.post("/polls/{poll_id}/reopen")
async def reopen_poll(poll_id: str, body: Version, db: Db, actor: Actor):
    poll, previous = poll_for_write(db, poll_id, actor, body, author=True)
    if not is_closed(previous):
        fail(409, "poll_open", "請先結束本輪投票。")
    result = round_view(db, previous, actor.id)["results"]
    winners = result["winners"]
    next_round = PollRound(
        poll_id=poll.id,
        number=previous.number + 1,
        title=previous.title,
        kind=previous.kind,
        mode=previous.mode,
    )
    db.add(next_round)
    db.flush()
    for o in get_options(db, previous):
        if len(winners) <= 1 or o.id in winners:
            db.add(
                PollOption(
                    round_id=next_round.id,
                    option_text=o.option_text,
                    place_id=o.place_id,
                    created_by=o.created_by,
                    ordinal=o.ordinal,
                )
            )
    poll.version += 1
    await changed(db, poll, actor, "poll.reopened")
    return poll_view(db, poll, actor.id)


@router.post("/polls/{poll_id}/adopt")
async def adopt_poll(poll_id: str, body: Adopt, db: Db, actor: Actor):
    from .planning import append_item

    poll, round_ = poll_for_write(db, poll_id, actor, body)
    if not is_closed(round_):
        fail(409, "poll_open", "請先等待投票結束。")
    if round_view(db, round_, actor.id)["results"]["winners"] != [body.option_id]:
        fail(409, "winner_required", "僅有明確勝出選項時才能採用，平票可開啟新一輪。")
    option = db.get(PollOption, body.option_id)
    adoption = db.scalar(
        select(PollAdoption).where(
            PollAdoption.option_id == option.id, PollAdoption.day_id == body.day_id
        )
    )
    if adoption and adoption.item_id:
        return {"item_id": adoption.item_id}
    item = append_item(
        db,
        poll.trip_id,
        actor.id,
        body.day_id,
        option.option_text,
        item_type="place" if round_.kind == "place" else "custom",
        place_id=option.place_id,
    )
    db.flush()
    if adoption:
        adoption.item_id = item.id
    else:
        db.add(PollAdoption(option_id=option.id, day_id=body.day_id, item_id=item.id))
    await changed(db, poll, actor, "poll.adopted")
    return {"item_id": item.id}


@router.delete("/polls/{poll_id}")
async def delete_poll(poll_id: str, body: Version, db: Db, actor: Actor):
    poll, _ = poll_for_write(db, poll_id, actor, body, author=True)
    trip_id = poll.trip_id
    audit(db, trip_id, actor.id, "poll", poll_id, "poll.deleted")
    db.delete(poll)
    db.commit()
    await hub.publish(trip_id, {"type": "poll.deleted", "id": poll_id})
    return {"ok": True}


def transfer_poll_edits(db: Session, trip_id: str, departed_id: str, owner_id: str):
    db.execute(
        update(Poll)
        .where(Poll.trip_id == trip_id, Poll.editable_by == departed_id)
        .values(editable_by=owner_id, version=Poll.version + 1)
    )


def serialize_comment(comment, nickname):
    return {
        "id": comment.id,
        "author_id": comment.author_id,
        "nickname": nickname,
        "parent_id": comment.parent_id,
        "content": comment.content,
        "deleted": comment.deleted,
        "version": comment.version,
        "created_at": as_utc(comment.created_at),
        "updated_at": as_utc(comment.updated_at) if comment.updated_at else None,
    }


@router.get("/trips/{trip_id}/comments")
def list_comments(trip_id: str, db: Db, actor: Actor):
    require_member(db, trip_id, actor.id)
    rows = db.execute(
        select(Comment, User.nickname)
        .join(User, User.id == Comment.author_id)
        .where(Comment.trip_id == trip_id)
        .order_by(Comment.created_at, Comment.id)
    )
    return [serialize_comment(c, name) for c, name in rows]


async def save_comment(db, comment, actor, action):
    db.flush()
    trip_id, comment_id = comment.trip_id, comment.id
    audit(db, trip_id, actor.id, "comment", comment_id, action)
    db.commit()
    await hub.publish(trip_id, {"type": action, "id": comment_id})
    return serialize_comment(comment, db.get(User, comment.author_id).nickname)


@router.post("/trips/{trip_id}/comments", status_code=201)
async def post_comment(
    trip_id: str,
    body: NewComment,
    db: Db,
    actor: Actor,
    idempotency_key: Annotated[str | None, Header(max_length=128)] = None,
):
    require_member(db, trip_id, actor.id, lock=True)
    comment_id, existing = creation_id(db, Comment, actor, trip_id, body, idempotency_key)
    if existing:
        return serialize_comment(existing, actor.nickname)
    if body.parent_id:
        parent = db.get(Comment, body.parent_id)
        if not parent or parent.trip_id != trip_id or parent.deleted:
            fail(422, "invalid_parent", "回覆的留言已刪除或不存在。")
    comment = Comment(
        id=comment_id,
        trip_id=trip_id,
        author_id=actor.id,
        content=body.content,
        parent_id=body.parent_id,
    )
    db.add(comment)
    return await save_comment(db, comment, actor, "comment.created")


def comment_for_write(db, comment_id, actor, body, *, removing=False):
    trip_id = db.scalar(select(Comment.trip_id).where(Comment.id == comment_id))
    if not trip_id:
        fail(404, "comment_not_found", "找不到此留言。")
    trip = require_member(db, trip_id, actor.id, lock=True)
    comment = db.get(Comment, comment_id)
    if not comment or comment.deleted:
        fail(404, "comment_not_found", "此留言已刪除。")
    if comment.author_id != actor.id and not (removing and trip.owner_id == actor.id):
        fail(403, "comment_forbidden", "你沒有管理此留言的權限。")
    check_version(comment.version, body.version)
    return comment


@router.patch("/comments/{comment_id}")
async def edit_comment(comment_id: str, body: CommentEdit, db: Db, actor: Actor):
    comment = comment_for_write(db, comment_id, actor, body)
    comment.content, comment.updated_at = body.content, utcnow()
    comment.version += 1
    return await save_comment(db, comment, actor, "comment.updated")


@router.delete("/comments/{comment_id}")
async def delete_comment(comment_id: str, body: Version, db: Db, actor: Actor):
    comment = comment_for_write(db, comment_id, actor, body, removing=True)
    comment.deleted, comment.content, comment.updated_at = True, "", utcnow()
    comment.version += 1
    return await save_comment(db, comment, actor, "comment.deleted")
