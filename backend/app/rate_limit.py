import os
import threading
import time
from collections import defaultdict
from typing import DefaultDict, List, Optional, Tuple

from fastapi import HTTPException, Request, status


_lock = threading.Lock()
_buckets: DefaultDict[str, List[float]] = defaultdict(list)


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _window_seconds() -> int:
    value = os.getenv("COMPLIANCE_RATE_LIMIT_WINDOW_SECONDS", "60")
    try:
        return max(1, int(value))
    except ValueError:
        return 60


def _category_limit(category: str) -> int:
    if category == "invite_status":
        value = os.getenv("COMPLIANCE_RATE_LIMIT_INVITE_STATUS_MAX_REQUESTS", "30")
    else:
        value = os.getenv("COMPLIANCE_RATE_LIMIT_AUTH_MAX_REQUESTS", "10")
    try:
        return max(1, int(value))
    except ValueError:
        return 10


def _is_enabled() -> bool:
    return _env_bool("COMPLIANCE_RATE_LIMIT_ENABLED", True)


def _cleanup_bucket(bucket: List[float], now: float, window: int) -> None:
    cutoff = now - window
    while bucket and bucket[0] < cutoff:
        bucket.pop(0)


def get_request_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "").strip()
    if forwarded:
        first = forwarded.split(",", 1)[0].strip()
        if first:
            return first

    if request.client and request.client.host:
        return request.client.host

    return "unknown"


def enforce_rate_limit(category: str, identifier: str) -> None:
    if not _is_enabled():
        return

    window = _window_seconds()
    limit = _category_limit(category)
    key = f"{category}:{identifier}"
    now = time.time()

    with _lock:
        bucket = _buckets[key]
        _cleanup_bucket(bucket, now, window)
        if len(bucket) >= limit:
            retry_after = max(1, int(window - (now - bucket[0])))
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded. Please retry shortly.",
                headers={"Retry-After": str(retry_after)},
            )
        bucket.append(now)


def reset_rate_limits() -> None:
    with _lock:
        _buckets.clear()
