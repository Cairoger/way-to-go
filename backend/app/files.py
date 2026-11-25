import os
from typing import Literal
from urllib.parse import quote

from fastapi import APIRouter, Request
from fastapi.responses import PlainTextResponse, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import delete, func, select
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import UploadFile

from .core import DB, Actor, audit, check_version, current_user, fail, require_member
from .file_access import allowed, check_target, file_card, links_for
from .file_formats import inspect_file
from .file_models import FileLink, FilePermission, TripFile
from .models import Membership, utcnow
from .realtime import hub

router = APIRouter(tags=["文件與附件"])
LinkKind = Literal["trip", "item", "task", "expense", "booking", "comment"]


class Version(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: int = Field(ge=1)


class FileEdit(Version):
    category: str = Field(min_length=1, max_length=64)
    private: bool = False
    reader_ids: list[str] = Field(default_factory=list, max_length=200)


def quotas():
    return int(os.getenv("FILE_MAX_BYTES", str(10 * 1024**2))), int(
        os.getenv("TRIP_FILE_QUOTA_BYTES", str(500 * 1024**2))
    )


def readers(db, trip_id, ids):
    if ids:
        known = set(
            db.scalars(
                select(Membership.user_id).where(
                    Membership.trip_id == trip_id,
                    Membership.left_at.is_(None),
                    Membership.user_id.in_(ids),
                )
            )
        )
        if set(ids) != known:
            fail(422, "INVALID_READERS", "請選擇此旅程的有效成員。")
    return set(ids)


def member_file(db, file_id, user_id, *, write=False, removed=False):
    trip_id = db.scalar(select(TripFile.trip_id).where(TripFile.id == file_id))
    if not trip_id:
        fail(404, "FILE_MISSING", "找不到附件。")
    require_member(db, trip_id, user_id, lock=write)
    row = db.get(TripFile, file_id, populate_existing=True)
    if not row or (row.removed_at and not removed):
        fail(404, "FILE_MISSING", "找不到附件。")
    if not allowed(db, row, user_id) or (write and row.owner_id != user_id):
        fail(403, "FILE_FORBIDDEN", "你沒有這份附件的存取權。")
    return row


@router.get("/trips/{trip_id}/files")
def list_files(
    trip_id: str,
    db: DB,
    user: Actor,
    kind: LinkKind | None = None,
    target_id: str | None = None,
    recycled: bool = False,
):
    require_member(db, trip_id, user.id)
    q = select(TripFile).where(TripFile.trip_id == trip_id)
    if kind:
        check_target(db, trip_id, kind, target_id or trip_id, user.id)
        q = q.join(FileLink).where(
            FileLink.kind == kind, FileLink.target_id == (target_id or trip_id)
        )
    q = (
        q.where(TripFile.removed_at.is_not(None), TripFile.owner_id == user.id)
        if recycled
        else q.where(TripFile.removed_at.is_(None))
    )
    result = []
    for row in db.scalars(q.order_by(TripFile.created_at.desc(), TripFile.id)):
        links = links_for(db, row.id)
        if allowed(db, row, user.id, links):
            result.append(file_card(db, row, user.id, links))
    return result


@router.get("/trips/{trip_id}/files/limits")
def file_limits(trip_id: str, db: DB, user: Actor):
    require_member(db, trip_id, user.id)
    per_file, total = quotas()
    return {"file_max_bytes": per_file, "trip_max_bytes": total, "batch_max": 10}


async def parse_upload(request, limit):
    max_request = 10 * limit + 128 * 1024
    received = 0

    async def bounded():
        nonlocal received
        message = await request.receive()
        received += len(message.get("body", b""))
        if received > max_request:
            fail(413, "UPLOAD_TOO_LARGE", "批次上傳超過容量限制。")
        return message

    wrapped = Request(request.scope, receive=bounded)
    async with wrapped.form(max_files=10, max_fields=215, max_part_size=8192) as form:
        uploaded = form.getlist("files") + form.getlist("file")
        if not 1 <= len(uploaded) <= 10 or not all(isinstance(f, UploadFile) for f in uploaded):
            fail(422, "MISSING_UPLOAD", "每次請選擇一至十個檔案。")
        category = str(form.get("category", "其他")).strip()
        if not 1 <= len(category) <= 64:
            fail(422, "INVALID_CATEGORY", "分類長度請介於 1 到 64 字。")
        private = form.get("private", "false")
        if private not in {"true", "false"}:
            fail(422, "INVALID_PRIVACY", "請設定附件可見範圍。")
        batch = []
        for f in uploaded:
            if f.size and f.size > limit:
                fail(413, "FILE_TOO_LARGE", "單一附件超過上限。")
            data = await f.read(limit + 1)
            if not data or len(data) > limit:
                fail(413, "FILE_SIZE", "檔案為空或超過單檔上限。")
            mime, text = await run_in_threadpool(inspect_file, f.filename, data, f.content_type)
            batch.append((f.filename, mime, text, data))
        return (
            batch,
            category,
            private == "true",
            form.getlist("reader_ids"),
            form.get("kind", "trip"),
            form.get("target_id"),
        )


@router.post(
    "/trips/{trip_id}/files",
    status_code=201,
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "multipart/form-data": {
                    "schema": {
                        "type": "object",
                        "required": ["files"],
                        "properties": {
                            "files": {
                                "type": "array",
                                "items": {"type": "string", "format": "binary"},
                            },
                            "category": {"type": "string"},
                            "private": {"type": "boolean"},
                            "reader_ids": {"type": "array", "items": {"type": "string"}},
                            "kind": {"type": "string"},
                            "target_id": {"type": "string"},
                        },
                    }
                }
            },
        }
    },
)
async def upload(trip_id: str, request: Request, db: DB, user: Actor):
    require_member(db, trip_id, user.id)
    db.rollback()
    per_file, total = quotas()
    batch, category, private, ids, kind, target = await parse_upload(request, per_file)
    # SQLite has no row-level FOR UPDATE. Reserve the writer before measuring the quota.
    if db.get_bind().dialect.name == "sqlite":
        db.connection().exec_driver_sql("BEGIN IMMEDIATE")
    actor = current_user(request, db)
    require_member(db, trip_id, actor.id, lock=True)
    check_target(db, trip_id, kind, target or trip_id, actor.id, writing=True)
    ids = readers(db, trip_id, ids) if private else set()
    used = db.scalar(
        select(func.coalesce(func.sum(TripFile.size), 0)).where(TripFile.trip_id == trip_id)
    )
    if used + sum(len(data) for _, _, _, data in batch) > total:
        fail(413, "TRIP_FILE_QUOTA", "旅程附件已達總容量上限，回收中的檔案仍占空間。")
    rows = []
    for name, mime, text, data in batch:
        if kind in {"comment", "draft"} and (private or not mime.startswith("image/")):
            fail(422, "INVALID_COMMENT_IMAGE", "留言僅接受共用的圖片。")
        row = TripFile(
            trip_id=trip_id,
            owner_id=actor.id,
            category=category,
            private=private,
            filename=name,
            mime=mime,
            preview_text=text,
            data=data,
            size=len(data),
        )
        db.add(row)
        db.flush()
        db.add(FileLink(file_id=row.id, kind=kind, target_id=target or trip_id))
        db.add_all(FilePermission(file_id=row.id, user_id=i) for i in ids - {actor.id})
        audit(db, trip_id, actor.id, "file", row.id, "file.uploaded")
        rows.append(row)
    db.flush()
    result = [file_card(db, row, actor.id) for row in rows]
    db.commit()
    await hub.publish(trip_id, {"type": "files.changed"})
    return result


@router.get("/files/{file_id}/download")
def download(file_id: str, db: DB, user: Actor):
    row = member_file(db, file_id, user.id)
    return Response(
        row.data,
        media_type=row.mime,
        headers={
            "Content-Disposition": "attachment; filename*=UTF-8''" + quote(row.filename, safe=""),
            "Content-Security-Policy": "default-src 'none'; sandbox",
        },
    )


@router.get("/files/{file_id}/preview")
def preview(file_id: str, db: DB, user: Actor):
    row = member_file(db, file_id, user.id)
    headers = {"Content-Security-Policy": "default-src 'none'; sandbox"}
    if row.mime.startswith("image/"):
        return Response(row.data, media_type=row.mime, headers=headers)
    return PlainTextResponse(row.preview_text, headers=headers)


async def finish(db, row, user_id, event):
    row.version += 1
    audit(db, row.trip_id, user_id, "file", row.id, event)
    result = file_card(db, row, user_id)
    trip_id = row.trip_id
    db.commit()
    await hub.publish(trip_id, {"type": "files.changed"})
    return result


@router.patch("/files/{file_id}")
async def edit_file(file_id: str, body: FileEdit, db: DB, user: Actor):
    row = member_file(db, file_id, user.id, write=True)
    check_version(row, body.version)
    if body.private and any(x.kind == "comment" for x in links_for(db, row.id)):
        fail(422, "COMMENT_VISIBILITY", "已在留言公開的圖片不能改為私人。")
    authorized = readers(db, row.trip_id, body.reader_ids) if body.private else set()
    db.execute(delete(FilePermission).where(FilePermission.file_id == row.id))
    db.add_all(FilePermission(file_id=row.id, user_id=i) for i in authorized - {user.id})
    row.category, row.private = body.category, body.private
    return await finish(db, row, user.id, "file.updated")


@router.delete("/files/{file_id}")
async def remove_file(file_id: str, body: Version, db: DB, user: Actor):
    row = member_file(db, file_id, user.id, write=True)
    check_version(row, body.version)
    row.removed_at = utcnow()
    return await finish(db, row, user.id, "file.recycled")


@router.post("/files/{file_id}/restore")
async def restore_file(file_id: str, body: Version, db: DB, user: Actor):
    row = member_file(db, file_id, user.id, write=True, removed=True)
    check_version(row, body.version)
    if not row.removed_at:
        fail(409, "FILE_ACTIVE", "附件已在文件清單中。")
    row.removed_at = None
    return await finish(db, row, user.id, "file.restored")
