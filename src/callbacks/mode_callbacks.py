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
        # Lấy giá trị đang lưu trong Local Storage, nếu không có thì mặc định Tích sản
        new_mode = current_mode if current_mode else "investing"
        
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