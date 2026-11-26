from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta


def create_poll(client, trip, **fields):
    payload = {
        "title": "下一站去哪裡？",
        "kind": "place",
        "mode": "single",
        "options": [{"text": "博物館"}, {"text": "公園"}, {"text": "海邊"}],
        **fields,
    }
    response = client.post(f"/api/v1/trips/{trip['id']}/polls", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def ballot(client, poll, *indices, ballot_version=0):
    option_ids = [poll["rounds"][0]["options"][i]["id"] for i in indices]
    return client.put(
        f"/api/v1/polls/{poll['id']}/ballot",
        json={
            "version": poll["version"],
            "ballot_version": ballot_version,
            "option_ids": option_ids,
        },
    )


def test_secret_ballots_and_review_after_new_option(owner, guest, trip):
    poll = create_poll(guest, trip)
    path = f"/api/v1/polls/{poll['id']}"
    listing = f"/api/v1/trips/{trip['id']}/polls"
    assert ballot(owner, poll, 0, 1).status_code == 422
    assert ballot(owner, poll, 0).status_code == 200
    view = guest.get(listing).json()[0]
    assert "results" not in view["rounds"][0]
    assert view["rounds"][0]["my_choices"] == []
    assert view["version"] == poll["version"]
    assert (
        guest.patch(path, json={"version": 1, "title": "改規則", "mode": "multiple"}).status_code
        == 409
    )
    assert owner.post(path + "/close", json={"version": 1}).status_code == 403
    poll = guest.post(path + "/options", json={"text": "圖書館", "version": 1}).json()
    owner_view = owner.get(listing).json()[0]["rounds"][0]
    assert owner_view["review_needed"]
    assert ballot(owner, poll, 1).status_code == 409
    assert ballot(owner, poll, 1, ballot_version=1).json()["rounds"][0]["review_needed"] is False
    assert ballot(guest, poll, 0).status_code == 200
    closed = guest.post(path + "/close", json={"version": poll["version"]}).json()
    latest = closed["rounds"][0]
    assert len(latest["results"]["ballots"]) == 2
    assert set(latest["results"]["winners"]) == {o["id"] for o in latest["options"][:2]}
    assert ballot(owner, closed, 0, ballot_version=2).status_code == 409
    reopened = guest.post(path + "/reopen", json={"version": closed["version"]}).json()
    assert reopened["rounds"][1]["results"] == latest["results"]
    assert len(reopened["rounds"][0]["options"]) == 2
    assert "results" not in reopened["rounds"][0]
    assert reopened["rounds"][0]["my_choices"] == []


def test_manual_adoption_keeps_item_after_revote(owner, guest, trip):
    poll = create_poll(owner, trip, mode="multiple")
    assert ballot(guest, poll, 1, 2).status_code == 200
    assert ballot(owner, poll, 1).status_code == 200
    path = f"/api/v1/polls/{poll['id']}"
    closed = owner.post(path + "/close", json={"version": poll["version"]}).json()
    days = f"/api/v1/trips/{trip['id']}/days"
    day = owner.post(days, json={}).json()
    payload = {
        "day_id": day["id"],
        "option_id": closed["rounds"][0]["results"]["winners"][0],
        "version": closed["version"],
    }
    assert guest.post(path + "/adopt", json=payload | {"day_id": "missing"}).status_code == 404
    adopted = guest.post(path + "/adopt", json=payload)
    assert adopted.status_code == 200, adopted.text
    assert guest.post(path + "/adopt", json=payload).json() == adopted.json()
    assert owner.post(path + "/reopen", json={"version": closed["version"]}).status_code == 200
    saved = next(d for d in guest.get(days).json() if d["id"] == day["id"])["items"]
    assert [i["id"] for i in saved] == [adopted.json()["item_id"]]
    assert saved[0]["title"] == "公園"


def test_adoption_retries_follow_item_lifecycle(owner, guest, trip):
    poll = create_poll(owner, trip)
    assert ballot(owner, poll, 0).is_success
    path = f"/api/v1/polls/{poll['id']}"
    closed = owner.post(path + "/close", json={"version": poll["version"]}).json()
    days = f"/api/v1/trips/{trip['id']}/days"
    first = owner.get(days).json()[0]
    second = owner.post(days, json={}).json()
    payload = {
        "version": closed["version"],
        "option_id": closed["rounds"][0]["results"]["winners"][0],
        "day_id": first["id"],
    }
    with ThreadPoolExecutor(max_workers=2) as pool:
        calls = [
            pool.submit(client.post, path + "/adopt", json=payload) for client in (owner, guest)
        ]
        responses = [call.result() for call in calls]
    assert all(r.status_code == 200 for r in responses)
    assert responses[0].json() == responses[1].json()
    item_id = responses[0].json()["item_id"]
    [item] = owner.get(days).json()[0]["items"]
    assert item["id"] == item_id
    editor = owner if owner.get("/api/v1/auth/me").json()["id"] == item["editable_by"] else guest
    item_path = "/api/v1/itinerary-items/" + item_id

    def lease():
        granted = editor.post(
            "/api/v1/edit-leases", json={"resource_id": item_id, "resource_type": "item"}
        )
        assert granted.is_success, granted.text
        return {"lease_id": granted.json()["id"], "version": granted.json()["version"]}

    assert editor.post(
        item_path + "/move", json={**lease(), "day_id": second["id"], "position": 0}
    ).is_success
    moved = owner.post(path + "/adopt", json=payload)
    assert moved.status_code == 409 and moved.json()["code"] == "adopted_item_moved"
    assert editor.request("DELETE", item_path, json=lease()).is_success
    removed = owner.post(path + "/adopt", json=payload)
    assert removed.status_code == 409 and removed.json()["code"] == "adopted_item_removed"
    assert all(not day["items"] for day in guest.get(days).json())

    restored = editor.post(
        "/api/v1/planner-history/item/" + item_id + "/restore",
        json={**lease(), "restore_version": 1},
    )
    assert restored.is_success, restored.text
    retried = guest.post(path + "/adopt", json=payload)
    assert retried.status_code == 200 and retried.json()["item_id"] == item_id
    assert [i["id"] for i in guest.get(days).json()[0]["items"]] == [item_id]


def test_expired_date_poll_zero_result(owner, guest, trip, monkeypatch):
    from app import decisions

    deadline = datetime.now(UTC) + timedelta(days=2)
    poll = create_poll(
        owner,
        trip,
        kind="date",
        options=[{"text": "2027-01-01"}, {"text": "2027-01-02 ~ 2027-01-04"}],
        deadline=deadline.isoformat(),
    )
    monkeypatch.setattr(decisions, "utcnow", lambda: deadline + timedelta(seconds=5))
    assert ballot(guest, poll, 0).status_code == 409
    round_ = guest.get(f"/api/v1/trips/{trip['id']}/polls").json()[0]["rounds"][0]
    assert round_["closed"]
    assert round_["results"]["winners"] == []
    assert not any(round_["results"]["counts"].values())


def test_comment_moderation_and_preserved_replies(owner, guest, trip):
    listing = f"/api/v1/trips/{trip['id']}/comments"
    parent = guest.post(listing, json={"content": "明天幾點集合？"}).json()
    reply = owner.post(listing, json={"content": "早上十點", "parent_id": parent["id"]}).json()
    path = f"/api/v1/comments/{parent['id']}"
    assert owner.patch(path, json={"content": "其他人的內容", "version": 1}).status_code == 403
    assert (
        guest.request("DELETE", f"/api/v1/comments/{reply['id']}", json={"version": 1}).status_code
        == 403
    )
    assert guest.patch(path, json={"content": "在哪集合？", "version": 1}).status_code == 200
    assert guest.patch(path, json={"content": "舊版本", "version": 1}).status_code == 409
    assert owner.request("DELETE", path, json={"version": 2}).status_code == 200
    assert (
        guest.post(listing, json={"content": "追加", "parent_id": parent["id"]}).status_code == 422
    )
    comments = {c["id"]: c for c in guest.get(listing).json()}
    assert comments[parent["id"]]["content"] == ""
    assert comments[reply["id"]]["parent_id"] == parent["id"]


def test_retried_comment_request(owner, trip):
    url = f"/api/v1/trips/{trip['id']}/comments"
    key = {"Idempotency-Key": "same-request"}
    body = {"content": "重送同一筆留言"}
    first = owner.post(url, headers=key, json=body)
    second = owner.post(url, headers=key, json=body)
    assert first.status_code == second.status_code == 201
    assert first.json() == second.json()
    assert len(owner.get(url).json()) == 1
    assert owner.post(url, headers=key, json={"content": "不同內容"}).status_code == 409


def test_rating_ballot_requirements_privacy_review_and_result(owner, guest, trip):
    poll = create_poll(owner, trip, mode="rating")
    url = "/api/v1/polls/" + poll["id"]
    a, b, c = [o["id"] for o in poll["rounds"][0]["options"]]
    base = {"version": 1, "ballot_version": 0}
    for ratings in ({a: 3, b: 5}, {a: 6, b: 3, c: 4}, {a: True, b: 3, c: 4}):
        assert guest.put(url + "/ballot", json=base | {"ratings": ratings}).status_code == 422
    ballot_body = base | {"ratings": {a: 4, b: 3, c: 1}}
    assert guest.put(url + "/ballot", json=ballot_body).is_success
    assert guest.put(url + "/ballot", json=ballot_body).status_code == 409
    listing = f"/api/v1/trips/{trip['id']}/polls"
    view = owner.get(listing).json()[0]["rounds"][0]
    assert view["my_ratings"] == {} and "results" not in view
    assert (
        owner.patch(url, json={"version": 1, "title": "改規則", "mode": "single"}).status_code
        == 409
    )
    changed = owner.post(url + "/options", json={"version": 1, "text": "花園"}).json()
    d = changed["rounds"][0]["options"][-1]["id"]
    assert guest.get(listing).json()[0]["rounds"][0]["review_needed"]
    voted = owner.put(
        url + "/ballot",
        json={
            "version": changed["version"],
            "ballot_version": 0,
            "ratings": {a: 1, b: 5, c: 2, d: 5},
        },
    )
    assert voted.is_success, voted.text
    closed = owner.post(url + "/close", json={"version": changed["version"]}).json()
    result = closed["rounds"][0]["results"]
    assert result["counts"] == {a: 5, b: 8, c: 3, d: 5}
    assert result["winners"] == [b]
    assert result["ballots"][0]["ratings"] == ballot_body["ratings"]
    history = owner.post(url + "/reopen", json={"version": closed["version"]}).json()["rounds"]
    assert history[1]["results"] == result and history[0]["mode"] == "rating"
    assert not history[0]["my_ratings"]


def test_ranked_ballots_and_tie_round(owner, guest, trip):
    poll = create_poll(owner, trip, mode="ranked")
    a, b, c = [o["id"] for o in poll["rounds"][0]["options"]]
    assert ballot(guest, poll, 1, 0).status_code == 422
    assert ballot(guest, poll, 2, 0, 2).status_code == 422
    assert ballot(guest, poll, 0, 2, 1).is_success
    assert ballot(guest, poll, 1, 0, 2, ballot_version=1).json()["rounds"][0]["my_choices"] == [
        b,
        a,
        c,
    ]
    round_ = owner.get(f"/api/v1/trips/{trip['id']}/polls").json()[0]["rounds"][0]
    assert round_["my_choices"] == [] and "results" not in round_
    assert ballot(owner, poll, 0, 1, 2).is_success
    path = "/api/v1/polls/" + poll["id"]
    closed = owner.post(path + "/close", json={"version": 1}).json()
    result = closed["rounds"][0]["results"]
    assert result["counts"] == {a: 5, b: 5, c: 2}
    assert set(result["winners"]) == {a, b}
    assert result["ballots"][0]["option_ids"] == [b, a, c]
    new = owner.post(path + "/reopen", json={"version": closed["version"]}).json()
    assert len(new["rounds"][0]["options"]) == 2
    assert new["rounds"][1]["results"] == result


def test_structured_and_plain_mentions_on_create_edit(owner, guest, trip, monkeypatch):
    from app import decisions

    deliveries = []

    async def failing_push(ids):
        deliveries.extend(ids)
        raise RuntimeError("provider offline")

    monkeypatch.setattr(decisions, "deliver_mentions", failing_push)
    member = guest.get("/api/v1/auth/me").json()
    url = f"/api/v1/trips/{trip['id']}/comments"
    text = f"請 @[{member['nickname']}]({member['id']}) 看行程"
    first = owner.post(url, json={"content": text})
    assert first.is_success, first.text
    assert len(guest.get("/api/v1/notifications").json()["items"]) == 1
    edit = "/api/v1/comments/" + first.json()["id"]
    assert owner.patch(edit, json={"version": 1, "content": text + "，謝謝"}).is_success
    assert len(deliveries) == 1
    second = owner.post(url, json={"content": "再確認"}).json()
    assert owner.patch(
        "/api/v1/comments/" + second["id"],
        json={"version": 1, "content": "@" + member["nickname"] + " 請確認"},
    ).is_success
    assert len(guest.get("/api/v1/notifications").json()["items"]) == 2
