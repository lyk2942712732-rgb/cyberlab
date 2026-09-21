"""Create local secrets without overwriting an existing configuration."""
import secrets
from pathlib import Path

root = Path(__file__).resolve().parents[1]
destination = root / ".env"
if destination.exists():
    raise SystemExit(".env already exists; leaving it unchanged")
values = {
    "POSTGRES_PASSWORD": secrets.token_hex(24),
    "SECRET_KEY": secrets.token_hex(32),
    "ORCHESTRATOR_SECRET": secrets.token_hex(32),
    "ADMIN_PASSWORD": secrets.token_urlsafe(18),
    "STUDENT_PASSWORD": secrets.token_urlsafe(18),
}
lines = (root / ".env.example").read_text(encoding="utf-8").splitlines()
destination.write_text("\n".join(f"{line.split('=', 1)[0]}={values[line.split('=', 1)[0]]}" if "=" in line and line.split("=", 1)[0] in values else line for line in lines) + "\n", encoding="utf-8")
print("Created .env. Read ADMIN_PASSWORD and STUDENT_PASSWORD there; keep this file private.")
