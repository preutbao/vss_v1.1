# src/callbacks/compare_callbacks.py
"""
So sánh tương đối nhiều cổ phiếu trên cùng 1 chart (% thay đổi so với điểm gốc).
Kèm JCI làm benchmark.
"""
from dash import Input, Output, State, html, dcc, no_update, callback_context
from src.app_instance import app
import plotly.graph_objects as go
import pandas as pd
import numpy as np
import dash_bootstrap_components as dbc
import logging

logger = logging.getLogger(__name__)

COMPARE_COLORS = ["#00d4ff", "#10b981", "#f59e0b", "#a78bfa", "#f87171", "#34d399"]

# ── Modal layout ──
compare_modal = dbc.Modal([
    dbc.ModalHeader(
        dbc.ModalTitle([
            html.I(className="fas fa-code-compare", style={"marginRight": "8px", "color": "#00d4ff"}),
            "So sánh cổ phiếu",
        ]),
        close_button=True,
    ),
    dbc.ModalBody([
        html.Div([
            dcc.Dropdown(
                id="compare-ticker-select",
                options=[],
                value=[],
                multi=True,
                placeholder="Thêm mã cổ phiếu để so sánh...",
                className="ssi-dropdown-custom",
                style={"flex": "1", "minWidth": "0"},
            ),
            dcc.Dropdown(
                id="compare-period-select",
                options=[
                    {"label": "1 tháng",  "value": 30},
                    {"label": "3 tháng",  "value": 90},
                    {"label": "6 tháng",  "value": 180},
                    {"label": "1 năm",    "value": 365},
                    {"label": "2 năm",    "value": 730},
                ],
                value=90,
                clearable=False,
                className="ssi-dropdown-custom",
                style={"width": "130px", "flexShrink": "0"},
            ),
            dbc.Checklist(
                options=[{"label": "vs VNINDEX", "value": "jci"}],
                value=["jci"],
                id="compare-show-jci",
                inline=True,
                style={"color": "#c9d1d9", "fontSize": "12px", "marginLeft": "8px",
                       "flexShrink": "0", "whiteSpace": "nowrap"},
            ),
        ], style={"display": "flex", "gap": "10px", "alignItems": "center",
                  "marginBottom": "16px",
                  "position": "relative", "zIndex": "10"}),

        html.Div(id="compare-empty-state"),

        # Div bọc chart — ẩn khi chưa chọn mã, hiện khi có data
        html.Div(
            dcc.Graph(
                id="compare-chart",
                config={"displayModeBar": True},
                style={"height": "500px"},
            ),
            id="compare-chart-wrapper",
            style={"height": "500px", "overflow": "hidden", "display": "none"},
        ),

        html.Div(id="compare-summary-table", style={"marginTop": "12px"}),

        # Interval bắn 1 lần sau 800ms khi modal mở
        dcc.Interval(
            id="compare-render-trigger",
            interval=800,
            n_intervals=0,
            max_intervals=0,
            disabled=True,
        ),
    ], style={"backgroundColor": "#0c1220",
              "overflow": "visible", "minHeight": "520px"}),
], id="compare-modal", size="xl", is_open=False, centered=True,
   scrollable=False,
   style={"zIndex": "1060"})


@app.callback(
    Output("compare-ticker-select", "options"),
    Input("compare-modal",          "is_open"),
    prevent_initial_call=True,
)
def load_compare_options(is_open):
    if not is_open:
        return no_update
    try:
        from src.backend.data_loader import get_ticker_list
        return get_ticker_list()
    except Exception:
        return []


@app.callback(
    Output("compare-render-trigger", "disabled"),
    Output("compare-render-trigger", "n_intervals"),
    Output("compare-render-trigger", "max_intervals"),
    Input("compare-modal", "is_open"),
    prevent_initial_call=True,
)
def toggle_render_trigger(is_open):
    if is_open:
        return False, 0, 1   # bật, reset đếm, cho phép bắn 1 lần
    return True, 0, 0         # tắt, reset hết


def _clean_price_df(df_price: pd.DataFrame) -> pd.DataFrame:
    df = df_price.copy()
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df["Price Close"] = pd.to_numeric(df["Price Close"], errors="coerce").astype("float64")
    df = df.dropna(subset=["Date", "Price Close"])
    df = df[df["Price Close"] > 0]
    raw_max_date = df["Date"].max()
    df = df[df["Date"] < raw_max_date]
    return df


def _build_figure(tickers, days, show_jci):
    from src.backend.data_loader import load_market_data, load_index_data
    df_price = _clean_price_df(load_market_data())
    df_index = load_index_data()

    cutoff       = df_price["Date"].max() - pd.Timedelta(days=days)
    fig          = go.Figure()
    summary_rows = []

    for i, ticker in enumerate(tickers[:6]):
        df_t = df_price[
            (df_price["Ticker"] == ticker) & (df_price["Date"] >= cutoff)
        ].sort_values("Date")

        if df_t.empty:
            continue

        base = float(df_t["Price Close"].iloc[0])
        if base <= 0:
            continue

        pct    = ((df_t["Price Close"] / base) - 1) * 100
        color  = COMPARE_COLORS[i % len(COMPARE_COLORS)]
        last_p = float(pct.iloc[-1])

        fig.add_trace(go.Scatter(
            x=df_t["Date"], y=pct,
            mode="lines", name=ticker,
            line=dict(color=color, width=2),
            hovertemplate=f"<b>{ticker}</b><br>%{{x|%d/%m/%y}}<br>%{{y:+.2f}}%<extra></extra>",
        ))

        try:
            price_start = int(df_t["Price Close"].iloc[0])
            price_end   = int(df_t["Price Close"].iloc[-1])
        except (ValueError, OverflowError):
            price_start = round(float(df_t["Price Close"].iloc[0]), 0)
            price_end   = round(float(df_t["Price Close"].iloc[-1]), 0)

        summary_rows.append({
            "Mã":         ticker,
            "Đầu kỳ":     f"{price_start:,}",
            "Hiện tại":   f"{price_end:,}",
            f"% {days}N": f"{last_p:+.2f}%",
            "_color":     color,
            "_perf":      last_p,
        })

    # Vẽ JCI
    if show_jci and "jci" in (show_jci or []) and df_index is not None and not df_index.empty:
        df_jci = df_index.copy()
        df_jci["Date"]      = pd.to_datetime(df_jci["Date"], errors="coerce")
        df_jci["JCI_Close"] = pd.to_numeric(df_jci["JCI_Close"], errors="coerce")
        df_jci = df_jci.dropna(subset=["Date", "JCI_Close"])
        df_jci = df_jci[df_jci["Date"] >= cutoff].sort_values("Date")

        if not df_jci.empty:
            base_j = float(df_jci["JCI_Close"].iloc[0])
            if base_j > 0:
                pct_j = ((df_jci["JCI_Close"] / base_j) - 1) * 100
                fig.add_trace(go.Scatter(
                    x=df_jci["Date"], y=pct_j,
                    mode="lines", name="VNINDEX",
                    line=dict(color="#ffffff", width=1.5, dash="dot"),
                    hovertemplate="<b>VNINDEX</b><br>%{x|%d/%m/%y}<br>%{y:+.2f}%<extra></extra>",
                ))

    fig.add_hline(y=0, line_color="rgba(255,255,255,0.15)", line_width=1)

    import time as _time
    fig.update_layout(
        uirevision=str(_time.time()),
        # autosize=True: Plotly tự fit theo wrapper div 500px
        autosize=True,
        paper_bgcolor="#0c1220", plot_bgcolor="#0c1220",
        margin=dict(l=10, r=10, t=20, b=10),
        legend=dict(
            bgcolor="rgba(22,27,34,0.8)", bordercolor="#30363d",
            borderwidth=1, font=dict(color="#c9d1d9", size=11),
        ),
        xaxis=dict(
            showgrid=False, zeroline=False,
            tickfont=dict(color="#484f58", size=10),
        ),
        yaxis=dict(
            showgrid=True, gridcolor="rgba(255,255,255,0.04)",
            zeroline=False, tickfont=dict(color="#484f58", size=10),
            ticksuffix="%",
        ),
        hovermode="x unified",
        hoverlabel=dict(bgcolor="#161b22", font_size=11),
    )

    # Summary table
    if summary_rows:
        header = html.Div([
            html.Span("Mã",         style={"flex": "0 0 70px",  "fontWeight": "600", "color": "#7fa8cc", "fontSize": "11px"}),
            html.Span("Đầu kỳ",     style={"flex": "0 0 90px",  "fontWeight": "600", "color": "#7fa8cc", "fontSize": "11px", "textAlign": "right"}),
            html.Span("Hiện tại",   style={"flex": "0 0 90px",  "fontWeight": "600", "color": "#7fa8cc", "fontSize": "11px", "textAlign": "right"}),
            html.Span(f"% {days}N", style={"flex": "0 0 90px",  "fontWeight": "600", "color": "#7fa8cc", "fontSize": "11px", "textAlign": "right"}),
        ], style={"display": "flex", "padding": "6px 10px", "borderBottom": "1px solid #21262d"})

        rows_html = []
        for r in summary_rows:
            c = "#10b981" if r["_perf"] >= 0 else "#ef4444"
            rows_html.append(html.Div([
                html.Span(r["Mã"],          style={"flex": "0 0 70px", "color": r["_color"], "fontWeight": "700", "fontSize": "12px"}),
                html.Span(r["Đầu kỳ"],      style={"flex": "0 0 90px", "color": "#c9d1d9",   "fontSize": "12px", "textAlign": "right"}),
                html.Span(r["Hiện tại"],    style={"flex": "0 0 90px", "color": "#c9d1d9",   "fontSize": "12px", "textAlign": "right"}),
                html.Span(r[f"% {days}N"],  style={"flex": "0 0 90px", "color": c,           "fontSize": "12px", "textAlign": "right", "fontWeight": "700"}),
            ], style={"display": "flex", "padding": "5px 10px", "borderBottom": "1px solid #161b22"}))

        summary = html.Div([header, *rows_html], style={
            "backgroundColor": "#161b22", "borderRadius": "8px",
            "border": "1px solid #21262d", "overflow": "hidden",
        })
    else:
        summary = []

    return fig, summary


@app.callback(
    Output("compare-chart",         "figure"),
    Output("compare-chart-wrapper", "style"),
    Output("compare-empty-state",   "children"),
    Output("compare-summary-table", "children"),
    Input("compare-ticker-select",  "value"),
    Input("compare-period-select",  "value"),
    Input("compare-show-jci",       "value"),
    Input("compare-render-trigger", "n_intervals"),
    State("compare-modal",          "is_open"),
    prevent_initial_call=True,
)
def update_compare_chart(tickers, days, show_jci, _n, is_open):
    HIDDEN  = {"height": "500px", "overflow": "hidden", "display": "none"}
    VISIBLE = {"height": "500px", "overflow": "hidden", "display": "block"}

    if not is_open:
        return no_update, no_update, no_update, no_update

    tickers = tickers or []
    days    = days or 90

    if not tickers:
        empty_state = html.Div([
            html.I(className="fas fa-code-compare",
                   style={"fontSize": "32px", "color": "#30363d", "marginBottom": "8px"}),
            html.P("Chưa chọn mã — thêm cổ phiếu để bắt đầu so sánh",
                   style={"color": "#484f58", "fontSize": "13px"}),
        ], style={"textAlign": "center", "padding": "30px"})
        blank = go.Figure(layout=dict(
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            margin=dict(l=0, r=0, t=0, b=0),
            height=460, autosize=False,
        ))
        return blank, HIDDEN, empty_state, []

    try:
        fig, summary = _build_figure(tickers, days, show_jci)
        return fig, VISIBLE, [], summary
    except Exception as e:
        logger.error(f"Compare chart error: {e}", exc_info=True)
        return go.Figure(), HIDDEN, [], []


@app.callback(
    Output("compare-modal",         "is_open"),
    Output("compare-ticker-select", "value"),
    Input("btn-compare",            "n_clicks"),
    State("screener-table",         "selectedRows"),
    State("compare-ticker-select",  "value"),
    prevent_initial_call=True,
)
def open_compare_modal(n_clicks, selected_rows, current_tickers):
    if not n_clicks:
        return no_update, no_update
    current_tickers = current_tickers or []
    if selected_rows:
        ticker = selected_rows[0].get("Ticker", "")
        if ticker and ticker not in current_tickers:
            current_tickers = current_tickers + [ticker]
    return True, current_tickers


app.clientside_callback(
    """
    function(n) {
        var doResize = function() {
            var el = document.getElementById('compare-chart');
            if (el && el._fullLayout && window.Plotly) {
                window.Plotly.Plots.resize(el);
            }
        };
        setTimeout(doResize, 50);
        setTimeout(doResize, 200);
        return window.dash_clientside.no_update;
    }
    """,
    Output("compare-chart", "className"),
    Input("compare-render-trigger", "n_intervals"),
    prevent_initial_call=True,
)

# ============================================================================
# KHÓA SCROLL MÀN HÌNH CHÍNH KHI BẤT KỲ MODAL/OFFCANVAS NÀO MỞ
# ============================================================================
app.clientside_callback(
    """
    function(a, b, c, d, e, f, g, h) {
        var anyOpen = a || b || c || d || e || f || g || h;
        document.body.style.overflow = anyOpen ? 'hidden' : '';
        document.documentElement.style.overflow = anyOpen ? 'hidden' : '';
        return window.dash_clientside.no_update;
    }
    """,
    Output("screener-scroll-anchor", "style"),
    Input("compare-modal",            "is_open"),
    Input("portfolio-modal",          "is_open"),
    Input("detail-modal",             "is_open"),
    Input("watchlist-modal",          "is_open"),
    Input("heatmap-collapse",         "is_open"),
    Input("alert-modal",              "is_open"),
    Input("score-breakdown-modal",    "is_open"),
    Input("health-methodology-modal", "is_open"),
    prevent_initial_call=True,
)