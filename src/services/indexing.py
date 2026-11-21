"""
Instant Indexing & Google WebSub (PubSubHubbub) Ping Service for Blogger Auto-Pilot SaaS.
Notifies Google's official WebSub hub whenever an article is published live, accelerating search crawling.
"""

import logging
import urllib.parse
from typing import Optional, Dict, Any

import httpx

logger = logging.getLogger(__name__)

WEBSUB_HUB_URL = "https://pubsubhubbub.appspot.com/"

class IndexingAdapter:
    """Base interface for indexing ping adapters (enables clean testing)."""
    def ping(self, feed_url: str, post_url: Optional[str] = None) -> Dict[str, Any]:
        raise NotImplementedError

class GoogleWebSubAdapter(IndexingAdapter):
    """Production adapter that pings Google's PubSubHubbub / WebSub hub."""
    def __init__(self, timeout: float = 5.0):
        self.timeout = timeout

    def ping(self, feed_url: str, post_url: Optional[str] = None) -> Dict[str, Any]:
        if not feed_url:
            return {"success": False, "error": "Feed URL kosong", "status_code": None}

        payload = {
            "hub.mode": "publish",
            "hub.url": feed_url
        }
        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.post(WEBSUB_HUB_URL, data=payload)
                # Google WebSub returns 204 No Content on success
                ok = resp.status_code in (200, 202, 204)
                return {
                    "success": ok,
                    "hub_url": WEBSUB_HUB_URL,
                    "feed_url": feed_url,
                    "post_url": post_url,
                    "status_code": resp.status_code
                }
        except Exception as e:
            logger.warning(f"[INDEXING] WebSub ping failed for {feed_url}: {e}")
            return {
                "success": False,
                "hub_url": WEBSUB_HUB_URL,
                "feed_url": feed_url,
                "post_url": post_url,
                "status_code": None,
                "error": str(e)
            }

class InMemoryIndexingAdapter(IndexingAdapter):
    """Test double that records pings without making external network requests."""
    def __init__(self):
        self.pings: list[Dict[str, Any]] = []

    def ping(self, feed_url: str, post_url: Optional[str] = None) -> Dict[str, Any]:
        record = {
            "success": True,
            "hub_url": WEBSUB_HUB_URL,
            "feed_url": feed_url,
            "post_url": post_url,
            "status_code": 204
        }
        self.pings.append(record)
        return record

_current_adapter: IndexingAdapter = GoogleWebSubAdapter()

def get_indexing_adapter() -> IndexingAdapter:
    return _current_adapter

def set_indexing_adapter(adapter: IndexingAdapter) -> None:
    global _current_adapter
    _current_adapter = adapter

def build_blogger_feed_url(blog_url: Optional[str]) -> Optional[str]:
    """Derives the official Blogger Atom feed URL from a blog base URL."""
    if not blog_url:
        return None
    clean_url = blog_url.strip().rstrip("/")
    if not clean_url.startswith(("http://", "https://")):
        clean_url = "https://" + clean_url
    parsed = urllib.parse.urlparse(clean_url)
    if not parsed.netloc:
        return None
    base = f"{parsed.scheme}://{parsed.netloc}"
    return f"{base}/feeds/posts/default"

def ping_websub_for_blog(blog_url: Optional[str], post_url: Optional[str] = None) -> Dict[str, Any]:
    """
    Triggers a non-blocking WebSub ping for a Blogger site when a live post is published.
    Safe to call in route handlers; errors are caught and returned cleanly.
    """
    feed_url = build_blogger_feed_url(blog_url)
    if not feed_url:
        return {"success": False, "error": "URL blog belum dikonfigurasi"}
    return get_indexing_adapter().ping(feed_url=feed_url, post_url=post_url)

