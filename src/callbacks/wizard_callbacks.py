# src/callbacks/wizard_callbacks.py
"""
Callbacks cho bộ lọc dạng Wizard 3 cột:
  Cột 1: Click nhóm → cập nhật cột 2 (danh sách tiêu chí)
  Cột 2: Click tiêu chí → thêm filter card vào cột 3
  Badge:  Đếm số tiêu chí đang active trong mỗi nhóm (cột 1)
  Highlight: Nhóm đang được chọn có nền sáng hơn
"""

from dash import Input, Output, State, html, ALL, callback_context, no_update
from src.app_instance import app
import logging
import pandas as pd
import plotly.graph_objects as go

logger = logging.getLogger(__name__)

logger = logging.getLogger(__name__)

# ── Map group_id → danh sách criteria index (khớp với CRITERIA_CONFIG trong filter_interaction_callbacks.py)
GROUP_CRITERIA_MAP = {
    "tong-quan": [
        ("criteria-price",        "Giá hiện tại (VND)"),
        ("criteria-volume",       "Khối lượng giao dịch"),
        ("criteria-market-cap",   "Vốn hóa thị trường"),
        ("criteria-eps",          "EPS (Thu nhập/CP)"),
        ("criteria-roe",          "ROE (%)"),
        ("criteria-pe",           "P/E Ratio"),
        ("criteria-rs-3d",        "RS 3 ngày"),
    ],
    "dinh-gia": [
        ("criteria-pb",           "P/B Ratio"),
        ("criteria-ps",           "P/S Ratio"),
        # ("criteria-ev-ebitda",    "EV/EBITDA"),
        ("criteria-div-yield",    "Tỷ suất Cổ tức (%)"),
    ],
    "sinh-loi": [
        ("criteria-roa",          "ROA (%)"),
        ("criteria-gross-margin", "Biên LN gộp (%)"),
        ("criteria-net-margin",   "Biên LN ròng (%)"),
        ("criteria-ebit-margin",  "Biên EBIT (%)"),
    ],
    "tang-truong": [
        ("criteria-rev-growth-yoy",  "% Tăng trưởng DT 1 năm"),
        ("criteria-rev-cagr-5y",     "% Tăng trưởng DT 5 năm"),
        ("criteria-eps-growth-yoy",  "% Tăng trưởng EPS 1 năm"),
        ("criteria-eps-cagr-5y",     "% Tăng trưởng EPS 5 năm"),
    ],
    "suc-khoe": [
        ("criteria-de",              "D/E (Nợ vay / VCSH)"),
        ("criteria-current-ratio",   "Tỷ lệ thanh toán hiện hành"),
        ("criteria-net-cash-cap",    "Tiền mặt ròng / Vốn hóa (%)"),
        ("criteria-net-cash-assets", "Tiền mặt ròng / Tổng TS (%)"),
    ],
    "gia-sma": [
        ("criteria-price-vs-sma5",   "Giá vs SMA(5) (%)"),
        ("criteria-price-vs-sma10",  "Giá vs SMA(10) (%)"),
        ("criteria-price-vs-sma20",  "Giá vs SMA(20) (%)"),
        ("criteria-price-vs-sma50",  "Giá vs SMA(50) (%)"),
        ("criteria-price-vs-sma100", "Giá vs SMA(100) (%)"),
        ("criteria-price-vs-sma200", "Giá vs SMA(200) (%)"),
        ("criteria-break-high-52w",  "Vượt đỉnh 52 tuần"),
        ("criteria-break-low-52w",   "Phá đáy 52 tuần"),
        ("criteria-pct-from-high-1y",  "% Cách đỉnh 1 năm"),
        ("criteria-pct-from-low-1y",   "% Cách đáy 1 năm"),
        ("criteria-pct-from-high-all", "% Cách đỉnh lịch sử"),
        ("criteria-pct-from-low-all",  "% Cách đáy lịch sử"),
    ],
    "ky-thuat": [
        ("criteria-rsi14",       "RSI (14)"),
        ("criteria-rsi-state",   "Trạng thái RSI(14)"),
        ("criteria-macd-hist",   "MACD Histogram"),
        ("criteria-bb-width",    "Mở Band Bollinger (%)"),
        ("criteria-consec-up",   "Phiên tăng liên tiếp"),
        ("criteria-consec-down", "Phiên giảm liên tiếp"),
    ],
    "momentum": [
        ("criteria-beta",        "Beta"),
        ("criteria-alpha",       "Alpha (% năm)"),
        ("criteria-rs-1m",       "RS 1 tháng"),
        ("criteria-rs-3m",       "RS 3 tháng"),
        ("criteria-rs-1y",       "RS 1 năm"),
        ("criteria-rs-avg",      "RS Trung bình"),
        ("criteria-vol-vs-sma5",  "KL so với SMA(5)"),
        ("criteria-vol-vs-sma10", "KL so với SMA(10)"),
        ("criteria-vol-vs-sma20", "KL so với SMA(20)"),
        ("criteria-vol-vs-sma50", "KL so với SMA(50)"),
        ("criteria-avg-vol-5d",   "KL TB 5 phiên"),
        ("criteria-avg-vol-10d",  "KL TB 10 phiên"),
        ("criteria-avg-vol-50d",  "KL TB 50 phiên"),
        ("criteria-gtgd-1w",      "GTGD 1 tuần (VND)"),
        ("criteria-gtgd-10d",     "GTGD 10 ngày (VND)"),
        ("criteria-gtgd-1m",      "GTGD 1 tháng (VND)"),
    ],
}

# Map criteria_index → filter_id (để check active_filters)
CRITERIA_TO_FILTER = {
    "criteria-price":          "filter-price",
    "criteria-volume":         "filter-volume",
    "criteria-market-cap":     "filter-market-cap",
    "criteria-eps":            "filter-eps",
    "criteria-roe":            "filter-roe",
    "criteria-pe":             "filter-pe",
    "criteria-rs-3d":          "filter-rs-3d",
    "criteria-pb":             "filter-pb",
    "criteria-ps":             "filter-ps",
    #"criteria-ev-ebitda":      "filter-ev-ebitda",
    "criteria-div-yield":      "filter-div-yield",
    "criteria-roa":            "filter-roa",
    "criteria-gross-margin":   "filter-gross-margin",
    "criteria-net-margin":     "filter-net-margin",
    "criteria-ebit-margin":    "filter-ebit-margin",
    "criteria-rev-growth-yoy": "filter-rev-growth-yoy",
    "criteria-rev-cagr-5y":    "filter-rev-cagr-5y",
    "criteria-eps-growth-yoy": "filter-eps-growth-yoy",
    "criteria-eps-cagr-5y":    "filter-eps-cagr-5y",
    "criteria-de":             "filter-de",
    "criteria-current-ratio":  "filter-current-ratio",
    "criteria-net-cash-cap":   "filter-net-cash-cap",
    "criteria-net-cash-assets":"filter-net-cash-assets",
    "criteria-price-vs-sma5":  "filter-price-vs-sma5",
    "criteria-price-vs-sma10": "filter-price-vs-sma10",
    "criteria-price-vs-sma20": "filter-price-vs-sma20",
    "criteria-price-vs-sma50": "filter-price-vs-sma50",
    "criteria-price-vs-sma100":"filter-price-vs-sma100",
    "criteria-price-vs-sma200":"filter-price-vs-sma200",
    "criteria-break-high-52w": "filter-break-high-52w",
    "criteria-break-low-52w":  "filter-break-low-52w",
    "criteria-pct-from-high-1y":  "filter-pct-from-high-1y",
    "criteria-pct-from-low-1y":   "filter-pct-from-low-1y",
    "criteria-pct-from-high-all": "filter-pct-from-high-all",
    "criteria-pct-from-low-all":  "filter-pct-from-low-all",
    "criteria-rsi14":          "filter-rsi14",
    "criteria-rsi-state":      "filter-rsi-state",
    "criteria-macd-hist":      "filter-macd-hist",
    "criteria-bb-width":       "filter-bb-width",
    "criteria-consec-up":      "filter-consec-up",
    "criteria-consec-down":    "filter-consec-down",
    "criteria-beta":           "filter-beta",
    "criteria-alpha":          "filter-alpha",
    "criteria-rs-1m":          "filter-rs-1m",
    "criteria-rs-3m":          "filter-rs-3m",
    "criteria-rs-1y":          "filter-rs-1y",
    "criteria-rs-avg":         "filter-rs-avg",
    "criteria-vol-vs-sma5":    "filter-vol-vs-sma5",
    "criteria-vol-vs-sma10":   "filter-vol-vs-sma10",
    "criteria-vol-vs-sma20":   "filter-vol-vs-sma20",
    "criteria-vol-vs-sma50":   "filter-vol-vs-sma50",
    "criteria-avg-vol-5d":     "filter-avg-vol-5d",
    "criteria-avg-vol-10d":    "filter-avg-vol-10d",
    "criteria-avg-vol-50d":    "filter-avg-vol-50d",
    "criteria-gtgd-1w":        "filter-gtgd-1w",
    "criteria-gtgd-10d":       "filter-gtgd-10d",
    "criteria-gtgd-1m":        "filter-gtgd-1m",
}

ALL_GROUP_IDS = list(GROUP_CRITERIA_MAP.keys())


# ============================================================================
# CALLBACK 1: Click nhóm (cột 1) → render danh sách tiêu chí (cột 2)
#             + highlight nhóm đang chọn
# ============================================================================
@app.callback(
    Output("wizard-col2-content", "children"),
    Output("wizard-col2-title",   "children"),
    Input({"type": "wizard-group-btn", "group": ALL}, "n_clicks"),
    State("active-filters-store", "data"),
    prevent_initial_call=True,
)
def render_col2_criteria(n_clicks_list, active_filters):
    ctx = callback_context
    if not ctx.triggered:
        return no_update, no_update

    triggered_id = ctx.triggered[0]["prop_id"]
    try:
        import json
        group_id = json.loads(triggered_id.split(".")[0])["group"]
    except Exception:
        return no_update, no_update

    items = GROUP_CRITERIA_MAP.get(group_id, [])
    active_filters = active_filters or {}

    # Tên nhóm để hiển thị trên title cột 2
    group_labels = {
        "tong-quan": "Thông tin chung",
        "dinh-gia":  "Định giá",
        "sinh-loi":  "Khả năng sinh lời",
        "tang-truong": "Tăng trưởng",
        "suc-khoe":  "Chỉ số tài chính",
        "gia-sma":   "Biến động giá & KL",
        "ky-thuat":  "Chỉ báo kỹ thuật",
        "momentum":  "Hành vi thị trường",
    }
    title = group_labels.get(group_id, "Chọn tiêu chí")

    rows = []
    for idx, (criteria_id, label) in enumerate(items, start=1):
        filter_id  = CRITERIA_TO_FILTER.get(criteria_id, "")
        is_active  = filter_id in active_filters

        rows.append(
            html.Div(
                [
                    # Số thứ tự (ẩn nếu chưa active, hiện nếu active)
                    html.Span(
                        str(idx),
                        style={
                            "fontSize": "10px", "fontWeight": "700",
                            "color": "#ff3d57" if is_active else "#484f58",
                            "minWidth": "18px", "textAlign": "right",
                            "marginRight": "8px",
                        },
                    ),
                    html.Span(label, style={
                        "fontSize": "12px",
                        "color": "#58a6ff" if is_active else "#c9d1d9",
                        "fontWeight": "600" if is_active else "400",
                        "flex": "1",
                    }),
                    # Tick nếu đã active
                    html.I(
                        className="fas fa-check-circle" if is_active else "",
                        style={"color": "#3fb950", "fontSize": "11px"}
                    ),
                ],
                id={"type": "criteria-item", "index": criteria_id},
                n_clicks=0,
                style={
                    "display": "flex", "alignItems": "center",
                    "padding": "8px 12px",
                    "borderBottom": "1px solid #161b22",
                    "cursor": "pointer",
                    "backgroundColor": "rgba(88,166,255,0.08)" if is_active else "transparent",
                    "transition": "background 0.15s",
                },
                className="criteria-item-hover",
            )
        )

    return rows, title


# ============================================================================
# CALLBACK 2: Cập nhật badge số tiêu chí trên cột 1 khi active_filters thay đổi
# ============================================================================
@app.callback(
    [Output({"type": "wizard-group-badge", "group": gid}, "children") for gid in ALL_GROUP_IDS]
    + [Output({"type": "wizard-group-badge", "group": gid}, "style")   for gid in ALL_GROUP_IDS],
    Input("active-filters-store", "data"),
    Input("selected-filters-container", "children"),  # ← thêm
    prevent_initial_call=False,
)
def update_group_badges(active_filters, filter_children):
    active_filters = active_filters or {}

    # Thu thập filter_id của tất cả card đang hiển thị (cả chưa kéo)
    rendered_filter_ids = set()
    if filter_children:
        if isinstance(filter_children, dict):
            filter_children = [filter_children]
        for c in filter_children:
            try:
                fid = c.get('props', {}).get('id', {}).get('index')
                if fid:
                    rendered_filter_ids.add(fid)
            except Exception:
                pass

    # Gộp: active (đã kéo) + rendered (chưa kéo)
    all_active_ids = set(active_filters.keys()) | rendered_filter_ids

    counts = []
    for gid in ALL_GROUP_IDS:
        items = GROUP_CRITERIA_MAP.get(gid, [])
        n = sum(
            1 for (criteria_id, _) in items
            if CRITERIA_TO_FILTER.get(criteria_id, "") in all_active_ids
        )
        counts.append(n)

    badge_texts  = [str(c) for c in counts]
    badge_styles = []
    _base = {
        "fontSize": "10px", "fontWeight": "700",
        "color": "#ff3d57",
        "backgroundColor": "rgba(255,61,87,0.15)",
        "border": "1px solid rgba(255,61,87,0.3)",
        "borderRadius": "10px",
        "padding": "1px 6px",
        "minWidth": "18px",
        "textAlign": "center",
    }
    for c in counts:
        style = {**_base, "display": "inline-block" if c > 0 else "none"}
        badge_styles.append(style)

    return badge_texts + badge_styles


# ============================================================================
# CALLBACK 3: Highlight nhóm đang được chọn (cột 1)
# ============================================================================
@app.callback(
    [Output({"type": "wizard-group-btn", "group": gid}, "style") for gid in ALL_GROUP_IDS],
    Input({"type": "wizard-group-btn", "group": ALL}, "n_clicks"),
    prevent_initial_call=True,
)
def highlight_active_group(n_clicks_list):
    ctx = callback_context
    if not ctx.triggered:
        return [no_update] * len(ALL_GROUP_IDS)

    triggered_id = ctx.triggered[0]["prop_id"]
    try:
        import json
        active_group = json.loads(triggered_id.split(".")[0])["group"]
    except Exception:
        return [no_update] * len(ALL_GROUP_IDS)

    styles = []
    for gid in ALL_GROUP_IDS:
        if gid == active_group:
            styles.append({
                "display": "flex", "alignItems": "center",
                "padding": "9px 14px", "cursor": "pointer",
                "borderBottom": "1px solid #21262d",
                "transition": "background 0.15s",
                "backgroundColor": "rgba(88,166,255,0.1)",
                "borderLeft": "3px solid #58a6ff",
            })
        else:
            styles.append({
                "display": "flex", "alignItems": "center",
                "padding": "9px 14px", "cursor": "pointer",
                "borderBottom": "1px solid #21262d",
                "transition": "background 0.15s",
                "backgroundColor": "#0d1117",
                "borderLeft": "3px solid transparent",
            })
    return styles


# ============================================================================
# CALLBACK 4: IDX INDEX CHART + STATS PANEL
# ============================================================================

@app.callback(
    Output("idx-mini-chart",    "figure"),
    Output("idx-chart-change",  "children"),
    Output("idx-chart-change",  "style"),
    Output("idx-stats-panel",   "children"),
    Input("filter-offcanvas",   "is_open"),
    prevent_initial_call=True,
)
def render_idx_mini_chart(is_open):
    if not is_open:
        return go.Figure(), "", {}, []

    try:
        from src.backend.data_loader import load_index_data

        df_full = load_index_data()

        # ── Fallback: nếu parquet rỗng → tải thẳng từ yfinance ──
        if df_full is None or df_full.empty:
            logger.warning("[IDX Chart] index.parquet rỗng → thử tải trực tiếp từ yfinance ^JKSE")
            try:
                import yfinance as yf
                df_yf = yf.download("^JKSE", period="2y", auto_adjust=True, progress=False)
                if not df_yf.empty:
                    df_yf = df_yf.reset_index()
                    df_yf.columns = [str(c[0]) if isinstance(c, tuple) else str(c)
                                     for c in df_yf.columns]
                    df_yf['Date']      = pd.to_datetime(df_yf['Date']).dt.tz_localize(None)
                    df_yf['JCI_Close'] = pd.to_numeric(df_yf.get('Close', df_yf.iloc[:, 1]),
                                                        errors='coerce')
                    df_yf['JCI_Volume'] = pd.to_numeric(df_yf.get('Volume', 0), errors='coerce')
                    df_full = df_yf[['Date','JCI_Close','JCI_Volume']].dropna(subset=['JCI_Close'])
            except Exception as e2:
                logger.error(f"[IDX Chart] yfinance fallback lỗi: {e2}")

        if df_full is None or df_full.empty:
            raise ValueError("Không có dữ liệu index từ cả parquet lẫn yfinance")

        df_full = df_full.sort_values("Date").copy()
        df      = df_full.tail(90)
        prices  = df["JCI_Close"]
        latest  = float(prices.iloc[-1])
        prev    = float(prices.iloc[-2]) if len(prices) >= 2 else latest

        # ── Tính các chỉ số ──
        chg_1d  = (latest - prev) / prev * 100
        p_1w    = df_full[df_full["Date"] <= df_full["Date"].max() - pd.Timedelta(days=7)]["JCI_Close"]
        p_1m    = df_full[df_full["Date"] <= df_full["Date"].max() - pd.Timedelta(days=30)]["JCI_Close"]
        p_1y    = df_full[df_full["Date"] <= df_full["Date"].max() - pd.Timedelta(days=365)]["JCI_Close"]
        chg_1w  = (latest - p_1w.iloc[-1]) / p_1w.iloc[-1] * 100 if not p_1w.empty else None
        chg_1m  = (latest - p_1m.iloc[-1]) / p_1m.iloc[-1] * 100 if not p_1m.empty else None
        chg_1y  = (latest - p_1y.iloc[-1]) / p_1y.iloc[-1] * 100 if not p_1y.empty else None

        hi52 = float(df_full.tail(252)["JCI_Close"].max())
        lo52 = float(df_full.tail(252)["JCI_Close"].min())
        pct_from_hi = (latest - hi52) / hi52 * 100

        vol_col = "JCI_Volume" if "JCI_Volume" in df_full.columns else None
        vol_avg = float(df_full.tail(20)[vol_col].mean()) if vol_col else None

        last_date = df_full["Date"].max()

        # ── Màu sắc title bar ──
        is_up_1d   = chg_1d >= 0
        color_1d   = "#10b981" if is_up_1d else "#ef4444"
        sign_1d    = "+" if is_up_1d else ""
        change_text  = f"{sign_1d}{chg_1d:.2f}%  ·  {int(latest):,}"
        change_style = {"fontSize": "11px", "fontWeight": "700", "color": color_1d}

        # ── Helper render 1 stat row ──
        def stat_row(label, value, color="#c9d1d9"):
            return html.Div([
                html.Span(label, style={
                    "fontSize": "9px", "color": "#7fa8cc",
                    "fontWeight": "500", "whiteSpace": "nowrap",
                    "textTransform": "uppercase", "letterSpacing": "0.3px",
                }),
                html.Span(value, style={
                    "fontSize": "12px", "fontWeight": "700",
                    "color": color, "whiteSpace": "nowrap",
                }),
            ], style={
                "display": "flex", "flexDirection": "column",
                "padding": "5px 8px",
                "borderBottom": "1px solid #0e2540",
                "borderRight": "1px solid #0e2540",
            })

        def fmt_pct(v):
            if v is None: return "–", "#484f58"
            s = "+" if v >= 0 else ""
            return f"{s}{v:.2f}%", "#10b981" if v >= 0 else "#ef4444"

        p1w_txt, p1w_col = fmt_pct(chg_1w)
        p1m_txt, p1m_col = fmt_pct(chg_1m)
        p1y_txt, p1y_col = fmt_pct(chg_1y)

        stats = html.Div([
            stat_row("Giá",          f"{int(latest):,}",                "#e6edf3"),
            stat_row("Hôm nay",      f"{sign_1d}{chg_1d:.2f}%",         color_1d),
            stat_row("1 tuần",       p1w_txt,                            p1w_col),
            stat_row("1 tháng",      p1m_txt,                            p1m_col),
            stat_row("1 năm",        p1y_txt,                            p1y_col),
            stat_row("52W Cao",      f"{int(hi52):,}",                   "#f59e0b"),
            stat_row("52W Thấp",     f"{int(lo52):,}",                   "#f59e0b"),
            stat_row("Cách đỉnh",    f"{pct_from_hi:.1f}%",
                     "#ef4444" if pct_from_hi < -5 else "#10b981"),
            stat_row("KL TB 20P",    f"{int(vol_avg/1e6):.0f}M"
                     if vol_avg else "–",                                "#7fa8cc"),
            stat_row("Cập nhật",     last_date.strftime("%d/%m/%y"),     "#484f58"),
        ], style={
            "display": "grid",
            "gridTemplateColumns": "1fr 1fr",
            "alignContent": "start",
        })

        # ── Tính toán trục Y ──
        y_min = prices.min()
        y_max = prices.max()
        # Mở rộng trục Y: dưới min 150 điểm và trên max một chút để chart thoáng hơn
        y_range = [y_min - 150, y_max + (y_max - y_min) * 0.1]

        # ── Vẽ chart ──
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df["Date"], 
            y=prices,
            # Nếu DataFrame của bạn có cột Volume, ta có thể truyền nó vào customdata để dùng trong hover
            customdata=df["JCI_Volume"] if "JCI_Volume" in df.columns else [None]*len(df),
            mode="lines",
            line=dict(color=color_1d, width=1.8),
            fill="tozeroy",
            fillcolor=f"rgba({'16,185,129' if is_up_1d else '239,68,68'},0.08)",
            # 🟢 Mở rộng Hovertemplate
            # %{x} là Date, %{y} là Giá, %{customdata} là Volume
            hovertemplate=(
                "<b>Ngày:</b> %{x|%d/%m/%Y}<br>"
                "<b>Chỉ số:</b> %{y:,.2f} điểm<br>"
                "<b>KLGD:</b> %{customdata:,.0f}<extra></extra>" 
                # <extra></extra> dùng để giấu cái hộp tên trace dư thừa bên cạnh
            ),
        ))
        
        fig.update_layout(
            paper_bgcolor="#0d1117",
            plot_bgcolor="#0d1117",
            hovermode='closest',
            margin=dict(l=6, r=40, t=4, b=20),
            xaxis=dict(
                showgrid=False, zeroline=False,
                tickfont=dict(size=8, color="#484f58"),
                tickformat="%b %y", nticks=6,
            ),
            yaxis=dict(
                showgrid=True, gridcolor="rgba(255,255,255,0.04)",
                zeroline=False, showticklabels=True,
                tickfont=dict(size=8, color="#484f58"),
                tickformat=",.0f", side="right",
                range=y_range, # 🟢 Ép trục Y theo khoảng đã tính
            ),
            showlegend=False,
            hoverlabel=dict(bgcolor="#161b22", font_size=11, bordercolor=color_1d),
        )
        return fig, change_text, change_style, stats

    except Exception as e:
        logger.error(f"[IDX Chart] Lỗi render: {e}")
        empty_fig = go.Figure(layout=dict(
            paper_bgcolor="#0d1117", plot_bgcolor="#0d1117",
            margin=dict(l=0, r=0, t=0, b=0),
            annotations=[dict(
                text=f"Lỗi tải dữ liệu: {str(e)[:40]}",
                x=0.5, y=0.5, xref="paper", yref="paper",
                showarrow=False, font=dict(color="#484f58", size=11),
            )],
        ))
        return empty_fig, "–", {"color": "#484f58", "fontSize": "11px"}, []