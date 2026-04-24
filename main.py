# main.py — VSS Smart Screener v1.1
# ─────────────────────────────────────────────────────────────────────────────
# Entry point cho cả hai môi trường:
#   Local dev  :  python main.py
#   Production :  gunicorn --bind 0.0.0.0:7860 --workers 1 --worker-class sync
#                          --timeout 300 main:server
# ─────────────────────────────────────────────────────────────────────────────

import sys
import os
import logging
import dash_bootstrap_components as dbc
from dash import dcc

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# BƯỚC 0: KIỂM TRA & TỰ ĐỘNG CHUYỂN ĐỔI PARQUET NẾU
# ─────────────────────────────────────────────────────────────────────────────

BASE_DIR      = os.path.dirname(os.path.abspath(__file__))
PROCESSED_DIR = os.path.join(BASE_DIR, "data", "processed")
RAW_DIR       = os.path.join(BASE_DIR, "data", "raw")

_REQUIRED_PARQUETS = {
    "market_prices.parquet":       "Giá lịch sử",
    "financial_yearly.parquet":    "BCTC năm",
    "financial_quarterly.parquet": "BCTC quý",
    "index.parquet":               "Chỉ số JCI",
}


def _check_parquets():
    """Trả về danh sách tên file Parquet còn thiếu."""
    return [
        fname for fname in _REQUIRED_PARQUETS
        if not os.path.exists(os.path.join(PROCESSED_DIR, fname))
    ]


def _ensure_parquets():
    """
    Kiểm tra 4 file Parquet bắt buộc. Nếu thiếu bất kỳ file nào,
    tự động chạy convert_to_parquet.py để chuyển đổi từ raw data.
    """
    missing = _check_parquets()
    if not missing:
        logger.info("✅ Đủ 4 file Parquet — bỏ qua bước chuyển đổi.")
        return

    logger.warning(f"⚠️  Thiếu {len(missing)} file Parquet: {missing}")

    if not os.path.exists(RAW_DIR) or not os.listdir(RAW_DIR):
        logger.error(
            "❌ Thư mục data/raw/ rỗng hoặc không tồn tại. "
            "Không thể chạy convert_to_parquet.py. "
            "Hãy upload dữ liệu raw trước khi deploy."
        )
        return

    convert_script = os.path.join(BASE_DIR, "convert_to_parquet.py")
    if not os.path.exists(convert_script):
        logger.error(f"❌ Không tìm thấy {convert_script}")
        return

    logger.info("=" * 60)
    logger.info("🔄 Đang chạy convert_to_parquet.py ...")
    logger.info(f"   Thiếu: {[_REQUIRED_PARQUETS[f] for f in missing]}")
    logger.info("   (Quá trình này có thể mất 5-15 phút lần đầu)")
    logger.info("=" * 60)

    os.makedirs(PROCESSED_DIR, exist_ok=True)

    import subprocess
    result = subprocess.run(
        [sys.executable, convert_script],
        cwd=BASE_DIR,
        capture_output=False,   # in thẳng ra stdout/stderr để thấy progress
        text=True,
    )

    if result.returncode != 0:
        logger.error(f"❌ convert_to_parquet.py kết thúc với lỗi (code {result.returncode})")
    else:
        still_missing = _check_parquets()
        if still_missing:
            logger.warning(f"⚠️  Vẫn còn thiếu sau khi convert: {still_missing}")
        else:
            logger.info("✅ Chuyển đổi hoàn tất — đủ 4 file Parquet.")


# Chạy kiểm tra ngay khi module được import (trước cả Dash app)
_ensure_parquets()


# ─────────────────────────────────────────────────────────────────────────────
# IMPORT APP — phải sau _ensure_parquets() để data sẵn sàng
# ─────────────────────────────────────────────────────────────────────────────
from src.app_instance import app

# ─────────────────────────────────────────────────────────────────────────────
# IMPORT TẤT CẢ CALLBACKS (thứ tự quan trọng)
# ─────────────────────────────────────────────────────────────────────────────
import src.callbacks.column_callbacks
import src.callbacks.screener_callbacks
import src.callbacks.filter_interaction_callbacks
import src.callbacks.reset_callback
import src.callbacks.detail_tabs_callbacks
import src.callbacks.home_callbacks
import src.utils.chart_callbacks
import src.callbacks.strategy_callbacks
import src.callbacks.ticker_search_callbacks
import src.callbacks.pdf_export_callback
import src.callbacks.saved_filters_callbacks
import src.callbacks.wizard_callbacks
import src.callbacks.financial_charts_callbacks
import src.callbacks.heatmap_callbacks
import src.callbacks.compare_callbacks
import src.callbacks.portfolio_callbacks
import src.callbacks.alert_callbacks
import src.callbacks.score_breakdown_callbacks

# ─────────────────────────────────────────────────────────────────────────────
# BUILD LAYOUT (Đã cập nhật giao diện mới)
# ─────────────────────────────────────────────────────────────────────────────
from dash import html
from src.pages import screener
from src.components.header import create_header

app.layout = html.Div(
    style={"margin": "0", "padding": "0", "overflowX": "hidden"},
    children=[
        # ── Header cố định + Hero Banner full màn hình ──
        create_header(),

        # ── Screener (cuộn đến khi click "Khám phá ngay") ──
        html.Div(
            id="screener-section",
            children=[screener.layout],
        ),
    ],
)

# ─────────────────────────────────────────────────────────────────────────────
# PRE-LOAD DATA
# ─────────────────────────────────────────────────────────────────────────────
from src.backend.data_loader import (
    load_market_data,
    load_financial_data,
    load_index_data,
    get_snapshot_df,
)


def preload_data():
    logger.info("=" * 60)
    logger.info("🚀 IDX SMART SCREENER — Pre-loading data...")
    logger.info("=" * 60)

    try:
        df_price = load_market_data()
        logger.info(f"✅ Giá: {len(df_price):,} dòng | {df_price['Ticker'].nunique()} mã")
    except Exception as e:
        logger.error(f"❌ Lỗi load giá: {e}")

    try:
        df_year = load_financial_data('yearly')
        logger.info(f"✅ BCTC năm: {len(df_year):,} dòng | {len(df_year.columns)} cột")
    except Exception as e:
        logger.error(f"❌ Lỗi load BCTC năm: {e}")

    try:
        df_index = load_index_data()
        logger.info(f"✅ Index: {len(df_index):,} dòng")
    except Exception as e:
        logger.error(f"❌ Lỗi load index: {e}")

    try:
        df_snap = get_snapshot_df()
        if df_snap is not None and not df_snap.empty:
            perf_cols = sorted(c for c in df_snap.columns if c.startswith("Perf_"))
            logger.info(f"✅ Snapshot: {len(df_snap)} mã | {len(df_snap.columns)} cột")
            logger.info(f"   Perf cols: {perf_cols}")
        else:
            logger.warning("⚠️ Snapshot rỗng!")
    except Exception as e:
        logger.error(f"❌ Lỗi build snapshot: {e}")

    logger.info("=" * 60)
    logger.info("✅ Pre-load xong — server sẵn sàng nhận request")
    logger.info("=" * 60)


preload_data()

# ─────────────────────────────────────────────────────────────────────────────
# WSGI entrypoint: gunicorn main:server
# ─────────────────────────────────────────────────────────────────────────────
server = app.server


# ─────────────────────────────────────────────────────────────────────────────
# LOCAL DEV & PRODUCTION MODE: python main.py test thử cho NCN coi
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    port  = int(os.environ.get("PORT", 8050))
    
    # BƯỚC 1: Gán cứng biến debug thành False 
    debug = False

    logger.info(f"🌐 Trạng thái máy chủ: http://127.0.0.1:{port}  |  debug={debug}")

    app.run(
        debug=debug,
        host="0.0.0.0",
        port=port,
        # BƯỚC 2: Tắt sạch mọi công cụ hỗ trợ của Dash để giải phóng tài nguyên
        dev_tools_ui=False,
        dev_tools_hot_reload=False, 
    )