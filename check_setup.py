#!/usr/bin/env python3
"""
Diagnostic & Setup Readiness Checker for Blogger Auto-Pilot
Verifies database, Google Blogger OAuth credentials, AI keys, and Image CDN readiness.
"""

import os
import sys
import json
import sqlite3

# Load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from db import DB_PATH, BASE_DIR
from blogger_client import resolve_file_path, get_active_blog_info

def print_header(title):
    print("\n" + "=" * 60)
    print(f" {title}")
    print("=" * 60)

def check_setup():
    print_header("BLOGGER AUTO-PILOT: DIAGNOSTIC & READINESS CHECK")
    all_ready = True

    # 1. Database Check
    print("\n[1/5] Memeriksa Database SQLite:")
    if os.path.exists(DB_PATH):
        try:
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            blogs_cnt = c.execute("SELECT count(*) FROM blogs").fetchone()[0]
            arts_cnt = c.execute("SELECT count(*) FROM articles").fetchone()[0]
            kws_cnt = c.execute("SELECT count(*) FROM keywords").fetchone()[0]
            conn.close()
            print(f"  ✓ Database aktif di: {DB_PATH}")
            print(f"    - Total Blog: {blogs_cnt} | Total Artikel: {arts_cnt} | Total Keyword: {kws_cnt}")
        except Exception as e:
            print(f"  ✗ Error membaca database: {e}")
            all_ready = False
    else:
        print(f"  ✗ File database '{DB_PATH}' belum ada. Jalankan: python db.py && python migrate_multi_blog.py")
        all_ready = False

    # 2. Google Blogger OAuth Check
    print("\n[2/5] Memeriksa Kredensial Google Blogger API v3:")
    blog_id, token_file, blog_name, blog_url = get_active_blog_info()
    client_secret_path = resolve_file_path(os.environ.get('GOOGLE_CLIENT_SECRETS_FILE', 'client_secret.json'))
    resolved_token_path = resolve_file_path(token_file)

    secret_ok = os.path.exists(client_secret_path) if client_secret_path else False
    token_ok = os.path.exists(resolved_token_path) if resolved_token_path else False

    if secret_ok:
        print(f"  ✓ Client Secret ditemukan: {client_secret_path}")
    else:
        print(f"  ✗ Client Secret TIDAK ditemukan: {client_secret_path}")
        print("    -> Langkah: Buat OAuth Client ID (Desktop App) di Google Cloud Console")
        print("       dan simpan file JSON sebagai 'client_secret.json' di direktori ini.")
        all_ready = False

    if token_ok:
        print(f"  ✓ Token file ditemukan: {resolved_token_path}")
        try:
            from blogger_client import get_service
            service, b_id = get_service()
            blog_obj = service.blogs().get(blogId=b_id).execute()
            print(f"  ✓ Koneksi Google API Berhasil! Terhubung ke blog: '{blog_obj.get('name')}' ({blog_obj.get('url')})")
        except Exception as e:
            print(f"  ⚠ Token ditemukan tapi gagal verifikasi ke Blogger API: {e}")
            print("    -> Jalankan: python auth.py --url untuk login ulang.")
            all_ready = False
    else:
        print(f"  ✗ Token file TIDAK ditemukan: {resolved_token_path}")
        print("    -> Langkah: Jalankan 'python auth.py --url' dan selesaikan login Google.")
        all_ready = False

    # 3. AI Providers Check
    print("\n[3/5] Memeriksa Kunci API AI (Autonomous Content Writer):")
    gemini_key = os.environ.get('GEMINI_API_KEY')
    groq_key = os.environ.get('GROQ_API_KEY')
    openai_key = os.environ.get('OPENAI_API_KEY')

    ai_found = False
    if gemini_key:
        print(f"  ✓ Google Gemini API Key: Terdeteksi ({gemini_key[:4]}...{gemini_key[-4:]})")
        ai_found = True
    if groq_key:
        print(f"  ✓ Groq API Key: Terdeteksi ({groq_key[:4]}...{groq_key[-4:]})")
        ai_found = True
    if openai_key:
        print(f"  ✓ OpenAI API Key: Terdeteksi ({openai_key[:4]}...{openai_key[-4:]})")
        ai_found = True

    if not ai_found:
        print("  ⚠ Belum ada API Key AI (GEMINI_API_KEY/GROQ_API_KEY/OPENAI_API_KEY) di .env.")
        print("    -> Sistem akan menggunakan Template Fallback SEO terstruktur sampai Anda memasukkan API Key.")
    else:
        print("  ✓ AI Engine siap memproduksi artikel mendalam!")

    # 4. Image CDN Check
    print("\n[4/5] Memeriksa Image Hosting & CDN Publik:")
    c_url = os.environ.get('CLOUDINARY_URL')
    c_name = os.environ.get('CLOUDINARY_CLOUD_NAME')
    
    if c_url or c_name:
        print("  ✓ Cloudinary CDN: Dikonfigurasi (Gambar artikel akan di-host di CDN publik cepat).")
    else:
        print("  ⚠ Cloudinary CDN belum diset di .env.")
        print("    -> Media lokal akan tersimpan di /uploads/ (Untuk blog publik, disarankan isi CLOUDINARY_URL).")

    # 5. Summary
    print_header("HASIL KESIAPAN WORKFLOW REAL")
    if all_ready:
        print("🎉 SELAMAT! Sistem ini sudah 100% SIAP untuk alur kerja riil Blogger:")
        print("   1. Auto-Draft & Keyword Research bekerja penuh.")
        print("   2. Preview & Visual Editor siap digunakan.")
        print("   3. Fitur 'Kirim Draft ke Blogger' & 'Publish Live' aktif dan terhubung.")
    else:
        print("📋 Langkah berikutnya agar 100% siap:")
        if not secret_ok:
            print("   - Letakkan file 'client_secret.json' dari Google Cloud Console.")
        if not token_ok:
            print("   - Jalankan 'python auth.py --url' untuk membuat token otentikasi.")
        if not ai_found:
            print("   - Masukkan GEMINI_API_KEY di .env agar artikel digenerate secara pintar.")
        if not (c_url or c_name):
            print("   - (Opsional) Masukkan CLOUDINARY_URL di .env untuk CDN gambar bebas broken link.")
    print("=" * 60 + "\n")

if __name__ == '__main__':
    check_setup()
