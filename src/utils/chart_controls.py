# src/components/chart_controls.py
"""
UI Controls cho biểu đồ - Nâng cấp phong cách Glassmorphism & Dark Theme từ VnStock Pro
"""

from dash import html, dcc
import dash_bootstrap_components as dbc
import dash_daq as daq


def create_chart_controls():
    """
    Tạo các controls để điều khiển biểu đồ với thiết kế hiện đại
    """
    # Màu sắc dựa trên theme VnStock Pro
    glass_bg = "rgba(6, 15, 30, 0.85)"  # Xanh Slate trong suốt
    glass_border = "rgba(0, 212, 255, 0.12)"
    primary_color = "#00d4ff"
    text_color = "#d6eaf8"
    text_muted = "#7fa8cc"

    return html.Div([
        dbc.Row([
            # Time Period Quick Select
            dbc.Col([
                html.Label([
                    html.I(className="fas fa-calendar-alt", style={
                        "marginRight": "8px", "color": primary_color
                    }),
                    "Khoảng thời gian"
                ], style={
                    "color": text_color, "fontSize": "13px", "fontWeight": "600",
                    "marginBottom": "8px", "display": "flex", "alignItems": "center"
                }),
                dbc.ButtonGroup([
                    dbc.Button("1T", id="period-1w", size="sm", outline=True, color="secondary",
                               className="period-btn"),
                    dbc.Button("1M", id="period-1m", size="sm", outline=True, color="secondary",
                               className="period-btn"),
                    dbc.Button("3M", id="period-3m", size="sm", outline=True, color="secondary",
                               className="period-btn"),
                    dbc.Button("6M", id="period-6m", size="sm", outline=True, color="secondary",
                               className="period-btn"),
                    dbc.Button("1Y", id="period-1y", size="sm", outline=False, color="primary", className="period-btn"),
                    dbc.Button("YTD", id="period-ytd", size="sm", outline=True, color="secondary",
                               className="period-btn"),
                    dbc.Button("All", id="period-all", size="sm", outline=True, color="secondary",
                               className="period-btn"),
                ], style={"width": "100%", "boxShadow": "0 4px 6px rgba(0,0,0,0.1)"})
            ], width=12, lg=5),

            # MA Selector
            dbc.Col([
                html.Label([
                    html.I(className="fas fa-wave-square", style={
                        "marginRight": "8px", "color": primary_color
                    }),
                    "Đường trung bình động (MA)"
                ], style={
                    "color": text_color, "fontSize": "13px", "fontWeight": "600",
                    "marginBottom": "8px", "display": "flex", "alignItems": "center"
                }),
                dcc.Dropdown(
                    id="ma-selector",
                    options=[
                        {"label": "MA 5", "value": 5},
                        {"label": "MA 10", "value": 10},
                        {"label": "MA 20", "value": 20},
                        {"label": "MA 50", "value": 50},
                        {"label": "MA 100", "value": 100},
                        {"label": "MA 200", "value": 200}
                    ],
                    value=[20, 50],  # Mặc định chọn MA20 và MA50
                    multi=True,
                    placeholder="Chọn các kỳ hạn MA...",
                    style={
                        "backgroundColor": "#091526",  # Card bg
                        "color": text_color,
                        "border": f"1px solid {glass_border}",
                        "borderRadius": "8px"
                    },
                    className="custom-dropdown"
                )
            ], width=12, lg=7),
        ], className="mb-3"),

        # Row 2: Toggle Switches + Chart Type
        dbc.Row([
            # Volume Toggle
            dbc.Col([
                html.Div([
                    html.I(className="fas fa-chart-bar",
                           style={"marginRight": "8px", "color": primary_color, "fontSize": "14px"}),
                    html.Span("Khối lượng", style={"color": text_color, "fontSize": "13px", "marginRight": "10px",
                                                   "fontWeight": "500"}),
                    daq.BooleanSwitch(
                        id="show-volume-toggle",
                        on=True,
                        color="#00e676",  # Màu xanh positive từ theme
                        style={"display": "inline-block"}
                    )
                ], style={
                    "display": "flex", "alignItems": "center", "padding": "8px 12px",
                    "backgroundColor": "#091526", "borderRadius": "8px",
                    "border": f"1px solid {glass_border}",
                    "boxShadow": "inset 0 2px 4px rgba(0,0,0,0.1)"
                })
            ], width=6, lg=2, className="mb-2 mb-lg-0"),

            # RSI Toggle
            dbc.Col([
                html.Div([
                    html.I(className="fas fa-chart-line",
                           style={"marginRight": "8px", "color": "#00d4ff", "fontSize": "14px"}),
                    html.Span("RSI", style={"color": text_color, "fontSize": "13px", "marginRight": "10px",
                                            "fontWeight": "500"}),
                    daq.BooleanSwitch(
                        id="show-rsi-toggle",
                        on=False,
                        color="#00d4ff",  # Màu cyan accent3
                        style={"display": "inline-block"}
                    )
                ], style={
                    "display": "flex", "alignItems": "center", "padding": "8px 12px",
                    "backgroundColor": "#091526", "borderRadius": "8px",
                    "border": f"1px solid {glass_border}",
                    "boxShadow": "inset 0 2px 4px rgba(0,0,0,0.1)"
                })
            ], width=6, lg=2, className="mb-2 mb-lg-0"),

            # MACD Toggle
            dbc.Col([
                html.Div([
                    html.I(className="fas fa-chart-area",
                           style={"marginRight": "8px", "color": "#b388ff", "fontSize": "14px"}),
                    html.Span("MACD", style={"color": text_color, "fontSize": "13px", "marginRight": "10px",
                                             "fontWeight": "500"}),
                    daq.BooleanSwitch(
                        id="show-macd-toggle",
                        on=False,
                        color="#b388ff",
                        style={"display": "inline-block"}
                    )
                ], style={
                    "display": "flex", "alignItems": "center", "padding": "8px 12px",
                    "backgroundColor": "#091526", "borderRadius": "8px",
                    "border": f"1px solid {glass_border}",
                    "boxShadow": "inset 0 2px 4px rgba(0,0,0,0.1)"
                })
            ], width=6, lg=2, className="mb-2 mb-lg-0"),

            # Index Toggle
            dbc.Col([
                html.Div([
                    html.I(className="fas fa-globe",
                           style={"marginRight": "8px", "color": "#fbbf24", "fontSize": "14px"}),
                    html.Span("Index", style={"color": text_color, "fontSize": "13px", "marginRight": "10px",
                                              "fontWeight": "500"}),
                    daq.BooleanSwitch(
                        id="show-index-toggle",
                        on=False,
                        color="#fbbf24",
                        style={"display": "inline-block"}
                    )
                ], style={
                    "display": "flex", "alignItems": "center", "padding": "8px 12px",
                    "backgroundColor": "#091526", "borderRadius": "8px",
                    "border": f"1px solid {glass_border}",
                    "boxShadow": "inset 0 2px 4px rgba(0,0,0,0.1)"
                })
            ], width=6, lg=2, className="mb-2 mb-lg-0"),

            # Chart Type Selector
            dbc.Col([
                dcc.Dropdown(
                    id="chart-type-selector",
                    options=[
                        {"label": "Biểu đồ Nến", "value": "candlestick"},
                        {"label": "Biểu đồ Đường", "value": "line"},
                        {"label": "Biểu đồ Vùng", "value": "area"}
                    ],
                    value="candlestick",
                    clearable=False,
                    style={
                        "backgroundColor": "#091526",
                        "color": "#ffffff",
                        "fontSize": "13px",
                        "border": f"1px solid {glass_border}",
                        "borderRadius": "8px",
                    },
                    className="custom-dropdown chart-type-dd"
                )
            ], width=6, lg=2, className="mb-2 mb-lg-0"),

            # Action Buttons (nhỏ gọn)
            dbc.Col([
                dbc.ButtonGroup([
                    dbc.Button(
                        html.I(className="fas fa-sync-alt"),
                        id="refresh-chart-btn",
                        color="primary", outline=False,
                        title="Làm mới biểu đồ",
                        style={"padding": "6px 10px"}
                    ),
                    dbc.Button(
                        html.I(className="fas fa-expand"),
                        id="fullscreen-chart-btn",
                        color="primary", outline=False,
                        title="Toàn màn hình",
                        style={"padding": "6px 10px"}
                    ),
                ], size="sm", style={"boxShadow": "0 4px 10px rgba(59, 130, 246, 0.3)"})
            ], width="auto", className="mb-2 mb-lg-0")
        ], className="mb-3"),

        # Row 3: Instructions (Glassmorphism Info Box)
        html.Div([
            html.Div([
                html.I(className="fas fa-lightbulb",
                       style={"marginRight": "10px", "color": "#ffb703", "fontSize": "16px"}),
                html.Span("Mẹo sử dụng: ", style={"color": "#ffb703", "fontSize": "13px", "fontWeight": "700"}),
                html.Span(
                    "Lăn chuột để Zoom • Kéo thả để Pan • Double click để Reset view • Sử dụng thanh công cụ bên trên biểu đồ để vẽ",
                    style={"color": text_muted, "fontSize": "12px", "marginLeft": "5px"})
            ], style={
                "display": "flex", "alignItems": "center", "padding": "10px 15px",
                "backgroundColor": "rgba(251, 191, 36, 0.05)",  # Nền vàng nhạt
                "borderRadius": "8px",
                "border": "1px solid rgba(251, 191, 36, 0.2)",
                "borderLeft": "4px solid #fbbf24"
            })
        ])

    ], style={
        "padding": "20px",
        "background": glass_bg,
        "backdropFilter": "blur(20px) saturate(180%)",
        "borderRadius": "15px",
        "border": f"1px solid {glass_border}",
        "boxShadow": "0 10px 25px rgba(0, 0, 0, 0.2)",
        "marginBottom": "20px"
    })


def create_chart_container():
    """
    Tạo container chứa biểu đồ nến
    """
    glass_border = "rgba(0, 212, 255, 0.12)"

    return html.Div([
        # Controls
        create_chart_controls(),

        # Chart Container
        html.Div([
            html.Div([
                html.I(className="fas fa-chart-line", style={
                    "fontSize": "48px", "color": "#475569", "marginBottom": "15px",
                    "animation": "pulse 2s infinite"
                }),
                html.P("Chọn một mã cổ phiếu từ bảng Screener để tải biểu đồ chuyên sâu", style={
                    "color": "#7fa8cc", "fontSize": "15px", "fontWeight": "500"
                })
            ], style={
                "display": "flex", "flexDirection": "column", "alignItems": "center",
                "justifyContent": "center", "padding": "80px 20px", "textAlign": "center"
            })
        ], id="candlestick-chart-container", style={
            "minHeight": "600px",
            "backgroundColor": "#0c1220",  # Background siêu tối cho biểu đồ
            "borderRadius": "15px",
            "border": f"1px solid {glass_border}",
            "padding": "0",
            "boxShadow": "0 15px 35px rgba(0, 0, 0, 0.4)",
            "overflow": "hidden"  # Để bo góc biểu đồ bên trong
        })
    ])