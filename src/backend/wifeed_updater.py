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
import pandas as pd
from datetime import datetime, time as dtime
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
_EOD_CONFIRM   = dtime(15, 0)   # 1 lần cuối xác nhận EOD
_EOD_CUTOFF    = dtime(17, 0)   # Cho phép fetch EOD đến 17:00
                                 # (Wifeed giữ data cuối ngày đến tối)

# Khoảng cách tối thiểu giữa 2 request (giây) — Wifeed rate limit
_MIN_INTERVAL  = 60

# ── State nội bộ ─────────────────────────────────────────────────────────────
_last_fetch_ts:  float        = 0.0          # unix timestamp lần fetch cuối
_eod_appended:   bool         = False        # đã append EOD hôm nay chưa
_eod_date:       str          = ""           # "YYYY-MM-DD" của ngày đã append
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
        df_idx_rows = df_idx_rows[["Ticker", "Date", "Price Close"]].copy()
        df_pivot    = df_idx_rows.pivot(index="Date", columns="Ticker", values="Price Close")

        # Đổi tên cột theo mapping
        rename_cols = {sym: col for sym, col in INDEX_SYMBOLS.items() if sym in df_pivot.columns}
        df_pivot    = df_pivot.rename(columns=rename_cols).reset_index()

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
        logger.info(
            f"[Wifeed] Index parquet updated: {cols_saved} | "
            f"Tổng: {len(df_combined)} phiên"
        )

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
    """True nếu đang trong khoảng 15:00–15:05 để append EOD."""
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
        return pd.DataFrame()

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
            return pd.DataFrame()

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

    logger.info(f"[Wifeed] root-put EOD hoàn tất: {len(df)} mã, ngày {trading_date}")
    return df[["Ticker", "Volume", "Turnover"]]

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
    """
    Append dữ liệu EOD vào market_prices.parquet.
    Dedup theo (Ticker, Date) — giữ bản mới nhất.
    Chỉ chạy 1 lần mỗi ngày.
    Volume/Turnover được lấy từ root-put (khớp lệnh + thỏa thuận = chuẩn SSI),
    KHÔNG dùng volume_adjust của ohcl (chỉ khớp lệnh, thiếu thỏa thuận).
    Ticker cũng được chuẩn hóa đuôi sàn (.HM/.HN/.HNO) qua root-put luôn,
    tránh bị tách đôi định danh với ticker trong parquet lịch sử.
    """
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

    # ── Lấy Volume/Turnover thật (khớp lệnh + thỏa thuận) + Ticker đúng đuôi sàn ──
    df_root = _fetch_root_put_eod(today_str)
    if not df_root.empty:
        # Ticker gốc trong df_eod chưa có đuôi sàn (Wifeed ohcl trả "MBB" trần)
        # -> strip mọi đuôi cũ nếu có, rồi map sang bản root-put (đã có đuôi đúng)
        df_eod["_base_ticker"] = df_eod["Ticker"].astype(str).str.upper().str.strip()
        df_root["_base_ticker"] = df_root["Ticker"].str.replace(r'\.(HM|HN|HNO)$', '', regex=True)

        vol_map    = df_root.set_index("_base_ticker")["Volume"].to_dict()
        turn_map   = df_root.set_index("_base_ticker")["Turnover"].to_dict()
        ticker_map = df_root.set_index("_base_ticker")["Ticker"].to_dict()

        n_matched = df_eod["_base_ticker"].isin(ticker_map).sum()
        df_eod["Volume"]   = df_eod["_base_ticker"].map(vol_map).fillna(df_eod["Volume"])
        df_eod["Turnover"] = df_eod["_base_ticker"].map(turn_map).fillna(df_eod.get("Turnover", 0))
        df_eod["Ticker"]   = df_eod["_base_ticker"].map(ticker_map).fillna(df_eod["Ticker"])
        df_eod = df_eod.drop(columns=["_base_ticker"])

        logger.info(
            f"[Wifeed] Đã override Volume/Turnover thật từ root-put: "
            f"{n_matched}/{len(df_eod)} mã khớp"
        )
    else:
        logger.warning(
            "[Wifeed] root-put EOD trống — giữ Volume từ ohcl (CHỈ khớp lệnh, "
            "thiếu thỏa thuận) và Ticker KHÔNG có đuôi sàn (có thể gây lệch định danh)"
        )

    with _cache_lock:
        try:
            if os.path.exists(_PRICE_PATH):
                df_existing = pd.read_parquet(_PRICE_PATH)

                if "Exchange" in df_existing.columns:
                    exchange_map = (
                        df_existing[["Ticker", "Exchange"]]
                        .drop_duplicates("Ticker")
                        .set_index("Ticker")["Exchange"]
                        .to_dict()
                    )
                    df_eod["Exchange"] = df_eod["Ticker"].map(exchange_map).fillna("")
                    logger.info(
                        f"[Wifeed] Gắn Exchange cho df_eod: "
                        f"{df_eod['Exchange'].value_counts().to_dict()}"
                    )

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
            added = len(df_combined) - (len(df_existing) if os.path.exists(_PRICE_PATH) else 0)
            logger.info(
                f"[Wifeed] EOD appended: +{max(added,0):,} dòng mới | "
                f"Tổng: {len(df_combined):,} | ngày {today_str}"
            )

            _eod_appended = True
            _eod_date     = today_str

            try:
                import src.backend.data_loader as _dl
                _dl._MARKET_CACHE["data"] = None
                _dl._MARKET_CACHE["ts"]   = 0.0
                logger.info("[Wifeed] Market cache cleared — giá mới sẽ load khi screener refresh tiếp theo")
            except Exception as e:
                logger.warning(f"[Wifeed] Lỗi clear cache: {e}")

        except Exception as e:
            logger.error(f"[Wifeed] Lỗi append EOD: {e}", exc_info=True)

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

# SAU:
def _fetch_job() -> None:
    now_t = _now_vn().time()
    if now_t > _EOD_CUTOFF:
        logger.info(f"[Wifeed] Đã qua {_EOD_CUTOFF} — dừng scheduler")
        _stop_scheduler()
        return
    if not _is_trading_time():
        logger.debug(f"[Wifeed] Ngoài giờ GD ({_now_vn().strftime('%H:%M')}), bỏ qua")
        return



    df_stocks, df_all = _fetch_wifeed()
    if df_stocks.empty:
        return
    df_filtered = _filter_known_tickers(df_stocks)
    _save_realtime_cache(df_filtered, df_all)   # ← thêm df_all
    if _is_eod_time():
        _append_eod_to_parquet(df_filtered)
        _append_index_to_parquet(df_all)   # ← thêm dòng này


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
    def _startup_fetch():
        import datetime as dt
        today_vn = _now_vn().date()
        now_t = _now_vn().time()

        # 1. Kiểm tra ngày giao dịch (Thứ 2 - Thứ 6)
        is_trading_day = today_vn.weekday() < 5  # 0: Mon, 4: Fri

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

        # 3. Logic Backfill bằng SSI/VNDirect (gọi từ daily_updater)
        if last_date:
            days_missing = (today_vn - last_date).days
            
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
                needs_wifeed_eod = True # Chênh 1 ngày thì chỉ cần gọi EOD của Wifeed là đủ
        else:
            needs_wifeed_eod = True # File chưa tồn tại, bắt buộc lấy

        # 4. Logic lấy data Wifeed "Hôm nay"
        # Điều kiện lấy EOD Wifeed: 
        # Cần lấy EOD VÀ là ngày GD VÀ đã qua 15:00 VÀ hôm nay chưa có data
        append_today_eod = needs_wifeed_eod and is_trading_day and (now_t >= _EOD_CONFIRM) and (last_date != today_vn)

        # Điều kiện tạo realtime_cache: Đang trong giờ giao dịch (để Screener load)
        needs_realtime_cache = is_trading_day and (_TRADING_START <= now_t <= _EOD_CUTOFF)

        if append_today_eod or needs_realtime_cache:
            logger.info(f"[Wifeed] Chạy startup fetch. Append EOD: {append_today_eod}, Build Cache: {needs_realtime_cache}")
            df_stocks, df_all = _fetch_wifeed()

            if not df_stocks.empty:
                df_stocks = _filter_known_tickers(df_stocks)
                _save_realtime_cache(df_stocks, df_all)

                if append_today_eod:
                    _append_eod_to_parquet(df_stocks)
                    _append_index_to_parquet(df_all)
                    logger.info("[Wifeed] Startup fetch: Đã append EOD hôm nay (Wifeed) vào parquet.")
        else:
            logger.info("[Wifeed] Dữ liệu lịch sử đã Up-to-date hoặc ngoài giờ GD, bỏ qua Wifeed EOD.")

    # Đẩy toàn bộ quá trình (kể cả loop 1500 mã của SSI mất 5-8 phút) vào Background Thread 
    # => Web Dash App sẽ bật lên ngay lập tức không bị treo!
    threading.Thread(target=_startup_fetch, daemon=True, name="wifeed-startup").start()

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