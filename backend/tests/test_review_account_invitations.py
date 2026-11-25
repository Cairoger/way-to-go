from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from conftest import browser
from sqlalchemy import select

from app.core import COOKIE, make_session
from app.models import Invitation, User


def test_profile_is_self_only_and_creator_survives_transfer(owner, guest, trip):
    api = "/api/v1"
    original = owner.get(api + "/auth/me").json()
    recipient = guest.get(api + "/auth/me").json()
    before = guest.get(api + "/notifications").json()["preferences"]
    updated = owner.patch(
        api + "/auth/me", json={"nickname": " 海邊旅人 ", "version": original["version"]}
    )
    assert updated.is_success and updated.json()["nickname"] == "海邊旅人"
    assert updated.json()["version"] == original["version"] + 1
    assert owner.get(api + "/auth/me").json()["nickname"] == "海邊旅人"
    assert (
        guest.patch(
            api + "/auth/me",
            json={"nickname": " ", "version": recipient["version"]},
        ).status_code
        == 422
    )
    assert (
        guest.patch(
            api + "/auth/me",
            json={"nickname": "其他", "id": original["id"], "version": recipient["version"]},
        ).status_code
        == 422
    )
    assert owner.patch(api + "/auth/me", json={"nickname": "沒有版本"}).status_code == 422
    assert guest.get(api + "/auth/me").json() == recipient
    assert guest.get(api + "/notifications").json()["preferences"] == before
    path = api + "/trips/" + trip["id"]
    assert owner.post(
        path + "/transfer", json={"version": trip["version"], "user_id": recipient["id"]}
    ).is_success
    got = guest.get(path).json()
    assert (got["created_by"], got["creator_name"], got["owner_id"], got["created_at"]) == (
        original["id"],
        "海邊旅人",
        recipient["id"],
        trip["created_at"],
    )
    with make_session() as db:
        assert db.get(User, original["id"]).nickname == "海邊旅人"


def test_concurrent_profile_saves_accept_one_version(owner, guest, trip):
    profile = "/api/v1/auth/me"
    original = owner.get(profile).json()
    session = owner.cookies.get(COOKIE)
    gate = Barrier(2)

    def save(name):
        with browser() as tab:
            tab.cookies.set(COOKIE, session, domain="testserver.local", path="/")
            gate.wait(timeout=10)
            return tab.patch(profile, json={"nickname": name, "version": original["version"]})

    with ThreadPoolExecutor(max_workers=2) as pool:
        writes = list(pool.map(save, ["名稱甲", "名稱乙"]))
    success, conflict = sorted(writes, key=lambda r: r.status_code)
    assert (success.status_code, conflict.status_code) == (200, 409)
    assert conflict.json()["code"] == "VERSION_CONFLICT"
    assert success.json() == owner.get(profile).json()
    assert success.json()["version"] == original["version"] + 1
    members = guest.get(f"/api/v1/trips/{trip['id']}/members").json()
    assert (
        next(m["nickname"] for m in members if m["id"] == original["id"])
        == success.json()["nickname"]
    )


def test_invitation_retries_preserve_one_working_code(owner, client, trip):
    path = "/api/v1/trips/" + trip["id"] + "/invitations"
    headers = {"Idempotency-Key": "same-logical-operation"}
    first = owner.post(path, json={"days": 2}, headers=headers)
    replay = owner.post(path, json={"days": 2}, headers=headers)
    assert first.status_code == replay.status_code == 201
    assert first.json() == replay.json()
    assert len(owner.get(path).json()) == 1
    assert owner.post(path, json={"days": 3}, headers=headers).status_code == 409
    assert client.post(
        "/api/v1/auth/guest", json={"nickname": "新旅伴", "code": replay.json()["code"]}
    ).is_success
    second = owner.post(path, json={"days": 2}, headers={"Idempotency-Key": "new-operation"})
    assert second.json()["id"] != first.json()["id"]
    with make_session() as db:
        assert all(row.token_hash != first.json()["code"] for row in db.scalars(select(Invitation)))
    assert owner.delete(path + "/" + first.json()["id"]).is_success
    assert owner.post(path, json={"days": 2}, headers=headers).status_code == 410
