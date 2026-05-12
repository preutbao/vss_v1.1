# src/pages/onboarding.py
# ─────────────────────────────────────────────────────────────────────────────
# IPS Onboarding — FIXED
# Giữ nguyên dict-ID pattern để callbacks trong investor_profile_callbacks.py
# hoạt động đúng. Bước 4 & 5 được ẩn/hiện hoàn toàn qua Dash callback
# (render_step_visibility), không dùng JS để hide/show nữa.
# ─────────────────────────────────────────────────────────────────────────────

from dash import html, dcc
import dash_bootstrap_components as dbc
from src.components.header import create_topbar

_BG_PAGE  = "#080d16"
_BG_CARD  = "#0d1117"
_BG_CARD2 = "#161b22"
_BORDER   = "#21262d"
_BORDER2  = "#30363d"
_TEXT_PRI = "#e6edf3"
_TEXT_SEC = "#8b949e"
_TEXT_MUT = "#484f58"
_BLUE     = "#3b82f6"
_GREEN    = "#10b981"
_AMBER    = "#f59e0b"
_RED      = "#ef4444"
_PURPLE   = "#a78bfa"
_FONT_SORA  = "'Sora', 'Inter', sans-serif"
_FONT_INTER = "'Inter', sans-serif"
_FONT_MONO  = "'Roboto Mono', monospace"


# ── Choice card — dict ID, n_clicks — khớp 100% với callbacks ────────────────
def _choice_card(group, value, icon, label, sub):
    color_map = {
        "goal": _BLUE, "will": _AMBER, "time": _GREEN, "liq": _PURPLE
    }
    c = color_map.get(group, _BLUE)
    return html.Div(
        [
            html.I(className=icon, style={
                "fontSize": "22px", "color": c,
                "marginBottom": "8px", "display": "block",
            }),
            html.Div(label, style={
                "fontSize": "14px", "fontWeight": "700",
                "color": _TEXT_PRI, "marginBottom": "4px",
                "fontFamily": _FONT_SORA,
            }),
            html.Div(sub, style={
                "fontSize": "12px", "color": _TEXT_SEC,
            }),
        ],
        # ── Dict ID — bắt buộc để callbacks select_goal/will/time/liq chạy ──
        id={"type": "ips-choice", "id": f"{group}-{value}"},
        n_clicks=0,
        className="choice-card",
        style={
            "padding": "16px 12px",
            "border": f"1px solid {_BORDER}",
            "borderRadius": "8px",
            "backgroundColor": _BG_CARD,
            "cursor": "pointer",
            "textAlign": "center",
            "transition": "all 0.2s",
        },
    )


def _hero_section():
    return html.Section(id="hero-section", className="hero", children=[
        html.Div(id="hero-progress", className="hero-progress-bar", style={"width": "0%"}),
        html.Div(id="hero-slides-container"),
        html.Div(className="hero-controls", children=[
            html.Button("←", id="hero-prev", className="hero-btn"),
            html.Button("→", id="hero-next", className="hero-btn"),
            html.Span("01 / 10", id="hero-counter", className="hero-counter"),
            html.Span("· ← → keys", className="hero-keys"),
        ]),
        html.Div(id="hero-legend", className="hero-legend"),
        html.Div(id="hero-credit", className="hero-credit"),
        html.Div(id="hero-eras", className="hero-eras"),
        html.Div(className="hero-timeline", children=[
            html.Div(id="tl-inner", className="tl-inner"),
        ]),
    ])


# ── STEP 1 ────────────────────────────────────────────────────────────────────
def _step1():
    return html.Div(id="ips-step-1", children=[
        html.Div([
            html.Div("BƯỚC 01 / 05", style={
                "fontFamily": _FONT_MONO, "fontSize": "11px",
                "color": _BLUE, "letterSpacing": "2px", "marginBottom": "8px",
            }),
            html.Div(style={"flex": "1", "height": "1px",
                            "backgroundColor": _BORDER}),
        ], style={"display": "flex", "alignItems": "center", "gap": "12px",
                  "marginBottom": "16px"}),
        html.H4("Mục tiêu đầu tư chính của bạn là gì?", style={
            "color": _TEXT_PRI, "fontFamily": _FONT_SORA,
            "fontSize": "clamp(18px,2.5vw,26px)", "fontWeight": "700",
            "marginBottom": "6px",
        }),
        html.P("Câu trả lời này quyết định toàn bộ chiến lược và bộ lọc được áp dụng.", style={
            "fontSize": "13px", "color": _TEXT_SEC, "marginBottom": "20px",
        }),
        html.Div([
            _choice_card("goal","preserve","fas fa-shield-alt","Bảo toàn vốn","An toàn là ưu tiên số 1"),
            _choice_card("goal","income",  "fas fa-coins","Tạo dòng tiền","Cổ tức đều đặn hàng quý"),
            _choice_card("goal","growth",  "fas fa-chart-line","Tăng trưởng tài sản","Tích lũy dài hạn 3–10 năm"),
            _choice_card("goal","speculate","fas fa-rocket","Lướt sóng sinh lời","Cơ hội ngắn hạn, linh hoạt"),
        ], style={"display": "grid", "gridTemplateColumns": "1fr 1fr",
                  "gap": "12px", "marginBottom": "12px"}),
        html.Div(id="ips-step1-error", style={
            "color": _RED, "fontSize": "12px", "minHeight": "18px",
        }),
    ])


# ── STEP 2 ────────────────────────────────────────────────────────────────────
def _step2():
    return html.Div(id="ips-step-2", children=[
        html.Div([
            html.Div("BƯỚC 02 / 05", style={
                "fontFamily": _FONT_MONO, "fontSize": "11px",
                "color": _AMBER, "letterSpacing": "2px", "marginBottom": "8px",
            }),
            html.Div(style={"flex": "1", "height": "1px", "backgroundColor": _BORDER}),
        ], style={"display": "flex", "alignItems": "center", "gap": "12px",
                  "marginBottom": "16px"}),
        html.H4("Nếu danh mục giảm 20% trong 1 tháng, bạn làm gì?", style={
            "color": _TEXT_PRI, "fontFamily": _FONT_SORA,
            "fontSize": "clamp(18px,2.5vw,26px)", "fontWeight": "700",
            "marginBottom": "6px",
        }),
        html.P("Đây là thước đo khẩu vị rủi ro thực sự (CFA L3 — Willingness to Take Risk).", style={
            "fontSize": "13px", "color": _TEXT_SEC, "marginBottom": "20px",
        }),
        html.Div([
            _choice_card("will","panic","fas fa-exclamation-triangle","Bán cắt lỗ ngay","Không thể chịu thua lỗ"),
            _choice_card("will","worry","fas fa-mug-hot","Lo lắng, chờ đợi","Theo dõi và chờ tình hình"),
            _choice_card("will","hold", "fas fa-anchor","Giữ vững kế hoạch","Tin tưởng chiến lược dài hạn"),
            _choice_card("will","buy",  "fas fa-shopping-cart","Vui mừng mua thêm","Giảm giá = cơ hội mua vào"),
        ], style={"display": "grid", "gridTemplateColumns": "1fr 1fr",
                  "gap": "12px", "marginBottom": "12px"}),
        html.Div(id="ips-step2-error", style={
            "color": _RED, "fontSize": "12px", "minHeight": "18px",
        }),
    ])


# ── STEP 3 ────────────────────────────────────────────────────────────────────
def _step3():
    return html.Div(id="ips-step-3", children=[
        html.Div([
            html.Div("BƯỚC 03 / 05", style={
                "fontFamily": _FONT_MONO, "fontSize": "11px",
                "color": _GREEN, "letterSpacing": "2px", "marginBottom": "8px",
            }),
            html.Div(style={"flex": "1", "height": "1px", "backgroundColor": _BORDER}),
        ], style={"display": "flex", "alignItems": "center", "gap": "12px",
                  "marginBottom": "16px"}),
        html.H4("Thời gian & ràng buộc tài chính", style={
            "color": _TEXT_PRI, "fontFamily": _FONT_SORA,
            "fontSize": "clamp(18px,2.5vw,26px)", "fontWeight": "700",
            "marginBottom": "6px",
        }),
        html.P("Giúp VSS xác định Ability to Take Risk (CFA L3 — TTLLU).", style={
            "fontSize": "13px", "color": _TEXT_SEC, "marginBottom": "20px",
        }),

        html.Div("Thời gian đầu tư dự kiến", style={
            "fontSize": "12px", "color": _TEXT_SEC,
            "fontWeight": "600", "marginBottom": "10px",
        }),
        html.Div([
            _choice_card("time","short","fas fa-stopwatch","Dưới 1 Năm","Ngắn hạn linh hoạt"),
            _choice_card("time","mid","fas fa-calendar-alt","1 – 3 Năm","Trung hạn cân bằng"),
            _choice_card("time","long","fas fa-infinity","Trên 3 Năm","Dài hạn tích lũy"),
        ], style={"display": "grid", "gridTemplateColumns": "1fr 1fr 1fr",
                  "gap": "10px", "marginBottom": "20px"}),

        html.Div("Nhu cầu rút tiền đột xuất (Liquidity)", style={
            "fontSize": "12px", "color": _TEXT_SEC,
            "fontWeight": "600", "marginBottom": "10px",
        }),
        html.Div([
            _choice_card("liq","high","fas fa-money-bill-wave","Cao","Cần rút bất cứ lúc nào"),
            _choice_card("liq","mid", "fas fa-tint","Trung bình","Thỉnh thoảng cần rút"),
            _choice_card("liq","low", "fas fa-lock","Thấp","Có thể để dài hạn"),
        ], style={"display": "grid", "gridTemplateColumns": "1fr 1fr 1fr",
                  "gap": "10px", "marginBottom": "20px"}),

        html.Div("% Thu nhập hàng tháng dành cho Chứng khoán:", style={
            "fontSize": "12px", "color": _TEXT_SEC, "marginBottom": "6px",
        }),
        dcc.Slider(0, 100, 10, value=30, id="ips-pct-savings-slider",
                   tooltip={"placement": "bottom", "always_visible": True}),
        html.Div(style={"height": "16px"}),

        html.Div("Quỹ dự phòng khẩn cấp (tháng chi tiêu):", style={
            "fontSize": "12px", "color": _TEXT_SEC, "marginBottom": "6px",
        }),
        dcc.Slider(0, 12, 1, value=4, id="ips-emergency-slider",
                   tooltip={"placement": "bottom", "always_visible": True}),
        html.Div(style={"height": "16px"}),

        dbc.Checklist(
            options=[
                {"label": "Ưu tiên nhận cổ tức đều đặn",        "value": "prefer_dividend"},
                {"label": "Tránh mua Ngân hàng / BĐS",           "value": "avoid_bank_re"},
                {"label": "Bật chế độ Người Mới (Beginner Mode)","value": "beginner"},
            ],
            value=["beginner"],
            id="ips-unique-checklist",
            inline=True,
            style={"color": _TEXT_PRI, "fontSize": "13px"},
        ),
        html.Div(id="ips-step3-error", style={
            "color": _RED, "fontSize": "12px",
            "minHeight": "18px", "marginTop": "10px",
        }),
    ])


# ── STEP 4 — render bởi callback render_profile_preview ──────────────────────
def _step4():
    return html.Div(id="ips-step-4", children=[
        html.Div([
            html.Div("BƯỚC 04 / 05", style={
                "fontFamily": _FONT_MONO, "fontSize": "11px",
                "color": _PURPLE, "letterSpacing": "2px", "marginBottom": "8px",
            }),
            html.Div(style={"flex": "1", "height": "1px", "backgroundColor": _BORDER}),
        ], style={"display": "flex", "alignItems": "center", "gap": "12px",
                  "marginBottom": "16px"}),
        html.H4("Hồ sơ đầu tư của bạn", style={
            "color": _TEXT_PRI, "fontFamily": _FONT_SORA,
            "fontSize": "clamp(18px,2.5vw,26px)", "fontWeight": "700",
            "marginBottom": "6px",
        }),
        html.P("VSS đã tổng hợp hồ sơ IPS dựa trên câu trả lời. Xem lại và xác nhận trước khi áp dụng.", style={
            "fontSize": "13px", "color": _TEXT_SEC, "marginBottom": "20px",
        }),
        # Nội dung được điền bởi callback render_profile_preview
        html.Div(id="ips-profile-preview"),
    ])


# ── STEP 5 — render bởi callback render_final_summary ────────────────────────
def _step5():
    return html.Div(id="ips-step-5", children=[
        html.Div([
            html.Div("BƯỚC 05 / 05", style={
                "fontFamily": _FONT_MONO, "fontSize": "11px",
                "color": _GREEN, "letterSpacing": "2px", "marginBottom": "8px",
            }),
            html.Div(style={"flex": "1", "height": "1px", "backgroundColor": _BORDER}),
        ], style={"display": "flex", "alignItems": "center", "gap": "12px",
                  "marginBottom": "16px"}),
        html.H4("Sẵn sàng khám phá thị trường", style={
            "color": _TEXT_PRI, "fontFamily": _FONT_SORA,
            "fontSize": "clamp(18px,2.5vw,26px)", "fontWeight": "700",
            "marginBottom": "6px",
        }),
        html.P("Lưu hồ sơ và áp dụng bộ lọc thông minh ngay vào Screener.", style={
            "fontSize": "13px", "color": _TEXT_SEC, "marginBottom": "20px",
        }),
        # Nội dung được điền bởi callback render_final_summary
        html.Div(id="ips-final-summary"),

        dbc.Checklist(
            options=[{
                "label": "Tự động cấu hình Bộ Lọc Screener theo Hồ sơ này",
                "value": "apply_filters",
            }],
            value=["apply_filters"],
            id="ips-apply-options",
            style={"marginTop": "20px", "color": _GREEN,
                   "fontWeight": "600", "fontSize": "13px"},
        ),

        html.Div([
            html.I(className="fas fa-exclamation-triangle",
                   style={"color": _AMBER, "marginRight": "6px", "fontSize": "11px"}),
            html.Span(
                "Toàn bộ gợi ý chỉ mang tính tham khảo, không phải khuyến nghị "
                "mua/bán. Nhà đầu tư tự chịu trách nhiệm.",
                style={"fontSize": "11px", "color": _TEXT_MUT, "lineHeight": "1.6"},
            ),
        ], style={
            "backgroundColor": "#0c0a00", "border": "1px solid #92400e",
            "borderRadius": "6px", "padding": "10px 12px", "marginTop": "14px",
        }),

        html.Div(id="ips-apply-status", style={
            "fontSize": "12px", "minHeight": "20px", "marginTop": "10px",
        }),
    ])

# ─────────────────────────────────────────────────────────────────────────────
# LAYOUT
# ─────────────────────────────────────────────────────────────────────────────
layout = html.Div(
    id="ips-onboarding-wrapper",
    style={
        "minHeight": "100vh",
        "paddingTop": "60px",  # <--- THÊM padding-top ĐỂ KHÔNG BỊ TOPBAR ĐÈ
        "backgroundColor": _BG_PAGE,
        "backgroundImage": (
            "radial-gradient(ellipse at 20% 50%, rgba(59,130,246,0.06) 0%, transparent 60%),"
            "radial-gradient(ellipse at 80% 20%, rgba(16,185,129,0.04) 0%, transparent 50%)"
        ),
    },
    children=[
        # ── GỌI TOPBAR RA ĐÂY ──────────────────────────────────────────────
        create_topbar(),

        _hero_section(),

        html.Div(
            style={
                "maxWidth": "680px", "margin": "0 auto",
                "padding": "48px 24px 80px",
            },
            children=[
                # ── Logo ──────────────────────────────────────────────────
                html.Div([
                    html.Div([
                        html.I(className="fas fa-chart-line",
                               style={"color": _BLUE, "fontSize": "24px",
                                      "marginRight": "10px"}),
                        html.Span("VSS Smart Screener", style={
                            "fontSize": "20px", "fontWeight": "800",
                            "color": _TEXT_PRI, "fontFamily": _FONT_SORA,
                        }),
                    ], style={"display": "flex", "alignItems": "center",
                              "justifyContent": "center", "marginBottom": "8px"}),
                    html.P(
                        "Trước khi bắt đầu, hãy để VSS hiểu rõ hơn về bạn — "
                        "chỉ mất 2 phút để thiết lập hồ sơ đầu tư cá nhân.",
                        style={"fontSize": "13px", "color": _TEXT_SEC,
                               "textAlign": "center", "lineHeight": "1.7",
                               "marginBottom": "32px"},
                    ),
                ]),

                # ── Progress bar — render bởi callback ───────────────────
                html.Div(id="ips-progress-bar", style={"marginBottom": "32px"}),

                # ── Card wrapper ──────────────────────────────────────────
                html.Div(
                    style={
                        "backgroundColor": _BG_CARD,
                        "border": f"1px solid {_BORDER}",
                        "borderRadius": "16px",
                        "overflow": "hidden",
                        "boxShadow": "0 24px 80px rgba(0,0,0,0.5)",
                    },
                    children=[
                        # Card header
                        html.Div([
                            html.Div([
                                html.I(className="fas fa-user-cog",
                                       style={"color": _BLUE, "marginRight": "8px"}),
                                html.Span("Thiết lập Hồ sơ Đầu tư",
                                          style={"fontSize": "14px", "fontWeight": "700",
                                                 "color": _TEXT_PRI, "fontFamily": _FONT_SORA}),
                                html.Span(" — IPS",
                                          style={"fontSize": "12px", "color": _TEXT_MUT,
                                                 "fontFamily": _FONT_MONO, "marginLeft": "6px"}),
                            ], style={"display": "flex", "alignItems": "center"}),
                            html.Div("Bước 1 / 5", id="ips-step-counter", style={
                                "fontSize": "11px", "color": _TEXT_MUT,
                                "fontFamily": _FONT_MONO,
                                "backgroundColor": "#0d1117",
                                "border": f"1px solid {_BORDER}",
                                "padding": "4px 10px", "borderRadius": "20px",
                            }),
                        ], style={
                            "display": "flex", "justifyContent": "space-between",
                            "alignItems": "center",
                            "padding": "14px 22px",
                            "borderBottom": f"1px solid {_BORDER}",
                            "backgroundColor": _BG_CARD2,
                        }),

                        # Card body — chứa tất cả steps
                        html.Div(
                            style={"padding": "24px", "backgroundColor": "#0c1220"},
                            children=[
                                _step1(),
                                _step2(),
                                _step3(),
                                _step4(),
                                _step5(),

                                # Stores
                                dcc.Store(id="ips-current-step", data=1),
                                dcc.Store(id="ips-goal-store",   data=None),
                                dcc.Store(id="ips-will-store",   data=None),
                                dcc.Store(id="ips-time-store",   data=None),
                                dcc.Store(id="ips-liq-store",    data=None),
                            ],
                        ),

                        # Card footer — nav buttons
                        html.Div([
                            dbc.Button(
                                [html.I(className="fas fa-arrow-left",
                                        style={"marginRight": "6px"}), "Quay lại"],
                                id="ips-btn-prev", size="sm",
                                style={
                                    "backgroundColor": _BG_CARD2,
                                    "border": f"1px solid {_BORDER2}",
                                    "color": _TEXT_SEC, "borderRadius": "6px",
                                    "fontFamily": _FONT_INTER, "fontSize": "12px",
                                    "minWidth": "100px",
                                },
                            ),
                            dbc.Button(
                                ["Tiếp theo ",
                                 html.I(className="fas fa-arrow-right",
                                        style={"marginLeft": "6px"})],
                                id="ips-btn-next", size="sm",
                                style={
                                    "background": "linear-gradient(135deg,#1d4ed8,#2563eb)",
                                    "border": "none", "color": "#e0f2fe",
                                    "borderRadius": "6px",
                                    "fontFamily": _FONT_SORA, "fontSize": "12px",
                                    "fontWeight": "700", "minWidth": "120px",
                                },
                            ),
                        ], style={
                            "display": "flex", "justifyContent": "space-between",
                            "alignItems": "center",
                            "padding": "14px 22px",
                            "borderTop": f"1px solid {_BORDER}",
                            "backgroundColor": _BG_CARD2,
                        }),
                    ],
                ),

                html.P(
                    "🔒 Dữ liệu hồ sơ được lưu trên thiết bị của bạn — không gửi lên máy chủ.",
                    style={"fontSize": "11px", "color": _TEXT_MUT,
                           "textAlign": "center", "marginTop": "20px"},
                ),
            ],
        ),
    ],
)