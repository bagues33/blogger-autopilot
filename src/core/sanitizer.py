"""
Server-side HTML Sanitizer for Blogger Auto-Pilot SaaS
Neutralizes XSS payloads (<script>, <iframe>, event handlers, javascript: URIs) from
user-edited articles and LLM outputs while safely preserving SEO JSON-LD schema blocks
and standard Blogger editorial formatting.
"""

import re
import json
import html as html_lib
from html.parser import HTMLParser
from urllib.parse import urlparse

_BLOCKED_TAGS = frozenset({
    "script", "iframe", "object", "embed", "applet", "form", "input",
    "textarea", "button", "select", "option", "meta", "link", "base",
    "svg", "math", "style", "noscript", "template", "frame", "frameset"
})

_VOID_TAGS = frozenset({
    "area", "base", "br", "col", "embed", "hr", "img", "input",
    "link", "meta", "param", "source", "track", "wbr"
})

_URL_ATTRS = frozenset({"href", "src", "action", "poster", "cite", "data", "formaction"})
_SAFE_URL_SCHEMES = frozenset({"http", "https", "mailto", ""})
_SAFE_DATA_IMG_RE = re.compile(r"^data:image/(png|jpeg|jpg|webp|gif);base64,[A-Za-z0-9+/=\s]+$", re.I)
_UNSAFE_STYLE_RE = re.compile(r"(javascript\s*:|vbscript\s*:|expression\s*\(|url\s*\(\s*['\"]?\s*(javascript|vbscript|data:text))", re.I)


def _is_safe_url(value: str) -> bool:
    cleaned = re.sub(r"[\x00-\x20\x7f]+", "", (value or "")).strip()
    if not cleaned:
        return True
    if cleaned.startswith(("/", "#")):
        return True
    if _SAFE_DATA_IMG_RE.match(cleaned):
        return True
    try:
        parsed = urlparse(cleaned)
        return (parsed.scheme or "").lower() in _SAFE_URL_SCHEMES
    except Exception:
        return False


class _ArticleHTMLSanitizer(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.out = []
        self._skip_depth = 0
        self._in_jsonld = False
        self._jsonld_buf = []

    def handle_starttag(self, tag, attrs):
        t = tag.lower()

        if self._in_jsonld:
            return

        if t == "script":
            attr_map = {k.lower(): (v or "") for k, v in attrs}
            if attr_map.get("type", "").strip().lower() == "application/ld+json":
                self._in_jsonld = True
                self._jsonld_buf = []
                return
            self._skip_depth += 1
            return

        if t in _BLOCKED_TAGS:
            if t not in _VOID_TAGS:
                self._skip_depth += 1
            return

        if self._skip_depth > 0:
            return

        safe_attrs = []
        for raw_k, raw_v in attrs:
            k = (raw_k or "").strip().lower()
            if not k:
                continue
            # Strip all inline JS event handlers and dangerous attributes
            if k.startswith("on") or k in ("srcdoc", "formaction", "xlink:href"):
                continue
            v = raw_v if raw_v is not None else ""
            if k in _URL_ATTRS and not _is_safe_url(v):
                continue
            if k == "style" and _UNSAFE_STYLE_RE.search(v):
                continue
            escaped_v = html_lib.escape(v, quote=True)
            safe_attrs.append(f' {k}="{escaped_v}"')

        self.out.append(f"<{t}{''.join(safe_attrs)}>")

    def handle_startendtag(self, tag, attrs):
        t = tag.lower()
        if self._in_jsonld or self._skip_depth > 0 or t in _BLOCKED_TAGS:
            return
        safe_attrs = []
        for raw_k, raw_v in attrs:
            k = (raw_k or "").strip().lower()
            if not k or k.startswith("on") or k in ("srcdoc", "formaction", "xlink:href"):
                continue
            v = raw_v if raw_v is not None else ""
            if k in _URL_ATTRS and not _is_safe_url(v):
                continue
            if k == "style" and _UNSAFE_STYLE_RE.search(v):
                continue
            safe_attrs.append(f' {k}="{html_lib.escape(v, quote=True)}"')
        self.out.append(f"<{t}{''.join(safe_attrs)} />")

    def handle_endtag(self, tag):
        t = tag.lower()
        if t == "script" and self._in_jsonld:
            raw_json = "".join(self._jsonld_buf).strip()
            self._in_jsonld = False
            self._jsonld_buf = []
            # Only emit valid JSON-LD and escape </ to prevent script-tag breakout
            try:
                parsed = json.loads(raw_json)
                safe_json = json.dumps(parsed, ensure_ascii=False).replace("</", "<\\/")
                self.out.append(f'<script type="application/ld+json">{safe_json}</script>')
            except Exception:
                pass
            return

        if t in _BLOCKED_TAGS:
            if t not in _VOID_TAGS and self._skip_depth > 0:
                self._skip_depth -= 1
            return

        if self._skip_depth > 0:
            return

        if t not in _VOID_TAGS:
            self.out.append(f"</{t}>")

    def handle_data(self, data):
        if self._in_jsonld:
            self._jsonld_buf.append(data)
            return
        if self._skip_depth > 0:
            return
        self.out.append(data)

    def handle_entityref(self, name):
        if self._in_jsonld:
            self._jsonld_buf.append(f"&{name};")
            return
        if self._skip_depth > 0:
            return
        self.out.append(f"&{name};")

    def handle_charref(self, name):
        if self._in_jsonld:
            self._jsonld_buf.append(f"&#{name};")
            return
        if self._skip_depth > 0:
            return
        self.out.append(f"&#{name};")


def sanitize_article_html(html_content: str) -> str:
    """
    Sanitizes article HTML against Stored XSS and LLM prompt-injection markup
    while retaining safe formatting and valid JSON-LD SEO schema.
    """
    if not html_content:
        return ""
    parser = _ArticleHTMLSanitizer()
    parser.feed(html_content)
    parser.close()
    return "".join(parser.out)
