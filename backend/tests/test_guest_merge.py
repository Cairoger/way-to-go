from datetime import date, timedelta
from urllib.parse import parse_qs, urlsplit

from sqlalchemy import select

from app import auth
from app.availability_models import AvailabilityEntry
from app.core import COOKIE, make_session
from app.decisions_models import Ballot, BallotChoice, Poll, PollOption, PollRound
from app.merge_models import GuestMerge
from app.models import AuthIdentity, Membership, utcnow
from app.planning_models import Place
from app.preparation_models import Booking, Task, TaskAssignee


def callback(guest, target, monkeypatch, subject="test-verified-subject"):
    with make_session() as db:
        db.add(AuthIdentity(provider="google", provider_subject=subject, user_id=target))
        db.commit()
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "test-client")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "test-secret")
    query = parse_qs(urlsplit(guest.post("/api/v1/auth/google", json={}).json()["url"]).query)
    monkeypatch.setattr(
        auth, "exchange_code", lambda *args: {"sub": subject, "nonce": query["nonce"][0]}
    )
    result = guest.get(auth.OAUTH_PATH, params={"state": query["state"][0], "code": "tested-code"})
    assert result.status_code == 303, result.text


def test_merge_keeps_owner_authorization_finances_and_private_travel_data(
    owner, guest, client, trip, monkeypatch
):
    root = "/api/v1/trips/" + trip["id"]
    old_token = guest.cookies.get(COOKIE)
    target = owner.get("/api/v1/auth/me").json()["id"]
    source = guest.get("/api/v1/auth/me").json()["id"]
    assert owner.post(root + "/transfer", json={"user_id": source, "version": 1}).status_code == 200
    expense = {
        "title": "車資",
        "category": "交通",
        "incurred_on": "2026-11-20",
        "kind": "actual",
        "currency": "TWD",
        "amount": "120",
        "split_mode": "custom",
        "payers": {target: "90", source: "30"},
        "splits": {source: "90", target: "30"},
    }
    assert guest.post(root + "/expenses", json=expense).status_code == 201
    state = guest.get(root + "/finance").json()
    assert (
        guest.post(
            root + "/settlements",
            json={
                "from_user_id": source,
                "to_user_id": target,
                "amount": "10",
                "version": state["version"],
            },
        ).status_code
        == 201
    )
    with make_session() as db:
        place = Place(trip_id=trip["id"], name="碼頭", created_by=source, editable_by=source)
        db.add(place)
        booking = Booking(
            trip_id=trip["id"],
            created_by=source,
            kind="flight",
            title="去程",
            status="booked",
            currency="TWD",
            reference="private-code",
            website="",
            segments=[{"passengers": [{"user_id": source, "seat": "12F", "baggage": "1件"}]}],
        )
        db.add(booking)
        task = Task(
            trip_id=trip["id"],
            created_by=source,
            scope="shared",
            title="整理文件",
            description="",
            priority="normal",
        )
        db.add(task)
        db.flush()
        db.add_all(
            [
                TaskAssignee(task_id=task.id, user_id=source, state="done"),
                TaskAssignee(task_id=task.id, user_id=target, state="todo"),
            ]
        )
        db.commit()
    callback(guest, target, monkeypatch)
    assert guest.get("/api/v1/auth/me").json()["id"] == target
    assert (
        client.get("/api/v1/auth/me", headers={"Cookie": COOKIE + "=" + old_token}).status_code
        == 401
    )
    roster = guest.get(root + "/members").json()
    assert len(roster) == 1 and roster[0]["role"] == "owner" and roster[0]["id"] == target
    state = guest.get(root + "/finance").json()
    assert state["balances"] == {target: "0.00"} and state["status"] == "settled"
    assert state["expenses"][0]["editable"] and state["expenses"][0]["base_amount"] == "120.00"
    assert (
        state["expenses"][0]["payers"] == {target: "90.00", source: "30.00"}
        and len(state["settlements"]) == 1
    )
    with make_session() as db:
        merged_place = db.get(Place, place.id)
        assert (merged_place.created_by, merged_place.editable_by) == (source, target)
        merged_booking = db.get(Booking, booking.id)
        assert merged_booking.created_by == target and merged_booking.segments[0]["passengers"] == [
            {"user_id": target, "seat": "12F", "baggage": "1件"}
        ]
        assignees = db.scalars(select(TaskAssignee).where(TaskAssignee.task_id == task.id)).all()
        assert len(assignees) == 1 and (assignees[0].user_id, assignees[0].state) == (
            target,
            "done",
        )


def test_open_ballot_collisions_dates_and_closed_results(owner, guest, trip, monkeypatch):
    target = owner.get("/api/v1/auth/me").json()["id"]
    source = guest.get("/api/v1/auth/me").json()["id"]
    with make_session() as db:
        poll = Poll(trip_id=trip["id"], created_by=source, editable_by=source)
        db.add(poll)
        db.flush()
        rounds = []
        for number, closed in [(1, True), (2, False)]:
            round_ = PollRound(
                poll_id=poll.id,
                number=number,
                title="餐廳",
                kind="place",
                mode="single",
                closed_at=utcnow() if closed else None,
            )
            db.add(round_)
            db.flush()
            rounds.append(round_.id)
            for i, user in enumerate([target, source], 1):
                option = PollOption(
                    round_id=round_.id, created_by=user, option_text=str(i), ordinal=i
                )
                ballot = Ballot(
                    round_id=round_.id,
                    user_id=user,
                    submitted_at=utcnow() + timedelta(seconds=i),
                    options_version=1,
                )
                db.add_all([option, ballot])
                db.flush()
                db.add(BallotChoice(ballot_id=ballot.id, option_id=option.id))
        db.add_all(
            [
                AvailabilityEntry(
                    trip_id=trip["id"],
                    user_id=source,
                    start_date=date(2027, 1, 1),
                    end_date=date(2027, 1, 5),
                    status="yes",
                ),
                AvailabilityEntry(
                    trip_id=trip["id"],
                    user_id=target,
                    start_date=date(2027, 1, 3),
                    end_date=date(2027, 1, 4),
                    status="no",
                ),
            ]
        )
        db.commit()
    callback(guest, target, monkeypatch)
    with make_session() as db:
        assert len(db.scalars(select(Ballot).where(Ballot.round_id == rounds[0])).all()) == 2
        ballots = db.scalars(select(Ballot).where(Ballot.round_id == rounds[1])).all()
        assert len(ballots) == 1 and ballots[0].user_id == target
        option = db.scalar(
            select(PollOption).join(BallotChoice).where(BallotChoice.ballot_id == ballots[0].id)
        )
        assert option.option_text == "2"
        merged = db.scalar(select(GuestMerge).where(GuestMerge.guest_id == source))
        assert merged.history["superseded_ballots"][0]["user_id"] == target
        statuses = [
            (row.start_date.day, row.end_date.day, row.status)
            for row in db.scalars(
                select(AvailabilityEntry)
                .where(AvailabilityEntry.user_id == target)
                .order_by(AvailabilityEntry.start_date)
            )
        ]
        assert statuses == [(1, 2, "yes"), (3, 4, "no"), (5, 5, "yes")]
        assert (
            db.get(Poll, poll.id).created_by == source
            and db.get(Poll, poll.id).editable_by == target
        )
        assert db.scalar(select(Membership).where(Membership.user_id == source)).left_at
