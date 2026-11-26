import hashlib
import os
import re
from datetime import timedelta
from functools import lru_cache
from typing import Annotated, NoReturn
from urllib.parse import urlparse

from fastapi import Depends, HTTPException, Request
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session, sessionmaker

from .models import AuditLog, AuthIdentity, LoginSession, Membership, Trip, User, utcnow

COOKIE = "wtg_session"


def local_test_config() -> tuple[str, bytes, bytes] | None:
    origin = urlparse(public_origin())
    if origin.scheme != "http" or origin.hostname not in {"localhost", "127.0.0.1", "::1"}:
        return None
    username = os.getenv("LOCAL_TEST_USERNAME", "")
    if not username.strip() or len(username) > 80:
        return None
    encoded = os.getenv("LOCAL_TEST_PASSWORD_HASH", "")
    match = re.fullmatch(
        r"pbkdf2_sha256\$600000\$((?:[a-fA-F0-9]{2}){1,128})\$([a-fA-F0-9]{64})", encoded
    )
    if not match:
        return None
    return username, bytes.fromhex(match[1]), bytes.fromhex(match[2])


@lru_cache
def public_origin() -> str:
    value = os.getenv("PUBLIC_ORIGIN", "").rstrip("/")
    origin = urlparse(value)
    if (
        not origin.hostname
        or origin.username
        or origin.password
        or origin.path
        or origin.query
        or origin.fragment
    ):
        raise RuntimeError("PUBLIC_ORIGIN 必須是完整的公開網站來源，例如 http://localhost:3000")
    if origin.scheme != "https" and not (
        origin.scheme == "http"
        and origin.hostname in {"localhost", "127.0.0.1", "::1", "testserver"}
    ):
        raise RuntimeError("公開部署的 PUBLIC_ORIGIN 必須使用 HTTPS")
    return value


@lru_cache
def get_engine():
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("缺少 DATABASE_URL，請設定 PostgreSQL 的連線網址")
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    options = {"pool_pre_ping": True}
    if url.startswith("sqlite"):
        from sqlalchemy.pool import StaticPool

        options["connect_args"] = {"check_same_thread": False}
        if ":memory:" in url or url.endswith("://"):
            options["poolclass"] = StaticPool
    engine = create_engine(url, **options)
    if engine.dialect.name == "sqlite":

        @event.listens_for(engine, "connect")
        def sqlite_foreign_keys(connection, record):
            connection.execute("PRAGMA foreign_keys=ON")

    return engine


def make_session() -> Session:
    return sessionmaker(bind=get_engine(), expire_on_commit=False)()


def get_db():
    with make_session() as db:
        yield db


DB = Annotated[Session, Depends(get_db)]


def digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def fail(status: int, code: str, message: str) -> NoReturn:
    raise HTTPException(status, {"code": code, "message": message})


def valid_session(
    db: Session, token: str | None, *, trip_id: str | None = None
) -> LoginSession | None:
    if not token or len(token) > 256:
        return None
    query = (
        select(LoginSession, User.account_type)
        .join(User)
        .where(
            LoginSession.token_hash == digest(token),
            LoginSession.revoked_at.is_(None),
            LoginSession.expires_at > utcnow(),
        )
    )
    if trip_id is not None:
        query = (
            query.join(Membership, Membership.user_id == User.id)
            .join(Trip, Trip.id == Membership.trip_id)
            .where(
                Membership.trip_id == trip_id,
                Membership.left_at.is_(None),
                Trip.deleted_at.is_(None),
            )
        )
    result = db.execute(query).first()
    if not result:
        return None
    login, account_type = result
    if account_type == "local_test":
        config = local_test_config()
        if not config or not db.scalar(
            select(AuthIdentity.id).where(
                AuthIdentity.user_id == login.user_id,
                AuthIdentity.provider == "local_test",
                AuthIdentity.provider_subject == config[0],
            )
        ):
            return None
    return login


def current_user(request: Request, db: DB) -> User:
    login = valid_session(db, request.cookies.get(COOKIE))
    if not login:
        fail(401, "SESSION_REQUIRED", "登入階段已結束，請重新登入或使用邀請加入。")
    request.state.session_id = login.id
    return db.get(User, login.user_id)


Actor = Annotated[User, Depends(current_user)]


def begin_sqlite_write(db: Session) -> None:
    """Serialize read-then-write decisions where SQLite ignores SELECT FOR UPDATE."""
    if db.get_bind().dialect.name == "sqlite":
        db.connection().exec_driver_sql("BEGIN IMMEDIATE")


def trip_recovery_cutoff():
    return utcnow() - timedelta(days=30)


def require_member(
    db: Session, trip_id: str, user_id: str, *, lock=False, allow_deleted=False
) -> Trip:
    query = select(Trip).where(Trip.id == trip_id)
    if lock:
        query = query.with_for_update().execution_options(populate_existing=True)
    trip = db.scalar(query)
    membership = db.scalar(
        select(Membership.id).where(
            Membership.trip_id == trip_id,
            Membership.user_id == user_id,
            Membership.left_at.is_(None),
        )
    )
    if not trip or not membership:
        fail(403, "MEMBERSHIP_REQUIRED", "你沒有這個旅程的存取權限。")
    if trip.deleted_at:
        from .models import as_utc

        if (
            not allow_deleted
            or trip.owner_id != user_id
            or as_utc(trip.deleted_at) <= trip_recovery_cutoff()
        ):
            fail(404, "TRIP_REMOVED", "這個旅程已移至回收區或已到期。")
    return trip


def require_owner(
    db: Session, trip_id: str, user_id: str, *, lock=False, allow_deleted=False
) -> Trip:
    trip = require_member(db, trip_id, user_id, lock=lock, allow_deleted=allow_deleted)
    if trip.owner_id != user_id:
        fail(403, "OWNER_REQUIRED", "只有旅程擁有者可以執行這個操作。")
    return trip


def audit(
    db: Session,
    trip_id: str,
    actor_id: str,
    entity_type: str,
    entity_id: str,
    action: str,
    changes=None,
):
    db.add(
        AuditLog(
            trip_id=trip_id,
            actor_id=actor_id,
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            changes=changes or {},
        )
    )


def check_version(entity, version: int):
    if entity.version != version:
        fail(409, "VERSION_CONFLICT", "資料已由其他人更新，請重新載入後再修改。")
