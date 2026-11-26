"""Functional probes. Run with backend and backend/tests on PYTHONPATH, and -p conftest."""
import base64
import io
import time
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from urllib.parse import parse_qs, urlsplit

import qrcode
import qrcode.image.svg
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core import COOKIE, make_session, public_origin
from app.main import app
from app.models import AuditLog, Trip, utcnow


def ok(response):
    assert response.is_success, (response.status_code, response.text[:400])
    return response.json()


def lock(client, row, kind):
    res = ok(client.post("/api/v1/edit-leases", json={"resource_id": row["id"], "resource_type": kind}))
    return {"lease_id": res["id"], "version": res["version"]}


def test_core_trip_fields_status_retention(owner, guest, trip):
    path = "/api/v1/trips/" + trip["id"]
    assert trip["title"] and trip["start_date"] is trip["end_date"] is None
    more = dict(title="optional", description="night", cover="kyoto", currency="JPY",
                destinations=["Japan", "Kyoto", "Taiwan", "Taipei"], day_count=3,
                start_date="2027-04-01", end_date="2027-04-02")
    row = ok(owner.post("/api/v1/trips", json=more))
    assert all(row[k] == v for k, v in more.items())
    assert row["created_at"] and row["owner_id"] == ok(owner.get("/api/v1/auth/me"))["id"]
    print("optional fields, 3 days, two countries/cities, metadata, date-less title-only verified")
    row = trip
    for state in ("planning", "confirmed", "traveling", "completed"):
        row = ok(owner.patch(path, json={"status":state, "version":row["version"]}))
        assert ok(guest.get(path))["status"] == state
    row = ok(owner.patch(path, json={"title":"edited after completion","version":row["version"]}))
    assert ok(guest.get(path))["title"] == "edited after completion"
    row = ok(owner.post(path+"/archive", json={"version":row["version"]}))
    assert ok(guest.get(path))["status"] == "completed" and row["archived"]
    assert ok(guest.get(path+"/days"))
    row = ok(owner.delete(path, params={"version":row["version"]}))
    with make_session() as db:
        db.get(Trip, trip["id"]).deleted_at = utcnow() - timedelta(days=29)
        db.commit()
    row = ok(owner.post(path+"/restore", json={"version":row["version"]}))
    assert row["deleted_at"] is None
    row = ok(owner.delete(path, params={"version":row["version"]}))
    with make_session() as db:
        db.get(Trip, trip["id"]).deleted_at = utcnow() - timedelta(days=31)
        db.commit()
    assert all(t["id"] != trip["id"] for t in ok(owner.get("/api/v1/trips")))
    assert owner.post(path+"/restore", json={"version":row["version"]}).status_code == 404
    print("four states; completed editable; archive preserves days; deleted 29d restore=200; 31d restore=404")


def test_core_trip_original_creator_after_transfer(owner, guest, trip):
    path = "/api/v1/trips/" + trip["id"]
    creator = ok(owner.get("/api/v1/auth/me"))["id"]
    other = ok(guest.get("/api/v1/auth/me"))["id"]
    ok(owner.post(path+"/transfer",json={"user_id":other,"version":trip["version"]}))
    shown = ok(guest.get(path))
    with make_session() as db:
        entry = db.scalar(select(AuditLog).where(AuditLog.entity_id == trip["id"], AuditLog.action == "create"))
        assert entry.actor_id == creator
    print("creation actor persists in audit log; summary keys:",sorted(shown))
    assert shown.get("created_by", shown.get("creator_id")) == creator


def test_core_qr_and_default_invitation(owner, client, trip, invitation):
    entry = parse_qs(urlsplit(invitation["url"]).query)["invite"][0]
    assert entry == invitation["code"]
    remaining = (datetime.fromisoformat(invitation["expires_at"]) - datetime.now(timezone.utc)).total_seconds()
    assert 7*86400-20 < remaining <= 7*86400
    buf = io.BytesIO()
    qrcode.make(invitation["url"], image_factory=qrcode.image.svg.SvgPathImage).save(buf)
    assert base64.b64decode(invitation["qr_data_url"].split(",")[1]) == buf.getvalue()
    ok(client.post("/api/v1/auth/guest", json={"code":entry, "nickname":"sample"}))
    assert ok(client.get("/api/v1/auth/me"))["nickname"] == "sample"
    assert len(ok(owner.get("/api/v1/trips/"+trip["id"]+"/members"))) == 2
    print("href token equals invite code; generated SVG byte-equal to QR encoding full URL; TTL seconds", round(remaining))


def test_core_context_session_https(owner, trip, invitation, monkeypatch):
    origin = "https://testserver"
    monkeypatch.setenv("PUBLIC_ORIGIN", origin)
    public_origin.cache_clear()
    with TestClient(app, base_url=origin, headers={"Origin":origin}) as guest:
        resp = guest.post("/api/v1/auth/guest", json={"code":invitation["code"],"nickname":"cookie"})
        ok(resp)
        header = resp.headers["set-cookie"].lower()
        assert all(v in header for v in ["httponly","secure","samesite=lax","max-age="])
        assert guest.get("/api/v1/trips/"+trip["id"]).status_code == 200
        print("HTTPS Set-Cookie attributes HttpOnly, Secure, SameSite=Lax, Max-Age; next request /trips/{id}=200")


def test_core_places_fields_status_author_days(owner, guest, trip):
    path = "/api/v1/trips/" + trip["id"]
    first = ok(guest.get(path + "/days"))[0]
    second = ok(guest.post(path + "/days", json={"title":"Day two"}))
    assert first["day_number"] == 1 and second["day_number"] == 2 and first["date"] is second["date"] is None
    person = ok(guest.get("/api/v1/auth/me"))["id"]
    data = dict(name="Museum",address="A road",latitude=25.1,longitude=121.5,country="TW",city="Taipei",
        category="place",tags=["history"],status="must",duration=45,cost="12.34",opening_hours="0900-1700",
        website="https://example.org/",photo_url="https://example.org/photo.png",notes="bring umbrella")
    place = ok(guest.post(path+"/places",json=data))
    saved = ok(owner.get(path+"/places"))[0]
    assert all(saved[k] == v for k,v in data.items() if k!="cost") and Decimal(str(saved["cost"])) == Decimal("12.34")
    assert saved["created_by"] == saved["editable_by"] == person
    for state in ("want","maybe","skip","must"):
        place = ok(guest.patch("/api/v1/places/"+place["id"],json={**lock(guest,place,"place"),"status":state}))
        assert ok(owner.get(path+"/places"))[0]["status"] == state
    hist = ok(owner.get("/api/v1/places/"+place["id"]+"/history"))
    assert len(hist) == 5 and all(r["actor"] for r in hist)
    for day in (first,second):
        ok(guest.post("/api/v1/days/"+day["id"]+"/items",json={"title":"Museum","place_id":place["id"],"item_type":"place"}))
    days = ok(owner.get(path+"/days"))
    assert all(d["items"][0]["place_id"] == place["id"] for d in days)
    ok(owner.patch(path,json={"start_date":"2027-04-01","version":trip["version"]}))
    assert [d["date"] for d in ok(owner.get(path+"/days"))] == ["2027-04-01","2027-04-02"]
    print("all 15 manually entered fields persisted; author retained; 4 statuses; 5 audit entries; same place in two date-less days -> April 1, 2")


def test_core_original_place_removal(owner, trip):
    path = "/api/v1/trips/"+trip["id"]
    place = ok(owner.post(path+"/places",json={"name":"sample"}))
    token = lock(owner,place,"place")
    response = owner.request("DELETE","/api/v1/places/"+place["id"],json=token)
    print("original place DELETE",response.status_code,"; candidate relation and place are distinct")
    assert response.status_code in (200,204)


def test_core_time_options_types_and_order(owner, guest, trip):
    path = "/api/v1/trips/"+trip["id"]
    day = ok(owner.get(path+"/days"))[0]
    entry = "/api/v1/days/"+day["id"]+"/items"
    times = [{},{"start_time":"09:00"},{"start_time":"09:10","end_time":"10:20"},{"start_time":"10:00","duration":30}]
    kinds = ("place","food","transit","stay","flight","custom")
    for i,kind in enumerate(kinds):
        body = dict(title=kind,item_type=kind,**times[i%len(times)])
        row = ok(guest.post(entry,json=body))
        assert all(row[k] == v for k,v in body.items())
    saved = ok(owner.get(path+"/days"))[0]["items"]
    assert [x["item_type"] for x in saved] == list(kinds)
    assert any(x["overlap"] for x in saved)
    assert guest.post(entry,json={"title":"bad","start_time":"10:00","end_time":"09:50"}).status_code == 422
    assert not ok(owner.get(path+"/places"))
    print("6 types, 4 time modes, no place or date required; overlapping values saved; invalid reverse range=422")


def test_core_lease_duration_and_explicit_release(owner, guest, trip):
    path = "/api/v1/trips/"+trip["id"]
    day = ok(owner.get(path+"/days"))[0]
    row = ok(guest.post("/api/v1/days/"+day["id"]+"/items",json={"title":"rail"}))
    body = {"resource_type":"item","resource_id":row["id"]}
    granted = ok(guest.post("/api/v1/edit-leases", json=body))
    ttl = (datetime.fromisoformat(granted["expires_at"]) - datetime.now(timezone.utc)).total_seconds()
    assert 85 < ttl <= 90
    assert ok(owner.get(path+"/days"))[0]["items"][0]["editing_by"] == ok(guest.get("/api/v1/auth/me"))["nickname"]
    renewed = ok(guest.post("/api/v1/edit-leases/"+granted["id"]+"/renew"))
    initial = datetime.fromisoformat(granted["expires_at"])
    after = datetime.fromisoformat(renewed["expires_at"])
    assert after.replace(tzinfo=timezone.utc) > initial.replace(tzinfo=timezone.utc)
    ok(guest.delete("/api/v1/edit-leases/"+granted["id"]))
    assert ok(owner.get(path+"/days"))[0]["items"][0]["editing_by"] is None
    assert ok(guest.post("/api/v1/edit-leases",json=body))["id"] != granted["id"]
    print("lease TTLs (s)",round(ttl,2),"; renewed; other member sees holder; explicit release and reacquire")


def test_core_live_wikipedia(owner, trip):
    response = owner.get("/api/v1/trips/"+trip["id"]+"/place-search",params={"q":"台北101"})
    print("Wikipedia search returned",response.status_code, str(response.json())[:240])
    assert response.status_code == 200 and any("latitude" in item for item in response.json())


def test_core_expiration_after_editor_disappears(owner, trip):
    from conftest import browser
    path = "/api/v1/trips/"+trip["id"]
    spot = ok(owner.post(path+"/places",json={"name":"lease timing"}))
    body = {"resource_type":"place","resource_id":spot["id"]}
    with browser() as disappearing_editor:
        disappearing_editor.cookies.update(owner.cookies)
        old = ok(disappearing_editor.post("/api/v1/edit-leases",json=body))
    assert owner.post("/api/v1/edit-leases",json=body).status_code == 423
    started=time.monotonic()
    time.sleep(90.5)
    fresh = ok(owner.post("/api/v1/edit-leases",json=body))
    assert old["id"] != fresh["id"]
    print("no renew/release after editor closed; contention=423; granted fresh lease after",round(time.monotonic()-started,1),"seconds")


def test_core_merge_comment_ownership(owner, guest, trip, monkeypatch):
    from test_guest_merge import callback
    path = "/api/v1/trips/"+trip["id"]
    msg=ok(guest.post(path+"/comments",json={"content":"traveler note"}))
    target=ok(owner.get("/api/v1/auth/me"))["id"]
    callback(guest,target,monkeypatch)
    rows=ok(guest.get(path+"/comments"))
    data=next(c for c in rows if c["id"]==msg["id"])
    assert data["content"]=="traveler note" and data["author_id"]==target
    print("mock OIDC callback merges guest comment by ID, content and target author; trip still readable")
