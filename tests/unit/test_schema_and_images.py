"""
Unit tests for SEO schema auto-injector and image optimization.
"""
import io
import pytest
from PIL import Image

from src.services.schema import (
    extract_faq_qa_pairs,
    generate_json_ld_schema,
    inject_schema_if_missing
)
from src.services.images import optimize_to_webp

def test_extract_faq_qa_pairs():
    sample_html = """
    <h2>Pengantar Panduan</h2>
    <p>Ini adalah artikel komprehensif tentang topik teknologi.</p>
    <h2>Pertanyaan yang Sering Diajukan</h2>
    <h3>Berapa biaya pembuatan blog profesional?</h3>
    <p>Biaya pembuatan blog berkisar antara Rp 100.000 hingga Rp 1.000.000 tergantung domain dan hosting.</p>
    <h3>Apakah Google Blogger gratis selamanya?</h3>
    <p>Ya, Google Blogger sepenuhnya gratis tanpa biaya bulanan.</p>
    """
    faqs = extract_faq_qa_pairs(sample_html)
    assert len(faqs) == 2
    assert "biaya" in faqs[0]["question"].lower()
    assert "blogger" in faqs[1]["question"].lower()

def test_inject_schema_if_missing():
    sample_html = """
    <h2>Pengantar Panduan</h2>
    <p>Ini adalah artikel komprehensif tentang topik teknologi.</p>
    <h3>Apakah ini ramah SEO?</h3>
    <p>Ya, artikel ini terstruktur dengan schema JSON-LD otomatis.</p>
    """
    injected = inject_schema_if_missing(
        sample_html,
        title="Panduan Lengkap Blogger 2026",
        meta_description="Deskripsi singkat panduan lengkap",
        author_name="Pakar SEO"
    )
    assert "application/ld+json" in injected
    assert "schema.org" in injected
    assert "FAQPage" in injected
    assert "Article" in injected

def test_optimize_to_webp():
    # Create a small RGB image in memory
    img = Image.new("RGB", (100, 100), color="blue")
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format="PNG")
    png_bytes = img_byte_arr.getvalue()

    webp_bytes = optimize_to_webp(png_bytes, max_width=50, quality=80)
    assert len(webp_bytes) > 0
    # Verify the output is a valid WebP image
    out_img = Image.open(io.BytesIO(webp_bytes))
    assert out_img.format == "WEBP"
    assert out_img.width == 50

