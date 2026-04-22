# src/callbacks/column_callbacks.py
"""
Callback cập nhật cột của AG Grid screener-table dựa trên bộ lọc đang active.
Logic: Khi user thêm chỉ tiêu vào bộ lọc → cột tương ứng hiện ra trên bảng.
"""
from dash import Input, Output, no_update
from src.app_instance import app

# ============================================================================
# HELPER: GRADE CELL STYLE (dùng chung cho Value/Growth/Momentum/VGM Score)
# ============================================================================
_GRADE_CELL_STYLE = {
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
        return {'backgroundColor': c.bg, 'color': c.color,
                'fontWeight': '700', 'textAlign': 'center',
                'borderRadius': '4px'};
    """
}

_PCT_CELL_STYLE = {
    "function": """
        const base = {
            'fontFamily': "'Roboto Mono', monospace",
            'fontSize': '12.5px',
            'fontVariantNumeric': 'tabular-nums',
            'fontWeight': '600',
            'letterSpacing': '0.2px'
        };
        if (params.value == null) return {...base, 'color': '#484f58'};
        if (params.value > 0)  return {...base, 'color': '#10b981'};
        if (params.value < 0)  return {...base, 'color': '#ef4444'};
        return {...base, 'color': '#f5c842'};
    """
}

_DE_CELL_STYLE = {
    "function": """
        if (!params.value) return {};
        if (params.value < 1) return {'color': '#10b981', 'fontWeight': '600'};
        if (params.value > 3) return {'color': '#ef4444', 'fontWeight': '600'};
        return {'color': '#f59e0b'};
    """
}

_RSI_CELL_STYLE = {
    "function": """
        if (!params.value) return {};
        if (params.value >= 70) return {'color': '#ef4444', 'fontWeight': '700'};
        if (params.value <= 30) return {'color': '#10b981', 'fontWeight': '700'};
        return {'color': '#c9d1d9'};
    """
}

_MACD_CELL_STYLE = {
    "function": """
        if (params.value == null) return {};
        return params.value > 0
            ? {'color': '#10b981', 'fontWeight': '600'}
            : {'color': '#ef4444', 'fontWeight': '600'};
    """
}

_BOOL_CELL_STYLE = {
    "function": """
        return params.value === 1
            ? {'color': '#10b981', 'fontWeight': '700'}
            : {'color': '#8b949e'};
    """
}


def _num(field, header, width=100, decimals=2, suffix="", color=None):
    """Tạo cột số với formatter chuẩn."""
    if suffix:
        fmt_fn = f"params.value != null ? d3.format(',.{decimals}f')(params.value) + '{suffix}' : '-'"
    else:
        fmt_fn = f"params.value != null ? d3.format(',.{decimals}f')(params.value) : '-'"
    col = {
        "field": field,
        "headerName": header,
        "type": "rightAligned",
        "sortable": True,
        "width": width,
        "valueFormatter": {"function": fmt_fn},
    }
    if color:
        col["cellStyle"] = {"function": f"return {{'color': '{color}'}};"}
    return col


def _pct(field, header, width=110):
    """Cột % có màu xanh/đỏ."""
    return {
        "field": field,
        "headerName": header,
        "type": "rightAligned",
        "sortable": True,
        "width": width,
        "valueFormatter": {"function": "params.value != null ? d3.format(',.2f')(params.value) + '%' : '-'"},
        "cellStyle": _PCT_CELL_STYLE,
    }


def _grade(field, header, width=100):
    return {"field": field, "headerName": header,
            "width": width, "sortable": True, "cellStyle": _GRADE_CELL_STYLE}


# ============================================================================
# CỘT CỐ ĐỊNH (luôn hiển thị)
# ============================================================================

# JS function tính màu SSI — viết thẳng vào cellStyle, KHÔNG dùng f-string
# để tránh lỗi Python/JS escaping
def _ssi_ticker_style():
    return {
        "color": "#00d4ff",
        "fontWeight": "800",
        "fontSize": "14px",
        "letterSpacing": "1px",
        "fontFamily": "'Sora', 'Inter', sans-serif",
    }

def _ssi_price_style():
    return {
        "color": "#fbbf24",
        "fontWeight": "700",
        "fontSize": "13px",
        "fontVariantNumeric": "tabular-nums",
        "fontFamily": "'Roboto Mono', monospace",
    }

def _ssi_pct_style():
    return {
        "function": """
            var d = params.data;
            if (!d) return {color: '#94a3b8'};
            var pct = d['Price_Change_Pct'];
            var n = Number(pct);
            var color = '#94a3b8';
            if (pct !== null && pct !== undefined && !isNaN(n)) {
                if      (n >= 6.9)  color = '#38bdf8';
                else if (n >  0.1)  color = '#4ade80';
                else if (n >= -0.1) color = '#fde047';
                else if (n > -6.9)  color = '#f87171';
                else                color = '#ff6b6b';
            }
            return {color: color, fontWeight: '700', fontSize: '12.5px', fontVariantNumeric: 'tabular-nums'};
        """
    }

FIXED_COLS = [
    {
        "field": "Ticker",
        "headerName": "MÃ CK",
        "pinned": "left",
        "width": 100,
        "sortable": True,
        "filter": True,
        "cellStyle": _ssi_ticker_style(),
    },
    {
        "field": "Sector",
        "headerName": "NGÀNH",
        "width": 160,
        "sortable": True,
        "filter": True,
        "cellStyle": {
            "fontFamily": "'Inter', sans-serif",
            "fontSize": "12px",
            "color": "#94a3b8",
        },
    },
    {
        "field": "Price Close",
        "headerName": "GIÁ",
        "type": "rightAligned",
        "sortable": True,
        "width": 110,
        "valueFormatter": {"function": "d3.format(',.0f')(params.value)"},
        "cellStyle": _ssi_price_style(),
    },
    {
        "field": "Price_Change_Pct",
        "headerName": "+/- (%)",
        "headerTooltip": "% thay đổi so với giá đóng cửa ngày hôm trước",
        "type": "rightAligned",
        "sortable": True,
        "width": 90,
        "valueFormatter": {
            "function": "params.value != null ? (params.value > 0 ? '+' : '') + d3.format('.2f')(params.value) + '%' : '–'"
        },
        "cellStyle": _ssi_pct_style(),
    },
    {
        "field": "Perf_1W",
        "headerName": "%1T",
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
        "type": "rightAligned",
        "sortable": True,
        "width": 120,
        "valueFormatter": {"function": "d3.format(',.0f')(params.value)"},
        "cellStyle": {
            "fontFamily": "'Roboto Mono', monospace",
            "fontSize": "12px",
            "fontVariantNumeric": "tabular-nums",
            "color": "#94a3b8",
        },
    },
    {
        "field": "Forward P/E *",
        "headerName": "FWD P/E*",
        "type": "rightAligned",
        "sortable": True,
        "width": 100,
        "valueFormatter": {"function": "params.value != null ? d3.format('.2f')(params.value) : '–'"},
        "cellStyle": {"function": """
            var base = {
                fontFamily: "'Roboto Mono', monospace",
                fontSize: '12px',
                fontVariantNumeric: 'tabular-nums',
            };
            if (!params.value) return Object.assign({}, base, {color: '#484f58'});
            if (params.value < 10) return Object.assign({}, base, {color: '#4ade80', fontWeight: '600'});
            if (params.value > 30) return Object.assign({}, base, {color: '#f87171'});
            return Object.assign({}, base, {color: '#cbd5e1'});
        """},
        "headerTooltip": "Forward P/E ước tính = Giá / (EPS × (1 + EPS Growth)). Chỉ mang tính tham khảo.",
    },
]
# Các cột đặc trưng được tính bởi calculate_*_metrics cho từng trường phái
_FSCORE_COL = {
    "field": "f_score", "headerName": "F-SCORE",
    "type": "rightAligned", "sortable": True, "width": 100,
    "valueFormatter": {"function": "params.value != null ? params.value + '/9' : '-'"},
    "cellStyle": {"function": """
        if (params.value == null) return {};
        if (params.value >= 7) return {'color': '#10b981', 'fontWeight': '700'};
        if (params.value >= 4) return {'color': '#f59e0b'};
        return {'color': '#ef4444'};
    """}
}

_MF_SCORE_COL = {
    "field": "MF_Total_Score", "headerName": "MAGIC SCORE",
    "type": "rightAligned", "sortable": True, "width": 125,
    "valueFormatter": {"function": "params.value != null ? d3.format(',.0f')(params.value) : '-'"},
    "cellStyle": {"function": """
        if (params.value == null) return {};
        if (params.value <= 20) return {'color': '#10b981', 'fontWeight': '700'};
        if (params.value <= 50) return {'color': '#f59e0b'};
        return {'color': '#ef4444'};
    """}
}

_ROC_COL = _pct("ROC_MF", "ROC %", 95)
_EY_COL = _pct("Earnings_Yield_MF", "E.YIELD %", 110)
_PEG_COL = _num("peg_ratio", "PEG", 90, 2)
_RS_RATE = _num("rs_rating", "RS RATING", 105, 1)

# Mapping trường phái → filter_ids cần show thêm (dùng FILTER_TO_COLDEF)
STRATEGY_FILTER_IDS = {
    "STRAT_VALUE": ["filter-pe", "filter-pb", "filter-ps", "filter-ev-ebitda",
                    "filter-de", "filter-current-ratio", "filter-eps", "filter-div-yield"],
    "STRAT_TURNAROUND": ["filter-pe", "filter-pb", "filter-roe", "filter-net-margin",
                         "filter-perf-1m", "filter-perf-1w", "filter-pct-from-low-1y"],
    "STRAT_QUALITY": ["filter-roe", "filter-roa", "filter-gross-margin",
                      "filter-net-margin", "filter-de", "filter-pe", "filter-pb"],
    "STRAT_GARP": ["filter-pe", "filter-eps-growth-yoy", "filter-roe",
                   "filter-rev-growth-yoy", "filter-de", "filter-eps-cagr-5y"],
    "STRAT_DIVIDEND": ["filter-div-yield", "filter-pe", "filter-roe",
                       "filter-eps", "filter-market-cap", "filter-de"],
    "STRAT_PIOTROSKI": ["filter-roe", "filter-roa", "filter-de",
                        "filter-current-ratio", "filter-net-margin", "filter-gross-margin",
                        "filter-rev-growth-yoy"],
    "STRAT_CANSLIM": ["filter-eps-growth-yoy", "filter-rev-growth-yoy", "filter-rs-1y",
                      "filter-vol-vs-sma50", "filter-pe", "filter-pct-from-high-1y",
                      "filter-market-cap"],
    "STRAT_GROWTH": ["filter-rev-growth-yoy", "filter-rev-cagr-5y", "filter-net-margin",
                     "filter-gross-margin", "filter-roe", "filter-eps-growth-yoy",
                     "filter-eps-cagr-5y"],
    "STRAT_MAGIC": ["filter-pe", "filter-roe", "filter-ev-ebitda", "filter-net-margin",
                    "filter-market-cap"],
}

# Mapping trường phái → cột đặc trưng riêng (không có filter tương ứng)
STRATEGY_DIRECT_COLS = {
    "STRAT_PIOTROSKI": [_FSCORE_COL],
    "STRAT_CANSLIM": [_RS_RATE],
    "STRAT_GARP": [_PEG_COL],
    "STRAT_MAGIC": [_MF_SCORE_COL, _ROC_COL, _EY_COL],
}

# ============================================================================
# ÁNH XẠ filter_id → column definition
# ============================================================================
FILTER_TO_COLDEF = {
    # ── Tổng quan ──
    "filter-market-cap": {
        "field": "Market Cap", "headerName": "VỐN HÓA",
        "type": "rightAligned", "sortable": True, "width": 140,
        "valueFormatter": {"function": "params.value != null ? d3.format(',.0f')(params.value/1e9) + ' tỷ' : '-'"},
    },
    "filter-eps": _num("EPS", "EPS", 100, 2, " VND"),
    "filter-perf-1w": _pct("Perf_1W", "1 TUẦN %", 100),
    "filter-perf-1m": _pct("Perf_1M", "1 THÁNG %", 105),

    # ── Định giá ──
    "filter-pe": {
        "field": "P/E", "headerName": "P/E",
        "type": "rightAligned", "sortable": True, "width": 90,
        "valueFormatter": {"function": "params.value ? d3.format('.2f')(params.value) : '-'"},
        "cellStyle": {"function": """
            if (!params.value) return {};
            if (params.value < 15) return {'color': '#10b981', 'fontWeight': '600'};
            if (params.value > 30) return {'color': '#ef4444'};
            return {};
        """}
    },
    "filter-pb": _num("P/B", "P/B", 85, 2),
    "filter-ps": _num("P/S", "P/S", 85, 2),
    "filter-ev-ebitda": _num("EV/EBITDA", "EV/EBITDA", 110, 2),
    "filter-div-yield": _pct("Dividend Yield (%)", "CỔ TỨC %", 105),

    # ── Sinh lời ──
    "filter-roe": {
        "field": "ROE (%)", "headerName": "ROE",
        "type": "rightAligned", "sortable": True, "width": 95,
        "valueFormatter": {"function": "params.value != null ? d3.format('.2f')(params.value) + '%' : '-'"},
        "cellStyle": {"function": """
            if (!params.value) return {};
            if (params.value > 15) return {'color': '#10b981', 'fontWeight': '700'};
            if (params.value < 0)  return {'color': '#ef4444', 'fontWeight': '700'};
            return {};
        """}
    },
    "filter-roa": _pct("ROA (%)", "ROA", 90),
    "filter-gross-margin": _pct("Gross Margin (%)", "BIÊN GỘP", 110),
    "filter-net-margin": _pct("Net Margin (%)", "BIÊN RÒNG", 110),
    "filter-ebit-margin": _pct("EBIT Margin (%)", "BIÊN EBIT", 110),

    # ── Tăng trưởng ──
    "filter-rev-growth-yoy": _pct("Revenue Growth YoY (%)", "DT 1Y%", 105),
    "filter-rev-cagr-5y": _pct("Revenue CAGR 5Y (%)", "DT 5Y%", 100),
    "filter-eps-growth-yoy": _pct("EPS Growth YoY (%)", "EPS 1Y%", 105),
    "filter-eps-cagr-5y": _pct("EPS CAGR 5Y (%)", "EPS 5Y%", 100),

    # ── Sức khỏe TC ──
    "filter-de": {
        "field": "D/E", "headerName": "D/E",
        "type": "rightAligned", "sortable": True, "width": 90,
        "valueFormatter": {"function": "params.value != null ? d3.format('.2f')(params.value) : '-'"},
        "cellStyle": _DE_CELL_STYLE
    },
    "filter-current-ratio": _num("Current Ratio", "THANH TOÁN", 110, 2),
    "filter-net-cash-cap": _pct("Net Cash / Market Cap (%)", "CASH/VH%", 110),
    "filter-net-cash-assets": _pct("Net Cash / Assets (%)", "CASH/TS%", 110),

    # ── Kỹ thuật: Giá vs SMA ──
    "filter-price-vs-sma5": _pct("Price_vs_SMA5", "vs SMA5", 100),
    "filter-price-vs-sma10": _pct("Price_vs_SMA10", "vs SMA10", 105),
    "filter-price-vs-sma20": _pct("Price_vs_SMA20", "vs SMA20", 105),
    "filter-price-vs-sma50": _pct("Price_vs_SMA50", "vs SMA50", 105),
    "filter-price-vs-sma100": _pct("Price_vs_SMA100", "vs SMA100", 110),
    "filter-price-vs-sma200": _pct("Price_vs_SMA200", "vs SMA200", 110),

    # ── Kỹ thuật: Đỉnh/Đáy ──
    "filter-break-high-52w": {
        "field": "Break_High_52W", "headerName": "VƯỢT ĐỈNH 52W",
        "sortable": True, "width": 130,
        "valueFormatter": {"function": "params.value === 1 ? '✅ Có' : '—'"},
        "cellStyle": _BOOL_CELL_STYLE
    },
    "filter-break-low-52w": {
        "field": "Break_Low_52W", "headerName": "PHÁ ĐÁY 52W",
        "sortable": True, "width": 120,
        "valueFormatter": {"function": "params.value === 1 ? '🔻 Có' : '—'"},
        "cellStyle": _BOOL_CELL_STYLE
    },
    "filter-pct-from-high-1y": _pct("Pct_From_High_1Y", "CÁCH ĐỈNH 1Y", 120),
    "filter-pct-from-low-1y": _pct("Pct_From_Low_1Y", "CÁCH ĐÁY 1Y", 120),
    "filter-pct-from-high-all": _pct("Pct_From_High_All", "CÁCH ĐỈNH LS", 120),
    "filter-pct-from-low-all": _pct("Pct_From_Low_All", "CÁCH ĐÁY LS", 120),

    # ── Kỹ thuật: Chỉ báo ──
    "filter-rsi14": {
        "field": "RSI_14", "headerName": "RSI(14)",
        "type": "rightAligned", "sortable": True, "width": 95,
        "valueFormatter": {"function": "params.value != null ? d3.format('.1f')(params.value) : '-'"},
        "cellStyle": _RSI_CELL_STYLE
    },
    "filter-rsi-state": {
        "field": "RSI_State", "headerName": "TRẠNG THÁI RSI",
        "sortable": True, "width": 150,
        "cellStyle": {"function": """
            if (!params.value) return {};
            if (params.value.includes('Over')) return {'color': '#ef4444', 'fontWeight': '600'};
            if (params.value.includes('Sold')) return {'color': '#10b981', 'fontWeight': '600'};
            return {'color': '#8b949e'};
        """}
    },
    "filter-macd-hist": {
        "field": "MACD_Histogram", "headerName": "MACD HIST",
        "type": "rightAligned", "sortable": True, "width": 115,
        "valueFormatter": {"function": "params.value != null ? d3.format(',.4f')(params.value) : '-'"},
        "cellStyle": _MACD_CELL_STYLE
    },
    "filter-bb-width": _pct("BB_Width", "BB WIDTH%", 105),
    "filter-consec-up": {
        "field": "Consec_Up", "headerName": "PHIÊN TĂNG",
        "type": "rightAligned", "sortable": True, "width": 110,
        "valueFormatter": {"function": "params.value ? params.value + ' phiên' : '—'"},
        "cellStyle": {
            "function": "return params.value > 0 ? {'color': '#10b981', 'fontWeight': '700'} : {'color': '#8b949e'};"}
    },
    "filter-consec-down": {
        "field": "Consec_Down", "headerName": "PHIÊN GIẢM",
        "type": "rightAligned", "sortable": True, "width": 115,
        "valueFormatter": {"function": "params.value ? params.value + ' phiên' : '—'"},
        "cellStyle": {
            "function": "return params.value > 0 ? {'color': '#ef4444', 'fontWeight': '700'} : {'color': '#8b949e'};"}
    },

    # ── Kỹ thuật: Momentum / RS ──
    "filter-beta": {
        "field": "Beta", "headerName": "BETA",
        "type": "rightAligned", "sortable": True, "width": 85,
        "valueFormatter": {"function": "params.value != null ? d3.format('.3f')(params.value) : '-'"},
        "cellStyle": {"function": """
            if (params.value == null) return {};
            if (params.value > 1.5) return {'color': '#ef4444'};
            if (params.value < 0.5) return {'color': '#8b949e'};
            return {'color': '#c9d1d9'};
        """}
    },
    "filter-alpha": _pct("Alpha", "ALPHA %", 90),
    "filter-rs-3d": _pct("RS_3D", "RS 3N", 90),
    "filter-rs-1m": _pct("RS_1M", "RS 1TH", 95),
    "filter-rs-3m": _pct("RS_3M", "RS 3TH", 95),
    "filter-rs-1y": _pct("RS_1Y", "RS 1Y", 90),
    "filter-rs-avg": _pct("RS_Avg", "RS TB", 90),

    # ── Kỹ thuật: Khối lượng ──
    "filter-vol-vs-sma5": _num("Vol_vs_SMA5", "KL/SMA5", 100, 2),
    "filter-vol-vs-sma10": _num("Vol_vs_SMA10", "KL/SMA10", 105, 2),
    "filter-vol-vs-sma20": _num("Vol_vs_SMA20", "KL/SMA20", 105, 2),
    "filter-vol-vs-sma50": _num("Vol_vs_SMA50", "KL/SMA50", 105, 2),
    "filter-avg-vol-5d": {
        "field": "Avg_Vol_5D", "headerName": "KL TB 5P",
        "type": "rightAligned", "sortable": True, "width": 115,
        "valueFormatter": {"function": "params.value != null ? d3.format(',.0f')(params.value) : '-'"},
    },
    "filter-avg-vol-10d": {
        "field": "Avg_Vol_10D", "headerName": "KL TB 10P",
        "type": "rightAligned", "sortable": True, "width": 120,
        "valueFormatter": {"function": "params.value != null ? d3.format(',.0f')(params.value) : '-'"},
    },
    "filter-avg-vol-50d": {
        "field": "Avg_Vol_50D", "headerName": "KL TB 50P",
        "type": "rightAligned", "sortable": True, "width": 120,
        "valueFormatter": {"function": "params.value != null ? d3.format(',.0f')(params.value) : '-'"},
    },
    "filter-gtgd-1w": {
        "field": "GTGD_1W", "headerName": "GTGD 1T",
        "type": "rightAligned", "sortable": True, "width": 130,
        "valueFormatter": {"function": "params.value != null ? d3.format(',.0f')(params.value/1e9) + ' tỷ' : '-'"},
    },
    "filter-gtgd-10d": {
        "field": "GTGD_10D", "headerName": "GTGD 10N",
        "type": "rightAligned", "sortable": True, "width": 130,
        "valueFormatter": {"function": "params.value != null ? d3.format(',.0f')(params.value/1e9) + ' tỷ' : '-'"},
    },
    "filter-gtgd-1m": {
        "field": "GTGD_1M", "headerName": "GTGD 1TH",
        "type": "rightAligned", "sortable": True, "width": 130,
        "valueFormatter": {"function": "params.value != null ? d3.format(',.0f')(params.value/1e9) + ' tỷ' : '-'"},
    },

}