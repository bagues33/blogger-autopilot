#!/usr/bin/env python3
"""
SaaS Demo Data Seeder for Blogger Auto-Pilot
Populates local or cloud database with realistic Indonesian creators,
blogs, keywords, and SEO E-E-A-T articles for demonstrations or testing.
"""

from db_saas import SessionLocal, init_saas_db
from models_saas import User, Subscription, Blog, Article, Keyword, NotificationSetting
from auth_saas import hash_password
from schema_builder import inject_schema_if_missing
from datetime import datetime, timezone, timedelta
import uuid

def seed():
    print("🌱 Initializing SaaS Demo Data...")
    init_saas_db()
    db = SessionLocal()

    try:
        # 1. Superadmin User
        admin_email = "admin@bagustech.id"
        admin = db.query(User).filter(User.email == admin_email).first()
        if not admin:
            admin = User(
                email=admin_email,
                hashed_password=hash_password("AdminBagus2026!"),
                full_name="Bagus Admin",
                role="admin",
                is_active=True
            )
            db.add(admin)
            db.flush()

            admin_sub = Subscription(
                user_id=admin.id,
                plan_tier="agency",
                status="active",
                article_credits_limit=500,
                article_credits_used=12,
                current_period_start=datetime.now(timezone.utc),
                current_period_end=datetime.now(timezone.utc) + timedelta(days=365)
            )
            db.add(admin_sub)

            admin_notify = NotificationSetting(
                user_id=admin.id,
                notify_on_draft=True,
                notify_on_publish=True,
                notify_on_credit_low=True
            )
            db.add(admin_notify)
            print(f"✓ Created Superadmin: {admin_email} (Agency Plan, 500 credits)")

        # 2. Solo Creator (Starter Plan)
        creator_email = "creator.nusantara@gmail.com"
        creator = db.query(User).filter(User.email == creator_email).first()
        if not creator:
            creator = User(
                email=creator_email,
                hashed_password=hash_password("CreatorPass123!"),
                full_name="Budi Creator Nusantara",
                role="subscriber",
                is_active=True
            )
            db.add(creator)
            db.flush()

            creator_sub = Subscription(
                user_id=creator.id,
                plan_tier="starter",
                status="active",
                article_credits_limit=30,
                article_credits_used=5,
                current_period_start=datetime.now(timezone.utc),
                current_period_end=datetime.now(timezone.utc) + timedelta(days=30)
            )
            db.add(creator_sub)

            # Blog for Creator
            blog_id = "blog_nusantara_tech"
            existing_blog = db.query(Blog).filter(Blog.id == blog_id).first()
            if not existing_blog:
                b = Blog(
                    id=blog_id,
                    user_id=creator.id,
                    name="Nusantara Tech & Gadget",
                    url="https://nusantaratech.blogspot.com",
                    account_name="Akun Google Budi",
                    niche_description="Ulasan gadget, tutorial teknologi, dan AI untuk produktivitas di Indonesia.",
                    is_active=1
                )
                db.add(b)

            # Keywords for Creator
            demo_keywords = [
                ("rekomendasi hp 2 jutaan terbaik 2026", "Commercial"),
                ("cara menggunakan deepseek ai untuk pemula", "Informational"),
                ("tips menghemat baterai laptop windows 11", "Informational"),
                ("aplikasi edit video android tanpa watermark", "Commercial"),
                ("perbandingan google gemini vs chatgpt gratis", "Informational")
            ]
            for kw_text, intent in demo_keywords:
                exists_kw = db.query(Keyword).filter(Keyword.user_id == creator.id, Keyword.keyword == kw_text).first()
                if not exists_kw:
                    db.add(Keyword(
                        user_id=creator.id,
                        blog_id=blog_id,
                        keyword=kw_text,
                        search_intent=intent,
                        status="planned"
                    ))

            # Sample High-Quality Article with Schema
            article_title = "5 Rekomendasi HP 2 Jutaan Terbaik 2026 dengan Kamera Jernih & Baterai Awet"
            raw_html = """
            <p>Pasar smartphone kelas menengah ke bawah di Indonesia semakin kompetitif di tahun 2026. Dengan anggaran sekitar 2 jutaan rupiah, pengguna kini sudah dapat menikmati layar AMOLED 120Hz dan chipset 5G yang kencang.</p>
            <h2>Kriteria Memilih Smartphone 2 Jutaan</h2>
            <p>Sebelum memutuskan membeli, ada beberapa faktor penting yang perlu diperhatikan seperti efisiensi baterai 5000 mAh dan dukungan update sistem operasi minimal 2 tahun.</p>
            <h2>Pertanyaan yang Sering Diajukan (FAQ)</h2>
            <h3>Apakah HP 2 jutaan di tahun 2026 sudah mendukung jaringan 5G?</h3>
            <p>Ya, mayoritas smartphone keluaran 2026 di rentang harga 2 jutaan telah dilengkapi modem 5G terintegrasi.</p>
            <h3>Berapa lama rata-rata daya tahan baterai untuk penggunaan harian?</h3>
            <p>Dengan kapasitas standar 5000 mAh, daya tahan rata-rata mencapai 1,5 hingga 2 hari untuk pemakaian normal.</p>
            """
            final_content = inject_schema_if_missing(
                html_content=raw_html,
                title=article_title,
                meta_description="Daftar rekomendasi HP 2 jutaan terbaik tahun 2026 dengan spesifikasi mantap, kamera jernih, dan baterai tahan lama.",
                author_name="Budi Creator Nusantara"
            )

            art = Article(
                user_id=creator.id,
                blog_id=blog_id,
                title=article_title,
                target_keyword="rekomendasi hp 2 jutaan terbaik 2026",
                meta_description="Daftar rekomendasi HP 2 jutaan terbaik tahun 2026 dengan spesifikasi mantap, kamera jernih, dan baterai tahan lama.",
                content_html=final_content,
                labels="Gadget, Smartphone, Rekomendasi",
                status="published",
                blogger_post_id="post_demo_9901",
                blogger_url="https://nusantaratech.blogspot.com/2026/10/hp-2-jutaan-terbaik.html"
            )
            db.add(art)
            print(f"✓ Created Creator Demo: {creator_email} with Blog & Articles.")

        db.commit()
        print("🎉 SaaS Demo Seeding Completed Successfully!")
    finally:
        db.close()

if __name__ == "__main__":
    seed()
