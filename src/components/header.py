# src/components/header.py
# ─────────────────────────────────────────────────────────────────────────────
# Header gồm:
#   - Sticky transparent navbar (overlay lên hero, kiểu Finovate)
#   - Hero banner 2 cột: text bên trái + illustration SVG bên phải
#   - Login modal (Premium Split-Layout)
#   - dcc.Store auth-store (localStorage)
#   - Dual theme: light / dark (dùng CSS variables từ style.css)
# ─────────────────────────────────────────────────────────────────────────────

from dash import html, dcc
import dash_bootstrap_components as dbc

sys_font = "'Inter', 'Segoe UI', system-ui, -apple-system, sans-serif"

# ── Helper: Input field ────────────────────────────────────────────────────────
def _login_field(label, input_id, input_type="text", placeholder="", icon_cls=""):
    return html.Div([
        html.Label(label, style={
            "fontSize": "12px", "fontWeight": "600", "color": "#9ca3af",
            "marginBottom": "6px", "display": "block", "letterSpacing": "0.02em"
        }),
        html.Div([
            html.I(className=icon_cls, style={
                "position": "absolute", "left": "14px", "top": "50%",
                "transform": "translateY(-50%)", "color": "#6b7280", "fontSize": "13px"
            }) if icon_cls else None,
            dbc.Input(
                id=input_id,
                type=input_type,
                placeholder=placeholder,
                n_submit=0,
                debounce=False,
                autocomplete="off" if input_type == "password" else "username",
                style={
                    "backgroundColor": "rgba(255,255,255,0.03)",
                    "border": "1px solid rgba(255,255,255,0.08)",
                    "borderRadius": "8px",
                    "color": "#f3f4f6",
                    "padding": f"10px 14px 10px { '38px' if icon_cls else '14px' }",
                    "fontSize": "14px",
                    "transition": "all 0.2s ease-in-out",
                    "boxShadow": "none",
                }
            ),
        ], style={"position": "relative"}),
    ], style={"marginBottom": "16px"})


def _pricing_row(icon_cls, color, text, is_pro=False):
    return html.Div([
        html.Div(
            html.I(className=icon_cls, style={"color": color, "fontSize": "10px"}),
            style={
                "width": "18px", "height": "18px", "borderRadius": "50%",
                "backgroundColor": f"{color}15" if is_pro else "transparent",
                "display": "flex", "alignItems": "center", "justifyContent": "center",
                "flexShrink": "0", "marginTop": "1px"
            }
        ),
        html.Span(text, style={
            "fontSize": "13px",
            "color": "#e5e7eb" if is_pro else "#9ca3af",
            "fontWeight": "500" if is_pro else "400",
            "lineHeight": "1.5",
            "textDecoration": "line-through" if color == "#484f58" else "none",
        }),
    ], style={"display": "flex", "alignItems": "flex-start", "gap": "10px", "marginBottom": "10px"})


# ── Login Modal ────────────────────────────────────────────────────────────────
def _create_login_modal():
    return dbc.Modal(
        id="login-modal",
        is_open=False,
        centered=True,
        backdrop="static",
        size="xl",
        contentClassName="premium-modal-content",
        style={"backgroundColor": "transparent", "border": "none"},
        children=[
            html.Button(
                html.I(className="fas fa-times"),
                id="btn-close-login",
                style={
                    "position": "absolute", "top": "16px", "right": "16px",
                    "background": "rgba(255,255,255,0.05)", "border": "none",
                    "color": "#9ca3af", "width": "32px", "height": "32px",
                    "borderRadius": "50%", "zIndex": "10", "cursor": "pointer",
                    "display": "flex", "alignItems": "center", "justifyContent": "center",
                    "transition": "all 0.2s"
                }
            ),
            html.Div(style={
                "display": "flex", "flexWrap": "wrap",
                "backgroundColor": "#030712", "borderRadius": "16px",
                "overflow": "hidden",
                "border": "1px solid rgba(255,255,255,0.08)",
                "boxShadow": "0 25px 50px -12px rgba(0, 0, 0, 0.5)"
            }, children=[
                # Left: Login form
                html.Div(style={"flex": "1 1 40%", "padding": "48px 32px", "display": "flex", "flexDirection": "column", "justifyContent": "center"}, children=[
                    html.Div([
                        html.Div([
                            html.I(className="fas fa-user", style={"color": "#fff", "fontSize": "16px"}),
                        ], style={
                            "width": "40px", "height": "40px",
                            "background": "linear-gradient(135deg, #00a651, #00c85a)",
                            "borderRadius": "10px", "display": "flex",
                            "alignItems": "center", "justifyContent": "center",
                            "boxShadow": "0 8px 16px rgba(0,166,81,0.25)",
                            "marginBottom": "20px",
                        }),
                        html.H2("Đăng nhập", style={"fontSize": "24px", "fontWeight": "700", "color": "#f9fafb", "marginBottom": "6px", "letterSpacing": "-0.02em"}),
                        html.P("Truy cập hệ thống dữ liệu định lượng VSS", style={"fontSize": "14px", "color": "#9ca3af", "marginBottom": "32px"}),
                    ]),
                    _login_field("TÊN ĐĂNG NHẬP", "login-username", placeholder="user@vietcap.com", icon_cls="fas fa-envelope"),
                    _login_field("MẬT KHẨU", "login-password", input_type="password", placeholder="••••••••", icon_cls="fas fa-lock"),
                    html.Div(id="login-error-msg", style={"display": "none", "color": "#ef4444", "fontSize": "12px", "marginTop": "-8px", "marginBottom": "12px"}),
                    dbc.Button(
                        "Đăng nhập hệ thống",
                        id="login-submit-btn", n_clicks=0,
                        style={
                            "width": "100%", "padding": "12px", "backgroundColor": "#fff",
                            "color": "#030712", "fontWeight": "600", "fontSize": "14px",
                            "border": "none", "borderRadius": "8px", "marginTop": "8px",
                            "transition": "all 0.2s"
                        }
                    ),
                    html.Div([
                        html.Span("Chưa có tài khoản? ", style={"color": "#6b7280"}),
                        html.A("Mở tài khoản ngay", href="https://www.vietcap.com.vn/mo-tai-khoan?language=vi", target="_blank",
                               style={"color": "#00a651", "textDecoration": "none", "fontWeight": "600"})
                    ], style={"fontSize": "13px", "textAlign": "center", "marginTop": "24px"})
                ]),
                # Right: Upsell
                html.Div(style={
                    "flex": "1 1 55%", "padding": "48px 32px",
                    "background": "linear-gradient(145deg, #05130a 0%, #020604 100%)",
                    "borderLeft": "1px solid rgba(0, 166, 81, 0.1)",
                    "position": "relative", "overflow": "hidden"
                }, children=[
                    html.Div(style={
                        "position": "absolute", "top": "-50px", "right": "-50px",
                        "width": "200px", "height": "200px", "background": "#00a651",
                        "filter": "blur(100px)", "opacity": "0.15", "borderRadius": "50%"
                    }),
                    html.Div("NÂNG TẦM CHIẾN LƯỢC ĐẦU TƯ", style={
                        "fontSize": "11px", "fontWeight": "800", "color": "#00a651",
                        "letterSpacing": "0.15em", "marginBottom": "12px",
                        "display": "flex", "alignItems": "center", "gap": "8px"
                    }),
                    html.H3("Mở khóa toàn bộ sức mạnh của Smart Screener", style={
                        "fontSize": "20px", "fontWeight": "700", "color": "#fff",
                        "lineHeight": "1.3", "marginBottom": "32px", "maxWidth": "90%"
                    }),
                    html.Div(style={"display": "flex", "gap": "16px"}, children=[
                        html.Div(style={
                            "flex": "1", "padding": "20px 16px",
                            "backgroundColor": "rgba(255,255,255,0.02)",
                            "borderRadius": "12px", "border": "1px solid rgba(255,255,255,0.04)"
                        }, children=[
                            html.Div("TRẢI NGHIỆM BASIC", style={"fontSize": "12px", "color": "#9ca3af", "fontWeight": "700", "marginBottom": "4px"}),
                            html.Div("Miễn phí", style={"fontSize": "20px", "color": "#d1d5db", "fontWeight": "800", "marginBottom": "20px"}),
                            _pricing_row("fas fa-check", "#6b7280", "Data đóng cửa hàng ngày"),
                            _pricing_row("fas fa-check", "#6b7280", "Screener cơ bản"),
                            _pricing_row("fas fa-times", "#484f58", "Export báo cáo PDF"),
                            _pricing_row("fas fa-times", "#484f58", "Margin Crisis Radar"),
                        ]),
                        html.Div(style={
                            "flex": "1", "padding": "20px 16px",
                            "backgroundColor": "rgba(0, 166, 81, 0.05)",
                            "borderRadius": "12px", "border": "1px solid rgba(0, 166, 81, 0.3)",
                            "boxShadow": "0 10px 30px -10px rgba(0, 166, 81, 0.2)",
                            "position": "relative", "display": "flex", "flexDirection": "column"
                        }, children=[
                            html.Div("✦ PRO PLAN", style={
                                "position": "absolute", "top": "-10px", "left": "50%",
                                "transform": "translateX(-50%)",
                                "background": "linear-gradient(90deg, #00a651, #00c85a)",
                                "color": "#000", "fontSize": "10px", "fontWeight": "800",
                                "padding": "4px 10px", "borderRadius": "12px", "letterSpacing": "0.05em"
                            }),
                            html.Div([
                                html.Div([
                                    html.Span("2.490k", style={"fontSize": "13px", "color": "#6b7280", "textDecoration": "line-through", "fontWeight": "500", "marginRight": "8px"}),
                                    html.Span("-20%", style={"backgroundColor": "rgba(239,68,68,0.15)", "color": "#ef4444", "fontSize": "10px", "fontWeight": "800", "padding": "2px 6px", "borderRadius": "4px", "letterSpacing": "0.05em", "border": "1px solid rgba(239,68,68,0.3)"}),
                                ], style={"marginBottom": "2px", "display": "flex", "alignItems": "center"}),
                                html.Span("1.990k", style={"fontSize": "26px", "color": "#00e676", "fontWeight": "800", "lineHeight": "1"}),
                                html.Span(" /năm", style={"fontSize": "12px", "color": "#9ca3af", "fontWeight": "500"})
                            ], style={"marginTop": "12px", "marginBottom": "20px"}),
                            _pricing_row("fas fa-check", "#00e676", "Chatbot AI Real-time", is_pro=True),
                            _pricing_row("fas fa-check", "#00e676", "Backtest 10 trường phái", is_pro=True),
                            _pricing_row("fas fa-check", "#00e676", "Báo cáo phân tích chuyên sâu", is_pro=True),
                            _pricing_row("fas fa-check", "#00e676", "Tín hiệu Margin Crisis Radar", is_pro=True),
                            html.A("Nâng cấp ngay", href="https://www.vietcap.com.vn/mo-tai-khoan?language=vi", target="_blank", style={
                                "display": "block", "textAlign": "center", "marginTop": "18px",
                                "padding": "10px 0", "background": "rgba(0,166,81,0.15)",
                                "color": "#00e676", "fontWeight": "600", "fontSize": "13px",
                                "borderRadius": "6px", "textDecoration": "none",
                                "border": "1px solid rgba(0,166,81,0.4)", "transition": "all 0.2s"
                            }),
                            html.Div([
                                html.I(className="fas fa-info-circle", style={"marginRight": "4px", "fontSize": "10px"}),
                                "Kèm theo ưu tiên hỗ trợ chiến lược từ đội ngũ tư vấn Vietcap."
                            ], style={"fontSize": "10px", "color": "#6b7280", "fontStyle": "italic", "textAlign": "center", "marginTop": "12px", "lineHeight": "1.4"})
                        ]),
                    ])
                ])
            ])
        ]
    )


# ── Vietcap coin illustration (inline SVG) ────────────────────────────────────
def _create_coin_svg():
    """
    3D coin / disc SVG illustration loaded via external file.
    """
    return html.Div(className="vss-coin-wrap", children=[
        html.Img(src="/assets/coin.svg", className="vss-coin-svg", style={"width": "100%", "height": "100%"})
    ])


# ── TOPBAR ────────────────────────────────────────────────────────────────────
def create_topbar(id_suffix=""):
    wrapper_id = f"vietcap-topbar{id_suffix}" if id_suffix else "vietcap-topbar-only"

    theme_switch = html.Div(
    [
        dbc.Switch(
            id="theme-switch-button",
            value=True, # true = đang ở dark mode
            style={"cursor": "pointer", "marginBottom": "0"}
        )
    ],
    className="d-flex align-items-center",
    style={
        "backgroundColor": "transparent",
        "padding": "4px 8px",
        "marginRight": "8px"
    }
)

    scroll_script = html.Script("")

    return html.Div(id=wrapper_id, children=[
        dcc.Store(id='auth-store', storage_type='local', data={"logged_in": False}),
        _create_login_modal(),
        scroll_script,

        html.Div(id="vss-sticky-nav", children=[
            html.Div(className="vss-nav-inner", children=[

                # Logo
                html.A([
                    html.Span("Vietcap", className="vss-logo-text"),
                    html.Span("▲", className="vss-logo-accent", style={
                        "fontSize": "10px", "marginLeft": "2px",
                        "verticalAlign": "super", "fontStyle": "normal",
                    }),
                ], href="https://www.vietcap.com.vn", target="_blank",
                    style={"textDecoration": "none", "display": "flex", "alignItems": "center"}),

                # Nav links
                html.Div([
                    html.A("Về Vietcap", href="https://www.vietcap.com.vn/ve-vietcap", target="_blank", className="vietcap-nav-link"),
                    html.A("Dịch vụ", href="https://www.vietcap.com.vn/tu-van-khach-hang-ca-nhan", target="_blank", className="vietcap-nav-link"),
                    html.A("Sản phẩm", href="#", className="vietcap-nav-link"),
                    html.A("Truyền thông", href="https://www.vietcap.com.vn/chien-dich", target="_blank", className="vietcap-nav-link"),
                    html.A("Screener", href="#screener-scroll-anchor", className="vietcap-nav-link vietcap-nav-screener"),
                ], className="d-flex align-items-center gap-4"),

                # Auth area
                html.Div([
                    theme_switch,
                    dbc.Button(
                        [html.I(className="fas fa-sign-in-alt", style={"marginRight": "6px"}), "Đăng nhập"],
                        id="btn-login", n_clicks=0, className="vietcap-nav-login-btn",
                        style={
                            "backgroundColor": "transparent",
                            "border": "1px solid rgba(255,255,255,0.2)",
                            "color": "rgba(255,255,255,0.85)",
                            "fontSize": "13px", "fontWeight": "500",
                            "padding": "6px 16px", "borderRadius": "6px"
                        }
                    ),
                    html.Div(
                        id="btn-logout-wrap", style={"display": "none"},
                        children=[
                            html.Div(id="navbar-user-name", style={"display": "flex", "alignItems": "center", "gap": "8px", "fontSize": "13px", "color": "#d1d5db"}),
                            dbc.Button("Đăng xuất", id="btn-logout", n_clicks=0, outline=True, color="secondary", size="sm")
                        ]
                    ),
                ], style={"display": "flex", "alignItems": "center", "gap": "12px"}),
            ])
        ], style={
            "position": "fixed",
            "top": "0",
            "left": "0",
            "right": "0",
            "zIndex": "9000",
            "width": "100%",
            "backgroundColor": "#000000", # <--- THÊM DÒNG NÀY Ở ĐÂY
            "borderBottom": "1px solid #333", # <--- (Tùy chọn) Thêm viền dưới mỏng cho đẹp
        }),
        html.Div(id="navbar-user-menu", style={"display": "none"}),
    ])


# ── HERO BANNER ───────────────────────────────────────────────────────────────
def create_banner():
    return html.Div(id="vss-hero", children=[
        # Background layers
        html.Div(id="vss-hero-bg"),
        html.Div(id="vss-hero-grid"),
        html.Div(id="vss-orb-1"),
        html.Div(id="vss-orb-2"),

        # 2-column content
        html.Div(id="vss-hero-content", children=[

            # ── LEFT: Text ──
            html.Div(className="vss-hero-left", children=[

                # Headline (brand only)
                html.H1(className="vss-headline", children=[
                    html.Span("Vietcap", className="vss-headline-brand"),
                    html.Span("Smart Screener", className="vss-headline-sub"),
                ]),

                # Stats row — icon cards
                html.Div(className="vss-stats", children=[
                    # Card 1
                    html.Div(className="vss-stat-card", children=[
                        html.Div(html.I(className="fas fa-file-alt"), className="vss-stat-icon"),
                        html.Div(children=[
                            html.Div("1,500+", className="vss-stat-value"),
                            html.Div("mã niêm yết", className="vss-stat-label"),
                        ], className="vss-stat-body"),
                    ]),
                    # Card 2
                    html.Div(className="vss-stat-card", children=[
                        html.Div(html.I(className="fas fa-chart-bar"), className="vss-stat-icon"),
                        html.Div(children=[
                            html.Div("165+", className="vss-stat-value"),
                            html.Div("chỉ báo định lượng", className="vss-stat-label"),
                        ], className="vss-stat-body"),
                    ]),
                    # Card 3
                    html.Div(className="vss-stat-card", children=[
                        html.Div(html.I(className="fas fa-shield-alt"), className="vss-stat-icon"),
                        html.Div(children=[
                            html.Div("HOSE · HNX · UPCoM", className="vss-stat-value",
                                     style={"fontSize": "13px"}),
                            html.Div("sàn giao dịch", className="vss-stat-label"),
                        ], className="vss-stat-body"),
                    ]),
                ]),
            ]),

            # ── RIGHT: Coin illustration ──
            #html.Div(className="vss-hero-right", children=[
                #_create_coin_svg()
            #]),
        ]),
    ])


# ── MAIN HEADER ───────────────────────────────────────────────────────────────
def create_header():
    return html.Div(id="vietcap-master-header", style={"position": "relative"}, children=[
        create_topbar(),
        create_banner(),
    ])