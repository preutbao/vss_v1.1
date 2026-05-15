# src/pages/onboarding.py
# ─────────────────────────────────────────────────────────────────────────────
# IPS Onboarding — PREMIUM UI/UX UPGRADE
# Áp dụng phong cách Institutional Wealth Management
# ─────────────────────────────────────────────────────────────────────────────

from dash import html, dcc
import dash_bootstrap_components as dbc

# ── Color Palette (Premium Dark Mode) ────────────────────────────────────────
_BG_PAGE  = "#05080f"  # Nền trang sâu hơn
_BG_CARD  = "#0b1018"  # Nền card chính
_BG_CARD2 = "#111823"  # Nền các khối nhỏ bên trong
_BORDER   = "#1f2937"
_BORDER2  = "#374151"
_TEXT_PRI = "#f9fafb"  # Trắng sáng cho tiêu đề
_TEXT_SEC = "#9ca3af"  # Xám sáng cho mô tả
_TEXT_MUT = "#6b7280"  # Xám tối cho ghi chú
_BLUE     = "#3b82f6"
_GREEN    = "#10b981"
_AMBER    = "#f59e0b"
_RED      = "#ef4444"
_PURPLE   = "#8b5cf6"
_CYAN     = "#06b6d4"

_FONT_SORA  = "'Sora', 'Inter', sans-serif"
_FONT_INTER = "'Inter', sans-serif"
_FONT_MONO  = "'Roboto Mono', monospace"

# ─────────────────────────────────────────────────────────────────────────────
# COMPONENTS HELPER
# ─────────────────────────────────────────────────────────────────────────────

def _step_header(step_num, title, subtitle, color):
    """Tiêu đề chuẩn hóa cho mỗi bước với UI cao cấp."""
    return html.Div([
        html.Div([
            html.Span(f"BƯỚC {step_num:02d}", style={
                "fontFamily": _FONT_MONO, "fontSize": "11px", "fontWeight": "700",
                "color": color, "letterSpacing": "2px",
            }),
            html.Span(" / 05", style={
                "fontFamily": _FONT_MONO, "fontSize": "11px", "fontWeight": "600",
                "color": _TEXT_MUT, "letterSpacing": "2px",
            }),
        ], style={"marginBottom": "12px", "display": "flex", "alignItems": "center"}),
        
        html.H4(title, style={
            "color": _TEXT_PRI, "fontFamily": _FONT_SORA,
            "fontSize": "24px", "fontWeight": "700", "marginBottom": "8px",
            "letterSpacing": "-0.5px"
        }),
        html.P(subtitle, style={
            "fontSize": "14px", "color": _TEXT_SEC, "marginBottom": "28px",
            "lineHeight": "1.6"
        }),
    ])

def _choice_card(group, value, icon, label, sub):
    """Card lựa chọn với tỷ lệ đẹp hơn và hiệu ứng hover chìm (thông qua class)."""
    color_map = {"goal": _BLUE, "will": _AMBER, "time": _GREEN, "liq": _PURPLE}
    c = color_map.get(group, _BLUE)
    
    return html.Div(
        [
            html.Div([
                html.I(className=icon, style={"fontSize": "22px", "color": c}),
            ], style={
                "width": "48px", "height": "48px", "borderRadius": "12px",
                "backgroundColor": f"{c}15", "display": "flex",
                "alignItems": "center", "justifyContent": "center",
                "marginBottom": "16px", "border": f"1px solid {c}30"
            }),
            
            html.Div(label, style={
                "fontSize": "15px", "fontWeight": "700",
                "color": _TEXT_PRI, "marginBottom": "6px",
                "fontFamily": _FONT_SORA,
            }),
            html.Div(sub, style={
                "fontSize": "12px", "color": _TEXT_SEC, "lineHeight": "1.5"
            }),
        ],
        id={"type": "ips-choice", "id": f"{group}-{value}"},
        n_clicks=0,
        className="ips-choice-card",
        style={
            "padding": "24px 20px",
            "border": f"1px solid {_BORDER}",
            "borderRadius": "16px",
            "backgroundColor": _BG_CARD2,
            "cursor": "pointer",
            "transition": "all 0.2s ease-in-out",
            "height": "100%",
            "display": "flex", "flexDirection": "column"
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

def _slider_container(title, desc, slider_component):
    """Gói các slider vào một khối UI sạch sẽ."""
    return html.Div([
        html.Div([
            html.Div(title, style={"fontSize": "14px", "fontWeight": "600", "color": _TEXT_PRI, "marginBottom": "4px"}),
            html.Div(desc, style={"fontSize": "12px", "color": _TEXT_MUT}),
        ], style={"marginBottom": "16px"}),
        slider_component,
    ], style={
        "padding": "20px", "backgroundColor": _BG_CARD2,
        "borderRadius": "12px", "border": f"1px solid {_BORDER}",
        "marginBottom": "16px"
    })

# ─────────────────────────────────────────────────────────────────────────────
# STEPS LAYOUT
# ─────────────────────────────────────────────────────────────────────────────

def _step1():
    return html.Div(id="ips-step-1", children=[
        _step_header(1, "Mục tiêu Lợi nhuận (Return Objective)", 
                     "Xác định Required Return vs. Desired Return để định hình cấu trúc Core-Satellite của danh mục.", _BLUE),
        html.Div([
            _choice_card("goal", "preserve", "fas fa-shield-alt", "Bảo toàn Vốn", "Duy trì sức mua, bù đắp lạm phát. Rủi ro tối thiểu."),
            _choice_card("goal", "income", "fas fa-hand-holding-usd", "Tối ưu Dòng tiền", "Tập trung Dividend Yield và dòng tiền đều đặn thay vì lãi vốn."),
            _choice_card("goal", "growth", "fas fa-chart-line", "Tăng trưởng Lãi vốn", "Tối đa hóa giá trị danh mục dài hạn, chấp nhận biến động."),
            _choice_card("goal", "speculate", "fas fa-chart-network", "Lợi nhuận Tuyệt đối", "Tìm kiếm Alpha qua chiến lược linh hoạt, không phụ thuộc benchmark."),
        ], style={"display": "grid", "gridTemplateColumns": "1fr 1fr", "gap": "16px", "marginBottom": "12px"}),
        html.Div(id="ips-step1-error", style={"color": _RED, "fontSize": "13px", "minHeight": "20px", "marginTop": "8px"}),
    ])

def _step2():
    return html.Div(id="ips-step-2", children=[
        _step_header(2, "Khẩu vị Rủi ro (Risk Tolerance)", 
                     "Hành vi dự kiến của bạn khi danh mục vi phạm giới hạn Maximum Drawdown (VD: giảm 20% trong 1 tháng).", _AMBER),
        html.Div([
            _choice_card("will", "panic", "fas fa-exclamation-circle", "Bảo vệ vốn tuyệt đối", "Rất nhạy cảm. Hạ tỷ trọng ngay lập tức bằng mọi giá."),
            _choice_card("will", "worry", "fas fa-balance-scale-left", "Kiểm soát chủ động", "Lo lắng nhưng sẽ rà soát lại yếu tố cơ bản thay vì hoảng loạn."),
            _choice_card("will", "hold", "fas fa-layer-group", "Tuân thủ kỷ luật", "Giữ nguyên cấu trúc danh mục nếu Thesis đầu tư chưa phá vỡ."),
            _choice_card("will", "buy", "fas fa-chess-knight", "Contrarian (Đi ngược)", "Sẵn sàng tái cấp vốn (Rebalance) vào tài sản đang bị định giá thấp."),
        ], style={"display": "grid", "gridTemplateColumns": "1fr 1fr", "gap": "16px", "marginBottom": "12px"}),
        html.Div(id="ips-step2-error", style={"color": _RED, "fontSize": "13px", "minHeight": "20px", "marginTop": "8px"}),
    ])

def _step3():
    return html.Div(id="ips-step-3", children=[
        _step_header(3, "Ràng buộc Đầu tư (Constraints)", 
                     "Cung cấp các biến số TTLLU (Time, Liquidity, Unique) để hệ thống lượng hóa Năng lực tài chính (Ability Score).", _GREEN),

        html.Div("1. Đường cong đầu tư (Time Horizon)", style={"fontSize": "13px", "color": _TEXT_PRI, "fontWeight": "700", "marginBottom": "12px"}),
        html.Div([
            _choice_card("time", "short", "fas fa-hourglass-start", "Dưới 1 Năm", "Ngắn hạn, chu kỳ quay vòng nhanh."),
            _choice_card("time", "mid", "fas fa-hourglass-half", "1 – 3 Năm", "Trung hạn, đủ cho 1 chu kỳ kinh doanh."),
            _choice_card("time", "long", "fas fa-hourglass-end", "Trên 3 Năm", "Dài hạn, tận dụng sức mạnh lãi kép."),
        ], style={"display": "grid", "gridTemplateColumns": "1fr 1fr 1fr", "gap": "12px", "marginBottom": "24px"}),

        html.Div("2. Nhu cầu Thanh khoản (Liquidity)", style={"fontSize": "13px", "color": _TEXT_PRI, "fontWeight": "700", "marginBottom": "12px"}),
        html.Div([
            _choice_card("liq", "high", "fas fa-water", "Biến động cao", "Dễ phát sinh rút vốn (Cash outflow) đột xuất."),
            _choice_card("liq", "mid", "fas fa-sliders-h", "Dự phóng được", "Có kế hoạch rút vốn một phần định kỳ."),
            _choice_card("liq", "low", "fas fa-lock", "Khóa vốn dài hạn", "Vốn nhàn rỗi hoàn toàn, không áp lực."),
        ], style={"display": "grid", "gridTemplateColumns": "1fr 1fr 1fr", "gap": "12px", "marginBottom": "32px"}),

        html.Div("3. Chỉ số Tài chính Cá nhân", style={"fontSize": "13px", "color": _TEXT_PRI, "fontWeight": "700", "marginBottom": "12px"}),
        _slider_container(
            "Tỷ lệ thặng dư thu nhập (Savings Rate)", 
            "% thu nhập hàng tháng bạn có thể phân bổ vào vốn cổ phần.",
            dcc.Slider(0, 100, 10, value=30, id="ips-pct-savings-slider", className="custom-slider", tooltip={"placement": "bottom", "always_visible": True})
        ),
        _slider_container(
            "Đệm thanh khoản (Emergency Buffer)", 
            "Số tháng chi phí sinh hoạt bạn đã dự phòng tiền mặt ở bên ngoài.",
            dcc.Slider(0, 12, 1, value=4, id="ips-emergency-slider", className="custom-slider", tooltip={"placement": "bottom", "always_visible": True})
        ),

        html.Div("4. Ràng buộc đặc thù (Unique Circumstances)", style={"fontSize": "13px", "color": _TEXT_PRI, "fontWeight": "700", "marginBottom": "12px", "marginTop": "24px"}),
        html.Div([
            dbc.Checklist(
                options=[
                    {"label": "Ưu tiên cấu trúc vốn an toàn & Lợi suất cổ tức cao", "value": "prefer_dividend"},
                    {"label": "Loại trừ nhóm ngành có rủi ro pháp lý/chu kỳ (BĐS, Ngân hàng)", "value": "avoid_bank_re"},
                    {"label": "Kích hoạt giao diện giải thích thuật ngữ (Beginner/Tooltip Mode)", "value": "beginner"},
                ],
                value=["beginner"],
                id="ips-unique-checklist",
                inline=False,
                className="custom-checklist",
                style={"color": _TEXT_PRI, "fontSize": "14px", "lineHeight": "2.5"},
            )
        ], style={"padding": "16px 20px", "backgroundColor": _BG_CARD2, "borderRadius": "12px", "border": f"1px solid {_BORDER}"}),

        html.Div(id="ips-step3-error", style={"color": _RED, "fontSize": "13px", "minHeight": "20px", "marginTop": "12px"}),
    ])

def _step4():
    return html.Div(id="ips-step-4", children=[
        _step_header(4, "Hồ sơ Đầu tư (IPS Output)", 
                     "VSS đã tổng hợp hồ sơ IPS dựa trên lý thuyết hữu dụng. Xem lại các thông số kỹ thuật trước khi áp dụng.", _PURPLE),
        html.Div(id="ips-profile-preview"),
    ])

def _step5():
    return html.Div(id="ips-step-5", children=[
        _step_header(5, "Xác nhận & Khởi tạo", 
                     "Lưu hồ sơ và đồng bộ hóa các bộ lọc định lượng vào VSS Smart Screener.", _CYAN),
        html.Div(id="ips-final-summary"),

        html.Div([
            dbc.Checklist(
                options=[{"label": "Tự động cấu hình Bộ Lọc Screener theo Hồ sơ IPS này", "value": "apply_filters"}],
                value=["apply_filters"],
                id="ips-apply-options",
                style={"color": _GREEN, "fontWeight": "600", "fontSize": "14px", "marginBottom": "16px"},
            ),
            html.Div([
                html.I(className="fas fa-info-circle", style={"color": _BLUE, "marginRight": "8px", "fontSize": "12px"}),
                html.Span("Toàn bộ gợi ý chỉ mang tính tham khảo học thuật dựa trên CFA Framework, không phải khuyến nghị mua/bán.", 
                          style={"fontSize": "12px", "color": _TEXT_SEC}),
            ], style={"backgroundColor": "rgba(59, 130, 246, 0.1)", "border": "1px solid rgba(59, 130, 246, 0.2)", "borderRadius": "8px", "padding": "12px 16px"}),
        ], style={"marginTop": "24px", "paddingTop": "24px", "borderTop": f"1px dashed {_BORDER}"}),

        html.Div(id="ips-apply-status", style={"fontSize": "13px", "minHeight": "24px", "marginTop": "16px"}),
    ])

# ─────────────────────────────────────────────────────────────────────────────
# MAIN LAYOUT
# ─────────────────────────────────────────────────────────────────────────────
layout = html.Div(
    id="ips-onboarding-wrapper",
    style={
        "minHeight": "100vh",
        "paddingTop": "80px",
        "paddingBottom": "80px",
        "backgroundColor": _BG_PAGE,
        "backgroundImage": "radial-gradient(circle at 15% 50%, rgba(59, 130, 246, 0.05), transparent 30%), radial-gradient(circle at 85% 30%, rgba(16, 185, 129, 0.05), transparent 30%)",
        "fontFamily": _FONT_INTER,
    },
    children=[
        _hero_section(),          # ← THÊM DÒNG NÀY VÀO ĐÂY
        html.Div(
            style={"maxWidth": "760px", "margin": "0 auto", "padding": "0 24px"},
            children=[
                # ── Logo & Intro ──────────────────────────────────────────────
                html.Div([
                    html.Div([
                        html.Div([
                            html.I(className="fas fa-chart-line", style={"color": _BG_PAGE, "fontSize": "16px"}),
                        ], style={
                            "width": "32px", "height": "32px", "backgroundColor": _BLUE,
                            "borderRadius": "8px", "display": "flex", "alignItems": "center",
                            "justifyContent": "center", "marginRight": "12px",
                            "boxShadow": f"0 0 15px {_BLUE}40"
                        }),
                        html.Span("VSS Wealth Management", style={
                            "fontSize": "22px", "fontWeight": "800",
                            "color": _TEXT_PRI, "fontFamily": _FONT_SORA,
                            "letterSpacing": "-0.5px"
                        }),
                    ], style={"display": "flex", "alignItems": "center", "justifyContent": "center", "marginBottom": "12px"}),
                    
                    html.P(
                        "Thiết lập Investment Policy Statement (IPS) cá nhân hóa.",
                        style={"fontSize": "15px", "color": _TEXT_SEC, "textAlign": "center", "marginBottom": "40px"},
                    ),
                ]),

                # ── Progress Bar ─────────────────────────────────────────────
                html.Div(id="ips-progress-bar", style={"marginBottom": "32px"}),

                # ── Main Wizard Card ──────────────────────────────────────────
                html.Div(
                    style={
                        "backgroundColor": _BG_CARD,
                        "border": f"1px solid {_BORDER}",
                        "borderRadius": "24px",
                        "boxShadow": "0 25px 50px -12px rgba(0, 0, 0, 0.7), 0 0 40px rgba(59, 130, 246, 0.05)",
                        "overflow": "hidden",
                    },
                    children=[
                        # Card Body (Steps Content)
                        html.Div(
                            style={"padding": "40px 48px", "position": "relative"},
                            children=[
                                _step1(), _step2(), _step3(), _step4(), _step5(),

                                # Hidden Stores
                                dcc.Store(id="ips-current-step", data=1),
                                dcc.Store(id="ips-goal-store",   data=None),
                                dcc.Store(id="ips-will-store",   data=None),
                                dcc.Store(id="ips-time-store",   data=None),
                                dcc.Store(id="ips-liq-store",    data=None),
                            ],
                        ),

                        # Card Footer (Navigation)
                        html.Div([
                            dbc.Button(
                                [html.I(className="fas fa-arrow-left", style={"marginRight": "8px"}), "Quay lại"],
                                id="ips-btn-prev", size="md",
                                style={
                                    "backgroundColor": _BG_CARD2, "border": f"1px solid {_BORDER2}",
                                    "color": _TEXT_SEC, "borderRadius": "8px",
                                    "fontFamily": _FONT_INTER, "fontSize": "14px", "fontWeight": "600",
                                    "padding": "10px 20px", "transition": "all 0.2s"
                                },
                            ),
                            dbc.Button(
                                ["Tiếp tục ", html.I(className="fas fa-arrow-right", style={"marginLeft": "8px"})],
                                id="ips-btn-next", size="md",
                                style={
                                    "background": "linear-gradient(135deg, #2563eb, #1d4ed8)",
                                    "border": "none", "color": "#ffffff", "borderRadius": "8px",
                                    "fontFamily": _FONT_SORA, "fontSize": "14px", "fontWeight": "700",
                                    "padding": "10px 28px", "boxShadow": "0 4px 14px 0 rgba(37, 99, 235, 0.39)",
                                    "transition": "all 0.2s"
                                },
                            ),
                        ], style={
                            "display": "flex", "justifyContent": "space-between", "alignItems": "center",
                            "padding": "20px 48px", "borderTop": f"1px solid {_BORDER}",
                            "backgroundColor": "rgba(17, 24, 35, 0.5)", "backdropFilter": "blur(10px)"
                        }),
                    ],
                ),

                # ── Footer Links ──────────────────────────────────────────────
                html.Div([
                    html.Span(
                        "Bỏ qua thiết lập, truy cập toàn thị trường",
                        id="btn-skip-onboarding", n_clicks=0,
                        style={
                            "color": _TEXT_MUT, "fontSize": "13px", "cursor": "pointer",
                            "textDecoration": "underline", "textUnderlineOffset": "4px",
                            "fontFamily": _FONT_INTER, "transition": "color 0.2s"
                        }
                    )
                ], style={"textAlign": "center", "marginTop": "32px"}),
                
                html.P(
                    "🔒 Dữ liệu hồ sơ được mã hóa và lưu trữ cục bộ trên thiết bị của bạn.",
                    style={"fontSize": "12px", "color": _TEXT_MUT, "textAlign": "center", "marginTop": "24px", "opacity": "0.7"},
                ),
            ],
        ),
    ],
)