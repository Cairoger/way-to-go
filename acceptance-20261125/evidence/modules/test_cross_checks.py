"""Additional scope checks with the existing per-test temporary database fixture."""
from datetime import datetime
from zoneinfo import ZoneInfo
from test_decisions import ballot, create_poll


def test_closing_poll_preserves_existing_items_until_manual_adoption(owner,guest,trip):
    base=f"/api/v1/trips/{trip['id']}"
    day=owner.get(base+"/days").json()[0]["id"]
    original=guest.post(f"/api/v1/days/{day}/items",json={"title":"旅伴原先的安排"}).json()
    poll=create_poll(owner,trip)
    assert ballot(guest,poll,0).is_success
    pollurl="/api/v1/polls/"+poll["id"]
    closed=owner.post(pollurl+"/close",json={"version":poll["version"]}).json()
    listing=lambda:guest.get(base+"/days").json()[0]["items"]
    assert [i["id"] for i in listing()]==[original["id"]]
    candidate=closed["rounds"][0]["results"]["winners"][0]
    added=owner.post(pollurl+"/adopt",json={"day_id":day,"option_id":candidate,"version":closed["version"]})
    assert added.is_success
    assert [(v["id"],v["title"],v["version"]) for v in listing() if v["id"]==original["id"]]==[(original["id"],original["title"],original["version"])]
    assert len(listing())==2 and original["id"]!=added.json()["item_id"]
    reopened=owner.post(pollurl+"/reopen",json={"version":closed["version"]}).json()
    edited=owner.patch(pollurl,json={"version":reopened["version"],"title":"下一輪","mode":"multiple"})
    assert edited.is_success and edited.json()["rounds"][1]["results"]==closed["rounds"][0]["results"]
    print("before manual adoption: original row only; after: two distinct IDs; after reopen: prior result preserved, new round mode editable")


def test_iana_dst_gap_round_trip(owner,trip):
    base=f"/api/v1/trips/{trip['id']}"
    assert owner.patch(base,json={"start_date":"2027-03-14","version":trip["version"]}).is_success
    day=owner.get(base+"/days").json()[0]["id"]
    zone="America/New_York"
    response=owner.post(f"/api/v1/days/{day}/items",json={"title":"春季調鐘","timezone":zone,"start_time":"02:30"})
    if response.status_code==422:
        print("nonexistent local wall time rejected");return
    assert response.status_code==201
    item=owner.get(base+"/days").json()[0]["items"][0]
    roundtrip=datetime.fromisoformat(item["start_instant"]).astimezone(ZoneInfo(zone)).strftime("%H:%M")
    print("POST",response.status_code,"persisted",item["start_time"],"instant",item["start_instant"],"IANA local time at that instant",roundtrip)
    assert item["start_time"]==roundtrip,"saved local time and absolute instant describe different clock times"
