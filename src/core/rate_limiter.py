"""
Lightweight In-Memory Sliding Window Rate Limiter
Protects authentication endpoints against brute-force and DDoS attacks.
Zero external dependencies.
"""

import time
from typing import Dict, List, Tuple
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse

class InMemoryRateLimiter:
    def __init__(self):
        # Maps key -> list of timestamps
        self.requests: Dict[str, List[float]] = {}
        self.last_cleanup = time.time()

    def _cleanup_old_entries(self):
        now = time.time()
        if now - self.last_cleanup > 300: # Every 5 minutes
            cutoff = now - 600
            for k in list(self.requests.keys()):
                self.requests[k] = [t for t in self.requests[k] if t > cutoff]
                if not self.requests[k]:
                    del self.requests[k]
            self.last_cleanup = now

    def is_rate_limited(self, key: str, max_requests: int, window_seconds: int) -> Tuple[bool, int]:
        """
        Returns (is_limited, retry_after_seconds)
        """
        self._cleanup_old_entries()
        now = time.time()
        cutoff = now - window_seconds

        timestamps = [t for t in self.requests.get(key, []) if t > cutoff]
        if len(timestamps) >= max_requests:
            retry_after = int(timestamps[0] + window_seconds - now) + 1
            return True, max(1, retry_after)

        timestamps.append(now)
        self.requests[key] = timestamps
        return False, 0

limiter = InMemoryRateLimiter()

class ConcurrencyLimiter:
    """
    Limits simultaneous long-running operations (like LLM content generation) per tenant/user.
    """
    def __init__(self, max_concurrent: int = 2):
        self.max_concurrent = max_concurrent
        self.in_flight: Dict[str, int] = {}

    def acquire(self, key: str) -> bool:
        current = self.in_flight.get(key, 0)
        if current >= self.max_concurrent:
            return False
        self.in_flight[key] = current + 1
        return True

    def release(self, key: str):
        if key in self.in_flight:
            self.in_flight[key] = max(0, self.in_flight[key] - 1)
            if self.in_flight[key] == 0:
                del self.in_flight[key]

concurrency_limiter = ConcurrencyLimiter(max_concurrent=2)

def check_concurrency(key: str, max_concurrent: int = 2):
    if not concurrency_limiter.acquire(key):
        raise HTTPException(
            status_code=429,
            detail="Tugas pembuatan artikel sedang berjalan untuk akun Anda. Silakan tunggu tugas selesai sebelum memicu yang baru.",
            headers={"Retry-After": "5"}
        )

def release_concurrency(key: str):
    concurrency_limiter.release(key)

def get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"

def check_rate_limit(request: Request, max_requests: int = 15, window_seconds: int = 60, endpoint_tag: str = "auth"):
    """
    Helper function to check rate limits inside FastAPI endpoints.
    """
    ip = get_client_ip(request)
    key = f"{endpoint_tag}:{ip}"
    is_limited, retry_after = limiter.is_rate_limited(key, max_requests, window_seconds)
    if is_limited:
        raise HTTPException(
            status_code=429,
            detail=f"Terlalu banyak permintaan. Silakan tunggu {retry_after} detik sebelum mencoba kembali.",
            headers={"Retry-After": str(retry_after)}
        )
