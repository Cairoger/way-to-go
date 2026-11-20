import time
from collections import deque
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from starlette.exceptions import HTTPException

from . import auth, decisions, planning, realtime, trips
from .core import get_engine, public_origin


@asynccontextmanager
async def lifespan(app):
    public_origin()
    with get_engine().connect() as connection:
        connection.execute(text("SELECT 1"))
    yield


app = FastAPI(title="WayToGo 旅程協作 API", version="1.0", lifespan=lifespan)
for module in (auth, trips, planning, decisions):
    app.include_router(module.router, prefix="/api/v1")
app.include_router(realtime.router)


def problem(request: Request, status: int, code: str, message: str):
    return JSONResponse(
        {"code": code, "message": message, "request_id": request.state.request_id},
        status_code=status,
    )


@app.exception_handler(HTTPException)
async def http_error(request: Request, exc: HTTPException):
    detail = exc.detail
    if isinstance(detail, dict):
        return problem(
            request,
            exc.status_code,
            detail.get("code", "HTTP_ERROR"),
            detail.get("message", "無法完成操作。"),
        )
    return problem(request, exc.status_code, "HTTP_ERROR", str(detail))


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError):
    first = exc.errors()[0]
    field = ".".join(str(key) for key in first["loc"] if key not in ("body", "query", "path"))
    issue = first["msg"].removeprefix("Value error, ")
    if not any("\u4e00" <= char <= "\u9fff" for char in issue):
        issue = "請檢查此欄位的格式、長度或必填內容。"
    return problem(request, 422, "INVALID_INPUT", (f"欄位 {field}：" if field else "") + issue)


@app.exception_handler(IntegrityError)
async def integrity_error(request: Request, exc: IntegrityError):
    return problem(request, 409, "DATA_CONFLICT", "這筆資料已變更或重複，請重新載入後再試。")


# Single API process per deployment. Keys expire so inactive clients take no permanent space.
attempts: dict[tuple[str, str], deque[float]] = {}
last_sweep = 0.0


def rate_limited(request: Request):
    path = request.url.path
    if path.endswith("/place-search"):
        category, limit = "search", 30
    elif path == "/api/v1/auth/local-test" and request.method == "POST":
        category, limit = "local-login", 15
    elif path.startswith("/api/v1/auth/google"):
        category, limit = "oidc", 30
    elif (
        path.endswith(("/auth/guest", "/invitations/accept", "/invitations"))
        and request.method == "POST"
    ):
        category, limit = "invite", 45
    else:
        return False
    now = time.monotonic()
    global last_sweep
    if now - last_sweep > 60:
        for key in list(attempts):
            if not attempts[key] or attempts[key][-1] < now - 60:
                del attempts[key]
        last_sweep = now
    key = (request.client.host if request.client else "local", category)
    bucket = attempts.setdefault(key, deque())
    while bucket and bucket[0] <= now - 60:
        bucket.popleft()
    if len(bucket) >= limit:
        return True
    bucket.append(now)
    return False


@app.middleware("http")
async def security(request: Request, call_next):
    request.state.request_id = str(uuid4())
    origin = request.headers.get("origin")
    if request.method not in {"GET", "HEAD", "OPTIONS"} and (
        (origin and origin != public_origin())
        or (not origin and request.headers.get("x-requested-with") != "WayToGo")
    ):
        response = problem(request, 403, "ORIGIN_DENIED", "請由本站畫面執行此操作。")
    elif rate_limited(request):
        response = problem(request, 429, "RATE_LIMITED", "操作過於頻繁，請稍後再試。")
        response.headers["Retry-After"] = "60"
    else:
        response = await call_next(request)
    response.headers["X-Request-ID"] = request.state.request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/health", include_in_schema=False)
def health():
    with get_engine().connect() as connection:
        connection.execute(text("SELECT 1"))
    return {"status": "ok"}
