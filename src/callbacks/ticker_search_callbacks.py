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


@app.callback(
    Output("search-ticker-input", "options"),
    Input("screener-table", "id"),          # trigger 1 lần duy nhất khi DOM sẵn sàng
    prevent_initial_call=False,
)
def populate_ticker_dropdown(_table_id):
    """
    Nạp toàn bộ danh sách mã + tên công ty vào Dropdown tìm kiếm.
    Chạy 1 lần khi page load. get_ticker_list() dùng snapshot đã có trong RAM
    nên cực nhanh (<5ms sau lần khởi động đầu tiên).
    """
    try:
        options = get_ticker_list()
        logger.info(f"Ticker search dropdown: {len(options)} mã")
        return options
    except Exception as e:
        logger.error(f"Lỗi nạp ticker list: {e}")
        return []