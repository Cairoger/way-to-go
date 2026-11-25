from conftest import browser

from app.core import make_session
from app.models import utcnow
from app.planning_models import ItineraryItem


def test_existing_task_and_booking_links_survive_item_removal(owner, trip):
    base = f"/api/v1/trips/{trip['id']}"
    day = owner.get(base + "/days").json()[0]["id"]
    item = owner.post(
        f"/api/v1/days/{day}/items", json={"title": "飯店報到", "item_type": "custom"}
    ).json()["id"]
    task = {"title": "收拾行李", "item_id": item}
    stay = {
        "kind": "stay",
        "title": "測試住宿",
        "item_id": item,
        "currency": "JPY",
        "price": "12000",
        "stay": {"check_in": "2027-01-01", "check_out": "2027-01-02", "guests": []},
    }
    task_id, booking_id = (
        owner.post(base + "/tasks", json=task).json()["id"],
        owner.post(base + "/bookings", json=stay).json()["id"],
    )
    with make_session() as db:
        db.get(ItineraryItem, item).deleted_at = utcnow()
        db.commit()
    assert owner.post(base + "/tasks", json=task).status_code == 422
    assert owner.post(base + "/bookings", json=stay).status_code == 422
    assert (
        owner.put(
            base + "/tasks/" + task_id, json=task | {"version": 1, "title": "行李已整理"}
        ).json()["item_id"]
        == item
    )
    saved = owner.put(
        base + "/bookings/" + booking_id, json=stay | {"version": 1, "status": "booked"}
    ).json()
    assert saved["item_id"] == item and saved["currency"] == "JPY"
    assert saved["price"].split(".")[0] == "12000"


def test_shared_tasks_and_private_lists(owner, guest, trip):
    base = f"/api/v1/trips/{trip['id']}/tasks"
    mine = owner.get("/api/v1/auth/me").json()["id"]
    theirs = guest.get("/api/v1/auth/me").json()["id"]
    personal = guest.post(base, json={"scope": "personal", "title": "我的證件"})
    assert personal.status_code == 201, personal.text
    task = personal.json()
    assert task["assignees"][0]["user_id"] == theirs
    assert owner.get(base).json() == []
    assert (
        owner.put(
            base + "/" + task["id"] + "/progress", json={"version": 1, "state": "done"}
        ).status_code
        == 404
    )
    assert (
        guest.post(
            base, json={"title": "護照", "scope": "personal", "assignees": [mine]}
        ).status_code
        == 422
    )
    shared = {
        "title": "買車票",
        "assignees": [mine, theirs],
        "priority": "high",
        "due_date": "2027-05-03",
    }
    one = owner.post(base, json=shared, headers={"Idempotency-Key": "train"})
    two = owner.post(base, json=shared, headers={"Idempotency-Key": "train"})
    assert one.status_code == 201 and one.json()["id"] == two.json()["id"]
    change = base + "/" + one.json()["id"] + "/progress"
    assert owner.put(change, json={"state": "done", "version": 1}).json()["state"] == "doing"
    assert guest.put(change, json={"state": "done", "version": 1}).status_code == 409
    assert guest.put(change, json={"state": "done", "version": 2}).json()["state"] == "done"
    assert (
        owner.put(change, json={"user_id": theirs, "state": "todo", "version": 3}).status_code
        == 422
    )
    only_guest = owner.post(base, json={"title": "試車", "assignees": [theirs]}).json()["id"]
    assert (
        owner.put(
            base + "/" + only_guest + "/progress", json={"version": 1, "state": "done"}
        ).status_code
        == 403
    )


def test_reservation_privacy_and_edits(owner, guest, invitation, trip):
    base = f"/api/v1/trips/{trip['id']}/bookings"
    creator = owner.get("/api/v1/auth/me").json()["id"]
    traveller = guest.get("/api/v1/auth/me").json()["id"]
    leg = {
        "number": "WT10",
        "origin": "TPE",
        "destination": "NRT",
        "departure": "2027-04-11T09:00:00+08:00",
        "arrival": "2027-04-11T13:00:00+09:00",
        "passengers": [
            {"user_id": traveller, "seat": "8A", "baggage": "20 kg"},
            {"user_id": creator, "seat": "5C", "baggage": "10 kg"},
        ],
    }
    payload = {
        "kind": "flight",
        "title": "東京機票",
        "price": "100.00",
        "currency": "TWD",
        "reference": "BOOK-EXAMPLE",
        "segments": [leg, {**leg, "number": "WT12", "passengers": []}],
    }
    result = owner.post(base, json=payload)
    assert result.status_code == 201, result.text
    row = result.json()
    with browser() as observer:
        assert observer.post(
            "/api/v1/auth/guest", json={"code": invitation["code"], "nickname": "另一位旅伴"}
        ).is_success
        public = observer.get(base).json()[0]
        assert "reference" not in public and all(
            set(p) == {"user_id"} for p in public["segments"][0]["passengers"]
        )
        own = guest.get(base).json()[0]
        assert (
            own["reference"] == "BOOK-EXAMPLE"
            and own["segments"][0]["passengers"][0]["seat"] == "8A"
        )
        assert "seat" not in own["segments"][0]["passengers"][1]
        assert (
            observer.put(base + "/" + row["id"], json={**payload, "version": 1}).status_code == 403
        )
    assert owner.put(
        base + "/" + row["id"], json={**payload, "version": 1, "status": "booked"}
    ).is_success
    assert owner.request("DELETE", base + "/" + row["id"], json={"version": 1}).status_code == 409
    assert (
        owner.post(
            base, json={**payload, "segments": [{**leg, "arrival": "2027-01-01T00:00:00Z"}]}
        ).status_code
        == 422
    )
    assert owner.post(base, json={**payload, "item_id": "missing"}).status_code == 422
    stay = {
        "kind": "stay",
        "title": "溫泉旅館",
        "reference": "STAY-TEST",
        "stay": {"check_in": "2027-04-11", "check_out": "2027-04-12", "guests": []},
    }
    assert owner.post(base, json=stay).status_code == 201
    assert "reference" not in guest.get(base).json()[1]


def test_owner_maintains_departed_creators_public_booking_only(owner, guest, invitation, trip):
    base = f"/api/v1/trips/{trip['id']}/bookings"
    creator = guest.get("/api/v1/auth/me").json()["id"]
    admin = owner.get("/api/v1/auth/me").json()["id"]
    with browser() as passenger:
        assert passenger.post(
            "/api/v1/auth/guest", json={"nickname": "同班旅客", "code": invitation["code"]}
        ).is_success
        traveller = passenger.get("/api/v1/auth/me").json()["id"]
        leg = {
            "origin": "TPE",
            "destination": "NRT",
            "number": "WT30",
            "departure": "2027-04-03T11:30:00+08:00",
            "arrival": "2027-04-03T16:00:00+09:00",
        }
        personal = {"user_id": traveller, "seat": "1B", "baggage": "20KG"}
        public = {
            "kind": "flight",
            "title": "去程",
            "currency": "JPY",
            "price": "10000",
            "segments": [leg],
        }
        flight = guest.post(
            base,
            json=public
            | {"segments": [leg | {"passengers": [personal]}], "reference": "PRIVATE-FLIGHT"},
        ).json()
        hotel = {
            "kind": "stay",
            "title": "旅館",
            "stay": {"check_in": "2027-04-03", "check_out": "2027-04-05", "room": "雙人房"},
        }
        stay = guest.post(
            base,
            json=hotel
            | {"stay": hotel["stay"] | {"guests": [traveller]}, "reference": "PRIVATE-HOTEL"},
        ).json()
        url = base + "/" + flight["id"] + "/public"
        edit = public | {"title": "去程已確認", "version": 1, "status": "booked"}
        assert owner.put(url, json=edit).status_code == 403
        assert guest.delete(f"/api/v1/trips/{trip['id']}/members/{creator}").is_success
        assert guest.get(base).status_code == 403
        assert all(r["can_edit_public"] and "reference" not in r for r in owner.get(base).json())
        assert passenger.put(url, json=edit).status_code == 403
        assert owner.put(url, json=edit | {"reference": "REPLACE"}).status_code == 422
        assert (
            owner.put(
                url, json=edit | {"segments": [leg | {"passengers": [{"user_id": admin}]}]}
            ).status_code
            == 422
        )
        assert owner.put(url, json=edit | {"segments": [leg, leg]}).status_code == 422
        assert (
            owner.request("DELETE", base + "/" + flight["id"], json={"version": 1}).status_code
            == 403
        )
        saved = owner.put(url, json=edit)
        assert saved.is_success, saved.text
        assert saved.json()["created_by"] == creator and "reference" not in saved.json()
        assert saved.json()["segments"][0]["passengers"] == [{"user_id": traveller}]
        assert owner.put(url, json=edit).status_code == 409
        hotel_url = base + "/" + stay["id"] + "/public"
        assert (
            owner.put(
                hotel_url, json=hotel | {"version": 1, "stay": hotel["stay"] | {"guests": [admin]}}
            ).status_code
            == 422
        )
        assert owner.put(hotel_url, json=hotel | {"version": 1, "title": "海景旅館"}).is_success
        private = {r["kind"]: r for r in passenger.get(base).json()}
        assert (
            private["flight"]["title"] == "去程已確認"
            and private["flight"]["reference"] == "PRIVATE-FLIGHT"
        )
        assert private["flight"]["segments"][0]["passengers"] == [personal]
        assert private["stay"]["title"] == "海景旅館" and private["stay"]["stay"]["guests"] == [
            traveller
        ]
        assert private["stay"]["reference"] == "PRIVATE-HOTEL"
        assert guest.post(
            "/api/v1/invitations/accept", json={"code": invitation["code"]}
        ).is_success
        assert owner.put(url, json=edit | {"version": 2}).status_code == 403
        assert not any(r["can_edit_public"] for r in owner.get(base).json())
