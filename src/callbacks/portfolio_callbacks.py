# src/callbacks/portfolio_callbacks.py
"""
Portfolio Tracker — lưu danh mục đầu tư vào localStorage.
Tính lời/lỗ theo giá hiện tại từ snapshot, so sánh với JCI.
"""
from dash import Input, Output, State, html, dcc, no_update, callback_context, ALL
from src.app_instance import app
import dash_bootstrap_components as dbc
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import logging, json

logger = logging.getLogger(__name__)

# ── Portfolio Modal Layout ──
portfolio_modal = dbc.Modal([
    dbc.ModalHeader(
        dbc.ModalTitle([
            html.I(className="fas fa-briefcase", style={"marginRight": "8px", "color": "#f59e0b"}),
            "Danh mục đầu tư",
        ]),
        close_button=True,
    ),
    dbc.ModalBody([
        # Form thêm vị thế
        html.Div([
            dcc.Dropdown(
                id="portfolio-ticker-input",
                options=[],
                placeholder="Mã cổ phiếu...",
                className="ssi-dropdown-custom",
                style={"flex": "1"},
            ),
            dcc.Input(
                id="portfolio-qty-input",
                type="number", placeholder="Số lượng (CP)",
                min=1, step=1,
                style={
                    "width": "130px", "padding": "6px 10px",
                    "backgroundColor": "#0d1117", "color": "#c9d1d9",
                    "border": "1px solid #30363d", "borderRadius": "6px",
                    "fontSize": "12px", "outline": "none",
                },
            ),
            html.Div([
                dcc.Input(
                    id="portfolio-price-input",
                    type="number", placeholder="Giá mua (VND)",
                    min=1,
                    style={
                        "width": "150px", "padding": "6px 10px",
                        "backgroundColor": "#0d1117", "color": "#c9d1d9",
                        "border": "1px solid #30363d", "borderRadius": "6px",
                        "fontSize": "12px", "outline": "none",
                    },
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
        ], style={"display": "flex", "gap": "8px", "alignItems": "center",
                  "marginBottom": "16px", "padding": "10px",
                  "backgroundColor": "#161b22", "borderRadius": "8px",
                  "border": "1px solid #21262d"}),

        # Bảng danh mục
        html.Div(id="portfolio-table", style={"marginBottom": "16px"}),

        # Summary cards
        html.Div(id="portfolio-summary"),

        # Chart so sánh với JCI — ẩn khi chưa có cổ phiếu
        html.Div(id="portfolio-chart-wrapper", children=[
            dcc.Graph(id="portfolio-chart",
                      style={"height": "280px"},
                      config={"displayModeBar": False}),
        ], style={"display": "none"}),  # hiện/ẩn qua callback

    ], style={"backgroundColor": "#0c1220"}),
], id="portfolio-modal", size="xl", is_open=False, centered=True, scrollable=True)

# Store lưu danh mục (localStorage)
portfolio_store = dcc.Store(id="portfolio-store", storage_type="local", data=[])


def _fmt_idr(v):
    try:
        v = float(v)
        if abs(v) >= 1e12: return f"{v/1e12:.2f}T"
        if abs(v) >= 1e9:  return f"{v/1e9:.1f}B"
        if abs(v) >= 1e6:  return f"{v/1e6:.1f}M"
        return f"{int(v):,}"
    except Exception:
        return "–"


@app.callback(
    Output("portfolio-ticker-input", "options"),
    Input("portfolio-modal",         "is_open"),
    prevent_initial_call=True,
)
def load_portfolio_tickers(is_open):
    if not is_open: return no_update
    try:
        from src.backend.data_loader import get_ticker_list
        return get_ticker_list()
    except Exception:
        return []


# ── Auto-fill giá tham chiếu khi chọn mã ────────────────────────────────────
@app.callback(
    Output("portfolio-price-input", "value", allow_duplicate=True),
    Input("portfolio-ticker-input", "value"),
    prevent_initial_call=True,
)
def autofill_ref_price(ticker):
    if not ticker: return no_update
    try:
        from src.backend.data_loader import get_snapshot_df
        records = get_snapshot_df().to_dict("records")
        snap    = {r["Ticker"]: r for r in (records or [])}
        price   = snap.get(ticker, {}).get("Price Close")
        if price is not None:
            return round(float(price))
    except Exception:
        pass
    return no_update


# ── Cảnh báo khi giá nhập vượt biên độ IDX ±35% ────────────────────────────
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
        records = get_snapshot_df().to_dict("records")
        snap    = {r["Ticker"]: r for r in (records or [])}
        ref     = float(snap.get(ticker, {}).get("Price Close") or 0)
        if ref <= 0:
            return "", hide
        ratio = float(price_val) / ref
        if ratio > 1.15:
            return f"⚠ Cao hơn giá tham chiếu {(ratio-1)*100:.1f}% — vượt biên độ ±15%", show
        if ratio < 0.85:
            return f"⚠ Thấp hơn giá tham chiếu {(1-ratio)*100:.1f}% — vượt biên độ ±15%", show
    except Exception:
        pass
    return "", hide


@app.callback(
    Output("portfolio-store",  "data",    allow_duplicate=True),
    Output("portfolio-ticker-input", "value"),
    Output("portfolio-qty-input",    "value"),
    Output("portfolio-price-input",  "value", allow_duplicate=True),
    Input("portfolio-add-btn", "n_clicks"),
    State("portfolio-ticker-input", "value"),
    State("portfolio-qty-input",    "value"),
    State("portfolio-price-input",  "value"),
    State("portfolio-store",        "data"),
    prevent_initial_call=True,
)
def add_portfolio_position(n, ticker, qty, price, current):
    if not n or not ticker or not qty or not price:
        return no_update, no_update, no_update, no_update
    current = current or []
    # Update nếu mã đã có
    for pos in current:
        if pos["ticker"] == ticker:
            pos["qty"]   += int(qty)
            pos["cost"]   = (pos["cost"] * (pos["qty"] - int(qty)) + float(price) * int(qty)) / pos["qty"]
            return current, None, None, None
    current.append({"ticker": ticker, "qty": int(qty), "cost": float(price)})
    return current, None, None, None


@app.callback(
    Output("portfolio-store", "data", allow_duplicate=True),
    Input({"type": "portfolio-remove-btn", "index": ALL}, "n_clicks"),
    State("portfolio-store", "data"),
    prevent_initial_call=True,
)
def remove_portfolio_position(n_clicks_list, current):
    ctx = callback_context
    if not ctx.triggered or not any(n_clicks_list):
        return no_update
    triggered = ctx.triggered[0]["prop_id"]
    try:
        idx = json.loads(triggered.split(".")[0])["index"]
        current = [p for p in (current or []) if p["ticker"] != idx]
    except Exception:
        pass
    return current


@app.callback(
    Output("portfolio-table",          "children"),
    Output("portfolio-summary",        "children"),
    Output("portfolio-chart",          "figure"),
    Output("portfolio-chart-wrapper",  "style"),   # ← ẩn/hiện wrapper thay vì chart trực tiếp
    Input("portfolio-store",           "data"),
    prevent_initial_call=False,
)
def render_portfolio(positions):
    positions = positions or []

    # ── Empty state: watermark mờ, KHÔNG render chart rỗng ──
    if not positions:
        empty = html.Div([
            html.I(className="fas fa-briefcase",
                   style={"fontSize": "40px", "color": "#1e3a5f", "marginBottom": "12px"}),
            html.P("Danh mục của bạn đang trống",
                   style={"color": "#3d6a8a", "fontSize": "14px", "fontWeight": "600",
                          "marginBottom": "4px"}),
            html.P("Hãy thêm cổ phiếu ở ô bên trên để bắt đầu theo dõi lợi nhuận",
                   style={"color": "#2a4d6e", "fontSize": "12px"}),
        ], style={"textAlign": "center", "padding": "50px 20px",
                  "border": "1px dashed #1e3a5f", "borderRadius": "8px",
                  "backgroundColor": "rgba(9,21,38,0.4)", "marginBottom": "16px"})
        return empty, [], go.Figure(), {"display": "none"}

    try:
        from src.backend.data_loader import get_snapshot_df, load_market_data, load_index_data
        records  = get_snapshot_df().to_dict("records")
        snap     = {r["Ticker"]: r for r in (records or [])}
        df_price = load_market_data()
        df_index = load_index_data()

        total_cost   = 0
        total_value  = 0
        table_rows   = []
        chart_data   = {}

        for pos in positions:
            ticker  = pos["ticker"]
            qty     = pos["qty"]
            cost_px = pos["cost"]
            rec     = snap.get(ticker, {})
            cur_px  = float(rec.get("Price Close", cost_px) or cost_px)

            pos_cost  = cost_px * qty
            pos_val   = cur_px  * qty
            pos_pnl   = pos_val - pos_cost
            pos_pnl_p = (pos_pnl / pos_cost * 100) if pos_cost else 0

            total_cost  += pos_cost
            total_value += pos_val

            color = "#10b981" if pos_pnl >= 0 else "#ef4444"
            sign  = "+" if pos_pnl >= 0 else ""

            table_rows.append(html.Div([
                html.Span(ticker,               style={"flex":"0 0 80px","color":"#3b82f6","fontWeight":"700","fontSize":"13px"}),
                html.Span(f"{qty:,}",           style={"flex":"0 0 70px","color":"#c9d1d9","fontSize":"12px","textAlign":"right"}),
                html.Span(_fmt_idr(cost_px),    style={"flex":"0 0 90px","color":"#7fa8cc","fontSize":"12px","textAlign":"right"}),
                html.Span(_fmt_idr(cur_px),     style={"flex":"0 0 90px","color":"#c9d1d9","fontSize":"12px","textAlign":"right"}),
                html.Span(_fmt_idr(pos_val),    style={"flex":"0 0 100px","color":"#c9d1d9","fontSize":"12px","textAlign":"right"}),
                html.Span(f"{sign}{pos_pnl_p:.2f}%", style={"flex":"0 0 90px","color":color,"fontSize":"12px","textAlign":"right","fontWeight":"700"}),
                html.Span(_fmt_idr(pos_pnl),    style={"flex":"0 0 100px","color":color,"fontSize":"12px","textAlign":"right"}),
                html.I(className="fas fa-times",
                       id={"type":"portfolio-remove-btn","index":ticker},
                       n_clicks=0,
                       style={"color":"#484f58","cursor":"pointer","fontSize":"12px","marginLeft":"8px"}),
            ], style={"display":"flex","alignItems":"center","padding":"7px 10px",
                      "borderBottom":"1px solid #0e2540"}))

            # Lịch sử giá cho chart
            df_t = df_price[df_price["Ticker"] == ticker].sort_values("Date").tail(252)
            if not df_t.empty:
                chart_data[ticker] = df_t.set_index("Date")["Price Close"]

        # Header bảng
        header = html.Div([
            html.Span("Mã",        style={"flex":"0 0 80px","color":"#7fa8cc","fontWeight":"600","fontSize":"11px"}),
            html.Span("SL (CP)",   style={"flex":"0 0 70px","color":"#7fa8cc","fontWeight":"600","fontSize":"11px","textAlign":"right"}),
            html.Span("Giá mua",   style={"flex":"0 0 90px","color":"#7fa8cc","fontWeight":"600","fontSize":"11px","textAlign":"right"}),
            html.Span("Giá HT",    style={"flex":"0 0 90px","color":"#7fa8cc","fontWeight":"600","fontSize":"11px","textAlign":"right"}),
            html.Span("Giá trị",   style={"flex":"0 0 100px","color":"#7fa8cc","fontWeight":"600","fontSize":"11px","textAlign":"right"}),
            html.Span("% L/L",     style={"flex":"0 0 90px","color":"#7fa8cc","fontWeight":"600","fontSize":"11px","textAlign":"right"}),
            html.Span("L/L (VND)", style={"flex":"0 0 100px","color":"#7fa8cc","fontWeight":"600","fontSize":"11px","textAlign":"right"}),
            html.Span("",          style={"flex":"0 0 24px"}),
        ], style={"display":"flex","padding":"6px 10px","borderBottom":"2px solid #21262d",
                  "backgroundColor":"#161b22"})

        table = html.Div([header, *table_rows], style={
            "backgroundColor":"#0d1117","borderRadius":"8px",
            "border":"1px solid #21262d","overflow":"hidden","marginBottom":"12px",
        })

        # Summary cards
        total_pnl   = total_value - total_cost
        total_pnl_p = (total_pnl / total_cost * 100) if total_cost else 0
        c_pnl       = "#10b981" if total_pnl >= 0 else "#ef4444"

        def summary_card(label, value, color="#c9d1d9"):
            return html.Div([
                html.Span(label, style={"fontSize":"10px","color":"#7fa8cc","fontWeight":"500"}),
                html.Span(value, style={"fontSize":"16px","fontWeight":"800","color":color,"marginTop":"2px"}),
            ], style={"display":"flex","flexDirection":"column","padding":"10px 14px",
                      "backgroundColor":"#161b22","borderRadius":"8px","border":"1px solid #21262d"})

        summary = html.Div([
            summary_card("Vốn đầu tư",   _fmt_idr(total_cost),  "#c9d1d9"),
            summary_card("Giá trị hiện tại", _fmt_idr(total_value), "#c9d1d9"),
            summary_card("Lời/Lỗ (VND)", ("+" if total_pnl >= 0 else "") + _fmt_idr(total_pnl), c_pnl),
            summary_card("Lời/Lỗ (%)",   f"{'+'if total_pnl_p>=0 else''}{total_pnl_p:.2f}%",   c_pnl),
        ], style={"display":"grid","gridTemplateColumns":"repeat(4,1fr)","gap":"8px","marginBottom":"14px"})

        # Performance chart (% từ ngày mua sớm nhất)
        fig = go.Figure()
        COLORS = ["#00d4ff","#10b981","#f59e0b","#a78bfa","#f87171","#34d399"]
        for i, (ticker, series) in enumerate(chart_data.items()):
            base = float(series.iloc[0])
            pct  = ((series / base) - 1) * 100
            fig.add_trace(go.Scatter(
                x=pct.index, y=pct.values,
                mode="lines", name=ticker,
                line=dict(color=COLORS[i % len(COLORS)], width=1.8),
                hovertemplate=f"<b>{ticker}</b><br>%{{x|%d/%m/%y}}<br>%{{y:+.1f}}%<extra></extra>",
            ))

        # JCI overlay
        if df_index is not None and not df_index.empty:
            min_date = min(s.index.min() for s in chart_data.values()) if chart_data else None
            if min_date:
                jci = df_index[df_index["Date"] >= min_date].sort_values("Date")
                if not jci.empty:
                    base_j = float(jci["JCI_Close"].iloc[0])
                    pct_j  = ((jci["JCI_Close"] / base_j) - 1) * 100
                    fig.add_trace(go.Scatter(
                        x=jci["Date"], y=pct_j,
                        mode="lines", name="VN-Index",
                        line=dict(color="#ffffff", width=1.2, dash="dot"),
                        hovertemplate="<b>VN-Index</b><br>%{x|%d/%m/%y}<br>%{y:+.1f}%<extra></extra>",
                    ))

        fig.add_hline(y=0, line_color="rgba(255,255,255,0.1)", line_width=1)
        fig.update_layout(
            paper_bgcolor="#0c1220", plot_bgcolor="#0c1220",
            margin=dict(l=5, r=5, t=5, b=5),
            legend=dict(bgcolor="rgba(22,27,34,0.8)", bordercolor="#30363d",
                        borderwidth=1, font=dict(color="#c9d1d9", size=11)),
            xaxis=dict(showgrid=False, zeroline=False, tickfont=dict(color="#484f58", size=9)),
            yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.04)", zeroline=False,
                       tickfont=dict(color="#484f58", size=9), ticksuffix="%"),
            hovermode="x unified",
        )

        return table, summary, fig, {"display": "block"}

    except Exception as e:
        logger.error(f"Portfolio render error: {e}")
        return html.P(f"Lỗi: {e}", style={"color":"#ef4444"}), [], go.Figure(), {"display":"none"}


@app.callback(
    Output("portfolio-modal", "is_open"),
    Input("btn-portfolio",    "n_clicks"),
    prevent_initial_call=True,
)
def open_portfolio_modal(n):
    return True if n else no_update