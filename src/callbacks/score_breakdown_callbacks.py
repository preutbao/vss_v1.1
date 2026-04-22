# src/callbacks/score_breakdown_callbacks.py
"""
Hiển thị breakdown chi tiết Value / Growth / Momentum score
khi user click vào ô score trong bảng screener.
"""
from dash import Input, Output, State, html, no_update, callback_context
from src.app_instance import app
import dash_bootstrap_components as dbc
import logging

logger = logging.getLogger(__name__)

# ── Màu theo grade ──
GRADE_COLOR = {
    'A': '#10b981', 'B': '#3b82f6',
    'C': '#f59e0b', 'D': '#ef4444', 'F': '#64748b',
}

def _grade_badge(grade):
    c = GRADE_COLOR.get(str(grade), '#64748b')
    return html.Span(str(grade), style={
        "display": "inline-block",
        "padding": "2px 10px", "borderRadius": "4px",
        "backgroundColor": f"{c}25", "color": c,
        "fontWeight": "700", "fontSize": "13px",
        "border": f"1px solid {c}60",
    })

def _bar(pct, color):
    """Thanh progress nhỏ."""
    return html.Div([
        html.Div(style={
            "width": f"{max(0, min(100, pct))}%",
            "height": "6px", "borderRadius": "3px",
            "backgroundColor": color,
            "transition": "width 0.4s ease",
        })
    ], style={
        "width": "100%", "height": "6px",
        "backgroundColor": "rgba(255,255,255,0.06)",
        "borderRadius": "3px", "marginTop": "4px",
    })

def _score_section(title, icon, items):
    """
    items: list of (label, value_str, grade, pct)
    """
    rows = []
    for label, val, grade, pct in items:
        c = GRADE_COLOR.get(str(grade), '#64748b')
        rows.append(html.Div([
            html.Div([
                html.Span(label, style={"fontSize": "11px", "color": "#7fa8cc", "flex": "1"}),
                html.Span(val,   style={"fontSize": "11px", "color": "#c9d1d9",
                                        "marginRight": "8px", "fontWeight": "600"}),
                _grade_badge(grade),
            ], style={"display": "flex", "alignItems": "center"}),
            _bar(pct, c),
        ], style={"marginBottom": "8px"}))

    return html.Div([
        html.Div([
            html.I(className=icon, style={"color": "#58a6ff", "marginRight": "6px", "fontSize": "11px"}),
            html.Span(title, style={"fontSize": "12px", "fontWeight": "700", "color": "#c9d1d9"}),
        ], style={"marginBottom": "10px", "paddingBottom": "6px",
                  "borderBottom": "1px solid #21262d"}),
        *rows,
    ], style={
        "padding": "12px", "backgroundColor": "#161b22",
        "borderRadius": "8px", "border": "1px solid #21262d",
        "marginBottom": "10px",
    })


def build_score_breakdown(stock: dict) -> html.Div:
    """Tạo nội dung breakdown từ dict record của 1 cổ phiếu."""

    def fmt(v, suffix="", decimals=1):
        try:
            if v is None or (isinstance(v, float) and v != v):
                return "–"
            return f"{float(v):.{decimals}f}{suffix}"
        except Exception:
            return "–"

    def pct_bar(v, lo, hi):
        """Chuyển giá trị v sang % trong khoảng [lo, hi] để vẽ bar."""
        try:
            return max(0, min(100, (float(v) - lo) / (hi - lo) * 100))
        except Exception:
            return 0

    pe  = stock.get('P/E')
    pb  = stock.get('P/B')
    roe = stock.get('ROE (%)')
    roa = stock.get('ROA (%)')
    rs1m = stock.get('RS_1M')
    rs3m = stock.get('RS_3M')
    perf1m = stock.get('Perf_1M')
    perf3m = stock.get('Perf_3M')
    rsi = stock.get('RSI_14')

    vpe_g = stock.get('Value_PE_Grade', '–')
    vpb_g = stock.get('Value_PB_Grade', '–')
    groe_g = stock.get('Growth_ROE_Grade', '–')
    groa_g = stock.get('Growth_ROA_Grade', '–')

    v_score = stock.get('Value Score', '–')
    g_score = stock.get('Growth Score', '–')
    m_score = stock.get('Momentum Score', '–')
    vgm     = stock.get('VGM Score', '–')

    value_section = _score_section(
        f"VALUE  {_grade_badge(v_score).to_plotly_json() if False else ''}",
        "fas fa-tag",
        [
            ("P/E Ratio",  fmt(pe, "x"),  vpe_g, pct_bar(pe, 0, 50) if pe else 0),
            ("P/B Ratio",  fmt(pb, "x"),  vpb_g, pct_bar(pb, 0, 10) if pb else 0),
        ]
    )

    growth_section = _score_section(
        "GROWTH",
        "fas fa-chart-line",
        [
            ("ROE (%)",  fmt(roe, "%"), groe_g, pct_bar(roe, 0, 40) if roe else 0),
            ("ROA (%)",  fmt(roa, "%"), groa_g, pct_bar(roa, 0, 20) if roa else 0),
        ]
    )

    momentum_section = _score_section(
        "MOMENTUM",
        "fas fa-rocket",
        [
            ("RS 1 tháng",   fmt(rs1m, "%"),  "A" if (rs1m or 0) > 10 else "C" if (rs1m or 0) > 0 else "F",
             pct_bar(rs1m, -30, 50) if rs1m else 50),
            ("RS 3 tháng",   fmt(rs3m, "%"),  "A" if (rs3m or 0) > 15 else "C" if (rs3m or 0) > 0 else "F",
             pct_bar(rs3m, -50, 100) if rs3m else 50),
            ("Perf 1 tháng", fmt(perf1m, "%"), "A" if (perf1m or 0) > 10 else "C" if (perf1m or 0) > 0 else "F",
             pct_bar(perf1m, -30, 50) if perf1m else 50),
            ("RSI (14)",     fmt(rsi),         "A" if 40 < (rsi or 0) < 60 else "C",
             float(rsi) if rsi else 50),
        ]
    )

    return html.Div([
        # VGM tổng hợp
        html.Div([
            html.Div([
                html.Span("VGM Score", style={"fontSize": "11px", "color": "#7fa8cc"}),
                html.Div([
                    html.Span("V ", style={"color": "#7fa8cc", "fontSize": "11px"}),
                    _grade_badge(v_score),
                    html.Span("  G ", style={"color": "#7fa8cc", "fontSize": "11px", "marginLeft": "6px"}),
                    _grade_badge(g_score),
                    html.Span("  M ", style={"color": "#7fa8cc", "fontSize": "11px", "marginLeft": "6px"}),
                    _grade_badge(m_score),
                    html.Span("  →  ", style={"color": "#484f58", "fontSize": "11px", "marginLeft": "6px"}),
                    _grade_badge(vgm),
                ], style={"display": "flex", "alignItems": "center", "marginTop": "6px"}),
            ]),
        ], style={
            "padding": "10px 12px", "backgroundColor": "#0d1117",
            "borderRadius": "8px", "border": "1px solid #21262d",
            "marginBottom": "10px",
        }),
        value_section,
        growth_section,
        momentum_section,
    ])


# ── Modal layout (thêm vào screener layout) ──
score_breakdown_modal = dbc.Modal([
    dbc.ModalHeader(
        dbc.ModalTitle(id="score-breakdown-title", children="Score Breakdown"),
        close_button=True,
    ),
    dbc.ModalBody(html.Div(id="score-breakdown-body"), style={"backgroundColor": "#0c1220"}),
], id="score-breakdown-modal", size="md", is_open=False, centered=True,
   style={"fontFamily": "'Inter', sans-serif"})


@app.callback(
    Output("score-breakdown-modal", "is_open"),
    Output("score-breakdown-title", "children"),
    Output("score-breakdown-body",  "children"),
    Input("screener-table", "cellClicked"),
    State("screener-table", "rowData"),
    prevent_initial_call=True,
)
def open_score_breakdown(cell_clicked, row_data):
    if not cell_clicked:
        return no_update, no_update, no_update

    col = cell_clicked.get("colId", "")
    if col not in ("Value Score", "Growth Score", "Momentum Score", "VGM Score"):
        return no_update, no_update, no_update

    row_idx = cell_clicked.get("rowIndex")
    if row_idx is None or not row_data:
        return no_update, no_update, no_update

    try:
        stock = row_data[row_idx]
        ticker = stock.get("Ticker", "")
        title = [
            html.I(className="fas fa-chart-pie", style={"marginRight": "8px", "color": "#58a6ff"}),
            f"Score Breakdown — {ticker}",
        ]
        body = build_score_breakdown(stock)
        return True, title, body
    except Exception as e:
        logger.error(f"Score breakdown error: {e}")
        return no_update, no_update, no_update