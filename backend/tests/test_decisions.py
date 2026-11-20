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
