"""
Subscriber & Client-Facing Analytics & ROI Reporting Router
Provides ROI calculations, productivity metrics, and printable/PDF reports for agencies and creators.
"""

import re
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from sqlalchemy import desc

from db_saas import get_saas_db
from models_saas import User, Blog, Article, Keyword, AuditLog
from dependencies import get_session_user

router = APIRouter(tags=["Analytics & ROI"])

def strip_tags_and_count_words(html_text: str) -> int:
    if not html_text:
        return 0
    clean = re.sub(r'<[^>]+>', ' ', html_text)
    words = clean.split()
    return len(words)

def format_rupiah(amount: int) -> str:
    return f"Rp {amount:,.0f}".replace(",", ".")

@router.get('/api/analytics/roi')
def get_analytics_roi(
    request: Request,
    blog_id: Optional[str] = Query(None),
    db: Session = Depends(get_saas_db)
):
    user = get_session_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Sesi telah berakhir. Silakan login kembali.")

    art_query = db.query(Article).filter(Article.user_id == user.id)
    kw_query = db.query(Keyword).filter(Keyword.user_id == user.id)

    if blog_id:
        art_query = art_query.filter(Article.blog_id == blog_id)
        kw_query = kw_query.filter(Keyword.blog_id == blog_id)

    articles = art_query.all()
    keywords = kw_query.all()

    total_articles = len(articles)
    published_count = sum(1 for a in articles if a.status == 'published')
    draft_count = sum(1 for a in articles if a.status in ['draft', 'blogger_draft'])
    review_count = sum(1 for a in articles if a.status == 'pending_review')

    total_words = sum(strip_tags_and_count_words(a.content_html) for a in articles)
    
    # 3.5 hrs per live published article, 1.2 hrs per researched draft
    hours_saved = round((published_count * 3.5) + (draft_count * 1.2), 1)
    # Market standard IDR 150/word for SEO content writing in Indonesia
    cost_saved_idr = total_words * 150

    kw_planned = sum(1 for k in keywords if k.status == 'planned')
    kw_used = sum(1 for k in keywords if k.status == 'used')
    kw_in_progress = sum(1 for k in keywords if k.status == 'in_progress')

    success_rate = round((published_count / max(1, total_articles)) * 100, 1)

    # Recent activity from audit logs
    recent_logs = db.query(AuditLog).filter(
        AuditLog.user_id == user.id
    ).order_by(desc(AuditLog.created_at)).limit(8).all()

    activity = []
    for l in recent_logs:
        activity.append({
            "event_type": l.event_type,
            "entity_id": l.entity_id,
            "created_at": l.created_at.strftime("%d %b %H:%M") if l.created_at else "-"
        })

    return {
        "success": True,
        "metrics": {
            "total_articles": total_articles,
            "published_count": published_count,
            "draft_count": draft_count,
            "review_count": review_count,
            "total_words": total_words,
            "hours_saved": hours_saved,
            "cost_saved_idr": cost_saved_idr,
            "cost_saved_formatted": format_rupiah(cost_saved_idr),
            "success_rate_percent": success_rate,
            "keywords": {
                "total": len(keywords),
                "planned": kw_planned,
                "in_progress": kw_in_progress,
                "used": kw_used
            }
        },
        "recent_activity": activity
    }

@router.get('/api/analytics/report', response_class=HTMLResponse)
def get_printable_roi_report(
    request: Request,
    blog_id: Optional[str] = Query(None),
    db: Session = Depends(get_saas_db)
):
    user = get_session_user(request, db)
    if not user:
        return HTMLResponse("<p>Sesi login diperlukan untuk mencetak laporan.</p>", status_code=401)

    # Active blog or selected
    blog = None
    if blog_id:
        blog = db.query(Blog).filter(Blog.id == blog_id, Blog.user_id == user.id).first()
    if not blog:
        blog = db.query(Blog).filter(Blog.user_id == user.id, Blog.is_active == 1).first() or db.query(Blog).filter(Blog.user_id == user.id).first()

    articles = db.query(Article).filter(Article.user_id == user.id).order_by(desc(Article.created_at)).all()
    total_articles = len(articles)
    published_count = sum(1 for a in articles if a.status == 'published')
    total_words = sum(strip_tags_and_count_words(a.content_html) for a in articles)
    hours_saved = round((published_count * 3.5) + ((total_articles - published_count) * 1.2), 1)
    cost_saved_idr = total_words * 150
    now_str = datetime.now().strftime("%d %B %Y, %H:%M WIB")

    article_rows = ""
    for idx, a in enumerate(articles[:25], 1):
        status_badge = '<span style="color:#059669;font-weight:600;">Published</span>' if a.status == 'published' else '<span style="color:#d97706;font-weight:600;">Draft</span>'
        words = strip_tags_and_count_words(a.content_html)
        article_rows += f"""
        <tr>
            <td style="padding:10px 14px;border-bottom:1px solid #e2e8f0;text-align:center;">{idx}</td>
            <td style="padding:10px 14px;border-bottom:1px solid #e2e8f0;font-weight:500;">{a.title}</td>
            <td style="padding:10px 14px;border-bottom:1px solid #e2e8f0;color:#64748b;">{a.target_keyword or '-'}</td>
            <td style="padding:10px 14px;border-bottom:1px solid #e2e8f0;text-align:right;">{words:,} kata</td>
            <td style="padding:10px 14px;border-bottom:1px solid #e2e8f0;text-align:center;">{status_badge}</td>
        </tr>
        """

    html = f"""<!DOCTYPE html>
<html lang="id">
<head>
    <meta charset="UTF-8">
    <title>Laporan Kinerja & ROI Konten SEO — {blog.name if blog else 'Blogger Auto-Pilot'}</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; color: #1e293b; background: #f8fafc; margin: 0; padding: 32px; }}
        .container {{ max-width: 900px; margin: 0 auto; background: #ffffff; border: 1px solid #e2e8f0; border-radius: 12px; padding: 40px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05); }}
        .header {{ display: flex; justify-content: space-between; align-items: flex-start; border-bottom: 2px solid #0284c7; padding-bottom: 20px; margin-bottom: 30px; }}
        .logo {{ font-size: 22px; font-weight: 800; color: #0284c7; }}
        .meta-text {{ font-size: 13px; color: #64748b; line-height: 1.6; text-align: right; }}
        .grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin-bottom: 32px; }}
        .card {{ background: #f1f5f9; border-radius: 8px; padding: 20px; border-left: 4px solid #0284c7; }}
        .card h4 {{ margin: 0 0 6px 0; font-size: 13px; color: #475569; text-transform: uppercase; letter-spacing: 0.05em; }}
        .card .val {{ font-size: 26px; font-weight: 800; color: #0f172a; margin: 0; }}
        .card .sub {{ font-size: 12px; color: #64748b; margin-top: 4px; }}
        table {{ width: 100%; border-collapse: collapse; font-size: 13px; margin-top: 16px; }}
        th {{ background: #f8fafc; color: #475569; font-weight: 600; text-align: left; padding: 10px 14px; border-bottom: 2px solid #cbd5e1; }}
        .actions {{ margin-bottom: 24px; display: flex; gap: 12px; }}
        .btn {{ padding: 10px 18px; border-radius: 6px; font-weight: 600; font-size: 14px; cursor: pointer; text-decoration: none; display: inline-block; }}
        .btn-primary {{ background: #0284c7; color: #ffffff; border: none; }}
        .btn-secondary {{ background: #ffffff; color: #334155; border: 1px solid #cbd5e1; }}
        @media print {{
            body {{ background: #ffffff; padding: 0; }}
            .container {{ border: none; box-shadow: none; padding: 0; }}
            .actions {{ display: none !important; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="actions">
            <button class="btn btn-primary" onclick="window.print()">🖨️ Cetak / Simpan ke PDF</button>
            <a href="/" class="btn btn-secondary">← Kembali ke Dashboard</a>
        </div>
        <div class="header">
            <div>
                <div class="logo">⚡ Blogger Auto-Pilot SaaS</div>
                <h1 style="font-size:24px;margin:8px 0 4px 0;color:#0f172a;">Laporan Kinerja & Estimasi ROI Konten</h1>
                <p style="margin:0;font-size:14px;color:#64748b;">Blog: <strong>{blog.name if blog else 'Semua Blog'}</strong> ({blog.url if blog and blog.url else 'Blogger Integration'})</p>
            </div>
            <div class="meta-text">
                Dibuat untuk: <strong>{user.full_name or user.email}</strong><br>
                Paket: <strong>{user.subscription.plan_tier.upper() if user.subscription else 'STARTER'}</strong><br>
                Waktu Cetak: {now_str}
            </div>
        </div>

        <div class="grid">
            <div class="card">
                <h4>Total Konten Dihasilkan</h4>
                <div class="val">{total_articles} Artikel</div>
                <div class="sub">{published_count} live terpublikasi | {total_words:,} total kata</div>
            </div>
            <div class="card" style="border-left-color:#10b981;">
                <h4>Estimasi Waktu Dihemat</h4>
                <div class="val">{hours_saved} Jam</div>
                <div class="sub">Setara ~{round(hours_saved / 8, 1)} hari kerja penuh penulis</div>
            </div>
            <div class="card" style="border-left-color:#f59e0b;">
                <h4>Nilai Efisiensi Anggaran</h4>
                <div class="val">{format_rupiah(cost_saved_idr)}</div>
                <div class="sub">Berdasarkan tarif standar copywriter IDR 150/kata</div>
            </div>
        </div>

        <h3 style="font-size:16px;color:#0f172a;margin-top:30px;">Daftar Konten & Riwayat Publikasi Terbaru</h3>
        <table>
            <thead>
                <tr>
                    <th style="width:40px;text-align:center;">#</th>
                    <th>Judul Artikel</th>
                    <th>Target Keyword SEO</th>
                    <th style="text-align:right;">Panjang</th>
                    <th style="text-align:center;">Status</th>
                </tr>
            </thead>
            <tbody>
                {article_rows if article_rows else '<tr><td colspan="5" style="text-align:center;padding:20px;color:#94a3b8;">Belum ada artikel yang dibuat.</td></tr>'}
            </tbody>
        </table>

        <div style="margin-top:40px;padding-top:20px;border-top:1px solid #e2e8f0;text-align:center;font-size:12px;color:#94a3b8;">
            Laporan ini dihasilkan secara otomatis oleh sistem kecerdasan buatan Blogger Auto-Pilot SaaS untuk keperluan evaluasi efisiensi tim dan pelaporan klien.
        </div>
    </div>
</body>
</html>
"""
    return HTMLResponse(content=html)
