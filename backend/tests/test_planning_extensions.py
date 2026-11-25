from datetime import datetime
from zoneinfo import ZoneInfo

from app import planning_weather
from app.core import make_session
from app.planning_models import ItineraryItem


def ok(response):
    assert response.is_success, response.text
    return response.json()


def lock(client, row, kind):
    granted = ok(
        client.post("/api/v1/edit-leases", json={"resource_type": kind, "resource_id": row["id"]})
    )
    return {"lease_id": granted["id"], "version": granted["version"]}


def test_dst_gap_fold_and_date_changes(owner, trip):
    base = "/api/v1/trips/" + trip["id"]
    trip = ok(owner.patch(base, json={"start_date": "2027-03-13", "version": trip["version"]}))
    day = ok(owner.get(base + "/days"))[0]
    tomorrow = ok(owner.post(base + "/days", json={"timezone": "America/New_York"}))
    path = "/api/v1/days/" + day["id"] + "/items"
    gap_path = "/api/v1/days/" + tomorrow["id"] + "/items"
    zone = "America/New_York"
    body = {"title": "集合", "timezone": zone, "start_time": "02:30"}
    result = owner.post(gap_path, json=body)
    assert result.status_code == 422 and "02:30" in result.text and zone in result.text
    assert (
        owner.post(gap_path, json=body | {"start_time": "01:30", "end_time": "02:15"}).status_code
        == 422
    )
    item = ok(owner.post(path, json=body))
    mutation = "/api/v1/itinerary-items/" + item["id"]
    lease = lock(owner, item, "item")
    assert (
        owner.post(
            mutation + "/move", json=lease | {"day_id": tomorrow["id"], "position": 0}
        ).status_code
        == 422
    )
    assert (
        owner.patch(base, json={"start_date": "2027-03-14", "version": trip["version"]}).status_code
        == 422
    )
    assert ok(owner.get(base))["start_date"] == "2027-03-13"
    ok(owner.patch(mutation, json=lease | {"start_time": "01:30"}))
    ok(owner.patch(base, json={"start_date": "2027-11-07", "version": trip["version"]}))
    saved = ok(owner.get(base + "/days"))[0]["items"][0]
    instant = datetime.fromisoformat(saved["start_instant"])
    assert instant.isoformat() == "2027-11-07T05:30:00+00:00"
    assert instant.astimezone(ZoneInfo(zone)).strftime("%H:%M") == saved["start_time"]
    assert "第一次" in saved["clock_note"]


def test_original_place_delete_is_versioned_and_preserves_reference(owner, guest, trip):
    base = "/api/v1/trips/" + trip["id"]
    day = ok(owner.get(base + "/days"))[0]
    items = "/api/v1/days/" + day["id"] + "/items"
    place = ok(guest.post(base + "/places", json={"name": "展館", "address": "中央路一號"}))
    item = ok(owner.post(items, json={"title": "參觀", "place_id": place["id"]}))
    task_data = {"title": "準備門票", "place_id": place["id"]}
    task = ok(owner.post(base + "/tasks", json=task_data))
    path = "/api/v1/places/" + place["id"]
    lease = lock(guest, place, "place")
    assert owner.request("DELETE", path, json=lease).status_code == 403
    assert guest.request("DELETE", path, json=lease | {"lease_id": "expired"}).status_code == 423
    assert (
        guest.request("DELETE", path, json=lease | {"version": lease["version"] + 1}).status_code
        == 409
    )
    candidate = base + "/candidates/" + place["candidate_id"]
    current = ok(guest.request("DELETE", candidate, json=lease))
    assert not current["candidate"] and ok(owner.get(base + "/places"))[0]["id"] == place["id"]
    assert "archived_place" not in ok(owner.get(base + "/days"))[0]["items"][0]
    ok(guest.request("DELETE", path, json=lock(guest, current, "place")))
    assert ok(owner.get(base + "/places")) == []
    saved = ok(owner.get(base + "/days"))[0]["items"][0]
    assert saved["place_id"] == place["id"] and saved["id"] == item["id"]
    assert saved["archived_place"] == {"name": "展館", "address": "中央路一號"}
    assert owner.post(base + "/tasks", json=task_data).status_code == 422
    assert (
        ok(owner.put(base + "/tasks/" + task["id"], json=task_data | {"version": task["version"]}))[
            "place_id"
        ]
        == place["id"]
    )
    copied = "/api/v1/trips/" + ok(owner.post(base + "/copy", json={}))["id"]
    assert ok(owner.get(copied + "/places")) == []
    copied_item = ok(owner.get(copied + "/days"))[0]["items"][0]
    assert copied_item["archived_place"] == saved["archived_place"]
    assert copied_item["place_id"] != place["id"]
    assert owner.post(items, json={"title": "新活動", "place_id": place["id"]}).status_code == 404
    ok(
        owner.patch(
            "/api/v1/itinerary-items/" + item["id"],
            json=lock(owner, item, "item") | {"title": "新標題"},
        )
    )
    assert any(event["action"] == "place.deleted" for event in ok(owner.get(path + "/history")))
    revision = next(
        e
        for e in ok(guest.get(base + "/planner-history"))
        if e["kind"] == "place" and e["version"] == 1
    )
    restore = "/api/v1/planner-history/place/" + place["id"] + "/restore"
    token = lock(guest, place, "place")
    assert (
        guest.post(base + "/candidates", json=token | {"place_id": place["id"]}).status_code == 409
    )
    ok(guest.post(restore, json=token | {"restore_version": revision["version"]}))
    restored = ok(owner.get(base + "/places"))[0]
    assert restored["candidate"] and restored["id"] == place["id"]
    assert "archived_place" not in ok(owner.get(base + "/days"))[0]["items"][0]
    guest_id = ok(guest.get("/api/v1/auth/me"))["id"]
    assert guest.delete(base + "/members/" + guest_id).status_code == 204
    ok(owner.request("DELETE", path, json=lock(owner, restored, "place")))
    assert ok(owner.get(base + "/places")) == []


def test_time_suggestions_and_local_zones(owner, guest, trip):
    base = "/api/v1/trips/" + trip["id"]
    ok(owner.patch(base, json={"start_date": "2026-07-15", "version": trip["version"]}))
    day = ok(owner.get(base + "/days"))[0]
    path = "/api/v1/days/" + day["id"] + "/items"
    anchored = ok(
        guest.post(
            path,
            json={
                "title": "當地午餐",
                "start_time": "12:00",
                "duration": 60,
                "timezone": "America/New_York",
            },
        )
    )
    floating = ok(owner.post(path, json={"title": "下午散步", "timezone": "America/New_York"}))
    items = ok(owner.get(base + "/days"))[0]["items"]
    assert items[0]["start_instant"] == "2026-07-15T16:00:00+00:00"
    assert items[1]["suggested_time"] == "13:00"
    ok(
        owner.post(
            "/api/v1/itinerary-items/" + floating["id"] + "/move",
            json={**lock(owner, floating, "item"), "day_id": day["id"], "position": 0},
        )
    )
    refreshed = ok(owner.get(base + "/days"))[0]["items"]
    assert refreshed[0]["start_time"] is None
    assert refreshed[1]["start_time"] == "12:00" and refreshed[1]["version"] == anchored["version"]
    with make_session() as db:
        assert db.get(ItineraryItem, floating["id"]).start_time is None
    assert owner.post(path, json={"title": "時區錯誤", "timezone": "Not/Real"}).status_code == 422


def test_restore_changed_place_and_deleted_item(owner, guest, trip):
    base = "/api/v1/trips/" + trip["id"]
    place = ok(
        guest.post(base + "/places", json={"name": "原名", "cost": "120.45", "tags": ["散步"]})
    )
    updated = ok(
        guest.patch(
            "/api/v1/places/" + place["id"], json={**lock(guest, place, "place"), "name": "更新"}
        )
    )
    path = "/api/v1/planner-history/place/" + place["id"] + "/restore"
    assert (
        owner.post(
            path, json={"version": 2, "lease_id": "invalid", "restore_version": 1}
        ).status_code
        == 403
    )
    token = lock(guest, updated, "place")
    assert guest.post(path, json={**token, "version": 1, "restore_version": 1}).status_code == 409
    ok(guest.post(path, json={**token, "restore_version": 1}))
    restored = ok(owner.get(base + "/places"))[0]
    assert (restored["name"], float(restored["cost"]), restored["tags"], restored["version"]) == (
        "原名",
        120.45,
        ["散步"],
        3,
    )
    day = ok(owner.get(base + "/days"))[0]
    row = ok(
        guest.post(
            "/api/v1/days/" + day["id"] + "/items",
            json={"title": "保留活動", "place_id": place["id"]},
        )
    )
    ok(
        guest.request(
            "DELETE", "/api/v1/itinerary-items/" + row["id"], json=lock(guest, row, "item")
        )
    )
    assert not ok(owner.get(base + "/days"))[0]["items"]
    history = ok(owner.get(base + "/planner-history"))
    assert any(r["title"] == "保留活動" and not r["editable"] for r in history)
    ok(
        guest.post(
            "/api/v1/planner-history/item/" + row["id"] + "/restore",
            json={**lock(guest, row, "item"), "restore_version": 1},
        )
    )
    returned = ok(guest.get(base + "/days"))[0]["items"][0]
    assert (
        returned["id"] == row["id"]
        and returned["version"] == 3
        and returned["created_by"] == row["created_by"]
    )


def test_weather_success_and_provider_failure(owner, trip, monkeypatch):
    base = "/api/v1/trips/" + trip["id"]
    today = datetime.now(ZoneInfo("Asia/Taipei")).date().isoformat()
    ok(owner.patch(base, json={"start_date": today, "version": trip["version"]}))
    day = ok(owner.get(base + "/days"))[0]
    weather = "/api/v1/days/" + day["id"] + "/weather"
    assert ok(owner.get(weather))["available"] is False
    place = ok(
        owner.post(base + "/places", json={"name": "公園", "latitude": 25.03, "longitude": 121.50})
    )
    ok(
        owner.post(
            "/api/v1/days/" + day["id"] + "/items", json={"place_id": place["id"], "title": "散步"}
        )
    )

    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return {
                "daily": {
                    "time": [today],
                    "weather_code": [3],
                    "temperature_2m_min": [20],
                    "temperature_2m_max": [28],
                    "precipitation_probability_max": [25],
                }
            }

    async def simulated_get(self, url, params):
        assert params["latitude"] == 25.03 and params["timezone"] == "Asia/Taipei"
        return Response()

    monkeypatch.setattr(planning_weather.httpx.AsyncClient, "get", simulated_get)
    monkeypatch.setenv("OPEN_METEO_URL", "https://test.invalid/simulated")
    result = ok(owner.get(weather))
    assert (result["min"], result["max"], result["rain"], result["place"]) == (20, 28, 25, "公園")

    async def broken_get(self, url, params):
        raise planning_weather.httpx.ConnectTimeout("timeout")

    monkeypatch.setenv("OPEN_METEO_URL", "https://test.invalid/unavailable")
    monkeypatch.setattr(planning_weather.httpx.AsyncClient, "get", broken_get)
    assert ok(owner.get(weather))["message"] == "尚無可用天氣預報"
    assert ok(owner.get(base + "/days"))[0]["items"][0]["title"] == "散步"
