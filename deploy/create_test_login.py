"""Provision a fixed local test account. Only the password verifier is written to .env."""

import hashlib
import os
import secrets
import tempfile
from pathlib import Path


def provision(config_path: Path) -> str:
    contents = config_path.read_text(encoding="utf-8")
    keys = {"LOCAL_TEST_USERNAME", "LOCAL_TEST_PASSWORD_HASH"}
    retained = []
    for line in contents.splitlines(keepends=True):
        key, sep, value = line.partition("=")
        if sep and key.strip() in keys:
            if value.strip().strip("'\""):
                raise ValueError("測試帳號已設定，現有密碼會繼續有效。")
        else:
            retained.append(line)

    password = secrets.token_urlsafe(15)
    salt = secrets.token_bytes(16)
    iterations = 600_000
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iterations)
    verifier = f"pbkdf2_sha256${iterations}${salt.hex()}${digest.hex()}"
    # Compose reads single-quoted values literally, including the separators in the hash.
    updated = "".join(retained).rstrip("\n") + "\n"
    updated += f"LOCAL_TEST_USERNAME=tester\nLOCAL_TEST_PASSWORD_HASH='{verifier}'\n"
    staged_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", dir=config_path.parent, prefix=".env.", suffix=".tmp",
            encoding="utf-8", delete=False
        ) as staged:
            staged_path = Path(staged.name)
            staged.write(updated)
            staged.flush()
            os.fsync(staged.fileno())
        os.replace(staged_path, config_path)
    finally:
        if staged_path is not None:
            staged_path.unlink(missing_ok=True)
    return password


if __name__ == "__main__":
    path = Path(__file__).resolve().parents[1] / ".env"
    try:
        credential = provision(path)
    except FileNotFoundError:
        raise SystemExit("請先執行 python deploy/init_env.py 建立 .env。") from None
    except ValueError as error:
        raise SystemExit(str(error)) from None
    print("帳號：tester")
    print(f"密碼：{credential}")
