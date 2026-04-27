"""
daily_updater.py — VSS Smart Screener (SSI + VNDirect Fallback Version)
═══════════════════════════════════════════════════════════════════════════════
Script ETL độc lập — KHÔNG liên quan đến Dash Web App.
Chạy như Cronjob lúc 15:15 sau ATC, ghi đè Parquet.

PIPELINE:
  1. Load danh sách ticker từ market_prices.parquet 
  2. Sequential download giá lịch sử (SSI làm nguồn chính, VNDirect dự phòng)
  3. Download index VNINDEX
  4. Ghi đè market_prices.parquet + index.parquet
  5. Trigger rebuild snapshot_cache.parquet
═══════════════════════════════════════════════════════════════════════════════
"""

import os
import sys
import time
import logging
import argparse
import warnings
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import requests

warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning)

# ─────────────────────────────────────────────────────────────────────────────
# LOGGING & PATHS
# ─────────────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("daily_updater")

BASE_DIR       = Path(__file__).parent
PROCESSED_DIR  = BASE_DIR / "data" / "processed"
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

PRICES_PARQUET   = PROCESSED_DIR / "market_prices.parquet"
INDEX_PARQUET    = PROCESSED_DIR / "index.parquet"
SNAPSHOT_PARQUET = PROCESSED_DIR / "snapshot_cache.parquet"

# ─────────────────────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────────────────────
# Số ngày lịch sử cần tải từ API mỗi lần chạy (khoảng 20 ngày để bao trọn từ 11/04/2026)
# Lưu ý: Nên để dư ra vài ngày (ví dụ 30) làm vùng đệm, code merge sẽ tự động xử lý phần dư.
HISTORY_DAYS = 60   

API_SLEEP    = 0.45 # Trễ 450ms giữa các request để giảm nguy cơ bị chặn IP (SSI có thể chặn nếu quá nhanh)

INDEX_SYMBOL = "^VNINDEX"
INDEX_COL    = "JCI_Close"


# ═════════════════════════════════════════════════════════════════════════════
# PHẦN 1: LẤY DANH SÁCH TICKER
# ═════════════════════════════════════════════════════════════════════════════
def get_ticker_list_from_parquet() -> pd.DataFrame:
    if not PRICES_PARQUET.exists():
        logger.error(f"Không tìm thấy {PRICES_PARQUET}.")
        return pd.DataFrame()

    logger.info("Đang đọc danh sách ticker từ market_prices.parquet...")
    df = pd.read_parquet(PRICES_PARQUET)

    if "Ticker" not in df.columns:
        return pd.DataFrame()

    # Sửa lỗi Duplicate Ticker column ở bản cũ
    meta_cols = ["Ticker"] + [
        c for c in df.columns
        if c not in ["Ticker", "Date", "Price Open", "Price High", "Price Low",
                     "Price Close", "Volume", "Adj Close"]
    ]
    df_meta = df[meta_cols].drop_duplicates(subset=["Ticker"]).reset_index(drop=True)
    logger.info(f"Tìm thấy {len(df_meta):,} ticker trong Parquet.")
    return df_meta

def clean_symbol(ticker: str) -> str:
    """Cắt bỏ mọi hậu tố sau dấu chấm (.VN, .HM, .HNO) để khớp với API nội địa"""
    # 1. Chuyển thành chuỗi và viết hoa
    t = str(ticker).strip().upper()
    
    # 2. Bỏ dấu ^ (dành cho ^VNINDEX)
    t = t.replace("^", "")
    
    # 3. Cắt chuỗi tại dấu chấm và chỉ lấy phần đầu tiên (VD: "CHP.HM" -> "CHP")
    t = t.split('.')[0]
    
    return t


# ═════════════════════════════════════════════════════════════════════════════
# PHẦN 2: CORE ENGINE - ROBUST API FETCHERS
# ═════════════════════════════════════════════════════════════════════════════

def fetch_ssi(symbol: str, start_dt: datetime, end_dt: datetime) -> pd.DataFrame:
    """Nguồn chính: SSI iBoard API"""
    url = "https://iboard-api.ssi.com.vn/statistics/company/ssmi/stock-info"
    params = {
        "symbol": symbol,
        "page": 1,
        "pageSize": 5000, # Đủ cho 5-10 năm lịch sử
        "fromDate": start_dt.strftime("%d/%m/%Y"),
        "toDate": end_dt.strftime("%d/%m/%Y")
    }
    headers = {
        "Accept": "application/json",
        "Connection": "keep-alive",
        "Origin": "https://iboard.ssi.com.vn",
        "Referer": "https://iboard.ssi.com.vn/",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    resp = requests.get(url, params=params, headers=headers, timeout=4)
    if resp.status_code == 200:
        data = resp.json()
        if data.get("code") == "SUCCESS" and data.get("data"):
            df = pd.DataFrame(data["data"])
            df = df[['tradingDate', 'open', 'high', 'low', 'close', 'volume']]
            df.columns = ['Date', 'Price Open', 'Price High', 'Price Low', 'Price Close', 'Volume']
            df['Date'] = pd.to_datetime(df['Date'], format="%d/%m/%Y")
            for col in ['Price Open', 'Price High', 'Price Low', 'Price Close', 'Volume']:
                df[col] = pd.to_numeric(df[col], errors='coerce')
            return df
    return pd.DataFrame()

def fetch_vndirect(symbol: str, start_dt: datetime, end_dt: datetime) -> pd.DataFrame:
    """Nguồn dự phòng: VNDirect Open API"""
    url = "https://finfo-api.vndirect.com.vn/v4/stock_prices"
    q_str = f"code:{symbol}~date:gte:{start_dt.strftime('%Y-%m-%d')}~date:lte:{end_dt.strftime('%Y-%m-%d')}"
    params = {"sort": "date", "q": q_str, "size": 5000}
    headers = {"User-Agent": "Mozilla/5.0"}

    resp = requests.get(url, params=params, headers=headers, timeout=4)
    if resp.status_code == 200:
        data = resp.json().get("data", [])
        if data:
            df = pd.DataFrame(data)
            df = df[['date', 'adOpen', 'adHigh', 'adLow', 'adClose', 'nmVolume']]
            df.columns = ['Date', 'Price Open', 'Price High', 'Price Low', 'Price Close', 'Volume']
            df['Date'] = pd.to_datetime(df['Date'])
            for col in ['Price Open', 'Price High', 'Price Low', 'Price Close']:
                df[col] = pd.to_numeric(df[col], errors='coerce') * 1000 # Cân bằng đơn vị giá
            df['Volume'] = pd.to_numeric(df['Volume'], errors='coerce')
            return df
    return pd.DataFrame()

def get_market_data_robust(original_ticker: str, start_dt: datetime, end_dt: datetime) -> pd.DataFrame:
    """Hệ thống Fallback tự động - Khớp nối tên API và tên Parquet"""
    
    # 1. Tạo "mã sạch" (bỏ .HM, .HNO, ^) để máy chủ SSI/VNDirect hiểu được
    clean_sym = clean_symbol(original_ticker)
    
    try:
        # 2. Gọi API bằng MÃ SẠCH
        df = fetch_ssi(clean_sym, start_dt, end_dt)
        if not df.empty:
            # 3. QUAN TRỌNG: Gán lại MÃ GỐC vào cột Ticker để Parquet merge chuẩn xác
            df['Ticker'] = original_ticker 
            return df.sort_values('Date').reset_index(drop=True)
            
        # Nếu SSI rỗng, lùi về VNDirect
        df_vnd = fetch_vndirect(clean_sym, start_dt, end_dt)
        if not df_vnd.empty:
            # QUAN TRỌNG: Gán lại MÃ GỐC 
            df_vnd['Ticker'] = original_ticker 
            return df_vnd.sort_values('Date').reset_index(drop=True)
            
    except Exception as e:
        logger.debug(f"Lỗi fetch mã {original_ticker}: {e}")
        pass
        
    return pd.DataFrame()


def download_all_prices_sequential(tickers: list[str], days: int = HISTORY_DAYS) -> pd.DataFrame:
    """Tải tuần tự toàn bộ thị trường bằng API nội địa"""
    end_date   = datetime.today()
    start_date = end_date - timedelta(days=days)
    total = len(tickers)
    
    logger.info(f"Bắt đầu tải tuần tự {total:,} mã (SSI -> Fallback VNDirect)")
    logger.info(f"Khoảng thời gian: {start_date.date()} → {end_date.date()}")

    all_dfs = []
    success = 0
    t_start = time.time()

    for i, ticker in enumerate(tickers):
        # Bỏ cái if % 50 đi, in trực tiếp tiến trình từng mã
        print(f"[{i+1}/{total}] Đang tải {ticker:<8}...", end=" ", flush=True)
        
        try:
            df_t = get_market_data_robust(ticker, start_date, end_date)
            
            if not df_t.empty:
                all_dfs.append(df_t)
                success += 1
                print(f"✅ Xong ({len(df_t)} dòng)")
            else:
                print("❌ Trống/Bị chặn")
                
        except Exception as e:
             print(f"⚠️ Lỗi: {e}")
            
        time.sleep(API_SLEEP) # Trễ 0.5s giữa các mã

    elapsed = time.time() - t_start
    logger.info(f"Download xong: {success:,}/{total:,} mã thành công | Thời gian: {elapsed:.1f}s")

    if not all_dfs:
        return pd.DataFrame()

    df_final = pd.concat(all_dfs, ignore_index=True)
    return df_final.dropna(subset=["Date", "Price Close"]).drop_duplicates(subset=["Date", "Ticker"])


# ═════════════════════════════════════════════════════════════════════════════
# PHẦN 3: DOWNLOAD INDEX (^VNINDEX)
# ═════════════════════════════════════════════════════════════════════════════
def download_index(symbol: str = INDEX_SYMBOL, days: int = HISTORY_DAYS) -> pd.DataFrame:
    end_date   = datetime.today()
    start_date = end_date - timedelta(days=days)

    logger.info(f"Downloading index {symbol}...")
    df_idx = get_market_data_robust(symbol, start_date, end_date)
    
    if df_idx.empty:
        logger.warning(f"Không có dữ liệu index {symbol}")
        return pd.DataFrame()

    # Chuẩn hóa format Index cho VSS
    df_idx = df_idx.rename(columns={"Price Close": INDEX_COL, "Volume": "JCI_Volume"})
    df_idx = df_idx[["Date", INDEX_COL, "JCI_Volume"]]
    
    logger.info(f"  ✓ Index {symbol}: {len(df_idx):,} ngày")
    return df_idx


# ═════════════════════════════════════════════════════════════════════════════
# PHẦN 4: MERGE PARQUET VÀ SNAPSHOT
# ═════════════════════════════════════════════════════════════════════════════
def merge_prices_into_parquet(df_new: pd.DataFrame, df_meta: pd.DataFrame) -> pd.DataFrame:
    if PRICES_PARQUET.exists():
        df_old = pd.read_parquet(PRICES_PARQUET)
        df_old["Date"] = pd.to_datetime(df_old["Date"]).dt.tz_localize(None)
        min_new = df_new["Date"].min() if not df_new.empty else pd.Timestamp.max
        df_old_hist = df_old[df_old["Date"] < min_new]
    else:
        df_old_hist = pd.DataFrame()

    frames = [f for f in [df_old_hist, df_new] if not f.empty]
    if not frames: return pd.DataFrame()
    df_merged = pd.concat(frames, ignore_index=True)

    if not df_meta.empty:
        price_cols = {"Date", "Price Open", "Price High", "Price Low", "Price Close", "Volume"}
        meta_cols  = [c for c in df_meta.columns if c not in price_cols or c == "Ticker"]
        old_meta = [c for c in meta_cols if c in df_merged.columns and c != "Ticker"]
        if old_meta: df_merged = df_merged.drop(columns=old_meta)
        df_merged = df_merged.merge(df_meta[meta_cols], on="Ticker", how="left")

    return df_merged.drop_duplicates(subset=["Date", "Ticker"], keep="last").sort_values(["Ticker", "Date"]).reset_index(drop=True)

def merge_index_into_parquet(df_new_idx: pd.DataFrame) -> pd.DataFrame:
    if INDEX_PARQUET.exists():
        df_old = pd.read_parquet(INDEX_PARQUET)
        df_old["Date"] = pd.to_datetime(df_old["Date"]).dt.tz_localize(None)
        min_new = df_new_idx["Date"].min() if not df_new_idx.empty else pd.Timestamp.max
        df_old_hist = df_old[df_old["Date"] < min_new]
    else:
        df_old_hist = pd.DataFrame()

    frames = [f for f in [df_old_hist, df_new_idx] if not f.empty]
    if not frames: return pd.DataFrame()
    return pd.concat(frames, ignore_index=True).drop_duplicates(subset=["Date"], keep="last").sort_values("Date").reset_index(drop=True)

def invalidate_snapshot_cache():
    if SNAPSHOT_PARQUET.exists():
        SNAPSHOT_PARQUET.unlink()
        logger.info(f"✓ Đã xóa snapshot cache")

def trigger_snapshot_rebuild():
    logger.info("Đang rebuild snapshot_cache.parquet...")
    try:
        sys.path.insert(0, str(BASE_DIR))
        import src.backend.data_loader as dl
        with dl._snapshot_lock:
            dl._snapshot_df = None
        df_snap = dl.get_snapshot_df()
        if df_snap is not None and not df_snap.empty:
            logger.info(f"✓ Snapshot rebuilt: {len(df_snap):,} mã")
    except Exception as e:
        logger.error(f"Lỗi rebuild snapshot: {e}")


# ═════════════════════════════════════════════════════════════════════════════
# PHẦN 5: MAIN PIPELINE
# ═════════════════════════════════════════════════════════════════════════════
def run_update(rebuild_snapshot: bool = False) -> bool:
    t0 = time.time()
    logger.info("=" * 70)
    logger.info("VSS DAILY UPDATER (SSI/VND API) — BẮT ĐẦU")
    logger.info("=" * 70)

    df_meta = get_ticker_list_from_parquet()
    if df_meta.empty: return False

    tickers = df_meta["Ticker"].tolist()
    
    logger.info("\n─── BƯỚC 2: DOWNLOAD GIÁ CỔ PHIẾU ───")
    df_new_prices = download_all_prices_sequential(tickers, days=HISTORY_DAYS)

    logger.info("\n─── BƯỚC 3: DOWNLOAD INDEX ───")
    df_new_index = download_index(symbol=INDEX_SYMBOL, days=HISTORY_DAYS)

    logger.info("\n─── BƯỚC 4: MERGE & GHI PARQUET ───")
    df_prices_final = merge_prices_into_parquet(df_new_prices, df_meta)
    if not df_prices_final.empty:
        if PRICES_PARQUET.exists(): PRICES_PARQUET.rename(PRICES_PARQUET.with_suffix(".bak.parquet"))
        df_prices_final.to_parquet(PRICES_PARQUET, index=False)
        logger.info(f"  ✓ Ghi market_prices.parquet: {len(df_prices_final):,} dòng")

    if not df_new_index.empty:
        df_index_final = merge_index_into_parquet(df_new_index)
        if not df_index_final.empty:
            if INDEX_PARQUET.exists(): INDEX_PARQUET.rename(INDEX_PARQUET.with_suffix(".bak.parquet"))
            df_index_final.to_parquet(INDEX_PARQUET, index=False)
            logger.info(f"  ✓ Ghi index.parquet: {len(df_index_final):,} dòng")

    logger.info("\n─── BƯỚC 5: SNAPSHOT CACHE ───")
    if rebuild_snapshot: trigger_snapshot_rebuild()
    else: invalidate_snapshot_cache()

    logger.info("=" * 70)
    logger.info(f"✅ HOÀN TẤT — Tổng thời gian: {time.time() - t0:.1f}s")
    logger.info("=" * 70)
    return True

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--rebuild-snapshot", action="store_true")
    args = parser.parse_args()
    success = run_update(rebuild_snapshot=args.rebuild_snapshot)
    sys.exit(0 if success else 1)