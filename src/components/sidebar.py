# src/components/sidebar.py
# Bộ lọc dạng INLINE PANEL phía trên bảng screener.
# - Thay thế dbc.Offcanvas bằng dbc.Collapse(id="filter-offcanvas")
#   → callback toggle_filter_offcanvas trong screener_callbacks.py KHÔNG thay đổi gì.
# - Toàn bộ IDs, Stores, logic giữ nguyên 100%.

from dash import html, dcc
import dash_bootstrap_components as dbc
from src.constants import SECTOR_TRANSLATION

# Để trống — callback auto_update_dropdowns trong screener_callbacks.py
# sẽ tự động điền đúng danh sách ngành từ snapshot thực tế khi page load.
# Không hardcode 11 ngành GICS lớn vì VN data dùng cấp sub-industry.
sector_options = []


# ── Premium wrapper helper ────────────────────────────────────────────────────
# Bao bọc content trong premium-locked div.
# auth_callbacks.update_premium_gates() toggle className giữa
#   "premium-wrapper premium-locked" ↔ "premium-wrapper premium-unlocked"
def _premium_wrap(content, wrapper_id: str, section: str, label: str = "Đăng nhập"):
    return html.Div(
        id=wrapper_id,
        className="premium-wrapper premium-locked",
        children=[
            # Nội dung thực — bị blur khi locked
            html.Div(content, className="premium-content"),
            # Overlay khóa — click để mở login modal
            html.Div(
                id={"type": "premium-overlay-btn", "section": section},
                n_clicks=0,
                className="premium-overlay",
                children=[
                    html.I(className="fas fa-lock",
                           style={"fontSize": "10px", "color": "#00a651",
                                  "marginBottom": "2px"}),
                    html.Span(label,
                              style={"fontSize": "9.5px", "fontWeight": "600",
                                     "color": "#6e7681", "whiteSpace": "nowrap"}),
                ],
            ),
        ],
    )


# ── Lấy min/max thực tế từ parquet để set data cho dcc.Store ──
def _get_r(ranges, key, fallback):
    return ranges.get(key, fallback)


try:
    from src.backend.data_loader import get_filter_ranges as _get_filter_ranges

    _DR = _get_filter_ranges()
except Exception:
    _DR = {}


# ============================================================================
# HELPER FUNCTIONS  (giữ nguyên)
# ============================================================================

def create_criteria_item(id_suffix, label):
    return html.Div(
        [
            html.I(className="fas fa-plus-circle",
                   style={"color": "#58a6ff", "marginRight": "8px", "fontSize": "11px"}),
            html.Span(label, style={"color": "#c9d1d9", "fontSize": "12px", "fontWeight": "500"}),
        ],
        id={"type": "criteria-item", "index": id_suffix},
        n_clicks=0,
        style={
            "padding": "7px 12px",
            "borderBottom": "1px solid #21262d",
            "cursor": "pointer",
            "transition": "background 0.15s",
            "display": "flex",
            "alignItems": "center",
        },
        className="criteria-item-hover",
    )


def collapse_group(btn_id, collapse_id, title, items, is_open=False, icon="fas fa-chart-bar", color="#8b949e",
                   title_id=None):
    return html.Div(
        [
            html.Div(
                [
                    html.I(className=icon, style={"marginRight": "7px", "color": color, "fontSize": "10px"}),
                    html.Span(title, id=title_id, style={"flex": "1", "fontSize": "11px", "fontWeight": "700",
                                                         "color": color}) if title_id else html.Span(title,
                                                                                                     style={"flex": "1",
                                                                                                            "fontSize": "11px",
                                                                                                            "fontWeight": "700",
                                                                                                            "color": color}),
                    html.I(className="fas fa-chevron-down", style={"fontSize": "9px", "color": "#6e7681"}),
                ],
                id=btn_id,
                className="collapse-header",
                style={
                    "display": "flex",
                    "alignItems": "center",
                    "padding": "8px 12px",
                    "cursor": "pointer",
                    "borderBottom": "1px solid #21262d",
                    "backgroundColor": "#0d1117",
                },
            ),
            dbc.Collapse(items, id=collapse_id, is_open=is_open),
        ]
    )


# ============================================================================
# CRITERIA GROUPS  (giữ nguyên)
# ============================================================================

TONG_QUAN_ITEMS = [
    create_criteria_item("price", "Giá hiện tại (VND)"),
    create_criteria_item("volume", "Khối lượng giao dịch"),
    create_criteria_item("market-cap", "Vốn hóa thị trường"),
    create_criteria_item("eps", "EPS (Thu nhập/CP)"),
    create_criteria_item("roe", "ROE (%)"),
    create_criteria_item("pe", "P/E Ratio"),
    create_criteria_item("rs-3d", "RS 3 ngày"),
]

DINH_GIA_ITEMS = [
    create_criteria_item("pb", "P/B Ratio"),
    create_criteria_item("ps", "P/S Ratio"),
    # create_criteria_item("ev-ebitda", "EV/EBITDA"),
    create_criteria_item("ev", "Giá trị doanh nghiệp (EV)"),
    create_criteria_item("div-yield", "Tỷ suất Cổ tức (%)"),
]

SINH_LOI_ITEMS = [
    create_criteria_item("roa", "ROA (%)"),
    create_criteria_item("gross-margin", "Biên LN gộp (%)"),
    create_criteria_item("net-margin", "Biên LN ròng (%)"),
    create_criteria_item("ebit-margin", "Biên EBIT (%)"),
]

TANG_TRUONG_ITEMS = [
    create_criteria_item("rev-growth-yoy", "% Tăng trưởng DT 1 năm"),
    create_criteria_item("rev-cagr-5y", "% Tăng trưởng DT 5 năm"),
    create_criteria_item("eps-growth-yoy", "% Tăng trưởng EPS 1 năm"),
    create_criteria_item("eps-cagr-5y", "% Tăng trưởng EPS 5 năm"),
]

SUC_KHOE_TC_ITEMS = [
    create_criteria_item("de", "D/E (Nợ vay / VCSH)"),
    create_criteria_item("current-ratio", "Tỷ lệ thanh toán hiện hành"),
    create_criteria_item("net-cash-cap", "Tiền mặt ròng / Vốn hóa (%)"),
    create_criteria_item("net-cash-assets", "Tiền mặt ròng / Tổng TS (%)"),
]

GIA_VS_MA_ITEMS = [
    create_criteria_item("price-vs-sma5", "Giá vs SMA(5) (%)"),
    create_criteria_item("price-vs-sma10", "Giá vs SMA(10) (%)"),
    create_criteria_item("price-vs-sma20", "Giá vs SMA(20) (%)"),
    create_criteria_item("price-vs-sma50", "Giá vs SMA(50) (%)"),
    create_criteria_item("price-vs-sma100", "Giá vs SMA(100) (%)"),
    create_criteria_item("price-vs-sma200", "Giá vs SMA(200) (%)"),
]

HIGH_LOW_ITEMS = [
    create_criteria_item("break-high-52w", "Vượt đỉnh 52 tuần"),
    create_criteria_item("break-low-52w", "Phá đáy 52 tuần"),
    create_criteria_item("pct-from-high-1y", "% Cách đỉnh 1 năm"),
    create_criteria_item("pct-from-low-1y", "% Cách đáy 1 năm"),
    create_criteria_item("pct-from-high-all", "% Cách đỉnh lịch sử"),
    create_criteria_item("pct-from-low-all", "% Cách đáy lịch sử"),
]

CHI_BAO_KT_ITEMS = [
    create_criteria_item("rsi14", "RSI (14)"),
    create_criteria_item("rsi-state", "Trạng thái RSI(14)"),
    create_criteria_item("macd-hist", "MACD Histogram"),
    create_criteria_item("bb-width", "Mở Band Bollinger (%)"),
    create_criteria_item("consec-up", "Phiên tăng liên tiếp"),
    create_criteria_item("consec-down", "Phiên giảm liên tiếp"),
]

MOMENTUM_ITEMS = [
    create_criteria_item("beta", "Beta"),
    create_criteria_item("alpha", "Alpha (% năm)"),
    create_criteria_item("rs-1m", "RS 1 tháng"),
    create_criteria_item("rs-3m", "RS 3 tháng"),
    create_criteria_item("rs-1y", "RS 1 năm"),
    create_criteria_item("rs-avg", "RS Trung bình"),
]

VOLUME_KT_ITEMS = [
    create_criteria_item("vol-vs-sma5", "KL so với SMA(5)"),
    create_criteria_item("vol-vs-sma10", "KL so với SMA(10)"),
    create_criteria_item("vol-vs-sma20", "KL so với SMA(20)"),
    create_criteria_item("vol-vs-sma50", "KL so với SMA(50)"),
    create_criteria_item("avg-vol-5d", "KL TB 5 phiên"),
    create_criteria_item("avg-vol-10d", "KL TB 10 phiên"),
    create_criteria_item("avg-vol-50d", "KL TB 50 phiên"),
    create_criteria_item("gtgd-1w", "GTGD 1 tuần (VND)"),
    create_criteria_item("gtgd-10d", "GTGD 10 ngày (VND)"),
    create_criteria_item("gtgd-1m", "GTGD 1 tháng (VND)"),
]

# ============================================================================
# WIZARD PANEL – 3 CỘT: Nhóm → Tiêu chí → Slider
# ============================================================================

# Định nghĩa các nhóm và tiêu chí tương ứng
WIZARD_GROUPS = [
    {
        "id": "tong-quan",
        "label": "Thông tin chung",
        "icon": "fas fa-info-circle",
        "color": "#58a6ff",
        "items": TONG_QUAN_ITEMS,
    },
    {
        "id": "dinh-gia",
        "label": "Định giá",
        "icon": "fas fa-tag",
        "color": "#3fb950",
        "items": DINH_GIA_ITEMS,
    },
    {
        "id": "sinh-loi",
        "label": "Khả năng sinh lời",
        "icon": "fas fa-percent",
        "color": "#3fb950",
        "items": SINH_LOI_ITEMS,
    },
    {
        "id": "tang-truong",
        "label": "Tăng trưởng",
        "icon": "fas fa-chart-line",
        "color": "#58a6ff",
        "items": TANG_TRUONG_ITEMS,
    },
    {
        "id": "suc-khoe",
        "label": "Chỉ số tài chính",
        "icon": "fas fa-heartbeat",
        "color": "#f85149",
        "items": SUC_KHOE_TC_ITEMS,
    },
    {
        "id": "gia-sma",
        "label": "Biến động giá & KL",
        "icon": "fas fa-wave-square",
        "color": "#a78bfa",
        "items": GIA_VS_MA_ITEMS + HIGH_LOW_ITEMS,
    },
    {
        "id": "ky-thuat",
        "label": "Chỉ báo kỹ thuật",
        "icon": "fas fa-chart-area",
        "color": "#a78bfa",
        "items": CHI_BAO_KT_ITEMS,
    },
    {
        "id": "momentum",
        "label": "Hành vi thị trường",
        "icon": "fas fa-rocket",
        "color": "#a78bfa",
        "items": MOMENTUM_ITEMS + VOLUME_KT_ITEMS,
    },
]

# --- CỘT 1: Danh sách nhóm ---
_col1_groups = html.Div(
    [
        html.Div(
            [
                html.Span("Chọn điều kiện lọc",
                          style={"fontSize": "11px", "fontWeight": "700",
                                 "color": "#6e7681", "letterSpacing": "0.5px"}),
            ],
            style={
                "padding": "0 12px",
                "height": "38px",
                "display": "flex",
                "alignItems": "center",
                "borderBottom": "1px solid #21262d",
                "backgroundColor": "#161b22",
                "flexShrink": "0",
            },
        ),
        html.Div(
            [
                # Nhóm "momentum" được wrap premium, các nhóm còn lại render bình thường
                _premium_wrap(
                    content=html.Div(
                        [
                            html.Span(g["label"], style={
                                "fontSize": "12px", "fontWeight": "600",
                                "color": "#c9d1d9", "flex": "1",
                            }),
                            html.Span(
                                "0",
                                id={"type": "wizard-group-badge", "group": g["id"]},
                                style={
                                    "fontSize": "10px", "fontWeight": "700",
                                    "color": "#ff3d57",
                                    "backgroundColor": "rgba(255,61,87,0.15)",
                                    "border": "1px solid rgba(255,61,87,0.3)",
                                    "borderRadius": "10px",
                                    "padding": "1px 6px",
                                    "minWidth": "18px",
                                    "textAlign": "center",
                                    "display": "none",
                                },
                            ),
                            html.I(className="fas fa-chevron-right",
                                   style={"fontSize": "9px", "color": "#484f58",
                                          "marginLeft": "6px"}),
                        ],
                        id={"type": "wizard-group-btn", "group": g["id"]},
                        n_clicks=0,
                        style={
                            "display": "flex", "alignItems": "center",
                            "padding": "9px 14px",
                            "cursor": "pointer",
                            "borderBottom": "1px solid #21262d",
                            "transition": "background 0.15s",
                            "backgroundColor": "#0d1117",
                        },
                        className="wizard-group-item",
                    ),
                    wrapper_id="pw-momentum",
                    section="momentum",
                    label="Hành vi TT · VIP",
                ) if g["id"] == "momentum" else
                html.Div(
                    [
                        html.Span(g["label"], style={
                            "fontSize": "12px", "fontWeight": "600",
                            "color": "#c9d1d9", "flex": "1",
                        }),
                        # Badge đếm số tiêu chí đang active trong nhóm này
                        html.Span(
                            "0",
                            id={"type": "wizard-group-badge", "group": g["id"]},
                            style={
                                "fontSize": "10px", "fontWeight": "700",
                                "color": "#ff3d57",
                                "backgroundColor": "rgba(255,61,87,0.15)",
                                "border": "1px solid rgba(255,61,87,0.3)",
                                "borderRadius": "10px",
                                "padding": "1px 6px",
                                "minWidth": "18px",
                                "textAlign": "center",
                                "display": "none",  # ẩn khi = 0, callback sẽ show khi > 0
                            },
                        ),
                        html.I(className="fas fa-chevron-right",
                               style={"fontSize": "9px", "color": "#484f58", "marginLeft": "6px"}),
                    ],
                    id={"type": "wizard-group-btn", "group": g["id"]},
                    n_clicks=0,
                    style={
                        "display": "flex", "alignItems": "center",
                        "padding": "9px 14px",
                        "cursor": "pointer",
                        "borderBottom": "1px solid #21262d",
                        "transition": "background 0.15s",
                        "backgroundColor": "#0d1117",
                    },
                    className="wizard-group-item",
                )
                for g in WIZARD_GROUPS
            ],
            style={
                "overflowY": "auto",
                "backgroundColor": "#0d1117",
                "scrollbarWidth": "thin",
                "scrollbarColor": "#30363d #0d1117",
            },
        ),
    ],
    style={
        "flex": "0 0 222px",
        "borderRight": "1px solid #21262d",
        "display": "flex",
        "flexDirection": "column",
        "overflow": "hidden",
    },
)

# --- CỘT 2: Danh sách tiêu chí trong nhóm được chọn ---
_col2_criteria = html.Div(
    [
        html.Div(
            [
                html.I(className="fas fa-chevron-right",
                       style={"color": "#484f58", "fontSize": "10px", "margin": "0 6px"}),
                html.Span("Chọn tiêu chí",
                          id="wizard-col2-title",
                          style={"fontSize": "11px", "fontWeight": "700", "color": "#6e7681"}),
            ],
            style={
                "padding": "0 12px",
                "height": "38px",
                "display": "flex",
                "alignItems": "center",
                "borderBottom": "1px solid #21262d",
                "backgroundColor": "#161b22",
                "flexShrink": "0",
            },
        ),
        html.Div(
            # Nội dung được inject bởi callback khi chọn nhóm
            id="wizard-col2-content",
            style={
                "overflowY": "auto",
                "backgroundColor": "#0d1117",
                "flex": "1",
                "scrollbarWidth": "thin",
                "scrollbarColor": "#30363d #0d1117",
            },
        ),
    ],
    style={
        "flex": "0 0 222px",
        "borderRight": "1px solid #21262d",
        "display": "flex",
        "flexDirection": "column",
        "overflow": "hidden",
    },
)

# --- CỘT 3: Slider / filter cards đã chọn ---
_col3_filters = html.Div(
    [
        # Header với breadcrumb + nút reset/save
        html.Div(
            [
                html.Div([
                    html.I(className="fas fa-chevron-right",
                           style={"color": "#484f58", "fontSize": "10px", "margin": "0 6px"}),
                    html.Span("Nhập số hoặc kéo chọn",
                              style={"fontSize": "11px", "fontWeight": "700", "color": "#6e7681"}),
                ], style={"display": "flex", "alignItems": "center", "flex": "1"}),

                # Dropdown lọc năm
                dcc.Dropdown(
                    id="filter-year-dropdown",
                    options=[{"label": "Toàn bộ", "value": "all"}]
                           + [{"label": str(y), "value": y} for y in range(2019, 2025)],
                    value="all",
                    clearable=False,
                    searchable=False,
                    style={
                        "width": "88px",
                        "fontSize": "11px",
                        "color": "#c9d1d9",
                        "flexShrink": "0",
                        "marginRight": "6px",
                    },
                    className="year-filter-dropdown",
                ),

                # Nút Tải lại + Xóa tất cả
                html.Div([
                    dbc.Button(
                        [html.I(className="fas fa-sync-alt",
                                style={"fontSize": "10px", "marginRight": "4px"}),
                         "Tải lại kết quả"],
                        id="btn-filter", className="btn-apply-ssi",
                        n_clicks=0, size="sm",
                        style={"fontSize": "10px", "padding": "3px 8px",
                               "backgroundColor": "transparent",
                               "border": "1px solid #30363d", "color": "#8b949e", "display": "none"},
                    ),
                    dbc.Button(
                        [html.I(className="fas fa-times",
                                style={"fontSize": "10px", "marginRight": "4px"}),
                         "Xoá tất cả"],
                        id="btn-reset-ui", color="secondary", outline=True,
                        n_clicks=0, size="sm",
                        style={"fontSize": "10px", "padding": "3px 8px"},
                    ),
                    dbc.Button(
                        [html.I(className="fas fa-save", style={"fontSize": "10px", "marginRight": "4px"}),
                         "Lưu bộ lọc"],
                        id="btn-save", color="secondary", outline=True,
                        n_clicks=0, size="sm",
                        style={"fontSize": "10px", "padding": "3px 8px"},
                    ),
                ], style={"display": "flex", "gap": "6px", "alignItems": "center"}),
            ],
            style={
                "display": "flex",
                "justifyContent": "space-between",
                "alignItems": "center",
                "padding": "0 12px",
                "height": "38px",
                "backgroundColor": "#161b22",
                "borderBottom": "1px solid #21262d",
                "flexShrink": "0",
            },
        ),

        # Scrollable filter cards — dạng danh sách dọc như ảnh tham khảo
        html.Div(
            [],
            id="selected-filters-container",
            style={
                "padding": "6px 10px",
                "overflowY": "auto",
                "flex": "1",
                "backgroundColor": "#0d1117",
                "scrollbarWidth": "thin",
                "scrollbarColor": "#30363d #0d1117",
                "display": "flex",
                "flexDirection": "column",
                "gap": "4px",
            },
        ),
    ],
    style={
        "flex": "1",
        "display": "flex",
        "flexDirection": "column",
        "overflow": "hidden",
        "minWidth": "0",
    },
)

# Panel tổng hợp 3 cột
_filter_wizard = html.Div(
    [_col1_groups, _col2_criteria, _col3_filters],
    style={
        "display": "flex",
        "flexDirection": "row",
        "height": "266px",
        "border": "1px solid #21262d",
        "borderRadius": "8px",
        "overflow": "hidden",
        "backgroundColor": "#0d1117",
    },
)

# ============================================================================
# MAIN LAYOUT
# ============================================================================

layout = html.Div(
    [
        # ── Scroll anchor: auto-scroll xuống đây khi user chọn trường phái/ngành ──
        html.Div(id="screener-scroll-anchor", style={"height": "0", "overflow": "hidden"}),

        # ── CSS: fix màu chữ input trong ticker search dropdown ──

        # ── ALWAYS-VISIBLE HEADER BAR ──────────────────────────────────────
        html.Div(
            [
                # Left cluster: icon + title + toggle button
                html.Div(
                    [
                        # =======================================================
                        # 🟢 THANH TÌM KIẾM MÃ / TÊN CÔNG TY
                        # dcc.Dropdown searchable — options nạp động lúc app start
                        # =======================================================
                        html.Div([
                            html.I(
                                className="fas fa-search",
                                style={
                                    "position": "absolute",
                                    "left": "10px",
                                    "top": "50%",
                                    "transform": "translateY(-50%)",
                                    "color": "#8b949e",
                                    "fontSize": "12px",
                                    "zIndex": "10",
                                    "pointerEvents": "none",
                                }
                            ),
                            dcc.Dropdown(
                                id="search-ticker-input",
                                options=[],  # nạp động bởi ticker_search_callbacks.py
                                value=None,
                                placeholder="Tìm mã (VD: FPT)",
                                searchable=True,
                                clearable=True,
                                multi=False,
                                className="ssi-dropdown-custom ticker-search-dropdown",
                                style={
                                    "minWidth": "190px",
                                    "color": "#ffffff",  # màu chữ trắng khi gõ
                                },
                            ),
                        ], style={
                            "position": "relative",
                            "display": "flex",
                            "alignItems": "center",
                            "marginLeft": "10px",
                        }),
                        dbc.Button(
                            [html.I(className="fas fa-filter", style={"marginRight": "6px"}),
                             html.Span("BỘ LỌC", id="label-filter-btn", className="btn-filter-shimmer")],
                            id="toggle-filter-btn",
                            color="primary", outline=True, size="sm",
                            style={"borderRadius": "20px", "fontSize": "12px", "padding": "4px 14px"},
                        ),
                    ],
                    style={"display": "flex", "alignItems": "center", "gap": "16px"},
                ),

                # Center: Strategy dropdown
                html.Div(
                    [
                        html.Div(
                            [
                                html.I(className="fas fa-crown",
                                       style={"marginRight": "6px", "color": "#ffca28", "fontSize": "11px"}),
                                html.Span("Trường phái", id="label-strategy",
                                          style={"fontSize": "11px", "color": "#6e7681", "fontWeight": "600",
                                                 "marginRight": "8px", "whiteSpace": "nowrap"}),
                            ],
                            style={"display": "flex", "alignItems": "center"},
                        ), 
                        _premium_wrap(
                            content=dbc.InputGroup(
                                [
                                    dcc.Dropdown(
                                        id="strategy-preset-dropdown",
                                        options=[
                                            {"label": "[Vietcap] Khuyến nghị - Team TVĐT", "value": "STRAT_NCN"},
                                            {"label": "Đầu tư giá trị (Graham)", "value": "STRAT_VALUE"},
                                            {"label": "Đầu tư phục hồi (Turnaround)", "value": "STRAT_TURNAROUND"},
                                            {"label": "Đầu tư chất lượng (Quality)", "value": "STRAT_QUALITY"},
                                            {"label": "Tăng trưởng giá hợp lý (GARP)", "value": "STRAT_GARP"},
                                            {"label": "Cổ tức & Thu nhập (Neff)", "value": "STRAT_DIVIDEND"},
                                            {"label": "Điểm sức khỏe Piotroski", "value": "STRAT_PIOTROSKI"},
                                            {"label": "Siêu cổ phiếu CANSLIM", "value": "STRAT_CANSLIM"},
                                            {"label": "Tăng trưởng bền vững (Fisher)", "value": "STRAT_GROWTH"},
                                            {"label": "Công Thức Kỳ Diệu (Greenblatt)", "value": "STRAT_MAGIC"},
                                        ],
                                        placeholder="Chọn chiến lược đầu tư...",
                                        className="ssi-dropdown-custom",
                                        style={"minWidth": "220px", "flex": "1"},
                                    ),
                                    dbc.Button(
                                        html.I(className="fas fa-info-circle"),
                                        id="btn-strategy-info", color="primary", outline=True,
                                        size="sm",
                                        style={"borderLeft": "none", "padding": "0 10px"},
                                    ),
                                ],
                                style={"flexWrap": "nowrap"},
                            ),
                            wrapper_id="pw-strategies",
                            section="strategies",
                            label="Chiến lược VIP",
                        ),
                    ],
                    style={"display": "flex", "alignItems": "center", "gap": "8px", "flex": "1",
                           "maxWidth": "420px"},
                ),

                # Right: Industry + Sub-Industry + Saved filters + Export
                html.Div(
                    [
                        # Badge result count (ẩn — redundant với result-count ở bảng)
                        html.Span(id="result-count-number", style={"display": "none"}),

                        # Sàn giao dịch
                        html.I(className="fas fa-building-columns",
                               style={"marginRight": "6px", "color": "#a78bfa", "fontSize": "11px"}),
                        html.Span("Sàn",
                                  style={"fontSize": "11px", "color": "#6e7681", "fontWeight": "600",
                                         "marginRight": "8px", "whiteSpace": "nowrap"}),
                        dcc.Dropdown(
                            id="filter-exchange",
                            options=[
                                {"label": "Tất cả sàn", "value": "all"},
                                {"label": "HOSE",       "value": "HOSE"},  # Đổi "HM" thành "HOSE"
                                {"label": "HNX",        "value": "HNX"},   # Đổi "HN" thành "HNX"
                                {"label": "UPCOM",      "value": "UPCOM"}, # Đổi "HNO" thành "UPCOM"
                            ],
                            value=["all"], multi=True,
                            placeholder="Chọn sàn...",
                            className="ssi-dropdown-custom",
                            style={"minWidth": "150px"},
                        ),

                        html.I(className="fas fa-industry",
                               style={"marginRight": "6px", "color": "#3fb950", "fontSize": "11px"}),
                        html.Span("Ngành", id="label-industry",
                                  style={"fontSize": "11px", "color": "#6e7681", "fontWeight": "600",
                                         "marginRight": "8px", "whiteSpace": "nowrap"}),

                        # Sector (ngành lớn)
                        dcc.Dropdown(
                            id="filter-all-industry",
                            options=[{"label": "Tất cả ngành", "value": "all"}] + sector_options,
                            value=["all"], multi=True,
                            placeholder="Chọn ngành...",
                            className="ssi-dropdown-custom",
                            style={"minWidth": "160px"},
                        ),

                        # Sub-Industry (ngành con)
                        dcc.Dropdown(
                            id="filter-sub-industry",
                            options=[{"label": "Tất cả ngành con", "value": "all"}],
                            value=["all"], multi=True,
                            placeholder="Ngành con...",
                            className="ssi-dropdown-custom",
                            style={"minWidth": "160px", "maxWidth": "260px"},
                        ),

                        dcc.Dropdown(
                            id="saved-filters-dropdown",
                            options=[{"label": "Bộ lọc mặc định", "value": "default"}],
                            value="default",
                            placeholder="Bộ lọc đã lưu...",
                            clearable=False,
                            className="ssi-dropdown-custom",
                            style={"minWidth": "160px"},
                        ),

                        # Nút VI (ẩn - chưa có chức năng)
                        dbc.Button(
                            [html.Span("VI", style={"fontSize": "11px", "fontWeight": "700"})],
                            id="btn-lang-toggle",
                            n_clicks=0,
                            style={"display": "none"},
                        ),
                    ],
                    style={"display": "flex", "alignItems": "center", "gap": "8px", "flexWrap": "nowrap"},
                ),
            ],
            style={
                "display": "flex",
                "alignItems": "center",
                "justifyContent": "space-between",
                "padding": "10px 20px",
                "backgroundColor": "#161b22",
                "borderBottom": "2px solid #21262d",
                "flexWrap": "wrap",
                "gap": "10px",
            },
        ),

        # ── COLLAPSIBLE FILTER BODY — WIZARD 3 CỘT + IDX Chart phải ──────
        dbc.Collapse(
            id="filter-offcanvas",
            is_open=False,
            children=html.Div(
                [
                    # ── Wizard 3 cột (trái) ──
                    html.Div(_filter_wizard, style={
                        "flex": "1",
                        "minWidth": "0",
                        "display": "flex",
                        "flexDirection": "column",
                        "alignSelf": "stretch",
                    }),

                    # ── IDX Index Chart + Stats (phải) ──
                    html.Div([
                        # 1. Title bar (Sẽ tự động chiếm khoảng 30-40px tùy nội dung)
                        html.Div([
                            html.Span("IDX Composite  ·  ^VNINDEX", style={
                                "fontSize": "11px", "fontWeight": "700",
                                "color": "#c9d1d9", "flex": "1",
                            }),
                            html.Span(id="idx-chart-change", style={
                                "fontSize": "11px", "fontWeight": "700",
                                "color": "#10b981",
                            }),
                        ], style={
                            "display": "flex", "alignItems": "center",
                            "padding": "6px 10px",
                            "borderBottom": "1px solid #21262d",
                            "backgroundColor": "#161b22",
                        }),

                        # 2. Body: Sẽ dùng flex: 1 để TỰ ĐỘNG lấp đầy phần chiều cao còn lại
                        html.Div([
                            # Stats panel
                            html.Div(
                                id="idx-stats-panel",
                                style={
                                    "width": "160px",
                                    "height": "100%",
                                    "flexShrink": "0",
                                    "borderRight": "1px solid #21262d",
                                    "backgroundColor": "#0a1628",
                                    "overflow": "hidden",
                                }
                            ),
                            # Chart Container
                            html.Div([
                                dcc.Graph(
                                    id="idx-mini-chart",
                                    config={"displayModeBar": False},
                                    # 🔴 Đặt height 100% để nó ăn theo container chứa nó
                                    style={"height": "100%", "width": "100%"}, 
                                    figure={
                                        "data": [],
                                        "layout": {
                                            "autosize": True, # 🔴 Bật autosize để chart tự scale
                                            "paper_bgcolor": "#0d1117",
                                            "plot_bgcolor": "#0d1117",
                                            "margin": {"l": 0, "r": 0, "t": 0, "b": 0},
                                            # (Nhớ XÓA biến "height": 222 ở trong layout này đi nếu bạn từng thêm vào)
                                        }
                                    }
                                )
                            ], style={"flex": "1", "minWidth": "0", "height": "100%"}) # Container bọc ngoài chart cũng cao 100%

                        ], style={
                            "display": "flex", 
                            "flex": "1",               # 🔴 Rất quan trọng: Bắt body tự động dài ra cho hết vùng 262px
                            "alignItems": "stretch",   # 🔴 Rất quan trọng: Ép cả bảng Stats và Chart phải cao ngang nhau
                            "overflow": "hidden"
                        }),
                    ], style={
                        "width": "555px",
                        "height": "266px",        # ← thêm dòng này, khớp với wizard
                        "height": "262px",             # 🟢 BẠN CHỈ CẦN QUẢN LÝ TỔNG CHIỀU CAO Ở ĐÂY LÀ ĐỦ
                        "flexShrink": "0",
                        "border": "1px solid #21262d",
                        "borderRadius": "8px",
                        "overflow": "hidden",
                        "backgroundColor": "#0d1117",
                        "marginLeft": "12px",
                        "display": "flex",
                        "flexDirection": "column",     # 🔴 Bắt buộc để flex: 1 của Body hoạt động
                    }),
                ],
                style={
                    "display": "flex",
                    "flexDirection": "row",
                    "alignItems": "stretch",
                    "padding": "12px 20px",
                    "backgroundColor": "#0c1220",
                    "borderBottom": "2px solid #21262d",
                    "boxShadow": "0 8px 24px rgba(0,0,0,0.4)",
                },
            ),
        ),

        # ── HIDDEN STORES & GHOST BUTTONS (giữ nguyên 100%) ───────────────
        # Grade Stores
        # Stores kept for backward compat with screener_callbacks.py
        dcc.Store(id='filter-value-score', data=[]),
        dcc.Store(id='filter-growth-score', data=[]),
        dcc.Store(id='filter-momentum-score', data=[]),
        dcc.Store(id='filter-vgm-score', data=[]),

        # ── Range Stores — data lấy từ min/max thực tế trong parquet ──────────
        # Tổng quan
        dcc.Store(id='filter-price', data=_get_r(_DR, 'filter-price', [0, 100000])),
        dcc.Store(id='filter-volume', data=_get_r(_DR, 'filter-volume', [0, 50000000])),
        dcc.Store(id='filter-market-cap', data=_get_r(_DR, 'filter-market-cap', [0, 500000000000000])),
        dcc.Store(id='filter-eps', data=_get_r(_DR, 'filter-eps', [-500, 5000])),
        dcc.Store(id='filter-perf-1w', data=_get_r(_DR, 'filter-perf-1w', [-30, 30])),
        dcc.Store(id='filter-perf-1m', data=_get_r(_DR, 'filter-perf-1m', [-50, 100])),

        # Định giá
        dcc.Store(id='filter-pe', data=_get_r(_DR, 'filter-pe', [0, 100])),
        dcc.Store(id='filter-pb', data=_get_r(_DR, 'filter-pb', [0, 20])),
        dcc.Store(id='filter-ps', data=_get_r(_DR, 'filter-ps', [0, 20])),
        dcc.Store(id='filter-ev-ebitda', data=_get_r(_DR, 'filter-ev-ebitda', [0, 50])),
        dcc.Store(id='filter-div-yield', data=_get_r(_DR, 'filter-div-yield', [0, 20])),

        # Sinh lời
        dcc.Store(id='filter-roe', data=_get_r(_DR, 'filter-roe', [-50, 100])),
        dcc.Store(id='filter-roa', data=_get_r(_DR, 'filter-roa', [-30, 50])),
        dcc.Store(id='filter-gross-margin', data=_get_r(_DR, 'filter-gross-margin', [-50, 100])),
        dcc.Store(id='filter-net-margin', data=_get_r(_DR, 'filter-net-margin', [-50, 50])),
        dcc.Store(id='filter-ebit-margin', data=_get_r(_DR, 'filter-ebit-margin', [-50, 50])),

        # Tăng trưởng
        dcc.Store(id='filter-rev-growth-yoy', data=_get_r(_DR, 'filter-rev-growth-yoy', [-50, 200])),
        dcc.Store(id='filter-rev-cagr-5y', data=_get_r(_DR, 'filter-rev-cagr-5y', [-20, 100])),
        dcc.Store(id='filter-eps-growth-yoy', data=_get_r(_DR, 'filter-eps-growth-yoy', [-100, 300])),
        dcc.Store(id='filter-eps-cagr-5y', data=_get_r(_DR, 'filter-eps-cagr-5y', [-20, 100])),

        # Sức khỏe
        dcc.Store(id='filter-de', data=_get_r(_DR, 'filter-de', [0, 10])),
        dcc.Store(id='filter-current-ratio', data=_get_r(_DR, 'filter-current-ratio', [0, 10])),
        dcc.Store(id='filter-net-cash-cap', data=_get_r(_DR, 'filter-net-cash-cap', [-100, 100])),
        dcc.Store(id='filter-net-cash-assets', data=_get_r(_DR, 'filter-net-cash-assets', [-100, 100])),

        # Kỹ thuật – Giá vs SMA
        dcc.Store(id='filter-price-vs-sma5', data=_get_r(_DR, 'filter-price-vs-sma5', [-30, 50])),
        dcc.Store(id='filter-price-vs-sma10', data=_get_r(_DR, 'filter-price-vs-sma10', [-30, 50])),
        dcc.Store(id='filter-price-vs-sma20', data=_get_r(_DR, 'filter-price-vs-sma20', [-30, 50])),
        dcc.Store(id='filter-price-vs-sma50', data=_get_r(_DR, 'filter-price-vs-sma50', [-50, 100])),
        dcc.Store(id='filter-price-vs-sma100', data=_get_r(_DR, 'filter-price-vs-sma100', [-50, 100])),
        dcc.Store(id='filter-price-vs-sma200', data=_get_r(_DR, 'filter-price-vs-sma200', [-50, 100])),

        # Kỹ thuật – Đỉnh/Đáy
        dcc.Store(id='filter-pct-from-high-1y', data=_get_r(_DR, 'filter-pct-from-high-1y', [-80, 10])),
        dcc.Store(id='filter-pct-from-low-1y', data=_get_r(_DR, 'filter-pct-from-low-1y', [-10, 200])),
        dcc.Store(id='filter-pct-from-high-all', data=_get_r(_DR, 'filter-pct-from-high-all', [-90, 10])),
        dcc.Store(id='filter-pct-from-low-all', data=_get_r(_DR, 'filter-pct-from-low-all', [-10, 500])),
        dcc.Store(id='filter-break-high-52w', data=None),  # None = không lọc, 1 = Có, 0 = Không
        dcc.Store(id='filter-break-low-52w', data=None),

        # Kỹ thuật – Oscillators
        dcc.Store(id='filter-rsi14', data=_get_r(_DR, 'filter-rsi14', [0, 100])),
        dcc.Store(id='filter-macd-hist', data=_get_r(_DR, 'filter-macd-hist', [-1000, 1000])),
        dcc.Store(id='filter-bb-width', data=_get_r(_DR, 'filter-bb-width', [0, 50])),
        dcc.Store(id='filter-consec-up', data=_get_r(_DR, 'filter-consec-up', [0, 20])),
        dcc.Store(id='filter-consec-down', data=_get_r(_DR, 'filter-consec-down', [0, 20])),

        # Kỹ thuật – Momentum/RS
        dcc.Store(id='filter-beta', data=_get_r(_DR, 'filter-beta', [-2, 4])),
        dcc.Store(id='filter-alpha', data=_get_r(_DR, 'filter-alpha', [-50, 100])),
        dcc.Store(id='filter-rs-3d', data=_get_r(_DR, 'filter-rs-3d', [-20, 20])),
        dcc.Store(id='filter-rs-1m', data=_get_r(_DR, 'filter-rs-1m', [-30, 50])),
        dcc.Store(id='filter-rs-3m', data=_get_r(_DR, 'filter-rs-3m', [-50, 100])),
        dcc.Store(id='filter-rs-1y', data=_get_r(_DR, 'filter-rs-1y', [-80, 200])),
        dcc.Store(id='filter-rs-avg', data=_get_r(_DR, 'filter-rs-avg', [-50, 100])),

        # Kỹ thuật – Volume
        dcc.Store(id='filter-vol-vs-sma5', data=_get_r(_DR, 'filter-vol-vs-sma5', [0, 10])),
        dcc.Store(id='filter-vol-vs-sma10', data=_get_r(_DR, 'filter-vol-vs-sma10', [0, 10])),
        dcc.Store(id='filter-vol-vs-sma20', data=_get_r(_DR, 'filter-vol-vs-sma20', [0, 10])),
        dcc.Store(id='filter-vol-vs-sma50', data=_get_r(_DR, 'filter-vol-vs-sma50', [0, 10])),
        dcc.Store(id='filter-avg-vol-5d', data=_get_r(_DR, 'filter-avg-vol-5d', [0, 100000000])),
        dcc.Store(id='filter-avg-vol-10d', data=_get_r(_DR, 'filter-avg-vol-10d', [0, 100000000])),
        dcc.Store(id='filter-avg-vol-50d', data=_get_r(_DR, 'filter-avg-vol-50d', [0, 100000000])),

        # GTGD
        dcc.Store(id='filter-gtgd-1w', data=_get_r(_DR, 'filter-gtgd-1w', [0, 100000000000])),
        dcc.Store(id='filter-gtgd-10d', data=_get_r(_DR, 'filter-gtgd-10d', [0, 200000000000])),
        dcc.Store(id='filter-gtgd-1m', data=_get_r(_DR, 'filter-gtgd-1m', [0, 500000000000])),

        # Active filters master store
        dcc.Store(id='active-filters-store', data={}),
        dcc.Store(id='filter-unsaved-flag', data=None),
        dcc.Store(id='filter-year-store', data='all'),  # ← lọc theo năm
        dcc.Store(id='chart-refresh-store', data=0),  # trigger làm mới biểu đồ

        # ── SAVED FILTERS STORE ──
        # Lưu các bộ lọc đã lưu:
        dcc.Store(id='saved-filters-store', data={}, storage_type='local'),

        # ── TOAST THÔNG BÁO LƯU ──
        dbc.Toast(
            id="save-toast",
            header="Bộ lọc",
            is_open=False,
            dismissable=True,
            duration=3000,
            icon="success",
            style={
                "position": "fixed",
                "bottom": "24px",
                "right": "24px",
                "zIndex": "9999",
                "minWidth": "260px",
                "backgroundColor": "#161b22",
                "color": "#c9d1d9",
                "border": "1px solid #3fb950",
                "borderLeft": "4px solid #3fb950",
            },
        ),

        # Updater stores (Pattern Matching compat)
        dcc.Store(id={"type": "filter-store-updater", "filter": "filter-value-score"}, data=[]),
        dcc.Store(id={"type": "filter-store-updater", "filter": "filter-growth-score"}, data=[]),
        dcc.Store(id={"type": "filter-store-updater", "filter": "filter-momentum-score"}, data=[]),
        dcc.Store(id={"type": "filter-store-updater", "filter": "filter-vgm-score"}, data=[]),

        # Hidden helpers
        dcc.Store(id='filter-canslim', data=[0, 6]),
        dbc.Button("", id="btn-reset", style={"display": "none"}, n_clicks=0),
        html.Div(id="filter-stats", style={"display": "none"}),

        # Export CSV
        dcc.Download(id="download-csv"),

        # Export Excel
        dcc.Download(id="download-excel"),

        # Language store
        dcc.Store(id='lang-store', data='vi', storage_type='local'),

        # Watchlist store (lưu trong localStorage — giữ qua session)
        dcc.Store(id='watchlist-store', data=[], storage_type='local'),
        dcc.Store(id='watchlist-selected-store', data=None),  # ticker được click trong watchlist tab

        # Watchlist Modal
        dbc.Modal([
            dbc.ModalHeader(dbc.ModalTitle([
                html.I(className="fas fa-star", style={"color": "#ffca28", "marginRight": "8px"}),
                "Danh sách theo dõi"
            ]), close_button=True),
            dbc.ModalBody([
                html.Div(id="watchlist-content", style={"minHeight": "100px"}),
            ]),
            dbc.ModalFooter([
                dbc.Button("Xóa tất cả", id="btn-clear-watchlist", color="danger",
                           outline=True, size="sm", style={"fontSize": "11px"}),
                dbc.Button("Đóng", id="btn-close-watchlist", color="secondary", size="sm"),
            ], style={"display": "flex", "justifyContent": "space-between"}),
        ], id="watchlist-modal", size="lg", is_open=False, scrollable=True,
            style={"fontFamily": "'Inter', sans-serif"}),

        # NOTE: Collapse group buttons (collapse-scores-btn, etc.) are already
        # rendered inside _left_panel via collapse_group(). dbc.Collapse always
        # keeps children in the DOM so no ghost buttons are needed here.
        # The old sidebar.py had duplicates — we deliberately remove them.
    ]
)