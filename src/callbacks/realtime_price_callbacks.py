# src/callbacks/realtime_price_callbacks.py
"""
Realtime Price Callbacks
========================
Cập nhật giá Wifeed vào 2 vị trí:
  1. Bảng screener chính (Price Close, Price_Change_Pct, Volume)
  2. Giá hiện tại trong tab Tổng quan (khi modal đang mở)

Kèm blur overlay giống YouTube buffering trong thời gian fetch (~0.3s).

Architecture:
  - dcc.Interval(60s) → trigger server callback
  - Server đọc in-memory snapshot từ wifeed_updater (0ms latency)
  - Patch rowData của AG Grid (chỉ update 3 cột, không re-render toàn bộ)
  - Clientside callback xử lý blur/unblur để không tốn round-trip
"""

import datetime

from dash import Input, Output, State, no_update, clientside_callback, dcc, html
from src.app_instance import app
import logging
import time

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# LAYOUT COMPONENTS (import vào screener.py)
# ─────────────────────────────────────────────────────────────────────────────

def create_realtime_components():
    """
    Trả về list các component cần thêm vào layout screener:
      - dcc.Interval 60s trigger
      - dcc.Store lưu timestamp fetch gần nhất
      - Overlay blur div (CSS-based)
    """
    return [
        dcc.Interval(
            id="realtime-price-interval",
            interval=60_000,
            n_intervals=0,
            disabled=False,
        ),
        # Thêm 2 Store ẩn làm bia đỡ đạn cho clientside callback
        dcc.Store(id="dummy-blur-output"),
        dcc.Store(id="dummy-unblur-output"),
    ]


def create_screener_overlay():
    """
    Overlay blur cho bảng screener.
    Đặt position:absolute bao ngoài AG Grid container.
    """
    return html.Div(
        id="screener-blur-overlay",
        style={
            "position":        "absolute",
            "top":             "0",
            "left":            "0",
            "width":           "100%",
            "height":          "100%",
            "backgroundColor": "rgba(12,18,32,0.45)",
            "backdropFilter":  "blur(2px)",
            "zIndex":          "10",
            "display":         "none",      # ẩn mặc định
            "pointerEvents":   "none",
            "borderRadius":    "8px",
            "transition":      "opacity 0.15s ease",
        },
        children=[
            # Spinner nhỏ ở giữa
            html.Div([
                html.Div(className="wifeed-spinner"),
                html.Span(
                    "Đang cập nhật giá...",
                    style={
                        "fontSize":   "11px",
                        "color":      "#00d4ff",
                        "marginTop":  "8px",
                        "fontFamily": "'JetBrains Mono', monospace",
                        "letterSpacing": "0.05em",
                    }
                ),
            ], style={
                "display":        "flex",
                "flexDirection":  "column",
                "alignItems":     "center",
                "justifyContent": "center",
                "height":         "100%",
            }),
        ],
    )


def create_overview_overlay():
    """Overlay blur cho tab Tổng quan trong detail modal."""
    return html.Div(
        id="overview-blur-overlay",
        style={
            "position":        "absolute",
            "top":             "0",
            "left":            "0",
            "width":           "100%",
            "height":          "100%",
            "backgroundColor": "rgba(12,18,32,0.4)",
            "backdropFilter":  "blur(1.5px)",
            "zIndex":          "5",
            "display":         "none",
            "pointerEvents":   "none",
            "borderRadius":    "6px",
        },
    )


# ─────────────────────────────────────────────────────────────────────────────
# CSS cần thêm vào assets/style.css (hoặc assets/realtime.css)
# ─────────────────────────────────────────────────────────────────────────────
REALTIME_CSS = """
/* Wifeed realtime spinner */
.wifeed-spinner {
    width: 20px;
    height: 20px;
    border: 2px solid rgba(0,212,255,0.2);
    border-top-color: #00d4ff;
    border-radius: 50%;
    animation: wifeed-spin 0.7s linear infinite;
}
@keyframes wifeed-spin {
    to { transform: rotate(360deg); }
}

/* Container bao ngoài screener table cần position:relative */
#screener-table-wrapper {
    position: relative;
}

/* Container bao ngoài tab overview cần position:relative */
#tab-overview-content-wrapper {
    position: relative;
    min-height: 200px;
}
"""

def _patch_rows(current_row_data: list, snapshot: dict) -> list:
    """Patch Price Close / Volume / Price_Change_Pct từ realtime snapshot vào rowData."""
    new_row_data = []
    for row in current_row_data:
        rt = snapshot.get(row.get("Ticker", ""))
        if rt is None:
            new_row_data.append(row)
            continue
        new_row = dict(row)
        if rt.get("Price Close") is not None:
            new_row["Price Close"]      = rt["Price Close"]
        #if rt.get("Volume") is not None:
        #    new_row["Volume"]           = int(rt["Volume"])
        if rt.get("Price_Change_Pct") is not None:
            new_row["Price_Change_Pct"] = round(float(rt["Price_Change_Pct"]), 2)
        new_row_data.append(new_row)
    return new_row_data

# ─────────────────────────────────────────────────────────────────────────────
# CALLBACK: Blur / Unblur (clientside — 0 latency)
# ─────────────────────────────────────────────────────────────────────────────

# Khi interval fire → hiện blur ngay
clientside_callback(
    """
    function(n_intervals) {
        var overlay = document.getElementById('screener-blur-overlay');
        if (overlay) {
            overlay.style.display = 'flex';
            overlay.style.opacity = '1';
        }
        var ov2 = document.getElementById('overview-blur-overlay');
        if (ov2) {
            ov2.style.display = 'block';
            ov2.style.opacity = '1';
        }
        return window.dash_clientside.no_update;
    }
    """,
    Output("dummy-blur-output", "data"), # Trỏ sang dummy 1
    Input("realtime-price-interval", "n_intervals"),
    prevent_initial_call=True,
)

# Khi server trả về timestamp mới → ẩn blur
clientside_callback(
    """
    function(ts) {
        if (!ts || ts === 0) return window.dash_clientside.no_update;

        setTimeout(function() {
            var overlay = document.getElementById('screener-blur-overlay');
            if (overlay) {
                overlay.style.opacity = '0';
                setTimeout(function() { overlay.style.display = 'none'; }, 150);
            }
            var ov2 = document.getElementById('overview-blur-overlay');
            if (ov2) {
                ov2.style.opacity = '0';
                setTimeout(function() { ov2.style.display = 'none'; }, 150);
            }
        }, 300);

        return window.dash_clientside.no_update;
    }
    """,
    Output("dummy-unblur-output", "data"), # Trỏ sang dummy 2
    Input("realtime-fetch-ts", "data"),
    prevent_initial_call=True,
)


# ─────────────────────────────────────────────────────────────────────────────
# CALLBACK: Cập nhật rowData screener với giá mới
# ─────────────────────────────────────────────────────────────────────────────

@app.callback(
    Output("screener-table",    "rowData",  allow_duplicate=True),
    Output("realtime-fetch-ts", "data"),
    Input("realtime-price-interval", "n_intervals"),
    State("screener-table",     "rowData"),
    prevent_initial_call=True,
)
def update_screener_realtime(n_intervals, current_row_data):
    """
    Mỗi 60s: đọc in-memory snapshot từ wifeed_updater → patch rowData.
    Luôn chạy để apply khi có dữ liệu mới, kể cả ngoài giờ giao dịch.
    Scheduler tự lo việc không fetch khi ngoài giờ.
    """
    if not current_row_data:
        return no_update, no_update

    try:
        from src.backend.wifeed_updater import get_realtime_snapshot

        snapshot = get_realtime_snapshot()
        if not snapshot:
            # Chưa có cache nào → unblur, giữ nguyên rowData
            return no_update, time.time()

        new_row_data = _patch_rows(current_row_data, snapshot)

        n_patched = sum(
            1 for r, nr in zip(current_row_data, new_row_data)
            if r.get("Price Close") != nr.get("Price Close")
        )

        if n_patched == 0:
            # Không có gì thay đổi → trả timestamp để unblur, không re-render grid
            return no_update, time.time()

        import pytz
        from datetime import datetime
        t_str = datetime.now(pytz.timezone("Asia/Ho_Chi_Minh")).strftime("%H:%M:%S")
        logger.info(f"[Realtime] Patch: {n_patched}/{len(current_row_data)} mã | {t_str} VN")

        return new_row_data, time.time()

    except Exception as e:
        logger.error(f"[Realtime] Lỗi: {e}", exc_info=True)
        return no_update, time.time()


# ─────────────────────────────────────────────────────────────────────────────
# CALLBACK: Cập nhật giá trong tab Tổng quan
# ─────────────────────────────────────────────────────────────────────────────

@app.callback(
    Output("realtime-overview-price", "children"),
    Output("realtime-overview-price", "style"),
    Input("realtime-price-interval",  "n_intervals"),
    State("selected-stock-store",     "data"),
    State("detail-modal",             "is_open"),
    prevent_initial_call=True,
)
def update_overview_price(n_intervals, stock, modal_open):
    """
    Cập nhật giá hiển thị trong tab Tổng quan.
    Chỉ chạy khi modal đang mở.
    """
    if not modal_open or not stock:
        return no_update, no_update

    ticker = stock.get("Ticker", "")
    if not ticker:
        return no_update, no_update

    try:
        from src.backend.wifeed_updater import get_realtime_snapshot, _is_trading_time

        if not _is_trading_time():
            return no_update, no_update

        snapshot = get_realtime_snapshot()
        rt       = snapshot.get(ticker)

        if rt is None:
            return no_update, no_update

        price = rt.get("Price Close")
        pct   = rt.get("Price_Change_Pct", 0)

        if price is None:
            return no_update, no_update

        price   = float(price)
        pct     = float(pct or 0)
        sign    = "+" if pct >= 0 else ""
        color   = "#10b981" if pct >= 0 else "#ef4444"

        display = f"{price:,.0f}  {sign}{pct:.2f}%"
        style   = {
            "textAlign":    "right",
            "fontSize":     "28px",
            "color":        color,
            "fontWeight":   "bold",
            "fontFamily":   "'JetBrains Mono', monospace",
            "transition":   "color 0.3s ease",
        }

        logger.debug(f"[Realtime] Overview price updated: {ticker} = {price:,.0f}")
        return display, style

    except Exception as e:
        logger.error(f"[Realtime] Lỗi update overview price: {e}")
        return no_update, no_update