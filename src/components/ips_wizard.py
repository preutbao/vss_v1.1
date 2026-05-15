# src/components/ips_wizard.py
# ─────────────────────────────────────────────────────────────────────────────
# IPS Wizard — Investor Policy Statement onboarding (CFA Level 3–inspired)
#
# Layout thuần túy, không chứa logic. Toàn bộ callback nằm trong:
#   src/callbacks/investor_profile_callbacks.py
#
# Wizard gồm 5 bước:
#   1. Mục tiêu lợi nhuận   (CFA L3: Return Objective)
#   2. Khẩu vị rủi ro        (CFA L3: Willingness + Ability to Take Risk)
#   3. Ràng buộc đầu tư      (CFA L3: TTLLU — Time · Tax · Liquidity · Legal · Unique)
#   4. Hồ sơ & Chiến lược    (Strategy Mapping từ 10 trường phái VSS)
#   5. Xác nhận & Áp dụng   (Auto-apply filters vào screener)
# ─────────────────────────────────────────────────────────────────────────────

from dash import html, dcc
import dash_bootstrap_components as dbc


# ── Màu sắc và typography nhất quán với dark theme của VSS ──────────────────
_BG_MODAL   = "#0c1220"
_BG_CARD    = "#0d1117"
_BG_CARD2   = "#161b22"
_BORDER     = "#21262d"
_BORDER2    = "#30363d"
_TEXT_PRI   = "#e6edf3"
_TEXT_SEC   = "#8b949e"
_TEXT_MUT   = "#484f58"
_BLUE       = "#3b82f6"
_GREEN      = "#10b981"
_AMBER      = "#f59e0b"
_RED        = "#ef4444"
_PURPLE     = "#a78bfa"
_CYAN       = "#00d4ff"

# ── Font helpers ─────────────────────────────────────────────────────────────
_FONT_SORA  = "'Sora', 'Inter', sans-serif"
_FONT_INTER = "'Inter', sans-serif"
_FONT_MONO  = "'Roboto Mono', monospace"


# ─────────────────────────────────────────────────────────────────────────────
# HELPER: tạo một ô lựa chọn kiểu card (Goal / Time / Liquidity cards)
# ─────────────────────────────────────────────────────────────────────────────
def _choice_card(card_id: str, icon_cls: str, label: str, desc: str,
                 icon_color: str = _BLUE, value: str = ""):
    """
    Card có thể click — trạng thái selected/unselected được xử lý bằng JS
    clientside hoặc callback server-side qua n_clicks + State.
    """
    return html.Div(
        id={"type": "ips-choice", "id": card_id},
        n_clicks=0,
        **{"data-value": value},
        children=[
            html.I(className=icon_cls,
                   style={"fontSize": "20px", "color": icon_color,
                          "marginBottom": "6px", "display": "block"}),
            html.Div(label,
                     style={"fontSize": "13px", "fontWeight": "700",
                            "color": _TEXT_PRI, "marginBottom": "4px",
                            "fontFamily": _FONT_SORA}),
            html.Div(desc,
                     style={"fontSize": "11px", "color": _TEXT_SEC,
                            "lineHeight": "1.5", "fontFamily": _FONT_INTER}),
        ],
        style={
            "padding": "14px 12px",
            "border": f"1px solid {_BORDER}",
            "borderRadius": "8px",
            "cursor": "pointer",
            "transition": "all .15s",
            "backgroundColor": _BG_CARD,
            "textAlign": "center",
        },
        className="ips-choice-card",
    )


def _step_badge(num: int, label: str, active: bool = False, done: bool = False):
    """Viên thuốc step indicator."""
    if done:
        bg, color, icon = "#0f3d22", _GREEN, "fas fa-check"
    elif active:
        bg, color, icon = "#0d2137", _BLUE, None
    else:
        bg, color, icon = _BG_CARD2, _TEXT_MUT, None

    return html.Div([
        html.Span(
            html.I(className=icon) if done else str(num),
            style={"fontSize": "11px", "fontWeight": "700",
                   "color": color, "marginRight": "6px",
                   "fontFamily": _FONT_MONO},
        ),
        html.Span(label,
                  style={"fontSize": "11px", "color": color,
                         "fontFamily": _FONT_INTER}),
    ], style={
        "display": "flex", "alignItems": "center",
        "padding": "6px 10px", "borderRadius": "6px",
        "backgroundColor": bg,
        "border": f"1px solid {'#1d4ed8' if active else '#0f3d22' if done else _BORDER}",
    })


# ─────────────────────────────────────────────────────────────────────────────
# STEP PROGRESS BAR (cố định trên cùng modal body)
# ─────────────────────────────────────────────────────────────────────────────
def _progress_bar():
    return html.Div(
        id="ips-progress-bar",
        children=[
            _step_badge(1, "Mục tiêu",  active=True),
            html.Div("→", style={"color": _TEXT_MUT, "fontSize": "12px"}),
            _step_badge(2, "Rủi ro"),
            html.Div("→", style={"color": _TEXT_MUT, "fontSize": "12px"}),
            _step_badge(3, "Ràng buộc"),
            html.Div("→", style={"color": _TEXT_MUT, "fontSize": "12px"}),
            _step_badge(4, "Chiến lược"),
            html.Div("→", style={"color": _TEXT_MUT, "fontSize": "12px"}),
            _step_badge(5, "Xác nhận"),
        ],
        style={
            "display": "flex", "alignItems": "center", "gap": "6px",
            "overflowX": "auto", "paddingBottom": "4px",
            "marginBottom": "20px",
        },
    )


# ─────────────────────────────────────────────────────────────────────────────
# STEP 1 — RETURN OBJECTIVE
# ─────────────────────────────────────────────────────────────────────────────
def _step1_layout():
    return html.Div(id="ips-step-1", children=[
        # Header
        html.Div([
            html.Span("IPS · Bước 1 / 5", style={
                "fontSize": "10px", "color": _BLUE,
                "backgroundColor": "#0d2137",
                "border": f"1px solid #1d4ed8",
                "padding": "3px 8px", "borderRadius": "20px",
                "fontFamily": _FONT_MONO, "letterSpacing": "0.5px",
                "marginBottom": "8px", "display": "inline-block",
            }),
            html.H4("Bạn đang đầu tư vì điều gì?",
                    style={"color": _TEXT_PRI, "fontFamily": _FONT_SORA,
                           "fontSize": "18px", "fontWeight": "700",
                           "marginBottom": "6px", "marginTop": "6px"}),
            html.P(
                "Câu trả lời quyết định toàn bộ chiến lược và bộ lọc sẽ được áp dụng. "
                "Không có câu đúng hay sai — hãy chọn điều thực sự quan trọng với bạn.",
                style={"fontSize": "12px", "color": _TEXT_SEC,
                       "lineHeight": "1.7", "marginBottom": "16px"},
            ),
        ]),

        # Hidden radio để capture giá trị
        dcc.Store(id="ips-goal-store", data=None),

        # 4 choice cards
        html.Div([
            _choice_card("goal-preserve",
                         "fas fa-shield-alt", "Bảo toàn vốn",
                         "Giữ tiền an toàn, lợi nhuận kỳ vọng 6–9%/năm. Phù hợp nếu bạn sắp cần dùng tiền.",
                         icon_color="#10b981", value="preserve"),
            _choice_card("goal-income",
                         "fas fa-hand-holding-usd", "Thu nhập thụ động",
                         "Muốn nhận cổ tức đều đặn. Kỳ vọng dividend yield 6–10%/năm.",
                         icon_color=_AMBER, value="income"),
            _choice_card("goal-growth",
                         "fas fa-chart-line", "Tăng trưởng tài sản",
                         "Tích lũy dài hạn 3–5 năm+. Chấp nhận biến động để đổi lấy 12–18%/năm.",
                         icon_color=_BLUE, value="growth"),
            _choice_card("goal-speculate",
                         "fas fa-rocket", "Tối đa hóa lợi nhuận",
                         "Tận dụng xu hướng thị trường. Chấp nhận rủi ro cao, kỳ vọng 20%+/năm.",
                         icon_color=_RED, value="speculate"),
        ], style={
            "display": "grid", "gridTemplateColumns": "1fr 1fr",
            "gap": "10px", "marginBottom": "16px",
        }),

        # CFA insight box
        html.Div([
            html.I(className="fas fa-graduation-cap",
                   style={"color": _BLUE, "marginRight": "8px", "fontSize": "11px"}),
            html.Span("CFA L3 — Return Objective: ",
                      style={"color": _BLUE, "fontSize": "11px", "fontWeight": "700"}),
            html.Span(
                "Bước đầu tiên xây dựng Investment Policy Statement là xác định lợi nhuận "
                "tối thiểu bạn cần (required return) và tối đa bạn mong muốn (desired return). "
                "Khoảng cách giữa 2 con số này chính là room rủi ro của bạn.",
                style={"fontSize": "11px", "color": _TEXT_SEC, "lineHeight": "1.6"},
            ),
        ], style={
            "backgroundColor": "#071628",
            "border": f"1px solid #1d4ed8",
            "borderRadius": "6px", "padding": "10px 12px",
        }),

        # Error message
        html.Div(id="ips-step1-error", children="",
                 style={"color": _RED, "fontSize": "11px",
                        "marginTop": "8px", "minHeight": "16px"}),
    ])


# ─────────────────────────────────────────────────────────────────────────────
# STEP 2 — RISK TOLERANCE (Willingness + Ability)
# ─────────────────────────────────────────────────────────────────────────────
def _step2_layout():
    return html.Div(id="ips-step-2", children=[
        html.Div([
            html.Span("IPS · Bước 2 / 5 — Khẩu vị rủi ro", style={
                "fontSize": "10px", "color": _AMBER,
                "backgroundColor": "#1f1200",
                "border": "1px solid #92400e",
                "padding": "3px 8px", "borderRadius": "20px",
                "fontFamily": _FONT_MONO, "display": "inline-block",
                "marginBottom": "8px",
            }),
            html.H4("Bạn cảm thấy thế nào với biến động?",
                    style={"color": _TEXT_PRI, "fontFamily": _FONT_SORA,
                           "fontSize": "18px", "fontWeight": "700",
                           "marginBottom": "6px", "marginTop": "6px"}),
            html.P(
                "CFA L3 tách biệt 2 chiều rủi ro. "
                "Willingness = tâm lý. Ability = năng lực tài chính. "
                "Khi 2 chiều xung đột, hệ thống chọn chiều thấp hơn để bảo vệ bạn.",
                style={"fontSize": "12px", "color": _TEXT_SEC,
                       "lineHeight": "1.7", "marginBottom": "16px"},
            ),
        ]),

        dcc.Store(id="ips-will-store", data=None),

        # 2a. Willingness
        html.Div([
            html.Div([
                html.I(className="fas fa-brain",
                       style={"color": _PURPLE, "marginRight": "8px"}),
                html.Span("Willingness — Tâm lý rủi ro",
                          style={"color": _TEXT_PRI, "fontSize": "13px",
                                 "fontWeight": "700", "fontFamily": _FONT_SORA}),
            ], style={"marginBottom": "10px"}),
            html.P("Nếu danh mục giảm 20% trong vòng 1 tháng, bạn sẽ làm gì?",
                   style={"fontSize": "12px", "color": _TEXT_SEC,
                          "marginBottom": "10px"}),
            html.Div([
                _choice_card("will-panic",   "fas fa-times-circle",
                             "Bán hết ngay", "Không thể chịu đựng thêm",
                             icon_color=_RED, value="panic"),
                _choice_card("will-worry",   "fas fa-exclamation-triangle",
                             "Lo lắng, theo dõi", "Khó chịu nhưng chờ đợi",
                             icon_color=_AMBER, value="worry"),
                _choice_card("will-hold",    "fas fa-hand-paper",
                             "Giữ theo kế hoạch", "Tin vào chiến lược dài hạn",
                             icon_color=_BLUE, value="hold"),
                _choice_card("will-buy",     "fas fa-shopping-cart",
                             "Mua thêm vào đáy", "Cơ hội giải ngân thêm",
                             icon_color=_GREEN, value="buy"),
            ], style={
                "display": "grid", "gridTemplateColumns": "repeat(2, 1fr)",
                "gap": "8px",
            }),
        ], style={
            "backgroundColor": _BG_CARD2,
            "border": f"1px solid {_BORDER}",
            "borderRadius": "8px", "padding": "14px",
            "marginBottom": "12px",
        }),

        # 2b. Ability (financial)
        html.Div([
            html.Div([
                html.I(className="fas fa-wallet",
                       style={"color": _GREEN, "marginRight": "8px"}),
                html.Span("Ability — Khả năng tài chính chịu rủi ro",
                          style={"color": _TEXT_PRI, "fontSize": "13px",
                                 "fontWeight": "700", "fontFamily": _FONT_SORA}),
            ], style={"marginBottom": "12px"}),

            html.Div([
                html.Div([
                    html.Div("% tiết kiệm dành cho chứng khoán",
                             style={"fontSize": "12px", "color": _TEXT_SEC,
                                    "marginBottom": "6px"}),
                    dcc.Slider(
                        id="ips-pct-savings-slider",
                        min=5, max=80, step=5, value=30,
                        marks={5: "5%", 20: "20%", 40: "40%",
                               60: "60%", 80: "80%"},
                        tooltip={"placement": "top", "always_visible": True},
                        className="ips-slider",
                    ),
                ], style={"marginBottom": "20px"}),

                html.Div([
                    html.Div("Quỹ dự phòng khẩn cấp (số tháng chi phí)",
                             style={"fontSize": "12px", "color": _TEXT_SEC,
                                    "marginBottom": "6px"}),
                    dcc.Slider(
                        id="ips-emergency-slider",
                        min=0, max=12, step=1, value=4,
                        marks={0: "0", 2: "2 tháng", 4: "4", 6: "6 tháng", 12: "12"},
                        tooltip={"placement": "top", "always_visible": True},
                        className="ips-slider",
                    ),
                ]),
            ]),
        ], style={
            "backgroundColor": _BG_CARD2,
            "border": f"1px solid {_BORDER}",
            "borderRadius": "8px", "padding": "14px",
        }),

        html.Div(id="ips-step2-error", children="",
                 style={"color": _RED, "fontSize": "11px",
                        "marginTop": "8px", "minHeight": "16px"}),
    ])


# ─────────────────────────────────────────────────────────────────────────────
# STEP 3 — CONSTRAINTS (Time · Liquidity · Unique)
# ─────────────────────────────────────────────────────────────────────────────
def _step3_layout():
    return html.Div(id="ips-step-3", children=[
        html.Div([
            html.Span("IPS · Bước 3 / 5 — Ràng buộc đầu tư", style={
                "fontSize": "10px", "color": _PURPLE,
                "backgroundColor": "#1a0d2e",
                "border": "1px solid #6d28d9",
                "padding": "3px 8px", "borderRadius": "20px",
                "fontFamily": _FONT_MONO, "display": "inline-block",
                "marginBottom": "8px",
            }),
            html.H4("Thêm thông tin để cá nhân hóa",
                    style={"color": _TEXT_PRI, "fontFamily": _FONT_SORA,
                           "fontSize": "18px", "fontWeight": "700",
                           "marginBottom": "6px", "marginTop": "6px"}),
            html.P(
                "CFA L3 định nghĩa 5 ràng buộc: Time horizon · Tax · Liquidity · Legal · Unique. "
                "Đây là phiên bản đơn giản hoá cho thị trường Việt Nam.",
                style={"fontSize": "12px", "color": _TEXT_SEC,
                       "lineHeight": "1.7", "marginBottom": "16px"},
            ),
        ]),

        dcc.Store(id="ips-time-store", data="long"),
        dcc.Store(id="ips-liq-store",  data="low"),

        # Time Horizon
        html.Div([
            html.Div([
                html.I(className="fas fa-clock",
                       style={"color": _CYAN, "marginRight": "8px"}),
                html.Span("Time Horizon — Thời gian đầu tư",
                          style={"color": _TEXT_PRI, "fontSize": "13px",
                                 "fontWeight": "700", "fontFamily": _FONT_SORA}),
            ], style={"marginBottom": "10px"}),
            html.Div([
                _choice_card("time-short", "fas fa-bolt",
                             "Dưới 1 năm", "Ngắn hạn — cần tiền tương đối sớm",
                             icon_color=_RED, value="short"),
                _choice_card("time-mid",   "fas fa-calendar-alt",
                             "1 – 3 năm",  "Trung hạn — tích lũy có kế hoạch",
                             icon_color=_AMBER, value="mid"),
                _choice_card("time-long",  "fas fa-mountain",
                             "Trên 3 năm", "Dài hạn — đầu tư cho tương lai",
                             icon_color=_GREEN, value="long"),
            ], style={
                "display": "grid", "gridTemplateColumns": "repeat(3, 1fr)",
                "gap": "8px",
            }),
        ], style={
            "backgroundColor": _BG_CARD2,
            "border": f"1px solid {_BORDER}",
            "borderRadius": "8px", "padding": "14px",
            "marginBottom": "12px",
        }),

        # Liquidity
        html.Div([
            html.Div([
                html.I(className="fas fa-tint",
                       style={"color": _BLUE, "marginRight": "8px"}),
                html.Span("Liquidity — Nhu cầu thanh khoản",
                          style={"color": _TEXT_PRI, "fontSize": "13px",
                                 "fontWeight": "700", "fontFamily": _FONT_SORA}),
            ], style={"marginBottom": "10px"}),
            html.Div([
                _choice_card("liq-high",  "fas fa-fire",
                             "Cao", "Có thể cần rút tiền bất kỳ lúc nào",
                             icon_color=_RED, value="high"),
                _choice_card("liq-mid",   "fas fa-tachometer-alt",
                             "Trung bình", "Có thể cần tiền trong 6–12 tháng",
                             icon_color=_AMBER, value="mid"),
                _choice_card("liq-low",   "fas fa-anchor",
                             "Thấp", "Không cần rút trước ít nhất 1 năm",
                             icon_color=_GREEN, value="low"),
            ], style={
                "display": "grid", "gridTemplateColumns": "repeat(3, 1fr)",
                "gap": "8px",
            }),
        ], style={
            "backgroundColor": _BG_CARD2,
            "border": f"1px solid {_BORDER}",
            "borderRadius": "8px", "padding": "14px",
            "marginBottom": "12px",
        }),

        # Unique Circumstances
        html.Div([
            html.Div([
                html.I(className="fas fa-star",
                       style={"color": _AMBER, "marginRight": "8px"}),
                html.Span("Unique Circumstances — Đặc điểm riêng",
                          style={"color": _TEXT_PRI, "fontSize": "13px",
                                 "fontWeight": "700", "fontFamily": _FONT_SORA}),
            ], style={"marginBottom": "10px"}),
            html.Div([
                dbc.Checklist(
                    id="ips-unique-checklist",
                    options=[
                        {"label": "Tôi mới bắt đầu tìm hiểu về chứng khoán (F0)",
                         "value": "beginner"},
                        {"label": "Ưu tiên cổ phiếu trả cổ tức đều đặn",
                         "value": "prefer_dividend"},
                        {"label": "Tránh cổ phiếu ngân hàng / bất động sản",
                         "value": "avoid_bank_re"},
                        {"label": "Ưu tiên doanh nghiệp có quản trị tốt (ESG)",
                         "value": "prefer_esg"},
                    ],
                    value=["beginner"],
                    switch=True,
                    style={"fontSize": "13px", "color": _TEXT_SEC},
                ),
            ]),
        ], style={
            "backgroundColor": _BG_CARD2,
            "border": f"1px solid {_BORDER}",
            "borderRadius": "8px", "padding": "14px",
        }),

        html.Div(id="ips-step3-error", children="",
                 style={"color": _RED, "fontSize": "11px",
                        "marginTop": "8px", "minHeight": "16px"}),
    ])


# ─────────────────────────────────────────────────────────────────────────────
# STEP 4 — PROFILE PREVIEW + STRATEGY MAP (server-rendered từ callback)
# ─────────────────────────────────────────────────────────────────────────────
def _step4_layout():
    return html.Div(id="ips-step-4", children=[
        html.Div([
            html.Span("IPS · Bước 4 / 5 — Hồ sơ & Chiến lược", style={
                "fontSize": "10px", "color": _GREEN,
                "backgroundColor": "#071e12",
                "border": "1px solid #065f46",
                "padding": "3px 8px", "borderRadius": "20px",
                "fontFamily": _FONT_MONO, "display": "inline-block",
                "marginBottom": "8px",
            }),
            html.H4("Hồ sơ nhà đầu tư của bạn",
                    style={"color": _TEXT_PRI, "fontFamily": _FONT_SORA,
                           "fontSize": "18px", "fontWeight": "700",
                           "marginBottom": "6px", "marginTop": "6px"}),
            html.P(
                "Hệ thống đã tổng hợp IPS và gợi ý tổ hợp chiến lược tối ưu. "
                "Bạn có thể điều chỉnh trọng số trước khi xác nhận.",
                style={"fontSize": "12px", "color": _TEXT_SEC,
                       "lineHeight": "1.7", "marginBottom": "16px"},
            ),
        ]),

        # Nội dung được render động từ callback
        html.Div(id="ips-profile-preview",
                 style={"minHeight": "200px"}),
    ])


# ─────────────────────────────────────────────────────────────────────────────
# STEP 5 — CONFIRM & APPLY
# ─────────────────────────────────────────────────────────────────────────────
def _step5_layout():
    return html.Div(id="ips-step-5", children=[
        html.Div([
            html.Span("IPS · Bước 5 / 5 — Xác nhận", style={
                "fontSize": "10px", "color": _CYAN,
                "backgroundColor": "#071628",
                "border": "1px solid #0e4f7a",
                "padding": "3px 8px", "borderRadius": "20px",
                "fontFamily": _FONT_MONO, "display": "inline-block",
                "marginBottom": "8px",
            }),
            html.H4("Sẵn sàng bắt đầu!",
                    style={"color": _TEXT_PRI, "fontFamily": _FONT_SORA,
                           "fontSize": "18px", "fontWeight": "700",
                           "marginBottom": "6px", "marginTop": "6px"}),
        ]),

        # Summary box — render từ callback
        html.Div(id="ips-final-summary"),

        # Tùy chọn áp dụng filter
        html.Div([
            html.Div([
                html.I(className="fas fa-filter",
                       style={"color": _BLUE, "marginRight": "8px"}),
                html.Span("Tùy chọn áp dụng",
                          style={"color": _TEXT_PRI, "fontSize": "13px",
                                 "fontWeight": "700"}),
            ], style={"marginBottom": "10px"}),
            dbc.Checklist(
                id="ips-apply-options",
                options=[
                    {"label": "Tự động áp dụng bộ lọc IPS vào Screener ngay bây giờ",
                     "value": "apply_filters"},
                    {"label": "Hiển thị giải thích đơn giản bên cạnh mỗi chỉ số (Beginner mode)",
                     "value": "beginner_tooltips"},
                    {"label": "Nhận gợi ý cổ phiếu hàng tuần phù hợp với IPS",
                     "value": "weekly_suggestions"},
                ],
                value=["apply_filters", "beginner_tooltips"],
                switch=True,
                style={"fontSize": "13px", "color": _TEXT_SEC},
            ),
        ], style={
            "backgroundColor": _BG_CARD2,
            "border": f"1px solid {_BORDER}",
            "borderRadius": "8px", "padding": "14px",
            "marginTop": "14px", "marginBottom": "14px",
        }),

        # Disclaimer
        html.Div([
            html.I(className="fas fa-exclamation-triangle",
                   style={"color": _AMBER, "marginRight": "6px",
                          "fontSize": "11px"}),
            html.Span(
                "Toàn bộ gợi ý chỉ mang tính tham khảo, không phải khuyến nghị mua/bán. "
                "Nhà đầu tư tự chịu trách nhiệm với quyết định của mình.",
                style={"fontSize": "11px", "color": _TEXT_MUT, "lineHeight": "1.6"},
            ),
        ], style={
            "backgroundColor": "#0c0a00",
            "border": "1px solid #92400e",
            "borderRadius": "6px", "padding": "10px 12px",
        }),

        html.Div(id="ips-apply-status", children="",
                 style={"fontSize": "12px", "color": _GREEN,
                        "marginTop": "10px", "minHeight": "20px"}),
    ])


# ─────────────────────────────────────────────────────────────────────────────
# NAVIGATION FOOTER (Prev / Next / Finish)
# ─────────────────────────────────────────────────────────────────────────────
def _wizard_footer():
    return html.Div([
        dbc.Button(
            [html.I(className="fas fa-arrow-left", style={"marginRight": "6px"}),
             "Quay lại"],
            id="ips-btn-prev",
            size="sm",
            style={
                "backgroundColor": _BG_CARD2,
                "border": f"1px solid {_BORDER2}",
                "color": _TEXT_SEC,
                "borderRadius": "6px",
                "fontFamily": _FONT_INTER,
                "fontSize": "12px",
            },
        ),
        # Step counter text
        html.Span(id="ips-step-counter", children="Bước 1 / 5",
                  style={"fontSize": "12px", "color": _TEXT_MUT,
                         "fontFamily": _FONT_MONO}),

        dbc.Button(
            ["Tiếp theo ",
             html.I(className="fas fa-arrow-right", style={"marginLeft": "6px"})],
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
            },
        ),
    ], style={
        "display": "flex", "justifyContent": "space-between",
        "alignItems": "center", "paddingTop": "16px",
        "borderTop": f"1px solid {_BORDER}",
        "marginTop": "8px",
    })


# ─────────────────────────────────────────────────────────────────────────────
# MAIN EXPORT: create_ips_wizard_modal()
# ─────────────────────────────────────────────────────────────────────────────
def create_ips_wizard_modal():
    """
    Trả về toàn bộ IPS Wizard dưới dạng dbc.Modal.
    Gọi hàm này trong main.py hoặc layout chính và append vào app.layout.

    Các Stores cần có trong layout (đã khai báo trong sidebar.py):
        - investor-profile-store  (localStorage)
        - profile-setup-done      (localStorage)
    """
    return dbc.Modal(
        id="ips-wizard-modal",
        size="lg",
        centered=True,
        scrollable=True,
        backdrop="static",          # không đóng khi click ngoài → buộc hoàn thành
        keyboard=False,
        is_open=False,
        style={"fontFamily": _FONT_INTER},
        children=[
            dbc.ModalHeader(
                children=[
                    html.Div([
                        html.I(className="fas fa-user-cog",
                               style={"color": _BLUE, "marginRight": "10px",
                                      "fontSize": "16px"}),
                        html.Span("Thiết lập hồ sơ nhà đầu tư",
                                  style={"color": _TEXT_PRI, "fontSize": "15px",
                                         "fontWeight": "700",
                                         "fontFamily": _FONT_SORA}),
                        html.Span(" — Investor Policy Statement",
                                  style={"color": _TEXT_MUT, "fontSize": "12px",
                                         "fontFamily": _FONT_MONO,
                                         "marginLeft": "6px"}),
                    ]),
                ],
                close_button=True,
                style={"backgroundColor": _BG_CARD,
                       "borderBottom": f"1px solid {_BORDER}"},
            ),
            dbc.ModalBody(
                style={"backgroundColor": _BG_MODAL, "padding": "20px 24px"},
                children=[
                    # Store trung tâm theo dõi step hiện tại
                    dcc.Store(id="ips-current-step", data=1),

                    # Progress bar
                    _progress_bar(),

                    # Tất cả 5 step containers — hiện/ẩn qua callback
                    html.Div(id="ips-steps-container", children=[
                        _step1_layout(),
                        _step2_layout(),
                        _step3_layout(),
                        _step4_layout(),
                        _step5_layout(),
                    ]),

                    # Footer navigation
                    _wizard_footer(),
                ],
            ),
        ],
    )