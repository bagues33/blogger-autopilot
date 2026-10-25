#!/usr/bin/env python3
"""
Blogger Auto-Pilot SaaS CLI Management Tool
Provides CLI commands for server operators to manage tenants, subscriptions, and system health.
"""

import sys
import argparse
from datetime import datetime, timezone, timedelta
from db_saas import SessionLocal, init_saas_db
from models_saas import User, Subscription, Blog, Article, Keyword
from auth_saas import hash_password, register_new_tenant_user
from midtrans_service import PLAN_TIERS

def get_stats():
    db = SessionLocal()
    try:
        total_users = db.query(User).count()
        subs = db.query(Subscription).all()
        tier_counts = {'free': 0, 'starter': 0, 'pro': 0, 'agency': 0}
        for s in subs:
            tier = s.plan_tier if s.plan_tier in tier_counts else 'free'
            tier_counts[tier] += 1
            
        mrr = (
            tier_counts['starter'] * 99000 +
            tier_counts['pro'] * 249000 +
            tier_counts['agency'] * 699000
        )
        total_blogs = db.query(Blog).count()
        total_arts = db.query(Article).count()
        total_kws = db.query(Keyword).count()

        print("=====================================================")
        print("📊 BLOGGER AUTO-PILOT SAAS SYSTEM KPIS")
        print("=====================================================")
        print(f"Total Registered Tenants : {total_users}")
        print(f"  • Free Community       : {tier_counts['free']}")
        print(f"  • Starter Solo (99k)   : {tier_counts['starter']}")
        print(f"  • Pro Publisher (249k) : {tier_counts['pro']}")
        print(f"  • Agency Network (699k): {tier_counts['agency']}")
        print(f"Estimated MRR (IDR)      : Rp {mrr:,.0f}")
        print("-----------------------------------------------------")
        print(f"Total Connected Blogs    : {total_blogs}")
        print(f"Total Drafted/Published  : {total_arts}")
        print(f"Total Queued Keywords    : {total_kws}")
        print("=====================================================")
    finally:
        db.close()

def list_tenants():
    db = SessionLocal()
    try:
        users = db.query(User).order_by(User.created_at.desc()).all()
        print(f"{'Email':<35} | {'Role':<10} | {'Plan':<10} | {'Credits':<10} | {'Blogs':<6} | {'Active'}")
        print("-" * 88)
        for u in users:
            sub = u.subscription
            plan = sub.plan_tier.upper() if sub else 'FREE'
            credits_str = f"{sub.article_credits_used}/{sub.article_credits_limit}" if sub else "0/3"
            blog_count = len(u.blogs)
            status_str = "YES" if u.is_active else "NO"
            print(f"{u.email:<35} | {u.role:<10} | {plan:<10} | {credits_str:<10} | {blog_count:<6} | {status_str}")
        print(f"\nTotal: {len(users)} tenant(s)")
    finally:
        db.close()

def create_user(email, password, full_name=None, role='subscriber', plan='free'):
    db = SessionLocal()
    try:
        clean_email = email.strip().lower()
        existing = db.query(User).filter(User.email == clean_email).first()
        if existing:
            print(f"❌ Error: User dengan email '{clean_email}' sudah terdaftar.")
            return

        user = register_new_tenant_user(
            db=db,
            email=clean_email,
            password=password,
            full_name=full_name or clean_email.split('@')[0],
            role=role,
            plan_tier=plan
        )
        print(f"✅ User berhasil dibuat:")
        print(f"   ID    : {user.id}")
        print(f"   Email : {user.email}")
        print(f"   Role  : {user.role}")
        print(f"   Plan  : {user.subscription.plan_tier} ({user.subscription.article_credits_limit} credits)")
    finally:
        db.close()

def set_plan(email, plan_tier, credits=None):
    db = SessionLocal()
    try:
        clean_email = email.strip().lower()
        user = db.query(User).filter(User.email == clean_email).first()
        if not user:
            print(f"❌ Error: User '{clean_email}' tidak ditemukan.")
            return

        tier_info = PLAN_TIERS.get(plan_tier.lower(), PLAN_TIERS['free'])
        sub = user.subscription
        if not sub:
            sub = Subscription(user_id=user.id)
            db.add(sub)

        sub.plan_tier = plan_tier.lower()
        sub.status = 'active'
        sub.article_credits_limit = credits if credits is not None else tier_info['credits']
        sub.article_credits_used = 0
        sub.current_period_start = datetime.now(timezone.utc)
        sub.current_period_end = datetime.now(timezone.utc) + timedelta(days=30)
        db.commit()

        print(f"✅ Plan user '{clean_email}' berhasil diperbarui ke '{plan_tier.upper()}' dengan limit {sub.article_credits_limit} kredit.")
    finally:
        db.close()

def add_credits(email, amount):
    db = SessionLocal()
    try:
        clean_email = email.strip().lower()
        user = db.query(User).filter(User.email == clean_email).first()
        if not user:
            print(f"❌ Error: User '{clean_email}' tidak ditemukan.")
            return

        sub = user.subscription
        if not sub:
            sub = Subscription(user_id=user.id)
            db.add(sub)

        sub.article_credits_limit += amount
        db.commit()

        print(f"✅ Berhasil menambahkan {amount} kredit untuk '{clean_email}'. Limit baru: {sub.article_credits_limit} kredit.")
    finally:
        db.close()

def main():
    parser = argparse.ArgumentParser(description="Blogger Auto-Pilot SaaS CLI Admin")
    subparsers = parser.add_subparsers(dest="command")

    # stats
    subparsers.add_parser("stats", help="Tampilkan KPI dan metrik pendapatan SaaS")

    # list
    subparsers.add_parser("list", help="Tampilkan daftar seluruh tenant")

    # create-user
    p_create = subparsers.add_parser("create-user", help="Buat pengguna baru atau admin")
    p_create.add_argument("--email", required=True, help="Email pengguna")
    p_create.add_argument("--password", required=True, help="Password minimal 6 karakter")
    p_create.add_argument("--name", help="Nama lengkap pengguna")
    p_create.add_argument("--role", default="subscriber", choices=["subscriber", "admin", "agency"], help="Peran pengguna")
    p_create.add_argument("--plan", default="free", choices=["free", "starter", "pro", "agency"], help="Paket awal")

    # set-plan
    p_plan = subparsers.add_parser("set-plan", help="Ubah paket langganan pengguna")
    p_plan.add_argument("--email", required=True, help="Email pengguna")
    p_plan.add_argument("--plan", required=True, choices=["free", "starter", "pro", "agency"], help="Paket baru")
    p_plan.add_argument("--credits", type=int, help="Limit kredit kustom (opsional)")

    # add-credits
    p_cred = subparsers.add_parser("add-credits", help="Tambahkan kredit bonus untuk pengguna")
    p_cred.add_argument("--email", required=True, help="Email pengguna")
    p_cred.add_argument("--amount", type=int, required=True, help="Jumlah kredit yang ditambahkan")

    # run-cycle
    subparsers.add_parser("run-cycle", help="Jalankan satu siklus autopilot untuk seluruh tenant aktif")

    args = parser.parse_args()

    if args.command == "stats":
        get_stats()
    elif args.command == "list":
        list_tenants()
    elif args.command == "create-user":
        create_user(args.email, args.password, args.name, args.role, args.plan)
    elif args.command == "set-plan":
        set_plan(args.email, args.plan, args.credits)
    elif args.command == "add-credits":
        add_credits(args.email, args.amount)
    elif args.command == "run-cycle":
        from autopilot_scheduler import run_scheduler_cycle
        res = run_scheduler_cycle()
        print("Cycle Result:", res)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
