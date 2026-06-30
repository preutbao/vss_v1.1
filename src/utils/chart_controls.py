# src/components/chart_controls.py
"""
UI Controls cho biểu đồ — tab "BIẾN ĐỘNG GIÁ".

Lưu ý quan trọng: layout trong file này được dựng TĨNH một lần khi app khởi
động (không phải trong callback), nên Python không thể biết theme hiện tại
(sáng/tối) tại thời điểm render. Vì vậy mọi màu sắc ở đây dùng CSS class
(.chart-controls-panel, .chart-toggle-box, .chart-tip-box...) tham chiếu tới
biến CSS theo theme trong style.css, thay cho hex cứng — khi người dùng đổi
theme, CSS tự áp dụng lại mà không cần callback nào.
"""

from dash import html, dcc
import dash_bootstrap_components as dbc
import dash_daq as daq


def create_chart_controls():
    """Tạo các controls để điều khiển biểu đồ — theme-aware qua CSS class."""
    return html.Div([
        dbc.Row([
            # Time Period Quick Select
            dbc.Col([
                html.Label([
                    html.I(className="fas fa-calendar-alt"),
                    "Khoảng thời gian"
                ], className="chart-controls-label"),
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
                    html.I(className="fas fa-wave-square"),
                    "Đường trung bình động (MA)"
                ], className="chart-controls-label"),
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
                    className="custom-dropdown"
                )
            ], width=12, lg=7),
        ], className="mb-3"),

        # Row 2: Toggle Switches + Chart Type
        dbc.Row([
            # Volume Toggle
            dbc.Col([
                html.Div([
                    html.I(className="fas fa-chart-bar", style={"marginRight": "8px", "fontSize": "14px"}),
                    html.Span("Khối lượng"),
                    daq.BooleanSwitch(
                        id="show-volume-toggle",
                        on=True,
                        color="#10b981",
                        style={"display": "inline-block"}
                    )
                ], className="chart-toggle-box")
            ], width=6, lg=2, className="mb-2 mb-lg-0"),

            # RSI Toggle
            dbc.Col([
                html.Div([
                    html.I(className="fas fa-chart-line", style={"marginRight": "8px", "fontSize": "14px"}),
                    html.Span("RSI"),
                    daq.BooleanSwitch(
                        id="show-rsi-toggle",
                        on=False,
                        color="#0ea5e9",
                        style={"display": "inline-block"}
                    )
                ], className="chart-toggle-box")
            ], width=6, lg=2, className="mb-2 mb-lg-0"),

            # MACD Toggle
            dbc.Col([
                html.Div([
                    html.I(className="fas fa-chart-area", style={"marginRight": "8px", "fontSize": "14px"}),
                    html.Span("MACD"),
                    daq.BooleanSwitch(
                        id="show-macd-toggle",
                        on=False,
                        color="#a78bfa",
                        style={"display": "inline-block"}
                    )
                ], className="chart-toggle-box")
            ], width=6, lg=2, className="mb-2 mb-lg-0"),

            # ADX Toggle
            dbc.Col([
                html.Div([
                    html.I(className="fas fa-tachometer-alt", style={"marginRight": "8px", "fontSize": "14px"}),
                    html.Span("ADX"),
                    daq.BooleanSwitch(
                        id="show-adx-toggle",
                        on=False,
                        color="#f59e0b",
                        style={"display": "inline-block"}
                    )
                ], className="chart-toggle-box")
            ], width=6, lg=2, className="mb-2 mb-lg-0"),

            # Index Toggle
            dbc.Col([
                html.Div([
                    html.I(className="fas fa-globe", style={"marginRight": "8px", "fontSize": "14px"}),
                    html.Span("Index"),
                    daq.BooleanSwitch(
                        id="show-index-toggle",
                        on=False,
                        color="#f59e0b",
                        style={"display": "inline-block"}
                    )
                ], className="chart-toggle-box")
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
                    className="custom-dropdown chart-type-dd"
                )
            ], width=6, lg=3, className="mb-2 mb-lg-0"),

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

        # Row 3: Instructions
        html.Div([
            html.Div([
                html.I(className="fas fa-lightbulb", style={"marginRight": "10px", "fontSize": "16px", "color": "#f59e0b"}),
                html.Span("Mẹo sử dụng: ", className="tip-label"),
                html.Span(
                    "Lăn chuột để Zoom • Kéo thả để Pan • Double click để Reset view • Sử dụng thanh công cụ bên trên biểu đồ để vẽ",
                    className="tip-text")
            ], className="chart-tip-box")
        ])

    ], className="chart-controls-panel")


def create_chart_container():
    """Tạo container chứa biểu đồ nến. Khung rỗng này được callback
    chart_callbacks.py đổ nội dung (đã theme-aware) vào khi người dùng chọn mã."""
    return html.Div([
        # Controls
        create_chart_controls(),

        # Chart Container (placeholder — callback sẽ ghi đè nội dung)
        html.Div([
            html.Div([
                html.I(className="fas fa-chart-line", style={
                    "fontSize": "48px", "marginBottom": "15px",
                    "animation": "pulse 2s infinite"
                }),
                html.P("Chọn một mã cổ phiếu từ bảng Screener để tải biểu đồ chuyên sâu", style={
                    "fontSize": "15px", "fontWeight": "500"
                })
            ], className="chart-empty-state", style={
                "display": "flex", "flexDirection": "column", "alignItems": "center",
                "justifyContent": "center", "padding": "80px 20px", "textAlign": "center"
            })
        ], id="candlestick-chart-container", className="chart-controls-panel", style={
            "minHeight": "600px",
            "padding": "0",
            "overflow": "hidden",  # Để bo góc biểu đồ bên trong
        }),
    ])