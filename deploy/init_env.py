"""Create a local Compose configuration without overwriting an existing installation."""
from pathlib import Path
import secrets

root = Path(__file__).resolve().parents[1]
template = (root / ".env.example").read_text(encoding="utf-8")
try:
    with (root / ".env").open("x", encoding="utf-8") as target:
        target.write(template.replace("POSTGRES_PASSWORD=\n", f"POSTGRES_PASSWORD={secrets.token_urlsafe(32)}\n", 1))
except FileExistsError:
    raise SystemExit(".env already exists; keeping the existing configuration.")
print("Created .env. Add Google OIDC credentials to enable sign-in.")
