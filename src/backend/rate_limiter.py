# src/backend/rate_limiter.py
"""
AUDIT FIX (muc 15 - Security): Rate limiting cho cac endpoint nhay cam
(dang nhap, redeem invite code) — truoc audit KHONG co bat ky rate limit
nao, cho phep brute-force khong gioi han so lan thu.

Tai sao khong dung flask-limiter truc tiep:
    Toan bo app la MOT Dash app — moi callback (login, redeem code, filter,
    chart...) deu POST vao CUNG MOT endpoint Flask `/_dash-update-component`.
    flask-limiter gan rate limit theo route se limit ca nhung callback vo
    hai (vd keo filter) chung voi callback nhay cam (login) tren cung 1
    endpoint -> khong the phan biet. Vi vay rate limit duoc ap dung THU CONG
    ngay ben trong tung callback nhay cam, dua tren client IP.

Thiet ke:
    - Dung diskcache (da la dependency co san cho background_callback_manager
      trong app_instance.py) de luu so lan thu trong 1 cua so thoi gian
      (sliding window don gian bang danh sach timestamp).
    - Fixed-window/sliding-window dam bao hoat dong dung ca khi Docker/HF
      Space restart (persist tren disk) va ca khi co nhieu gunicorn worker
      (diskcache an toan cho multi-process, khong nhu dict trong RAM).

Cach dung:
    from src.backend.rate_limiter import check_rate_limit, reset_rate_limit

    allowed, retry_after = check_rate_limit(f"login:{client_ip}", max_attempts=5, window_seconds=300)
    if not allowed:
        return error_message_with(retry_after)
    ...
    if login_success:
        reset_rate_limit(f"login:{client_ip}:{username}")
"""
import os
import time
import logging

from diskcache import Cache

logger = logging.getLogger(__name__)

_CACHE_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "cache", "rate_limit"
)
os.makedirs(_CACHE_DIR, exist_ok=True)
_cache = Cache(_CACHE_DIR)


def check_rate_limit(key: str, max_attempts: int = 5, window_seconds: int = 300):
    """
    Tra ve (allowed: bool, retry_after_seconds: int).

    Moi lan goi ham nay duoc tinh la MOT lan thu (nen goi 1 lan duy nhat
    dau moi request nhay cam, KHONG goi lai neu khong thuc su co 1 lan thu
    moi — xem cach dung trong auth_callbacks.py).
    """
    now = time.time()
    try:
        bucket = _cache.get(key) or []
    except Exception as e:
        # Neu disk cache loi vi ly do bat ky (disk full, permission...),
        # fail-open ve mat chuc nang (khong chan user hop le) nhung log canh bao,
        # vi rate-limit la lop phong ve bo sung, khong phai xac thuc chinh.
        logger.warning(f"[RateLimiter] Loi doc cache cho key='{key}': {e}. Tam thoi cho phep.")
        return True, 0

    bucket = [t for t in bucket if now - t < window_seconds]

    if len(bucket) >= max_attempts:
        oldest = min(bucket)
        retry_after = max(1, int(window_seconds - (now - oldest)))
        logger.warning(
            f"[RateLimiter] BLOCKED key='{key}' — {len(bucket)} lan thu trong {window_seconds}s, "
            f"can doi {retry_after}s."
        )
        return False, retry_after

    bucket.append(now)
    try:
        _cache.set(key, bucket, expire=window_seconds)
    except Exception as e:
        logger.warning(f"[RateLimiter] Loi ghi cache cho key='{key}': {e}")

    return True, 0


def reset_rate_limit(key: str):
    """Xoa counter khi user thanh cong (login dung, redeem dung) de khong
    phat cho hanh vi hop le sau khi ho da tung go sai vai lan."""
    try:
        _cache.delete(key)
    except Exception as e:
        logger.warning(f"[RateLimiter] Loi xoa cache cho key='{key}': {e}")


def get_client_ip() -> str:
    """Lay IP that cua client trong Flask request context cua Dash callback.
    Uu tien X-Forwarded-For (khi chay sau reverse proxy nhu HF Spaces/Nginx),
    fallback ve remote_addr."""
    try:
        from flask import request
        fwd = request.headers.get("X-Forwarded-For", "")
        if fwd:
            return fwd.split(",")[0].strip()
        return request.remote_addr or "unknown"
    except Exception:
        return "unknown"
