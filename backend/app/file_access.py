from collections import defaultdict

from sqlalchemy import delete, select

from .core import fail
from .decisions_models import Comment
from .file_models import FileLink, FilePermission, TripFile
from .finance_models import Expense
from .planning_models import ItineraryItem
from .preparation_models import Booking, Task

MODELS = {
    "item": ItineraryItem,
    "task": Task,
    "expense": Expense,
    "booking": Booking,
    "comment": Comment,
}


def target_access(db, trip_id, kind, target_id, user_id, *, writing=False, owns_file=False):
    if kind == "draft":
        return target_id == user_id
    if kind == "trip":
        return target_id == trip_id
    model = MODELS.get(kind)
    row = db.get(model, target_id) if model and target_id else None
    if not row:
        return owns_file and model is not None
    if row.trip_id != trip_id:
        return False
    if kind == "item":
        return row.deleted_at is None or owns_file
    if kind == "task":
        return row.scope == "shared" or row.created_by == user_id
    if kind == "comment":
        return owns_file if row.deleted else not writing or row.author_id == user_id
    if kind == "booking":
        related = {p["user_id"] for leg in row.segments for p in leg["passengers"]}
        return (
            user_id == row.created_by
            or user_id in related
            or user_id in (row.stay or {}).get("guests", [])
        )
    return True


def check_target(db, trip_id, kind, target_id, user_id, *, writing=False):
    if not target_access(db, trip_id, kind, target_id, user_id, writing=writing):
        fail(403, "FILE_TARGET_DENIED", "你沒有這個附件關聯項目的權限。")


def links_for(db, file_id):
    return db.scalars(select(FileLink).where(FileLink.file_id == file_id)).all()


def grants_for(db, file_id):
    return list(db.scalars(select(FilePermission.user_id).where(FilePermission.file_id == file_id)))


def allowed(db, row, user_id, links=None):
    if row.private and user_id != row.owner_id and user_id not in grants_for(db, row.id):
        return False
    # Every link is an additional visibility constraint, including direct downloads via UUID.
    links = links if links is not None else links_for(db, row.id)
    if not links:
        return user_id == row.owner_id
    for link in links:
        if not target_access(
            db, row.trip_id, link.kind, link.target_id, user_id, owns_file=row.owner_id == user_id
        ):
            return False
    return True


def file_card(db, row, user_id, links=None):
    links = links_for(db, row.id) if links is None else links
    return {
        "id": row.id,
        "filename": row.filename,
        "size": row.size,
        "mime": row.mime,
        "category": row.category,
        "owner_id": row.owner_id,
        "editable": row.owner_id == user_id,
        "private": row.private,
        "reader_ids": grants_for(db, row.id) if row.owner_id == user_id else [],
        "version": row.version,
        "removed": bool(row.removed_at),
        "created_at": row.created_at,
        "links": [{"kind": x.kind, "target_id": x.target_id} for x in links],
    }


def bound_files(db, trip_id, kind, user_id, target_ids=None):
    stmt = (
        select(TripFile, FileLink.target_id)
        .join(FileLink, FileLink.file_id == TripFile.id)
        .where(TripFile.trip_id == trip_id, FileLink.kind == kind, TripFile.removed_at.is_(None))
    )
    if target_ids is not None:
        stmt = stmt.where(FileLink.target_id.in_(target_ids))
    result = defaultdict(list)
    for row, target in db.execute(stmt.order_by(TripFile.created_at, TripFile.id)):
        if allowed(db, row, user_id):
            result[target].append({"id": row.id, "filename": row.filename, "mime": row.mime})
    return result


def bind_files(db, trip_id, kind, target_id, ids, user_id):
    if len(ids) != len(set(ids)):
        fail(422, "INVALID_FILE_IDS", "附件不可重複。")
    existing = set(
        db.scalars(
            select(FileLink.file_id)
            .join(TripFile, TripFile.id == FileLink.file_id)
            .where(
                TripFile.trip_id == trip_id, FileLink.kind == kind, FileLink.target_id == target_id
            )
        )
    )
    for file_id in ids:
        row = db.get(TripFile, file_id)
        if not row or row.trip_id != trip_id or row.removed_at:
            fail(422, "INVALID_FILE_IDS", "附件不存在、已移除或不屬於這趟旅程。")
        if file_id not in existing:
            if row.owner_id != user_id or not allowed(db, row, user_id):
                fail(403, "FILE_LINK_DENIED", "只能關聯自己的可讀附件。")
            if kind == "comment" and (
                not row.mime.startswith("image/")
                or row.private
                or any(
                    link.kind not in {"comment", "trip", "draft"} for link in links_for(db, row.id)
                )
            ):
                fail(422, "INVALID_COMMENT_IMAGE", "留言僅能使用旅程共用圖片。")
            if kind == "comment":
                db.execute(
                    delete(FileLink).where(FileLink.file_id == row.id, FileLink.kind == "draft")
                )
            db.add(FileLink(file_id=file_id, kind=kind, target_id=target_id))
    # A task editor cannot remove another uploader's links, including links invisible to that editor.
    for file_id in existing - set(ids):
        row = db.get(TripFile, file_id)
        if row.owner_id == user_id:
            db.execute(
                delete(FileLink).where(
                    FileLink.file_id == file_id,
                    FileLink.kind == kind,
                    FileLink.target_id == target_id,
                )
            )
