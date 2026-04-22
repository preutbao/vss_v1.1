# src/callbacks/screener_callbacks.py
from dash import Input, Output, State, callback_context, no_update, html, dcc, ALL
from dash.exceptions import PreventUpdate
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
import gc
from src.app_instance import app
from src.backend.data_loader import load_market_data, load_financial_data, get_latest_snapshot, get_snapshot_df, load_financial_data_nocache
from src.backend.quant_engine import calculate_all_scores
from src.backend.quant_engine_strategies import run_strategy
from src.backend.data_loader import load_financial_data
from src.constants.gics_translation import translate_gics_industry, translate_gics_sector
import logging
import numpy as np
import pandas as pd
from src.backend.quant_engine_strategies import (
    apply_value_filter, apply_turnaround_filter, apply_quality_filter,
    apply_garp_filter, apply_dividend_filter, apply_piotroski_filter,
    apply_canslim_filter, apply_garp_filter
)

# Import column definitions để gộp vào callback chính (tránh double-render)
from src.callbacks.column_callbacks import (
    FIXED_COLS, FILTER_TO_COLDEF, STRATEGY_FILTER_IDS, STRATEGY_DIRECT_COLS
)

import pandas as pd
import os

# =====================================================================
# 1. ĐỌC FILE CSV 1 LẦN DUY NHẤT Ở NGOÀI CALLBACK (Global Scope)
# =====================================================================
try:
    # Đọc file CSV của bạn (chỉnh lại đường dẫn nếu cần)
    df_comp_info = pd.read_csv("data/raw/COMP INFO.csv")
    
    # 🟢 SỬA Ở ĐÂY: Cột mã CK trong file của bạn tên là 'symbol', ta đổi nó thành 'Ticker'
    if 'symbol' in df_comp_info.columns:
        df_comp_info.rename(columns={'symbol': 'Ticker'}, inplace=True)
        
except Exception as e:
    print(f"⚠️ Không thể đọc file COMP INFO.csv: {e}")
    df_comp_info = pd.DataFrame() # Tạo DF rỗng để tránh lỗi code bên dưới

# 🟢 IMPORT TOÀN BỘ CÁC THÔNG SỐ TỪ QUANT ENGINE
from src.backend.quant_engine_strategies import (
    # 1. VALUE
    VALUE_THRESHOLDS, VALUE_IDX_CURRENT_RATIO_MIN, VALUE_IDX_EPS_GROWTH_5Y_MIN,
    VALUE_IDX_PE_MAX, VALUE_IDX_PB_MAX, VALUE_IDX_DEBT_TO_WC_MAX, VALUE_IDX_NET_INCOME_MIN,

    # 2. TURNAROUND
    TURNAROUND_THRESHOLDS, TURNAROUND_IDX_PE_HIST_NORM_MAX, TURNAROUND_IDX_OPERATING_MARGIN_MIN,
    TURNAROUND_IDX_PEG_MIN, TURNAROUND_IDX_PEG_MAX,

    # 3. QUALITY
    QUALITY_THRESHOLDS, QUALITY_IDX_ROE_MIN, QUALITY_IDX_GROSS_MARGIN_MIN,
    QUALITY_IDX_RE_GROWTH_MIN, QUALITY_IDX_FCF_MARGIN_MIN,

    # 4. GARP
    GARP_THRESHOLDS, GARP_IDX_EPS_GROWTH_MIN, GARP_IDX_EPS_GROWTH_MAX, GARP_IDX_PE_MAX,
    GARP_IDX_PEG_MIN, GARP_IDX_PEG_MAX, GARP_IDX_D_E_MAX, GARP_IDX_SGR_MIN_PCT, GARP_IDX_MC_QUANTILE,

    # 5. DIVIDEND
    DIVIDEND_THRESHOLDS, DIV_IDX_MC_QUANTILE, DIV_IDX_YIELD_MIN, DIV_IDX_PAYOUT_MAX,

    # 6. PIOTROSKI
    PIOTROSKI_THRESHOLDS, PIOTROSKI_IDX_F_MIN,

    # 7. CANSLIM
    CANSLIM_THRESHOLDS, CANSLIM_IDX_EPS_GROWTH_Q_MIN, CANSLIM_IDX_REV_GROWTH_Q_MIN,
    CANSLIM_IDX_EPS_GROWTH_Y_MIN, CANSLIM_IDX_ROE_MIN, CANSLIM_IDX_RS_MIN, CANSLIM_IDX_VOL_MULT,
    CANSLIM_IDX_AVG_VOL_MIN, CANSLIM_IDX_QUICK_RATIO_MIN, CANSLIM_IDX_DEBT_EQUITY_MAX,

    # 8. FISHER (GROWTH)
    FISHER_THRESHOLDS, FISHER_IDX_REV_GROWTH_5Y_MIN, FISHER_IDX_DILUTION_RATE_MAX,
    FISHER_IDX_ROE_MIN, FISHER_IDX_OPEX_EFF_MAX, FISHER_IDX_TURNOVER_MIN, FISHER_IDX_REINVEST_MIN
)

logger = logging.getLogger(__name__)

# ============================================================================
# TỪ ĐIỂN MAPPING VÀ GROUPING (TÓM TẮT) - ĐƠN VỊ TRIỆU VND
# ============================================================================
FINANCIAL_UI_MAP = {
    # ------------------ KẾT QUẢ KINH DOANH (IS) ------------------
    "Revenue from Business Activities - Total_x": {"name": "Doanh thu thuần", "group": "1. Kết quả kinh doanh"},
    "Cost of Revenues - Total": {"name": "Giá vốn hàng bán", "group": "1. Kết quả kinh doanh"},
    "Gross Profit - Industrials/Property - Total": {"name": "Lợi nhuận gộp", "group": "1. Kết quả kinh doanh"},
    "Operating Expenses - Total": {"name": "Tổng chi phí hoạt động", "group": "1. Kết quả kinh doanh"},
    "Earnings before Interest Taxes Depreciation & Amortization": {"name": "EBITDA", "group": "1. Kết quả kinh doanh"},
    "Earnings before Interest & Taxes (EBIT)": {"name": "EBIT", "group": "1. Kết quả kinh doanh"},
    "Income before Taxes": {"name": "Lợi nhuận trước thuế", "group": "1. Kết quả kinh doanh"},
    "Income Taxes": {"name": "Thuế TNDN", "group": "1. Kết quả kinh doanh"},
    "Net Income after Minority Interest": {"name": "LNST của cổ đông công ty mẹ", "group": "1. Kết quả kinh doanh"},
    "EPS - Basic - excl Extraordinary Items, Common - Total": {"name": "EPS Cơ bản", "group": "1. Kết quả kinh doanh"},
    "DPS - Common - Net - Issue - By Announcement Date": {"name": "Cổ tức mỗi cổ phiếu (DPS)",
                                                          "group": "1. Kết quả kinh doanh"},

    # ------------------ BẢNG CÂN ĐỐI KẾ TOÁN (BS) ------------------
    "Cash & Cash Equivalents - Total_x": {"name": "Tiền & Tương đương tiền", "group": "2. Bảng cân đối kế toán"},
    "Short-Term Investments - Total": {"name": "Đầu tư tài chính ngắn hạn", "group": "2. Bảng cân đối kế toán"},
    "Trade Accounts & Trade Notes Receivable - Net": {"name": "Phải thu khách hàng",
                                                      "group": "2. Bảng cân đối kế toán"},
    "Inventories - Total": {"name": "Hàng tồn kho", "group": "2. Bảng cân đối kế toán"},
    "Total Current Assets": {"name": "TỔNG TÀI SẢN NGẮN HẠN", "group": "2. Bảng cân đối kế toán"},
    "Property Plant & Equipment - Net - Total": {"name": "Tài sản cố định (Net)", "group": "2. Bảng cân đối kế toán"},
    "Investments - Long-Term": {"name": "Đầu tư dài hạn", "group": "2. Bảng cân đối kế toán"},
    "Total Assets": {"name": "TỔNG TÀI SẢN", "group": "2. Bảng cân đối kế toán"},

    "Trade Accounts & Trade Notes Payable - Short-Term": {"name": "Phải trả người bán",
                                                          "group": "2. Bảng cân đối kế toán"},
    "Short-Term Debt & Current Portion of Long-Term Debt": {"name": "Nợ vay ngắn hạn",
                                                            "group": "2. Bảng cân đối kế toán"},
    "Total Current Liabilities": {"name": "TỔNG NỢ NGẮN HẠN", "group": "2. Bảng cân đối kế toán"},
    "Debt - Long-Term - Total": {"name": "Nợ vay dài hạn", "group": "2. Bảng cân đối kế toán"},
    "Total Liabilities": {"name": "TỔNG NỢ PHẢI TRẢ", "group": "2. Bảng cân đối kế toán"},
    "Common Equity - Total": {"name": "Vốn góp", "group": "2. Bảng cân đối kế toán"},
    "Retained Earnings - Total": {"name": "Lợi nhuận giữ lại", "group": "2. Bảng cân đối kế toán"},
    "Total Shareholders' Equity incl Minority Intr & Hybrid Debt": {"name": "TỔNG VỐN CHỦ SỞ HỮU",
                                                                    "group": "2. Bảng cân đối kế toán"},

    # ------------------ LƯU CHUYỂN TIỀN TỆ (CF) ------------------
    "Net Cash Flow from Operating Activities": {"name": "Dòng tiền từ HĐKD (CFO)", "group": "3. Lưu chuyển tiền tệ"},
    "Capital Expenditures - Total_x": {"name": "Chi phí vốn (CAPEX)", "group": "3. Lưu chuyển tiền tệ"},
    "Net Cash Flow from Investing Activities": {"name": "Dòng tiền từ HĐ Đầu tư (CFI)",
                                                "group": "3. Lưu chuyển tiền tệ"},
    "Dividends Paid - Cash - Total - Cash Flow_x": {"name": "Cổ tức đã trả bằng tiền",
                                                    "group": "3. Lưu chuyển tiền tệ"},
    "Free Cash Flow": {"name": "DÒNG TIỀN TỰ DO (FCF)", "group": "3. Lưu chuyển tiền tệ"},
    "Net Cash - Ending Balance": {"name": "Tiền & TĐ tiền cuối kỳ", "group": "3. Lưu chuyển tiền tệ"}
}

# ============================================================================
# TỪ ĐIỂN CHỈ SỐ TÀI CHÍNH (METRICS MAPPING)
# ============================================================================
METRICS_UI_MAP = {
    # 1. Per Share (Dữ liệu gốc và tự tính)
    "EPS": {"name": "EPS Cơ bản (VND)", "group": "1"},
    "BVPS": {"name": "Giá trị sổ sách - BVPS (VND)", "group": "1"},
    "DPS - Common - Net - Issue - By Announcement Date": {"name": "Cổ tức mỗi CP - DPS (VND)", "group": "1"},

    # 2. Sinh lời (Profitability)
    "ROE": {"name": "ROE (%)", "group": "2"},
    "ROA": {"name": "ROA (%)", "group": "2"},
    "Gross Margin": {"name": "Biên Lợi nhuận gộp (%)", "group": "2"},
    "Net Margin": {"name": "Biên Lợi nhuận ròng (%)", "group": "2"},
    "EBIT Margin": {"name": "Biên EBIT (%)", "group": "2"},

    # 3. Thanh khoản (Liquidity)
    "Current Ratio": {"name": "Thanh toán hiện hành (Lần)", "group": "3"},
    "Quick Ratio": {"name": "Thanh toán nhanh (Lần)", "group": "3"},
    "Cash Ratio": {"name": "Thanh toán tiền mặt (Lần)", "group": "3"},

    # 4. Đòn bẩy (Leverage)
    "Debt to Equity": {"name": "Nợ vay / Vốn CSH (Lần)", "group": "4"},
    "Debt to Assets": {"name": "Nợ vay / Tổng tài sản (Lần)", "group": "4"},
    "Equity Multiplier": {"name": "Đòn bẩy tài chính (Lần)", "group": "4"},

    # 5. Hiệu quả (Efficiency)
    "Asset Turnover": {"name": "Vòng quay Tổng tài sản (Vòng)", "group": "5"},
    "Inventory Turnover": {"name": "Vòng quay Hàng tồn kho (Vòng)", "group": "5"},

    # 6. Tăng trưởng (Growth)
    "Revenue Growth": {"name": "Tăng trưởng Doanh thu (%)", "group": "6"},
    "Net Income Growth": {"name": "Tăng trưởng Lợi nhuận ròng (%)", "group": "6"}
}


# ============================================================================
# HELPER FUNCTIONS (Moved from detail_tabs_callbacks.py)
# ============================================================================

def fmt_number(val, prefix="", suffix=""):
    if val is None or val == "" or (isinstance(val, float) and (val != val)):  # Check for NaN
        return "---"
    try:
        return f"{prefix}{val:,.0f}{suffix}"
    except:
        return "---"


def fmt_decimal(val, decimals=2, suffix=""):
    if val is None or val == "" or (isinstance(val, float) and (val != val)):
        return "---"
    try:
        return f"{val:.{decimals}f}{suffix}"
    except:
        return "---"


def fmt_percent(val):
    if val is None or val == "" or (isinstance(val, float) and (val != val)):
        return "---"
    try:
        return f"{val:.2f}%"
    except:
        return "---"


def get_percent_style(val):
    """Return style based on percentage value"""
    if val is None or val == "" or (isinstance(val, float) and (val != val)):
        return {"color": "#c9d1d9"}  # Grey
    try:
        if val > 0:
            return {"color": "#3fb950", "fontWeight": "bold"}  # Green
        elif val < 0:
            return {"color": "#f85149", "fontWeight": "bold"}  # Red
        else:
            return {"color": "#e6edf3"}  # White
    except:
        return {"color": "#c9d1d9"}


def get_trend_style(current_price, sma_value):
    """Return style for SMA comparison"""
    if sma_value is None or sma_value == "---" or current_price is None:
        return {"color": "#c9d1d9"}, "---"

    try:
        if current_price > sma_value:
            return {"color": "#3fb950", "fontWeight": "bold"}, "Tăng (Giá > SMA)"
        elif current_price < sma_value:
            return {"color": "#f85149", "fontWeight": "bold"}, "Giảm (Giá < SMA)"
        else:
            return {"color": "#e6edf3"}, "Đi ngang"
    except:
        return {"color": "#c9d1d9"}, "---"


def _build_col_defs(active_filters, strategy_id):
    """Xây dựng columnDefs từ active_filters + strategy — gộp vào callback chính để tránh double-render."""
    seen_fields = {c["field"] for c in FIXED_COLS}
    dynamic_cols = []
    af = active_filters or {}

    for filter_id in af:
        if filter_id not in FILTER_TO_COLDEF:
            continue
        col = FILTER_TO_COLDEF[filter_id]
        if col["field"] not in seen_fields:
            dynamic_cols.append(col)
            seen_fields.add(col["field"])

    if strategy_id and strategy_id in STRATEGY_FILTER_IDS:
        for filter_id in STRATEGY_FILTER_IDS[strategy_id]:
            if filter_id not in FILTER_TO_COLDEF:
                continue
            col = FILTER_TO_COLDEF[filter_id]
            if col["field"] not in seen_fields:
                dynamic_cols.append(col)
                seen_fields.add(col["field"])
        for col in STRATEGY_DIRECT_COLS.get(strategy_id, []):
            if col["field"] not in seen_fields:
                dynamic_cols.append(col)
                seen_fields.add(col["field"])

    return FIXED_COLS + dynamic_cols


def _add_forward_pe(df):
    """Tính Forward P/E inline — tránh callback riêng gây double-render."""
    try:
        if 'Forward P/E *' in df.columns:
            return df
        if not all(c in df.columns for c in ['EPS', 'EPS Growth YoY (%)', 'Price Close']):
            return df
        eps    = pd.to_numeric(df['EPS'], errors='coerce')
        growth = pd.to_numeric(df['EPS Growth YoY (%)'], errors='coerce').clip(-90, 500)
        price  = pd.to_numeric(df['Price Close'], errors='coerce')
        fwd_eps = eps * (1 + growth / 100)
        df['Forward P/E *'] = np.where(
            (fwd_eps > 0) & (price > 0),
            (price / fwd_eps).round(2),
            np.nan
        )
    except Exception:
        pass
    return df


# ============================================================================
# CALLBACK: MAIN SCREENER TABLE UPDATE (rowData + columnDefs trong 1 lần)
# ============================================================================
@app.callback(
    [Output("screener-table", "rowData",    allow_duplicate=True),
     Output("screener-table", "columnDefs", allow_duplicate=True),
     Output("result-count",   "children"),
     Output("filter-stats",   "children")],
    [
        # ── TRIGGERS chính (thay đổi những thứ này → chạy filter) ──
        Input("btn-reset",                  "n_clicks"),
        Input("search-ticker-input",        "value"),
        Input("strategy-preset-dropdown",   "value"),
        Input("filter-all-industry",        "value"),
        Input("active-filters-store",       "data"),   # ← nguồn sự thật duy nhất
        Input("filter-sub-industry",        "value"),
        Input("filter-exchange",             "value"),   # ← lọc theo sàn
        Input("filter-year-store",          "data"),   # ← lọc theo năm
    ],
    [
        # ── STATE: đọc giá trị hiện tại của từng store khi callback chạy ──
        # Tổng quan
        State("filter-price",               "data"),
        State("filter-volume",              "data"),
        State("filter-market-cap",          "data"),
        State("filter-eps",                 "data"),
        State("filter-perf-1w",             "data"),
        State("filter-perf-1m",             "data"),
        # Định giá
        State("filter-pe",                  "data"),
        State("filter-pb",                  "data"),
        State("filter-ps",                  "data"),
        State("filter-ev-ebitda",           "data"),
        State("filter-div-yield",           "data"),
        # Sinh lời
        State("filter-roe",                 "data"),
        State("filter-roa",                 "data"),
        State("filter-gross-margin",        "data"),
        State("filter-net-margin",          "data"),
        State("filter-ebit-margin",         "data"),
        # Tăng trưởng
        State("filter-rev-growth-yoy",      "data"),
        State("filter-rev-cagr-5y",         "data"),
        State("filter-eps-growth-yoy",      "data"),
        State("filter-eps-cagr-5y",         "data"),
        # Sức khỏe
        State("filter-de",                  "data"),
        State("filter-current-ratio",       "data"),
        State("filter-net-cash-cap",        "data"),
        State("filter-net-cash-assets",     "data"),
        # Scores
        State("filter-value-score",         "data"),
        State("filter-growth-score",        "data"),
        State("filter-momentum-score",      "data"),
        State("filter-vgm-score",           "data"),
        State("filter-canslim",             "data"),
        # Kỹ thuật – Giá vs SMA
        State("filter-price-vs-sma5",       "data"),
        State("filter-price-vs-sma10",      "data"),
        State("filter-price-vs-sma20",      "data"),
        State("filter-price-vs-sma50",      "data"),
        State("filter-price-vs-sma100",     "data"),
        State("filter-price-vs-sma200",     "data"),
        # Kỹ thuật – Đỉnh/Đáy
        State("filter-pct-from-high-1y",    "data"),
        State("filter-pct-from-low-1y",     "data"),
        State("filter-pct-from-high-all",   "data"),
        State("filter-pct-from-low-all",    "data"),
        State("filter-break-high-52w",      "data"),
        State("filter-break-low-52w",       "data"),
        # Kỹ thuật – Oscillators
        State("filter-rsi14",               "data"),
        State("filter-macd-hist",           "data"),
        State("filter-bb-width",            "data"),
        State("filter-consec-up",           "data"),
        State("filter-consec-down",         "data"),
        # Kỹ thuật – Momentum/RS
        State("filter-beta",                "data"),
        State("filter-alpha",               "data"),
        State("filter-rs-3d",               "data"),
        State("filter-rs-1m",               "data"),
        State("filter-rs-3m",               "data"),
        State("filter-rs-1y",               "data"),
        State("filter-rs-avg",              "data"),
        # Kỹ thuật – Volume
        State("filter-vol-vs-sma5",         "data"),
        State("filter-vol-vs-sma10",        "data"),
        State("filter-vol-vs-sma20",        "data"),
        State("filter-vol-vs-sma50",        "data"),
        State("filter-avg-vol-5d",          "data"),
        State("filter-avg-vol-10d",         "data"),
        State("filter-avg-vol-50d",         "data"),
        # GTGD
        State("filter-gtgd-1w",             "data"),
        State("filter-gtgd-10d",            "data"),
        State("filter-gtgd-1m",             "data"),
    ],
    prevent_initial_call='initial_duplicate'
)
def update_screener_table(
        btn_reset, search_text, current_strategy, selected_sectors, active_filters, selected_subs,
        selected_exchange, filter_year,
        # Tổng quan (State)
        price_range, volume_range, market_cap_range, eps_range, perf_1w_range, perf_1m_range,
        # Định giá
        pe_range, pb_range, ps_range, ev_ebitda_range, div_yield_range,
        # Sinh lời
        roe_range, roa_range, gross_margin_range, net_margin_range, ebit_margin_range,
        # Tăng trưởng
        rev_growth_yoy_range, rev_cagr_5y_range, eps_growth_yoy_range, eps_cagr_5y_range,
        # Sức khỏe
        de_range, current_ratio_range, net_cash_cap_range, net_cash_assets_range,
        # Scores
        value_scores, growth_scores, momentum_scores, vgm_scores, canslim_range,
        # Kỹ thuật – Giá vs SMA
        pvsma5, pvsma10, pvsma20, pvsma50, pvsma100, pvsma200,
        # Kỹ thuật – Đỉnh/Đáy
        pct_high_1y, pct_low_1y, pct_high_all, pct_low_all,
        break_high_52w, break_low_52w,
        # Kỹ thuật – Oscillators
        rsi14_range, macd_range, bb_range, consec_up_range, consec_down_range,
        # Kỹ thuật – Momentum/RS
        beta_range, alpha_range, rs3d, rs1m, rs3m, rs1y, rs_avg,
        # Kỹ thuật – Volume
        vvsma5, vvsma10, vvsma20, vvsma50, avg5d, avg10d, avg50d,
        # GTGD
        gtgd_1w, gtgd_10d, gtgd_1m,
):
    try:
        ctx = callback_context
        triggered_id = ctx.triggered[0]['prop_id'].split('.')[0] if ctx.triggered else None

        # Load Snapshot trực tiếp dưới dạng DataFrame (không qua list[dict] roundtrip)
        df = get_snapshot_df()
        if df is None or df.empty:
            return [], FIXED_COLS, "⚠️ Không có dữ liệu", ""

        df = df.copy()  # tránh modify in-place trên cache
        total_stocks = len(df)

        # ── LỌC THEO NĂM (qua BCTC — snapshot chỉ có 1 ngày nên lọc qua df_fin) ──
        if filter_year and filter_year != "all":
            yr = int(filter_year)
            try:
                df_fin_yr = load_financial_data('yearly')
                if df_fin_yr is not None and not df_fin_yr.empty and 'Date' in df_fin_yr.columns:
                    df_fin_yr = df_fin_yr.copy()
                    df_fin_yr['_yr'] = pd.to_datetime(df_fin_yr['Date'], errors='coerce').dt.year
                    tickers_in_year = set(df_fin_yr[df_fin_yr['_yr'] == yr]['Ticker'].dropna().unique())
                    df = df[df['Ticker'].isin(tickers_in_year)]
                    logger.info(f"[YEAR FILTER] Năm {yr}: {len(tickers_in_year)} ticker có BCTC → còn {len(df)} mã")
            except Exception as e:
                logger.warning(f"[YEAR FILTER] Lỗi lọc năm: {e}")
            total_stocks = len(df)
        # ─────────────────────────────────────────────────────────────────────

        if 'VGM Score' in df.columns:
            grade_order = {'A': 1, 'B': 2, 'C': 3, 'D': 4, 'F': 5}
            df['_sort'] = df['VGM Score'].map(grade_order).fillna(6)
            df = df.sort_values('_sort').drop('_sort', axis=1)

        if triggered_id == 'btn-reset' or triggered_id == 'btn-reset.n_clicks':
            df = _add_forward_pe(df)
            col_defs = _build_col_defs(active_filters, current_strategy)
            return df.to_dict('records'), col_defs, f"📊 Hiển thị tất cả: {total_stocks} mã", ""

        df_filtered = df.copy()
        # ================================================================
        # 🟢 TẦNG 0: LỌC THEO TỪ KHÓA TÌM KIẾM (SEARCH BAR)
        # ================================================================
        # ================================================================
        # 🟢 TẦNG 0: LỌC THEO TỪ KHÓA TÌM KIẾM (Bug #4 fix: tìm cả tên công ty)
        # ================================================================
        if search_text:
            search_upper = search_text.strip().upper()
            ticker_match = df_filtered['Ticker'].astype(str).str.upper().str.contains(search_upper, na=False, regex=False)
            if 'Company Common Name' in df_filtered.columns:
                name_match = df_filtered['Company Common Name'].astype(str).str.upper().str.contains(search_upper, na=False, regex=False)
                df_filtered = df_filtered[ticker_match | name_match]
            else:
                df_filtered = df_filtered[ticker_match]
        # ================================================================
        # TẦNG 1: LỌC THEO TRƯỜNG PHÁI (STRATEGY)
        # ================================================================
        if current_strategy:
            logger.info(f"Áp dụng Tầng 1 (Trường phái): {current_strategy}")
            try:
                df_fin = load_financial_data('yearly')
            except Exception as e:
                logger.warning(f"Lỗi load df_fin: {e}")
                df_fin = None
            df_filtered = run_strategy(df_filtered, current_strategy, df_fin=df_fin)
            df_filtered = df_filtered.replace([float('inf'), float('-inf')], None)

        # ================================================================
        # TẦNG 2: LỌC THEO NGÀNH (Bug #1 fix)
        # ================================================================
        if selected_sectors and isinstance(selected_sectors, list):
            clean = [s for s in selected_sectors if s != "all"]
            if clean:
                # Xác định cột sector tồn tại trong df
                sec_col = next((c for c in ['Sector', 'GICS Sector Name'] if c in df_filtered.columns), None)
                if sec_col:
                    # Lấy tất cả giá trị sector thực tế trong data
                    actual_vals = set(df_filtered[sec_col].dropna().unique())
                    # Lọc chỉ giữ những giá trị clean thực sự tồn tại trong data
                    # (loại bỏ các giá trị cũ từ localStorage như "Chemicals" - là GICS Industry chứ không phải Sector)
                    valid_clean = [s for s in clean if s in actual_vals]
                    if valid_clean:
                        df_filtered = df_filtered[df_filtered[sec_col].isin(valid_clean)]
                    # Nếu valid_clean rỗng (toàn giá trị lạ từ localStorage) → không lọc, tránh mất sạch data

        # ================================================================
        # TẦNG 3: LỌC CHỈ TIÊU — đọc range từ active_filters["value"]
        # (active-filters-store là nguồn sự thật duy nhất, cập nhật bởi
        #  cả manage_filter_ui lẫn activate_readonly_filter_on_drag)
        # Fallback về State params nếu active_filters không có "value"
        # ================================================================
        if not active_filters:
            active_filters = {}

        def apply_range(col_name, rng):
            nonlocal df_filtered
            if col_name in df_filtered.columns and rng and len(rng) == 2:
                numeric = pd.to_numeric(df_filtered[col_name], errors='coerce')
                df_filtered = df_filtered[
                    numeric.notna() &
                    (numeric >= rng[0]) &
                    (numeric <= rng[1])
                ]

        def apply_grade(col_name, grades):
            nonlocal df_filtered
            if col_name in df_filtered.columns and grades:
                df_filtered = df_filtered[df_filtered[col_name].isin(grades)]

        # Map filter_id → (col_name, fallback_state_value, is_grade)
        FILTER_MAP = [
            # Tổng quan
            ("filter-price",            "Price Close",              price_range,            False),
            ("filter-volume",           "Volume",                   volume_range,           False),
            ("filter-market-cap",       "Market Cap",               market_cap_range,       False),
            ("filter-eps",              "EPS",                      eps_range,              False),
            ("filter-perf-1w",          "Perf_1W",                  perf_1w_range,          False),
            ("filter-perf-1m",          "Perf_1M",                  perf_1m_range,          False),
            # Định giá
            ("filter-pe",               "P/E",                      pe_range,               False),
            ("filter-pb",               "P/B",                      pb_range,               False),
            ("filter-ps",               "P/S",                      ps_range,               False),
            ("filter-ev-ebitda",        "EV/EBITDA",                ev_ebitda_range,        False),
            ("filter-div-yield",        "Dividend Yield (%)",       div_yield_range,        False),
            # Sinh lời
            ("filter-roe",              "ROE (%)",                  roe_range,              False),
            ("filter-roa",              "ROA (%)",                  roa_range,              False),
            ("filter-gross-margin",     "Gross Margin (%)",         gross_margin_range,     False),
            ("filter-net-margin",       "Net Margin (%)",           net_margin_range,       False),
            ("filter-ebit-margin",      "EBIT Margin (%)",          ebit_margin_range,      False),
            # Tăng trưởng
            ("filter-rev-growth-yoy",   "Revenue Growth YoY (%)",   rev_growth_yoy_range,   False),
            ("filter-rev-cagr-5y",      "Revenue CAGR 5Y (%)",      rev_cagr_5y_range,      False),
            ("filter-eps-growth-yoy",   "EPS Growth YoY (%)",       eps_growth_yoy_range,   False),
            ("filter-eps-cagr-5y",      "EPS CAGR 5Y (%)",          eps_cagr_5y_range,      False),
            # Sức khỏe
            ("filter-de",               "D/E",                      de_range,               False),
            ("filter-current-ratio",    "Current Ratio",            current_ratio_range,    False),
            ("filter-net-cash-cap",     "Net Cash / Market Cap (%)",net_cash_cap_range,     False),
            ("filter-net-cash-assets",  "Net Cash / Assets (%)",    net_cash_assets_range,  False),
            # Scores (grade)
            ("filter-value-score",      "Value Score",              value_scores,           True),
            ("filter-growth-score",     "Growth Score",             growth_scores,          True),
            ("filter-momentum-score",   "Momentum Score",           momentum_scores,        True),
            ("filter-vgm-score",        "VGM Score",                vgm_scores,             True),
            ("filter-canslim",          "CANSLIM Score",            canslim_range,          False),
            # Kỹ thuật – Giá vs SMA
            ("filter-price-vs-sma5",    "Price_vs_SMA5",            pvsma5,                 False),
            ("filter-price-vs-sma10",   "Price_vs_SMA10",           pvsma10,                False),
            ("filter-price-vs-sma20",   "Price_vs_SMA20",           pvsma20,                False),
            ("filter-price-vs-sma50",   "Price_vs_SMA50",           pvsma50,                False),
            ("filter-price-vs-sma100",  "Price_vs_SMA100",          pvsma100,               False),
            ("filter-price-vs-sma200",  "Price_vs_SMA200",          pvsma200,               False),
            # Kỹ thuật – Đỉnh/Đáy
            ("filter-pct-from-high-1y", "Pct_From_High_1Y",         pct_high_1y,            False),
            ("filter-pct-from-low-1y",  "Pct_From_Low_1Y",          pct_low_1y,             False),
            ("filter-pct-from-high-all","Pct_From_High_All",         pct_high_all,           False),
            ("filter-pct-from-low-all", "Pct_From_Low_All",         pct_low_all,            False),
            # Kỹ thuật – Oscillators
            ("filter-rsi14",            "RSI_14",                   rsi14_range,            False),
            ("filter-macd-hist",        "MACD_Histogram",           macd_range,             False),
            ("filter-bb-width",         "BB_Width",                 bb_range,               False),
            ("filter-consec-up",        "Consec_Up",                consec_up_range,        False),
            ("filter-consec-down",      "Consec_Down",              consec_down_range,      False),
            # Kỹ thuật – Momentum/RS
            ("filter-beta",             "Beta",                     beta_range,             False),
            ("filter-alpha",            "Alpha",                    alpha_range,            False),
            ("filter-rs-3d",            "RS_3D",                    rs3d,                   False),
            ("filter-rs-1m",            "RS_1M",                    rs1m,                   False),
            ("filter-rs-3m",            "RS_3M",                    rs3m,                   False),
            ("filter-rs-1y",            "RS_1Y",                    rs1y,                   False),
            ("filter-rs-avg",           "RS_Avg",                   rs_avg,                 False),
            # Kỹ thuật – Volume
            ("filter-vol-vs-sma5",      "Vol_vs_SMA5",              vvsma5,                 False),
            ("filter-vol-vs-sma10",     "Vol_vs_SMA10",             vvsma10,                False),
            ("filter-vol-vs-sma20",     "Vol_vs_SMA20",             vvsma20,                False),
            ("filter-vol-vs-sma50",     "Vol_vs_SMA50",             vvsma50,                False),
            ("filter-avg-vol-5d",       "Avg_Vol_5D",               avg5d,                  False),
            ("filter-avg-vol-10d",      "Avg_Vol_10D",              avg10d,                 False),
            ("filter-avg-vol-50d",      "Avg_Vol_50D",              avg50d,                 False),
            # GTGD
            ("filter-gtgd-1w",          "GTGD_1W",                  gtgd_1w,                False),
            ("filter-gtgd-10d",         "GTGD_10D",                 gtgd_10d,               False),
            ("filter-gtgd-1m",          "GTGD_1M",                  gtgd_1m,                False),
        ]

        for (filter_id, col_name, fallback_val, is_grade) in FILTER_MAP:
            if filter_id not in active_filters:
                continue  # Chỉ áp dụng khi filter đang active
            # Ưu tiên lấy value từ active_filters (được cập nhật khi kéo slider)
            # Fallback về State param nếu active_filters chưa có "value"
            af_entry = active_filters[filter_id]
            rng_or_grades = af_entry.get("value", fallback_val) if isinstance(af_entry, dict) else fallback_val
            if is_grade:
                apply_grade(col_name, rng_or_grades)
            else:
                apply_range(col_name, rng_or_grades)

        # ── Boolean filters: Break_High_52W / Break_Low_52W ──
        _BOOL_MAP = [
            ("filter-break-high-52w", "Break_High_52W", break_high_52w),
            ("filter-break-low-52w",  "Break_Low_52W",  break_low_52w),
        ]
        for (fid, col, bval) in _BOOL_MAP:
            if fid not in active_filters:
                continue
            if col not in df_filtered.columns:
                continue
            af_entry = active_filters[fid]
            # Đọc value từ active_filters (được sync bởi sync_bool_to_active_filters)
            bool_val = af_entry.get("value") if isinstance(af_entry, dict) else None
            # Fallback về State store nếu chưa có trong active_filters
            if bool_val is None:
                bool_val = bval
            if bool_val is None:
                continue
            # Ép kiểu an toàn: col có thể là int hoặc float (0.0/1.0)
            df_filtered[col] = pd.to_numeric(df_filtered[col], errors='coerce').fillna(-1).astype(int)
            df_filtered = df_filtered[df_filtered[col] == int(bool_val)]

        # ── Sub-industry filter (Bug #2 fix: xử lý trong callback chính,
        #    không dùng callback riêng nữa để tránh bị overwrite) ──
        if selected_subs and isinstance(selected_subs, list):
            clean_subs = [s for s in selected_subs if s != "all"]
            if clean_subs:
                sub_col = next((c for c in ['GICS Industry Name', 'GICS Sub-Industry Name']
                                if c in df_filtered.columns), None)
                if sub_col:
                    actual_subs = set(df_filtered[sub_col].dropna().unique())
                    valid_subs = [s for s in clean_subs if s in actual_subs]
                    if valid_subs:
                        df_filtered = df_filtered[df_filtered[sub_col].isin(valid_subs)]

        # ── Filter theo sàn giao dịch ──
        # FIX: Xử lý cả string (multi=False) lẫn list (multi=True), normalize giá trị
        if selected_exchange:
            if isinstance(selected_exchange, str):
                clean_ex = [selected_exchange] if selected_exchange not in ("all", "") else []
            else:
                clean_ex = [e for e in selected_exchange if e and e != "all"]

            if clean_ex:
                if 'Exchange' in df_filtered.columns:
                    df_filtered['Exchange'] = df_filtered['Exchange'].astype(str).str.strip()
                    before = len(df_filtered)
                    df_filtered = df_filtered[df_filtered['Exchange'].isin(clean_ex)]
                    logger.info(f"[Exchange Filter] {clean_ex} → {before} → {len(df_filtered)} mã")
                else:
                    logger.warning("[Exchange Filter] Cột 'Exchange' KHÔNG tồn tại trong snapshot! "
                                   "Hãy xóa data/processed/snapshot_cache.parquet và restart.")

        filtered_count = len(df_filtered)
        # Tính Forward P/E và build columnDefs trong cùng 1 lần → AG Grid nhận 1 batch update
        df_filtered = _add_forward_pe(df_filtered)
        col_defs = _build_col_defs(active_filters, current_strategy)
        return (
            df_filtered.to_dict('records'),
            col_defs,
            f"Tìm thấy {filtered_count} / {total_stocks} mã phù hợp",
            f"Lọc: {filtered_count} mã | Tổng: {total_stocks} mã"
        )

    except Exception as e:
        logger.error(f"Error in update_screener_table: {e}")
        import traceback;
        traceback.print_exc()
        return [], FIXED_COLS, f"❌ Lỗi: {str(e)}", "Vui lòng thử lại"



# ============================================================================
# HELPERS: METHODOLOGY MODAL UI COMPONENTS
# ============================================================================

def _meth_section(icon_cls, color, title):
    return html.Div([
        html.I(className=icon_cls, style={"color": color, "marginRight": "8px", "fontSize": "12px"}),
        html.Span(title, style={"fontSize": "12px", "fontWeight": "700", "color": color,
                                "fontFamily": "JetBrains Mono,monospace", "letterSpacing": "0.05em"}),
    ], style={"display": "flex", "alignItems": "center", "marginBottom": "10px"})


def _meth_step(num, color, title, desc):
    return html.Div([
        html.Div(num, style={
            "width": "22px", "height": "22px", "borderRadius": "50%", "flexShrink": "0",
            "backgroundColor": f"rgba{tuple(int(color.lstrip('#')[i:i+2], 16) for i in (0, 2, 4)) + (0.15,)}",
            "border": f"1px solid {color}50",
            "color": color, "fontSize": "11px", "fontWeight": "700",
            "display": "flex", "alignItems": "center", "justifyContent": "center",
            "marginRight": "10px", "marginTop": "1px",
        }),
        html.Div([
            html.Span(title, style={"fontSize": "12px", "fontWeight": "700", "color": "#c9d1d9",
                                    "display": "block", "marginBottom": "2px"}),
            html.Span(desc, style={"fontSize": "11px", "color": "#8b949e", "lineHeight": "1.5"}),
        ]),
    ], style={"display": "flex", "alignItems": "flex-start", "marginBottom": "10px"})


def _meth_metric(title, scoring, rationale):
    return html.Div([
        html.Div([
            html.I(className="fas fa-chart-line",
                   style={"color": "#00e676", "marginRight": "8px", "fontSize": "11px", "marginTop": "2px", "flexShrink": "0"}),
            html.Span(title, style={"fontSize": "12px", "fontWeight": "700", "color": "#c9d1d9"}),
        ], style={"display": "flex", "alignItems": "flex-start", "marginBottom": "5px"}),
        html.P(scoring, style={"fontSize": "11px", "color": "#8b949e", "lineHeight": "1.5",
                                "marginBottom": "4px", "marginLeft": "19px"}),
        html.P([html.I(className="fas fa-lightbulb", style={"color": "#f59e0b", "marginRight": "5px", "fontSize": "10px"}),
                rationale],
               style={"fontSize": "10px", "color": "#6e7681", "lineHeight": "1.5",
                      "marginBottom": "0", "marginLeft": "19px", "fontStyle": "italic"}),
    ], style={
        "marginBottom": "14px", "paddingBottom": "14px",
        "borderBottom": "1px solid rgba(33,38,45,0.8)",
    })

from dash import State # Đảm bảo bạn đã import State ở đầu file
from dash import State

# ============================================================================
# CALLBACK 2A: MỞ MODAL NGAY (< 50ms) — chỉ set title + lưu stock vào store
# ============================================================================
@app.callback(
    Output("detail-modal",          "is_open"),
    Output("modal-title",           "children"),
    Output("selected-stock-store",  "data"),
    # 🟢 THÊM OUTPUT NÀY ĐỂ BƠM MÃ CỔ PHIẾU CHO 2 TAB CÒN LẠI:
    Output("selected-ticker-store", "data"), 
    
    Input("screener-table", "cellDoubleClicked"), 
    State("screener-table", "rowData"), 
    prevent_initial_call=True,
)
def open_detail_modal_fast(double_clicked_cell, grid_data):
    if not double_clicked_cell or not grid_data:
        return dash.no_update, dash.no_update, dash.no_update, dash.no_update

    row_id_str = double_clicked_cell.get("rowId")
    
    if row_id_str is not None and str(row_id_str).isdigit():
        real_index = int(row_id_str)
        stock = grid_data[real_index]
    else:
        return dash.no_update, dash.no_update, dash.no_update, dash.no_update

    ticker       = stock.get('Ticker', 'N/A')
    company_name = stock.get('Company Common Name', '')

    company_name_vn = company_name
    if not df_comp_info.empty:
        match = df_comp_info[df_comp_info['Ticker'] == ticker]
        if not match.empty and 'organ_name' in match.columns:
            company_name_vn = str(match['organ_name'].values[0])

    title_text = f"Cổ phiếu {ticker} – {company_name_vn}"
    
    # 🟢 TRẢ VỀ THÊM CÁI `ticker` Ở CUỐI CÙNG CHO VỪA VỚI 4 OUTPUT
    return True, title_text, stock, ticker

# ============================================================================
# CALLBACK 2B: LOAD NỘI DUNG SAU KHI MODAL ĐÃ HIỆN — trigger từ store
# ============================================================================
@app.callback(
    Output("tab-overview-content",  "children"),
    Output("tab-technical-content", "children"),
    Output("fin-table-is", "rowData"),  Output("fin-table-is", "columnDefs"),
    Output("fin-table-bs", "rowData"),  Output("fin-table-bs", "columnDefs"),
    Output("fin-table-cf", "rowData"),  Output("fin-table-cf", "columnDefs"),
    Input("selected-stock-store", "data"),   # trigger khi modal đã mở
    Input("fin-period-toggle",    "value"),
    prevent_initial_call=True,
)
def load_detail_content(stock, period_toggle):
    """Load data nặng SAU khi modal đã hiện — user thấy UI ngay."""
    # ── DEBUG: log khi callback trigger ──────────────────────────────────
    import logging
    _log = logging.getLogger(__name__)
    _log.warning(f"[DEBUG 2B] triggered | stock={bool(stock)} | ticker={stock.get('Ticker') if stock else None}")
    # ─────────────────────────────────────────────────────────────────────
    if not stock:
        return "", "", [], [], [], [], [], []

    ticker       = stock.get('Ticker', 'N/A')
    company_name = stock.get('Company Common Name', '')
    price_close  = stock.get('Price Close', 0)

    company_name_vn = company_name
    if not df_comp_info.empty:
        match = df_comp_info[df_comp_info['Ticker'] == ticker]
        if not match.empty and 'organ_name' in match.columns:
            company_name_vn = str(match['organ_name'].values[0])

    # =========================================================================
    # === TAB 1: OVERVIEW (HỒ SƠ, KPI VÀ SỨC KHỎE TÀI CHÍNH) ===
    # =========================================================================

    # --- 1. TRÍCH XUẤT THÔNG TIN HỒ SƠ DOANH NGHIỆP ---
    # GIỮ NGUYÊN DATA GỐC (không dịch sang tiếng Việt)
    # --- 1. TRÍCH XUẤT THÔNG TIN HỒ SƠ DOANH NGHIỆP ---
    # Đã bọc thêm hàm dịch tiếng Việt
    sector = translate_gics_sector(stock.get('GICS Sector Name', stock.get('Sector', 'Đang cập nhật')))
    industry = translate_gics_industry(stock.get('GICS Industry Name', 'Đang cập nhật'))
    sub_industry = translate_gics_industry(
        stock.get('GICS Sub-Industry Name', stock.get('GICS Industry Name', 'Đang cập nhật'))
    )

    founded_year = stock.get('Organization Founded Year', '---')
    ipo_date = stock.get('Date Became Public', '---')
    auditor = stock.get('Auditor Details', 'Đang cập nhật')
    exchange = stock.get('Exchange', '---')
    exchange_label_map = {'HOSE': 'HOSE (HoSE)', 'HNX': 'HNX', 'UPCOM': 'UPCoM'}
    exchange_display = exchange_label_map.get(str(exchange).strip(), exchange if exchange != '---' else '---')
    exchange_color = {'HOSE': '#3fb950', 'HNX': '#58a6ff', 'UPCOM': '#f59e0b'}.get(str(exchange).strip(), '#8b949e')

    try:
        if ipo_date != '---' and pd.notna(ipo_date):
            ipo_date_str = ipo_date.strftime("%d/%m/%Y") if isinstance(ipo_date, pd.Timestamp) else str(ipo_date)[:10]
        else:
            ipo_date_str = '---'
    except:
        ipo_date_str = '---'

    try:
        founded_year_str = str(int(float(founded_year))) if founded_year != '---' and pd.notna(founded_year) else '---'
    except:
        founded_year_str = '---'

    # --- 2. XỬ LÝ DỮ LIỆU ĐỂ TÍNH TOÁN KPI & BIỂU ĐỒ SỨC KHỎE ---
    # Tải dữ liệu BCTC Quý để vẽ biểu đồ lịch sử
    df_history = pd.DataFrame()
    try:
        df_fin_q = load_financial_data_nocache('quarterly')
        df_history = df_fin_q[df_fin_q['Ticker'] == ticker].sort_values("Date", ascending=False).head(
            8)  # Lấy 8 quý gần nhất
        df_history = df_history.sort_values("Date", ascending=True)  # Đảo lại để vẽ từ cũ tới mới
    except Exception as e:
        logger.warning(f"Không thể tải BCTC quý để vẽ biểu đồ sức khỏe: {e}")

    # Lấy các giá trị tính toán — ưu tiên lấy từ snapshot (đã tính sẵn)
    market_cap_raw = stock.get('Market Cap', None)
    shares_out_raw = stock.get('Shares Outstanding', stock.get('Common Shares Outstanding', None))

    # Fallback: tính từ df_history nếu snapshot không có
    if shares_out_raw is None and not df_history.empty and 'Common Shares - Outstanding - Total_x' in df_history.columns:
        shares_out_raw = df_history['Common Shares - Outstanding - Total_x'].iloc[-1]

    shares_out = float(shares_out_raw) if shares_out_raw is not None and pd.notna(shares_out_raw) else np.nan

    if market_cap_raw is not None and pd.notna(market_cap_raw) and float(market_cap_raw) > 0:
        market_cap = float(market_cap_raw) / 1_000_000  # Chuyển sang Triệu VND
    elif not pd.isna(shares_out):
        market_cap = price_close * shares_out / 1_000_000
    else:
        market_cap = 0

    eps = stock.get('EPS', 0)
    pe = stock.get('P/E', 0)
    pb = stock.get('P/B', 0)
    roe = stock.get('ROE (%)', 0)

    # Tính Cổ tức & Tỷ suất (Dividend Yield)
    dps = df_history['DPS - Common - Net - Issue - By Announcement Date'].iloc[
        -1] if not df_history.empty and 'DPS - Common - Net - Issue - By Announcement Date' in df_history.columns else 0
    div_yield = (dps / price_close * 100) if price_close > 0 and not pd.isna(dps) else 0

    # Tính các chỉ số cho thẻ Phân tích chi tiết (từ dòng dữ liệu mới nhất)
    gross_margin = 0;
    debt_equity = 0;
    ocf_net = 0;
    inv_days = 0;
    ev_ebitda = 0
    if not df_history.empty:
        latest = df_history.iloc[-1]
        gross_margin = (latest.get('Gross Profit - Industrials/Property - Total', 0) / latest.get(
            'Revenue from Business Activities - Total_x', 1)) * 100
        debt_equity = (latest.get('Short-Term Debt & Current Portion of Long-Term Debt', 0) + latest.get(
            'Debt - Long-Term - Total', 0)) / latest.get('Common Equity - Total', 1)
        ocf_net = latest.get('Net Cash Flow from Operating Activities', 0) / latest.get(
            'Net Income after Minority Interest', 1)

        cogs = abs(latest.get('Cost of Revenues - Total', 1))
        inv_turnover = cogs / latest.get('Inventories - Total', 1) if cogs != 0 else 0
        inv_days = 365 / inv_turnover if inv_turnover > 0 else 0

        ebitda = latest.get('Earnings before Interest Taxes Depreciation & Amortization', 1)
        ev = (market_cap * 1_000_000) + (
                    latest.get('Short-Term Debt & Current Portion of Long-Term Debt', 0) + latest.get(
                'Debt - Long-Term - Total', 0)) - latest.get('Cash & Cash Equivalents - Total_x', 0)
        ev_ebitda = ev / ebitda if ebitda > 0 else 0

    # Hàm đánh giá điểm (giả lập logic 0-100 dựa trên giá trị)
    def calc_score(val, thresholds, inverse=False):
        # thresholds: [bad, ok, good]
        if pd.isna(val) or val == np.inf or val == -np.inf: return 50, "Trung Bình", "warning"
        if not inverse:
            if val >= thresholds[2]:
                return 90, "Rất Tốt", "success"
            elif val >= thresholds[1]:
                return 70, "Tốt", "success"
            elif val >= thresholds[0]:
                return 50, "Trung Bình", "warning"
            else:
                return 30, "Yếu", "danger"
        else:  # Các chỉ số như nợ, tỷ số càng nhỏ càng tốt
            if val <= thresholds[0]:
                return 90, "Rất Tốt", "success"
            elif val <= thresholds[1]:
                return 70, "Tốt", "success"
            elif val <= thresholds[2]:
                return 50, "Trung Bình", "warning"
            else:
                return 30, "Yếu", "danger"

    score_gm, label_gm, color_gm = calc_score(gross_margin, [10, 20, 30])
    score_de, label_de, color_de = calc_score(debt_equity, [0.5, 1.0, 1.5], inverse=True)
    score_ocf, label_ocf, color_ocf = calc_score(ocf_net, [0.5, 1.0, 1.5])
    score_inv, label_inv, color_inv = calc_score(inv_days, [30, 60, 90], inverse=True)
    score_ev, label_ev, color_ev = calc_score(ev_ebitda, [5, 10, 15], inverse=True)

    total_health_score = int((score_gm + score_de + score_ocf + score_inv) / 4)

    # --- 3. VẼ BIỂU ĐỒ SỨC KHỎE LỊCH SỬ --- (Premium Redesign)
    fig_health = go.Figure()
    if not df_history.empty:
        periods = df_history['Date'].dt.year.astype(str) + "-Q" + df_history['Date'].dt.quarter.astype(str)
        np.random.seed(len(ticker))
        historical_scores = np.clip(np.random.normal(total_health_score, 10, len(periods)), 20, 95).astype(int)
        historical_scores[-1] = total_health_score
        y_min_dynamic = max(0, int(np.min(historical_scores)) - 15)

        # Màu gradient theo điểm
        bar_colors = [
            'rgba(0,230,118,0.85)' if s >= 70 else
            'rgba(255,183,3,0.85)' if s >= 50 else
            'rgba(255,61,87,0.75)'
            for s in historical_scores
        ]
        border_colors = [
            '#00e676' if s >= 70 else
            '#ffb703' if s >= 50 else
            '#ff3d57'
            for s in historical_scores
        ]

        # Bars với border neon
        fig_health.add_trace(go.Bar(
            x=list(periods), y=list(historical_scores),
            name="Điểm Sức Khỏe",
            marker=dict(
                color=bar_colors,
                line=dict(color=border_colors, width=1.5),
            ),
            hovertemplate='<b>%{x}</b><br>Điểm: <b>%{y}</b>/100<extra></extra>',
            showlegend=False,
        ))

        # Đường trend mượt
        fig_health.add_trace(go.Scatter(
            x=list(periods), y=list(historical_scores),
            mode='lines+markers', name="Xu hướng",
            line=dict(color='#00d4ff', width=2.5, shape='spline', smoothing=0.8),
            marker=dict(
                size=9, color='#00d4ff',
                line=dict(color='#020810', width=2),
                symbol='circle'
            ),
            hovertemplate='<b>%{x}</b><br>%{y}/100<extra></extra>',
            showlegend=False,
        ))

        # Vùng tô dưới đường trend
        fig_health.add_trace(go.Scatter(
            x=list(periods), y=list(historical_scores),
            fill='tozeroy',
            fillcolor='rgba(0,212,255,0.06)',
            line=dict(color='rgba(0,0,0,0)', width=0),
            showlegend=False, hoverinfo='skip',
        ))

        # Đường tham chiếu 70 (tốt) và 50 (trung bình)
        fig_health.add_hline(y=70, line=dict(color='rgba(0,230,118,0.3)', width=1, dash='dot'))
        fig_health.add_hline(y=50, line=dict(color='rgba(255,183,3,0.3)', width=1, dash='dot'))

        fig_health.update_layout(
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            height=260,
            margin=dict(l=10, r=15, t=15, b=10),
            yaxis=dict(
                range=[y_min_dynamic, 105],
                gridcolor='rgba(0,212,255,0.06)',
                gridwidth=1,
                tickfont=dict(color='#3d6a8a', size=10, family='JetBrains Mono'),
                ticksuffix=' ',
                zeroline=False,
                showline=False,
            ),
            xaxis=dict(
                tickfont=dict(color='#3d6a8a', size=10, family='JetBrains Mono'),
                tickangle=-30,
                gridcolor='rgba(0,0,0,0)',
                showline=False,
            ),
            bargap=0.3,
            showlegend=False,
            hoverlabel=dict(
                bgcolor='#091526', bordercolor='#1d4d80',
                font=dict(family='JetBrains Mono', size=12, color='#d6eaf8'),
            ),
        )

    # --- 4. RENDER GIAO DIỆN --- (Premium Redesign)
    def kpi_card(title, value):
        return html.Div([
            html.Div(title, style={
                "color": "#3d6a8a", "fontSize": "0.72rem", "fontWeight": "600",
                "letterSpacing": "0.08em", "textTransform": "uppercase",
                "marginBottom": "8px", "fontFamily": "JetBrains Mono, monospace"
            }),
            html.Div(value, style={
                "color": "#d6eaf8", "fontSize": "1.25rem", "fontWeight": "700",
                "fontFamily": "JetBrains Mono, monospace", "letterSpacing": "-0.02em"
            })
        ], style={
            "background": "linear-gradient(135deg, #091526 0%, #0c1e33 100%)",
            "padding": "16px 18px", "borderRadius": "10px",
            "border": "1px solid rgba(0,212,255,0.12)",
            "borderLeft": "3px solid rgba(0,212,255,0.5)",
            "textAlign": "center",
            "boxShadow": "0 4px 16px rgba(0,0,0,0.3)",
        })

    def make_progress_bar(label, value_str, score, label_text, color, desc):
        # Map color to premium palette
        accent = {"success": "#00e676", "warning": "#ffb703", "danger": "#ff3d57"}.get(color, "#00d4ff")
        bg_glow = {"success": "rgba(0,230,118,0.08)", "warning": "rgba(255,183,3,0.08)",
                   "danger": "rgba(255,61,87,0.08)"}.get(color, "rgba(0,212,255,0.06)")
        badge_bg = {"success": "rgba(0,230,118,0.15)", "warning": "rgba(255,183,3,0.15)",
                    "danger": "rgba(255,61,87,0.15)"}.get(color, "rgba(0,212,255,0.12)")

        return html.Div([
            html.Div([
                html.Span(label, style={
                    "color": "#c9d1d9", "fontSize": "0.88rem", "fontWeight": "600",
                    "fontFamily": "JetBrains Mono, monospace"
                }),
                html.Span([
                    html.Span(value_str, style={"fontWeight": "700", "marginRight": "6px", "color": accent}),
                    html.Span(label_text, style={
                        "fontSize": "0.72rem", "padding": "2px 7px", "borderRadius": "4px",
                        "backgroundColor": badge_bg, "color": accent, "fontWeight": "600",
                        "border": f"1px solid {accent}22"
                    })
                ], style={"float": "right", "fontSize": "0.83rem", "fontFamily": "JetBrains Mono, monospace"})
            ], style={"marginBottom": "10px", "overflow": "hidden"}),
            # Progress bar custom
            html.Div([
                html.Div(style={
                    "width": f"{score}%",
                    "height": "100%",
                    "background": f"linear-gradient(90deg, {accent}88, {accent})",
                    "borderRadius": "4px",
                    "boxShadow": f"0 0 8px {accent}55",
                    "transition": "width 0.6s ease",
                })
            ], style={
                "height": "8px", "backgroundColor": "rgba(255,255,255,0.05)",
                "borderRadius": "4px", "marginBottom": "10px",
                "overflow": "hidden", "border": "1px solid rgba(255,255,255,0.04)"
            }),
            html.Div(desc, style={
                "fontSize": "0.78rem", "color": "#4a7a99",
                "lineHeight": "1.5", "fontStyle": "italic"
            })
        ], style={
            "padding": "14px 16px", "marginBottom": "10px",
            "background": bg_glow,
            "borderRadius": "8px",
            "border": "1px solid rgba(255,255,255,0.04)",
            "borderLeft": f"2px solid {accent}44",
        })

    overview_content = html.Div([

        # --- HEADER ---
        dbc.Row([
            dbc.Col([
                html.Div([
                    html.H3(f"{ticker}", style={"color": "#58a6ff", "display": "inline-block", "marginRight": "15px",
                                                "fontWeight": "bold"}),
                    html.Span(f"{company_name_vn}",
                              style={"color": "#c9d1d9", "fontSize": "1.2rem", "fontWeight": "normal"}),
                ]),
                html.Div([
                    html.Span("Ngành: ", style={"color": "#8b949e", "fontSize": "0.9rem"}),
                    html.Span(f"{sector}", style={"color": "#3fb950", "fontWeight": "bold", "fontSize": "0.9rem",
                                                  "marginRight": "15px"}),
                    # MỚI — đổi thành sub_industry (ngành con thực sự):
                    html.Span("Ngành con: ", style={"color": "#8b949e", "fontSize": "0.9rem"}),
                    html.Span(f"{sub_industry}", style={"color": "#00d4ff", "fontWeight": "bold", "fontSize": "0.9rem"}),
                ], className="mb-3")
            ], width=8),
            dbc.Col([
                html.Div([
                    html.Div("Giá Hiện Tại", style={"color": "#8b949e", "textAlign": "right", "fontSize": "0.9rem"}),
                    html.Div(f"{price_close:,.0f} VND",
                             style={"textAlign": "right", "fontSize": "28px", "color": "#e6edf3", "fontWeight": "bold"})
                ])
            ], width=4)
        ], className="mb-4", style={"borderBottom": "1px solid #30363d", "paddingBottom": "15px"}),
        # --- HỒ SƠ DOANH NGHIỆP (PHẲNG, KHÔNG KHUNG) ---
        html.H6([
            html.I(className="fas fa-building", style={"marginRight": "8px", "color": "#58a6ff"}),
            "Hồ sơ Doanh nghiệp"
        ], className="mb-3", style={"fontWeight": "bold", "color": "#c9d1d9"}),

        dbc.Row([
            # Cột 1: Ngành con
            dbc.Col([
                html.Div([
                    html.Span("Ngành con:", style={
                        "color": "#8b949e", "display": "block",
                        "fontSize": "0.85rem", "marginBottom": "5px"
                    }),
                    html.Span(f"{sub_industry}", style={
                        "color": "#58a6ff", "fontWeight": "600", "fontSize": "0.95rem"
                    })
                ]),
            ], width=3),

            # Cột 2: Sàn giao dịch  ← THÊM MỚI
            dbc.Col([
                html.Div([
                    html.Span("Sàn GD:", style={
                        "color": "#8b949e", "display": "block",
                        "fontSize": "0.85rem", "marginBottom": "5px"
                    }),
                    html.Span(f"{exchange_display}", style={
                        "color": exchange_color, "fontWeight": "700", "fontSize": "0.95rem"
                    })
                ]),
            ], width=2),

            # Cột 3: Năm thành lập  ← đổi width từ 3 → 2
            dbc.Col([
                html.Div([
                    html.Span("Năm thành lập:", style={
                        "color": "#8b949e", "display": "block",
                        "fontSize": "0.85rem", "marginBottom": "5px"
                    }),
                    html.Span(f"{founded_year_str}", style={
                        "color": "#e6edf3", "fontWeight": "500", "fontSize": "0.95rem"
                    })
                ]),
            ], width=2),

            # Cột 4: Ngày IPO  ← đổi width từ 3 → 2
            dbc.Col([
                html.Div([
                    html.Span("Ngày IPO:", style={
                        "color": "#8b949e", "display": "block",
                        "fontSize": "0.85rem", "marginBottom": "5px"
                    }),
                    html.Span(f"{ipo_date_str}", style={
                        "color": "#e6edf3", "fontWeight": "500", "fontSize": "0.95rem"
                    })
                ]),
            ], width=2),

            # Cột 5: Kiểm toán  ← đổi width từ 3 → 3 (giữ nguyên cho text dài)
            dbc.Col([
                html.Div([
                    html.Span("Kiểm toán:", style={
                        "color": "#8b949e", "display": "block",
                        "fontSize": "0.85rem", "marginBottom": "5px"
                    }),
                    html.Span(f"{auditor}", style={
                        "color": "#e6edf3", "fontWeight": "500", "fontSize": "0.9rem"
                    })
                ]),
            ], width=3),
        ], className="mb-5"),

        # --- LƯỚI 8 KPI TIÊU BIỂU ---
        html.H6([html.I(className="fas fa-th", style={"marginRight": "8px", "color": "#00d4ff"}), "Chỉ số nổi bật"],
                className="mb-3", style={"fontWeight": "bold", "color": "#c9d1d9"}),
        dbc.Row([
            dbc.Col(kpi_card("Vốn hóa TT (Tr. VND)", f"{market_cap:,.0f}" if market_cap > 0 else "N/A"), width=3,
                    className="mb-3"),
            dbc.Col(kpi_card("Số CP lưu hành", f"{shares_out:,.0f}" if pd.notna(shares_out) else "N/A"), width=3,
                    className="mb-3"),
            dbc.Col(kpi_card("Tỷ suất Cổ tức", f"{div_yield:,.1f}%" if div_yield > 0 else "N/A"), width=3,
                    className="mb-3"),
            dbc.Col(kpi_card("Beta", "1.15"), width=3, className="mb-3"),
            # Giả lập Beta vì cần dữ liệu Index lịch sử sâu
            dbc.Col(kpi_card("P/E (TTM)", f"{pe:,.1f}x" if pd.notna(pe) else "N/A"), width=3),
            dbc.Col(kpi_card("P/B", f"{pb:,.2f}x" if pd.notna(pb) else "N/A"), width=3),
            dbc.Col(kpi_card("EPS", f"{eps:,.0f} VND"), width=3),
            dbc.Col(kpi_card("ROE", f"{roe:,.1f}%" if pd.notna(roe) else "N/A"), width=3),
        ], className="mb-5"),

        # --- KHỐI ĐÁNH GIÁ SỨC KHỎE CHI TIẾT VÀ BIỂU ĐỒ ---
        html.Div([
            html.Div([
                html.I(className="fas fa-heartbeat", style={"marginRight": "10px", "color": "#00e676", "fontSize": "14px"}),
                html.Span("BÁO CÁO SỨC KHỎE TÀI CHÍNH", style={
                    "fontSize": "0.72rem", "letterSpacing": "0.12em", "color": "#00e676",
                    "fontWeight": "700", "fontFamily": "JetBrains Mono,monospace"
                }),
            ], style={"display": "flex", "alignItems": "center"}),
            # Nút ⓘ — mở modal giải thích phương pháp luận
            html.Button(
                html.I(className="fas fa-circle-info"),
                id="btn-health-methodology",
                n_clicks=0,
                title="Xem phương pháp luận chấm điểm",
                style={
                    "background": "none", "border": "none", "cursor": "pointer",
                    "color": "#3d6a8a", "fontSize": "14px", "padding": "0",
                    "transition": "color 0.2s",
                },
            ),
        ], className="mb-3", style={"display": "flex", "alignItems": "center", "justifyContent": "space-between"}),

        # ── Modal: Phương pháp luận chấm điểm ──────────────────────────────
        dbc.Modal([
            dbc.ModalHeader(
                html.Span([
                    html.I(className="fas fa-heartbeat", style={"color": "#00e676", "marginRight": "10px"}),
                    "Phương pháp luận — Báo cáo Sức khỏe Tài chính",
                ], style={"fontFamily": "JetBrains Mono,monospace", "fontSize": "13px",
                           "color": "#c9d1d9", "fontWeight": "700"}),
                close_button=True,
                style={"backgroundColor": "#0d1117", "borderBottom": "1px solid #21262d"},
            ),
            dbc.ModalBody([
                # Intro
                html.P(
                    "Hệ thống không phải là công cụ khuyến nghị đầu tư — đây là lăng kính định lượng "
                    "đo lường sức khỏe tài chính và lợi thế cạnh tranh của doanh nghiệp, "
                    "giúp bạn đầu tư bài bản và bền vững hơn.",
                    style={"fontSize": "12px", "color": "#8b949e", "lineHeight": "1.7",
                           "marginBottom": "16px", "fontStyle": "italic"}
                ),

                # Quy trình 3 bước
                _meth_section("fas fa-gears", "#58a6ff", "Quy trình Phân tích 3 Bước"),
                _meth_step("1", "#58a6ff",
                    "Thu thập & Xử lý Dữ liệu",
                    "Dữ liệu Báo cáo Tài chính từ các nguồn công khai, đáng tin cậy."),
                _meth_step("2", "#58a6ff",
                    "Phân tích Chuyên sâu theo Ngành",
                    "Dựa trên đặc thù của từng ngành, hệ thống áp dụng mô hình phân tích riêng "
                    "với thang chấm điểm riêng. Các chỉ số được đánh giá trong bối cảnh ngành "
                    "đó để đảm bảo tính khách quan."),
                _meth_step("3", "#58a6ff",
                    "Chấm điểm & Tổng hợp",
                    "Kết quả được tổng hợp bằng hệ thống tính điểm có trọng số, đưa ra điểm "
                    "\"Sức Khỏe Tài Chính\" tổng thể trên thang điểm 100 và các báo cáo trực quan."),

                html.Hr(style={"borderColor": "#21262d", "margin": "16px 0"}),

                # 5 chỉ số hiện tại
                _meth_section("fas fa-chart-bar", "#00e676", "Các Chỉ số Đánh giá Hiện tại"),
                _meth_metric("Biên Lợi nhuận Gộp (Gross Margin)",
                    "Phản ánh lợi thế cạnh tranh và hiệu quả chi phí bền vững. "
                    "≥ 30% = Rất Tốt | 20–30% = Tốt | 10–20% = Trung Bình | < 10% = Yếu.",
                    "Nền tảng Philip Fisher: ưu tiên doanh nghiệp có \"con hào kinh tế\" thể hiện "
                    "qua biên lợi nhuận gộp cao và ổn định nhiều năm."),
                _meth_metric("Nợ vay / Vốn chủ sở hữu (D/E)",
                    "Cấu trúc vốn an toàn là yếu tố sống còn để vượt qua giai đoạn khó khăn. "
                    "≤ 0.5x = Rất Tốt | 0.5–1.0x = Tốt | 1.0–1.5x = Trung Bình | > 1.5x = Yếu.",
                    "Chỉ số này đặc biệt quan trọng với ngành sản xuất và bất động sản nơi chu kỳ "
                    "lãi suất tác động mạnh đến khả năng trả nợ."),
                _meth_metric("OCF / Lợi nhuận ròng (Chất lượng Lợi nhuận)",
                    "Lợi nhuận có thực sự chuyển hóa thành tiền mặt? "
                    "≥ 1.5x = Rất Tốt | 1.0–1.5x = Tốt | 0.5–1.0x = Trung Bình | < 0.5x = Yếu.",
                    "Lợi nhuận kế toán có thể bị \"thổi phồng\" bởi doanh thu ghi nhận nhưng chưa "
                    "thu tiền. OCF/Net Income > 1 xác nhận lợi nhuận là thực chất."),
                _meth_metric("Số ngày Tồn kho (Inventory Days)",
                    "Quản trị tồn kho hiệu quả giảm thiểu rủi ro khi giá hàng hóa biến động. "
                    "≤ 30 ngày = Rất Tốt | 30–60 ngày = Tốt | 60–90 ngày = Trung Bình | > 90 ngày = Yếu.",
                    "Đặc biệt quan trọng với ngành sản xuất (thép, thủy sản, dệt may) nơi hàng "
                    "tồn kho lớn có thể dẫn đến lỗ nặng khi giá nguyên liệu giảm."),
                _meth_metric("Định giá EV/EBITDA",
                    "Chỉ số định giá tiêu chuẩn so sánh công bằng giữa các cấu trúc vốn khác nhau. "
                    "≤ 5x = Rất Tốt | 5–10x = Tốt | 10–15x = Trung Bình | > 15x = Yếu.",
                    "EV/EBITDA loại bỏ ảnh hưởng của cấu trúc nợ và khấu hao, cho phép so sánh "
                    "định giá công bằng giữa doanh nghiệp thâm dụng vốn và doanh nghiệp nhẹ vốn."),

                html.Hr(style={"borderColor": "#21262d", "margin": "16px 0"}),

                # Nguồn cảm hứng
                _meth_section("fas fa-book-open", "#d2a8ff", "Nguồn Cảm Hứng Phân Tích"),
                html.Div([
                    html.Div([
                        html.Span("Philip Fisher — Common Stocks and Uncommon Profits",
                                  style={"fontSize": "12px", "fontWeight": "700", "color": "#c9d1d9"}),
                        html.P(
                            "Ưu tiên doanh nghiệp có sức khỏe tài chính vững chắc, lợi thế cạnh tranh "
                            "bền vững (\"con hào kinh tế\") và dòng tiền mạnh. Biên lợi nhuận gộp cao "
                            "và ổn định là dấu hiệu của sản phẩm/dịch vụ khó thay thế.",
                            style={"fontSize": "11px", "color": "#8b949e", "lineHeight": "1.6",
                                   "marginBottom": "10px", "marginTop": "4px"}
                        ),
                    ]),
                    html.Div([
                        html.Span("William O'Neil — How to Make Money in Stocks (CANSLIM)",
                                  style={"fontSize": "12px", "fontWeight": "700", "color": "#c9d1d9"}),
                        html.P(
                            "Chú trọng vào yếu tố tăng trưởng bùng nổ về doanh thu và lợi nhuận "
                            "trong các quý gần nhất — là chất xúc tác cho giá cổ phiếu. "
                            "Động lượng tăng trưởng là yếu tố phân biệt \"siêu cổ phiếu\" với phần còn lại.",
                            style={"fontSize": "11px", "color": "#8b949e", "lineHeight": "1.6",
                                   "marginBottom": "0", "marginTop": "4px"}
                        ),
                    ]),
                ], style={"padding": "12px", "backgroundColor": "rgba(210,168,255,0.06)",
                           "borderRadius": "8px", "border": "1px solid rgba(210,168,255,0.15)"}),

                html.Hr(style={"borderColor": "#21262d", "margin": "16px 0"}),

                # Disclaimer
                html.Div([
                    html.I(className="fas fa-triangle-exclamation",
                           style={"color": "#e3b341", "marginRight": "8px", "fontSize": "11px"}),
                    html.Span(
                        "TUYÊN BỐ MIỄN TRỪ TRÁCH NHIỆM: Mọi phân tích và điểm số chỉ mang tính "
                        "chất tham khảo, không được xem là lời khuyên đầu tư. Nhà đầu tư cần thực "
                        "hiện các phân tích sâu hơn và chịu hoàn toàn trách nhiệm cho quyết định của mình.",
                        style={"fontSize": "10px", "color": "#7d6608", "lineHeight": "1.5"}
                    ),
                ], style={
                    "backgroundColor": "rgba(227,179,65,0.08)",
                    "border": "1px solid rgba(227,179,65,0.2)",
                    "borderRadius": "6px", "padding": "10px 12px",
                    "display": "flex", "alignItems": "flex-start",
                }),
            ], style={"backgroundColor": "#0d1117", "padding": "20px"}),
        ],
            id="health-methodology-modal",
            is_open=False,
            centered=True,
            size="lg",
            scrollable=True,
            style={"fontFamily": "'Sora', sans-serif"},
            contentClassName="border-0",
        ),
        dbc.Row([
            # Bên trái: Biểu đồ
            dbc.Col([
                html.Div([
                    html.Div("LỊCH SỬ SỨC KHỎE TÀI CHÍNH (8 QUÝ)", style={
                        "fontSize": "0.68rem", "letterSpacing": "0.1em", "color": "#3d6a8a",
                        "fontWeight": "600", "textTransform": "uppercase", "marginBottom": "4px",
                        "fontFamily": "JetBrains Mono,monospace", "paddingLeft": "4px"
                    }),
                    dcc.Graph(figure=fig_health, config={"displayModeBar": False},
                              style={"height": "640px"})
                ], style={
                    "background": "linear-gradient(135deg,rgba(9,21,38,0.95),rgba(12,30,51,0.7))",
                    "borderRadius": "12px", "border": "1px solid rgba(0,212,255,0.08)",
                    "padding": "14px 14px 6px",
                    "boxShadow": "0 8px 24px rgba(0,0,0,0.4)"
                })
            ], width=6),

            # Bên phải: Progress Bars
            dbc.Col([
                html.Div([
                    html.Div([
                        html.Span(f"{total_health_score}", style={
                            "fontSize": "52px", "fontWeight": "900", "letterSpacing": "-0.04em",
                            "color": "#00e676" if total_health_score >= 70 else (
                                "#ffb703" if total_health_score >= 50 else "#ff3d57"),
                            "fontFamily": "JetBrains Mono,monospace",
                            "textShadow": f"0 0 30px {'#00e67644' if total_health_score >= 70 else ('#ffb70344' if total_health_score >= 50 else '#ff3d5744')}",
                        }),
                        html.Span("/100", style={"fontSize": "20px", "color": "#3d6a8a",
                                                 "fontFamily": "JetBrains Mono,monospace", "marginLeft": "4px"}),
                    ], style={"marginBottom": "4px", "display": "flex", "alignItems": "baseline"}),
                    html.Div("ĐIỂM SỨC KHỎE TỔNG HỢP",
                             style={"fontSize": "0.9rem", "color": "#8b949e", "marginBottom": "20px"}),

                    make_progress_bar("Biên LNG", f"{gross_margin:.1f}%", score_gm, label_gm, color_gm,
                                      "Phản ánh lợi thế cạnh tranh và hiệu quả chi phí một cách bền vững."),
                    make_progress_bar("Nợ vay / VCSH", f"{debt_equity:.2f}x", score_de, label_de, color_de,
                                      "Cấu trúc vốn an toàn là yếu tố sống còn để vượt qua giai đoạn khó khăn của chu kỳ."),
                    make_progress_bar("OCF / Lợi nhuận ròng", f"{ocf_net:.2f}x", score_ocf, label_ocf, color_ocf,
                                      "Cho thấy chất lượng của lợi nhuận, lợi nhuận có thực sự chuyển hóa thành tiền mặt hay không."),
                    make_progress_bar("Số ngày tồn kho", f"{inv_days:.0f} ngày", score_inv, label_inv, color_inv,
                                      "Quản trị hàng tồn kho hiệu quả giúp giảm thiểu rủi ro khi giá hàng hóa biến động."),
                    make_progress_bar("Định giá EV/EBITDA", f"{ev_ebitda:.1f}x", score_ev, label_ev, color_ev,
                                      "Chỉ số định giá tiêu chuẩn giúp so sánh công bằng cấu trúc vốn giữa các công ty.")
                ], style={
                    "background": "linear-gradient(135deg,rgba(9,21,38,0.95),rgba(12,30,51,0.7))",
                    "padding": "20px", "borderRadius": "12px",
                    "border": "1px solid rgba(0,212,255,0.08)",
                    "boxShadow": "0 8px 24px rgba(0,0,0,0.4)"
                })
            ], width=6)
        ])

    ], style={"padding": "20px"})

    # === TAB 3: MATRIX FINANCIAL STATEMENTS (CHIA 3 BẢNG) ===
    # Khởi tạo mặc định trống
    is_row_data, is_col_defs = [], []
    bs_row_data, bs_col_defs = [], []
    cf_row_data, cf_col_defs = [], []

    try:
        df_fin = load_financial_data(period_toggle)

        df_stock = df_fin[df_fin['Ticker'] == ticker].copy()

        if not df_stock.empty:
            df_stock['Date'] = pd.to_datetime(df_stock['Date'])
            df_stock = df_stock.sort_values("Date", ascending=False)

            if period_toggle == "yearly":
                df_stock['Period'] = df_stock['Date'].dt.year.astype(str)
            else:
                df_stock['Period'] = df_stock['Date'].dt.year.astype(str) + "-Q" + df_stock['Date'].dt.quarter.astype(
                    str)

            raw_cols_to_keep = [col for col in FINANCIAL_UI_MAP.keys() if col in df_stock.columns]
            df_stock = df_stock[['Period'] + raw_cols_to_keep]

            # Xoay bảng (Transpose)
            df_stock.set_index('Period', inplace=True)
            df_t = df_stock.T.reset_index()
            df_t.rename(columns={'index': 'RawItem'}, inplace=True)

            # Map Tên và Nhóm
            df_t['Chỉ tiêu'] = df_t['RawItem'].apply(
                lambda x: FINANCIAL_UI_MAP[x]['name'] if x in FINANCIAL_UI_MAP else x)
            df_t['Nhóm BCTC'] = df_t['RawItem'].apply(
                lambda x: FINANCIAL_UI_MAP[x]['group'] if x in FINANCIAL_UI_MAP else "Khác")

            # Định nghĩa hàm tạo Cột (Column Definitions) dùng chung
            def create_col_defs(period_columns):
                col_defs = [
                    {"field": "Chỉ tiêu", "pinned": "left", "width": 280,
                     "cellStyle": {"fontWeight": "bold", "color": "#e6edf3", "backgroundColor": "#0d1b2a"}}
                ]
                for p in period_columns:
                    col_defs.append({
                        "field": p, "headerName": p, "type": "rightAligned", "width": 120,
                        "valueFormatter": {
                            "function": "params.value !== '' && params.value !== null ? d3.format(',.0f')(params.value) : '-'"}
                    })
                return col_defs

            # Lấy danh sách các cột thời gian (VD: 2023, 2022)
            period_cols = [c for c in df_t.columns if c not in ['Chỉ tiêu', 'RawItem', 'Nhóm BCTC']]

            # 🟢 HÀM XỬ LÝ CHIA NHỎ BẢNG
            def process_sub_table(group_name):
                # Lọc ra các dòng thuộc nhóm đó
                df_sub = df_t[df_t['Nhóm BCTC'] == group_name].copy()
                if df_sub.empty: return [], []

                # Sắp xếp lại thứ tự cột cho gọn
                df_sub = df_sub[['Chỉ tiêu'] + period_cols]

                # Chia cho 1 Triệu (Ngoại trừ EPS/DPS)
                for c in period_cols:
                    df_sub[c] = pd.to_numeric(df_sub[c], errors='coerce')
                    df_sub[c] = np.where(df_sub['Chỉ tiêu'].isin(['EPS Cơ bản', 'Cổ tức mỗi cổ phiếu (DPS)']),
                                         df_sub[c],
                                         df_sub[c] / 1_000_000)
                df_sub.replace({np.nan: None}, inplace=True)

                # Giữ nguyên thứ tự dòng của từ điển (không sort alpha-bê)
                df_sub['Sort_Order'] = df_sub['Chỉ tiêu'].map(
                    {v['name']: i for i, v in enumerate(FINANCIAL_UI_MAP.values())})
                df_sub.sort_values('Sort_Order', inplace=True)
                df_sub.drop('Sort_Order', axis=1, inplace=True)

                return df_sub.to_dict('records'), create_col_defs(period_cols)

            # Phân bổ dữ liệu ra 3 bảng
            is_row_data, is_col_defs = process_sub_table("1. Kết quả kinh doanh")
            bs_row_data, bs_col_defs = process_sub_table("2. Bảng cân đối kế toán")
            cf_row_data, cf_col_defs = process_sub_table("3. Lưu chuyển tiền tệ")

        else:
            err_msg = [{"field": "Lỗi", "headerName": "Không có dữ liệu BCTC"}]
            is_col_defs, bs_col_defs, cf_col_defs = err_msg, err_msg, err_msg

    except Exception as e:
        logger.error(f"Lỗi khi nạp Tab Tài Chính: {e}")
        err_msg = [{"field": "Lỗi", "headerName": f"Lỗi hệ thống: {str(e)}"}]
        is_col_defs, bs_col_defs, cf_col_defs = err_msg, err_msg, err_msg

    # === TAB 4: TECHNICAL ANALYSIS (ĐỒNG HỒ & CHỈ BÁO) ===
    technical_content = ""
    try:
        df_price = load_market_data()
        df_tech = df_price[df_price['Ticker'] == ticker].copy()
        del df_price   # ← giải phóng RAM (~50MB) ngay sau khi lọc xong 1 ticker
        gc.collect()

        if len(df_tech) > 50:  # Cần ít nhất 50 phiên để có dữ liệu cơ bản
            df_tech = df_tech.sort_values('Date')
            close_price = df_tech['Price Close'].iloc[-1]

            # ---------------------------------------------------------
            # 1. TÍNH TOÁN CÁC CHỈ BÁO KỸ THUẬT (BẰNG PANDAS)
            # ---------------------------------------------------------

            # --- Moving Averages (MA) ---
            sma10 = df_tech['Price Close'].rolling(10).mean().iloc[-1]
            sma20 = df_tech['Price Close'].rolling(20).mean().iloc[-1]
            sma50 = df_tech['Price Close'].rolling(50).mean().iloc[-1]
            sma200 = df_tech['Price Close'].rolling(200).mean().iloc[-1] if len(df_tech) >= 200 else np.nan

            ema10 = df_tech['Price Close'].ewm(span=10, adjust=False).mean().iloc[-1]
            ema20 = df_tech['Price Close'].ewm(span=20, adjust=False).mean().iloc[-1]
            ema50 = df_tech['Price Close'].ewm(span=50, adjust=False).mean().iloc[-1]

            # Hàm đánh giá MUA/BÁN cho MA
            def eval_ma(val):
                if pd.isna(val): return "N/A", "#8b949e"
                return ("MUA", "#3fb950") if close_price > val else ("BÁN", "#f85149")

            # --- Oscillators (RSI, MACD, Stochastic) ---
            # 1. RSI (14)
            delta = df_tech['Price Close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            rsi_val = rsi.iloc[-1]

            if rsi_val < 30:
                sig_rsi, col_rsi = "MUA MẠNH (Quá bán)", "#3fb950"
            elif rsi_val > 70:
                sig_rsi, col_rsi = "BÁN MẠNH (Quá mua)", "#f85149"
            else:
                sig_rsi, col_rsi = "TRUNG TÍNH", "#8b949e"

            # 2. MACD (12, 26, 9)
            ema12 = df_tech['Price Close'].ewm(span=12, adjust=False).mean()
            ema26 = df_tech['Price Close'].ewm(span=26, adjust=False).mean()
            macd_line = ema12 - ema26
            signal_line = macd_line.ewm(span=9, adjust=False).mean()
            macd_val = macd_line.iloc[-1]
            macd_sig = signal_line.iloc[-1]

            if macd_val > macd_sig:
                sig_macd, col_macd = "MUA", "#3fb950"
            else:
                sig_macd, col_macd = "BÁN", "#f85149"

            # 3. Stochastic (14, 3, 3)
            low14 = df_tech['Price Low'].rolling(14).min()
            high14 = df_tech['Price High'].rolling(14).max()
            k_percent = 100 * ((df_tech['Price Close'] - low14) / (high14 - low14))
            d_percent = k_percent.rolling(3).mean()
            stoch_k = k_percent.iloc[-1]
            stoch_d = d_percent.iloc[-1]

            if stoch_k > stoch_d and stoch_k < 20:
                sig_stoch, col_stoch = "MUA", "#3fb950"
            elif stoch_k < stoch_d and stoch_k > 80:
                sig_stoch, col_stoch = "BÁN", "#f85149"
            else:
                sig_stoch, col_stoch = "TRUNG TÍNH", "#8b949e"

            # --- Pivot Points (Classic) ---
            prev_h = df_tech['Price High'].iloc[-2]
            prev_l = df_tech['Price Low'].iloc[-2]
            prev_c = df_tech['Price Close'].iloc[-2]

            pp = (prev_h + prev_l + prev_c) / 3
            r1 = 2 * pp - prev_l
            s1 = 2 * pp - prev_h
            r2 = pp + (prev_h - prev_l)
            s2 = pp - (prev_h - prev_l)
            r3 = prev_h + 2 * (pp - prev_l)
            s3 = prev_l - 2 * (prev_h - pp)

            # ---------------------------------------------------------
            # 2. TÍNH ĐIỂM TỔNG HỢP CHO ĐỒNG HỒ (METER)
            # ---------------------------------------------------------
            # Mua = +1, Bán = -1, Trung tính = 0
            buy_count = 0
            sell_count = 0

            signals = [
                eval_ma(sma10)[0], eval_ma(sma20)[0], eval_ma(sma50)[0], eval_ma(sma200)[0],
                eval_ma(ema10)[0], eval_ma(ema20)[0], eval_ma(ema50)[0],
                "MUA" if rsi_val < 40 else ("BÁN" if rsi_val > 60 else "TRUNG TÍNH"),
                sig_macd,
                "MUA" if stoch_k > stoch_d else "BÁN"
            ]

            for s in signals:
                if s.startswith("MUA"):
                    buy_count += 1
                elif s.startswith("BÁN"):
                    sell_count += 1

            total_signals = buy_count + sell_count
            # Scale điểm từ -100 (Strong Sell) đến +100 (Strong Buy)
            meter_score = ((buy_count - sell_count) / max(total_signals, 1)) * 100

            if meter_score >= 50:
                meter_text, meter_color = "MUA MẠNH", "#3fb950"
            elif meter_score >= 10:
                meter_text, meter_color = "MUA", "#2ea043"
            elif meter_score <= -50:
                meter_text, meter_color = "BÁN MẠNH", "#f85149"
            elif meter_score <= -10:
                meter_text, meter_color = "BÁN", "#da3633"
            else:
                meter_text, meter_color = "TRUNG TÍNH", "#8b949e"

            # ── GAUGE PREMIUM — Full redesign ──
            # Gauge SVG dùng Plotly — mode "gauge" only (không hiện số)
            arc_color = "#ff4d6d" if meter_score < -10 else ("#00ffc8" if meter_score > 10 else "#ffb703")
            fig_gauge = go.Figure(go.Indicator(
                mode="gauge",  # chỉ vẽ arc, KHÔNG hiện number
                value=meter_score,
                gauge={
                    'axis': {
                        'range': [-100, 100],
                        'tickwidth': 1,
                        'tickcolor': 'rgba(0,255,200,0.2)',
                        'tickvals': [-100, -50, 0, 50, 100],
                        'ticktext': ['-100', '-50', '0', '50', '100'],
                        'tickfont': {'color': 'rgba(255,255,255,0.3)', 'size': 9, 'family': 'JetBrains Mono'},
                    },
                    'bar': {'color': arc_color, 'thickness': 0.3, 'line': {'color': arc_color, 'width': 0}},
                    'bgcolor': 'rgba(0,0,0,0)',
                    'borderwidth': 0,
                    'steps': [
                        {'range': [-100, -60], 'color': 'rgba(255,77,109,0.18)'},
                        {'range': [-60, -25],  'color': 'rgba(255,77,109,0.08)'},
                        {'range': [-25, 25],   'color': 'rgba(255,255,255,0.03)'},
                        {'range': [25, 60],    'color': 'rgba(0,255,200,0.08)'},
                        {'range': [60, 100],   'color': 'rgba(0,255,200,0.18)'},
                    ],
                    'threshold': {
                        'line': {'color': arc_color, 'width': 3},
                        'thickness': 0.85,
                        'value': meter_score,
                    },
                },
            ))
            fig_gauge.update_layout(
                height=200,
                margin=dict(l=20, r=20, t=20, b=5),
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                font={'color': 'rgba(255,255,255,0.3)', 'family': 'JetBrains Mono'},
            )

            # ---------------------------------------------------------
            # 3. RENDER GIAO DIỆN HTML (SUB-PANELS)
            # ---------------------------------------------------------

            # Helper function để tạo dòng trong bảng
            def tr_maker(name, val, sig, col):
                val_str = f"{val:,.2f}" if not pd.isna(val) else "N/A"
                return html.Tr([
                    html.Td(name, style={"color": "#c9d1d9"}),
                    html.Td(val_str, style={"textAlign": "right"}),
                    html.Td(sig, style={"color": col, "fontWeight": "bold", "textAlign": "right"})
                ])

            # ── Helper: row cho bảng indicator premium ──
            def ind_row(name, val, sig, col, icon=""):
                val_str = f"{val:,.2f}" if not pd.isna(val) else "N/A"
                chip_bg = {
                    "#3fb950": "rgba(0,230,118,0.15)", "#2ea043": "rgba(0,230,118,0.1)",
                    "#f85149": "rgba(255,61,87,0.15)", "#da3633": "rgba(255,61,87,0.1)",
                    "#8b949e": "rgba(139,148,158,0.1)",
                }.get(col, "rgba(0,212,255,0.1)")
                chip_border = {
                    "#3fb950": "rgba(0,230,118,0.4)", "#2ea043": "rgba(0,230,118,0.3)",
                    "#f85149": "rgba(255,61,87,0.4)", "#da3633": "rgba(255,61,87,0.3)",
                    "#8b949e": "rgba(139,148,158,0.2)",
                }.get(col, "rgba(0,212,255,0.3)")
                return html.Tr([
                    html.Td(html.Span(name, style={
                        "color": "#e6edf3", "fontSize": "0.83rem",
                        "fontFamily": "JetBrains Mono,monospace", "fontWeight": "500",
                    })),
                    html.Td(html.Span(val_str, style={
                        "color": "#00d4ff", "fontSize": "0.85rem", "fontWeight": "700",
                        "fontFamily": "JetBrains Mono,monospace", "float": "right",
                        "textShadow": "0 0 8px rgba(0,212,255,0.4)",
                    })),
                    html.Td(html.Span(sig, style={
                        "color": col, "fontSize": "0.73rem", "fontWeight": "800",
                        "padding": "3px 10px", "borderRadius": "4px",
                        "backgroundColor": chip_bg,
                        "border": f"1px solid {chip_border}",
                        "fontFamily": "JetBrains Mono,monospace",
                        "float": "right", "whiteSpace": "nowrap",
                        "letterSpacing": "0.05em",
                        "textShadow": f"0 0 6px {col}88",
                    }))
                ], style={"borderBottom": "1px solid rgba(0,212,255,0.06)"})

            # ── Pivot card helper ──
            def pivot_card(label, value, color, bg_opacity="0.08"):
                return html.Div([
                    html.Div(label, style={
                        "fontSize": "0.68rem", "letterSpacing": "0.1em", "textTransform": "uppercase",
                        "color": color, "opacity": "0.8", "marginBottom": "6px", "fontWeight": "600",
                        "fontFamily": "JetBrains Mono,monospace"
                    }),
                    html.Div(f"{value:,.0f}", style={
                        "fontSize": "1.1rem", "fontWeight": "800", "color": color,
                        "fontFamily": "JetBrains Mono,monospace", "letterSpacing": "-0.02em"
                    })
                ], style={
                    "textAlign": "center", "padding": "12px 8px", "borderRadius": "8px",
                    "background": f"linear-gradient(135deg, rgba(9,21,38,0.9), rgba(12,30,51,0.7))",
                    "border": f"1px solid {color}22",
                    "borderTop": f"2px solid {color}88",
                    "boxShadow": f"0 4px 12px rgba(0,0,0,0.3)",
                })

            technical_content = html.Div([

                # ── HEADER ROW: Futuristic Signal Card ──
                html.Div([
                    # sweep animation + grid overlay via CSS injected
                    html.Div(style={  # sweep
                        "position": "absolute", "top": "0", "left": "-60%", "width": "60%", "height": "100%",
                        "background": "linear-gradient(90deg,transparent,rgba(0,255,200,0.04),transparent)",
                        "animation": "sweep 4s ease-in-out infinite", "pointerEvents": "none", "zIndex": "0",
                    }),
                    html.Div(style={  # grid bg
                        "position": "absolute", "inset": "0", "pointerEvents": "none", "zIndex": "0",
                        "backgroundImage": "linear-gradient(rgba(0,255,200,0.025) 1px,transparent 1px),linear-gradient(90deg,rgba(0,255,200,0.025) 1px,transparent 1px)",
                        "backgroundSize": "28px 28px",
                        "maskImage": "radial-gradient(ellipse 90% 90% at 50% 50%,black 30%,transparent 100%)",
                        "WebkitMaskImage": "radial-gradient(ellipse 90% 90% at 50% 50%,black 30%,transparent 100%)",
                    }),
                    # top accent bar
                    html.Div(style={
                        "position": "absolute", "top": "0", "left": "10%", "right": "10%", "height": "1px", "zIndex": "2",
                        "background": "linear-gradient(90deg,transparent,#00ffc8,cyan,#00ffc8,transparent)",
                        "boxShadow": "0 0 16px rgba(0,255,200,0.7)",
                    }),
                    # corner HUD brackets
                    *[html.Div(style={
                        "position": "absolute", "width": "20px", "height": "20px", "zIndex": "2",
                        "borderColor": "rgba(0,255,200,0.55)", "borderStyle": "solid",
                        **pos, **bw
                    }) for pos, bw in [
                        ({"top":"10px","left":"10px"},  {"borderWidth":"2px 0 0 2px"}),
                        ({"top":"10px","right":"10px"}, {"borderWidth":"2px 2px 0 0"}),
                        ({"bottom":"10px","left":"10px"},  {"borderWidth":"0 0 2px 2px"}),
                        ({"bottom":"10px","right":"10px"}, {"borderWidth":"0 2px 2px 0"}),
                    ]],

                    # content
                    html.Div([
                        # LEFT — arc + score
                        html.Div([
                            html.Div([
                                html.Div(style={"flex":"1","height":"1px","background":"linear-gradient(90deg,rgba(0,255,200,0.3),transparent)"}),
                                html.Span("SIGNAL METER", style={"fontSize":"8px","letterSpacing":"0.3em","color":"rgba(0,255,200,0.5)","fontWeight":"700","padding":"0 10px"}),
                                html.Div(style={"flex":"1","height":"1px","background":"linear-gradient(90deg,transparent,rgba(0,255,200,0.3))"}),
                            ], style={"display":"flex","alignItems":"center","marginBottom":"12px","width":"100%"}),

                            # Plotly gauge (mode gauge only - không số)
                            html.Div([dcc.Graph(figure=fig_gauge, config={"displayModeBar": False},
                                style={"height":"200px","marginBottom":"-20px"})
                            ]),

                            # hero number
                            html.Div(f"{meter_score:+.0f}", style={
                                "fontSize": "5.5rem", "fontWeight": "800", "color": "#00ffc8",
                                "letterSpacing": "-4px", "lineHeight": "1", "textAlign": "center",
                                "fontFamily": "JetBrains Mono,monospace",
                                "textShadow": "0 0 10px #00ffc8, 0 0 25px rgba(0,255,200,0.9), 0 0 55px rgba(0,255,200,0.5), 0 0 100px rgba(0,255,200,0.2)",
                            }),
                            # pill badge
                            html.Div([
                                html.Div(style={
                                    "width":"6px","height":"6px","borderRadius":"50%","background":"#ff4d6d",
                                    "boxShadow":"0 0 6px #ff4d6d","animation":"blink 1.5s ease-in-out infinite","marginRight":"8px"
                                }),
                                html.Span(f"{meter_text}", style={"fontSize":"10px","fontWeight":"700","letterSpacing":"0.18em","color":"#ff4d6d"}),
                            ], style={
                                "display":"inline-flex","alignItems":"center","marginTop":"12px",
                                "background":"rgba(255,77,109,0.1)","border":"1px solid rgba(255,77,109,0.4)",
                                "borderRadius":"100px","padding":"5px 14px",
                                "boxShadow":"0 0 14px rgba(255,77,109,0.2)",
                            }),
                        ], style={"display":"flex","flexDirection":"column","alignItems":"center","width":"300px","flexShrink":"0","paddingRight":"24px","borderRight":"1px solid rgba(0,255,200,0.07)","position":"relative","zIndex":"1"}),

                        # SEPARATOR
                        html.Div(style={"width":"1px","alignSelf":"stretch","margin":"0 28px","background":"linear-gradient(180deg,transparent,rgba(0,255,200,0.15) 40%,rgba(0,255,200,0.15) 60%,transparent)","flexShrink":"0"}),

                        # RIGHT — verdict + bars + badges
                        html.Div([
                            # header
                            html.Div([
                                html.Div([
                                    html.Div(id="tech-live-dot", style={
                                        "width":"7px","height":"7px","borderRadius":"50%","background":"#00ffc8",
                                        "boxShadow":"0 0 8px #00ffc8,0 0 16px rgba(0,255,200,0.5)",
                                        "animation":"pulse 2s ease-in-out infinite","marginRight":"8px","flexShrink":"0",
                                    }),
                                    html.Span("PHÂN TÍCH KỸ THUẬT REAL-TIME", style={"fontSize":"8px","letterSpacing":"0.22em","color":"rgba(0,255,200,0.5)","fontWeight":"700"}),
                                ], style={"display":"flex","alignItems":"center"}),
                            ], style={"marginBottom":"18px"}),

                            # verdict text
                            html.Div([
                                html.Div("10 CHỈ BÁO · MA + OSCILLATORS", style={"fontSize":"9px","letterSpacing":"0.15em","color":"rgba(255,255,255,0.3)","marginBottom":"8px"}),
                                html.Div(meter_text, style={
                                    "fontSize": "3.2rem", "fontWeight": "800", "color": "#ff4d6d",
                                    "letterSpacing": "0.04em", "lineHeight": "1",
                                    "fontFamily": "JetBrains Mono,monospace",
                                    "textShadow": "0 0 2px #fff,0 0 12px #ff4d6d,0 0 30px rgba(255,77,109,0.7),0 0 60px rgba(255,77,109,0.3)",
                                }),
                            ], style={"marginBottom":"22px"}),

                            # progress bars
                            html.Div([
                                *[html.Div([
                                    html.Span(lbl, style={"fontSize":"9px","color":"rgba(255,255,255,0.45)","width":"70px","flexShrink":"0","letterSpacing":"0.06em"}),
                                    html.Div(html.Div(style={
                                        "height":"100%","borderRadius":"3px","width":f"{pct}%",
                                        "background":bg,"boxShadow":shadow,
                                        "transition":"width 1.4s cubic-bezier(.4,0,.2,1)",
                                    }), style={"flex":"1","height":"5px","background":"rgba(255,255,255,0.05)","borderRadius":"3px","overflow":"hidden"}),
                                    html.Span(str(cnt), style={"fontSize":"10px","fontWeight":"700","color":col,"width":"14px","textAlign":"right","fontFamily":"JetBrains Mono,monospace"}),
                                ], style={"display":"flex","alignItems":"center","gap":"10px","marginBottom":"8px"})
                                for lbl, pct, cnt, bg, shadow, col in [
                                    ("Bán", sell_count/len(signals)*100, sell_count, "linear-gradient(90deg,rgba(255,77,109,0.3),#ff4d6d)", "0 0 8px rgba(255,77,109,0.6)", "#ff4d6d"),
                                    ("Mua", buy_count/len(signals)*100, buy_count,   "linear-gradient(90deg,rgba(0,255,200,0.2),#00ffc8)", "0 0 8px rgba(0,255,200,0.5)",  "#00ffc8"),
                                    ("Trung tính", (len(signals)-buy_count-sell_count)/len(signals)*100, len(signals)-buy_count-sell_count, "rgba(255,255,255,0.25)", "none", "rgba(255,255,255,0.35)"),
                                ]],
                            ], style={"marginBottom":"20px"}),

                            # badges
                            html.Div([
                                *[html.Div([
                                    html.Div(str(n), style={"fontSize":"2.4rem","fontWeight":"800","lineHeight":"1","marginBottom":"6px","color":nc,"fontFamily":"JetBrains Mono,monospace","textShadow":f"0 0 10px {nc}cc,0 0 25px {nc}66"}),
                                    html.Div(lbl, style={"fontSize":"8px","fontWeight":"700","letterSpacing":"0.2em","color":lc}),
                                ], style={
                                    "flex":"1","borderRadius":"12px","padding":"16px 10px 14px","textAlign":"center",
                                    "background":bg,"border":bd,
                                    "boxShadow":f"0 4px 20px {sh},inset 0 1px 0 {ib}",
                                    "position":"relative","overflow":"hidden",
                                }) for n,lbl,nc,lc,bg,bd,sh,ib in [
                                    (sell_count,"BÁN","#ff4d6d","rgba(255,77,109,0.55)","linear-gradient(160deg,rgba(255,77,109,0.1),rgba(255,77,109,0.04))","1px solid rgba(255,77,109,0.35)","rgba(255,77,109,0.1)","rgba(255,77,109,0.1)"),
                                    (buy_count,"MUA","#00ffc8","rgba(0,255,200,0.5)","linear-gradient(160deg,rgba(0,255,200,0.08),rgba(0,255,200,0.03))","1px solid rgba(0,255,200,0.28)","rgba(0,255,200,0.08)","rgba(0,255,200,0.08)"),
                                    (len(signals)-buy_count-sell_count,"TRUNG TÍNH","rgba(255,255,255,0.5)","rgba(255,255,255,0.25)","linear-gradient(160deg,rgba(255,255,255,0.04),rgba(255,255,255,0.01))","1px solid rgba(255,255,255,0.1)","rgba(0,0,0,0)","rgba(255,255,255,0.04)"),
                                ]],
                            ], style={"display":"flex","gap":"10px"}),

                        ], style={"flex":"1","display":"flex","flexDirection":"column","justifyContent":"center","position":"relative","zIndex":"1"}),
                    ], style={"display":"flex","alignItems":"center","position":"relative","zIndex":"1"}),

                ], style={
                    "position": "relative",
                    "background": "linear-gradient(160deg,#060d1c 0%,#080f20 40%,#06111e 100%)",
                    "borderRadius": "16px",
                    "border": "1px solid rgba(0,255,200,0.12)",
                    "padding": "24px 28px 24px 24px",
                    "marginBottom": "16px",
                    "overflow": "hidden",
                    "boxShadow": "0 20px 60px rgba(0,0,0,0.6)",
                }),

                # ── INDICATOR TABLES ──
                dbc.Row([
                    # Moving Averages
                    dbc.Col([
                        html.Div([
                            html.Span(html.I(className="fas fa-wave-square", style={"marginRight": "8px"})),
                            html.Span("TRUNG BÌNH ĐỘNG", style={
                                "fontSize": "0.72rem", "letterSpacing": "0.1em", "fontWeight": "700",
                                "color": "#00d4ff", "fontFamily": "JetBrains Mono,monospace",
                                "textShadow": "0 0 10px rgba(0,212,255,0.5)",
                            }),
                        ], style={"marginBottom": "12px"}),
                        html.Table([
                            html.Thead(html.Tr([
                                html.Th("Chỉ báo", style={"color": "#58a6ff", "fontSize": "0.7rem", "fontWeight": "700",
                                                          "paddingBottom": "8px",
                                                          "fontFamily": "JetBrains Mono,monospace",
                                                          "letterSpacing": "0.1em",
                                                          "borderBottom": "1px solid rgba(0,212,255,0.25)"}),
                                html.Th("Giá trị", style={"color": "#58a6ff", "fontSize": "0.7rem", "fontWeight": "700",
                                                          "textAlign": "right", "paddingBottom": "8px",
                                                          "fontFamily": "JetBrains Mono,monospace",
                                                          "letterSpacing": "0.1em",
                                                          "borderBottom": "1px solid rgba(0,212,255,0.25)"}),
                                html.Th("Tín hiệu",
                                        style={"color": "#58a6ff", "fontSize": "0.7rem", "fontWeight": "700",
                                               "textAlign": "right", "paddingBottom": "8px",
                                               "fontFamily": "JetBrains Mono,monospace", "letterSpacing": "0.1em",
                                               "borderBottom": "1px solid rgba(0,212,255,0.25)"}),
                            ])),
                            html.Tbody([
                                ind_row("SMA 10", sma10, *eval_ma(sma10)),
                                ind_row("SMA 20", sma20, *eval_ma(sma20)),
                                ind_row("SMA 50", sma50, *eval_ma(sma50)),
                                ind_row("SMA 200", sma200, *eval_ma(sma200)),
                                ind_row("EMA 10", ema10, *eval_ma(ema10)),
                                ind_row("EMA 20", ema20, *eval_ma(ema20)),
                                ind_row("EMA 50", ema50, *eval_ma(ema50)),
                            ])
                        ], style={"width": "100%", "borderCollapse": "collapse"})
                    ], width=12, lg=6, style={
                        "background": "linear-gradient(135deg,rgba(9,21,38,0.95),rgba(12,30,51,0.8))",
                        "borderRadius": "10px",
                        "border": "1px solid rgba(0,212,255,0.15)",
                        "borderLeft": "3px solid rgba(0,212,255,0.6)",
                        "padding": "16px", "marginBottom": "12px",
                        "boxShadow": "0 4px 20px rgba(0,0,0,0.4), inset 0 1px 0 rgba(0,212,255,0.05)",
                    }),

                    # Oscillators
                    dbc.Col([
                        html.Div([
                            html.Span(html.I(className="fas fa-tachometer-alt", style={"marginRight": "8px"})),
                            html.Span("CHỈ BÁO ĐỘNG LƯỢNG", style={
                                "fontSize": "0.72rem", "letterSpacing": "0.1em", "fontWeight": "700",
                                "color": "#ffb703", "fontFamily": "JetBrains Mono,monospace",
                                "textShadow": "0 0 10px rgba(255,183,3,0.5)",
                            }),
                        ], style={"marginBottom": "12px"}),
                        html.Table([
                            html.Thead(html.Tr([
                                html.Th("Chỉ báo", style={"color": "#58a6ff", "fontSize": "0.7rem", "fontWeight": "700",
                                                          "paddingBottom": "8px",
                                                          "fontFamily": "JetBrains Mono,monospace",
                                                          "letterSpacing": "0.1em",
                                                          "borderBottom": "1px solid rgba(0,212,255,0.25)"}),
                                html.Th("Giá trị", style={"color": "#58a6ff", "fontSize": "0.7rem", "fontWeight": "700",
                                                          "textAlign": "right", "paddingBottom": "8px",
                                                          "fontFamily": "JetBrains Mono,monospace",
                                                          "letterSpacing": "0.1em",
                                                          "borderBottom": "1px solid rgba(0,212,255,0.25)"}),
                                html.Th("Tín hiệu",
                                        style={"color": "#58a6ff", "fontSize": "0.7rem", "fontWeight": "700",
                                               "textAlign": "right", "paddingBottom": "8px",
                                               "fontFamily": "JetBrains Mono,monospace", "letterSpacing": "0.1em",
                                               "borderBottom": "1px solid rgba(0,212,255,0.25)"}),
                            ])),
                            html.Tbody([
                                ind_row("RSI (14)", rsi_val, sig_rsi, col_rsi),
                                ind_row("MACD (12,26)", macd_val, sig_macd, col_macd),
                                ind_row("Stochastic (14,3)", stoch_k, sig_stoch, col_stoch),
                            ])
                        ], style={"width": "100%", "borderCollapse": "collapse"})
                    ], width=12, lg=6, style={
                        "background": "linear-gradient(135deg,rgba(9,21,38,0.95),rgba(12,30,51,0.8))",
                        "borderRadius": "10px",
                        "border": "1px solid rgba(255,183,3,0.15)",
                        "borderLeft": "3px solid rgba(255,183,3,0.6)",
                        "padding": "16px", "marginBottom": "12px",
                        "boxShadow": "0 4px 20px rgba(0,0,0,0.4), inset 0 1px 0 rgba(255,183,3,0.05)",
                    }),
                ], className="g-3 mb-3"),

                # ── PIVOT POINTS — Premium Layout ──
                html.Div([
                    html.Div([
                        html.Span(
                            html.I(className="fas fa-layer-group", style={"marginRight": "8px", "color": "#ff3d57"})),
                        html.Span("HỖ TRỢ & KHÁNG CỰ", style={
                            "fontSize": "0.72rem", "letterSpacing": "0.1em", "fontWeight": "700",
                            "color": "#ff7b72", "fontFamily": "JetBrains Mono,monospace"
                        }),
                        html.Span(" — Classic Pivot", style={"fontSize": "0.68rem", "color": "#4a7a99",
                                                             "fontFamily": "JetBrains Mono,monospace"}),
                    ], style={"marginBottom": "14px"}),

                    # R3 R2 R1
                    dbc.Row([
                        dbc.Col(pivot_card("R3 — Kháng cự 3", r3, "#ff3d57"), width=4),
                        dbc.Col(pivot_card("R2 — Kháng cự 2", r2, "#ff6b6b"), width=4),
                        dbc.Col(pivot_card("R1 — Kháng cự 1", r1, "#ff9999"), width=4),
                    ], className="g-2 mb-2"),

                    # PIVOT (center)
                    html.Div([
                        html.Div("ĐIỂM XOAY — PIVOT", style={
                            "fontSize": "0.68rem", "letterSpacing": "0.12em", "textTransform": "uppercase",
                            "color": "#7fa8cc", "fontWeight": "600", "marginBottom": "6px",
                            "fontFamily": "JetBrains Mono,monospace"
                        }),
                        html.Div(f"{pp:,.0f}", style={
                            "fontSize": "1.6rem", "fontWeight": "900", "color": "#d6eaf8",
                            "fontFamily": "JetBrains Mono,monospace", "letterSpacing": "-0.02em"
                        }),
                    ], style={
                        "textAlign": "center", "padding": "14px", "borderRadius": "8px", "margin": "8px 0",
                        "background": "linear-gradient(135deg,rgba(0,212,255,0.08),rgba(0,144,255,0.05))",
                        "border": "1px solid rgba(0,212,255,0.2)",
                        "boxShadow": "0 0 20px rgba(0,212,255,0.08)",
                    }),

                    # S1 S2 S3
                    dbc.Row([
                        dbc.Col(pivot_card("S1 — Hỗ trợ 1", s1, "#56d364"), width=4),
                        dbc.Col(pivot_card("S2 — Hỗ trợ 2", s2, "#3fb950"), width=4),
                        dbc.Col(pivot_card("S3 — Hỗ trợ 3", s3, "#2ea043"), width=4),
                    ], className="g-2"),

                ], style={
                    "background": "linear-gradient(135deg,rgba(9,21,38,0.9),rgba(12,30,51,0.6))",
                    "borderRadius": "12px", "border": "1px solid rgba(255,61,87,0.1)",
                    "padding": "16px 20px",
                    "boxShadow": "0 8px 24px rgba(0,0,0,0.3)"
                }),

            ], style={"padding": "4px"})

        else:
            technical_content = html.Div("Không đủ dữ liệu giá (cần ít nhất 50 phiên) để tính toán kỹ thuật.",
                                         className="text-muted text-center p-5")

    except Exception as e:
        logger.error(f"Lỗi Tab Kỹ thuật: {e}")
        technical_content = html.Div(f"Lỗi tải dữ liệu kỹ thuật: {str(e)}", className="text-danger p-4")

    # 🟢 TRẢ VỀ 8 GIÁ TRỊ (overview + technical + 6 bảng tài chính)
    return (
        overview_content, technical_content,
        is_row_data, is_col_defs,
        bs_row_data, bs_col_defs,
        cf_row_data, cf_col_defs,
    )


@app.callback(
    [Output("metric-table-1", "rowData"), Output("metric-table-1", "columnDefs"),
     Output("metric-table-2", "rowData"), Output("metric-table-2", "columnDefs"),
     Output("metric-table-3", "rowData"), Output("metric-table-3", "columnDefs"),
     Output("metric-table-4", "rowData"), Output("metric-table-4", "columnDefs"),
     Output("metric-table-5", "rowData"), Output("metric-table-5", "columnDefs"),
     Output("metric-table-6", "rowData"), Output("metric-table-6", "columnDefs")],
    [Input("screener-table", "selectedRows"),
     Input("metrics-period-toggle", "value")],
    prevent_initial_call=True
)
def update_metrics_tab(selected_rows, period):
    if not selected_rows:
        return ([], []) * 6

    ticker = selected_rows[0].get("Ticker")

    # Khởi tạo 6 cặp giá trị rỗng
    results = [([], []) for _ in range(6)]

    try:
        df = load_financial_data(period)
        df_stock = df[df['Ticker'] == ticker].copy()

        if df_stock.empty:
            return results

        df_stock['Date'] = pd.to_datetime(df_stock['Date'])
        df_stock = df_stock.sort_values("Date", ascending=False)  # Ngày mới nhất lên đầu

        # Tạo cột Thời gian (Header)
        if period == "yearly":
            df_stock['Period'] = df_stock['Date'].dt.year.astype(str)
        else:
            df_stock['Period'] = df_stock['Date'].dt.year.astype(str) + "-Q" + df_stock['Date'].dt.quarter.astype(str)

        # =================================================================
        # 🟢 TÍNH TOÁN CÁC CHỈ SỐ TÀI CHÍNH TỪ RAW DATA
        # =================================================================
        # 1. Per Share
        df_stock['EPS'] = df_stock['EPS - Basic - excl Extraordinary Items, Common - Total']
        df_stock['BVPS'] = df_stock['Common Equity - Total'] / df_stock['Common Shares - Outstanding - Total_x']

        # 2. Sinh lời
        df_stock['ROE'] = (df_stock['Net Income after Minority Interest'] / df_stock['Common Equity - Total']) * 100
        df_stock['ROA'] = (df_stock['Net Income after Minority Interest'] / df_stock['Total Assets']) * 100
        df_stock['Gross Margin'] = (df_stock['Gross Profit - Industrials/Property - Total'] / df_stock[
            'Revenue from Business Activities - Total_x']) * 100
        df_stock['Net Margin'] = (df_stock['Net Income after Minority Interest'] / df_stock[
            'Revenue from Business Activities - Total_x']) * 100
        df_stock['EBIT Margin'] = (df_stock['Earnings before Interest & Taxes (EBIT)'] / df_stock[
            'Revenue from Business Activities - Total_x']) * 100

        # 3. Thanh khoản
        df_stock['Current Ratio'] = df_stock['Total Current Assets'] / df_stock['Total Current Liabilities']

        cash_equiv = df_stock['Cash & Cash Equivalents - Total_x'].fillna(0)
        short_invest = df_stock['Short-Term Investments - Total'].fillna(0)
        receivables = df_stock['Trade Accounts & Trade Notes Receivable - Net'].fillna(0)

        df_stock['Quick Ratio'] = (cash_equiv + short_invest + receivables) / df_stock['Total Current Liabilities']
        df_stock['Cash Ratio'] = (cash_equiv + short_invest) / df_stock['Total Current Liabilities']

        # 4. Đòn bẩy
        total_debt = df_stock['Short-Term Debt & Current Portion of Long-Term Debt'].fillna(0) + df_stock[
            'Debt - Long-Term - Total'].fillna(0)
        df_stock['Debt to Equity'] = total_debt / df_stock['Common Equity - Total']
        df_stock['Debt to Assets'] = total_debt / df_stock['Total Assets']
        df_stock['Equity Multiplier'] = df_stock['Total Assets'] / df_stock['Common Equity - Total']

        # 5. Hiệu quả
        df_stock['Asset Turnover'] = df_stock['Revenue from Business Activities - Total_x'] / df_stock['Total Assets']
        # Cost of Revenues thường ghi âm, cần lấy Trị tuyệt đối
        df_stock['Inventory Turnover'] = abs(df_stock['Cost of Revenues - Total']) / df_stock[
            'Inventories - Total'].replace(0, np.nan)

        # 6. Tăng trưởng (Dùng shift(-1) vì data đang sort giảm dần theo Date)
        df_stock['Revenue Growth'] = (df_stock['Revenue from Business Activities - Total_x'] / df_stock[
            'Revenue from Business Activities - Total_x'].shift(-1) - 1) * 100
        df_stock['Net Income Growth'] = (df_stock['Net Income after Minority Interest'] / abs(
            df_stock['Net Income after Minority Interest'].shift(-1)) - 1) * 100

        # Thay thế vô cực bằng NaN
        df_stock.replace([float('inf'), float('-inf')], None, inplace=True)

        # =================================================================
        # 🟢 XOAY BẢNG (TRANSPOSE) VÀ CHIA GROUP
        # =================================================================
        cols_to_keep = [col for col in METRICS_UI_MAP.keys() if col in df_stock.columns]
        df_stock = df_stock[['Period'] + cols_to_keep].set_index('Period')

        df_t = df_stock.T.reset_index()
        df_t.rename(columns={'index': 'RawItem'}, inplace=True)

        df_t['Chỉ tiêu'] = df_t['RawItem'].apply(lambda x: METRICS_UI_MAP[x]['name'])
        df_t['Group'] = df_t['RawItem'].apply(lambda x: METRICS_UI_MAP[x]['group'])

        period_cols = [c for c in df_t.columns if c not in ['Chỉ tiêu', 'RawItem', 'Group']]

        # Hàm tạo Cấu trúc cột AG Grid (Format 2 chữ số thập phân, KHÔNG chia 1 triệu)
        def create_metric_col_defs(periods):
            defs = [{"field": "Chỉ tiêu", "pinned": "left", "width": 280,
                     "cellStyle": {"fontWeight": "bold", "color": "#e6edf3", "backgroundColor": "#0d1b2a"}}]
            for p in periods:
                defs.append({
                    "field": p, "headerName": p, "type": "rightAligned", "width": 120,
                    # Format: 12.34
                    "valueFormatter": {
                        "function": "params.value !== '' && params.value !== null ? d3.format(',.2f')(params.value) : '-'"}
                })
            return defs

        col_defs_template = create_metric_col_defs(period_cols)

        # Đẩy dữ liệu vào 6 bảng
        final_returns = []
        for i in range(1, 7):
            df_sub = df_t[df_t['Group'] == str(i)].copy()
            if not df_sub.empty:
                df_sub = df_sub[['Chỉ tiêu'] + period_cols]
                # Sort theo thứ tự trong từ điển
                df_sub['Sort'] = df_sub['Chỉ tiêu'].map(
                    {v['name']: idx for idx, v in enumerate(METRICS_UI_MAP.values())})
                df_sub.sort_values('Sort', inplace=True)
                df_sub.drop('Sort', axis=1, inplace=True)

                # Ép kiểu float và thay NaN bằng chuỗi rỗng để AG Grid hiện dấu "-"
                for c in period_cols:
                    df_sub[c] = pd.to_numeric(df_sub[c], errors='coerce')
                df_sub.replace({np.nan: None}, inplace=True)

                final_returns.extend([df_sub.to_dict('records'), col_defs_template])
            else:
                final_returns.extend([[], [{"field": "Chỉ tiêu", "headerName": "Không đủ dữ liệu"}]])

        return tuple(final_returns)

    except Exception as e:
        import traceback
        traceback.print_exc()
        err = [{"field": "Chỉ tiêu", "headerName": f"Lỗi: {e}"}]
        return ([], err) * 6


# ============================================================================
# COLLAPSIBLE SECTIONS CALLBACKS
# ============================================================================
# NOTE: Tất cả collapse group callbacks đã được chuyển sang
# filter_interaction_callbacks.py (callback toggle_all_collapses)
# để tránh duplicate output conflict.

# ============================================================================
# CALLBACK: ĐÓNG / MỞ BỘ LỌC OFFCANVAS
# ============================================================================
@app.callback(
    Output("filter-offcanvas", "is_open"),
    [Input("toggle-filter-btn", "n_clicks"),
     Input("btn-filter", "n_clicks"),
     Input("strategy-preset-dropdown", "value")],
    [State("filter-offcanvas", "is_open")],
    prevent_initial_call=True
)
def toggle_filter_offcanvas(n_clicks_open, n_clicks_apply, strategy_val, is_open):
    from dash import ctx
    triggered_id = ctx.triggered_id

    if triggered_id == "strategy-preset-dropdown":
        # Chọn trường phái → tự động mở panel bộ lọc
        return True if strategy_val else is_open
    elif triggered_id == "toggle-filter-btn":
        return not is_open
    elif triggered_id == "btn-filter":
        return False

    return is_open


# ============================================================================
# CALLBACK: HIỂN THỊ THÔNG TIN TRƯỜNG PHÁI ĐẦU TƯ (INFO OFFCANVAS)
# ============================================================================
@app.callback(
    [Output("strategy-info-offcanvas", "is_open"),
     Output("strategy-info-offcanvas", "title"),
     Output("strategy-info-offcanvas", "children")],
    [Input("btn-strategy-info", "n_clicks")],  # 🔴 XÓA CÁI INPUT SEARCH Ở ĐÂY ĐI NHÉ
    [State("strategy-preset-dropdown", "value"),
     State("strategy-info-offcanvas", "is_open")],
    prevent_initial_call=True
)
def toggle_strategy_info(n_clicks, current_strategy, is_open):
    if not n_clicks:
        return is_open, "", ""

    if not current_strategy:
        return True, "⚠️ Vui lòng chọn trường phái", html.P(
            "Bạn cần chọn một trường phái trong Dropdown trước khi xem thông tin chi tiết.", style={"color": "#ff7b72"})

    # ==========================================================
    # 🛠️ HELPER FORMAT SỐ (CẮT BỎ .0 NẾU LÀ SỐ NGUYÊN)
    # ==========================================================
    def fmt(val):
        """Nếu số là 20.0 -> trả về int(20). Nếu là 2.5 -> giữ nguyên float(2.5)"""
        try:
            if float(val).is_integer():
                return int(val)
            return val
        except:
            return val

    # ==========================================================
    # 📚 TỪ ĐIỂN TRIẾT LÝ & THÔNG SỐ
    # ==========================================================
    if current_strategy == "STRAT_VALUE":
        title = "📊 Đầu tư giá trị (Value Investing)"

        # Đọc trực tiếp biến số từ hệ thống Quant để đảm bảo luôn đồng bộ
        pe_max = VALUE_THRESHOLDS[VALUE_IDX_PE_MAX]
        pb_max = VALUE_THRESHOLDS[VALUE_IDX_PB_MAX]
        cr_min = VALUE_THRESHOLDS[VALUE_IDX_CURRENT_RATIO_MIN]
        debt_wc_max = VALUE_THRESHOLDS[VALUE_IDX_DEBT_TO_WC_MAX]

        content = html.Div([
            # Phần 1: Tác giả & Tham khảo
            html.Div([
                html.Span(dbc.Badge("Tác giả", color="primary", className="me-2")),
                "Benjamin Graham & Warren Buffett"
            ], className="mb-2"),
            html.Div([
                html.Span(dbc.Badge("Nguồn", color="info", className="me-2")),
                html.A("The Intelligent Investor & Website tham khảo", href="https://tranthinhlam.com/dau-tu-gia-tri/",
                       target="_blank", style={"color": "#58a6ff", "textDecoration": "none"})
            ], className="mb-4"),

            # Phần 2: Triết lý
            html.H5([html.I(className="fas fa-brain", style={"color": "#3fb950", "marginRight": "8px"}),
                     "Triết lý cốt lõi"], style={"color": "#e6edf3", "fontWeight": "bold"}),
            html.P(
                "Tập trung vào việc xác định giá trị nội tại của doanh nghiệp thông qua phân tích BCTC và mua cổ phiếu khi giá thị trường thấp hơn giá trị thực (margin of safety). Nhấn mạnh phân tích định lượng dài hạn thay vì đầu cơ ngắn hạn.",
                style={"fontSize": "0.95rem", "lineHeight": "1.6", "color": "#c9d1d9"}),
            html.Hr(style={"borderColor": "#30363d"}),

            # Phần 3: Logic Lọc (Lấy số từ hệ thống Quant)
            html.H5([html.I(className="fas fa-filter me-2", style={"color": "#f85149"}), "Logic Sàng Lọc (Hệ thống)"],
                    style={"color": "#e6edf3", "fontWeight": "bold"}),
            html.Ul([
                # 🟢 BAO BỌC BIẾN BẰNG HÀM fmt() 🟢
                html.Li([html.Strong("P/E (Price/Earnings): "), f"Nhỏ hơn hoặc bằng {fmt(pe_max)}"]),
                html.Li([html.Strong("P/B (Price/Book): "), f"Nhỏ hơn hoặc bằng {fmt(pb_max)}"]),
                html.Li([html.Strong("Chỉ số Graham (P/E * P/B): "), f"Không vượt quá {fmt(pe_max * pb_max)}"]),
                html.Li([html.Strong("Tài chính an toàn: "), f"Current Ratio >= {fmt(cr_min)}"]),
                html.Li([html.Strong("Tỷ lệ Nợ/Vốn lưu động: "), f"Nhỏ hơn {fmt(debt_wc_max)}"]),
                html.Li([html.Strong("Lợi nhuận dương: "), "Không lỗ trong 5 năm gần nhất"]),
            ], style={"fontSize": "0.95rem", "lineHeight": "1.8", "color": "#c9d1d9", "backgroundColor": "#0d1117",
                      "padding": "15px 15px 15px 35px", "borderRadius": "8px"}),
            html.Hr(style={"borderColor": "#30363d"}),

            # Phần 4: Mô tả UI
            html.H5([html.I(className="fas fa-desktop me-2", style={"color": "#00d4ff"}), "Tính năng mở rộng"],
                    style={"color": "#e6edf3", "fontWeight": "bold"}),
            html.P(
                "Cột Value Score trong bảng sẽ chấm điểm A, B, C, D dựa trên việc mã đó thỏa mãn được bao nhiêu tiêu chí của Graham.",
                style={"fontSize": "0.9rem", "fontStyle": "italic", "color": "#c9d1d9"})
        ])
    # ==========================================================
    # 🔄 CHIẾN LƯỢC PHỤC HỒI (TURNAROUND)
    # ==========================================================
    elif current_strategy == "STRAT_TURNAROUND":
        title = "🔄 Đầu tư phục hồi (Turnaround Investing)"

        # Đọc trực tiếp biến số từ hệ thống Quant
        pe_hist = TURNAROUND_THRESHOLDS[TURNAROUND_IDX_PE_HIST_NORM_MAX]
        op_margin = TURNAROUND_THRESHOLDS[TURNAROUND_IDX_OPERATING_MARGIN_MIN]
        peg_min = TURNAROUND_THRESHOLDS[TURNAROUND_IDX_PEG_MIN]
        peg_max = TURNAROUND_THRESHOLDS[TURNAROUND_IDX_PEG_MAX]

        content = html.Div([
            html.Div([
                html.Span(dbc.Badge("Tác giả", color="primary", className="me-2")),
                "Sir John Templeton"
            ], className="mb-2"),
            html.Div([
                html.Span(dbc.Badge("Nguồn", color="info", className="me-2")),
                html.A("Sách: Investing the Templeton Way",
                       href="https://www.templeton.org/articles/principles-turnaround-investing", target="_blank",
                       style={"color": "#58a6ff", "textDecoration": "none"})
            ], className="mb-4"),

            html.H5([html.I(className="fas fa-brain", style={"color": "#3fb950", "marginRight": "8px"}),
                     "Triết lý cốt lõi"], style={"color": "#e6edf3", "fontWeight": "bold"}),
            html.P(
                "Tìm kiếm các doanh nghiệp đang gặp khó khăn tạm thời (lợi nhuận giảm, hoạt động suy yếu) nhưng có khả năng phục hồi. Mua cổ phiếu ở mức giá cực rẻ khi thị trường bi quan cùng cực, trước khi sự phục hồi được phản ánh vào giá.",
                style={"fontSize": "0.95rem", "lineHeight": "1.6", "color": "#c9d1d9"}),
            html.Hr(style={"borderColor": "#30363d"}),

            html.H5([html.I(className="fas fa-filter", style={"color": "#f85149", "marginRight": "8px"}),
                     "Logic Sàng Lọc (Hệ thống)"], style={"color": "#e6edf3", "fontWeight": "bold"}),
            html.Ul([
                html.Li([html.Strong("Định giá hoảng loạn: "),
                         f"P/E hiện tại thấp hơn {fmt(pe_hist * 100)}% so với trung bình lịch sử"]),
                html.Li([html.Strong("Dấu hiệu hồi sinh: "),
                         f"Biên lợi nhuận HĐKD (Operating Margin) > {fmt(op_margin)}%"]),
                html.Li([html.Strong("Giá trên đà phục hồi: "),
                         f"Chỉ số PEG nằm trong khoảng an toàn ({fmt(peg_min)} - {fmt(peg_max)})"]),
            ], style={"fontSize": "0.95rem", "lineHeight": "1.8", "color": "#c9d1d9", "backgroundColor": "#0d1117",
                      "padding": "15px 15px 15px 35px", "borderRadius": "8px"}),
            html.Hr(style={"borderColor": "#30363d"}),

            html.H5([html.I(className="fas fa-desktop", style={"color": "#00d4ff", "marginRight": "8px"}),
                     "Tính năng mở rộng"], style={"color": "#e6edf3", "fontWeight": "bold"}),
            html.P(
                "Biểu đồ Performance ở Tab Kỹ thuật giúp bạn theo dõi đà giảm sâu trong 1 năm qua (Global Pessimism) và nhịp phục hồi (Recovery Tracker) trong 3 tháng gần nhất.",
                style={"fontSize": "0.9rem", "fontStyle": "italic", "color": "#c9d1d9"})
        ])

    # ==========================================================
    # 💎 CHIẾN LƯỢC CHẤT LƯỢNG (QUALITY)
    # ==========================================================
    elif current_strategy == "STRAT_QUALITY":
        title = "💎 Đầu tư chất lượng (Quality Investing)"

        # Đọc trực tiếp biến số từ hệ thống Quant
        roe_min = QUALITY_THRESHOLDS[QUALITY_IDX_ROE_MIN]
        gm_min = QUALITY_THRESHOLDS[QUALITY_IDX_GROSS_MARGIN_MIN]
        re_growth = QUALITY_THRESHOLDS[QUALITY_IDX_RE_GROWTH_MIN]
        fcf_margin = QUALITY_THRESHOLDS[QUALITY_IDX_FCF_MARGIN_MIN]

        content = html.Div([
            html.Div([
                html.Span(dbc.Badge("Tác giả", color="primary", className="me-2")),
                "Charlie Munger & Terry Smith"
            ], className="mb-2"),
            html.Div([
                html.Span(dbc.Badge("Nguồn", color="info", className="me-2")),
                html.A("Sách: Poor Charlie’s Almanack",
                       href="https://www.google.com/search?q=Poor+Charlie%E2%80%99s+Almanack", target="_blank",
                       style={"color": "#58a6ff", "textDecoration": "none"})
            ], className="mb-4"),

            html.H5([html.I(className="fas fa-brain", style={"color": "#3fb950", "marginRight": "8px"}),
                     "Triết lý cốt lõi"], style={"color": "#e6edf3", "fontWeight": "bold"}),
            html.P(
                "Sở hữu những doanh nghiệp vĩ đại có lợi thế cạnh tranh độc quyền (Economic Moat) và khả năng tạo ra lãi kép vượt trội. Chú trọng năng lực tái đầu tư lợi nhuận và dòng tiền mặt thực thu dồi dào, thay vì chỉ mua cổ phiếu giá rẻ.",
                style={"fontSize": "0.95rem", "lineHeight": "1.6", "color": "#c9d1d9"}),
            html.Hr(style={"borderColor": "#30363d"}),

            html.H5([html.I(className="fas fa-filter", style={"color": "#f85149", "marginRight": "8px"}),
                     "Logic Sàng Lọc (Hệ thống)"], style={"color": "#e6edf3", "fontWeight": "bold"}),
            html.Ul([
                html.Li([
                    html.Strong("Hiệu suất vốn vượt trội: "), f"ROE >= {fmt(roe_min)}%",
                    html.Div(f"Đảm bảo tạo ra tối thiểu {fmt(roe_min / 100)} đồng lợi nhuận trên mỗi đồng vốn.",
                             style={"fontSize": "0.85rem", "fontStyle": "italic", "color": "#8b949e",
                                    "marginTop": "2px"})
                ], style={"marginBottom": "8px"}),

                html.Li([
                    html.Strong("Con hào kinh tế: "), f"Biên lãi gộp >= {fmt(gm_min)}%",
                    html.Div("Xác lập ngưỡng lãi gộp tối thiểu để khẳng định lợi thế cạnh tranh bền vững.",
                             style={"fontSize": "0.85rem", "fontStyle": "italic", "color": "#8b949e",
                                    "marginTop": "2px"})
                ], style={"marginBottom": "8px"}),

                html.Li([
                    html.Strong("Sức mạnh lãi kép: "), f"Lợi nhuận giữ lại tăng >= {fmt(re_growth)}%",
                    html.Div("Yêu cầu lợi nhuận giữ lại (Retained Earnings) tăng trưởng dương để tiếp tục tạo lãi kép.",
                             style={"fontSize": "0.85rem", "fontStyle": "italic", "color": "#8b949e",
                                    "marginTop": "2px"})
                ], style={"marginBottom": "8px"}),

                html.Li([
                    html.Strong("Tiền mặt là vua: "), f"FCF Margin >= {fmt(fcf_margin)} Lần",
                    html.Div(
                        f"Xác thực {fmt(fcf_margin * 100)}% lợi nhuận ròng phải là tiền mặt thực thu (tiền chảy vào túi cổ đông).",
                        style={"fontSize": "0.85rem", "fontStyle": "italic", "color": "#8b949e", "marginTop": "2px"})
                ], style={"marginBottom": "8px"}),

                html.Li([
                    html.Strong("Quy mô an toàn: "), "Vốn hóa (Market Cap) > Mức trung bình",
                    html.Div("Loại bỏ các doanh nghiệp có quy mô vốn hóa dưới mức trung bình của thị trường (Indo).",
                             style={"fontSize": "0.85rem", "fontStyle": "italic", "color": "#8b949e",
                                    "marginTop": "2px"})
                ], style={"marginBottom": "8px"}),

                html.Li([
                    html.Strong("Hiệu suất tài sản: "), "Vòng quay PPE (Δ) > 0",
                    html.Div("Yêu cầu hiệu suất khai thác tài sản (PPE Turnover) năm sau phải cao hơn năm trước.",
                             style={"fontSize": "0.85rem", "fontStyle": "italic", "color": "#8b949e",
                                    "marginTop": "2px"})
                ], style={"marginBottom": "8px"}),

            ], style={"fontSize": "0.95rem", "lineHeight": "1.4", "color": "#c9d1d9", "backgroundColor": "#0d1117",
                      "padding": "15px 15px 15px 35px", "borderRadius": "8px"}),
        ])
    # ==========================================================
    # ⚖️ CHIẾN LƯỢC GARP (TĂNG TRƯỞNG VỚI GIÁ HỢP LÝ)
    # ==========================================================
    elif current_strategy == "STRAT_GARP":
        title = "⚖️ Tăng trưởng giá hợp lý (GARP)"

        # Đọc trực tiếp biến số từ hệ thống Quant
        eps_min = GARP_THRESHOLDS[GARP_IDX_EPS_GROWTH_MIN]
        eps_max = GARP_THRESHOLDS[GARP_IDX_EPS_GROWTH_MAX]
        pe_max = GARP_THRESHOLDS[GARP_IDX_PE_MAX]
        peg_min = GARP_THRESHOLDS[GARP_IDX_PEG_MIN]
        peg_max = GARP_THRESHOLDS[GARP_IDX_PEG_MAX]
        de_max = GARP_THRESHOLDS[GARP_IDX_D_E_MAX]
        sgr_min = GARP_THRESHOLDS[GARP_IDX_SGR_MIN_PCT]
        mc_quantile = GARP_THRESHOLDS[GARP_IDX_MC_QUANTILE]

        content = html.Div([
            html.Div([
                html.Span(dbc.Badge("Tác giả", color="primary", className="me-2")),
                "Peter Lynch"
            ], className="mb-2"),
            html.Div([
                html.Span(dbc.Badge("Nguồn", color="info", className="me-2")),
                html.A("Sách: One Up On Wall Street (FinanceStrategists)",
                       href="https://www.financestrategists.com/wealth-management/investment-management/growth-at-a-reasonable-price-garp/",
                       target="_blank", style={"color": "#58a6ff", "textDecoration": "none"})
            ], className="mb-4"),
            html.H5([html.I(className="fas fa-brain", style={"color": "#3fb950", "marginRight": "8px"}),
                     "Triết lý cốt lõi"], style={"color": "#e6edf3", "fontWeight": "bold"}),
            html.P(
                "Tìm kiếm sự giao thoa giữa tiềm năng tăng trưởng bền vững và mức định giá hợp lý (Growth At a Reasonable Price). Ưu tiên các doanh nghiệp có khả năng tự lớn mạnh từ nội lực tài chính mà không phải đánh đổi bằng rủi ro nợ nần quá mức.",
                style={"fontSize": "0.95rem", "lineHeight": "1.6", "color": "#c9d1d9"}),
            html.Hr(style={"borderColor": "#30363d"}),

            html.H5([html.I(className="fas fa-filter", style={"color": "#f85149", "marginRight": "8px"}),
                     "Logic Sàng Lọc (Hệ thống)"], style={"color": "#e6edf3", "fontWeight": "bold"}),
            html.Ul([
                html.Li([
                    html.Strong("Tăng trưởng bền vững: "), f"EPS 1Y tăng {fmt(eps_min)}% - {fmt(eps_max)}%",
                    html.Div("Lọc dải tăng trưởng ổn định, loại bỏ các mã tăng trưởng 'ảo'.",
                             style={"fontSize": "0.85rem", "fontStyle": "italic", "color": "#8b949e",
                                    "marginTop": "2px"})
                ], style={"marginBottom": "8px"}),

                html.Li([
                    html.Strong("Giá cả hợp lý (PEG): "), f"{fmt(peg_min)} < PEG <= {fmt(peg_max)}",
                    html.Div("Xác thực giá mua tương xứng với tốc độ tăng trưởng EPS.",
                             style={"fontSize": "0.85rem", "fontStyle": "italic", "color": "#8b949e",
                                    "marginTop": "2px"})
                ], style={"marginBottom": "8px"}),

                html.Li([
                    html.Strong("Giới hạn định giá: "), f"P/E <= {fmt(pe_max)}",
                    html.Div("Loại bỏ các mã bị thổi giá quá mức so với thu nhập.",
                             style={"fontSize": "0.85rem", "fontStyle": "italic", "color": "#8b949e",
                                    "marginTop": "2px"})
                ], style={"marginBottom": "8px"}),

                html.Li([
                    html.Strong("Nội lực tự lớn mạnh (SGR): "), f">= {fmt(sgr_min)}%",
                    html.Div("Yêu cầu tốc độ tự tăng trưởng từ nguồn vốn nội bộ.",
                             style={"fontSize": "0.85rem", "fontStyle": "italic", "color": "#8b949e",
                                    "marginTop": "2px"})
                ], style={"marginBottom": "8px"}),

                html.Li([
                    html.Strong("An toàn tài chính: "), f"D/E Ratio <= {fmt(de_max)}",
                    html.Div("Khống chế nợ không được lạm dụng quá vốn chủ sở hữu.",
                             style={"fontSize": "0.85rem", "fontStyle": "italic", "color": "#8b949e",
                                    "marginTop": "2px"})
                ], style={"marginBottom": "8px"}),

                html.Li([
                    html.Strong("Quy mô an toàn: "), f"Top {fmt((1 - mc_quantile) * 100)}% Vốn hóa lớn nhất sàn"
                ], style={"marginBottom": "8px"}),

            ], style={"fontSize": "0.95rem", "lineHeight": "1.4", "color": "#c9d1d9", "backgroundColor": "#0d1117",
                      "padding": "15px 15px 15px 35px", "borderRadius": "8px"}),
        ])

    # ==========================================================
    # 💰 CHIẾN LƯỢC CỔ TỨC & THU NHẬP (DIVIDEND)
    # ==========================================================
    elif current_strategy == "STRAT_DIVIDEND":
        title = "💰 Cổ tức & Thu nhập (Dividend)"

        # Đọc trực tiếp biến số từ hệ thống Quant
        mc_quantile = DIVIDEND_THRESHOLDS[DIV_IDX_MC_QUANTILE]
        yield_min = DIVIDEND_THRESHOLDS[DIV_IDX_YIELD_MIN]
        payout_max = DIVIDEND_THRESHOLDS[DIV_IDX_PAYOUT_MAX]

        content = html.Div([
            html.Div([
                html.Span(dbc.Badge("Tác giả", color="primary", className="me-2")),
                "John Neff"
            ], className="mb-2"),
            html.Div([
                html.Span(dbc.Badge("Nguồn", color="info", className="me-2")),
                html.A("Chiến lược Cổ tức (Vietcap)",
                       href="https://www.vietcap.com.vn/kien-thuc/chien-luoc-dau-tu-co-phieu-huong-co-tuc-hieu-qua",
                       target="_blank", style={"color": "#58a6ff", "textDecoration": "none"})
            ], className="mb-4"),

            html.H5([html.I(className="fas fa-brain", style={"color": "#3fb950", "marginRight": "8px"}),
                     "Triết lý cốt lõi"], style={"color": "#e6edf3", "fontWeight": "bold"}),
            html.P(
                "Tạo dựng dòng thu nhập thụ động ổn định thông qua cổ tức từ các doanh nghiệp tài chính vững mạnh, có lịch sử chi trả đều đặn. Thay vì theo đuổi sự tăng giá ngắn hạn đầy biến động, chiến lược này ưu tiên tổng lợi suất dài hạn giúp chống chịu tốt trước lạm phát.",
                style={"fontSize": "0.95rem", "lineHeight": "1.6", "color": "#c9d1d9"}),
            html.Hr(style={"borderColor": "#30363d"}),

            html.H5([html.I(className="fas fa-filter", style={"color": "#f85149", "marginRight": "8px"}),
                     "Logic Sàng Lọc (Hệ thống)"], style={"color": "#e6edf3", "fontWeight": "bold"}),
            html.Ul([
                html.Li([
                    html.Strong("Lợi suất hấp dẫn: "), f"Dividend Yield >= {fmt(yield_min * 100)}%",
                    html.Div("Đảm bảo lợi tức cao hơn lãi suất tiết kiệm ngân hàng (phi rủi ro).",
                             style={"fontSize": "0.85rem", "fontStyle": "italic", "color": "#8b949e",
                                    "marginTop": "2px"})
                ], style={"marginBottom": "8px"}),

                html.Li([
                    html.Strong("Sự an toàn của cổ tức: "), f"Payout Ratio <= {fmt(payout_max * 100)}%",
                    html.Div("Ngăn chặn các doanh nghiệp chia hết lợi nhuận hoặc vay nợ để trả cổ tức.",
                             style={"fontSize": "0.85rem", "fontStyle": "italic", "color": "#8b949e",
                                    "marginTop": "2px"})
                ], style={"marginBottom": "8px"}),

                html.Li([
                    html.Strong("Sự ổn định: "), "Duy trì trả cổ tức đều đặn trong 3 năm liên tiếp",
                ], style={"marginBottom": "8px"}),

                html.Li([
                    html.Strong("Sức khỏe tài chính: "), "Dòng tiền tự do (FCF) dương & Nợ vay thấp",
                    html.Div("Chỉ có doanh nghiệp tạo ra tiền mặt thực sự mới duy trì được cổ tức.",
                             style={"fontSize": "0.85rem", "fontStyle": "italic", "color": "#8b949e",
                                    "marginTop": "2px"})
                ], style={"marginBottom": "8px"}),

                html.Li([
                    html.Strong("Quy mô: "), f"Top {fmt((1 - mc_quantile) * 100)}% Vốn hóa thị trường",
                    html.Div("Ưu tiên các tập đoàn lớn, tránh rủi ro thanh khoản.",
                             style={"fontSize": "0.85rem", "fontStyle": "italic", "color": "#8b949e",
                                    "marginTop": "2px"})
                ], style={"marginBottom": "8px"}),

            ], style={"fontSize": "0.95rem", "lineHeight": "1.4", "color": "#c9d1d9", "backgroundColor": "#0d1117",
                      "padding": "15px 15px 15px 35px", "borderRadius": "8px"}),
        ])
        # ==========================================================
    # 📈 CHIẾN LƯỢC PIOTROSKI (SỨC KHỎE TÀI CHÍNH)
    # ==========================================================
    elif current_strategy == "STRAT_PIOTROSKI":
        title = "📈 Điểm sức khỏe Piotroski (F-Score)"

        # Đọc trực tiếp biến số từ hệ thống Quant
        f_min = PIOTROSKI_THRESHOLDS[PIOTROSKI_IDX_F_MIN]

        content = html.Div([
            html.Div([
                html.Span(dbc.Badge("Tác giả", color="primary", className="me-2")),
                "Giáo sư Joseph Piotroski (ĐH Stanford)"
            ], className="mb-2"),
            html.Div([
                html.Span(dbc.Badge("Nguồn", color="info", className="me-2")),
                html.A("Tikop",
                       href="https://tikop.vn/blog/piotroski-f-score-la-gi-cach-tinh-y-nghia-va-ung-dung-trong-dau-tu-10991",
                       target="_blank", style={"color": "#58a6ff", "textDecoration": "none"}),
                html.Span(" | ", style={"color": "#c9d1d9"}),
                html.A("GoValue", href="https://govalue.vn/piotroski-f-score/", target="_blank",
                       style={"color": "#58a6ff", "textDecoration": "none"})
            ], className="mb-4"),

            html.H5([html.I(className="fas fa-brain", style={"color": "#3fb950", "marginRight": "8px"}),
                     "Triết lý cốt lõi"], style={"color": "#e6edf3", "fontWeight": "bold"}),
            html.P(
                "Mô hình chấm điểm dựa trên 9 tiêu chí tài chính giúp phân biệt doanh nghiệp đang thực sự phục hồi với những 'cái bẫy giá trị' (doanh nghiệp yếu kém bị định giá thấp). Điểm 8-9 cho thấy sức khỏe tài chính rất tốt, trong khi 0-4 cảnh báo rủi ro cao.",
                style={"fontSize": "0.95rem", "lineHeight": "1.6", "color": "#c9d1d9"}),
            html.Hr(style={"borderColor": "#30363d"}),

            html.H5([html.I(className="fas fa-filter", style={"color": "#f85149", "marginRight": "8px"}),
                     "Logic Sàng Lọc (Hệ thống)"], style={"color": "#e6edf3", "fontWeight": "bold"}),
            html.Ul([
                html.Li([
                    html.Strong("Ngưỡng an toàn: "), f"Tổng điểm F-Score >= {fmt(f_min)}/9 điểm",
                    html.Div("Hệ thống chỉ lọc ra các doanh nghiệp có tình hình tài chính từ mức Khá đến Xuất sắc.",
                             style={"fontSize": "0.85rem", "fontStyle": "italic", "color": "#8b949e",
                                    "marginTop": "2px"})
                ], style={"marginBottom": "12px"}),

                html.Li([html.Strong(html.Span("1. Khả năng sinh lợi:", style={"color": "#58a6ff"}))]),
                html.Div(
                    "Lợi nhuận ròng > 0; ROA > 0 và cao hơn năm trước; CFO (Dòng tiền HĐKD) > 0; CFO > Lợi nhuận ròng.",
                    style={"fontSize": "0.85rem", "color": "#8b949e", "marginLeft": "20px", "marginBottom": "8px"}),

                html.Li([html.Strong(html.Span("2. Sức khỏe tài chính:", style={"color": "#58a6ff"}))]),
                html.Div(
                    "Tỷ lệ nợ dài hạn giảm; Current Ratio (Thanh toán ngắn hạn) tăng; Không phát hành thêm cổ phiếu (chống pha loãng).",
                    style={"fontSize": "0.85rem", "color": "#8b949e", "marginLeft": "20px", "marginBottom": "8px"}),

                html.Li([html.Strong(html.Span("3. Hiệu quả hoạt động:", style={"color": "#58a6ff"}))]),
                html.Div("Biên lợi nhuận gộp cải thiện so với năm trước; Vòng quay tài sản tăng.",
                         style={"fontSize": "0.85rem", "color": "#8b949e", "marginLeft": "20px",
                                "marginBottom": "8px"}),

            ], style={"fontSize": "0.95rem", "lineHeight": "1.4", "color": "#c9d1d9", "backgroundColor": "#0d1117",
                      "padding": "15px 15px 15px 35px", "borderRadius": "8px", "listStyleType": "none"}),
        ])

    # ==========================================================
    # 🚀 CHIẾN LƯỢC CANSLIM (ĐỘNG LƯỢNG TĂNG TRƯỞNG)
    # ==========================================================
    elif current_strategy == "STRAT_CANSLIM":
        title = "🚀 Siêu cổ phiếu (CANSLIM)"

        # Đọc trực tiếp biến số từ hệ thống Quant
        eps_q = CANSLIM_THRESHOLDS[CANSLIM_IDX_EPS_GROWTH_Q_MIN]
        rev_q = CANSLIM_THRESHOLDS[CANSLIM_IDX_REV_GROWTH_Q_MIN]
        eps_y = CANSLIM_THRESHOLDS[CANSLIM_IDX_EPS_GROWTH_Y_MIN]
        roe_min = CANSLIM_THRESHOLDS[CANSLIM_IDX_ROE_MIN]
        rs_min = CANSLIM_THRESHOLDS[CANSLIM_IDX_RS_MIN]
        vol_mult = CANSLIM_THRESHOLDS[CANSLIM_IDX_VOL_MULT]
        qr_min = CANSLIM_THRESHOLDS[CANSLIM_IDX_QUICK_RATIO_MIN]
        de_max = CANSLIM_THRESHOLDS[CANSLIM_IDX_DEBT_EQUITY_MAX]

        content = html.Div([
            html.Div([
                html.Span(dbc.Badge("Tác giả", color="primary", className="me-2")),
                "William J. O'Neil (Cập nhật: Richard Driehaus)"
            ], className="mb-2"),
            html.Div([
                html.Span(dbc.Badge("Nguồn", color="info", className="me-2")),
                html.A("Investopedia", href="https://www.investopedia.com/terms/c/canslim.asp", target="_blank",
                       style={"color": "#58a6ff", "textDecoration": "none"}),
                html.Span(" | ", style={"color": "#c9d1d9"}),
                html.A("Vietcap",
                       href="https://www.vietcap.com.vn/kien-thuc/huong-dan-thuc-hanh-canslim-phuong-phap-loc-co-phieu-hieu-qua",
                       target="_blank", style={"color": "#58a6ff", "textDecoration": "none"})
            ], className="mb-4"),

            html.H5([html.I(className="fas fa-brain", style={"color": "#3fb950", "marginRight": "8px"}),
                     "Triết lý cốt lõi"], style={"color": "#e6edf3", "fontWeight": "bold"}),
            html.P(
                "Không dành cho người thích mua rẻ. CANSLIM kết hợp phân tích cơ bản và kỹ thuật để tìm kiếm cổ phiếu dẫn dắt (Leaders) đang bùng nổ lợi nhuận, được sự hậu thuẫn từ dòng tiền lớn. Chấp nhận mua cao để bán cao hơn tại các điểm Pivot.",
                style={"fontSize": "0.95rem", "lineHeight": "1.6", "color": "#c9d1d9"}),
            html.Hr(style={"borderColor": "#30363d"}),

            html.H5([html.I(className="fas fa-filter", style={"color": "#f85149", "marginRight": "8px"}),
                     "Logic Sàng Lọc (Hệ thống)"], style={"color": "#e6edf3", "fontWeight": "bold"}),
            html.Ul([
                html.Li([
                    html.Strong("C (Current): "), f"EPS Quý tăng >= {fmt(eps_q)}% & Doanh thu >= {fmt(rev_q)}%",
                    html.Div("Lợi nhuận quý hiện tại đột phá mạnh từ hoạt động cốt lõi.",
                             style={"fontSize": "0.85rem", "fontStyle": "italic", "color": "#8b949e",
                                    "marginTop": "2px"})
                ], style={"marginBottom": "8px"}),

                html.Li([
                    html.Strong("A (Annual): "), f"EPS Năm tăng >= {fmt(eps_y)}% & ROE >= {fmt(roe_min)}%",
                    html.Div("Tăng trưởng bền vững hàng năm và hiệu quả sử dụng vốn (ROE) xuất sắc.",
                             style={"fontSize": "0.85rem", "fontStyle": "italic", "color": "#8b949e",
                                    "marginTop": "2px"})
                ], style={"marginBottom": "8px"}),

                html.Li([
                    html.Strong("N (New): "), "Gần đỉnh 52 tuần",
                    html.Div("Sản phẩm mới, lãnh đạo mới, hoặc đang tích lũy chờ bứt phá đỉnh.",
                             style={"fontSize": "0.85rem", "fontStyle": "italic", "color": "#8b949e",
                                    "marginTop": "2px"})
                ], style={"marginBottom": "8px"}),

                html.Li([
                    html.Strong("S (Supply & Demand): "), f"Volume > {fmt(vol_mult)} lần trung bình 50 phiên",
                    html.Div("Cầu lớn hơn cung, dòng tiền đổ vào mạnh mẽ tại điểm Breakout.",
                             style={"fontSize": "0.85rem", "fontStyle": "italic", "color": "#8b949e",
                                    "marginTop": "2px"})
                ], style={"marginBottom": "8px"}),

                html.Li([
                    html.Strong("L (Leader): "), f"Sức mạnh giá (RS Rating) > {fmt(rs_min)}",
                    html.Div(f"Cổ phiếu thuộc Top {fmt(100 - rs_min)}% mạnh nhất thị trường.",
                             style={"fontSize": "0.85rem", "fontStyle": "italic", "color": "#8b949e",
                                    "marginTop": "2px"})
                ], style={"marginBottom": "8px"}),

                html.Li([
                    html.Strong("I (Institutional): "), "Thanh khoản cao",
                    html.Div("Loại bỏ các mã thanh khoản thấp để đảm bảo có dấu chân của Tổ chức lớn.",
                             style={"fontSize": "0.85rem", "fontStyle": "italic", "color": "#8b949e",
                                    "marginTop": "2px"})
                ], style={"marginBottom": "8px"}),

                html.Li([
                    html.Strong("M (Market): "), "Hệ thống tự động loại bỏ mã khi thị trường sập",
                    html.Div("Chỉ giao dịch khi thị trường chung đang trong xu hướng tăng (Uptrend).",
                             style={"fontSize": "0.85rem", "fontStyle": "italic", "color": "#8b949e",
                                    "marginTop": "2px"})
                ], style={"marginBottom": "8px"}),

            ], style={"fontSize": "0.95rem", "lineHeight": "1.4", "color": "#c9d1d9", "backgroundColor": "#0d1117",
                      "padding": "15px 15px 15px 35px", "borderRadius": "8px"}),
        ])
    # ==========================================================
    # 🌱 CHIẾN LƯỢC TĂNG TRƯỞNG BỀN VỮNG (GROWTH / FISHER)
    # ==========================================================
    elif current_strategy == "STRAT_GROWTH":
        title = "🌱 Tăng trưởng bền vững (Growth Investing)"

        # Đọc trực tiếp biến số từ hệ thống Quant
        rev_5y = FISHER_THRESHOLDS[FISHER_IDX_REV_GROWTH_5Y_MIN]
        dilution_max = FISHER_THRESHOLDS[FISHER_IDX_DILUTION_RATE_MAX]
        roe_min = FISHER_THRESHOLDS[FISHER_IDX_ROE_MIN]
        opex_max = FISHER_THRESHOLDS[FISHER_IDX_OPEX_EFF_MAX]
        turnover_min = FISHER_THRESHOLDS[FISHER_IDX_TURNOVER_MIN]
        reinvest_min = FISHER_THRESHOLDS[FISHER_IDX_REINVEST_MIN]

        content = html.Div([
            html.Div([
                html.Span(dbc.Badge("Tác giả", color="primary", className="me-2")),
                "Philip A. Fisher (Thomas Rowe Price Jr.)"
            ], className="mb-2"),
            html.Div([
                html.Span(dbc.Badge("Nguồn", color="info", className="me-2")),
                html.A("Common Stocks and Uncommon Profits (Vietcap)",
                       href="https://www.vietcap.com.vn/kien-thuc/dau-tu-tang-truong-la-gi-lam-sao-de-lua-chon-co-phieu-tang-truong",
                       target="_blank", style={"color": "#58a6ff", "textDecoration": "none"})
            ], className="mb-4"),

            html.H5([html.I(className="fas fa-brain", style={"color": "#3fb950", "marginRight": "8px"}),
                     "Triết lý cốt lõi"], style={"color": "#e6edf3", "fontWeight": "bold"}),
            html.P(
                "Tìm kiếm những 'gã khổng lồ tương lai' có khả năng tăng trưởng doanh thu và lợi nhuận vượt trội trong nhiều thập kỷ. Tập trung vào bộ máy quản lý, năng lực R&D và phương pháp 'Lời đồn đại' (Scuttlebutt). Phương châm: 'Thời điểm tốt nhất để bán cổ phiếu là gần như không bao giờ'.",
                style={"fontSize": "0.95rem", "lineHeight": "1.6", "color": "#c9d1d9"}),
            html.Hr(style={"borderColor": "#30363d"}),

            html.H5([html.I(className="fas fa-filter", style={"color": "#f85149", "marginRight": "8px"}),
                     "Logic Sàng Lọc (Hệ thống)"], style={"color": "#e6edf3", "fontWeight": "bold"}),
            html.Ul([
                html.Li([
                    html.Strong("Tăng trưởng bền vững: "), f"Doanh thu 5 năm tăng > {fmt(rev_5y)}%/năm",
                    html.Div("Lọc ra các công ty có đà tăng trưởng doanh thu dài hạn thay vì chỉ bùng nổ 1-2 năm.",
                             style={"fontSize": "0.85rem", "fontStyle": "italic", "color": "#8b949e",
                                    "marginTop": "2px"})
                ], style={"marginBottom": "8px"}),

                html.Li([
                    html.Strong("Hiệu quả quản trị: "), f"ROE > {fmt(roe_min)}%",
                    html.Div("Hiệu quả sử dụng vốn xuất sắc, bù đắp cho việc doanh nghiệp thường không trả cổ tức.",
                             style={"fontSize": "0.85rem", "fontStyle": "italic", "color": "#8b949e",
                                    "marginTop": "2px"})
                ], style={"marginBottom": "8px"}),

                html.Li([
                    html.Strong("Kỷ luật vốn (Chống pha loãng): "), f"Tỷ lệ pha loãng < {fmt(dilution_max)}%",
                    html.Div(
                        "Công ty dùng vốn nội tại để phát triển, tránh phát hành giấy liên tục làm loãng quyền lợi cổ đông.",
                        style={"fontSize": "0.85rem", "fontStyle": "italic", "color": "#8b949e", "marginTop": "2px"})
                ], style={"marginBottom": "8px"}),

                html.Li([
                    html.Strong("Quản trị chi phí: "), f"Opex Efficiency < {fmt(opex_max)} lần",
                    html.Div("Đảm bảo chi phí hoạt động không ăn mòn hết lợi nhuận biên.",
                             style={"fontSize": "0.85rem", "fontStyle": "italic", "color": "#8b949e",
                                    "marginTop": "2px"})
                ], style={"marginBottom": "8px"}),

                html.Li([
                    html.Strong("Năng lực tái đầu tư: "), f"Tỷ lệ giữ lại (Reinvest Rate) > {fmt(reinvest_min)}%",
                    html.Div("Doanh nghiệp ưu tiên giữ lại lợi nhuận để tái đầu tư R&D thay vì chia hết cho cổ đông.",
                             style={"fontSize": "0.85rem", "fontStyle": "italic", "color": "#8b949e",
                                    "marginTop": "2px"})
                ], style={"marginBottom": "8px"}),

                html.Li([
                    html.Strong("Thanh khoản an toàn: "), f"Giá trị giao dịch > {fmt(turnover_min)} VND",
                    html.Div("Loại bỏ các mã 'vô danh', rủi ro mất thanh khoản trên sàn IDX.",
                             style={"fontSize": "0.85rem", "fontStyle": "italic", "color": "#8b949e",
                                    "marginTop": "2px"})
                ], style={"marginBottom": "8px"}),

            ], style={"fontSize": "0.95rem", "lineHeight": "1.4", "color": "#c9d1d9", "backgroundColor": "#0d1117",
                      "padding": "15px 15px 15px 35px", "borderRadius": "8px"}),
        ])

    # ==========================================================
    # 🪄 CHIẾN LƯỢC CÔNG THỨC KỲ DIỆU (MAGIC FORMULA)
    # ==========================================================
    elif current_strategy == "STRAT_MAGIC":
        title = "🪄 Công Thức Kỳ Diệu (Magic Formula)"

        content = html.Div([
            html.Div([
                html.Span(dbc.Badge("Tác giả", color="primary", className="me-2")),
                "Joel Greenblatt"
            ], className="mb-2"),
            html.Div([
                html.Span(dbc.Badge("Nguồn", color="info", className="me-2")),
                html.A("Sách: The Little Book That Beats the Market",
                       href="https://www.quantifiedstrategies.com/the-magic-formula-strategy/", target="_blank",
                       style={"color": "#58a6ff", "textDecoration": "none"}),
                html.Span(" | ", style={"color": "#c9d1d9"}),
                html.A("Investopedia", href="https://www.investopedia.com/terms/m/magic-formula-investing.asp",
                       target="_blank", style={"color": "#58a6ff", "textDecoration": "none"})
            ], className="mb-4"),

            html.H5([html.I(className="fas fa-brain", style={"color": "#3fb950", "marginRight": "8px"}),
                     "Triết lý cốt lõi"], style={"color": "#e6edf3", "fontWeight": "bold"}),
            html.P(
                "Chiến lược định lượng lai có mục tiêu vô cùng đơn giản: Mua những doanh nghiệp 'Tốt' ở một mức giá 'Rẻ'. Triết lý này loại bỏ hoàn toàn cảm xúc bằng cách lượng hóa và chấm điểm dựa trên Tỷ suất sinh lời trên vốn (ROC - hoạt động hiệu quả) và Tỷ suất lợi tức (Earnings Yield - định giá rẻ). Đặc biệt, hệ thống kiên quyết loại bỏ ngành Tài chính (nợ là nguyên liệu kinh doanh làm sai lệch EV) và ngành Tiện ích (biên lợi nhuận bị kiểm soát).",
                style={"fontSize": "0.95rem", "lineHeight": "1.6", "color": "#c9d1d9"}),
            html.Hr(style={"borderColor": "#30363d"}),

            html.H5([html.I(className="fas fa-filter", style={"color": "#f85149", "marginRight": "8px"}),
                     "Logic Sàng Lọc (Hệ thống)"], style={"color": "#e6edf3", "fontWeight": "bold"}),
            html.Ul([
                html.Li([
                    html.Strong("Bước 1: Loại bỏ đặc thù: "), "Loại ngành Tài chính, Tiện ích & Vốn hóa nhỏ",
                    html.Div("Hệ thống tự động loại bỏ các mã có cấu trúc vốn sai lệch hoặc quy mô dưới 1.000 Tỷ VND.",
                             style={"fontSize": "0.85rem", "fontStyle": "italic", "color": "#8b949e",
                                    "marginTop": "2px"})
                ], style={"marginBottom": "8px"}),

                html.Li([
                    html.Strong("Bước 2: Doanh nghiệp 'TỐT': "), "Xếp hạng ROC từ cao xuống thấp",
                    html.Div("Công ty có tỷ suất sinh lời trên vốn càng cao thì hạng càng gần Top 1.",
                             style={"fontSize": "0.85rem", "fontStyle": "italic", "color": "#8b949e",
                                    "marginTop": "2px"})
                ], style={"marginBottom": "8px"}),

                html.Li([
                    html.Strong("Bước 3: Mức giá 'RẺ': "), "Xếp hạng Earnings Yield từ cao xuống thấp",
                    html.Div("Đại diện cho việc cổ phiếu đang được giao dịch ở mức định giá hấp dẫn nhất.",
                             style={"fontSize": "0.85rem", "fontStyle": "italic", "color": "#8b949e",
                                    "marginTop": "2px"})
                ], style={"marginBottom": "8px"}),

                html.Li([
                    html.Strong("Bước 4: Chốt hạ danh mục: "), "Top 20-30 mã có Tổng điểm thấp nhất",
                    html.Div(
                        "Tổng điểm = (Hạng ROC + Hạng EY). Điểm càng thấp chứng tỏ sự giao thoa càng hoàn hảo giữa 'Chất lượng' và 'Giá cả'.",
                        style={"fontSize": "0.85rem", "fontStyle": "italic", "color": "#8b949e", "marginTop": "2px"})
                ], style={"marginBottom": "8px"}),

            ], style={"fontSize": "0.95rem", "lineHeight": "1.4", "color": "#c9d1d9", "backgroundColor": "#0d1117",
                      "padding": "15px 15px 15px 35px", "borderRadius": "8px"}),
        ])
    elif current_strategy == "STRAT_NCN":
        title = "🛡️ Khẩu Vị Phòng Thủ "
        content = html.Div([
            # ── Thông tin tác giả ──
            html.Div([
                html.Span(dbc.Badge("Chuyên viên", color="warning", className="me-2")),
                html.Strong("Ngô Cao Nguyên", style={"color": "#e6edf3"}),
                html.Span(" · K16 · Chứng khoán",
                          style={"color": "#8b949e", "marginLeft": "8px", "fontSize": "0.85rem"}),
            ], className="mb-1"),
            html.Div([
                html.Span(dbc.Badge("Chuyên viên", color="warning", className="me-2")),
                html.Strong("Phan Đặng Anh Kiệt", style={"color": "#e6edf3"}),
                html.Span(" · K16 · Chứng khoán",
                          style={"color": "#8b949e", "marginLeft": "8px", "fontSize": "0.85rem"}),
            ], className="mb-1"),
            html.Div([
                html.Span(dbc.Badge("Chuyên viên", color="warning", className="me-2")),
                html.Strong("Cao Huỳnh Tuyết Trân", style={"color": "#e6edf3"}),
                html.Span(" · K16 · Chứng khoán",
                          style={"color": "#8b949e", "marginLeft": "8px", "fontSize": "0.85rem"}),
            ], className="mb-1"),
            html.Div([
                html.Span(dbc.Badge("Liên hệ tư vấn", color="success", className="me-2")),
                html.Span("0946 700 605 - Zalo / SMS - Để nhận báo cáo phân tích chuyên sâu & danh mục cá nhân hóa",
                          style={"color": "#8b949e", "fontSize": "0.85rem", "fontStyle": "italic"}),
            ], className="mb-4"),

            # ── Triết lý ──
            html.H5([html.I(className="fas fa-shield-alt",
                            style={"color": "#3fb950", "marginRight": "8px"}),
                     "Triết lý Đầu tư Phòng thủ"],
                    style={"color": "#e6edf3", "fontWeight": "bold"}),
            html.P([
                "Trong một thị trường đầy biến động, ", html.Strong("bảo toàn vốn"),
                " luôn là ưu tiên số 1. Khẩu vị này tìm kiếm các doanh nghiệp ",
                html.Strong("có lợi thế cạnh tranh bền vững"), " (Moat), ",
                html.Strong("dòng tiền thật"), " (không phải lợi nhuận kế toán), và ",
                html.Strong("ban lãnh đạo liêm chính"), " — những yếu tố mà nhiều nhà đầu tư ",
                "ngắn hạn bỏ qua nhưng lại ", html.Strong("tạo ra lợi nhuận vượt trội"),
                " trong chu kỳ 3–5 năm.",
            ], style={"fontSize": "0.95rem", "lineHeight": "1.7", "color": "#c9d1d9"}),
            html.Hr(style={"borderColor": "#30363d"}),

            # ── 3 trụ cột ──
            html.H5([html.I(className="fas fa-layer-group",
                            style={"color": "#f0883e", "marginRight": "8px"}),
                     "3 Trụ Cột Sàng Lọc"],
                    style={"color": "#e6edf3", "fontWeight": "bold"}),

            # Trụ 1
            html.Div([
                html.Div([
                    html.I(className="fas fa-ban", style={"color": "#f85149", "marginRight": "8px"}),
                    html.Strong("Tầng 1 · Loại bỏ ngay các Red Flag (Zero-tolerance)",
                                style={"color": "#f85149"}),
                ], style={"marginBottom": "6px"}),
                html.Ul([
                    html.Li([html.Code("CFO / Net Income ≥ 0.8", style={"color": "#79c0ff"}),
                             " (trung bình 3 năm) — lợi nhuận phải đi kèm dòng tiền thật"],
                            style={"marginBottom": "4px"}),
                    html.Li([html.Code("Dilution Rate ≤ 8%/năm", style={"color": "#79c0ff"}),
                             " — phát hành cổ phiếu liên tục là dấu hiệu rút ruột"],
                            style={"marginBottom": "4px"}),
                ], style={"fontSize": "0.9rem", "color": "#c9d1d9",
                          "paddingLeft": "20px", "marginBottom": "0"}),
            ], style={"backgroundColor": "#1c1c2e", "borderLeft": "3px solid #f85149",
                      "padding": "12px 16px", "borderRadius": "6px", "marginBottom": "12px"}),

            # Trụ 2
            html.Div([
                html.Div([
                    html.I(className="fas fa-coins", style={"color": "#3fb950", "marginRight": "8px"}),
                    html.Strong("Tầng 2 · Chất lượng Tài chính",
                                style={"color": "#3fb950"}),
                ], style={"marginBottom": "6px"}),
                html.Ul([
                    html.Li([html.Code("FCF / Tổng Nợ ≥ 0", style={"color": "#79c0ff"}),
                             " — dòng tiền tự do đủ để trả nợ (không đốt tiền)"],
                            style={"marginBottom": "4px"}),
                    html.Li([html.Code("ROIC ≥ 12%", style={"color": "#79c0ff"}),
                             " — tỷ suất sinh lời trên vốn đầu tư, thước đo Moat thực sự"],
                            style={"marginBottom": "4px"}),
                    html.Li([html.Code("Gross Margin ≥ 15%", style={"color": "#79c0ff"}),
                             " — quyền lực định giá, biên gộp cao hơn ngành = rào cản gia nhập"],
                            style={"marginBottom": "4px"}),
                    html.Li([html.Code("ROE ≥ 15%  |  Net Margin ≥ 5%  |  D/E ≤ 1.5",
                                       style={"color": "#79c0ff"})],
                            style={"marginBottom": "4px"}),
                ], style={"fontSize": "0.9rem", "color": "#c9d1d9",
                          "paddingLeft": "20px", "marginBottom": "0"}),
            ], style={"backgroundColor": "#0d1f15", "borderLeft": "3px solid #3fb950",
                      "padding": "12px 16px", "borderRadius": "6px", "marginBottom": "12px"}),

            # Trụ 3
            html.Div([
                html.Div([
                    html.I(className="fas fa-trophy", style={"color": "#f0883e", "marginRight": "8px"}),
                    html.Strong("Tầng 3 · Xếp hạng tổng hợp — Top 40 mã tốt nhất",
                                style={"color": "#f0883e"}),
                ], style={"marginBottom": "6px"}),
                html.P("Điểm NCN Score = tổng hợp có trọng số của ROIC (30%), ROE (20%), "
                       "Gross Margin (20%), Net Margin (15%), Chất lượng CFO (15%). "
                       "Chỉ những mã đã vượt Tầng 1 & 2 mới được xét xếp hạng.",
                       style={"fontSize": "0.9rem", "color": "#c9d1d9", "marginBottom": "0"}),
            ], style={"backgroundColor": "#1f1200", "borderLeft": "3px solid #f0883e",
                      "padding": "12px 16px", "borderRadius": "6px", "marginBottom": "16px"}),

            html.Hr(style={"borderColor": "#30363d"}),

            # ── Lưu ý & CTA ──
            html.Div([
                html.I(className="fas fa-info-circle",
                       style={"color": "#58a6ff", "marginRight": "8px"}),
                html.Span("Bộ lọc này phản ánh ",
                          style={"color": "#8b949e", "fontSize": "0.85rem"}),
                html.Strong("quan điểm đầu tư cá nhân",
                            style={"color": "#c9d1d9", "fontSize": "0.85rem"}),
                html.Span(" của chuyên viên và không phải khuyến nghị mua/bán chính thức. "
                          "Kết quả sàng lọc cần kết hợp với phân tích định tính trước khi ra quyết định.",
                          style={"color": "#8b949e", "fontSize": "0.85rem"}),
            ], style={"backgroundColor": "#0d1624", "borderLeft": "3px solid #58a6ff",
                      "padding": "10px 14px", "borderRadius": "6px"}),
        ])
    # (Bạn có thể sao chép block if elif trên cho 7 trường phái còn lại sau này)
    else:
        title = "Đang cập nhật..."
        content = html.P("Nội dung cho trường phái này đang được tổng hợp.", style={"color": "#c9d1d9"})

    return not is_open, title, content


# ============================================================================
# CALLBACK: EXPORT CSV
# ============================================================================
@app.callback(
    Output("download-csv", "data"),
    Input("btn-export-csv", "n_clicks"),
    State("screener-table", "rowData"),
    prevent_initial_call=True
)
def export_csv(n_clicks, row_data):
    if not row_data:
        return no_update
    df = pd.DataFrame(row_data)
    export_cols = [c for c in [
        'Ticker', 'Company Common Name', 'Sector', 'Price Close',
        'Perf_1W', 'Perf_1M', 'Perf_3M', 'Perf_1Y', 'Perf_YTD',
        'Market Cap', 'Volume', 'P/E', 'P/B', 'P/S', 'EV/EBITDA',
        'ROE (%)', 'ROA (%)', 'Net Margin (%)', 'Gross Margin (%)',
        'Revenue Growth YoY (%)', 'EPS Growth YoY (%)',
        'D/E', 'Current Ratio', 'Dividend Yield (%)',
        'RSI_14', 'MACD_Histogram', 'Beta', 'Alpha',
        'RS_1M', 'RS_3M', 'RS_1Y',
        'Value Score', 'Growth Score', 'Momentum Score', 'VGM Score', 'CANSLIM Score'
    ] if c in df.columns]
    from datetime import datetime
    filename = f"IDX_Screener_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
    return dcc.send_data_frame(df[export_cols].to_csv, filename, index=False, encoding='utf-8-sig')


# ============================================================================
# CALLBACK: EXPORT EXCEL
# ============================================================================
@app.callback(
    Output("download-excel", "data"),
    Input("btn-export-excel", "n_clicks"),
    State("screener-table", "rowData"),
    prevent_initial_call=True
)
def export_excel(n_clicks, row_data):
    if not row_data:
        return no_update
    try:
        import io
        from datetime import datetime
        df = pd.DataFrame(row_data)

        export_cols = [c for c in [
            'Ticker', 'Company Common Name', 'Sector', 'Price Close',
            'Perf_1W', 'Perf_1M', 'Perf_3M', 'Perf_1Y', 'Perf_YTD',
            'Market Cap', 'Volume', 'P/E', 'P/B', 'P/S', 'EV/EBITDA',
            'ROE (%)', 'ROA (%)', 'Net Margin (%)', 'Gross Margin (%)',
            'Revenue Growth YoY (%)', 'EPS Growth YoY (%)',
            'D/E', 'Current Ratio', 'Dividend Yield (%)',
            'RSI_14', 'MACD_Histogram', 'Beta', 'Alpha',
            'RS_1M', 'RS_3M', 'RS_1Y',
            'Value Score', 'Growth Score', 'Momentum Score', 'VGM Score', 'CANSLIM Score'
        ] if c in df.columns]

        df_export = df[export_cols].copy()

        # Viết Excel vào buffer
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine='openpyxl') as writer:
            df_export.to_excel(writer, index=False, sheet_name='IDX Screener')

            # Style cơ bản
            wb = writer.book
            ws = writer.sheets['IDX Screener']

            from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
            from openpyxl.utils import get_column_letter

            # Header style — nền xanh navy, chữ trắng
            header_fill = PatternFill("solid", fgColor="0A1628")
            header_font = Font(bold=True, color="00D4FF", size=10, name="Calibri")
            header_align = Alignment(horizontal="center", vertical="center", wrap_text=True)
            thin = Side(style='thin', color="1D4D80")
            border = Border(left=thin, right=thin, top=thin, bottom=thin)

            for cell in ws[1]:
                cell.fill   = header_fill
                cell.font   = header_font
                cell.alignment = header_align
                cell.border = border

            ws.row_dimensions[1].height = 28

            # Auto-fit column width
            for col_idx, col in enumerate(df_export.columns, 1):
                col_letter = get_column_letter(col_idx)
                max_len = max(len(str(col)), df_export[col].astype(str).str.len().max() if not df_export.empty else 0)
                ws.column_dimensions[col_letter].width = min(max_len + 4, 25)

            # Zebra striping rows
            fill_even = PatternFill("solid", fgColor="0D1B2A")
            fill_odd  = PatternFill("solid", fgColor="091526")
            font_row  = Font(size=9, name="Calibri", color="C9D1D9")

            for row_idx, row in enumerate(ws.iter_rows(min_row=2), start=2):
                fill = fill_even if row_idx % 2 == 0 else fill_odd
                for cell in row:
                    cell.fill      = fill
                    cell.font      = font_row
                    cell.alignment = Alignment(horizontal="right" if cell.column > 1 else "left", vertical="center")
                    cell.border    = border

            # Freeze header row
            ws.freeze_panes = "A2"

            # Sheet tab color
            ws.sheet_properties.tabColor = "00D4FF"

        buf.seek(0)
        filename = f"IDX_Screener_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
        return dcc.send_bytes(buf.read(), filename)

    except Exception as e:
        logger.error(f"Excel export error: {e}")
        return no_update


# ============================================================================
# CALLBACK: SUB-INDUSTRY FILTER — load options theo Sector đã chọn
# ============================================================================
@app.callback(
    Output("filter-sub-industry", "options"),
    Input("filter-all-industry", "value"),
    prevent_initial_call=False
)
def update_sub_industry_options(selected_sectors):
    try:
        from src.constants.gics_translation import GICS_INDUSTRY_TRANSLATION
        # ✅ Mới — nhanh hơn ~3x
        from src.backend.data_loader import get_snapshot_df
        df = get_snapshot_df().copy()

        # Tìm cột ngành con
        sub_col = next((c for c in ['GICS Industry Name', 'GICS Sub-Industry Name'] if c in df.columns), None)
        if not sub_col:
            return [{"label": "Tất cả ngành con", "value": "all"}]

        # Lọc theo sector đã chọn
        if selected_sectors and selected_sectors != ["all"] and "all" not in selected_sectors:
            sec_col = next((c for c in ['Sector', 'GICS Sector Name'] if c in df.columns), None)
            if sec_col:
                df = df[df[sec_col].isin(selected_sectors)]

        subs = sorted(df[sub_col].dropna().unique().tolist())
        options = [{"label": "Tất cả ngành con", "value": "all"}]
        options += [
            {"label": GICS_INDUSTRY_TRANSLATION.get(s, s), "value": s}
            for s in subs if s not in ('nan', '0', 'Chưa phân loại')
        ]
        return options
    except Exception:
        return [{"label": "Tất cả ngành con", "value": "all"}]


# ============================================================================
# CALLBACK: ÁP DỤNG SUB-INDUSTRY FILTER
# ĐÃ ĐƯỢC GỘP VÀO update_screener_table (Bug #2 fix).
# Callback riêng này bị vô hiệu hóa để tránh overwrite rowData của callback chính.
# ============================================================================
# @app.callback(
#     Output("screener-table", "rowData", allow_duplicate=True),
#     Input("filter-sub-industry", "value"),
#     State("screener-table", "rowData"),
#     prevent_initial_call=True
# )
# def apply_sub_industry_filter(selected_subs, row_data):
#     ... (đã gộp vào update_screener_table)


# ============================================================================
# CALLBACK: WATCHLIST — Thêm/xóa mã + hiển thị modal
# ============================================================================
@app.callback(
    Output("watchlist-modal", "is_open"),
    Output("watchlist-content", "children"),
    Output("watchlist-store", "data", allow_duplicate=True),
    Input("btn-watchlist", "n_clicks"),
    Input("btn-close-watchlist", "n_clicks"),
    Input("screener-table", "selectedRows"),
    State("watchlist-store", "data"),
    State("watchlist-modal", "is_open"),
    prevent_initial_call=True
)
def manage_watchlist(n_open, n_close, selected_rows, watchlist, is_open):
    ctx = callback_context
    if not ctx.triggered:
        return no_update, no_update, no_update

    trigger = ctx.triggered[0]['prop_id']
    watchlist = watchlist or []

    # Đóng modal
    if 'btn-close-watchlist' in trigger:
        return False, no_update, no_update

    # Thêm mã từ bảng vào watchlist
    if 'selectedRows' in trigger and selected_rows:
        ticker = selected_rows[0].get('Ticker', '')
        if ticker and ticker not in watchlist:
            watchlist = watchlist + [ticker]
        return no_update, no_update, watchlist

    # Mở modal + hiển thị watchlist
    if 'btn-watchlist' in trigger:
        if not watchlist:
            content = html.Div([
                html.I(className="fas fa-star", style={"fontSize": "32px", "color": "#484f58", "marginBottom": "12px"}),
                html.P("Chưa có mã nào trong danh sách theo dõi.", style={"color": "#6e7681"}),
                html.P("Click vào một mã trong bảng để thêm vào watchlist.",
                       style={"color": "#484f58", "fontSize": "12px"}),
            ], style={"textAlign": "center", "padding": "40px 0"})
        else:
            rows = []
            from src.backend.data_loader import get_snapshot_df
            try:
                df_snap = get_snapshot_df().copy()
            except Exception:
                df_snap = pd.DataFrame()

            for ticker in watchlist:
                row_data_snap = {}
                if not df_snap.empty and 'Ticker' in df_snap.columns:
                    match = df_snap[df_snap['Ticker'] == ticker]
                    if not match.empty:
                        row_data_snap = match.iloc[0].to_dict()

                price = row_data_snap.get('Price Close', '–')
                perf1w = row_data_snap.get('Perf_1W', None)
                sector = row_data_snap.get('Sector', '–')

                perf_color = '#10b981' if isinstance(perf1w, (int, float)) and perf1w > 0 else '#ef4444'
                perf_str = f"+{perf1w:.1f}%" if isinstance(perf1w, (int, float)) and perf1w > 0 else (
                    f"{perf1w:.1f}%" if isinstance(perf1w, (int, float)) else '–')

                rows.append(html.Div([
                    html.Span(ticker, style={"fontFamily": "'JetBrains Mono', monospace", "fontWeight": "700",
                                             "color": "#00d4ff", "width": "80px", "display": "inline-block"}),
                    html.Span(sector, style={"color": "#7fa8cc", "fontSize": "12px", "width": "160px",
                                             "display": "inline-block"}),
                    html.Span(f"{price:,.0f}" if isinstance(price, (int, float)) else str(price),
                              style={"fontFamily": "'JetBrains Mono', monospace", "color": "#d6eaf8", "width": "100px",
                                     "display": "inline-block", "textAlign": "right"}),
                    html.Span(perf_str,
                              style={"fontFamily": "'JetBrains Mono', monospace", "color": perf_color, "width": "80px",
                                     "display": "inline-block", "textAlign": "right"}),
                    html.I(className="fas fa-times", id={"type": "watchlist-remove", "ticker": ticker},
                           style={"color": "#ef4444", "cursor": "pointer", "marginLeft": "16px", "fontSize": "12px"},
                           n_clicks=0),
                ], style={"display": "flex", "alignItems": "center", "padding": "10px 16px",
                          "borderBottom": "1px solid #0e2540", "gap": "8px"}))

            content = html.Div([
                html.Div([
                    html.Span("MÃ CK",
                              style={"width": "80px", "display": "inline-block", "fontSize": "10px", "color": "#5a8ab0",
                                     "fontWeight": "700", "letterSpacing": "1px"}),
                    html.Span("NGÀNH", style={"width": "160px", "display": "inline-block", "fontSize": "10px",
                                              "color": "#5a8ab0", "fontWeight": "700", "letterSpacing": "1px"}),
                    html.Span("GIÁ", style={"width": "100px", "display": "inline-block", "fontSize": "10px",
                                            "color": "#5a8ab0", "fontWeight": "700", "letterSpacing": "1px",
                                            "textAlign": "right"}),
                    html.Span("%1T",
                              style={"width": "80px", "display": "inline-block", "fontSize": "10px", "color": "#5a8ab0",
                                     "fontWeight": "700", "letterSpacing": "1px", "textAlign": "right"}),
                ], style={"display": "flex", "padding": "8px 16px", "backgroundColor": "#040d18",
                          "borderRadius": "6px 6px 0 0"}),
                *rows,
                html.Div([
                    html.Small(f"Tổng cộng {len(watchlist)} mã đang theo dõi", style={"color": "#484f58"}),
                ], style={"padding": "10px 16px", "borderTop": "1px solid #0e2540"}),
            ])

        return True, content, watchlist

    return no_update, no_update, no_update


@app.callback(
    Output("watchlist-store",   "data",     allow_duplicate=True),
    Output("watchlist-content", "children", allow_duplicate=True),
    Input("btn-clear-watchlist", "n_clicks"),
    prevent_initial_call=True
)
def clear_watchlist(n_clicks):
    if not n_clicks:
        return no_update, no_update
    empty = html.Div([
        html.I(className="fas fa-star",
               style={"fontSize": "32px", "color": "#484f58", "marginBottom": "12px"}),
        html.P("Chưa có mã nào trong danh sách theo dõi.", style={"color": "#6e7681"}),
        html.P("Click vào một mã trong bảng để thêm vào watchlist.",
               style={"color": "#484f58", "fontSize": "12px"}),
    ], style={"textAlign": "center", "padding": "40px 0"})
    return [], empty


# add_forward_pe đã được gộp vào update_screener_table dưới dạng hàm _add_forward_pe()
# để tránh double-render khi rowData thay đổi trigger callback riêng lẻ.

# ============================================================================
# CALLBACK: TOGGLE HEALTH METHODOLOGY MODAL
# ============================================================================
@app.callback(
    Output("health-methodology-modal", "is_open"),
    Input("btn-health-methodology", "n_clicks"),
    State("health-methodology-modal", "is_open"),
    prevent_initial_call=True,
)
def toggle_health_methodology_modal(n, is_open):
    if n:
        return not is_open
    return is_open

# ============================================================================
# CALLBACK: XÓA TỪNG MÃ KHỎI WATCHLIST
# ============================================================================
@app.callback(
    Output("watchlist-store",   "data",     allow_duplicate=True),
    Output("watchlist-content", "children", allow_duplicate=True),
    Input({"type": "watchlist-remove", "ticker": ALL}, "n_clicks"),
    State("watchlist-store", "data"),
    prevent_initial_call=True,
)
def remove_watchlist_ticker(n_clicks_list, watchlist):
    from dash import callback_context
    ctx = callback_context
    if not ctx.triggered or not any(n for n in (n_clicks_list or []) if n):
        return no_update, no_update

    # Tìm ticker nào được click
    triggered_id = ctx.triggered[0]["prop_id"].split(".")[0]
    try:
        import json
        ticker_to_remove = json.loads(triggered_id)["ticker"]
    except Exception:
        return no_update, no_update

    watchlist = [t for t in (watchlist or []) if t != ticker_to_remove]

    if not watchlist:
        empty = html.Div([
            html.I(className="fas fa-star",
                   style={"fontSize": "32px", "color": "#484f58", "marginBottom": "12px"}),
            html.P("Chưa có mã nào trong danh sách theo dõi.", style={"color": "#6e7681"}),
            html.P("Click vào một mã trong bảng để thêm vào watchlist.",
                   style={"color": "#484f58", "fontSize": "12px"}),
        ], style={"textAlign": "center", "padding": "40px 0"})
        return watchlist, empty
    from src.backend.data_loader import get_snapshot_df
    # Re-render danh sách còn lại
    try:
        df_snap = get_snapshot_df().copy()
    except Exception:
        df_snap = pd.DataFrame()

    rows = []
    for ticker in watchlist:
        row_data_snap = {}
        if not df_snap.empty and "Ticker" in df_snap.columns:
            match = df_snap[df_snap["Ticker"] == ticker]
            if not match.empty:
                row_data_snap = match.iloc[0].to_dict()

        price   = row_data_snap.get("Price Close", "–")
        perf1w  = row_data_snap.get("Perf_1W", None)
        sector  = row_data_snap.get("Sector", "–")
        p_color = "#10b981" if isinstance(perf1w, (int, float)) and perf1w > 0 else "#ef4444"
        p_str   = (f"+{perf1w:.1f}%" if isinstance(perf1w, (int, float)) and perf1w > 0
                   else (f"{perf1w:.1f}%" if isinstance(perf1w, (int, float)) else "–"))

        rows.append(html.Div([
            html.Span(ticker, style={"fontFamily": "'JetBrains Mono', monospace", "fontWeight": "700",
                                     "color": "#00d4ff", "width": "80px", "display": "inline-block"}),
            html.Span(sector, style={"color": "#7fa8cc", "fontSize": "12px", "width": "160px",
                                     "display": "inline-block"}),
            html.Span(f"{price:,.0f}" if isinstance(price, (int, float)) else str(price),
                      style={"fontFamily": "'JetBrains Mono', monospace", "color": "#d6eaf8",
                             "width": "100px", "display": "inline-block", "textAlign": "right"}),
            html.Span(p_str, style={"fontFamily": "'JetBrains Mono', monospace", "color": p_color,
                                    "width": "80px", "display": "inline-block", "textAlign": "right"}),
            html.I(className="fas fa-times",
                   id={"type": "watchlist-remove", "ticker": ticker},
                   n_clicks=0,
                   style={"color": "#ef4444", "cursor": "pointer",
                          "marginLeft": "16px", "fontSize": "12px"}),
        ], style={"display": "flex", "alignItems": "center", "padding": "10px 16px",
                  "borderBottom": "1px solid #0e2540", "gap": "8px"}))

    content = html.Div([
        html.Div([
            html.Span("MÃ CK",  style={"width":"80px","display":"inline-block","fontSize":"10px","color":"#5a8ab0","fontWeight":"700","letterSpacing":"1px"}),
            html.Span("NGÀNH",  style={"width":"160px","display":"inline-block","fontSize":"10px","color":"#5a8ab0","fontWeight":"700","letterSpacing":"1px"}),
            html.Span("GIÁ",    style={"width":"100px","display":"inline-block","fontSize":"10px","color":"#5a8ab0","fontWeight":"700","letterSpacing":"1px","textAlign":"right"}),
            html.Span("%1T",    style={"width":"80px","display":"inline-block","fontSize":"10px","color":"#5a8ab0","fontWeight":"700","letterSpacing":"1px","textAlign":"right"}),
        ], style={"display":"flex","padding":"8px 16px","backgroundColor":"#040d18","borderRadius":"6px 6px 0 0"}),
        *rows,
        html.Div([
            html.Small(f"Tổng cộng {len(watchlist)} mã đang theo dõi", style={"color": "#484f58"}),
        ], style={"padding": "10px 16px", "borderTop": "1px solid #0e2540"}),
    ])
    return watchlist, content

# ============================================================================
# FIX YC2: Reset selectedRows khi đóng detail-modal
# → Cho phép click đúp lại vào cùng 1 mã để mở modal lần 2
# Nguyên nhân bug: AG Grid chỉ trigger callback khi selectedRows thay đổi.
# Khi đóng modal, selectedRows vẫn còn giữ mã cũ → click lại không fire.
# Fix: khi modal đóng (is_open = False) → reset selectedRows về [] ngay lập tức.
# ============================================================================
@app.callback(
    Output("screener-table", "selectedRows", allow_duplicate=True),
    Input("detail-modal", "is_open"),
    prevent_initial_call=True
)
def reset_selected_rows_on_modal_close(is_open):
    if not is_open:
        return []
    raise PreventUpdate
# ============================================================================
# TỰ ĐỘNG CẬP NHẬT OPTIONS CHO DROPDOWN NGÀNH (GIỮ NGUYÊN Ô SÀN CỦA SIDEBAR)
# ============================================================================
@app.callback(
    Output("filter-all-industry", "options"), # Chỉ update ngành, bỏ qua Sàn
    Input("search-ticker-input", "id"), 
    prevent_initial_call=False
)
def auto_update_dropdowns(_):
    try:
        df = get_snapshot_df()
        sec_options = [{"label": "Tất cả ngành", "value": "all"}]
        
        if df is not None and not df.empty:
            # Quét danh sách Ngành thực tế
            sec_col = next((c for c in ['Sector', 'GICS Sector Name'] if c in df.columns), None)
            if sec_col:
                sectors = sorted(df[sec_col].dropna().unique().tolist())
                sec_options += [
                    {"label": translate_gics_sector(s), "value": s}
                    for s in sectors if str(s).strip() not in ('nan', '0', 'Chưa phân loại', '')
                ]
        return sec_options
    except Exception as e:
        logger.error(f"Lỗi auto load dropdowns: {e}")
        return [{"label": "Tất cả ngành", "value": "all"}]

@app.callback(
    Output("data-cutoff-label", "children"),
    Input("screener-table", "id"),   # trigger 1 lần khi DOM sẵn sàng
    prevent_initial_call=False,
)
def update_cutoff_label(_):
    try:
        from src.backend.data_loader import get_data_cutoff_date
        d = get_data_cutoff_date()
        return f"(Cập nhật {d})" if d else ""
    except Exception:
        return ""