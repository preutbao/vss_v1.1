# tests/test_auth.py
"""
Test cho Critical 2 (bản đánh giá backend): mật khẩu trước đây so sánh
plaintext trực tiếp (users[username]['password'] == password), không hash.

Bộ test này xác nhận:
1) Mật khẩu hash được verify đúng.
2) Mật khẩu SAI bị từ chối.
3) Dữ liệu cũ còn plaintext (trước khi có bản vá) vẫn đăng nhập được và
   TỰ ĐỘNG được hash lại ngay (migrate-on-login) — không làm khóa tài
   khoản người dùng cũ.
"""
import sys
import os
import json
import tempfile

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.callbacks.auth_callbacks import _verify_password, _has_premium_ui
from werkzeug.security import generate_password_hash


class TestPasswordVerification:
    def test_correct_hashed_password_succeeds(self):
        users = {"alice": {"password": generate_password_hash("mypassword123")}}
        assert _verify_password("alice", "mypassword123", users) is True

    def test_wrong_password_fails(self):
        users = {"alice": {"password": generate_password_hash("mypassword123")}}
        assert _verify_password("alice", "wrongpassword", users) is False

    def test_unknown_username_fails(self):
        users = {"alice": {"password": generate_password_hash("mypassword123")}}
        assert _verify_password("nobody", "anything", users) is False

    def test_empty_password_fails(self):
        users = {"alice": {"password": generate_password_hash("mypassword123")}}
        assert _verify_password("alice", "", users) is False


class TestPlaintextMigration:
    """Bug cũ: users.json lưu password dạng plaintext. Bản vá phải cho phép
    tài khoản cũ (còn plaintext) đăng nhập bình thường VÀ tự động hash lại
    ngay lần đăng nhập đầu tiên, không được khóa tài khoản người dùng cũ."""

    def test_legacy_plaintext_password_still_works(self):
        users = {"legacy_user": {"password": "123@"}}  # plaintext kiểu cũ
        assert _verify_password("legacy_user", "123@", users) is True

    def test_legacy_plaintext_wrong_password_rejected(self):
        users = {"legacy_user": {"password": "123@"}}
        assert _verify_password("legacy_user", "wrong", users) is False

    def test_legacy_plaintext_gets_migrated_to_hash_after_login(self, monkeypatch):
        """Sau khi verify thành công 1 lần với mật khẩu plaintext cũ, mật
        khẩu trong bộ nhớ (dict users) phải được thay bằng dạng đã hash,
        không còn lưu plaintext nữa."""
        import src.callbacks.auth_callbacks as auth_mod

        saved = {}
        monkeypatch.setattr(auth_mod, "_save_users", lambda users: saved.update(users))

        users = {"legacy_user": {"password": "123@"}}
        result = _verify_password("legacy_user", "123@", users)

        assert result is True
        stored = users["legacy_user"]["password"]
        assert stored != "123@", "Mật khẩu vẫn còn plaintext sau khi đăng nhập — chưa migrate"
        assert ":" in stored and "$" in stored, "Mật khẩu sau migrate phải có định dạng hash của werkzeug"

    def test_never_stores_plaintext_after_successful_verify(self, monkeypatch):
        """Test hồi quy trực tiếp cho Critical 2: nếu bug so sánh plaintext
        quay lại (bỏ qua bước hash), test này sẽ FAIL vì phát hiện password
        vẫn ở dạng đọc được trực tiếp."""
        import src.callbacks.auth_callbacks as auth_mod
        monkeypatch.setattr(auth_mod, "_save_users", lambda users: None)

        users = {"u1": {"password": "plaintext_pw_1"}}
        _verify_password("u1", "plaintext_pw_1", users)
        assert users["u1"]["password"] != "plaintext_pw_1"


class TestHasPremiumUi:
    """_has_premium_ui() thay thế _is_vip() cũ — tier hệ thống mới chỉ còn
    'pro' và 'b2b' (bỏ 'vip')."""

    def test_true_when_logged_in_and_pro_tier(self):
        assert _has_premium_ui({"logged_in": True, "tier": "pro"}) is True

    def test_true_when_logged_in_and_b2b_tier(self):
        assert _has_premium_ui({"logged_in": True, "tier": "b2b"}) is True

    def test_false_when_free_tier(self):
        """Bug cũ (screener_callbacks.py): chỉ check 'logged_in', khiến
        user free đăng nhập cũng được coi là premium. Test hồi quy trực
        tiếp cho logic _has_premium_ui dùng chung."""
        assert _has_premium_ui({"logged_in": True, "tier": "free"}) is False

    def test_false_when_not_logged_in(self):
        assert _has_premium_ui({"logged_in": False, "tier": "pro"}) is False

    def test_false_when_none(self):
        assert _has_premium_ui(None) is False

    def test_false_when_empty_dict(self):
        assert _has_premium_ui({}) is False


class TestRequireEntitlement:
    """
    Test cho require_entitlement() — hàm bảo vệ endpoint premium DÙNG CHUNG
    (audit mục 4, Major Issue: trước đây logic re-check server-side bị lặp
    lại độc lập ở screener_callbacks.py và chatbot_callbacks.py).

    Điểm quan trọng nhất: hàm PHẢI bỏ qua auth_data.tier gửi từ client và
    luôn đối chiếu với users.json (server-side) — nếu không sẽ tái diễn lỗ
    hổng cho phép giả mạo tier='pro' qua localStorage/DevTools.

    Tier hệ thống mới chỉ còn 'pro' và 'b2b' (bỏ 'vip'); mặc định
    allowed_tiers=("pro", "b2b").
    """

    def test_grants_when_server_side_tier_matches_pro(self, monkeypatch):
        import src.callbacks.auth_callbacks as auth_mod
        monkeypatch.setattr(auth_mod, "_load_users", lambda: {"alice": {"tier": "pro"}})
        auth_data = {"logged_in": True, "username": "alice", "tier": "pro"}
        assert auth_mod.require_entitlement(auth_data) is True

    def test_grants_when_server_side_tier_matches_b2b(self, monkeypatch):
        import src.callbacks.auth_callbacks as auth_mod
        monkeypatch.setattr(auth_mod, "_load_users", lambda: {"alice": {"tier": "b2b"}})
        auth_data = {"logged_in": True, "username": "alice", "tier": "b2b"}
        assert auth_mod.require_entitlement(auth_data) is True

    def test_denies_when_client_claims_pro_but_server_says_free(self, monkeypatch):
        """Mô phỏng chính xác cuộc tấn công đã được audit ghi nhận: user tự
        sửa localStorage để auth_data.tier='pro' dù server chỉ ghi 'free'."""
        import src.callbacks.auth_callbacks as auth_mod
        monkeypatch.setattr(auth_mod, "_load_users", lambda: {"alice": {"tier": "free"}})
        spoofed_auth_data = {"logged_in": True, "username": "alice", "tier": "pro"}
        assert auth_mod.require_entitlement(spoofed_auth_data) is False

    def test_denies_when_not_logged_in(self, monkeypatch):
        import src.callbacks.auth_callbacks as auth_mod
        monkeypatch.setattr(auth_mod, "_load_users", lambda: {"alice": {"tier": "pro"}})
        assert auth_mod.require_entitlement({"logged_in": False, "username": "alice"}) is False

    def test_denies_when_auth_data_is_none(self, monkeypatch):
        import src.callbacks.auth_callbacks as auth_mod
        monkeypatch.setattr(auth_mod, "_load_users", lambda: {"alice": {"tier": "pro"}})
        assert auth_mod.require_entitlement(None) is False

    def test_respects_custom_allowed_tiers(self, monkeypatch):
        """allowed_tiers giờ có thể tùy biến — ví dụ endpoint chỉ giới hạn
        riêng cho 'b2b' thì user 'pro' phải bị từ chối."""
        import src.callbacks.auth_callbacks as auth_mod
        monkeypatch.setattr(auth_mod, "_load_users", lambda: {"alice": {"tier": "pro"}})
        auth_data = {"logged_in": True, "username": "alice", "tier": "pro"}
        assert auth_mod.require_entitlement(auth_data, allowed_tiers=("b2b",)) is False
        assert auth_mod.require_entitlement(auth_data, allowed_tiers=("pro", "b2b")) is True

    def test_denies_unknown_username(self, monkeypatch):
        import src.callbacks.auth_callbacks as auth_mod
        monkeypatch.setattr(auth_mod, "_load_users", lambda: {"alice": {"tier": "pro"}})
        auth_data = {"logged_in": True, "username": "ghost"}
        assert auth_mod.require_entitlement(auth_data) is False

    def test_fails_closed_when_users_file_unreadable(self, monkeypatch):
        """Nếu users.json lỗi/không đọc được, PHẢI từ chối (fail-closed),
        không được mặc định cấp quyền VIP."""
        import src.callbacks.auth_callbacks as auth_mod

        def _boom():
            raise IOError("disk error")

        monkeypatch.setattr(auth_mod, "_load_users", _boom)
        auth_data = {"logged_in": True, "username": "alice"}
        assert auth_mod.require_entitlement(auth_data) is False


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))