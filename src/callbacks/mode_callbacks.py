from dash import html, Input, Output, State, callback, callback_context, no_update
from src.app_instance import app

# ============================================================================
# CALLBACK 1: Xử lý logic nút bấm Toggle & Bài test Tour Guide
# ============================================================================
@app.callback(
    Output("trading-mode-store", "data"),
    Output("mode-toggle-btn",    "color"),
    Output("mode-toggle-btn",    "children"),
    Input("mode-toggle-btn",     "n_clicks"),
    Input("tour-selected-mode",  "data"),
    State("trading-mode-store",  "data"),
    prevent_initial_call=False, # <--- CHÌA KHÓA: Phải là False để nó đồng bộ UI lúc mới F5
)
def sync_trading_mode(btn_clicks, tour_val, current_mode):
    ctx = callback_context
    
    # 1. NẾU MỚI LOAD TRANG (Chưa ai bấm gì)
    if not ctx.triggered:
        # Lấy giá trị đang lưu trong Local Storage, nếu không có thì mặc định Toan thị trường
        new_mode = current_mode if current_mode else "all_market"
        
    # 2. NẾU CÓ NGƯỜI TƯƠNG TÁC
    else:
        trigger_id = ctx.triggered[0]["prop_id"].split(".")[0]

        if trigger_id == "tour-selected-mode" and tour_val:
            new_mode = tour_val

        elif trigger_id == "mode-toggle-btn":
            # Xoay vòng: investing → trading → all_market → investing
            cycle = {"investing": "trading", "trading": "all_market", "all_market": "investing"}
            new_mode = cycle.get(current_mode or "investing", "investing")
            
        else:
            new_mode = current_mode or "investing"

    # 3. BUILD LẠI GIAO DIỆN NÚT CHO KHỚP VỚI MODE
    _btn_config = {
        "investing":  ("success",   [html.I(className="fas fa-seedling", style={"marginRight": "5px"}), "Tích sản"]),
        "trading":    ("warning",   [html.I(className="fas fa-bolt",     style={"marginRight": "5px"}), "Lướt sóng"]),
        "all_market": ("secondary", [html.I(className="fas fa-globe",    style={"marginRight": "5px"}), "Toàn TT"]),
    }
    btn_color, btn_label = _btn_config.get(new_mode, _btn_config["investing"])

    # Trả về: [Lưu vào Store], [Đổi màu nút], [Đổi chữ nút]
    return new_mode, btn_color, btn_label


# ============================================================================
# CALLBACK 2: Cập nhật badge hiển thị mode hiện tại
# ============================================================================
@app.callback(
    Output("mode-indicator-badge", "children"),
    Output("mode-indicator-badge", "style"),
    Input("trading-mode-store", "data"),
    prevent_initial_call=False,
)
def update_mode_badge(mode):
    _cfg = {
        "trading": (
            "⚡ Lướt sóng",
            {
                "fontSize": "10px", "fontWeight": "700",
                "padding": "2px 10px", "borderRadius": "10px",
                "backgroundColor": "rgba(245,158,11,0.15)",
                "color": "#f59e0b",
                "border": "1px solid rgba(245,158,11,0.35)",
                "marginLeft": "10px", "verticalAlign": "middle",
                "letterSpacing": "0.5px",
            },
        ),
        "all_market": (
            "🌐 Toàn thị trường",
            {
                "fontSize": "10px", "fontWeight": "700",
                "padding": "2px 10px", "borderRadius": "10px",
                "backgroundColor": "rgba(100,116,139,0.15)",
                "color": "#828A95",
                "border": "1px solid rgba(100,116,139,0.35)",
                "marginLeft": "10px", "verticalAlign": "middle",
                "letterSpacing": "0.5px",
            },
        ),
    }
    
    label, style = _cfg.get(
        mode,
        (
            "📊 Tích sản",
            {
                "fontSize": "10px", "fontWeight": "700",
                "padding": "2px 10px", "borderRadius": "10px",
                "backgroundColor": "rgba(16,185,129,0.15)",
                "color": "#10b981",
                "border": "1px solid rgba(16,185,129,0.35)",
                "marginLeft": "10px", "verticalAlign": "middle",
                "letterSpacing": "0.5px",
            },
        ),
    )
    return label, style

from dash import html

_MODE_TOOLTIP_CONTENT = {
    "investing": html.Div([
        html.Div([
            html.I(className="fas fa-seedling", style={"color": "#10b981", "marginRight": "7px"}),
            html.Span("Tích sản — Dài hạn", style={
                "fontWeight": "700", "color": "#10b981", "fontSize": "12px",
            }),
        ], style={"marginBottom": "7px"}),
        html.Div("Lọc doanh nghiệp có nền tảng tài chính lành mạnh, phù hợp nắm giữ trung-dài hạn:", style={
            "color": "#8b949e", "fontSize": "11px", "lineHeight": "1.5", "marginBottom": "7px",
        }),
        html.Ul([
            html.Li("P/E dương, doanh nghiệp có lợi nhuận thực"),
            html.Li("Vốn hóa ≥ 200 tỷ (loại shell company)"),
            html.Li("ROE ≥ -20% (không lỗ nặng)"),
            html.Li("Giá ≥ 3,000 VND (tránh cổ dưới mệnh giá)"),
            html.Li("KLGD TB ≥ 30,000 CP/ngày"),
        ], style={"color": "#c9d1d9", "fontSize": "11px", "lineHeight": "1.7",
                  "paddingLeft": "16px", "margin": "0"}),
    ], style={"padding": "12px 14px"}),

    "trading": html.Div([
        html.Div([
            html.I(className="fas fa-bolt", style={"color": "#f59e0b", "marginRight": "7px"}),
            html.Span("Lướt sóng — T+", style={
                "fontWeight": "700", "color": "#f59e0b", "fontSize": "12px",
            }),
        ], style={"marginBottom": "7px"}),
        html.Div("Lọc cổ phiếu có thanh khoản và động lượng đủ để vào/ra nhanh:", style={
            "color": "#8b949e", "fontSize": "11px", "lineHeight": "1.5", "marginBottom": "7px",
        }),
        html.Ul([
            html.Li("KLGD TB ≥ 200,000 CP/ngày (đủ thanh khoản)"),
            html.Li("Giá ≥ 5,000 VND (loại penny stock)"),
            html.Li("Vốn hóa ≥ 500 tỷ (tránh thao túng)"),
            html.Li("RSI ≥ 25 (không bắt dao rơi)"),
            html.Li("Không cách đỉnh 1Y quá -40%"),
        ], style={"color": "#c9d1d9", "fontSize": "11px", "lineHeight": "1.7",
                  "paddingLeft": "16px", "margin": "0"}),
    ], style={"padding": "12px 14px"}),

    "all_market": html.Div([
        html.Div([
            html.I(className="fas fa-globe", style={"color": "#a5a7a9", "marginRight": "7px"}),
            html.Span("Toàn thị trường — Chuyên gia", style={
                "fontWeight": "700", "color": "#a5a7a9", "fontSize": "12px",
            }),
        ], style={"marginBottom": "7px"}),
        html.Div("Hiển thị toàn bộ ~1,500 mã niêm yết, không áp bộ lọc cứng:", style={
            "color": "#8b949e", "fontSize": "11px", "lineHeight": "1.5", "marginBottom": "7px",
        }),
        html.Ul([
            html.Li("Bao gồm cả penny stock, shell company"),
            html.Li("Phù hợp Broker, Data Analyst, quét thị trường"),
            html.Li("Kết hợp với bộ lọc thủ công từ Wizard"),
            html.Li("Không có hard filter tự động"),
        ], style={"color": "#c9d1d9", "fontSize": "11px", "lineHeight": "1.7",
                  "paddingLeft": "16px", "margin": "0"}),
    ], style={"padding": "12px 14px"}),
}


@app.callback(
    Output("mode-toggle-tooltip", "children"),
    Input("trading-mode-store", "data"),
    prevent_initial_call=False,
)
def update_mode_tooltip(mode):
    return _MODE_TOOLTIP_CONTENT.get(mode or "investing",
                                     _MODE_TOOLTIP_CONTENT["investing"])


# ============================================================================
# CLIENTSIDE CALLBACK: TOOLBAR TAB SWITCHING
# ============================================================================
app.clientside_callback(
    """
    function(n_search, n_strategy, n_scope, n_personal) {
        const SEARCH_ACTIVE = [
            'toolbar-tab  toolbar-tab-active', 'toolbar-tab',
            'toolbar-tab', 'toolbar-tab',
            'toolbar-panel',
            'toolbar-panel toolbar-panel-hidden',
            'toolbar-panel toolbar-panel-hidden',
            'toolbar-panel toolbar-panel-hidden'
        ];

        // ← THÊM MỚI: default khi load trang là Chiến lược
        const STRATEGY_ACTIVE = [
            'toolbar-tab', 'toolbar-tab  toolbar-tab-active',
            'toolbar-tab', 'toolbar-tab',
            'toolbar-panel toolbar-panel-hidden',
            'toolbar-panel',
            'toolbar-panel toolbar-panel-hidden',
            'toolbar-panel toolbar-panel-hidden'
        ];

        const ctx = dash_clientside.callback_context;

        // ← ĐỔI: SEARCH_ACTIVE → STRATEGY_ACTIVE
        if (!ctx || !ctx.triggered || !ctx.triggered.length) {
            return STRATEGY_ACTIVE;
        }

        const triggeredId = ctx.triggered[0].prop_id.split('.')[0];

        const TAB_IDS   = ['toolbar-tab-search', 'toolbar-tab-strategy',
                           'toolbar-tab-scope',  'toolbar-tab-personal'];
        const PANEL_IDS = ['toolbar-panel-search', 'toolbar-panel-strategy',
                           'toolbar-panel-scope',  'toolbar-panel-personal'];

        const activeIdx = TAB_IDS.indexOf(triggeredId);
        if (activeIdx === -1) return STRATEGY_ACTIVE;  // ← ĐỔI từ SEARCH_ACTIVE

        const tabClasses = TAB_IDS.map((_, i) =>
            i === activeIdx
                ? 'toolbar-tab  toolbar-tab-active'
                : 'toolbar-tab'
        );
        const panelClasses = PANEL_IDS.map((_, i) =>
            i === activeIdx
                ? 'toolbar-panel'
                : 'toolbar-panel toolbar-panel-hidden'
        );

        return [...tabClasses, ...panelClasses];
    }
    """,
    [
        Output("toolbar-tab-search",     "className"),
        Output("toolbar-tab-strategy",   "className"),
        Output("toolbar-tab-scope",      "className"),
        Output("toolbar-tab-personal",   "className"),
        Output("toolbar-panel-search",   "className"),
        Output("toolbar-panel-strategy", "className"),
        Output("toolbar-panel-scope",    "className"),
        Output("toolbar-panel-personal", "className"),
    ],
    [
        Input("toolbar-tab-search",   "n_clicks"),
        Input("toolbar-tab-strategy", "n_clicks"),
        Input("toolbar-tab-scope",    "n_clicks"),
        Input("toolbar-tab-personal", "n_clicks"),
    ],
    prevent_initial_call=False,   # ← đổi thành False để set active ngay khi load
)