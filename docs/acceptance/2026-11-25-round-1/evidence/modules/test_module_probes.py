"""Run from backend with backend/tests in PYTHONPATH and pytest -p conftest."""
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

from sqlalchemy import select

from app.core import make_session
from app.models import AuditLog
from test_decisions import ballot, create_poll
from test_finance import expense


def test_four_kind_mode_combinations_and_options(owner, guest, trip):
    for kind in ("date", "place"):
        for mode in ("single", "multiple"):
            labels = ["2027-01-01", "2027-01-02"] if kind == "date" else ["公園", "海邊"]
            poll = create_poll(guest, trip, kind=kind, mode=mode, options=[{"text": x} for x in labels])
            assert ballot(owner, poll, *([0] if mode == "single" else [0, 1])).is_success
            option = "2027-01-03" if kind == "date" else "車站"
            changed = owner.post("/api/v1/polls/" + poll["id"] + "/options", json={"text": option, "version": 1})
            assert changed.is_success and changed.json()["rounds"][0]["options"][-1]["text"] == option
            print(kind, mode, "member-created; owner-voted; cross-author option", changed.status_code)
    owner_poll=create_poll(owner,trip)
    member_option=guest.post("/api/v1/polls/"+owner_poll["id"]+"/options",json={"version":1,"text":"市集"})
    assert member_option.is_success and member_option.json()["rounds"][0]["options"][-1]["text"]=="市集"
    print("member added option on owner-created poll",member_option.status_code)


def test_poll_creator_lifecycle_and_no_deadline(owner, guest, trip, monkeypatch):
    from app import decisions
    poll = create_poll(guest, trip)
    url = "/api/v1/polls/" + poll["id"]
    listing = f"/api/v1/trips/{trip['id']}/polls"
    edit = guest.patch(url, json={"title": "新標題", "mode": "multiple", "version": 1})
    assert edit.is_success and edit.json()["rounds"][0]["title"] == "新標題"
    moment = datetime.now(UTC) + timedelta(days=60)
    monkeypatch.setattr(decisions, "utcnow", lambda: moment)
    view = owner.get(listing).json()[0]
    assert view["rounds"][0]["deadline"] is None and not view["rounds"][0]["closed"]
    closed = guest.post(url + "/close", json={"version": edit.json()["version"]})
    deleted = guest.request("DELETE", url, json={"version": closed.json()["version"]})
    assert deleted.is_success and not owner.get(listing).json()
    print("edit, close, delete", edit.status_code, closed.status_code, deleted.status_code, "open after 60 simulated days")


def test_availability_is_independent(owner, guest, trip):
    url = f"/api/v1/trips/{trip['id']}"
    assert owner.post(url + "/availability", json={"start_date":"2027-05-09","status":"yes"}).is_success
    assert not guest.get(url + "/polls").json()
    poll = create_poll(guest, trip, kind="date", options=[{"text":"2027-05-01"},{"text":"2027-05-02"}])
    assert ballot(owner, poll, 0).is_success
    assert [(e["start_date"],e["status"]) for e in guest.get(url+"/availability").json()["entries"]] == [("2027-05-09","yes")]


def test_task_all_fields_links_and_repeat(owner, guest, trip):
    base = f"/api/v1/trips/{trip['id']}"
    place = owner.post(base + "/places", json={"name":"車站"}).json()
    me = guest.get("/api/v1/auth/me").json()["id"]
    data = {"title":"提早報到","description":"需在十點前抵達","assignees":[me],"due_date":"2027-06-01","priority":"high","place_id":place["id"]}
    saved = owner.post(base + "/tasks", json=data)
    assert saved.status_code == 201
    row = guest.get(base + "/tasks").json()[0]
    assert all(row[k] == v for k,v in data.items() if k != "assignees")
    assert row["assignees"][0]["user_id"] == me and row["state"] == "todo"
    repeat = owner.post(base+"/tasks", json=data | {"recurrence":"weekly"})
    attach = owner.post(base+"/tasks", json=data | {"attachment_ids":[]})
    print("recurrence, attachment fields", repeat.status_code, attach.status_code)
    assert repeat.status_code == attach.status_code == 422


def test_booking_complete_fields_and_links(owner, guest, trip):
    base = f"/api/v1/trips/{trip['id']}"
    url = base + "/bookings"
    me = guest.get("/api/v1/auth/me").json()["id"]
    day = owner.get(base + "/days").json()[0]["id"]
    item = guest.post(f"/api/v1/days/{day}/items", json={"title":"會合"}).json()["id"]
    leg={"airline":"旅伴航空","number":"WT101","origin":"TPE","destination":"NRT","departure":"2027-05-01T08:00:00+08:00","arrival":"2027-05-01T13:00:00+09:00","departure_terminal":"T1","arrival_terminal":"T2","passengers":[{"user_id":me,"seat":"1A","baggage":"20 kg"}]}
    basics={"title":"抵達","kind":"flight","currency":"JPY","price":"1300","item_id":item,"reference":"TEST-ONLY","website":"https://example.org/flight","segments":[leg]}
    flight=owner.post(url,json=basics)
    assert flight.status_code == 201
    returned=guest.get(url).json()[0]
    assert returned["segments"] == [leg] and Decimal(returned["price"])==1300
    assert returned["item_id"]==item and returned["reference"]=="TEST-ONLY"
    update = owner.put(url+"/"+returned["id"],json=basics|{"version":1,"status":"booked","website":"https://example.org/updated"})
    assert update.is_success and update.json()["website"].endswith("/updated")
    for i in [1,2]:
        stay={"check_in":"2027-06-01","check_out":"2027-06-02","room":"雙人房","guests":[me],"address":"測試路"}
        created=owner.post(url,json={"kind":"stay","title":f"旅館{i}","status":"booked","stay":stay,"price":"500","currency":"TWD","item_id":item})
        assert created.status_code==201
    stays=[b for b in guest.get(url).json() if b["kind"]=="stay"]
    assert len(stays)==2 and all(b["stay"]==stay and Decimal(b["price"])==500 and b["status"]=="booked" and b["item_id"]==item for b in stays)
    print("flight attributes persisted, two stays linked to itinerary; website changed", update.status_code)


def test_split_multiple_payers_and_subset(owner, guest, trip):
    root=f"/api/v1/trips/{trip['id']}"
    a,b=[c.get("/api/v1/auth/me").json()["id"] for c in (owner,guest)]
    saved=owner.post(root+"/expenses",json=expense(a,b,splits={b:"100"}))
    assert saved.status_code==201
    row=guest.get(root+"/finance").json()["expenses"][0]
    assert set(row["payers"])=={a,b} and set(row["splits"])=={b}
    print("persisted payers", len(row["payers"]), "participants", len(row["splits"]))


def test_file_contract_and_comment_images(owner, trip):
    base=f"/api/v1/trips/{trip['id']}"
    contract=owner.get("/openapi.json").json()
    declared=[p for p in contract["paths"] if any(s in p for s in ("file","attachment","upload"))]
    assert not declared
    print("OpenAPI file/attachment/upload paths", declared)
    for form in ("/files", base+"/files"):
        api="/api/v1"+form if form=="/files" else form
        upload=owner.post(api,files={"file":("readme.txt",BytesIO(b"demo"),"text/plain")})
        listing=owner.get(api)
        print("file HTTP", form.replace(trip["id"],"{id}"), "multipart POST",upload.status_code,"GET",listing.status_code)
        assert upload.status_code==listing.status_code==404
    word=BytesIO()
    with ZipFile(word,"w") as z:
        z.writestr("[Content_Types].xml",'<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>')
        z.writestr("_rels/.rels",'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>')
        z.writestr("word/document.xml",'<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p/></w:body></w:document>')
    pdf=BytesIO()
    pdf.write(b"%PDF-1.4\n")
    offsets=[]
    for obj,value in enumerate([b"<< /Type /Catalog /Pages 2 0 R >>",b"<< /Type /Pages /Count 1 /Kids [3 0 R] >>",b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 10 10] /Resources << >> >>"],1):
        offsets.append(pdf.tell())
        pdf.write(f"{obj} 0 obj\n".encode()+value+b"\nendobj\n")
    start=pdf.tell()
    pdf.write(b"xref\n0 4\n0000000000 65535 f \n")
    for offset in offsets:
        pdf.write(f"{offset:010d} 00000 n \n".encode())
    pdf.write(f"trailer\n<< /Size 4 /Root 1 0 R >>\nstartxref\n{start}\n%%EOF".encode())
    png=Path(__file__).resolve().parents[3]/"frontend"/"public"/"icon-192.png"
    for name,mime,content in [("sample.png","image/png",png.read_bytes()),("sample.pdf","application/pdf",pdf.getvalue()),("sample.docx","application/vnd.openxmlformats-officedocument.wordprocessingml.document",word.getvalue())]:
        sample=owner.post(base+"/files",files={"file":(name,content,mime)})
        print("synthetic upload",name,sample.status_code)
        assert sample.status_code==404
    comment=owner.post(base+"/comments",json={"content":"照片","attachments":[{"name":"demo.png"}]})
    received=owner.get(base+"/comments").json()[0]
    print("comment with attachment metadata",comment.status_code,"stored fields",sorted(received))
    assert comment.status_code==201 and "attachments" not in received
    docs=owner.get("/openapi.json").json()["components"]["schemas"]
    for name in ("TaskInput","BookingInput","NewComment"):
        print(name,sorted(docs[name]["properties"]))


def test_audit_origins(owner,guest,trip):
    base=f"/api/v1/trips/{trip['id']}"
    a,b=[c.get("/api/v1/auth/me").json()["id"] for c in (owner,guest)]
    comment=guest.post(base+"/comments",json={"content":"新增集合點"}).json()
    task=owner.post(base+"/tasks",json={"title":"蒐集提案"}).json()
    with make_session() as db:
        rows=db.scalars(select(AuditLog).where(AuditLog.trip_id==trip["id"])).all()
        assert any(r.entity_id==comment["id"] and r.actor_id==b for r in rows)
        assert any(r.entity_id==task["id"] and r.actor_id==a for r in rows)
        print("audit rows (no identity values)",[(r.entity_type,r.action) for r in rows])
