import sqlite3
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from uuid import uuid4
from zipfile import ZipFile

import pytest
from conftest import browser
from PIL import Image
from pypdf import PdfWriter

from app.core import get_engine
from app.file_formats import OFFICE


def png():
    buf = BytesIO()
    Image.new("RGB", (4, 3), "#16774c").save(buf, format="PNG")
    return buf.getvalue()


def pdf():
    buf = BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    writer.write(buf)
    return buf.getvalue()


def office(ext):
    main, subtype = OFFICE[ext]
    mime = "application/vnd.openxmlformats-officedocument." + subtype
    buf = BytesIO()
    with ZipFile(buf, "w") as archive:
        archive.writestr(
            "[Content_Types].xml",
            f'<Types><Override PartName="/{main}" ContentType="{mime}.main+xml"/></Types>',
        )
        archive.writestr(main, "<document><t>Fixture text</t></document>")
    return "sample" + ext, buf.getvalue(), mime


def post_files(actor, url, *, parts=None, **fields):
    files = [("files", f) for f in (parts or [("photo.png", png(), "image/png")])]
    return actor.post(url, files=files, data=fields)


def create_file(actor, base, **fields):
    response = post_files(actor, base + "/files", **fields)
    assert response.status_code == 201, response.text
    return response.json()[0]


def test_batch_types_previews_and_all_or_nothing(owner, guest, trip):
    url = "/api/v1/trips/" + trip["id"] + "/files"
    parts = [
        ("photo.png", png(), "image/png"),
        ("plan.pdf", pdf(), "application/pdf"),
        *[office(ext) for ext in OFFICE],
    ]
    rows = post_files(owner, url, parts=parts, category="憑證")
    assert rows.status_code == 201, rows.text
    for row, (filename, data, mime) in zip(rows.json(), parts, strict=True):
        assert row["filename"] == filename and row["category"] == "憑證"
        base = "/api/v1/files/" + row["id"]
        download = guest.get(base + "/download")
        assert download.content == data and download.headers["content-type"] == mime
        assert download.headers["content-disposition"].startswith("attachment;")
        preview = guest.get(base + "/preview")
        assert "sandbox" in preview.headers["content-security-policy"]
        if mime.startswith("image"):
            assert preview.content == data
        else:
            assert preview.headers["content-type"].startswith("text/plain")
            assert ("PDF" if mime == "application/pdf" else "Fixture text") in preview.text
    for bad in [
        ("bad.jpg", png(), "image/jpeg"),
        ("bad.png", png(), "application/pdf"),
        ("bad.html", b"text", "text/html"),
        ("bad.docx", b"unreadable", "application/octet-stream"),
    ]:
        assert post_files(owner, url, parts=[parts[0], bad]).status_code == 415
    assert len(guest.get(url).json()) == len(parts)


def test_attachment_permissions_revocation_copy_and_restore(owner, guest, client, trip, invitation):
    base = "/api/v1/trips/" + trip["id"]
    guest_id = guest.get("/api/v1/auth/me").json()["id"]
    private = create_file(owner, base, private="true", reader_ids=guest_id)
    resource = "/api/v1/files/" + private["id"]
    assert guest.get(resource + "/download").content == png()
    with browser() as other:
        assert other.post(
            "/api/v1/auth/guest", json={"code": invitation["code"], "nickname": "另一位"}
        ).is_success
        assert other.get(base + "/files").json() == []
        assert other.get(resource + "/preview").status_code == 403
        assert other.get(resource + "/download").status_code == 403
        assert other.request("DELETE", resource, json={"version": 1}).status_code == 403
    assert client.get(resource + "/download").status_code == 401
    assert guest.patch(resource, json={"version": 1, "category": "x"}).status_code == 403
    settings = {"version": 1, "category": "收據", "private": True, "reader_ids": []}
    assert owner.patch(resource, json=settings).is_success
    assert owner.patch(resource, json=settings).status_code == 409
    assert guest.get(resource + "/download").status_code == 403
    assert owner.request("DELETE", resource, json={"version": 2}).is_success
    assert owner.get(resource + "/download").status_code == 404
    assert owner.get(base + "/files?recycled=true").json()[0]["id"] == private["id"]
    assert guest.get(base + "/files?recycled=true").json() == []
    assert owner.post(resource + "/restore", json={"version": 3}).is_success
    assert owner.get(resource + "/download").content == png()
    copied = owner.post(base + "/copy", json={})
    assert copied.status_code == 201, copied.text
    assert owner.get("/api/v1/trips/" + copied.json()["id"] + "/files").json() == []
    assert owner.patch(
        resource, json=settings | {"version": 4, "reader_ids": [guest_id]}
    ).is_success
    assert guest.get(resource + "/preview").is_success
    assert guest.delete(base + "/members/" + guest_id).is_success
    assert guest.get(resource + "/preview").status_code == 403


def test_file_quota_counts_recycle_and_rate_limit(owner, trip, monkeypatch):
    base = "/api/v1/trips/" + trip["id"]
    url = base + "/files"
    assert owner.get(url + "/limits").json() == {
        "file_max_bytes": 10485760,
        "trip_max_bytes": 524288000,
        "batch_max": 10,
    }
    size = len(png())
    monkeypatch.setenv("FILE_MAX_BYTES", str(size - 1))
    assert post_files(owner, url).status_code == 413
    monkeypatch.setenv("FILE_MAX_BYTES", str(size))
    monkeypatch.setenv("TRIP_FILE_QUOTA_BYTES", str(size))
    row = create_file(owner, base)
    assert post_files(owner, url).status_code == 413
    assert owner.request("DELETE", "/api/v1/files/" + row["id"], json={"version": 1}).is_success
    assert post_files(owner, url).status_code == 413
    for _ in range(26):
        assert post_files(owner, url).status_code == 413
    assert post_files(owner, url).status_code == 429


def test_concurrent_uploads_respect_last_available_space(owner, guest, trip, monkeypatch):
    url = "/api/v1/trips/" + trip["id"] + "/files"
    monkeypatch.setenv("TRIP_FILE_QUOTA_BYTES", str(len(png())))
    with ThreadPoolExecutor(max_workers=2) as pool:
        pending = [pool.submit(post_files, actor, url) for actor in (owner, guest)]
        assert sorted(call.result().status_code for call in pending) == [201, 413]
    assert len(owner.get(url).json()) == 1


def test_bound_targets_and_private_booking(owner, guest, trip):
    base = "/api/v1/trips/" + trip["id"]
    a, b = [actor.get("/api/v1/auth/me").json()["id"] for actor in [owner, guest]]
    day = owner.get(base + "/days").json()[0]["id"]
    item = owner.post(
        "/api/v1/days/" + day + "/items", json={"title": "行程", "item_type": "custom"}
    ).json()["id"]
    expense = owner.post(
        base + "/expenses",
        json={
            "title": "午餐",
            "category": "餐飲",
            "incurred_on": "2027-01-01",
            "kind": "actual",
            "currency": "TWD",
            "amount": "80",
            "split_mode": "custom",
            "payers": {a: "80"},
            "splits": {b: "80"},
        },
    ).json()["id"]
    private_task = guest.post(
        base + "/tasks", json={"title": "個人證件", "scope": "personal"}
    ).json()["id"]
    booking = owner.post(
        base + "/bookings",
        json={
            "kind": "stay",
            "title": "私人訂位",
            "stay": {"check_in": "2027-01-01", "check_out": "2027-01-02", "guests": []},
        },
    ).json()["id"]
    for kind, target, creator, viewer, visible in [
        ("item", item, guest, owner, True),
        ("expense", expense, owner, guest, True),
        ("task", private_task, guest, owner, False),
        ("booking", booking, owner, guest, False),
    ]:
        f = create_file(creator, base, kind=kind, target_id=target)
        query = f"/files?kind={kind}&target_id={target}"
        assert creator.get(base + query).json()[0]["id"] == f["id"]
        assert viewer.get("/api/v1/files/" + f["id"] + "/download").status_code == (
            200 if visible else 403
        )
        assert viewer.get(base + query).status_code == (200 if visible else 403)
    assert post_files(guest, base + "/files", kind="booking", target_id=booking).status_code == 403


def test_comment_images_draft_visibility_and_rejections(owner, guest, trip):
    base = "/api/v1/trips/" + trip["id"]
    actor = owner.get("/api/v1/auth/me").json()["id"]
    img = create_file(owner, base, kind="draft", target_id=actor)
    assert guest.get(base + "/files").json() == []
    doc = create_file(owner, base, parts=[("sample.pdf", pdf(), "application/pdf")])
    private = create_file(owner, base, private="true")
    payload = {"content": "留言測試"}
    for bad in [str(uuid4()), doc["id"], private["id"]]:
        assert (
            owner.post(base + "/comments", json=payload | {"attachment_ids": [bad]}).status_code
            == 422
        )
    assert (
        owner.post(base + "/comments", json=payload | {"attachments": [img["id"]]}).status_code
        == 422
    )
    assert (
        guest.post(base + "/comments", json=payload | {"attachment_ids": [img["id"]]}).status_code
        == 403
    )
    assert guest.get(base + "/comments").json() == []
    saved = owner.post(base + "/comments", json=payload | {"attachment_ids": [img["id"]]})
    assert saved.status_code == 201, saved.text
    assert guest.get(base + "/comments").json()[0]["attachments"] == [
        {"id": img["id"], "filename": "photo.png", "mime": "image/png"}
    ]
    assert guest.get("/api/v1/files/" + img["id"] + "/preview").content == png()
    assert owner.patch(
        "/api/v1/comments/" + saved.json()["id"],
        json=payload | {"version": 1, "attachment_ids": []},
    ).is_success
    assert guest.get("/api/v1/files/" + img["id"] + "/preview").status_code == 403


@pytest.mark.parametrize(
    "recurrence,dates",
    [
        ("monthly", ["2027-02-28", "2027-03-31"]),
        ("daily", ["2027-02-01", "2027-02-02"]),
        ("weekly", ["2027-02-07", "2027-02-14"]),
    ],
)
def test_repeat_two_periods_with_persistent_files(owner, guest, trip, recurrence, dates):
    base = "/api/v1/trips/" + trip["id"]
    people = [actor.get("/api/v1/auth/me").json()["id"] for actor in (owner, guest)]
    file = create_file(owner, base, private="true")
    task = {
        "title": "定期確認",
        "recurrence": recurrence,
        "assignees": people,
        "attachment_ids": [file["id"]],
    }
    assert owner.post(base + "/tasks", json=task).status_code == 422
    result = owner.post(base + "/tasks", json=task | {"due_date": "2027-01-31"})
    assert result.status_code == 201, result.text
    row = result.json()
    progress = base + "/tasks/" + row["id"] + "/progress"
    for period, due in enumerate(dates, 1):
        first = owner.put(progress, json={"state": "done", "version": row["version"]}).json()
        assert first["period"] == period and first["state"] == "doing"
        payload = {"state": "done", "version": first["version"]}
        assert guest.put(progress, json=payload).is_success
        assert guest.put(progress, json=payload).status_code == 409
        row = owner.get(base + "/tasks").json()[0]
        assert row["state"] == "todo" and row["period"] == period + 1 and row["due_date"] == due
        assert row["attachment_ids"] == [file["id"]] and row["recurrence"] == recurrence
        observed = guest.get(base + "/tasks").json()[0]
        assert observed["attachment_ids"] == []
        assert len(observed["completed_periods"]) == period
        assert {
            p["user_id"]
            for p in observed["completed_periods"][-1]["progress"]
            if p["state"] == "done"
        } == set(people)


def test_sqlite_file_backup_preserves_content_reader_and_links(owner, guest, trip, tmp_path):
    engine = get_engine()
    if engine.dialect.name != "sqlite":
        pytest.skip("此測試使用 SQLite 的備份 API。")
    guest_id = guest.get("/api/v1/auth/me").json()["id"]
    row = create_file(owner, "/api/v1/trips/" + trip["id"], private="true", reader_ids=guest_id)
    path = tmp_path / "restored.sqlite"
    with sqlite3.connect(engine.url.database) as source, sqlite3.connect(path) as dest:
        source.backup(dest)
    with sqlite3.connect(path) as restored:
        assert (
            restored.execute("SELECT data FROM files WHERE id=?", (row["id"],)).fetchone()[0]
            == png()
        )
        assert restored.execute(
            "SELECT kind,target_id FROM file_links WHERE file_id=?", (row["id"],)
        ).fetchone() == ("trip", trip["id"])
        assert restored.execute(
            "SELECT user_id FROM file_permissions WHERE file_id=?", (row["id"],)
        ).fetchone() == (guest_id,)
