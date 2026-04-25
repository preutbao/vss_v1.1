# src/callbacks/filter_interaction_callbacks.py
"""
Callbacks xử lý tương tác với bộ lọc.
FIX 1: Sync TẤT CẢ range sliders vào dcc.Store tương ứng (không chỉ 5 store).
FIX 2: Min/max của RangeSlider lấy từ dữ liệu thực tế (snapshot_cache.parquet).
"""
from dash import Input, Output, State, html, ALL, MATCH, callback_context, no_update, dcc
from src.app_instance import app
import json
from dash import callback_context
from src.constants import SECTOR_TRANSLATION

# Import hàm lấy range thực tế từ data
from src.backend.data_loader import get_filter_ranges, load_financial_data

# ── Cache histogram (tránh tính lại mỗi lần thêm filter card) ──
_histogram_cache: dict = {}  # { filter_id: base64_svg_string }


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def _fmt_display(v):
    """Format số thông minh cho display."""
    try:
        abs_v = abs(v)
        if abs_v >= 1_000_000_000_000:
            return f"{v / 1_000_000_000_000:.1f}T"
        elif abs_v >= 1_000_000_000:
            return f"{v / 1_000_000_000:.1f}B"
        elif abs_v >= 1_000_000:
            return f"{v / 1_000_000:.1f}M"
        elif abs_v >= 10_000:
            return f"{v:,.0f}"
        elif abs_v >= 1:
            return f"{v:,.1f}"
        else:
            return f"{v:.2f}"
    except Exception:
        return str(v)


def _count_matching(filter_id, current_range, filter_year=None):
    """Đếm số mã thỏa mãn range của chỉ tiêu này từ snapshot."""
    try:
        from src.backend.data_loader import get_latest_snapshot
        import pandas as pd
        # Map filter_id → tên cột trong snapshot
        _COL_MAP = {
            "filter-price": "Price Close", "filter-volume": "Volume",
            "filter-market-cap": "Market Cap", "filter-eps": "EPS",
            "filter-perf-1w": "Perf_1W", "filter-perf-1m": "Perf_1M",
            "filter-pe": "P/E", "filter-pb": "P/B", "filter-ps": "P/S",
            "filter-ev-ebitda": "EV/EBITDA", "filter-div-yield": "Dividend Yield (%)",
            "filter-roe": "ROE (%)", "filter-roa": "ROA (%)",
            "filter-gross-margin": "Gross Margin (%)", "filter-net-margin": "Net Margin (%)",
            "filter-ebit-margin": "EBIT Margin (%)",
            "filter-rev-growth-yoy": "Revenue Growth YoY (%)",
            "filter-rev-cagr-5y": "Revenue CAGR 5Y (%)",
            "filter-eps-growth-yoy": "EPS Growth YoY (%)",
            "filter-eps-cagr-5y": "EPS CAGR 5Y (%)",
            "filter-de": "D/E", "filter-current-ratio": "Current Ratio",
            "filter-net-cash-cap": "Net Cash / Market Cap (%)",
            "filter-net-cash-assets": "Net Cash / Assets (%)",
            "filter-price-vs-sma5": "Price_vs_SMA5", "filter-price-vs-sma10": "Price_vs_SMA10",
            "filter-price-vs-sma20": "Price_vs_SMA20", "filter-price-vs-sma50": "Price_vs_SMA50",
            "filter-price-vs-sma100": "Price_vs_SMA100", "filter-price-vs-sma200": "Price_vs_SMA200",
            "filter-pct-from-high-1y": "Pct_From_High_1Y", "filter-pct-from-low-1y": "Pct_From_Low_1Y",
            "filter-pct-from-high-all": "Pct_From_High_All", "filter-pct-from-low-all": "Pct_From_Low_All",
            "filter-rsi14": "RSI_14", "filter-macd-hist": "MACD_Histogram",
            "filter-bb-width": "BB_Width", "filter-consec-up": "Consec_Up",
            "filter-consec-down": "Consec_Down", "filter-beta": "Beta",
            "filter-alpha": "Alpha", "filter-rs-3d": "RS_3D",
            "filter-rs-1m": "RS_1M", "filter-rs-3m": "RS_3M",
            "filter-rs-1y": "RS_1Y", "filter-rs-avg": "RS_Avg",
            "filter-vol-vs-sma5": "Vol_vs_SMA5", "filter-vol-vs-sma10": "Vol_vs_SMA10",
            "filter-vol-vs-sma20": "Vol_vs_SMA20", "filter-vol-vs-sma50": "Vol_vs_SMA50",
            "filter-avg-vol-5d": "Avg_Vol_5D", "filter-avg-vol-10d": "Avg_Vol_10D",
            "filter-avg-vol-50d": "Avg_Vol_50D",
        }
        col = _COL_MAP.get(filter_id)
        if not col or not current_range or len(current_range) != 2:
            return None
        records = get_latest_snapshot()
        if not records:
            return None
        df = pd.DataFrame(records)

        # Lọc theo năm nếu có chọn
        if filter_year and filter_year != "all":
            try:
                yr = int(filter_year)
                df_fin_yr = load_financial_data('yearly')
                if df_fin_yr is not None and not df_fin_yr.empty and 'Date' in df_fin_yr.columns:
                    df_fin_yr['_yr'] = pd.to_datetime(df_fin_yr['Date'], errors='coerce').dt.year
                    tickers_in_year = set(df_fin_yr[df_fin_yr['_yr'] == yr]['Ticker'].dropna().unique())
                    df = df[df['Ticker'].isin(tickers_in_year)]
            except Exception:
                pass  # nếu lỗi thì bỏ qua, đếm toàn bộ

        if col not in df.columns:
            return None
        s = pd.to_numeric(df[col], errors='coerce').dropna()
        count = int(((s >= current_range[0]) & (s <= current_range[1])).sum())
        return count
    except Exception:  # ← except bọc ngoài cùng
        return None


def _get_histogram_svg_b64(filter_id, min_val, max_val, bins=24):
    """
    Wrapper có cache — mỗi filter_id chỉ tính 1 lần/session.
    """
    global _histogram_cache
    if filter_id in _histogram_cache:
        return _histogram_cache[filter_id]
    result = _compute_histogram(filter_id, min_val, max_val, bins)
    _histogram_cache[filter_id] = result
    return result


def _compute_histogram(filter_id, min_val, max_val, bins=24):
    """
    Tạo SVG histogram thật, encode base64 để nhúng vào img tag.
    Bars có chiều cao thật theo phân phối → trông giống TCInvest.
    """
    try:
        from src.backend.data_loader import get_latest_snapshot, FILTER_COL_MAP
        import numpy as np
        import pandas as pd
        import base64

        col = FILTER_COL_MAP.get(filter_id)
        if not col:
            return None

        records = get_latest_snapshot()
        if not records:
            return None

        df = pd.DataFrame(records)
        if col not in df.columns:
            return None

        s = pd.to_numeric(df[col], errors='coerce').dropna()
        if len(s) < 5:
            return None

        # Các chỉ tiêu phân phối lệch mạnh → dùng log scale
        LOG_SCALE_FILTERS = {
            # Giá & khối lượng
            'filter-volume', 'filter-market-cap', 'filter-price',
            'filter-avg-vol-5d', 'filter-avg-vol-10d', 'filter-avg-vol-50d',
            'filter-gtgd-1w', 'filter-gtgd-10d', 'filter-gtgd-1m',
            # Định giá
            'filter-pe', 'filter-pb', 'filter-ps',
            # EPS & tăng trưởng (outlier rất lớn)
            'filter-eps',
            'filter-rev-growth-yoy', 'filter-eps-growth-yoy',
            'filter-rev-cagr-5y', 'filter-eps-cagr-5y',
            # Kỹ thuật lệch mạnh
            'filter-pct-from-low-1y', 'filter-pct-from-low-all',
            'filter-bb-width',
            'filter-rs-1y', 'filter-rs-3m', 'filter-rs-avg',
        }
        use_log = filter_id in LOG_SCALE_FILTERS

        if use_log:
            s_pos = s[s > 0]
            if len(s_pos) < 5:
                use_log = False  # fallback về linear
            else:
                s = s_pos

        if use_log:
            s_transformed = np.log10(s)
            p5 = float(s_transformed.quantile(0.05))
            p95 = float(s_transformed.quantile(0.95))
            if p5 >= p95:
                p5, p95 = float(s_transformed.min()), float(s_transformed.max())
            s_clipped = s_transformed.clip(p5, p95)
        else:
            p5 = float(s.quantile(0.05))
            p95 = float(s.quantile(0.95))
            if p5 >= p95:
                p5, p95 = float(s.min()), float(s.max())
            s_clipped = s.clip(p5, p95)

        counts, _ = np.histogram(s_clipped, bins=bins, range=(float(s_clipped.min()), float(s_clipped.max())))
        if counts.max() == 0:
            return None

        norm = counts / counts.max()

        W, H = 240, 36
        bar_w = W / bins
        gap = 1

        bars = ""
        for i, h in enumerate(norm):
            bar_h = max(2, float(h) * H)
            x = i * bar_w + gap / 2
            y = H - bar_h
            w = bar_w - gap
            # Màu sáng hơn ở bar cao
            opacity = 0.3 + float(h) * 0.6
            bars += (f'<rect x="{x:.1f}" y="{y:.1f}" '
                     f'width="{w:.1f}" height="{bar_h:.1f}" '
                     f'fill="#00c8ff" opacity="{opacity:.2f}" rx="1"/>')

        svg = (f'<svg xmlns="http://www.w3.org/2000/svg" '
               f'viewBox="0 0 {W} {H}" '
               f'preserveAspectRatio="none">'
               f'{bars}</svg>')

        b64 = base64.b64encode(svg.encode()).decode()
        return f"data:image/svg+xml;base64,{b64}"

    except Exception:
        return None


def create_range_filter_ui(filter_id, label, min_val=0, max_val=100, current_range=None):
    """
    Filter card dạng HÀNG NGANG — histogram trên, slider dưới, không chồng lên nhau.
    [✓] Label  |  [min]  [histogram / slider]  [max]  |  N mã  ×
    """
    ranges = get_filter_ranges()
    if filter_id in ranges:
        min_val, max_val = ranges[filter_id]

    if current_range is None:
        current_range = [min_val, max_val]
    else:
        current_range = [
            max(min_val, min(float(current_range[0]), max_val)),
            max(min_val, min(float(current_range[1]), max_val)),
        ]

    hist_src = _get_histogram_svg_b64(filter_id, min_val, max_val)

    return html.Div([

        # ── Checkbox icon ──
        html.I(className="fas fa-check-square",
               style={"color": "#3fb950", "fontSize": "13px",
                      "marginRight": "10px", "flexShrink": "0"}),

        # ── Label ──
        html.Span(label, style={
            "color": "#c9d1d9", "fontSize": "12px", "fontWeight": "600",
            "width": "170px", "minWidth": "170px", "flexShrink": "0",
            "overflow": "hidden", "textOverflow": "ellipsis", "whiteSpace": "nowrap",
        }),

        # ── Min input ──
        dcc.Input(
            id={"type": "range-min-input", "filter": filter_id},
            type="number", value=current_range[0], debounce=True, step="any",
            style={
                "width": "70px", "padding": "3px 5px", "fontSize": "11px",
                "backgroundColor": "#0d1117", "color": "#58a6ff",
                "border": "1px solid #30363d", "borderRadius": "4px",
                "textAlign": "center", "outline": "none", "flexShrink": "0",
            }
        ),

        # ── Histogram + Slider (xếp dọc, không chồng) ──
        html.Div([
            # Histogram SVG phía trên
            *([html.Img(
                src=hist_src,
                style={
                    "width": "100%", "height": "28px",
                    "display": "block", "borderRadius": "3px",
                    "pointerEvents": "none",
                    "opacity": "0.85",
                }
            )] if hist_src else []),
            # Slider phía dưới — KHÔNG bị che
            dcc.RangeSlider(
                id={"type": "range-slider", "filter": filter_id},
                min=min_val, max=max_val, value=current_range,
                marks=None,
                tooltip={"always_visible": False},
                className="custom-range-slider",
                updatemode="mouseup",   # ← chỉ fire khi thả chuột, không fire liên tục
            ),
        ], style={
            "flex": "1",
            "display": "flex",
            "flexDirection": "column",
            "justifyContent": "center",
            "margin": "0 8px",
            "minWidth": "0",
        }),

        # ── Max input ──
        dcc.Input(
            id={"type": "range-max-input", "filter": filter_id},
            type="number", value=current_range[1], debounce=True, step="any",
            style={
                "width": "70px", "padding": "3px 5px", "fontSize": "11px",
                "backgroundColor": "#0d1117", "color": "#58a6ff",
                "border": "1px solid #30363d", "borderRadius": "4px",
                "textAlign": "center", "outline": "none", "flexShrink": "0",
            }
        ),

        # ── Badge số mã ──
        html.Span(
            "–",
            id={"type": "filter-count-badge", "filter": filter_id},
            style={
                "fontSize": "11px", "fontWeight": "700",
                "color": "#00d4ff",
                "backgroundColor": "rgba(0,212,255,0.08)",
                "border": "1px solid rgba(0,212,255,0.2)",
                "borderRadius": "8px", "padding": "2px 8px",
                "whiteSpace": "nowrap", "marginLeft": "8px",
                "minWidth": "55px", "textAlign": "center", "flexShrink": "0",
            }
        ),

        # ── Nút xóa ──
        html.I(
            className="fas fa-times",
            id={"type": "remove-filter", "index": filter_id},
            style={"color": "#484f58", "cursor": "pointer", "fontSize": "13px",
                   "marginLeft": "8px", "flexShrink": "0"},
            n_clicks=0
        ),

    ], id={"type": "selected-filter", "index": filter_id}, style={
        "display": "flex",
        "alignItems": "center",
        "padding": "5px 10px",
        "backgroundColor": "#161b22",
        "borderRadius": "5px",
        "border": "1px solid #21262d",
        "borderLeft": "3px solid #3fb950",
        "animation": "fadeIn 0.2s ease-in-out",
        "minWidth": "0",
    })


# ── Boolean filter UI (Có / Không / Tất cả) ──────────────────────────────────

def create_bool_filter_ui(filter_id, label, true_label="Có", false_label="Không"):
    """
    Compact boolean card: 2 nút Có / Không + nút xóa.
    Store value: 1 = Có, 0 = Không, None = bỏ qua.
    """
    btn_style_base = {
        "flex": "1", "padding": "4px 0", "fontSize": "11px",
        "fontWeight": "600", "border": "1px solid #30363d",
        "borderRadius": "4px", "cursor": "pointer",
        "transition": "all 0.15s",
    }
    return html.Div([
        # Header
        html.Div([
            html.Span(label, style={
                "color": "#c9d1d9", "fontSize": "11px", "fontWeight": "600",
                "flex": "1", "overflow": "hidden", "textOverflow": "ellipsis",
                "whiteSpace": "nowrap", "marginRight": "4px",
            }),
            html.I(
                className="fas fa-times",
                id={"type": "remove-filter", "index": filter_id},
                style={"color": "#6e7681", "cursor": "pointer", "fontSize": "11px",
                       "marginLeft": "6px", "flexShrink": "0"},
                n_clicks=0
            ),
        ], style={"display": "flex", "alignItems": "center", "marginBottom": "8px"}),

        # Toggle buttons
        html.Div([
            html.Button(
                [html.I(className="fas fa-check-circle", style={"marginRight": "4px"}), true_label],
                id={"type": "bool-btn-true", "filter": filter_id},
                n_clicks=0,
                style={**btn_style_base,
                       "backgroundColor": "#1a3a1a", "color": "#3fb950",
                       "borderColor": "#3fb950"},
            ),
            html.Button(
                [html.I(className="fas fa-times-circle", style={"marginRight": "4px"}), false_label],
                id={"type": "bool-btn-false", "filter": filter_id},
                n_clicks=0,
                style={**btn_style_base,
                       "backgroundColor": "#0d1117", "color": "#6e7681",
                       "borderColor": "#30363d"},
            ),
        ], style={"display": "flex", "gap": "6px"}),

        # Hidden store to track current value
        dcc.Store(id={"type": "bool-filter-value", "filter": filter_id}, data=1),

    ], id={"type": "selected-filter", "index": filter_id}, style={
        "padding": "8px 10px",
        "backgroundColor": "#161b22",
        "borderRadius": "6px",
        "border": "1px solid #3fb950",
        "animation": "fadeIn 0.25s ease-in-out",
        "minWidth": "0",
    })


def create_range_filter_ui_readonly(filter_id, label, min_val=0, max_val=100, current_range=None):
    """
    Filter card dạng "Tham khảo" — CÙNG layout hàng ngang với card thường,
    nhưng có tag "Tham khảo" màu vàng và borderLeft amber thay vì xanh.
    """
    ranges = get_filter_ranges()
    if filter_id in ranges:
        min_val, max_val = ranges[filter_id]

    if current_range is None:
        current_range = [min_val, max_val]
    else:
        current_range = [
            max(min_val, min(float(current_range[0]), max_val)),
            max(min_val, min(float(current_range[1]), max_val)),
        ]

    hist_src = _get_histogram_svg_b64(filter_id, min_val, max_val)

    return html.Div([

        # ── Icon bookmark (phân biệt với card thường dùng check-square) ──
        html.I(className="fas fa-bookmark",
               style={"color": "#f59e0b", "fontSize": "13px",
                      "marginRight": "10px", "flexShrink": "0"}),

        # ── Label + Tag "Tham khảo" xếp dọc ──
        html.Div([
            html.Span(label, style={
                "color": "#c9d1d9", "fontSize": "12px", "fontWeight": "600",
                "overflow": "hidden", "textOverflow": "ellipsis",
                "whiteSpace": "nowrap", "display": "block",
            }),
            html.Span("Tham khảo", style={
                "fontSize": "9px", "fontWeight": "700", "color": "#f59e0b",
                "backgroundColor": "#1c1a10", "border": "1px solid #f59e0b50",
                "borderRadius": "6px", "padding": "0px 5px",
                "whiteSpace": "nowrap", "display": "inline-block",
                "marginTop": "2px",
            }),
        ], style={"width": "170px", "minWidth": "170px", "flexShrink": "0",
                  "display": "flex", "flexDirection": "column", "justifyContent": "center"}),

        # ── Min input ──
        dcc.Input(
            id={"type": "range-min-input", "filter": filter_id},
            type="number", value=current_range[0], debounce=True, step="any",
            style={
                "width": "70px", "padding": "3px 5px", "fontSize": "11px",
                "backgroundColor": "#0d1117", "color": "#f59e0b",
                "border": "1px solid #f59e0b40", "borderRadius": "4px",
                "textAlign": "center", "outline": "none", "flexShrink": "0",
            }
        ),

        # ── Histogram + Slider ──
        html.Div([
            *([html.Img(
                src=hist_src,
                style={
                    "width": "100%", "height": "28px",
                    "display": "block", "borderRadius": "3px",
                    "pointerEvents": "none", "opacity": "0.7",
                }
            )] if hist_src else []),
            dcc.RangeSlider(
                id={"type": "range-slider", "filter": filter_id},
                min=min_val, max=max_val, value=current_range,
                marks=None,
                tooltip={"always_visible": False},
                className="custom-range-slider amber-slider",
                updatemode="mouseup",   # ← chỉ fire khi thả chuột, không fire liên tục
            ),
        ], style={
            "flex": "1", "display": "flex", "flexDirection": "column",
            "justifyContent": "center", "margin": "0 8px", "minWidth": "0",
        }),

        # ── Max input ──
        dcc.Input(
            id={"type": "range-max-input", "filter": filter_id},
            type="number", value=current_range[1], debounce=True, step="any",
            style={
                "width": "70px", "padding": "3px 5px", "fontSize": "11px",
                "backgroundColor": "#0d1117", "color": "#f59e0b",
                "border": "1px solid #f59e0b40", "borderRadius": "4px",
                "textAlign": "center", "outline": "none", "flexShrink": "0",
            }
        ),

        # ── Nút xóa ──
        html.I(
            className="fas fa-times",
            id={"type": "remove-filter", "index": filter_id},
            style={"color": "#6e7681", "cursor": "pointer", "fontSize": "12px",
                   "marginLeft": "10px", "flexShrink": "0"},
            n_clicks=0
        ),

    ], id={"type": "selected-filter", "index": filter_id}, style={
        "display": "flex",
        "alignItems": "center",
        "padding": "5px 10px",
        "backgroundColor": "#161b22",
        "borderRadius": "5px",
        "border": "1px solid #21262d",
        "borderLeft": "3px solid #f59e0b",  # amber = tham khảo
        "animation": "fadeIn 0.2s ease-in-out",
        "minWidth": "0",
    })


CRITERIA_CONFIG = {
    # ── TỔNG QUAN ──
    "criteria-price": {"label": "Giá hiện tại (IDR)", "filter_id": "filter-price", "type": "range", "min": 0,
                       "max": 50000, "default_value": [0, 50000]},
    "criteria-volume": {"label": "Khối lượng giao dịch", "filter_id": "filter-volume", "type": "range", "min": 0,
                        "max": 10000000, "default_value": [0, 10000000]},
    "criteria-market-cap": {"label": "Vốn hóa thị trường", "filter_id": "filter-market-cap", "type": "range", "min": 0,
                            "max": 999000000000000, "default_value": [0, 999000000000000]},
    "criteria-eps": {"label": "EPS (Thu nhập / cổ phiếu)", "filter_id": "filter-eps", "type": "range", "min": -1000,
                     "max": 10000, "default_value": [-1000, 10000]},
    "criteria-perf-1w": {"label": "% Thay đổi giá 1 tuần", "filter_id": "filter-perf-1w", "type": "range", "min": -30,
                         "max": 30, "default_value": [-30, 30]},
    "criteria-perf-1m": {"label": "% Thay đổi giá 1 tháng", "filter_id": "filter-perf-1m", "type": "range", "min": -50,
                         "max": 100, "default_value": [-50, 100]},
    "criteria-rs-3d": {"label": "RS 3 ngày", "filter_id": "filter-rs-3d", "type": "range", "min": -20, "max": 20,
                       "default_value": [-20, 20]},
    # ── ĐỊNH GIÁ ──
    "criteria-pe": {"label": "P/E Ratio", "filter_id": "filter-pe", "type": "range", "min": 0, "max": 100,
                    "default_value": [0, 100]},
    "criteria-pb": {"label": "P/B Ratio", "filter_id": "filter-pb", "type": "range", "min": 0, "max": 20,
                    "default_value": [0, 20]},
    "criteria-ps": {"label": "P/S Ratio", "filter_id": "filter-ps", "type": "range", "min": 0, "max": 20,
                    "default_value": [0, 20]},
    # "criteria-ev-ebitda":    {"label": "EV/EBITDA",                     "filter_id": "filter-ev-ebitda",       "type": "range", "min": 0,     "max": 50,              "default_value": [0, 50]},
    "criteria-ev": {"label": "Giá trị doanh nghiệp (EV)", "filter_id": "filter-market-cap", "type": "range", "min": 0,
                    "max": 999000000000000, "default_value": [0, 999000000000000]},
    "criteria-div-yield": {"label": "Tỷ suất Cổ tức (%)", "filter_id": "filter-div-yield", "type": "range", "min": 0,
                           "max": 25, "default_value": [0, 25]},
    # ── SINH LỜI ──
    "criteria-roe": {"label": "ROE (%)", "filter_id": "filter-roe", "type": "range", "min": -50, "max": 100,
                     "default_value": [-50, 100]},
    "criteria-roa": {"label": "ROA (%)", "filter_id": "filter-roa", "type": "range", "min": -30, "max": 50,
                     "default_value": [-30, 50]},
    "criteria-gross-margin": {"label": "Biên LN gộp (%)", "filter_id": "filter-gross-margin", "type": "range",
                              "min": -50, "max": 100, "default_value": [-50, 100]},
    "criteria-net-margin": {"label": "Biên LN ròng (%)", "filter_id": "filter-net-margin", "type": "range", "min": -50,
                            "max": 50, "default_value": [-50, 50]},
    "criteria-ebit-margin": {"label": "Biên EBIT (%)", "filter_id": "filter-ebit-margin", "type": "range", "min": -50,
                             "max": 50, "default_value": [-50, 50]},
    # ── TĂNG TRƯỞNG ──
    "criteria-rev-growth-yoy": {"label": "% Tăng trưởng DT 1 năm", "filter_id": "filter-rev-growth-yoy",
                                "type": "range", "min": -50, "max": 300, "default_value": [-50, 300]},
    "criteria-rev-cagr-5y": {"label": "% Tăng trưởng DT 5 năm", "filter_id": "filter-rev-cagr-5y", "type": "range",
                             "min": -20, "max": 100, "default_value": [-20, 100]},
    "criteria-eps-growth-yoy": {"label": "% Tăng trưởng EPS 1 năm", "filter_id": "filter-eps-growth-yoy",
                                "type": "range", "min": -100, "max": 500, "default_value": [-100, 500]},
    "criteria-eps-cagr-5y": {"label": "% Tăng trưởng EPS 5 năm", "filter_id": "filter-eps-cagr-5y", "type": "range",
                             "min": -20, "max": 100, "default_value": [-20, 100]},
    # ── SỨC KHỎE TÀI CHÍNH ──
    "criteria-de": {"label": "D/E (Nợ vay / VCSH)", "filter_id": "filter-de", "type": "range", "min": 0, "max": 15,
                    "default_value": [0, 15]},
    "criteria-current-ratio": {"label": "Tỷ lệ thanh toán hiện hành", "filter_id": "filter-current-ratio",
                               "type": "range", "min": 0, "max": 10, "default_value": [0, 10]},
    "criteria-net-cash-cap": {"label": "Tiền mặt ròng / Vốn hóa (%)", "filter_id": "filter-net-cash-cap",
                              "type": "range", "min": -100, "max": 100, "default_value": [-100, 100]},
    "criteria-net-cash-assets": {"label": "Tiền mặt ròng / Tổng TS (%)", "filter_id": "filter-net-cash-assets",
                                 "type": "range", "min": -100, "max": 100, "default_value": [-100, 100]},
    # ── KỸ THUẬT: GIÁ VS SMA ──
    "criteria-price-vs-sma5": {"label": "Giá vs SMA(5) (%)", "filter_id": "filter-price-vs-sma5", "type": "range",
                               "min": -30, "max": 50, "default_value": [-30, 50]},
    "criteria-price-vs-sma10": {"label": "Giá vs SMA(10) (%)", "filter_id": "filter-price-vs-sma10", "type": "range",
                                "min": -30, "max": 50, "default_value": [-30, 50]},
    "criteria-price-vs-sma20": {"label": "Giá vs SMA(20) (%)", "filter_id": "filter-price-vs-sma20", "type": "range",
                                "min": -30, "max": 50, "default_value": [-30, 50]},
    "criteria-price-vs-sma50": {"label": "Giá vs SMA(50) (%)", "filter_id": "filter-price-vs-sma50", "type": "range",
                                "min": -50, "max": 100, "default_value": [-50, 100]},
    "criteria-price-vs-sma100": {"label": "Giá vs SMA(100) (%)", "filter_id": "filter-price-vs-sma100", "type": "range",
                                 "min": -50, "max": 100, "default_value": [-50, 100]},
    "criteria-price-vs-sma200": {"label": "Giá vs SMA(200) (%)", "filter_id": "filter-price-vs-sma200", "type": "range",
                                 "min": -50, "max": 100, "default_value": [-50, 100]},
    # ── KỸ THUẬT: ĐỈNH & ĐÁY ──
    "criteria-break-high-52w": {"label": "Vượt đỉnh 52 tuần", "filter_id": "filter-break-high-52w", "type": "boolean",
                                "true_label": "Có vượt đỉnh", "false_label": "Không vượt"},
    "criteria-break-low-52w": {"label": "Phá đáy 52 tuần", "filter_id": "filter-break-low-52w", "type": "boolean",
                               "true_label": "Có phá đáy", "false_label": "Không phá"},
    "criteria-pct-from-high-1y": {"label": "% Cách đỉnh 1 năm", "filter_id": "filter-pct-from-high-1y", "type": "range",
                                  "min": -80, "max": 10, "default_value": [-80, 10]},
    "criteria-pct-from-low-1y": {"label": "% Cách đáy 1 năm", "filter_id": "filter-pct-from-low-1y", "type": "range",
                                 "min": -10, "max": 300, "default_value": [-10, 300]},
    "criteria-pct-from-high-all": {"label": "% Cách đỉnh lịch sử", "filter_id": "filter-pct-from-high-all",
                                   "type": "range", "min": -90, "max": 10, "default_value": [-90, 10]},
    "criteria-pct-from-low-all": {"label": "% Cách đáy lịch sử", "filter_id": "filter-pct-from-low-all",
                                  "type": "range", "min": -10, "max": 500, "default_value": [-10, 500]},
    # ── KỸ THUẬT: CHỈ BÁO ──
    "criteria-rsi14": {"label": "RSI(14)", "filter_id": "filter-rsi14", "type": "range", "min": 0, "max": 100,
                       "default_value": [0, 100]},
    "criteria-rsi-state": {"label": "Trạng thái RSI(14)", "filter_id": "filter-rsi14", "type": "range", "min": 0,
                           "max": 100, "default_value": [0, 100]},
    "criteria-macd-hist": {"label": "MACD Histogram", "filter_id": "filter-macd-hist", "type": "range", "min": -1000,
                           "max": 1000, "default_value": [-1000, 1000]},
    "criteria-bb-width": {"label": "Mở rộng Bollinger (%)", "filter_id": "filter-bb-width", "type": "range", "min": 0,
                          "max": 50, "default_value": [0, 50]},
    "criteria-consec-up": {"label": "Phiên tăng liên tiếp", "filter_id": "filter-consec-up", "type": "range", "min": 0,
                           "max": 20, "default_value": [0, 20]},
    "criteria-consec-down": {"label": "Phiên giảm liên tiếp", "filter_id": "filter-consec-down", "type": "range",
                             "min": 0, "max": 20, "default_value": [0, 20]},
    # ── KỸ THUẬT: MOMENTUM & SỨC MẠNH TƯƠNG ĐỐI ──
    "criteria-beta": {"label": "Beta", "filter_id": "filter-beta", "type": "range", "min": -2, "max": 4,
                      "default_value": [-2, 4]},
    "criteria-alpha": {"label": "Alpha (% năm)", "filter_id": "filter-alpha", "type": "range", "min": -50, "max": 100,
                       "default_value": [-50, 100]},
    "criteria-rs-1m": {"label": "RS 1 tháng", "filter_id": "filter-rs-1m", "type": "range", "min": -30, "max": 50,
                       "default_value": [-30, 50]},
    "criteria-rs-3m": {"label": "RS 3 tháng", "filter_id": "filter-rs-3m", "type": "range", "min": -50, "max": 100,
                       "default_value": [-50, 100]},
    "criteria-rs-1y": {"label": "RS 1 năm", "filter_id": "filter-rs-1y", "type": "range", "min": -80, "max": 200,
                       "default_value": [-80, 200]},
    "criteria-rs-avg": {"label": "RS Trung bình", "filter_id": "filter-rs-avg", "type": "range", "min": -50, "max": 100,
                        "default_value": [-50, 100]},
    # ── KỸ THUẬT: KHỐI LƯỢNG GIAO DỊCH ──
    "criteria-vol-vs-sma5": {"label": "KL so với SMA(5)", "filter_id": "filter-vol-vs-sma5", "type": "range", "min": 0,
                             "max": 10, "default_value": [0, 10]},
    "criteria-vol-vs-sma10": {"label": "KL so với SMA(10)", "filter_id": "filter-vol-vs-sma10", "type": "range",
                              "min": 0, "max": 10, "default_value": [0, 10]},
    "criteria-vol-vs-sma20": {"label": "KL so với SMA(20)", "filter_id": "filter-vol-vs-sma20", "type": "range",
                              "min": 0, "max": 10, "default_value": [0, 10]},
    "criteria-vol-vs-sma50": {"label": "KL so với SMA(50)", "filter_id": "filter-vol-vs-sma50", "type": "range",
                              "min": 0, "max": 10, "default_value": [0, 10]},
    "criteria-avg-vol-5d": {"label": "KL trung bình 5 phiên", "filter_id": "filter-avg-vol-5d", "type": "range",
                            "min": 0, "max": 100000000, "default_value": [0, 100000000]},
    "criteria-avg-vol-10d": {"label": "KL trung bình 10 phiên", "filter_id": "filter-avg-vol-10d", "type": "range",
                             "min": 0, "max": 100000000, "default_value": [0, 100000000]},
    "criteria-avg-vol-50d": {"label": "KL trung bình 50 phiên", "filter_id": "filter-avg-vol-50d", "type": "range",
                             "min": 0, "max": 100000000, "default_value": [0, 100000000]},
    "criteria-gtgd-1w": {"label": "GTGD 1 tuần", "filter_id": "filter-gtgd-1w", "type": "range", "min": 0,
                         "max": 100000000000, "default_value": [0, 100000000000]},
    "criteria-gtgd-10d": {"label": "GTGD 10 ngày", "filter_id": "filter-gtgd-10d", "type": "range", "min": 0,
                          "max": 200000000000, "default_value": [0, 200000000000]},
    "criteria-gtgd-1m": {"label": "GTGD 1 tháng", "filter_id": "filter-gtgd-1m", "type": "range", "min": 0,
                         "max": 500000000000, "default_value": [0, 500000000000]},
}

# ============================================================================
# STRATEGY → FILTER CARDS MAPPING
# Khi chọn trường phái, tự động add các thẻ chỉ tiêu tương ứng.
# format: { strategy_id: [(filter_id, label, [lo, hi]), ...] }
# ============================================================================

_STRATEGY_FILTERS = {
    "STRAT_VALUE": [
        ("filter-pe", "P/E Ratio", [0, 16]),
        ("filter-pb", "P/B Ratio", [0, 2.5]),
        ("filter-current-ratio", "Thanh toán hiện hành", [1.0, 10]),
        ("filter-de", "D/E (Nợ / VCSH)", [0, 2]),
        ("filter-roe", "ROE (%)", [5, 100]),
        ("filter-eps-growth-yoy", "% Tăng trưởng EPS 1 năm", [0, 300]),
        ("filter-net-margin", "Biên LN ròng (%)", [0, 50]),
        ("filter-eps", "EPS", [0, 5000]),
    ],
    "STRAT_TURNAROUND": [
        ("filter-pe", "P/E Ratio", [0, 15]),
        ("filter-net-margin", "Biên LN ròng (%)", [0, 50]),
        ("filter-pct-from-high-1y", "% Cách đỉnh 1 năm", [-80, -20]),
        ("filter-ebit-margin", "Biên EBIT (%)", [3, 100]),
        ("filter-current-ratio", "Thanh toán hiện hành", [1.0, 10]),
        ("filter-rev-growth-yoy", "% Tăng trưởng DT 1 năm", [0, 200]),
        ("filter-price-vs-sma200", "Giá so với SMA200 (%)", [-50, 50]),
        ("filter-rs-1m", "RS 1 tháng", [-30, 50]),
    ],
    "STRAT_QUALITY": [
        ("filter-roe", "ROE (%)", [15, 100]),
        ("filter-roa", "ROA (%)", [8, 50]),
        ("filter-gross-margin", "Biên LN gộp (%)", [30, 100]),
        ("filter-net-margin", "Biên LN ròng (%)", [10, 50]),
        ("filter-de", "D/E (Nợ / VCSH)", [0, 1]),
        ("filter-rev-cagr-5y", "CAGR Doanh thu 5 năm (%)", [5, 100]),
        ("filter-eps-cagr-5y", "CAGR EPS 5 năm (%)", [5, 100]),
        ("filter-current-ratio", "Thanh toán hiện hành", [1.0, 10]),
    ],
    "STRAT_GARP": [
        ("filter-pe", "P/E Ratio", [0, 25]),
        ("filter-eps-growth-yoy", "% Tăng trưởng EPS 1 năm", [10, 40]),
        ("filter-roe", "ROE (%)", [10, 100]),
        ("filter-de", "D/E (Nợ / VCSH)", [0, 1.5]),
        ("filter-rev-growth-yoy", "% Tăng trưởng DT 1 năm", [5, 200]),
        ("filter-net-margin", "Biên LN ròng (%)", [5, 50]),
        ("filter-market-cap", "Vốn hoá (IDR)", [500000000000, 500000000000000]),
    ],
    "STRAT_DIVIDEND": [
        ("filter-div-yield", "Tỷ suất Cổ tức (%)", [3, 25]),
        ("filter-pe", "P/E Ratio", [0, 20]),
        ("filter-roe", "ROE (%)", [5, 100]),
        ("filter-current-ratio", "Thanh toán hiện hành", [1.0, 10]),
        ("filter-de", "D/E (Nợ / VCSH)", [0, 2]),
        ("filter-eps-growth-yoy", "% Tăng trưởng EPS 1 năm", [0, 300]),
        ("filter-market-cap", "Vốn hoá (IDR)", [1000000000000, 500000000000000]),
    ],
    "STRAT_PIOTROSKI": [
        ("filter-roe", "ROE (%)", [5, 100]),
        ("filter-roa", "ROA (%)", [3, 50]),
        ("filter-current-ratio", "Thanh toán hiện hành", [1.0, 10]),
        ("filter-gross-margin", "Biên LN gộp (%)", [0, 100]),
        ("filter-de", "D/E (Nợ / VCSH)", [0, 5]),
        ("filter-rev-growth-yoy", "% Tăng trưởng DT 1 năm", [0, 200]),
        ("filter-eps-growth-yoy", "% Tăng trưởng EPS 1 năm", [0, 300]),
        ("filter-net-margin", "Biên LN ròng (%)", [0, 50]),
    ],
    "STRAT_CANSLIM": [
        ("filter-eps-growth-yoy", "% Tăng trưởng EPS 1 năm", [20, 500]),
        ("filter-rev-growth-yoy", "% Tăng trưởng DT 1 năm", [20, 300]),
        ("filter-roe", "ROE (%)", [12, 100]),
        ("filter-rsi14", "RSI(14)", [50, 100]),
        ("filter-vol-vs-sma20", "KL so với SMA(20)", [1.1, 10]),
        ("filter-price-vs-sma50", "Giá so với SMA50 (%)", [0, 100]),
        ("filter-rs-avg", "RS Trung bình", [0, 100]),
        ("filter-current-ratio", "Thanh toán hiện hành", [0.8, 10]),
        ("filter-de", "D/E (Nợ / VCSH)", [0, 2]),
    ],
    "STRAT_GROWTH": [
        ("filter-rev-growth-yoy", "% Tăng trưởng DT 1 năm", [15, 300]),
        ("filter-rev-cagr-5y", "CAGR Doanh thu 5 năm (%)", [7, 100]),
        ("filter-roe", "ROE (%)", [15, 100]),
        ("filter-roa", "ROA (%)", [8, 50]),
        ("filter-eps-growth-yoy", "% Tăng trưởng EPS 1 năm", [15, 500]),
        ("filter-eps-cagr-5y", "CAGR EPS 5 năm (%)", [5, 100]),
        ("filter-net-margin", "Biên LN ròng (%)", [10, 50]),
        ("filter-gross-margin", "Biên LN gộp (%)", [20, 100]),
        ("filter-de", "D/E (Nợ / VCSH)", [0, 1.5]),
    ],
    "STRAT_MAGIC": [
        ("filter-roe", "ROE (%)", [25, 100]),
        ("filter-roa", "ROA (%)", [15, 50]),
        ("filter-ebit-margin", "Biên EBIT (%)", [10, 100]),
        ("filter-ev-ebitda", "EV/EBITDA", [0, 15]),
        ("filter-pe", "P/E Ratio", [0, 20]),
        ("filter-market-cap", "Vốn hoá (IDR)", [700000000000, 500000000000000]),
    ],

    # ── NCN K16: Khẩu Vị Phòng Thủ ──────────────────────────────────────────
    # 3 tầng lọc: Red Flag → Chất lượng tài chính → Lợi thế cạnh tranh
    # Range hiển thị dựa trên ngưỡng thực tế trong NCN_THRESHOLDS
    "STRAT_NCN": [
        # Tầng 1 – Chất lượng lợi nhuận (proxy: Net Margin thay CFO/NI chưa có store)
        ("filter-net-margin",      "Biên LN ròng (%)",              [5,   50]),
        ("filter-gross-margin",    "Biên LN gộp (%) – Pricing Power", [15, 100]),
        # Tầng 2 – Chất lượng dòng tiền & cấu trúc vốn
        ("filter-roe",             "ROE (%)",                        [15, 100]),
        ("filter-roa",             "ROA (%)",                        [8,   50]),
        ("filter-de",              "D/E (Nợ / VCSH)",               [0,   1.5]),
        ("filter-current-ratio",   "Thanh toán hiện hành",           [1.0, 10]),
        # Tầng 3 – Lợi thế cạnh tranh & định giá hợp lý
        ("filter-rev-cagr-5y",     "CAGR Doanh thu 5 năm (%)",      [7,  100]),
        ("filter-eps-cagr-5y",     "CAGR EPS 5 năm (%)",            [5,  100]),
        ("filter-pe",              "P/E Ratio – Định giá hợp lý",   [0,   20]),
        ("filter-ebit-margin",     "Biên EBIT (%) – Hiệu quả vốn",  [10, 100]),
    ],
}


# ============================================================================
# Gộp: thêm/xóa filter + load bộ lọc đã lưu + reset
# (tránh duplicate output conflict)
# ============================================================================

@app.callback(
    Output("selected-filters-container", "children", allow_duplicate=True),
    Output("active-filters-store", "data", allow_duplicate=True),
    Output("strategy-preset-dropdown", "value", allow_duplicate=True),
    Output("filter-all-industry", "value", allow_duplicate=True),
    Output("saved-filters-dropdown", "value"),
    Output("saved-filters-store", "data"),
    Output("saved-filters-dropdown", "options"),
    Output("save-toast", "is_open"),
    Output("save-toast", "children"),
    Output("filter-unsaved-flag", "data", allow_duplicate=True),  # 10th: unsaved state
    Output("readonly-filters-store", "data", allow_duplicate=True),  # 11th: readonly filter ids
    Input({"type": "criteria-item", "index": ALL}, "n_clicks"),
    Input({"type": "remove-filter", "index": ALL}, "n_clicks"),
    Input("saved-filters-dropdown", "value"),
    Input("btn-reset-ui", "n_clicks"),
    Input("btn-save", "n_clicks"),
    Input("strategy-preset-dropdown", "value"),
    State("active-filters-store", "data"),
    State("selected-filters-container", "children"),
    State("strategy-preset-dropdown", "value"),
    State("filter-all-industry", "value"),
    State("saved-filters-store", "data"),
    State("saved-filters-dropdown", "options"),
    prevent_initial_call=True,
)
def manage_filter_ui(
        criteria_clicks, remove_clicks,
        dd_selected, n_reset, n_save, strategy_selected,
        active_filters, current_children,
        strategy, industry,
        saved_store, saved_options,
):
    from datetime import datetime

    ctx = callback_context
    if not ctx.triggered:
        return (no_update,) * 11

    trigger_prop = ctx.triggered[0]['prop_id']

    # helpers
    def _norm_children(ch):
        if ch is None: return []
        if isinstance(ch, dict): return [ch]
        if not isinstance(ch, list): return []
        return ch

    def _build_slider_ui(af):
        """Tái tạo danh sách filter UI từ dict active_filters."""
        dr = get_filter_ranges()
        children = []
        for fid, fdata in af.items():
            label = fdata.get('label', fid)
            val = fdata.get('value', None)
            ftype = fdata.get('type', 'range')
            if ftype == 'boolean':
                tl, fl = 'Có', 'Không'
                for cfg in CRITERIA_CONFIG.values():
                    if cfg['filter_id'] == fid and cfg.get('type') == 'boolean':
                        tl = cfg.get('true_label', 'Có')
                        fl = cfg.get('false_label', 'Không')
                        break
                children.append(create_bool_filter_ui(fid, label, tl, fl))
            else:
                if fid in dr:
                    fmin, fmax = dr[fid]
                else:
                    fmin, fmax = 0, 100
                    for cfg in CRITERIA_CONFIG.values():
                        if cfg['filter_id'] == fid:
                            fmin = cfg.get('min', 0)
                            fmax = cfg.get('max', 100)
                            break
                children.append(create_range_filter_ui(fid, label, fmin, fmax, val))
        return children

    NO = no_update
    af = dict(active_filters or {})
    ch = _norm_children(current_children)
    saved = dict(saved_store or {})
    opts = list(saved_options or [{"label": "Bộ lọc cá nhân", "value": "default"}])

    # ── CHỌN TRƯỜNG PHÁI → AUTO ADD FILTER CARDS (display-only, không active) ──
    if trigger_prop == "strategy-preset-dropdown.value":
        if not strategy_selected:
            return (NO,) * 11
        filt_list = _STRATEGY_FILTERS.get(strategy_selected, [])
        if not filt_list:
            return (NO,) * 11
        new_ch = []
        readonly_ids = []          # ← THÊM danh sách này
        ranges = get_filter_ranges()
        for (fid, lbl, default_rng) in filt_list:
            if fid in ranges:
                actual_min, actual_max = ranges[fid]
                lo = max(actual_min, min(float(default_rng[0]), actual_max))
                hi = max(actual_min, min(float(default_rng[1]), actual_max))
            else:
                actual_min, actual_max = default_rng[0], default_rng[1]
                lo, hi = float(default_rng[0]), float(default_rng[1])
            readonly_ids.append(fid)   # ← THÊM dòng này
            # Dùng card "Tham khảo" thay vì card active
            new_ch.append(create_range_filter_ui_readonly(fid, lbl, actual_min, actual_max, [lo, hi]))
        dirty_opts = [
            {**o, "label": ("* " + o["label"]) if (o.get("value") == dd_selected
                                                   and dd_selected and dd_selected != "default"
                                                   and not o["label"].startswith("* ")) else o["label"]}
            for o in opts
        ]
        return new_ch, NO, NO, NO, NO, NO, dirty_opts, NO, NO, True, readonly_ids

    # ── RESET ──────────────────────────────────────────────────────────────
    if trigger_prop == "btn-reset-ui.n_clicks":
        clean_opts = [{**o, "label": o["label"][2:] if o["label"].startswith("* ") else o["label"]}
                      for o in opts]
        return [], {}, None, ["all"], "default", NO, clean_opts, NO, NO, None, []  # ← thêm []


    # ── LƯU BỘ LỌC ─────────────────────────────────────────────────────────
    if trigger_prop == "btn-save.n_clicks":
        has_f = bool(af)
        has_s = bool(strategy)
        has_i = (bool(industry) and industry != "all"
                 and isinstance(industry, list)
                 and any(x != "all" for x in industry))
        if not has_f and not has_s and not has_i:
            return (NO, NO, NO, NO, NO, NO, NO,
                    True,
                    [html.I(className="fas fa-exclamation-triangle me-2"),
                     "Chưa chọn bộ lọc nào để lưu!"],
                    NO)
        name = datetime.now().strftime("%H:%M:%S – %d/%m/%Y")
        saved[name] = {"active_filters": af, "strategy": strategy, "industry": industry}
        base = {"label": "Bộ lọc cá nhân", "value": "default"}
        new_opts = [o for o in opts if o.get("value") != name]
        if not any(o.get("value") == "default" for o in new_opts):
            new_opts = [base] + new_opts
        # Remove * from all options when saving fresh
        new_opts = [{**o, "label": o["label"][2:] if o["label"].startswith("* ") else o["label"]}
                    for o in new_opts]
        new_opts.append({"label": name, "value": name})
        return (
            NO, NO, NO, NO,
            name,
            saved, new_opts,
            True,
            [html.I(className="fas fa-check-circle me-2", style={"color": "#3fb950"}),
             f' Đã lưu: "{name}"'],
            False,  # clean
            NO,   # ← thêm NO cho readonly-filters-store
        )

    # ── LOAD BỘ LỌC ĐÃ LƯU ────────────────────────────────────────────────
    if trigger_prop == "saved-filters-dropdown.value":
        if not dd_selected or dd_selected == "default":
            clean_opts = [{**o, "label": o["label"][2:] if o["label"].startswith("* ") else o["label"]}
                          for o in opts]
            return [], {}, None, ["all"], "default", NO, clean_opts, NO, NO, None, []  # ← thêm []

        if dd_selected not in saved:
            return (NO,) * 11
        snap = saved[dd_selected]
        af2 = snap.get("active_filters", {})
        # Clean * from loaded preset label
        clean_opts = [{**o, "label": o["label"][2:] if o["label"].startswith("* ") else o["label"]}
                      for o in opts]
        return (
            _build_slider_ui(af2), af2,
            snap.get("strategy", None),
            snap.get("industry", "all"),
            NO, NO, clean_opts, NO, NO, False,
            [],   # ← reset readonly khi load preset đã lưu
        )

    # ── XÓA FILTER ─────────────────────────────────────────────────────────
    if '"type":"remove-filter"' in trigger_prop:
        fid = json.loads(trigger_prop.split('.')[0])['index']
        af.pop(fid, None)
        ch = [c for c in ch
              if not (isinstance(c, dict)
                      and isinstance(c.get('props', {}).get('id', {}), dict)
                      and c['props']['id'].get('index') == fid)]
        dirty_opts = [
            {**o, "label": ("* " + o["label"]) if (o.get("value") == dd_selected
                                                   and dd_selected and dd_selected != "default"
                                                   and not o["label"].startswith("* ")) else o["label"]}
            for o in opts
        ]
        return ch, af, NO, NO, NO, NO, dirty_opts, NO, NO, True, NO

    # ── THÊM FILTER ─────────────────────────────────────────────────────────
    if '"type":"criteria-item"' in trigger_prop:
        # Guard: n_clicks phải > 0, tránh false trigger khi Dash mount component mới
        triggered_val = ctx.triggered[0].get('value', 0)
        if not triggered_val or triggered_val == 0:
            return (NO,) * 11

        idx = json.loads(trigger_prop.split('.')[0])['index']
        criteria_id = idx if idx.startswith("criteria-") else f"criteria-{idx}"
        if criteria_id not in CRITERIA_CONFIG:
            return (NO,) * 11
        config = CRITERIA_CONFIG[criteria_id]
        filter_id = config['filter_id']
        if filter_id in af:
            return (NO,) * 11

        # Kiểm tra trùng trên cả af VÀ ch (vì af không được set ngay khi thêm card)
        already_in_af = filter_id in af
        already_in_ch = any(
            isinstance(c, dict)
            and isinstance(c.get('props', {}).get('id', {}), dict)
            and c['props']['id'].get('index') == filter_id
            for c in ch
        )
        if already_in_af or already_in_ch:
            return (NO,) * 11
        ranges = get_filter_ranges()
        if config['type'] == 'boolean':
            # KHÔNG set af[filter_id] — chỉ render card, activate khi user click Có/Không
            if ch and isinstance(ch[0], str): ch = []
            ch.append(create_bool_filter_ui(
                filter_id, config['label'],
                true_label=config.get('true_label', 'Có'),
                false_label=config.get('false_label', 'Không'),
            ))
            dirty_opts = [
                {**o, "label": ("* " + o["label"]) if (o.get("value") == dd_selected
                                                       and dd_selected and dd_selected != "default"
                                                       and not o["label"].startswith("* ")) else o["label"]}
                for o in opts
            ]
            return ch, NO, NO, NO, NO, NO, dirty_opts, NO, NO, NO, NO
        if filter_id in ranges:
            actual_min, actual_max = ranges[filter_id]
            default_val = [actual_min, actual_max]
        else:
            actual_min = config.get('min', 0)
            actual_max = config.get('max', 100)
            default_val = config['default_value']
        # KHÔNG set af[filter_id] — card chỉ hiện lên, screener không chạy ngay.
        # activate_readonly_filter_on_drag sẽ activate khi user thực sự kéo slider.
        if ch and isinstance(ch[0], str): ch = []
        ch.append(create_range_filter_ui(filter_id, config['label'], actual_min, actual_max, default_val))
        dirty_opts = [
            {**o, "label": ("* " + o["label"]) if (o.get("value") == dd_selected
                                                   and dd_selected and dd_selected != "default"
                                                   and not o["label"].startswith("* ")) else o["label"]}
            for o in opts
        ]
        return ch, NO, NO, NO, NO, NO, dirty_opts, NO, NO, NO, NO

    return (NO,) * 11


# ============================================================================
# CALLBACK: CẬP NHẬT BADGE ĐẾM MÃ KHI SLIDER THAY ĐỔI (REALTIME)
# ============================================================================

@app.callback(
    Output({"type": "filter-count-badge", "filter": MATCH}, "children"),
    Output({"type": "filter-count-badge", "filter": MATCH}, "style"),
    Input({"type": "range-slider", "filter": MATCH}, "value"),
    State("filter-year-store", "data"),
    prevent_initial_call=True
)
def update_count_badge(range_value, filter_year):
    """Khi kéo slider → đếm mã thỏa mãn range và cập nhật badge màu."""
    _style_base = {
        "fontSize": "9px", "fontWeight": "700",
        "backgroundColor": "#0d1117", "border": "1px solid #21262d",
        "borderRadius": "8px", "padding": "1px 5px", "whiteSpace": "nowrap",
    }
    if not range_value or len(range_value) != 2:
        return "–", {**_style_base, "color": "#484f58"}
    ctx = callback_context
    if not ctx.triggered:
        return no_update, no_update
    try:
        filter_id = json.loads(ctx.triggered[0]["prop_id"].split(".")[0])["filter"]
    except Exception:
        return "–", {**_style_base, "color": "#484f58"}
    count = _count_matching(filter_id, range_value, filter_year)
    if count is None:
        return "–", {**_style_base, "color": "#484f58"}
    return f"{count} mã", {**_style_base, "color": "#3fb950" if count > 0 else "#ef4444"}


# ============================================================================
# CALLBACK 5 (FIXED): SYNC TẤT CẢ RANGE SLIDERS -> STORES TƯƠNG ỨNG
# ============================================================================

_ALL_FILTER_STORE_IDS = [
    "filter-price", "filter-volume", "filter-market-cap", "filter-eps",
    "filter-perf-1w", "filter-perf-1m",
    "filter-pe", "filter-pb", "filter-ps", "filter-ev-ebitda", "filter-div-yield",
    "filter-roe", "filter-roa", "filter-gross-margin", "filter-net-margin", "filter-ebit-margin",
    "filter-rev-growth-yoy", "filter-rev-cagr-5y", "filter-eps-growth-yoy", "filter-eps-cagr-5y",
    "filter-de", "filter-current-ratio", "filter-net-cash-cap", "filter-net-cash-assets",
    "filter-price-vs-sma5", "filter-price-vs-sma10", "filter-price-vs-sma20",
    "filter-price-vs-sma50", "filter-price-vs-sma100", "filter-price-vs-sma200",
    "filter-pct-from-high-1y", "filter-pct-from-low-1y",
    "filter-pct-from-high-all", "filter-pct-from-low-all",
    "filter-rsi14", "filter-macd-hist", "filter-bb-width",
    "filter-consec-up", "filter-consec-down",
    "filter-beta", "filter-alpha",
    "filter-rs-3d", "filter-rs-1m", "filter-rs-3m", "filter-rs-1y", "filter-rs-avg",
    "filter-vol-vs-sma5", "filter-vol-vs-sma10", "filter-vol-vs-sma20", "filter-vol-vs-sma50",
    "filter-avg-vol-5d", "filter-avg-vol-10d", "filter-avg-vol-50d",
    "filter-gtgd-1w", "filter-gtgd-10d", "filter-gtgd-1m",
    "filter-canslim",
]

@app.callback(
    [Output(fid, "data", allow_duplicate=True) for fid in _ALL_FILTER_STORE_IDS]
    + [Output("filter-unsaved-flag", "data", allow_duplicate=True)],
    Input({"type": "range-slider", "filter": ALL}, "value"),
    State({"type": "range-slider", "filter": ALL}, "id"),
    State({"type": "range-slider", "filter": ALL}, "min"),
    State({"type": "range-slider", "filter": ALL}, "max"),
    State("saved-filters-dropdown", "value"),
    State("readonly-filters-store", "data"),   # ← THÊM
    prevent_initial_call=True
)
def update_all_range_stores(slider_values, slider_ids, slider_mins, slider_maxs,
                             current_dd_val, readonly_filter_ids):   # ← THÊM tham số
    ctx = callback_context
    if not ctx.triggered:
        return [no_update] * (len(_ALL_FILTER_STORE_IDS) + 1)

    readonly_ids = readonly_filter_ids or []

    slider_map = {}
    for val, id_spec, smin, smax in zip(slider_values, slider_ids, slider_mins, slider_maxs):
        if isinstance(id_spec, dict) and 'filter' in id_spec:
            fid = id_spec['filter']
            # Bỏ qua slider readonly (card Tham khảo)
            if fid in readonly_ids:
                continue
            # Bỏ qua nếu value == [min, max] → slider chỉ mới mount
            if val and len(val) == 2 and val[0] == smin and val[1] == smax:
                continue
            slider_map[fid] = val

    store_outputs = [slider_map.get(fid, no_update) for fid in _ALL_FILTER_STORE_IDS]

    has_saved = bool(current_dd_val and current_dd_val != "default")
    unsaved_out = True if has_saved and slider_map else no_update

    return store_outputs + [unsaved_out]

@app.callback(
    Output("active-filters-store", "data", allow_duplicate=True),
    Input({"type": "range-slider", "filter": ALL}, "value"),
    State({"type": "range-slider", "filter": ALL}, "id"),
    State({"type": "range-slider", "filter": ALL}, "min"),
    State({"type": "range-slider", "filter": ALL}, "max"),
    State("active-filters-store", "data"),
    State("selected-filters-container", "children"),
    State("readonly-filters-store", "data"),
    prevent_initial_call=True
)
def activate_readonly_filter_on_drag(slider_values, slider_ids, slider_mins,
                                      slider_maxs, active_filters, filter_children,
                                      readonly_filter_ids):
    ctx = callback_context
    if not ctx.triggered:
        return no_update

    try:
        triggered_id = json.loads(ctx.triggered[0]["prop_id"].split(".")[0])
        dragged_fid = triggered_id.get("filter")
    except Exception:
        return no_update

    if not dragged_fid:
        return no_update

    # Lấy value + min + max của slider vừa trigger
    new_val = s_min = s_max = None
    for val, id_spec, smin, smax in zip(slider_values, slider_ids, slider_mins, slider_maxs):
        if isinstance(id_spec, dict) and id_spec.get("filter") == dragged_fid:
            new_val, s_min, s_max = val, smin, smax
            break

    if new_val is None:
        return no_update

    # Guard 1: slider mới mount (value == [min, max]) → bỏ qua
    if s_min is not None and s_max is not None:
        if new_val[0] == s_min and new_val[1] == s_max:
            return no_update

    af = dict(active_filters or {})
    readonly_ids = readonly_filter_ids or []

    # Guard 2: card "Tham khảo" → KHÔNG auto-activate, chỉ update nếu đã active
    if dragged_fid in readonly_ids:
        if dragged_fid not in af:
            return no_update   # ← Return hẳn, không fall-through
        # Đã active rồi (user thêm tay trùng với strategy) → update value
        af[dragged_fid]["value"] = new_val
        return af

    # Card thường
    if dragged_fid not in af:
        # Auto-activate khi user kéo lần đầu
        label = dragged_fid
        for cfg in CRITERIA_CONFIG.values():
            if cfg.get("filter_id") == dragged_fid:
                label = cfg.get("label", dragged_fid)
                break
        af[dragged_fid] = {"label": label, "type": "range", "value": new_val}
    else:
        af[dragged_fid]["value"] = new_val

    return af


# ============================================================================
# CALLBACK: TOGGLE COLLAPSE GROUPS
# ============================================================================

@app.callback(
    [Output("collapse-overview", "is_open"),
     Output("collapse-valuation", "is_open"),
     Output("collapse-profitability", "is_open"),
     Output("collapse-growth", "is_open"),
     Output("collapse-health", "is_open"),
     Output("collapse-price-ma", "is_open"),
     Output("collapse-highlow", "is_open"),
     Output("collapse-tech-indicators", "is_open"),
     Output("collapse-momentum", "is_open"),
     Output("collapse-volume-tech", "is_open")],
    [Input("collapse-overview-btn", "n_clicks"),
     Input("collapse-valuation-btn", "n_clicks"),
     Input("collapse-profitability-btn", "n_clicks"),
     Input("collapse-growth-btn", "n_clicks"),
     Input("collapse-health-btn", "n_clicks"),
     Input("collapse-price-ma-btn", "n_clicks"),
     Input("collapse-highlow-btn", "n_clicks"),
     Input("collapse-tech-indicators-btn", "n_clicks"),
     Input("collapse-momentum-btn", "n_clicks"),
     Input("collapse-volume-tech-btn", "n_clicks")],
    [State("collapse-overview", "is_open"),
     State("collapse-valuation", "is_open"),
     State("collapse-profitability", "is_open"),
     State("collapse-growth", "is_open"),
     State("collapse-health", "is_open"),
     State("collapse-price-ma", "is_open"),
     State("collapse-highlow", "is_open"),
     State("collapse-tech-indicators", "is_open"),
     State("collapse-momentum", "is_open"),
     State("collapse-volume-tech", "is_open")],
    prevent_initial_call=True
)
def toggle_all_collapses(
        n_ov, n_va, n_pr, n_gr, n_he, n_pm, n_hl, n_tc, n_mo, n_vo,
        s_ov, s_va, s_pr, s_gr, s_he, s_pm, s_hl, s_tc, s_mo, s_vo
):
    ctx = callback_context
    if not ctx.triggered:
        return [no_update] * 10

    triggered_id = ctx.triggered[0]["prop_id"].split(".")[0]
    states = [s_ov, s_va, s_pr, s_gr, s_he, s_pm, s_hl, s_tc, s_mo, s_vo]
    btn_ids = [
        "collapse-overview-btn", "collapse-valuation-btn",
        "collapse-profitability-btn", "collapse-growth-btn", "collapse-health-btn",
        "collapse-price-ma-btn", "collapse-highlow-btn", "collapse-tech-indicators-btn",
        "collapse-momentum-btn", "collapse-volume-tech-btn"
    ]
    return [not states[i] if triggered_id == b else no_update for i, b in enumerate(btn_ids)]


# ============================================================================
# CALLBACK: SYNC SLIDER → INPUT BOXES (slider di chuyển → cập nhật 2 ô nhập)
# ============================================================================

@app.callback(
    Output({"type": "range-min-input", "filter": MATCH}, "value"),
    Output({"type": "range-max-input", "filter": MATCH}, "value"),
    Input({"type": "range-slider", "filter": MATCH}, "value"),
    prevent_initial_call=True
)
def sync_inputs_from_slider(range_value):
    """Khi kéo slider → cập nhật 2 ô nhập tay tương ứng."""
    if not range_value or len(range_value) != 2:
        return no_update, no_update
    return range_value[0], range_value[1]


# ============================================================================
# CALLBACK: SYNC MIN INPUT → SLIDER (nhập tay min → cập nhật slider)
# ============================================================================

@app.callback(
    Output({"type": "range-slider", "filter": MATCH}, "value", allow_duplicate=True),
    Input({"type": "range-min-input", "filter": MATCH}, "value"),
    State({"type": "range-slider", "filter": MATCH}, "value"),
    State({"type": "range-slider", "filter": MATCH}, "min"),
    State({"type": "range-slider", "filter": MATCH}, "max"),
    prevent_initial_call=True
)
def sync_slider_from_min_input(min_input, current_val, s_min, s_max):
    """Nhập tay ô Min → cập nhật slider (debounce=True nên chỉ kích hoạt khi blur/Enter)."""
    if min_input is None or current_val is None:
        return no_update
    try:
        lo = max(s_min, min(float(min_input), s_max))
        hi = current_val[1]
        # Nếu min vượt max thì kéo max lên theo
        hi = max(lo, hi)
        return [lo, hi]
    except (TypeError, ValueError):
        return no_update


# ============================================================================
# CALLBACK: SYNC MAX INPUT → SLIDER (nhập tay max → cập nhật slider)
# ============================================================================

@app.callback(
    Output({"type": "range-slider", "filter": MATCH}, "value", allow_duplicate=True),
    Input({"type": "range-max-input", "filter": MATCH}, "value"),
    State({"type": "range-slider", "filter": MATCH}, "value"),
    State({"type": "range-slider", "filter": MATCH}, "min"),
    State({"type": "range-slider", "filter": MATCH}, "max"),
    prevent_initial_call=True
)
def sync_slider_from_max_input(max_input, current_val, s_min, s_max):
    """Nhập tay ô Max → cập nhật slider (debounce=True nên chỉ kích hoạt khi blur/Enter)."""
    if max_input is None or current_val is None:
        return no_update
    try:
        lo = current_val[0]
        hi = max(s_min, min(float(max_input), s_max))
        # Nếu max thấp hơn min thì kéo min xuống theo
        lo = min(lo, hi)
        return [lo, hi]
    except (TypeError, ValueError):
        return no_update


# ============================================================================
# CALLBACK: QUẢN LÝ BỘ LỌC NGÀNH (logic "Tất cả ngành" tự động)
#
# Quy tắc (dùng list comprehension thuần, không cần callback phức tạp):
#   - Khi chọn ngành cụ thể → "all" tự bị loại (dư thừa)
#   - Khi xóa hết ngành cụ thể (hoặc chọn rỗng) → khôi phục ["all"]
# ============================================================================

@app.callback(
    Output("filter-all-industry", "value", allow_duplicate=True),
    Input("filter-all-industry", "value"),
    prevent_initial_call=True
)
def manage_industry_all_option(selected):
    """
    Dùng list comprehension để lọc:
      specific = các giá trị khác "all"
      → Nếu có specific: trả về specific (loại bỏ "all" thừa)
      → Nếu không có specific (rỗng hoặc chỉ có "all"): trả về ["all"]
    """
    if not selected:
        return ["all"]

    specific = [v for v in selected if v != "all"]

    return specific if specific else ["all"]


# ── SUB-INDUSTRY: giữ "Tất cả ngành con" khi không chọn gì ──────────────────
@app.callback(
    Output("filter-sub-industry", "value", allow_duplicate=True),
    Input("filter-sub-industry", "value"),
    prevent_initial_call=True
)
def manage_sub_industry_all_option(selected):
    if not selected:
        return ["all"]
    specific = [v for v in selected if v != "all"]
    return specific if specific else ["all"]


# ============================================================================
# CALLBACK: BOOLEAN FILTER TOGGLE (Có / Không nút bấm)
# Khi click Có → active, Không → inactive; click lại sẽ toggle active-filters-store
# ============================================================================

@app.callback(
    Output({"type": "bool-filter-value", "filter": MATCH}, "data"),
    Output({"type": "bool-btn-true", "filter": MATCH}, "style"),
    Output({"type": "bool-btn-false", "filter": MATCH}, "style"),
    Input({"type": "bool-btn-true", "filter": MATCH}, "n_clicks"),
    Input({"type": "bool-btn-false", "filter": MATCH}, "n_clicks"),
    State({"type": "bool-filter-value", "filter": MATCH}, "data"),
    prevent_initial_call=True,
)
def toggle_bool_filter(n_true, n_false, current_val):
    """Toggle Có/Không và cập nhật style nút active."""
    _active_true = {"flex": "1", "padding": "4px 0", "fontSize": "11px",
                    "fontWeight": "700", "border": "1px solid #3fb950",
                    "borderRadius": "4px", "cursor": "pointer",
                    "backgroundColor": "#1a3a1a", "color": "#3fb950"}
    _active_false = {"flex": "1", "padding": "4px 0", "fontSize": "11px",
                     "fontWeight": "700", "border": "1px solid #ef4444",
                     "borderRadius": "4px", "cursor": "pointer",
                     "backgroundColor": "#3a1a1a", "color": "#ef4444"}
    _inactive = {"flex": "1", "padding": "4px 0", "fontSize": "11px",
                 "fontWeight": "600", "border": "1px solid #30363d",
                 "borderRadius": "4px", "cursor": "pointer",
                 "backgroundColor": "#0d1117", "color": "#6e7681"}

    ctx = callback_context
    if not ctx.triggered:
        return no_update, no_update, no_update

    trigger = ctx.triggered[0]["prop_id"]
    new_val = 1 if "bool-btn-true" in trigger else 0

    if new_val == 1:
        return 1, _active_true, _inactive
    else:
        return 0, _inactive, _active_false


# ============================================================================
# CALLBACK: SYNC BOOLEAN VALUE → active-filters-store (trigger screener)
# Fix: toggle Có/Không phải cập nhật active-filters-store để screener chạy lại
# ============================================================================

@app.callback(
    Output("active-filters-store", "data", allow_duplicate=True),
    Input({"type": "bool-filter-value", "filter": ALL}, "data"),
    State({"type": "bool-filter-value", "filter": ALL}, "id"),
    State("active-filters-store", "data"),
    prevent_initial_call=True,
)
def sync_bool_to_active_filters(bool_values, bool_ids, active_filters):
    """
    Khi user click Có/Không trên bất kỳ boolean filter nào:
    → cập nhật active-filters-store["filter_id"]["value"] = 0/1
    → screener tự trigger vì active-filters-store là Input của nó
    """
    ctx = callback_context
    if not ctx.triggered:
        return no_update

    # DEBUG - xóa sau khi fix
    print(f"[sync_bool] triggered={ctx.triggered[0]['prop_id']}")
    print(f"[sync_bool] bool_values={bool_values}")
    print(f"[sync_bool] active_filters keys={list((active_filters or {}).keys())}")

    af = dict(active_filters or {})
    changed = False

    for val, id_spec in zip(bool_values, bool_ids):
        fid = id_spec.get("filter") if isinstance(id_spec, dict) else None
        if not fid:
            continue
        if fid in af:
            # Filter đã tồn tại → chỉ cập nhật value nếu thay đổi
            if af[fid].get("value") != val:
                af[fid] = dict(af[fid])  # copy để tránh mutate
                af[fid]["value"] = val
                changed = True
        else:
            # Filter chưa có trong store → tìm label từ CRITERIA_CONFIG rồi ADD MỚI
            label = fid  # fallback
            for cfg in CRITERIA_CONFIG.values():
                if cfg.get("filter_id") == fid and cfg.get("type") == "boolean":
                    label = cfg.get("label", fid)
                    break
            af[fid] = {"label": label, "type": "boolean", "value": val}
            changed = True

    return af if changed else no_update


# ============================================================================
# CLIENTSIDE CALLBACK: AUTO-SCROLL KHI USER TƯƠNG TÁC SIDEBAR
# Cuộn xuống #screener-scroll-anchor khi chọn trường phái hoặc ngành
# ============================================================================

app.clientside_callback(
    """
    function(strategy_val, industry_val, sub_industry_val, ticker_val,
             btn_apply, btn_reset, filter_children) {
        // Bất kỳ thao tác nào trên BỘ LỌC → scroll anchor lên top
        const anchor = document.getElementById('screener-scroll-anchor');
        if (anchor) {
            setTimeout(function() {
                anchor.scrollIntoView({ behavior: 'smooth', block: 'start' });
            }, 100);
        }
        return window.dash_clientside.no_update;
    }
    """,
    Output("screener-scroll-anchor", "children"),
    Input("strategy-preset-dropdown", "value"),
    Input("filter-all-industry", "value"),
    Input("filter-sub-industry", "value"),
    Input("search-ticker-input", "value"),
    Input("btn-filter", "n_clicks"),
    Input("btn-reset", "n_clicks"),
    Input("selected-filters-container", "children"),
    prevent_initial_call=True,
)

# ============================================================================
# CALLBACK: TỰ ĐỘNG CO GIÃN CHIỀU CAO selected-filters-container
# Dùng clientside để cập nhật DOM ngay lập tức, không cần round-trip server.
# ≤4 thẻ → 150px | ≤8 → 300px | ≤12 → 450px | >12 → 600px + scroll
# ============================================================================

# (Clientside callback co giãn grid đã bị xóa — layout mới dùng flex column trong wizard)

# ============================================================================
# CLIENTSIDE CALLBACK: CẬP NHẬT BADGE TỔNG MÃ REALTIME
# Đọc từ screener-table rowData → không cần round-trip server
# ============================================================================

app.clientside_callback(
    """
    function(rowData) {
        if (!rowData) return '–';
        return String(rowData.length);
    }
    """,
    Output("result-count-number", "children"),
    Input("screener-table", "rowData"),
    prevent_initial_call=False,
)


# ============================================================================
# CALLBACK: SYNC YEAR DROPDOWN → STORE
# ============================================================================

@app.callback(
    Output("filter-year-store", "data"),
    Input("filter-year-dropdown", "value"),
    prevent_initial_call=True,
)
def sync_year_filter(year_val):
    """Đồng bộ dropdown năm vào store để screener đọc."""
    return year_val

@app.callback(
    Output("filter-exchange", "value", allow_duplicate=True),
    Input("filter-exchange", "value"),
    prevent_initial_call=True
)
def normalize_exchange_filter(val):
    if not val:
        return ["all"]
    # Nếu vừa chọn thêm sàn cụ thể, xóa "all"
    if "all" in val and len(val) > 1:
        return [v for v in val if v != "all"]
    # Nếu bỏ hết → về all
    if not [v for v in val if v != "all"]:
        return ["all"]
    return val