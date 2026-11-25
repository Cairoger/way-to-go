from collections import defaultdict
from datetime import date

from sqlalchemy import delete, select, update

from .availability_models import AvailabilityEntry
from .core import audit, fail
from .decisions import is_closed
from .decisions_models import Ballot, BallotChoice, Comment, Poll, PollRound
from .file_models import FileLink, FilePermission, TripFile
from .finance_models import Budget, FinanceLedger
from .merge_models import GuestMerge
from .models import CreationKey, LoginSession, Membership, Trip, User, as_utc, utcnow
from .notice_models import Notice, NoticePreference
from .planning_models import EditLease, ItineraryItem, Place
from .preparation_models import Booking, Task, TaskAssignee


def membership_union(db, trip, source, account):
    target = db.scalar(
        select(Membership).where(Membership.trip_id == trip.id, Membership.user_id == account)
    )
    active = not source.left_at or bool(target and not target.left_at)
    if not target:
        target = Membership(trip_id=trip.id, user_id=account, joined_at=source.joined_at)
        db.add(target)
    elif as_utc(source.joined_at) < as_utc(target.joined_at):
        target.joined_at = source.joined_at
    if trip.owner_id == source.user_id:
        trip.owner_id = account
    target.role = "owner" if trip.owner_id == account else "member"
    target.left_at = (
        None
        if active or target.role == "owner"
        else max((as_utc(t) for t in (source.left_at, target.left_at) if t), default=utcnow())
    )
    source.role = "member"
    if not source.left_at:
        source.left_at = utcnow()
    trip.version += 1


def merge_ballots(db, guest, account, history):
    entries = db.execute(
        select(Ballot, PollRound)
        .join(PollRound, PollRound.id == Ballot.round_id)
        .where(Ballot.user_id == guest)
    ).all()
    for ballot, round_ in entries:
        other = db.scalar(
            select(Ballot).where(Ballot.user_id == account, Ballot.round_id == round_.id)
        )
        if not other:
            history["ballots"].append({"id": ballot.id, "original_user": guest})
            ballot.user_id = account
            ballot.version += 1
            continue
        if is_closed(round_):
            # The two identities' already-published tallies are historical facts.
            # No ballot can be cast or changed in this round after the merge.
            continue
        guest_is_newer = as_utc(ballot.submitted_at) > as_utc(other.submitted_at)
        winner, superseded = (ballot, other) if guest_is_newer else (other, ballot)
        choices = db.scalars(
            select(BallotChoice).where(BallotChoice.ballot_id == superseded.id)
        ).all()
        history["superseded_ballots"].append(
            {
                "round_id": round_.id,
                "id": superseded.id,
                "user_id": superseded.user_id,
                "submitted_at": as_utc(superseded.submitted_at).isoformat(),
                "choices": [
                    {"option_id": c.option_id, "value": c.value, "rank": c.rank} for c in choices
                ],
                "kept_ballot": winner.id,
            }
        )
        next_version = max(winner.version, superseded.version) + 1
        db.delete(superseded)
        db.flush()
        winner.user_id, winner.version = account, next_version


def merge_availability(db, guest, account):
    for source in db.scalars(
        select(AvailabilityEntry).where(AvailabilityEntry.user_id == guest)
    ).all():
        existing = db.scalars(
            select(AvailabilityEntry)
            .where(
                AvailabilityEntry.trip_id == source.trip_id,
                AvailabilityEntry.user_id == account,
                AvailabilityEntry.end_date >= source.start_date,
                AvailabilityEntry.start_date <= source.end_date,
            )
            .order_by(AvailabilityEntry.start_date)
        ).all()
        cursor, last = source.start_date.toordinal(), source.end_date.toordinal()
        uncovered = []
        for row in existing:
            start, end = row.start_date.toordinal(), row.end_date.toordinal()
            if cursor < start:
                uncovered.append((cursor, start - 1))
            cursor = max(cursor, end + 1)
        if cursor <= last:
            uncovered.append((cursor, last))
        for start, end in uncovered:
            db.add(
                AvailabilityEntry(
                    trip_id=source.trip_id,
                    user_id=account,
                    start_date=date.fromordinal(start),
                    end_date=date.fromordinal(end),
                    status=source.status,
                )
            )
        # Keep original dated statements on the retired membership for provenance.


def merge_tasks_and_bookings(db, trip_ids, guest, account, history):
    for assignment in db.scalars(select(TaskAssignee).where(TaskAssignee.user_id == guest)).all():
        task = db.get(Task, assignment.task_id)
        other = db.scalar(
            select(TaskAssignee).where(
                TaskAssignee.task_id == task.id, TaskAssignee.user_id == account
            )
        )
        if other:
            statuses = ["todo", "doing", "done"]
            other.state = max([assignment.state, other.state], key=statuses.index)
            db.delete(assignment)
        else:
            assignment.user_id = account
        task.version += 1
    for booking in db.scalars(select(Booking).where(Booking.trip_id.in_(trip_ids))).all():
        changed = booking.created_by == guest
        segments = []
        for leg in booking.segments:
            passengers = [dict(person) for person in leg["passengers"]]
            source = next((p for p in passengers if p["user_id"] == guest), None)
            if source:
                changed = True
                other = next((p for p in passengers if p["user_id"] == account), None)
                if other:
                    history["passengers"].append(
                        {
                            "booking_id": booking.id,
                            "segment": len(segments),
                            "source": source,
                            "target": dict(other),
                        }
                    )
                    for key in ("seat", "baggage"):
                        other[key] = other.get(key) or source.get(key) or ""
                    passengers.remove(source)
                else:
                    source["user_id"] = account
            segments.append({**leg, "passengers": passengers})
        if booking.stay and guest in booking.stay["guests"]:
            changed = True
            booking.stay = {
                **booking.stay,
                "guests": list(
                    dict.fromkeys(
                        account if who == guest else who for who in booking.stay["guests"]
                    )
                ),
            }
        if changed:
            if booking.created_by == guest:
                history["booking_authors"].append(booking.id)
                booking.created_by = account
            booking.segments = segments
            booking.version += 1


def merge_guest(db, source: User, target: User):
    guest, account = source.id, target.id
    if source.account_type != "guest" or target.account_type != "google" or guest == account:
        fail(409, "INVALID_MERGE", "無法合併這兩個帳號。")
    if db.scalar(select(GuestMerge.id).where(GuestMerge.guest_id == guest)):
        fail(409, "ALREADY_MERGED", "這個訪客身分已完成合併，請重新登入。")
    # Serialize independent guest upgrades into this account and all writes in involved trips.
    db.scalar(select(User.id).where(User.id == account).with_for_update())
    trips = db.scalars(
        select(Trip)
        .join(Membership)
        .where(Membership.user_id == guest)
        .order_by(Trip.id)
        .with_for_update(of=Trip)
    ).all()
    trip_ids = [trip.id for trip in trips]
    history = defaultdict(list)
    for trip in trips:
        member = db.scalar(
            select(Membership).where(Membership.trip_id == trip.id, Membership.user_id == guest)
        )
        membership_union(db, trip, member, account)
        audit(
            db,
            trip.id,
            account,
            "membership",
            member.id,
            "guest_merge",
            {"original_user_id": guest},
        )
    for model in (Place, ItineraryItem, Poll):
        db.execute(
            update(model)
            .where(model.editable_by == guest)
            .values(editable_by=account, version=model.version + 1)
        )
    db.execute(delete(EditLease).where(EditLease.user_id == guest))
    for model, field in ((Comment, "author_id"), (Task, "created_by")):
        column = getattr(model, field)
        history[model.__tablename__].extend(
            db.scalars(select(model.id).where(column == guest)).all()
        )
        db.execute(
            update(model)
            .where(column == guest)
            .values(**{field: account, "version": model.version + 1})
        )
    merge_ballots(db, guest, account, history)
    merge_availability(db, guest, account)
    merge_tasks_and_bookings(db, trip_ids, guest, account, history)
    history["files"].extend(db.scalars(select(TripFile.id).where(TripFile.owner_id == guest)))
    db.execute(
        update(FileLink)
        .where(FileLink.kind == "draft", FileLink.target_id == guest)
        .values(target_id=account)
    )
    db.execute(
        update(TripFile)
        .where(TripFile.owner_id == guest)
        .values(owner_id=account, version=TripFile.version + 1)
    )
    for grant in db.scalars(select(FilePermission).where(FilePermission.user_id == guest)).all():
        if db.scalar(
            select(FilePermission.id).where(
                FilePermission.file_id == grant.file_id, FilePermission.user_id == account
            )
        ):
            db.delete(grant)
        else:
            grant.user_id = account
    for budget in db.scalars(
        select(Budget).where(Budget.scope == "personal", Budget.target == guest)
    ).all():
        other = db.scalar(
            select(Budget.id).where(
                Budget.trip_id == budget.trip_id,
                Budget.scope == "personal",
                Budget.target == account,
            )
        )
        if not other:
            budget.target, budget.version = account, budget.version + 1
        # Conflicting original personal budgets remain private on the retired identity.
    db.execute(
        update(FinanceLedger)
        .where(FinanceLedger.trip_id.in_(trip_ids))
        .values(version=FinanceLedger.version + 1)
    )
    for notice in db.scalars(select(Notice).where(Notice.user_id == guest)).all():
        other = db.scalar(
            select(Notice).where(Notice.user_id == account, Notice.comment_id == notice.comment_id)
        )
        if not other:
            notice.user_id = account
        elif notice.read_at is None:
            other.read_at = None
    settings = db.get(NoticePreference, guest)
    if settings and not db.get(NoticePreference, account):
        db.add(NoticePreference(user_id=account, mentions=settings.mentions, push=False))
    for key in db.scalars(select(CreationKey).where(CreationKey.user_id == guest)).all():
        other = db.scalar(
            select(CreationKey.id).where(
                CreationKey.user_id == account,
                CreationKey.operation == key.operation,
                CreationKey.key == key.key,
            )
        )
        if not other:
            key.user_id = account
    db.add(GuestMerge(guest_id=guest, account_id=account, history=dict(history)))
    db.execute(
        update(LoginSession)
        .where(LoginSession.user_id == guest, LoginSession.revoked_at.is_(None))
        .values(revoked_at=utcnow())
    )
    return trip_ids
