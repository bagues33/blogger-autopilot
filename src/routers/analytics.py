"""
Subscriber & Client-Facing Analytics, White-Label Reporting & CSV Export Router
Provides ROI calculations, intent/production breakdowns, CSV exports, and white-label PDF reports.
"""

import csv
import io
import html as html_escape
import re
from datetime import datetime, timedelta, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import desc

from src.core.database import get_saas_db
from src.models.models import User, Blog, Article, Keyword, AuditLog
from src.core.dependencies import get_session_user, check_feature_access
from src.core.rbac import get_accessible_blogs, get_blog_effective_owner

router = APIRouter(tags=["Analytics & ROI"])

def strip_tags_and_count_words(html_text: str) -> int:
    if not html_text:
        return 0
    clean = re.sub(r'<[^>]+>', ' ', html_text)
    words = clean.split()
    return len(words)

def format_rupiah(amount: int) -> str:
    return f"Rp {amount:,.0f}".replace(",", ".")

def _resolve_scoped_blogs(user: User, blog_id: Optional[str], db: Session):
    accessible_blogs = get_accessible_blogs(user, db)
    if not accessible_blogs:
        return [], None

    if blog_id:
        target = next((b for b in accessible_blogs if b.id == blog_id), None)
        if not target:
            raise HTTPException(status_code=403, detail="Anda tidak memiliki izin akses ke blog ini.")
        return [target.id], target

    return [b.id for b in accessible_blogs], None

@router.get('/api/analytics/roi')
def get_analytics_roi(
    request: Request,
    blog_id: Optional[str] = Query(None),
    db: Session = Depends(get_saas_db)
):
    user = get_session_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Sesi telah berakhir. Silakan login kembali.")

    scoped_ids, target_blog = _resolve_scoped_blogs(user, blog_id, db)

    if not scoped_ids:
        articles = []
        keywords = []
    else:
        articles = db.query(Article).filter(Article.blog_id.in_(scoped_ids)).all()
        keywords = db.query(Keyword).filter(Keyword.blog_id.in_(scoped_ids)).all()

    total_articles = len(articles)
    published_count = sum(1 for a in articles if a.status == 'published')
    draft_count = sum(1 for a in articles if a.status in ['draft', 'blogger_draft'])
    review_count = sum(1 for a in articles if a.status == 'pending_review')
    approved_count = sum(1 for a in articles if a.status == 'approved')

    total_words = sum(strip_tags_and_count_words(a.content_html) for a in articles)

    # 3.5 hrs per live published article, 1.2 hrs per researched draft
    hours_saved = round((published_count * 3.5) + ((total_articles - published_count) * 1.2), 1)
    # Market standard IDR 150/word for SEO content writing in Indonesia
    cost_saved_idr = total_words * 150

    kw_planned = sum(1 for k in keywords if k.status == 'planned')
    kw_used = sum(1 for k in keywords if k.status == 'used')
    kw_in_progress = sum(1 for k in keywords if k.status == 'in_progress')

    # Search intent breakdown
    intent_counts = {
        "Informational": 0,
        "Commercial": 0,
        "Transactional": 0,
        "Other": 0
    }
    for k in keywords:
        intent = (k.search_intent or "Informational").strip().capitalize()
        if intent in intent_counts:
            intent_counts[intent] += 1
        else:
            intent_counts["Other"] += 1

    # Last 7 days production trend
    today = datetime.now(timezone.utc).date()
    daily_buckets = {}
    for offset in range(6, -1, -1):
        d = today - timedelta(days=offset)
        daily_buckets[d.isoformat()] = {"label": d.strftime("%d %b"), "count": 0}

    for a in articles:
        if a.created_at:
            d_str = a.created_at.date().isoformat()
            if d_str in daily_buckets:
                daily_buckets[d_str]["count"] += 1

    weekly_production = list(daily_buckets.values())

    success_rate = round((published_count / max(1, total_articles)) * 100, 1)

    # Recent activity from audit logs
    recent_logs = db.query(AuditLog).filter(
        AuditLog.user_id == user.id
    ).order_by(desc(AuditLog.created_at)).limit(8).all()

    activity = [
        {
            "event_type": l.event_type,
            "entity_id": l.entity_id,
            "created_at": l.created_at.strftime("%d %b %H:%M") if l.created_at else "-"
        }
        for l in recent_logs
    ]

    return {
        "success": True,
        "scope_blog_name": target_blog.name if target_blog else "Semua Blog",
        "metrics": {
            "total_articles": total_articles,
            "published_count": published_count,
            "draft_count": draft_count,
            "review_count": review_count,
            "approved_count": approved_count,
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
            },
            "intent_distribution": intent_counts,
            "weekly_production": weekly_production
        },
        "recent_activity": activity
    }

@router.get('/api/analytics/export-csv')
def export_articles_csv(
    request: Request,
    blog_id: Optional[str] = Query(None),
    db: Session = Depends(get_saas_db)
):
    user = get_session_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Sesi telah berakhir. Silakan login kembali.")

    scoped_ids, target_blog = _resolve_scoped_blogs(user, blog_id, db)

    # Feature Gating: Pro / Agency or team member on Pro/Agency blog
    has_export = check_feature_access(user, 'export_backup')
    if not has_export and target_blog:
        owner = get_blog_effective_owner(target_blog, db)
        if owner:
            has_export = check_feature_access(owner, 'export_backup')
    if not has_export:
        raise HTTPException(
            status_code=403,
            detail="Fitur ekspor laporan CSV memerlukan paket Pro Publisher atau Agency Network. Silakan upgrade paket Anda."
        )

    if not scoped_ids:
        articles = []
    else:
        articles = db.query(Article).filter(Article.blog_id.in_(scoped_ids)).order_by(desc(Article.created_at)).all()

    output = io.StringIO()
    # UTF-8 BOM for clean Excel opening
    output.write('\ufeff')
    writer = csv.writer(output)
    writer.writerow([
        "No", "Blog", "Judul Artikel", "Target Keyword", "Status",
        "Jumlah Kata", "Penulis", "Tanggal Dibuat", "URL Live Blogger"
    ])

    blogs_map = {b.id: b.name for b in get_accessible_blogs(user, db)}

    for idx, a in enumerate(articles, 1):
        words = strip_tags_and_count_words(a.content_html)
        author_label = (a.author.full_name or a.author.email) if a.author else "SEO AI Specialist"
        created_str = a.created_at.strftime("%Y-%m-%d %H:%M") if a.created_at else "-"
        writer.writerow([
            idx,
            blogs_map.get(a.blog_id, a.blog_id),
            a.title,
            a.target_keyword or "-",
            a.status,
            words,
            author_label,
            created_str,
            a.blogger_url or "-"
        ])

    output.seek(0)
    slug = re.sub(r'[^a-zA-Z0-9_-]', '_', (target_blog.name if target_blog else "semua_blog")).lower()
    date_tag = datetime.now().strftime("%Y%m%d")
    filename = f"laporan_konten_{slug}_{date_tag}.csv"

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )

@router.get('/api/analytics/report', response_class=HTMLResponse)
def get_printable_roi_report(
    request: Request,
    blog_id: Optional[str] = Query(None),
    agency_name: Optional[str] = Query(None),
    db: Session = Depends(get_saas_db)
):
    user = get_session_user(request, db)
    if not user:
        return HTMLResponse("<p>Sesi login diperlukan untuk mencetak laporan.</p>", status_code=401)

    accessible_blogs = get_accessible_blogs(user, db)
    blog = None
    if blog_id:
        blog = next((b for b in accessible_blogs if b.id == blog_id), None)
    if not blog and accessible_blogs:
        blog = next((b for b in accessible_blogs if b.is_active == 1), accessible_blogs[0])

    if blog:
        articles = db.query(Article).filter(Article.blog_id == blog.id).order_by(desc(Article.created_at)).all()
    else:
        articles = []

    total_articles = len(articles)
    published_count = sum(1 for a in articles if a.status == 'published')
    total_words = sum(strip_tags_and_count_words(a.content_html) for a in articles)
    hours_saved = round((published_count * 3.5) + ((total_articles - published_count) * 1.2), 1)
    cost_saved_idr = total_words * 150
    now_str = datetime.now().strftime("%d %B %Y, %H:%M WIB")

    # White-Label Branding (Gated to Pro / Agency or team members on Pro/Agency blog)
    can_whitelabel = check_feature_access(user, 'export_backup')
    if not can_whitelabel and blog:
        owner = get_blog_effective_owner(blog, db)
        if owner:
            can_whitelabel = check_feature_access(owner, 'export_backup')

    is_whitelabel = can_whitelabel and bool(agency_name and agency_name.strip())
    brand_title = html_escape.escape(agency_name.strip()) if is_whitelabel else "⚡ Blogger Auto-Pilot SaaS"
    footer_text = (
        f"Laporan Kinerja Konten SEO — Disusun oleh {brand_title}."
        if is_whitelabel
        else "Laporan ini dihasilkan secara otomatis oleh platform Blogger Auto-Pilot SaaS untuk keperluan evaluasi efisiensi tim dan pelaporan klien."
    )

    article_rows = ""
    for idx, a in enumerate(articles[:50], 1):
        status_map = {
            'published': '<span style="color:#059669;font-weight:600;">Published</span>',
            'approved': '<span style="color:#4f46e5;font-weight:600;">Approved</span>',
            'pending_review': '<span style="color:#d97706;font-weight:600;">Review</span>',
            'blogger_draft': '<span style="color:#0284c7;font-weight:600;">Blogger Draft</span>',
        }
        status_badge = status_map.get(a.status, '<span style="color:#64748b;font-weight:600;">Draft</span>')
        words = strip_tags_and_count_words(a.content_html)
        safe_title = html_escape.escape(a.title or "")
        safe_kw = html_escape.escape(a.target_keyword or "-")
        link_html = f'<br><a href="{html_escape.escape(a.blogger_url)}" target="_blank" style="font-size:11px;color:#0284c7;text-decoration:none;">{html_escape.escape(a.blogger_url)}</a>' if a.blogger_url else ''
        article_rows += f"""
        <tr>
            <td style="padding:10px 14px;border-bottom:1px solid #e2e8f0;text-align:center;">{idx}</td>
            <td style="padding:10px 14px;border-bottom:1px solid #e2e8f0;font-weight:500;">{safe_title}{link_html}</td>
            <td style="padding:10px 14px;border-bottom:1px solid #e2e8f0;color:#64748b;">{safe_kw}</td>
            <td style="padding:10px 14px;border-bottom:1px solid #e2e8f0;text-align:right;">{words:,} kata</td>
            <td style="padding:10px 14px;border-bottom:1px solid #e2e8f0;text-align:center;">{status_badge}</td>
        </tr>
        """

    safe_blog_name = html_escape.escape(blog.name if blog else 'Semua Blog')
    safe_blog_url = html_escape.escape(blog.url if blog and blog.url else 'Blogger Integration')
    safe_user_name = html_escape.escape(user.full_name or user.email)

    html = f"""<!DOCTYPE html>
<html lang="id">
<head>
    <meta charset="UTF-8">
    <title>Laporan Kinerja & ROI Konten SEO — {safe_blog_name}</title>
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
            <a href="/dashboard" class="btn btn-secondary">← Kembali ke Dashboard</a>
        </div>
        <div class="header">
            <div>
                <div class="logo">{brand_title}</div>
                <h1 style="font-size:24px;margin:8px 0 4px 0;color:#0f172a;">Laporan Kinerja & Estimasi ROI Konten</h1>
                <p style="margin:0;font-size:14px;color:#64748b;">Blog Klien: <strong>{safe_blog_name}</strong> ({safe_blog_url})</p>
            </div>
            <div class="meta-text">
                Disusun untuk: <strong>{safe_user_name}</strong><br>
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
                    <th>Judul Artikel & Tautan Live</th>
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
            {footer_text}
        </div>
    </div>
</body>
</html>
"""
    return HTMLResponse(content=html)
