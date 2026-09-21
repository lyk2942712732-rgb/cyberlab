import argparse
import getpass
import re
from sqlalchemy import select
from app.core.db import SessionLocal
from app.core.security import passwords
from app.models import User


def main():
    parser = argparse.ArgumentParser(description="Create an ADMIN account without a public registration endpoint")
    parser.add_argument("username")
    parser.add_argument("--name", default="教学管理员")
    args = parser.parse_args()
    if not re.fullmatch(r"[a-zA-Z0-9_.-]{3,64}", args.username):
        raise SystemExit("Username must be 3–64 letters, digits, underscores, dots or hyphens")
    password = getpass.getpass("Password (12–128 characters): ")
    if not 12 <= len(password) <= 128 or password != getpass.getpass("Confirm password: "):
        raise SystemExit("Invalid password length or confirmation mismatch")
    with SessionLocal.begin() as db:
        if db.scalar(select(User.id).where(User.username == args.username)):
            raise SystemExit("Username already exists; no changes made")
        db.add(User(username=args.username, real_name=args.name, password_hash=passwords.hash(password), role="ADMIN"))
    print("ADMIN created.")


if __name__ == "__main__":
    main()
