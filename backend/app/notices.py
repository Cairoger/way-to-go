import asyncio
import base64
import json
import logging
import os
import re
import time
from collections import Counter
from urllib.parse import urlsplit

import httpx
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, utils
from fastapi import APIRouter, Request
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from starlette.concurrency import run_in_threadpool

from .core import DB, Actor, check_version, digest, fail, make_session, public_origin
from .decisions_models import Comment
from .models import LoginSession, Membership, Trip, User, uid, utcnow
from .notice_models import Notice, NoticePreference, PushDevice
from .realtime import hub

router = APIRouter(tags=["通知"])
logger = logging.getLogger(__name__)
explicit = re.compile(r"@\[[^\]\n]{1,100}\]\(([0-9a-fA-F-]{36})\)")


def mentioned(text, members):
    allowed = {u.id for u in members}
    ids = set(explicit.findall(text)) & allowed
    plain = explicit.sub("", text)
    counts = Counter(u.nickname for u in members)
    for user in members:
        if counts[user.nickname] == 1 and re.search(
            r"(?<!\w)@" + re.escape(user.nickname) + r"(?!\w)", plain
        ):
            ids.add(user.id)
    return ids


def queue_mentions(db, comment, actor, previous_text=""):
    if "@" not in comment.content:
        return []
    members = db.scalars(
        select(User)
        .join(Membership, Membership.user_id == User.id)
        .where(Membership.trip_id == comment.trip_id, Membership.left_at.is_(None))
    ).all()
    ids = mentioned(comment.content, members) - mentioned(previous_text, members) - {actor.id}
    created = []
    for recipient in sorted(ids):
        pref = db.get(NoticePreference, recipient)
        if pref and not pref.mentions:
            continue
        prior = db.scalar(
            select(Notice).where(Notice.comment_id == comment.id, Notice.user_id == recipient)
        )
        if prior:
            continue
        row = Notice(
            id=uid(),
            user_id=recipient,
            trip_id=comment.trip_id,
            comment_id=comment.id,
            actor_id=actor.id,
        )
        db.add(row)
        created.append(row.id)
    return created


def b64(raw):
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def vapid():
    encoded = os.getenv("VAPID_PRIVATE_KEY", "")
    subject = os.getenv("VAPID_SUBJECT", "") or public_origin()
    if not encoded or not subject.startswith(("mailto:", "https://")):
        return None
    try:
        raw = base64.urlsafe_b64decode(encoded + "===")
        if len(raw) != 32:
            return None
        key = ec.derive_private_key(int.from_bytes(raw, "big"), ec.SECP256R1())
    except (ValueError, TypeError):
        return None
    public = b64(
        key.public_key().public_bytes(
            serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
        )
    )
    return key, public, subject


def allowed_endpoint(endpoint):
    try:
        url = urlsplit(endpoint)
        host = url.hostname or ""
        trusted = host in {
            "fcm.googleapis.com",
            "updates.push.services.mozilla.com",
            "web.push.apple.com",
        } or host.endswith((".push.apple.com", ".notify.windows.com", ".push.services.mozilla.com"))
        return (
            url.scheme == "https"
            and url.port in (None, 443)
            and not url.username
            and not url.password
            and not url.fragment
            and bool(url.path.strip("/"))
            and trusted
        )
    except ValueError:
        return False


def push_auth(endpoint, config):
    key, public, subject = config
    audience = "https://" + urlsplit(endpoint).netloc
    claims = {"aud": audience, "exp": int(time.time()) + 3600, "sub": subject}
    token = (
        b64(b'{"typ":"JWT","alg":"ES256"}')
        + "."
        + b64(json.dumps(claims, separators=(",", ":")).encode())
    )
    r, s = utils.decode_dss_signature(key.sign(token.encode(), ec.ECDSA(hashes.SHA256())))
    signature = b64(r.to_bytes(32, "big") + s.to_bytes(32, "big"))
    return "vapid t=" + token + "." + signature + ", k=" + public


def delivery_targets(ids):
    endpoints = {}
    users = set()
    with make_session() as db:
        for notice in db.scalars(select(Notice).where(Notice.id.in_(ids))):
            member = db.scalar(
                select(Membership.id).where(
                    Membership.trip_id == notice.trip_id,
                    Membership.user_id == notice.user_id,
                    Membership.left_at.is_(None),
                )
            )
            if not member:
                continue
            users.add((notice.trip_id, notice.user_id))
            pref = db.get(NoticePreference, notice.user_id)
            if not pref or not pref.push or not pref.mentions:
                continue
            for device in db.scalars(
                select(PushDevice)
                .join(LoginSession)
                .where(
                    LoginSession.user_id == notice.user_id,
                    LoginSession.revoked_at.is_(None),
                    LoginSession.expires_at > utcnow(),
                )
            ):
                endpoints[device.id] = device.endpoint
    return users, endpoints


def remove_expired_devices(ids):
    with make_session() as db:
        db.execute(delete(PushDevice).where(PushDevice.id.in_(ids)))
        db.commit()


async def deliver_mentions(ids):
    if not ids:
        return
    users, endpoints = await run_in_threadpool(delivery_targets, ids)
    for trip_id, user_id in users:
        await hub.publish_to(trip_id, user_id, {"type": "notifications.changed"})
    config = vapid()
    if not config or not endpoints:
        return
    expired = []
    async with httpx.AsyncClient(timeout=3, follow_redirects=False) as client:

        async def send(device, endpoint):
            if not allowed_endpoint(endpoint):
                return
            try:
                # Empty payload: the device only displays a generic prompt to open its authenticated inbox.
                response = await client.post(
                    endpoint,
                    content=b"",
                    headers={"TTL": "300", "Authorization": push_auth(endpoint, config)},
                )
                if response.status_code in (404, 410):
                    expired.append(device)
                elif response.status_code >= 400:
                    logger.info("Push provider returned HTTP %s", response.status_code)
            except httpx.HTTPError:
                logger.info("Push delivery unavailable")

        await asyncio.gather(*(send(device, endpoint) for device, endpoint in endpoints.items()))
    if expired:
        await run_in_threadpool(remove_expired_devices, expired)


def visible_notices(user_id):
    return (
        select(Notice, Trip.title, User.nickname)
        .join(Trip, Trip.id == Notice.trip_id)
        .join(User, User.id == Notice.actor_id)
        .join(Membership, (Membership.trip_id == Trip.id) & (Membership.user_id == Notice.user_id))
        .join(Comment, Comment.id == Notice.comment_id)
        .where(
            Notice.user_id == user_id,
            Membership.left_at.is_(None),
            Trip.deleted_at.is_(None),
            Comment.deleted.is_(False),
        )
    )


def preference(db, user_id):
    row = db.get(NoticePreference, user_id)
    config = vapid()
    return {
        "mentions": row.mentions if row else True,
        "push": row.push if row else False,
        "version": row.version if row else 0,
        "public_key": config[1] if config else None,
    }


@router.get("/notifications")
def inbox(request: Request, db: DB, user: Actor):
    return {
        "device_registered": db.scalar(
            select(PushDevice.id).where(PushDevice.session_id == request.state.session_id).limit(1)
        )
        is not None,
        "preferences": preference(db, user.id),
        "items": [
            {
                "id": n.id,
                "comment_id": n.comment_id,
                "trip_id": n.trip_id,
                "trip": title,
                "actor": name,
                "read": n.read_at is not None,
                "created_at": n.created_at,
            }
            for n, title, name in db.execute(
                visible_notices(user.id).order_by(Notice.created_at.desc())
            )
        ],
    }


class Preferences(BaseModel):
    mentions: bool
    push: bool
    version: int = Field(ge=0)


@router.put("/notifications/preferences")
def save_preferences(body: Preferences, db: DB, user: Actor):
    db.scalar(select(User.id).where(User.id == user.id).with_for_update())
    row = db.get(NoticePreference, user.id)
    if not row:
        row = NoticePreference(user_id=user.id, version=0)
        db.add(row)
    check_version(row, body.version)
    row.mentions, row.push = body.mentions, body.push
    row.version += 1
    db.commit()
    return preference(db, user.id)


@router.post("/notifications/{notice_id}/read", status_code=204)
def mark_read(notice_id: str, db: DB, user: Actor):
    result = db.execute(visible_notices(user.id).where(Notice.id == notice_id)).first()
    if not result:
        fail(404, "NOTICE_MISSING", "找不到這則通知。")
    result[0].read_at = result[0].read_at or utcnow()
    db.commit()


class DeviceInput(BaseModel):
    endpoint: str = Field(min_length=1, max_length=4096)


@router.put("/notifications/device", status_code=204)
def subscribe(body: DeviceInput, request: Request, db: DB, user: Actor):
    if not vapid():
        fail(503, "PUSH_DISABLED", "此部署尚未設定瀏覽器推播。")
    if not allowed_endpoint(body.endpoint):
        fail(422, "INVALID_PUSH_ENDPOINT", "此瀏覽器推播端點未受支援。")
    session_id = request.state.session_id
    db.scalar(select(User.id).where(User.id == user.id).with_for_update())
    key = digest(body.endpoint)
    row = db.scalar(select(PushDevice).where(PushDevice.endpoint_hash == key).with_for_update())
    if row:
        current_owner = db.scalar(
            select(LoginSession.user_id).where(
                LoginSession.id == row.session_id,
                LoginSession.revoked_at.is_(None),
                LoginSession.expires_at > utcnow(),
            )
        )
        if current_owner and current_owner != user.id:
            fail(409, "DEVICE_IN_USE", "請重新建立這台裝置的瀏覽器推播訂閱。")
        row.session_id = session_id
    else:
        db.add(PushDevice(session_id=session_id, endpoint_hash=key, endpoint=body.endpoint))
    db.execute(
        delete(PushDevice).where(
            PushDevice.session_id == session_id, PushDevice.endpoint_hash != key
        )
    )
    db.commit()


@router.delete("/notifications/device", status_code=204)
def unsubscribe(request: Request, db: DB, user: Actor):
    db.execute(delete(PushDevice).where(PushDevice.session_id == request.state.session_id))
    db.commit()
