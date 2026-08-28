"""
backtest.py — Backtest Engine cho hệ thống FSS (Vietcap Smart Screener)
=========================================================================
BẢN ĐÃ SỬA sau khi đọc trực tiếp data_loader.py và quant_engine_strategies.py
thật của bạn. Các thay đổi quan trọng so với bản đầu (xem "NHẬT KÝ SỬA LỖI"
bên dưới) đến từ việc đọc source thật, không phải suy đoán.

MỤC ĐÍCH
--------
Backtest VGM Score và 11 chiến lược (STRAT_*) dùng ĐÚNG hàm scoring thật
(`calculate_all_scores`, `run_strategy`) và ĐÚNG loader thật
(`load_market_data`, `load_financial_data`, `load_index_data`), có point-in-time
layer để tránh Look-ahead Bias.

NHẬT KÝ SỬA LỖI (so với bản đầu tiên)
--------------------------------------
1. VNINDEX KHÔNG nằm trong market_prices.parquet — nó ở index.parquet riêng
   (cột `VNINDEX_Close` theo `Date`, không có `Ticker`). Dùng đúng
   `load_index_data()` thay vì tìm ticker "VNINDEX" trong price_matrix.

2. SỬA BUG SCHEMA NGHIÊM TRỌNG: `calculate_all_scores()` và mọi hàm
   `calculate_*_metrics(df, df_fin)` cần `df_fin` là TOÀN BỘ lịch sử BCTC
   (nhiều dòng/ticker, có cột Date) — chúng tự làm groupby('Ticker').last()
   hoặc tính CAGR/YoY bên trong. Bản đầu của tôi rút gọn df_fin xuống 1
   dòng/ticker trước khi truyền vào → làm hầu hết chỉ số tăng trưởng (YoY,
   CAGR 3-5Y, F-Score...) âm thầm ra NaN. Đã sửa: point-in-time layer giờ
   trả về TOÀN BỘ history có available_date <= as_of_date, không rút gọn.

3. `calculate_all_scores()` trong _build_snapshot_df CHỈ dùng
   `load_financial_data("yearly")` — không gộp quarterly vào như bản đầu.
   Quarterly chỉ được dùng RIÊNG bên trong CANSLIM (xem mục 4).

4. LOOK-AHEAD BIAS THẬT trong code gốc: `calculate_canslim_metrics()` tự gọi
   `load_financial_data_nocache('quarterly')` — LUÔN lấy BCTC quý MỚI NHẤT
   hiện có trên đĩa, bất kể đang backtest ở ngày nào. Đã vá bằng
   monkeypatch tạm thời (`_point_in_time_quarterly`) để ép nó dùng đúng dữ
   liệu quý có sẵn tại as_of_date trong lúc chạy CANSLIM.

5. `run_strategy()` = calc_fn + apply_fn (bộ lọc cứng), và một số apply_fn
   ĐÃ TỰ sort/truncate: Magic Formula (top 30 theo MF_Total_Score), NCN (top
   40 theo ncn_score), Dividend (sort theo yield), ADX (sort theo ưu tiên
   VN30/VN100 + ADX_14). Với các chiến lược này, script GIỮ NGUYÊN thứ tự có
   sẵn thay vì rank lại. Chỉ áp dụng ranking dự phòng (z-score trung bình)
   cho Value/Turnaround/Quality/GARP/Growth — các chiến lược apply_fn chỉ lọc
   boolean, không có cột điểm tổng hợp cuối cùng.

6. `apply_adx_strategy_filter()` gọi API SỐNG của SSI
   (`fetch_index_constituents`) để lấy rổ VN30/VN100 HIỆN TẠI chỉ để ưu tiên
   sắp xếp. Trong backtest việc này vừa chậm (gọi mạng mỗi lần rebalance),
   vừa dùng rổ chỉ số hiện tại cho một thời điểm lịch sử. Đã tắt bằng
   monkeypatch `_disable_live_index_constituents()` — chiến lược vẫn lọc
   đúng, chỉ mất phần ưu tiên sắp xếp VN30/VN100.

7. Risk-free rate mặc định đổi thành 5%/năm (lãi suất gửi tiết kiệm VN
   tham chiếu) để Sharpe Ratio thực chất hơn thay vì so với 0%.

8. Không cần cấu hình processed_dir/RAW_DIR thủ công nữa — dùng thẳng
   load_market_data()/load_financial_data()/load_index_data() thật, tự biết
   đường dẫn qua BASE_DIR nội bộ của data_loader.py.

CÁC GIỚI HẠN CÒN LẠI (đọc trước khi dùng số liệu để thuyết trình)
------------------------------------------------------------------
- PUBLISH LAG vẫn là giả định (không có Publish Date thật trong dữ liệu):
  mặc định 90 ngày cho BCTC năm, 45 ngày cho BCTC quý.
- Tôi CHƯA có source của `quant_engine.py` và `technical_indicators.py` (chỉ
  có data_loader.py và quant_engine_strategies.py). `_build_snapshot_df()`
  cho thấy nó tự tính thêm Avg_Vol_20D, Avg_Vol_20D_VND, Sparkline_30D,
  EPS_Growth_QoQ TRƯỚC khi gọi calculate_all_scores() — script này đã mô
  phỏng lại đúng các bước đó. Nếu calculate_all_scores() vẫn báo lỗi thiếu
  cột kỹ thuật khác (RS_1M, RS_3M, ADX_14, Beta...), nghĩa là có bước tiền
  xử lý khác từ technical_indicators.py mà tôi chưa thấy được — gửi thêm
  file đó để tôi khớp chính xác 100%.
- Giá có thể là hỗn hợp raw/adjusted (xem data_loader: SSI dùng giá thường,
  VNDirect/yfinance dùng giá adjusted) — không có cột đánh dấu để tự sửa.
- Không mô phỏng slippage khi giao dịch khối lượng lớn.

CÁCH CHẠY
---------
    python backtest.py --strategy VGM
    python backtest.py                      # VGM + toàn bộ 11 chiến lược
    python backtest.py --start 2023-01-01 --end 2026-08-01 --top-n 20
    python backtest.py --project-root /path/to/VSS   # nếu backtest.py không
                                                       # nằm cùng cấp với src/
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
# 0. PROJECT ROOT — cần nằm CÙNG CẤP với thư mục `src/` (data_loader.py tự
#    tính BASE_DIR = 3 cấp cha của chính nó, tức là project root thật).
#    Mặc định giả sử backtest.py đặt ngay tại project root; đổi bằng
#    --project-root nếu không phải vậy.
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
        # 0.15% = phí môi giới CTCK + thuế bán 0.1% — mức chuẩn cho thị
        # trường VN. NÊN highlight con số này khi thuyết trình: nhiều backtest
        # sinh viên bỏ quên phí giao dịch khiến lợi nhuận bị "ảo".
        self.transaction_cost = 0.0015
        self.lag_days_yearly = 90     # giả định trễ công bố BCTC năm (kiểm toán)
        self.lag_days_quarterly = 45  # giả định trễ công bố BCTC quý
        self.risk_free_rate = 0.05    # 5%/năm — lãi suất gửi tiết kiệm VN tham chiếu

        # NGƯỠNG THANH KHOẢN TỐI THIỂU (VNĐ/phiên, bình quân 20 phiên gần nhất).
        # Loại các mã "ma" (volume ~0, giá tham chiếu không phản ánh giao dịch
        # thật — vd VNX/DKC trên UPCOM) TRƯỚC khi xếp hạng, để equity curve
        # không bị nhảy ảo vì mua/bán ở mức giá không ai khớp lệnh được.
        # 100 triệu/phiên là mức sàn khá dễ dãi; tăng lên nếu vẫn thấy nhảy giá bất thường.
        self.min_avg_turnover_vnd = 100_000_000.0


# ==========================================================================
# 1. POINT-IN-TIME LAYER
# ==========================================================================
def add_available_date(df_fin: pd.DataFrame, lag_days: int) -> pd.DataFrame:
    """available_date = ngày kỳ báo cáo (Date) + độ trễ công bố giả định."""
    df = df_fin.copy()
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df["available_date"] = df["Date"] + pd.Timedelta(days=lag_days)
    return df


def get_financial_history_asof(df_fin_avail: pd.DataFrame, as_of_date: pd.Timestamp) -> pd.DataFrame:
    """QUAN TRỌNG: trả về TOÀN BỘ lịch sử (nhiều dòng/ticker) có
    available_date <= as_of_date — KHÔNG rút gọn về 1 dòng/ticker.
    calculate_all_scores() và các hàm calculate_*_metrics() tự làm
    groupby('Ticker').last() / tính CAGR, YoY bên trong, nên chúng cần thấy
    toàn bộ chuỗi thời gian, không phải bản đã rút gọn."""
    valid = df_fin_avail[df_fin_avail["available_date"] <= as_of_date]
    return valid.drop(columns=["available_date"], errors="ignore")


def generate_rebalance_dates(start: str, end: str, lag_days_quarterly: int) -> list[pd.Timestamp]:
    """Mốc tái cơ cấu = cuối mỗi quý + độ trễ công bố quý."""
    quarter_ends = pd.date_range(start=start, end=end, freq="QE")
    rebal_dates = quarter_ends + pd.Timedelta(days=lag_days_quarterly)
    return list(rebal_dates[rebal_dates <= pd.Timestamp(end)])


def build_price_matrix(df_price: pd.DataFrame, business_days: pd.DatetimeIndex) -> pd.DataFrame:
    """Pivot giá đóng cửa thành ma trận Date x Ticker, forward-fill để xử lý
    ngày nghỉ lễ. Mã chưa niêm yết vẫn là NaN (ffill không kéo ngược từ
    tương lai)."""
    pivot = df_price.pivot_table(index="Date", columns="Ticker", values="Price Close")
    return pivot.reindex(business_days).ffill()


def build_benchmark_series(business_days: pd.DatetimeIndex, initial_capital: float) -> pd.Series | None:
    """VNINDEX nằm ở index.parquet riêng (load_index_data), KHÔNG phải một
    Ticker trong market_prices.parquet."""
    df_index = load_index_data()
    if df_index.empty or "VNINDEX_Close" not in df_index.columns:
        print("[Cảnh báo] load_index_data() rỗng hoặc thiếu cột VNINDEX_Close. Bỏ qua benchmark.")
        return None
    df_index = df_index.copy()
    df_index["Date"] = pd.to_datetime(df_index["Date"], errors="coerce")
    s = df_index.set_index("Date")["VNINDEX_Close"].sort_index()
    s = s.reindex(business_days).ffill().dropna()
    if s.empty:
        return None
    return (s / s.iloc[0] * initial_capital).rename("Total Value")


def build_exchange_map() -> dict:
    """Sao chép đúng logic trong data_loader._build_snapshot_df(): đọc đuôi
    sàn (.HM/.HN/.HNO) từ parquet giá GỐC để gắn cột Exchange — cần cho
    gatekeeper của STRAT_ADX_MOMENTUM (loại UPCOM)."""
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
# 2. MONKEYPATCH — vá 2 điểm look-ahead / phụ thuộc mạng trong code gốc
# ==========================================================================
@contextmanager
def _point_in_time_quarterly(df_fin_q_asof: pd.DataFrame):
    """Ép calculate_canslim_metrics() dùng đúng BCTC quý ĐÃ CÓ tại
    as_of_date, thay vì tự ý load bản quý mới nhất hiện có trên đĩa."""
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
    lọc cứng). Tắt đi cho backtest: nhanh hơn, không cần mạng, và không dùng
    rổ chỉ số hiện tại cho một thời điểm lịch sử. Chiến lược vẫn lọc đúng,
    chỉ mất phần ưu tiên sắp xếp VN30/VN100 lên đầu danh sách."""
    def _empty(index_code):
        return [], None
    data_loader_module.fetch_index_constituents = _empty


# ==========================================================================
# 3. TIỀN XỬ LÝ GIÁ TRƯỚC KHI CHẤM ĐIỂM (mô phỏng lại _build_snapshot_df)
# ==========================================================================
def build_latest_price_snapshot(df_price_asof: pd.DataFrame) -> pd.DataFrame:
    """Mô phỏng các bước tiền xử lý mà data_loader._build_snapshot_df() làm
    TRƯỚC khi gọi calculate_all_scores(): Avg_Vol_20D, Avg_Vol_20D_VND,
    Sparkline_30D, EPS_Growth_QoQ. (Không có source quant_engine.py /
    technical_indicators.py nên không chắc calculate_all_scores() có cần
    thêm cột kỹ thuật nào khác — xem docstring đầu file.)"""
    df = df_price_asof.sort_values(["Ticker", "Date"]).copy()

    df["Avg_Vol_20D"] = (
        df.groupby("Ticker", sort=False)["Volume"]
          .transform(lambda x: x.rolling(20, min_periods=1).mean())
          .round(0).fillna(0)
    )
    df["Avg_Vol_20D_VND"] = (df["Avg_Vol_20D"] * df["Price Close"]).round(0).fillna(0)

    df_latest = df.drop_duplicates(subset=["Ticker"], keep="last").copy()

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
# 4. XẾP HẠNG / CHỌN DANH MỤC THEO TỪNG CHIẾN LƯỢC
# ==========================================================================
# Các strategy mà apply_fn() TRONG CODE GỐC đã tự sort/truncate đúng —
# KHÔNG re-rank, chỉ head(top_n) trên thứ tự sẵn có.
ALREADY_SORTED_STRATEGIES = {"STRAT_MAGIC", "STRAT_NCN", "STRAT_DIVIDEND", "STRAT_ADX_MOMENTUM"}

# Đã có cột điểm tổng hợp rõ ràng, chỉ cần sort desc.
EXPLICIT_SCORE_COLS = {
    "STRAT_PIOTROSKI": "f_score",
}

# CHƯA có cột điểm tổng hợp cuối cùng trong code gốc — cần ranking dự phòng
# (trung bình z-score) trên phần đã qua bộ lọc apply_fn.
STRATEGY_METRIC_COLS = {
    "STRAT_VALUE": ["current_ratio", "eps_growth_5y"],
    "STRAT_TURNAROUND": ["operating_margin", "pe_historical_norm", "peg_ratio"],
    "STRAT_QUALITY": ["gross_margin", "re_growth", "fcf_margin"],
    "STRAT_GARP": ["eps_growth_1y", "peg", "sgr"],
    "STRAT_CANSLIM": ["eps_growth_y", "eps_growth_q", "rev_growth_q", "rs_rating"],
    "STRAT_GROWTH": ["rev_growth_5y", "gross_margin", "reinvest_rate"],
}

# Metric nào "thấp hơn = tốt hơn" (đảo dấu trước khi z-score).
LOWER_IS_BETTER = {
    "STRAT_TURNAROUND": {"pe_historical_norm": True, "peg_ratio": True},
    "STRAT_GARP": {"peg": True},
}


def _rank_by_metrics(df: pd.DataFrame, cols: list[str], lower_is_better: dict) -> pd.DataFrame:
    """Ranking dự phòng: trung bình z-score các metric thành phần, CHỈ dùng
    khi chiến lược chưa có sẵn 1 cột điểm tổng hợp cuối cùng trong code gốc."""
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
    strategy_id: str,
    top_n: int,
    exchange_map: dict,
    min_avg_turnover_vnd: float = 0.0,
) -> list[str]:
    """Xây snapshot tại 1 thời điểm CHỈ từ dữ liệu đã "biết" tại thời điểm
    đó, chấm điểm bằng đúng hàm scoring thật của VSS, trả về Top N mã."""
    if df_price_asof.empty or df_fin_y_asof.empty:
        return []

    latest_price_snapshot = build_latest_price_snapshot(df_price_asof)

    # --- LỌC THANH KHOẢN: loại cổ phiếu "ma" (volume ~0) trước khi chấm điểm ---
    # Áp dụng ở đây, trước calculate_all_scores(), vì Avg_Vol_20D_VND đã có sẵn
    # và việc loại sớm cũng tiết kiệm compute cho các bước chấm điểm phía sau.
    if min_avg_turnover_vnd > 0 and "Avg_Vol_20D_VND" in latest_price_snapshot.columns:
        n_before = len(latest_price_snapshot)
        latest_price_snapshot = latest_price_snapshot[
            latest_price_snapshot["Avg_Vol_20D_VND"] >= min_avg_turnover_vnd
        ]
        n_excluded = n_before - len(latest_price_snapshot)
        if n_excluded > 0:
            print(f"[Liquidity Filter] {strategy_id}: loại {n_excluded}/{n_before} mã "
                  f"có GTGD BQ 20 phiên < {min_avg_turnover_vnd:,.0f} VNĐ")

    try:
        df_snapshot = calculate_all_scores(latest_price_snapshot, df_fin_y_asof)
    except Exception as e:
        raise RuntimeError(
            f"calculate_all_scores() thất bại cho strategy={strategy_id}. "
            f"Có thể thiếu cột kỹ thuật (xem mục Giới Hạn ở đầu file). Lỗi gốc: {e}"
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

    # CANSLIM: vá look-ahead bias — ép dùng đúng BCTC quý tại as_of_date
    if strategy_id == "STRAT_CANSLIM":
        with _point_in_time_quarterly(df_fin_q_asof):
            df_strat = run_strategy(df_snapshot, strategy_id, df_fin_y_asof)
    else:
        df_strat = run_strategy(df_snapshot, strategy_id, df_fin_y_asof)

    if strategy_id in ALREADY_SORTED_STRATEGIES:
        if df_strat.empty:
            return []
        ranked = df_strat  # giữ nguyên thứ tự apply_fn() đã tự sort/truncate
    elif strategy_id in EXPLICIT_SCORE_COLS:
        if df_strat.empty:
            return []
        ranked = df_strat.sort_values(EXPLICIT_SCORE_COLS[strategy_id], ascending=False)
    else:
        cols = STRATEGY_METRIC_COLS.get(strategy_id, [])
        lower_is_better = LOWER_IS_BETTER.get(strategy_id, {})
        ranked = _rank_by_metrics(df_strat, cols, lower_is_better) if not df_strat.empty else df_strat

        # --- FALLBACK cho các chiến lược apply_fn quá khắt khe (đặc biệt CANSLIM) ---
        # apply_fn() lọc cứng boolean trong quant_engine_strategies.py có thể trả về
        # 0 hoặc rất ít mã ở những giai đoạn thị trường xấu/thiếu dữ liệu BCTC sớm
        # (vd 2023 tại VN). Thay vì để danh mục 100% tiền mặt do bộ lọc quá chặt
        # (khác với việc CHỦ ĐỘNG né thị trường xấu), bổ sung thêm ứng viên tốt
        # nhất còn lại từ TOÀN BỘ universe đã qua lọc thanh khoản (df_snapshot),
        # xếp hạng bằng đúng bộ metric của chiến lược đó, cho đủ top_n.
        #
        # ĐÂY LÀ LỰA CHỌN CÓ CHỦ Ý, KHÔNG BẮT BUỘC: nếu bạn muốn giữ đúng triết lý
        # CANSLIM gốc của O'Neil ("cash is a position" khi không đủ mã đạt chuẩn),
        # hãy set ENABLE_FALLBACK_FILL = False bên dưới hoặc xoá khối này.
        ENABLE_FALLBACK_FILL = True
        if ENABLE_FALLBACK_FILL and cols and len(ranked) < top_n:
            n_missing = top_n - len(ranked)
            already_have = set(ranked["Ticker"]) if not ranked.empty else set()
            remaining_pool = df_snapshot[~df_snapshot["Ticker"].isin(already_have)]
            if not remaining_pool.empty:
                filler_ranked = _rank_by_metrics(remaining_pool, cols, lower_is_better)
                filler = filler_ranked.head(n_missing)
                if len(ranked):
                    print(f"[Fallback Fill] {strategy_id}: apply_fn() chỉ có {len(ranked)}/{top_n} mã "
                          f"đạt chuẩn cứng -> bổ sung {len(filler)} mã tốt nhất còn lại theo z-score.")
                else:
                    print(f"[Fallback Fill] {strategy_id}: apply_fn() không có mã nào đạt chuẩn cứng "
                          f"-> dùng {len(filler)} mã tốt nhất theo z-score (toàn bộ universe).")
                ranked = pd.concat([ranked, filler], ignore_index=True) if len(ranked) else filler

    if ranked.empty:
        return []

    return ranked["Ticker"].head(top_n).tolist()


ALL_STRATEGY_IDS = [
    "VGM", "STRAT_VALUE", "STRAT_TURNAROUND", "STRAT_QUALITY", "STRAT_GARP",
    "STRAT_DIVIDEND", "STRAT_PIOTROSKI", "STRAT_CANSLIM", "STRAT_GROWTH",
    "STRAT_MAGIC", "STRAT_NCN", "STRAT_ADX_MOMENTUM",
]


# ==========================================================================
# 5. MÔ PHỎNG DANH MỤC (equal-weight, có cost-basis để tính Win Rate)
# ==========================================================================
class Position:
    __slots__ = ("shares", "avg_cost")

    def __init__(self, shares: float = 0.0, avg_cost: float = 0.0):
        self.shares = shares
        self.avg_cost = avg_cost


class Portfolio:
    def __init__(self, capital: float):
        self.cash = capital
        self.positions: dict[str, Position] = {}
        self.equity_history: list[dict] = []
        self.closed_trades: list[dict] = []

    def _sell(self, ticker, shares_to_sell, price, date, tx_cost):
        pos = self.positions.get(ticker)
        if pos is None or pos.shares <= 0 or shares_to_sell <= 0:
            return
        shares_to_sell = min(shares_to_sell, pos.shares)
        proceeds = shares_to_sell * price * (1 - tx_cost)
        self.cash += proceeds
        pos.shares -= shares_to_sell
        if pos.shares <= 1e-6:
            pnl_pct = (price - pos.avg_cost) / pos.avg_cost * 100 if pos.avg_cost > 0 else np.nan
            self.closed_trades.append({
                "Ticker": ticker, "Exit Date": date,
                "Entry Price": pos.avg_cost, "Exit Price": price,
                "PnL (%)": pnl_pct,
            })
            del self.positions[ticker]

    def _buy(self, ticker, value_to_buy, price, tx_cost):
        if value_to_buy <= 0 or price <= 0:
            return
        cost = value_to_buy * (1 + tx_cost)
        if cost > self.cash:
            value_to_buy = self.cash / (1 + tx_cost)
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

    def rebalance(self, date, target_tickers: list[str], price_row: pd.Series, tx_cost: float):
        target_tickers = [t for t in target_tickers if pd.notna(price_row.get(t, np.nan))]

        for ticker in list(self.positions.keys()):
            if ticker not in target_tickers:
                price = price_row.get(ticker, np.nan)
                if pd.notna(price):
                    self._sell(ticker, self.positions[ticker].shares, price, date, tx_cost)

        if not target_tickers:
            return

        current_total = self.total_value(price_row)
        target_value_each = current_total / len(target_tickers)

        for ticker in target_tickers:
            price = price_row[ticker]
            pos = self.positions.get(ticker)
            current_value = pos.shares * price if pos else 0.0
            diff = target_value_each - current_value
            if diff < 0:
                self._sell(ticker, -diff / price, price, date, tx_cost)

        for ticker in target_tickers:
            price = price_row[ticker]
            pos = self.positions.get(ticker)
            current_value = pos.shares * price if pos else 0.0
            diff = target_value_each - current_value
            if diff > 0:
                self._buy(ticker, diff, price, tx_cost)

    def liquidate_all(self, date, price_row: pd.Series, tx_cost: float):
        for ticker in list(self.positions.keys()):
            price = price_row.get(ticker, np.nan)
            if pd.notna(price):
                self._sell(ticker, self.positions[ticker].shares, price, date, tx_cost)

    def mark_to_market(self, date, price_row: pd.Series):
        self.equity_history.append({"Date": date, "Total Value": self.total_value(price_row)})


# ==========================================================================
# 6. VÒNG LẶP BACKTEST CHÍNH
# ==========================================================================
def run_backtest(
    price_matrix: pd.DataFrame,
    df_price_long: pd.DataFrame,
    df_fin_y_avail: pd.DataFrame,
    df_fin_q_avail: pd.DataFrame,
    config: BacktestConfig,
    strategy_id: str,
    exchange_map: dict,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    rebalance_dates = generate_rebalance_dates(config.start_date, config.end_date, config.lag_days_quarterly)
    trading_days = price_matrix.loc[config.start_date:config.end_date].index

    if len(trading_days) == 0:
        print(f"   [{strategy_id}] Không có phiên giao dịch nào trong khoảng "
              f"{config.start_date} -> {config.end_date}. Bỏ qua.")
        return pd.DataFrame(columns=["Total Value"]).rename_axis("Date"), pd.DataFrame()

    print(f"   [{strategy_id}] {len(trading_days)} phiên giao dịch "
          f"({trading_days[0].date()} -> {trading_days[-1].date()}), "
          f"{len(rebalance_dates)} lần tái cơ cấu dự kiến.")

    portfolio = Portfolio(config.initial_capital)
    rebal_idx = 0
    t_loop_start = time.time()

    for i, date in enumerate(trading_days):
        while rebal_idx < len(rebalance_dates) and date >= rebalance_dates[rebal_idx]:
            df_price_asof = df_price_long[df_price_long["Date"] <= date]
            df_fin_y_asof = get_financial_history_asof(df_fin_y_avail, date)
            df_fin_q_asof = get_financial_history_asof(df_fin_q_avail, date)
            targets = select_portfolio(
                df_price_asof, df_fin_y_asof, df_fin_q_asof, strategy_id, config.top_n, exchange_map,
                min_avg_turnover_vnd=config.min_avg_turnover_vnd,
            )
            portfolio.rebalance(date, targets, price_matrix.loc[date], config.transaction_cost)
            nav = portfolio.total_value(price_matrix.loc[date])
            elapsed = time.time() - t_loop_start
            print(f"   [{strategy_id}] Rebalance {rebal_idx + 1}/{len(rebalance_dates)} "
                  f"@ {date.date()}: chọn {len(targets)}/{config.top_n} mã, "
                  f"NAV={nav:,.0f} VNĐ, +{elapsed:.1f}s")
            rebal_idx += 1

        portfolio.mark_to_market(date, price_matrix.loc[date])

    if len(trading_days) > 0:
        last_date = trading_days[-1]
        portfolio.liquidate_all(last_date, price_matrix.loc[last_date], config.transaction_cost)

    total_elapsed = time.time() - t_loop_start
    print(f"   [{strategy_id}] Hoàn tất mô phỏng {len(trading_days)} phiên trong {total_elapsed:.1f}s.")

    equity_df = pd.DataFrame(portfolio.equity_history).set_index("Date")
    trades_df = pd.DataFrame(portfolio.closed_trades)
    return equity_df, trades_df


# ==========================================================================
# 7. CÁC CHỈ SỐ ĐO LƯỜNG HIỆU QUẢ
# ==========================================================================
def compute_performance_metrics(equity_df: pd.DataFrame, freq_per_year: int = 252,
                                 risk_free_rate: float = 0.05) -> dict:
    """risk_free_rate mặc định 5%/năm — lãi suất gửi tiết kiệm VN tham chiếu,
    để Sharpe Ratio phản ánh đúng phần bù rủi ro thực tế thay vì so với 0%."""
    equity = equity_df["Total Value"].dropna()
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


def compute_win_rate(trades_df: pd.DataFrame) -> float:
    if trades_df.empty:
        return np.nan
    wins = (trades_df["PnL (%)"] > 0).sum()
    return round(wins / len(trades_df) * 100, 2)


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
# 8. CHẠY TOÀN BỘ (VGM + 11 chiến lược) -> bảng tổng hợp + Phụ lục
# ==========================================================================
def run_full_report(config: BacktestConfig, strategy_ids: list[str] | None = None,
                     output_dir: str = "backtest_output") -> pd.DataFrame:
    if config.end_date is None:
        config.end_date = pd.Timestamp.today().strftime("%Y-%m-%d")
    strategy_ids = strategy_ids or ALL_STRATEGY_IDS
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    disable_live_index_constituents()

    print("Đang tải dữ liệu giá và tài chính (dùng đúng loader thật của VSS)...")
    t_load_start = time.time()
    df_price = load_market_data()
    df_price["Date"] = pd.to_datetime(df_price["Date"])
    df_price = df_price.sort_values(["Ticker", "Date"]).drop_duplicates(["Ticker", "Date"])
    print(f"   -> Đã tải {len(df_price):,} dòng giá, {df_price['Ticker'].nunique():,} mã "
          f"trong {time.time() - t_load_start:.1f}s.")

    business_days = pd.date_range(config.start_date, config.end_date, freq="B")
    price_matrix = build_price_matrix(df_price, business_days)
    benchmark_series = build_benchmark_series(business_days, config.initial_capital)
    exchange_map = build_exchange_map()

    df_fin_y = load_financial_data("yearly")
    df_fin_q = load_financial_data("quarterly")  # dùng cho point-in-time patch của CANSLIM
    df_fin_y_avail = add_available_date(df_fin_y, config.lag_days_yearly)
    df_fin_q_avail = add_available_date(df_fin_q, config.lag_days_quarterly) if not df_fin_q.empty else df_fin_q
    print(f"   -> Đã tải xong dữ liệu tài chính. Bắt đầu chạy {len(strategy_ids)} chiến lược: "
          f"{', '.join(strategy_ids)}\n")

    summary_rows = []
    t_report_start = time.time()
    for i, strategy_id in enumerate(strategy_ids, start=1):
        t_strategy_start = time.time()
        print(f"--- [{i}/{len(strategy_ids)}] Đang chạy backtest: {strategy_id} ---")
        try:
            equity_df, trades_df = run_backtest(
                price_matrix, df_price, df_fin_y_avail, df_fin_q_avail, config, strategy_id, exchange_map
            )
        except Exception as e:
            print(f"[Lỗi] Bỏ qua {strategy_id}: {e}")
            continue

        strategy_elapsed = time.time() - t_strategy_start
        avg_per_strategy = (time.time() - t_report_start) / i
        eta = avg_per_strategy * (len(strategy_ids) - i)
        print(f"--- [{i}/{len(strategy_ids)}] Xong {strategy_id} trong {strategy_elapsed:.1f}s. "
              f"ETA còn lại: ~{eta:.0f}s ---\n")

        metrics = compute_performance_metrics(equity_df, risk_free_rate=config.risk_free_rate)
        metrics["Win Rate (%)"] = compute_win_rate(trades_df)
        metrics["Strategy"] = strategy_id
        summary_rows.append(metrics)

        equity_df.to_csv(out_dir / f"equity_{strategy_id}.csv")
        trades_df.to_csv(out_dir / f"trades_{strategy_id}.csv", index=False)
        plot_equity_curve(equity_df, benchmark_series, strategy_id, out_dir / f"equity_{strategy_id}.png")

    if benchmark_series is not None:
        bench_metrics = compute_performance_metrics(benchmark_series.to_frame(), risk_free_rate=config.risk_free_rate)
        bench_metrics["Win Rate (%)"] = np.nan
        bench_metrics["Strategy"] = "VN-Index (Benchmark)"
        summary_rows.append(bench_metrics)

    summary_df = pd.DataFrame(summary_rows).set_index("Strategy")
    summary_df.to_csv(out_dir / "summary_all_strategies.csv")

    print("\n=== BẢNG TỔNG HỢP (Phần 3: Key Metrics + Phụ lục 11 chiến lược) ===")
    print(summary_df.to_string())
    print(f"\nKết quả chi tiết đã lưu vào: {out_dir.resolve()}")
    print(
        f"\n[Giới hạn] Publish lag giả định: {config.lag_days_yearly} ngày (BCTC năm), "
        f"{config.lag_days_quarterly} ngày (BCTC quý). Risk-free rate: {config.risk_free_rate*100:.1f}%/năm. "
        f"Phí giao dịch: {config.transaction_cost*100:.2f}% (đã gồm phí môi giới + thuế bán 0.1%). "
        "Một số chiến lược dùng ranking dự phòng (z-score) — xem docstring đầu file."
    )
    return summary_df


# ==========================================================================
# 9. CLI
# ==========================================================================
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="FSS Backtest Engine (VSS)")
    parser.add_argument("--start", default="2023-01-01")
    parser.add_argument("--end", default=None)
    parser.add_argument("--capital", type=float, default=1_000_000_000)
    parser.add_argument("--top-n", type=int, default=20)
    parser.add_argument("--cost", type=float, default=0.0015)
    parser.add_argument("--lag-days-yearly", type=int, default=90)
    parser.add_argument("--lag-days-quarterly", type=int, default=45)
    parser.add_argument("--risk-free-rate", type=float, default=0.05)
    parser.add_argument("--project-root", default=None,
                         help="Đường dẫn tới project root (nơi chứa thư mục src/), "
                              "nếu backtest.py không đặt cùng cấp với src/.")
    parser.add_argument(
        "--strategy", default=None,
        help="Chỉ chạy 1 chiến lược, vd: VGM, STRAT_PIOTROSKI. "
             "Bỏ trống để chạy toàn bộ VGM + 11 chiến lược.",
    )
    parser.add_argument("--output-dir", default="backtest_output")
    args = parser.parse_args()

    if args.project_root:
        _setup_project_root(args.project_root)

    cfg = BacktestConfig()
    cfg.start_date = args.start
    cfg.end_date = args.end
    cfg.initial_capital = args.capital
    cfg.top_n = args.top_n
    cfg.transaction_cost = args.cost
    cfg.lag_days_yearly = args.lag_days_yearly
    cfg.lag_days_quarterly = args.lag_days_quarterly
    cfg.risk_free_rate = args.risk_free_rate

    run_full_report(cfg, strategy_ids=[args.strategy] if args.strategy else None,
                     output_dir=args.output_dir)