# src/pages/screener.py - Complete with 4 Detail Tabs + Sector Column
from dash import html, dcc
from dash import dcc, html
import dash_bootstrap_components as dbc
import dash_bootstrap_components as dbc
import dash_ag_grid as dag
from src.components import sidebar as sidebar
from src.utils.chart_controls import create_chart_container

# === AG GRID COLUMN DEFINITIONS ===
# Chỉ khai báo cột CỐ ĐỊNH ở đây.
# Các cột động sẽ được bơm vào bởi callback trong column_callbacks.py
# khi user thêm chỉ tiêu vào bộ lọc.

_GRADE_STYLE = {
    "function": """
        const grade = params.value || 'F';
        const map = {
            'A': {'bg': '#10b98120', 'color': '#10b981'},
            'B': {'bg': '#3b82f620', 'color': '#3b82f6'},
            'C': {'bg': '#f59e0b20', 'color': '#f59e0b'},
            'D': {'bg': '#ef444420', 'color': '#ef4444'},
            'F': {'bg': '#64748b20', 'color': '#64748b'}
        };
        const c = map[grade] || map['F'];
        return {
            'backgroundColor': c.bg,
            'color': c.color,
            'fontWeight': '700',
            'textAlign': 'center',
            'borderRadius': '4px',
            'fontFamily': "'Inter', sans-serif",
            'fontSize': '12px',
            'letterSpacing': '0.5px',
        };
    """
}

# Row styling theo VGM Score
_ROW_STYLE = {
    "function": """
        const grade = params.data && params.data['VGM Score'];
        if (grade === 'A') return {'backgroundColor': 'rgba(16,185,129,0.06)'};
        if (grade === 'B') return {'backgroundColor': 'rgba(59,130,246,0.05)'};
        if (grade === 'F') return {'backgroundColor': 'rgba(239,68,68,0.04)'};
        return {};
    """
}

# Tooltip header giải thích chỉ số
_TOOLTIPS = {
    "MÃ CK": "Mã chứng khoán niêm yết trên sàn HOSE / HNX / UPCoM",
    "NGÀNH": "Ngành theo phân loại GICS",
    "GIÁ": "Giá đóng cửa phiên gần nhất (VND)",
    "%1T": "% thay đổi giá trong 1 tuần giao dịch",
    "%1TH": "% thay đổi giá trong 1 tháng",
    "KL": "Khối lượng giao dịch phiên gần nhất",
    "VALUE": "Điểm định giá: A=rẻ nhất, F=đắt nhất (dựa trên P/E và P/B)",
    "GROWTH": "Điểm tăng trưởng: A=tốt nhất (dựa trên ROE và ROA)",
    "MOM.": "Điểm động lượng giá: A=xu hướng mạnh nhất",
    "VGM": "Tổng hợp Value + Growth + Momentum. A=tốt nhất toàn diện",
    "%3TH": "% thay đổi giá trong 3 tháng",
    "%1Y": "% thay đổi giá trong 1 năm",
    "VỐN HÓA": "Vốn hóa thị trường (nghìn tỷ VND)",
    "CANSLIM": "Điểm CANSLIM (0-7): ≥5 = đạt tiêu chí siêu cổ phiếu",
    "BCTC": "Ngày báo cáo tài chính gần nhất có trong dữ liệu",
}

# ── Font helpers dùng lại nhiều lần ──────────────────────────────────────────
# Font cho mã CK (Sora bold — giống heading SSI iBoard)
_TICKER_STYLE = {
    "fontFamily": "'Sora', 'Inter', sans-serif",
    "fontWeight": "800",
    "color": "#00e676",
    "fontSize": "13px",
    "letterSpacing": "0.8px",
}

# Font cho số liệu (Roboto Mono — tabular-nums, thẳng hàng)
_NUM_STYLE_GREEN = {
    "fontFamily": "'Roboto Mono', 'JetBrains Mono', monospace",
    "fontWeight": "700",
    "fontSize": "13px",
    "color": "#fbbf24",
    "fontVariantNumeric": "tabular-nums",
    "letterSpacing": "0.2px",
}

# cellStyle function cho cột % tăng/giảm (xanh/đỏ)
_PCT_CELL_STYLE = {
    "function": (
        "const v = params.value; "
        "if (v == null) return {"
        "  'color': '#484f58',"
        "  'fontFamily': \"'Roboto Mono', monospace\","
        "  'fontSize': '12.5px',"
        "  'fontVariantNumeric': 'tabular-nums'"
        "}; "
        "const base = {"
        "  'fontFamily': \"'Roboto Mono', monospace\","
        "  'fontSize': '12.5px',"
        "  'fontVariantNumeric': 'tabular-nums',"
        "  'fontWeight': '600',"
        "  'letterSpacing': '0.2px'"
        "}; "
        "return v > 0 ? {...base, 'color': '#10b981'} "
        "     : v < 0 ? {...base, 'color': '#ef4444'} "
        "     : {...base, 'color': '#8b949e'};"
    )
}

columnDefs = [
    {
        "field": "Ticker",
        "headerName": "MÃ CK",
        "headerTooltip": _TOOLTIPS["MÃ CK"],
        "pinned": "left",
        "width": 95,
        "sortable": True,
        "filter": True,
        "cellStyle": _TICKER_STYLE,
    },
    {
        "field": "Sector",
        "headerName": "NGÀNH",
        "headerTooltip": _TOOLTIPS["NGÀNH"],
        "width": 130,
        "sortable": True,
        "filter": True,
        "cellStyle": {
            "fontFamily": "'Inter', sans-serif",
            "fontSize": "12px",
            "color": "#c9d1d9",
        },
    },
    {
        "field": "Price Close",
        "headerName": "GIÁ",
        "headerTooltip": _TOOLTIPS["GIÁ"],
        "type": "rightAligned",
        "sortable": True,
        "width": 105,
        "valueFormatter": {"function": "d3.format(',.0f')(params.value)"},
        "cellStyle": _NUM_STYLE_GREEN,
    },
    {
        "field": "Perf_1W",
        "headerName": "%1T",
        "headerTooltip": _TOOLTIPS["%1T"],
        "type": "rightAligned",
        "sortable": True,
        "width": 82,
        "valueFormatter": {
            "function": "params.value != null ? (params.value > 0 ? '+' : '') + d3.format('.1f')(params.value) + '%' : '–'"},
        "cellStyle": _PCT_CELL_STYLE,
    },
    {
        "field": "Perf_1M",
        "headerName": "%1TH",
        "headerTooltip": _TOOLTIPS["%1TH"],
        "type": "rightAligned",
        "sortable": True,
        "width": 88,
        "valueFormatter": {
            "function": "params.value != null ? (params.value > 0 ? '+' : '') + d3.format('.1f')(params.value) + '%' : '–'"},
        "cellStyle": _PCT_CELL_STYLE,
    },
    {
        "field": "Volume",
        "headerName": "KL",
        "headerTooltip": _TOOLTIPS["KL"],
        "type": "rightAligned",
        "sortable": True,
        "width": 120,
        "valueFormatter": {"function": "d3.format(',.0f')(params.value)"},
        "cellStyle": {
            "fontFamily": "'Roboto Mono', monospace",
            "fontSize": "12.5px",
            "fontVariantNumeric": "tabular-nums",
            "letterSpacing": "0.2px",
            "color": "#c9d1d9",
        },
    },
    {"field": "Value Score", "headerName": "VALUE", "headerTooltip": _TOOLTIPS["VALUE"], "width": 90, "sortable": True,
     "cellStyle": _GRADE_STYLE},
    {"field": "Growth Score", "headerName": "GROWTH", "headerTooltip": _TOOLTIPS["GROWTH"], "width": 95,
     "sortable": True, "cellStyle": _GRADE_STYLE},
    {"field": "Momentum Score", "headerName": "MOM.", "headerTooltip": _TOOLTIPS["MOM."], "width": 90, "sortable": True,
     "cellStyle": _GRADE_STYLE},
    {"field": "VGM Score", "headerName": "VGM", "headerTooltip": _TOOLTIPS["VGM"], "width": 85, "sortable": True,
     "cellStyle": _GRADE_STYLE},
    {
        "field": "Perf_3M",
        "headerName": "%3TH",
        "headerTooltip": _TOOLTIPS["%3TH"],
        "type": "rightAligned",
        "sortable": True,
        "width": 88,
        "valueFormatter": {
            "function": "params.value != null ? (params.value > 0 ? '+' : '') + d3.format('.1f')(params.value) + '%' : '–'"},
        "cellStyle": _PCT_CELL_STYLE,
    },
    {
        "field": "Perf_1Y",
        "headerName": "%1Y",
        "headerTooltip": _TOOLTIPS["%1Y"],
        "type": "rightAligned",
        "sortable": True,
        "width": 88,
        "valueFormatter": {
            "function": "params.value != null ? (params.value > 0 ? '+' : '') + d3.format('.1f')(params.value) + '%' : '–'"},
        "cellStyle": _PCT_CELL_STYLE,
    },
    {
        "field": "Market Cap",
        "headerName": "VỐN HÓA",
        "headerTooltip": _TOOLTIPS["VỐN HÓA"],
        "type": "rightAligned",
        "sortable": True,
        "width": 130,
        "valueFormatter": {"function": "params.value != null ? d3.format(',.0f')(params.value/1e12) + ' T' : '–'"},
        "cellStyle": {
            "fontFamily": "'Roboto Mono', monospace",
            "fontSize": "12px",
            "fontVariantNumeric": "tabular-nums",
            "color": "#7fa8cc",
        },
    },
    {
        "field": "CANSLIM Score",
        "headerName": "CANSLIM",
        "headerTooltip": _TOOLTIPS["CANSLIM"],
        "type": "rightAligned",
        "sortable": True,
        "width": 100,
        "valueFormatter": {"function": "params.value || '0'"},
        "cellStyle": {
            "function": (
                "const s = params.value || 0; "
                "const base = {"
                "  'fontFamily': \"'Roboto Mono', monospace\","
                "  'fontSize': '12.5px',"
                "  'fontVariantNumeric': 'tabular-nums'"
                "}; "
                "if (s >= 5) return {...base, 'color': '#10b981', 'fontWeight': '700'}; "
                "if (s >= 3) return {...base, 'color': '#3b82f6', 'fontWeight': '600'}; "
                "return {...base, 'color': '#7fa8cc'};"
            )
        },
    },
    {
        "field": "Date",
        "headerName": "BCTC",
        "headerTooltip": _TOOLTIPS["BCTC"],
        "type": "rightAligned",
        "sortable": True,
        "width": 100,
        "valueFormatter": {
            "function": "params.value ? new Date(params.value).toLocaleDateString('vi-VN', {month:'2-digit',year:'numeric'}) : '–'"
        },
        "cellStyle": {
            "fontFamily": "'Roboto Mono', monospace",
            "color": "#484f58",
            "fontSize": "11px",
            "fontVariantNumeric": "tabular-nums",
        },
    },
]


# === HELPER FUNCTIONS FOR TABS ===
def create_tab_tong_quan():
    """Tab 1: TỔNG QUAN - Overview"""
    return html.Div([
        html.Div([
            html.Table([
                # Header
                html.Thead([
                    html.Tr([
                        html.Th("MÃ",
                                style={"padding": "12px", "fontSize": "12px", "color": "#7fa8cc", "fontWeight": "700"}),
                        html.Th("NGÀNH",
                                style={"padding": "12px", "fontSize": "12px", "color": "#7fa8cc", "fontWeight": "700"}),
                        html.Th("ĐIỂM ĐẦU TƯ GIÁ TRỊ",
                                style={"padding": "12px", "fontSize": "12px", "color": "#7fa8cc", "textAlign": "center",
                                       "fontWeight": "700"}),
                    ])
                ]),
                # Body
                html.Tbody([
                    html.Tr([
                        html.Td("---", id="ov-ticker",
                                style={"padding": "12px", "fontSize": "13px", "color": "#00a651", "fontWeight": "600"}),
                        html.Td("---", id="ov-sector",
                                style={"padding": "12px", "fontSize": "13px", "color": "#d6eaf8"}),
                        html.Td("---", id="ov-value-score",
                                style={"padding": "12px", "fontSize": "13px", "textAlign": "center"}),
                    ])
                ])
            ], style={
                "width": "100%",
                "backgroundColor": "#091526",
                "borderRadius": "6px",
                "border": "1px solid #163660"
            })
        ], style={"overflowX": "auto"})
    ], style={"padding": "20px"})


def create_tab_bien_dong_gia():
    """Tab 2: BIẾN ĐỘNG GIÁ - Price performance"""
    return html.Div([
        html.Div([
            html.Table([
                # Header
                html.Thead([
                    html.Tr([
                        html.Th("MÃ",
                                style={"padding": "12px", "fontSize": "12px", "color": "#7fa8cc", "fontWeight": "700"}),
                        html.Th("GIÁ",
                                style={"padding": "12px", "fontSize": "12px", "color": "#7fa8cc", "textAlign": "right",
                                       "fontWeight": "700"}),
                        html.Th("1 NGÀY",
                                style={"padding": "12px", "fontSize": "12px", "color": "#7fa8cc", "textAlign": "right",
                                       "fontWeight": "700"}),
                        html.Th("1 TUẦN",
                                style={"padding": "12px", "fontSize": "12px", "color": "#7fa8cc", "textAlign": "right",
                                       "fontWeight": "700"}),
                        html.Th("2 TUẦN",
                                style={"padding": "12px", "fontSize": "12px", "color": "#7fa8cc", "textAlign": "right",
                                       "fontWeight": "700"}),
                        html.Th("1 THÁNG",
                                style={"padding": "12px", "fontSize": "12px", "color": "#7fa8cc", "textAlign": "right",
                                       "fontWeight": "700"}),
                        html.Th("3 THÁNG",
                                style={"padding": "12px", "fontSize": "12px", "color": "#7fa8cc", "textAlign": "right",
                                       "fontWeight": "700"}),
                        html.Th("6 THÁNG",
                                style={"padding": "12px", "fontSize": "12px", "color": "#7fa8cc", "textAlign": "right",
                                       "fontWeight": "700"}),
                        html.Th("9 THÁNG",
                                style={"padding": "12px", "fontSize": "12px", "color": "#7fa8cc", "textAlign": "right",
                                       "fontWeight": "700"}),
                        html.Th("1 NĂM",
                                style={"padding": "12px", "fontSize": "12px", "color": "#7fa8cc", "textAlign": "right",
                                       "fontWeight": "700"}),
                        html.Th("TÍNH ĐẾN HIỆN TẠI",
                                style={"padding": "12px", "fontSize": "12px", "color": "#7fa8cc", "textAlign": "right",
                                       "fontWeight": "700"}),
                    ])
                ]),
                # Body
                html.Tbody([
                    html.Tr([
                        html.Td("---", id="perf-ticker",
                                style={"padding": "12px", "fontSize": "13px", "color": "#00a651", "fontWeight": "600"}),
                        html.Td("---", id="perf-price",
                                style={"padding": "12px", "fontSize": "13px", "textAlign": "right"}),
                        html.Td("---", id="perf-1d",
                                style={"padding": "12px", "fontSize": "13px", "textAlign": "right"}),
                        html.Td("---", id="perf-1w",
                                style={"padding": "12px", "fontSize": "13px", "textAlign": "right"}),
                        html.Td("---", id="perf-2w",
                                style={"padding": "12px", "fontSize": "13px", "textAlign": "right"}),
                        html.Td("---", id="perf-1m",
                                style={"padding": "12px", "fontSize": "13px", "textAlign": "right"}),
                        html.Td("---", id="perf-3m",
                                style={"padding": "12px", "fontSize": "13px", "textAlign": "right"}),
                        html.Td("---", id="perf-6m",
                                style={"padding": "12px", "fontSize": "13px", "textAlign": "right"}),
                        html.Td("---", id="perf-9m",
                                style={"padding": "12px", "fontSize": "13px", "textAlign": "right"}),
                        html.Td("---", id="perf-1y",
                                style={"padding": "12px", "fontSize": "13px", "textAlign": "right"}),
                        html.Td("---", id="perf-ytd",
                                style={"padding": "12px", "fontSize": "13px", "textAlign": "right"}),
                    ])
                ])
            ], style={
                "width": "100%",
                "backgroundColor": "#091526",
                "borderRadius": "6px",
                "border": "1px solid #163660"
            })
        ], style={"overflowX": "auto"})
    ], style={"padding": "20px"})


def create_tab_chi_so():
    """Tab 4: CHỈ SỐ TÀI CHÍNH (Financial Metrics)"""

    def create_metric_grid(grid_id):
        return dag.AgGrid(
            id=grid_id,
            rowData=[],
            columnDefs=[],
            className="ag-theme-alpine-dark",
            style={"height": "200px", "width": "100%", "marginBottom": "20px"},
            dashGridOptions={
                "suppressRowClickSelection": True,
                "rowHeight": 35,
                "headerHeight": 40,
                "enableCellTextSelection": True,
            }
        )

    return html.Div([
        # --- Header & Công tắc Năm/Quý ---
        html.Div([
            html.Div([
                html.H6(html.I(className="fas fa-chart-pie", style={"marginRight": "8px", "color": "#b388ff"})),
                html.H6("CHỈ SỐ TÀI CHÍNH (FINANCIAL RATIOS)",
                        style={"color": "#d6eaf8", "margin": "0", "fontWeight": "bold"}),
                html.Span("(Đơn vị: %, Số lần, VND)",
                          style={"marginLeft": "10px", "fontSize": "12px", "color": "#7fa8cc", "fontStyle": "italic"})
            ], style={"display": "flex", "alignItems": "center"}),

            dbc.RadioItems(
                id="metrics-period-toggle",
                className="btn-group",
                inputClassName="btn-check",
                labelClassName="btn btn-outline-primary btn-sm",
                labelCheckedClassName="active",
                options=[
                    {"label": "Theo Năm", "value": "yearly"},
                    {"label": "Theo Quý", "value": "quarterly"},
                ],
                value="yearly",
            ),
        ], style={"display": "flex", "justifyContent": "space-between", "alignItems": "center",
                  "marginBottom": "20px"}),

        # --- Vùng chứa 6 Bảng dữ liệu ---
        html.Div([
            dcc.Loading(
                type="dot", color="#b388ff",
                children=[
                    html.H6("1. CHỈ SỐ MỖI CỔ PHIẾU (Per Share)",
                            style={"color": "#b388ff", "fontWeight": "bold", "fontSize": "14px"}),
                    create_metric_grid("metric-table-1"),
                    html.H6("2. KHẢ NĂNG SINH LỜI (Profitability)",
                            style={"color": "#b388ff", "fontWeight": "bold", "fontSize": "14px"}),
                    create_metric_grid("metric-table-2"),
                    html.H6("3. THANH KHOẢN (Liquidity)",
                            style={"color": "#b388ff", "fontWeight": "bold", "fontSize": "14px"}),
                    create_metric_grid("metric-table-3"),
                    html.H6("4. ĐÒN BẨY & SỨC KHỎE (Leverage)",
                            style={"color": "#b388ff", "fontWeight": "bold", "fontSize": "14px"}),
                    create_metric_grid("metric-table-4"),
                    html.H6("5. HIỆU QUẢ HOẠT ĐỘNG (Efficiency)",
                            style={"color": "#b388ff", "fontWeight": "bold", "fontSize": "14px"}),
                    create_metric_grid("metric-table-5"),
                    html.H6("6. TĂNG TRƯỞNG (Growth)",
                            style={"color": "#b388ff", "fontWeight": "bold", "fontSize": "14px"}),
                    create_metric_grid("metric-table-6"),
                ]
            )
        ], style={"height": "600px", "overflowY": "auto", "paddingRight": "5px"})

    ], id="tab-metrics-content", style={"padding": "20px"})


def create_tab_tai_chinh():
    """Tab 3: TÀI CHÍNH - 3 Separate Matrix Tables"""

    # Hàm tạo cấu hình Grid chung cho cả 3 bảng để code đỡ dài
    def create_grid(grid_id):
        return dag.AgGrid(
            id=grid_id,
            rowData=[],
            columnDefs=[],
            className="ag-theme-alpine-dark",
            # Giảm chiều cao mỗi bảng xuống, tự động hiện thanh cuộn nếu nhiều dòng
            style={"height": "300px", "width": "100%", "marginBottom": "20px"},
            dashGridOptions={
                "suppressRowClickSelection": True,
                "rowHeight": 35,
                "headerHeight": 40,
                "enableCellTextSelection": True,
            }
        )

    return html.Div([
        # --- 1. Header & Thanh điều khiển ---
        html.Div([
            html.Div([
                html.H6(
                    html.I(className="fas fa-file-invoice-dollar", style={"marginRight": "8px", "color": "#00a651"})),
                html.H6("BÁO CÁO TÀI CHÍNH TÓM TẮT", style={"color": "#d6eaf8", "margin": "0", "fontWeight": "bold"}),
                html.Span("(Đơn vị: Triệu VND)",
                          style={"marginLeft": "10px", "fontSize": "12px", "color": "#7fa8cc", "fontStyle": "italic"})
            ], style={"display": "flex", "alignItems": "center"}),

            # CÔNG TẮC NĂM / QUÝ
            dbc.RadioItems(
                id="fin-period-toggle",
                className="btn-group",
                inputClassName="btn-check",
                labelClassName="btn btn-outline-primary btn-sm",
                labelCheckedClassName="active",
                options=[
                    {"label": "Theo Năm", "value": "yearly"},
                    {"label": "Theo Quý", "value": "quarterly"},
                ],
                value="yearly",
            ),
        ], style={"display": "flex", "justifyContent": "space-between", "alignItems": "center",
                  "marginBottom": "20px"}),

        # --- 2. Vùng chứa 3 Bảng dữ liệu ---
        html.Div([
            dcc.Loading(
                type="dot", color="#00a651",
                children=[
                    # BẢNG 1: Kết quả Kinh Doanh
                    html.H6("1. KẾT QUẢ KINH DOANH (Income Statement)",
                            style={"color": "#00a651", "fontWeight": "bold", "fontSize": "14px"}),
                    create_grid("fin-table-is"),

                    # BẢNG 2: Bảng Cân Đối Kế Toán
                    html.H6("2. BẢNG CÂN ĐỐI KẾ TOÁN (Balance Sheet)",
                            style={"color": "#00a651", "fontWeight": "bold", "fontSize": "14px"}),
                    create_grid("fin-table-bs"),

                    # BẢNG 3: Lưu Chuyển Tiền Tệ
                    html.H6("3. LƯU CHUYỂN TIỀN TỆ (Cash Flow Statement)",
                            style={"color": "#00a651", "fontWeight": "bold", "fontSize": "14px"}),
                    create_grid("fin-table-cf")
                ]
            )
        ], style={"height": "650px", "overflowY": "auto", "paddingRight": "5px"})  # Cấp thêm thanh cuộn tổng

    ], id="tab-financial-content", style={"padding": "20px"})


def create_tab_ky_thuat():
    """Tab 4: KỸ THUẬT - Technical indicators"""
    return html.Div([
        html.Div([
            html.Table([
                # Header
                html.Thead([
                    html.Tr([
                        html.Th("MÃ",
                                style={"padding": "12px", "fontSize": "12px", "color": "#7fa8cc", "fontWeight": "700"}),
                        html.Th("GIÁ",
                                style={"padding": "12px", "fontSize": "12px", "color": "#7fa8cc", "textAlign": "right",
                                       "fontWeight": "700"}),
                        html.Th("KHỐI LƯỢNG",
                                style={"padding": "12px", "fontSize": "12px", "color": "#7fa8cc", "textAlign": "right",
                                       "fontWeight": "700"}),
                        html.Th("SMA20",
                                style={"padding": "12px", "fontSize": "12px", "color": "#7fa8cc", "textAlign": "right",
                                       "fontWeight": "700"}),
                        html.Th("SMA50",
                                style={"padding": "12px", "fontSize": "12px", "color": "#7fa8cc", "textAlign": "right",
                                       "fontWeight": "700"}),
                        html.Th("SMA100",
                                style={"padding": "12px", "fontSize": "12px", "color": "#7fa8cc", "textAlign": "right",
                                       "fontWeight": "700"}),
                        html.Th("RSI",
                                style={"padding": "12px", "fontSize": "12px", "color": "#7fa8cc", "textAlign": "right",
                                       "fontWeight": "700"}),
                        html.Th("MÔ HÌNH NẾN",
                                style={"padding": "12px", "fontSize": "12px", "color": "#7fa8cc", "textAlign": "right",
                                       "fontWeight": "700"}),
                    ])
                ]),
                # Body
                html.Tbody([
                    html.Tr([
                        html.Td("---", id="tech-ticker",
                                style={"padding": "12px", "fontSize": "13px", "color": "#00a651", "fontWeight": "600"}),
                        html.Td("---", id="tech-price",
                                style={"padding": "12px", "fontSize": "13px", "color": "#d6eaf8",
                                       "textAlign": "right"}),
                        html.Td("---", id="tech-volume",
                                style={"padding": "12px", "fontSize": "13px", "color": "#d6eaf8",
                                       "textAlign": "right"}),
                        html.Td("---", id="tech-sma20",
                                style={"padding": "12px", "fontSize": "13px", "textAlign": "right"}),
                        html.Td("---", id="tech-sma50",
                                style={"padding": "12px", "fontSize": "13px", "textAlign": "right"}),
                        html.Td("---", id="tech-sma100",
                                style={"padding": "12px", "fontSize": "13px", "textAlign": "right"}),
                        html.Td("---", id="tech-rsi", style={"padding": "12px", "fontSize": "13px", "color": "#d6eaf8",
                                                             "textAlign": "right"}),
                        html.Td("---", id="tech-pattern",
                                style={"padding": "12px", "fontSize": "13px", "color": "#d6eaf8",
                                       "textAlign": "right"}),
                    ])
                ])
            ], style={
                "width": "100%",
                "backgroundColor": "#091526",
                "borderRadius": "6px",
                "border": "1px solid #163660"
            })
        ], style={"overflowX": "auto"})
    ], style={"padding": "20px"})


# === DETAIL TABS (Giữ nguyên của bạn) ===
detail_tabs = dbc.Tabs([
    dbc.Tab(
        label="TỔNG QUAN",
        tab_id="tab-overview",
        children=html.Div(id="tab-overview-content")
    ),
    dbc.Tab(
        label="BIẾN ĐỘNG GIÁ",
        tab_id="tab-price",
        children=create_chart_container()
    ),
    dbc.Tab(
        label="BIỂU ĐỒ",
        tab_id="tab-fin-charts",
        children=html.Div([
            dcc.Loading(type="dot", color="#00a651", children=[
                html.Div(id="tab-fin-charts-content", style={"minHeight": "200px"})
            ])
        ])
    ),
    dbc.Tab(
        label="TÀI CHÍNH",
        tab_id="tab-financial",
        children=create_tab_tai_chinh()
    ),
    dbc.Tab(
        label="CHỈ SỐ",
        tab_id="tab-metrics",
        children=create_tab_chi_so()
    ),
    dbc.Tab(
        label="KỸ THUẬT",
        tab_id="tab-technical",
        children=html.Div([
            dcc.Loading(type="dot", color="#ff3d57", children=[
                html.Div(id="tab-technical-content", style={"padding": "20px"})
            ])
        ])
    ),
], id="detail-tabs", active_tab="tab-overview", style={"marginTop": "10px", "borderBottom": "2px solid #163660"})

# === MODALS ===
detail_modal = dbc.Modal(
    [
        dbc.ModalHeader(
            children=html.Div([
                html.Button("PDF", id="btn-export-pdf", n_clicks=0,
                            title="Xuất báo cáo PDF kỹ thuật",
                            style={
                                "width": "30px", "height": "30px",
                                "backgroundColor": "#D32F2F", "color": "#fff",
                                "border": "none", "borderRadius": "4px",
                                "fontSize": "13px", "fontWeight": "700",
                                "cursor": "pointer", "flexShrink": "0", "marginRight": "10px",
                                "boxShadow": "0 2px 8px rgba(211,47,47,0.45)",
                                "display": "inline-flex", "alignItems": "center",
                                "justifyContent": "center", "verticalAlign": "middle",
                            }),
                html.Span("Phân tích chi tiết", id="modal-title",
                          style={"fontWeight": "600", "fontSize": "0.95rem",
                                 "color": "#e6edf3", "verticalAlign": "middle"}),
                dcc.Download(id="pdf-download"),
                html.Span(id="pdf-export-status",
                          style={"fontSize": "0.75rem", "color": "#8b949e",
                                 "marginLeft": "12px", "fontStyle": "italic"}),
            ], style={"display": "flex", "alignItems": "center"}),
            close_button=True,
        ),
        dbc.ModalBody(
            children=detail_tabs,
            style={"height": "80vh", "overflowY": "auto"}
        ),
    ],
    id="detail-modal",
    size="xl", is_open=False, centered=True, backdrop=True,
)

strategy_info_offcanvas = dbc.Offcanvas(
    id="strategy-info-offcanvas",
    title="Thông tin Trường phái",
    is_open=False, placement="end", scrollable=True,
    style={"width": "450px", "backgroundColor": "#091526", "color": "#d6eaf8"}
)

# Import các modal mới
from src.callbacks.score_breakdown_callbacks import score_breakdown_modal
from src.callbacks.compare_callbacks import compare_modal
from src.callbacks.portfolio_callbacks import portfolio_modal, portfolio_store
from src.callbacks.alert_callbacks import alert_modal, alert_store, alert_interval

# === MAIN LAYOUT ===
layout = html.Div([
    # Stores
    portfolio_store,
    alert_store,
    alert_interval,
    dcc.Store(id="fin-chart-period-store", data="quarterly"),  # ← period store cho biểu đồ TC
    dcc.Store(id="fin-chart-selection-store", data=[]),  # ← template store (persist across tabs)

    # Top Filter Panel
    sidebar.layout,

    # Main Content Area
    html.Div([
        # Page Header + Action Buttons
        html.Div([
            html.Div([
                html.Div([
                    html.I(className="fas fa-chart-bar", style={
                        "color": "#00a651", "marginRight": "10px", "fontSize": "16px"
                    }),
                    html.Div([
                        html.B("VIETCAP SMART SCREENER - KẾT QUẢ SÀNG LỌC"),
                        html.Span(id="data-cutoff-label", style={
                            "fontSize": "11px", "color": "#5a8ab0",
                            "fontFamily": "'JetBrains Mono', monospace",
                            "marginLeft": "10px", "fontWeight": "400",
                            "letterSpacing": "0.3px",
                        }),
                    ], style={"display": "flex", "alignItems": "center"})
                ], style={"display": "flex", "alignItems": "center", "marginBottom": "4px"}),
                html.Div([
                    html.I(className="fas fa-filter", style={
                        "color": "#00a651", "marginRight": "6px", "fontSize": "10px"
                    }),
                    dcc.Loading(
                        type="circle",
                        color="#00a651",
                        style={"display": "inline-block"},
                        children=[
                            html.Span(id="result-count", style={
                                "fontFamily": "'JetBrains Mono', monospace",
                                "fontSize": "12px", "color": "#5a8ab0", "letterSpacing": "0.5px"
                            }),
                        ]
                    ),
                ], style={"display": "flex", "alignItems": "center"}),
            ], style={"flex": "1"}),

            # Action buttons
            html.Div([

                # Export CSV
                dbc.Button(
                    [html.I(className="fas fa-download", style={"marginRight": "5px"}),
                     html.Span("CSV", id="label-export-btn")],
                    id="btn-export-csv",
                    color="success", outline=True, size="sm",
                    style={"borderRadius": "6px", "fontSize": "11px",
                           "padding": "4px 10px", "whiteSpace": "nowrap"},
                ),
                # Export Excel
                dbc.Button(
                    [html.I(className="fas fa-file-excel", style={"marginRight": "5px"}),
                     "Excel"],
                    id="btn-export-excel",
                    color="success", outline=True, size="sm",
                    style={"borderRadius": "6px", "fontSize": "11px",
                           "padding": "4px 10px", "whiteSpace": "nowrap",
                           "borderColor": "#1D6F42", "color": "#1D6F42"},
                ),
                # Watchlist
                dbc.Button(
                    [html.I(className="fas fa-eye", style={"marginRight": "5px"}),
                     html.Span("Watchlist", id="label-watchlist-btn")],
                    id="btn-watchlist",
                    color="warning", outline=True, size="sm",
                    style={"borderRadius": "6px", "fontSize": "11px",
                           "padding": "4px 10px", "whiteSpace": "nowrap"},
                ),
                # Heatmap
                dbc.Button([
                    html.I(className="fas fa-th-large", style={"marginRight": "5px"}),
                    "Heatmap",
                ], id="btn-heatmap", color="secondary", outline=True, size="sm",
                    style={"borderRadius": "6px", "fontSize": "11px"}),

                # So sánh
                dbc.Button([
                    html.I(className="fas fa-code-compare", style={"marginRight": "5px"}),
                    "So sánh",
                ], id="btn-compare", color="info", outline=True, size="sm",
                    style={"borderRadius": "6px", "fontSize": "11px"}),

                # Portfolio
                dbc.Button([
                    html.I(className="fas fa-briefcase", style={"marginRight": "5px"}),
                    "Danh mục",
                ], id="btn-portfolio", color="warning", outline=True, size="sm",
                    style={"borderRadius": "6px", "fontSize": "11px"}),

                # Alerts
                html.Div([
                    dbc.Button([
                        html.I(className="fas fa-bell", style={"marginRight": "5px"}),
                        "Cảnh báo",
                    ], id="btn-alerts", color="danger", outline=True, size="sm",
                        style={"borderRadius": "6px", "fontSize": "11px"}),
                    html.Span("0", id="alert-badge", style={"display": "none"}),
                ], style={"position": "relative"}),

            ], style={"display": "flex", "gap": "8px", "alignItems": "center"}),
        ], style={
            "display": "flex", "alignItems": "center", "justifyContent": "space-between",
            "padding": "12px 0 10px 2px",
            "borderBottom": "1px solid #0e2540", "marginBottom": "12px",
        }),

        # Heatmap panel (collapse, ẩn mặc định)
        dbc.Collapse(
            html.Div([
                html.Div([
                    html.Span("Sector Heatmap", style={
                        "fontSize": "12px", "fontWeight": "700", "color": "#c9d1d9", "flex": "1",
                    }),
                    dcc.Dropdown(
                        id="heatmap-metric",
                        options=[
                            {"label": "% 1 tuần", "value": "Perf_1W"},
                            {"label": "% 1 tháng", "value": "Perf_1M"},
                            {"label": "% 3 tháng", "value": "Perf_3M"},
                            {"label": "% 1 năm", "value": "Perf_1Y"},
                        ],
                        value="Perf_1W",
                        clearable=False,
                        className="ssi-dropdown-custom",
                        style={"width": "140px"},
                    ),
                ], style={"display": "flex", "alignItems": "center", "gap": "10px",
                          "marginBottom": "8px"}),
                dcc.Graph(id="sector-heatmap-graph", style={"height": "1px", "visibility": "hidden"},
                          config={"displayModeBar": False}),
                html.Div(id="heatmap-html-container"),
            ], style={"padding": "14px", "backgroundColor": "#0c1220",
                      "border": "1px solid #21262d", "borderRadius": "8px",
                      "marginBottom": "14px"}),
            id="heatmap-collapse", is_open=False,
        ),

        # KHU VỰC BẢNG SCREENER — spinner ở result-count, không bọc AG Grid
        html.Div([
            html.Div([
                dag.AgGrid(
                    id="screener-table",
                    rowData=[],
                    columnDefs=columnDefs,
                    defaultColDef={
                        "resizable": True,
                        "sortable": True,
                        "filter": False,
                        "tooltipShowDelay": 300,
                    },
                    className="ag-theme-alpine-dark ssi-screener-grid",
                    style={"width": "100%"},
                    dashGridOptions={
                        "domLayout": "autoHeight",
                        "pagination": True,
                        "paginationPageSize": 20,
                        "rowSelection": "single",
                        "animateRows": True,
                        "enableCellChangeFlash": False,
                        "rowHeight": 45,
                        # ── THÊM: Sort mặc định theo Volume giảm dần ──
                        "initialState": {
                            "sort": {
                                "sortModel": [{"colId": "Volume", "sort": "desc"}]
                            }
                        },
                        "getRowStyle": _ROW_STYLE,
                        "tooltipShowDelay": 300,
                        "tooltipHideDelay": 5000,
                        "suppressLoadingOverlay": True,
                        "suppressNoRowsOverlay": False,
                    }
                )
            ], className="info-card mb-3")
        ]),

    ], className="main-content"),

    # Modals & Popups
    detail_modal,
    strategy_info_offcanvas,
    score_breakdown_modal,
    compare_modal,
    portfolio_modal,
    alert_modal,

    # ── Hint Modal — gợi ý double-click ──────────────────────────────────
    dbc.Modal([
        dbc.ModalBody([
            html.Div([
                # Icon góc trên phải đóng
                html.Button("×", id="hint-modal-close", n_clicks=0, style={
                    "position": "absolute", "top": "12px", "right": "16px",
                    "background": "none", "border": "none",
                    "color": "#484f58", "fontSize": "20px", "cursor": "pointer",
                    "lineHeight": "1", "padding": "0",
                }),

                # Icon chính
                html.Div([
                    html.I(className="fas fa-computer-mouse", style={
                        "fontSize": "28px",
                        "color": "#00a651",
                        "filter": "drop-shadow(0 0 8px rgba(0,212,255,0.5))",
                    }),
                ], style={"marginBottom": "14px"}),

                # Tiêu đề
                html.Div("Mẹo sử dụng", style={
                    "fontFamily": "'JetBrains Mono', monospace",
                    "fontSize": "11px", "fontWeight": "700",
                    "color": "#00a651", "letterSpacing": "2px",
                    "textTransform": "uppercase", "marginBottom": "10px",
                }),

                # Nội dung chính
                html.P([
                    "Nhấp đúp chuột (", html.Strong("double-click", style={"color": "#00a651"}),
                    ") vào bất kỳ mã cổ phiếu nào trong bảng kết quả để xem ",
                    html.Strong("hồ sơ phân tích chi tiết", style={"color": "#c9d1d9"}),
                    " — bao gồm biểu đồ giá, báo cáo tài chính và chỉ số kỹ thuật.",
                ], style={
                    "fontFamily": "'Sora', sans-serif",
                    "fontSize": "13px", "color": "#8b949e",
                    "lineHeight": "1.7", "marginBottom": "16px",
                }),

                # Divider
                html.Hr(style={"borderColor": "#21262d", "margin": "0 0 14px 0"}),

                # Các gợi ý nhỏ
                html.Div([
                    html.Div([
                        html.I(className="fas fa-filter",
                               style={"color": "#3fb950", "width": "16px", "marginRight": "8px", "fontSize": "11px"}),
                        html.Span("Dùng panel bộ lọc bên trái để thu hẹp danh sách",
                                  style={"fontSize": "12px", "color": "#6e7681"}),
                    ], style={"display": "flex", "alignItems": "center", "marginBottom": "7px"}),
                    html.Div([
                        html.I(className="fas fa-code-compare",
                               style={"color": "#4caf50", "width": "16px", "marginRight": "8px", "fontSize": "11px"}),
                        html.Span("Chọn nhiều mã rồi bấm \"So sánh\" để xem hiệu suất tương đối",
                                  style={"fontSize": "12px", "color": "#6e7681"}),
                    ], style={"display": "flex", "alignItems": "center", "marginBottom": "7px"}),
                    html.Div([
                        html.I(className="fas fa-wand-magic-sparkles",
                               style={"color": "#d2a8ff", "width": "16px", "marginRight": "8px", "fontSize": "11px"}),
                        html.Span("Chọn \"Trường phái\" để áp dụng chiến lược đầu tư kinh điển ngay",
                                  style={"fontSize": "12px", "color": "#6e7681"}),
                    ], style={"display": "flex", "alignItems": "center"}),
                ]),
                # Cảnh báo HuggingFace
                html.Div([
                    html.Div([
                        html.I(className="fas fa-triangle-exclamation",
                               style={"color": "#e3b341", "marginRight": "8px", "fontSize": "12px"}),
                        html.Span("Đang chạy trên Hugging Face?", style={
                            "fontSize": "11px", "fontWeight": "700", "color": "#e3b341",
                        }),
                    ], style={"display": "flex", "alignItems": "center", "marginBottom": "5px"}),
                    html.Span(
                        "Phiên bản online có thể bị giật lag các chức năng do RAM & CPU giới hạn (free tier). "
                        "Để trải nghiệm mượt nhất, hãy tải mã nguồn về và chạy local!",
                        style={"fontSize": "11px", "color": "#7d6608", "lineHeight": "1.5"},
                    ),
                ], style={
                    "backgroundColor": "rgba(227,179,65,0.08)",
                    "border": "1px solid rgba(227,179,65,0.25)",
                    "borderRadius": "6px", "padding": "10px 12px",
                    "marginTop": "14px", "textAlign": "left",
                }),
                # Nút đóng
                html.Div([
                    dbc.Button("Đã hiểu!", id="hint-modal-ok", size="sm", style={
                        "background": "linear-gradient(135deg, #007a3d, #00a651)",
                        "border": "none", "borderRadius": "6px",
                        "fontFamily": "'JetBrains Mono', monospace",
                        "fontSize": "11px", "fontWeight": "700",
                        "color": "#001a20", "letterSpacing": "0.5px",
                        "padding": "6px 20px", "marginTop": "18px",
                    }),
                ], style={"textAlign": "center"}),

            ], style={"position": "relative", "padding": "8px 4px 4px 4px", "textAlign": "center"}),
        ], style={
            "backgroundColor": "#0d1117",
            "border": "1px solid #21262d",
            "borderRadius": "10px",
            "padding": "24px",
        }),
    ],
        id="hint-modal",
        is_open=False,
        centered=True,
        backdrop=True,
        size="sm",
        style={"fontFamily": "'Sora', sans-serif"},
        contentClassName="bg-transparent border-0 p-0",
    ),

    # Store để nhớ đã hiển thị hint chưa (persist qua session)
    dcc.Store(id="hint-shown-store", storage_type="session", data=False),
    # 🟢 THÊM DÒNG NÀY: Store để nhớ người dùng đang ở bước mấy của Tour
    dcc.Store(id="tour-step-store", storage_type="memory", data=1),
    # Store tạm chứa ticker được chọn — để render modal nhanh trước, load data sau
    dcc.Store(id="selected-ticker-store", data=None),
    dcc.Store(id="selected-stock-store", data=None),   # ← store cho detail modal 2-phase
# ── ZALO CHAT BUBBLE ──────────────────────────────────────────────────────
html.Div(children=[

    # Nút X đóng bubble
    html.Button("×", id="zalo-bubble-close", n_clicks=0, style={
        "position": "absolute", "top": "-8px", "right": "-8px",
        "width": "20px", "height": "20px",
        "borderRadius": "50%", "border": "none",
        "backgroundColor": "#ef4444", "color": "white",
        "fontSize": "12px", "fontWeight": "bold",
        "cursor": "pointer", "lineHeight": "1",
        "display": "flex", "alignItems": "center", "justifyContent": "center",
        "zIndex": "10001", "padding": "0",
    }),

    # Chấm đỏ thông báo
    html.Div(style={
        "position": "absolute", "top": "0px", "left": "0px",
        "width": "14px", "height": "14px",
        "borderRadius": "50%", "backgroundColor": "#ef4444",
        "border": "2px solid #0d1117",
        "animation": "pulse-red 1.5s infinite",
        "zIndex": "10001",
    }),

    # Icon Zalo
    html.Img(
        src="/assets/zalo.png",
        id="zalo-icon-btn",
        n_clicks=0,
        style={
            "width": "56px", "height": "56px",
            "borderRadius": "50%",
            "cursor": "pointer",
            "boxShadow": "0 4px 20px rgba(0,100,255,0.4)",
            "border": "2px solid #0068ff",
            "display": "block",
        }
    ),

], id="zalo-bubble-container", style={
    "position": "fixed", "bottom": "28px", "right": "28px",
    "zIndex": "10000", "display": "flex", "flexDirection": "column",
    "alignItems": "center",
}),

# ── ZALO CHAT WINDOW ──────────────────────────────────────────────────────
html.Div([
    # Header
    html.Div([
        html.Div([
            html.Img(src="/assets/zalo.png",
                     style={"width": "28px", "height": "28px", "borderRadius": "50%", "marginRight": "8px"}),
            html.Div([
                html.Div("Tư vấn đầu tư", style={
                    "fontWeight": "700", "fontSize": "13px", "color": "#ffffff"}),
                html.Div("● Trực tuyến", style={
                    "fontSize": "11px", "color": "#4ade80"}),
            ]),
        ], style={"display": "flex", "alignItems": "center"}),
        html.Button("×", id="zalo-chat-close", n_clicks=0, style={
            "background": "none", "border": "none", "color": "#ffffff",
            "fontSize": "20px", "cursor": "pointer", "padding": "0",
            "lineHeight": "1",
        }),
    ], style={
        "background": "linear-gradient(135deg, #0068ff, #0050cc)",
        "padding": "12px 16px",
        "display": "flex", "justifyContent": "space-between", "alignItems": "center",
        "borderRadius": "12px 12px 0 0",
    }),

    # Messages area
    html.Div([
        # Tin nhắn chào
        html.Div([
            html.Img(src="/assets/zalo.png",
                     style={"width": "28px", "height": "28px", "borderRadius": "50%",
                            "marginRight": "8px", "flexShrink": "0", "alignSelf": "flex-end"}),
            html.Div([
                html.Div("Vietcap Smart Screener", style={
                    "fontSize": "10px", "color": "#8b949e", "marginBottom": "4px"}),
                html.Div(
                    "Xin chào! 👋 Tôi là trợ lý tự động của Vietcap Smart Screener. "
                    "Hãy để lại tin nhắn — đội ngũ tư vấn đầu tư của chúng tôi sẽ liên hệ lại qua Zalo sớm nhất!",
                    style={
                        "backgroundColor": "#1e2d3d",
                        "border": "1px solid #30363d",
                        "borderRadius": "0 12px 12px 12px",
                        "padding": "10px 14px",
                        "fontSize": "13px", "color": "#c9d1d9",
                        "lineHeight": "1.6",
                    }
                ),
            ]),
        ], style={"display": "flex", "alignItems": "flex-start", "marginBottom": "12px"}),

        # Gợi ý nhanh
        html.Div([
            html.Div("💬 Tôi muốn tư vấn danh mục", style={
                "border": "1px solid #0068ff", "borderRadius": "20px",
                "padding": "6px 14px", "fontSize": "12px", "color": "#58a6ff",
                "cursor": "pointer", "marginBottom": "6px",
                "backgroundColor": "#0d1829",
            }),
            html.Div("📊 Hỏi về cổ phiếu cụ thể", style={
                "border": "1px solid #0068ff", "borderRadius": "20px",
                "padding": "6px 14px", "fontSize": "12px", "color": "#58a6ff",
                "cursor": "pointer",
                "backgroundColor": "#0d1829",
            }),
        ], style={"marginLeft": "36px"}),

    ], style={
        "padding": "16px",
        "minHeight": "200px",
        "backgroundColor": "#0d1117",
        "overflowY": "auto",
    }),

    # Input area
    html.Div([
        dcc.Input(
            id="zalo-chat-input",
            placeholder="Nhập tin nhắn...",
            debounce=False,
            style={
                "flex": "1", "backgroundColor": "#161b22",
                "border": "1px solid #30363d", "borderRadius": "20px",
                "padding": "8px 14px", "color": "#c9d1d9", "fontSize": "13px",
                "outline": "none",
            }
        ),
        html.Button(
            html.I(className="fas fa-paper-plane"),
            id="zalo-chat-send", n_clicks=0,
            style={
                "marginLeft": "8px", "backgroundColor": "#0068ff",
                "border": "none", "borderRadius": "50%",
                "width": "36px", "height": "36px",
                "color": "white", "cursor": "pointer", "fontSize": "14px",
            }
        ),
    ], style={
        "display": "flex", "alignItems": "center",
        "padding": "12px 16px",
        "borderTop": "1px solid #21262d",
        "backgroundColor": "#0d1117",
        "borderRadius": "0 0 12px 12px",
    }),

], id="zalo-chat-window", style={
    "display": "none",   # ẩn mặc định
    "position": "fixed", "bottom": "96px", "right": "28px",
    "width": "320px",
    "border": "1px solid #30363d",
    "borderRadius": "12px",
    "boxShadow": "0 8px 32px rgba(0,0,0,0.6)",
    "zIndex": "9999",
    "fontFamily": "'Sora', sans-serif",
}),
], style={"width": "100%"})