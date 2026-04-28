# src/callbacks/mode_callbacks.py
from dash import html
from dash import Input, Output, State, no_update
from src.app_instance import app

@app.callback(
    Output("trading-mode-store", "data"),
    Output("mode-toggle-btn", "color"),
    Output("mode-toggle-btn", "children"),
    Input("mode-toggle-btn", "n_clicks"),
    State("trading-mode-store", "data"),
    prevent_initial_call=True,
)
def toggle_trading_mode(n, current_mode):
    if not n:
        return no_update, no_update, no_update
        
    # LOGIC XOAY VÒNG: Tích sản -> Lướt sóng -> Toàn TT -> Tích sản
    if current_mode == "investing":
        new_mode = "trading"
        color = "warning"
        label = [
            html.I(className="fas fa-bolt", style={"marginRight": "5px"}),
            html.Span("Lướt sóng", id="mode-toggle-label"),
        ]
    elif current_mode == "trading":
        new_mode = "all_market"
        color = "secondary" # Dùng màu xám mờ cho toàn thị trường
        label = [
            html.I(className="fas fa-globe", style={"marginRight": "5px"}),
            html.Span("Toàn TT", id="mode-toggle-label"),
        ]
    else: # Trường hợp current_mode == "all_market" hoặc lỗi
        new_mode = "investing"
        color = "success"
        label = [
            html.I(className="fas fa-seedling", style={"marginRight": "5px"}),
            html.Span("Tích sản", id="mode-toggle-label"),
        ]
        
    return new_mode, color, label

from dash import Input, Output

@app.callback(
    Output("mode-indicator-badge", "children"),
    Output("mode-indicator-badge", "style"),
    Input("trading-mode-store", "data"),
    prevent_initial_call=False,
)
def update_mode_badge(mode):
    if mode == "trading":
        return "⚡ Lướt sóng", {
            "fontSize": "10px", "fontWeight": "700",
            "padding": "2px 10px", "borderRadius": "10px",
            "backgroundColor": "rgba(245,158,11,0.15)",
            "color": "#f59e0b",
            "border": "1px solid rgba(245,158,11,0.35)",
            "marginLeft": "10px", "verticalAlign": "middle", "letterSpacing": "0.5px",
        }
    elif mode == "all_market":
        return "🌐 Thị trường", {
            "fontSize": "10px", "fontWeight": "700",
            "padding": "2px 10px", "borderRadius": "10px",
            "backgroundColor": "rgba(100,116,139,0.15)", # Màu xám chuyên nghiệp
            "color": "#64748b",
            "border": "1px solid rgba(100,116,139,0.35)",
            "marginLeft": "10px", "verticalAlign": "middle", "letterSpacing": "0.5px",
        }
        
    # Mặc định là Tích sản
    return "📊 Tích sản", {
        "fontSize": "10px", "fontWeight": "700",
        "padding": "2px 10px", "borderRadius": "10px",
        "backgroundColor": "rgba(16,185,129,0.15)",
        "color": "#10b981",
        "border": "1px solid rgba(16,185,129,0.35)",
        "marginLeft": "10px", "verticalAlign": "middle", "letterSpacing": "0.5px",
    }

from dash import Input, Output, callback, callback_context

@callback(
    Output("trading-mode-store", "data"),
    Output("mode-selector-radio", "value"), # Update luôn nút Radio trên Header cho đồng bộ
    Input("mode-selector-radio", "value"),
    Input("tour-selected-mode", "data"),    # Lắng nghe kết quả từ bài Test Tour Guide
    prevent_initial_call=False
)
def sync_mode_store(radio_mode, tour_mode):
    ctx = callback_context
    if not ctx.triggered:
        return "investing", "investing"
        
    trigger_id = ctx.triggered[0]["prop_id"]
    
    # Nếu tín hiệu đến từ việc user vừa làm xong bài test
    if "tour-selected-mode" in trigger_id and tour_mode:
        return tour_mode, tour_mode
        
    # Nếu tín hiệu đến từ việc user tự bấm nút radio trên header
    return radio_mode, radio_mode

# src/callbacks/mode_callbacks.py
from dash import Input, Output, callback, callback_context

@callback(
    Output("trading-mode-store", "data"),
    Output("mode-selector-radio", "value"), # Đồng bộ nút bấm trên Header
    Input("mode-selector-radio", "value"),
    Input("tour-selected-mode", "data"),    # Kết quả từ bài trắc nghiệm trốn Home
    prevent_initial_call=False
)
def sync_mode_from_tour(radio_val, tour_val):
    ctx = callback_context
    if not ctx.triggered:
        return "investing", "investing"
        
    trigger_id = ctx.triggered[0]["prop_id"]
    
    # Nếu user vừa hoàn thành bài test ở Tour Guide
    if "tour-selected-mode" in trigger_id and tour_val:
        return tour_val, tour_val
        
    # Nếu user tự bấm đổi mode trên Header
    return radio_val, radio_val