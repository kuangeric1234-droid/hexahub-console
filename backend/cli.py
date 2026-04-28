"""
CLI management commands.

Usage (from backend/ directory):
    python -m backend.cli create-admin
    python -m backend.cli create-admin --email admin@example.com --password secret
"""
from __future__ import annotations

import argparse
import asyncio
import getpass
import sys
import uuid


async def _create_admin(email: str, password: str, full_name: str) -> None:
    from backend.api.auth import hash_password
    from backend.db.database import AsyncSessionLocal
    from backend.db.models import User
    from sqlalchemy import select

    async with AsyncSessionLocal() as session:
        existing = await session.execute(select(User).where(User.email == email))
        if existing.scalar_one_or_none():
            print(f"[!] User '{email}' already exists.")
            sys.exit(1)

        user = User(
            id=uuid.uuid4(),
            email=email,
            hashed_password=hash_password(password),
            full_name=full_name or "Admin",
            role="admin",
            is_active=True,
        )
        session.add(user)
        await session.commit()
        print(f"[✓] Admin user created: {email}  (id={user.id})")


def cmd_create_admin(args: argparse.Namespace) -> None:
    email = args.email or input("Email: ").strip()
    if not email:
        print("[!] Email is required.")
        sys.exit(1)

    password = args.password or getpass.getpass("Password: ")
    if len(password) < 8:
        print("[!] Password must be at least 8 characters.")
        sys.exit(1)

    full_name = args.full_name or input("Full name (optional): ").strip()

    asyncio.run(_create_admin(email, password, full_name))


def main() -> None:
    parser = argparse.ArgumentParser(description="Hexa Hub management CLI")
    subs   = parser.add_subparsers(dest="command")

    # create-admin
    p_admin = subs.add_parser("create-admin", help="Create an admin user")
    p_admin.add_argument("--email",     default="", help="Admin email address")
    p_admin.add_argument("--password",  default="", help="Admin password (min 8 chars)")
    p_admin.add_argument("--full-name", default="", dest="full_name")

    args = parser.parse_args()

    if args.command == "create-admin":
        cmd_create_admin(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
