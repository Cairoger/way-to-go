import base64
import hashlib
import hmac
import os
import secrets
from datetime import timedelta
from urllib.parse import urlencode

import requests
from fastapi import APIRouter, Request, Response
from fastapi.responses import RedirectResponse
from google.auth.exceptions import GoogleAuthError
from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2.id_token import verify_oauth2_token
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from .core import COOKIE, DB, Actor, digest, fail, local_test_config, public_origin, valid_session
from .models import AuthIdentity, LoginSession, Membership, OAuthAttempt, User, as_utc, utcnow
from .realtime import hub

router = APIRouter(tags=["身分驗證"])
OAUTH_COOKIE = "wtg_oauth"
OAUTH_PATH = "/api/v1/auth/google/callback"
SESSION_DAYS = 30


def public_user(user: User):
    return {
        "id": user.id,
        "nickname": user.nickname,
        "version": user.version,
        "account_type": user.account_type,
        "email": user.email,
    }


def issue_session(db: Session, response: Response, user: User, previous=None):
    if previous:
        previous.revoked_at = utcnow()
    raw = secrets.token_urlsafe(32)
    db.add(
        LoginSession(
            user_id=user.id,
            token_hash=digest(raw),
            expires_at=utcnow() + timedelta(days=SESSION_DAYS),
        )
    )
    response.set_cookie(
        COOKIE,
        raw,
        httponly=True,
        secure=public_origin().startswith("https:"),
        samesite="lax",
        path="/",
        max_age=SESSION_DAYS * 86400,
    )


@router.get("/auth/me")
def me(user: Actor):
    return public_user(user)


class ProfileEdit(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    nickname: str = Field(min_length=1, max_length=80)
    version: int = Field(ge=1)


@router.patch("/auth/me")
async def update_profile(payload: ProfileEdit, db: DB, user: Actor):
    updated = db.scalar(
        update(User)
        .where(User.id == user.id, User.version == payload.version)
        .values(nickname=payload.nickname, version=User.version + 1)
        .returning(User)
        .execution_options(populate_existing=True)
    )
    if updated is None:
        fail(409, "VERSION_CONFLICT", "暱稱已在其他分頁更新。請重新讀取最新暱稱後再儲存。")
    trips = list(
        db.scalars(
            select(Membership.trip_id).where(
                Membership.user_id == user.id, Membership.left_at.is_(None)
            )
        )
    )
    db.commit()
    for trip_id in trips:
        await hub.publish(trip_id, {"type": "members"})
    return public_user(updated)


class LocalCredentials(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=1024, repr=False)


@router.get("/auth/local-test")
def local_login_status():
    return {"enabled": local_test_config() is not None}


def local_test_user(db: Session, username: str) -> User:
    query = (
        select(User)
        .join(AuthIdentity)
        .where(
            AuthIdentity.provider == "local_test",
            AuthIdentity.provider_subject == username,
            User.account_type == "local_test",
        )
    )
    user = db.scalar(query)
    if user:
        return user
    user = User(account_type="local_test", nickname=username)
    try:
        db.add(user)
        db.flush()
        db.add(AuthIdentity(user_id=user.id, provider="local_test", provider_subject=username))
        db.flush()
    except IntegrityError:
        # Another first login may have created the same provider subject while we waited.
        db.rollback()
        winner = db.scalar(query)
        if not winner:
            raise
        return winner
    return user


@router.post("/auth/local-test")
def local_login(payload: LocalCredentials, request: Request, response: Response, db: DB):
    config = local_test_config()
    if config is None:
        fail(404, "LOCAL_TEST_DISABLED", "此部署未啟用本機測試帳號。")
    username, salt, expected_hash = config
    submitted_hash = hashlib.pbkdf2_hmac("sha256", payload.password.encode(), salt, 600000)
    username_ok = hmac.compare_digest(payload.username.encode(), username.encode())
    password_ok = hmac.compare_digest(submitted_hash, expected_hash)
    if not username_ok or not password_ok:
        fail(401, "INVALID_LOCAL_CREDENTIALS", "帳號或密碼錯誤。")
    user = local_test_user(db, username)
    previous = valid_session(db, request.cookies.get(COOKIE))
    issue_session(db, response, user, previous)
    db.commit()
    if previous:
        hub.revalidate(previous.id)
    return public_user(user)


@router.post("/auth/logout", status_code=204)
async def logout(request: Request, response: Response, db: DB):
    login = valid_session(db, request.cookies.get(COOKIE))
    if login:
        login.revoked_at = utcnow()
        db.commit()
        hub.revalidate(login.id)
    response.delete_cookie(
        COOKIE,
        path="/",
        httponly=True,
        secure=public_origin().startswith("https:"),
        samesite="lax",
    )


class LoginOptions(BaseModel):
    return_to: str = Field(default="/", max_length=512)


def flow_binding(request: Request, binding: str):
    # A delayed callback may only upgrade the browser identity that began the flow.
    return digest(binding + ":" + request.cookies.get(COOKIE, ""))


def credentials():
    client_id = os.getenv("GOOGLE_CLIENT_ID")
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
    if not client_id or not client_secret:
        fail(
            503,
            "OIDC_NOT_CONFIGURED",
            "此部署尚未設定 Google 登入，請管理員設定 GOOGLE_CLIENT_ID 與 GOOGLE_CLIENT_SECRET。",
        )
    return client_id, client_secret


@router.post("/auth/google")
def start_google(request: Request, response: Response, db: DB, options: LoginOptions | None = None):
    client_id, _ = credentials()
    return_to = options.return_to if options else "/"
    if (
        not return_to.startswith("/")
        or return_to.startswith("//")
        or any(c in return_to for c in ("\\", "\r", "\n", "\t"))
    ):
        fail(422, "INVALID_RETURN_PATH", "登入後的返回位置必須位於本站。")
    state, binding, verifier, nonce = (secrets.token_urlsafe(32) for _ in range(4))
    db.execute(delete(OAuthAttempt).where(OAuthAttempt.expires_at <= utcnow()))
    db.add(
        OAuthAttempt(
            state_hash=digest(state),
            binding_hash=flow_binding(request, binding),
            verifier=verifier,
            nonce=nonce,
            return_to=return_to,
            expires_at=utcnow() + timedelta(minutes=10),
        )
    )
    db.commit()
    response.set_cookie(
        OAUTH_COOKIE,
        binding,
        max_age=600,
        path=OAUTH_PATH,
        httponly=True,
        secure=public_origin().startswith("https:"),
        samesite="lax",
    )
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("ascii")).digest())
        .rstrip(b"=")
        .decode()
    )
    params = {
        "client_id": client_id,
        "redirect_uri": public_origin() + OAUTH_PATH,
        "response_type": "code",
        "scope": "openid email profile",
        "nonce": nonce,
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    return {"url": "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(params)}


def exchange_code(code: str, verifier: str, client_id: str, client_secret: str):
    try:
        result = requests.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": client_id,
                "client_secret": client_secret,
                "code_verifier": verifier,
                "redirect_uri": public_origin() + OAUTH_PATH,
                "grant_type": "authorization_code",
            },
            timeout=10,
        )
        result.raise_for_status()
        id_token = result.json()["id_token"]
        transport = GoogleRequest()
        return verify_oauth2_token(
            id_token,
            lambda *args, **kwargs: transport(*args, **kwargs, timeout=10),
            client_id,
        )
    except (requests.RequestException, ValueError, KeyError, GoogleAuthError):
        fail(401, "OIDC_EXCHANGE_FAILED", "Google 登入驗證失敗，請重新登入。")


@router.get("/auth/google/callback")
async def google_callback(request: Request, db: DB, state: str = "", code: str = ""):
    client_id, client_secret = credentials()
    attempt = db.scalar(
        select(OAuthAttempt).where(OAuthAttempt.state_hash == digest(state)).with_for_update()
    )
    binding = request.cookies.get(OAUTH_COOKIE, "")
    if (
        not attempt
        or not code
        or as_utc(attempt.expires_at) <= utcnow()
        or not hmac.compare_digest(flow_binding(request, binding), attempt.binding_hash)
    ):
        fail(401, "INVALID_OIDC_STATE", "登入連結已失效，請重新開始 Google 登入。")
    nonce, verifier, return_to = attempt.nonce, attempt.verifier, attempt.return_to
    db.delete(attempt)
    db.commit()
    claims = await run_in_threadpool(exchange_code, code, verifier, client_id, client_secret)
    if not claims.get("sub") or not hmac.compare_digest(claims.get("nonce", ""), nonce):
        fail(401, "INVALID_OIDC_NONCE", "Google 身分驗證結果不符合此次登入。")
    identity = db.scalar(
        select(AuthIdentity).where(
            AuthIdentity.provider == "google",
            AuthIdentity.provider_subject == claims["sub"],
        )
    )
    previous = valid_session(db, request.cookies.get(COOKIE))
    existing = (
        db.scalar(select(User).where(User.id == previous.user_id).with_for_update())
        if previous
        else None
    )
    if previous and not valid_session(db, request.cookies.get(COOKIE)):
        fail(401, "SESSION_REQUIRED", "原本的瀏覽器身分已失效，請重新登入。")
    email = claims.get("email") if claims.get("email_verified") is True else None
    merged_trips = []
    if identity:
        user = db.get(User, identity.user_id)
        if existing and existing.account_type == "guest" and existing.id != identity.user_id:
            from .merge import merge_guest

            merged_trips = merge_guest(db, existing, user)
    else:
        if existing and existing.account_type == "guest":
            db.execute(
                update(LoginSession)
                .where(LoginSession.user_id == existing.id, LoginSession.revoked_at.is_(None))
                .values(revoked_at=utcnow())
            )
        user = (
            existing
            if existing and existing.account_type == "guest"
            else User(account_type="google", nickname="旅人")
        )
        user.account_type = "google"
        user.email = email
        if user != existing:
            user.nickname = str(claims.get("name") or "旅人")[:80]
        db.add(user)
        db.flush()
        db.add(AuthIdentity(user_id=user.id, provider="google", provider_subject=claims["sub"]))
    response = RedirectResponse(public_origin() + return_to, status_code=303)
    response.delete_cookie(
        OAUTH_COOKIE,
        path=OAUTH_PATH,
        httponly=True,
        secure=public_origin().startswith("https:"),
        samesite="lax",
    )
    issue_session(db, response, user, previous)
    db.commit()
    if previous:
        hub.revalidate(previous.id)
    for trip_id in merged_trips:
        await hub.publish(trip_id, {"type": "members"})
    return response
