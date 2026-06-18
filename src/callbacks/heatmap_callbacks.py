# src/callbacks/heatmap_callbacks.py
from dash import Input, Output, State, html, dcc, ALL, callback_context, no_update
from src.app_instance import app
import plotly.graph_objects as go
import pandas as pd
import numpy as np
import math, logging, json

logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════════════════════════
# PHẦN 1: HEATMAP TOÀN THỊ TRƯỜNG (giữ nguyên + thêm exchange filter)
# ══════════════════════════════════════════════════════════════════════════════

def _color(v):
    try: v = float(v)
    except: return "#1f2937"
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
    values = [max(v, 0) for v in values]
    total  = sum(values)
    if total <= 0 or w <= 0 or h <= 0:
        return [(x, y, w/max(len(values),1), h)] * len(values)
    try:
        import squarify
        norm  = squarify.normalize_sizes(values, w, h)
        rects = squarify.squarify(norm, x, y, w, h)
        return [(r["x"], r["y"], r["dx"], r["dy"]) for r in rects]
    except ImportError:
        result, pos = [], x
        for v in values:
            bw = w * v / total
            result.append((pos, y, bw, h))
            pos += bw
        return result


def _cell(ticker, perf, company, mc_t, tw, th):
    bg     = _color(perf)
    fg     = "#000" if bg in {"#86efac", "#22c55e"} else "#fff"
    is_nan = perf is None or (isinstance(perf, float) and math.isnan(perf))
    ps     = f"{perf:+.2f}%" if not is_nan else "N/A"
    if is_nan: bg = "#1f2937"; fg = "#4b5563"
    fs = max(8, min(18, int(min(tw, th) / 2.8)))

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
    df["perf"] = pd.to_numeric(df[perf_col], errors="coerce")
    df = df[df["mc"] > 0]

    sector_mc = df.groupby("Sector")["mc"].sum().sort_values(ascending=False)
    s_rects   = _squarify_rects(list(sector_mc.values), 0, 0, W, H)

    out = []
    for i, (sx, sy, sw, sh) in enumerate(s_rects):
        sn  = sector_mc.index[i]
        tdf = df[df["Sector"] == sn].sort_values("mc", ascending=False)
        if tdf.empty: continue

        iw = max(sw - GAP, 1)
        ih = max(sh - HDR - GAP, 1)

        mc_sum_s = tdf["mc"].sum()
        min_area = iw * ih * 0.003
        min_mc   = mc_sum_s * (min_area / (iw * ih)) if iw * ih > 0 else 0
        tdf_show = tdf[tdf["mc"] >= min_mc]
        if tdf_show.empty:
            tdf_show = tdf.head(1)

        t_rects = _squarify_rects(list(tdf_show["mc"].values), 0, 0, iw, ih)

        cells = []
        for j, (tx, ty, tw2, th2) in enumerate(t_rects):
            if j >= len(tdf_show): break
            if tw2 < 5 or th2 < 5: continue
            row = tdf_show.iloc[j]
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

        tdf_valid = tdf.dropna(subset=["perf"])
        mc_valid  = tdf_valid["mc"].sum()
        wp     = float((tdf_valid["mc"] * tdf_valid["perf"]).sum() / mc_valid) if mc_valid > 0 else float("nan")
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


# ── Heatmap toàn thị trường — thêm exchange filter ───────────────────────────
@app.callback(
    Output("heatmap-html-container", "children"),
    Input("btn-heatmap",             "n_clicks"),
    Input("heatmap-metric",          "value"),
    Input("heatmap-exchange-filter", "value"),   # ← MỚI: lọc theo sàn
    prevent_initial_call=False,
)
def render_heatmap(_, metric, exchange):
    try:
        from src.backend.data_loader import get_snapshot_df
        df = get_snapshot_df().copy()

        # Lọc sàn cho heatmap toàn thị trường
        exchange = exchange or "HOSE"
        if exchange != "ALL" and "Exchange" in df.columns:
            df = df[df["Exchange"] == exchange]

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

        hm = _build(df, perf_col, W=1500, H=600)

        legend_v = html.Div([
            html.Div([
                html.Div(style={
                    "width": "12px", "height": "12px", "borderRadius": "3px",
                    "backgroundColor": c, "marginRight": "6px", "flexShrink": "0",
                    "border": "1px solid rgba(255,255,255,0.1)",
                }),
                html.Span(lbl, style={
                    "fontSize": "10px", "color": "#94a3b8",
                    "fontFamily": "'Sora', sans-serif", "whiteSpace": "nowrap",
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
        })

        return html.Div([
            html.Div([
                html.Div(hm, style={"overflow": "hidden", "flex": "1", "minWidth": "0"}),
                legend_v,
            ], style={"display": "flex", "alignItems": "flex-start", "gap": "0", "width": "100%"}),
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


# ══════════════════════════════════════════════════════════════════════════════
# PHẦN 2: X-RAY DÒNG TIỀN — HELPERS
# ══════════════════════════════════════════════════════════════════════════════

_C = {
    "bg":     "#0d1117",
    "card":   "#0c1220",
    "border": "#1e2d3d",
    "border2":"#21262d",
    "text":   "#c9d1d9",
    "muted":  "#8b949e",
    "accent": "#3b82f6",
    "green":  "#10b981",
    "red":    "#ef4444",
    "yellow": "#f59e0b",
    "orange": "#f97316",
    "font":   "'Sora', 'JetBrains Mono', 'Segoe UI', sans-serif",
}

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


def _card(children, style_extra=None):
    s = {
        "backgroundColor": _C["card"],
        "border":          f"1px solid {_C['border']}",
        "borderRadius":    "8px",
        "padding":         "16px 24px",   # padding đều hơn, tránh tràn biên
        "boxSizing":       "border-box",
        "overflow":        "hidden",       # chặn tràn ngang
    }
    if style_extra:
        s.update(style_extra)
    return html.Div(children, style=s)


def _label(text, style_extra=None):
    s = {"fontSize": "12px", "fontWeight": "700", "letterSpacing": "1.4px",
         "color": _C["muted"], "textTransform": "uppercase",
         "marginBottom": "10px", "fontFamily": _C["font"]}
    if style_extra:
        s.update(style_extra)
    return html.Div(text, style=s)


def _sbs_bar_row(rank, sector, sbs, delta=None, color="#3b82f6", n_stocks=0):
    """Một hàng clickable trong bảng xếp hạng ngành."""
    delta_el = html.Span()
    if delta is not None:
        sign = "▲" if delta > 0.05 else ("▼" if delta < -0.05 else "—")
        dcol = _C["green"] if delta > 0.05 else (_C["red"] if delta < -0.05 else _C["muted"])
        delta_el = html.Span(
            f"{sign} {abs(delta):.1f}",
            style={"fontSize": "11px", "color": dcol,
                   "fontFamily": _C["font"], "minWidth": "52px", "textAlign": "right"},
        )

    sub     = _SECTOR_SUB.get(sector, "")
    n_label = f" (n={n_stocks})" if n_stocks == 0 else ""

    return html.Div([
        html.Div([
            html.Span(f"{rank:02d}", style={
                "fontSize": "14px", "color": _C["muted"],
                "fontFamily": _C["font"], "minWidth": "26px", "flexShrink": "0",
            }),
            html.Div([
                html.Div(f"{sector}{n_label}", style={
                    "fontSize": "14px", "fontWeight": "600",
                    "color": _C["text"], "fontFamily": _C["font"], "lineHeight": "1.2",
                }),
                html.Div(sub, style={
                    "fontSize": "12px", "color": _C["muted"],
                    "fontFamily": _C["font"], "marginTop": "1px",
                }),
            ], style={"flex": "1", "minWidth": "0", "overflow": "hidden"}),
            html.Div([
                html.Span(f"{sbs:.1f}", style={
                    "fontSize": "20px", "fontWeight": "800",
                    "color": color, "fontFamily": _C["font"], "lineHeight": "1",
                }),
                delta_el,
            ], style={"display": "flex", "flexDirection": "column",
                      "alignItems": "flex-end", "gap": "2px", "flexShrink": "0"}),
        ], style={"display": "flex", "alignItems": "center",
                  "gap": "10px", "marginBottom": "5px"}),
        html.Div(
            html.Div(style={
                "width": f"{min(sbs, 100):.0f}%", "height": "100%",
                "backgroundColor": color, "borderRadius": "2px",
                "transition": "width 0.4s ease",
            }),
            style={"height": "3px", "backgroundColor": "#1e2d3d",
                   "borderRadius": "2px", "marginLeft": "36px"},
        ),
    ], style={
        "padding": "10px 16px",
        "borderBottom": f"1px solid {_C['border2']}",
        "cursor": "pointer",
    },
        id={"type": "sector-rank-row", "index": sector},
        n_clicks=0,
    )


# ══════════════════════════════════════════════════════════════════════════════
# PHẦN 3: MODAL PHƯƠNG PHÁP LUẬN
# ══════════════════════════════════════════════════════════════════════════════

def _methodology_modal():
    """Modal popup giải thích phương pháp tính SBS."""
    import dash_bootstrap_components as dbc
    return dbc.Modal([
        dbc.ModalHeader(
            dbc.ModalTitle("Phương pháp luận — Sector Breadth Score (SBS)",
                           style={"fontSize": "15px", "fontWeight": "700",
                                  "color": _C["text"], "fontFamily": _C["font"]}),
            style={"backgroundColor": _C["card"],
                   "borderBottom": f"1px solid {_C['border']}"},
            close_button=True,
        ),
        dbc.ModalBody([
            # Công thức
            html.Div([
                _label("CÔNG THỨC TỔNG HỢP"),
                html.Div(
                    "SBS = 0.20·P_MA50 + 0.20·P_MA200 + 0.15·AD₂₀ + 0.15·HL + 0.10·RSI_D + 0.20·VB₂₀",
                    style={
                        "fontFamily": "JetBrains Mono, monospace",
                        "fontSize": "12px", "color": _C["accent"],
                        "backgroundColor": "#0d1117",
                        "padding": "12px 16px", "borderRadius": "6px",
                        "border": f"1px solid {_C['border']}",
                        "marginBottom": "20px", "overflowX": "auto",
                    }
                ),
            ]),
            # Giải thích 6 thành phần
            _label("6 THÀNH PHẦN & Ý NGHĨA"),
            *[html.Div([
                html.Div([
                    html.Span(name, style={
                        "fontSize": "12px", "fontWeight": "700",
                        "color": _C["accent"], "fontFamily": _C["font"],
                        "minWidth": "130px",
                    }),
                    html.Span(f"Tỷ trọng: {w}", style={
                        "fontSize": "10px", "color": _C["muted"],
                        "fontFamily": _C["font"], "marginLeft": "8px",
                    }),
                ], style={"display": "flex", "alignItems": "center",
                          "marginBottom": "4px"}),
                html.Div(desc, style={
                    "fontSize": "12px", "color": _C["text"],
                    "fontFamily": _C["font"], "lineHeight": "1.6",
                    "marginBottom": "4px",
                }),
                html.Div(formula, style={
                    "fontSize": "11px", "color": _C["muted"],
                    "fontFamily": "JetBrains Mono, monospace",
                    "backgroundColor": "#0d1117",
                    "padding": "4px 8px", "borderRadius": "4px",
                    "marginBottom": "12px",
                }),
            ]) for name, w, desc, formula in [
                ("P_MA50", "20%",
                 "Tỷ lệ % cổ phiếu trong ngành có giá đóng cửa nằm trên đường trung bình động 50 phiên (MA50). Đo lường xu hướng trung hạn của toàn ngành.",
                 "P_MA50 = (Số CP có Close > MA50) / Tổng số CP × 100"),
                ("P_MA200", "20%",
                 "Tỷ lệ % cổ phiếu có giá nằm trên MA200. Đo lường xu hướng dài hạn. Khi P_MA200 < 50%, đa số cổ phiếu trong ngành đang trong downtrend dài hạn — tín hiệu rủi ro hệ thống.",
                 "P_MA200 = (Số CP có Close > MA200) / Tổng số CP × 100"),
                ("AD₂₀", "15%",
                 "Advance/Decline Ratio tính trong 20 phiên giao dịch gần nhất. Đo lường xem dòng tiền đang chảy vào bao nhiêu mã (Advance) so với số mã đang bị bán ra (Decline). Giá trị > 50 nghĩa là nhiều mã tăng hơn giảm.",
                 "AD₂₀ = Advance / (Advance + Decline) × 100, rolling 20 phiên"),
                ("HL (High-Low Index)", "15%",
                 "Chỉ số Đỉnh-Đáy 52 tuần. Đo lường tỷ lệ cổ phiếu đang tiếp cận vùng đỉnh 52 tuần. Khi nhiều mã phá đỉnh, sức mạnh nội tại của ngành đang ở giai đoạn tích lũy/bứt phá.",
                 "HL = (Số CP gần đỉnh 52W ±1%) / Tổng số CP × 100"),
                ("RSI_D", "10%",
                 "Tỷ lệ % cổ phiếu có RSI(14) > 50. RSI > 50 cho thấy động lượng giá đang dương — cổ phiếu đang trong đà tăng. Chỉ số này phản ánh breadth của momentum trong ngành.",
                 "RSI_D = (Số CP có RSI₁₄ > 50) / Tổng số CP × 100"),
                ("VB₂₀ (Volume Breadth)", "20%",
                 "Độ rộng thanh khoản — dấu chân thực sự của dòng tiền. Tính tỷ lệ khối lượng giao dịch trong các phiên tăng điểm so với tổng khối lượng trong 20 phiên. VB > 60% cho thấy dòng tiền mua đang áp đảo.",
                 "VB₂₀ = Tổng volume phiên tăng / Tổng volume 20 phiên × 100"),
            ]],
            # Tier legend
            html.Div([
                _label("THANG ĐIỂM PHÂN LOẠI (TIER LEGEND)"),
                html.Div([
                    html.Div([
                        html.Div(style={"width": "12px", "height": "12px", "borderRadius": "3px",
                                        "backgroundColor": clr, "marginRight": "8px", "flexShrink": "0"}),
                        html.Div([
                            html.Span(f"{rng}: ", style={"fontWeight": "700", "color": clr,
                                                          "fontSize": "12px", "fontFamily": _C["font"]}),
                            html.Span(desc, style={"fontSize": "11px", "color": _C["muted"],
                                                    "fontFamily": _C["font"]}),
                        ]),
                    ], style={"display": "flex", "alignItems": "center", "marginBottom": "8px"})
                    for clr, rng, desc in [
                        ("#10b981", "80–100", "Rủi ro thấp — Ưu tiên tăng tỷ trọng, dòng tiền đồng thuận"),
                        ("#34d399", "65–79",  "Mạnh — Duy trì tỷ trọng, xu hướng tích cực"),
                        ("#f59e0b", "50–64",  "Trung tính — Chọn lọc kỹ, không mở rộng position"),
                        ("#f97316", "35–49",  "Yếu — Giảm tỷ trọng, ưu tiên phòng thủ"),
                        ("#ef4444", "0–34",   "Broad Bear — Ngừng mua mới, siết margin, cảnh báo hệ thống"),
                    ]
                ]),
            ], style={"marginTop": "16px",
                      "paddingTop": "16px",
                      "borderTop": f"1px solid {_C['border']}"}),
            # Lưu ý
            html.Div([
                html.Div("⚠️  Lưu ý sử dụng", style={
                    "fontSize": "11px", "fontWeight": "700",
                    "color": _C["yellow"], "fontFamily": _C["font"],
                    "marginBottom": "6px",
                }),
                html.Div(
                    "SBS là công cụ đo lường sức khỏe nội tại của thị trường dựa trên dữ liệu giá và khối lượng lịch sử. "
                    "Chỉ số này phản ánh trạng thái hiện tại của dòng tiền, không phải dự báo tương lai. "
                    "Bộ lọc Avg_Vol_20D > 100,000 và Giá > 5,000 VND được áp dụng trước khi tính SBS để loại bỏ "
                    "các mã penny và thanh khoản thấp có thể gây nhiễu tín hiệu. "
                    "Nội dung mang tính tham khảo, không phải khuyến nghị đầu tư.",
                    style={"fontSize": "11px", "color": _C["muted"],
                           "fontFamily": _C["font"], "lineHeight": "1.7"},
                ),
            ], style={
                "marginTop": "16px", "padding": "12px 14px",
                "backgroundColor": "#0d1117", "borderRadius": "6px",
                "border": f"1px solid {_C['border']}",
            }),
        ], style={"backgroundColor": _C["card"], "padding": "20px 24px",
                  "maxHeight": "70vh", "overflowY": "auto"}),
    ],
        id="sbs-methodology-modal",
        is_open=False,
        size="lg",
        backdrop=True,
        scrollable=True,
        style={"fontFamily": _C["font"]},
    )


@app.callback(
    Output("sbs-methodology-modal", "is_open"),
    Input("btn-sbs-info",            "n_clicks"),
    Input("sbs-methodology-modal",   "is_open"),
    prevent_initial_call=True,
)
def toggle_methodology_modal(n, is_open):
    ctx = callback_context
    if not ctx.triggered:
        return no_update
    if ctx.triggered[0]["prop_id"].startswith("btn-sbs-info"):
        return not is_open
    return is_open


# ══════════════════════════════════════════════════════════════════════════════
# PHẦN 4: RENDER X-RAY DÒNG TIỀN
# ══════════════════════════════════════════════════════════════════════════════

@app.callback(
    Output("breadth-xray-container", "children"),
    Input("btn-heatmap",             "n_clicks"),
    Input("heatmap-exchange-filter", "value"),
    State("heatmap-collapse",        "is_open"),
    prevent_initial_call=False,
)
def render_breadth_xray(_, exchange, is_open):
    try:
        from src.backend.data_loader import (
            get_market_internals,
            get_market_internals_history,
        )
        from src.backend.quant_engine import _sbs_tier
        import dash_bootstrap_components as dbc

        exchange = exchange or "HOSE"
        result   = get_market_internals(exchange_filter=exchange)

        if not result:
            return html.P("Đang tính toán dữ liệu độ rộng thị trường...",
                          style={"color": _C["muted"], "fontSize": "12px",
                                 "padding": "20px 0"})

        sdf     = result["sector_sbs"]
        mkt_sbs = result["market_sbs"]
        regime  = result["regime"]
        r_clr   = result["regime_color"]
        top3    = result["top_sectors"]
        weak3   = result["weak_sectors"]

        # ── Rank rows ─────────────────────────────────────────────────────────
        rank_rows = []
        for i, row in sdf.iterrows():
            _, clr = _sbs_tier(row["SBS"])
            rank_rows.append(_sbs_bar_row(
                i + 1, row["Sector"], row["SBS"],
                delta=None, color=clr, n_stocks=int(row.get("N", 0)),
            ))

        # ── Panel bảng xếp hạng (cột trái) ───────────────────────────────────
        panel_ranking = _card([
            html.Div([
                _label("XẾP HẠNG SỨC MẠNH NGÀNH", {"marginBottom": "0"}),
                html.Span("GICS · NHẤP ĐỂ XEM CHI TIẾT", style={
                    "fontSize": "9px", "color": _C["muted"],
                    "fontFamily": _C["font"], "letterSpacing": "1px",
                }),
            ], style={"display": "flex", "justifyContent": "space-between",
                      "alignItems": "center", "marginBottom": "12px",
                      "paddingBottom": "10px",
                      "borderBottom": f"1px solid {_C['border']}"}),
            *rank_rows,
        ], style_extra={"padding": "16px 0", "height": "100%",
                        "boxSizing": "border-box"})

        # ── Panel Regime (cột phải — trên) ───────────────────────────────────
        regime_desc = (
            "Suy yếu diện rộng — Rủi ro hệ thống, ngừng mua mới"
            if "Bear" in regime else
            "Xác nhận Uptrend — Duy trì và mở rộng tỷ trọng"
            if mkt_sbs >= 65 else
            "Trung tính — Chọn lọc kỹ, không mở rộng position"
        )

        panel_regime = _card([
            html.Div([
                # SBS score
                html.Div([
                    html.Div("ĐIỂM ĐỘ RỘNG (SBS)", style={
                        "fontSize": "9px", "letterSpacing": "1.5px",
                        "color": _C["muted"], "fontFamily": _C["font"],
                        "marginBottom": "6px",
                    }),
                    html.Div([
                        html.Span(f"{mkt_sbs}", style={
                            "fontSize": "44px", "fontWeight": "800",
                            "color": r_clr, "lineHeight": "1",
                            "fontFamily": _C["font"],
                        }),
                        html.Span(" /100", style={
                            "fontSize": "14px", "color": _C["muted"],
                            "fontFamily": _C["font"], "marginLeft": "4px",
                        }),
                    ]),
                ], style={"flex": "1"}),
                # Regime
                html.Div([
                    html.Div("TRẠNG THÁI", style={
                        "fontSize": "9px", "letterSpacing": "1.5px",
                        "color": _C["muted"], "fontFamily": _C["font"],
                        "marginBottom": "6px",
                    }),
                    html.Div(regime, style={
                        "fontSize": "16px", "fontWeight": "800",
                        "color": r_clr, "fontFamily": _C["font"],
                        "lineHeight": "1.2",
                    }),
                    html.Div(regime_desc, style={
                        "fontSize": "10px", "color": _C["muted"],
                        "fontFamily": _C["font"], "marginTop": "5px",
                        "lineHeight": "1.5",
                    }),
                ], style={"flex": "1.4", "paddingLeft": "16px",
                          "borderLeft": f"1px solid {_C['border']}"}),
            ], style={"display": "flex", "alignItems": "flex-start",
                      "marginBottom": "16px", "paddingBottom": "16px",
                      "borderBottom": f"1px solid {_C['border']}"}),

            # Top + Weak
            html.Div([
                html.Div([
                    _label("DẪN DẮT"),
                    *[html.Div([
                        html.Span(r["Sector"], style={
                            "fontSize": "11px", "color": _C["green"],
                            "fontFamily": _C["font"], "flex": "1",
                            "overflow": "hidden", "textOverflow": "ellipsis",
                            "whiteSpace": "nowrap",
                        }),
                        html.Span(f"{r['SBS']:.1f}", style={
                            "fontSize": "12px", "fontWeight": "700",
                            "color": _C["green"], "fontFamily": _C["font"],
                            "marginLeft": "8px", "flexShrink": "0",
                        }),
                    ], style={"display": "flex", "alignItems": "center",
                              "marginBottom": "6px"}) for r in top3],
                ], style={"flex": "1", "minWidth": "0"}),
                html.Div(style={"width": "1px", "backgroundColor": _C["border"],
                                "margin": "0 12px"}),
                html.Div([
                    _label("SUY YẾU"),
                    *[html.Div([
                        html.Span(r["Sector"], style={
                            "fontSize": "11px", "color": _C["red"],
                            "fontFamily": _C["font"], "flex": "1",
                            "overflow": "hidden", "textOverflow": "ellipsis",
                            "whiteSpace": "nowrap",
                        }),
                        html.Span(f"{r['SBS']:.1f}", style={
                            "fontSize": "12px", "fontWeight": "700",
                            "color": _C["red"], "fontFamily": _C["font"],
                            "marginLeft": "8px", "flexShrink": "0",
                        }),
                    ], style={"display": "flex", "alignItems": "center",
                              "marginBottom": "6px"}) for r in weak3],
                ], style={"flex": "1", "minWidth": "0"}),
            ], style={"display": "flex"}),
        ])

        # ── Charts cột phải (Divergence + Heatmap nhỏ) ───────────────────────
        chart_right_1 = html.Div()   # line chart VNIndex vs SBS
        chart_right_2 = html.Div()   # thêm chart SBS ngành top/bottom

        try:
            df_hist = get_market_internals_history(exchange_filter=exchange)
            if df_hist is not None and not df_hist.empty:
                mkt_daily = (
                    df_hist.groupby("Date")
                    .apply(lambda g: (g["SBS"] * g["N"]).sum() / g["N"].sum()
                           if g["N"].sum() > 0 else None,
                           include_groups=False)
                    .dropna()
                    .reset_index()
                )
                mkt_daily.columns = ["Date", "Market_SBS"]

                from src.backend.data_loader import load_index_data
                df_idx = load_index_data()

                if df_idx is not None and not df_idx.empty:
                    df_idx["Date"] = pd.to_datetime(df_idx["Date"])
                    merged = mkt_daily.merge(
                        df_idx[["Date", "VNINDEX_Close"]], on="Date", how="left"
                    ).dropna()

                    if len(merged) >= 5:
                        sbs_slope5 = float(np.polyfit(
                            range(min(5, len(merged))),
                            merged["Market_SBS"].tail(5).values, 1)[0])
                        vnx_slope5 = float(np.polyfit(
                            range(min(5, len(merged))),
                            merged["VNINDEX_Close"].tail(5).values, 1)[0])

                        if sbs_slope5 < -0.1 and vnx_slope5 >= 0:
                            div_label = "⚠️ PHÂN KỲ ÂM — Kéo trụ xả hàng"
                            div_color = _C["red"]
                        elif sbs_slope5 > 0.1 and vnx_slope5 <= 0:
                            div_label = "🌟 PHÂN KỲ DƯƠNG — Dòng tiền gom đáy"
                            div_color = _C["green"]
                        elif sbs_slope5 < 0 and vnx_slope5 < 0:
                            div_label = "📉 ĐỒNG THUẬN GIẢM — Xác nhận Downtrend"
                            div_color = _C["yellow"]
                        else:
                            div_label = "📈 ĐỒNG THUẬN TĂNG — Xác nhận Uptrend"
                            div_color = _C["green"]

                        fig_div = go.Figure()
                        fig_div.add_trace(go.Scatter(
                            x=merged["Date"], y=merged["VNINDEX_Close"],
                            name="VN-Index", yaxis="y1",
                            line=dict(color="#f59e0b", width=1.5),
                            hovertemplate="VN-Index: %{y:.0f}<extra></extra>",
                        ))
                        fig_div.add_trace(go.Scatter(
                            x=merged["Date"], y=merged["Market_SBS"],
                            name="Market SBS", yaxis="y2",
                            line=dict(color=_C["accent"], width=1.5, dash="dot"),
                            hovertemplate="SBS: %{y:.1f}<extra></extra>",
                        ))
                        fig_div.update_layout(
                            paper_bgcolor=_C["bg"],
                            plot_bgcolor=_C["card"],
                            margin=dict(l=50, r=55, t=10, b=30),
                            height=200,
                            legend=dict(
                                orientation="h", x=0, y=1.12,
                                font=dict(color=_C["muted"], size=9),
                                bgcolor="rgba(0,0,0,0)",
                            ),
                            hovermode="x unified",
                            xaxis=dict(showgrid=False,
                                       tickfont=dict(color=_C["muted"], size=8)),
                            yaxis=dict(showgrid=True, gridcolor="#1e2d3d",
                                       tickfont=dict(color="#f59e0b", size=8),
                                       side="left"),
                            yaxis2=dict(overlaying="y", side="right",
                                        range=[0, 100], showgrid=False,
                                        tickfont=dict(color=_C["accent"], size=8)),
                            font=dict(family=_C["font"]),
                        )

                        chart_right_1 = html.Div([
                            html.Div([
                                _label("PHÂN KỲ: VN-INDEX VS DÒNG TIỀN",
                                       {"marginBottom": "0"}),
                                html.Span(div_label, style={
                                    "fontSize": "10px", "fontWeight": "700",
                                    "color": div_color, "fontFamily": _C["font"],
                                }),
                            ], style={"display": "flex", "justifyContent": "space-between",
                                      "alignItems": "center", "marginBottom": "8px"}),
                            dcc.Graph(figure=fig_div,
                                        config={"displayModeBar": False},
                                        style={"width": "100%", "height": "200px"},
                                        ),
                        ])

                        # Chart 2: SBS top 3 mạnh vs yếu nhất
                        top_sectors   = [r["Sector"] for r in top3]
                        weak_sectors  = [r["Sector"] for r in weak3]
                        watch_sectors = top_sectors + weak_sectors

                        fig_lines = go.Figure()
                        _colors_top  = ["#10b981", "#3b82f6", "#06b6d4"]
                        _colors_weak = ["#ef4444", "#f97316", "#f43f5e"]
                        _top_i = _weak_i = 0
                        for sector in watch_sectors:
                            sh = df_hist[df_hist["Sector"] == sector].sort_values("Date")
                            if sh.empty:
                                continue
                            is_top = sector in top_sectors
                            if is_top:
                                s_color = _colors_top[_top_i % len(_colors_top)]
                                _top_i += 1
                                line_cfg = dict(color=s_color, width=2.2)
                            else:
                                s_color = _colors_weak[_weak_i % len(_colors_weak)]
                                _weak_i += 1
                                line_cfg = dict(color=s_color, width=1.8, dash="dot")
                            fig_lines.add_trace(go.Scatter(
                                x=sh["Date"], y=sh["SBS"],
                                name=sector[:18],
                                line=line_cfg,
                                opacity=0.9,
                                hovertemplate=f"{sector}<br>SBS: %{{y:.1f}}<extra></extra>",
                            ))
                            
                        # Vẽ đường ngưỡng
                        for thr, lbl, tclr in [(65, "Mạnh", "#34d399"),
                                                (50, "T.Bình", "#f59e0b"),
                                                (35, "Yếu", "#f97316")]:
                            fig_lines.add_hline(
                                y=thr, line_dash="dot",
                                line_color=tclr, opacity=0.4,
                                annotation_text=lbl,
                                annotation_font=dict(color=tclr, size=8),
                            )
                        fig_lines.update_layout(
                            paper_bgcolor=_C["bg"],
                            plot_bgcolor=_C["card"],
                            margin=dict(l=40, r=20, t=10, b=30),
                            height=200,
                            legend=dict(
                                orientation="v", x=1.01, y=1,
                                font=dict(color=_C["muted"], size=8),
                                bgcolor="rgba(0,0,0,0)",
                            ),
                            hovermode="x unified",
                            yaxis=dict(range=[0, 100], showgrid=True,
                                       gridcolor="#1e2d3d",
                                       tickfont=dict(color=_C["muted"], size=8)),
                            xaxis=dict(showgrid=False,
                                       tickfont=dict(color=_C["muted"], size=8)),
                            font=dict(family=_C["font"]),
                        )
                        chart_right_2 = html.Div([
                            _label("DÒNG TIỀN: NHÓM DẪN DẮT vs SUY YẾU",
                                   {"marginBottom": "8px"}),
                            dcc.Graph(figure=fig_lines,
                                    config={"displayModeBar": False},
                                    style={"width": "100%", "height": "200px"},
                                    ),
                        ], style={"marginTop": "12px"})

        except Exception as e:
            logger.warning(f"Charts error: {e}")

        panel_charts = _card([
            panel_regime,
            html.Div(style={"height": "12px"}),
            chart_right_1,
            chart_right_2,
        ], style_extra={
            "height": "100%", "boxSizing": "border-box",
            "display": "flex", "flexDirection": "column",
        })

        # ── Heatmap 60 phiên ──────────────────────────────────────────────────
        panel_heatmap60 = html.Div()
        try:
            df_hist2 = get_market_internals_history(exchange_filter=exchange)
            if df_hist2 is not None and not df_hist2.empty:
                pivot_hm = df_hist2.pivot_table(
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
                        [0.00, "#7f1d1d"], [0.34, "#dc2626"],
                        [0.50, "#f59e0b"], [0.65, "#34d399"],
                        [1.00, "#065f46"],
                    ],
                    showscale=True,
                    colorbar=dict(
                        title=dict(text="SBS",
                                   font=dict(color=_C["muted"], size=10)),
                        tickfont=dict(color=_C["muted"], size=9),
                        thickness=12, len=0.8,
                    ),
                    hovertemplate=(
                        "<b>%{y}</b><br>Ngày: %{x}<br>SBS: %{z:.1f}"
                        "<extra></extra>"
                    ),
                ))
                fig_hm.update_layout(
                    paper_bgcolor=_C["bg"], plot_bgcolor=_C["card"],
                    margin=dict(l=190, r=60, t=20, b=40),
                    height=300,
                    xaxis=dict(tickfont=dict(color=_C["muted"], size=8),
                               showgrid=False, tickangle=-45, nticks=20),
                    yaxis=dict(tickfont=dict(color=_C["text"], size=10),
                               showgrid=False),
                    font=dict(family=_C["font"]),
                )
                panel_heatmap60 = _card([
                    _label("BẢN ĐỒ NHIỆT 60 PHIÊN — Luân chuyển dòng tiền"),
                    dcc.Graph(figure=fig_hm,
                              config={"displayModeBar": False},
                              style={"marginTop": "6px"}),
                ], style_extra={"marginTop": "12px"})

        except Exception as e:
            logger.warning(f"Heatmap 60 phiên error: {e}")

        # ── Panel chi tiết ngành (khi click) ─────────────────────────────────
        panel_detail = _card([
            _label("PHÂN TÍCH CHI TIẾT NGÀNH — Nhấp vào một ngành trên bảng xếp hạng để xem"),
            dcc.Store(id="selected-sector-store", data=None),
            html.Div(id="sector-detail-container",
                     style={"color": _C["muted"], "fontSize": "12px",
                            "textAlign": "center", "padding": "30px 0"}),
        ], style_extra={"marginTop": "12px"})

        # ── Divider ───────────────────────────────────────────────────────────
        xray_header = html.Div([
            html.Div(style={"flex": "1", "height": "1px",
                            "backgroundColor": _C["border"]}),
            # Nút info
            html.Div([
                html.Span("DÒNG TIỀN ĐỊNH LƯỢNG", style={
                    "fontSize": "10px", "fontWeight": "700",
                    "letterSpacing": "2px", "color": _C["muted"],
                    "padding": "0 14px", "fontFamily": _C["font"],
                }),
                html.Button([
                    "ⓘ Đọc Hiểu Dòng Tiền"
                ], id="btn-sbs-info", n_clicks=0, style={
                    "background": "rgba(59,130,246,0.10)",
                    "border": "1px solid rgba(59,130,246,0.35)",
                    "borderRadius": "12px",
                    "color": "#3b82f6",
                    "fontSize": "11px", "fontWeight": "700",
                    "cursor": "pointer",
                    "padding": "4px 12px",
                    "fontFamily": _C["font"],
                    "marginLeft": "8px",
                    "letterSpacing": "0.3px",
                }),
            ], style={"display": "flex", "alignItems": "center"}),
            html.Div(style={"flex": "1", "height": "1px",
                            "backgroundColor": _C["border"]}),
        ], style={"display": "flex", "alignItems": "center",
                  "margin": "20px 0 14px 0"})

        return html.Div([
            xray_header,
            _methodology_modal(),

            # Row 1: Bảng xếp hạng (trái) + Charts (phải) — chiều cao đồng đều
            html.Div([
                html.Div(
                    panel_ranking,
                    style={"flex": "1.15", "minWidth": "0",
                           "display": "flex", "flexDirection": "column"}
                ),
                html.Div(
                    panel_charts,
                    style={"flex": "1", "minWidth": "0",
                           "display": "flex", "flexDirection": "column"}
                ),
            ], style={
                "display": "flex", "gap": "12px",
                "marginTop": "0", "alignItems": "stretch",
            }),

            # Row 2: Heatmap 60 phiên
            panel_heatmap60,

            # Row 3: Chi tiết ngành
            panel_detail,
        ])

    except Exception as e:
        logger.error(f"render_breadth_xray error: {e}")
        import traceback; traceback.print_exc()
        return html.P(f"Lỗi X-Ray: {str(e)[:120]}",
                      style={"color": _C["red"], "fontSize": "12px"})


# ══════════════════════════════════════════════════════════════════════════════
# PHẦN 5: CHI TIẾT NGÀNH KHI CLICK
# ══════════════════════════════════════════════════════════════════════════════

@app.callback(
    Output("sector-detail-container", "children"),
    Input("selected-sector-store",    "data"),
    State("heatmap-exchange-filter",  "value"),
    prevent_initial_call=True,
)
def render_sector_detail(selected_sector, exchange):
    """Radar 6 cánh (fixed size) + trajectory + factor bars + constituents."""
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

        # ── Radar 6 cánh — FIXED SIZE để tránh grow loop ─────────────────────
        categories = [
            "% CP > MA50",
            "% CP > MA200",
            "Lan tỏa đà tăng (A/D)",
            "Vượt Đỉnh 52 Tuần",
            "RSI(14) > 50",
            "Độ rộng Thanh khoản",
        ]
        values        = [row["P_MA50"], row["P_MA200"], row["AD_20"],
                         row["HL"],     row["RSI_D"],   row["VB_20"]]
        values_closed = values + [values[0]]
        cats_closed   = categories + [categories[0]]

        fig_radar = go.Figure(go.Scatterpolar(
            r=values_closed, theta=cats_closed,
            fill="toself", fillcolor="rgba(59,130,246,0.12)",
            line=dict(color=_C["accent"], width=1.8),
            hovertemplate="%{theta}: %{r:.1f}<extra></extra>",
        ))
        fig_radar.update_layout(
            polar=dict(
                bgcolor=_C["card"],
                radialaxis=dict(
                    visible=True, range=[0, 100],
                    tickfont=dict(color=_C["muted"], size=7),
                    gridcolor="#1e2d3d", linecolor="#1e2d3d",
                    tickvals=[25, 50, 75, 100],
                ),
                angularaxis=dict(
                    tickfont=dict(color=_C["text"], size=9),
                    linecolor="#1e2d3d", gridcolor="#1e2d3d",
                ),
            ),
            paper_bgcolor=_C["bg"],
            # QUAN TRỌNG: width + height cố định, autosize=False → tránh grow loop
            autosize=False,
            width=360,
            height=340,
            margin=dict(l=30, r=30, t=20, b=20),
            showlegend=False,
            font=dict(family=_C["font"]),
        )

        # ── 60-session trajectory ─────────────────────────────────────────────
        trajectory_el = html.Div()
        try:
            df_hist = get_market_internals_history(exchange_filter=exchange or "HOSE")
            if df_hist is not None and not df_hist.empty:
                sector_hist = (df_hist[df_hist["Sector"] == selected_sector]
                               .sort_values("Date"))
                if not sector_hist.empty:
                    sector_hist = sector_hist.copy()
                    sector_hist["SBS_MA10"] = sector_hist["SBS"].rolling(10, min_periods=3).mean()

                    fig_traj = go.Figure()
                    fig_traj.add_trace(go.Scatter(
                        x=sector_hist["Date"], y=sector_hist["SBS"],
                        fill="tozeroy", fillcolor="rgba(59,130,246,0.06)",
                        line=dict(color=_C["accent"], width=1.5),
                        name="SBS",
                        hovertemplate="SBS: %{y:.1f}<extra></extra>",
                    ))
                    fig_traj.add_trace(go.Scatter(
                        x=sector_hist["Date"], y=sector_hist["SBS_MA10"],
                        line=dict(color="#f59e0b", width=1.5, dash="dash"),
                        name="MA10",
                        hovertemplate="MA10: %{y:.1f}<extra></extra>",
                    ))
                    for thr, lbl, tclr in [(65, "Mạnh", "#34d399"),
                                            (50, "T.Bình", "#f59e0b"),
                                            (35, "Yếu", "#f97316")]:
                        fig_traj.add_hline(
                            y=thr, line_dash="dot",
                            line_color=tclr, opacity=0.45,
                            annotation_text=lbl,
                            annotation_font=dict(color=tclr, size=7),
                        )
                    fig_traj.update_layout(
                        paper_bgcolor=_C["bg"], plot_bgcolor=_C["card"],
                        margin=dict(l=40, r=20, t=36, b=40),
                        height=240,
                        showlegend=True,
                        legend=dict(
                            orientation="h", x=0, y=1.12,
                            font=dict(color=_C["muted"], size=9),
                            bgcolor="rgba(0,0,0,0)",
                        ),
                        title=dict(
                            text=f"SBS Score — {selected_sector}",
                            font=dict(color=_C["muted"], size=10, family=_C["font"]),
                            x=0.01, xanchor="left", y=0.97,
                        ),
                        yaxis=dict(range=[0, 100], showgrid=True,
                                gridcolor="#1e2d3d",
                                tickfont=dict(color=_C["muted"], size=9),
                                title=dict(text="SBS", font=dict(color=_C["muted"], size=9))),
                        xaxis=dict(showgrid=True, gridcolor="#1e2d3d",
                                tickfont=dict(color=_C["muted"], size=9),
                                nticks=15, tickangle=-30),
                        font=dict(family=_C["font"]),
                    )
                    trajectory_el = html.Div([
                        _label("XU HƯỚNG SBS 60 PHIÊN"),
                        dcc.Graph(figure=fig_traj,
                                config={"displayModeBar": False},
                                style={"width": "100%", "height": "240px"},
                                ),
                    ], style={"marginTop": "14px"})
        except Exception:
            pass

        # ── Factor breakdown bars ─────────────────────────────────────────────
        factor_rows = []
        for fname, val, weight in [
            ("% CP > MA50",              row["P_MA50"],  "20%"),
            ("% CP > MA200",             row["P_MA200"], "20%"),
            ("Lan tỏa đà tăng (A/D)",   row["AD_20"],   "15%"),
            ("Vượt Đỉnh 52 Tuần",       row["HL"],       "15%"),
            ("RSI(14) > 50",             row["RSI_D"],   "10%"),
            ("Độ rộng Thanh khoản",     row["VB_20"],   "20%"),
        ]:
            _, fcol = _sbs_tier(val)
            factor_rows.append(html.Div([
                html.Div([
                    html.Span(fname, style={
                        "fontSize": "12px", "color": _C["text"],
                        "fontFamily": _C["font"], "flex": "1",
                    }),
                    html.Span(f"w={weight}", style={
                        "fontSize": "10px", "color": _C["muted"],
                        "fontFamily": _C["font"],
                    }),
                ], style={"display": "flex", "justifyContent": "space-between",
                          "marginBottom": "4px"}),
                html.Div([
                    html.Div(
                        html.Div(style={
                            "width": f"{min(val, 100):.0f}%", "height": "100%",
                            "backgroundColor": fcol, "borderRadius": "2px",
                            "opacity": "0.85",
                        }),
                        style={"flex": "1", "height": "6px",
                               "backgroundColor": "#1e2d3d",
                               "borderRadius": "2px"},
                    ),
                    html.Span(f"{val:.1f}", style={
                        "fontSize": "12px", "fontWeight": "700",
                        "color": fcol, "fontFamily": _C["font"],
                        "minWidth": "36px", "textAlign": "right",
                        "marginLeft": "10px",
                    }),
                ], style={"display": "flex", "alignItems": "center"}),
            ], style={"marginBottom": "10px", "paddingBottom": "10px",
                      "borderBottom": f"1px solid {_C['border2']}"}))

        # ── Constituents ──────────────────────────────────────────────────────
        consti_el = html.Div()
        if df_snap is not None and "Sector" in df_snap.columns:
            consti = (df_snap[df_snap["Sector"] == selected_sector]
                      [["Ticker", "Perf_1W"]].copy())
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
                    "backgroundColor": bg,
                    "border": f"1px solid {fg}33",
                    "borderRadius": "4px", "padding": "4px 7px",
                    "cursor": "pointer",
                }))

            consti_el = html.Div([
                _label(f"DANH SÁCH MÃ TRONG NGÀNH — {len(consti)} mã",
                       {"marginTop": "16px"}),
                html.Div(badges, style={
                    "display": "flex", "flexWrap": "wrap", "gap": "6px",
                    "maxHeight": "200px",
                    "overflowY": "auto",
                    "padding": "4px",
                    "borderRadius": "6px",
                    "border": f"1px solid {_C['border2']}",
                }),
            ])

        # ── Layout chi tiết ───────────────────────────────────────────────────
        return html.Div([
            # Header
            html.Div([
                html.Div([
                    html.Div(selected_sector, style={
                        "fontSize": "18px", "fontWeight": "800",
                        "color": _C["text"], "fontFamily": _C["font"],
                    }),
                    html.Div(
                        _SECTOR_SUB.get(selected_sector, ""),
                        style={"fontSize": "11px", "color": _C["muted"],
                               "fontFamily": _C["font"], "marginTop": "2px"},
                    ),
                ], style={"flex": "1"}),
                html.Div([
                    html.Span(f"{sbs:.1f}", style={
                        "fontSize": "28px", "fontWeight": "800",
                        "color": clr, "fontFamily": _C["font"],
                    }),
                    html.Span("/100", style={
                        "fontSize": "12px", "color": _C["muted"],
                        "fontFamily": _C["font"], "marginLeft": "2px",
                    }),
                    html.Div(row["SBS_Label"], style={
                        "fontSize": "10px", "fontWeight": "700",
                        "color": clr, "fontFamily": _C["font"],
                        "backgroundColor": f"{clr}20",
                        "padding": "3px 8px", "borderRadius": "10px",
                        "border": f"1px solid {clr}40",
                        "marginTop": "4px", "textAlign": "center",
                    }),
                ], style={"display": "flex", "flexDirection": "column",
                          "alignItems": "flex-end"}),
            ], style={"display": "flex", "alignItems": "flex-start",
                      "marginBottom": "16px", "paddingBottom": "16px",
                      "borderBottom": f"1px solid {_C['border']}"}),

            # Radar + Factor bars — 2 cột
            # Radar dùng width/height cố định → bọc trong div overflow:hidden
            html.Div([
                html.Div([
                    _label("RADAR 6 YẾU TỐ"),
                    # overflow:hidden + width cố định để tránh grow loop
                    html.Div(
                        dcc.Graph(
                            figure=fig_radar,
                            config={"displayModeBar": False,
                                    "responsive": False},  # QUAN TRỌNG
                        ),
                        style={"overflow": "hidden", "width": "360px",
                               "flexShrink": "0"},
                    ),
                ], style={"flexShrink": "0"}),

                html.Div([
                    _label("BÓC TÁCH THÀNH PHẦN"),
                    *factor_rows,
                ], style={"flex": "1", "minWidth": "0",
                          "paddingLeft": "20px"}),
            ], style={"display": "flex", "gap": "0",
                      "alignItems": "flex-start"}),

            trajectory_el,
            consti_el,
        ])

    except Exception as e:
        logger.error(f"render_sector_detail error: {e}")
        import traceback; traceback.print_exc()
        return html.P(f"Lỗi: {e}", style={"color": _C["red"]})


# ══════════════════════════════════════════════════════════════════════════════
# PHẦN 6: CLICK CHỌN NGÀNH
# ══════════════════════════════════════════════════════════════════════════════

@app.callback(
    Output("selected-sector-store", "data"),
    Input({"type": "sector-rank-row", "index": ALL}, "n_clicks"),
    State({"type": "sector-rank-row", "index": ALL}, "id"),
    prevent_initial_call=True,
)
def select_sector(n_clicks_list, id_list):
    ctx = callback_context
    if not ctx.triggered or not any(n_clicks_list):
        return no_update
    try:
        triggered = json.loads(ctx.triggered[0]["prop_id"].split(".")[0])
        return triggered["index"]
    except Exception:
        return no_update