# src/callbacks/heatmap_callbacks.py
from dash import Input, Output, State, html
from src.app_instance import app
import plotly.graph_objects as go
import pandas as pd
import numpy as np
import math, logging

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