# src/callbacks/alert_callbacks.py
"""
Alert System — cảnh báo khi cổ phiếu thỏa điều kiện đã set.
Lưu alerts vào localStorage. Check mỗi lần mở app hoặc theo interval.
"""
from dash import Input, Output, State, html, dcc, no_update, callback_context, ALL
from src.app_instance import app
import dash_bootstrap_components as dbc
import pandas as pd
import json
import logging

logger = logging.getLogger(__name__)

# ── Alert conditions available ──
ALERT_CONDITIONS = [
    {"label": "Giá vượt trên",          "value": "price_above"},
    {"label": "Giá xuống dưới",         "value": "price_below"},
    {"label": "RSI vào vùng Oversold (<30)", "value": "rsi_oversold"},
    {"label": "RSI vào vùng Overbought (>70)", "value": "rsi_overbought"},
    {"label": "Giá vượt SMA 20",        "value": "price_cross_sma20"},
    {"label": "Giá phá đáy SMA 20",     "value": "price_below_sma20"},
    {"label": "Giá vượt SMA 200",       "value": "price_cross_sma200"},
    {"label": "Volume tăng đột biến (>3x SMA20)", "value": "volume_spike"},
    {"label": "VGM Score = A",          "value": "vgm_a"},
    {"label": "CANSLIM Score ≥ 5",      "value": "canslim_5"},
    {"label": "% thay đổi 1 tuần > X%", "value": "perf_1w_above"},
]

# ── Alert Modal Layout ──
alert_modal = dbc.Modal([
    dbc.ModalHeader(
        dbc.ModalTitle([
            html.I(className="fas fa-bell", style={"marginRight": "8px", "color": "#f59e0b"}),
            "Cảnh báo cổ phiếu",
        ]),
        close_button=True,
    ),
    dbc.ModalBody([
        # Form tạo alert
        html.Div([
            html.Div([
                html.Label("Mã CK", style={"fontSize":"11px","color":"#7fa8cc","marginBottom":"4px"}),
                dcc.Dropdown(
                    id="alert-ticker-select",
                    options=[],
                    placeholder="Chọn mã...",
                    className="ssi-dropdown-custom",
                ),
            ], style={"flex":"1"}),
            html.Div([
                html.Label("Điều kiện", style={"fontSize":"11px","color":"#7fa8cc","marginBottom":"4px"}),
                dcc.Dropdown(
                    id="alert-condition-select",
                    options=ALERT_CONDITIONS,
                    placeholder="Chọn điều kiện...",
                    className="ssi-dropdown-custom",
                ),
            ], style={"flex":"2"}),
            html.Div([
                html.Label("Giá trị", style={"fontSize":"11px","color":"#7fa8cc","marginBottom":"4px"}),
                dcc.Input(
                    id="alert-value-input",
                    type="number", placeholder="Không bắt buộc",
                    style={
                        "width":"100%","padding":"7px 10px",
                        "backgroundColor":"#0d1117","color":"#c9d1d9",
                        "border":"1px solid #30363d","borderRadius":"6px",
                        "fontSize":"12px","outline":"none",
                    },
                ),
            ], style={"flex":"1"}),
            html.Div([
                html.Label(" ", style={"fontSize":"11px","color":"transparent","marginBottom":"4px"}),
                dbc.Button(
                    [html.I(className="fas fa-bell-plus", style={"marginRight":"5px"}), "Thêm"],
                    id="alert-add-btn", color="warning", size="sm",
                    style={"width":"100%","borderRadius":"6px"},
                ),
            ], style={"flex":"0 0 80px"}),
        ], style={"display":"flex","gap":"10px","alignItems":"flex-end",
                  "padding":"12px","backgroundColor":"#161b22",
                  "borderRadius":"8px","border":"1px solid #21262d","marginBottom":"14px"}),

        # Danh sách alerts hiện có
        html.Div(id="alert-list"),

        # Thông báo alerts đang kích hoạt
        html.Div(id="alert-triggered-list", style={"marginTop":"12px"}),

    ], style={"backgroundColor":"#0c1220"}),
], id="alert-modal", size="lg", is_open=False, centered=True, scrollable=True)

alert_store = dcc.Store(id="alert-store", storage_type="local", data=[])
alert_interval = dcc.Interval(id="alert-check-interval", interval=5*60*1000, n_intervals=0)  # 5 phút


@app.callback(
    Output("alert-ticker-select", "options"),
    Input("alert-modal", "is_open"),
    prevent_initial_call=True,
)
def load_alert_tickers(is_open):
    if not is_open: return no_update
    try:
        from src.backend.data_loader import get_ticker_list
        return get_ticker_list()
    except Exception:
        return []


@app.callback(
    Output("alert-store",          "data",  allow_duplicate=True),
    Output("alert-ticker-select",  "value"),
    Output("alert-condition-select","value"),
    Output("alert-value-input",    "value"),
    Input("alert-add-btn",         "n_clicks"),
    State("alert-ticker-select",   "value"),
    State("alert-condition-select","value"),
    State("alert-value-input",     "value"),
    State("alert-store",           "data"),
    prevent_initial_call=True,
)
def add_alert(n, ticker, condition, val, current):
    if not n or not ticker or not condition:
        return no_update, no_update, no_update, no_update
    current = current or []
    import time
    current.append({
        "id":        str(int(time.time() * 1000)),
        "ticker":    ticker,
        "condition": condition,
        "value":     float(val) if val else None,
        "triggered": False,
        "created":   pd.Timestamp.now().strftime("%d/%m/%Y %H:%M"),
    })
    return current, None, None, None


@app.callback(
    Output("alert-store", "data", allow_duplicate=True),
    Input({"type":"alert-remove-btn","index":ALL}, "n_clicks"),
    State("alert-store", "data"),
    prevent_initial_call=True,
)
def remove_alert(n_clicks_list, current):
    ctx = callback_context
    if not ctx.triggered or not any(n_clicks_list):
        return no_update
    triggered = ctx.triggered[0]["prop_id"]
    try:
        alert_id = json.loads(triggered.split(".")[0])["index"]
        current  = [a for a in (current or []) if a["id"] != alert_id]
    except Exception:
        pass
    return current


@app.callback(
    Output("alert-list",           "children"),
    Output("alert-triggered-list", "children"),
    Output("alert-store",          "data",     allow_duplicate=True),
    Input("alert-store",           "data"),
    Input("alert-check-interval",  "n_intervals"),
    prevent_initial_call='initial_duplicate',
)
def render_and_check_alerts(alerts, _intervals):
    alerts = alerts or []

    # ── Check conditions ──
    triggered_now = []
    try:
        from src.backend.data_loader import get_snapshot_df
        records = get_snapshot_df().to_dict("records")
        snap    = {r["Ticker"]: r for r in (records or [])}

        for alert in alerts:
            ticker = alert["ticker"]
            rec    = snap.get(ticker, {})
            if not rec:
                continue

            cond  = alert["condition"]
            val   = alert.get("value")
            price = float(rec.get("Price Close") or 0)
            rsi   = float(rec.get("RSI_14") or 50)
            vol_r = float(rec.get("Vol_vs_SMA20") or 1)
            sma20 = float(rec.get("_sma20") or price)
            sma200= float(rec.get("_sma200") or price)
            vgm   = rec.get("VGM Score", "")
            canslim=float(rec.get("CANSLIM Score") or 0)
            p1w   = float(rec.get("Perf_1W") or 0)

            hit = False
            if   cond == "price_above"        and val and price >= val:   hit = True
            elif cond == "price_below"        and val and price <= val:   hit = True
            elif cond == "rsi_oversold"       and rsi < 30:               hit = True
            elif cond == "rsi_overbought"     and rsi > 70:               hit = True
            elif cond == "price_cross_sma20"  and price > sma20:          hit = True
            elif cond == "price_below_sma20"  and price < sma20:          hit = True
            elif cond == "price_cross_sma200" and price > sma200:         hit = True
            elif cond == "volume_spike"       and vol_r >= 3:             hit = True
            elif cond == "vgm_a"              and vgm == "A":             hit = True
            elif cond == "canslim_5"          and canslim >= 5:           hit = True
            elif cond == "perf_1w_above"      and val and p1w >= val:     hit = True

            if hit and not alert.get("triggered"):
                alert["triggered"]     = True
                alert["triggered_at"]  = pd.Timestamp.now().strftime("%d/%m %H:%M")
                triggered_now.append(alert)

    except Exception as e:
        logger.warning(f"Alert check error: {e}")

    # ── Render danh sách alerts ──
    def cond_label(cond):
        return next((o["label"] for o in ALERT_CONDITIONS if o["value"] == cond), cond)

    if not alerts:
        list_html = html.Div([
            html.I(className="fas fa-bell-slash",
                   style={"fontSize":"24px","color":"#30363d","marginBottom":"6px"}),
            html.P("Chưa có cảnh báo nào — thêm điều kiện để theo dõi",
                   style={"color":"#484f58","fontSize":"12px"}),
        ], style={"textAlign":"center","padding":"20px"})
    else:
        rows = []
        for a in alerts:
            is_hit = a.get("triggered", False)
            color  = "#f59e0b" if is_hit else "#484f58"
            icon   = "fas fa-bell" if is_hit else "fas fa-bell-slash"
            rows.append(html.Div([
                html.I(className=icon, style={"color":color,"fontSize":"12px","marginRight":"8px","flexShrink":"0"}),
                html.Span(a["ticker"], style={"color":"#3b82f6","fontWeight":"700","fontSize":"12px","marginRight":"8px","minWidth":"60px"}),
                html.Span(cond_label(a["condition"]),
                          style={"color":"#c9d1d9","fontSize":"11px","flex":"1"}),
                html.Span(f"= {a['value']}" if a.get("value") else "",
                          style={"color":"#7fa8cc","fontSize":"11px","marginRight":"8px"}),
                html.Span(
                    f"✓ {a.get('triggered_at','')}" if is_hit else a.get("created",""),
                    style={"color":color,"fontSize":"10px","marginRight":"8px","whiteSpace":"nowrap"}
                ),
                html.I(className="fas fa-times",
                       id={"type":"alert-remove-btn","index":a["id"]},
                       n_clicks=0,
                       style={"color":"#484f58","cursor":"pointer","fontSize":"11px"}),
            ], style={
                "display":"flex","alignItems":"center","padding":"7px 10px",
                "borderBottom":"1px solid #0e2540",
                "backgroundColor":"rgba(245,158,11,0.05)" if is_hit else "transparent",
            }))
        list_html = html.Div(rows, style={
            "backgroundColor":"#0d1117","borderRadius":"8px",
            "border":"1px solid #21262d","overflow":"hidden",
        })

    # ── Render triggered notifications ──
    if triggered_now:
        notifs = html.Div([
            html.Div([
                html.I(className="fas fa-exclamation-triangle",
                       style={"color":"#f59e0b","marginRight":"8px"}),
                html.Span("Cảnh báo mới kích hoạt:",
                          style={"color":"#f59e0b","fontWeight":"700","fontSize":"12px"}),
            ], style={"marginBottom":"6px"}),
            *[html.Div(
                f"🔔 {a['ticker']} — {cond_label(a['condition'])}",
                style={"color":"#c9d1d9","fontSize":"12px","padding":"4px 0",
                       "borderBottom":"1px solid #21262d"}
              ) for a in triggered_now],
        ], style={
            "padding":"10px 12px","backgroundColor":"rgba(245,158,11,0.08)",
            "border":"1px solid rgba(245,158,11,0.3)","borderRadius":"8px",
        })
    else:
        notifs = []

    return list_html, notifs, alerts


@app.callback(
    Output("alert-modal", "is_open"),
    Input("btn-alerts",   "n_clicks"),
    prevent_initial_call=True,
)
def open_alert_modal(n):
    return True if n else no_update


# Badge số alerts đang kích hoạt
@app.callback(
    Output("alert-badge", "children"),
    Output("alert-badge", "style"),
    Input("alert-store",  "data"),
    prevent_initial_call=False,
)
def update_alert_badge(alerts):
    n = sum(1 for a in (alerts or []) if a.get("triggered"))
    base = {
        "position":"absolute","top":"-6px","right":"-6px",
        "fontSize":"9px","fontWeight":"700",
        "backgroundColor":"#ef4444","color":"white",
        "borderRadius":"10px","padding":"1px 5px",
        "minWidth":"16px","textAlign":"center",
    }
    if n > 0:
        return str(n), base
    return "", {**base, "display":"none"}