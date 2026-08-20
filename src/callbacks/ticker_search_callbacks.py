# src/callbacks/ticker_search_callbacks.py
"""
Callback nạp options cho Dropdown tìm kiếm mã / tên công ty.

- Khi app khởi động (n_intervals=0 từ dcc.Interval hoặc page load),
  gọi get_ticker_list() để lấy danh sách đầy đủ từ snapshot.
- Screener callback đọc giá trị `search-ticker-input` (value = ticker string)
  giống hệt như trước → KHÔNG cần sửa screener_callbacks.py.
"""
from dash import Input, Output, callback_context, no_update
from src.app_instance import app
from src.backend.data_loader import get_ticker_list
import logging

logger = logging.getLogger(__name__)

from dash import Input, Output, State, ctx
from dash.exceptions import PreventUpdate
from src.backend.data_loader import get_ticker_list # Import hàm sinh data của bạn

# 1. CALLBACK: NẠP DATA CHO DROPDOWN (GỘP LỊCH SỬ + TẤT CẢ)
@app.callback(
    Output("search-ticker-input", "options"),
    Input("recent-searches-store", "data") # Tự động chạy khi mở web hoặc khi lịch sử đổi
)
def populate_dropdown_with_history(recent_tickers):
    recent_tickers = recent_tickers or []
    full_list = get_ticker_list()
    
    if not full_list:
        return []
        
    lookup = {item['value']: item for item in full_list}
    options = []
    
    # --- PHẦN LỊCH SỬ (YOUTUBE STYLE) ---
    if recent_tickers:
        for ticker in recent_tickers:
            if ticker in lookup:
                hist_item = lookup[ticker].copy()
                hist_item['label'] = "🕒 " + hist_item['label'] # Thêm icon đồng hồ
                options.append(hist_item)
        
        # Thêm vạch phân cách giả (không bấm được)
        options.append({
            'label': '────────── Tất cả mã ──────────', 
            'value': 'divider', 
            'disabled': True
        })
        
    for item in full_list:
        # Ẩn bớt những mã đã xuất hiện ở phần lịch sử cho đỡ trùng lặp
        if item['value'] not in recent_tickers:
            options.append(item)
            
    return options

# 2. CALLBACK: CẬP NHẬT LỊCH SỬ MỖI KHI NGƯỜI DÙNG CHỌN MÃ
@app.callback(
    Output("recent-searches-store", "data"),
    Input("search-ticker-input", "value"),
    State("recent-searches-store", "data"),
    prevent_initial_call=True
)
def save_recent_search(selected_ticker, current_history):
    if not selected_ticker or selected_ticker == 'divider':
        raise PreventUpdate
        
    current_history = current_history or []
    
    # Nếu mã đã có trong lịch sử thì xóa đi để đưa lên đầu
    if selected_ticker in current_history:
        current_history.remove(selected_ticker)
        
    current_history.insert(0, selected_ticker)
    
    # Chỉ giữ tối đa 5 mã tìm kiếm gần nhất
    return current_history[:5]

# 3. CALLBACK: BẤM VÀO CHIP NỔI BẬT THÌ TỰ NHẢY VÀO Ô SEARCH
@app.callback(
    Output("search-ticker-input", "value", allow_duplicate=True),
    [Input("trend-chip-FPT", "n_clicks"),
     Input("trend-chip-VIC", "n_clicks"),
     Input("trend-chip-SSI", "n_clicks"),
     Input("trend-chip-VCB", "n_clicks")],
    prevent_initial_call=True
)
def click_trending_chip(n1, n2, n3, n4):
    if not ctx.triggered:
        raise PreventUpdate
    
    button_id = ctx.triggered_id
    ticker = button_id.split("-")[-1]  # Lấy đuôi FPT, VIC...
    return ticker

# ============================================================================
# 4. THANH TÌM KIẾM Ở HERO SECTION (home-hero-search-*)
# ----------------------------------------------------------------------------
# Gõ mã -> Bấm tìm kiếm -> Lấy data -> Mở thẳng Pop-up chi tiết doanh nghiệp.
# ============================================================================
from dash.exceptions import PreventUpdate

@app.callback(
    Output("detail-modal", "is_open", allow_duplicate=True),
    Output("modal-title", "children", allow_duplicate=True),
    Output("selected-stock-store", "data", allow_duplicate=True),
    Output("selected-ticker-store", "data", allow_duplicate=True),
    Input("home-hero-search-submit", "n_clicks"),
    Input("home-hero-search-input", "n_submit"),
    State("home-hero-search-input", "value"),
    prevent_initial_call=True,
)
def open_modal_from_hero_search(n_clicks, n_submit, value):
    if not value:
        raise PreventUpdate
        
    ticker = value.strip().upper()
    if not ticker:
        raise PreventUpdate
        
    try:
        from src.backend.data_loader import get_snapshot_df
        df = get_snapshot_df()
        
        if df is not None and not df.empty:
            stock_data = df[df["Ticker"] == ticker]
            
            if not stock_data.empty:
                # 1. Trích xuất thành Dictionary chuẩn (không bọc list)
                stock_dict = stock_data.iloc[0].to_dict()
                
                # 2. Tạo tiêu đề Pop-up
                company_name = stock_dict.get('Company Common Name', '')
                title_text = f"Cổ phiếu {ticker} – {company_name}"
                
                # 3. Trả về đúng 4 giá trị giống y hệt thao tác double-click
                return True, title_text, stock_dict, ticker
    except Exception:
        pass

    raise PreventUpdate