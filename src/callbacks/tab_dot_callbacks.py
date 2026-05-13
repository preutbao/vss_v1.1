# src/callbacks/tab_dot_callbacks.py
"""
Hiển thị/ẩn chấm tròn xám trên 4 tab toolbar
khi người dùng thay đổi cài đặt so với mặc định.
"""
from dash import Input, Output, no_update
from src.app_instance import app

_DOT_SHOW = {
    "display": "inline-block",
    "width": "7px", "height": "7px",
    "borderRadius": "50%",
    "backgroundColor": "#8b949e",
    "position": "absolute",
    "top": "7px", "right": "7px",
}
_DOT_HIDE = {"display": "none"}


@app.callback(
    Output("tab-dot-search",   "style"),
    Output("tab-dot-strategy", "style"),
    Output("tab-dot-scope",    "style"),
    Output("tab-dot-personal", "style"),
    # ── Inputs cho từng tab ──────────────────────────────
    Input("search-ticker-input",     "value"),    # Tab Tìm mã
    Input("strategy-preset-dropdown","value"),    # Tab Chiến lược
    Input("active-filters-store",    "data"),     # Tab Chiến lược (bộ lọc)
    Input("filter-all-industry",     "value"),    # Tab Phạm vi
    Input("filter-sub-industry",     "value"),    # Tab Phạm vi
    Input("filter-exchange",         "value"),    # Tab Phạm vi
    Input("filter-index",            "value"),    # Tab Phạm vi
    Input("saved-filters-store",     "data"),     # Tab Cá nhân
    prevent_initial_call=False,
)
def update_tab_dots(
    ticker,
    strategy,
    active_filters,
    industry,
    sub_industry,
    exchange,
    index_filter,
    saved_filters,
):
    # ── Tab 1: Tìm mã ──────────────────────────────────
    search_dot = _DOT_SHOW if ticker else _DOT_HIDE

    # ── Tab 2: Chiến lược ──────────────────────────────
    # Hiện khi có strategy HOẶC có filter đang active
    # (bao gồm cả filter được set từ onboarding IPS)
    has_strategy = bool(strategy)
    has_active  = bool(active_filters)          # dict rỗng = falsy
    strategy_dot = _DOT_SHOW if (has_strategy or has_active) else _DOT_HIDE

    # ── Tab 3: Phạm vi ─────────────────────────────────
    def _changed(val, default):
        if not val:
            return False
        if isinstance(val, list):
            cleaned = [v for v in val if v != "all"]
            return bool(cleaned)              # có ít nhất 1 giá trị khác "all"
        return val != default

    scope_changed = any([
        _changed(industry,    None),
        _changed(sub_industry, None),
        _changed(exchange,    None),
        index_filter and index_filter != "all",
    ])
    scope_dot = _DOT_SHOW if scope_changed else _DOT_HIDE

    # ── Tab 4: Cá nhân ─────────────────────────────────
    # Hiện khi có TỪ 2 BỘ LỌC TRỞ LÊN (tức là đã lưu thêm ít nhất 1 cái ngoài bộ lọc mặc định)
    if not saved_filters:
        has_saved = False
    else:
        # Kiểm tra xem saved_filters (dù là list hay dict) có nhiều hơn 1 phần tử hay không
        has_saved = len(saved_filters) > 1 

    personal_dot = _DOT_SHOW if has_saved else _DOT_HIDE

    return search_dot, strategy_dot, scope_dot, personal_dot