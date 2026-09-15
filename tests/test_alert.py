# tests/test_alert.py
"""
Test cho Alert Engine (audit mục 9).

Bộ test này bao phủ 2 phần:
1. `src/backend/alert_engine.evaluate_alert()` — logic đánh giá điều kiện
   thuần (price/RSI/SMA/volume/VGM/CANSLIM/perf), dùng chung giữa UI callback
   và backend scheduler.
2. `src/backend/database` — các hàm CRUD bảng `alerts` mới (server-side
   persistence), phục vụ scheduler chạy độc lập browser.

Đặc biệt: có test hồi quy cho bug SMA đã ghi chú trong code gốc (trước đây
"_sma20"/"_sma200" luôn None → alert vượt/thủng SMA không bao giờ kích hoạt).
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest

from src.backend.alert_engine import evaluate_alert, evaluate_all


# ─────────────────────────────────────────────────────────────
# evaluate_alert() — từng loại điều kiện
# ─────────────────────────────────────────────────────────────

class TestEvaluateAlertPriceConditions:
    def test_price_above_hits_when_price_meets_target(self):
        alert = {"condition": "price_above", "value": 100}
        rec = {"Price Close": 105}
        assert evaluate_alert(alert, rec) is True

    def test_price_above_no_hit_when_below_target(self):
        alert = {"condition": "price_above", "value": 100}
        rec = {"Price Close": 95}
        assert evaluate_alert(alert, rec) is False

    def test_price_below_hits_when_price_under_target(self):
        alert = {"condition": "price_below", "value": 50}
        rec = {"Price Close": 45}
        assert evaluate_alert(alert, rec) is True


class TestEvaluateAlertRSI:
    def test_rsi_oversold_hits_below_30(self):
        alert = {"condition": "rsi_oversold", "value": None}
        rec = {"Price Close": 10, "RSI_14": 25}
        assert evaluate_alert(alert, rec) is True

    def test_rsi_oversold_no_hit_above_30(self):
        alert = {"condition": "rsi_oversold", "value": None}
        rec = {"Price Close": 10, "RSI_14": 45}
        assert evaluate_alert(alert, rec) is False

    def test_rsi_overbought_hits_above_70(self):
        alert = {"condition": "rsi_overbought", "value": None}
        rec = {"Price Close": 10, "RSI_14": 75}
        assert evaluate_alert(alert, rec) is True


class TestEvaluateAlertSMA:
    """
    Test hồi quy cho bug đã ghi chú trong code gốc:
    cột "_sma20"/"_sma200" thô không tồn tại trong snapshot (bị xoá bởi
    technical_indicators.py) -> phải suy ngược SMA từ Price_vs_SMA{n} (%).
    Nếu ai đó vô tình quay lại đọc "_sma20" trực tiếp, các test dưới đây
    sẽ FAIL vì luôn nhận price==sma (fallback an toàn) thay vì giá trị đúng.
    """

    def test_price_cross_sma20_hits_when_price_above_derived_sma(self):
        # Price_vs_SMA20 = -5% nghĩa là giá đang THẤP hơn SMA20 5% -> SMA20 > price
        # Dùng +5% (giá cao hơn SMA20) để hit "price_cross_sma20"
        rec = {"Price Close": 105, "Price_vs_SMA20": 5.0}  # sma20 = 105 / 1.05 = 100
        alert = {"condition": "price_cross_sma20", "value": None}
        assert evaluate_alert(alert, rec) is True

    def test_price_below_sma20_hits_when_price_under_derived_sma(self):
        rec = {"Price Close": 95, "Price_vs_SMA20": -5.0}  # sma20 = 95 / 0.95 = 100
        alert = {"condition": "price_below_sma20", "value": None}
        assert evaluate_alert(alert, rec) is True

    def test_missing_pct_field_falls_back_safely_no_false_trigger(self):
        """Nếu thiếu Price_vs_SMA20 hoàn toàn -> derive về = price -> không
        bao giờ price > sma20 hay price < sma20 -> không false-trigger."""
        rec = {"Price Close": 100}  # không có Price_vs_SMA20
        assert evaluate_alert({"condition": "price_cross_sma20", "value": None}, rec) is False
        assert evaluate_alert({"condition": "price_below_sma20", "value": None}, rec) is False


class TestEvaluateAlertOtherConditions:
    def test_volume_spike_hits_at_3x_sma20(self):
        rec = {"Price Close": 10, "Vol_vs_SMA20": 3.5}
        assert evaluate_alert({"condition": "volume_spike", "value": None}, rec) is True

    def test_vgm_a_hits_only_on_grade_a(self):
        rec_a = {"Price Close": 10, "VGM Score": "A"}
        rec_b = {"Price Close": 10, "VGM Score": "B"}
        assert evaluate_alert({"condition": "vgm_a", "value": None}, rec_a) is True
        assert evaluate_alert({"condition": "vgm_a", "value": None}, rec_b) is False

    def test_canslim_5_hits_at_threshold(self):
        rec = {"Price Close": 10, "CANSLIM Score": 5}
        assert evaluate_alert({"condition": "canslim_5", "value": None}, rec) is True

    def test_perf_1w_above_hits_when_meets_target(self):
        rec = {"Price Close": 10, "Perf_1W": 12.0}
        assert evaluate_alert({"condition": "perf_1w_above", "value": 10}, rec) is True

    def test_missing_record_never_hits(self):
        assert evaluate_alert({"condition": "price_above", "value": 1}, {}) is False


# ─────────────────────────────────────────────────────────────
# evaluate_all() — chỉ trả về alert MỚI chuyển sang triggered
# ─────────────────────────────────────────────────────────────

class TestEvaluateAll:
    def test_skips_already_triggered_alerts(self):
        alerts = [
            {"ticker": "AAA", "condition": "price_above", "value": 10, "triggered": True},
        ]
        snap = {"AAA": {"Price Close": 100}}
        assert evaluate_all(alerts, snap) == []

    def test_returns_newly_triggered_only(self):
        alerts = [
            {"ticker": "AAA", "condition": "price_above", "value": 10, "triggered": False},
            {"ticker": "BBB", "condition": "price_above", "value": 999, "triggered": False},
        ]
        snap = {"AAA": {"Price Close": 100}, "BBB": {"Price Close": 100}}
        result = evaluate_all(alerts, snap)
        assert len(result) == 1
        assert result[0]["ticker"] == "AAA"


# ─────────────────────────────────────────────────────────────
# Server-side alerts table (database.py) — dùng bởi backend scheduler
# ─────────────────────────────────────────────────────────────

@pytest.fixture
def temp_db(monkeypatch):
    """Trỏ database.py sang 1 file SQLite tạm, không đụng vào data/fss.db thật."""
    import src.backend.database as db_module

    tmp_dir = tempfile.mkdtemp(prefix="fss_test_db_")
    tmp_path = os.path.join(tmp_dir, "test.db")
    monkeypatch.setattr(db_module, "DB_PATH", tmp_path, raising=False)
    db_module.init_db()
    yield db_module


class TestServerSideAlertsTable:
    def test_create_and_list_alert(self, temp_db):
        alert_id = temp_db.create_alert("alice", "AAA", "price_above", 100)
        assert isinstance(alert_id, int)

        alerts = temp_db.list_alerts_for_owner("alice")
        assert len(alerts) == 1
        assert alerts[0]["ticker"] == "AAA"
        assert alerts[0]["triggered"] == 0

    def test_list_all_active_alerts_excludes_triggered(self, temp_db):
        id1 = temp_db.create_alert("alice", "AAA", "price_above", 100)
        temp_db.create_alert("bob", "BBB", "rsi_oversold", None)

        temp_db.mark_alert_triggered(id1)

        active = temp_db.list_all_active_alerts()
        tickers = {a["ticker"] for a in active}
        assert "AAA" not in tickers
        assert "BBB" in tickers

    def test_delete_alert_only_by_correct_owner(self, temp_db):
        alert_id = temp_db.create_alert("alice", "AAA", "price_above", 100)

        # Bob không sở hữu alert này -> không xoá được
        assert temp_db.delete_alert(alert_id, "bob") is False
        assert len(temp_db.list_alerts_for_owner("alice")) == 1

        # Alice xoá đúng alert của mình -> thành công
        assert temp_db.delete_alert(alert_id, "alice") is True
        assert len(temp_db.list_alerts_for_owner("alice")) == 0

    def test_mark_alert_triggered_sets_timestamp(self, temp_db):
        alert_id = temp_db.create_alert("alice", "AAA", "price_above", 100)
        temp_db.mark_alert_triggered(alert_id)

        alerts = temp_db.list_alerts_for_owner("alice")
        assert alerts[0]["triggered"] == 1
        assert alerts[0]["triggered_at"] is not None
