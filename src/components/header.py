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
import os
from dash_iconify import DashIconify
sys_font = "'Inter', 'Segoe UI', system-ui, -apple-system, sans-serif"
def _get_avatar_color(name: str) -> str:
    """Màu nền avatar Google-style dựa theo chữ cái đầu tên."""
    _palette = ["#0057D9","#0057D9","#f59e0b","#8b5cf6","#ef4444","#06b6d4","#ec4899"]
    idx = ord(name.split()[-1][0].upper()) % len(_palette) if name else 0
    return _palette[idx]
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
def _create_profile_modal():
    """Popup chỉnh profile người dùng — avatar, bio, hồ sơ nhà đầu tư."""
    _avatar_templates = [f"avt_{i}" for i in range(1, 4)]
    return dbc.Modal(
        id="profile-modal",
        is_open=False,
        centered=True,
        size="md",
        contentClassName="fss-profile-modal-content",
        style={"border": "none"},
        children=[
            # ── Nút đóng ─────────────────────────────────────────────────
            html.Button(
                html.I(className="fas fa-times"),
                id="btn-close-profile",
                n_clicks=0,
                style={
                    "position": "absolute", "top": "14px", "right": "14px",
                    "background": "rgba(255,255,255,0.06)", "border": "none",
                    "color": "#9ca3af", "width": "30px", "height": "30px",
                    "borderRadius": "50%", "zIndex": "10", "cursor": "pointer",
                    "display": "flex", "alignItems": "center", "justifyContent": "center",
                },
            ),
            dbc.ModalBody([
                # ── Title ────────────────────────────────────────────────
                html.Div([
                    html.Div("Cập nhật hồ sơ nhà đầu tư",
                             style={"fontSize": "16px", "fontWeight": "700",
                                    "color": "#e5e7eb", "marginBottom": "4px"}),
                    html.Div("Cá nhân hóa trải nghiệm đầu tư của bạn",
                             style={"fontSize": "12px", "color": "#6b7280"}),
                ], style={"marginBottom": "24px", "paddingBottom": "16px",
                          "borderBottom": "1px solid rgba(255,255,255,0.06)"}),
                # ── Avatar lớn + picker ───────────────────────────────────
                html.Div([
                    # Preview avatar hiện tại
                    html.Div(id="profile-avatar-preview",
                             className="fss-profile-avatar-lg",
                             children="?"),
                    # Template picker
                    html.Div([
                        # Option: initials (Google-style)
                        html.Div(
                            id={"type": "avatar-opt", "src": "initials"},
                            className="fss-avatar-opt fss-avatar-opt--initials",
                            n_clicks=0,
                            children=html.Span(id="profile-avatar-initials-opt",
                                               style={"fontSize": "12px",
                                                      "fontWeight": "700",
                                                      "color": "#fff"}),
                        ),
                        html.Div(
                            id={"type": "avatar-opt", "src": "initials_purple"},
                            className="fss-avatar-opt fss-avatar-opt--initials",
                            n_clicks=0,
                            children=html.Span(id="profile-avatar-initials-purple",
                                               style={"fontSize": "12px",
                                                      "fontWeight": "700",
                                                      "color": "#fff"}),
                            style={"backgroundColor": "#8b5cf6"},
                        ),
                        html.Div(
                            id={"type": "avatar-opt", "src": "initials_red"},
                            className="fss-avatar-opt fss-avatar-opt--initials",
                            n_clicks=0,
                            children=html.Span(id="profile-avatar-initials-red",
                                               style={"fontSize": "12px",
                                                      "fontWeight": "700",
                                                      "color": "#fff"}),
                            style={"backgroundColor": "#ef4444"},
                        ),
                        *[
                            html.Img(
                                id={"type": "avatar-opt", "src": key},
                                src=f"/assets/avatar_templates/{key}.png",
                                className="fss-avatar-opt fss-avatar-opt--img",
                                n_clicks=0,
                            )
                            for key in _avatar_templates
                        ],
                    ], className="fss-avatar-picker"),
                    # Mock upload
                    html.Label([
                        html.I(className="fas fa-upload",
                               style={"marginRight": "6px"}),
                        "Tải ảnh lên",
                    ], className="fss-avatar-upload-btn"),
                ], className="fss-profile-avatar-section"),
                # ── Tên hiển thị (read-only) ──────────────────────────────
                html.Div([
                    html.Label("Tên hiển thị",
                               style={"fontSize": "11px", "color": "#6b7280",
                                      "fontWeight": "600", "letterSpacing": "0.05em",
                                      "textTransform": "uppercase", "marginBottom": "6px",
                                      "display": "block"}),
                    html.Div(id="profile-display-name",
                             className="fss-profile-readonly-field"),
                ], style={"marginBottom": "16px"}),
                # ── Bio ───────────────────────────────────────────────────
                html.Div([
                    html.Label("Giới thiệu",
                               style={"fontSize": "11px", "color": "#6b7280",
                                      "fontWeight": "600", "letterSpacing": "0.05em",
                                      "textTransform": "uppercase", "marginBottom": "6px",
                                      "display": "block"}),
                    dbc.Textarea(
                        id="profile-bio-input",
                        placeholder="Chia sẻ phong cách đầu tư của bạn...",
                        rows=3,
                        style={
                            "backgroundColor": "rgba(255,255,255,0.04)",
                            "border": "1px solid rgba(255,255,255,0.08)",
                            "borderRadius": "8px", "color": "#e5e7eb",
                            "fontSize": "13px", "resize": "none",
                        },
                    ),
                ], style={"marginBottom": "16px"}),
                # ── Hồ sơ nhà đầu tư (read-only từ onboarding) ───────────
                html.Div([
                    html.Label("Hồ sơ nhà đầu tư",
                               style={"fontSize": "11px", "color": "#6b7280",
                                      "fontWeight": "600", "letterSpacing": "0.05em",
                                      "textTransform": "uppercase", "marginBottom": "8px",
                                      "display": "block"}),
                    html.Div(id="profile-investor-tags",
                             className="fss-profile-investor-tags",
                             children=html.Span("Chưa thiết lập hồ sơ",
                                                style={"color": "#6b7280",
                                                       "fontSize": "12px"})),
                    dbc.Button(
                        [html.I(className="fas fa-file-pdf",
                                style={"marginRight": "6px", "color": "#ef4444"}),
                         "Tải báo cáo chi tiết hồ sơ PDF"],
                        id="btn-profile-download-pdf",
                        n_clicks=0,
                        className="",
                        style={
                            "marginTop": "12px",
                            "background": "rgba(239,68,68,0.08)",
                            "border": "1px solid rgba(239,68,68,0.25)",
                            "color": "#fca5a5",
                            "fontSize": "12px", "fontWeight": "600",
                            "fontFamily": "'Inter', sans-serif",
                            "borderRadius": "8px", "padding": "7px 16px",
                            "cursor": "pointer", "width": "100%",
                        },
                    ),
                    dcc.Download(id="ips-pdf-download-profile"),
                ], style={"marginBottom": "8px"}),
                # Store lưu avatar đang chọn tạm trong modal
                dcc.Store(id="selected-avatar-store", data="initials"),
            ], style={"padding": "32px 28px 16px"}),
            # ── Footer ───────────────────────────────────────────────────
            dbc.ModalFooter([
                dbc.Button(
                    [html.I(className="fas fa-sign-out-alt",
                            style={"marginRight": "6px"}), "Đăng xuất"],
                    id="btn-logout",
                    n_clicks=0,
                    className="",
                    style={
                        "background": "rgba(248,81,73,0.15)",
                        "border": "1px solid rgba(248,81,73,0.35)",
                        "color": "#f87171",
                        "fontSize": "11px", "fontWeight": "600",
                        "fontFamily": "'Inter', sans-serif",
                        "borderRadius": "8px", "padding": "8px 22px",
                        "cursor": "pointer",
                    },
                ),
                dbc.Button(
                    [html.I(className="fas fa-check",
                            style={"marginRight": "6px"}), "Cập nhật"],
                    id="btn-save-profile",
                    n_clicks=0,
                    className="",
                    style={
                        "background": "linear-gradient(135deg, #0057D9, #00c8ff)",
                        "border": "none",
                        "color": "#fff",
                        "fontSize": "13px", "fontWeight": "600",
                        "fontFamily": "'Inter', sans-serif",
                        "borderRadius": "8px", "padding": "8px 22px",
                        "cursor": "pointer",
                    },
                ),
                html.Div(id="profile-save-msg", style={"display": "none"}),
            ], style={
                "borderTop": "1px solid rgba(255,255,255,0.06)",
                "padding": "14px 28px",
                "display": "flex", "gap": "10px", "justifyContent": "flex-end",
            }),
        ],
    )

def _field(label, input_id, placeholder, input_type="text"):
    return html.Div([
        html.Label(label, style={
            "fontSize": "12px", "fontWeight": "600", "color": "#9ca3af",
            "marginBottom": "6px", "display": "block", "letterSpacing": "0.02em"
        }),
        dbc.Input(
            id=input_id, type=input_type, placeholder=placeholder,
            style={
                "backgroundColor": "rgba(255,255,255,0.03)",
                "border": "1px solid rgba(255,255,255,0.08)",
                "borderRadius": "8px", "padding": "10px 14px",
                "fontSize": "14px", "color": "#f3f4f6", "width": "100%",
            }
        ),
    ], style={"marginBottom": "16px"})


def _textarea_field(label, input_id, placeholder):
    return html.Div([
        html.Label(label, style={
            "fontSize": "12px", "fontWeight": "600", "color": "#9ca3af",
            "marginBottom": "6px", "display": "block", "letterSpacing": "0.02em"
        }),
        dbc.Textarea(
            id=input_id, placeholder=placeholder,
            style={
                "backgroundColor": "rgba(255,255,255,0.03)",
                "border": "1px solid rgba(255,255,255,0.08)",
                "borderRadius": "8px", "padding": "10px 14px",
                "fontSize": "14px", "color": "#f3f4f6", "minHeight": "100px",
            }
        ),
    ], style={"marginBottom": "20px"})


def _create_contact_demo_modal():
    """Popup liên hệ nhanh cho khách hàng tổ chức (B2B) — layout 2 cột kiểu WiFeed."""
    return dbc.Modal(
        id="contact-demo-modal",
        is_open=False,
        centered=True,
        size="lg",
        contentClassName="fss-contact-demo-modal-content",
        style={"border": "none"},
        children=[
            html.Button(
                html.I(className="fas fa-times"),
                id="btn-close-contact-demo", n_clicks=0,
                style={
                    "position": "absolute", "top": "16px", "right": "16px",
                    "background": "rgba(0,0,0,0.05)", "border": "none",
                    "color": "#4b5563", "width": "32px", "height": "32px",
                    "borderRadius": "50%", "zIndex": "10", "cursor": "pointer",
                    "display": "flex", "alignItems": "center", "justifyContent": "center",
                }
            ),
            html.Div(style={
                "display": "flex", "flexWrap": "wrap",
                "backgroundColor": "#030712", "borderRadius": "16px",
                "overflow": "hidden",
                "border": "1px solid rgba(255,255,255,0.08)",
                "boxShadow": "0 25px 50px -12px rgba(0, 0, 0, 0.5)"
            }, children=[
                # Cột trái: thông tin liên hệ
                html.Div(style={
                    "flex": "1 1 32%", "padding": "40px 24px 32px 24px",
                    "background": "linear-gradient(145deg, #05130a 0%, #020604 100%)",
                    "borderRight": "1px solid rgba(0, 87, 217, 0.1)",
                    "position": "relative", "overflow": "hidden",
                }, children=[
                    html.Div(style={
                        "position": "absolute", "top": "-50px", "left": "-50px",
                        "width": "160px", "height": "160px", "background": "#0057D9",
                        "filter": "blur(100px)", "opacity": "0.15", "borderRadius": "50%"
                    }),
                    html.P("Bạn đang cần truy xuất dữ liệu để phục vụ cho những phân tích của mình?",
                        style={"fontWeight": "700", "fontSize": "14px", "color": "#f9fafb", "marginBottom": "16px", "position": "relative"}),
                    html.P("Hãy liên hệ với chúng tôi để đặt lịch hẹn và thảo luận về vấn đề này hoặc bất kỳ nhu cầu thông tin nào khác bạn có.",
                        style={"fontSize": "13px", "color": "#9ca3af", "lineHeight": "1.6", "position": "relative"}),
                    html.Div([
                        html.Span("Nếu cần hỏi đáp trực tiếp, hãy liên hệ với chúng tôi:",
                                style={"fontSize": "12px", "color": "#6b7280", "display": "block", "marginBottom": "10px"}),
                        html.Div([
                            html.Div(html.I(className="fas fa-phone"), style={
                                "width": "36px", "height": "36px", "borderRadius": "50%",
                                "backgroundColor": "#0057D9", "color": "#fff",
                                "display": "flex", "alignItems": "center", "justifyContent": "center",
                            }),
                            html.Span("1900 6067", style={"fontWeight": "700", "fontSize": "15px", "color": "#f9fafb"}),
                        ], style={"display": "flex", "alignItems": "center", "gap": "10px"}),
                    ], style={"marginTop": "40px", "position": "relative"}),
                ]),
                # Cột phải: form liên hệ
                html.Div(style={"flex": "1 1 68%", "padding": "32px", "backgroundColor": "#030712"}, children=[
                    html.H4("Hãy để lại thông tin liên hệ", style={
                        "fontSize": "18px", "fontWeight": "700", "color": "#f9fafb", "marginBottom": "18px"
                    }),
                    _field("Họ và tên", "contact-demo-name", "Nhập họ và tên"),
                    _field("Số điện thoại", "contact-demo-phone", "Nhập số điện thoại"),
                    _field("Email", "contact-demo-email", "Nhập email", input_type="email"),
                    html.Div(style={"display": "flex", "gap": "16px"}, children=[
                        html.Div(_field("Công ty", "contact-demo-company", "Nhập tên công ty"), style={"flex": "1"}),
                        html.Div(_field("Chức vụ", "contact-demo-role", "Nhập chức vụ"), style={"flex": "1"}),
                    ]),
                    _textarea_field("Nhu cầu tư vấn", "contact-demo-note", "Nhập nhu cầu sản phẩm bạn mong muốn"),
                    html.Div(
                        dbc.Button(
                            "Xác Nhận",
                            id="btn-confirm-contact-demo",  # mock — chưa nối logic gửi dữ liệu đi đâu cả
                            n_clicks=0,
                            style={
                                "backgroundColor": "#fff", "color": "#030712", "fontWeight": "600",
                                "fontSize": "14px", "border": "none", "borderRadius": "8px",
                                "padding": "10px 28px",
                            }
                        ),
                        style={"textAlign": "right", "marginTop": "8px"}
                    ),
                ]),
            ]),
        ]
    )

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
                html.Div(style={"flex": "1 1 40%", "padding": "32px 32px", "display": "flex", "flexDirection": "column", "justifyContent": "center"}, children=[
                    html.Div([
                        html.Div([
                            html.I(className="fas fa-user", style={"color": "#fff", "fontSize": "16px"}),
                        ], style={
                            "width": "40px", "height": "40px",
                            "background": "linear-gradient(135deg, #0057D9, #1E88E5)",
                            "borderRadius": "10px", "display": "flex",
                            "alignItems": "center", "justifyContent": "center",
                            "boxShadow": "0 8px 16px rgba(0, 87, 217,0.25)",
                            "marginBottom": "20px",
                        }),
                        html.H2("Đăng nhập", style={"fontSize": "24px", "fontWeight": "700", "color": "#f9fafb", "marginBottom": "6px", "letterSpacing": "-0.02em"}),
                        html.P("Truy cập hệ thống dữ liệu định lượng FSS", style={"fontSize": "14px", "color": "#9ca3af", "marginBottom": "32px"}),
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
                        html.Div([
                            html.Span("Chưa có tài khoản? ", style={"color": "#6b7280"}),
                            html.A("Mở tài khoản ngay", href="https://www.vietcap.com.vn/mo-tai-khoan?language=vi", target="_blank",
                                style={"color": "#0057D9", "textDecoration": "none", "fontWeight": "600"}),
                        ]),
                        html.Br(),
                        html.Div([
                            html.Span("Group Zalo cộng đồng đầu tư định lượng: ", style={"color": "#6b7280"}),
                            html.A("Tham gia ngay", href="https://zalo.me/g/yqowtg325", target="_blank",
                                style={"color": "#003da6", "textDecoration": "none", "fontWeight": "600"})
                        ], style={"marginTop": "10px"}) # Bạn có thể chỉnh khoảng cách ở đây
                    ], style={"fontSize": "13px", "textAlign": "center", "marginTop": "24px"}),
                ]),
                # Right: Upsell
                html.Div(style={
                    "flex": "1 1 55%", "padding": "32px 32px",
                    "background": "linear-gradient(145deg, #05130a 0%, #020604 100%)",
                    "borderLeft": "1px solid rgba(0, 87, 217, 0.1)",
                    "position": "relative", "overflow": "hidden"
                }, children=[
                    html.Div(style={
                        "position": "absolute", "top": "-50px", "right": "-50px",
                        "width": "200px", "height": "200px", "background": "#0057D9",
                        "filter": "blur(100px)", "opacity": "0.15", "borderRadius": "50%"
                    }),
                    html.Div("NÂNG TẦM CHIẾN LƯỢC ĐẦU TƯ", style={
                        "fontSize": "11px", "fontWeight": "800", "color": "#0057D9",
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
                            "backgroundColor": "rgba(0, 87, 217, 0.05)",
                            "borderRadius": "12px", "border": "1px solid rgba(0, 87, 217, 0.3)",
                            "boxShadow": "0 10px 30px -10px rgba(0, 87, 217, 0.2)",
                            "position": "relative", "display": "flex", "flexDirection": "column"
                        }, children=[
                            html.Div("✦ PRO PLAN", style={
                                "position": "absolute", "top": "-10px", "left": "50%",
                                "transform": "translateX(-50%)",
                                "background": "linear-gradient(90deg, #0057D9, #1E88E5)",
                                "color": "#ffffff", "fontSize": "10px", "fontWeight": "800",
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
                                "padding": "11px 0",
                                "background": "linear-gradient(135deg, #F9A11B, #F57C00)",
                                "color": "#ffffff", "fontWeight": "700", "fontSize": "13.5px",
                                "borderRadius": "6px", "textDecoration": "none",
                                "border": "none", "transition": "all 0.2s",
                                "boxShadow": "0 4px 14px rgba(245, 124, 0, 0.35)",
                            }),
                            # ── Ô nhập mã kích hoạt ──
                            html.Div([
                                html.Div("Đã có mã kích hoạt?",
                                        style={"fontSize": "11px", "color": "#6b7280",
                                                "marginBottom": "6px"}),
                                html.Div([
                                    dbc.Input(
                                        id="invite-code-input",
                                        placeholder="FSS-...",
                                        style={
                                            "flex": "1",
                                            "backgroundColor": "rgba(255,255,255,0.05)",
                                            "border": "1px solid rgba(0, 87, 217,0.3)",
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
                                            "backgroundColor": "#0057D9",
                                            "border": "none",
                                            "borderRadius": "0 6px 6px 0",
                                            "color": "#ffffff",
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
                                "backgroundColor": "rgba(0, 87, 217,0.05)",
                                "border": "1px solid rgba(0, 87, 217,0.15)",
                                "borderRadius": "8px",
                                "padding": "12px 14px",
                                "marginBottom": "12px",
                            }),
                        ]),
                    ]),
                    # ── THÊM KHỐI B2B ENTERPRISE Ở ĐÂY ──
                    html.Div(style={
                        "marginTop": "24px", 
                        "padding": "16px",
                        "backgroundColor": "rgba(255, 255, 255, 0.02)",
                        "border": "1px dashed rgba(255, 255, 255, 0.15)",
                        "borderRadius": "8px",
                        "transition": "all 0.2s"
                    }, className="b2b-hover-box", children=[
                        html.Div([
                            html.Span("GIẢI PHÁP ENTERPRISE & WHITE-LABEL", style={
                                "fontSize": "11px", "fontWeight": "800", 
                                "color": "#9ca3af", "letterSpacing": "0.1em"
                            }),
                        ], style={"marginBottom": "8px"}),
                        html.Div([
                            html.Span("Tích hợp API, Export Data thô & Báo cáo cho Định chế tài chính.", 
                                      style={"fontSize": "12px", "color": "#6b7280", "flex": "1"}),
                            html.Span([
                                "Liên hệ ",
                                html.I(className="fas fa-phone-volume", style={"marginLeft": "2px"}),
                            ], id="btn-open-contact-demo", n_clicks=0, style={
                                "marginLeft": "16px", "fontSize": "12px", "fontWeight": "700",
                                "color": "#00e676", "textDecoration": "none", "whiteSpace": "nowrap",
                                "cursor": "pointer", "display": "inline-flex", "alignItems": "center", "gap": "4px",
                            })
                        ], style={"display": "flex", "alignItems": "center"})
                    ])
                    # ── KẾT THÚC KHỐI B2B ──

                ]) # Kết thúc phần Right: Upsell
            ])
        ]
    )
# ── Vietcap coin illustration (inline SVG) ────────────────────────────────────
def _create_coin_svg():
    """
    3D coin / disc SVG illustration loaded via external file.
    (Hiện không dùng trong hero — giữ lại để tái sử dụng nếu cần.)
    """
    return html.Div(className="fss-coin-wrap", children=[
        html.Img(src="/assets/coin.svg", className="fss-coin-svg", style={"width": "100%", "height": "100%"})
    ])


def _notif_card_v2(category: str, cat_color: str, title: str, detail: str,
                    date_str: str, is_unread: bool = True, idx: int = 0,
                    cta_text: str = None, id_tag: str = None,
                    note_text: str = None) -> html.Div:
    card_id = id_tag if id_tag else {"type": "notif-card", "idx": idx}

    detail_kwargs = {"className": "fss-notif-card-detail"}
    title_kwargs  = {"className": "fss-notif-card-title"}
    date_kwargs   = {"className": "fss-notif-card-date"}
    if id_tag:
        detail_kwargs["id"] = f"{id_tag}-detail"
        title_kwargs["id"]  = f"{id_tag}-title"
        date_kwargs["id"]   = f"{id_tag}-date"

    extra_attrs = {}
    if id_tag == "strategy-match":
        extra_attrs["data-dismissed"] = "0"

    body_children = [html.Div(detail, **detail_kwargs)]
    if cta_text:
        body_children.append(html.Span(cta_text, className="fss-notif-card-cta"))
    if note_text:
        note_kwargs = {"className": "fss-notif-card-note"}
        if id_tag:
            note_kwargs["id"] = f"{id_tag}-note"
        body_children.append(html.Div(note_text, **note_kwargs))

    return html.Div(
        id=card_id,
        n_clicks=0,
        className=f"fss-notif-card {'is-unread' if is_unread else ''}",
        children=[
            html.Div(className="fss-notif-card-inner", children=[
                html.Span(category, className=f"fss-notif-cat fss-notif-cat--{cat_color}"),
                html.Div(className="fss-notif-card-top", children=[
                    html.Div(title, **title_kwargs),
                    html.Button(
                        html.I(className="fas fa-times"),
                        id={"type": "notif-dismiss", "idx": idx},
                        n_clicks=0,
                        className="fss-notif-card-dismiss",
                    ),
                ]),
                html.Div(body_children, className="fss-notif-card-body"),
                html.Div(date_str, **date_kwargs),
            ]),
        ],
        **extra_attrs,
    )


def _notif_card_bctc(category: str, cat_color: str, title: str,
                      preview: str, full: str, date_str: str,
                      is_unread: bool, idx: int, id_tag: str) -> html.Div:
    return html.Div(
        id=id_tag,
        n_clicks=0,
        className=f"fss-notif-card {'is-unread' if is_unread else ''}",
        children=[
            html.Div(className="fss-notif-card-inner", children=[
                html.Span(category, className=f"fss-notif-cat fss-notif-cat--{cat_color}"),
                html.Div(className="fss-notif-card-top", children=[
                    html.Div(title, className="fss-notif-card-title"),
                    html.Button(
                        html.I(className="fas fa-times"),
                        id={"type": "notif-dismiss", "idx": idx},
                        n_clicks=0,
                        className="fss-notif-card-dismiss",
                    ),
                ]),
                html.Div(className="fss-notif-card-body", children=[
                    html.Div(preview, id=f"{id_tag}-preview",
                             className="fss-notif-card-detail"),
                    html.Div(full, id=f"{id_tag}-full",
                             className="fss-notif-card-detail",
                             style={"display": "none"}),
                    html.Button(
                        "Xem thêm →",
                        id={"type": "notif-expand-btn", "tag": id_tag},
                        n_clicks=0,
                        className="fss-notif-expand-btn",
                    ),
                ]),
                html.Div(date_str, className="fss-notif-card-date"),
            ]),
        ],
    )

def _create_notification_panel():
    """Panel thông báo — 6 loại theo đề xuất UX, BCTC gộp 2 card ở cuối."""

    notifs = [
        # ── 1. Strategy Match (TẠM MOCK — sẽ nối động sau khi có strategy_callbacks.py) ──
        dict(category="STRATEGY", cat_color="cyan",
             title="Chọn một trường phái đầu tư để xem gợi ý",
             detail="Chưa có chiến lược nào được áp dụng.",
             date="—", unread=False, id_tag="strategy-match",
             note="Kết quả được tính trên toàn bộ thị trường, không phụ thuộc chế độ đang chọn."),

        # ── 2. FSS Score Change ────────────────────────────────────────
        dict(category="SCORE", cat_color="blue",
             title="FSS Score của MBB thay đổi",
             detail="82 → 87 sau khi cập nhật dữ liệu tài chính mới.",
             date="01/09/2026 · 14:50", unread=True,
             cta="Xem nguyên nhân"),

        # ── 3. Saved Screener ──────────────────────────────────────────
        dict(category="SÀNG LỌC", cat_color="cyan",
             title="7 mã mới thỏa bộ lọc \u201cTích sản\u201d",
             detail="FPT, MBB, VCG, HPG, TPB, ACB, VHM",
             date="01/09/2026 · 15:05", unread=True,
             cta="Xem 7 mã"),

        # ── 4. Price / Technical Alert ─────────────────────────────────
        dict(category="ALERT", cat_color="amber",
             title="FPT đạt điều kiện cảnh báo",
             detail="Giá vượt SMA20 · Khối lượng = 2,1× trung bình 20 phiên",
             date="01/09/2026 · 14:45", unread=False),

        # ── 5. Data Quality ─────────────────────────────────────────────
        dict(category="DATA", cat_color="red",
             title="Dữ liệu VHM đang chậm cập nhật",
             detail="Nguồn dữ liệu chính chưa phản hồi. FSS đang dùng dữ liệu gần nhất đã xác thực.",
             date="01/09/2026 · 16:05", unread=False),

        # ── 6+7. BCTC — GỘP THÀNH 2 CARD Ở CUỐI ──────────────────────
        dict(category="DỮ LIỆU", cat_color="gray",
             title="26 doanh nghiệp vừa cập nhật BCTC bán niên 2026",
             detail_preview="HPW, SKV, HAP...",
             detail_full="HPW, SKV, HAP, VNP, HII, TSC, TLH, ICT, HHP, ITC, CKG, DTD, VTO, SGN, "
                         "HPX, RAL, IDI, LBM, SGR, ANT, HDC, DCL, VC3, PTB, DPG, AAA",
             date="31/08/2026 · 09:00", unread=False, id_tag="bctc-half-year"),
        dict(category="DỮ LIỆU", cat_color="gray",
             title="18 doanh nghiệp vừa cập nhật BCTC quý 2/2026",
             detail_preview="GEE, SAB, KDH...",
             detail_full="GEE, SAB, KDH, KBC, CII, OIL, VEA, CTR, DGW, PAN, ELC, AST, SAM, CTF, "
                         "HDC, DCL, VC3, PTB",
             date="28/08/2026 · 09:00", unread=False, id_tag="bctc-q2"),
    ]

    return html.Div(
        id="fss-notif-panel",
        className="fss-notif-panel",
        style={"display": "none"},
        children=[
            dcc.Store(id="strategy-match-ticker-store", data=None),   # ← THÊM DÒNG NÀY
            html.Div(className="fss-notif-panel-header", children=[
                html.Span("Thông báo", className="fss-notif-panel-title"),
                html.Button(
                    html.I(className="fas fa-check-double"),
                    id="btn-notif-mark-all-read",
                    n_clicks=0,
                    className="fss-notif-panel-mark-all",
                    title="Đánh dấu tất cả đã đọc",
                ),
            ]),
            html.Div(className="fss-notif-tabs", children=[
                html.Button("Tất cả", id="notif-tab-all", n_clicks=0,
                            className="fss-notif-tab is-active"),
                html.Button("Chưa đọc", id="notif-tab-unread", n_clicks=0,
                            className="fss-notif-tab"),
            ]),
            html.Div(
                id="fss-notif-list",
                className="fss-notif-list",
                children=[
                    # ── Welcome / Tour Guide card — luôn ở đầu ──────────
                    html.Div(
                        id="notif-welcome-tour",
                        n_clicks=0,
                        className="fss-notif-card fss-notif-card--tour",
                        children=[
                            html.Div(className="fss-notif-card-inner", children=[
                                html.Span("CHÀO MỪNG", className="fss-notif-cat fss-notif-cat--cyan"),
                                html.Div(className="fss-notif-card-top", children=[
                                    html.Div([
                                        html.I(className="fas fa-play-circle",
                                               style={"marginRight": "8px", "color": "#4A90E2"}),
                                        "Xem hướng dẫn sử dụng hệ thống FSS",
                                    ], className="fss-notif-card-title"),
                                ]),
                                html.Div("Khám phá nhanh các tính năng chính của FinSmartScreener trong 60 giây.",
                                         className="fss-notif-card-detail"),
                                html.Div("Nhấn để bắt đầu →", className="fss-notif-card-cta"),
                            ]),
                        ],
                    ),
                ] + [
                    _notif_card_bctc(
                        category=n["category"], cat_color=n["cat_color"],
                        title=n["title"], preview=n["detail_preview"],
                        full=n["detail_full"], date_str=n["date"],
                        is_unread=n["unread"], idx=i, id_tag=n["id_tag"],
                    ) if "detail_preview" in n else
                    _notif_card_v2(
                        category=n["category"], cat_color=n["cat_color"],
                        title=n["title"], detail=n["detail"],
                        date_str=n["date"], is_unread=n["unread"], idx=i,
                        cta_text=n.get("cta"), id_tag=n.get("id_tag"),
                        note_text=n.get("note"),
                    )
                    for i, n in enumerate(notifs)
                ],
            ),
        ],
    )


# ── TOPBAR ────────────────────────────────────────────────────────────────────
def create_topbar(id_suffix=""):
    wrapper_id = f"vietcap-topbar{id_suffix}" if id_suffix else "vietcap-topbar-only"
    # Cụm Theme Switcher "Pro"
    theme_switch = html.Div(
        [
            # Icon Mặt trời (Light Mode)
            DashIconify(
                icon="line-md:sun-twotone", 
                width=22, 
                color="#F5A623" # Màu vàng cam sang trọng
            ), 
            
            # Toggle chính
            dbc.Switch(
                id="theme-switch-button",
                value=True,  # True = Dark mode đang kích hoạt
                className="mx-2", # Cấp margin trái/phải bằng Bootstrap
                style={
                    "cursor": "pointer", 
                    "marginBottom": "0",
                    "transform": "scale(1.2)" # Phóng to công tắc lên một chút cho dễ bấm
                }
            ),
            
            # Icon Mặt trăng (Dark Mode)
            DashIconify(
                icon="line-md:moon-twotone", 
                width=22, 
                color="#4A90E2" # Màu xanh Fintech
            ), 
        ],
        className="d-flex align-items-center justify-content-center",
        style={
            # Hiệu ứng Glassmorphism (Kính mờ) tạo cảm giác cao cấp
            "backgroundColor": "rgba(255, 255, 255, 0.05)", 
            "padding": "6px 14px",
            "borderRadius": "30px", # Bo tròn dạng viên thuốc (Pill)
            "border": "1px solid rgba(255, 255, 255, 0.1)", # Viền mờ bắt sáng
            "marginRight": "16px",
            "boxShadow": "0 4px 6px rgba(0, 0, 0, 0.1)" # Đổ bóng nhẹ tạo chiều sâu
        }
    )
    scroll_script = html.Script("")
    return html.Div(id=wrapper_id, children=[
        dcc.Store(id='auth-store', storage_type='local', data={"logged_in": False}),
        dcc.Store(id='user-phone-store', storage_type='session', data=None),
        _create_login_modal(),
        _create_contact_demo_modal(),
        scroll_script,
        html.Div(id="fss-sticky-nav", children=[
            html.Div(className="fss-nav-inner", children=[
                # Logo
                html.A([
                    html.Span("Vietcap", className="fss-logo-text"),
                    html.Span("▲", className="fss-logo-accent", style={
                        "fontSize": "10px", "marginLeft": "2px",
                        "verticalAlign": "super", "fontStyle": "normal",
                    }),
                ], href="#faq-section", target="_blank",
                    style={"textDecoration": "none", "display": "flex", "alignItems": "center"}),
                # Nav links
                html.Div([
                    html.A("Về chúng tôi", href="#faq-section", className="vietcap-nav-link"),
                    html.A("Dịch vụ", href="#faq-section", className="vietcap-nav-link"),
                    html.A("Sản phẩm", href="#screener-scroll-anchor", className="vietcap-nav-link"),
                    html.A("Truyền thông", href="#faq-section", className="vietcap-nav-link"),
                    html.A("Screener", href="#screener-scroll-anchor", className="vietcap-nav-link vietcap-nav-screener"),
                ], className="d-flex align-items-center gap-4"),
                # Auth area
                html.Div([
                    theme_switch,
                    # Nút đăng nhập (chưa login)
                    dbc.Button(
                        [html.I(className="fas fa-sign-in-alt",
                                style={"marginRight": "6px"}), "Đăng nhập"],
                        id="btn-login", n_clicks=0,
                        className="vietcap-nav-login-btn",
                        style={
                            "backgroundColor": "transparent",
                            "border": "1px solid rgba(255,255,255,0.2)",
                            "color": "rgba(255,255,255,0.85)",
                            "fontSize": "13px", "fontWeight": "500",
                            "padding": "6px 16px", "borderRadius": "6px",
                        },
                    ),
                    # Avatar button (hiện sau khi login, ẩn khi chưa login)
                    html.Button(
                        id="btn-user-avatar",
                        n_clicks=0,
                        className="fss-nav-avatar-btn",
                        style={"display": "none"},
                        children=[
                            html.Div(id="navbar-avatar-circle",
                                     className="fss-nav-avatar-circle",
                                     children="?"),
                            html.Div(id="navbar-user-name",
                                     style={"fontSize": "13px",
                                            "color": "#d1d5db",
                                            "fontWeight": "500"}),
                            html.Span(id="navbar-vip-badge",
                                      children="VIP",
                                      className="vip-badge",
                                      style={"display": "none"}),
                        ],
                    ),
                    # btn-logout-wrap giữ lại (hidden) để không vỡ callback cũ
                    html.Div(id="btn-logout-wrap", style={"display": "none"}),
                    # Notification bell — CHỈ render ở lần gọi chính (tránh duplicate id)
                    *([html.Div(className="fss-notif-bell-wrap", children=[
                        html.Button(
                            id="btn-notif-bell",
                            n_clicks=0,
                            className="fss-notif-bell-btn",
                            children=[
                                html.I(className="fas fa-bell"),
                                html.Span(id="notif-dot", className="fss-notif-dot"),
                            ],
                        ),
                        _create_notification_panel(),
                    ])] if not id_suffix else []),
                    # Profile modal
                    _create_profile_modal(),
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
            "backgroundColor": "var(--bg-base)",
            "borderBottom": "1px solid var(--border-subtle)",  # Tương tự cho màu viền
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
        # ── Lọc chỉ lấy mã trong rổ VN100 ──
        try:
            from src.backend.data_loader import fetch_index_constituents
            vn100_tickers, _err = fetch_index_constituents("VN100")
            if vn100_tickers:
                df = df[df["Ticker"].isin(vn100_tickers)]
        except Exception:
            pass  # nếu API lỗi thì dùng toàn bộ snapshot, không crash
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
            {"ticker": "VCB",  "pct": 4.9,  "price": "92,100",  "up": True},
            {"ticker": "FPT",  "pct": 3.8,  "price": "140,200", "up": True},
            {"ticker": "HPG",  "pct": 4.1,  "price": "28,500",  "up": True},
            {"ticker": "MBB",  "pct": 2.7,  "price": "25,300",  "up": True},
            {"ticker": "TCB",  "pct": 3.3,  "price": "24,100",  "up": True},
            {"ticker": "VNM",  "pct": 6.9,  "price": "61,000",  "up": True},
            {"ticker": "SSI",  "pct": -2.4, "price": "32,000",  "up": False},
            {"ticker": "DXG",  "pct": -3.1, "price": "12,800",  "up": False},
            {"ticker": "NVL",  "pct": -4.5, "price": "7,500",   "up": False},
            {"ticker": "PDR",  "pct": -2.8, "price": "9,200",   "up": False},
        ]
def _build_top_movers_card(movers):
    """Tạo card 'TOP ĐỘNG' tĩnh (kiểu bảng nhỏ góc phải hero), lấy dữ liệu
    thật từ _get_top_movers(). Thay cho globe SVG + ticker marquee cũ —
    giờ nền hero dùng ảnh thật Trái Đất chụp từ không gian (assets/earth-bg.jpg)
    nên không cần dựng quả cầu giả lập nữa."""
    def _row(m):
        color = "var(--fss-term-green)" if m["up"] else "var(--fss-term-red)"
        sign = "+" if m["up"] else ""
        return html.Div(className="fss-mover-row", children=[
            html.Span(m["ticker"], className="fss-mover-ticker"),
            html.Span(m["price"], className="fss-mover-price"),
            html.Span(f"{sign}{m['pct']:.2f}", className="fss-mover-pct", style={"color": color}),
        ])
    rows = [_row(m) for m in movers]
    return html.Div(className="fss-movers-card", children=[
        # Header cố định — KHÔNG nằm trong track-wrap nên không bị cuộn
        html.Div(className="fss-movers-header", children=[
            html.Span("TOP MÃ BIẾN ĐỘNG - VN100", className="fss-movers-title"),
            html.Div(className="fss-movers-status", children=[
                html.Span(className="fss-movers-status-dot"),
                html.Span("Dữ liệu cuối phiên"),
            ]),
        ]),
        html.Div(className="fss-movers-col-header", children=[
            html.Span("Mã CK", className="fss-mover-col-ticker"),
            html.Span("Giá", className="fss-mover-col-price"),
            html.Span("%", className="fss-mover-col-pct"),
        ]),
        # Track-wrap chứa list nhân đôi → cuộn liền mạch (translateY -50%)
        html.Div(className="fss-movers-track-wrap", children=[
            html.Div(className="fss-movers-list", children=rows + rows),
        ]),
    ])
def _build_ticker_tape(movers):
    """Dải ticker chạy ngang full-width ngay dưới navbar — dùng CHÍNH dữ liệu
    thật từ _get_top_movers() (không phải trang trí giả), nhân đôi để cuộn
    liền mạch giống bảng điện sàn giao dịch thật."""
    def _chip(m):
        color = "var(--fss-term-green)" if m["up"] else "var(--fss-term-red)"
        arrow = "▲" if m["up"] else "▼"
        sign = "+" if m["up"] else ""
        return html.Div(className="fss-tape-chip", children=[
            html.Span(m["ticker"], className="fss-tape-ticker"),
            html.Span(m["price"], className="fss-tape-price"),
            html.Span(f"{arrow} {sign}{m['pct']:.2f}%", className="fss-tape-pct", style={"color": color}),
        ])
    chips = [_chip(m) for m in movers]
    return html.Div(id="fss-ticker-tape", children=[
        html.Div(className="fss-tape-track", children=chips + chips),
    ])
def create_banner():
    """[BƯỚC 1] Home Hero — nền để trong suốt để hero-wrap phía ngoài
    (vietcap-header-bg-wrap) lộ background GIF ra qua CSS ::before."""
    return html.Div(
        id="home-hero",
        className="home-hero",
        style={"backgroundColor": "transparent"},
        children=[
            html.H1("Fin Smart Screener", className="home-hero-title"),
            html.P(
                [
                    "Từ 1.500+ cổ phiếu đến shortlist phù hợp chiến lược đầu tư của bạn.",
                    html.Br(),
                    html.Div([
                        html.Button("193 chỉ số định lượng", 
                                id="hero-metrics-btn", 
                                n_clicks=0,
                                style={
                                    "background": "none", "border": "none", "padding": "0",
                                    "color": "inherit", "fontSize": "inherit", "fontFamily": "inherit",
                                    "fontStyle": "italic", "cursor": "pointer", 
                                    "textDecoration": "underline", "textDecorationColor": "rgba(255,255,255,0.3)",
                                    "margin": "0", "lineHeight": "inherit",
                                    "font-weight": "inherit",
                                }),
                        " · ",
                        html.Button("10 trường phái đầu tư",
                                id="hero-schools-btn",
                                n_clicks=0,
                                style={
                                    "background": "none", "border": "none", "padding": "0",
                                    "color": "inherit", "fontSize": "inherit", "fontFamily": "inherit",
                                    "fontStyle": "italic", "cursor": "pointer", 
                                    "textDecoration": "underline", "textDecorationColor": "rgba(255,255,255,0.3)",
                                    "margin": "0", "lineHeight": "inherit",
                                    "font-weight": "inherit",
                                }),
                        " · ",
                        html.Button("AI hỗ trợ diễn giải",
                                id="hero-ai-chat-btn",
                                n_clicks=0,
                                style={
                                    "background": "none", "border": "none", "padding": "0",
                                    "color": "inherit", "fontSize": "inherit", "fontFamily": "inherit",
                                    "fontStyle": "italic", "cursor": "pointer", 
                                    "textDecoration": "underline", "textDecorationColor": "rgba(255,255,255,0.3)",
                                    "margin": "0", "lineHeight": "inherit",
                                    "font-weight": "inherit",
                                }),
                    ], style={"display": "inline"})
                ],
                className="home-hero-desc",
            ),
            html.Div(
                style={
                    "display": "flex",
                    "justifyContent": "center",
                    "alignItems": "center",
                    "gap": "10px",
                    "flexWrap": "nowrap",
                    "marginTop": "8px",
                    "marginBottom": "8px",
                    "width": "100%"
                },
                children=[
                    html.Div(
                        className="home-hero-search",
                        style={
                            "width": "100%",
                            "maxWidth": "450px"
                        },
                        children=[
                            dcc.Input(
                                id="home-hero-search-input",
                                type="text",
                                placeholder="Tìm mã cổ phiếu (VCB, FPT, HPG,...)",
                                className="home-hero-search-input",
                                debounce=True,
                                autoComplete="off",
                                style={"width": "100%"}
                            ),
                            html.Button(
                                html.I(className="fa-solid fa-arrow-right"),
                                id="home-hero-search-submit",
                                className="home-hero-search-btn",
                                n_clicks=0,
                                title="Tìm kiếm",
                            ),
                        ]
                    ),
                    html.A(
                        href="#screener-scroll-anchor",
                        style={"textDecoration": "none"},
                        children=[
                            html.Button(
                                [
                                    html.I(className="fa-solid fa-filter", style={"marginRight": "8px"}),
                                    "Tự Xây Bộ Lọc"
                                ],
                                className="fss-tour-pulse",
                                style={
                                    "padding": "12px 24px",
                                    "fontSize": "16px",
                                    "cursor": "pointer",
                                    "height": "100%",
                                    "display": "flex",
                                    "alignItems": "center",
                                    "whiteSpace": "nowrap"
                                }
                            )
                        ]
                    )
                ]
            ),
        ]
    )
# ── [BƯỚC 2] MARKET OVERVIEW — 4 thẻ chỉ số ngang ──────────────────────────────
def _market_change_badge(change_pct: float = None):
    """Badge % cho 3 thẻ chỉ số (VN-INDEX/HNX-INDEX/VN30-INDEX).

    LƯU Ý: quant_engine.py KHÔNG có hàm "badge" riêng cho market index — file
    đó chỉ có công thức % thay đổi chuẩn dùng cho CỔ PHIẾU:
        _prev_close = df_px.groupby('Ticker')['Price Close'].shift(1)
        change_pct  = (close - _prev_close) / _prev_close * 100
    (xem calculate_sbs_snapshot() trong quant_engine.py). Với index cũng áp
    dụng đúng công thức % thay đổi chuẩn này (chỉ khác input là giá đóng cửa
    chỉ số thay vì giá cổ phiếu) — không bịa quy ước riêng.

    Class CSS "is-positive"/"is-negative" lấy đúng theo quy ước ĐÃ CÓ SẴN ở
    _pick_card() (biến change_cls) trong cùng file header.py, để đồng bộ toàn
    app thay vì tạo class mới.

    Trả về (label, css_class). label=None khi chưa có dữ liệu -> badge để
    trống, giữ đúng hành vi placeholder cũ.
    """
    base_cls = "home-market-badge"
    if change_pct is None or (isinstance(change_pct, float) and pd.isna(change_pct)):
        return None, base_cls
    if change_pct > 0:
        return f"+{change_pct:.2f}%", f"{base_cls} is-positive"
    if change_pct < 0:
        return f"{change_pct:.2f}%", f"{base_cls} is-negative"
    return "0.00%", f"{base_cls} is-flat"


def _market_index_card(key: str, label: str, change_pct: float = None,
                        value_str: str = None, pts_str: str = None) -> html.Div:
    """1 thẻ chỉ số (VN-INDEX / HNX-INDEX / VN30-INDEX).
    key dùng làm hậu tố id, vd key='vnindex' -> home-mkt-vnindex-value...

    [ĐÃ NỐI BADGE] change_pct/value_str/pts_str đều optional (mặc định None)
    để KHÔNG phá code cũ — create_market_overview() hiện gọi hàm này không
    kèm data, nên hành vi placeholder "—" / badge rỗng vẫn giữ nguyên y hệt
    trước đây, và callback (home_callbacks.py) vẫn Output vào đúng các id bên
    dưới như cũ. Nếu sau này muốn render sẵn phía server, chỉ cần gọi kèm
    change_pct=... (và value_str/pts_str nếu có) — badge sẽ tự tính đúng nhãn
    +/-/flat qua _market_change_badge() ở trên.
    """
    badge_label, badge_class = _market_change_badge(change_pct)
    return html.Div(id=f"home-mkt-{key}-card", className="home-market-card", children=[
        html.Div(className="home-market-card-top", children=[
            html.Span(label, className="home-market-card-label"),
            html.Span(badge_label, id=f"home-mkt-{key}-badge", className=badge_class),
        ]),
        html.Div(value_str if value_str is not None else "—",
                 id=f"home-mkt-{key}-value", className="home-market-card-value"),
        html.Div(pts_str, id=f"home-mkt-{key}-pts", className="home-market-card-pts"),
        dcc.Graph(
            id=f"home-mkt-{key}-spark",
            className="home-market-card-spark",
            figure={},
            config={"staticPlot": True, "displayModeBar": False},
        ),
    ])
def _market_volume_card() -> html.Div:
    """Thẻ TOTAL VOLUME — khác 3 thẻ index ở chỗ badge là nhãn xu hướng
    (vd 'Avg. High') thay vì %, và biểu đồ mini là bar chart thay vì line."""
    return html.Div(id="home-mkt-volume-card", className="home-market-card", children=[
        html.Div(className="home-market-card-top", children=[
            html.Span("TỔNG GT GIAO DỊCH", className="home-market-card-label"),
            html.Span(id="home-mkt-volume-badge", className="home-market-badge"),
        ]),
        html.Div(id="home-mkt-volume-value", className="home-market-card-value", children="—"),
        dcc.Graph(
            id="home-mkt-volume-spark",
            className="home-market-card-spark",
            figure={},
            config={"staticPlot": True, "displayModeBar": False},
        ),
    ])
def create_market_overview() -> html.Div:
    """Grid ngang 4 cột: VN-INDEX, HNX-INDEX, VN30-INDEX, TOTAL VOLUME."""
    return html.Div(id="home-market-overview", className="home-market-grid", children=[
        _market_index_card("vnindex", "VN-INDEX"),
        
        _market_index_card("vn30index", "VN30-INDEX"),

        _market_index_card("hnxindex", "HNX-INDEX"),
        _market_volume_card(),
    ])
# ── [BƯỚC 3] TOP FIN PICKS + MARKET PULSE — layout 65/35 ──────────────────────
_PICK_TAGS = {
    # variant: (nhãn hiển thị, biến CSS màu tái dùng từ design token có sẵn)
    "growth":   ("GROWTH",   "positive"),   # xanh lá — dùng chung --positive
    "value":    ("VALUE",    "accent"),     # xanh dương — dùng chung --accent
    "momentum": ("MOMENTUM", "warning"),    # cam — dùng chung --warning
}
def _pick_tag(variant: str) -> html.Span:
    label, _ = _PICK_TAGS[variant]
    return html.Span(label, className=f"home-pick-tag home-pick-tag-{variant}")


def _star_row(filled: int = 5, total: int = 5) -> html.Div:
    stars = []
    for i in range(total):
        is_filled = i < filled
        stars.append(html.I(className=f"fa-{'solid' if is_filled else 'regular'} fa-star"))
    return html.Div(stars, className="home-pick-card-stars")


def _score_bar(label: str, value) -> html.Div:
    """1 mục breakdown điểm — NEUTRAL, không còn màu riêng theo loại."""
    v = int(value) if value is not None else 0
    return html.Div(className="home-pick-score-item", children=[
        html.Span(label, className="home-pick-score-label"),
        html.Span(str(v), className="home-pick-score-value"),
    ])


def _infer_pick_tag(value_score=None, growth_score=None, momentum_score=None) -> str:
    """Chọn tag_variant (value/growth/momentum) cho _pick_card dựa trên thành
    phần VGM cao nhất — đúng theo cách quant_engine.py tính (Value_Score_Pct,
    Growth_Score_Pct, Momentum_Score_Pct — đều thang 0-100, xem
    calculate_value_score/calculate_growth_score/calculate_momentum_score).
    Cổ phiếu vào Top Quant Scores vì mạnh nhất ở thành phần nào thì gắn tag
    thành phần đó (vd Value 86 · Growth 72 · Momentum 77 -> tag "value").
    """
    scores = {"value": value_score, "growth": growth_score, "momentum": momentum_score}
    scores = {k: v for k, v in scores.items()
              if v is not None and not (isinstance(v, float) and pd.isna(v))}
    if not scores:
        return "value"  # fallback an toàn khi thiếu cả 3 điểm, tránh KeyError ở _PICK_TAGS
    return max(scores, key=scores.get)


def _pick_card(key: str, ticker: str, tag_variant: str = None, price_str: str = "—",
                change_str: str = "", is_positive: bool = True, stars_filled: int = 5,
                value_score: float = None,
                growth_score: float = None,
                momentum_score: float = None,
                insight_text: str = None) -> html.Div:
    """1 thẻ trong Top Quant Scores.
    [BƯỚC 3.3] Giảm rainbow effect:
      - Điểm trung bình (avg của Value/Growth/Momentum) đặt cạnh ticker,
        dùng màu accent — đây là điểm nổi bật duy nhất ngoài badge/CTA màu.
      - Breakdown 3 điểm thành phần chuyển NEUTRAL (label xám, số trắng),
        không còn 3 màu khác nhau.
      - Bỏ nút "Xem vì sao" — TOÀN BỘ CARD giờ clickable (n_clicks ở
        chính html.Div card), icon '›' chỉ hiện khi hover qua CSS.

    [ĐÃ NỐI TAG] tag_variant giờ optional — nếu người gọi (home_callbacks.py)
    vẫn truyền tag_variant tường minh như cũ thì giữ nguyên giá trị đó (không
    đổi hành vi cũ). Nếu KHÔNG truyền (None), tự suy ra bằng _infer_pick_tag()
    dựa trên value_score/growth_score/momentum_score — đúng điểm thành phần
    cao nhất theo quant_engine.py.
    """
    if tag_variant is None:
        tag_variant = _infer_pick_tag(value_score, growth_score, momentum_score)

    change_cls = "home-pick-card-change is-positive" if is_positive else "home-pick-card-change is-negative"

    # Điểm trung bình 3 sub-score — hiển thị cạnh ticker
    sub_scores = [s for s in [value_score, growth_score, momentum_score] if s is not None]
    avg_score = round(sum(sub_scores) / len(sub_scores)) if sub_scores else None

    children = [
        html.Div(className="home-pick-card-top", children=[
            _pick_tag(tag_variant),
            html.Span(
                # f"{avg_score}" if avg_score is not None else "—",
                f"" if avg_score is not None else "", # tam thoi an diem so di nhin dep hon
                className="home-pick-card-avgscore-inline",
            ),
            _star_row(filled=stars_filled),
        ]),
        html.Div(ticker, className="home-pick-card-ticker"),
    ]
    if insight_text:
        children.append(html.Div(insight_text, className="home-pick-card-insight"))

    children.append(html.Div(className="home-pick-card-bottom", children=[
        html.Div(price_str, className="home-pick-card-price"),
        html.Div(change_str, className=change_cls),
    ]))

    # ── Breakdown — NEUTRAL, không màu riêng theo loại ──────────────────
    children.append(html.Div(className="home-pick-score-breakdown", children=[
        _score_bar("Value",    value_score),
        html.Span("·", className="home-pick-score-dot"),
        _score_bar("Growth",   growth_score),
        html.Span("·", className="home-pick-score-dot"),
        _score_bar("Momentum", momentum_score),
    ]))

    return html.Div(
        id={"type": "pick-card-click", "ticker": ticker},
        n_clicks=0,
        className="home-pick-card home-pick-card-clickable",
        children=children,
    )


def create_top_fin_picks() -> html.Div:
    """Cột trái (65%) — Top Fin Picks. [BƯỚC 3.1] `home-picks-grid` khởi tạo
    RỖNG (children=[]) — không còn fix cứng TPB/MBB/VHM. Callback trong
    home_callbacks.py sẽ Output thẳng vào `home-picks-grid.children` với danh
    sách card linh hoạt (3 mã 5 sao thật, đứng đầu bảng lọc, đổi theo dữ liệu).
    """
    return html.Div(id="home-picks-col", className="home-picks-col", children=[
        html.Div(className="home-picks-header", children=[
            html.Div(children=[
                html.H3("Top Quant Scores", className="home-picks-title"),
                html.P("Các mã có điểm định lượng cao theo bộ tiêu chí hiện tại.",
                       className="home-picks-subtitle"),
            ]),
            html.A(["Xem tất cả ", html.I(className="fa-solid fa-arrow-right-from-bracket")],
                   href="#screener-scroll-anchor", className="home-picks-viewall"),
        ]),
        html.Div(id="home-picks-grid", className="home-picks-grid", children=[]),
    ])
def create_market_pulse() -> html.Div:
    """Cột phải (35%) — thanh Market Breadth + danh sách cảnh báo dòng tiền.
    Toàn bộ nội dung động để id trống/placeholder cho callback tự nối sau.
    """
    return html.Div(id="home-market-pulse", className="home-pulse-col", children=[
        html.H3("Nhịp đập Thị trường", className="home-pulse-title"),
        # ── Market Breadth ──
        html.Div(className="home-pulse-breadth", children=[
            html.Div(className="home-pulse-breadth-head", children=[
                html.Span("ĐỘ RỘNG TT", className="home-pulse-breadth-label-static"),
                html.Span(id="home-pulse-breadth-label", className="home-pulse-breadth-label",
                           children="...% TĂNG"),
            ]),
            html.Div(className="home-pulse-breadth-track", children=[
                html.Div(id="home-pulse-breadth-fill-bull", className="home-pulse-breadth-fill-bull",
                          style={"width": "69%"}),
                html.Div(id="home-pulse-breadth-fill-bear", className="home-pulse-breadth-fill-bear",
                          style={"width": "31%"}),
            ]),
            # [MỚI] Hiển thị số mã tăng/giảm/đứng giá — 3 span riêng để
            # canh space-between (dài hết thanh) và bold riêng từng số.
            html.Div(id="home-pulse-breadth-counts", className="home-pulse-breadth-counts", children=[
                html.Span([html.Strong("..."), " tăng"], className="home-pulse-breadth-count-item"),
                html.Span([html.Strong("..."), " giảm"], className="home-pulse-breadth-count-item"),
                html.Span("... đứng giá", className="home-pulse-breadth-count-item"),
            ]),
        ]),
        # ── Danh sách cảnh báo — callback trả list các <li> mới để thay children ──
        html.Ul(id="home-pulse-alerts-list", className="home-pulse-alerts", children=[
            html.Li(className="home-pulse-alert-item", children=[
                html.I(className="fa-solid fa-bolt home-pulse-alert-icon home-pulse-alert-icon-positive"),
                html.Div(children=[
                    html.Div("Tích lũy mạnh", className="home-pulse-alert-title"),
                    html.Div("Dòng tiền mạnh đổ vào nhóm ...", className="home-pulse-alert-desc"),
                ]),
            ]),
            html.Li(className="home-pulse-alert-item", children=[
                html.I(className="fa-solid fa-arrow-right home-pulse-alert-icon home-pulse-alert-icon-neutral"),
                html.Div(children=[
                    html.Div("Tích lũy ngành", className="home-pulse-alert-title"),
                    html.Div("Nhóm ... đang tích lũy ổn định", className="home-pulse-alert-desc"),
                ]),
            ]),
            html.Li(className="home-pulse-alert-item", children=[
                html.I(className="fa-solid fa-triangle-exclamation home-pulse-alert-icon home-pulse-alert-icon-negative"),
                html.Div(children=[
                    html.Div("Gặp vùng cản", className="home-pulse-alert-title"),
                    html.Div("Nhóm ... chạm kháng cự 52 tuần", className="home-pulse-alert-desc"),
                ]),
            ]),
        ]),
    ])
def create_picks_and_pulse_section() -> html.Div:
    """Bọc chung 'Top Fin Picks' (65%) + 'Market Pulse' (35%) trong 1 grid."""
    return html.Div(id="home-picks-pulse-section", className="home-picks-pulse-grid", children=[
        create_top_fin_picks(),
        create_market_pulse(),
    ])
# ── MAIN HEADER ───────────────────────────────────────────────────────────────
def create_header_content():
    """
    Phần "nội dung + nền GIF" của header — KHÔNG bao gồm create_topbar().
    Tách riêng hàm này vì main.py hiện tại gọi create_topbar() độc lập ở
    chỗ khác trong app.layout (để topbar dính sticky trên cùng, tách khỏi
    khối có thể cuộn) — gọi lại create_topbar() lần nữa bên trong sẽ tạo
    ra 2 topbar trùng lặp (trùng id).

    Vì lý do đó, layout thật trong main.py trước đây gọi thẳng 3 hàm con
    (create_banner(), create_market_overview(), create_picks_and_pulse_
    section()) tách rời nhau, bỏ qua toàn bộ lớp bọc GIF nền — đây là
    hàm thay thế cho đúng 3 dòng đó, giữ nguyên hiệu ứng GIF blur mà
    không kéo theo create_topbar().

    Cách dùng trong main.py: thay
        create_banner(),
        create_market_overview(),
        create_picks_and_pulse_section(),
    bằng
        create_header_content(),
    (một lời gọi hàm duy nhất, trả về đủ cả 3 khối + lớp nền GIF).

    Background GIF dựng 100% bằng INLINE STYLE (không phụ thuộc style.css).
    Cấu trúc:
      vietcap-header-bg-wrap (position: relative, overflow: hidden — INLINE)
        ├── bg_gif_layer (position: absolute, phủ kín, blur — INLINE)
        └── content_layer (position: relative, zIndex: 1 — INLINE)
              ├── wrap-transparent > create_banner()
              ├── wrap-transparent > create_market_overview()
              └── wrap-transparent > create_picks_and_pulse_section()
    """
    # --- ĐOẠN MỚI THÊM VÀO ---
    # Kiểm tra xem app đang chạy trên Hugging Face (có biến SPACE_ID) hay chạy Local
    is_huggingface = "SPACE_ID" in os.environ
    bg_filename = "infinite_candlesticks_dark_glow.png" if is_huggingface else "infinite_candlesticks_dark_glow.gif"
    BG_URL = f"/assets/{bg_filename}"
    # -------------------------

    bg_gif_layer = html.Div(style={
        "position": "absolute",
        "top": "-24px", "bottom": "-24px",
        # "Full-bleed" trick: ép chiều rộng đúng bằng 100% VIEWPORT (100vw),
        # canh giữa bằng left:50% + translateX(-50%) — nhờ vậy luôn phủ kín
        # ngang màn hình dù div cha (vietcap-header-bg-wrap) hẹp hơn do bị
        # max-width/padding của các khối con (home-hero, home-market-grid...)
        # bên trong quy định. Chiều cao vẫn giữ nguyên theo cha (top/bottom
        # -24px), phần dư theo chiều dọc bị cắt bởi overflowY: hidden ở cha.
        "left": "50%",
        "width": "100vw",
        "transform": "translateX(-50%)",
        "backgroundImage": f"url('{BG_URL}')",  # <-- Đã đổi thành biến BG_URL động
        "backgroundSize": "cover",
        "backgroundPosition": "center",
        "backgroundRepeat": "no-repeat",
        "filter": "blur(8px)",
        "opacity": "0.35",
        "zIndex": "0",
        "pointerEvents": "none",
    })

    def _transparent_wrap(component):
        return html.Div(component, style={"backgroundColor": "transparent", "position": "relative"})

    # SAU — thêm dcc.Interval làm phần tử đầu tiên:
    content_layer = html.Div(
        style={"position": "relative", "zIndex": "1"},
        children=[
            # Interval cập nhật header mỗi 60s — đồng bộ với Wifeed fetch
            dcc.Interval(
                id="header-realtime-interval",
                interval=60_000,   # 60 giây
                n_intervals=0,
                disabled=False,
            ),
            _transparent_wrap(create_banner()),
            _transparent_wrap(create_market_overview()),
            _transparent_wrap(create_picks_and_pulse_section()),
        ],
    )

    return html.Div(
        id="vietcap-header-bg-wrap",
        # overflowX: visible để lớp gif "100vw" phía trên được phép tràn ra
        # ngoài bề rộng thật của khối cha (vốn có thể hẹp hơn viewport do
        # max-width của home-hero/home-market-grid...) và phủ đúng full màn
        # hình theo chiều ngang. overflowY: hidden để cắt phần dư theo chiều
        # dọc như yêu cầu (-24px trên/dưới), không cho nó tràn xuống nội
        # dung phía sau.
        style={"position": "relative", "overflowX": "visible", "overflowY": "hidden"},
        children=[bg_gif_layer, content_layer],
    )


def create_header():
    """
    Bản đầy đủ (topbar + nội dung + GIF nền) — dùng khi bạn KHÔNG gọi
    create_topbar() riêng ở chỗ khác trong layout. Với cấu trúc main.py
    hiện tại (topbar đã tách riêng), dùng create_header_content() ở trên
    thay vì hàm này để tránh trùng topbar.
    """
    return html.Div(id="vietcap-master-header", style={"position": "relative"}, children=[
        create_topbar(),
        create_header_content(),
    ])
# LƯU Ý: callback theme toggle (đổi data-theme trên <html>) nằm trong
# main.py, dùng app.clientside_callback(...) — đúng convention của dự án
# (mọi clientside_callback khác đều đăng ký qua app, không đăng ký rời
# trong file component). Không cần thêm callback nào ở đây nữa.