def test_single_dates_ranges_overlap_and_active_members(owner, guest, trip):
    path = f"/api/v1/trips/{trip['id']}/availability"
    owner_mark = {"start_date": "2027-02-01", "end_date": "2027-02-05", "status": "yes"}
    mark = owner.post(path, json=owner_mark, headers={"Idempotency-Key": "owner-mark"})
    assert mark.status_code == 201, mark.text
    assert (
        owner.post(path, json=owner_mark, headers={"Idempotency-Key": "owner-mark"}).json()
        == mark.json()
    )
    assert owner.post(path, json=owner_mark | {"start_date": "2027-02-05"}).status_code == 409
    assert owner.post(path, json=owner_mark | {"start_date": "2027-03-01"}).status_code == 422
    assert guest.post(path, json={"start_date": "2027-02-02", "status": "maybe"}).is_success
    second = guest.post(
        path, json={"start_date": "2027-02-03", "end_date": "2027-02-04", "status": "yes"}
    ).json()
    assert guest.post(path, json={"start_date": "2027-02-05", "status": "no"}).is_success
    rows = guest.get(path).json()["recommendations"]
    assert rows[0] == {
        "start_date": "2027-02-03",
        "end_date": "2027-02-04",
        "yes": 2,
        "maybe": 0,
        "no": 0,
        "unknown": 0,
    }
    assert rows[1]["maybe"] == 1
    assert rows[2]["unknown"] == 1
    assert rows[3]["no"] == 1
    edit_url = path + "/" + second["id"]
    body = {"start_date": "2027-02-03", "end_date": "2027-02-04", "status": "maybe", "version": 1}
    assert owner.patch(edit_url, json=body).status_code == 403
    assert guest.patch(edit_url, json=body).json()["version"] == 2
    assert guest.patch(edit_url, json=body).status_code == 409
    assert guest.delete(edit_url, params={"version": 1}).status_code == 409
    assert guest.delete(edit_url, params={"version": 2}).status_code == 204
    assert guest.delete(f"/api/v1/trips/{trip['id']}/members/{second['user_id']}").is_success
    assert guest.get(path).status_code == 403
    snapshot = owner.get(path).json()
    assert snapshot["member_count"] == 1 and len(snapshot["entries"]) == 1
    assert snapshot["recommendations"][0]["end_date"] == "2027-02-05"


def test_apply_dates_preserves_scheduled_items_and_versions(owner, guest, trip):
    path = f"/api/v1/trips/{trip['id']}"
    saved = owner.patch(path, json={"version": trip["version"], "day_count": 3}).json()
    days = guest.get(path + "/days").json()
    item = guest.post(
        f"/api/v1/days/{days[2]['id']}/items", json={"title": "車站集合", "item_type": "custom"}
    ).json()
    proposed = {"start_date": "2027-02-12", "end_date": "2027-02-13", "version": saved["version"]}
    assert guest.patch(path, json=proposed).status_code == 403
    saved = owner.patch(path, json=proposed).json()
    assert owner.patch(path, json=proposed).status_code == 409
    before = guest.get(path + "/days").json()
    assert before[0]["date"] == proposed["start_date"]
    proposed.update(start_date="2027-02-10", end_date="2027-02-10", version=saved["version"])
    assert owner.patch(path, json=proposed).is_success
    after = guest.get(path + "/days").json()
    assert [d["id"] for d in after] == [d["id"] for d in days]
    assert after[2]["date"] == "2027-02-12"
    assert after[2]["items"][0]["id"] == item["id"]
    assert after[2]["items"][0]["editable_by"] == item["editable_by"]


def test_adjacent_intervals_merge_only_for_same_members(owner, guest, trip):
    path = f"/api/v1/trips/{trip['id']}/availability"
    for day in ["2027-07-01", "2027-07-02"]:
        assert owner.post(path, json={"start_date": day, "status": "yes"}).is_success
    assert guest.post(path, json={"start_date": "2027-07-03", "status": "yes"}).is_success
    rec = guest.get(path).json()["recommendations"]
    assert [(r["start_date"], r["end_date"]) for r in rec] == [
        ("2027-07-01", "2027-07-02"),
        ("2027-07-03", "2027-07-03"),
    ]
