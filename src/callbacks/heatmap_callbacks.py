# src/callbacks/heatmap_callbacks.py
from dash import Input, Output, State, html
from src.app_instance import app
import plotly.graph_objects as go
import pandas as pd
import numpy as np
import math, logging
from dash import Input, Output, State, html, dcc, ALL
import json
import numpy as np
import pandas as pd


logger = logging.getLogger(__name__)


def _color(v):
    try: v = float(v)
    except: return "#1f2937"  # NaN = không có dữ liệu
    if math.isnan(v): return "#1f2937"
    if v >  6:    return "#065f46"
    if v >  3:    return "#16a34a"
    if v >  1:    return "#22c55e"
    if v >  0.1:  return "#86efac"
    if v >= -0.1: return "#854d0e"
    if v > -1:    return "#ca8a04"
    if v > -3:    return "#ea580c"
    if v > -6:    return "#dc2626"
    return "#7f1d1d"


def _squarify_rects(values, x, y, w, h):
    """Dùng package squarify chuẩn, fallback về chia đều nếu chưa install."""
    values = [max(v, 0) for v in values]
    total  = sum(values)
    if total <= 0 or w <= 0 or h <= 0:
        return [(x, y, w/max(len(values),1), h)] * len(values)
    try:
        import squarify
        norm = squarify.normalize_sizes(values, w, h)
        rects = squarify.squarify(norm, x, y, w, h)
        return [(r["x"], r["y"], r["dx"], r["dy"]) for r in rects]
    except ImportError:
        # Fallback: chia theo chiều ngang đơn giản
        result, pos = [], x
        for v in values:
            bw = w * v / total
            result.append((pos, y, bw, h))
            pos += bw
        return result


def _cell(ticker, perf, company, mc_t, tw, th):
    bg  = _color(perf)
    fg  = "#000" if bg in {"#86efac", "#22c55e"} else "#fff"
    is_nan = perf is None or (isinstance(perf, float) and math.isnan(perf))
    ps  = f"{perf:+.2f}%" if not is_nan else "N/A"
    if is_nan: bg = "#1f2937"; fg = "#4b5563"
    fs  = max(8, min(18, int(min(tw, th) / 2.8)))

    kids = []
    if tw > 45 and th > 36:
        kids.append(html.B(ticker, style={
            "fontSize": f"{fs}px", "lineHeight": "1.2",
            "display": "block", "overflow": "hidden",
            "textOverflow": "ellipsis", "whiteSpace": "nowrap",
            "textShadow": "0 1px 3px rgba(0,0,0,0.35)",
        }))
    if tw > 44 and th > 34:
        kids.append(html.Span(ps, style={
            "fontSize": f"{max(7, fs-2)}px",
            "opacity": ".92", "display": "block",
            "textShadow": "0 1px 2px rgba(0,0,0,0.3)",
        }))

    return html.Div(kids,
        title=f"{ticker}  {ps}\n{company}\n{mc_t:.2f}T VND",
        style={
            "position": "absolute", "inset": "0",
            "backgroundColor": bg, "color": fg,
            "display": "flex", "flexDirection": "column",
            "alignItems": "center", "justifyContent": "center",
            "overflow": "hidden", "textAlign": "center",
            "padding": "2px", "boxSizing": "border-box",
            "fontFamily": "'Sora', 'JetBrains Mono', Segoe UI, sans-serif",
            "cursor": "pointer",
        },
        className="hm-cell",
    )


def _build(df, perf_col, W=1560, H=600):
    HDR = 22
    GAP = 3

    df = df.copy()
    df["mc"]   = pd.to_numeric(df["Market Cap"], errors="coerce").fillna(0)
    df["perf"] = pd.to_numeric(df[perf_col], errors="coerce")  # NaN = chưa có dữ liệu
    df = df[df["mc"] > 0]

    sector_mc = df.groupby("Sector")["mc"].sum().sort_values(ascending=False)
    s_rects   = _squarify_rects(
        list(sector_mc.values), 0, 0, W, H
    )

    out = []
    for i, (sx, sy, sw, sh) in enumerate(s_rects):
        sn  = sector_mc.index[i]
        tdf = df[df["Sector"] == sn].sort_values("mc", ascending=False)
        if tdf.empty: continue

        iw = max(sw - GAP, 1)
        ih = max(sh - HDR - GAP, 1)

        # Lọc bỏ ticker quá nhỏ: ô nào chiếm <0.3% diện tích sector thì bỏ
        mc_sum_s = tdf["mc"].sum()
        min_area = iw * ih * 0.003   # 0.3% diện tích = ~18px² trên 600x100
        min_mc   = mc_sum_s * (min_area / (iw * ih)) if iw * ih > 0 else 0
        tdf_show = tdf[tdf["mc"] >= min_mc]
        if tdf_show.empty:
            tdf_show = tdf.head(1)  # luôn hiện ít nhất 1 ô

        t_rects = _squarify_rects(
            list(tdf_show["mc"].values), 0, 0, iw, ih
        )

        cells = []
        for j, (tx, ty, tw2, th2) in enumerate(t_rects):
            if j >= len(tdf_show): break
            if tw2 < 5 or th2 < 5: continue
            row = tdf_show.iloc[j]  # FIX: removed duplicate line
            cells.append(html.Div(
                _cell(row["Ticker"], float(row["perf"]),
                      str(row.get("Company Common Name", ""))[:25],
                      float(row["mc"]) / 1e12, tw2, th2),
                style={
                    "position": "absolute",
                    "left":   f"{tx+1:.1f}px",
                    "top":    f"{ty+1:.1f}px",
                    "width":  f"{max(tw2-1, 1):.1f}px",
                    "height": f"{max(th2-1, 1):.1f}px",
                    "overflow": "hidden",
                }
            ))

        # FIX: tách accent ra dòng riêng biệt
        mc_sum = tdf["mc"].sum()
        tdf_valid = tdf.dropna(subset=["perf"])
        mc_valid  = tdf_valid["mc"].sum()
        wp = float((tdf_valid["mc"] * tdf_valid["perf"]).sum() / mc_valid) if mc_valid > 0 else float("nan")
        accent = _color(wp)

        out.append(html.Div([
            html.Div(sn, style={
                "position": "absolute", "top": "0", "left": "0",
                "width": "100%", "height": f"{HDR}px",
                "backgroundColor": "#111827",
                "borderBottom": f"2px solid {accent}",
                "color": "#f1f5f9", "fontSize": "11px", "fontWeight": "700",
                "display": "flex", "alignItems": "center", "paddingLeft": "8px",
                "boxSizing": "border-box", "zIndex": "2",
                "overflow": "hidden", "whiteSpace": "nowrap",
                "textOverflow": "ellipsis",
                "fontFamily": "'Sora', 'JetBrains Mono', Segoe UI, sans-serif",
                "letterSpacing": "0.5px", "textTransform": "uppercase",
            }),
            html.Div(cells, style={
                "position": "absolute", "top": f"{HDR}px", "left": "0",
                "width": f"{iw:.1f}px", "height": f"{ih:.1f}px",
                "overflow": "hidden",
            }),
        ], style={
            "position": "absolute",
            "left":   f"{sx + GAP/2:.1f}px",
            "top":    f"{sy + GAP/2:.1f}px",
            "width":  f"{max(sw - GAP, 1):.1f}px",
            "height": f"{max(sh - GAP, 1):.1f}px",
            "backgroundColor": "#0d1117",
            "border": "1px solid #1e2d3d",
            "borderRadius": "5px",
            "overflow": "hidden",
        }))

    return html.Div(out, style={
        "position": "relative",
        "width": "100%", "height": f"{H}px",
        "backgroundColor": "#0d1117",
        "borderRadius": "6px", "flexShrink": "0",
    })


@app.callback(
    Output("heatmap-html-container", "children"),
    Input("btn-heatmap",    "n_clicks"),
    Input("heatmap-metric", "value"),
    prevent_initial_call=False,
)
def render_heatmap(_, metric):
    try:
        from src.backend.data_loader import get_snapshot_df
        df = get_snapshot_df().copy()
        perf_col = metric if (metric and metric in df.columns) else "Perf_1W"
        for col in ["Ticker", "Company Common Name", "Sector", "Market Cap"]:
            if col not in df.columns: df[col] = ""
        if perf_col not in df.columns: df[perf_col] = 0.0
        df["Sector"] = df["Sector"].fillna("Chưa phân loại").astype(str)
        df["Sector"] = df["Sector"].replace(
            {"nan": "Chưa phân loại", "None": "Chưa phân loại", "": "Chưa phân loại"})

        LEGEND = [
            ("#1f2937", "N/A"),
            ("#065f46", ">+6%"), ("#16a34a", "+3~6%"), ("#22c55e", "+1~3%"),
            ("#86efac", "0~+1%"), ("#854d0e", "≈0%"),
            ("#ca8a04", "0~-1%"), ("#ea580c", "-1~-3%"),
            ("#dc2626", "-3~-6%"), ("#7f1d1d", "<-6%"),
        ]
        legend = html.Div([
            html.Div([
                html.Div(style={"width": "13px", "height": "13px", "borderRadius": "2px",
                                "backgroundColor": c, "marginRight": "4px"}),
                html.Span(lbl, style={"fontSize": "10px", "color": "#94a3b8", "whiteSpace": "nowrap"}),
            ], style={"display": "flex", "alignItems": "center", "marginRight": "10px"})
            for c, lbl in LEGEND
        ], style={"display": "flex", "flexWrap": "wrap", "marginBottom": "8px"})

        hm = _build(df, perf_col, W=1500, H=600)

        # Right-side vertical legend
        legend_v = html.Div([
            html.Div([
                html.Div(style={
                    "width": "12px", "height": "12px", "borderRadius": "3px",
                    "backgroundColor": c, "marginRight": "6px", "flexShrink": "0",
                    "border": "1px solid rgba(255,255,255,0.1)",
                }),
                html.Span(lbl, style={
                    "fontSize": "10px", "color": "#94a3b8",
                    "fontFamily": "'Sora', sans-serif",
                    "whiteSpace": "nowrap",
                }),
            ], style={"display": "flex", "alignItems": "center", "marginBottom": "5px"})
            for c, lbl in LEGEND
        ], style={
            "display": "flex", "flexDirection": "column",
            "padding": "10px 12px",
            "backgroundColor": "#0c1220",
            "borderRadius": "8px",
            "border": "1px solid #1e2d3d",
            "marginLeft": "10px", "flexShrink": "0",
            "alignSelf": "flex-start",
            "marginTop": "0",
        })

        return html.Div([
            html.Div([
                # 🔴 Thêm CSS thần thánh này để ép nội dung 1600px co giãn vừa khít không gian còn lại (bỏ qua legend)
                html.Div(hm, style={
                    "overflow": "hidden", 
                    "flex": "1", 
                    "minWidth": "0",
                    "width": "100%", # Chiếm trọn không gian flex 1
                }),
                legend_v,
            ], style={
                "display": "flex", 
                "alignItems": "flex-start", 
                "gap": "0", 
                "width": "100%" # Container tổng chiếm 100%
            }),
        ])

    except Exception as e:
        logger.error(f"Heatmap error: {e}")
        import traceback; traceback.print_exc()
        return html.P(f"Lỗi: {str(e)[:120]}", style={"color": "#ef4444", "fontSize": "12px"})


@app.callback(
    Output("sector-heatmap-graph", "figure"),
    Input("heatmap-metric", "value"),
    prevent_initial_call=False,
)
def _stub(_):
    return go.Figure(layout=dict(
        paper_bgcolor="#0d1117", plot_bgcolor="#0d1117",
        margin=dict(l=0, r=0, t=0, b=0), height=10,
    ))


@app.callback(
    Output("heatmap-collapse", "is_open"),
    Input("btn-heatmap",       "n_clicks"),
    State("heatmap-collapse",  "is_open"),
    prevent_initial_call=True,
)
def toggle_heatmap(n, is_open):
    return not is_open if n else is_open

# ── CSS theme constants ───────────────────────────────────────────────────────
_C = {
    "bg":       "#0d1117",
    "card":     "#0c1220",
    "border":   "#1e2d3d",
    "border2":  "#21262d",
    "text":     "#c9d1d9",
    "muted":    "#8b949e",
    "accent":   "#3b82f6",
    "green":    "#10b981",
    "red":      "#ef4444",
    "yellow":   "#f59e0b",
    "orange":   "#f97316",
    "font":     "'Sora', 'JetBrains Mono', 'Segoe UI', sans-serif",
}

def _card(children, style_extra=None):
    """Card chuẩn VSS theme."""
    s = {
        "backgroundColor": _C["card"],
        "border":          f"1px solid {_C['border']}",
        "borderRadius":    "8px",
        "padding":         "14px",
    }
    if style_extra:
        s.update(style_extra)
    return html.Div(children, style=s)


def _label(text, style_extra=None):
    s = {"fontSize": "10px", "fontWeight": "700", "letterSpacing": "1.2px",
         "color": _C["muted"], "textTransform": "uppercase",
         "marginBottom": "8px", "fontFamily": _C["font"]}
    if style_extra:
        s.update(style_extra)
    return html.Div(text, style=s)


def _regime_badge(label, color):
    return html.Div([
        html.Div(style={
            "width": "8px", "height": "8px", "borderRadius": "50%",
            "backgroundColor": color, "marginRight": "8px", "flexShrink": "0",
            "boxShadow": f"0 0 6px {color}",
        }),
        html.Span(label, style={
            "fontSize": "13px", "fontWeight": "700",
            "color": color, "fontFamily": _C["font"],
        }),
    ], style={"display": "flex", "alignItems": "center"})


_SECTOR_SUB = {
    "Energy":                 "Dầu khí & Năng lượng",
    "Financials":             "Tài chính (Ngân hàng, CK, Bảo hiểm)",
    "Utilities":              "Tiện ích (Điện, Nước, Gas)",
    "Materials":              "Nguyên vật liệu, Hóa chất, Khai khoáng",
    "Industrials":            "Công nghiệp & Vận tải",
    "Consumer Discretionary": "Bán lẻ, Dịch vụ, Du lịch",
    "Health Care":            "Y tế & Dược phẩm",
    "Consumer Staples":       "Hàng tiêu dùng thiết yếu & Thực phẩm",
    "Information Technology": "Công nghệ Thông tin",
    "Real Estate":            "Bất động sản & Xây dựng",
    "Communication Services": "Truyền thông & Viễn thông",
}

def _sbs_bar_row(rank, sector, sbs, delta=None, color="#3b82f6", n_stocks=0):
    """Một hàng trong bảng xếp hạng ngành — clickable."""
    delta_el = html.Span()
    if delta is not None:
        sign  = "▲" if delta > 0.05 else ("▼" if delta < -0.05 else "—")
        dcol  = _C["green"] if delta > 0.05 else (_C["red"] if delta < -0.05 else _C["muted"])
        delta_el = html.Span(
            f"{sign} {abs(delta):.1f}",
            style={"fontSize": "11px", "color": dcol, "fontFamily": _C["font"],
                   "minWidth": "52px", "textAlign": "right"},
        )

    sub = _SECTOR_SUB.get(sector, "")
    n_label = f" (n={n_stocks})" if n_stocks == 0 else ""

    return html.Div([
        html.Div([
            # Rank
            html.Span(f"{rank:02d}", style={
                "fontSize": "11px", "color": _C["muted"],
                "fontFamily": _C["font"], "minWidth": "24px",
                "flexShrink": "0",
            }),
            # Tên ngành + sub
            html.Div([
                html.Div(f"{sector}{n_label}", style={
                    "fontSize": "13px", "fontWeight": "600",
                    "color": _C["text"], "fontFamily": _C["font"],
                    "lineHeight": "1.2",
                }),
                html.Div(sub, style={
                    "fontSize": "10px", "color": _C["muted"],
                    "fontFamily": _C["font"], "lineHeight": "1.2",
                    "marginTop": "1px",
                }),
            ], style={"flex": "1", "minWidth": "0"}),
            # Score + delta
            html.Div([
                html.Span(f"{sbs:.1f}", style={
                    "fontSize": "20px", "fontWeight": "800",
                    "color": color, "fontFamily": _C["font"],
                    "lineHeight": "1",
                }),
                delta_el,
            ], style={"display": "flex", "flexDirection": "column",
                      "alignItems": "flex-end", "gap": "2px"}),
        ], style={"display": "flex", "alignItems": "center",
                  "gap": "10px", "marginBottom": "5px"}),
        # Progress bar
        html.Div(
            html.Div(style={
                "width":  f"{min(sbs, 100):.0f}%",
                "height": "100%",
                "backgroundColor": color,
                "borderRadius": "2px",
                "transition": "width 0.4s ease",
            }),
            style={
                "height": "3px", "backgroundColor": "#1e2d3d",
                "borderRadius": "2px", "marginLeft": "34px",
            },
        ),
    ], style={
        "padding": "10px 14px",
        "borderBottom": f"1px solid {_C['border2']}",
        "cursor": "pointer",
        "transition": "background 0.15s",
        "_hover": {"backgroundColor": "#111827"},
    },
        id={"type": "sector-rank-row", "index": sector},
        n_clicks=0,
    )

@app.callback(
    Output("breadth-xray-container", "children"),
    Input("btn-heatmap",             "n_clicks"),
    Input("heatmap-exchange-filter", "value"),
    State("heatmap-collapse",        "is_open"),
    prevent_initial_call=False,
)
def render_breadth_xray(_, exchange, is_open):
    """
    Render toàn bộ khu vực X-Ray Dòng Tiền bên dưới treemap heatmap.
    """
    import plotly.graph_objects as go
    import plotly.express as px

    try:
        from src.backend.data_loader import (
            get_market_internals,
            get_market_internals_history,
        )

        exchange = exchange or "HOSE"
        result   = get_market_internals(exchange_filter=exchange)

        if not result:
            return html.P("Đang tính toán dữ liệu dòng tiền...",
                          style={"color": _C["muted"], "fontSize": "12px",
                                 "padding": "20px 0"})

        sdf        = result["sector_sbs"]       # DataFrame ngành
        mkt_sbs    = result["market_sbs"]
        regime     = result["regime"]
        r_clr      = result["regime_color"]
        top3       = result["top_sectors"]
        weak3      = result["weak_sectors"]

        # ── Tier color cho từng hàng ──────────────────────────────────────────
        from src.backend.quant_engine import _sbs_tier

        # ══════════════════════════════════════════════════════════════════════
        # PANEL 2: Bảng xếp hạng ngành
        # ══════════════════════════════════════════════════════════════════════
        rank_rows = []
        for i, row in sdf.iterrows():
            _, clr = _sbs_tier(row["SBS"])
            rank_rows.append(
                _sbs_bar_row(
                    i + 1, row["Sector"], row["SBS"],
                    delta=None,
                    color=clr,
                    n_stocks=int(row.get("N", 0)),
                )
            )

        panel_ranking = _card([
            html.Div([
                _label("XẾP HẠNG SỨC MẠNH NGÀNH", {"marginBottom": "0"}),
                html.Span(f"11 NGÀNH GICS · NHẤP CHUỘT ĐỂ XEM CHI TIẾT", style={
                    "fontSize": "9px", "color": _C["muted"],
                    "fontFamily": _C["font"], "letterSpacing": "1px",
                }),
            ], style={"display": "flex", "justifyContent": "space-between",
                      "alignItems": "center", "marginBottom": "12px"}),
            *rank_rows,
        ], style_extra={"padding": "14px 0"})

        # ── Panel phải: Regime + Top/Weak ─────────────────────────────────────
        panel_regime_card = _card([
            # Market SBS
            html.Div([
                html.Div([
                    html.Div("ĐIỂM ĐỘ RỘNG THỊ TRƯỜNG (SBS)", style={
                        "fontSize": "9px", "letterSpacing": "1.5px",
                        "color": _C["muted"], "fontFamily": _C["font"],
                        "marginBottom": "6px",
                    }),
                    html.Div([
                        html.Span(f"{mkt_sbs}", style={
                            "fontSize": "48px", "fontWeight": "800",
                            "color": r_clr, "lineHeight": "1",
                            "fontFamily": _C["font"],
                        }),
                        html.Span(" /100", style={
                            "fontSize": "16px", "color": _C["muted"],
                            "fontFamily": _C["font"], "marginLeft": "4px",
                        }),
                    ]),
                ], style={"flex": "1"}),
                html.Div([
                    html.Div("TRẠNG THÁI THỊ TRƯỜNG", style={
                        "fontSize": "9px", "letterSpacing": "1.5px",
                        "color": _C["muted"], "fontFamily": _C["font"],
                        "marginBottom": "6px",
                    }),
                    html.Div(regime, style={
                        "fontSize": "20px", "fontWeight": "800",
                        "color": r_clr, "fontFamily": _C["font"],
                        "lineHeight": "1.2",
                    }),
                    html.Div(
                        "Suy yếu diện rộng — Rủi ro hệ thống"
                        if "Bear" in regime else
                        "Xác nhận Uptrend — Duy trì tỷ trọng",
                        style={"fontSize": "10px", "color": _C["muted"],
                               "fontFamily": _C["font"], "marginTop": "4px"}
                    ),
                ], style={"flex": "1", "paddingLeft": "20px",
                          "borderLeft": f"1px solid {_C['border']}"}),
            ], style={"display": "flex", "marginBottom": "16px",
                      "paddingBottom": "16px",
                      "borderBottom": f"1px solid {_C['border']}"}),

            # Top + Weak
            html.Div([
                html.Div([
                    _label("NHÓM DẪN DẮT (MẠNH NHẤT)"),
                    *[html.Div([
                        html.Span(r["Sector"], style={
                            "fontSize": "11px", "color": _C["green"],
                            "fontFamily": _C["font"], "flex": "1",
                        }),
                        html.Span(f"{r['SBS']:.1f}", style={
                            "fontSize": "12px", "fontWeight": "700",
                            "color": _C["green"], "fontFamily": _C["font"],
                        }),
                        html.Div(
                            html.Div(style={
                                "width": f"{r['SBS']:.0f}%", "height": "100%",
                                "backgroundColor": _C["green"], "borderRadius": "1px",
                            }),
                            style={"width": "80px", "height": "3px",
                                   "backgroundColor": "#1e2d3d",
                                   "borderRadius": "1px", "marginLeft": "8px"},
                        ),
                    ], style={"display": "flex", "alignItems": "center",
                              "gap": "6px", "marginBottom": "8px",
                              "paddingBottom": "8px",
                              "borderBottom": f"1px solid {_C['border2']}"})
                      for r in top3],
                ], style={"flex": "1"}),
                html.Div([
                    _label("NHÓM SUY YẾU (YẾU NHẤT)"),
                    *[html.Div([
                        html.Span(r["Sector"], style={
                            "fontSize": "11px", "color": _C["red"],
                            "fontFamily": _C["font"], "flex": "1",
                        }),
                        html.Span(f"{r['SBS']:.1f}", style={
                            "fontSize": "12px", "fontWeight": "700",
                            "color": _C["red"], "fontFamily": _C["font"],
                        }),
                        html.Div(
                            html.Div(style={
                                "width": f"{r['SBS']:.0f}%", "height": "100%",
                                "backgroundColor": _C["red"], "borderRadius": "1px",
                            }),
                            style={"width": "80px", "height": "3px",
                                   "backgroundColor": "#1e2d3d",
                                   "borderRadius": "1px", "marginLeft": "8px"},
                        ),
                    ], style={"display": "flex", "alignItems": "center",
                              "gap": "6px", "marginBottom": "8px",
                              "paddingBottom": "8px",
                              "borderBottom": f"1px solid {_C['border2']}"})
                      for r in weak3],
                ], style={"flex": "1", "paddingLeft": "20px",
                          "borderLeft": f"1px solid {_C['border']}"}),
            ], style={"display": "flex"}),
        ])

        # ══════════════════════════════════════════════════════════════════════
        # PANEL 3: Heatmap 60 phiên (Phase 2)
        # ══════════════════════════════════════════════════════════════════════
        panel_heatmap60 = html.Div()  # placeholder
        try:
            df_hist = get_market_internals_history(exchange_filter=exchange)
            if df_hist is not None and not df_hist.empty:
                pivot_hm = df_hist.pivot_table(
                    index="Sector", columns="Date", values="SBS"
                )
                sector_order = sdf["Sector"].tolist()
                pivot_hm = pivot_hm.reindex(
                    [s for s in sector_order if s in pivot_hm.index]
                )
                date_labels = [
                    d.strftime("%d/%m") if hasattr(d, "strftime") else str(d)
                    for d in pivot_hm.columns
                ]

                fig_hm = go.Figure(go.Heatmap(
                    z=pivot_hm.values,
                    x=date_labels,
                    y=pivot_hm.index.tolist(),
                    zmin=0, zmax=100,
                    colorscale=[
                        [0.00, "#7f1d1d"],
                        [0.34, "#dc2626"],
                        [0.50, "#f59e0b"],
                        [0.65, "#34d399"],
                        [1.00, "#065f46"],
                    ],
                    showscale=True,
                    colorbar=dict(
                        title=dict(
                            text="SBS",
                            font=dict(color=_C["muted"], size=10),
                        ),
                        tickfont=dict(color=_C["muted"], size=9),
                        thickness=12,
                        len=0.8,
                    ),
                    hovertemplate=(
                        "<b>%{y}</b><br>Ngày: %{x}<br>SBS: %{z:.1f}<extra></extra>"
                    ),
                ))
                fig_hm.update_layout(
                    paper_bgcolor=_C["bg"],
                    plot_bgcolor=_C["card"],
                    margin=dict(l=140, r=60, t=20, b=40),
                    height=320,
                    xaxis=dict(
                        tickfont=dict(color=_C["muted"], size=8),
                        showgrid=False,
                        tickangle=-45,
                        nticks=20,
                    ),
                    yaxis=dict(
                        tickfont=dict(color=_C["text"], size=10),
                        showgrid=False,
                    ),
                    font=dict(family=_C["font"]),
                )

                panel_heatmap60 = _card([
                    _label("BẢN ĐỒ NHIỆT 60 PHIÊN — Luân chuyển dòng tiền các ngành"),
                    dcc.Graph(
                        figure=fig_hm,
                        config={"displayModeBar": False},
                        style={"marginTop": "8px"},
                    ),
                ], style_extra={"marginTop": "12px"})

        except Exception as e:
            logger.warning(f"Heatmap 60 phiên error: {e}")

        # ══════════════════════════════════════════════════════════════════════
        # PANEL 4: Line chart VN-Index vs Market SBS
        # ══════════════════════════════════════════════════════════════════════
        panel_divergence = html.Div()
        try:
            df_hist2 = get_market_internals_history(exchange_filter=exchange)
            if df_hist2 is not None and not df_hist2.empty:
                mkt_daily = (
                    df_hist2.groupby("Date")
                    .apply(lambda g: (g["SBS"] * g["N"]).sum() / g["N"].sum()
                           if g["N"].sum() > 0 else None, include_groups=False)
                    .dropna()
                    .reset_index()
                )
                mkt_daily.columns = ["Date", "Market_SBS"]

                from src.backend.data_loader import load_index_data
                df_idx = load_index_data()
                if df_idx is not None and not df_idx.empty:
                    df_idx["Date"] = pd.to_datetime(df_idx["Date"])
                    merged = mkt_daily.merge(
                        df_idx[["Date","VNINDEX_Close"]],
                        on="Date", how="left"
                    ).dropna()

                    if len(merged) >= 5:
                        sbs_slope5  = float(np.polyfit(
                            range(min(5, len(merged))),
                            merged["Market_SBS"].tail(5).values, 1)[0])
                        vnx_slope5  = float(np.polyfit(
                            range(min(5, len(merged))),
                            merged["VNINDEX_Close"].tail(5).values, 1)[0])

                        diverging   = (sbs_slope5 < -0.1 and vnx_slope5 >= 0)
                        div_label   = "⚠️ PHÂN KỲ — Tiềm ẩn rủi ro giảm điểm" if diverging else "Đồng thuận (Khỏe)"
                        div_color   = _C["red"] if diverging else _C["green"]

                        fig_div = go.Figure()
                        fig_div.add_trace(go.Scatter(
                            x=merged["Date"], y=merged["VNINDEX_Close"],
                            name="VN-Index", yaxis="y1",
                            line=dict(color="#f59e0b", width=1.5),
                            hovertemplate="VN-Index: %{y:.0f}<extra></extra>",
                        ))
                        fig_div.add_trace(go.Scatter(
                            x=merged["Date"], y=merged["Market_SBS"],
                            name="Sức mạnh TT (SBS)", yaxis="y2",
                            line=dict(color=_C["accent"], width=1.5,
                                      dash="dot"),
                            hovertemplate="Điểm SBS: %{y:.1f}<extra></extra>",
                        ))
                        fig_div.update_layout(
                            paper_bgcolor=_C["bg"],
                            plot_bgcolor=_C["card"],
                            margin=dict(l=50, r=60, t=20, b=30),
                            height=220,
                            legend=dict(
                                orientation="h", x=0, y=1.08,
                                font=dict(color=_C["muted"], size=10),
                                bgcolor="rgba(0,0,0,0)",
                            ),
                            hovermode="x unified",
                            xaxis=dict(
                                showgrid=False, tickfont=dict(
                                    color=_C["muted"], size=9)),
                            yaxis=dict(
                                showgrid=True,
                                gridcolor="#1e2d3d",
                                tickfont=dict(color="#f59e0b", size=9),
                                side="left",
                            ),
                            yaxis2=dict(
                                overlaying="y", side="right",
                                range=[0, 100],
                                showgrid=False,
                                tickfont=dict(color=_C["accent"], size=9),
                            ),
                            font=dict(family=_C["font"]),
                        )

                        panel_divergence = _card([
                            html.Div([
                                _label("PHÂN KỲ CHỈ SỐ VS DÒNG TIỀN NỘI TẠI",
                                       {"marginBottom": "0"}),
                                html.Span(div_label, style={
                                    "fontSize": "11px", "fontWeight": "700",
                                    "color": div_color,
                                    "fontFamily": _C["font"],
                                    "marginLeft": "auto",
                                }),
                            ], style={"display": "flex", "alignItems": "center",
                                      "marginBottom": "10px"}),
                            dcc.Graph(
                                figure=fig_div,
                                config={"displayModeBar": False},
                            ),
                        ], style_extra={"marginTop": "12px"})

        except Exception as e:
            logger.warning(f"Divergence chart error: {e}")

        # ══════════════════════════════════════════════════════════════════════
        # PANEL 5: Radar + Chi tiết ngành (click từ bảng xếp hạng)
        # ══════════════════════════════════════════════════════════════════════
        panel_detail = _card([
            _label("PHÂN TÍCH CHI TIẾT NGÀNH — Chọn một ngành trên bảng xếp hạng để xem"),
            dcc.Store(id="selected-sector-store", data=None),
            html.Div(id="sector-detail-container",
                     style={"color": _C["muted"], "fontSize": "12px",
                            "textAlign": "center", "padding": "20px 0"}),
        ], style_extra={"marginTop": "12px"})

        # ── Divider tiêu đề X-Ray ─────────────────────────────────────────────
        xray_header = html.Div([
            html.Div(style={"flex": "1", "height": "1px",
                            "backgroundColor": _C["border"]}),
            html.Span("DÒNG TIỀN ĐỊNH LƯỢNG", style={
                "fontSize": "10px", "fontWeight": "700",
                "letterSpacing": "2px", "color": _C["muted"],
                "padding": "0 14px", "fontFamily": _C["font"],
            }),
            html.Div(style={"flex": "1", "height": "1px",
                            "backgroundColor": _C["border"]}),
        ], style={"display": "flex", "alignItems": "center",
                  "margin": "20px 0 14px 0"})

        # ── Return layout tổng ────────────────────────────────────────────────
        return html.Div([
            xray_header,
            panel_regime_card,
            html.Div([
                html.Div(panel_ranking,
                         style={"flex": "1.2", "minWidth": "0"}),
                html.Div([
                    panel_divergence if panel_divergence.children else html.Div(),
                ], style={"flex": "1", "minWidth": "0"}),
            ], style={"display": "flex", "gap": "12px", "marginTop": "12px"}),
            panel_heatmap60,
            panel_detail,
        ])

    except Exception as e:
        logger.error(f"render_breadth_xray error: {e}")
        import traceback; traceback.print_exc()
        return html.P(f"Lỗi X-Ray: {str(e)[:120]}",
                      style={"color": _C["red"], "fontSize": "12px"})


@app.callback(
    Output("sector-detail-container", "children"),
    Input("selected-sector-store",    "data"),
    State("heatmap-exchange-filter",  "value"),
    prevent_initial_call=True,
)
def render_sector_detail(selected_sector, exchange):
    """Radar 6 cánh + 60-session trajectory + constituents khi click ngành."""
    import plotly.graph_objects as go
    if not selected_sector:
        return html.Div()

    try:
        from src.backend.data_loader import (
            get_market_internals,
            get_market_internals_history,
            get_snapshot_df,
        )
        from src.backend.quant_engine import _sbs_tier

        result  = get_market_internals(exchange_filter=exchange or "HOSE")
        df_snap = get_snapshot_df()
        if not result:
            return html.Div()

        sdf = result["sector_sbs"]
        row = sdf[sdf["Sector"] == selected_sector]
        if row.empty:
            return html.Div()
        row = row.iloc[0]

        sbs, clr = row["SBS"], row["SBS_Color"]

        # ── Radar 6 cánh ─────────────────────────────────────────────────────
        categories = ["% CP Vượt MA50","% CP Vượt MA200","Tỷ lệ Tăng/Giảm (A/D)","Đỉnh-Đáy (H-L)",
                      "Động lượng RSI>50","Thanh khoản"]
        values = [row["P_MA50"], row["P_MA200"], row["AD_20"],
                  row["HL"],     row["RSI_D"],   row["VB_20"]]
        values_closed = values + [values[0]]
        cats_closed   = categories + [categories[0]]

        fig_radar = go.Figure(go.Scatterpolar(
            r=values_closed, theta=cats_closed,
            fill="toself", fillcolor=f"rgba(59,130,246,0.15)",
            line=dict(color=_C["accent"], width=1.8),
            hovertemplate="%{theta}: %{r:.1f}<extra></extra>",
        ))
        fig_radar.update_layout(
            polar=dict(
                bgcolor=_C["card"],
                radialaxis=dict(
                    visible=True, range=[0, 100],
                    tickfont=dict(color=_C["muted"], size=8),
                    gridcolor="#1e2d3d", linecolor="#1e2d3d",
                ),
                angularaxis=dict(
                    tickfont=dict(color=_C["text"], size=9),
                    linecolor="#1e2d3d", gridcolor="#1e2d3d",
                ),
            ),
            paper_bgcolor=_C["bg"],
            margin=dict(l=40, r=40, t=30, b=30),
            height=260,
            showlegend=False,
            font=dict(family=_C["font"]),
        )

        # ── 60-session trajectory ─────────────────────────────────────────────
        trajectory_el = html.Div()
        try:
            df_hist = get_market_internals_history(exchange_filter=exchange or "HOSE")
            if df_hist is not None and not df_hist.empty:
                sector_hist = df_hist[df_hist["Sector"] == selected_sector].sort_values("Date")
                if not sector_hist.empty:
                    fig_traj = go.Figure(go.Scatter(
                        x=sector_hist["Date"],
                        y=sector_hist["SBS"],
                        fill="tozeroy",
                        fillcolor="rgba(59,130,246,0.08)",
                        line=dict(color=_C["accent"], width=1.5),
                        hovertemplate="SBS: %{y:.1f}<extra></extra>",
                    ))
                    # Vẽ các ngưỡng tier
                    for thr, lbl, tclr in [(65,"Mạnh","#34d399"),(50,"T.Bình","#f59e0b"),(35,"Yếu","#f97316")]:
                        fig_traj.add_hline(
                            y=thr, line_dash="dot",
                            line_color=tclr, opacity=0.5,
                            annotation_text=lbl,
                            annotation_font=dict(color=tclr, size=8),
                        )
                    fig_traj.update_layout(
                        paper_bgcolor=_C["bg"],
                        plot_bgcolor=_C["card"],
                        margin=dict(l=40, r=20, t=10, b=30),
                        height=220,
                        yaxis=dict(
                            range=[0, 100], showgrid=True,
                            gridcolor="#1e2d3d",
                            tickfont=dict(color=_C["muted"], size=9),
                        ),
                        xaxis=dict(
                            showgrid=False,
                            tickfont=dict(color=_C["muted"], size=9),
                        ),
                        font=dict(family=_C["font"]),
                    )
                    trajectory_el = html.Div([
                        _label("XU HƯỚNG DÒNG TIỀN 60 PHIÊN"),
                        dcc.Graph(figure=fig_traj,
                                  config={"displayModeBar": False}),
                    ], style={"marginTop": "14px"})
        except Exception:
            pass

        # ── 6 factor breakdown bars ───────────────────────────────────────────
        factor_rows = []
        for fname, val, weight in [
            ("% Cổ phiếu nằm trên MA50",  row["P_MA50"],  "Tỷ trọng: 20%"),
            ("% Cổ phiếu nằm trên MA200", row["P_MA200"], "Tỷ trọng: 20%"),
            ("Tỷ lệ Tăng/Giảm (A/D 20)",row["AD_20"], "Tỷ trọng: 15%"),
            ("Chỉ số Đỉnh-Đáy mới (H-L)", row["HL"],      "Tỷ trọng: 15%"),
            ("Độ rộng Động lượng (RSI>50)",row["RSI_D"],"Tỷ trọng: 10%"),
            ("Độ rộng Thanh khoản (VB 20)",row["VB_20"],   "Tỷ trọng: 20%"),
        ]:
            _, fcol = _sbs_tier(val)
            factor_rows.append(html.Div([
                html.Div([
                    html.Span(fname, style={
                        "fontSize": "11px", "color": _C["text"],
                        "fontFamily": _C["font"], "flex": "1",
                    }),
                    html.Span(weight, style={
                        "fontSize": "9px", "color": _C["muted"],
                        "fontFamily": _C["font"],
                    }),
                ], style={"display": "flex", "justifyContent": "space-between",
                          "marginBottom": "3px"}),
                html.Div([
                    html.Div(
                        html.Div(style={
                            "width":  f"{min(val,100):.0f}%", "height": "100%",
                            "backgroundColor": fcol, "borderRadius": "2px",
                            "opacity": "0.8",
                        }),
                        style={"flex": "1", "height": "6px",
                               "backgroundColor": "#1e2d3d",
                               "borderRadius": "2px"},
                    ),
                    html.Span(f"{val:.1f}", style={
                        "fontSize": "11px", "fontWeight": "700",
                        "color": fcol, "fontFamily": _C["font"],
                        "minWidth": "34px", "textAlign": "right",
                        "marginLeft": "10px",
                    }),
                ], style={"display": "flex", "alignItems": "center"}),
            ], style={"marginBottom": "10px",
                      "paddingBottom": "10px",
                      "borderBottom": f"1px solid {_C['border2']}"}))

        # ── Constituents ──────────────────────────────────────────────────────
        consti_el = html.Div()
        if df_snap is not None and "Sector" in df_snap.columns:
            consti = df_snap[df_snap["Sector"] == selected_sector][["Ticker","Perf_1W"]].copy()
            consti["Perf_1W"] = pd.to_numeric(consti["Perf_1W"], errors="coerce")
            consti = consti.sort_values("Perf_1W", ascending=False)

            def _badge_color(p):
                if pd.isna(p): return "#374151", "#6b7280"
                if p > 3:  return "#065f46", "#10b981"
                if p > 0:  return "#1a3a2a", "#34d399"
                if p > -3: return "#3a1f0d", "#f97316"
                return "#3b0d0d", "#ef4444"

            badges = []
            for _, crow in consti.iterrows():
                bg, fg = _badge_color(crow["Perf_1W"])
                perf_txt = (f"{crow['Perf_1W']:+.1f}%"
                            if pd.notna(crow["Perf_1W"]) else "")
                badges.append(html.Div([
                    html.Span(crow["Ticker"], style={
                        "fontSize": "11px", "fontWeight": "700",
                        "color": fg, "display": "block",
                    }),
                    html.Span(perf_txt, style={
                        "fontSize": "9px", "color": fg, "opacity": "0.8",
                    }),
                ], style={
                    "backgroundColor": bg, "border": f"1px solid {fg}33",
                    "borderRadius": "4px", "padding": "4px 7px",
                    "cursor": "pointer",
                }))

            consti_el = html.Div([
                _label(f"DANH SÁCH CỔ PHIẾU TRONG NGÀNH — {len(consti)} mã",
                       {"marginTop": "16px"}),
                html.Div(badges, style={
                    "display": "flex", "flexWrap": "wrap", "gap": "6px",
                }),
            ])

        return html.Div([
            # Header ngành
            html.Div([
                html.Div([
                    html.Div(selected_sector, style={
                        "fontSize": "18px", "fontWeight": "800",
                        "color": _C["text"], "fontFamily": _C["font"],
                    }),
                    html.Div(f"Điểm SBS: {sbs:.1f}", style={
                        "fontSize": "13px", "color": clr,
                        "fontFamily": _C["font"], "marginTop": "2px",
                    }),
                ], style={"flex": "1"}),
                html.Div(row["SBS_Label"], style={
                    "fontSize": "11px", "fontWeight": "700",
                    "color": clr, "fontFamily": _C["font"],
                    "backgroundColor": f"{clr}22",
                    "padding": "4px 10px", "borderRadius": "12px",
                    "border": f"1px solid {clr}44",
                }),
            ], style={"display": "flex", "alignItems": "center",
                      "marginBottom": "16px"}),

            # 2 cột: radar + factors
            html.Div([
                html.Div([
                    _label("RADAR 6 YẾU TỐ ĐỘ RỘNG"),
                    dcc.Graph(figure=fig_radar,
                              config={"displayModeBar": False}),
                ], style={"flex": "1"}),
                html.Div([
                    _label("BÓC TÁCH CÁC CHỈ SỐ"),
                    *factor_rows,
                ], style={"flex": "1", "paddingLeft": "20px"}),
            ], style={"display": "flex", "gap": "20px"}),

            trajectory_el,
            consti_el,
        ])

    except Exception as e:
        logger.error(f"render_sector_detail error: {e}")
        return html.P(f"Lỗi: {e}", style={"color": _C["red"]})
    

@app.callback(
    Output("selected-sector-store", "data"),
    Input({"type": "sector-rank-row", "index": ALL}, "n_clicks"),
    State({"type": "sector-rank-row", "index": ALL}, "id"),
    prevent_initial_call=True,
)
def select_sector(n_clicks_list, id_list):
    from dash import callback_context, no_update
    ctx = callback_context
    if not ctx.triggered or not any(n_clicks_list):
        return no_update
    try:
        triggered = json.loads(ctx.triggered[0]["prop_id"].split(".")[0])
        return triggered["index"]
    except Exception:
        return no_update