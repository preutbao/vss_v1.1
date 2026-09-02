# tests/test_wifeed_updater.py
"""
Test cho src/backend/wifeed_updater.py — tính năng Wifeed EOD/Realtime mới
(chưa có trong bộ test cũ, chỉ mới xuất hiện trong version hiện tại).

Phạm vi: chỉ test các HÀM THUẦN hoặc GẦN THUẦN (parse, filter, tính giờ
giao dịch, merge/ghi file cục bộ với path đã cô lập bằng tmp_path). KHÔNG
gọi mạng thật tới Wifeed (dùng unittest.mock.patch cho requests.get) — vừa
tránh phụ thuộc mạng khi chạy CI, vừa tránh vi phạm rate-limit 60s/request
thật của Wifeed (xem docstring đầu wifeed_updater.py).

Mỗi test tự cô lập state bằng 2 fixture dưới đây:
  - `_reset_wifeed_globals` (autouse): reset toàn bộ biến global module-level
    (cache, timestamp, flag EOD...) về trạng thái sạch trước MỖI test, tránh
    1 test làm bẩn state ảnh hưởng test chạy sau (thứ tự chạy pytest không
    đảm bảo, và các biến này là module-level singleton).
  - `tmp_paths`: trỏ _PRICE_PATH / _CACHE_PATH / _INDEX_PATH / _PROCESSED_DIR
    sang thư mục tmp_path riêng của từng test — KHÔNG BAO GIỜ đụng vào
    data/processed/ thật của dự án.

[PHÁT HIỆN TRONG LÚC VIẾT TEST — 2 lỗi thật trong _fetch_wifeed()]
Hàm được khai báo kiểu trả về `tuple[pd.DataFrame, pd.DataFrame]` và MỌI
lời gọi (`df_stocks, df_all = _fetch_wifeed()`) đều unpack 2 giá trị.
Nhưng có 2 nhánh early-return chỉ trả về DUY NHẤT 1 DataFrame rỗng thay vì
tuple 2 phần tử:
  1. Khi thiếu WIFEED_API_KEY (dòng `return pd.DataFrame()`).
  2. Khi HTTP status != 200 (dòng `return pd.DataFrame()` trong nhánh lỗi).
Cả 2 trường hợp này, nếu code gọi thật `df_stocks, df_all = _fetch_wifeed()`
sẽ crash với `ValueError: not enough values to unpack (expected 2, got 0)`
— tức là khi Wifeed die/rate-limit-ban (rất hay gặp HTTP lỗi) hoặc quên set
API key, scheduler sẽ crash thay vì log lỗi rồi bỏ qua như ý đồ thiết kế.
2 test `test_fetch_wifeed_returns_tuple_when_*` dưới đây SẼ FAIL với code
hiện tại — đây là bug thật cần fix trong wifeed_updater.py (không phải lỗi
của test), sửa bằng cách đổi `return pd.DataFrame()` thành
`return pd.DataFrame(), pd.DataFrame()` ở 2 chỗ đó.
"""
import copy
import json
import os
import sys
import time
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.backend import wifeed_updater as wu


# ─────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _reset_wifeed_globals(monkeypatch):
    """Reset toàn bộ state module-level trước MỖI test (xem docstring đầu file)."""
    monkeypatch.setattr(wu, "_realtime_snapshot", {}, raising=False)
    monkeypatch.setattr(wu, "_snapshot_ts", 0.0, raising=False)
    monkeypatch.setattr(wu, "_realtime_index", {}, raising=False)
    monkeypatch.setattr(wu, "_eod_appended", False, raising=False)
    monkeypatch.setattr(wu, "_eod_date", "", raising=False)
    monkeypatch.setattr(wu, "_last_fetch_ts", 0.0, raising=False)
    yield


@pytest.fixture
def tmp_paths(tmp_path, monkeypatch):
    """Cô lập toàn bộ đường dẫn file Wifeed sang thư mục tmp riêng của test."""
    price_path = tmp_path / "market_prices.parquet"
    cache_path = tmp_path / "realtime_cache.parquet"
    index_path = tmp_path / "index.parquet"
    monkeypatch.setattr(wu, "_PRICE_PATH", str(price_path))
    monkeypatch.setattr(wu, "_CACHE_PATH", str(cache_path))
    monkeypatch.setattr(wu, "_INDEX_PATH", str(index_path))
    monkeypatch.setattr(wu, "_PROCESSED_DIR", str(tmp_path))
    return {"price": price_path, "cache": cache_path, "index": index_path, "dir": tmp_path}


def _make_raw_record(mack, ngay="2026-08-28T00:00:00.000Z", close=10000.0,
                      ceiling=10700.0, floor=9300.0, changed=100.0, changed_pct=1.0,
                      volume=100000, turnover=1_000_000_000):
    """Tạo 1 record thô đúng format response Wifeed thật (đã xác nhận field
    name qua file mẫu wifeed_output.txt: mack/ngay/*_adjust/ceilingprice/...)."""
    return {
        "mack": mack, "ngay": ngay,
        "open_root": close, "high_root": close * 1.01, "low_root": close * 0.99, "close_root": close,
        "volume_root": volume,
        "open_adjust": close, "high_adjust": close * 1.01, "low_adjust": close * 0.99,
        "close_adjust": close, "volume_adjust": volume,
        "ceilingprice": ceiling, "changed": changed, "changedratio": changed_pct,
        "floorprice": floor, "giatri_giaodich": turnover,
        "kl_nn_ban": 0, "kl_nn_mua": 0, "gt_nn_ban": 0, "gt_nn_mua": 0,
        "lastupdate": "2026-08-28T13:56:27.000Z",
        "created_at": "2026-08-28T02:00:00.000Z", "updated_at": "2026-08-28T20:59:04.000Z",
    }


def _sample_data():
    """5 mã cổ phiếu bình thường + 2 mã chỉ số (ceiling=None, giống thật:
    VNINDEX/VN30/HNXINDEX/HNX30/UPCOM luôn có ceilingprice=null)."""
    stocks = [_make_raw_record(f"AA{i}", close=10000 + i * 100) for i in range(5)]
    indices = [
        _make_raw_record("VNINDEX", close=1832.12, ceiling=None, floor=None),
        _make_raw_record("VN30", close=1982.96, ceiling=None, floor=None),
    ]
    return stocks + indices


# ─────────────────────────────────────────────────────────────
# _parse_wifeed_response_all() / _parse_wifeed_response()
# ─────────────────────────────────────────────────────────────

class TestParseWifeedResponseAll:
    def test_renames_columns_to_standard_schema(self):
        df = wu._parse_wifeed_response_all(_sample_data())
        for col in ["Ticker", "Date", "Price Open", "Price High", "Price Low",
                    "Price Close", "Volume", "Price_Change", "Price_Change_Pct",
                    "Ceiling", "Floor", "Turnover"]:
            assert col in df.columns, f"Thiếu cột chuẩn hóa '{col}' sau rename"

    def test_row_count_matches_input_when_all_valid(self):
        data = _sample_data()
        df = wu._parse_wifeed_response_all(data)
        assert len(df) == len(data)

    def test_numeric_columns_are_coerced_to_numeric_dtype(self):
        df = wu._parse_wifeed_response_all(_sample_data())
        for col in ["Price Open", "Price High", "Price Low", "Price Close", "Ceiling", "Floor"]:
            assert pd.api.types.is_numeric_dtype(df[col]), f"'{col}' không phải kiểu số sau parse"

    def test_volume_and_turnover_are_int64_and_null_becomes_zero(self):
        """Volume/Turnover phải là int64 (theo code: fillna(0).astype('int64')),
        null trong response -> 0, KHÔNG được NaN (NaN sẽ gãy khi hiển thị UI dạng int)."""
        data = [_make_raw_record("BBB")]
        data[0]["giatri_giaodich"] = None
        df = wu._parse_wifeed_response_all(data)
        assert df["Turnover"].dtype == np.int64
        assert df.loc[df["Ticker"] == "BBB", "Turnover"].iloc[0] == 0

    def test_date_is_normalized_naive_no_timezone(self):
        df = wu._parse_wifeed_response_all(_sample_data())
        assert df["Date"].dt.tz is None
        # normalize() phải xóa phần giờ:phút:giây -> luôn là 00:00:00
        assert (df["Date"].dt.time == pd.Timestamp("00:00:00").time()).all()

    def test_ticker_is_stripped_string(self):
        data = [_make_raw_record("  AAA  ")]
        df = wu._parse_wifeed_response_all(data)
        assert df["Ticker"].iloc[0] == "AAA"

    def test_rows_missing_ticker_or_price_close_are_dropped(self):
        data = _sample_data()
        bad = _make_raw_record("BADROW")
        bad["close_adjust"] = None  # -> Price Close NaN -> phải bị dropna
        data.append(bad)
        df = wu._parse_wifeed_response_all(data)
        assert "BADROW" not in df["Ticker"].values

    def test_empty_input_returns_empty_dataframe(self):
        df = wu._parse_wifeed_response_all([])
        assert df.empty

    def test_missing_optional_columns_do_not_crash(self):
        """Response thiếu 1 số field phụ (vd không có kl_nn_mua) không được
        làm hàm crash — chỉ rename những cột thực sự có mặt."""
        minimal = {
            "mack": "MIN1", "ngay": "2026-08-28T00:00:00.000Z",
            "close_adjust": 10000.0,
        }
        df = wu._parse_wifeed_response_all([minimal])
        assert len(df) == 1
        assert df["Ticker"].iloc[0] == "MIN1"


class TestParseWifeedResponse:
    def test_filters_out_rows_without_ceiling_price(self):
        """Bug hồi quy tiềm ẩn: nếu ai đó xóa nhầm bước filter Ceiling
        notna(), các mã chỉ số (VNINDEX/VN30/...) sẽ lẫn vào danh sách cổ
        phiếu của màn hình screener — sai hoàn toàn về nghiệp vụ."""
        data = _sample_data()
        df = wu._parse_wifeed_response(data)
        assert "VNINDEX" not in df["Ticker"].values
        assert "VN30" not in df["Ticker"].values
        assert len(df) == 5  # chỉ 5 mã cổ phiếu thật

    def test_returns_empty_when_all_rows_are_indices(self):
        data = [
            _make_raw_record("VNINDEX", ceiling=None, floor=None),
            _make_raw_record("VN30", ceiling=None, floor=None),
        ]
        df = wu._parse_wifeed_response(data)
        assert df.empty


# ─────────────────────────────────────────────────────────────
# _is_trading_time() / _is_eod_time()
# ─────────────────────────────────────────────────────────────

class TestTradingTimeWindows:
    """
    Test hồi quy cho ranh giới giờ giao dịch (mục 09:00-17:00, EOD confirm
    15:00-17:00). Nếu ai đó sửa nhầm _TRADING_START/_EOD_CUTOFF, các test
    biên (boundary) dưới đây sẽ bắt được ngay.
    """

    @staticmethod
    def _patch_now(monkeypatch, hh, mm):
        from datetime import time as dtime

        class _FakeNow:
            def time(self_inner):
                return dtime(hh, mm)

        monkeypatch.setattr(wu, "_now_vn", lambda: _FakeNow())

    @pytest.mark.parametrize("hh,mm,expected", [
        (8, 59, False),
        (9, 0, True),
        (12, 0, True),
        (14, 45, True),
        (16, 59, True),
        (17, 0, True),
        (17, 1, False),
    ])
    def test_is_trading_time_boundaries(self, monkeypatch, hh, mm, expected):
        self._patch_now(monkeypatch, hh, mm)
        assert wu._is_trading_time() is expected

    @pytest.mark.parametrize("hh,mm,expected", [
        (9, 0, False),
        (14, 59, False),
        (15, 0, True),
        (15, 5, True),
        (17, 0, True),
        (17, 1, False),
    ])
    def test_is_eod_time_boundaries(self, monkeypatch, hh, mm, expected):
        self._patch_now(monkeypatch, hh, mm)
        assert wu._is_eod_time() is expected


# ─────────────────────────────────────────────────────────────
# _filter_known_tickers()
# ─────────────────────────────────────────────────────────────

class TestFilterKnownTickers:
    def test_strips_exchange_suffix_to_match_wifeed_format(self, tmp_paths):
        """Parquet lưu 'AA0.HM' nhưng Wifeed trả 'AA0' (không đuôi) — hàm
        phải tự strip đuôi sàn để so khớp đúng, đây là bug hồi quy đã ghi
        chú ngay trong docstring gốc của hàm."""
        known = pd.DataFrame({"Ticker": ["AA0.HM", "AA1.HN", "AA2.HNO"]})
        known.to_parquet(tmp_paths["price"], index=False)

        df = wu._parse_wifeed_response(_sample_data())
        filtered = wu._filter_known_tickers(df)
        assert set(filtered["Ticker"]) == {"AA0", "AA1", "AA2"}

    def test_unknown_tickers_are_dropped(self, tmp_paths):
        known = pd.DataFrame({"Ticker": ["AA0.HM"]})
        known.to_parquet(tmp_paths["price"], index=False)

        df = wu._parse_wifeed_response(_sample_data())
        filtered = wu._filter_known_tickers(df)
        assert "AA4" not in filtered["Ticker"].values  # AA4 có trong data nhưng không trong parquet

    def test_missing_price_parquet_returns_df_unfiltered(self, tmp_paths):
        """Chưa từng có market_prices.parquet (lần chạy đầu tiên) -> KHÔNG
        được làm rỗng toàn bộ dữ liệu, phải trả nguyên df gốc."""
        df = wu._parse_wifeed_response(_sample_data())
        filtered = wu._filter_known_tickers(df.copy())
        assert len(filtered) == len(df)

    def test_empty_input_returns_empty(self, tmp_paths):
        result = wu._filter_known_tickers(pd.DataFrame())
        assert result.empty

    def test_corrupt_price_parquet_falls_back_to_unfiltered(self, tmp_paths):
        """Nếu đọc parquet lỗi (file hỏng) -> không crash, giữ nguyên df gốc."""
        with open(tmp_paths["price"], "w") as f:
            f.write("not a real parquet file")
        df = wu._parse_wifeed_response(_sample_data())
        filtered = wu._filter_known_tickers(df.copy())
        assert len(filtered) == len(df)


# ─────────────────────────────────────────────────────────────
# _save_realtime_cache() / get_realtime_snapshot() / get_realtime_index()
# ─────────────────────────────────────────────────────────────

class TestSaveRealtimeCache:
    def test_updates_in_memory_snapshot_and_timestamp(self, tmp_paths):
        df = wu._parse_wifeed_response(_sample_data())
        before_ts = wu.get_snapshot_timestamp()
        wu._save_realtime_cache(df)
        assert wu.get_snapshot_timestamp() > before_ts
        snap = wu.get_realtime_snapshot()
        assert set(snap.keys()) == set(df["Ticker"])

    def test_writes_parquet_cache_file(self, tmp_paths):
        df = wu._parse_wifeed_response(_sample_data())
        wu._save_realtime_cache(df)
        assert os.path.exists(tmp_paths["cache"])
        reloaded = pd.read_parquet(tmp_paths["cache"])
        assert len(reloaded) == len(df)

    def test_empty_dataframe_is_a_noop(self, tmp_paths):
        wu._save_realtime_cache(pd.DataFrame())
        assert wu.get_realtime_snapshot() == {}
        assert not os.path.exists(tmp_paths["cache"])

    def test_populates_realtime_index_from_df_all(self, tmp_paths):
        df_stocks = wu._parse_wifeed_response(_sample_data())
        df_all = wu._parse_wifeed_response_all(_sample_data())
        wu._save_realtime_cache(df_stocks, df_all)
        idx = wu.get_realtime_index()
        assert "VNINDEX" in idx
        assert idx["VNINDEX"]["close"] == pytest.approx(1832.12)
        assert "close" in idx["VNINDEX"] and "change_pct" in idx["VNINDEX"]

    def test_write_failure_does_not_raise_or_crash(self, tmp_paths, monkeypatch):
        """Ghi file lỗi (disk đầy, quyền truy cập...) -> phải log và tiếp
        tục chạy, KHÔNG được raise exception làm sập scheduler."""
        df = wu._parse_wifeed_response(_sample_data())

        def _boom(*a, **kw):
            raise OSError("disk full (giả lập)")

        monkeypatch.setattr(pd.DataFrame, "to_parquet", _boom)
        try:
            wu._save_realtime_cache(df)  # không được raise
        except OSError:
            pytest.fail("_save_realtime_cache phải bắt lỗi ghi file, không được để lộ ra ngoài")


# ─────────────────────────────────────────────────────────────
# _append_index_to_parquet()
# ─────────────────────────────────────────────────────────────

class TestAppendIndexToParquet:
    def test_creates_new_index_parquet_with_pivoted_columns(self, tmp_paths):
        df_all = wu._parse_wifeed_response_all(_sample_data())
        wu._append_index_to_parquet(df_all)

        assert os.path.exists(tmp_paths["index"])
        idx_df = pd.read_parquet(tmp_paths["index"])
        assert "VNINDEX_Close" in idx_df.columns
        assert "VN30_Close" in idx_df.columns
        assert idx_df["VNINDEX_Close"].iloc[0] == pytest.approx(1832.12)

    def test_merges_with_existing_index_parquet_dedup_by_date_keep_last(self, tmp_paths):
        existing = pd.DataFrame({
            "Date": [pd.Timestamp("2026-08-27"), pd.Timestamp("2026-08-28")],
            "VNINDEX_Close": [1800.0, 1810.0],  # 28/08 sẽ bị ghi đè bởi giá trị mới hơn
        })
        existing.to_parquet(tmp_paths["index"], index=False)

        df_all = wu._parse_wifeed_response_all(_sample_data())  # Date = 2026-08-28
        wu._append_index_to_parquet(df_all)

        idx_df = pd.read_parquet(tmp_paths["index"]).sort_values("Date").reset_index(drop=True)
        assert len(idx_df) == 2  # không nhân đôi dòng 28/08
        row_2808 = idx_df[idx_df["Date"] == pd.Timestamp("2026-08-28")].iloc[0]
        assert row_2808["VNINDEX_Close"] == pytest.approx(1832.12)  # giá trị MỚI, không phải 1810.0 cũ

    def test_no_index_symbols_in_response_does_not_crash(self, tmp_paths):
        data = [_make_raw_record("AA0"), _make_raw_record("AA1")]  # không có mã chỉ số nào
        df_all = wu._parse_wifeed_response_all(data)
        wu._append_index_to_parquet(df_all)  # không được raise
        assert not os.path.exists(tmp_paths["index"])  # không tạo file rỗng vô nghĩa

    def test_empty_dataframe_is_a_noop(self, tmp_paths):
        wu._append_index_to_parquet(pd.DataFrame())
        assert not os.path.exists(tmp_paths["index"])


# ─────────────────────────────────────────────────────────────
# _merge_eod_into_price_parquet()
# ─────────────────────────────────────────────────────────────

class TestMergeEodIntoPriceParquet:
    def _fake_eod_df(self):
        return pd.DataFrame({
            "Ticker": ["AA0", "AA1"],
            "Date": [pd.Timestamp("2026-08-28")] * 2,
            "Price Open": [10000.0, 10100.0],
            "Price High": [10100.0, 10200.0],
            "Price Low": [9900.0, 10000.0],
            "Price Close": [10050.0, 10150.0],
            "Volume": [100000, 200000],
            "Turnover": [1_000_000_000, 2_000_000_000],
        })

    def test_creates_new_parquet_when_none_exists(self, tmp_paths):
        ok = wu._merge_eod_into_price_parquet(self._fake_eod_df())
        assert ok is True
        assert os.path.exists(tmp_paths["price"])
        df = pd.read_parquet(tmp_paths["price"])
        assert len(df) == 2

    def test_upserts_by_ticker_and_date_no_duplicates(self, tmp_paths):
        existing = pd.DataFrame({
            "Ticker": ["AA0"], "Date": [pd.Timestamp("2026-08-28")],
            "Price Open": [1.0], "Price High": [1.0], "Price Low": [1.0],
            "Price Close": [1.0], "Volume": [1], "Turnover": [1],
        })
        existing.to_parquet(tmp_paths["price"], index=False)

        wu._merge_eod_into_price_parquet(self._fake_eod_df())

        df = pd.read_parquet(tmp_paths["price"])
        assert len(df) == 2  # AA0 cũ bị upsert (không nhân đôi), AA1 được thêm mới
        aa0 = df[df["Ticker"] == "AA0"].iloc[0]
        assert aa0["Price Close"] == pytest.approx(10050.0)  # giá trị MỚI ghi đè giá trị cũ (1.0)

    def test_reattaches_company_info_columns_from_existing_data(self, tmp_paths):
        """Dòng EOD mới từ Wifeed KHÔNG có Exchange/Sector — hàm phải tự
        map lại từ dữ liệu cũ theo Ticker để không làm mất thông tin công ty."""
        existing = pd.DataFrame({
            "Ticker": ["AA0"], "Date": [pd.Timestamp("2026-08-20")],
            "Price Close": [1.0], "Exchange": ["HOSE"],
            "Company Common Name": ["Cong ty AA0"],
        })
        existing.to_parquet(tmp_paths["price"], index=False)

        wu._merge_eod_into_price_parquet(self._fake_eod_df())

        df = pd.read_parquet(tmp_paths["price"])
        new_row = df[(df["Ticker"] == "AA0") & (df["Date"] == pd.Timestamp("2026-08-28"))].iloc[0]
        assert new_row["Exchange"] == "HOSE"
        assert new_row["Company Common Name"] == "Cong ty AA0"

    def test_clears_data_loader_market_cache_on_success(self, tmp_paths, monkeypatch):
        """Đây là hành vi CỐT LÕI cho cache-coherency: merge EOD thành công
        PHẢI clear data_loader._MARKET_CACHE để lần load_market_data() kế
        tiếp đọc lại parquet mới, không phục vụ giá cũ trong 5 phút TTL.

        LƯU Ý MOCK: wifeed_updater.py clear cache bằng
        `import src.backend.data_loader as _dl` — đây là dạng "import a.b.c
        as x", Python resolve _dl qua thuộc tính đã gắn sẵn trên package
        src.backend (từ lần import thật đầu tiên), KHÔNG tra lại
        sys.modules["src.backend.data_loader"] mỗi lần. Vì vậy không thể
        giả lập bằng cách thay thế cả module qua
        monkeypatch.setitem(sys.modules, ...) — làm vậy sẽ khiến code chạy
        trên module data_loader THẬT, còn fake module không hề bị đụng tới,
        và assertion sẽ fail dù code sản xuất hoàn toàn đúng.
        Cách đúng: patch trực tiếp dict _MARKET_CACHE thật (mutate in-place),
        vì đó chính là object mà _dl._MARKET_CACHE trỏ tới lúc runtime."""
        import src.backend.data_loader as dl
        monkeypatch.setitem(dl._MARKET_CACHE, "data", "DU_LIEU_CU")
        monkeypatch.setitem(dl._MARKET_CACHE, "ts", time.time())

        ok = wu._merge_eod_into_price_parquet(self._fake_eod_df())

        assert ok is True
        assert dl._MARKET_CACHE["data"] is None
        assert dl._MARKET_CACHE["ts"] == 0.0

    def test_clear_cache_failure_does_not_fail_the_merge(self, tmp_paths, monkeypatch):
        """Nếu import/clear data_loader._MARKET_CACHE lỗi vì lý do nào đó,
        việc GHI dữ liệu EOD vẫn phải coi là thành công (True) — clear cache
        chỉ là optimization, không phải điều kiện đúng/sai của việc ghi.

        Cùng lý do như test ở trên: phải patch _MARKET_CACHE của module
        data_loader THẬT (qua monkeypatch.setattr trên chính module đó),
        không tạo module giả rồi nhét vào sys.modules — nếu không, đoạn
        code `_dl._MARKET_CACHE["data"] = None` trong wifeed_updater.py sẽ
        chạy trên dict thật (không raise), khiến test "pass" nhưng không hề
        kiểm chứng nhánh except như tên test mô tả."""
        import src.backend.data_loader as dl

        class _BoomDict(dict):
            def __setitem__(self, key, value):
                raise RuntimeError("giả lập lỗi clear cache")

        monkeypatch.setattr(dl, "_MARKET_CACHE", _BoomDict(data="x", ts=1.0))

        ok = wu._merge_eod_into_price_parquet(self._fake_eod_df())
        assert ok is True

    def test_write_failure_returns_false(self, tmp_paths, monkeypatch):
        def _boom(*a, **kw):
            raise OSError("disk full (giả lập)")

        monkeypatch.setattr(pd.DataFrame, "to_parquet", _boom)
        ok = wu._merge_eod_into_price_parquet(self._fake_eod_df())
        assert ok is False


# ─────────────────────────────────────────────────────────────
# _fetch_wifeed() — mock requests, KHÔNG gọi mạng thật
# ─────────────────────────────────────────────────────────────

class TestFetchWifeedRateLimit:
    def test_sleeps_when_called_before_min_interval_elapsed(self, monkeypatch):
        monkeypatch.setenv("WIFEED_API_KEY", "fake_key")
        wu._last_fetch_ts = time.time() - 10  # mới gọi cách đây 10s (< 60s)

        fake_resp = MagicMock(status_code=200, json=lambda: {"data": _sample_data()})
        with patch.object(wu.time, "sleep") as mock_sleep, \
                patch.object(wu.requests, "get", return_value=fake_resp):
            wu._fetch_wifeed()
        assert mock_sleep.called
        slept_seconds = mock_sleep.call_args[0][0]
        assert 45 <= slept_seconds <= 51  # ~50s còn lại để đủ 60s

    def test_no_sleep_when_interval_already_elapsed(self, monkeypatch):
        monkeypatch.setenv("WIFEED_API_KEY", "fake_key")
        wu._last_fetch_ts = time.time() - 120

        fake_resp = MagicMock(status_code=200, json=lambda: {"data": _sample_data()})
        with patch.object(wu.time, "sleep") as mock_sleep, \
                patch.object(wu.requests, "get", return_value=fake_resp):
            wu._fetch_wifeed()
        assert not mock_sleep.called


class TestFetchWifeedSuccessPath:
    def test_returns_stocks_and_all_as_separate_dataframes(self, monkeypatch):
        monkeypatch.setenv("WIFEED_API_KEY", "fake_key")
        wu._last_fetch_ts = 0.0
        data = _sample_data()
        fake_resp = MagicMock(status_code=200, json=lambda: {"data": data})

        with patch.object(wu.requests, "get", return_value=fake_resp):
            df_stocks, df_all = wu._fetch_wifeed()

        assert len(df_all) == len(data)
        assert len(df_stocks) == 5  # 2 mã chỉ số bị loại khỏi df_stocks
        assert "VNINDEX" not in df_stocks["Ticker"].values
        assert "VNINDEX" in df_all["Ticker"].values

    def test_updates_last_fetch_timestamp(self, monkeypatch):
        monkeypatch.setenv("WIFEED_API_KEY", "fake_key")
        wu._last_fetch_ts = 0.0
        fake_resp = MagicMock(status_code=200, json=lambda: {"data": _sample_data()})
        with patch.object(wu.requests, "get", return_value=fake_resp):
            wu._fetch_wifeed()
        assert wu._last_fetch_ts > 0.0


class TestFetchWifeedErrorHandlingRegressions:
    """
    [BUG THẬT — xem docstring đầu file] 2 test dưới đây khẳng định hợp đồng
    (contract) ĐÚNG của hàm: `_fetch_wifeed()` PHẢI luôn trả về tuple 2
    phần tử `(df_stocks, df_all)`, kể cả khi lỗi — vì MỌI nơi gọi hàm này
    trong codebase đều unpack 2 giá trị. Với code hiện tại, 2 test này SẼ
    FAIL vì 2 nhánh early-return (thiếu API key / HTTP lỗi) chỉ trả về 1
    DataFrame thay vì tuple. Đây là bug cần fix trong wifeed_updater.py,
    KHÔNG phải lỗi viết sai của test.
    """

    def test_fetch_wifeed_returns_tuple_when_missing_api_key(self, monkeypatch):
        monkeypatch.setenv("WIFEED_API_KEY", "")
        result = wu._fetch_wifeed()
        assert isinstance(result, tuple) and len(result) == 2, (
            "_fetch_wifeed() trả về "
            f"{type(result).__name__} thay vì tuple 2 phần tử khi thiếu "
            "API key — mọi lời gọi 'df_stocks, df_all = _fetch_wifeed()' "
            "trong codebase sẽ crash ValueError. Sửa: đổi "
            "'return pd.DataFrame()' thành "
            "'return pd.DataFrame(), pd.DataFrame()' ở nhánh thiếu API key."
        )

    def test_fetch_wifeed_returns_tuple_on_http_error(self, monkeypatch):
        monkeypatch.setenv("WIFEED_API_KEY", "fake_key")
        wu._last_fetch_ts = 0.0
        bad_resp = MagicMock(status_code=500, text="internal server error")
        with patch.object(wu.requests, "get", return_value=bad_resp):
            result = wu._fetch_wifeed()
        assert isinstance(result, tuple) and len(result) == 2, (
            "_fetch_wifeed() trả về "
            f"{type(result).__name__} thay vì tuple 2 phần tử khi HTTP "
            "trả lỗi (vd Wifeed rate-limit ban trả 4xx/5xx) — scheduler sẽ "
            "crash đúng lúc Wifeed đang gặp sự cố, thay vì log rồi bỏ qua "
            "như ý đồ thiết kế. Sửa: đổi 'return pd.DataFrame()' thành "
            "'return pd.DataFrame(), pd.DataFrame()' ở nhánh HTTP != 200."
        )

    def test_timeout_returns_two_empty_dataframes(self, monkeypatch):
        """Nhánh timeout/connection-error KHÔNG có bug — đã đúng tuple sẵn,
        test này giữ vai trò hồi quy để đảm bảo không bị sửa sai sau này."""
        import requests as real_requests
        monkeypatch.setenv("WIFEED_API_KEY", "fake_key")
        wu._last_fetch_ts = 0.0
        with patch.object(wu.requests, "get", side_effect=real_requests.exceptions.Timeout()):
            df_stocks, df_all = wu._fetch_wifeed()
        assert df_stocks.empty and df_all.empty

    def test_connection_error_returns_two_empty_dataframes(self, monkeypatch):
        import requests as real_requests
        monkeypatch.setenv("WIFEED_API_KEY", "fake_key")
        wu._last_fetch_ts = 0.0
        with patch.object(wu.requests, "get",
                           side_effect=real_requests.exceptions.ConnectionError()):
            df_stocks, df_all = wu._fetch_wifeed()
        assert df_stocks.empty and df_all.empty


# ─────────────────────────────────────────────────────────────
# Getters đơn giản
# ─────────────────────────────────────────────────────────────

class TestGetters:
    def test_get_realtime_snapshot_returns_current_dict(self, tmp_paths):
        assert wu.get_realtime_snapshot() == {}
        df = wu._parse_wifeed_response(_sample_data())
        wu._save_realtime_cache(df)
        assert wu.get_realtime_snapshot() != {}

    def test_get_snapshot_timestamp_starts_at_zero(self):
        assert wu.get_snapshot_timestamp() == 0.0

    def test_get_realtime_index_starts_empty(self):
        assert wu.get_realtime_index() == {}


# ─────────────────────────────────────────────────────────────
# (Tùy chọn) Sanity check trên file mẫu Wifeed THẬT, nếu người dùng đặt
# file tại tests/fixtures/wifeed_output_sample.txt — bỏ qua nếu không có,
# để không bắt buộc mọi máy CI phải có file mẫu ~850KB này.
# ─────────────────────────────────────────────────────────────

_REAL_SAMPLE_PATH = os.path.join(
    os.path.dirname(__file__), "fixtures", "wifeed_output.txt"
)


@pytest.mark.skipif(
    not os.path.exists(_REAL_SAMPLE_PATH),
    reason=f"Không có file mẫu thật tại {_REAL_SAMPLE_PATH} — bỏ qua sanity check tích hợp.",
)
class TestParseRealWifeedSample:
    def test_parses_real_captured_response_without_error(self):
        with open(_REAL_SAMPLE_PATH, encoding="utf-8") as f:
            payload = json.load(f)
        data = payload["data"]
        df_all = wu._parse_wifeed_response_all(data)
        df_stocks = wu._parse_wifeed_response(data)
        assert len(df_all) == len(data)
        assert len(df_stocks) <= len(df_all)
        assert df_stocks["Ceiling"].notna().all()


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))