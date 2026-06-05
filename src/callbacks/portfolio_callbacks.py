# src/callbacks/portfolio_callbacks.py
"""
Portfolio Tracker — Phòng Khám Danh Mục
========================================
Nâng cấp từ bản gốc (tracking) lên bản mới (advising + warning):

Tính năng mới:
  • Nhập Tỷ lệ Ký quỹ thực tế (Rtt) + Tổng nợ vay Margin
  • Bộ Rule Y Tế: Thanh khoản / Cắt lỗ / VGM / Phòng thủ
  • Cột "Hành động đề xuất" trong bảng danh mục
  • Stress Test: giả lập ngày mai thị trường -3%
  • Cảnh báo Force Sell nếu Rtt tương lai < 30%
  • Summary cards bổ sung Margin Health Meter
"""
from dash import Input, Output, State, html, dcc, no_update, callback_context, ALL
from src.app_instance import app
import dash_bootstrap_components as dbc
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import logging, json

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════════
# CONSTANTS — Ngưỡng Rule Y Tế
# ═══════════════════════════════════════════════════════════════════════════════
STOP_LOSS_PCT        = -7.0    # % — vi phạm kỷ luật cắt lỗ
MARGIN_FORCE_SELL    = 30.0    # % — Rtt ngưỡng Force Sell
MARGIN_CAUTION       = 40.0    # % — Rtt ngưỡng cảnh báo
LIQUIDITY_RATIO      = 0.3     # vol hôm nay < 30% SMA20 → kẹt thanh khoản
STRESS_MARKET_DROP   = 3.0     # % — giả lập thị trường giảm ngày mai
STRESS_WEAK_DROP     = 7.0     # % — VGM D/F giảm sàn
STRESS_STRONG_DROP   = 2.0     # % — VGM A/B chỉ giảm nhẹ

# ═══════════════════════════════════════════════════════════════════════════════
# MODAL LAYOUT
# ═══════════════════════════════════════════════════════════════════════════════
portfolio_modal = dbc.Modal([
    dbc.ModalHeader(
        dbc.ModalTitle([
            html.Div([
                html.Div([
                    html.I(className="fas fa-briefcase", style={"marginRight": "8px", "color": "#f59e0b"}),
                    "Phòng Khám Danh Mục",
                    html.Span(" · Portfolio Hospital", style={"fontSize": "12px", "color": "#5a8ab0", "fontWeight": "400", "marginLeft": "8px"}),
                ]),
                # THÊM NÚT HƯỚNG DẪN Ở ĐÂY:
                html.I(className="fas fa-info-circle", id="btn-portfolio-help",
                       style={"cursor": "pointer", "fontSize": "16px", "color": "#3b82f6", "marginLeft": "15px", "padding": "5px"}),
            ], style={"display": "flex", "alignItems": "center"})
        ]),
    ),
    dbc.ModalBody([

        # ── KHỐI 1: Sức khỏe Tài khoản Margin ──────────────────────────────
        html.Div([
            html.Div([
                html.I(className="fas fa-heartbeat",
                       style={"color": "#ef4444", "marginRight": "8px", "fontSize": "12px"}),
                html.Span("THÔNG SỐ TÀI KHOẢN MARGIN",
                          style={"fontSize": "10px", "fontWeight": "700",
                                 "color": "#ef4444", "letterSpacing": "0.1em"}),
            ], style={"marginBottom": "10px"}),

            html.Div([
                # Tổng giá trị tài khoản
                html.Div([
                    html.Label("Tổng GT tài khoản (VNĐ)",
                               style={"fontSize": "10px", "color": "#7fa8cc", "display": "block", "marginBottom": "4px"}),
                    dcc.Input(
                        id="margin-total-asset",
                        type="number", placeholder="VD: 500000000",
                        style={"width": "100%", "padding": "6px 8px", "backgroundColor": "#0d1117", "color": "#c9d1d9", "border": "1px solid #30363d", "borderRadius": "6px", "fontSize": "12px", "outline": "none"},
                    ),
                    # CHÈN THÊM Ô HIỂN THỊ FORMAT TIỀN:
                    html.Div(id="margin-total-asset-fmt", style={"fontSize": "11px", "color": "#10b981", "marginTop": "4px", "fontWeight": "600", "height": "16px"})
                ], style={"flex": "1"}),

                # Nợ vay Margin
                html.Div([
                    html.Label("Nợ vay Margin (VNĐ)",
                               style={"fontSize": "10px", "color": "#7fa8cc", "display": "block", "marginBottom": "4px"}),
                    dcc.Input(
                        id="margin-debt",
                        type="number", placeholder="VD: 200000000",
                        style={"width": "100%", "padding": "6px 8px", "backgroundColor": "#0d1117", "color": "#c9d1d9", "border": "1px solid #30363d", "borderRadius": "6px", "fontSize": "12px", "outline": "none"},
                    ),
                    # CHÈN THÊM Ô HIỂN THỊ FORMAT TIỀN:
                    html.Div(id="margin-debt-fmt", style={"fontSize": "11px", "color": "#10b981", "marginTop": "4px", "fontWeight": "600", "height": "16px"})
                ], style={"flex": "1"}),

                # Rtt hiện tại (tự tính hoặc nhập tay)
                html.Div([
                    html.Label("Tỷ lệ Rtt hiện tại (%)",
                               style={"fontSize": "10px", "color": "#7fa8cc",
                                      "display": "block", "marginBottom": "4px"}),
                    dcc.Input(
                        id="margin-rtt",
                        type="number", placeholder="VD: 45",
                        min=0, max=100, step=0.1,
                        style={"width": "100%", "padding": "6px 8px",
                               "backgroundColor": "#0d1117", "color": "#f59e0b",
                               "border": "1px solid #f59e0b40", "borderRadius": "6px",
                               "fontSize": "12px", "fontWeight": "700", "outline": "none"},
                    ),
                ], style={"flex": "0 0 140px"}),

                # Toggle ATC
                html.Div([
                    html.Label("Chế độ",
                               style={"fontSize": "10px", "color": "#7fa8cc",
                                      "display": "block", "marginBottom": "4px"}),
                    dbc.Switch(
                        id="margin-atc-mode",
                        label="Cấp cứu ATC",
                        value=False,
                        style={"fontSize": "11px", "color": "#ef4444"},
                    ),
                ], style={"flex": "0 0 120px", "paddingTop": "2px"}),

            ], style={"display": "flex", "gap": "10px", "alignItems": "flex-end"}),

            # Margin health bar (tự động render)
            html.Div(id="margin-health-bar", style={"marginTop": "10px"}),

        ], style={
            "padding": "12px 14px", "marginBottom": "14px",
            "backgroundColor": "#0d1117",
            "borderRadius": "8px",
            "border": "1px solid rgba(239,68,68,0.25)",
            "borderLeft": "3px solid #ef4444",
        }),

        # ── KHỐI 2: Form thêm vị thế ────────────────────────────────────────
        html.Div([
            html.Div([
                html.I(className="fas fa-plus-circle",
                       style={"color": "#10b981", "marginRight": "8px", "fontSize": "12px"}),
                html.Span("THÊM VỊ THẾ MỚI",
                          style={"fontSize": "10px", "fontWeight": "700",
                                 "color": "#10b981", "letterSpacing": "0.1em"}),
            ], style={"marginBottom": "10px"}),

            html.Div([
                dcc.Dropdown(
                    id="portfolio-ticker-input", options=[],
                    placeholder="Mã cổ phiếu...",
                    className="ssi-dropdown-custom", style={"flex": "1"},
                ),
                dcc.Input(
                    id="portfolio-qty-input", type="number",
                    placeholder="Số lượng (CP)", min=1, step=1,
                    style={"width": "130px", "padding": "6px 10px",
                           "backgroundColor": "#0d1117", "color": "#c9d1d9",
                           "border": "1px solid #30363d", "borderRadius": "6px",
                           "fontSize": "12px", "outline": "none"},
                ),
                html.Div([
                    dcc.Input(
                        id="portfolio-price-input", type="number",
                        placeholder="Giá mua (VND)", min=1,
                        style={"width": "150px", "padding": "6px 10px",
                               "backgroundColor": "#0d1117", "color": "#c9d1d9",
                               "border": "1px solid #30363d", "borderRadius": "6px",
                               "fontSize": "12px", "outline": "none"},
                    ),
                    html.Div(id="portfolio-price-warning",
                             style={"fontSize": "10px", "color": "#f59e0b",
                                    "marginTop": "3px", "display": "none"}),
                ], style={"display": "flex", "flexDirection": "column"}),
                dbc.Button(
                    [html.I(className="fas fa-plus", style={"marginRight": "5px"}), "Thêm"],
                    id="portfolio-add-btn", color="success", size="sm",
                    style={"borderRadius": "6px"},
                ),
            ], style={"display": "flex", "gap": "8px", "alignItems": "center"}),
        ], style={
            "padding": "12px 14px", "marginBottom": "14px",
            "backgroundColor": "#161b22", "borderRadius": "8px",
            "border": "1px solid #21262d",
        }),

        # ── KHỐI 3: Bảng danh mục + Hành động ──────────────────────────────
        html.Div(id="portfolio-table", style={"marginBottom": "16px"}),

        # ── KHỐI 4: Summary cards ────────────────────────────────────────────
        html.Div(id="portfolio-summary", style={"marginBottom": "16px"}),

        # ── KHỐI 5: Stress Test ──────────────────────────────────────────────
        html.Div(id="portfolio-stress-test", style={"marginBottom": "16px"}),

        # ── KHỐI 6: Biểu đồ hiệu suất ───────────────────────────────────────
        html.Div(id="portfolio-chart-wrapper", children=[
            html.Div([
                html.I(className="fas fa-chart-line",
                       style={"color": "#3b82f6", "marginRight": "6px", "fontSize": "11px"}),
                html.Span("HIỆU SUẤT SO VỚI VN-INDEX",
                          style={"fontSize": "10px", "fontWeight": "700",
                                 "color": "#5a8ab0", "letterSpacing": "0.08em"}),
            ], style={"marginBottom": "8px"}),
            dcc.Graph(id="portfolio-chart",
                      style={"height": "280px"},
                      config={"displayModeBar": False}),
        ], style={"display": "none"}),

    ], style={"backgroundColor": "#0c1220"}),
], id="portfolio-modal", size="xl", is_open=False, centered=True, scrollable=True)

portfolio_help_modal = dbc.Modal([
    dbc.ModalHeader(dbc.ModalTitle([
        html.I(className="fas fa-user-md", style={"marginRight": "8px", "color": "#10b981"}),
        "Hướng dẫn sử dụng Phòng Khám"
    ], style={"fontSize": "16px"})),
    dbc.ModalBody([
        html.P("Tính năng này hoạt động như một Trợ lý rủi ro, giúp bạn chẩn đoán và đưa ra quyết định mua/bán trong những phiên thị trường biến động mạnh.", style={"fontSize": "13px", "color": "#c9d1d9", "marginBottom": "16px"}),
        
        html.H6([html.I(className="fas fa-1", style={"marginRight": "8px", "color": "#3b82f6"}), "Khai báo tình trạng Margin"], style={"fontSize": "14px", "fontWeight": "700", "color": "#3b82f6"}),
        html.P("Nhập Tổng tài sản và Nợ vay. Hệ thống sẽ tự tính tỷ lệ ký quỹ (Rtt). Nếu bạn bật chế độ 'Cấp cứu ATC', hệ thống sẽ áp dụng các tiêu chí cắt lỗ gắt gao hơn để bảo vệ tài khoản.", style={"fontSize": "12px", "color": "#7fa8cc", "marginBottom": "16px"}),

        html.H6([html.I(className="fas fa-2", style={"marginRight": "8px", "color": "#f59e0b"}), "Thêm vị thế kẹp hàng"], style={"fontSize": "14px", "fontWeight": "700", "color": "#f59e0b"}),
        html.P("Nhập các mã cổ phiếu bạn đang nắm giữ cùng với giá vốn. Hệ thống sẽ tự kéo giá thị trường hiện tại để tính Lời/Lỗ.", style={"fontSize": "12px", "color": "#7fa8cc", "marginBottom": "16px"}),

        html.H6([html.I(className="fas fa-3", style={"marginRight": "8px", "color": "#10b981"}), "Đọc phác đồ điều trị"], style={"fontSize": "14px", "fontWeight": "700", "color": "#10b981"}),
        html.P("Cột 'Hành động' sẽ chỉ định rõ bạn nên làm gì: Ưu tiên cắt bỏ các mã mất thanh khoản (đề phòng kẹt lệnh) hoặc các mã yếu kém (VGM = D, F). Giữ lại các mã khỏe làm phòng thủ.", style={"fontSize": "12px", "color": "#7fa8cc", "marginBottom": "16px"}),

        html.H6([html.I(className="fas fa-4", style={"marginRight": "8px", "color": "#ef4444"}), "Xem kịch bản Stress Test"], style={"fontSize": "14px", "fontWeight": "700", "color": "#ef4444"}),
        html.P("Hệ thống giả lập ngày mai thị trường chung sập 3%. Nếu tỷ lệ Rtt của bạn rớt xuống dưới 30% trong kịch bản này, một khung đỏ Cảnh báo Force Sell sẽ hiện ra kèm danh sách các mã bạn bắt buộc phải bán ngay phiên hôm nay.", style={"fontSize": "12px", "color": "#7fa8cc"}),
    ], style={"backgroundColor": "#0d1117", "border": "1px solid #30363d", "borderRadius": "0 0 8px 8px"}),
], id="portfolio-help-modal", size="md", is_open=False, centered=True)

# Store
portfolio_store = dcc.Store(id="portfolio-store", storage_type="local", data=[])


# ═══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def _fmt(v):
    """Format số VND ngắn gọn."""
    try:
        v = float(v)
        if abs(v) >= 1e12: return f"{v/1e12:.2f}T"
        if abs(v) >= 1e9:  return f"{v/1e9:.1f}B"
        if abs(v) >= 1e6:  return f"{v/1e6:.1f}M"
        return f"{int(v):,}"
    except Exception:
        return "–"


def _badge(text, color, bg_opacity=0.15):
    """Badge nhỏ với màu sắc."""
    return html.Span(text, style={
        "fontSize": "10px", "fontWeight": "700",
        "padding": "2px 7px", "borderRadius": "4px",
        "backgroundColor": f"rgba{_hex_to_rgba(color, bg_opacity)}",
        "color": color,
        "border": f"1px solid {color}40",
        "whiteSpace": "nowrap",
    })


def _hex_to_rgba(hex_color, alpha):
    """Chuyển hex '#rrggbb' → tuple cho rgba()."""
    h = hex_color.lstrip('#')
    try:
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        return f"({r},{g},{b},{alpha})"
    except Exception:
        return f"(128,128,128,{alpha})"


def _diagnose(ticker, pos_pnl_p, rec, atc_mode=False):
    """
    Bộ Rule Y Tế — trả về (label_text, severity, action)
    severity: 'danger' | 'warning' | 'caution' | 'healthy'
    """
    vgm         = str(rec.get("VGM Score", "")).strip().upper()
    vol_today   = float(rec.get("Volume", 0) or 0)
    avg_vol_20  = float(rec.get("Avg_Vol_20D", 0) or 0)
    rsi         = float(rec.get("RSI_14", 50) or 50)
    perf_1w     = float(rec.get("Perf_1W", 0) or 0)

    # ATC mode: ngưỡng cắt lỗ gắt hơn (-5% thay vì -7%)
    stop_loss   = -5.0 if atc_mode else STOP_LOSS_PCT

    # Rule 1 — Kẹt thanh khoản (Tử huyệt)
    if avg_vol_20 > 0 and vol_today < avg_vol_20 * LIQUIDITY_RATIO:
        return ("🔴 Kẹt thanh khoản — tuyệt đối KHÔNG dùng Margin mua thêm",
                "danger",
                "Theo dõi, chờ volume hồi phục")

    # Rule 2 — Vi phạm kỷ luật cắt lỗ
    if pos_pnl_p <= stop_loss:
        label = f"🟠 Chạm ngưỡng cắt lỗ {stop_loss}%"
        if atc_mode:
            label += " · Chế độ ATC: bán ngay phiên ATC hôm nay"
        return (label, "danger", "Bán ngay – bảo toàn vốn")

    # Rule 3 — Mã rác đang lỗ
    if vgm in ("D", "F") and pos_pnl_p < 0:
        return ("🟠 Mã yếu kém (VGM = F/D) đang lỗ — cơ cấu lại danh mục",
                "warning",
                "Cân nhắc bán, chuyển sang mã mạnh hơn")

    # Rule 4 — Cảnh báo RSI quá mua (khó giữ margin)
    if rsi >= 75 and pos_pnl_p > 10:
        return ("🟡 RSI quá mua (%.0f) — giá đang căng, giảm tỷ trọng Margin" % rsi,
                "caution",
                "Chốt một phần, giảm rủi ro")

    # Rule 5 — Mã yếu đang thắng ngắn hạn (cẩn thận bẫy)
    if vgm in ("D", "F") and pos_pnl_p > 0:
        return ("🟡 Đang lãi nhưng VGM thấp — lãi ngắn hạn, rủi ro dài hạn",
                "caution",
                "Chốt lời một phần, đừng dùng margin")

    # Rule 6 — Mã phòng thủ, đang tốt
    if vgm in ("A", "B") and pos_pnl_p > 0:
        return ("🟢 Sức khỏe tốt (VGM = %s) — Giữ làm sức mua dự phòng" % vgm,
                "healthy",
                "Giữ — có thể dùng làm tài sản ký quỹ")

    # Default
    return ("⚪ Bình thường — tiếp tục theo dõi", "neutral", "Theo dõi")


def _severity_color(severity):
    return {
        "danger":  "#ef4444",
        "warning": "#f59e0b",
        "caution": "#f59e0b",
        "healthy": "#10b981",
        "neutral": "#7fa8cc",
    }.get(severity, "#7fa8cc")


def _action_chip(action_text, severity):
    color = _severity_color(severity)
    return html.Span(action_text, style={
        "fontSize": "10px", "fontWeight": "600",
        "padding": "2px 8px", "borderRadius": "10px",
        "backgroundColor": f"rgba{_hex_to_rgba(color, 0.12)}",
        "color": color, "border": f"1px solid {color}30",
        "whiteSpace": "nowrap",
    })


# ═══════════════════════════════════════════════════════════════════════════════
# CALLBACKS
# ═══════════════════════════════════════════════════════════════════════════════

@app.callback(
    Output("portfolio-ticker-input", "options"),
    Input("portfolio-modal",         "is_open"),
    prevent_initial_call=True,
)
def load_portfolio_tickers(is_open):
    if not is_open:
        return no_update
    try:
        from src.backend.data_loader import get_ticker_list
        return get_ticker_list()
    except Exception:
        return []


@app.callback(
    Output("portfolio-price-input", "value", allow_duplicate=True),
    Input("portfolio-ticker-input", "value"),
    prevent_initial_call=True,
)
def autofill_ref_price(ticker):
    if not ticker:
        return no_update
    try:
        from src.backend.data_loader import get_snapshot_df
        snap  = {r["Ticker"]: r for r in get_snapshot_df().to_dict("records")}
        price = snap.get(ticker, {}).get("Price Close")
        if price is not None:
            return round(float(price))
    except Exception:
        pass
    return no_update

@app.callback(
    Output("margin-total-asset-fmt", "children"),
    Output("margin-debt-fmt", "children"),
    Input("margin-total-asset", "value"),
    Input("margin-debt", "value"),
    prevent_initial_call=False,
)
def format_currency_inputs(asset, debt):
    def _format_vnd(val):
        if val is None or str(val) == "": return ""
        try:
            return f"≈ {int(val):,} VNĐ"
        except Exception:
            return ""
    return _format_vnd(asset), _format_vnd(debt)

@app.callback(
    Output("portfolio-help-modal", "is_open"),
    Input("btn-portfolio-help", "n_clicks"),
    prevent_initial_call=True,
)
def toggle_portfolio_help(n):
    if n:
        return True
    return no_update

@app.callback(
    Output("portfolio-price-warning", "children"),
    Output("portfolio-price-warning", "style"),
    Input("portfolio-price-input",    "value"),
    Input("portfolio-ticker-input",   "value"),
    prevent_initial_call=True,
)
def validate_portfolio_price(price_val, ticker):
    hide = {"fontSize": "10px", "color": "#f59e0b", "marginTop": "3px", "display": "none"}
    show = {"fontSize": "10px", "color": "#f59e0b", "marginTop": "3px", "display": "block"}
    if not ticker or price_val is None:
        return "", hide
    try:
        from src.backend.data_loader import get_snapshot_df
        snap  = {r["Ticker"]: r for r in get_snapshot_df().to_dict("records")}
        ref   = float(snap.get(ticker, {}).get("Price Close") or 0)
        if ref <= 0:
            return "", hide
        ratio = float(price_val) / ref
        if ratio > 1.15:
            return f"⚠ Cao hơn giá tham chiếu {(ratio-1)*100:.1f}%", show
        if ratio < 0.85:
            return f"⚠ Thấp hơn giá tham chiếu {(1-ratio)*100:.1f}%", show
    except Exception:
        pass
    return "", hide


@app.callback(
    Output("portfolio-store",           "data",  allow_duplicate=True),
    Output("portfolio-ticker-input",    "value"),
    Output("portfolio-qty-input",       "value"),
    Output("portfolio-price-input",     "value", allow_duplicate=True),
    Input("portfolio-add-btn",          "n_clicks"),
    State("portfolio-ticker-input",     "value"),
    State("portfolio-qty-input",        "value"),
    State("portfolio-price-input",      "value"),
    State("portfolio-store",            "data"),
    prevent_initial_call=True,
)
def add_position(n_clicks, ticker, qty, price, current):
    if not n_clicks or not ticker or not qty or not price:
        return no_update, no_update, no_update, no_update
    current = current or []
    # Cộng dồn nếu mã đã tồn tại (tính giá vốn bình quân)
    existing = next((p for p in current if p["ticker"] == ticker), None)
    if existing:
        old_cost_total  = existing["cost"] * existing["qty"]
        new_cost_total  = float(price) * float(qty)
        new_qty         = existing["qty"] + float(qty)
        avg_cost        = (old_cost_total + new_cost_total) / new_qty
        current         = [p for p in current if p["ticker"] != ticker]
        current.append({"ticker": ticker, "qty": new_qty, "cost": round(avg_cost)})
    else:
        current.append({"ticker": ticker, "qty": float(qty), "cost": float(price)})
    return current, None, None, None


@app.callback(
    Output("portfolio-store", "data", allow_duplicate=True),
    Input({"type": "portfolio-remove-btn", "index": ALL}, "n_clicks"),
    State("portfolio-store", "data"),
    prevent_initial_call=True,
)
def remove_position(n_clicks, current):
    ctx = callback_context
    if not ctx.triggered or not any(n for n in (n_clicks or []) if n):
        return no_update
    triggered = ctx.triggered[0]["prop_id"]
    try:
        idx     = json.loads(triggered.split(".")[0])["index"]
        current = [p for p in (current or []) if p["ticker"] != idx]
    except Exception:
        pass
    return current


# ── Margin Health Bar ────────────────────────────────────────────────────────
@app.callback(
    Output("margin-health-bar", "children"),
    Input("margin-rtt",         "value"),
    Input("margin-debt",        "value"),
    Input("margin-total-asset", "value"),
    prevent_initial_call=False,
)
def update_margin_health(rtt_input, debt, total_asset):
    """Tự tính Rtt nếu user nhập tổng tài sản + nợ vay."""
    rtt = None

    # Ưu tiên tự tính nếu có đủ dữ liệu
    if debt and total_asset and float(total_asset) > 0:
        equity = float(total_asset) - float(debt)
        rtt    = (equity / float(total_asset)) * 100

    # Fallback về ô nhập tay
    if rtt is None and rtt_input is not None:
        rtt = float(rtt_input)

    if rtt is None:
        return html.Div("Nhập thông tin tài khoản để xem trạng thái Margin",
                        style={"fontSize": "11px", "color": "#484f58",
                               "fontStyle": "italic", "marginTop": "4px"})

    # Màu sắc theo ngưỡng
    if rtt >= MARGIN_CAUTION:
        color, label, icon = "#10b981", "AN TOÀN", "fas fa-shield"
    elif rtt >= MARGIN_FORCE_SELL:
        color, label, icon = "#f59e0b", "CẢNH BÁO", "fas fa-exclamation-triangle"
    else:
        color, label, icon = "#ef4444", "NGUY HIỂM — GẦN FORCE SELL", "fas fa-skull-crossbones"

    bar_pct = min(rtt, 100)

    return html.Div([
        html.Div([
            html.Span([html.I(className=icon, style={"marginRight": "6px"}),
                       f"Rtt = {rtt:.1f}%  ·  {label}"],
                      style={"fontSize": "11px", "fontWeight": "700", "color": color}),
            html.Span(f"Force Sell ngưỡng {MARGIN_FORCE_SELL}%",
                      style={"fontSize": "10px", "color": "#484f58", "marginLeft": "8px"}),
        ], style={"display": "flex", "alignItems": "center", "marginBottom": "5px"}),
        # Progress bar
        html.Div([
            html.Div(style={
                "width": f"{bar_pct}%", "height": "100%",
                "background": f"linear-gradient(90deg, {color}80, {color})",
                "borderRadius": "3px", "transition": "width 0.5s ease",
            })
        ], style={
            "height": "6px", "backgroundColor": "rgba(255,255,255,0.06)",
            "borderRadius": "3px", "overflow": "hidden",
        }),
        # Dấu ngưỡng
        html.Div([
            html.Div(style={
                "position": "absolute",
                "left": f"{MARGIN_FORCE_SELL}%",
                "top": "-2px", "width": "1px", "height": "10px",
                "backgroundColor": "#ef4444",
            }),
            html.Div(style={
                "position": "absolute",
                "left": f"{MARGIN_CAUTION}%",
                "top": "-2px", "width": "1px", "height": "10px",
                "backgroundColor": "#f59e0b",
            }),
        ], style={"position": "relative", "height": "6px", "marginTop": "-6px"}),
    ])


# ── Main Render ──────────────────────────────────────────────────────────────
@app.callback(
    Output("portfolio-table",         "children"),
    Output("portfolio-summary",       "children"),
    Output("portfolio-stress-test",   "children"),
    Output("portfolio-chart",         "figure"),
    Output("portfolio-chart-wrapper", "style"),
    Input("portfolio-store",          "data"),
    State("margin-rtt",               "value"),
    State("margin-debt",              "value"),
    State("margin-total-asset",       "value"),
    State("margin-atc-mode",          "value"),
    prevent_initial_call=False,
)
def render_portfolio(positions, rtt_input, debt_input, asset_input, atc_mode):
    positions = positions or []
    atc_mode  = atc_mode or False

    # ── Empty state ──────────────────────────────────────────────────────────
    if not positions:
        empty = html.Div([
            html.I(className="fas fa-briefcase",
                   style={"fontSize": "40px", "color": "#1e3a5f", "marginBottom": "12px"}),
            html.P("Danh mục của bạn đang trống",
                   style={"color": "#3d6a8a", "fontSize": "14px",
                          "fontWeight": "600", "marginBottom": "4px"}),
            html.P("Thêm cổ phiếu ở ô bên trên để Phòng Khám bắt đầu chẩn đoán",
                   style={"color": "#2a4d6e", "fontSize": "12px"}),
        ], style={"textAlign": "center", "padding": "50px 20px",
                  "border": "1px dashed #1e3a5f", "borderRadius": "8px",
                  "backgroundColor": "rgba(9,21,38,0.4)", "marginBottom": "16px"})
        return empty, [], [], go.Figure(), {"display": "none"}

    try:
        from src.backend.data_loader import get_snapshot_df, load_market_data, load_index_data
        snap       = {r["Ticker"]: r for r in get_snapshot_df().to_dict("records")}
        df_price   = load_market_data()
        df_index   = load_index_data()

        # ── Tính Rtt thực tế ─────────────────────────────────────────────────
        rtt_current = None
        debt_val    = float(debt_input  or 0)
        asset_val   = float(asset_input or 0)
        if asset_val > 0 and debt_val >= 0:
            equity      = asset_val - debt_val
            rtt_current = (equity / asset_val) * 100
        elif rtt_input is not None:
            rtt_current = float(rtt_input)

        # ══════════════════════════════════════════════════════════════════════
        # VÒNG LẶP CHÍNH — tính toán + chẩn đoán từng vị thế
        # ══════════════════════════════════════════════════════════════════════
        total_cost              = 0.0
        total_value             = 0.0
        stress_total_value      = 0.0     # giá trị sau stress test
        table_rows              = []
        chart_data              = {}
        critical_actions        = []      # danh sách khuyến nghị bán gấp
        diagnoses               = []      # lưu lại để hiển thị sau

        for pos in positions:
            ticker  = pos["ticker"]
            qty     = float(pos["qty"])
            cost_px = float(pos["cost"])
            rec     = snap.get(ticker, {})

            cur_px   = float(rec.get("Price Close", cost_px) or cost_px)
            vgm      = str(rec.get("VGM Score", "")).strip().upper()

            pos_cost  = cost_px * qty
            pos_val   = cur_px  * qty
            pos_pnl   = pos_val - pos_cost
            pos_pnl_p = (pos_pnl / pos_cost * 100) if pos_cost else 0

            total_cost  += pos_cost
            total_value += pos_val

            # ── Stress test giá ngày mai ──────────────────────────────────
            if vgm in ("A", "B"):
                stress_drop = STRESS_STRONG_DROP / 100
            else:
                stress_drop = STRESS_WEAK_DROP / 100
            stress_px_tomorrow  = cur_px * (1 - stress_drop)
            stress_val_tomorrow = stress_px_tomorrow * qty
            stress_total_value += stress_val_tomorrow

            # ── Chẩn đoán Y Tế ───────────────────────────────────────────
            diag_label, severity, action = _diagnose(ticker, pos_pnl_p, rec, atc_mode)
            diagnoses.append((ticker, diag_label, severity, action))

            color  = _severity_color(severity) if severity in ("danger","warning") else (
                "#10b981" if pos_pnl >= 0 else "#ef4444")
            sign   = "+" if pos_pnl >= 0 else ""
            bg_row = {
                "danger":  "rgba(239,68,68,0.04)",
                "warning": "rgba(245,158,11,0.04)",
                "healthy": "rgba(16,185,129,0.03)",
            }.get(severity, "transparent")

            if severity == "danger":
                critical_actions.append({"ticker": ticker, "action": action, "pnl_p": pos_pnl_p})

            # ── VGM badge ────────────────────────────────────────────────
            vgm_color = {"A":"#10b981","B":"#3b82f6","C":"#f59e0b","D":"#ef4444","F":"#6b7280"}.get(vgm,"#6b7280")
            vgm_badge = html.Span(vgm or "–", style={
                "fontSize": "10px", "fontWeight": "800",
                "padding": "1px 5px", "borderRadius": "3px",
                "backgroundColor": f"rgba{_hex_to_rgba(vgm_color, 0.15)}",
                "color": vgm_color, "border": f"1px solid {vgm_color}40",
            })

            # ── Hàng bảng ────────────────────────────────────────────────
            table_rows.append(html.Div([
                # Cột: Mã + VGM badge
                html.Div([
                    html.Span(ticker, style={"color": "#3b82f6", "fontWeight": "700",
                                             "fontSize": "13px", "marginRight": "4px"}),
                    vgm_badge,
                ], style={"flex": "0 0 110px", "display": "flex", "alignItems": "center"}),

                # SL
                html.Span(f"{qty:,.0f}",
                          style={"flex": "0 0 65px", "color": "#c9d1d9",
                                 "fontSize": "12px", "textAlign": "right"}),
                # Giá vốn
                html.Span(_fmt(cost_px),
                          style={"flex": "0 0 85px", "color": "#7fa8cc",
                                 "fontSize": "12px", "textAlign": "right"}),
                # Giá HT
                html.Span(_fmt(cur_px),
                          style={"flex": "0 0 85px", "color": "#c9d1d9",
                                 "fontSize": "12px", "textAlign": "right"}),
                # Giá trị
                html.Span(_fmt(pos_val),
                          style={"flex": "0 0 95px", "color": "#c9d1d9",
                                 "fontSize": "12px", "textAlign": "right"}),
                # % L/L
                html.Span(f"{sign}{pos_pnl_p:.2f}%",
                          style={"flex": "0 0 80px",
                                 "color": "#10b981" if pos_pnl >= 0 else "#ef4444",
                                 "fontSize": "12px", "textAlign": "right", "fontWeight": "700"}),
                # L/L VND
                html.Span(f"{sign}{_fmt(pos_pnl)}",
                          style={"flex": "0 0 90px",
                                 "color": "#10b981" if pos_pnl >= 0 else "#ef4444",
                                 "fontSize": "12px", "textAlign": "right"}),
                # Cột hành động đề xuất (MỚI)
                html.Div([
                    _action_chip(action, severity),
                ], style={"flex": "1", "paddingLeft": "8px", "display": "flex",
                          "alignItems": "center"}),
                # Nút xóa
                html.I(className="fas fa-times",
                       id={"type": "portfolio-remove-btn", "index": ticker},
                       n_clicks=0,
                       style={"color": "#484f58", "cursor": "pointer",
                              "fontSize": "12px", "marginLeft": "6px", "flexShrink": "0"}),
            ], style={
                "display": "flex", "alignItems": "center",
                "padding": "7px 10px",
                "borderBottom": "1px solid #0e2540",
                "backgroundColor": bg_row,
            }))

            # Lịch sử giá cho chart
            df_t = df_price[df_price["Ticker"] == ticker].sort_values("Date").tail(252)
            if not df_t.empty:
                chart_data[ticker] = df_t.set_index("Date")["Price Close"]

        # ── Chẩn đoán chi tiết (panel dưới bảng) ─────────────────────────
        diag_rows = []
        for d_ticker, d_label, d_sev, d_action in diagnoses:
            d_color = _severity_color(d_sev)
            diag_rows.append(html.Div([
                html.Span(d_ticker, style={"width": "60px", "fontWeight": "700",
                                           "color": "#3b82f6", "fontSize": "11px",
                                           "flexShrink": "0"}),
                html.Span(d_label, style={"flex": "1", "fontSize": "11px",
                                          "color": d_color, "lineHeight": "1.4"}),
            ], style={"display": "flex", "gap": "10px", "alignItems": "flex-start",
                      "padding": "5px 0", "borderBottom": "1px solid #0e2540"}))

        # ── Header bảng ──────────────────────────────────────────────────
        header = html.Div([
            html.Span("Mã / VGM",    style={"flex": "0 0 110px", "color": "#7fa8cc", "fontWeight": "600", "fontSize": "11px"}),
            html.Span("SL (CP)",     style={"flex": "0 0 65px",  "color": "#7fa8cc", "fontWeight": "600", "fontSize": "11px", "textAlign": "right"}),
            html.Span("Giá mua",     style={"flex": "0 0 85px",  "color": "#7fa8cc", "fontWeight": "600", "fontSize": "11px", "textAlign": "right"}),
            html.Span("Giá HT",      style={"flex": "0 0 85px",  "color": "#7fa8cc", "fontWeight": "600", "fontSize": "11px", "textAlign": "right"}),
            html.Span("Giá trị",     style={"flex": "0 0 95px",  "color": "#7fa8cc", "fontWeight": "600", "fontSize": "11px", "textAlign": "right"}),
            html.Span("% L/L",       style={"flex": "0 0 80px",  "color": "#7fa8cc", "fontWeight": "600", "fontSize": "11px", "textAlign": "right"}),
            html.Span("L/L (VND)",   style={"flex": "0 0 90px",  "color": "#7fa8cc", "fontWeight": "600", "fontSize": "11px", "textAlign": "right"}),
            html.Span("Hành động",   style={"flex": "1",          "color": "#7fa8cc", "fontWeight": "600", "fontSize": "11px", "paddingLeft": "8px"}),
            html.Span("",            style={"flex": "0 0 20px"}),
        ], style={"display": "flex", "padding": "6px 10px",
                  "borderBottom": "2px solid #21262d", "backgroundColor": "#161b22"})

        table = html.Div([
            header,
            *table_rows,
            # Panel chẩn đoán chi tiết
            html.Div([
                html.Div([
                    html.I(className="fas fa-stethoscope",
                           style={"color": "#a78bfa", "marginRight": "6px", "fontSize": "11px"}),
                    html.Span("CHẨN ĐOÁN CHI TIẾT",
                              style={"fontSize": "10px", "fontWeight": "700",
                                     "color": "#a78bfa", "letterSpacing": "0.1em"}),
                ], style={"marginBottom": "8px"}),
                *diag_rows,
            ], style={
                "padding": "10px 12px", "margin": "8px",
                "backgroundColor": "rgba(167,139,250,0.04)",
                "border": "1px solid rgba(167,139,250,0.15)",
                "borderRadius": "6px",
            }),
        ], style={
            "backgroundColor": "#0d1117", "borderRadius": "8px",
            "border": "1px solid #21262d", "overflow": "hidden",
            "marginBottom": "12px",
        })

        # ══════════════════════════════════════════════════════════════════════
        # SUMMARY CARDS
        # ══════════════════════════════════════════════════════════════════════
        total_pnl   = total_value - total_cost
        total_pnl_p = (total_pnl / total_cost * 100) if total_cost else 0
        c_pnl       = "#10b981" if total_pnl >= 0 else "#ef4444"

        # Tính Rtt sau khi giá cổ phiếu thay đổi
        rtt_now = None
        if debt_val > 0 and total_value > 0:
            equity_now = total_value - debt_val
            rtt_now    = max(0, (equity_now / total_value) * 100)
        elif rtt_current is not None:
            rtt_now = rtt_current

        rtt_color = ("#10b981" if rtt_now and rtt_now >= MARGIN_CAUTION else
                     "#f59e0b" if rtt_now and rtt_now >= MARGIN_FORCE_SELL else
                     "#ef4444") if rtt_now else "#7fa8cc"

        def _card(label, value, color="#c9d1d9", sub=None):
            return html.Div([
                html.Span(label, style={"fontSize": "10px", "color": "#7fa8cc",
                                        "fontWeight": "500", "letterSpacing": "0.05em"}),
                html.Span(value, style={"fontSize": "15px", "fontWeight": "800",
                                        "color": color, "marginTop": "2px",
                                        "fontFamily": "'JetBrains Mono', monospace"}),
                *([html.Span(sub, style={"fontSize": "10px", "color": "#484f58",
                                         "marginTop": "1px"})] if sub else []),
            ], style={"display": "flex", "flexDirection": "column",
                      "padding": "10px 14px", "backgroundColor": "#161b22",
                      "borderRadius": "8px", "border": "1px solid #21262d"})

        summary = html.Div([
            _card("Vốn đầu tư",        _fmt(total_cost)),
            _card("Giá trị hiện tại",  _fmt(total_value)),
            _card("Lời / Lỗ (VND)",    ("+" if total_pnl >= 0 else "") + _fmt(total_pnl), c_pnl),
            _card("Lời / Lỗ (%)",      f"{'+'if total_pnl_p>=0 else''}{total_pnl_p:.2f}%", c_pnl),
            _card("Rtt hiện tại",
                  f"{rtt_now:.1f}%" if rtt_now else "Chưa nhập",
                  rtt_color,
                  sub="Force Sell < 30%" if rtt_now and rtt_now < MARGIN_CAUTION else None),
        ], style={"display": "grid",
                  "gridTemplateColumns": "repeat(5,1fr)",
                  "gap": "8px", "marginBottom": "14px"})

        # ══════════════════════════════════════════════════════════════════════
        # STRESS TEST — Kịch bản ngày mai thị trường -3%
        # ══════════════════════════════════════════════════════════════════════
        stress_pnl    = stress_total_value - total_cost
        stress_pnl_p  = (stress_pnl / total_cost * 100) if total_cost else 0
        stress_color  = "#10b981" if stress_pnl >= 0 else "#ef4444"

        # Tính Rtt sau stress
        stress_rtt    = None
        if debt_val > 0 and stress_total_value > 0:
            equity_stress = stress_total_value - debt_val
            stress_rtt    = max(0, (equity_stress / stress_total_value) * 100)

        force_sell_warning = (stress_rtt is not None and stress_rtt < MARGIN_FORCE_SELL)

        # Tổng thiếu hụt nếu force sell
        shortfall = 0.0
        if force_sell_warning and debt_val > 0:
            required_equity = stress_total_value * (MARGIN_FORCE_SELL / 100)
            actual_equity   = stress_total_value - debt_val
            shortfall       = required_equity - actual_equity

        # Mã khuyến nghị bán trong ATC
        sell_candidates = sorted(
            [d for d in diagnoses if d[2] == "danger"],
            key=lambda x: x[3]
        )[:3]

        stress_panel = html.Div([
            # Header
            html.Div([
                html.I(className="fas fa-bolt",
                       style={"color": "#f59e0b", "marginRight": "8px", "fontSize": "12px"}),
                html.Span("STRESS TEST — Kịch bản thị trường giảm ngày mai",
                          style={"fontSize": "11px", "fontWeight": "700",
                                 "color": "#f59e0b", "letterSpacing": "0.05em"}),
                html.Span(f"  (VGM A/B: -{STRESS_STRONG_DROP}%  |  VGM C/D/F: -{STRESS_WEAK_DROP}%  |  Thị trường: -{STRESS_MARKET_DROP}%)",
                          style={"fontSize": "10px", "color": "#484f58", "marginLeft": "8px"}),
            ], style={"display": "flex", "alignItems": "center", "marginBottom": "12px"}),

            # Kết quả giả lập
            html.Div([
                html.Div([
                    html.Span("Giá trị danh mục (ngày mai)",
                              style={"fontSize": "10px", "color": "#7fa8cc", "display": "block"}),
                    html.Span(_fmt(stress_total_value),
                              style={"fontSize": "15px", "fontWeight": "800",
                                     "color": stress_color, "fontFamily": "'JetBrains Mono', monospace"}),
                ], style={"flex": "1", "padding": "8px 12px", "backgroundColor": "#0d1117",
                          "borderRadius": "6px", "border": "1px solid #21262d"}),

                html.Div([
                    html.Span("P&L sau stress",
                              style={"fontSize": "10px", "color": "#7fa8cc", "display": "block"}),
                    html.Span(f"{'+'if stress_pnl>=0 else''}{_fmt(stress_pnl)}  ({stress_pnl_p:+.2f}%)",
                              style={"fontSize": "15px", "fontWeight": "800",
                                     "color": stress_color, "fontFamily": "'JetBrains Mono', monospace"}),
                ], style={"flex": "1", "padding": "8px 12px", "backgroundColor": "#0d1117",
                          "borderRadius": "6px", "border": "1px solid #21262d"}),

                html.Div([
                    html.Span("Rtt sau stress",
                              style={"fontSize": "10px", "color": "#7fa8cc", "display": "block"}),
                    html.Span(f"{stress_rtt:.1f}%" if stress_rtt is not None else "N/A",
                              style={"fontSize": "15px", "fontWeight": "800",
                                     "color": "#ef4444" if force_sell_warning else "#10b981",
                                     "fontFamily": "'JetBrains Mono', monospace"}),
                ], style={"flex": "1", "padding": "8px 12px", "backgroundColor": "#0d1117",
                          "borderRadius": "6px",
                          "border": "1px solid " + ("#ef444440" if force_sell_warning else "#21262d")}),

            ], style={"display": "flex", "gap": "8px", "marginBottom": "12px"}),

            # ⚠️ CẢNH BÁO FORCE SELL
            *([html.Div([
                html.Div([
                    html.I(className="fas fa-siren-on",
                           style={"fontSize": "18px", "color": "#ef4444",
                                  "marginRight": "10px", "flexShrink": "0"}),
                    html.Div([
                        html.Div("🚨 CẢNH BÁO: NGUY CƠ FORCE SELL SÁNG MAI",
                                 style={"fontWeight": "800", "color": "#ef4444",
                                        "fontSize": "13px", "marginBottom": "4px",
                                        "letterSpacing": "0.05em"}),
                        html.Div([
                            f"Tài khoản sẽ thiếu hụt ",
                            html.Strong(f"{_fmt(shortfall)} VNĐ",
                                        style={"color": "#ef4444"}),
                            f" để duy trì Rtt = {MARGIN_FORCE_SELL}%. ",
                            "Cần hành động trước phiên ATC hôm nay!",
                        ], style={"fontSize": "12px", "color": "#c9d1d9",
                                  "lineHeight": "1.6", "marginBottom": "8px"}),

                        # Danh sách mã nên bán
                        *([html.Div([
                            html.Span("Ưu tiên bán trong ATC: ",
                                      style={"fontSize": "11px", "color": "#f59e0b",
                                             "fontWeight": "700", "marginRight": "6px"}),
                            *[html.Span(sc[0], style={
                                "fontSize": "11px", "fontWeight": "700",
                                "color": "#fff", "backgroundColor": "#ef444430",
                                "border": "1px solid #ef444450",
                                "borderRadius": "4px", "padding": "1px 6px",
                                "marginRight": "4px",
                            }) for sc in sell_candidates],
                        ])] if sell_candidates else []),
                    ]),
                ], style={"display": "flex", "alignItems": "flex-start"}),
            ], style={
                "padding": "14px 16px",
                "backgroundColor": "rgba(239,68,68,0.06)",
                "border": "1px solid rgba(239,68,68,0.3)",
                "borderLeft": "4px solid #ef4444",
                "borderRadius": "8px",
                "animation": "pulse-border 2s ease-in-out infinite",
            })] if force_sell_warning else [

                # Tình trạng ổn
                html.Div([
                    html.I(className="fas fa-check-circle",
                           style={"color": "#10b981", "marginRight": "8px"}),
                    html.Span(
                        f"Tài khoản an toàn sau stress test. "
                        f"Rtt dự kiến: {stress_rtt:.1f}% > ngưỡng Force Sell {MARGIN_FORCE_SELL}%"
                        if stress_rtt is not None
                        else "Nhập thông tin Margin để xem cảnh báo Force Sell.",
                        style={"fontSize": "12px", "color": "#10b981"}),
                ], style={
                    "padding": "10px 14px",
                    "backgroundColor": "rgba(16,185,129,0.05)",
                    "border": "1px solid rgba(16,185,129,0.2)",
                    "borderRadius": "6px",
                })
            ]),

            # Ghi chú
            html.Div([
                html.I(className="fas fa-info-circle",
                       style={"color": "#484f58", "marginRight": "6px",
                              "fontSize": "10px"}),
                html.Span(
                    "Stress Test là kịch bản giả định, không phải dự báo chính xác. "
                    "Thực tế có thể khác biệt do biên độ, thanh khoản và điều kiện thị trường.",
                    style={"fontSize": "10px", "color": "#484f58",
                           "fontStyle": "italic"}),
            ], style={"display": "flex", "alignItems": "flex-start",
                      "marginTop": "10px"}),

        ], style={
            "padding": "14px 16px",
            "backgroundColor": "#0d1117",
            "border": "1px solid rgba(245,158,11,0.2)",
            "borderLeft": "3px solid #f59e0b",
            "borderRadius": "8px",
        })

        # ══════════════════════════════════════════════════════════════════════
        # BIỂU ĐỒ HIỆU SUẤT
        # ══════════════════════════════════════════════════════════════════════
        fig    = go.Figure()
        COLORS = ["#00d4ff", "#10b981", "#f59e0b", "#a78bfa", "#f87171", "#34d399"]

        for i, (t, series) in enumerate(chart_data.items()):
            base = float(series.iloc[0])
            if base <= 0:
                continue
            pct = ((series / base) - 1) * 100
            fig.add_trace(go.Scatter(
                x=pct.index, y=pct.values, mode="lines", name=t,
                line=dict(color=COLORS[i % len(COLORS)], width=1.8),
                hovertemplate=f"<b>{t}</b><br>%{{x|%d/%m/%y}}<br>%{{y:+.1f}}%<extra></extra>",
            ))

        if df_index is not None and not df_index.empty and chart_data:
            min_date = min(s.index.min() for s in chart_data.values())
            vnindex  = df_index[df_index["Date"] >= min_date].sort_values("Date")
            if not vnindex.empty:
                base_vn  = float(vnindex["VNINDEX_Close"].iloc[0])
                pct_vn   = ((vnindex["VNINDEX_Close"] / base_vn) - 1) * 100
                fig.add_trace(go.Scatter(
                    x=vnindex["Date"], y=pct_vn, mode="lines", name="VN-Index",
                    line=dict(color="#ffffff", width=1.2, dash="dot"),
                    hovertemplate="<b>VN-Index</b><br>%{x|%d/%m/%y}<br>%{y:+.1f}%<extra></extra>",
                ))

        fig.add_hline(y=0, line_color="rgba(255,255,255,0.1)", line_width=1)
        fig.update_layout(
            paper_bgcolor="#0c1220", plot_bgcolor="#0c1220",
            margin=dict(l=5, r=5, t=5, b=5),
            legend=dict(bgcolor="rgba(22,27,34,0.8)", bordercolor="#30363d",
                        borderwidth=1, font=dict(color="#c9d1d9", size=11)),
            xaxis=dict(showgrid=False, zeroline=False,
                       tickfont=dict(color="#484f58", size=9)),
            yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.04)",
                       zeroline=False, tickfont=dict(color="#484f58", size=9),
                       ticksuffix="%"),
            hovermode="x unified",
        )

        return table, summary, stress_panel, fig, {"display": "block"}

    except Exception as e:
        logger.error(f"Portfolio render error: {e}", exc_info=True)
        return html.P(f"Lỗi: {e}", style={"color": "#ef4444"}), [], [], go.Figure(), {"display": "none"}


@app.callback(
    Output("portfolio-modal", "is_open"),
    Input("btn-portfolio",    "n_clicks"),
    prevent_initial_call=True,
)
def open_portfolio_modal(n):
    return True if n else no_update