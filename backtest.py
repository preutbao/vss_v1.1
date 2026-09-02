"""
backtest.py — Backtest Engine cho hệ thống FSS (Vietcap Smart Screener)
=========================================================================
BẢN V2 — viết lại sau khi đọc trực tiếp `quant_engine.py`, `data_loader.py`
và `quant_engine_strategies.py` thật, và sau khi đối chiếu với đánh giá kỹ
thuật của BGK (xem "NHẬT KÝ SỬA LỖI V2" bên dưới). Mục tiêu: dữ liệu xuất ra
từ file này phải chịu được câu hỏi "làm sao chứng minh không có look-ahead
bias?" từ hội đồng giám khảo.

MỤC ĐÍCH
--------
Backtest VGM Score và 11 chiến lược (STRAT_*) dùng ĐÚNG hàm scoring thật
(`calculate_all_scores`, `run_strategy`) và ĐÚNG loader thật
(`load_market_data`, `load_financial_data`, `load_index_data`), với point-in-
time layer đầy đủ để tránh Look-ahead Bias — cả ở lớp tài chính (BCTC) LẪN
lớp kỹ thuật (giá/chỉ số), vốn là lỗ hổng nghiêm trọng nhất của bản V1.

NHẬT KÝ SỬA LỖI V2 (so với bản V1 đã bị BGK chỉ ra 4 Critical + 7 Major)
--------------------------------------------------------------------------
CRITICAL #1 — Technical indicators nhìn thấy tương lai (ĐÃ SỬA TẬN GỐC):
  `calculate_all_scores()` trong quant_engine.py (khối Technical Indicators
  dòng ~1149-1161 và khối ADX/Lifecycle dòng ~1272-1274) trước đây TỰ gọi
  `load_market_data()`/`load_index_data()` — load TOÀN BỘ dữ liệu hiện có
  trên đĩa, bỏ qua hoàn toàn snapshot point-in-time truyền vào tham số đầu.
  Đã sửa TRỰC TIẾP trong quant_engine.py: hàm giờ nhận thêm
  `as_of_date`, `df_price_full_override`, `df_index_override` (mặc định
  None -> hành vi live app KHÔNG đổi). Khi backtest gọi, nó truyền đúng dữ
  liệu đã cắt tại as_of_date, và có ASSERTION ngay trong quant_engine.py:
  `max(date đã dùng) <= as_of_date` — nếu vi phạm, lỗi ném ra ngay, không
  âm thầm cho qua. Đây là cách sửa sạch (refactor), KHÔNG PHẢI monkeypatch.

CRITICAL #2 — VGM dùng "hôm nay" thật để tính độ cũ BCTC (ĐÃ SỬA TẬN GỐC):
  `calculate_vgm_score()` trước đây dùng `pd.Timestamp.now()`. Đã sửa nhận
  thêm `as_of_date` (mặc định None -> now() như cũ cho live app), backtest
  truyền đúng ngày lịch sử đang mô phỏng.

CRITICAL #3 — Same-bar execution bias (ĐÃ SỬA): trước đây tín hiệu tạo từ
  `df_price_asof <= date` rồi mua/bán NGAY tại giá đóng cửa của chính ngày
  `date` đó — không thể có trong thực tế (tín hiệu chỉ hoàn tất SAU khi đóng
  cửa). Giờ: signal_day = ngày giao dịch gần nhất có dữ liệu tại mốc tái cơ
  cấu (quý + lag), execution_day = ngày giao dịch KẾ TIẾP (D+1). Portfolio
  chỉ giao dịch tại giá của execution_day, không bao giờ tại giá của
  signal_day.

CRITICAL #4 — Raw/Adjusted price (KHÔNG THỂ SỬA TẬN GỐC — thiếu cột đánh
  dấu nguồn giá trong dữ liệu). Đã thêm DIAGNOSTIC: quét toàn bộ price
  matrix, đếm số lần return 1 phiên vượt ±40% (dấu hiệu chia tách/cổ tức
  không được điều chỉnh hoặc lỗi dữ liệu) và in ra cảnh báo cuối mỗi lần
  chạy — KHÔNG tự động sửa dữ liệu (vì không chắc đó là lỗi hay biến động
  thật), chỉ đảm bảo minh bạch để bạn tự quyết định có cần làm sạch dữ liệu
  nguồn trước khi trình BGK hay không.

MAJOR #9 — Fallback Fill (ĐÃ SỬA): `ENABLE_FALLBACK_FILL` giờ mặc định
  **False** (tắt) — danh mục giữ đúng số mã đạt chuẩn filter + phần còn lại
  là TIỀN MẶT, đúng bản chất của chiến lược gốc. Có thể bật lại bằng
  `config.enable_fallback_fill = True` nếu muốn so sánh, nhưng nhãn kết quả
  sẽ khác nhau rõ ràng trong log.

MAJOR #11 — Liquidity floor cố định 100 triệu (ĐÃ SỬA): thay bằng ngưỡng
  ADV20 ĐỘNG theo % tham gia thị trường: `trade_value <= max_participation_pct
  x ADV20`. Với vốn 1 tỷ / top_n=20 (~50 triệu/mã) và max_participation_pct
  mặc định 8%, ngưỡng ADV20 tối thiểu ≈ 625 triệu/phiên — nghiêm hơn nhiều so
  với sàn 100 triệu cũ.

MAJOR #12 — So sánh không đồng bộ điểm bắt đầu (ĐÃ SỬA — Cách A theo đề
  xuất BGK): các chỉ số hiệu suất (CAGR/MDD/Sharpe) được tính từ đúng ngày
  giao dịch ĐẦU TIÊN của danh mục (execution day của lần rebalance đầu
  tiên), KHÔNG PHẢI từ config.start_date. Benchmark được re-normalize về
  đúng mốc vốn tại ngày đó để so sánh "táo với táo". Equity curve đầy đủ
  (kể cả đoạn 100% tiền mặt chờ rebalance đầu tiên) vẫn được lưu ra CSV để
  minh bạch, chỉ riêng METRICS là tính trên đoạn đã căn chỉnh.

MAJOR #13 — Lịch weekday giả (ĐÃ SỬA): trading calendar giờ lấy TRỰC TIẾP
  từ các ngày VNINDEX thực sự có quan sát (`load_index_data()`), không dùng
  `pd.date_range(freq="B")` nữa — loại bỏ hoàn toàn ngày nghỉ lễ VN giả làm
  "phiên đứng yên".

MAJOR #14 — Stale/suspended price (ĐÃ GIẢM THIỂU): trước khi chấm điểm,
  loại các mã có khoảng cách giữa as_of_date và ngày giao dịch thực tế cuối
  cùng (KHÔNG PHẢI ngày forward-fill) vượt `config.max_stale_days` (mặc định
  20 ngày lịch, ~1 tháng) ra khỏi danh sách ứng viên MỚI. Đã lưu ý: các vị
  thế ĐANG NẮM GIỮ mà trở nên "ma" vẫn được mark-to-market bằng giá cuối
  cùng đã biết (quy ước phổ biến, không tự động ép bán ở giá phantom) — đây
  là giới hạn còn lại, xem "CÁC GIỚI HẠN CÒN LẠI" bên dưới.

MODERATE #15 — Transaction cost & final NAV (ĐÃ SỬA):
  (a) Tách phí mua (chỉ brokerage) và phí bán (brokerage + thuế bán 0.1%) —
      trước đây áp cùng 0.15% cho cả 2 chiều, không đúng bản chất thuế VN.
  (b) `liquidate_all()` cuối kỳ giờ được VÁ vào equity_history — CAGR cuối
      cùng đã net-of-cost thanh lý, không bị "quên" như bản V1.

MODERATE #16 — Win Rate luôn kèm sample size (N Trades) trong summary, để
  không hiểu sai 76% của 16 lệnh với 76% của 160 lệnh.

KHÔNG THAY ĐỔI (theo đúng đề xuất của BGK):
  - `quant_engine_strategies.py`: review không chỉ ra lỗi cụ thể nào trong
    file này; toàn bộ filter/apply_fn giữ nguyên.
  - Monkeypatch `_point_in_time_quarterly` cho CANSLIM (nó tự gọi
    `load_financial_data_nocache('quarterly')` trực tiếp bên trong
    quant_engine_strategies.py, không đi qua `calculate_all_scores()`, nên
    không sửa được bằng tham số override — patch tạm thời là cách hợp lý).
  - Monkeypatch `disable_live_index_constituents` cho VN30/VN100 (API sống).

CÁC GIỚI HẠN CÒN LẠI (đọc trước khi dùng số liệu để thuyết trình)
------------------------------------------------------------------
- PUBLISH LAG vẫn là giả định (không có Publish Date thật trong dữ liệu):
  mặc định 90 ngày cho BCTC năm, 45 ngày cho BCTC quý.
- Giá có thể là hỗn hợp raw/adjusted — xem CRITICAL #4 ở trên. Diagnostic
  in ra số lần jump bất thường, nhưng KHÔNG tự sửa dữ liệu nguồn.
- Vị thế đang nắm giữ mà thành "mã ma" (ngừng giao dịch dài ngày) vẫn được
  mark-to-market bằng giá cuối cùng đã biết cho tới khi được rebalance loại
  khỏi target list ở lần tái cơ cấu kế tiếp (bán tại giá forward-fill đó) —
  xem MAJOR #14. Muốn xử lý triệt để cần cột "trạng thái niêm yết" thật.
- Universe hiện tại = mã CÒN tồn tại trong parquet giá hiện có. Nếu file giá
  không chứa các mã đã hủy niêm yết trong quá khứ, kết quả có thể có
  survivorship bias — chưa đủ dữ liệu để xác nhận hay bác bỏ điều này.
- Fallback fill mặc định TẮT (khác V1) — một số chiến lược lọc chặt (đặc
  biệt CANSLIM) có thể trả về portfolio ít hơn top_n mã, phần còn lại là
  tiền mặt. Đây là hành vi ĐÚNG với triết lý gốc, không phải lỗi.
- Position sizing dùng để tính ngưỡng thanh khoản ADV20 là XẤP XỈ
  (initial_capital / top_n), không phải NAV thực tế tại từng thời điểm —
  đủ tốt cho việc lọc thanh khoản nhưng không phải con số chính xác tuyệt
  đối.

CÁCH CHẠY
---------
    python backtest.py --strategy VGM
    python backtest.py                      # VGM + toàn bộ 11 chiến lược
    python backtest.py --start 2023-01-01 --end 2026-08-01 --top-n 20
    python backtest.py --project-root /path/to/VSS   # nếu backtest.py không
                                                       # nằm cùng cấp với src/
    python backtest.py --enable-fallback-fill         # bật lại fallback (V1)
    python backtest.py --strategy VGM --sensitivity   # + robustness Top N/cost/lag
"""

from __future__ import annotations

import os
import sys
import argparse
import time
from pathlib import Path
from contextlib import contextmanager

import numpy as np
import pandas as pd


# --------------------------------------------------------------------------
# 0. PROJECT ROOT
# --------------------------------------------------------------------------
def _setup_project_root(project_root: str | None) -> Path:
    root = Path(project_root).resolve() if project_root else Path(__file__).resolve().parent
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    return root


_DEFAULT_ROOT = _setup_project_root(None)

try:
    import src.backend.data_loader as data_loader_module
    from src.backend.data_loader import load_market_data, load_financial_data, load_index_data
    from src.backend.quant_engine import calculate_all_scores
    from src.backend.quant_engine_strategies import run_strategy
except ImportError as e:
    raise ImportError(
        "Không import được src.backend.data_loader / quant_engine / "
        "quant_engine_strategies.\n"
        "backtest.py cần được đặt CÙNG CẤP với thư mục 'src/' của repo VSS "
        "(hoặc chạy với --project-root /path/to/VSS).\n"
        f"Đang tìm ở: {_DEFAULT_ROOT}"
    ) from e


# ==========================================================================
# CONFIG
# ==========================================================================
class BacktestConfig:
    def __init__(self):
        self.start_date = "2023-01-01"
        self.end_date: str | None = None          # None -> hôm nay
        self.initial_capital = 1_000_000_000.0    # 1 tỷ VNĐ
        self.top_n = 20

        # --- CHI PHÍ GIAO DỊCH (tách buy/sell — MODERATE #15a) ---
        # Brokerage áp dụng CẢ 2 CHIỀU; thuế bán 0.1% CHỈ áp dụng khi BÁN.
        self.brokerage_pct = 0.0005    # 0.05% phí môi giới
        self.sell_tax_pct = 0.001      # 0.10% thuế bán (chỉ khi bán)

        self.lag_days_yearly = 90     # giả định trễ công bố BCTC năm (kiểm toán)
        self.lag_days_quarterly = 45  # giả định trễ công bố BCTC quý
        self.risk_free_rate = 0.05    # 5%/năm — lãi suất gửi tiết kiệm VN tham chiếu

        # --- THANH KHOẢN (MAJOR #11): ADV20 động thay vì sàn cố định ---
        self.max_participation_pct = 0.08   # trade_value <= 8% ADV20
        self.min_liquidity_floor_vnd = 50_000_000.0  # sàn tuyệt đối, phòng top_n lớn

        # --- FALLBACK FILL (MAJOR #9): mặc định TẮT, khác bản V1 ---
        self.enable_fallback_fill = False

        # --- STALE PRICE GATE (MAJOR #14) ---
        self.max_stale_days = 20   # ngày LỊCH, không phải phiên

        # --- Diagnostic: ngưỡng return 1 phiên coi là "bất thường" (%) ---
        self.anomaly_return_threshold_pct = 40.0


# ==========================================================================
# 1. POINT-IN-TIME LAYER — TÀI CHÍNH (giữ nguyên logic V1, đã đúng)
# ==========================================================================
def add_available_date(df_fin: pd.DataFrame, lag_days: int) -> pd.DataFrame:
    """available_date = ngày kỳ báo cáo (Date) + độ trễ công bố giả định."""
    df = df_fin.copy()
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df["available_date"] = df["Date"] + pd.Timedelta(days=lag_days)
    return df


def get_financial_history_asof(df_fin_avail: pd.DataFrame, as_of_date: pd.Timestamp) -> pd.DataFrame:
    """Trả về TOÀN BỘ lịch sử (nhiều dòng/ticker) có available_date <=
    as_of_date — KHÔNG rút gọn về 1 dòng/ticker (calculate_all_scores() tự
    làm groupby('Ticker').last() / tính CAGR, YoY bên trong)."""
    valid = df_fin_avail[df_fin_avail["available_date"] <= as_of_date]
    return valid.drop(columns=["available_date"], errors="ignore")


def generate_rebalance_dates(start: str, end: str, lag_days_quarterly: int) -> list[pd.Timestamp]:
    """Mốc tái cơ cấu DỰ KIẾN = cuối mỗi quý + độ trễ công bố quý. Đây chỉ
    là mốc "sớm nhất BCTC quý có thể coi là công bố" — ngày SIGNAL/EXECUTION
    thật sự được snap vào trading calendar thật ở compute_rebalance_events()."""
    quarter_ends = pd.date_range(start=start, end=end, freq="QE")
    rebal_dates = quarter_ends + pd.Timedelta(days=lag_days_quarterly)
    return list(rebal_dates[rebal_dates <= pd.Timestamp(end)])


# ==========================================================================
# 2. TRADING CALENDAR THẬT (MAJOR #13) — lấy từ chính VNINDEX
# ==========================================================================
def load_index_dataframe() -> pd.DataFrame:
    df_index = load_index_data()
    if df_index is None or df_index.empty or "VNINDEX_Close" not in df_index.columns:
        raise RuntimeError(
            "load_index_data() rỗng hoặc thiếu cột VNINDEX_Close — không thể "
            "xây trading calendar thật hoặc benchmark. Kiểm tra lại nguồn dữ liệu index."
        )
    df_index = df_index.copy()
    df_index["Date"] = pd.to_datetime(df_index["Date"], errors="coerce")
    df_index = df_index.dropna(subset=["Date", "VNINDEX_Close"]).sort_values("Date")
    df_index = df_index.drop_duplicates(subset=["Date"], keep="last")
    return df_index


def build_trading_calendar(df_index: pd.DataFrame, start: str, end: str) -> pd.DatetimeIndex:
    """Ngày nào VNINDEX có observation hợp lệ trong [start, end] thì đó là
    phiên giao dịch — thay hoàn toàn cho pd.date_range(freq='B') giả."""
    mask = (df_index["Date"] >= pd.Timestamp(start)) & (df_index["Date"] <= pd.Timestamp(end))
    days = pd.DatetimeIndex(sorted(df_index.loc[mask, "Date"].unique()))
    if len(days) == 0:
        raise RuntimeError(f"Không có phiên giao dịch VNINDEX nào trong [{start}, {end}].")
    return days


def build_benchmark_series(df_index: pd.DataFrame, trading_days: pd.DatetimeIndex,
                            initial_capital: float) -> pd.Series:
    s = df_index.set_index("Date")["VNINDEX_Close"].sort_index()
    s = s.reindex(trading_days).ffill().dropna()
    return (s / s.iloc[0] * initial_capital).rename("Total Value")


def build_exchange_map() -> dict:
    """Đọc đuôi sàn (.HM/.HN/.HNO) từ parquet giá GỐC để gắn cột Exchange —
    cần cho gatekeeper của STRAT_ADX_MOMENTUM (loại UPCOM)."""
    try:
        raw_path = Path(data_loader_module.PROCESSED_DIR) / data_loader_module.FILES["parquet_price"]
        if not raw_path.exists():
            return {}
        ticker_raw = pd.read_parquet(raw_path, columns=["Ticker"])
        ticker_raw["_Exchange"] = ""
        ticker_raw.loc[ticker_raw["Ticker"].str.endswith(".HNO", na=False), "_Exchange"] = "UPCOM"
        ticker_raw.loc[ticker_raw["Ticker"].str.endswith(".HN", na=False), "_Exchange"] = "HNX"
        ticker_raw.loc[ticker_raw["Ticker"].str.endswith(".HM", na=False), "_Exchange"] = "HOSE"
        ticker_raw["Ticker"] = ticker_raw["Ticker"].str.replace(r"\.(HNO|HN|HM)$", "", regex=True)
        ticker_raw = ticker_raw[ticker_raw["_Exchange"] != ""]
        return ticker_raw.drop_duplicates("Ticker").set_index("Ticker")["_Exchange"].to_dict()
    except Exception as e:
        print(f"[Cảnh báo] Không build được Exchange map: {e}")
        return {}


# ==========================================================================
# 3. GIÁ: MA TRẬN + STALE TRACKING + DIAGNOSTIC ANOMALY (Critical #4, Major #14)
# ==========================================================================
def build_price_matrix(df_price: pd.DataFrame, trading_days: pd.DatetimeIndex) -> pd.DataFrame:
    """Pivot giá đóng cửa thành ma trận Date x Ticker trên ĐÚNG trading
    calendar thật (không phải weekday giả), forward-fill CHỈ để lấp phiên mã
    không khớp lệnh (KHÔNG lấp ngày nghỉ lễ vì ngày nghỉ đã bị loại khỏi
    trading_days từ đầu)."""
    pivot = df_price.pivot_table(index="Date", columns="Ticker", values="Price Close")
    return pivot.reindex(trading_days).ffill()


def build_last_actual_trade_date(df_price: pd.DataFrame, trading_days: pd.DatetimeIndex) -> pd.DataFrame:
    """Với mỗi (Date, Ticker) trong trading_days, trả về ngày giao dịch THỰC
    TẾ gần nhất (không forward-fill giả) <= Date. Dùng để phát hiện mã
    'ma'/ngừng giao dịch dài ngày (MAJOR #14)."""
    raw = df_price.pivot_table(index="Date", columns="Ticker", values="Price Close")
    raw = raw.reindex(trading_days)
    has_actual = raw.notna()
    date_if_actual = pd.DataFrame(
        np.where(has_actual, np.tile(trading_days.values.reshape(-1, 1), (1, raw.shape[1])), np.datetime64("NaT")),
        index=trading_days, columns=raw.columns,
    )
    date_if_actual = date_if_actual.apply(pd.to_datetime)
    return date_if_actual.ffill()


def diagnose_price_anomalies(df_price: pd.DataFrame, threshold_pct: float) -> int:
    """CRITICAL #4 — không tự sửa raw/adjusted price (thiếu cột nguồn để
    biết chắc), chỉ đếm & cảnh báo số lần return 1 phiên vượt ngưỡng, dấu
    hiệu khả dĩ của chia tách/cổ tức chưa điều chỉnh hoặc lỗi dữ liệu."""
    df = df_price.sort_values(["Ticker", "Date"]).copy()
    df["_ret"] = df.groupby("Ticker", sort=False)["Price Close"].pct_change()
    n_anomalies = int((df["_ret"].abs() * 100 > threshold_pct).sum())
    if n_anomalies > 0:
        print(
            f"[Diagnostic] Phát hiện {n_anomalies} lần return 1 phiên vượt "
            f"±{threshold_pct:.0f}% trong dữ liệu giá — có thể do chia tách/"
            f"cổ tức chưa điều chỉnh, hoặc lỗi dữ liệu. KHÔNG tự sửa; xem "
            f"docstring 'CRITICAL #4' đầu file trước khi dùng số liệu thuyết trình."
        )
    return n_anomalies


# ==========================================================================
# 4. MONKEYPATCH — chỉ còn 2 điểm KHÔNG sửa được bằng tham số trực tiếp
# ==========================================================================
@contextmanager
def _point_in_time_quarterly(df_fin_q_asof: pd.DataFrame):
    """calculate_canslim_metrics() trong quant_engine_strategies.py tự gọi
    load_financial_data_nocache('quarterly') trực tiếp — không đi qua
    calculate_all_scores() nên không vá được bằng override param. Ép nó dùng
    đúng BCTC quý đã có tại as_of_date trong lúc chạy CANSLIM."""
    original_fn = data_loader_module.load_financial_data_nocache

    def _patched(report_type: str = "quarterly"):
        if report_type == "quarterly":
            return df_fin_q_asof
        return original_fn(report_type)

    data_loader_module.load_financial_data_nocache = _patched
    try:
        yield
    finally:
        data_loader_module.load_financial_data_nocache = original_fn


def disable_live_index_constituents():
    """STRAT_ADX_MOMENTUM gọi fetch_index_constituents() — API sống của SSI
    lấy rổ VN30/VN100 HIỆN TẠI chỉ để ưu tiên sắp xếp (không phải điều kiện
    lọc cứng). Tắt cho backtest: nhanh hơn, không cần mạng, không dùng rổ chỉ
    số hiện tại cho một thời điểm lịch sử."""
    def _empty(index_code):
        return [], None
    data_loader_module.fetch_index_constituents = _empty


# ==========================================================================
# 5. TIỀN XỬ LÝ GIÁ TRƯỚC KHI CHẤM ĐIỂM (mô phỏng _build_snapshot_df)
# ==========================================================================
def build_latest_price_snapshot(df_price_asof: pd.DataFrame, as_of_date: pd.Timestamp,
                                 max_stale_days: int) -> pd.DataFrame:
    """Mô phỏng tiền xử lý của data_loader._build_snapshot_df(): Avg_Vol_20D,
    Avg_Vol_20D_VND, Sparkline_30D, EPS_Growth_QoQ — VÀ áp STALE PRICE GATE
    (MAJOR #14): loại mã có khoảng cách tới ngày giao dịch thực tế cuối cùng
    > max_stale_days ra khỏi ứng viên MỚI cho lần rebalance này."""
    df = df_price_asof.sort_values(["Ticker", "Date"]).copy()

    df["Avg_Vol_20D"] = (
        df.groupby("Ticker", sort=False)["Volume"]
          .transform(lambda x: x.rolling(20, min_periods=1).mean())
          .round(0).fillna(0)
    )
    df["Avg_Vol_20D_VND"] = (df["Avg_Vol_20D"] * df["Price Close"]).round(0).fillna(0)

    df_latest = df.drop_duplicates(subset=["Ticker"], keep="last").copy()

    # --- STALE PRICE GATE (MAJOR #14) ---
    stale_days = (as_of_date - df_latest["Date"]).dt.days
    n_before = len(df_latest)
    df_latest = df_latest[stale_days <= max_stale_days]
    n_excluded = n_before - len(df_latest)
    if n_excluded > 0:
        print(f"[Stale Gate] Loại {n_excluded}/{n_before} mã không có giao dịch thực "
              f"trong {max_stale_days} ngày gần {as_of_date.date()} (khỏi ứng viên mới).")

    if "EPS Growth YoY (%)" in df_latest.columns:
        df_latest["EPS_Growth_QoQ"] = df_latest["EPS Growth YoY (%)"]
    else:
        df_latest["EPS_Growth_QoQ"] = float("nan")

    spark_map = (
        df.groupby("Ticker", sort=False)["Price Close"]
          .apply(lambda s: s.tail(30).round(0).tolist())
          .to_dict()
    )
    df_latest["Sparkline_30D"] = df_latest["Ticker"].map(spark_map)

    return df_latest


# ==========================================================================
# 6. XẾP HẠNG / CHỌN DANH MỤC THEO TỪNG CHIẾN LƯỢC
# ==========================================================================
ALREADY_SORTED_STRATEGIES = {"STRAT_MAGIC", "STRAT_NCN", "STRAT_DIVIDEND", "STRAT_ADX_MOMENTUM"}

EXPLICIT_SCORE_COLS = {
    "STRAT_PIOTROSKI": "f_score",
}

STRATEGY_METRIC_COLS = {
    "STRAT_VALUE": ["current_ratio", "eps_growth_5y"],
    "STRAT_TURNAROUND": ["operating_margin", "pe_historical_norm", "peg_ratio"],
    "STRAT_QUALITY": ["gross_margin", "re_growth", "fcf_margin"],
    "STRAT_GARP": ["eps_growth_1y", "peg", "sgr"],
    "STRAT_CANSLIM": ["eps_growth_y", "eps_growth_q", "rev_growth_q", "rs_rating"],
    "STRAT_GROWTH": ["rev_growth_5y", "gross_margin", "reinvest_rate"],
}

LOWER_IS_BETTER = {
    "STRAT_TURNAROUND": {"pe_historical_norm": True, "peg_ratio": True},
    "STRAT_GARP": {"peg": True},
}

# Vai trò ex-ante cho appendix / slide (KHÔNG dựa vào kết quả backtest —
# tránh ex-post cherry-picking, xem mục 18 trong đánh giá BGK).
STRATEGY_ROLE = {
    "VGM": "Core",
    "STRAT_ADX_MOMENTUM": "Aggressive",
    "STRAT_MAGIC": "Defensive",
}


def _rank_by_metrics(df: pd.DataFrame, cols: list[str], lower_is_better: dict) -> pd.DataFrame:
    """Ranking dự phòng: trung bình z-score các metric thành phần — chỉ dùng
    khi chiến lược chưa có sẵn 1 cột điểm tổng hợp cuối cùng trong code gốc.
    LƯU Ý (MAJOR #10): đây là quy tắc PORTFOLIO CONSTRUCTION do backtester bổ
    sung, KHÔNG PHẢI một phần của filter FSS gốc — tách biệt rõ khi báo cáo."""
    z = pd.DataFrame(index=df.index)
    for c in cols:
        if c not in df.columns:
            continue
        col = pd.to_numeric(df[c], errors="coerce")
        if lower_is_better.get(c, False):
            col = -col
        std = col.std()
        z[c] = (col - col.mean()) / std if std and not np.isnan(std) else 0.0
    df = df.copy()
    df["_composite_score"] = z.mean(axis=1) if not z.empty else np.nan
    return df.sort_values("_composite_score", ascending=False)


def select_portfolio(
    df_price_asof: pd.DataFrame,
    df_fin_y_asof: pd.DataFrame,
    df_fin_q_asof: pd.DataFrame,
    df_index_asof: pd.DataFrame,
    as_of_date: pd.Timestamp,
    strategy_id: str,
    top_n: int,
    exchange_map: dict,
    config: "BacktestConfig",
) -> list[str]:
    """Xây snapshot tại 1 thời điểm CHỈ từ dữ liệu đã "biết" tại thời điểm
    đó (giá, BCTC, VÀ chỉ số VNINDEX dùng cho technical/RS/ADX), chấm điểm
    bằng đúng hàm scoring thật của VSS, trả về Top N mã."""
    if df_price_asof.empty or df_fin_y_asof.empty:
        return []

    latest_price_snapshot = build_latest_price_snapshot(
        df_price_asof, as_of_date, config.max_stale_days
    )

    # --- LỌC THANH KHOẢN (MAJOR #11): ngưỡng ADV20 ĐỘNG theo % tham gia ---
    assumed_position_value = config.initial_capital / max(top_n, 1)
    min_avg_turnover_vnd = max(
        config.min_liquidity_floor_vnd,
        assumed_position_value / config.max_participation_pct,
    )
    if "Avg_Vol_20D_VND" in latest_price_snapshot.columns:
        n_before = len(latest_price_snapshot)
        latest_price_snapshot = latest_price_snapshot[
            latest_price_snapshot["Avg_Vol_20D_VND"] >= min_avg_turnover_vnd
        ]
        n_excluded = n_before - len(latest_price_snapshot)
        if n_excluded > 0:
            print(f"[Liquidity Filter] {strategy_id}: loại {n_excluded}/{n_before} mã "
                  f"có GTGD BQ 20 phiên < {min_avg_turnover_vnd:,.0f} VNĐ "
                  f"(<={config.max_participation_pct*100:.0f}% ADV20 cho vị thế ~"
                  f"{assumed_position_value:,.0f} VNĐ)")

    try:
        df_snapshot = calculate_all_scores(
            latest_price_snapshot, df_fin_y_asof,
            as_of_date=as_of_date,
            df_price_full_override=df_price_asof,
            df_index_override=df_index_asof,
        )
    except AssertionError:
        raise  # PIT violation — KHÔNG nuốt lỗi, phải nổi lên ngoài (xem CRITICAL #1)
    except Exception as e:
        raise RuntimeError(
            f"calculate_all_scores() thất bại cho strategy={strategy_id}. Lỗi gốc: {e}"
        ) from e

    if df_snapshot.empty:
        return []

    if exchange_map and "Ticker" in df_snapshot.columns:
        df_snapshot["Exchange"] = df_snapshot["Ticker"].map(exchange_map).fillna("")

    if strategy_id == "VGM":
        if "VGM_Score_Num" not in df_snapshot.columns:
            raise KeyError("Không tìm thấy cột 'VGM_Score_Num' trong output calculate_all_scores().")
        ranked = df_snapshot.sort_values("VGM_Score_Num", ascending=False)
        return ranked["Ticker"].head(top_n).tolist()

    if strategy_id == "STRAT_CANSLIM":
        with _point_in_time_quarterly(df_fin_q_asof):
            df_strat = run_strategy(df_snapshot, strategy_id, df_fin_y_asof)
    else:
        df_strat = run_strategy(df_snapshot, strategy_id, df_fin_y_asof)

    if strategy_id in ALREADY_SORTED_STRATEGIES:
        ranked = df_strat if not df_strat.empty else df_strat
    elif strategy_id in EXPLICIT_SCORE_COLS:
        ranked = df_strat.sort_values(EXPLICIT_SCORE_COLS[strategy_id], ascending=False) if not df_strat.empty else df_strat
    else:
        cols = STRATEGY_METRIC_COLS.get(strategy_id, [])
        lower_is_better = LOWER_IS_BETTER.get(strategy_id, {})
        ranked = _rank_by_metrics(df_strat, cols, lower_is_better) if not df_strat.empty else df_strat

        # --- FALLBACK FILL (MAJOR #9): mặc định TẮT — xem BacktestConfig ---
        if config.enable_fallback_fill and cols and len(ranked) < top_n:
            n_missing = top_n - len(ranked)
            already_have = set(ranked["Ticker"]) if not ranked.empty else set()
            remaining_pool = df_snapshot[~df_snapshot["Ticker"].isin(already_have)]
            if not remaining_pool.empty:
                filler_ranked = _rank_by_metrics(remaining_pool, cols, lower_is_better)
                filler = filler_ranked.head(n_missing)
                print(f"[Fallback Fill] {strategy_id}: bổ sung {len(filler)} mã "
                      f"(ĐÃ BẬT enable_fallback_fill — không phải hành vi mặc định).")
                ranked = pd.concat([ranked, filler], ignore_index=True) if len(ranked) else filler
        elif not config.enable_fallback_fill and cols and len(ranked) < top_n:
            print(f"[Cash Position] {strategy_id}: chỉ {len(ranked)}/{top_n} mã đạt chuẩn "
                  f"lọc cứng tại {as_of_date.date()} -> phần còn lại giữ TIỀN MẶT "
                  f"(fallback fill đang TẮT, đúng triết lý gốc của chiến lược).")

    if ranked.empty:
        return []

    return ranked["Ticker"].head(top_n).tolist()


ALL_STRATEGY_IDS = [
    "VGM", "STRAT_VALUE", "STRAT_TURNAROUND", "STRAT_QUALITY", "STRAT_GARP",
    "STRAT_DIVIDEND", "STRAT_PIOTROSKI", "STRAT_CANSLIM", "STRAT_GROWTH",
    "STRAT_MAGIC", "STRAT_NCN", "STRAT_ADX_MOMENTUM",
]


# ==========================================================================
# 7. MÔ PHỎNG DANH MỤC (equal-weight, buy/sell cost tách riêng)
# ==========================================================================
class Position:
    __slots__ = ("shares", "avg_cost")

    def __init__(self, shares: float = 0.0, avg_cost: float = 0.0):
        self.shares = shares
        self.avg_cost = avg_cost


class Portfolio:
    def __init__(self, capital: float, brokerage_pct: float, sell_tax_pct: float,
                 configured_top_n: int):
        self.cash = capital
        self.positions: dict[str, Position] = {}
        self.equity_history: list[dict] = []
        self.closed_trades: list[dict] = []
        self.brokerage_pct = brokerage_pct
        self.sell_tax_pct = sell_tax_pct
        # P0 FIX (đánh giá lần 2, mục 3-4): dùng ĐÚNG top_n cấu hình để chia
        # slot, KHÔNG dùng số mã thực sự lọt lưới (len(target_tickers)).
        # Trước đây nếu CANSLIM chỉ chọn được 4/20 mã, mỗi mã bị nhồi
        # NAV/4 (~25%) thay vì NAV/20 (5%) + 80% cash — biến "cash policy"
        # đã mô tả trong docstring thành một cam kết không có thật trong
        # code, đồng thời làm lệch giả định thanh khoản ADV20 (vốn được
        # tính trên NAV/top_n, không phải NAV/số mã thực chọn).
        self.configured_top_n = configured_top_n

    @property
    def _sell_cost_pct(self) -> float:
        return self.brokerage_pct + self.sell_tax_pct

    def _sell(self, ticker, shares_to_sell, price, date):
        pos = self.positions.get(ticker)
        if pos is None or pos.shares <= 0 or shares_to_sell <= 0:
            return
        shares_to_sell = min(shares_to_sell, pos.shares)
        proceeds = shares_to_sell * price * (1 - self._sell_cost_pct)
        self.cash += proceeds
        pos.shares -= shares_to_sell
        if pos.shares <= 1e-6:
            # Gross: chưa trừ phí. Net: đã trừ phí mua (brokerage) lúc vào
            # lệnh VÀ phí bán (brokerage + thuế) lúc ra lệnh — đây mới là
            # con số nên dùng để tính Win Rate (đánh giá lần 2, mục 14).
            gross_pnl_pct = (price - pos.avg_cost) / pos.avg_cost * 100 if pos.avg_cost > 0 else np.nan
            entry_cost_basis = pos.avg_cost * (1 + self.brokerage_pct)
            exit_net_proceeds = price * (1 - self._sell_cost_pct)
            net_pnl_pct = (
                (exit_net_proceeds - entry_cost_basis) / entry_cost_basis * 100
                if entry_cost_basis > 0 else np.nan
            )
            self.closed_trades.append({
                "Ticker": ticker, "Exit Date": date,
                "Entry Price": pos.avg_cost, "Exit Price": price,
                "Gross PnL (%)": gross_pnl_pct,
                "Net PnL (%)": net_pnl_pct,
            })
            del self.positions[ticker]

    def _buy(self, ticker, value_to_buy, price):
        if value_to_buy <= 0 or price <= 0:
            return
        cost = value_to_buy * (1 + self.brokerage_pct)
        if cost > self.cash:
            value_to_buy = self.cash / (1 + self.brokerage_pct)
            cost = self.cash
        if value_to_buy <= 0:
            return
        shares = value_to_buy / price
        pos = self.positions.get(ticker)
        if pos is None:
            self.positions[ticker] = Position(shares, price)
        else:
            total_cost = pos.avg_cost * pos.shares + value_to_buy
            pos.shares += shares
            pos.avg_cost = total_cost / pos.shares
        self.cash -= cost

    def total_value(self, price_row: pd.Series) -> float:
        val = self.cash
        for ticker, pos in self.positions.items():
            price = price_row.get(ticker, np.nan)
            if pd.notna(price):
                val += pos.shares * price
        return val

    def rebalance(self, date, target_tickers: list[str], price_row: pd.Series):
        target_tickers = [t for t in target_tickers if pd.notna(price_row.get(t, np.nan))]

        for ticker in list(self.positions.keys()):
            if ticker not in target_tickers:
                price = price_row.get(ticker, np.nan)
                if pd.notna(price):
                    self._sell(ticker, self.positions[ticker].shares, price, date)

        if not target_tickers:
            return

        current_total = self.total_value(price_row)
        # P0 FIX: chia theo configured_top_n (số slot ĐÃ CẤU HÌNH), không
        # phải theo số mã thực sự lọt lưới. Nếu target_tickers ít hơn
        # configured_top_n, phần dư tự động là CASH (không mua thêm để lấp
        # đầy). Nếu vì lý do nào đó target_tickers > configured_top_n
        # (không nên xảy ra vì select_portfolio() đã .head(top_n)), vẫn
        # chia đều theo số mã thực tế để không vượt 100% NAV.
        target_value_each = current_total / max(self.configured_top_n, len(target_tickers))

        for ticker in target_tickers:
            price = price_row[ticker]
            pos = self.positions.get(ticker)
            current_value = pos.shares * price if pos else 0.0
            diff = target_value_each - current_value
            if diff < 0:
                self._sell(ticker, -diff / price, price, date)

        for ticker in target_tickers:
            price = price_row[ticker]
            pos = self.positions.get(ticker)
            current_value = pos.shares * price if pos else 0.0
            diff = target_value_each - current_value
            if diff > 0:
                self._buy(ticker, diff, price)

    def liquidate_all(self, date, price_row: pd.Series):
        for ticker in list(self.positions.keys()):
            price = price_row.get(ticker, np.nan)
            if pd.notna(price):
                self._sell(ticker, self.positions[ticker].shares, price, date)

    def mark_to_market(self, date, price_row: pd.Series):
        self.equity_history.append({"Date": date, "Total Value": self.total_value(price_row)})

    def overwrite_last_mark(self, price_row: pd.Series):
        """MODERATE #15b: sau liquidate_all() cuối kỳ, ghi đè NAV của dòng
        cuối cùng bằng giá trị NET-OF-COST thanh lý — trước đây bị 'quên',
        khiến CAGR cuối kỳ không phản ánh đúng phí thoát vị thế."""
        if self.equity_history:
            self.equity_history[-1]["Total Value"] = self.total_value(price_row)


# ==========================================================================
# 8. VÒNG LẶP BACKTEST CHÍNH — D SIGNAL -> D+1 EXECUTION (CRITICAL #3)
# ==========================================================================
def compute_rebalance_events(rebalance_dates: list[pd.Timestamp],
                              trading_days: pd.DatetimeIndex) -> list[tuple]:
    """Với mỗi mốc tái cơ cấu dự kiến (quý + lag), snap về:
      signal_day    = phiên giao dịch thật gần nhất <= mốc đó (dữ liệu dùng
                       để tạo tín hiệu — giá/BCTC chỉ dùng <= signal_day).
      execution_day = phiên giao dịch KẾ TIẾP sau signal_day (D+1) — nơi
                       DUY NHẤT lệnh mua/bán được khớp.
    Trả về list (execution_day, signal_day) đã khử trùng theo execution_day
    (giữ signal_day mới nhất nếu 2 mốc rơi cùng 1 execution_day)."""
    td = trading_days
    n = len(td)
    events: dict[pd.Timestamp, pd.Timestamp] = {}
    for rd in rebalance_dates:
        pos = td.searchsorted(rd, side="right") - 1
        if pos < 0 or pos + 1 >= n:
            continue  # không đủ dữ liệu lịch sử, hoặc không còn phiên D+1 để khớp lệnh
        signal_day = td[pos]
        execution_day = td[pos + 1]
        events[execution_day] = signal_day
    return sorted(events.items())


def run_backtest(
    price_matrix: pd.DataFrame,
    last_actual_trade_date: pd.DataFrame,
    df_price_long: pd.DataFrame,
    df_fin_y_avail: pd.DataFrame,
    df_fin_q_avail: pd.DataFrame,
    df_index_full: pd.DataFrame,
    trading_days: pd.DatetimeIndex,
    config: BacktestConfig,
    strategy_id: str,
    exchange_map: dict,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.Timestamp | None]:
    rebalance_dates = generate_rebalance_dates(config.start_date, config.end_date, config.lag_days_quarterly)
    events = compute_rebalance_events(rebalance_dates, trading_days)
    event_map = dict(events)  # execution_day -> signal_day

    print(f"   [{strategy_id}] {len(trading_days)} phiên giao dịch thật "
          f"({trading_days[0].date()} -> {trading_days[-1].date()}), "
          f"{len(events)} lần tái cơ cấu (signal D -> execution D+1).")

    portfolio = Portfolio(config.initial_capital, config.brokerage_pct, config.sell_tax_pct,
                          configured_top_n=config.top_n)
    first_execution_day: pd.Timestamp | None = None
    t_loop_start = time.time()
    n_done = 0

    for date in trading_days:
        if date in event_map:
            signal_day = event_map[date]
            df_price_asof = df_price_long[df_price_long["Date"] <= signal_day]
            df_index_asof = df_index_full[df_index_full["Date"] <= signal_day]
            df_fin_y_asof = get_financial_history_asof(df_fin_y_avail, signal_day)
            df_fin_q_asof = get_financial_history_asof(df_fin_q_avail, signal_day)

            targets = select_portfolio(
                df_price_asof, df_fin_y_asof, df_fin_q_asof, df_index_asof,
                signal_day, strategy_id, config.top_n, exchange_map, config,
            )
            portfolio.rebalance(date, targets, price_matrix.loc[date])
            if first_execution_day is None and targets:
                first_execution_day = date

            n_done += 1
            nav = portfolio.total_value(price_matrix.loc[date])
            elapsed = time.time() - t_loop_start
            print(f"   [{strategy_id}] Rebalance {n_done}/{len(events)} "
                  f"signal={signal_day.date()} -> exec={date.date()}: "
                  f"chọn {len(targets)}/{config.top_n} mã, NAV={nav:,.0f} VNĐ, +{elapsed:.1f}s")

        portfolio.mark_to_market(date, price_matrix.loc[date])

    if len(trading_days) > 0:
        last_date = trading_days[-1]
        portfolio.liquidate_all(last_date, price_matrix.loc[last_date])
        portfolio.overwrite_last_mark(price_matrix.loc[last_date])  # MODERATE #15b

    total_elapsed = time.time() - t_loop_start
    print(f"   [{strategy_id}] Hoàn tất mô phỏng {len(trading_days)} phiên trong {total_elapsed:.1f}s.")

    equity_df = pd.DataFrame(portfolio.equity_history).set_index("Date")
    trades_df = pd.DataFrame(portfolio.closed_trades)
    return equity_df, trades_df, first_execution_day


# ==========================================================================
# 9. CHỈ SỐ ĐO LƯỜNG HIỆU QUẢ — CĂN CHỈNH ĐIỂM BẮT ĐẦU (MAJOR #12)
# ==========================================================================
def compute_performance_metrics(equity_series: pd.Series, freq_per_year: int = 252,
                                 risk_free_rate: float = 0.05) -> dict:
    equity = equity_series.dropna()
    if len(equity) < 2:
        return {"CAGR (%)": np.nan, "Max Drawdown (%)": np.nan, "Sharpe Ratio": np.nan}

    returns = equity.pct_change().dropna()

    n_years = (equity.index[-1] - equity.index[0]).days / 365.25
    cagr = (equity.iloc[-1] / equity.iloc[0]) ** (1 / n_years) - 1 if n_years > 0 else np.nan

    running_max = equity.cummax()
    max_drawdown = (equity / running_max - 1).min()

    excess = returns - risk_free_rate / freq_per_year
    sharpe = excess.mean() / excess.std() * np.sqrt(freq_per_year) if excess.std() > 0 else np.nan

    return {
        "CAGR (%)": round(cagr * 100, 2) if pd.notna(cagr) else np.nan,
        "Max Drawdown (%)": round(max_drawdown * 100, 2) if pd.notna(max_drawdown) else np.nan,
        "Sharpe Ratio": round(sharpe, 2) if pd.notna(sharpe) else np.nan,
    }


def compute_win_rate(trades_df: pd.DataFrame) -> tuple[float, float, int]:
    """Trả về (net_win_rate, gross_win_rate, n_closed_positions).
    MODERATE #16 + đánh giá lần 2 mục 14-15: Win Rate dùng NET PnL (đã trừ
    phí) làm số chính; Gross giữ lại để đối chiếu. Luôn kèm sample size —
    và đây là số VỊ THẾ ĐÃ ĐÓNG HOÀN TOÀN (N Closed Positions), không phải
    số lệnh khớp (partial rebalance không tạo thành 1 dòng ở đây), và KHÔNG
    tương đương "số quan sát độc lập" (nhiều mã cùng 1 quý chịu chung 1
    market regime) — xem đánh giá lần 2 mục 15 khi diễn giải ý nghĩa thống kê."""
    if trades_df.empty:
        return np.nan, np.nan, 0
    n = len(trades_df)
    net_win_rate = round((trades_df["Net PnL (%)"] > 0).sum() / n * 100, 2)
    gross_win_rate = round((trades_df["Gross PnL (%)"] > 0).sum() / n * 100, 2)
    return net_win_rate, gross_win_rate, n


def plot_equity_curve(equity_df: pd.DataFrame, benchmark_series, strategy_id: str, out_path: Path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(equity_df.index, equity_df["Total Value"], label=f"FSS - {strategy_id}")
    if benchmark_series is not None:
        ax.plot(benchmark_series.index, benchmark_series.values, label="VN-Index", linestyle="--")
    ax.set_title(f"Equity Curve: {strategy_id} vs VN-Index")
    ax.set_xlabel("Ngày")
    ax.set_ylabel("Giá trị danh mục (VNĐ)")
    ax.legend()
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


# ==========================================================================
# 9b. MODEL VALIDATION MANIFEST (đánh giá lần 2, mục 27)
# ==========================================================================
def write_model_validation_manifest(config: BacktestConfig, df_price: pd.DataFrame,
                                     df_index: pd.DataFrame, trading_days: pd.DatetimeIndex,
                                     n_anomalies: int, strategy_ids: list[str],
                                     out_dir: Path) -> None:
    """Ghi lại 'chứng chỉ tái lập' cho mỗi lần chạy — commit git (nếu có),
    dấu vân tay dữ liệu, toàn bộ tham số PIT/cost/liquidity, và các giới hạn
    đã biết — để trả lời trực tiếp câu hỏi 'làm sao tái lập được?' của BGK."""
    import hashlib
    import subprocess

    try:
        git_commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL, cwd=str(_DEFAULT_ROOT)
        ).decode().strip()
    except Exception:
        git_commit = "unknown (không phải git repo hoặc không có git CLI)"

    price_fingerprint = hashlib.sha256(
        pd.util.hash_pandas_object(df_price[["Ticker", "Date", "Price Close"]], index=False).values
    ).hexdigest()[:16]

    lines = [
        "FSS BACKTEST — MODEL VALIDATION MANIFEST",
        "=" * 60,
        f"Generated at        : {pd.Timestamp.now().isoformat()}",
        f"Git commit           : {git_commit}",
        f"Strategies run        : {', '.join(strategy_ids)}",
        "",
        "-- DATA SNAPSHOT --",
        f"Price rows            : {len(df_price):,}",
        f"Tickers                : {df_price['Ticker'].nunique():,}",
        f"Price date range       : {df_price['Date'].min().date()} -> {df_price['Date'].max().date()}",
        f"Price data fingerprint (sha256[:16]) : {price_fingerprint}",
        f"VNINDEX sessions used  : {len(trading_days)} "
        f"({trading_days[0].date()} -> {trading_days[-1].date()})",
        f"Price anomalies (>±{config.anomaly_return_threshold_pct:.0f}%/phiên) : {n_anomalies}",
        "",
        "-- BACKTEST CONFIG --",
        f"Initial capital        : {config.initial_capital:,.0f} VNĐ",
        f"Top N                  : {config.top_n}",
        f"Brokerage (buy)         : {config.brokerage_pct*100:.2f}%",
        f"Brokerage+tax (sell)    : {(config.brokerage_pct+config.sell_tax_pct)*100:.2f}%",
        f"Annual report lag       : {config.lag_days_yearly} ngày (giả định)",
        f"Quarterly report lag    : {config.lag_days_quarterly} ngày (giả định)",
        f"Risk-free rate          : {config.risk_free_rate*100:.1f}%/năm",
        f"Max participation (ADV20): {config.max_participation_pct*100:.0f}%",
        f"Min liquidity floor     : {config.min_liquidity_floor_vnd:,.0f} VNĐ",
        f"Fallback fill           : {'BẬT' if config.enable_fallback_fill else 'TẮT (mặc định)'}",
        f"Max stale days          : {config.max_stale_days} ngày",
        f"Execution rule          : Signal D (đóng cửa) -> Execution D+1 (đóng cửa)",
        "",
        "-- PIT ASSERTIONS --",
        "Technical/ADX max date <= as_of_date : enforced trong quant_engine.calculate_all_scores() "
        "(AssertionError nếu vi phạm -> backtest DỪNG, không âm thầm cho qua)",
        "VGM staleness dùng as_of_date thay vì pd.Timestamp.now() : enforced",
        "",
        "-- GIỚI HẠN ĐÃ BIẾT (KHÔNG được xử lý tự động bởi manifest này) --",
        "- Raw/adjusted price: có thể lẫn lộn; diagnostic chỉ bắt jump >ngưỡng ở trên,",
        "  KHÔNG bắt được cổ tức tiền mặt nhỏ (5-10%) không tạo jump đủ lớn.",
        "- Survivorship bias: universe = mã còn trong parquet giá hiện có; chưa xác nhận",
        "  có bao gồm mã đã hủy niêm yết trong quá khứ hay không.",
        "- Publish lag là giả định cố định, không phải Publish Date thật.",
        "- Execution price = D+1 Close (chưa mô phỏng D+1 Open/VWAP hay slippage).",
        "- N Closed Positions KHÔNG tương đương số quan sát thống kê độc lập",
        "  (nhiều mã cùng kỳ rebalance chịu chung 1 market regime).",
    ]
    manifest_path = out_dir / "MODEL_VALIDATION_MANIFEST.txt"
    manifest_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"[Manifest] Đã ghi {manifest_path}")


# ==========================================================================
# 10. CHẠY TOÀN BỘ (VGM + 11 chiến lược) -> bảng tổng hợp + Phụ lục
# ==========================================================================
def run_full_report(config: BacktestConfig, strategy_ids: list[str] | None = None,
                     output_dir: str = "backtest_output") -> pd.DataFrame:
    if config.end_date is None:
        config.end_date = pd.Timestamp.today().strftime("%Y-%m-%d")
    strategy_ids = strategy_ids or ALL_STRATEGY_IDS
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    disable_live_index_constituents()

    print("Đang tải dữ liệu giá, tài chính và VNINDEX (dùng đúng loader thật của VSS)...")
    t_load_start = time.time()
    df_price = load_market_data()
    df_price["Date"] = pd.to_datetime(df_price["Date"])
    df_price = df_price.sort_values(["Ticker", "Date"]).drop_duplicates(["Ticker", "Date"])
    df_index_full = load_index_dataframe()
    print(f"   -> Đã tải {len(df_price):,} dòng giá, {df_price['Ticker'].nunique():,} mã, "
          f"{len(df_index_full):,} phiên VNINDEX trong {time.time() - t_load_start:.1f}s.")

    n_anomalies = diagnose_price_anomalies(df_price, config.anomaly_return_threshold_pct)

    trading_days = build_trading_calendar(df_index_full, config.start_date, config.end_date)
    price_matrix = build_price_matrix(df_price, trading_days)
    last_actual_trade_date = build_last_actual_trade_date(df_price, trading_days)
    benchmark_series_full = build_benchmark_series(df_index_full, trading_days, config.initial_capital)
    exchange_map = build_exchange_map()

    df_fin_y = load_financial_data("yearly")
    df_fin_q = load_financial_data("quarterly")
    df_fin_y_avail = add_available_date(df_fin_y, config.lag_days_yearly)
    df_fin_q_avail = add_available_date(df_fin_q, config.lag_days_quarterly) if not df_fin_q.empty else df_fin_q
    print(f"   -> Đã tải xong dữ liệu tài chính. Bắt đầu chạy {len(strategy_ids)} chiến lược: "
          f"{', '.join(strategy_ids)}\n")

    write_model_validation_manifest(config, df_price, df_index_full, trading_days,
                                     n_anomalies, strategy_ids, out_dir)

    summary_rows = []
    t_report_start = time.time()
    for i, strategy_id in enumerate(strategy_ids, start=1):
        t_strategy_start = time.time()
        print(f"--- [{i}/{len(strategy_ids)}] Đang chạy backtest: {strategy_id} ---")
        try:
            equity_df, trades_df, first_exec_day = run_backtest(
                price_matrix, last_actual_trade_date, df_price, df_fin_y_avail, df_fin_q_avail,
                df_index_full, trading_days, config, strategy_id, exchange_map,
            )
        except Exception as e:
            print(f"[Lỗi] Bỏ qua {strategy_id}: {e}")
            continue

        strategy_elapsed = time.time() - t_strategy_start
        avg_per_strategy = (time.time() - t_report_start) / i
        eta = avg_per_strategy * (len(strategy_ids) - i)
        print(f"--- [{i}/{len(strategy_ids)}] Xong {strategy_id} trong {strategy_elapsed:.1f}s. "
              f"ETA còn lại: ~{eta:.0f}s ---\n")

        # --- MAJOR #12: metrics tính từ ngày giao dịch ĐẦU TIÊN thật sự ---
        if first_exec_day is not None and first_exec_day in equity_df.index:
            equity_aligned = equity_df.loc[first_exec_day:, "Total Value"]
            bench_aligned = (
                benchmark_series_full.loc[first_exec_day:]
                / benchmark_series_full.loc[first_exec_day] * config.initial_capital
            )
        else:
            equity_aligned = equity_df["Total Value"]
            bench_aligned = benchmark_series_full

        metrics = compute_performance_metrics(equity_aligned, risk_free_rate=config.risk_free_rate)

        # --- P0 FIX (đánh giá lần 2, mục 2): benchmark PHẢI được tính trên
        # ĐÚNG cùng cửa sổ thời gian [first_exec_day, ngày cuối] với từng
        # strategy — KHÔNG dùng 1 con số benchmark toàn cục duy nhất, vì mỗi
        # strategy có first_exec_day khác nhau (VGM: 16/05/2023, CANSLIM:
        # 15/08/2023, v.v.). Trước đây bảng tổng hợp so "CAGR strategy đã
        # aligned" với "CAGR benchmark KHÔNG aligned" — hai cửa sổ khác
        # nhau, nên con số "excess return" trước đó không hợp lệ. ---
        bench_metrics_aligned = compute_performance_metrics(bench_aligned, risk_free_rate=config.risk_free_rate)
        metrics["Benchmark CAGR (%)"] = bench_metrics_aligned["CAGR (%)"]
        metrics["Benchmark Max Drawdown (%)"] = bench_metrics_aligned["Max Drawdown (%)"]
        metrics["Benchmark Sharpe Ratio"] = bench_metrics_aligned["Sharpe Ratio"]
        if pd.notna(metrics["CAGR (%)"]) and pd.notna(metrics["Benchmark CAGR (%)"]):
            metrics["Excess CAGR (pp)"] = round(metrics["CAGR (%)"] - metrics["Benchmark CAGR (%)"], 2)
        else:
            metrics["Excess CAGR (pp)"] = np.nan

        net_win_rate, gross_win_rate, n_closed = compute_win_rate(trades_df)
        metrics["Net Win Rate (%)"] = net_win_rate
        metrics["Gross Win Rate (%)"] = gross_win_rate
        metrics["N Closed Positions"] = n_closed
        metrics["First Trade Date"] = first_exec_day.date() if first_exec_day is not None else None
        metrics["Role (ex-ante)"] = STRATEGY_ROLE.get(strategy_id, "")
        metrics["Strategy"] = strategy_id
        summary_rows.append(metrics)

        equity_df.to_csv(out_dir / f"equity_{strategy_id}.csv")
        trades_df.to_csv(out_dir / f"trades_{strategy_id}.csv", index=False)
        plot_equity_curve(equity_df, bench_aligned, strategy_id, out_dir / f"equity_{strategy_id}.png")

    # Dòng này CHỈ mang tính tham chiếu toàn kỳ (từ config.start_date) —
    # KHÔNG dùng để so "outperform" với bất kỳ strategy nào (mỗi strategy đã
    # có cột "Benchmark CAGR (%)" riêng, đúng cửa sổ thời gian của nó, ở
    # trên). Đổi tên rõ ràng để không ai lấy nhầm làm cột so sánh.
    bench_metrics = compute_performance_metrics(benchmark_series_full, risk_free_rate=config.risk_free_rate)
    bench_metrics["Benchmark CAGR (%)"] = bench_metrics["CAGR (%)"]
    bench_metrics["Benchmark Max Drawdown (%)"] = bench_metrics["Max Drawdown (%)"]
    bench_metrics["Benchmark Sharpe Ratio"] = bench_metrics["Sharpe Ratio"]
    bench_metrics["Excess CAGR (pp)"] = 0.0
    bench_metrics["Net Win Rate (%)"] = np.nan
    bench_metrics["Gross Win Rate (%)"] = np.nan
    bench_metrics["N Closed Positions"] = np.nan
    bench_metrics["First Trade Date"] = trading_days[0].date()
    bench_metrics["Role (ex-ante)"] = "Benchmark"
    bench_metrics["Strategy"] = "VN-Index (Benchmark, full period, KHÔNG dùng để so sánh trực tiếp)"
    summary_rows.append(bench_metrics)

    summary_df = pd.DataFrame(summary_rows).set_index("Strategy")
    col_order = [c for c in [
        "CAGR (%)", "Benchmark CAGR (%)", "Excess CAGR (pp)",
        "Max Drawdown (%)", "Benchmark Max Drawdown (%)",
        "Sharpe Ratio", "Benchmark Sharpe Ratio",
        "Net Win Rate (%)", "Gross Win Rate (%)", "N Closed Positions",
        "First Trade Date", "Role (ex-ante)",
    ] if c in summary_df.columns]
    summary_df = summary_df[col_order + [c for c in summary_df.columns if c not in col_order]]
    summary_df.to_csv(out_dir / "summary_all_strategies.csv")

    print("\n=== BẢNG TỔNG HỢP (đã sửa PIT technical + D+1 execution + liquidity ADV20) ===")
    print(summary_df.to_string())
    print(f"\nKết quả chi tiết đã lưu vào: {out_dir.resolve()}")
    print(
        f"\n[Giới hạn còn lại] Publish lag giả định: {config.lag_days_yearly} ngày (BCTC năm), "
        f"{config.lag_days_quarterly} ngày (BCTC quý). Risk-free rate: {config.risk_free_rate*100:.1f}%/năm. "
        f"Phí mua: {config.brokerage_pct*100:.2f}%, phí bán: {(config.brokerage_pct+config.sell_tax_pct)*100:.2f}% "
        f"(brokerage + thuế bán 0.1%). Fallback fill: "
        f"{'BẬT' if config.enable_fallback_fill else 'TẮT (mặc định)'}. "
        "Raw/adjusted price chưa được chuẩn hóa — xem diagnostic anomaly ở trên và docstring CRITICAL #4."
    )
    return summary_df


# ==========================================================================
# 11. SENSITIVITY (VÒNG 3 — tuỳ chọn) — chỉ VGM, Top N / cost / lag
# ==========================================================================
def run_vgm_sensitivity(base_config: BacktestConfig, output_dir: str = "backtest_output") -> pd.DataFrame:
    """Chạy nhanh VGM qua vài kịch bản tham số để trả lời trước câu hỏi
    'nếu phí tăng gấp đôi / Top N đổi thì sao?' — KHÔNG dùng để tune tới khi
    thắng (freeze rule trước khi chạy, xem mục 25 trong đánh giá BGK)."""
    scenarios = [
        {"top_n": 10}, {"top_n": 20}, {"top_n": 30},
        {"brokerage_pct": 0.0005, "sell_tax_pct": 0.001},   # base (0.15% bán)
        {"brokerage_pct": 0.0010, "sell_tax_pct": 0.002},   # phí gấp đôi
        {"lag_days_quarterly": 45}, {"lag_days_quarterly": 60},
        {"lag_days_yearly": 90}, {"lag_days_yearly": 120},
    ]
    rows = []
    for sc in scenarios:
        cfg = BacktestConfig()
        cfg.__dict__.update(base_config.__dict__)
        cfg.__dict__.update(sc)
        summary = run_full_report(cfg, strategy_ids=["VGM"], output_dir=output_dir + "/sensitivity")
        row = summary.loc["VGM"].to_dict()
        row.update(sc)
        rows.append(row)
    df = pd.DataFrame(rows)
    df.to_csv(Path(output_dir) / "vgm_sensitivity.csv", index=False)
    print("\n=== VGM SENSITIVITY (Top N / cost / lag) ===")
    print(df.to_string())
    return df


# ==========================================================================
# 12. CLI
# ==========================================================================
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="FSS Backtest Engine (VSS) — V2")
    parser.add_argument("--start", default="2023-01-01")
    parser.add_argument("--end", default=None)
    parser.add_argument("--capital", type=float, default=1_000_000_000)
    parser.add_argument("--top-n", type=int, default=20)
    parser.add_argument("--brokerage-pct", type=float, default=0.0005)
    parser.add_argument("--sell-tax-pct", type=float, default=0.001)
    parser.add_argument("--lag-days-yearly", type=int, default=90)
    parser.add_argument("--lag-days-quarterly", type=int, default=45)
    parser.add_argument("--risk-free-rate", type=float, default=0.05)
    parser.add_argument("--max-participation-pct", type=float, default=0.08)
    parser.add_argument("--max-stale-days", type=int, default=20)
    parser.add_argument("--enable-fallback-fill", action="store_true",
                         help="Bật lại fallback fill (hành vi bản V1) — mặc định TẮT.")
    parser.add_argument("--project-root", default=None)
    parser.add_argument("--strategy", default=None,
                         help="Chỉ chạy 1 chiến lược, vd: VGM, STRAT_PIOTROSKI. "
                              "Bỏ trống để chạy toàn bộ VGM + 11 chiến lược.")
    parser.add_argument("--output-dir", default="backtest_output")
    parser.add_argument("--sensitivity", action="store_true",
                         help="Chạy thêm sensitivity analysis cho VGM (Top N/cost/lag).")
    args = parser.parse_args()

    if args.project_root:
        _setup_project_root(args.project_root)

    cfg = BacktestConfig()
    cfg.start_date = args.start
    cfg.end_date = args.end
    cfg.initial_capital = args.capital
    cfg.top_n = args.top_n
    cfg.brokerage_pct = args.brokerage_pct
    cfg.sell_tax_pct = args.sell_tax_pct
    cfg.lag_days_yearly = args.lag_days_yearly
    cfg.lag_days_quarterly = args.lag_days_quarterly
    cfg.risk_free_rate = args.risk_free_rate
    cfg.max_participation_pct = args.max_participation_pct
    cfg.max_stale_days = args.max_stale_days
    cfg.enable_fallback_fill = args.enable_fallback_fill

    run_full_report(cfg, strategy_ids=[args.strategy] if args.strategy else None,
                     output_dir=args.output_dir)

    if args.sensitivity:
        run_vgm_sensitivity(cfg, output_dir=args.output_dir)