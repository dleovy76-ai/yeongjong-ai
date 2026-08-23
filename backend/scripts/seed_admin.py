"""One-off/rerunnable creation of an ADMIN user. Self-registration is
deliberately blocked for ADMIN (routers/auth.py SELF_REGISTERABLE_ROLES) -
this script is the only way to create one, run once by whoever operates the
platform, never exposed as an API endpoint.

Usage (from backend/):
    venv/Scripts/python.exe scripts/seed_admin.py --email a@b.com --password xxx --name "운영자"

Safe to rerun: if the email already exists, updates its role to ADMIN and
resets the password rather than erroring or inserting a duplicate.
"""

import argparse
import sys

from core.database import SessionLocal
from core.security import hash_password
from models import User, UserRole


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--name", default="운영자")
    args = parser.parse_args()

    if len(args.password) < 8:
        print("비밀번호는 8자 이상이어야 합니다.", file=sys.stderr)
        raise SystemExit(1)

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == args.email).first()
        if user is None:
            user = User(
                email=args.email,
                password_hash=hash_password(args.password),
                role=UserRole.ADMIN,
                name=args.name,
            )
            db.add(user)
            print(f"새 관리자 계정 생성: {args.email}", file=sys.stderr)
        else:
            user.role = UserRole.ADMIN
            user.password_hash = hash_password(args.password)
            print(f"기존 계정을 관리자로 갱신: {args.email}", file=sys.stderr)
        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    main()
