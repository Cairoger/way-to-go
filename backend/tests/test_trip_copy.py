from sqlalchemy import select

from app.availability_models import AvailabilityEntry
from app.core import make_session
from app.decisions_models import Comment, Poll
from app.finance_models import Budget
from app.models import Invitation, User, utcnow
from app.planning_models import Candidate, ItineraryItem
from app.preparation_models import Booking, Task


def test_copy_planning_snapshot_to_own_trip_only(owner, guest, trip):
    source = "/api/v1/trips/" + trip["id"]
    guest_id = guest.get("/api/v1/auth/me").json()["id"]
    assert guest.post(source + "/copy").status_code == 403
    updated = owner.patch(
        source,
        json={
            "version": trip["version"],
            "status": "completed",
            "day_count": 2,
            "currency": "JPY",
            "destinations": ["日本"],
            "description": "沿河散步",
        },
    ).json()
    days = guest.get(source + "/days").json()
    old_place = owner.post(
        source + "/places", json={"name": "河岸", "cost": "45.00", "tags": ["散步"]}
    ).json()
    kept_place = guest.post(source + "/places", json={"name": "美術館", "status": "must"}).json()
    unused = owner.post(source + "/places", json={"name": "已放棄"}).json()
    for day in days:
        r = owner.post(
            "/api/v1/days/" + day["id"] + "/items",
            json={
                "title": "河岸散步",
                "item_type": "place",
                "place_id": old_place["id"],
                "start_time": "10:00",
            },
        )
        assert r.is_success, r.text
    dropped = guest.post(
        "/api/v1/days/" + days[0]["id"] + "/items",
        json={"title": "已刪除的活動", "item_type": "custom"},
    ).json()
    assert guest.post(source + "/comments", json={"content": "旅伴的討論"}).is_success
    assert guest.post(
        source + "/availability", json={"start_date": "2027-02-01", "status": "maybe"}
    ).is_success
    assert guest.post(
        source + "/polls",
        json={
            "kind": "place",
            "mode": "single",
            "title": "去哪裡",
            "options": [{"text": "A"}, {"text": "B"}],
        },
    ).is_success
    with make_session() as db:
        db.get(User, guest_id).account_type = "google"
        db.get(Candidate, old_place["candidate_id"]).removed_at = utcnow()
        db.get(Candidate, unused["candidate_id"]).removed_at = utcnow()
        db.get(ItineraryItem, dropped["id"]).deleted_at = utcnow()
        db.add(
            Budget(
                trip_id=trip["id"], scope="personal", target=trip["owner_id"], amount_minor=25000
            )
        )
        db.add(
            Task(
                trip_id=trip["id"],
                scope="personal",
                created_by=trip["owner_id"],
                title="辦理護照",
                priority="high",
                description="私人備忘",
            )
        )
        db.add(
            Booking(
                trip_id=trip["id"],
                created_by=trip["owner_id"],
                kind="flight",
                title="航班預訂",
                status="booked",
                currency="JPY",
                reference="PRIVATE-BOOKING",
                website="",
                segments=[],
            )
        )
        db.commit()
    assert guest.post(source + "/copy", json={"version": 0}).status_code == 422
    assert guest.post(source + "/copy", json={"version": updated["version"] - 1}).status_code == 409
    key = {"Idempotency-Key": "copy-once"}
    response = guest.post(source + "/copy", json={}, headers=key)
    assert response.status_code == 201, response.text
    copy = response.json()
    destination = "/api/v1/trips/" + copy["id"]
    assert copy["id"] != trip["id"] and copy["owner_id"] == guest_id
    assert copy["title"] == trip["title"] + "（複本）"
    assert copy["member_count"] == 1 and copy["day_count"] == 2 and copy["place_count"] == 1
    assert (
        copy["status"] == "planning"
        and copy["currency"] == "JPY"
        and copy["description"] == "沿河散步"
    )
    assert guest.post(source + "/copy", json={}, headers=key).json()["id"] == copy["id"]
    assert guest.post(source + "/copy", json={"title": "不同請求"}, headers=key).status_code == 409
    assert owner.get(destination).status_code == 403
    places = guest.get(destination + "/places").json()
    assert {p["name"] for p in places} == {"河岸", "美術館"}
    assert all(p["created_by"] == p["editable_by"] == guest_id for p in places)
    assert all(p["id"] not in {kept_place["id"], old_place["id"]} for p in places)
    retained = next(p for p in places if p["name"] == "河岸")
    assert not retained["candidate"] and retained["tags"] == ["散步"]
    new_days = guest.get(destination + "/days").json()
    assert [d["id"] for d in new_days] != [d["id"] for d in days]
    for d in new_days:
        assert len(d["items"]) == 1
        item = d["items"][0]
        assert item["created_by"] == item["editable_by"] == guest_id
        assert item["place_id"] == retained["id"] and item["day_id"] == d["id"]
    with make_session() as db:
        for model in (Poll, Comment, AvailabilityEntry, Invitation, Budget, Task, Booking):
            assert db.scalar(select(model.id).where(model.trip_id == trip["id"]))
            assert not db.scalar(select(model.id).where(model.trip_id == copy["id"]))


def test_copy_linked_travel_arrangements_without_private_booking_or_assignees(owner, trip):
    base = "/api/v1/trips/" + trip["id"]
    day = owner.get(base + "/days").json()[0]
    item = owner.post(
        "/api/v1/days/" + day["id"] + "/items", json={"title": "抵達飯店", "item_type": "custom"}
    ).json()["id"]
    assert owner.post(
        base + "/bookings",
        json={
            "item_id": item,
            "title": "市區住宿",
            "kind": "stay",
            "status": "booked",
            "reference": "OLD-BOOKING",
            "website": "https://example.net/private",
            "price": "3800",
            "stay": {
                "address": "台南",
                "room": "雙人房",
                "check_in": "2027-02-01",
                "check_out": "2027-02-02",
                "guests": [trip["owner_id"]],
            },
        },
    ).is_success
    assert owner.post(
        base + "/tasks",
        json={"item_id": item, "title": "確認接駁車", "assignees": [trip["owner_id"]]},
    ).is_success
    dest = "/api/v1/trips/" + owner.post(base + "/copy", json={}).json()["id"]
    cloned_item = owner.get(dest + "/days").json()[0]["items"][0]["id"]
    booking = owner.get(dest + "/bookings").json()[0]
    task = owner.get(dest + "/tasks").json()[0]
    assert booking["item_id"] == task["item_id"] == cloned_item != item
    assert booking["stay"]["address"] == "台南" and booking["stay"]["guests"] == []
    assert booking["reference"] == booking["website"] == "" and booking["price"] is None
    assert booking["status"] == "planned" and task["assignees"] == []
