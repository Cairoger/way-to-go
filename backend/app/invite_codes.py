"""Re-create an invitation for an authorized retry without storing its bearer code."""

import base64
import hmac
import os
import secrets
import tempfile
from pathlib import Path

from .core import fail


def signing_key(db):
    configured = os.getenv("INVITATION_SIGNING_KEY")
    if configured:
        return configured.encode()
    # Standalone installs keep a stable, private key beside the local database.
    url = db.get_bind().url
    if url.get_backend_name() == "sqlite" and url.database not in (None, "", ":memory:"):
        directory = Path(url.database).resolve().parent
    else:
        directory = Path.home() / ".waytogo"
    path = directory / ".waytogo-invite.key"
    try:
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        if not path.exists():
            with tempfile.NamedTemporaryFile(dir=directory, delete=False) as staged:
                temporary = Path(staged.name)
                staged.write(secrets.token_bytes(32))
            try:
                os.link(temporary, path)
            except FileExistsError:
                pass
            finally:
                temporary.unlink(missing_ok=True)
        key = path.read_bytes()
        if len(key) != 32:
            raise ValueError("invalid key length")
        return key
    except (OSError, ValueError):
        fail(503, "INVITE_KEY_UNAVAILABLE", "請維護者設定邀請簽章金鑰後再試。")


def reusable_code(db, invitation_id):
    signature = hmac.digest(
        signing_key(db), ("waytogo:invite:v1:" + invitation_id).encode(), "sha256"
    )
    return base64.b32encode(signature).decode()[:14]
