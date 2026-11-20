from datetime import timedelta

from app.core import make_session
from app.models import utcnow
from app.planning_models import EditLease

API = "/api/v1"


def checked(response):
    assert response.is_success, response.text
    return response.json()


def lease(browser, resource, kind):
    result = checked(
        browser.post(
            API + "/edit-leases", json={"resource_type": kind, "resource_id": resource["id"]}
        )
    )
    return {"lease_id": result["id"], "version": resource["version"]}


def test_place_retained_after_candidate_removal(owner, guest, trip):
    base = f"{API}/trips/{trip['id']}"
    place = checked(
        guest.post(
            base + "/places",
            json={"name": "赤崁樓", "status": "must", "latitude": 22.998, "longitude": 120.20},
        )
    )
    day = checked(owner.get(base + "/days"))[0]
    item = checked(
        owner.post(
            f"{API}/days/{day['id']}/items",
            json={"title": "古蹟散步", "item_type": "place", "place_id": place["id"]},
        )
    )
    denied = owner.post(
        API + "/edit-leases", json={"resource_type": "place", "resource_id": place["id"]}
    )
    assert denied.status_code == 403
    checked(
        guest.request(
            "DELETE",
            base + "/candidates/" + place["candidate_id"],
            json=lease(guest, place, "place"),
        )
    )
    assert checked(owner.get(base + "/places"))[0]["candidate"] is False
    saved = checked(owner.get(base + "/days"))[0]["items"][0]
    assert (saved["place_id"], saved["id"]) == (place["id"], item["id"])
    assert (
        checked(owner.get(f"{API}/places/{place['id']}/history"))[0]["action"]
        == "candidate.removed"
    )


def test_move_overlap_and_passive_order(owner, guest, trip):
    base = f"{API}/trips/{trip['id']}"
    first = checked(owner.get(base + "/days"))[0]
    second = checked(guest.post(base + "/days", json={"timezone": "Asia/Tokyo"}))
    start = f"{API}/days/{first['id']}/items"
    left = checked(owner.post(start, json={"title": "咖啡", "start_time": "09:00", "duration": 60}))
    right = checked(
        guest.post(start, json={"title": "散步", "start_time": "09:30", "end_time": "10:15"})
    )
    assert all(i["overlap"] for i in checked(owner.get(base + "/days"))[0]["items"])
    edits = lease(guest, right, "item")
    move = {"day_id": first["id"], "position": 0, **edits}
    assert owner.post(f"{API}/itinerary-items/{right['id']}/move", json=move).status_code == 403
    moved = checked(guest.post(f"{API}/itinerary-items/{right['id']}/move", json=move))
    items = checked(owner.get(base + "/days"))[0]["items"]
    assert [i["id"] for i in items] == [right["id"], left["id"]]
    assert items[1]["version"] == left["version"]
    checked(
        guest.post(
            f"{API}/itinerary-items/{right['id']}/move",
            json={
                **lease(guest, moved, "item"),
                "position": 0,
                "day_id": second["id"],
            },
        )
    )
    days = checked(owner.get(base + "/days"))
    assert [d["items"][0]["position"] for d in days] == [0, 0]
    assert all(not d["items"][0]["overlap"] for d in days)
    assert days[0]["date"] is None


def test_lease_contention_renewal_timeout_and_stale_version(owner, trip):
    base = f"{API}/trips/{trip['id']}"
    place = checked(owner.post(base + "/places", json={"name": "車站"}))
    token = lease(owner, place, "place")
    assert (
        owner.post(
            API + "/edit-leases", json={"resource_type": "place", "resource_id": place["id"]}
        ).status_code
        == 423
    )
    checked(owner.post(f"{API}/edit-leases/{token['lease_id']}/renew"))
    with make_session() as db:
        db.get(EditLease, token["lease_id"]).expires_at = utcnow() - timedelta(seconds=1)
        db.commit()
    expired = owner.patch(f"{API}/places/{place['id']}", json={"name": "舊草稿", **token})
    assert expired.status_code == 423
    next_token = lease(owner, place, "place")
    updated = checked(
        owner.patch(f"{API}/places/{place['id']}", json={"name": "新名稱", **next_token})
    )
    stale = owner.patch(f"{API}/places/{place['id']}", json={"name": "舊草稿", **token})
    assert stale.status_code == 409
    assert checked(owner.get(base + "/places"))[0]["name"] == updated["name"]


def test_search_outage_preserves_saved_content(monkeypatch, owner, trip):
    base = f"{API}/trips/{trip['id']}"
    checked(owner.post(base + "/places", json={"name": "已儲存的地點"}))
    monkeypatch.setenv("WIKI_API_URL", "")
    response = owner.get(base + "/place-search", params={"q": "台南美術館"})
    assert response.status_code == 503
    assert checked(owner.get(base + "/places"))[0]["name"] == "已儲存的地點"
