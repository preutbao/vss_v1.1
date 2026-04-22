# src/components/header.py
from dash import html
import dash_bootstrap_components as dbc

def create_header():
    sys_font = "'Inter', 'Segoe UI', system-ui, -apple-system, sans-serif"

    return html.Div(id="vietcap-master-header", children=[
        # ====================================================================
        # TẦNG 1: STICKY NAVBAR (Menu cố định 56px)
        # ====================================================================
        html.Div([
            html.Div([
                # 1. Logo
                html.A([
                    html.Span("Vietcap", style={
                        "fontSize": "20px", "fontWeight": "800",
                        "color": "white", "letterSpacing": "-0.5px",
                        "fontFamily": sys_font
                    }),
                    html.Span("▲", style={
                        "color": "#00a651", "fontSize": "11px",
                        "marginLeft": "2px", "transform": "translateY(-6px)",
                        "display": "inline-block"
                    })
                ], href="https://www.vietcap.com.vn", target="_blank",
                   style={"textDecoration": "none", "display": "flex", "alignItems": "center"}),

                # 2. Links menu — dùng class nav-item để CSS hover hoạt động
                html.Div([
                    html.A("Về Vietcap",
                           href="https://www.vietcap.com.vn/ve-vietcap",
                           target="_blank",
                           className="vietcap-nav-link"),
                    html.A("Dịch vụ",
                           href="https://www.vietcap.com.vn/tu-van-khach-hang-ca-nhan",
                           target="_blank",
                           className="vietcap-nav-link"),
                    html.A("Sản phẩm",
                           href="#",
                           className="vietcap-nav-link"),
                    html.A("Truyền thông",
                           href="https://www.vietcap.com.vn/chien-dich",
                           target="_blank",
                           className="vietcap-nav-link"),
                    html.A("Screener",
                           href="#screener-scroll-anchor",
                           className="vietcap-nav-link vietcap-nav-screener"),
                ], className="d-flex align-items-center gap-4"),

                # 3. Nút mở tài khoản
                html.A("Mở tài khoản",
                       href="https://www.vietcap.com.vn/mo-tai-khoan?language=vi&utm_source=vietcap_website",
                       target="_blank",
                       className="vietcap-nav-cta")
            ], style={
                "width": "100%", "maxWidth": "1200px", "margin": "0 auto",
                "display": "flex", "alignItems": "center",
                "justifyContent": "space-between", "padding": "0 20px"
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
            "display": "flex", "alignItems": "center"
        }),

        # ====================================================================
        # TẦNG 2: HERO BANNER
        # ====================================================================
        html.Div([
            dbc.Carousel(
                items=[
                    {"key": "1", "src": "/assets/anh1.png", "img_style": {
                        "width": "100%", "height": "400px",
                        "objectFit": "cover", "filter": "brightness(0.55)"
                    }},
                    {"key": "2", "src": "/assets/anh2.png", "img_style": {
                        "width": "100%", "height": "400px",
                        "objectFit": "cover", "filter": "brightness(0.55)"
                    }},
                    {"key": "3", "src": "/assets/anh3.png", "img_style": {
                        "width": "100%", "height": "400px",
                        "objectFit": "cover", "filter": "brightness(0.55)"
                    }},
                ],
                controls=False, indicators=False,
                interval=3000,
                style={
                    "position": "absolute", "top": "0", "left": "0",
                    "width": "100%", "height": "100%", "zIndex": "1"
                }
            ),

            # Lớp bóng mờ gradient
            html.Div(style={
                "position": "absolute", "inset": "0",
                "background": "linear-gradient(to bottom, rgba(6,15,30,0.65) 0%, rgba(6,15,30,0.15) 40%, rgba(6,15,30,0.85) 85%, #0a0e14 100%)",
                "zIndex": "2"
            }),

            # Nội dung chữ
            html.Div([
                # Badge label
                html.P("NỀN TẢNG PHÂN TÍCH CỔ PHIẾU CHUYÊN NGHIỆP", style={
                    "fontSize": "11px",
                    "fontWeight": "600",
                    "letterSpacing": "2.5px",
                    "color": "rgba(160,210,180,0.75)",
                    "marginBottom": "14px",
                    "textTransform": "uppercase",
                    "fontFamily": sys_font,
                }),

                # Tiêu đề chính — to và táo bạo hơn
                html.H1([
                    html.Span("Vietcap ", style={
                        "color": "#00c85a",
                        "fontWeight": "800",
                        "fontFamily": "'Sora', " + sys_font,
                        "textShadow": "0 0 40px rgba(0,200,90,0.35)",
                    }),
                    html.Span("Smart Screener", style={
                        "color": "#f0f6ff",
                        "fontWeight": "300",
                        "fontFamily": "'Sora', " + sys_font,
                    }),
                ], style={
                    "fontSize": "clamp(36px, 5vw, 56px)",
                    "marginBottom": "20px",
                    "letterSpacing": "-1.5px",
                    "lineHeight": "1.1",
                }),

                # Đường kẻ trang trí
                html.Div(style={
                    "width": "56px", "height": "2px",
                    "background": "linear-gradient(90deg, transparent, #00a651, transparent)",
                    "margin": "0 auto 28px auto",
                    "opacity": "0.7",
                }),

                # Nút CTA
                html.A("Khám phá ngay ↓",
                       href="#screener-scroll-anchor",
                       className="vietcap-btn-explore-glass",
                       style={
                           "display": "inline-block",
                           "background": "rgba(0,166,81,0.14)",
                           "border": "1px solid rgba(0,166,81,0.45)",
                           "color": "#00e676",
                           "padding": "11px 32px",
                           "borderRadius": "30px",
                           "textDecoration": "none",
                           "fontWeight": "600",
                           "fontSize": "13px",
                           "fontFamily": sys_font,
                           "backdropFilter": "blur(8px)",
                           "WebkitBackdropFilter": "blur(8px)",
                           "boxShadow": "0 4px 20px rgba(0,0,0,0.25)",
                           "transition": "all 0.3s ease",
                           "letterSpacing": "0.3px",
                       })
            ], style={
                "position": "relative", "zIndex": "3",
                "textAlign": "center", "color": "white",
                "padding": "0 20px",
            })

        ], style={
            "marginTop": "56px",
            "position": "relative", "width": "100%", "height": "400px",
            "overflow": "hidden",
            "display": "flex", "alignItems": "center", "justifyContent": "center",
            "backgroundColor": "#050a0f",
        })
    ])
