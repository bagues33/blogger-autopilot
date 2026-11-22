#!/usr/bin/env python3
"""
SaaS Production Readiness Diagnostic Tool for Blogger Auto-Pilot
Audits Database (Supabase / Postgres), AES Encryption, Midtrans Gateway, OAuth & AI Engines.
"""

import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)
import json
import hashlib
from datetime import datetime

# Load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

def print_section(title):
    print(f"\n{'=' * 65}\n📌 {title}\n{'=' * 65}")

def check_mark(status):
    return "✅ [PASS]" if status else "⚠️  [WARN]"

def cross_mark(status):
    return "✅ [PASS]" if status else "❌ [FAIL]"

def run_diagnostics():
    print(f"Blogger Auto-Pilot SaaS Diagnostic Suite — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    all_critical_ok = True

    # 1. Database & Supabase Check
    print_section("1. Multi-Tenant Database & Supabase Check")
    try:
        from src.core.database import engine, is_sqlite, DB_URL, SessionLocal
        from src.models.models import User, Subscription, Blog, Article, Keyword
        
        masked_url = DB_URL
        if '@' in DB_URL:
            prefix, rest = DB_URL.split('@', 1)
            masked_url = f"{prefix.split(':')[0]}://****:****@{rest}"
            
        print(f"Target DB Engine    : {'SQLite (Local Dev)' if is_sqlite else 'PostgreSQL (Supabase / Managed)'}")
        print(f"Connection URI      : {masked_url}")

        db = SessionLocal()
        user_count = db.query(User).count()
        sub_count = db.query(Subscription).count()
        blog_count = db.query(Blog).count()
        art_count = db.query(Article).count()
        kw_count = db.query(Keyword).count()
        db.close()

        print(f"{cross_mark(True)} Database Connected Successfully!")
        print(f"  - Users Registered   : {user_count}")
        print(f"  - Active Subs        : {sub_count}")
        print(f"  - Connected Blogs    : {blog_count}")
        print(f"  - Total Articles     : {art_count}")
        print(f"  - Queued Keywords    : {kw_count}")
    except Exception as e:
        all_critical_ok = False
        print(f"{cross_mark(False)} Database Connection Failed: {e}")

    # 2. Security & AES Cryptography Check
    print_section("2. Security, JWT & AES-256 Token Encryption")
    try:
        from src.core.crypto import encrypt_token_data, decrypt_token_data
        from src.core.security import hash_password, verify_password, create_access_token, decode_access_token

        # Test AES
        dummy = {'refresh_token': '1//mock_sample_google_refresh_token_xyz', 'token': 'mock_token'}
        encrypted = encrypt_token_data(dummy)
        decrypted = decrypt_token_data(encrypted)
        aes_ok = decrypted.get('refresh_token') == dummy['refresh_token']
        print(f"{cross_mark(aes_ok)} AES-256 Symmetric Encryption/Decryption: {'Valid' if aes_ok else 'Failed'}")

        # Test JWT
        jwt_token = create_access_token({'sub': 'test-uuid-1234'})
        payload = decode_access_token(jwt_token)
        jwt_ok = payload and payload.get('sub') == 'test-uuid-1234'
        print(f"{cross_mark(jwt_ok)} JWT Token Sign & Verification (HS256): {'Valid' if jwt_ok else 'Failed'}")

        # Test Bcrypt
        hashed = hash_password('TestPassword123!')
        bcrypt_ok = verify_password('TestPassword123!', hashed)
        print(f"{cross_mark(bcrypt_ok)} Bcrypt Password Hashing & Salt: {'Valid' if bcrypt_ok else 'Failed'}")
    except Exception as e:
        all_critical_ok = False
        print(f"{cross_mark(False)} Security suite failed: {e}")

    # 3. Midtrans Payment Gateway Check
    print_section("3. Midtrans Indonesian Payment Gateway Check")
    try:
        from src.services.payment import (
            MIDTRANS_SERVER_KEY, MIDTRANS_CLIENT_KEY, MIDTRANS_IS_PRODUCTION,
            verify_signature, PLAN_TIERS
        )
        print(f"Mode Operasi        : {'PRODUCTION (Live)' if MIDTRANS_IS_PRODUCTION else 'SANDBOX (Testing)'}")
        print(f"Client Key          : {MIDTRANS_CLIENT_KEY[:10]}...")
        print(f"Server Key          : {MIDTRANS_SERVER_KEY[:10]}...")

        # Test SHA512 Signature verification
        order_test = "BAP-TEST-001"
        status_test = "200"
        gross_test = "149000"
        raw_hash = hashlib.sha512(f"{order_test}{status_test}{gross_test}{MIDTRANS_SERVER_KEY}".encode('utf-8')).hexdigest()
        sig_ok = verify_signature(order_test, status_test, gross_test, raw_hash)
        print(f"{cross_mark(sig_ok)} SHA-512 Webhook Signature Engine: {'Verified' if sig_ok else 'Failed'}")

        print("Tersedia Paket Langganan IDR:")
        for t, p in PLAN_TIERS.items():
            print(f"  • {p['name']:<24}: Rp {p['price']:>7,}/bln | {p['credits']} Kredit | {p['blogs']} Blog")
    except Exception as e:
        print(f"{cross_mark(False)} Midtrans check failed: {e}")

    # 4. Google Blogger OAuth Client
    print_section("4. Google Blogger OAuth Client Credentials")
    client_secret_path = os.environ.get('GOOGLE_CLIENT_SECRETS_FILE', 'client_secret.json')
    if os.path.exists(client_secret_path):
        try:
            with open(client_secret_path, 'r') as f:
                cdata = json.load(f)
            client_type = 'web' if 'web' in cdata else ('installed' if 'installed' in cdata else 'unknown')
            print(f"{cross_mark(True)} File '{client_secret_path}' ditemukan (Tipe: {client_type})")
        except Exception as e:
            print(f"{check_mark(False)} File '{client_secret_path}' invalid JSON: {e}")
    else:
        print(f"{check_mark(False)} File '{client_secret_path}' belum ditemukan.")
        print("  💡 Catatan: Diperlukan untuk Google Blogger OAuth auto-discovery.")

    # 5. AI LLM Providers Check
    print_section("5. Autonomous AI LLM Providers Check")
    gemini_key = os.environ.get('GEMINI_API_KEY')
    groq_key = os.environ.get('GROQ_API_KEY')
    openai_key = os.environ.get('OPENAI_API_KEY')
    has_any_llm = bool(gemini_key or groq_key or openai_key)

    print(f"{check_mark(bool(gemini_key))} Google Gemini API Key    : {'Terkonfigurasi' if gemini_key else 'Belum diisi'}")
    print(f"{check_mark(bool(groq_key))} Groq Cloud API Key        : {'Terkonfigurasi' if groq_key else 'Belum diisi'}")
    print(f"{check_mark(bool(openai_key))} OpenAI API Key            : {'Terkonfigurasi' if openai_key else 'Belum diisi'}")

    # 6. Public Image CDN, Cron Secret & Transactional Email
    print_section("6. Public Image CDN, Cron Security & Email Transaksional")
    c_url = os.environ.get('CLOUDINARY_URL')
    print(f"{check_mark(bool(c_url))} Cloudinary Public CDN     : {'Aktif (HTTPS CDN)' if c_url else 'Fallback Lokal (/uploads/ WebP)'}")

    from src.routers.cron import _is_weak_cron_secret
    from src.services.mailer import is_email_configured
    cron_raw = os.environ.get('CRON_SECRET_KEY', '').strip()
    cron_ok = not _is_weak_cron_secret(cron_raw)
    email_ok = is_email_configured()
    print(f"{check_mark(cron_ok)} CRON_SECRET_KEY           : {'Kuat (>=24 karakter)' if cron_ok else 'Masih default/lemah (WAJIB diisi di produksi)'}")
    print(f"{check_mark(email_ok)} Transactional Email       : {'Aktif (Resend / SMTP)' if email_ok else 'Belum diisi (Reset password produksi perlu Resend/SMTP)'}")

    is_prod_env = os.environ.get('ENVIRONMENT', '').strip().lower() == 'production'
    prod_warnings = []
    if not has_any_llm:
        prod_warnings.append("Belum ada API Key LLM (GEMINI_API_KEY / GROQ_API_KEY / OPENAI_API_KEY).")
    if is_sqlite:
        prod_warnings.append("Database masih memakai SQLite lokal (gunakan PostgreSQL/Supabase untuk produksi).")
    if not cron_ok:
        prod_warnings.append("CRON_SECRET_KEY masih kosong/lemah.")
    if not email_ok:
        prod_warnings.append("Transporter email (RESEND_API_KEY / SMTP_HOST) belum dikonfigurasi.")

    # Summary
    print_section("KESIMPULAN AUDIT SAAS")
    if all_critical_ok and (not is_prod_env or not prod_warnings):
        if prod_warnings:
            print("⚠️  STATUS: PONDASI LOKAL/DEV SIAP, NAMUN BELUM LENGKAP UNTUK GO-LIVE PRODUKSI:")
            for w in prod_warnings:
                print(f"   - {w}")
        else:
            print("🎉 STATUS: SIAP PRODUKSI! Seluruh pondasi inti Multi-Tenant SaaS, PostgreSQL,")
            print("   AES Enkripsi, CRON Secret, Email Transaksional, dan Midtrans terverifikasi.")
    else:
        print("❌ STATUS: BELUM SIAP RILIS PRODUKSI. Perbaiki item berikut sebelum go-live:")
        for w in prod_warnings:
            print(f"   - {w}")
        if is_prod_env:
            sys.exit(1)

if __name__ == '__main__':
    run_diagnostics()
