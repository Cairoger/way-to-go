"""Run browser workflows against disposable API and web services.

Install backend dev and frontend dependencies, install Playwright Chromium (or set
CHROME_EXECUTABLE to an installed Chromium browser), then run this file with the
project's virtual environment. The default suites cover preparation and finance.
Give Playwright spec paths to select other suites. Set E2E_POSTGRES_TEST_URL to a
loopback test database for a fresh PostgreSQL schema instead of temporary SQLite.
"""

import argparse
import base64
import hashlib
import os
import secrets
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from contextlib import ExitStack, contextmanager
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.schema import CreateSchema, DropSchema

BACKEND = Path(__file__).resolve().parent
FRONTEND = BACKEND.parent / "frontend"


def port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@contextmanager
def isolated_database(root):
    target = os.getenv("E2E_POSTGRES_TEST_URL")
    if not target:
        yield "sqlite:///" + (root / "test.sqlite").as_posix()
        return
    url = make_url(target)
    if url.get_backend_name() != "postgresql" or url.host not in {"localhost", "127.0.0.1", "::1"}:
        raise ValueError("E2E_POSTGRES_TEST_URL must address a loopback PostgreSQL test server")
    url = url.set(drivername="postgresql+psycopg")
    engine = create_engine(url)
    schema = "wtg_browser_" + uuid4().hex
    try:
        with engine.begin() as conn:
            conn.execute(CreateSchema(schema))
        try:
            yield url.update_query_dict({"options": "-csearch_path=" + schema}).render_as_string(
                hide_password=False
            )
        finally:
            with engine.begin() as conn:
                conn.execute(DropSchema(schema, cascade=True))
    finally:
        engine.dispose()


def stage_frontend(stage):
    stage.mkdir()
    for name in ("app", "components", "lib", "public"):
        shutil.copytree(FRONTEND / name, stage / name)
    for name in (
        "package.json",
        "pnpm-lock.yaml",
        "next.config.mjs",
        "postcss.config.js",
        "tailwind.config.js",
        "tsconfig.json",
    ):
        shutil.copyfile(FRONTEND / name, stage / name)
    modules = FRONTEND / "node_modules"
    if not modules.is_dir():
        raise RuntimeError("請先在 frontend 安裝 pnpm 依賴。")
    if os.name == "nt":
        # Junctions do not require Windows developer mode or administrator privileges.
        env = os.environ | {
            "WTG_MODULE_LINK": str(stage / "node_modules"),
            "WTG_MODULE_TARGET": str(modules),
        }
        subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-Command",
                "New-Item -ItemType Junction -Path $env:WTG_MODULE_LINK -Target $env:WTG_MODULE_TARGET | Out-Null",
            ],
            env=env,
            check=True,
        )
    else:
        (stage / "node_modules").symlink_to(modules, target_is_directory=True)


def stop(process):
    if process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            stdout=subprocess.DEVNULL,
            check=False,
        )
    else:
        os.killpg(process.pid, signal.SIGTERM)
    process.wait(timeout=15)


def server(stack, args, cwd, env, log, health):
    output = stack.enter_context(log.open("w", encoding="utf-8"))
    process = subprocess.Popen(
        args,
        cwd=cwd,
        env=env,
        stdout=output,
        stderr=subprocess.STDOUT,
        start_new_session=os.name != "nt",
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    stack.callback(stop, process)
    for _ in range(120):
        if process.poll() is not None:
            break
        try:
            with urllib.request.urlopen(health, timeout=3) as response:
                if response.status == 200:
                    return
        except urllib.error.HTTPError as err:
            if err.code >= 500:
                break
        except (urllib.error.URLError, TimeoutError):
            pass
        time.sleep(0.25)
    raise RuntimeError(
        "測試服務啟動失敗：\n" + log.read_text(encoding="utf-8", errors="replace")[-4500:]
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--browser", choices=["chromium", "firefox", "webkit"], default="chromium")
    parser.add_argument(
        "--production", action="store_true", help="Build and serve the production PWA"
    )
    parser.add_argument(
        "--push", action="store_true", help="Supply a temporary VAPID key to the local push probe"
    )
    parser.add_argument("tests", nargs="*", help="Playwright test file names or patterns")
    args = parser.parse_args()
    node = shutil.which("node")
    if not node:
        raise RuntimeError("找不到 Node.js。")
    # Webpack resolves entry points relative to this directory, which must share the
    # node_modules drive on Windows. Each run owns and removes its isolated directory.
    with (
        tempfile.TemporaryDirectory(prefix=".waytogo-acceptance-", dir=FRONTEND.parent) as tmp,
        ExitStack() as stack,
    ):
        root = Path(tmp)
        web = root / "web"
        stage_frontend(web)
        api_port, web_port = port(), port()
        while api_port == web_port:
            web_port = port()
        origin = f"http://127.0.0.1:{web_port}"
        upstream = f"http://127.0.0.1:{api_port}"
        login = "e2e-traveler"
        password = secrets.token_urlsafe(24)
        salt = secrets.token_bytes(16)
        digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 600000).hex()
        env = os.environ | {
            "DATABASE_URL": stack.enter_context(isolated_database(root)),
            "PUBLIC_ORIGIN": origin,
            "LOCAL_TEST_USERNAME": login,
            "INVITATION_SIGNING_KEY": secrets.token_hex(32),
            "LOCAL_TEST_PASSWORD_HASH": f"pbkdf2_sha256$600000${salt.hex()}${digest}",
            "WIKI_API_URL": "",
            "OPEN_METEO_URL": "",
            "GOOGLE_CLIENT_ID": "",
            "GOOGLE_CLIENT_SECRET": "",
            "VAPID_PRIVATE_KEY": "",
            "VAPID_SUBJECT": "",
        }
        if args.push:
            from cryptography.hazmat.primitives.asymmetric import ec

            key = (
                ec.generate_private_key(ec.SECP256R1())
                .private_numbers()
                .private_value.to_bytes(32, "big")
            )
            env["VAPID_PRIVATE_KEY"] = base64.urlsafe_b64encode(key).decode().rstrip("=")
            env["VAPID_SUBJECT"] = "mailto:qa@example.test"
        subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"], cwd=BACKEND, env=env, check=True
        )
        # Run the existing seeder against this run's database, keeping its private URL off stdout.
        seeded_url = subprocess.check_output(
            [
                sys.executable,
                "-c",
                "from seed_demo import seed_demo; print(seed_demo(hours=1)['url'])",
            ],
            cwd=BACKEND,
            env=env,
            encoding="utf-8",
        ).strip()
        invite = parse_qs(urlsplit(seeded_url).query)["invite"][0]
        server(
            stack,
            [
                sys.executable,
                "-m",
                "uvicorn",
                "app.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(api_port),
            ],
            BACKEND,
            env,
            root / "api.log",
            upstream + "/api/v1/auth/local-test",
        )
        web_env = os.environ | {"API_UPSTREAM": upstream, "NEXT_TELEMETRY_DISABLED": "1"}
        next_cli = [node, str(FRONTEND / "node_modules/next/dist/bin/next")]
        if args.production:
            subprocess.run([*next_cli, "build", "--webpack"], cwd=web, env=web_env, check=True)
        server(
            stack,
            [
                *next_cli,
                *(["start"] if args.production else ["dev", "--webpack"]),
                "--hostname",
                "127.0.0.1",
                "--port",
                str(web_port),
            ],
            web,
            web_env,
            root / "web.log",
            origin + "/",
        )
        result = subprocess.run(
            [
                node,
                str(FRONTEND / "node_modules/@playwright/test/cli.js"),
                "test",
                *(args.tests or ["tests/live-preparations.spec.ts", "tests/live-finance.spec.ts"]),
                "--browser=" + args.browser,
                "--reporter=line",
                "--trace=off",
                "--output=" + str(root / "results"),
            ],
            cwd=FRONTEND,
            env=os.environ
            | {
                "E2E_ORIGIN": origin,
                "E2E_INVITE": invite,
                "E2E_PYTHON": os.environ.get("E2E_PYTHON") or sys.executable,
                "E2E_LOCAL_USERNAME": login,
                "E2E_LOCAL_PASSWORD": password,
                "E2E_DISPOSABLE": "1",
                "E2E_BROWSER": args.browser,
                "E2E_PUSH_PROBE": "1" if args.push else "0",
            },
            check=False,
        )
        if result.returncode:
            for report in (root / "results").rglob("error-context.md"):
                context = report.read_text(encoding="utf-8", errors="replace").replace(
                    invite, "[invite]"
                )
                print(context[-3500:], file=sys.stderr)
        return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
