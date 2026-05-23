# src/pages/onboarding.py
# ─────────────────────────────────────────────────────────────────────────────
# IPS Onboarding — UI dùng class names từ onboarding_wizard.css
# CSS được load tự động từ assets/onboarding_wizard.css
# ─────────────────────────────────────────────────────────────────────────────

from dash import html, dcc
import dash_bootstrap_components as dbc

# ── Alias màu cho callbacks (giữ nguyên để không vỡ investor_profile_callbacks.py)
_BG_PAGE  = "#040810"
_BG_CARD  = "#0d1d36"
_BG_CARD2 = "#112340"
_BORDER   = "#1a3a60"
_TEXT_PRI = "#e8f4ff"
_TEXT_SEC = "#7aafcc"
_TEXT_MUT = "#3d6a8a"
_BLUE     = "#0090ff"
_GREEN    = "#00e676"
_AMBER    = "#ffb703"
_RED      = "#ff3d57"
_PURPLE   = "#8b5cf6"
_CYAN     = "#00e5ff"
_ACCENT   = "#00e5ff"
_ACCENT2  = "#0090ff"

_FONT_DISPLAY = "'Be Vietnam Pro', 'DM Sans', sans-serif"
_FONT_BODY    = "'DM Sans', sans-serif"
_FONT_MONO    = "'DM Mono', monospace"

# Alias cũ để không vỡ code callbacks
_FONT_SORA  = _FONT_DISPLAY
_FONT_INTER = _FONT_BODY


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _step_header(step_num, title, subtitle):
    """Header chuẩn dùng class CSS từ onboarding_wizard.css."""
    return html.Div([
        html.Div([
            html.Span(f"Bước {step_num:02d} / 05", className="vss-step-num"),
            html.Div(className="vss-step-line"),
        ], className="vss-step-eyebrow"),
        html.H4(title, className="vss-step-title"),
        html.P(subtitle, className="vss-step-desc"),
    ])


def _choice_card(group, value, icon, label, sub):
    """Card lựa chọn — dùng class vss-choice-card, toggle class 'selected' qua callback."""
    return html.Div(
        [
            # Check tick (hiện khi selected)
            html.Div("✓", className="vss-choice-check"),
            # Icon
            html.I(className=f"{icon} vss-choice-icon"),
            # Label + sub
            html.Div(label, className="vss-choice-label"),
            html.Div(sub,   className="vss-choice-sub"),
        ],
        id={"type": "ips-choice", "id": f"{group}-{value}"},
        n_clicks=0,
        className="vss-choice-card",
    )


def _hero_section():
    """Hero slideshow — giữ nguyên."""
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


# ─────────────────────────────────────────────────────────────────────────────
# STEPS
# ─────────────────────────────────────────────────────────────────────────────

def _step1():
    return html.Div(id="ips-step-1", children=[
        _step_header(1,
            "Mục tiêu Lợi nhuận (Return Objective)",
            "Xác định Required Return vs. Desired Return để định hình cấu trúc Core-Satellite của danh mục."),
        html.Div([
            _choice_card("goal", "preserve",  "fas fa-shield-alt",       "Bảo toàn Vốn",       "Duy trì sức mua, bù đắp lạm phát. Rủi ro tối thiểu."),
            _choice_card("goal", "income",    "fas fa-hand-holding-usd", "Tối ưu Dòng tiền",    "Tập trung Dividend Yield và dòng tiền đều đặn thay vì lãi vốn."),
            _choice_card("goal", "growth",    "fas fa-chart-line",       "Tăng trưởng Lãi vốn", "Tối đa hóa giá trị danh mục dài hạn, chấp nhận biến động."),
            _choice_card("goal", "speculate", "fas fa-rocket",           "Lợi nhuận Tuyệt đối", "Tìm kiếm Alpha qua chiến lược linh hoạt, không phụ thuộc benchmark."),
        ], className="vss-choice-grid"),
        html.Div(id="ips-step1-error", className="vss-error"),
    ])


def _step2():
    return html.Div(id="ips-step-2", children=[
        _step_header(2,
            "Khẩu vị Rủi ro (Risk Tolerance)",
            "Hành vi dự kiến của bạn khi danh mục vi phạm giới hạn Maximum Drawdown (VD: giảm 20% trong 1 tháng)."),
        html.Div([
            _choice_card("will", "panic", "fas fa-exclamation-circle",  "Bảo vệ vốn tuyệt đối", "Rất nhạy cảm. Hạ tỷ trọng ngay lập tức bằng mọi giá."),
            _choice_card("will", "worry", "fas fa-balance-scale-left",  "Kiểm soát chủ động",   "Lo lắng nhưng sẽ rà soát lại yếu tố cơ bản thay vì hoảng loạn."),
            _choice_card("will", "hold",  "fas fa-layer-group",          "Tuân thủ kỷ luật",     "Giữ nguyên cấu trúc danh mục nếu Thesis đầu tư chưa phá vỡ."),
            _choice_card("will", "buy",   "fas fa-chess-knight",         "Contrarian (Đi ngược)", "Sẵn sàng tái cấp vốn (Rebalance) vào tài sản đang bị định giá thấp."),
        ], className="vss-choice-grid"),
        html.Div(id="ips-step2-error", className="vss-error"),
    ])


def _step3():
    return html.Div(id="ips-step-3", children=[
        _step_header(3,
            "Ràng buộc Đầu tư (Constraints)",
            "Cung cấp các biến số TTLLU (Time, Liquidity, Unique) để hệ thống lượng hóa Năng lực tài chính (Ability Score)."),

        html.P("1. Đường cong đầu tư (Time Horizon)", className="vss-section-label"),
        html.Div([
            _choice_card("time", "short", "fas fa-hourglass-start", "Dưới 1 Năm",  "Ngắn hạn, chu kỳ quay vòng nhanh."),
            _choice_card("time", "mid",   "fas fa-hourglass-half",  "1 – 3 Năm",   "Trung hạn, đủ cho 1 chu kỳ kinh doanh."),
            _choice_card("time", "long",  "fas fa-hourglass-end",   "Trên 3 Năm",  "Dài hạn, tận dụng sức mạnh lãi kép."),
        ], className="vss-choice-grid cols-3", style={"marginBottom": "24px"}),

        html.P("2. Nhu cầu Thanh khoản (Liquidity)", className="vss-section-label"),
        html.Div([
            _choice_card("liq", "high", "fas fa-water",    "Biến động cao",      "Dễ phát sinh rút vốn (Cash outflow) đột xuất."),
            _choice_card("liq", "mid",  "fas fa-sliders-h","Dự phóng được",      "Có kế hoạch rút vốn một phần định kỳ."),
            _choice_card("liq", "low",  "fas fa-lock",     "Khóa vốn dài hạn",  "Vốn nhàn rỗi hoàn toàn, không áp lực."),
        ], className="vss-choice-grid cols-3", style={"marginBottom": "28px"}),

        html.P("3. Chỉ số Tài chính Cá nhân", className="vss-section-label"),

        html.Div([
            html.Div("Tỷ lệ thặng dư thu nhập (Savings Rate)",
                     style={"fontSize": "13px", "fontWeight": "600", "color": _TEXT_SEC, "marginBottom": "4px"}),
            html.Div("% thu nhập hàng tháng bạn có thể phân bổ vào vốn cổ phần.",
                     style={"fontSize": "11px", "color": _TEXT_MUT, "marginBottom": "12px"}),
            dcc.Slider(0, 100, 10, value=30, id="ips-pct-savings-slider",
                       tooltip={"placement": "bottom", "always_visible": True}),
        ], className="vss-slider-row"),

        html.Div([
            html.Div("Đệm thanh khoản (Emergency Buffer)",
                     style={"fontSize": "13px", "fontWeight": "600", "color": _TEXT_SEC, "marginBottom": "4px"}),
            html.Div("Số tháng chi phí sinh hoạt bạn đã dự phòng tiền mặt ở bên ngoài.",
                     style={"fontSize": "11px", "color": _TEXT_MUT, "marginBottom": "12px"}),
            dcc.Slider(0, 12, 1, value=4, id="ips-emergency-slider",
                       tooltip={"placement": "bottom", "always_visible": True}),
        ], className="vss-slider-row"),

        html.P("4. Ràng buộc đặc thù (Unique Circumstances)",
               className="vss-section-label", style={"marginTop": "20px"}),

        html.Div([
            dbc.Checklist(
                options=[
                    {"label": "Ưu tiên cấu trúc vốn an toàn & Lợi suất cổ tức cao", "value": "prefer_dividend"},
                    {"label": "Loại trừ nhóm ngành có rủi ro pháp lý/chu kỳ (BĐS, Ngân hàng)",  "value": "avoid_bank_re"},
                    {"label": "Kích hoạt giao diện giải thích thuật ngữ (Beginner/Tooltip Mode)", "value": "beginner"},
                ],
                value=["beginner"],
                id="ips-unique-checklist",
                inline=False,
            )
        ], className="vss-check-list-wrap"),

        html.Div(id="ips-step3-error", className="vss-error"),
    ])


def _step4():
    return html.Div(id="ips-step-4", children=[
        _step_header(4,
            "Hồ sơ Đầu tư (IPS Output)",
            "VSS đã tổng hợp hồ sơ IPS dựa trên lý thuyết hữu dụng. Xem lại các thông số kỹ thuật trước khi áp dụng."),
        html.Div(id="ips-profile-preview"),
    ])


def _step5():
    return html.Div(id="ips-step-5", children=[
        _step_header(5,
            "Xác nhận & Khởi tạo",
            "Lưu hồ sơ và đồng bộ hóa các bộ lọc định lượng vào VSS Smart Screener."),
        html.Div(id="ips-final-summary"),

        html.Div([
            dbc.Checklist(
                options=[{"label": "Tự động cấu hình Bộ Lọc Screener theo Hồ sơ IPS này", "value": "apply_filters"}],
                value=["apply_filters"],
                id="ips-apply-options",
                style={"color": _GREEN, "fontWeight": "600", "fontSize": "14px", "marginBottom": "16px"},
            ),
            html.Div([
                html.I(className="fas fa-info-circle",
                       style={"color": _BLUE, "marginRight": "8px", "fontSize": "12px"}),
                html.Span("Toàn bộ gợi ý chỉ mang tính tham khảo học thuật dựa trên CFA Framework, không phải khuyến nghị mua/bán.",
                          style={"fontSize": "12px", "color": _TEXT_SEC}),
            ], style={
                "backgroundColor": "rgba(0,144,255,0.08)",
                "border": "1px solid rgba(0,144,255,0.2)",
                "borderRadius": "8px", "padding": "12px 16px",
            }),
        ], style={"marginTop": "24px", "paddingTop": "24px",
                  "borderTop": f"1px dashed {_BORDER}"}),

        html.Div(id="ips-apply-status",
                 style={"fontSize": "13px", "minHeight": "24px", "marginTop": "16px"}),
    ])


# ─────────────────────────────────────────────────────────────────────────────
# MAIN LAYOUT
# ─────────────────────────────────────────────────────────────────────────────
layout = html.Div(
    id="ips-onboarding-wrapper",
    children=[
        # ── Hero Slideshow ───────────────────────────────────────────────────
        _hero_section(),

        # ── Wizard ──────────────────────────────────────────────────────────
        html.Div(className="vss-page", children=[

            # Logo bar
            html.Div([
                html.Div("📈", className="vss-logo-icon"),
                html.Div("VSS Smart Screener", className="vss-logo-name"),
            ], className="vss-logo-bar"),

            html.P(
                "Trước khi bắt đầu, hãy để VSS hiểu rõ hơn về bạn — chỉ mất 2 phút để thiết lập hồ sơ đầu tư cá nhân.",
                className="vss-logo-tagline",
            ),

            # Progress rail (được render bởi callback render_step_visibility)
            html.Div(id="ips-progress-bar", className="vss-progress-rail",
                     style={"marginBottom": "32px"}),

            # Wizard card
            html.Div(className="vss-wizard-card", children=[

                # Body — chứa 5 bước
                html.Div(className="vss-wizard-body", children=[
                    _step1(), _step2(), _step3(), _step4(), _step5(),

                    # dcc.Store
                    dcc.Store(id="ips-current-step", data=1),
                    dcc.Store(id="ips-goal-store",   data=None),
                    dcc.Store(id="ips-will-store",   data=None),
                    dcc.Store(id="ips-time-store",   data=None),
                    dcc.Store(id="ips-liq-store",    data=None),
                ]),

                # Footer — nút điều hướng
                html.Div(className="vss-wizard-footer", children=[
                    dbc.Button(
                        [html.I(className="fas fa-arrow-left",
                                style={"marginRight": "8px"}), "Quay lại"],
                        id="ips-btn-prev",
                        className="vss-btn-ghost",
                    ),
                    html.Span("Bước 1–3 / 5", id="ips-step-counter",
                              className="vss-step-counter"),
                    dbc.Button(
                        ["Tiếp tục ",
                         html.I(className="fas fa-arrow-right",
                                style={"marginLeft": "8px"})],
                        id="ips-btn-next",
                        className="vss-btn-primary",
                    ),
                ]),
            ]),

            # Skip + footer note
            html.Div([
                html.Span(
                    "Bỏ qua thiết lập, truy cập toàn thị trường",
                    id="btn-skip-onboarding", n_clicks=0,
                    style={
                        "color": _TEXT_MUT, "fontSize": "13px", "cursor": "pointer",
                        "textDecoration": "underline", "textUnderlineOffset": "4px",
                        "fontFamily": _FONT_BODY,
                    }
                )
            ], style={"textAlign": "center", "marginTop": "28px"}),

            html.P(
                "🔒 Dữ liệu hồ sơ được mã hóa và lưu trữ cục bộ trên thiết bị của bạn.",
                className="vss-footer-note",
            ),
        ]),

        # ── FAQ ─────────────────────────────────────────────────────────────
        html.Div([
            html.Div([
                html.H2(["FAQ", html.Span(".", style={"color": _ACCENT2})],
                        style={
                            "fontFamily": _FONT_DISPLAY, "fontWeight": "800",
                            "fontSize": "72px", "lineHeight": "0.82",
                            "letterSpacing": "-0.04em", "color": _TEXT_PRI, "margin": "0"
                        }),
                html.P("Giải đáp nhanh gọn các thắc mắc trước khi bạn bắt đầu hành trình đầu tư.",
                       style={"color": _TEXT_SEC, "fontSize": "14px",
                              "maxWidth": "250px", "marginTop": "24px", "lineHeight": "1.55"}),
            ], style={"flex": "0 0 320px", "marginBottom": "40px"}),

            html.Div([
                *[html.Div([
                    html.Button([
                        html.Span(f"0{i}", style={"fontFamily": "monospace", "fontSize": "11px",
                                                   "color": _TEXT_MUT, "letterSpacing": "0.14em",
                                                   "width": "40px", "textAlign": "left"}),
                        html.Span(q, style={"fontFamily": _FONT_DISPLAY, "fontWeight": "700",
                                            "fontSize": "22px", "color": _TEXT_PRI, "flex": "1",
                                            "textAlign": "left", "letterSpacing": "-0.01em"}),
                        html.Span("+" if i > 1 else "×", id=f"faq-icon-{i}",
                                  style={"fontSize": "28px",
                                         "color": _ACCENT2 if i == 1 else _TEXT_MUT,
                                         "lineHeight": "1"}),
                    ], id=f"faq-btn-{i}", n_clicks=0,
                       style={"width": "100%", "display": "flex", "alignItems": "baseline",
                              "background": "transparent", "border": "none",
                              "cursor": "pointer", "padding": "0"}),
                    html.Div(a, id=f"faq-content-{i}",
                             style={"marginLeft": "40px", "marginTop": "16px",
                                    "fontSize": "15px", "color": _TEXT_SEC,
                                    "lineHeight": "1.6", "maxWidth": "620px",
                                    "display": "block" if i == 1 else "none"}),
                ], style={"borderBottom": f"1px solid {_BORDER}", "padding": "32px 0"})
                for i, q, a in [
                    (1, "Vietcap Smart Screener (VSS) là gì?",
                     "VSS là nền tảng Robo-Advisor kết hợp lọc cổ phiếu định lượng. Không chỉ giúp bạn tìm ra cổ phiếu tốt theo dữ liệu thực tế, VSS còn đóng vai trò như một Cố vấn Tài chính: Gợi ý cách đi tiền, quản trị rủi ro và 'cấp cứu' danh mục khi thị trường biến động..."),
                    (2, "Điểm xếp hạng VGM có ý nghĩa gì?",
                     "Đây là hệ thống đánh giá độc quyền qua 3 trụ cột: Value (Định giá), Growth (Tăng trưởng) và Momentum (Động lượng). Điểm VGM tổng hợp giúp bạn nhanh chóng nhận diện cổ phiếu nào đang được thị trường đánh giá cao về cả tiềm năng tăng trưởng lẫn định giá hợp lý, từ đó tối ưu hóa danh mục đầu tư của mình."),
                    (3, "Tôi có vốn ít (10-50 triệu) có dùng được không?",
                     "Chắc chắn có! Nhập số tiền vào ô NAV, hệ thống sẽ ẩn các mã quá đắt, đồng thời Trợ lý AI sẽ đề xuất chính xác số lượng lô cổ phiếu bạn nên mua để tối ưu hóa rủi ro."),
                    (4, "Trợ lý VinanceAI có thể làm gì?",
                     "Hãy mở VinanceAI (Icon góc phải) khi đang xem một cổ phiếu. Bot sẽ lập tức đọc dữ liệu thị trường và phân tích cơ hội/rủi ro cho riêng mã đó như một Broker thực thụ."),
                    (5, "Tính năng 'Danh mục' khác gì bảng điện?",
                     "Khác biệt ở chức năng 'Phòng khám danh mục'. VSS không chỉ hiển thị Lãi/Lỗ mà còn dự báo kịch bản sập hầm, đo lường tỷ lệ Margin và chỉ định nên Bán/Giữ mã nào để cứu tài khoản."),
                    (6, "Có thể tự tạo bộ lọc cá nhân không?",
                     "Hoàn toàn được. Ở tab Chiến lược, bạn có thể chọn các mẫu có sẵn (CANSLIM, Tích sản...) hoặc tự kết hợp các chỉ số cơ bản/kỹ thuật để tạo nên 'chén thánh' của riêng mình."),
                ]],
            ], style={"flex": "1", "borderTop": f"1px solid {_BORDER}"}),

        ], style={
            "display": "flex", "flexWrap": "wrap", "gap": "60px",
            "justifyContent": "space-between", "width": "100%",
            "maxWidth": "1200px", "margin": "120px auto 60px auto",
            "padding": "0 40px", "alignItems": "flex-start", "boxSizing": "border-box",
        }),
    ]
)