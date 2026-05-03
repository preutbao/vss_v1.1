# src/components/header.py
# ─────────────────────────────────────────────────────────────────────────────
# Header gồm:
#   - Sticky navbar (có nút Đăng nhập / User menu)
#   - Hero banner slideshow
#   - Login modal
#   - dcc.Store auth-store (localStorage)
# ─────────────────────────────────────────────────────────────────────────────

from dash import html, dcc
import dash_bootstrap_components as dbc

sys_font = "'Inter', 'Segoe UI', system-ui, -apple-system, sans-serif"


# ── Helper: tạo một ô nhập liệu cho login form ───────────────────────────────
def _login_field(label, input_id, input_type="text", placeholder=""):
    return html.Div([
        html.Label(label, className="login-field-label"),
        dbc.Input(
            id=input_id,
            type=input_type,
            placeholder=placeholder,
            className="login-input",
            n_submit=0,          # cho phép bấm Enter để submit
            debounce=False,
            autocomplete="off" if input_type == "password" else "username",
        ),
    ], style={"marginBottom": "16px"})


# ── Login Modal ───────────────────────────────────────────────────────────────
def _create_login_modal():
    return dbc.Modal(
        id="login-modal",
        is_open=False,
        centered=True,
        backdrop=True,
        size="sm",
        children=[
            dbc.ModalHeader(
                close_button=True,
                id="btn-close-login",
                style={"border": "none", "paddingBottom": "0"},
                children=html.Div([
                    # Icon + Tiêu đề
                    html.Div([
                        html.Div([
                            html.I(className="fas fa-chart-line",
                                   style={"color": "#fff", "fontSize": "14px"}),
                        ], style={
                            "width": "36px", "height": "36px",
                            "background": "linear-gradient(135deg,#00a651,#00c85a)",
                            "borderRadius": "9px",
                            "display": "flex", "alignItems": "center",
                            "justifyContent": "center",
                            "boxShadow": "0 0 16px rgba(0,166,81,0.35)",
                            "marginBottom": "12px",
                        }),
                        html.Div("Đăng nhập", className="login-modal-title"),
                        html.P("Mở khóa toàn bộ tính năng phân tích chuyên sâu",
                               className="login-modal-subtitle"),
                    ]),
                ]),
            ),
            dbc.ModalBody([
                # Username
                _login_field("Tên đăng nhập", "login-username",
                              placeholder="Nhập tên đăng nhập..."),

                # Password
                _login_field("Mật khẩu", "login-password",
                              input_type="password", placeholder="Nhập mật khẩu..."),

                # Error message (ẩn mặc định)
                html.Div(id="login-error-msg", style={"display": "none"}),

                # Submit
                dbc.Button("Đăng nhập",
                           id="login-submit-btn",
                           n_clicks=0,
                           className="btn-login-submit",
                           style={"marginTop": "8px"}),

                # Divider
                html.Div([
                    html.Div(className="login-divider",
                             children="hoặc chưa có tài khoản?"),
                ]),

                # Mở tài khoản Vietcap
                html.A(
                    [html.I(className="fas fa-external-link-alt",
                             style={"marginRight": "6px", "fontSize": "11px"}),
                     "Mở tài khoản Vietcap miễn phí"],
                    href="https://www.vietcap.com.vn/mo-tai-khoan?language=vi&utm_source=vss",
                    target="_blank",
                    className="login-open-account-link",
                ),

                # Demo hint
                html.Div([
                    html.I(className="fas fa-info-circle",
                           style={"color": "#3b82f6", "fontSize": "10px",
                                  "marginRight": "5px"}),
                    html.Span("Demo: ",
                              style={"fontWeight": "700", "color": "#3b82f6"}),
                    html.Span("abcABC / 123@",
                              style={"fontFamily": "'Roboto Mono', monospace",
                                     "color": "#8b949e", "fontSize": "11.5px"}),
                ], style={
                    "marginTop": "14px",
                    "padding": "8px 12px",
                    "background": "rgba(59,130,246,0.07)",
                    "border": "1px solid rgba(59,130,246,0.2)",
                    "borderRadius": "6px",
                    "display": "flex",
                    "alignItems": "center",
                    "fontSize": "12px",
                }),
            ]),
        ],
    )


# ── Main header builder ───────────────────────────────────────────────────────
def create_header():
    return html.Div(id="vietcap-master-header", children=[

        # ── Auth store (localStorage — persist qua sessions) ──────────────
        dcc.Store(id='auth-store', storage_type='local', data={"logged_in": False}),

        # ── Login modal ───────────────────────────────────────────────────
        _create_login_modal(),

        # ================================================================
        # TẦNG 1: STICKY NAVBAR
        # ================================================================
        html.Div([
            html.Div([
                # 1. Logo
                html.A([
                    html.Span("Vietcap", style={
                        "fontSize": "20px", "fontWeight": "800",
                        "color": "white", "letterSpacing": "-0.5px",
                        "fontFamily": sys_font,
                    }),
                    html.Span("▲", style={
                        "color": "#00a651", "fontSize": "11px",
                        "marginLeft": "2px", "transform": "translateY(-6px)",
                        "display": "inline-block",
                    })
                ], href="https://www.vietcap.com.vn", target="_blank",
                   style={"textDecoration": "none", "display": "flex", "alignItems": "center"}),

                # 2. Nav links
                html.Div([
                    html.A("Về Vietcap",
                           href="https://www.vietcap.com.vn/ve-vietcap",
                           target="_blank", className="vietcap-nav-link"),
                    html.A("Dịch vụ",
                           href="https://www.vietcap.com.vn/tu-van-khach-hang-ca-nhan",
                           target="_blank", className="vietcap-nav-link"),
                    html.A("Sản phẩm", href="#", className="vietcap-nav-link"),
                    html.A("Truyền thông",
                           href="https://www.vietcap.com.vn/chien-dich",
                           target="_blank", className="vietcap-nav-link"),
                    html.A("Screener",
                           href="#screener-scroll-anchor",
                           className="vietcap-nav-link vietcap-nav-screener"),
                ], className="d-flex align-items-center gap-4"),

                # 3. Right: Auth area
                html.Div([
                    # ── Trạng thái chưa đăng nhập: nút Đăng nhập ──
                    dbc.Button(
                        [html.I(className="fas fa-sign-in-alt",
                                style={"marginRight": "5px"}),
                         "Đăng nhập"],
                        id="btn-login",
                        n_clicks=0,
                        className="vietcap-nav-login-btn",
                        style={},
                    ),

                    # ── Trạng thái đã đăng nhập: User menu ──
                    html.Div(
                        id="btn-logout-wrap",
                        style={"display": "none"},     # callback sẽ show
                        children=[
                            # Tên + badge
                            html.Div(
                                id="navbar-user-name",
                                style={
                                    "display": "flex", "alignItems": "center",
                                    "gap": "6px", "fontSize": "12.5px",
                                    "color": "#c9d1d9",
                                },
                            ),
                            # Nút Đăng xuất
                            dbc.Button(
                                [html.I(className="fas fa-sign-out-alt",
                                        style={"marginRight": "4px", "fontSize": "11px"}),
                                 "Đăng xuất"],
                                id="btn-logout",
                                n_clicks=0,
                                size="sm",
                                outline=True,
                                color="secondary",
                                style={
                                    "fontSize": "11px", "padding": "4px 12px",
                                    "borderRadius": "6px", "borderColor": "#30363d",
                                    "color": "#8b949e",
                                },
                            ),
                        ],
                    ),

                    # Nút mở tài khoản (luôn hiện)
                    html.A("Mở tài khoản",
                           href="https://www.vietcap.com.vn/mo-tai-khoan?language=vi",
                           target="_blank",
                           className="vietcap-nav-cta",
                           style={"marginLeft": "8px"}),
                ], style={"display": "flex", "alignItems": "center", "gap": "8px"}),

            ], style={
                "width": "100%", "maxWidth": "1200px", "margin": "0 auto",
                "display": "flex", "alignItems": "center",
                "justifyContent": "space-between", "padding": "0 20px",
            })
        ], style={
            "position": "fixed", "top": "0", "left": "0",
            "width": "100%", "height": "56px",
            "backgroundColor": "rgba(6, 15, 30, 0.92)",
            "backdropFilter": "blur(16px)",
            "WebkitBackdropFilter": "blur(16px)",
            "borderBottom": "1px solid rgba(0,166,81,0.18)",
            "boxShadow": "0 1px 0 rgba(0,166,81,0.08), 0 4px 32px rgba(0,0,0,0.5)",
            "zIndex": "9999",
            "display": "flex", "alignItems": "center",
        }),

        # Hidden placeholder (navbar-user-menu referenced by callback)
        html.Div(id="navbar-user-menu", style={"display": "none"}),

        # ================================================================
        # TẦNG 2: HERO BANNER
        # ================================================================
        html.Div([
            dbc.Carousel(
                items=[
                    {"key": "1", "src": "/assets/anh1.png", "img_style": {
                        "width": "100%", "height": "400px",
                        "objectFit": "cover", "filter": "brightness(0.55)"}},
                    {"key": "2", "src": "/assets/anh2.png", "img_style": {
                        "width": "100%", "height": "400px",
                        "objectFit": "cover", "filter": "brightness(0.55)"}},
                    {"key": "3", "src": "/assets/anh3.png", "img_style": {
                        "width": "100%", "height": "400px",
                        "objectFit": "cover", "filter": "brightness(0.55)"}},
                ],
                controls=False, indicators=False, interval=3000,
                style={"position": "absolute", "top": "0", "left": "0",
                       "width": "100%", "height": "100%", "zIndex": "1"}
            ),
            html.Div(style={
                "position": "absolute", "inset": "0",
                "background": "linear-gradient(to bottom, rgba(6,15,30,0.65) 0%, rgba(6,15,30,0.15) 40%, rgba(6,15,30,0.85) 85%, #0a0e14 100%)",
                "zIndex": "2",
            }),
            html.Div([
                html.P("NỀN TẢNG PHÂN TÍCH CỔ PHIẾU CHUYÊN NGHIỆP", style={
                    "fontSize": "11px", "fontWeight": "600", "letterSpacing": "2.5px",
                    "color": "rgba(160,210,180,0.75)", "marginBottom": "14px",
                    "textTransform": "uppercase", "fontFamily": sys_font,
                }),
                html.H1([
                    html.Span("Vietcap ", style={
                        "color": "#00c85a", "fontWeight": "800",
                        "fontFamily": "'Sora', " + sys_font,
                        "textShadow": "0 0 40px rgba(0,200,90,0.35)",
                    }),
                    html.Span("Smart Screener", style={
                        "color": "#f0f6ff", "fontWeight": "300",
                        "fontFamily": "'Sora', " + sys_font,
                    }),
                ], style={"fontSize": "clamp(36px, 5vw, 56px)", "marginBottom": "20px",
                          "letterSpacing": "-1.5px", "lineHeight": "1.1"}),
                html.Div(style={
                    "width": "56px", "height": "2px",
                    "background": "linear-gradient(90deg, transparent, #00a651, transparent)",
                    "margin": "0 auto 28px auto", "opacity": "0.7",
                }),
                html.A("Khám phá ngay ↓",
                       href="#screener-scroll-anchor",
                       className="vietcap-btn-explore-glass",
                       style={
                           "display": "inline-block",
                           "background": "rgba(0,166,81,0.14)",
                           "border": "1px solid rgba(0,166,81,0.45)",
                           "color": "#00e676", "padding": "11px 32px",
                           "borderRadius": "30px", "textDecoration": "none",
                           "fontWeight": "600", "fontSize": "13px",
                           "fontFamily": sys_font,
                           "backdropFilter": "blur(8px)",
                           "WebkitBackdropFilter": "blur(8px)",
                           "boxShadow": "0 4px 20px rgba(0,0,0,0.25)",
                           "transition": "all 0.3s ease", "letterSpacing": "0.3px",
                       })
            ], style={
                "position": "relative", "zIndex": "3",
                "textAlign": "center", "color": "white", "padding": "0 20px",
            })
        ], style={
            "marginTop": "56px",
            "position": "relative", "width": "100%", "height": "400px",
            "overflow": "hidden",
            "display": "flex", "alignItems": "center", "justifyContent": "center",
            "backgroundColor": "#050a0f",
        })
    ])