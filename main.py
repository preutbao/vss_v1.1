# main.py — VSS Smart Screener v1.1 (updated: IPS onboarding page)
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
from dash import dcc, Input, Output, no_update
from dotenv import load_dotenv
load_dotenv()

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# BƯỚC 0: KIỂM TRA & TỰ ĐỘNG CHUYỂN ĐỔI PARQUET NẾU CẦN
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
    return [
        fname for fname in _REQUIRED_PARQUETS
        if not os.path.exists(os.path.join(PROCESSED_DIR, fname))
    ]


def _ensure_parquets():
    missing = _check_parquets()
    if not missing:
        logger.info("✅ Đủ 4 file Parquet — bỏ qua bước chuyển đổi.")
        return

    logger.warning(f"⚠️  Thiếu {len(missing)} file Parquet: {missing}")

    if not os.path.exists(RAW_DIR) or not os.listdir(RAW_DIR):
        logger.error(
            "❌ Thư mục data/raw/ rỗng hoặc không tồn tại. "
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
    logger.info("=" * 60)

    os.makedirs(PROCESSED_DIR, exist_ok=True)

    import subprocess
    result = subprocess.run(
        [sys.executable, convert_script],
        cwd=BASE_DIR,
        capture_output=False,
        text=True,
    )

    if result.returncode != 0:
        logger.error(f"❌ convert_to_parquet.py lỗi (code {result.returncode})")
    else:
        still_missing = _check_parquets()
        if still_missing:
            logger.warning(f"⚠️  Vẫn còn thiếu: {still_missing}")
        else:
            logger.info("✅ Chuyển đổi hoàn tất.")


_ensure_parquets()


# ─────────────────────────────────────────────────────────────────────────────
# IMPORT APP
# ─────────────────────────────────────────────────────────────────────────────
from src.app_instance import app

# ─────────────────────────────────────────────────────────────────────────────
# IMPORT CALLBACKS
# ─────────────────────────────────────────────────────────────────────────────
import src.callbacks.auth_callbacks
import src.callbacks.column_callbacks
import src.callbacks.screener_callbacks
import src.callbacks.filter_interaction_callbacks
import src.callbacks.reset_callback
import src.callbacks.detail_tabs_callbacks
import src.callbacks.mode_callbacks
import src.callbacks.home_callbacks
import src.utils.chart_callbacks
import src.callbacks.chatbot_callbacks
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
import src.callbacks.investor_profile_callbacks
import src.callbacks.tab_dot_callbacks

# ─────────────────────────────────────────────────────────────────────────────
# BUILD LAYOUT — hai section: onboarding ↔ main app
# ─────────────────────────────────────────────────────────────────────────────
from dash import html, dcc
from src.pages import screener, onboarding
from src.components.header import create_header, create_topbar, create_banner
from src.callbacks.chatbot_callbacks import create_chatbot_layout


app.layout = html.Div(
    style={"margin": "0", "padding": "0", "overflowX": "hidden"},
    children=[
        # ── 0. THANH TOPBAR LUÔN HIỂN THỊ Ở MỌI TRANG ─────────────────────
        create_topbar(),

        # ── 1. GLOBAL STORES ──────────────────────────────────────────────
        dcc.Store(id="trading-mode-store",   storage_type="session",  data="investing"),
        dcc.Store(id="tour-selected-mode",   storage_type="memory",   data="investing"),
        dcc.Store(id="hint-shown-store",     storage_type="memory",   data=False),
        dcc.Store(id="tour-step-store",      data=1),

        # LƯU Ý QUAN TRỌNG: Nếu bạn đã khai báo 2 Store này ở file sidebar.py, 
        # thì bạn PHẢI XÓA CHÚNG Ở ĐÂY (hoặc xóa ở sidebar.py). Chỉ giữ lại 1 nơi duy nhất!
        dcc.Store(id="investor-profile-store", storage_type="local",  data=None),
        dcc.Store(id="profile-setup-done",     storage_type="local",  data=False),

        # ── 2. ONBOARDING PAGE ────────────────────────────────────────────
        # Hiển thị khi profile-setup-done = False (lần đầu vào / chưa setup)
        html.Div(
            id="onboarding-page",
            children=[onboarding.layout],
            # style mặc định: hiện — callback sẽ ẩn đi sau khi setup xong
        ),

        # ── 3. MAIN APP ───────────────────────────────────────────────────
        # Ẩn cho đến khi profile-setup-done = True
        html.Div(
            id="main-app-page",
            style={"display": "none"},
            children=[
                # THAY create_header() BẰNG create_banner() ĐỂ KHÔNG BỊ TRÙNG TOPBAR
                create_banner(), 
                html.Div(
                    id="screener-section",
                    children=[screener.layout],
                ),
                create_chatbot_layout(),
            ],
        ),
    ],
)


# ─────────────────────────────────────────────────────────────────────────────
# CALLBACK: Chuyển trang dựa trên profile-setup-done
# ─────────────────────────────────────────────────────────────────────────────
@app.callback(
    Output("onboarding-page", "style"),
    Output("main-app-page",   "style"),
    Input("profile-setup-done", "data"),
)
def toggle_pages(setup_done):
    """
    - setup_done = False (hoặc None) → hiển thị onboarding, ẩn main app
    - setup_done = True              → ẩn onboarding, hiển thị main app
    """
    if setup_done:
        return {"display": "none"}, {"display": "block"}
    return {"display": "block"}, {"display": "none"}


# ─────────────────────────────────────────────────────────────────────────────
# CALLBACK: Nút "Hồ sơ" trong header → quay về onboarding để chỉnh sửa
# ─────────────────────────────────────────────────────────────────────────────
@app.callback(
    Output("profile-setup-done", "data", allow_duplicate=True),
    Input("btn-investor-profile", "n_clicks"),
    prevent_initial_call=True,
)
def reopen_onboarding(n_clicks):
    """
    Khi user click nút "Hồ sơ" ở header → reset profile-setup-done về False
    để toggle_pages() hiển thị lại trang onboarding.
    """
    if n_clicks:
        return False
    return no_update


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
    logger.info("🚀 VSS SMART SCREENER — Pre-loading data...")
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
# WSGI entrypoint
# ─────────────────────────────────────────────────────────────────────────────
server = app.server

if __name__ == "__main__":
    port  = int(os.environ.get("PORT", 8050))
    debug = False

    logger.info(f"🌐 Server: http://127.0.0.1:{port}  |  debug={debug}")

    app.run(
        debug=debug,
        host="0.0.0.0",
        port=port,
        dev_tools_ui=False,
        dev_tools_hot_reload=False,
    )