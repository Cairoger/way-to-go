import os
import secrets
from datetime import timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.schema import CreateSchema, DropSchema

from app.core import COOKIE, digest, get_engine, make_session, public_origin
from app.main import app, attempts
from app.models import Base, LoginSession, User, utcnow
from app.realtime import hub


@pytest.fixture(autouse=True)
def database(tmp_path, monkeypatch):
    """Use a fresh SQLite file, or a private per-test schema on a CI PostgreSQL database."""
    pg_url = os.getenv("TEST_DATABASE_URL")
    admin_engine = None
    schema = "wtg_test_" + uuid4().hex
    if pg_url:
        source = make_url(pg_url)
        if source.get_backend_name() != "postgresql":
            pytest.fail("TEST_DATABASE_URL must refer to a PostgreSQL test database")
        source = source.set(drivername="postgresql+psycopg")
        admin_engine = create_engine(source)
        with admin_engine.begin() as conn:
            conn.execute(CreateSchema(schema))
        url = source.update_query_dict({"options": "-csearch_path=" + schema}).render_as_string(
            hide_password=False
        )
    else:
        url = "sqlite:///" + (tmp_path / "waytogo.sqlite").as_posix()
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("PUBLIC_ORIGIN", "http://testserver")
    get_engine.cache_clear()
    public_origin.cache_clear()
    attempts.clear()
    try:
        Base.metadata.create_all(get_engine())
        yield
    finally:
        hub.connections.clear()
        get_engine().dispose()
        get_engine.cache_clear()
        public_origin.cache_clear()
        if admin_engine:
            with admin_engine.begin() as conn:
                conn.execute(DropSchema(schema, cascade=True))
            admin_engine.dispose()


def browser():
    return TestClient(app, headers={"Origin": "http://testserver"}, follow_redirects=False)


@pytest.fixture
def client(database):
    with browser() as test_client:
        yield test_client


@pytest.fixture
def owner(database):
    raw = secrets.token_urlsafe(32)
    with make_session() as db:
        account = User(account_type="google", nickname="旅程發起者")
        db.add(account)
        db.flush()
        db.add(
            LoginSession(
                user_id=account.id, token_hash=digest(raw), expires_at=utcnow() + timedelta(days=1)
            )
        )
        db.commit()
    with browser() as test_client:
        test_client.cookies.set(COOKIE, raw, domain="testserver.local", path="/")
        yield test_client


@pytest.fixture
def trip(owner):
    response = owner.post("/api/v1/trips", json={"title": "台南散步"})
    assert response.status_code == 201, response.text
    return response.json()


@pytest.fixture
def invitation(owner, trip):
    response = owner.post(f"/api/v1/trips/{trip['id']}/invitations", json={})
    assert response.status_code == 201, response.text
    return response.json()


@pytest.fixture
def guest(invitation):
    with browser() as test_client:
        response = test_client.post(
            "/api/v1/auth/guest", json={"code": invitation["code"], "nickname": "同行旅伴"}
        )
        assert response.status_code == 200, response.text
        yield test_client
