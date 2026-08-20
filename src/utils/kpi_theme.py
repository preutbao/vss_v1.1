# src/utils/kpi_theme.py
"""
Bộ màu & helper dùng chung cho 6 tab chi tiết cổ phiếu (Tổng quan, Biến động
giá, Biểu đồ, Tài chính, Chỉ số, Kỹ thuật).

Mục tiêu:
  1. Tránh hard-code màu dark tuyệt đối trong callback Python (server-side
     không tự đọc được data-theme của browser) — mọi callback đọc
     State("theme-store", "data") rồi gọi get_kpi_theme(theme) ở đây.
  2. Đồng bộ phong cách "KPI pastel card" kiểu Global Data 365: nền pastel
     dịu, icon tròn, badge LY/YTD, số liệu to — áp dụng nhất quán cho cả
     6 tab, tự đổi đậm/nhạt theo theme sáng/tối mà chữ luôn đủ tương phản.
"""

from dash import html

# ============================================================================
# 1) BỘ MÀU PASTEL THEO THEME — 5 tông giống ảnh tham khảo Global Data 365
#    (rose/hồng, green/lá, purple/tím, amber/cam vàng, sky/xanh dương)
# ============================================================================
def get_kpi_theme(theme: str = "dark") -> dict:
    """Trả về dict màu pastel theme-aware dùng cho KPI card / badge / chart.
    theme: 'light' hoặc 'dark'."""
    if theme == "light":
        return {
            "page_text":      "#1e293b",
            "page_text_dim":  "#64748b",
            "card_border":    "#e2e8f0",
            "card_shadow":    "0 2px 10px rgba(15,23,42,0.06)",
            "positive":       "#10b981",
            "negative":       "#ef4444",
            "pastel": {
                "rose":   {"bg": "#fde8ec", "fg": "#be185d", "icon_bg": "#f9c8d4"},
                "green":  {"bg": "#e3f6ed", "fg": "#0f766e", "icon_bg": "#bbeed4"},
                "purple": {"bg": "#f1ecfb", "fg": "#6d28d9", "icon_bg": "#dcd0f7"},
                "amber":  {"bg": "#fdf1de", "fg": "#b45309", "icon_bg": "#fbdfac"},
                "sky":    {"bg": "#e3f1fc", "fg": "#0057D9", "icon_bg": "#CFE8FF"},
            },
            "chart_grid":     "rgba(15,23,42,0.08)",
            "chart_text":     "#475569",
            "chart_paper":    "rgba(0,0,0,0)",
            "bar_main":       "#16a34a",
            "bar_compare":    "#cbd5e1",
            "line_accent":    "#0057D9",
            "donut_colors":   ["#1d4ed8", "#16a34a", "#f59e0b", "#dc2626", "#7c3aed", "#0891b2"],
        }
    # dark (mặc định) — vẫn dùng pastel nhưng đậm/no hơn để nổi trên nền navy
    return {
        "page_text":      "#e6edf3",
        "page_text_dim":  "#94a3b8",
        "card_border":    "rgba(255,255,255,0.08)",
        "card_shadow":    "0 4px 16px rgba(0,0,0,0.35)",
        "positive":       "#10b981",
        "negative":       "#ef4444",
        "pastel": {
            "rose":   {"bg": "rgba(244,63,94,0.14)",  "fg": "#fb7185", "icon_bg": "rgba(244,63,94,0.22)"},
            "green":  {"bg": "rgba(16,185,129,0.14)", "fg": "#34d399", "icon_bg": "rgba(16,185,129,0.22)"},
            "purple": {"bg": "rgba(167,139,250,0.14)","fg": "#c4b5fd", "icon_bg": "rgba(167,139,250,0.22)"},
            "amber":  {"bg": "rgba(245,158,11,0.14)", "fg": "#fbbf24", "icon_bg": "rgba(245,158,11,0.22)"},
            "sky":    {"bg": "rgba(30,136,229,0.14)", "fg": "#64B5F6", "icon_bg": "rgba(30,136,229,0.22)"},
        },
        "chart_grid":     "rgba(255,255,255,0.07)",
        "chart_text":     "#94a3b8",
        "chart_paper":    "rgba(0,0,0,0)",
        "bar_main":       "#34d399",
        "bar_compare":    "#475569",
        "line_accent":    "#1E88E5",
        "donut_colors":   ["#60a5fa", "#34d399", "#fbbf24", "#fb7185", "#c4b5fd", "#22d3ee"],
    }


# ============================================================================
# 2) KPI CARD — pastel, icon tròn, badge LY/YTD (phong cách Global Data 365)
# ============================================================================
def kpi_card(theme, label, value, *, tone="sky", icon_class="fas fa-chart-line",
             sub_left=None, sub_right=None, delta=None, delta_is_good=None):
    """
    label:  tiêu đề nhỏ phía trên (VD: "VỐN HÓA TT")
    value:  số liệu chính, to (VD: "12,450,000")
    tone:   'rose' | 'green' | 'purple' | 'amber' | 'sky'
    sub_left / sub_right: tuple (label, value) hiển thị hàng badge dưới cùng
                           (giống "LY 35,176,580" / "YTD 44,631,301" trong ảnh mẫu)
    delta:  chuỗi hiển thị % thay đổi, ví dụ "+21%"
    delta_is_good: True→xanh, False→đỏ, None→tự suy từ dấu của delta
    """
    t = get_kpi_theme(theme)
    pastel = t["pastel"].get(tone, t["pastel"]["sky"])

    if delta_is_good is None and delta:
        delta_is_good = not str(delta).strip().startswith("-")
    delta_color = t["positive"] if delta_is_good else t["negative"]

    def _badge(lbl, val):
        if val is None:
            return None
        return html.Span([
            html.Span(lbl, style={
                "fontSize": "9px", "fontWeight": "700", "color": pastel["fg"],
                "opacity": "0.75", "marginRight": "5px", "letterSpacing": "0.04em",
            }),
            html.Span(str(val), style={
                "fontSize": "11px", "fontWeight": "700", "color": pastel["fg"],
            }),
        ], style={
            "backgroundColor": pastel["icon_bg"], "borderRadius": "100px",
            "padding": "3px 10px", "marginRight": "6px", "display": "inline-block",
        })

    badges = [b for b in [_badge(*sub_left) if sub_left else None,
                           _badge(*sub_right) if sub_right else None] if b]

    return html.Div([
        html.Div([
            html.Span(label, style={
                "fontSize": "11px", "fontWeight": "700", "color": pastel["fg"],
                "letterSpacing": "0.08em", "textTransform": "uppercase",
                "opacity": "0.85",
            }),
            html.Div(html.I(className=icon_class), style={
                "width": "30px", "height": "30px", "borderRadius": "50%",
                "backgroundColor": pastel["icon_bg"], "color": pastel["fg"],
                "display": "flex", "alignItems": "center", "justifyContent": "center",
                "fontSize": "13px", "flexShrink": "0",
            }),
        ], style={"display": "flex", "justifyContent": "space-between",
                   "alignItems": "flex-start", "marginBottom": "10px"}),

        html.Div([
            html.Span(value, style={
                "fontSize": "1.5rem", "fontWeight": "800", "color": pastel["fg"],
                "letterSpacing": "-0.02em", "marginRight": "8px",
            }),
            html.Span(delta, style={
                "fontSize": "11px", "fontWeight": "700", "color": delta_color,
            }) if delta else None,
        ], style={"marginBottom": "10px" if badges else "0", "display": "flex",
                   "alignItems": "baseline"}),

        html.Div(badges, style={"display": "flex", "flexWrap": "wrap"}) if badges else None,
    ], style={
        "backgroundColor": pastel["bg"], "borderRadius": "16px",
        "padding": "16px 18px", "border": f"1px solid {t['card_border']}",
        "boxShadow": t["card_shadow"], "height": "100%",
    })


# ============================================================================
# 3) PLOTLY LAYOUT BASE — theme-aware, dùng chung cho mọi go.Figure
# ============================================================================
def plotly_base_layout(theme, height=280, font_family="Inter, system-ui, sans-serif"):
    t = get_kpi_theme(theme)
    return dict(
        paper_bgcolor=t["chart_paper"],
        plot_bgcolor=t["chart_paper"],
        font=dict(color=t["chart_text"], size=11, family=font_family),
        margin=dict(l=10, r=15, t=30, b=30),
        height=height,
        legend=dict(
            bgcolor="rgba(0,0,0,0)", bordercolor=t["card_border"], borderwidth=0,
            font=dict(size=10, color=t["chart_text"], family=font_family),
            orientation="h", x=0, y=1.12, xanchor="left",
        ),
        hoverlabel=dict(
            bgcolor=t["pastel"]["sky"]["bg"], bordercolor=t["card_border"],
            font=dict(family=font_family, size=11, color=t["page_text"]),
        ),
        hovermode="x unified",
    )


def plotly_axis_style(theme):
    t = get_kpi_theme(theme)
    return dict(
        gridcolor=t["chart_grid"], gridwidth=1, zeroline=False,
        tickfont=dict(color=t["chart_text"], size=10),
        showline=False,
    )