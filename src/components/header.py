# src/components/header.py
# ─────────────────────────────────────────────────────────────────────────────
# Header gồm:
#   - Sticky navbar (có nút Đăng nhập / User menu)
#   - Hero banner (typography-forward, không dùng ảnh nền)
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
            n_submit=0,
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
                _login_field("Tên đăng nhập", "login-username",
                              placeholder="Nhập tên đăng nhập..."),
                _login_field("Mật khẩu", "login-password",
                              input_type="password", placeholder="Nhập mật khẩu..."),
                html.Div(id="login-error-msg", style={"display": "none"}),
                dbc.Button("Đăng nhập",
                           id="login-submit-btn",
                           n_clicks=0,
                           className="btn-login-submit",
                           style={"marginTop": "8px"}),
                html.Div([
                    html.Div(className="login-divider",
                             children="hoặc chưa có tài khoản?"),
                ]),
                html.A(
                    [html.I(className="fas fa-external-link-alt",
                             style={"marginRight": "6px", "fontSize": "11px"}),
                     "Mở tài khoản Vietcap ngay!"],
                    href="https://www.vietcap.com.vn/mo-tai-khoan?language=vi&utm_source=vss",
                    target="_blank",
                    className="login-open-account-link",
                ),
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

# ── TÁCH PHẦN 1: TOPBAR (Dùng được ở mọi nơi) ──────────────────────────────────
def create_topbar():
    return html.Div(id="vietcap-topbar-only", children=[
        # ── Auth store ────────────────────────────────────────────────────────
        dcc.Store(id='auth-store', storage_type='local', data={"logged_in": False}),

        # ── Login modal ───────────────────────────────────────────────────────
        _create_login_modal(),

        # ================================================================
        # TẦNG 1: STICKY NAVBAR
        # ================================================================
        html.Div(id="vss-sticky-nav", children=[
            html.Div(className="vss-nav-inner", children=[

                # Logo
                html.A([
                    html.Span([
                        html.Span("Vietcap", className="vss-logo-text"),
                        html.Span("▲", className="vss-logo-accent", style={
                            "fontSize": "10px", "marginLeft": "1px",
                            "verticalAlign": "super", "fontStyle": "normal",
                        }),
                    ], style={"textDecoration": "none"}),
                ], href="https://www.vietcap.com.vn", target="_blank",
                   style={"textDecoration": "none", "display": "flex", "alignItems": "center"}),

                # Nav links
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

                # Right: Auth area
                html.Div([
                    dbc.Button(
                        [html.I(className="fas fa-sign-in-alt",
                                style={"marginRight": "5px"}),
                         "Đăng nhập"],
                        id="btn-login",
                        n_clicks=0,
                        className="vietcap-nav-login-btn",
                        style={},
                    ),
                    html.Div(
                        id="btn-logout-wrap",
                        style={"display": "none"},
                        children=[
                            html.Div(
                                id="navbar-user-name",
                                style={
                                    "display": "flex", "alignItems": "center",
                                    "gap": "6px", "fontSize": "12.5px",
                                    "color": "#c9d1d9",
                                },
                            ),
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
                    html.A("Mở tài khoản",
                           href="https://www.vietcap.com.vn/mo-tai-khoan?language=vi",
                           target="_blank",
                           className="vietcap-nav-cta",
                           style={"marginLeft": "8px", "display": "none"}),
                ], style={"display": "flex", "alignItems": "center", "gap": "8px"}),

            ])
        ]),

        # Hidden placeholder
        html.Div(id="navbar-user-menu", style={"display": "none"}),
    ])


# ── TÁCH PHẦN 2: HERO BANNER (Chỉ dùng cho trang chủ) ─────────────────────────
def create_banner():
    return html.Div(id="vss-hero", style={
        "marginTop": "56px", # Giữ nguyên khoảng trống để không đè Topbar
        "width": "100%",
        "height": "400px",
    }, children=[

        # Layered background
        html.Div(id="vss-hero-bg"),
        html.Div(id="vss-hero-grid"),
        html.Div(id="vss-orb-1"),
        html.Div(id="vss-orb-2"),

        # Content
        html.Div(id="vss-hero-content", children=[

            # Eyebrow
            html.Div(className="vss-eyebrow", children=[
                html.Span(className="vss-eyebrow-dot"),
                "Nền tảng phân tích cổ phiếu chuyên nghiệp",
            ]),

            # Headline
            html.H1(className="vss-headline", children=[
                html.Span("Vietcap", className="vss-headline-brand"),
                html.Span("Smart Screener", className="vss-headline-sub"),
            ]),

            # Thin rule
            html.Div(className="vss-rule"),

            # Stat pills
            html.Div(className="vss-stats", children=[
                html.Span(className="vss-stat-pill", children=[
                    html.Strong("1,500+"), " mã niêm yết"
                ]),
                html.Span("·", className="vss-stat-sep"),
                html.Span(className="vss-stat-pill", children=[
                    html.Strong("165+"), " chỉ số định lượng"
                ]),
                html.Span("·", className="vss-stat-sep"),
                html.Span(className="vss-stat-pill", children=[
                    html.Strong("10"), " trường phái đầu tư"
                ]),
                html.Span("·", className="vss-stat-sep"),
                html.Span(className="vss-stat-pill", children=[
                    "HOSE · HNX · UPCoM"
                ]),
            ]),

            # CTA
            html.A(
                [
                    "Khám phá ngay",
                    html.Span("↓", className="vss-cta-arrow"),
                ],
                href="#screener-scroll-anchor",
                className="vss-cta",
            ),

        ]),
    ])


# ── TÁCH PHẦN 3: HEADER CHÍNH (Gộp cả Topbar và Banner cho trang Screener) ────
def create_header():
    return html.Div(id="vietcap-master-header", children=[
        create_topbar(),
        create_banner()
    ])