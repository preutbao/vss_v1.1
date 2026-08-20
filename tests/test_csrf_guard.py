# tests/test_csrf_guard.py
"""
Test cho CSRF/Origin guard (audit muc 15 - Security).

App khong dung cookie-based session (khong co flask.session/SECRET_KEY o
bat ky dau), nen CSRF token truyen thong khong phai lop phong ve phu hop.
Thay vao do, guard nay chan request POST cross-origin toi endpoint dung
chung `/_dash-update-component` bang cach doi chieu Origin/Referer header
voi host that cua server.

Test logic THUAN (should_block_cross_origin), khong can load toan bo app
(main.py load ~1500 ma CK, cham va khong can thiet cho unit test nay).
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.app_instance import should_block_cross_origin


def test_allows_get_requests_regardless_of_origin():
    assert should_block_cross_origin("GET", "/_dash-update-component", "https://evil.com", "localhost") is False


def test_allows_non_callback_paths():
    assert should_block_cross_origin("POST", "/assets/style.css", "https://evil.com", "localhost") is False


def test_blocks_cross_origin_post_to_callback_endpoint():
    assert should_block_cross_origin("POST", "/_dash-update-component", "https://evil.com", "localhost") is True


def test_allows_same_origin_post():
    assert should_block_cross_origin("POST", "/_dash-update-component", "http://localhost", "localhost") is False


def test_allows_same_origin_post_with_https_and_port():
    assert should_block_cross_origin(
        "POST", "/_dash-update-component", "https://fss.example.com", "fss.example.com"
    ) is False


def test_no_origin_header_is_not_blocked_here():
    """Header rong duoc xu ly rieng (log canh bao, khong chan cung) o noi goi —
    ham thuan nay chi tra ve False khi khong co origin de doi chieu."""
    assert should_block_cross_origin("POST", "/_dash-update-component", "", "localhost") is False


def test_extra_allowed_hosts_are_respected():
    """Cho phep domain phu (vd staging, custom domain qua FSS_ALLOWED_ORIGINS)."""
    assert should_block_cross_origin(
        "POST", "/_dash-update-component", "https://staging.fss.vn", "localhost",
        extra_allowed_hosts={"staging.fss.vn"},
    ) is False
