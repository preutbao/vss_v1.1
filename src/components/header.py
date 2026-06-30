# src/components/header.py
# ─────────────────────────────────────────────────────────────────────────────
# Header gồm:
#   - Sticky transparent navbar (overlay lên hero, kiểu Finovate)
#   - Hero banner 2 cột: text bên trái + Top Movers card bên phải (data thật)
#   - Login modal (Premium Split-Layout)
#   - dcc.Store auth-store (localStorage)
#   - Dual theme: light / dark (dùng CSS variables từ style.css)
# ─────────────────────────────────────────────────────────────────────────────
from dash import html, dcc
import dash_bootstrap_components as dbc
import pandas as pd

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

                            # ── Ô nhập mã kích hoạt ──
                            html.Div([
                                html.Div("Đã có mã kích hoạt?",
                                        style={"fontSize": "11px", "color": "#6b7280",
                                                "marginBottom": "6px"}),
                                html.Div([
                                    dbc.Input(
                                        id="invite-code-input",
                                        placeholder="VSS-...",
                                        style={
                                            "flex": "1",
                                            "backgroundColor": "rgba(255,255,255,0.05)",
                                            "border": "1px solid rgba(0,166,81,0.3)",
                                            "borderRadius": "6px 0 0 6px",
                                            "color": "#f3f4f6", "fontSize": "13px",
                                            "padding": "8px 12px",
                                            "fontFamily": "'JetBrains Mono', monospace",
                                            "letterSpacing": "1px",
                                            "outline": "none",
                                        },
                                    ),
                                    dbc.Button(
                                        "Kích hoạt",
                                        id="invite-code-submit-btn",
                                        n_clicks=0,
                                        style={
                                            "backgroundColor": "#00a651",
                                            "border": "none",
                                            "borderRadius": "0 6px 6px 0",
                                            "color": "#000",
                                            "fontSize": "12px",
                                            "fontWeight": "700",
                                            "padding": "8px 14px",
                                            "whiteSpace": "nowrap",
                                        }
                                    ),
                                ], style={"display": "flex"}),
                                html.Div(
                                    id="invite-code-msg",
                                    style={"fontSize": "11px", "marginTop": "6px",
                                        "minHeight": "16px"},
                                ),
                            ], style={
                                "backgroundColor": "rgba(0,166,81,0.05)",
                                "border": "1px solid rgba(0,166,81,0.15)",
                                "borderRadius": "8px",
                                "padding": "12px 14px",
                                "marginBottom": "12px",
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
    (Hiện không dùng trong hero — giữ lại để tái sử dụng nếu cần.)
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
                value=True,  # true = đang ở dark mode
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
        dcc.Store(id='user-phone-store', storage_type='session', data=None),
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
                    # Nút Trạm Tâm Lý (từ version 1)
                    dbc.Button(
                        [html.I(className="fa-solid fa-kit-medical", style={"marginRight": "6px"}), "Trạm Tâm Lý"],
                        id="btn-open-psy-clinic", n_clicks=0,
                        style={
                            "backgroundColor": "transparent",
                            "border": "1px solid rgba(255,255,255,0.2)",
                            "color": "rgba(255,255,255,0.85)",
                            "fontSize": "13px", "fontWeight": "500",
                            "padding": "6px 16px", "borderRadius": "6px",
                            "marginRight": "8px",
                        }
                    ),
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
        # TÌM ĐOẠN NÀY TRONG HÀM create_topbar():
        ], style={
            "position": "fixed",
            "top": "0",
            "left": "0",
            "right": "0",
            "zIndex": "1030",  # 🟢 SỬA TỪ 8999 -> 1030: Đảm bảo luôn nằm dưới mọi Popup/Modal (chuẩn Bootstrap)
            "width": "100%",
            # 🟢 SỬA THÀNH BIẾN CSS: Hãy thay '--bg-color' bằng biến màu nền bạn đang dùng trong file style.css
            "backgroundColor": "var(--bg-color, #000000)",
            "borderBottom": "1px solid var(--border-color, #333)",  # Tương tự cho màu viền
        }),
        html.Div(id="navbar-user-menu", style={"display": "none"}),
    ])


# ── HERO BANNER ───────────────────────────────────────────────────────────────
def _get_top_movers():
    """Lấy top 6 tăng mạnh và 4 giảm mạnh nhất từ snapshot thật."""
    try:
        from src.backend.data_loader import get_snapshot_df
        df = get_snapshot_df()
        if df is None or df.empty:
            raise ValueError("empty")
        perf_col = None
        for c in ["Perf_1W", "Perf_1D", "Perf_1M"]:
            if c in df.columns:
                perf_col = c
                break
        if perf_col is None:
            raise ValueError("no perf col")
        price_col = "Price Close" if "Price Close" in df.columns else None
        # ── Lọc bỏ sàn UPCoM ──
        exchange_col = next((c for c in ["Exchange", "exchange", "San", "Market"] if c in df.columns), None)
        if exchange_col:
            df = df[~df[exchange_col].astype(str).str.upper().str.contains("UPCOM|UP-COM")]
        cols = ["Ticker", perf_col] + ([price_col] if price_col else [])
        df2 = df[cols].dropna(subset=["Ticker", perf_col]).copy()
        df2[perf_col] = pd.to_numeric(df2[perf_col], errors="coerce")
        df2 = df2.dropna(subset=[perf_col])
        # ── Lọc chỉ lấy mã có giá > 0 ──
        if price_col:
            df2[price_col] = pd.to_numeric(df2[price_col], errors="coerce")
            df2 = df2[df2[price_col] > 0]
        gainers = df2.nlargest(6, perf_col)[["Ticker", perf_col] + ([price_col] if price_col else [])]
        losers = df2.nsmallest(4, perf_col)[["Ticker", perf_col] + ([price_col] if price_col else [])]
        result = []
        for _, row in gainers.iterrows():
            pct = row[perf_col]
            price = f"{row[price_col]:,.0f}" if price_col and pd.notna(row.get(price_col)) else "—"
            result.append({"ticker": row["Ticker"], "pct": pct, "price": price, "up": True})
        for _, row in losers.iterrows():
            pct = row[perf_col]
            price = f"{row[price_col]:,.0f}" if price_col and pd.notna(row.get(price_col)) else "—"
            result.append({"ticker": row["Ticker"], "pct": pct, "price": price, "up": False})
        return result
    except Exception:
        # Fallback cứng nếu data chưa ready
        return [
            {"ticker": "VCB", "pct": 5.2, "price": "92,000", "up": True},
            {"ticker": "FPT", "pct": 3.8, "price": "140,000", "up": True},
            {"ticker": "HPG", "pct": 4.1, "price": "28,500", "up": True},
            {"ticker": "MBB", "pct": 2.7, "price": "25,250", "up": True},
            {"ticker": "TCB", "pct": 3.3, "price": "24,000", "up": True},
            {"ticker": "VNM", "pct": 1.9, "price": "60,500", "up": True},
            {"ticker": "SSI", "pct": -2.4, "price": "32,000", "up": False},
            {"ticker": "DXG", "pct": -3.1, "price": "12,800", "up": False},
            {"ticker": "NVL", "pct": -4.5, "price": "7,500", "up": False},
            {"ticker": "PDR", "pct": -2.8, "price": "9,200", "up": False},
        ]


def _build_top_movers_card(movers):
    """Tạo card 'TOP ĐỘNG' tĩnh (kiểu bảng nhỏ góc phải hero), lấy dữ liệu
    thật từ _get_top_movers(). Thay cho globe SVG + ticker marquee cũ —
    giờ nền hero dùng ảnh thật Trái Đất chụp từ không gian (assets/earth-bg.jpg)
    nên không cần dựng quả cầu giả lập nữa."""
    def _row(m):
        color = "#00e676" if m["up"] else "#ff4d4f"
        sign = "+" if m["up"] else ""
        return html.Div(className="vss-mover-row", children=[
            html.Span(m["ticker"], className="vss-mover-ticker"),
            html.Span(m["price"], className="vss-mover-price"),
            html.Span(f"{sign}{m['pct']:.2f}", className="vss-mover-pct", style={"color": color}),
        ])
    rows = [_row(m) for m in movers]
    return html.Div(className="vss-movers-card", children=[
        # Header cố định — KHÔNG nằm trong track-wrap nên không bị cuộn
        html.Div(className="vss-movers-header", children=[
            html.Span("TOP MÃ BIẾN ĐỘNG", className="vss-movers-title"),
        ]),
        html.Div(className="vss-movers-col-header", children=[
            html.Span("Mã CK", className="vss-mover-col-ticker"),
            html.Span("Giá", className="vss-mover-col-price"),
            html.Span("%", className="vss-mover-col-pct"),
        ]),
        # Track-wrap chứa list nhân đôi → cuộn liền mạch (translateY -50%)
        html.Div(className="vss-movers-track-wrap", children=[
            html.Div(className="vss-movers-list", children=rows + rows),
        ]),
    ])


def create_banner():
    movers = _get_top_movers()
    return html.Div(id="vss-hero", children=[
        # Background layers — ảnh Trái Đất thật từ không gian (đặt file tại assets/earth-bg.jpg)
        html.Div(id="vss-hero-bg"),
        html.Div(id="vss-hero-earth-bg"),
        html.Div(id="vss-hero-grid"),
        html.Div(id="vss-orb-1"),
        html.Div(id="vss-orb-2"),
        # 2-column content
        html.Div(id="vss-hero-content", children=[
            # ── LEFT: Text ──
            html.Div(className="vss-hero-left", children=[
                html.H1(className="vss-headline", children=[
                    html.Span("Vietcap", className="vss-headline-brand"),
                    html.Span("Smart Screener", className="vss-headline-sub"),
                ]),
                html.Div(className="vss-stats", children=[
                    html.Div(className="vss-stat-card", children=[
                        html.Div(html.I(className="fas fa-file-alt"), className="vss-stat-icon"),
                        html.Div(children=[
                            html.Div("1,500+", className="vss-stat-value"),
                            html.Div("mã niêm yết", className="vss-stat-label"),
                        ], className="vss-stat-body"),
                    ]),
                    html.Div(className="vss-stat-card", children=[
                        html.Div(html.I(className="fas fa-chart-bar"), className="vss-stat-icon"),
                        html.Div(children=[
                            html.Div("165+", className="vss-stat-value"),
                            html.Div("chỉ báo định lượng", className="vss-stat-label"),
                        ], className="vss-stat-body"),
                    ]),
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
            # ── RIGHT: Card "TOP ĐỘNG" (dữ liệu thật từ data_loader) ──
            html.Div(className="vss-hero-right", children=[
                _build_top_movers_card(movers),
            ]),
        ]),
    ])


# ── MAIN HEADER ───────────────────────────────────────────────────────────────
def create_header():
    return html.Div(id="vietcap-master-header", style={"position": "relative"}, children=[
        create_topbar(),
        create_banner(),
    ])