#!/usr/bin/env python3
"""
Superadmin Provisioning & Role Management CLI for Blogger Auto-Pilot SaaS.

Usage examples:
  # Interactive creation / promotion
  .venv/bin/python3 scripts/create_admin.py

  # Non-interactive creation
  .venv/bin/python3 scripts/create_admin.py --email founder@agensi.id --name "Founder" --password "StrongPassword2026!"

  # Promote an existing registered user to admin
  .venv/bin/python3 scripts/create_admin.py --promote staf@agensi.id

  # Demote an admin back to subscriber
  .venv/bin/python3 scripts/create_admin.py --demote staf@agensi.id

  # List all current Superadmins
  .venv/bin/python3 scripts/create_admin.py --list
"""

import argparse
import getpass
import os
import sys
from datetime import datetime, timezone, timedelta

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from src.core.database import SessionLocal, init_saas_db
from src.models.models import User, Subscription, NotificationSetting
from src.core.security import hash_password
from src.services.audit import record_audit_log


def list_admins(db) -> int:
    admins = db.query(User).filter(User.role == "admin").order_by(User.created_at.asc()).all()
    if not admins:
        print("Belum ada akun dengan role 'admin'.")
        return 0
    print(f"Daftar Superadmin aktif ({len(admins)} akun):")
    for idx, a in enumerate(admins, 1):
        status = "Aktif" if a.is_active else "Suspend"
        plan = a.subscription.plan_tier if a.subscription else "free"
        print(f"  {idx}. {a.email} | Nama: {a.full_name or '-'} | Paket: {plan.upper()} | Status: {status}")
    return 0


def promote_or_demote(db, email: str, target_role: str) -> int:
    clean_email = email.strip().lower()
    user = db.query(User).filter(User.email == clean_email).first()
    if not user:
        print(f"Error: Pengguna dengan email '{clean_email}' tidak ditemukan di database.")
        return 1

    if target_role == "subscriber":
        admin_count = db.query(User).filter(User.role == "admin", User.is_active == True).count()
        if user.role == "admin" and admin_count <= 1:
            print("Error: Tidak dapat mencabut hak admin satu-satunya Superadmin aktif di sistem.")
            return 1

    old_role = user.role
    user.role = target_role
    db.commit()

    record_audit_log(
        db=db,
        event_type=f"cli.admin_{'promoted' if target_role == 'admin' else 'demoted'}",
        user_id=user.id,
        entity_id=user.id,
        metadata={"email": clean_email, "old_role": old_role, "new_role": target_role}
    )
    print(f"Berhasil: Peran '{clean_email}' diubah dari '{old_role}' menjadi '{target_role}'.")
    return 0


def create_or_update_admin(db, email: str, full_name: str, password: str) -> int:
    clean_email = email.strip().lower()
    if "@" not in clean_email or "." not in clean_email.split("@")[-1]:
        print("Error: Format email tidak valid.")
        return 1

    if len(password.strip()) < 8:
        print("Error: Kata sandi admin minimal 8 karakter demi keamanan production.")
        return 1

    existing = db.query(User).filter(User.email == clean_email).first()
    if existing:
        existing.role = "admin"
        existing.is_active = True
        existing.hashed_password = hash_password(password.strip())
        if full_name:
            existing.full_name = full_name.strip()
        db.commit()
        record_audit_log(
            db=db,
            event_type="cli.admin_promoted",
            user_id=existing.id,
            entity_id=existing.id,
            metadata={"email": clean_email, "password_updated": True}
        )
        print(f"Berhasil: Akun eksisting '{clean_email}' dipromosikan ke 'admin' dan kata sandi diperbarui.")
        return 0

    admin = User(
        email=clean_email,
        hashed_password=hash_password(password.strip()),
        full_name=full_name.strip() if full_name else clean_email.split("@")[0],
        role="admin",
        is_active=True
    )
    db.add(admin)
    db.flush()

    sub = Subscription(
        user_id=admin.id,
        plan_tier="agency",
        status="active",
        article_credits_limit=600,
        article_credits_used=0,
        current_period_start=datetime.now(timezone.utc),
        current_period_end=datetime.now(timezone.utc) + timedelta(days=365)
    )
    db.add(sub)

    notify = NotificationSetting(
        user_id=admin.id,
        notify_on_draft=True,
        notify_on_publish=True,
        notify_on_credit_low=True
    )
    db.add(notify)
    db.commit()

    record_audit_log(
        db=db,
        event_type="cli.admin_created",
        user_id=admin.id,
        entity_id=admin.id,
        metadata={"email": clean_email, "full_name": admin.full_name}
    )
    print(f"Berhasil: Akun Superadmin baru '{clean_email}' ({admin.full_name}) telah dibuat dengan paket Agency (600 kredit).")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Kelola akun Superadmin Blogger Auto-Pilot SaaS.")
    parser.add_argument("--list", action="store_true", help="Tampilkan semua akun Superadmin saat ini.")
    parser.add_argument("--promote", type=str, help="Promosikan email pengguna eksisting menjadi admin.")
    parser.add_argument("--demote", type=str, help="Cabut hak admin email tertentu kembali ke subscriber.")
    parser.add_argument("--email", type=str, help="Email untuk akun admin baru.")
    parser.add_argument("--name", type=str, default="", help="Nama lengkap admin baru.")
    parser.add_argument("--password", type=str, help="Password admin baru (minimal 8 karakter).")

    args = parser.parse_args()
    init_saas_db()
    db = SessionLocal()

    try:
        if args.list:
            return list_admins(db)
        if args.promote:
            return promote_or_demote(db, args.promote, "admin")
        if args.demote:
            return promote_or_demote(db, args.demote, "subscriber")

        email = args.email or input("Email Superadmin: ").strip()
        full_name = args.name or input("Nama Lengkap (opsional): ").strip()
        password = args.password
        if not password:
            password = getpass.getpass("Password (minimal 8 karakter): ")
            confirm = getpass.getpass("Konfirmasi Password: ")
            if password != confirm:
                print("Error: Konfirmasi password tidak cocok.")
                return 1

        return create_or_update_admin(db, email, full_name, password)
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
