# tests/test_rate_limiter.py
"""
Test cho src/backend/rate_limiter.py (audit muc 15 - Security).

Truoc audit: khong co bat ky rate limit nao tren login/redeem-code -> co the
bi brute-force khong gioi han. Bo test nay xac nhan:
1) Duoi nguong max_attempts -> luon allowed.
2) Vuot nguong -> bi block va tra ve retry_after > 0.
3) Sau khi het window_seconds -> duoc phep thu lai.
4) reset_rate_limit() xoa counter ngay lap tuc (dung cho truong hop
   dang nhap dung sau vai lan go sai).

Dung mot cache dir rieng (tempfile) cho moi test de khong dam vao
cache/rate_limit/ that cua ung dung va khong bi anh huong boi test khac.
"""
import importlib
import os
import sys
import tempfile
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest


@pytest.fixture
def limiter_module(monkeypatch):
    """Reload rate_limiter voi mot cache dir tam thoi rieng biet cho test."""
    import src.backend.rate_limiter as rl_module

    tmp_dir = tempfile.mkdtemp(prefix="fss_test_ratelimit_")
    monkeypatch.setattr(rl_module, "_CACHE_DIR", tmp_dir, raising=False)

    from diskcache import Cache
    rl_module._cache = Cache(tmp_dir)

    yield rl_module

    rl_module._cache.clear()


def test_allows_under_limit(limiter_module):
    key = "test:under-limit"
    for _ in range(3):
        allowed, retry_after = limiter_module.check_rate_limit(key, max_attempts=5, window_seconds=60)
        assert allowed is True
        assert retry_after == 0


def test_blocks_over_limit(limiter_module):
    key = "test:over-limit"
    for _ in range(5):
        allowed, _ = limiter_module.check_rate_limit(key, max_attempts=5, window_seconds=60)
        assert allowed is True

    # Lan thu thu 6 -> phai bi chan
    allowed, retry_after = limiter_module.check_rate_limit(key, max_attempts=5, window_seconds=60)
    assert allowed is False
    assert retry_after > 0


def test_window_expiry_allows_retry(limiter_module):
    key = "test:window-expiry"
    for _ in range(3):
        allowed, _ = limiter_module.check_rate_limit(key, max_attempts=3, window_seconds=1)
        assert allowed is True

    allowed, _ = limiter_module.check_rate_limit(key, max_attempts=3, window_seconds=1)
    assert allowed is False

    time.sleep(1.2)  # doi het window

    allowed, retry_after = limiter_module.check_rate_limit(key, max_attempts=3, window_seconds=1)
    assert allowed is True
    assert retry_after == 0


def test_reset_clears_counter_immediately(limiter_module):
    key = "test:reset"
    for _ in range(5):
        allowed, _ = limiter_module.check_rate_limit(key, max_attempts=5, window_seconds=300)
        assert allowed is True

    allowed, _ = limiter_module.check_rate_limit(key, max_attempts=5, window_seconds=300)
    assert allowed is False  # da het luot

    limiter_module.reset_rate_limit(key)

    allowed, retry_after = limiter_module.check_rate_limit(key, max_attempts=5, window_seconds=300)
    assert allowed is True
    assert retry_after == 0


def test_different_keys_are_independent(limiter_module):
    for _ in range(5):
        limiter_module.check_rate_limit("test:key-a", max_attempts=5, window_seconds=300)

    allowed_a, _ = limiter_module.check_rate_limit("test:key-a", max_attempts=5, window_seconds=300)
    allowed_b, _ = limiter_module.check_rate_limit("test:key-b", max_attempts=5, window_seconds=300)

    assert allowed_a is False
    assert allowed_b is True
