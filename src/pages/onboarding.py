# src/pages/onboarding.py
# ─────────────────────────────────────────────────────────────────────────────
# IPS Onboarding — Giao diện FULL-PAGE thay thế dbc.Modal
#
# Hiển thị toàn màn hình khi user chưa thiết lập hồ sơ (profile-setup-done=False).
# Sau khi nhấn "Lưu & Áp dụng" ở Bước 5, profile-setup-done → True và
# main.py sẽ ẩn trang này, hiện phần giao diện chính.
#
# Giữ nguyên 100% component IDs để các callback trong
# investor_profile_callbacks.py không cần sửa.
# ─────────────────────────────────────────────────────────────────────────────

from dash import html, dcc
import dash_bootstrap_components as dbc

# ── Màu sắc nhất quán với dark theme VSS ─────────────────────────────────────
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


# ── Choice card (giữ nguyên ID pattern để callbacks khớp) ─────────────────
def _card(id_str, label, icon, value):
    return html.Div(
        [
            html.I(className=icon, style={
                "fontSize": "26px", "marginBottom": "10px",
                "display": "block", "color": _BLUE,
            }),
            html.Div(label, style={
                "fontSize": "13px", "fontWeight": "600", "color": _TEXT_PRI,
                "fontFamily": _FONT_SORA,
            }),
        ],
        id={"type": "ips-choice", "id": id_str},
        **{"data-value": value},
        className="ips-choice-card",
        style={
            "padding": "20px 10px",
            "backgroundColor": _BG_CARD,
            "border": f"1px solid {_BORDER}",
            "borderRadius": "12px",
            "textAlign": "center",
            "cursor": "pointer",
            "transition": "all 0.2s",
        },
    )


# ── Tiêu đề trang (logo + brand) ─────────────────────────────────────────────
def _page_header():
    return html.Div(
        style={
            "textAlign": "center",
            "marginBottom": "32px",
        },
        children=[
            # Logo / brand badge
            html.Div(
                [
                    html.I(className="fas fa-chart-line",
                           style={"color": _BLUE, "fontSize": "28px", "marginRight": "10px"}),
                    html.Span("VSS Smart Screener", style={
                        "fontSize": "22px", "fontWeight": "800",
                        "color": _TEXT_PRI, "fontFamily": _FONT_SORA,
                        "letterSpacing": "0.3px",
                    }),
                ],
                style={"display": "flex", "alignItems": "center",
                       "justifyContent": "center", "marginBottom": "10px"},
            ),
            html.P(
                "Trước khi bắt đầu, hãy để VSS hiểu rõ hơn về bạn — "
                "chỉ mất 2 phút để thiết lập hồ sơ đầu tư cá nhân.",
                style={
                    "fontSize": "13px", "color": _TEXT_SEC,
                    "maxWidth": "480px", "margin": "0 auto",
                    "lineHeight": "1.7", "fontFamily": _FONT_INTER,
                },
            ),
        ],
    )


# ── Wizard card container ─────────────────────────────────────────────────────
def _wizard_card():
    return html.Div(
        style={
            "width": "100%",
            "maxWidth": "680px",
            "margin": "0 auto",
            "backgroundColor": _BG_CARD,
            "borderRadius": "16px",
            "border": f"1px solid {_BORDER}",
            "overflow": "hidden",
            "boxShadow": "0 24px 80px rgba(0,0,0,0.6)",
        },
        children=[
            # ── Card header ──────────────────────────────────────────────
            html.Div(
                style={
                    "backgroundColor": _BG_CARD2,
                    "borderBottom": f"1px solid {_BORDER}",
                    "padding": "16px 24px",
                    "display": "flex",
                    "alignItems": "center",
                    "justifyContent": "space-between",
                },
                children=[
                    html.Div([
                        html.I(className="fas fa-user-cog",
                               style={"color": _BLUE, "marginRight": "10px",
                                      "fontSize": "15px"}),
                        html.Span("Thiết lập Hồ sơ Đầu tư", style={
                            "color": _TEXT_PRI, "fontSize": "14px",
                            "fontWeight": "700", "fontFamily": _FONT_SORA,
                        }),
                        html.Span(" — IPS", style={
                            "color": _TEXT_MUT, "fontSize": "12px",
                            "fontFamily": _FONT_MONO, "marginLeft": "6px",
                        }),
                    ], style={"display": "flex", "alignItems": "center"}),
                    # Step counter badge
                    html.Div(
                        id="ips-step-counter",
                        children="Bước 1 / 5",
                        style={
                            "fontSize": "11px", "color": _TEXT_MUT,
                            "fontFamily": _FONT_MONO,
                            "backgroundColor": _BG_CARD,
                            "border": f"1px solid {_BORDER}",
                            "padding": "4px 10px", "borderRadius": "20px",
                        },
                    ),
                ],
            ),

            # ── Card body ─────────────────────────────────────────────────
            html.Div(
                style={"padding": "24px", "backgroundColor": "#0c1220"},
                children=[

                    # Progress bar (rendered bởi callback render_step_visibility)
                    html.Div(id="ips-progress-bar", style={"marginBottom": "24px"}),

                    # ── STEP 1: MỤC TIÊU ─────────────────────────────────
                    html.Div(id="ips-step-1", children=[
                        html.H5("Mục tiêu đầu tư chính của bạn là gì?", style={
                            "color": _TEXT_PRI, "marginBottom": "6px",
                            "fontWeight": "700", "fontFamily": _FONT_SORA,
                            "fontSize": "16px",
                        }),
                        html.P(
                            "Câu trả lời này quyết định toàn bộ chiến lược và bộ lọc được áp dụng.",
                            style={"fontSize": "12px", "color": _TEXT_SEC,
                                   "marginBottom": "20px", "lineHeight": "1.6"},
                        ),
                        html.Div([
                            _card("goal-preserve", "Bảo toàn vốn",       "fas fa-shield-alt",       "preserve"),
                            _card("goal-income",   "Tạo dòng tiền (Cổ tức)", "fas fa-coins",        "income"),
                            _card("goal-growth",   "Tăng trưởng tài sản", "fas fa-chart-line",       "growth"),
                            _card("goal-speculate","Lướt sóng sinh lời",  "fas fa-rocket",           "speculate"),
                        ], style={
                            "display": "grid", "gridTemplateColumns": "1fr 1fr",
                            "gap": "14px", "marginBottom": "16px",
                        }),
                        html.Div(id="ips-step1-error", style={
                            "color": _RED, "fontSize": "12px",
                            "fontWeight": "600", "minHeight": "20px",
                        }),
                    ]),

                    # ── STEP 2: TÂM LÝ (WILLINGNESS) ─────────────────────
                    html.Div(id="ips-step-2", children=[
                        html.H5("Nếu danh mục giảm 20% trong 1 tháng, bạn sẽ làm gì?",
                                style={"color": _TEXT_PRI, "marginBottom": "6px",
                                       "fontWeight": "700", "fontFamily": _FONT_SORA,
                                       "fontSize": "16px"}),
                        html.P("Đây là thước đo khẩu vị rủi ro thực sự của bạn (CFA L3 — Willingness).",
                               style={"fontSize": "12px", "color": _TEXT_SEC,
                                      "marginBottom": "20px", "lineHeight": "1.6"}),
                        html.Div([
                            _card("will-panic", "Bán cắt lỗ ngay",    "fas fa-arrow-trend-down", "panic"),
                            _card("will-worry", "Lo lắng, chờ đợi",   "fas fa-mug-hot",          "worry"),
                            _card("will-hold",  "Giữ vững kế hoạch",  "fas fa-anchor",           "hold"),
                            _card("will-buy",   "Vui mừng mua thêm",  "fas fa-cart-plus",        "buy"),
                        ], style={
                            "display": "grid", "gridTemplateColumns": "1fr 1fr",
                            "gap": "14px", "marginBottom": "16px",
                        }),
                        html.Div(id="ips-step2-error", style={
                            "color": _RED, "fontSize": "12px",
                            "fontWeight": "600", "minHeight": "20px",
                        }),
                    ]),

                    # ── STEP 3: RÀNG BUỘC TÀI CHÍNH ─────────────────────
                    html.Div(id="ips-step-3", children=[
                        html.H5("Thời gian & ràng buộc tài chính",
                                style={"color": _TEXT_PRI, "marginBottom": "6px",
                                       "fontWeight": "700", "fontFamily": _FONT_SORA,
                                       "fontSize": "16px"}),
                        html.P("Giúp VSS xác định Ability to Take Risk của bạn (CFA L3 — TTLLU).",
                               style={"fontSize": "12px", "color": _TEXT_SEC,
                                      "marginBottom": "20px", "lineHeight": "1.6"}),

                        html.Label("Thời gian đầu tư dự kiến:",
                                   style={"color": _TEXT_SEC, "fontSize": "12px",
                                          "fontWeight": "600", "marginBottom": "8px",
                                          "display": "block"}),
                        html.Div([
                            _card("time-short", "Dưới 1 Năm", "fas fa-stopwatch",    "short"),
                            _card("time-mid",   "1 – 3 Năm",  "fas fa-calendar-days","mid"),
                            _card("time-long",  "Trên 3 Năm", "fas fa-infinity",     "long"),
                        ], style={
                            "display": "grid", "gridTemplateColumns": "1fr 1fr 1fr",
                            "gap": "10px", "marginBottom": "22px",
                        }),

                        html.Label("Nhu cầu rút tiền đột xuất (Liquidity):",
                                   style={"color": _TEXT_SEC, "fontSize": "12px",
                                          "fontWeight": "600", "marginBottom": "8px",
                                          "display": "block"}),
                        html.Div([
                            _card("liq-high", "Cao",         "fas fa-money-bill-wave", "high"),
                            _card("liq-mid",  "Trung bình",  "fas fa-water",           "mid"),
                            _card("liq-low",  "Thấp",        "fas fa-lock",            "low"),
                        ], style={
                            "display": "grid", "gridTemplateColumns": "1fr 1fr 1fr",
                            "gap": "10px", "marginBottom": "22px",
                        }),

                        html.Label("% Thu nhập hàng tháng dành cho Chứng khoán:",
                                   style={"color": _TEXT_SEC, "fontSize": "12px",
                                          "marginBottom": "6px", "display": "block"}),
                        dcc.Slider(0, 100, 10, value=30, id="ips-pct-savings-slider",
                                   tooltip={"placement": "bottom", "always_visible": True}),
                        html.Div(style={"height": "18px"}),

                        html.Label("Quỹ dự phòng khẩn cấp (tháng chi tiêu):",
                                   style={"color": _TEXT_SEC, "fontSize": "12px",
                                          "marginBottom": "6px", "display": "block"}),
                        dcc.Slider(0, 12, 1, value=4, id="ips-emergency-slider",
                                   tooltip={"placement": "bottom", "always_visible": True}),
                        html.Div(style={"height": "18px"}),

                        dbc.Checklist(
                            options=[
                                {"label": "Ưu tiên nhận cổ tức đều đặn",      "value": "prefer_dividend"},
                                {"label": "Tránh mua Ngân hàng / BĐS",         "value": "avoid_bank_re"},
                                {"label": "Bật chế độ Người Mới (Beginner Mode)", "value": "beginner"},
                            ],
                            value=["beginner"],
                            id="ips-unique-checklist",
                            inline=True,
                            style={"color": _TEXT_PRI, "fontSize": "13px"},
                        ),
                        html.Div(id="ips-step3-error", style={
                            "color": _RED, "fontSize": "12px",
                            "fontWeight": "600", "minHeight": "20px",
                            "marginTop": "10px",
                        }),
                    ]),

                    # ── STEP 4: PREVIEW PROFILE ───────────────────────────
                    html.Div(id="ips-step-4", children=[
                        html.Div(id="ips-profile-preview"),
                    ]),

                    # ── STEP 5: SUMMARY & APPLY ───────────────────────────
                    html.Div(id="ips-step-5", children=[
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

                        # Disclaimer
                        html.Div([
                            html.I(className="fas fa-exclamation-triangle",
                                   style={"color": _AMBER, "marginRight": "6px",
                                          "fontSize": "11px"}),
                            html.Span(
                                "Toàn bộ gợi ý chỉ mang tính tham khảo, không phải "
                                "khuyến nghị mua/bán. Nhà đầu tư tự chịu trách nhiệm.",
                                style={"fontSize": "11px", "color": _TEXT_MUT,
                                       "lineHeight": "1.6"},
                            ),
                        ], style={
                            "backgroundColor": "#0c0a00",
                            "border": "1px solid #92400e",
                            "borderRadius": "6px", "padding": "10px 12px",
                            "marginTop": "14px",
                        }),

                        html.Div(id="ips-apply-status", style={
                            "fontSize": "12px", "minHeight": "20px",
                            "marginTop": "10px",
                        }),
                    ]),

                    # ── Stores ẩn ─────────────────────────────────────────
                    dcc.Store(id="ips-current-step",  data=1),
                    dcc.Store(id="ips-goal-store",    data=None),
                    dcc.Store(id="ips-will-store",    data=None),
                    dcc.Store(id="ips-time-store",    data=None),
                    dcc.Store(id="ips-liq-store",     data=None),
                ],
            ),

            # ── Card footer: navigation buttons ──────────────────────────
            html.Div(
                style={
                    "display": "flex",
                    "justifyContent": "space-between",
                    "alignItems": "center",
                    "padding": "14px 24px",
                    "borderTop": f"1px solid {_BORDER}",
                    "backgroundColor": _BG_CARD2,
                },
                children=[
                    dbc.Button(
                        [html.I(className="fas fa-arrow-left",
                                style={"marginRight": "6px"}), "Quay lại"],
                        id="ips-btn-prev",
                        size="sm",
                        style={
                            "backgroundColor": _BG_CARD2,
                            "border": f"1px solid {_BORDER2}",
                            "color": _TEXT_SEC,
                            "borderRadius": "6px",
                            "fontFamily": _FONT_INTER,
                            "fontSize": "12px",
                            "minWidth": "100px",
                        },
                    ),
                    dbc.Button(
                        ["Tiếp theo ",
                         html.I(className="fas fa-arrow-right",
                                style={"marginLeft": "6px"})],
                        id="ips-btn-next",
                        size="sm",
                        style={
                            "background": "linear-gradient(135deg, #1d4ed8, #2563eb)",
                            "border": "none",
                            "color": "#e0f2fe",
                            "borderRadius": "6px",
                            "fontFamily": _FONT_SORA,
                            "fontSize": "12px",
                            "fontWeight": "700",
                            "letterSpacing": "0.3px",
                            "minWidth": "120px",
                        },
                    ),
                ],
            ),
        ],
    )


# ─────────────────────────────────────────────────────────────────────────────
# EXPORT: layout — được import bởi main.py
# ─────────────────────────────────────────────────────────────────────────────
layout = html.Div(
    id="ips-onboarding-wrapper",
    style={
        "minHeight": "100vh",
        "backgroundColor": _BG_PAGE,
        "display": "flex",
        "flexDirection": "column",
        "alignItems": "center",
        "justifyContent": "center",
        "padding": "40px 20px",
        # Subtle animated gradient background
        "backgroundImage": (
            "radial-gradient(ellipse at 20% 50%, rgba(59,130,246,0.06) 0%, transparent 60%),"
            "radial-gradient(ellipse at 80% 20%, rgba(16,185,129,0.04) 0%, transparent 50%)"
        ),
    },
    children=[
        _page_header(),
        _wizard_card(),

        # Footer note
        html.P(
            "Dữ liệu hồ sơ được lưu trên thiết bị của bạn — không gửi lên máy chủ.",
            style={
                "fontSize": "11px", "color": _TEXT_MUT,
                "marginTop": "20px", "fontFamily": _FONT_INTER,
                "textAlign": "center",
            },
        ),
    ],
)