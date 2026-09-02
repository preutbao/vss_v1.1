# main.py — FSS Smart Screener v1.1 (updated: IPS onboarding page)
# ─────────────────────────────────────────────────────────────────────────────
# Entry point cho cả hai môi trường:
#   Local dev  :  python main.py
#   Production :  gunicorn --bind 0.0.0.0:7860 --workers 1 --worker-class sync
#                          --timeout 300 main:server
# ─────────────────────────────────────────────────────────────────────────────
import sys
import os
import logging

# [FIX] logging.basicConfig() PHẢI chạy ĐẦU TIÊN, trước bất kỳ import/lời gọi
# nào có thể tự log (init_db, seed_demo_codes, start_alert_scheduler,
# start_wifeed_scheduler...). Nếu chưa có handler nào được cấu hình, Python
# dùng "handler of last resort" — ngưỡng mặc định là WARNING — nên mọi
# logger.info(...) gọi TRƯỚC khi basicConfig() chạy sẽ bị nuốt hoàn toàn,
# không in ra đâu cả, dù sau đó basicConfig() có set level=INFO đi nữa.
# Đây chính là lý do log "[Wifeed] ..." lúc khởi động (chạy đồng bộ bên
# trong start_wifeed_scheduler()) không hề xuất hiện — không phải do
# wifeed_updater.py sai logic.
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

import dash
import dash_bootstrap_components as dbc
from dash import dcc, Input, Output, no_update
from dotenv import load_dotenv
load_dotenv()

from src.backend.database import init_db, seed_demo_codes
init_db()
# Chỉ seed demo code khi KHÔNG phải production — đặt FSS_ENV=production
# trong .env/biến môi trường khi deploy thật để không lộ mã VIP demo
# (FSS-DEMO-2026, FSS-VIP-ALPHA...) trong database.
if os.environ.get("FSS_ENV", "development").lower() != "production":
    seed_demo_codes()

# AUDIT FIX (mục 9 - Alert Engine): khởi động backend scheduler để alert được
# đánh giá kể cả khi không có browser nào mở tab (xem src/backend/alert_scheduler.py).
# Bỏ qua khi FSS_ENV=test để không tạo background thread trong lúc chạy pytest/CI.
if os.environ.get("FSS_ENV", "development").lower() != "test":
    from src.backend.alert_scheduler import start_alert_scheduler
    start_alert_scheduler(interval_minutes=5)
    # Wifeed realtime price scheduler
    from src.backend.wifeed_updater import start_wifeed_scheduler
    start_wifeed_scheduler()

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


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
    "index.parquet":               "Chỉ số VNINDEX, VN100, VN30",
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
import src.callbacks.realtime_price_callbacks
import src.callbacks.hero_callbacks
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
import src.callbacks.ips_pdf_callback
import src.callbacks.tab_dot_callbacks
import src.callbacks.tplus_callbacks
import src.callbacks.margin_crisis_callbacks
import src.callbacks.screener_pdf_callback
import src.callbacks.psychology_callbacks

# ─────────────────────────────────────────────────────────────────────────────
# BUILD LAYOUT — hai section: onboarding ↔ main app
# ─────────────────────────────────────────────────────────────────────────────
from dash import Dash, html, dcc, Input, Output, State
from src.pages import screener, onboarding
from src.components.header import create_header, create_topbar, create_banner, create_market_overview, create_picks_and_pulse_section, create_header_content
from src.callbacks.chatbot_callbacks import create_chatbot_layout
from src.callbacks.portfolio_callbacks import portfolio_modal, portfolio_help_modal
from src.callbacks.margin_crisis_callbacks import crisis_modal, crisis_help_modal
from src.callbacks.compare_callbacks import compare_modal, compare_help_modal

app.layout = html.Div(
    style={"margin": "0", "padding": "0", "overflowX": "hidden"},
    children=[
        # ── 0. THANH TOPBAR LUÔN HIỂN THỊ Ở MỌI TRANG ─────────────────────
        # Bọc topbar vào một Div để dính chặt lên top
        html.Div(
            style={
                "position": "sticky", 
                "top": "0", 
                "zIndex": "1030",       # Đặt thấp để luôn nằm dưới Popup/Modal (Bootstrap chuẩn 1040+)
            },
            children=[create_topbar()]
        ),

        # ── 1. GLOBAL STORES ──────────────────────────────────────────────
        dcc.Store(id="trading-mode-store",   storage_type="session",  data="investing"),
        dcc.Store(id="tour-selected-mode",   storage_type="memory",   data="investing"),
        dcc.Store(id="hint-shown-store",     storage_type="memory",   data=False),
        dcc.Store(id="tour-step-store",      data=1),
        dcc.Store(id="psy-history-store", storage_type="local", data=[]), # **thêm dòng này**

        # LƯU Ý QUAN TRỌNG: Nếu bạn đã khai báo 2 Store này ở file sidebar.py, 
        # thì bạn PHẢI XÓA CHÚNG Ở ĐÂY (hoặc xóa ở sidebar.py). Chỉ giữ lại 1 nơi duy nhất!
        dcc.Store(id="investor-profile-store", storage_type="local",  data=None),
        dcc.Store(id="profile-setup-done",     storage_type="local",  data=True),

        dcc.Store(id="has-seen-tour", storage_type="local", data=False),
        dcc.Store(id="tour-active-step", storage_type="memory", data=None),

        # 🛠 THÊM DÒNG NÀY VÀO ĐỂ KHÔNG BỊ LỖI CALLBACK
        dcc.Store(id="tour-finish-trigger", data=False),

        # 🎨 THEME STORE — đồng bộ data-theme (light/dark) từ DOM xuống server.
        # Các callback Python (Tổng quan, Kỹ thuật, Biểu đồ tài chính...) đọc
        # State("theme-store", "data") để build màu Plotly/HTML đúng theme,
        # vì server không tự đọc được document.documentElement của browser.
        dcc.Store(id="theme-store", storage_type="local", data="dark"),
        dcc.Store(id="dummy-autosize-output", data=None),
        dcc.Store(id="dummy-vip-banner-output", data=None),

        # ===================================================================
        # 🟢 CHÈN CÁC MODAL ẨN VÀO ĐÂY (NẰM GIỮA STORES VÀ PAGES)
        # ===================================================================
        compare_help_modal,   # Bảng Hướng dẫn So sánh (Popup i)
        crisis_help_modal,    # Bảng Chi tiết Khủng hoảng Ký quỹ (Popup i)
        portfolio_help_modal, # Bảng Hướng dẫn (Popup i)
        # psychology_modal,     # Trạm Cứu Viện Tâm Lý (Rumor Check)

        # ── 2. ONBOARDING PAGE ────────────────────────────────────────────
        # Hiển thị khi profile-setup-done = False (lần đầu vào / chưa setup)
        html.Div(
            id="onboarding-page",
            children=[onboarding.layout],
            style={"opacity": "0", "transition": "opacity 0.15s ease", "marginTop": "-40px"},
        ),

        # ── 3. MAIN APP ───────────────────────────────────────────────────
        # Ẩn cho đến khi profile-setup-done = True
        html.Div(
            id="main-app-page",
            style={"opacity": "0", "transition": "opacity 0.15s ease"},
            children=[
                # THAY create_header() BẰNG create_banner() ĐỂ KHÔNG BỊ TRÙNG TOPBAR
                #create_banner(), 
                #create_market_overview(),  # <--- MÁ THÊM ĐÚNG DÒNG NÀY VÀO ĐÂY NÈ
                #create_picks_and_pulse_section(),  # [BƯỚC 3] Top Fin Picks + Market Pulse

                create_header_content(),  # nội dung Hero + Market Overview + Picks/Pulse + nền GIF
                
                # Tour Guide Overlay
                html.Div(id="tour-overlay-container", children=[
                    # Overlay tối
                    html.Div(id="tour-backdrop", style={
                        "position": "fixed", "inset": "0",
                        "zIndex": "10000", "pointerEvents": "none",
                    }),
                    # Tooltip box
                    html.Div(id="tour-tooltip", style={
                        "position": "fixed",
                        "zIndex": "10001",
                        "display": "none",
                        "width": "320px",
                    }, children=[
                        html.Div(id="tour-tooltip-inner"),
                    ]),
                ], style={"display": "none"}),
                html.Div(
                    id="screener-section",
                    children=[screener.layout],
                ),
                create_chatbot_layout(),
            ],
        ),
    ],
)

# THÊM ĐOẠN NÀY — chạy ngay khi browser load, không chờ server roundtrip
app.clientside_callback(
    """
    function(setup_done) {
        var onboard = document.getElementById('onboarding-page');
        var main    = document.getElementById('main-app-page');
        if (!onboard || !main) return window.dash_clientside.no_update;

        if (setup_done) {
            onboard.style.display  = 'none';
            onboard.style.opacity  = '0';
            main.style.display     = 'block';
            // Fade in mượt
            setTimeout(function() { main.style.opacity = '1'; }, 10);
        } else {
            main.style.display     = 'none';
            main.style.opacity     = '0';
            onboard.style.display  = 'block';
            onboard.style.marginTop = '-0px';   // ← thêm dòng này
            setTimeout(function() { onboard.style.opacity = '1'; }, 10);
        }
        return window.dash_clientside.no_update;
    }
    """,
    Output("onboarding-page", "id"),   # Output giả — không dùng giá trị trả về
    Input("profile-setup-done", "data"),
    prevent_initial_call=False,
)

app.clientside_callback(
    """
    function(rowData, columnDefs) {
        if (!rowData || rowData.length === 0) return window.dash_clientside.no_update;
        
        // Đợi AG Grid render xong rồi mới autosize
        setTimeout(function() {
            var gridDiv = document.getElementById('screener-table');
            if (!gridDiv) return;
            
            // Lấy AG Grid API instance từ Dash AG Grid
            var gridComp = gridDiv._dashprivate_agGridInstance;
            if (!gridComp) return;
            
            var api = gridComp.api;
            if (!api) return;
            
            // AutoSize tất cả cột theo nội dung cell
            api.autoSizeAllColumns(false);  // false = tính cả header
            
        }, 150);  // 150ms đủ để AG Grid render xong 1 page (20 rows)
        
        return window.dash_clientside.no_update;
    }
    """,
    Output("dummy-autosize-output", "data"),
    Input("screener-table", "rowData"),
    Input("screener-table", "columnDefs"),
    prevent_initial_call=False,
)

# ─────────────────────────────────────────────────────────────────────────────
# CALLBACK: Theme toggle (sáng/tối) — ghi data-theme lên <html> + đồng bộ
# xuống theme-store để các callback Python (biểu đồ, màu sắc...) dùng chung.
# THÊM VÀO ĐÂY vì mọi clientside_callback khác của app đều đăng ký qua
# app.clientside_callback (không phải clientside_callback rời từ module dash).
# ─────────────────────────────────────────────────────────────────────────────
app.clientside_callback(
    """
    function(isDark) {
        var theme = isDark ? 'dark' : 'light';
        document.documentElement.setAttribute('data-theme', theme);
        return theme;
    }
    """,
    Output("theme-store", "data"),
    Input("theme-switch-button", "value"),
    prevent_initial_call=False,
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
    _transition = "opacity 0.2s ease"
    if setup_done:
        return (
            {"display": "none",  "opacity": "0",  "transition": _transition},
            {"display": "block", "opacity": "1",  "transition": _transition},
        )
    return (
        {"display": "block", "opacity": "1",  "transition": _transition},  # ← thêm vào đây
        {"display": "none",  "opacity": "0",  "transition": _transition},
    )

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

# ============================================================
# CALLBACK JAVASCRIPT CHO FAQ ONBOARDING (FIXED)
# ============================================================
for i in range(1, 8):
    app.clientside_callback(
        f"""
        function(n_clicks) {{
            if (!n_clicks) return window.dash_clientside.no_update;
            
            var content = document.getElementById('onb-faq-content-{i}');   
            var icon = document.getElementById('onb-faq-icon-{i}');         
            
            if (content && icon) {{
                if (content.style.display === 'none' || content.style.display === '') {{
                    content.style.display = 'block';
                    icon.innerText = '×';
                    icon.style.color = '#3b82f6';
                }} else {{
                    content.style.display = 'none';
                    icon.innerText = '+';
                    icon.style.color = '#6b7280';
                }}
            }}
            
            return window.dash_clientside.no_update;
        }}
        """,
        Output(f"onb-faq-content-{i}", "id"),  
        Input(f"onb-faq-btn-{i}", "n_clicks"), 
        prevent_initial_call=True
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
    logger.info("🚀 FSS SMART SCREENER — Pre-loading data...")
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

# ============================================================
# [BƯỚC 4] CLIENTSIDE CALLBACKS CHO TOUR GUIDE
# ============================================================

# 1. TRIGGER TOUR GUIDE TỰ ĐỘNG (LẦN ĐẦU)
app.clientside_callback(
    """
    function(setup_done, has_seen) {
        // Chỉ chạy khi đã xong onboarding (setup_done) VÀ chưa từng xem tour (has_seen == false)
        if (!setup_done || has_seen === true) {
            return window.dash_clientside.no_update;
        }

        // Kích hoạt tour
        setTimeout(function() {
            if (window.FssTour) {
                window.FssTour.start();
            }
        }, 1500);

        // Trả về True để lưu vào dcc.Store(storage_type='local') 
        return true; 
    }
    """,
    Output("has-seen-tour", "data"),
    Input("profile-setup-done", "data"),
    State("has-seen-tour", "data"),
    prevent_initial_call=False,
)

# 2. LƯU TRẠNG THÁI HOÀN TẤT
app.clientside_callback(
    """
    function(n) {
        return true;
    }
    """,
    Output("has-seen-tour", "data", allow_duplicate=True),
    Input("tour-finish-trigger", "data"),
    prevent_initial_call=True,
)

# 3. KÍCH HOẠT THỦ CÔNG (KHI BẤM NÚT << HƯỚNG DẪN)
app.clientside_callback(
    """
    function(n_clicks) {
        if (n_clicks && window.FssTour) {
            window.FssTour.start();
        }
        return window.dash_clientside.no_update;
    }
    """,
    Output("btn-start-tour", "children"), # Output giả để Dash chấp nhận
    Input("btn-start-tour", "n_clicks"),
    prevent_initial_call=True,
)

app.clientside_callback(
    """
    function(n_clicks) {
        if (n_clicks && window.FssTour) {
            window.FssTour.start();
            var panel = document.getElementById('fss-notif-panel');
            if (panel) panel.style.display = 'none';   // đóng panel sau khi mở tour
        }
        return window.dash_clientside.no_update;
    }
    """,
    Output("notif-welcome-tour", "title"),   # output giả
    Input("notif-welcome-tour", "n_clicks"),
    prevent_initial_call=True,
)

# ── CONGRATS: bấm nút VIP → mở modal login ───────────────────────────────
app.clientside_callback(
    """
    function(n) {
        if (!n) return window.dash_clientside.no_update;
        return true;
    }
    """,
    Output("login-modal", "is_open", allow_duplicate=True),
    Input("ips-congrats-login-btn", "n_clicks"),
    prevent_initial_call=True,
)

app.clientside_callback(
    """
    function(rowData, authData) {
        var banner = document.getElementById('fss-grid-lock-banner');
        var txt    = document.getElementById('fss-grid-lock-text');
        if (!banner) return window.dash_clientside.no_update;

        var isVip  = !!(authData && authData.logged_in);
        var total  = rowData ? rowData.length : 0;
        var locked = rowData ? rowData.filter(function(r){ return r._locked; }).length : 0;

        if (!isVip && locked > 0) {
            banner.style.display = 'block';
            if (txt) txt.textContent = 'Đăng nhập VIP để xem toàn bộ ' + (3 + locked) + ' mã';
        } else {
            banner.style.display = 'none';
        }
        return window.dash_clientside.no_update;
    }
    """,
    Output("dummy-vip-banner-output", "data"),
    Input("screener-table", "rowData"),
    Input("auth-store", "data"),
    prevent_initial_call=False,
)

app.clientside_callback(
    """
    function(n) {
        if (!n) return window.dash_clientside.no_update;
        return true;
    }
    """,
    Output("login-modal", "is_open", allow_duplicate=True),
    Input("fss-banner-login-btn", "n_clicks"),
    prevent_initial_call=True,
)

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