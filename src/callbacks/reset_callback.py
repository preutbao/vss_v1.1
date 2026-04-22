# src/callbacks/reset_callback.py
"""
Callback xử lý nút RESET - Xóa toàn bộ filters và khôi phục về mặc định.
"""
from dash import Input, Output, html, no_update
from src.app_instance import app

# Giá trị mặc định map với store IDs (phải khớp với sidebar.py)
FILTER_DEFAULTS = {
    # Grade
    "filter-value-score":    [],
    "filter-growth-score":   [],
    "filter-momentum-score": [],
    "filter-vgm-score":      [],
    # Tổng quan
    "filter-price":          [0, 100000],
    "filter-volume":         [0, 50000000],
    "filter-market-cap":     [0, 500000000000000],
    "filter-eps":            [-500, 5000],
    "filter-perf-1w":        [-30, 30],
    "filter-perf-1m":        [-50, 100],
    # Định giá
    "filter-pe":             [0, 100],
    "filter-pb":             [0, 20],
    "filter-ps":             [0, 20],
    "filter-ev-ebitda":      [0, 50],
    "filter-div-yield":      [0, 20],
    # Sinh lời
    "filter-roe":            [-50, 100],
    "filter-roa":            [-30, 50],
    "filter-gross-margin":   [-50, 100],
    "filter-net-margin":     [-50, 50],
    "filter-ebit-margin":    [-50, 50],
    # Tăng trưởng
    "filter-rev-growth-yoy": [-50, 200],
    "filter-rev-cagr-5y":    [-20, 100],
    "filter-eps-growth-yoy": [-100, 300],
    "filter-eps-cagr-5y":    [-20, 100],
    # Sức khỏe
    "filter-de":             [0, 10],
    "filter-current-ratio":  [0, 10],
    "filter-net-cash-cap":   [-100, 100],
    "filter-net-cash-assets":[-100, 100],
    # Kỹ thuật: Giá vs SMA
    "filter-price-vs-sma5":   [-30, 50],
    "filter-price-vs-sma10":  [-30, 50],
    "filter-price-vs-sma20":  [-30, 50],
    "filter-price-vs-sma50":  [-50, 100],
    "filter-price-vs-sma100": [-50, 100],
    "filter-price-vs-sma200": [-50, 100],
    # Kỹ thuật: Đỉnh/Đáy
    "filter-pct-from-high-1y":  [-80, 10],
    "filter-pct-from-low-1y":   [-10, 200],
    "filter-pct-from-high-all": [-90, 10],
    "filter-pct-from-low-all":  [-10, 500],
    # Kỹ thuật: Oscillators
    "filter-rsi14":           [0, 100],
    "filter-macd-hist":       [-1000, 1000],
    "filter-bb-width":        [0, 50],
    "filter-consec-up":       [0, 20],
    "filter-consec-down":     [0, 20],
    # Kỹ thuật: Momentum/RS
    "filter-beta":            [-2, 4],
    "filter-alpha":           [-50, 100],
    "filter-rs-3d":           [-20, 20],
    "filter-rs-1m":           [-30, 50],
    "filter-rs-3m":           [-50, 100],
    "filter-rs-1y":           [-80, 200],
    "filter-rs-avg":          [-50, 100],
    # Kỹ thuật: Volume
    "filter-vol-vs-sma5":     [0, 10],
    "filter-vol-vs-sma10":    [0, 10],
    "filter-vol-vs-sma20":    [0, 10],
    "filter-vol-vs-sma50":    [0, 10],
    "filter-avg-vol-5d":      [0, 100000000],
    "filter-avg-vol-10d":     [0, 100000000],
    "filter-avg-vol-50d":     [0, 100000000],
    "filter-gtgd-1w":         [0, 100000000000],
    "filter-gtgd-10d":        [0, 200000000000],
    "filter-gtgd-1m":         [0, 500000000000],
}

_STORE_IDS = list(FILTER_DEFAULTS.keys())


@app.callback(
    [Output("selected-filters-container", "children", allow_duplicate=True),
     Output("active-filters-store",       "data",     allow_duplicate=True)]
    + [Output(sid, "data", allow_duplicate=True) for sid in _STORE_IDS],
    Input("btn-reset-ui", "n_clicks"),
    prevent_initial_call=True
)
def reset_all_filters(n_clicks):
    if not n_clicks:
        return [no_update] * (2 + len(_STORE_IDS))

    defaults = [FILTER_DEFAULTS[sid] for sid in _STORE_IDS]
    return [[], {}] + defaults


@app.callback(
    Output("filter-all-industry",  "value", allow_duplicate=True),
    Output("filter-sub-industry",  "value", allow_duplicate=True),
    Output("filter-exchange",      "value", allow_duplicate=True),
    Input("btn-reset-ui", "n_clicks"),
    prevent_initial_call=True
)
def reset_industry_dropdowns(n_clicks):
    """Bug #5 fix: reset cả 2 dropdown ngành và bộ lọc sàn về mặc định khi bấm Reset."""
    if not n_clicks:
        return no_update, no_update, no_update
    return ["all"], ["all"], ["all"]