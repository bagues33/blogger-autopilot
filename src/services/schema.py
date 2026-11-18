"""
SEO Schema & Structured Data Auto-Injector
Generates Google E-E-A-T compliant JSON-LD Schema (Article & FAQPage)
to guarantee rich search snippets and high CTR on Google Search.
"""

import re
import json
from typing import Optional, List, Dict, Any

def extract_faq_qa_pairs(html_content: str) -> List[Dict[str, str]]:
    """
    Scans HTML for FAQ questions (headings ending with ? or FAQ sections)
    and extracts Question & Answer pairs.
    """
    qa_pairs = []
    
    # Pattern 1: Heading followed by paragraph (h2/h3/h4/strong containing '?')
    heading_pattern = re.compile(
        r'<h[2-4][^>]*>(.*?(\?|&#63;).*?)</h[2-4]>\s*(?:<p[^>]*>(.*?)</p>)+',
        re.IGNORECASE | re.DOTALL
    )
    for match in heading_pattern.finditer(html_content):
        raw_q = match.group(1)
        raw_a = match.group(3)
        # Strip HTML tags
        clean_q = re.sub(r'<[^>]+>', '', raw_q).strip()
        clean_a = re.sub(r'<[^>]+>', '', raw_a).strip()
        if len(clean_q) > 5 and len(clean_a) > 10:
            qa_pairs.append({'question': clean_q, 'answer': clean_a})

    # Pattern 2: Explicit FAQ item structure (e.g. bold question followed by answer)
    if not qa_pairs:
        bold_pattern = re.compile(
            r'<p><strong>(?:Q:|Pertanyaan:)?\s*(.*?(\?|&#63;).*?)</strong></p>\s*<p>(?:A:|Jawaban:)?\s*(.*?)</p>',
            re.IGNORECASE | re.DOTALL
        )
        for match in bold_pattern.finditer(html_content):
            raw_q = match.group(1)
            raw_a = match.group(3)
            clean_q = re.sub(r'<[^>]+>', '', raw_q).strip()
            clean_a = re.sub(r'<[^>]+>', '', raw_a).strip()
            if len(clean_q) > 5 and len(clean_a) > 10:
                qa_pairs.append({'question': clean_q, 'answer': clean_a})

    return qa_pairs[:5] # Max 5 FAQ items for clean schema

def generate_json_ld_schema(
    title: str,
    meta_description: Optional[str] = None,
    url: Optional[str] = None,
    author_name: str = "Tim Editorial SEO",
    publisher_name: str = "Bagus Tech Media",
    faq_items: Optional[List[Dict[str, str]]] = None
) -> str:
    """
    Builds a JSON-LD script containing Article and FAQPage schema.
    """
    graph = []

    # 1. Article Schema
    article_schema = {
        "@type": "Article",
        "headline": title,
        "description": meta_description or title,
        "author": {
            "@type": "Person",
            "name": author_name
        },
        "publisher": {
            "@type": "Organization",
            "name": publisher_name
        }
    }
    if url:
        article_schema["mainEntityOfPage"] = url

    graph.append(article_schema)

    # 2. FAQPage Schema (if FAQ items exist)
    if faq_items and len(faq_items) > 0:
        faq_entities = []
        for item in faq_items:
            faq_entities.append({
                "@type": "Question",
                "name": item['question'],
                "acceptedAnswer": {
                    "@type": "Answer",
                    "text": item['answer']
                }
            })
        
        faq_schema = {
            "@type": "FAQPage",
            "mainEntity": faq_entities
        }
        graph.append(faq_schema)

    schema_data = {
        "@context": "https://schema.org",
        "@graph": graph
    }

    json_str = json.dumps(schema_data, ensure_ascii=False, indent=2)
    return f'\n<script type="application/ld+json">\n{json_str}\n</script>\n'

def inject_schema_if_missing(
    html_content: str,
    title: str,
    meta_description: Optional[str] = None,
    url: Optional[str] = None,
    author_name: str = "Tim Editorial SEO"
) -> str:
    """
    Checks if HTML content already has schema.org structured data.
    If missing, automatically extracts FAQs, builds schema, and injects it.
    """
    if "application/ld+json" in html_content and "schema.org" in html_content:
        return html_content # Already has structured data

    faqs = extract_faq_qa_pairs(html_content)
    schema_block = generate_json_ld_schema(
        title=title,
        meta_description=meta_description,
        url=url,
        author_name=author_name,
        faq_items=faqs
    )

    return html_content.strip() + "\n" + schema_block
