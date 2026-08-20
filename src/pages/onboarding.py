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
_BLUE     = "#0057D9"
_GREEN    = "#00e676"
_AMBER    = "#ffb703"
_RED      = "#ff3d57"
_PURPLE   = "#8b5cf6"
_CYAN     = "#1E88E5"
_ACCENT   = "#1E88E5"
_ACCENT2  = "#0057D9"

_FONT_DISPLAY = "var(--font-display)"  # trước: 'Be Vietnam Pro' (đảo font riêng) -> đồng bộ với toàn app
_FONT_BODY    = "var(--font-ui)"       # trước: 'DM Sans'
_FONT_MONO    = "var(--font-data)"     # trước: 'DM Mono'

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
            html.Span(f"Bước {step_num:02d} / 05", className="fss-step-num"),
            html.Div(className="fss-step-line"),
        ], className="fss-step-eyebrow"),
        html.H4(title, className="fss-step-title"),
        html.P(subtitle, className="fss-step-desc"),
    ])


def _choice_card(group, value, icon, label, sub):
    """Card lựa chọn — dùng class fss-choice-card, toggle class 'selected' qua callback."""
    return html.Div(
        [
            # Check tick (hiện khi selected)
            html.Div("✓", className="fss-choice-check"),
            # Icon
            html.I(className=f"{icon} fss-choice-icon"),
            # Label + sub
            html.Div(label, className="fss-choice-label"),
            html.Div(sub,   className="fss-choice-sub"),
        ],
        id={"type": "ips-choice", "id": f"{group}-{value}"},
        n_clicks=0,
        className="fss-choice-card",
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
            "Kỳ vọng & Mục tiêu Đầu tư",
            "Bạn muốn tiền của mình làm gì? Chọn phong cách sinh lời "
            "phù hợp nhất với hoàn cảnh hiện tại."),
        html.Div([
            _choice_card("goal", "preserve",
                "fas fa-shield-alt",
                "Bảo toàn & Phòng thủ",
                "Ưu tiên không mất vốn. Chấp nhận lợi nhuận thấp "
                "hơn để đổi lấy sự an toàn. Phù hợp khi sắp cần dùng tiền."),
            _choice_card("goal", "income",
                "fas fa-coins",
                "Thu nhập Cổ tức đều đặn",
                "Muốn nhận dòng tiền hàng năm từ cổ tức. "
                "Ưu tiên DN chia cổ tức 5–8%/năm, ổn định qua nhiều chu kỳ."),
            _choice_card("goal", "growth",
                "fas fa-chart-line",
                "Tăng trưởng Tài sản",
                "Mục tiêu tích lũy dài hạn 3–5 năm+. Chấp nhận "
                "biến động để đổi lấy tăng trưởng 15–25%/năm."),
            _choice_card("goal", "speculate",
                "fas fa-bolt",
                "Lướt sóng & Nắm bắt cơ hội",
                "Canh bảng điện thường xuyên. Tìm điểm bùng phát "
                "Volume, Breakout kỹ thuật. Chấp nhận rủi ro ngắn hạn cao."),
        ], className="fss-choice-grid"),
        html.Div(id="ips-step1-error", className="fss-error"),
    ])


def _step2():
    return html.Div(id="ips-step-2", children=[
        _step_header(2,
            "Phản ứng khi Thị trường Rung lắc",
            "VN-Index vừa giảm 50–70 điểm trong 1 tuần (tương đương "
            "khoảng -4%). Danh mục của bạn đang âm 8%. Bạn sẽ làm gì?"),
        html.Div([
            _choice_card("will", "panic",
                "fas fa-sign-out-alt",
                "Cắt lỗ, bảo toàn tiền mặt",
                "Bán ra ngay để dừng lỗ. Chờ thị trường ổn định "
                "rõ ràng mới tính tiếp. Bảo vệ vốn là ưu tiên số 1."),
            _choice_card("will", "worry",
                "fas fa-search",
                "Rà soát lại, không hành động vội",
                "Xem lại từng mã trong danh mục. Nếu cơ bản "
                "vẫn tốt thì giữ nguyên, chỉ cắt những mã yếu nhất."),
            _choice_card("will", "hold",
                "fas fa-hand-paper",
                "Giữ nguyên theo kế hoạch",
                "Đã xác định được mức giá mua hợp lý từ trước. "
                "Giảm ngắn hạn không thay đổi câu chuyện dài hạn — giữ."),
            _choice_card("will", "buy",
                "fas fa-cart-plus",
                "Bắt đáy, mua thêm",
                "Thị trường giảm = hàng tốt đang sale. Giải ngân "
                "thêm vào những mã đã nghiên cứu kỹ, trung bình giá xuống."),
        ], className="fss-choice-grid"),
        html.Div(id="ips-step2-error", className="fss-error"),
    ])


def _step3():
    return html.Div(id="ips-step-3", children=[
        _step_header(3,
            "Hoàn cảnh & Ràng buộc Cá nhân",
            "Thêm thông tin để FSS cá nhân hóa bộ lọc phù hợp "
            "với thực tế tài chính của bạn."),

        html.P("1. Đường cong đầu tư (Time Horizon)", className="fss-section-label"),
        html.Div([
            _choice_card("time", "short", "fas fa-hourglass-start", "Dưới 1 Năm",  "Ngắn hạn, chu kỳ quay vòng nhanh."),
            _choice_card("time", "mid",   "fas fa-hourglass-half",  "1 – 3 Năm",   "Trung hạn, đủ cho 1 chu kỳ kinh doanh."),
            _choice_card("time", "long",  "fas fa-hourglass-end",   "Trên 3 Năm",  "Dài hạn, tận dụng sức mạnh lãi kép."),
        ], className="fss-choice-grid cols-3", style={"marginBottom": "24px"}),

        html.P("2. Nhu cầu Thanh khoản (Liquidity)", className="fss-section-label"),
        html.Div([
            _choice_card("liq", "high", "fas fa-water",    "Biến động cao",      "Dễ phát sinh rút vốn (Cash outflow) đột xuất."),
            _choice_card("liq", "mid",  "fas fa-sliders-h","Dự phóng được",      "Có kế hoạch rút vốn một phần định kỳ."),
            _choice_card("liq", "low",  "fas fa-lock",     "Khóa vốn dài hạn",  "Vốn nhàn rỗi hoàn toàn, không áp lực."),
        ], className="fss-choice-grid cols-3", style={"marginBottom": "28px"}),

        html.P("3. Chỉ số Tài chính Cá nhân", className="fss-section-label"),

        html.Div([
            html.Div("Bạn tiết kiệm được bao nhiêu % thu nhập mỗi tháng?",
                     style={"fontSize": "13px", "fontWeight": "600", "color": _TEXT_SEC, "marginBottom": "4px"}),
            html.Div("Phần % này dành cho đầu tư chứng khoán — không tính tiền sinh hoạt.",
                     style={"fontSize": "11px", "color": _TEXT_MUT, "marginBottom": "12px"}),
            dcc.Slider(0, 100, 10, value=30, id="ips-pct-savings-slider",
                       tooltip={"placement": "bottom", "always_visible": True}),
        ], className="fss-slider-row"),

        html.Div([
            html.Div("Quỹ dự phòng khẩn cấp của bạn đủ mấy tháng chi tiêu?",
                     style={"fontSize": "13px", "fontWeight": "600", "color": _TEXT_SEC, "marginBottom": "4px"}),
            html.Div("Tiền gửi ngân hàng/tiết kiệm không liên quan đến tài khoản chứng khoán.",
                     style={"fontSize": "11px", "color": _TEXT_MUT, "marginBottom": "12px"}),
            dcc.Slider(0, 12, 1, value=4, id="ips-emergency-slider",
                       tooltip={"placement": "bottom", "always_visible": True}),
        ], className="fss-slider-row"),

        html.P("4. Tùy chỉnh thêm (không bắt buộc)",
            className="fss-section-label", style={"marginTop": "20px"}),

        html.Div([
            dbc.Checklist(
                options=[
                    {
                        "label": "Ưu tiên cổ phiếu trả cổ tức đều đặn (Dividend ≥ 5%/năm)",
                        "value": "prefer_dividend",
                    },
                    {
                        "label": "Chỉ lọc BĐS có dòng tiền sạch (Nợ/VCSH < 1, tiền mua trước tăng)",
                        "value": "safe_realestate",
                    },
                    {
                        "label": "Chỉ lọc Ngân hàng mang tính phòng thủ",
                        "value": "defensive_bank",
                    },
                    {
                        "label": "Hiển thị giải thích đơn giản bên cạnh các chỉ số (Chế độ mới bắt đầu)",
                        "value": "beginner",
                    },
                ],
                value=["beginner"],
                id="ips-unique-checklist",
                inline=False,
            )
        ], className="fss-check-list-wrap"),

        html.Div(id="ips-step3-error", className="fss-error"),
    ])


def _step4():
    return html.Div(id="ips-step-4", children=[
        _step_header(4,
            "Hồ sơ Nhà đầu tư của bạn",
            "FSS đã tổng hợp chiến lược phù hợp dựa trên câu trả lời của bạn. "
            "Xem lại ngay trước khi áp dụng vào Screener."),
        html.Div(id="ips-profile-preview"),
    ])


def _step5():
    return html.Div(id="ips-step-5", children=[
        _step_header(5,
            "Xác nhận & Bắt đầu",
            "Lưu hồ sơ và tự động cấu hình bộ lọc vào Screener. "
            "Bạn có thể điều chỉnh lại bất cứ lúc nào."),
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
                html.Span("Toàn bộ gợi ý chỉ mang tính tham khảo, không phải khuyến nghị mua/bán cụ thể. "
                        "Nhà đầu tư tự chịu trách nhiệm với quyết định của mình.",
                          style={"fontSize": "12px", "color": _TEXT_SEC}),
            ], style={
                "backgroundColor": "rgba(0, 87, 217,0.08)",
                "border": "1px solid rgba(0, 87, 217,0.2)",
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
        html.Div(className="fss-page", children=[

            # Logo bar
            html.Div([
                html.Div("📈", className="fss-logo-icon"),
                html.Div("FSS Smart Screener", className="fss-logo-name"),
            ], className="fss-logo-bar"),

            html.P(
                "Hệ thống lọc & chấm điểm cổ phiếu tự động — Ra quyết định trong 30 giây dựa trên 100% dữ liệu thực.",
                className="fss-logo-tagline",
                style={"fontWeight": "600"},
            ),
            html.P(
                "Trước khi bắt đầu, hãy để FSS hiểu rõ hơn về bạn — chỉ mất 2 phút để thiết lập hồ sơ đầu tư cá nhân.",
                className="fss-logo-tagline",
            ),

            # ── MISSION CARD (Trust Builder) ─────────────────────────────────────
            html.Div([
                html.Div([
                    html.Div([
                        html.I(className="fas fa-shield-alt",
                            style={"color": _GREEN, "fontSize": "18px",
                                    "marginRight": "10px", "flexShrink": "0"}),
                        html.Span("Sứ mệnh của FSS",
                                style={"fontWeight": "800", "color": _TEXT_PRI,
                                        "fontSize": "15px", "fontFamily": _FONT_DISPLAY}),
                    ], style={"display": "flex", "alignItems": "center",
                            "marginBottom": "10px"}),
                    html.P(
                        "Bảo vệ tài sản nhà đầu tư trước các rủi ro tiềm ẩn của thị trường. "
                        "FSS mang đến công cụ minh bạch giúp bạn loại bỏ tâm lý FOMO, "
                        "rà soát rủi ro và đầu tư bền vững hơn.",
                        style={"fontSize": "13px", "color": _TEXT_SEC,
                            "lineHeight": "1.7", "margin": "0 0 12px 0"},
                    ),
                    html.Div([
                        html.Div([
                            html.I(className="fas fa-shield",
                                style={"color": _GREEN, "marginRight": "8px",
                                        "fontSize": "12px"}),
                            html.Span("Phòng thủ chặt: Loại bỏ DN xào nấu sổ sách, "
                                    "lãi giả lỗ thật — dựa trên dòng tiền thực.",
                                    style={"fontSize": "12px", "color": _TEXT_SEC}),
                        ], style={"display": "flex", "alignItems": "flex-start",
                                "marginBottom": "6px"}),
                        html.Div([
                            html.I(className="fas fa-crosshairs",
                                style={"color": _CYAN, "marginRight": "8px",
                                        "fontSize": "12px"}),
                            html.Span("Tấn công chuẩn: Xác định thời điểm mua/bán tối ưu "
                                    "theo dòng tiền lớn và sức mạnh giá.",
                                    style={"fontSize": "12px", "color": _TEXT_SEC}),
                        ], style={"display": "flex", "alignItems": "flex-start"}),
                    ]),
                ], style={
                    "background": "linear-gradient(135deg, "
                                "rgba(0,230,118,0.06), rgba(30, 136, 229,0.04))",
                    "border": "1px solid rgba(0,230,118,0.18)",
                    "borderLeft": f"3px solid {_GREEN}",
                    "borderRadius": "10px",
                    "padding": "16px 20px",
                }),
            ], style={"marginBottom": "28px"}),

            # Progress rail (được render bởi callback render_step_visibility)
            html.Div(id="ips-progress-bar", className="fss-progress-rail",
                     style={"marginBottom": "32px"}),

            # Wizard card
            html.Div(id="fss-wizard-card", className="fss-wizard-card", children=[
                # Body — chứa 5 bước
                html.Div(className="fss-wizard-body", children=[
                    _step1(), _step2(), _step3(), _step4(), _step5(),
                    # dcc.Store
                    dcc.Store(id="ips-current-step", data=1),
                    dcc.Store(id="ips-goal-store",   data=None),
                    dcc.Store(id="ips-will-store",   data=None),
                    dcc.Store(id="ips-time-store",   data=None),
                    dcc.Store(id="ips-liq-store",    data=None),
                    dcc.Store(id="ips-scroll-store", data=None),
                ]),
                # Footer — nút điều hướng
                html.Div(className="fss-wizard-footer", children=[
                    dbc.Button(
                        [html.I(className="fas fa-arrow-left",
                                style={"marginRight": "8px"}), "Quay lại"],
                        id="ips-btn-prev",
                        className="fss-btn-ghost",
                    ),
                    html.Span("Bước 1–3 / 5", id="ips-step-counter",
                              className="fss-step-counter"),
                    dbc.Button(
                        ["Tiếp tục ",
                         html.I(className="fas fa-arrow-right",
                                style={"marginLeft": "8px"})],
                        id="ips-btn-next",
                        className="fss-btn-primary",
                    ),
                ]),
            ]),
# ── CONGRATULATION SCREEN (hiện sau khi submit xong bước 5) ─────
            html.Div(
                id="ips-congrats-screen",
                children=[
                    html.Span("🏆", className="fss-congrats-icon"),
                    html.Div("Hồ sơ đầu tư đã sẵn sàng!", className="fss-congrats-title"),
                    html.P(
                        "FSS đã phân tích xong khẩu vị rủi ro và mục tiêu của bạn. "
                        "Bộ lọc Screener đã được cấu hình tự động theo hồ sơ cá nhân.",
                        className="fss-congrats-subtitle",
                    ),
                    html.Div([
                        html.Div("Danh mục phù hợp hồ sơ của bạn",
                                 className="fss-congrats-match-label"),
                        html.Div(id="ips-congrats-match-text",
                                 className="fss-congrats-match-text",
                                 children="Đang tính toán..."),
                        html.Div("Dựa trên dòng tiền thực, lọc sạch rủi ro sổ sách.",
                                 className="fss-congrats-match-sub"),
                    ], className="fss-congrats-match-card"),
                    html.Div(className="fss-congrats-divider"),
                    html.Div([
                        dbc.Button(
                            [
                                html.I(className="fas fa-file-pdf",
                                       style={"marginRight": "8px"}),
                                "Tải báo cáo hồ sơ PDF",
                            ],
                            id="ips-btn-download-pdf",
                            className="fss-btn-primary",
                            style={"fontSize": "14px", "padding": "13px 32px",
                                   "border": "none"},
                            n_clicks=0,
                        ),
                        dcc.Download(id="ips-pdf-download"),
                        html.Br(),
                        html.Button(
                            "Bỏ qua, vào Screener ngay →",
                            id="ips-congrats-enter-btn",
                            n_clicks=0,
                            style={
                                "background": "transparent", "border": "none",
                                "color": "#4d7a9a", "fontSize": "13px",
                                "cursor": "pointer", "marginTop": "10px",
                                "textDecoration": "underline",
                                "textUnderlineOffset": "4px",
                            },
                        ),
                    ], style={"marginBottom": "16px", "display": "flex",
                              "flexDirection": "column", "alignItems": "center"}),
                    html.P(
                        "Khách thường chỉ xem được 3 mã đầu tiên. "
                        "VIP nhận toàn bộ danh sách + cảnh báo rủi ro Red Flag.",
                        className="fss-congrats-match-sub",
                        style={"textAlign": "center"},
                    ),
                ],
            ),
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
                className="fss-footer-note",
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
                html.P("Giải đáp nhanh các thắc mắc trước khi bạn bắt đầu hành trình đầu tư.",
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
                    (1, "FinSmartScreener (FSS) là gì?",
                     "FSS là nền tảng Robo-Advisor kết hợp lọc cổ phiếu định lượng. Không chỉ giúp bạn tìm ra cổ phiếu tốt theo dữ liệu thực tế, FSS còn đóng vai trò như một Cố vấn Tài chính: Gợi ý cách đi tiền, quản trị rủi ro và 'cấp cứu' danh mục khi thị trường biến động..."),
                    (2, "Điểm xếp hạng VGM có ý nghĩa gì?",
                     "Đây là hệ thống đánh giá độc quyền qua 3 trụ cột: Value (Định giá), Growth (Tăng trưởng) và Momentum (Động lượng). Điểm VGM tổng hợp giúp bạn nhanh chóng nhận diện cổ phiếu nào đang được thị trường đánh giá cao về cả tiềm năng tăng trưởng lẫn định giá hợp lý, từ đó tối ưu hóa danh mục đầu tư của mình."),
                    (3, "Tôi có vốn ít (10-50 triệu) có dùng được không?",
                     "Chắc chắn có! Nhập số tiền vào ô NAV, hệ thống sẽ ẩn các mã quá đắt, đồng thời Trợ lý AI sẽ đề xuất chính xác số lượng lô cổ phiếu bạn nên mua để tối ưu hóa rủi ro."),
                    (4, "Trợ lý VinanceAI có thể làm gì?",
                     "Hãy mở VinanceAI (Icon góc phải) khi đang xem một cổ phiếu. Bot sẽ lập tức đọc dữ liệu thị trường và phân tích cơ hội/rủi ro cho riêng mã đó như một Broker thực thụ."),
                    (5, "Tính năng 'Danh mục' khác gì bảng điện?",
                     "Khác biệt ở chức năng 'Phòng khám danh mục'. FSS không chỉ hiển thị Lãi/Lỗ mà còn dự báo kịch bản sập hầm, đo lường tỷ lệ Margin và chỉ định nên Bán/Giữ mã nào để cứu tài khoản."),
                    (6, "Có thể tự tạo bộ lọc cá nhân không?",
                     "Hoàn toàn được. Ở tab Chiến lược, bạn có thể chọn các mẫu có sẵn (CANSLIM, Tích sản...) hoặc tự kết hợp các chỉ số cơ bản/kỹ thuật để tạo nên 'chén thánh' của riêng mình."),
                    (7, "FSS chọn lọc cổ phiếu dựa trên nguyên tắc nào?",
                     "FSS vận hành trên 2 nguyên tắc cốt lõi: (1) Phòng thủ chặt — tự động quét và loại bỏ các công ty xào nấu sổ sách, lãi giả lỗ thật, giúp bạn an tâm giải ngân; (2) Tấn công chuẩn — xác định thời điểm mua/bán tối ưu bằng cách theo dõi sát dòng tiền lớn và sức mạnh giá của từng cổ phiếu so với thị trường chung."),
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