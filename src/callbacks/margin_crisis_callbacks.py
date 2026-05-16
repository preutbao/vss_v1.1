# src/callbacks/margin_crisis_callbacks.py
"""
Margin Crisis Backtester — Vietcap Smart Screener
==================================================
Chức năng: Giúp quản lý xử lý khủng hoảng margin, tránh Force Sell.

Layout: Modal 3 tab
  Tab 1 — Danh mục Gốc     : Nhập vị thế + tỷ lệ margin từng mã
  Tab 2 — Kịch bản Stress   : Cài thông số T+1 worst/flat + ngưỡng an toàn
  Tab 3 — Kết quả Backtest  : So sánh Rtt trước/sau + khuyến nghị hành động

Dữ liệu dùng từ snapshot (không cần file mới):
  Price Close, Perf_1W, Consec_Down, Avg_Vol_20D, Vol_vs_SMA20,
  VGM Score, CANSLIM Score
"""

import json
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from dash import (
    Input, Output, State, html, dcc, no_update,
    callback_context, ALL
)
from src.app_instance import app
import dash_bootstrap_components as dbc
import logging

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────────────────────────────────────
RTT_FORCE_SELL   = 70.0   # Ngưỡng bị Force Sell (%)
RTT_CALL_MARGIN  = 60.0   # Ngưỡng Call Margin cảnh báo (%)
RTT_SAFE         = 40.0   # Ngưỡng an toàn mặc định (%)

_C = {
    "bg_dark":   "#07111e",
    "bg_card":   "#0d1829",
    "bg_card2":  "#111f30",
    "border":    "#1d3a5e",
    "border2":   "#254d7a",
    "red":       "#ef4444",
    "amber":     "#f59e0b",
    "green":     "#10b981",
    "blue":      "#3b82f6",
    "cyan":      "#00d4ff",
    "text_pri":  "#e2e8f0",
    "text_sec":  "#94a3b8",
    "text_mut":  "#64748b",
}

# ─────────────────────────────────────────────────────────────────────────────
# LAYOUT HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _card(children, style_extra=None):
    base = {
        "backgroundColor": _C["bg_card"],
        "border": f"1px solid {_C['border']}",
        "borderRadius": "10px",
        "padding": "16px",
        "marginBottom": "14px",
    }
    if style_extra:
        base.update(style_extra)
    return html.Div(children, style=base)


def _label(text, color=None):
    return html.Div(text, style={
        "fontSize": "11px", "fontWeight": "700",
        "color": color or _C["text_sec"],
        "letterSpacing": "0.8px", "textTransform": "uppercase",
        "marginBottom": "6px",
        "fontFamily": "'JetBrains Mono', monospace",
    })


def _input(id_, placeholder, type_="number", value=None, width="100%"):
    return dcc.Input(
        id=id_, type=type_, placeholder=placeholder, value=value,
        debounce=True,
        style={
            "width": width, "backgroundColor": _C["bg_dark"],
            "border": f"1px solid {_C['border2']}",
            "borderRadius": "6px", "padding": "7px 10px",
            "color": _C["text_pri"], "fontSize": "13px", "outline": "none",
            "fontFamily": "'JetBrains Mono', monospace",
        },
    )


def _rtt_gauge_color(rtt):
    if rtt is None:
        return _C["text_mut"]
    if rtt >= RTT_FORCE_SELL:
        return _C["red"]
    if rtt >= RTT_CALL_MARGIN:
        return _C["amber"]
    return _C["green"]


def _hex_to_rgba(hex_color: str, alpha: float = 0.53) -> str:
    """
    Convert '#rrggbb' → 'rgba(r,g,b,alpha)'.
    Plotly marker.line.color không chấp nhận hex 8 ký tự (#rrggbbaa),
    phải dùng rgba() string.
    alpha=0.53 ≈ hex 88 (136/255).
    """
    h = hex_color.lstrip("#")
    if len(h) == 6:
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        return f"rgba({r},{g},{b},{alpha})"
    # Fallback: trả về nguyên nếu không parse được
    return hex_color


def _fmt_vnd(val):
    try:
        v = float(val)
        if abs(v) >= 1e9:
            return f"{v/1e9:,.2f} tỷ"
        if abs(v) >= 1e6:
            return f"{v/1e6:,.0f} tr"
        return f"{v:,.0f}"
    except Exception:
        return "–"


# ─────────────────────────────────────────────────────────────────────────────
# TAB 1 LAYOUT — Danh mục Gốc
# ─────────────────────────────────────────────────────────────────────────────

def _build_tab1():
    return html.Div([
        # Header hướng dẫn
        html.Div([
            html.I(className="fas fa-info-circle",
                   style={"color": _C["blue"], "marginRight": "8px", "fontSize": "12px"}),
            html.Span(
                "Nhập từng mã đang dùng margin. "
                "Tỷ lệ vay (%) lấy từ thông báo CTCK — "
                "SCS bị cắt hạn mức thì nhập 0%.",
                style={"fontSize": "12px", "color": _C["text_sec"], "lineHeight": "1.6"}
            ),
        ], style={
            "backgroundColor": f"{_C['blue']}11",
            "border": f"1px solid {_C['blue']}33",
            "borderRadius": "8px", "padding": "10px 14px", "marginBottom": "16px",
        }),

        # Vốn tự có tổng
        _card([
            _label("Tổng vốn tự có (VND)"),
            html.Div([
                _input("crisis-equity-input", "VD: 500000000", value=None, width="100%"),
                html.Div(id="crisis-equity-display", style={
                    "fontSize": "11px", "color": _C["text_mut"],
                    "marginTop": "4px", "fontFamily": "'JetBrains Mono', monospace"
                }),
            ]),
        ]),

        # Form thêm vị thế
        _card([
            _label("Thêm mã cổ phiếu đang dùng Margin"),
            html.Div([
                # Row 1: Mã + Khối lượng
                html.Div([
                    html.Div([
                        _label("Mã CP"),
                        dcc.Dropdown(
                            id="crisis-ticker-input",
                            options=[], value=None,
                            placeholder="VD: VCI",
                            className="ssi-dropdown-custom",
                            style={"fontSize": "13px"},
                        ),
                    ], style={"flex": "2"}),
                    html.Div([
                        _label("Khối lượng (CP)"),
                        _input("crisis-qty-input", "VD: 10000", width="100%"),
                    ], style={"flex": "2"}),
                    html.Div([
                        _label("Giá vốn (VND)"),
                        _input("crisis-cost-input", "VD: 35000", width="100%"),
                    ], style={"flex": "2"}),
                ], style={"display": "flex", "gap": "10px", "marginBottom": "10px"}),

                # Row 2: Tỷ lệ vay + Số tiền vay + Nút thêm
                html.Div([
                    html.Div([
                        _label("Tỷ lệ vay Margin (%)"),
                        _input("crisis-margin-rate-input", "VD: 50", value=50, width="100%"),
                    ], style={"flex": "2"}),
                    html.Div([
                        _label("Số tiền vay (VND)"),
                        _input("crisis-loan-input", "Tự động tính", value=None, width="100%"),
                    ], style={"flex": "2"}),
                    html.Div([
                        _label("‎"),  # spacer
                        dbc.Button([
                            html.I(className="fas fa-plus", style={"marginRight": "6px"}),
                            "Thêm vị thế",
                        ], id="crisis-add-btn", color="primary", size="sm",
                           style={"width": "100%", "borderRadius": "6px",
                                  "fontSize": "12px", "fontWeight": "700"}),
                    ], style={"flex": "1.5"}),
                ], style={"display": "flex", "gap": "10px"}),

                html.Div(id="crisis-add-error", style={
                    "color": _C["red"], "fontSize": "12px",
                    "marginTop": "6px", "minHeight": "16px"
                }),
            ]),
        ]),

        # Bảng danh mục hiện tại
        html.Div(id="crisis-positions-table"),

        # Tóm tắt Rtt hiện tại
        html.Div(id="crisis-rtt-summary"),
    ], style={"padding": "4px"})


# ─────────────────────────────────────────────────────────────────────────────
# TAB 2 LAYOUT — Kịch bản Stress
# ─────────────────────────────────────────────────────────────────────────────

def _build_tab2():
    return html.Div([
        _card([
            _label("Ngưỡng Rtt an toàn mục tiêu (%)"),
            html.Div([
                dcc.Slider(
                    id="crisis-target-rtt",
                    min=25, max=65, step=5, value=40,
                    marks={25: "25%", 35: "35%", 40: "AN TOÀN", 50: "50%", 60: "60%", 65: "65%"},
                    tooltip={"placement": "bottom", "always_visible": True},
                    className="custom-slider",
                ),
            ], style={"marginTop": "8px"}),
        ]),

        _card([
            _label("Kịch bản giá T+1"),
            dbc.RadioItems(
                id="crisis-scenario",
                options=[
                    {
                        "label": html.Div([
                            html.I(className="fas fa-skull-crossbones",
                                   style={"color": _C["red"], "marginRight": "8px"}),
                            html.Span("Xấu nhất (Sập hầm)",
                                      style={"fontWeight": "700", "color": _C["text_pri"]}),
                            html.Br(),
                            html.Span("Áp Perf_1W tệ nhất 7 ngày qua vào giá hiện tại",
                                      style={"fontSize": "11px", "color": _C["text_sec"]}),
                        ], style={"lineHeight": "1.8"}),
                        "value": "worst",
                    },
                    {
                        "label": html.Div([
                            html.I(className="fas fa-equals",
                                   style={"color": _C["amber"], "marginRight": "8px"}),
                            html.Span("Đi ngang (Giá giữ nguyên)",
                                      style={"fontWeight": "700", "color": _C["text_pri"]}),
                            html.Br(),
                            html.Span("Giá T+1 = Giá hiện tại, chỉ tính lại room margin",
                                      style={"fontSize": "11px", "color": _C["text_sec"]}),
                        ], style={"lineHeight": "1.8"}),
                        "value": "flat",
                    },
                ],
                value="worst",
                style={"color": _C["text_pri"]},
                inputStyle={"marginRight": "10px"},
                labelStyle={"display": "block", "marginBottom": "12px",
                            "padding": "10px 14px",
                            "backgroundColor": _C["bg_dark"],
                            "borderRadius": "8px",
                            "border": f"1px solid {_C['border']}"},
            ),
        ]),

        _card([
            _label("Thuật toán tự động — Ưu tiên bán mã nào?"),
            dbc.RadioItems(
                id="crisis-action-mode",
                options=[
                    {
                        "label": html.Div([
                            html.Span("Tùy chọn A: Bán mã chất lượng kém (VGM thấp)",
                                      style={"fontWeight": "700", "color": _C["text_pri"],
                                             "fontSize": "13px"}),
                            html.Br(),
                            html.Span("Ưu tiên bán mã điểm F/D trước. Giữ lại mã A/B chất lượng cao.",
                                      style={"fontSize": "11px", "color": _C["text_sec"]}),
                        ], style={"lineHeight": "1.8"}),
                        "value": "quality",
                    },
                    {
                        "label": html.Div([
                            html.Span("Tùy chọn B: Bán mã thanh khoản cao (chắc khớp hơn)",
                                      style={"fontWeight": "700", "color": _C["text_pri"],
                                             "fontSize": "13px"}),
                            html.Br(),
                            html.Span("Ưu tiên mã có Vol_vs_SMA20 cao — lệnh dễ khớp nhất.",
                                      style={"fontSize": "11px", "color": _C["text_sec"]}),
                        ], style={"lineHeight": "1.8"}),
                        "value": "liquidity",
                    },
                ],
                value="quality",
                style={"color": _C["text_pri"]},
                inputStyle={"marginRight": "10px"},
                labelStyle={"display": "block", "marginBottom": "10px",
                            "padding": "10px 14px",
                            "backgroundColor": _C["bg_dark"],
                            "borderRadius": "8px",
                            "border": f"1px solid {_C['border']}"},
            ),
        ]),

        dbc.Button([
            html.I(className="fas fa-play-circle", style={"marginRight": "8px"}),
            "Chạy Stress Test & Xuất Khuyến nghị",
        ], id="crisis-run-btn", color="danger", size="lg",
           style={
               "width": "100%", "borderRadius": "8px",
               "fontFamily": "'JetBrains Mono', monospace",
               "fontWeight": "800", "fontSize": "14px",
               "letterSpacing": "0.5px",
               "boxShadow": f"0 4px 20px {_C['red']}44",
           }),

        html.Div(id="crisis-run-error", style={
            "color": _C["amber"], "fontSize": "12px",
            "marginTop": "8px", "textAlign": "center"
        }),
    ], style={"padding": "4px"})


# ─────────────────────────────────────────────────────────────────────────────
# TAB 3 LAYOUT — Kết quả Backtest
# ─────────────────────────────────────────────────────────────────────────────

def _build_tab3():
    return html.Div([
        dcc.Loading(
            type="dot", color=_C["cyan"],
            children=[html.Div(id="crisis-result-panel", style={"minHeight": "200px"})],
        ),
    ], style={"padding": "4px"})


# ─────────────────────────────────────────────────────────────────────────────
# MAIN MODAL LAYOUT
# ─────────────────────────────────────────────────────────────────────────────

crisis_modal = dbc.Modal([
    dbc.ModalHeader(
        html.Div([
            html.I(className="fas fa-fire-flame-curved",
                   style={"color": _C["red"], "marginRight": "10px", "fontSize": "16px"}),
            html.Span("Margin Crisis Backtester", style={
                "fontWeight": "800", "fontSize": "15px",
                "color": _C["text_pri"],
                "fontFamily": "'JetBrains Mono', monospace",
            }),
            html.Span(" — Xử lý khủng hoảng & tránh Force Sell", style={
                "fontSize": "12px", "color": _C["text_sec"], "marginLeft": "10px"
            }),
        ], style={"display": "flex", "alignItems": "center"}),
        close_button=True,
    ),

    dbc.ModalBody([
        dbc.Tabs([
            dbc.Tab(
                label="① Danh mục Gốc",
                tab_id="crisis-tab-1",
                children=_build_tab1(),
                tab_style={"fontSize": "12px"},
            ),
            dbc.Tab(
                label="② Thiết lập Kịch bản",
                tab_id="crisis-tab-2",
                children=_build_tab2(),
                tab_style={"fontSize": "12px"},
            ),
            dbc.Tab(
                label="③ Kết quả & Hành động",
                tab_id="crisis-tab-3",
                children=_build_tab3(),
                tab_style={"fontSize": "12px"},
            ),
        ], id="crisis-tabs", active_tab="crisis-tab-1",
           style={"marginBottom": "16px"}),
    ], style={"backgroundColor": _C["bg_dark"], "minHeight": "520px"}),
], id="crisis-modal", size="xl", is_open=False, centered=True, scrollable=True,
   style={"fontFamily": "'Inter', sans-serif"})

# Store lưu trạng thái danh mục khủng hoảng (localStorage)
crisis_store = dcc.Store(id="crisis-portfolio-store", storage_type="local", data={
    "positions": [],
    "total_equity": None,
})

# Store lưu kết quả tính toán (memory)
crisis_result_store = dcc.Store(id="crisis-result-store", storage_type="memory", data=None)


# ─────────────────────────────────────────────────────────────────────────────
# CALLBACK: Mở modal
# ─────────────────────────────────────────────────────────────────────────────

@app.callback(
    Output("crisis-modal", "is_open"),
    Output("crisis-ticker-input", "options"),
    Input("btn-crisis", "n_clicks"),
    prevent_initial_call=True,
)
def open_crisis_modal(n):
    if not n:
        return no_update, no_update
    try:
        from src.backend.data_loader import get_ticker_list
        opts = get_ticker_list()
    except Exception:
        opts = []
    return True, opts


# ─────────────────────────────────────────────────────────────────────────────
# CALLBACK: Hiển thị số tiền vay tự động khi nhập qty + giá + tỷ lệ margin
# ─────────────────────────────────────────────────────────────────────────────

@app.callback(
    Output("crisis-loan-input", "value"),
    Output("crisis-loan-input", "placeholder"),
    Input("crisis-qty-input",         "value"),
    Input("crisis-cost-input",        "value"),
    Input("crisis-margin-rate-input", "value"),
    prevent_initial_call=True,
)
def auto_calc_loan(qty, cost, rate):
    try:
        q = float(qty or 0)
        c = float(cost or 0)
        r = float(rate or 0)
        if q > 0 and c > 0 and r > 0:
            market_val = q * c
            loan = market_val * (r / 100)
            return round(loan), _fmt_vnd(loan)
    except Exception:
        pass
    return None, "Tự động tính"


# ─────────────────────────────────────────────────────────────────────────────
# CALLBACK: Hiển thị vốn tự có dưới dạng text đọc được
# ─────────────────────────────────────────────────────────────────────────────

@app.callback(
    Output("crisis-equity-display", "children"),
    Input("crisis-equity-input", "value"),
    prevent_initial_call=True,
)
def show_equity_readable(val):
    if val is None:
        return ""
    try:
        return f"≈ {_fmt_vnd(float(val))}"
    except Exception:
        return ""


# ─────────────────────────────────────────────────────────────────────────────
# CALLBACK: Thêm vị thế vào store
# ─────────────────────────────────────────────────────────────────────────────

@app.callback(
    Output("crisis-portfolio-store", "data",   allow_duplicate=True),
    Output("crisis-ticker-input",    "value",  allow_duplicate=True),
    Output("crisis-qty-input",       "value",  allow_duplicate=True),
    Output("crisis-cost-input",      "value",  allow_duplicate=True),
    Output("crisis-margin-rate-input", "value", allow_duplicate=True),
    Output("crisis-loan-input",      "value",  allow_duplicate=True),
    Output("crisis-add-error",       "children"),
    Input("crisis-add-btn",          "n_clicks"),
    State("crisis-ticker-input",     "value"),
    State("crisis-qty-input",        "value"),
    State("crisis-cost-input",       "value"),
    State("crisis-margin-rate-input","value"),
    State("crisis-loan-input",       "value"),
    State("crisis-equity-input",     "value"),
    State("crisis-portfolio-store",  "data"),
    prevent_initial_call=True,
)
def add_crisis_position(n, ticker, qty, cost, margin_rate, loan, equity, store):
    if not n:
        return no_update, no_update, no_update, no_update, no_update, no_update, ""

    # Validation
    if not ticker:
        return no_update, no_update, no_update, no_update, no_update, no_update, "⚠ Vui lòng chọn mã cổ phiếu"
    if not qty or float(qty) <= 0:
        return no_update, no_update, no_update, no_update, no_update, no_update, "⚠ Khối lượng phải > 0"
    if not cost or float(cost) <= 0:
        return no_update, no_update, no_update, no_update, no_update, no_update, "⚠ Giá vốn phải > 0"

    store = store or {"positions": [], "total_equity": None}
    positions = store.get("positions", [])

    try:
        q = int(float(qty))
        c = float(cost)
        r = float(margin_rate or 0)
        lv = float(loan or 0) if loan else q * c * (r / 100)
    except ValueError:
        return no_update, no_update, no_update, no_update, no_update, no_update, "⚠ Giá trị không hợp lệ"

    # Update nếu đã có mã
    found = False
    for pos in positions:
        if pos["ticker"] == ticker:
            total_qty  = pos["qty"] + q
            pos["cost"] = (pos["cost"] * pos["qty"] + c * q) / total_qty
            pos["qty"]  = total_qty
            pos["margin_rate"] = r
            pos["loan_amount"] = pos.get("loan_amount", 0) + lv
            found = True
            break

    if not found:
        positions.append({
            "ticker":      ticker,
            "qty":         q,
            "cost":        c,
            "margin_rate": r,
            "loan_amount": lv,
        })

    # Lưu equity nếu có
    if equity:
        try:
            store["total_equity"] = float(equity)
        except Exception:
            pass

    store["positions"] = positions
    return store, None, None, None, 50, None, ""


# ─────────────────────────────────────────────────────────────────────────────
# CALLBACK: Xóa một vị thế
# ─────────────────────────────────────────────────────────────────────────────

@app.callback(
    Output("crisis-portfolio-store", "data", allow_duplicate=True),
    Input({"type": "crisis-remove-btn", "index": ALL}, "n_clicks"),
    State("crisis-portfolio-store", "data"),
    prevent_initial_call=True,
)
def remove_crisis_position(n_clicks_list, store):
    ctx = callback_context
    if not ctx.triggered or not any(n for n in (n_clicks_list or []) if n):
        return no_update
    triggered = ctx.triggered[0]["prop_id"].split(".")[0]
    try:
        ticker_to_rm = json.loads(triggered)["index"]
        store = store or {"positions": [], "total_equity": None}
        store["positions"] = [p for p in store["positions"] if p["ticker"] != ticker_to_rm]
    except Exception as e:
        logger.error(f"[Crisis] Remove error: {e}")
    return store


# ─────────────────────────────────────────────────────────────────────────────
# CALLBACK: Render bảng vị thế + tóm tắt Rtt hiện tại
# ─────────────────────────────────────────────────────────────────────────────

@app.callback(
    Output("crisis-positions-table", "children"),
    Output("crisis-rtt-summary",     "children"),
    Input("crisis-portfolio-store",  "data"),
    prevent_initial_call=False,
)
def render_positions_table(store):
    store = store or {"positions": [], "total_equity": None}
    positions = store.get("positions", [])

    if not positions:
        empty = html.Div([
            html.I(className="fas fa-fire-flame-curved",
                   style={"fontSize": "28px", "color": "#2a3a4a", "marginBottom": "8px"}),
            html.P("Chưa có vị thế — thêm mã cổ phiếu đang dùng margin ở trên",
                   style={"color": _C["text_mut"], "fontSize": "13px"}),
        ], style={"textAlign": "center", "padding": "30px",
                  "border": f"1px dashed {_C['border']}",
                  "borderRadius": "8px", "marginBottom": "14px"})
        return empty, []

    # Lấy giá hiện tại từ snapshot
    price_map = {}
    perf1w_map = {}
    vgm_map = {}
    vol_sma20_map = {}
    avg_vol_map = {}
    consec_down_map = {}
    canslim_map = {}

    try:
        from src.backend.data_loader import get_snapshot_df
        df_snap = get_snapshot_df()
        if df_snap is not None and not df_snap.empty:
            for _, row in df_snap.iterrows():
                t = str(row.get("Ticker", ""))
                price_map[t]       = float(row.get("Price Close", 0) or 0)
                perf1w_map[t]      = float(row.get("Perf_1W", 0) or 0)
                vgm_map[t]         = str(row.get("VGM Score", "F") or "F")
                vol_sma20_map[t]   = float(row.get("Vol_vs_SMA20", 1) or 1)
                avg_vol_map[t]     = float(row.get("Avg_Vol_20D", 0) or 0)
                consec_down_map[t] = int(row.get("Consec_Down", 0) or 0)
                canslim_map[t]     = int(row.get("CANSLIM Score", 0) or 0)
    except Exception as e:
        logger.warning(f"[Crisis] Snapshot load error: {e}")

    # Tính toán
    total_asset_value = 0.0
    total_loan        = 0.0
    rows_html = []

    GRADE_COLOR = {"A": _C["green"], "B": "#3b82f6",
                   "C": _C["amber"], "D": "#f97316", "F": _C["red"]}

    for pos in positions:
        ticker   = pos["ticker"]
        qty      = pos["qty"]
        cost     = pos["cost"]
        rate     = pos["margin_rate"]
        loan     = pos["loan_amount"]
        price_now = price_map.get(ticker, cost)

        asset_val  = qty * price_now
        unrealized = asset_val - qty * cost
        unr_pct    = (unrealized / (qty * cost) * 100) if cost > 0 else 0
        unr_color  = _C["green"] if unrealized >= 0 else _C["red"]

        total_asset_value += asset_val
        total_loan        += loan

        vgm        = vgm_map.get(ticker, "F")
        vol_ratio  = vol_sma20_map.get(ticker, 1)
        avg_vol    = avg_vol_map.get(ticker, 0)
        cd         = consec_down_map.get(ticker, 0)

        # Cảnh báo thanh khoản
        liq_warn = ""
        if qty > avg_vol * 0.5 and avg_vol > 0:
            liq_warn = " ⚠ Khó khớp"
        if rate == 0:
            liq_warn += " 🔴 Margin=0%"

        rows_html.append(html.Div([
            # Ticker + grade
            html.Div([
                html.Span(ticker, style={
                    "fontFamily": "'JetBrains Mono', monospace",
                    "fontWeight": "800", "color": _C["cyan"],
                    "fontSize": "13px", "marginRight": "6px",
                }),
                html.Span(vgm, style={
                    "fontSize": "10px", "fontWeight": "700",
                    "color": GRADE_COLOR.get(vgm, _C["red"]),
                    "backgroundColor": f"{GRADE_COLOR.get(vgm, _C['red'])}22",
                    "border": f"1px solid {GRADE_COLOR.get(vgm, _C['red'])}55",
                    "borderRadius": "3px", "padding": "1px 5px",
                }),
            ], style={"flex": "0 0 110px", "display": "flex", "alignItems": "center"}),

            # Khối lượng
            html.Span(f"{qty:,}", style={
                "flex": "0 0 80px", "textAlign": "right",
                "fontFamily": "'JetBrains Mono', monospace",
                "fontSize": "12px", "color": _C["text_sec"],
            }),

            # Giá hiện tại
            html.Span(f"{price_now:,.0f}", style={
                "flex": "0 0 90px", "textAlign": "right",
                "fontFamily": "'JetBrains Mono', monospace",
                "fontSize": "12px", "color": _C["amber"],
            }),

            # Giá trị tài sản
            html.Span(_fmt_vnd(asset_val), style={
                "flex": "0 0 100px", "textAlign": "right",
                "fontFamily": "'JetBrains Mono', monospace",
                "fontSize": "12px", "color": _C["text_pri"],
            }),

            # Lãi/lỗ unrealized
            html.Span(f"{'+' if unr_pct >= 0 else ''}{unr_pct:.1f}%", style={
                "flex": "0 0 70px", "textAlign": "right",
                "fontFamily": "'JetBrains Mono', monospace",
                "fontSize": "12px", "color": unr_color, "fontWeight": "700",
            }),

            # Margin rate
            html.Span(f"{rate:.0f}%", style={
                "flex": "0 0 60px", "textAlign": "right",
                "fontFamily": "'JetBrains Mono', monospace",
                "fontSize": "12px",
                "color": _C["red"] if rate == 0 else _C["text_sec"],
                "fontWeight": "700" if rate == 0 else "400",
            }),

            # Số tiền vay
            html.Span(_fmt_vnd(loan), style={
                "flex": "0 0 100px", "textAlign": "right",
                "fontFamily": "'JetBrains Mono', monospace",
                "fontSize": "12px", "color": _C["red"],
            }),

            # Cảnh báo + nút xóa
            html.Div([
                html.Span(liq_warn, style={
                    "fontSize": "10px", "color": _C["amber"],
                    "marginRight": "8px",
                }),
                html.I(
                    className="fas fa-times",
                    id={"type": "crisis-remove-btn", "index": ticker},
                    n_clicks=0,
                    style={"color": "#484f58", "cursor": "pointer",
                           "fontSize": "11px"},
                ),
            ], style={"flex": "1", "display": "flex", "alignItems": "center",
                      "justifyContent": "flex-end"}),

        ], style={
            "display": "flex", "alignItems": "center",
            "padding": "8px 12px",
            "borderBottom": f"1px solid {_C['bg_card2']}",
        }))

    # Header bảng
    header = html.Div([
        html.Span("MÃ",      style={"flex": "0 0 110px", "color": _C["text_mut"], "fontSize": "10px", "fontWeight": "700", "letterSpacing": "1px"}),
        html.Span("SL (CP)", style={"flex": "0 0 80px",  "color": _C["text_mut"], "fontSize": "10px", "fontWeight": "700", "textAlign": "right"}),
        html.Span("GIÁ HT",  style={"flex": "0 0 90px",  "color": _C["text_mut"], "fontSize": "10px", "fontWeight": "700", "textAlign": "right"}),
        html.Span("GIÁ TRỊ", style={"flex": "0 0 100px", "color": _C["text_mut"], "fontSize": "10px", "fontWeight": "700", "textAlign": "right"}),
        html.Span("L/L%",    style={"flex": "0 0 70px",  "color": _C["text_mut"], "fontSize": "10px", "fontWeight": "700", "textAlign": "right"}),
        html.Span("MARGIN",  style={"flex": "0 0 60px",  "color": _C["text_mut"], "fontSize": "10px", "fontWeight": "700", "textAlign": "right"}),
        html.Span("NỢ VAY",  style={"flex": "0 0 100px", "color": _C["text_mut"], "fontSize": "10px", "fontWeight": "700", "textAlign": "right"}),
        html.Span("",        style={"flex": "1"}),
    ], style={
        "display": "flex", "padding": "6px 12px",
        "backgroundColor": _C["bg_card2"],
        "borderRadius": "6px 6px 0 0",
    })

    table = html.Div([
        header,
        html.Div(rows_html, style={"backgroundColor": _C["bg_card"],
                                    "borderRadius": "0 0 6px 6px",
                                    "border": f"1px solid {_C['border']}",
                                    "borderTop": "none"}),
    ], style={"marginBottom": "14px"})

    # Tóm tắt Rtt
    rtt = (total_loan / total_asset_value * 100) if total_asset_value > 0 else 0
    rtt_color = _rtt_gauge_color(rtt)

    if rtt >= RTT_FORCE_SELL:
        rtt_status = "🔴 NGUY HIỂM — Sắp bị Force Sell!"
        rtt_status_color = _C["red"]
    elif rtt >= RTT_CALL_MARGIN:
        rtt_status = "🟠 CẢNH BÁO — Call Margin đang đến gần"
        rtt_status_color = _C["amber"]
    else:
        rtt_status = "🟢 AN TOÀN — Tỷ lệ ký quỹ trong ngưỡng"
        rtt_status_color = _C["green"]

    total_equity = store.get("total_equity")
    nav = (total_asset_value - total_loan)
    nav_str = _fmt_vnd(nav) if total_asset_value > 0 else "–"

    summary = _card([
        html.Div([
            # Rtt big number
            html.Div([
                html.Div("TỶ LỆ KÝ QUỸ (Rtt)", style={
                    "fontSize": "10px", "color": _C["text_mut"],
                    "letterSpacing": "1px", "fontFamily": "'JetBrains Mono', monospace",
                    "marginBottom": "4px",
                }),
                html.Div(f"{rtt:.1f}%", style={
                    "fontSize": "40px", "fontWeight": "900",
                    "color": rtt_color,
                    "fontFamily": "'JetBrains Mono', monospace",
                    "lineHeight": "1",
                    "textShadow": f"0 0 20px {rtt_color}66",
                }),
                html.Div(rtt_status, style={
                    "fontSize": "12px", "fontWeight": "700",
                    "color": rtt_status_color, "marginTop": "6px",
                }),
            ], style={"textAlign": "center", "flex": "1"}),

            # Divider
            html.Div(style={"width": "1px", "backgroundColor": _C["border"],
                            "margin": "0 20px", "alignSelf": "stretch"}),

            # Metrics
            html.Div([
                _metric_row("Tổng TS ký quỹ", _fmt_vnd(total_asset_value)),
                _metric_row("Tổng nợ vay", _fmt_vnd(total_loan), _C["red"]),
                _metric_row("NAV (Tài sản ròng)", nav_str,
                            _C["green"] if nav >= 0 else _C["red"]),
                _metric_row("Số mã đang ký quỹ", str(len(positions))),
            ], style={"flex": "2"}),
        ], style={"display": "flex", "alignItems": "center"}),
    ])

    return table, summary


def _metric_row(label, value, val_color=None):
    return html.Div([
        html.Span(label, style={"fontSize": "12px", "color": _C["text_sec"], "flex": "1"}),
        html.Span(value, style={
            "fontSize": "13px", "fontWeight": "700",
            "color": val_color or _C["text_pri"],
            "fontFamily": "'JetBrains Mono', monospace",
        }),
    ], style={"display": "flex", "justifyContent": "space-between",
              "alignItems": "center", "marginBottom": "8px"})


# ─────────────────────────────────────────────────────────────────────────────
# CALLBACK: Chạy Stress Test → sinh kết quả + khuyến nghị
# ─────────────────────────────────────────────────────────────────────────────

@app.callback(
    Output("crisis-result-store", "data"),
    Output("crisis-run-error",    "children"),
    Output("crisis-tabs",         "active_tab"),
    Input("crisis-run-btn",   "n_clicks"),
    State("crisis-portfolio-store", "data"),
    State("crisis-target-rtt",      "value"),
    State("crisis-scenario",        "value"),
    State("crisis-action-mode",     "value"),
    prevent_initial_call=True,
)
def run_stress_test(n, store, target_rtt, scenario, action_mode):
    if not n:
        return no_update, "", no_update

    store = store or {}
    positions = store.get("positions", [])
    if not positions:
        return no_update, "⚠ Chưa có vị thế nào trong danh mục — quay lại Tab 1 để nhập", no_update

    target_rtt = float(target_rtt or 40)

    # Lấy dữ liệu từ snapshot
    snap_data = {}
    try:
        from src.backend.data_loader import get_snapshot_df
        df_snap = get_snapshot_df()
        if df_snap is not None and not df_snap.empty:
            for _, row in df_snap.iterrows():
                t = str(row.get("Ticker", ""))
                snap_data[t] = {
                    "price":        float(row.get("Price Close", 0) or 0),
                    "perf_1w":      float(row.get("Perf_1W", 0) or 0),
                    "vgm":          str(row.get("VGM Score", "F") or "F"),
                    "canslim":      int(row.get("CANSLIM Score", 0) or 0),
                    "vol_sma20":    float(row.get("Vol_vs_SMA20", 1) or 1),
                    "avg_vol":      float(row.get("Avg_Vol_20D", 0) or 0),
                    "consec_down":  int(row.get("Consec_Down", 0) or 0),
                }
    except Exception as e:
        logger.error(f"[Crisis StressTest] Snapshot error: {e}")
        return no_update, f"❌ Lỗi đọc dữ liệu thị trường: {e}", no_update

    # ── Tính Rtt hiện tại ──
    total_asset_now = sum(
        pos["qty"] * snap_data.get(pos["ticker"], {}).get("price", pos["cost"])
        for pos in positions
    )
    total_loan = sum(pos["loan_amount"] for pos in positions)
    rtt_now = (total_loan / total_asset_now * 100) if total_asset_now > 0 else 0

    # ── Tính Rtt kịch bản T+1 ──
    enriched = []
    for pos in positions:
        t     = pos["ticker"]
        sd    = snap_data.get(t, {})
        price = sd.get("price", pos["cost"])

        if scenario == "worst":
            perf_1w = sd.get("perf_1w", 0)
            # Áp hiệu suất 1 tuần (âm) vào giá hôm nay
            price_t1 = price * (1 + min(perf_1w, 0) / 100)
        else:
            price_t1 = price

        asset_now  = pos["qty"] * price
        asset_t1   = pos["qty"] * price_t1
        loan       = pos["loan_amount"]
        margin_rate = pos["margin_rate"]
        vgm        = sd.get("vgm", "F")
        vol_sma20  = sd.get("vol_sma20", 1)
        avg_vol    = sd.get("avg_vol", 0)
        consec_down = sd.get("consec_down", 0)
        canslim    = sd.get("canslim", 0)

        # Khả năng khớp lệnh (0-100%)
        if avg_vol > 0:
            fill_prob = min(100, int(min(avg_vol, pos["qty"]) / pos["qty"] * 100))
        else:
            fill_prob = 30  # không có data → giả định 30%

        if margin_rate == 0:
            fill_prob = min(fill_prob, 50)  # mã bị cắt margin thường có thanh khoản kém

        enriched.append({
            **pos,
            "price_now":    price,
            "price_t1":     price_t1,
            "asset_now":    asset_now,
            "asset_t1":     asset_t1,
            "vgm":          vgm,
            "vol_sma20":    vol_sma20,
            "avg_vol":      avg_vol,
            "consec_down":  consec_down,
            "canslim":      canslim,
            "fill_prob":    fill_prob,
        })

    total_asset_t1 = sum(e["asset_t1"] for e in enriched)
    rtt_t1 = (total_loan / total_asset_t1 * 100) if total_asset_t1 > 0 else 0

    # ── Tính thiếu hụt margin ──
    # Để Rtt về target_rtt: asset_needed = total_loan / (target_rtt/100)
    asset_needed = total_loan / (target_rtt / 100) if target_rtt > 0 else 0
    # Tiền cần giải phóng = asset_t1 - asset_needed
    cash_needed  = max(0, total_loan - total_asset_t1 * (target_rtt / 100))

    # ── Thuật toán gợi ý BÁN ──
    VGM_SELL_SCORE = {"F": 5, "D": 4, "C": 3, "B": 2, "A": 1}

    if action_mode == "quality":
        # Sắp xếp theo: margin=0 trước, rồi VGM thấp, rồi consec_down nhiều
        def sort_key(e):
            vgm_score = VGM_SELL_SCORE.get(e["vgm"], 3)
            is_cut = 1 if e["margin_rate"] == 0 else 0
            return (-is_cut, -vgm_score, -e["consec_down"])
    else:
        # Sắp xếp theo thanh khoản cao nhất (dễ khớp nhất)
        def sort_key(e):
            is_cut = 1 if e["margin_rate"] == 0 else 0
            return (-is_cut, -e["vol_sma20"], -e["avg_vol"])

    sell_candidates = sorted(enriched, key=sort_key)

    # Tạo danh sách khuyến nghị
    recommendations = []
    cash_freed = 0.0
    asset_freed = 0.0

    for e in sell_candidates:
        if cash_freed >= cash_needed and cash_needed > 0:
            break
        if e["margin_rate"] == 0:
            action = "BÁN_NGAY"
            qty_sell = e["qty"]
            reason   = f"Margin bị cắt về 0% — ATO ngày mai sẽ Force Sell toàn bộ {e['ticker']}"
        elif cash_needed <= 0:
            action   = "GIỮ"
            qty_sell = 0
            reason   = f"Rtt hiện tại an toàn, không cần bán {e['ticker']}"
        else:
            # Tính số lượng cần bán để đủ margin
            remaining_cash = cash_needed - cash_freed
            qty_sell = min(e["qty"], int(remaining_cash / e["price_t1"]) + 1)
            qty_sell = max(100, qty_sell - (qty_sell % 100))  # làm tròn 100 CP
            if qty_sell >= e["qty"] * 0.9:
                qty_sell = e["qty"]
                action   = "BÁN_TOÀN_BỘ"
            else:
                action = "BÁN_MỘT_PHẦN"
            reason = f"Giải phóng ≈ {_fmt_vnd(qty_sell * e['price_t1'])} để đưa Rtt về {target_rtt:.0f}%"

        cash_freed  += qty_sell * e["price_t1"]
        asset_freed += qty_sell * e["price_t1"]

        recommendations.append({
            **e,
            "action":    action,
            "qty_sell":  qty_sell,
            "reason":    reason,
            "cash_freed": qty_sell * e["price_t1"],
        })

    # Thêm mã GIỮ vào recommendations
    sell_tickers = {r["ticker"] for r in recommendations if r["action"] != "GIỮ"}
    for e in enriched:
        if e["ticker"] not in sell_tickers:
            recommendations.append({
                **e,
                "action":    "GIỮ",
                "qty_sell":  0,
                "reason":    f"VGM={e['vgm']}, không ảnh hưởng margin — GIỮ lại",
                "cash_freed": 0,
            })

    # Tính Rtt sau khi thực hiện
    total_asset_after = total_asset_t1 - asset_freed
    rtt_after = (total_loan / total_asset_after * 100) if total_asset_after > 0 else 0

    result = {
        "rtt_now":       round(rtt_now, 2),
        "rtt_t1":        round(rtt_t1, 2),
        "rtt_after":     round(rtt_after, 2),
        "target_rtt":    target_rtt,
        "scenario":      scenario,
        "action_mode":   action_mode,
        "cash_needed":   cash_needed,
        "recommendations": recommendations,
        "total_asset_now": total_asset_now,
        "total_asset_t1":  total_asset_t1,
        "total_loan":      total_loan,
    }

    return result, "", "crisis-tab-3"


# ─────────────────────────────────────────────────────────────────────────────
# CALLBACK: Render kết quả Tab 3
# ─────────────────────────────────────────────────────────────────────────────

@app.callback(
    Output("crisis-result-panel", "children"),
    Input("crisis-result-store", "data"),
    prevent_initial_call=False,
)
def render_result_panel(result):
    if not result:
        return html.Div([
            html.I(className="fas fa-arrow-left",
                   style={"fontSize": "20px", "color": _C["text_mut"], "marginBottom": "8px"}),
            html.P("Quay lại Tab ② để thiết lập kịch bản và bấm \"Chạy Stress Test\"",
                   style={"color": _C["text_mut"], "fontSize": "13px"}),
        ], style={"textAlign": "center", "padding": "60px 20px"})

    rtt_now   = result["rtt_now"]
    rtt_t1    = result["rtt_t1"]
    rtt_after = result["rtt_after"]
    target    = result["target_rtt"]
    scenario  = result["scenario"]
    recs      = result["recommendations"]

    scenario_label = "Kịch bản: Sập hầm (Perf_1W tệ nhất)" if scenario == "worst" \
                     else "Kịch bản: Đi ngang"

    # ── Biểu đồ Rtt comparison ──
    fig = go.Figure()

    rtt_values  = [rtt_now, rtt_t1, rtt_after, target]
    rtt_labels  = ["Rtt Hiện tại", f"Rtt T+1\n({scenario_label})", "Rtt Sau xử lý", "Mục tiêu an toàn"]
    rtt_colors  = [
        _rtt_gauge_color(rtt_now),
        _rtt_gauge_color(rtt_t1),
        _rtt_gauge_color(rtt_after),
        _C["cyan"],
    ]

    fig.add_trace(go.Bar(
        x=rtt_labels, y=rtt_values,
        marker_color=rtt_colors,
        marker_line=dict(color=[_hex_to_rgba(c, 0.53) for c in rtt_colors], width=1.5),
        text=[f"{v:.1f}%" for v in rtt_values],
        textposition="outside",
        textfont=dict(
            color=rtt_colors,
            size=14, family="JetBrains Mono",
        ),
    ))

    # Đường Force Sell và Call Margin
    fig.add_hline(y=RTT_FORCE_SELL, line_color=_C["red"], line_dash="dash",
                  annotation_text=f"Force Sell ({RTT_FORCE_SELL:.0f}%)",
                  annotation_font=dict(color=_C["red"], size=11))
    fig.add_hline(y=RTT_CALL_MARGIN, line_color=_C["amber"], line_dash="dot",
                  annotation_text=f"Call Margin ({RTT_CALL_MARGIN:.0f}%)",
                  annotation_font=dict(color=_C["amber"], size=11))
    fig.add_hline(y=target, line_color=_C["cyan"], line_dash="longdash",
                  annotation_text=f"Mục tiêu ({target:.0f}%)",
                  annotation_font=dict(color=_C["cyan"], size=11))

    fig.update_layout(
        paper_bgcolor=_C["bg_dark"], plot_bgcolor=_C["bg_dark"],
        margin=dict(l=10, r=10, t=20, b=10),
        height=240,
        showlegend=False,
        yaxis=dict(
            range=[0, max(max(rtt_values) * 1.25, 80)],
            gridcolor="rgba(255,255,255,0.04)",
            ticksuffix="%",
            tickfont=dict(color=_C["text_mut"], size=10),
        ),
        xaxis=dict(
            tickfont=dict(color=_C["text_sec"], size=11),
            tickangle=0,
        ),
        bargap=0.35,
    )

    # ── Metric summary cards ──
    def _summary_card(label, value, color, sub=""):
        return html.Div([
            html.Div(label, style={
                "fontSize": "10px", "color": _C["text_mut"],
                "letterSpacing": "0.8px", "fontFamily": "'JetBrains Mono', monospace",
                "marginBottom": "6px", "textTransform": "uppercase",
            }),
            html.Div(value, style={
                "fontSize": "22px", "fontWeight": "900", "color": color,
                "fontFamily": "'JetBrains Mono', monospace",
                "textShadow": f"0 0 12px {color}55",
            }),
            html.Div(sub, style={
                "fontSize": "11px", "color": _C["text_mut"], "marginTop": "4px"
            }),
        ], style={
            "padding": "14px 16px",
            "backgroundColor": _C["bg_card"],
            "border": f"1px solid {color}33",
            "borderTop": f"2px solid {color}88",
            "borderRadius": "8px",
            "flex": "1",
        })

    summary_cards = html.Div([
        _summary_card("Rtt Hiện Tại",   f"{rtt_now:.1f}%",   _rtt_gauge_color(rtt_now)),
        _summary_card("Rtt T+1 (KBest)", f"{rtt_t1:.1f}%",  _rtt_gauge_color(rtt_t1)),
        _summary_card("Rtt Sau Xử Lý",  f"{rtt_after:.1f}%", _rtt_gauge_color(rtt_after),
                      f"Mục tiêu: {target:.0f}%"),
        _summary_card("Cần Giải Phóng", _fmt_vnd(result["cash_needed"]), _C["amber"]),
    ], style={"display": "flex", "gap": "10px", "marginBottom": "14px"})

    # ── Actionable Recommendation Text ──
    force_sell_tickers = [r["ticker"] for r in recs if r["action"] == "BÁN_NGAY"]
    sell_full_tickers  = [r["ticker"] for r in recs if r["action"] == "BÁN_TOÀN_BỘ"]
    sell_part_recs     = [r for r in recs if r["action"] == "BÁN_MỘT_PHẦN"]
    keep_tickers       = [r["ticker"] for r in recs if r["action"] == "GIỮ"]

    action_blocks = []

    if rtt_t1 >= RTT_FORCE_SELL:
        action_blocks.append(html.Div([
            html.Div("🔴 CẢNH BÁO KHẨN CẤP", style={
                "fontFamily": "'JetBrains Mono', monospace",
                "fontWeight": "900", "color": _C["red"],
                "fontSize": "13px", "letterSpacing": "1px", "marginBottom": "6px",
            }),
            html.P(
                f"Với kịch bản {scenario_label}, Rtt sẽ lên {rtt_t1:.1f}% "
                f"— vượt ngưỡng Force Sell {RTT_FORCE_SELL:.0f}%. "
                f"CTCK có thể bán giải chấp ATO ngày mai mà không cần thông báo.",
                style={"fontSize": "13px", "color": "#fca5a5", "lineHeight": "1.7", "margin": "0"}
            ),
        ], style={
            "backgroundColor": f"{_C['red']}11",
            "border": f"1px solid {_C['red']}44",
            "borderLeft": f"4px solid {_C['red']}",
            "borderRadius": "8px", "padding": "14px 16px", "marginBottom": "10px",
        }))

    # Khuyến nghị hành động lúc 14:15
    action_items = []

    if force_sell_tickers:
        action_items.append(html.Div([
            html.I(className="fas fa-exclamation-triangle",
                   style={"color": _C["red"], "marginRight": "8px"}),
            html.Span([
                html.Strong("Bán MP ngay toàn bộ: ", style={"color": _C["red"]}),
                html.Span(", ".join(force_sell_tickers), style={
                    "fontFamily": "'JetBrains Mono', monospace",
                    "fontWeight": "800", "color": _C["amber"],
                }),
                html.Span(" (Margin đã bị cắt về 0% — ngày mai bị Force Sell ATO)",
                          style={"color": _C["text_sec"], "fontSize": "12px", "marginLeft": "8px"}),
            ]),
        ], style={"marginBottom": "8px", "lineHeight": "1.6"}))

    if sell_full_tickers:
        action_items.append(html.Div([
            html.I(className="fas fa-arrow-down",
                   style={"color": _C["amber"], "marginRight": "8px"}),
            html.Span([
                html.Strong("Bán toàn bộ: ", style={"color": _C["amber"]}),
                html.Span(", ".join(sell_full_tickers), style={
                    "fontFamily": "'JetBrains Mono', monospace",
                    "fontWeight": "800", "color": _C["amber"],
                }),
            ]),
        ], style={"marginBottom": "8px", "lineHeight": "1.6"}))

    for r in sell_part_recs:
        liq_note = ""
        if r["fill_prob"] < 50:
            liq_note = f" ⚠ Thanh khoản thấp (~{r['fill_prob']:.0f}% khả năng khớp)"

        action_items.append(html.Div([
            html.I(className="fas fa-minus-circle",
                   style={"color": "#f97316", "marginRight": "8px"}),
            html.Span([
                html.Strong(f"Bán {r['qty_sell']:,} CP {r['ticker']}: ",
                            style={"color": "#f97316"}),
                html.Span(r["reason"],
                          style={"color": _C["text_sec"], "fontSize": "12px"}),
                html.Span(liq_note,
                          style={"color": _C["amber"], "fontSize": "11px", "marginLeft": "6px"}),
            ]),
        ], style={"marginBottom": "8px", "lineHeight": "1.6"}))

    if keep_tickers:
        action_items.append(html.Div([
            html.I(className="fas fa-shield-check",
                   style={"color": _C["green"], "marginRight": "8px"}),
            html.Span([
                html.Strong("Giữ nguyên: ", style={"color": _C["green"]}),
                html.Span(", ".join(keep_tickers), style={
                    "fontFamily": "'JetBrains Mono', monospace",
                    "color": _C["text_pri"],
                }),
                html.Span(" (VGM tốt, không cần giải chấp)",
                          style={"color": _C["text_sec"], "fontSize": "12px", "marginLeft": "8px"}),
            ]),
        ], style={"marginBottom": "8px", "lineHeight": "1.6"}))

    action_blocks.append(html.Div([
        html.Div("🟢 HÀNH ĐỘNG KHUYẾN NGHỊ LÚC 14:15 HÔM NAY", style={
            "fontFamily": "'JetBrains Mono', monospace",
            "fontWeight": "900", "color": _C["green"],
            "fontSize": "12px", "letterSpacing": "1px", "marginBottom": "12px",
        }),
        html.Div(action_items),
    ], style={
        "backgroundColor": f"{_C['green']}08",
        "border": f"1px solid {_C['green']}33",
        "borderLeft": f"4px solid {_C['green']}",
        "borderRadius": "8px", "padding": "14px 16px", "marginBottom": "10px",
    }))

    # ── Bảng chi tiết từng mã ──
    ACTION_META = {
        "BÁN_NGAY":      ("🔴 BÁN NGAY",      _C["red"]),
        "BÁN_TOÀN_BỘ":  ("🟠 BÁN TOÀN BỘ",   _C["amber"]),
        "BÁN_MỘT_PHẦN": ("🟡 BÁN GIẢM",       "#f97316"),
        "GIỮ":           ("🟢 GIỮ",            _C["green"]),
    }

    detail_rows = []
    for r in sorted(recs, key=lambda x: ["BÁN_NGAY","BÁN_TOÀN_BỘ","BÁN_MỘT_PHẦN","GIỮ"].index(x["action"])):
        action_label, action_color = ACTION_META.get(r["action"], ("–", _C["text_mut"]))

        detail_rows.append(html.Div([
            html.Span(r["ticker"], style={
                "flex": "0 0 80px",
                "fontFamily": "'JetBrains Mono', monospace",
                "fontWeight": "800", "color": _C["cyan"], "fontSize": "13px",
            }),
            html.Span(action_label, style={
                "flex": "0 0 130px",
                "fontFamily": "'JetBrains Mono', monospace",
                "fontWeight": "700", "color": action_color, "fontSize": "12px",
            }),
            html.Span(f"{r['qty_sell']:,} CP" if r["qty_sell"] > 0 else "—", style={
                "flex": "0 0 90px", "textAlign": "right",
                "fontFamily": "'JetBrains Mono', monospace",
                "fontSize": "12px", "color": _C["text_sec"],
            }),
            html.Span(_fmt_vnd(r["cash_freed"]) if r["cash_freed"] > 0 else "—", style={
                "flex": "0 0 100px", "textAlign": "right",
                "fontFamily": "'JetBrains Mono', monospace",
                "fontSize": "12px", "color": _C["amber"],
            }),
            html.Span(f"{r['fill_prob']:.0f}%", style={
                "flex": "0 0 70px", "textAlign": "right",
                "fontFamily": "'JetBrains Mono', monospace",
                "fontSize": "12px",
                "color": _C["green"] if r["fill_prob"] >= 70 else
                         (_C["amber"] if r["fill_prob"] >= 40 else _C["red"]),
            }),
            html.Span(r["reason"][:55] + "…" if len(r["reason"]) > 55 else r["reason"], style={
                "flex": "1", "fontSize": "11px", "color": _C["text_mut"],
                "marginLeft": "10px",
            }),
        ], style={
            "display": "flex", "alignItems": "center",
            "padding": "8px 12px",
            "borderBottom": f"1px solid {_C['bg_card2']}",
        }))

    detail_header = html.Div([
        html.Span("MÃ",          style={"flex": "0 0 80px",  "color": _C["text_mut"], "fontSize": "10px", "fontWeight": "700", "letterSpacing": "1px"}),
        html.Span("HÀNH ĐỘNG",   style={"flex": "0 0 130px", "color": _C["text_mut"], "fontSize": "10px", "fontWeight": "700"}),
        html.Span("SL BÁN",      style={"flex": "0 0 90px",  "color": _C["text_mut"], "fontSize": "10px", "fontWeight": "700", "textAlign": "right"}),
        html.Span("TIỀN VỀ",     style={"flex": "0 0 100px", "color": _C["text_mut"], "fontSize": "10px", "fontWeight": "700", "textAlign": "right"}),
        html.Span("KN KHỚP",     style={"flex": "0 0 70px",  "color": _C["text_mut"], "fontSize": "10px", "fontWeight": "700", "textAlign": "right"}),
        html.Span("LÝ DO",       style={"flex": "1",         "color": _C["text_mut"], "fontSize": "10px", "fontWeight": "700", "marginLeft": "10px"}),
    ], style={
        "display": "flex", "padding": "6px 12px",
        "backgroundColor": _C["bg_card2"],
        "borderRadius": "6px 6px 0 0",
    })

    detail_table = html.Div([
        detail_header,
        html.Div(detail_rows, style={
            "backgroundColor": _C["bg_card"],
            "borderRadius": "0 0 6px 6px",
            "border": f"1px solid {_C['border']}",
            "borderTop": "none",
        }),
    ], style={"marginBottom": "14px"})

    # ── Disclaimer ──
    disclaimer = html.Div([
        html.I(className="fas fa-circle-exclamation",
               style={"color": _C["amber"], "marginRight": "8px", "fontSize": "11px"}),
        html.Span(
            "Mọi khuyến nghị dựa trên dữ liệu lịch sử và chỉ mang tính tham khảo. "
            "Xác nhận Margin Rate thực tế với CTCK trước khi thực hiện lệnh.",
            style={"fontSize": "11px", "color": "#7d6608", "lineHeight": "1.5"}
        ),
    ], style={
        "backgroundColor": "rgba(245,158,11,0.07)",
        "border": "1px solid rgba(245,158,11,0.2)",
        "borderRadius": "6px", "padding": "10px 14px",
    })

    return html.Div([
        html.Div([
            dcc.Graph(figure=fig, config={"displayModeBar": False},
                      style={"height": "240px"}),
        ], style={
            "backgroundColor": _C["bg_card"],
            "border": f"1px solid {_C['border']}",
            "borderRadius": "10px",
            "marginBottom": "14px",
            "overflow": "hidden",
        }),
        summary_cards,
        *action_blocks,
        detail_table,
        disclaimer,
    ])