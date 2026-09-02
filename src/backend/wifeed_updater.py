# src/backend/wifeed_updater.py
"""
Wifeed EOD API Scheduler
========================
- Fetch toàn bộ thị trường (~1500 mã) từ 1 request duy nhất
- Chạy mỗi 60 giây trong giờ giao dịch 09:00–14:45 (giờ Việt Nam)
- Chạy 1 lần cuối lúc 15:00 để xác nhận giá EOD
- Lưu kết quả vào data/processed/realtime_cache.parquet (ghi đè)
- Lúc 15:00 append vào market_prices.parquet
- Rate limit: KHÔNG gọi dưới 60s/request — vi phạm sẽ bị ban IP
Yêu cầu trong .env:
    WIFEED_API_KEY=your_key_here
"""
import os
import time
import logging
import threading
import requests
import numpy as np
import pandas as pd
from datetime import datetime, time as dtime
from datetime import timedelta, date
import pytz
logger = logging.getLogger(__name__)
# ── Cấu hình ────────────────────────────────────────────────────────────────
_BASE_DIR      = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_PROCESSED_DIR = os.path.join(_BASE_DIR, "data", "processed")
_CACHE_PATH    = os.path.join(_PROCESSED_DIR, "realtime_cache.parquet")
_PRICE_PATH    = os.path.join(_PROCESSED_DIR, "market_prices.parquet")
_WIFEED_URL    = "https://wifeed.vn/api/du-lieu-gia-eod/ohcl"
_TZ_VN         = pytz.timezone("Asia/Ho_Chi_Minh")
# Giờ giao dịch (giờ VN)
_TRADING_START = dtime(9, 0)
_TRADING_END   = dtime(14, 45)
_EOD_CONFIRM   = dtime(15, 30)   # 1 lần cuối xác nhận EOD # dời trễ 30 phút, đảm bảo Wifeed đã settle GD thỏa thuận
_EOD_CUTOFF    = dtime(17, 0)   # Cho phép fetch EOD đến 17:00
                                 # (Wifeed giữ data cuối ngày đến tối)
# Khoảng cách tối thiểu giữa 2 request (giây) — Wifeed rate limit.
# Đọc từ biến môi trường WIFEED_FETCH_INTERVAL_SECONDS để mỗi môi trường tự
# chỉnh riêng (vd: local test 60s cho nhanh, HF Space đặt 3600s để tiết kiệm
# quota/tránh rate-limit) mà KHÔNG cần sửa code — chỉ set env var tương ứng.
# Áp dụng cho CẢ giá lẫn index vì 2 loại dữ liệu này lấy chung 1 lần gọi API
# trong _fetch_wifeed() → dùng chung 1 interval là đủ, không cần tách riêng.
try:
    _MIN_INTERVAL = int(os.environ.get("WIFEED_FETCH_INTERVAL_SECONDS", "60"))
except ValueError:
    logger.warning(
        "[Wifeed] WIFEED_FETCH_INTERVAL_SECONDS không phải số hợp lệ — "
        "dùng mặc định 60s."
    )
    _MIN_INTERVAL = 60

# ── Ngày nghỉ giao dịch (HOSE/HNX) — KHÔNG tự tính được bằng weekday(),
# vì phụ thuộc lịch âm (Tết) và thông báo riêng từng năm của Sở GDCK.
# np.busday_count() mặc định chỉ loại thứ 7/CN — nếu không có list này,
# mọi ngày lễ giữa tuần (Tet, 30/4-1/5, Quoc khanh...) sẽ bị đếm NHẦM là
# "ngày giao dịch bị thiếu dữ liệu", kích hoạt backfill/SSI-fallback không
# cần thiết (đây chính là nguyên nhân days_missing=2 thay vì 1 hôm 1/9/2026
# — 31/8 là ngày nghỉ Quốc khánh theo lịch HOSE, không phải ngày bị thiếu
# data thật).
#
# Nguồn: Thông báo 2294/TB-SGDHCM (HOSE) + 5305/TB-SGDHN (HNX) ngày
# 09/12/2025 và 03/12/2025 công bố lịch nghỉ giao dịch năm 2026.
#
# CÁCH THÊM NĂM MỚI: mỗi năm HOSE công bố lịch nghỉ riêng (thường vào
# tháng 12 năm trước) — chỉ cần thêm các dòng `date(YYYY, M, D)` mới vào
# set bên dưới, không cần sửa logic nào khác trong file này.
_VN_HOLIDAYS: set = {
    # ── 2026 (theo Thông báo 2294/TB-SGDHCM & 5305/TB-SGDHN) ──────────
    date(2026, 1, 1),                                    # Tet Duong lich
    date(2026, 2, 16), date(2026, 2, 17),          # Tet Nguyen Dan
    date(2026, 2, 18), date(2026, 2, 19),          # (5 ngay GD, HOSE/HNX
    date(2026, 2, 20),                                   #  nghi 16/02-20/02)
    date(2026, 4, 27),                                   # Gio To Hung Vuong
                                                                 # (10/3 AL roi CN -> nghi bu T2 27/4)
    date(2026, 4, 30), date(2026, 5, 1),           # 30/4 va 1/5
    date(2026, 8, 31), date(2026, 9, 1),           # Quoc khanh (HOSE: 3 ngay GD
    date(2026, 9, 2),                                    #  31/08-02/09)
    # date(2026, 11, 24),  # Ngay Van hoa VN (moi, hieu luc tu 1/7/2026) —
    #   CHƯA xác nhận được HOSE đã cập nhật lịch nghỉ giao dịch cho ngày
    #   này hay chưa (calendar HOSE gốc công bố 12/2025, trước khi luật có
    #   hiệu lực) — bỏ comment dòng trên nếu xác nhận HOSE nghỉ giao dịch.

    # ── Thêm các năm sau tại đây (2027, 2028, ...) khi HOSE công bố ────
}

# ── State nội bộ ─────────────────────────────────────────────────────────────
_last_fetch_ts:  float        = 0.0          # unix timestamp lần fetch cuối
_eod_appended:   bool         = False        # đã append EOD hôm nay chưa
_eod_date:       str          = ""           # "YYYY-MM-DD" của ngày đã append
_index_appended: bool         = False        # đã append index hôm nay chưa (guard mới)
_index_date:     str          = ""           # "YYYY-MM-DD" của ngày đã append index
_cache_lock:     threading.Lock = threading.Lock()
_scheduler_started: bool      = False
# ── In-memory cache ──────────────────────────────────────────────────────────
# dict: { "Ticker": { "Price Close": float, "Volume": int, ... } }
_realtime_snapshot: dict = {}
_snapshot_ts:       float = 0.0    # timestamp lần cập nhật gần nhất
_realtime_index: dict = {}   # { "VNINDEX": 1821.32, "VN30": 1970.01, ... }
def get_realtime_index() -> dict:
    """Giá realtime các chỉ số thị trường."""
    return _realtime_index
# Thêm path index parquet
_INDEX_PATH = os.path.join(_PROCESSED_DIR, "index.parquet")
def _append_index_to_parquet(df_raw: pd.DataFrame) -> None:
    """
    Trích các mã chỉ số từ Wifeed response và merge vào index.parquet.
    Wifeed trả VNINDEX, VN30, HNXINDEX, HNX30, UPCOM trong cùng 1 response
    (ceiling=null, floor=null → bị filter bỏ trong _parse_wifeed_response).
    Nên hàm này phải nhận df_raw TRƯỚC KHI filter ceiling.
    """
    # Các mã chỉ số cần lấy
    INDEX_SYMBOLS = {
        "VNINDEX":  "VNINDEX_Close",
        "VN30":     "VN30_Close",
        "HNXINDEX": "HNXINDEX_Close",
        "HNX30":    "HNX30_Close",
        "UPCOM":    "UPCOM_Close",
    }
    # [FIX] Mapping Volume song song với Close — Wifeed đã trả sẵn Volume
    # (volume_adjust) cho cả dòng chỉ số trong df_raw, nhưng trước đây hàm
    # này chỉ pivot "Price Close", bỏ hẳn Volume. Hậu quả: index.parquet
    # KHÔNG BAO GIỜ có cột "{SYMBOL}_Volume", khiến ô "KL TB 20P" trên UI
    # luôn rỗng bất kể lấy bao nhiêu phiên trước đó — không phải do timing
    # trong phiên, mà do cột này chưa từng tồn tại trong file.
    INDEX_VOL_SYMBOLS = {
        "VNINDEX":  "VNINDEX_Volume",
        "VN30":     "VN30_Volume",
        "HNXINDEX": "HNXINDEX_Volume",
        "HNX30":    "HNX30_Volume",
        "UPCOM":    "UPCOM_Volume",
    }
    global _index_appended, _index_date
    today_str = _now_vn().strftime("%Y-%m-%d")
    # [FIX] Guard 1 lần/ngày — trước đây hàm này được gọi lại mỗi 60s trong
    # SUỐT cửa sổ EOD 15:00–17:00 (2 tiếng ≈ 120 lần gọi), mỗi lần đọc +
    # pivot + merge + ghi lại index.parquet dù dữ liệu Close cuối ngày
    # không đổi nữa sau khi đóng cửa — lãng phí I/O không cần thiết. Áp
    # dụng đúng pattern guard đã dùng cho _append_eod_to_parquet().
    if _index_appended and _index_date == today_str:
        logger.debug(f"[Wifeed] Index đã được append hôm nay ({today_str}), bỏ qua")
        return
    try:
        if df_raw.empty:
            return
        # df_raw ở đây là list dict từ API, chưa parse → cần parse lại không filter ceiling
        # Gọi trực tiếp với df đã rename (trước bước filter ceiling)
        # Lọc chỉ các mã index
        df_idx_rows = df_raw[df_raw["Ticker"].isin(INDEX_SYMBOLS.keys())].copy()
        if df_idx_rows.empty:
            logger.warning("[Wifeed] Không tìm thấy mã index trong response")
            return
        # Pivot: mỗi mã thành 1 cột Close
        df_close = df_idx_rows[["Ticker", "Date", "Price Close"]].copy()
        df_pivot = df_close.pivot(index="Date", columns="Ticker", values="Price Close")
        # Đổi tên cột theo mapping
        rename_cols = {sym: col for sym, col in INDEX_SYMBOLS.items() if sym in df_pivot.columns}
        df_pivot    = df_pivot.rename(columns=rename_cols)

        # [FIX] Pivot thêm Volume, ghép ngang theo Date (outer join — không
        # làm mất phiên nào dù thiếu Volume ở 1 vài dòng)
        if "Volume" in df_idx_rows.columns:
            df_vol = df_idx_rows[["Ticker", "Date", "Volume"]].copy()
            df_pivot_vol = df_vol.pivot(index="Date", columns="Ticker", values="Volume")
            rename_vol = {sym: col for sym, col in INDEX_VOL_SYMBOLS.items() if sym in df_pivot_vol.columns}
            df_pivot_vol = df_pivot_vol.rename(columns=rename_vol)
            df_pivot = df_pivot.join(df_pivot_vol, how="outer")
        else:
            logger.warning("[Wifeed] df_raw không có cột Volume — bỏ qua Volume cho index parquet")

        df_pivot = df_pivot.reset_index()
        def _to_naive(s):
            dt = pd.to_datetime(s, errors="coerce", utc=True)
            return dt.dt.tz_convert(None) if dt.dt.tz is not None else dt
        df_pivot["Date"] = _to_naive(df_pivot["Date"])
        # Merge với parquet cũ
        os.makedirs(_PROCESSED_DIR, exist_ok=True)
        if os.path.exists(_INDEX_PATH):
            df_existing = pd.read_parquet(_INDEX_PATH)
            df_existing["Date"] = _to_naive(df_existing["Date"])
            # Thêm các cột mới nếu chưa có
            for col in df_pivot.columns:
                if col not in df_existing.columns and col != "Date":
                    df_existing[col] = None
            df_combined = pd.concat([df_existing, df_pivot], ignore_index=True)
            df_combined = df_combined.drop_duplicates(subset=["Date"], keep="last")
            df_combined = df_combined.sort_values("Date")
        else:
            df_combined = df_pivot
        df_combined.to_parquet(_INDEX_PATH, index=False)
        cols_saved = [c for c in df_combined.columns if c != "Date"]
        last_date  = df_combined["Date"].max()
        last_row   = df_combined[df_combined["Date"] == last_date].iloc[-1].to_dict()
        logger.info(
            f"[Wifeed] Index parquet updated: {cols_saved} | "
            f"Tổng: {len(df_combined)} phiên"
        )
        # [DEBUG] Log tường minh ngày cuối cùng + giá trị dòng cuối — để tự
        # thấy ngay Volume có thật sự được ghi hay không, không cần chạy tay
        # pandas riêng mỗi lần nghi ngờ bug.
        logger.info(
            f"[Wifeed][DEBUG] Ngày cuối cùng trong index.parquet: {last_date} | "
            f"Dòng cuối: {last_row}"
        )
        _index_appended = True
        _index_date     = today_str
    except Exception as e:
        logger.error(f"[Wifeed] Lỗi append index: {e}", exc_info=True)
def get_realtime_snapshot() -> dict:
    """Trả về in-memory snapshot realtime (thread-safe read)."""
    return _realtime_snapshot
def get_snapshot_timestamp() -> float:
    """Unix timestamp của lần fetch gần nhất."""
    return _snapshot_ts
# ── Helpers ──────────────────────────────────────────────────────────────────
def _now_vn() -> datetime:
    return datetime.now(_TZ_VN)
def _is_trading_time() -> bool:
    """Trả về True nếu đang trong khung giờ giao dịch hoặc giờ xác nhận EOD."""
    t = _now_vn().time()
    return _TRADING_START <= t <= _EOD_CUTOFF
def _is_eod_time() -> bool:
    """True nếu đang trong khoảng 15:30–17:00 để append EOD."""
    t = _now_vn().time()
    return _EOD_CONFIRM <= t <= _EOD_CUTOFF
def _parse_wifeed_response_all(data: list) -> pd.DataFrame:
    """Parse toàn bộ — KHÔNG filter ceiling. Dùng nội bộ."""
    if not data:
        return pd.DataFrame()
    df = pd.DataFrame(data)
    rename = {
        "mack": "Ticker", "ngay": "Date",
        "open_adjust": "Price Open", "high_adjust": "Price High",
        "low_adjust": "Price Low", "close_adjust": "Price Close",
        "volume_adjust": "Volume", "changed": "Price_Change",
        "changedratio": "Price_Change_Pct", "giatri_giaodich": "Turnover",
        "ceilingprice": "Ceiling", "floorprice": "Floor",
        "kl_nn_mua": "Foreign_Buy_Vol", "kl_nn_ban": "Foreign_Sell_Vol",
        "gt_nn_mua": "Foreign_Buy_Val", "gt_nn_ban": "Foreign_Sell_Val",
        "lastupdate": "LastUpdate",
    }
    df = df.rename(columns={k: v for k, v in rename.items() if k in df.columns})
    for col in ["Price Open","Price High","Price Low","Price Close",
                "Price_Change","Price_Change_Pct","Ceiling","Floor"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    for col in ["Volume","Turnover","Foreign_Buy_Vol","Foreign_Sell_Vol",
                "Foreign_Buy_Val","Foreign_Sell_Val"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype("int64")
    if "Date" in df.columns:
        _dates = pd.to_datetime(df["Date"], errors="coerce", utc=True)
        if _dates.dt.tz is not None:
            _dates = _dates.dt.tz_convert(None)
        df["Date"] = _dates.dt.normalize()
    df = df.dropna(subset=["Ticker","Price Close"])
    df["Ticker"] = df["Ticker"].astype(str).str.strip()
    return df
def _parse_wifeed_response(data: list) -> pd.DataFrame:
    """Parse và filter chỉ cổ phiếu có ceiling. Backward compat."""
    df = _parse_wifeed_response_all(data)
    if "Ceiling" in df.columns:
        df = df[df["Ceiling"].notna()].copy()
    return df
# SAU — trả tuple (df_stocks, df_all_parsed):
def _fetch_wifeed() -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Trả (df_stocks, df_all):
      - df_stocks: chỉ cổ phiếu có ceiling/floor (dùng cho screener)
      - df_all:    toàn bộ bao gồm chỉ số (dùng cho index parquet)
    """
    global _last_fetch_ts
    api_key = os.environ.get("WIFEED_API_KEY", "").strip()
    if not api_key:
        logger.error("[Wifeed] WIFEED_API_KEY chưa được set trong .env — bỏ qua fetch")
        return pd.DataFrame(), pd.DataFrame()
    now = time.time()
    elapsed = now - _last_fetch_ts
    if elapsed < _MIN_INTERVAL:
        wait = _MIN_INTERVAL - elapsed
        logger.warning(
            f"[Wifeed] Gọi quá sớm ({elapsed:.1f}s < {_MIN_INTERVAL}s). "
            f"Đợi thêm {wait:.1f}s để tuân thủ rate limit."
        )
        time.sleep(wait)
    try:
        t0  = time.perf_counter()
        resp = requests.get(
            _WIFEED_URL,
            params={"apikey": api_key},
            timeout=30,
        )
        _last_fetch_ts = time.time()
        elapsed_req    = time.perf_counter() - t0
        if resp.status_code != 200:
            logger.error(f"[Wifeed] HTTP {resp.status_code}: {resp.text[:200]}")
            return pd.DataFrame(), pd.DataFrame()
        payload  = resp.json()
        data     = payload.get("data", [])
        df_all   = _parse_wifeed_response_all(data)   # không filter ceiling
        df_stocks = df_all[df_all["Ceiling"].notna()].copy()  # chỉ cổ phiếu
        logger.info(
            f"[Wifeed] Fetch OK: {len(df_stocks)} cổ phiếu + "
            f"{len(df_all)-len(df_stocks)} chỉ số | "
            f"{elapsed_req:.2f}s | {_now_vn().strftime('%H:%M:%S')} VN"
        )
        return df_stocks, df_all
    except requests.exceptions.Timeout:
        logger.error("[Wifeed] Request timeout sau 30s")
    except requests.exceptions.ConnectionError as e:
        logger.error(f"[Wifeed] Connection error: {e}")
    except Exception as e:
        logger.error(f"[Wifeed] Lỗi không xác định: {e}", exc_info=True)
    return pd.DataFrame(), pd.DataFrame()
_ROOT_PUT_URL   = "https://wifeed.vn/api/du-lieu-gia-eod/root-put"
_MARKET_SUFFIX  = {6: ".HM", 7: ".HN", 8: ".HNO"}
def _fetch_root_put_eod(trading_date: str) -> pd.DataFrame:
    """
    Gọi bulk root-put (KHÔNG truyền symbol) để lấy TOÀN THỊ TRƯỜNG cho 1 ngày,
    có đủ volume_match + volume_put (= Tổng khối lượng chuẩn giống SSI/CafeF),
    khác với endpoint ohcl (volume_adjust) chỉ có khớp lệnh.
    Chỉ dùng cho EOD (1 lần/ngày), KHÔNG dùng cho polling 60s trong phiên.
    Trả về DataFrame: Ticker (đã có đuôi sàn), Volume, Turnover.
    """
    api_key = os.environ.get("WIFEED_API_KEY", "").strip()
    if not api_key:
        logger.error("[Wifeed] WIFEED_API_KEY chưa set — bỏ qua fetch root-put EOD")
        return pd.DataFrame()
    all_rows = []
    page = 1
    while True:
        try:
            resp = requests.get(
                _ROOT_PUT_URL,
                params={
                    "apikey": api_key,
                    "from-date": trading_date,
                    "to-date": trading_date,
                    "limit": 100,
                    "page": page,
                },
                timeout=30,
            )
            resp.raise_for_status()
            payload = resp.json()
        except Exception as e:
            logger.error(f"[Wifeed] Lỗi gọi root-put trang {page}: {e}")
            break
        rows = payload.get("data", [])
        if not rows:
            break
        all_rows.extend(rows)
        total_page = payload.get("meta", {}).get("total_page", 1)
        logger.info(f"[Wifeed] root-put EOD: trang {page}/{total_page} ({len(rows)} mã)")
        if page >= total_page:
            break
        page += 1
        time.sleep(0.3)   # tránh spam quá nhanh giữa các trang
    if not all_rows:
        logger.warning("[Wifeed] root-put EOD không trả về dữ liệu nào")
        return pd.DataFrame()
    df = pd.DataFrame(all_rows)
    # Chỉ giữ cổ phiếu thường (7 = Stock) — bỏ trái phiếu/ETF/chứng quyền/futures/index
    if "security_group_id" in df.columns:
        df = df[df["security_group_id"] == 7].copy()
    if df.empty:
        return df
    df["Volume"]   = pd.to_numeric(df.get("volume_match"), errors="coerce").fillna(0) + \
                      pd.to_numeric(df.get("volume_put"), errors="coerce").fillna(0)
    df["Turnover"] = pd.to_numeric(df.get("gross_trade_amount"), errors="coerce").fillna(0) + \
                      pd.to_numeric(df.get("gross_trade_amount_put"), errors="coerce").fillna(0)
    # Ghép đuôi sàn theo market_id -> khớp đúng format ticker trong market_prices.parquet
    df["Ticker"] = df.apply(
        lambda r: str(r["symbol"]).strip().upper() + _MARKET_SUFFIX.get(r.get("market_id"), ""),
        axis=1
    )
    df = df.rename(columns={
        "open": "Price Open", "high": "Price High",
        "low": "Price Low", "close": "Price Close",
    })
    df["Date"] = pd.to_datetime(trading_date)
    logger.info(f"[Wifeed] root-put EOD hoàn tất: {len(df)} mã, ngày {trading_date}")
    return df[["Ticker", "Date", "Price Open", "Price High",
               "Price Low", "Price Close", "Volume", "Turnover"]]
def _save_realtime_cache(df: pd.DataFrame, df_all: pd.DataFrame = None) -> None:
    global _realtime_snapshot, _snapshot_ts, _realtime_index
    if df.empty:
        return
    # # ── Chỉ giữ ticker có trong market_prices.parquet ─────────────────────
    # try:
    #     if os.path.exists(_PRICE_PATH):
    #         _known = pd.read_parquet(_PRICE_PATH, columns=["Ticker"])
    #         known_tickers = set(_known["Ticker"].unique())
    #         before = len(df)
    #         df = df[df["Ticker"].isin(known_tickers)].copy()
    #         logger.info(
    #             f"[Wifeed] Filter ticker: {before} → {len(df)} mã "
    #             f"(bỏ {before - len(df)} mã không có trong parquet)"
    #         )
    # except Exception as e:
    #     logger.warning(f"[Wifeed] Không filter được ticker: {e} — giữ nguyên {len(df)} mã")
    os.makedirs(_PROCESSED_DIR, exist_ok=True)
    with _cache_lock:
        try:
            df.to_parquet(_CACHE_PATH, index=False)
            _realtime_snapshot = {
                row["Ticker"]: row.to_dict()
                for _, row in df.iterrows()
            }
            _snapshot_ts = time.time()
            logger.debug(f"[Wifeed] Cache saved: {len(df)} mã → {_CACHE_PATH}")
        except Exception as e:
            logger.error(f"[Wifeed] Lỗi ghi cache: {e}")
    # Lưu giá index realtime
    if df_all is not None and not df_all.empty:
        INDEX_SYMBOLS = {
            "VNINDEX": "VNINDEX", "VN30": "VN30",
            "HNXINDEX": "HNXINDEX", "HNX30": "HNX30", "UPCOM": "UPCOM",
        }
        idx_rows = df_all[df_all["Ticker"].isin(INDEX_SYMBOLS.keys())]
        for _, row in idx_rows.iterrows():
            ticker = row["Ticker"]
            price  = row.get("Price Close")
            change = row.get("Price_Change_Pct", 0)
            if price is not None and not pd.isna(price):
                _realtime_index[ticker] = {
                    "close": float(price),
                    "change_pct": float(change or 0),
                }
        if _realtime_index:
            logger.info(f"[Wifeed] Index realtime: { {k: v['close'] for k, v in _realtime_index.items()} }")
def _append_eod_to_parquet(df: pd.DataFrame) -> None:
    global _eod_appended, _eod_date
    today_str = _now_vn().strftime("%Y-%m-%d")
    if _eod_appended and _eod_date == today_str:
        logger.info(f"[Wifeed] EOD đã được append hôm nay ({today_str}), bỏ qua")
        return
    if df.empty:
        logger.warning("[Wifeed] DataFrame rỗng, không append EOD")
        return
    keep_cols = ["Ticker", "Date", "Price Open", "Price High",
             "Price Low", "Price Close", "Volume", "Turnover"]
    df_eod = df[[c for c in keep_cols if c in df.columns]].copy()
    df_root = _fetch_root_put_eod(today_str)

    if not df_root.empty:
        df_eod["_base_ticker"] = df_eod["Ticker"].astype(str).str.upper().str.strip()
        df_root["_base_ticker"] = df_root["Ticker"].str.replace(r'\.(HM|HN|HNO)$', '', regex=True)
        vol_map    = df_root.set_index("_base_ticker")["Volume"].to_dict()
        turn_map   = df_root.set_index("_base_ticker")["Turnover"].to_dict()
        ticker_map = df_root.set_index("_base_ticker")["Ticker"].to_dict()
        n_matched  = df_eod["_base_ticker"].isin(ticker_map).sum()

        # [FIX] match_ratio phải tính TRƯỚC dòng log dùng nó — bản trước đó
        # log dùng match_ratio ở đây rồi MỚI gán ở dòng dưới -> UnboundLocalError
        # mỗi khi root-put CÓ dữ liệu (tức là MỌI ngày giao dịch bình thường)
        # -> EOD không bao giờ merge được, job crash lặp lại mỗi 60s tới 17h.
        match_ratio = n_matched / len(df_eod) if len(df_eod) > 0 else 0
        logger.info(
            f"[Wifeed DEBUG] EOD fetch @ {_now_vn().strftime('%H:%M:%S')} | "
            f"match_ratio={match_ratio:.1%} | n_matched={n_matched}/{len(df_eod)}"
        )
        # ─── Validate root-put có "đủ" dữ liệu hay chưa ─────────────
        # Nếu số mã khớp quá ít (<80% tổng mã) → root-put backend có thể
        # chưa hoàn tất tính toán, KHÔNG lock guard, để job 60s sau retry.
        if match_ratio < 0.8:
            logger.warning(
                f"[Wifeed] root-put EOD chỉ khớp {n_matched}/{len(df_eod)} "
                f"({match_ratio:.0%}) — có thể backend chưa settle xong. "
                f"KHÔNG lock guard, sẽ retry ở lần fetch tiếp theo."
            )
            return   # ← không set _eod_appended, không merge, thử lại sau 60s

        df_eod["Volume"]   = df_eod["_base_ticker"].map(vol_map).fillna(df_eod["Volume"])
        df_eod["Turnover"] = df_eod["_base_ticker"].map(turn_map).fillna(df_eod.get("Turnover", 0))
        df_eod["Ticker"]   = df_eod["_base_ticker"].map(ticker_map).fillna(df_eod["Ticker"])
        df_eod = df_eod.drop(columns=["_base_ticker"])
        logger.info(f"[Wifeed] Đã override Volume/Turnover từ root-put: {n_matched}/{len(df_eod)} mã khớp")
    else:
        # [FIX] BỎ `return` ở đây — trước đây nếu root-put rỗng hoàn toàn thì
        # SKIP LUÔN việc merge giá, mâu thuẫn với chính comment ngay dòng này
        # ("giữ Volume/Ticker từ ohcl"): ý định gốc là vẫn merge với Volume
        # lấy tạm từ ohcl (kém chính xác hơn nhưng còn hơn không có gì), chứ
        # không phải bỏ merge giá hoàn toàn. Không return -> chạy tiếp xuống
        # _merge_eod_into_price_parquet(df_eod) bên dưới đúng như comment mô tả.
        logger.warning("[Wifeed] root-put EOD trống — giữ Volume/Ticker từ ohcl")

    if _merge_eod_into_price_parquet(df_eod):
        _eod_appended = True
        _eod_date     = today_str
def _trigger_background_snapshot_rebuild() -> None:
    """
    [MỚI] Sau khi EOD merge xong, _MARKET_CACHE và snapshot RAM
    (data_loader._snapshot_df) đều đã bị invalidate (xem
    _merge_eod_into_price_parquet). Nếu KHÔNG làm gì thêm, USER ĐẦU TIÊN
    mở screener sau 15:00 sẽ là người phải gánh full rebuild snapshot
    (~30s theo benchmark Scenario H) NGAY TRÊN request thread của họ —
    trải nghiệm rất tệ (trang treo ~30s không rõ lý do).

    Hàm này chủ động build lại snapshot trên 1 thread nền riêng (daemon),
    KHÔNG block scheduler job (_fetch_job chạy xong ngay, không đợi hàm
    này), để khi user thật sự vào web thì RAM đã sẵn sàng.

    An toàn với race condition: get_snapshot_df() đã có double-checked
    locking (_snapshot_build_lock + _snapshot_lock, xác nhận qua benchmark
    Scenario H: 20 thread gọi đồng thời chỉ 1 lần build) — nên nếu 1 user
    thật sự bấm vào web CÙNG LÚC thread nền này đang build, họ chỉ phải
    ĐỢI (không tự build lại lần 2), và cả hai đều nhận đúng 1 kết quả mới.
    """
    def _rebuild():
        try:
            import src.backend.data_loader as _dl
            t0 = time.time()
            _dl.get_snapshot_df()
            logger.info(
                f"[Wifeed] Background snapshot rebuild sau EOD hoàn tất "
                f"trong {time.time() - t0:.1f}s"
            )
        except Exception as e:
            logger.error(f"[Wifeed] Lỗi background rebuild snapshot: {e}", exc_info=True)

    threading.Thread(target=_rebuild, daemon=True, name="wifeed-snapshot-rebuild").start()


def _merge_eod_into_price_parquet(df_eod: pd.DataFrame) -> bool:
    """
    Merge 1 batch dữ liệu EOD (đã có đủ Ticker/Date/OHLC/Volume/Turnover)
    vào market_prices.parquet. Dùng chung cho cả luồng EOD-cuối-phiên lẫn
    luồng backfill ngày bị thiếu qua root-put.
    Trả True nếu ghi thành công.
    """
    with _cache_lock:
        try:
            if os.path.exists(_PRICE_PATH):
                df_existing = pd.read_parquet(_PRICE_PATH)
                _company_cols = [c for c in [
                    "Exchange", "Company Common Name", "GICS Sector Name",
                    "GICS Sub-Industry Name", "TRBC Industry Name",
                ] if c in df_existing.columns]
                if _company_cols:
                    company_map = (
                        df_existing[["Ticker"] + _company_cols]
                        .drop_duplicates("Ticker", keep="last")
                        .set_index("Ticker")
                    )
                    for col in _company_cols:
                        df_eod[col] = df_eod["Ticker"].map(company_map[col])
                    logger.info(f"[Wifeed] Đã gắn lại {_company_cols} cho {len(df_eod)} dòng EOD")
                def _to_naive(s):
                    dt = pd.to_datetime(s, errors="coerce", utc=True)
                    return dt.dt.tz_convert(None) if dt.dt.tz is not None else dt
                df_existing["Date"] = _to_naive(df_existing["Date"])
                df_eod["Date"]      = _to_naive(df_eod["Date"])
                df_combined = pd.concat([df_existing, df_eod], ignore_index=True)
                df_combined = df_combined.drop_duplicates(
                    subset=["Ticker", "Date"], keep="last"
                ).sort_values(["Ticker", "Date"])
            else:
                df_combined = df_eod
            df_combined.to_parquet(_PRICE_PATH, index=False)
            logger.info(f"[Wifeed] EOD merged: Tổng {len(df_combined):,} dòng")
            try:
                import src.backend.data_loader as _dl
                _dl._MARKET_CACHE["data"] = None
                _dl._MARKET_CACHE["ts"]   = 0.0
                # [FIX] Trước đây chỉ clear _MARKET_CACHE (dùng bởi
                # load_market_data()) — KHÔNG đụng tới _snapshot_df (dùng
                # bởi get_snapshot_df(), nguồn dữ liệu CHÍNH của UI
                # screener). Benchmark scenario_cache_invalidation đã xác
                # nhận thật: sau EOD merge, snapshot_df_unaffected_by_eod_merge
                # = true, tức UI vẫn hiển thị dữ liệu "thiu" của ngày hôm
                # trước cho tới khi app restart. Clear luôn _snapshot_df ở
                # đây để lần get_snapshot_df() kế tiếp tự phát hiện
                # market_prices.parquet mới hơn snapshot_cache.parquet
                # (qua _snapshot_stale()) và tự rebuild.
                with _dl._snapshot_lock:
                    _dl._snapshot_df = None
            except Exception as e:
                logger.warning(f"[Wifeed] Lỗi clear cache: {e}")
            else:
                # Chỉ trigger rebuild nền khi clear cache ở trên THÀNH CÔNG
                # (nếu import/clear lỗi, không có gì để rebuild dựa trên).
                _trigger_background_snapshot_rebuild()
            return True
        except Exception as e:
            logger.error(f"[Wifeed] Lỗi merge EOD: {e}", exc_info=True)
            return False
_scheduler_instance = None   # giữ reference để dừng được
def _stop_scheduler() -> None:
    """Dừng scheduler sau giờ giao dịch — sẽ restart vào ngày mai khi app restart."""
    global _scheduler_started
    try:
        if _scheduler_instance and _scheduler_instance.running:
            _scheduler_instance.shutdown(wait=False)
            _scheduler_started = False
            logger.info("[Wifeed] Scheduler đã dừng sau giờ giao dịch")
    except Exception as e:
        logger.warning(f"[Wifeed] Lỗi khi dừng scheduler: {e}")
def _filter_known_tickers(df: pd.DataFrame) -> pd.DataFrame:
    """
    Chỉ giữ ticker có trong market_prices.parquet.
    Tự động strip đuôi sàn (.HM/.HN/.HNO) khi so sánh vì:
      - Parquet lưu: 'A32.HM', 'AAA.HM', ...
      - Wifeed trả:  'A32', 'AAA', ...  (không có đuôi)
    """
    if df.empty:
        return df
    try:
        if os.path.exists(_PRICE_PATH):
            known = pd.read_parquet(_PRICE_PATH, columns=["Ticker"])
            # Strip đuôi sàn để so sánh đúng
            known_clean = (
                known["Ticker"]
                .astype(str)
                .str.replace(r'\.(HM|HN|HNO)$', '', regex=True)
                .str.strip()
                .unique()
            )
            known_set = set(known_clean)
            before    = len(df)
            df        = df[df["Ticker"].isin(known_set)].copy()
            logger.info(
                f"[Wifeed] Filter ticker: {before} → {len(df)} mã "
                f"(bỏ {before - len(df)} mã ngoài parquet)"
            )
    except Exception as e:
        logger.warning(f"[Wifeed] Không filter được ticker: {e} — giữ nguyên {len(df)} mã")
    return df
# ── Job chính chạy bởi scheduler ─────────────────────────────────────────────
def _fetch_job() -> None:
    global _eod_appended
    if not _is_trading_time():
        logger.debug(f"[Wifeed] Ngoài giờ GD ({_now_vn().strftime('%H:%M')}), bỏ qua")
        return

    # [FIX] _is_trading_time() chỉ check GIỜ trong ngày, không biết hôm nay
    # có phải ngày nghỉ lễ hay không — nếu không thêm check này, vào ngày
    # lễ giữa tuần (Tet, Quốc khánh...) trong khung 09:00-17:00, job vẫn
    # gọi Wifeed mỗi 60s và có thể tạo dòng EOD "giả" cho 1 ngày market
    # không hề mở cửa.
    if _now_vn().date() in _VN_HOLIDAYS:
        logger.debug(f"[Wifeed] Hôm nay ({_now_vn().strftime('%Y-%m-%d')}) là ngày nghỉ lễ, bỏ qua")
        return

    today_str = _now_vn().strftime("%Y-%m-%d")
    now_t     = _now_vn().time()

    # THÊM: force re-check 1 lần lúc 16:00 dù đã _eod_appended, để bắt các
    # trường hợp GD thỏa thuận muộn hoặc điều chỉnh late-settlement hiếm gặp.
    _FORCE_RECONFIRM = dtime(16, 0)
    force_recheck = (now_t.hour == _FORCE_RECONFIRM.hour
                      and now_t.minute == _FORCE_RECONFIRM.minute)

    if _is_eod_time() and _eod_appended and _eod_date == today_str and not force_recheck:
        logger.debug("[Wifeed] EOD hôm nay đã xong — bỏ qua phần còn lại của cửa sổ EOD")
        return

    df_stocks, df_all = _fetch_wifeed()
    if df_stocks.empty:
        return
    df_filtered = _filter_known_tickers(df_stocks)
    _save_realtime_cache(df_filtered, df_all)
    if _is_eod_time():
        if force_recheck:
            _eod_appended = False   # mở khóa tạm để cho phép merge lại 1 lần
        _append_eod_to_parquet(df_filtered)
        _append_index_to_parquet(df_all)
# ── Khởi động scheduler ──────────────────────────────────────────────────────
def start_wifeed_scheduler() -> None:
    """
    Khởi động APScheduler background thread.
    Gọi 1 lần duy nhất trong main.py TRƯỚC app.run().
    """
    global _scheduler_started
    if _scheduler_started:
        logger.info("[Wifeed] Scheduler đã chạy, bỏ qua lần gọi thứ 2")
        return
    # Kiểm tra API key trước khi start
    api_key = os.environ.get("WIFEED_API_KEY", "").strip()
    if not api_key:
        logger.warning(
            "[Wifeed] WIFEED_API_KEY chưa có trong .env → "
            "Scheduler KHÔNG được khởi động. "
            "Set biến môi trường và restart app."
        )
        return
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.interval import IntervalTrigger
    except ImportError:
        logger.error(
            "[Wifeed] APScheduler chưa được cài: pip install apscheduler — "
            "Scheduler không khởi động được."
        )
        return
    # SAU:
    global _scheduler_instance
    scheduler = BackgroundScheduler(
        timezone=_TZ_VN,
        job_defaults={
            "coalesce":           True,
            "max_instances":      1,
            "misfire_grace_time": 30,
        },
    )
    scheduler.add_job(
        _fetch_job,
        trigger=IntervalTrigger(seconds=_MIN_INTERVAL),
        id="wifeed_fetch",
        name="Wifeed EOD Fetch",
        replace_existing=True,
    )
    scheduler.start()
    _scheduler_instance  = scheduler   # ← lưu reference
    _scheduler_started   = True
    logger.info(
        f"[Wifeed] ✅ Scheduler started | "
        f"Interval: {_MIN_INTERVAL}s | "
        f"Giờ giao dịch: {_TRADING_START}–{_TRADING_END} | "
        f"EOD cutoff: {_EOD_CUTOFF}"
    )
    # ── Startup fetch: lấy data hôm nay nếu cache chưa có ─────────────────
    # ── Startup fetch: lấy data hôm nay hoặc backfill nếu thiếu ───────────
    #
    # [FIX] TRƯỚC ĐÂY toàn bộ logic này (kể cả phần backfill ngày thiếu qua
    # root-put) nằm trong 1 hàm nội bộ `_startup_fetch()`, bị ném vào
    # threading.Thread(daemon=True).start() KHÔNG có .join() — tức là
    # "bắn rồi quên". main.py gọi start_wifeed_scheduler() xong chạy tiếp
    # ngay bước preload/build snapshot trên thread chính, KHÔNG đợi thread
    # nền backfill xong. Trước đây bug vô hình vì nhánh backfill chỉ gán 1
    # biến rồi thoát ngay (siêu nhanh). Từ khi nhánh này gọi thật
    # _fetch_root_put_eod() (network + phân trang, chậm hơn hẳn), main
    # thread luôn đọc được parquet CŨ trước khi thread nền ghi xong —
    # snapshot build với data thiếu 1 ngày, đúng bug bạn gặp.
    #
    # GIẢI PHÁP: gọi ĐỒNG BỘ (blocking) ngay tại đây, KHÔNG dùng Thread nữa.
    # start_wifeed_scheduler() giờ chỉ return SAU KHI backfill xong — miễn
    # main.py gọi start_wifeed_scheduler() TRƯỚC bước preload/build snapshot
    # (đúng thứ tự log gốc bạn gửi: "Scheduler started" luôn in trước
    # "Pre-loading data") thì race condition biến mất hoàn toàn, không cần
    # sửa gì thêm ở main.py.
    run_startup_backfill()
def run_startup_backfill() -> None:
    """
    [FIX] Hàm PUBLIC, ĐỒNG BỘ (blocking) — main.py PHẢI gọi hàm này trực
    tiếp và đợi nó return xong TRƯỚC KHI build snapshot lần đầu (trước khi
    gọi get_snapshot_df()/_build_snapshot_df()). KHÔNG được bọc trong
    threading.Thread nữa — nếu chạy nền không đợi, sẽ tái diễn đúng race
    condition đã gây bug (preload đọc parquet trước khi backfill ghi xong).
    Logic bên trong giữ nguyên 100% như trước (chỉ đổi từ nested function
    sang top-level function để gọi được từ bên ngoài module).
    """
    import datetime as dt
    today_vn = _now_vn().date()
    now_t = _now_vn().time()
    # 1. Kiểm tra ngày giao dịch (Thứ 2 - Thứ 6)
    # [FIX] Thêm điều kiện not-holiday — trước đây chỉ check weekday() < 5,
    # nên các ngày lễ giữa tuần (Tet, 30/4-1/5, Quoc khanh...) vẫn bị coi
    # là "ngày giao dịch", dẫn tới days_missing tính sai (xem _VN_HOLIDAYS).
    is_trading_day = today_vn.weekday() < 5 and today_vn not in _VN_HOLIDAYS
    last_date = None
    # 2. Tìm ngày cuối cùng trong parquet
    if os.path.exists(_PRICE_PATH):
        try:
            df_cache = pd.read_parquet(_PRICE_PATH, columns=["Date"])
            if not df_cache.empty:
                last_date = pd.to_datetime(df_cache["Date"]).max().date()
        except Exception as e:
            logger.error(f"[Wifeed] Lỗi đọc parquet check date: {e}")
    needs_wifeed_eod = False
    # [FIX] Cờ riêng cho việc backfill index.parquet — TÁCH KHỎI needs_wifeed_eod.
    # Lý do: khi days_missing==1, nhánh root-put backfill giá cổ phiếu (dưới
    # đây) set needs_wifeed_eod=False ngay khi thành công -> điều kiện
    # append_today_eod (dòng ~816) trở thành False -> _append_index_to_parquet()
    # KHÔNG BAO GIỜ được gọi, vì đây là chỗ DUY NHẤT gọi hàm đó trong toàn bộ
    # luồng khởi động. Trong khi đó root-put CHỈ trả cổ phiếu thường
    # (security_group_id == 7), KHÔNG trả VNINDEX/VN30/HNXINDEX/HNX30/UPCOM
    # — nên market_prices.parquet được vá đúng ngày, còn index.parquet bị bỏ
    # quên, lệch pha ngày với nhau đúng như log bạn vừa cho thấy (27/08 vs
    # 28/08 của giá cổ phiếu).
    needs_index_backfill = False
    # 3. Logic Backfill bằng SSI/VNDirect (gọi từ daily_updater)
    if last_date:
        # SAU — đếm NGÀY GIAO DỊCH (Thứ 2–6) bị thiếu, bỏ qua cuối tuần:
        # [FIX] Truyền holidays= vào busday_count — trước đây chỉ loại
        # thứ 7/CN, khiến các ngày lễ giữa tuần bị đếm nhầm là "ngày giao
        # dịch bị thiếu dữ liệu" (đúng bug gây days_missing=2 thay vì 1
        # hôm 1/9/2026 — 31/8 là ngày nghỉ Quốc khánh theo lịch HOSE).
        days_missing = int(np.busday_count(
            last_date + timedelta(days=1), today_vn, holidays=sorted(_VN_HOLIDAYS)
        ))
        
        # Nếu hổng > 1 ngày (VD: qua cuối tuần, nghỉ lễ, tắt máy nhiều ngày)
        if days_missing > 1:
            logger.warning(f"[Data Gap] Phát hiện thiếu {days_missing} ngày dữ liệu (Từ {last_date}). Kích hoạt SSI/VND Fallback...")
            try:
                # Import động để tránh circular import, gọi trực tiếp bộ máy của daily_updater
                from daily_updater import run_update
                
                # Chạy update ngầm (Quét 60 ngày, check_if_up_to_date tự động)
                success = run_update(rebuild_snapshot=False)
                if success:
                    logger.info("[Data Gap] Backfill lịch sử bằng SSI/VNDirect thành công.")
                    # daily_updater đã xử lý sạch sẽ (kể cả giá EOD ngày hôm nay nếu có),
                    # nên ta không cần dùng Wifeed để append EOD nữa.
                    needs_wifeed_eod = False 
                else:
                    needs_wifeed_eod = True
            except Exception as e:
                logger.error(f"[Data Gap] Lỗi khi chạy SSI Fallback: {e}")
                needs_wifeed_eod = True # Nếu SSI sập, thử dùng Wifeed để vớt vát EOD
        
        elif days_missing == 1:
            # Ngày bị thiếu đã kết thúc phiên từ lâu -> dữ liệu đã chốt, lấy được
            # bất cứ lúc nào qua root-put (có tham số ngày cụ thể), KHÔNG phụ
            # thuộc hôm nay có phải ngày GD hay không, không phụ thuộc giờ hiện tại.
            missing_date = last_date + dt.timedelta(days=1)
            missing_date_str = missing_date.strftime("%Y-%m-%d")
            logger.info(f"[Wifeed] Backfill 1 ngày thiếu ({missing_date_str}) qua root-put...")
            try:
                df_backfill = _fetch_root_put_eod(missing_date_str)
                if not df_backfill.empty:
                    if _merge_eod_into_price_parquet(df_backfill):
                        logger.info(f"[Wifeed] Backfill {missing_date_str} thành công qua root-put.")
                        needs_wifeed_eod = False   # đã xong, khỏi cần nhánh append_today_eod nữa
                        # [FIX] root-put không có data index -> vẫn cần 1 lượt
                        # fetch bulk OHLC riêng để lấy VNINDEX/VN30/... cho
                        # đúng ngày vừa backfill.
                        needs_index_backfill = True
                    else:
                        needs_wifeed_eod = True
                else:
                    logger.warning(f"[Wifeed] root-put không có data cho {missing_date_str} — có thể là ngày nghỉ lễ.")
                    needs_wifeed_eod = False   # tránh loop vô ích nếu đó là ngày lễ
            except Exception as e:
                logger.error(f"[Wifeed] Lỗi backfill qua root-put: {e}")
                needs_wifeed_eod = True
    else:
        needs_wifeed_eod = True # File chưa tồn tại, bắt buộc lấy
    # 4. Logic lấy data Wifeed "Hôm nay"
    # Điều kiện lấy EOD Wifeed: 
    # Cần lấy EOD VÀ là ngày GD VÀ đã qua 15:00 VÀ hôm nay chưa có data
    append_today_eod = needs_wifeed_eod and is_trading_day and (now_t >= _EOD_CONFIRM) and (last_date != today_vn)
    # Điều kiện tạo realtime_cache: Đang trong giờ giao dịch (để Screener load)
    needs_realtime_cache = is_trading_day and (_TRADING_START <= now_t <= _EOD_CUTOFF)
    # [FIX] Thêm needs_index_backfill vào điều kiện fetch — trước đây chỉ
    # append_today_eod/needs_realtime_cache mới kích hoạt _fetch_wifeed(),
    # nên kịch bản root-put-backfill-thành-công (needs_wifeed_eod đã False)
    # sẽ KHÔNG bao giờ fetch để lấy index, dù cần.
    if append_today_eod or needs_realtime_cache or needs_index_backfill:
        logger.info(
            f"[Wifeed] Chạy startup fetch. Append EOD: {append_today_eod}, "
            f"Build Cache: {needs_realtime_cache}, Backfill Index: {needs_index_backfill}"
        )
        df_stocks, df_all = _fetch_wifeed()
        if not df_stocks.empty:
            df_stocks = _filter_known_tickers(df_stocks)
            _save_realtime_cache(df_stocks, df_all)
        # [FIX] Tách _append_index_to_parquet ra khỏi `if append_today_eod`
        # — chạy độc lập mỗi khi needs_index_backfill=True, kể cả khi
        # append_today_eod=False (đúng kịch bản root-put-backfill).
        if not df_all.empty and (append_today_eod or needs_index_backfill):
            _append_index_to_parquet(df_all)
        if append_today_eod and not df_stocks.empty:
            _append_eod_to_parquet(df_stocks)
            logger.info("[Wifeed] Startup fetch: Đã append EOD hôm nay (Wifeed) vào parquet.")
    else:
        logger.info("[Wifeed] Dữ liệu lịch sử đã Up-to-date hoặc ngoài giờ GD, bỏ qua Wifeed EOD.")
    logger.info("[Wifeed] run_startup_backfill() hoàn tất (đồng bộ).")
# ── Utility đọc cache ────────────────────────────────────────────────────────
def load_realtime_cache() -> pd.DataFrame:
    """
    Đọc realtime_cache.parquet từ disk.
    Dùng khi cần dữ liệu đầy đủ (không chỉ dict in-memory).
    Trả DataFrame rỗng nếu chưa có cache.
    """
    if not os.path.exists(_CACHE_PATH):
        return pd.DataFrame()
    try:
        return pd.read_parquet(_CACHE_PATH)
    except Exception as e:
        logger.error(f"[Wifeed] Lỗi đọc realtime cache: {e}")
        return pd.DataFrame()