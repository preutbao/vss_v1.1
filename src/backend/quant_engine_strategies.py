# src/backend/quant_engine_strategies.py
"""
Module tính toán chỉ số và áp dụng bộ lọc cho 8 chiến lược đầu tư.

Mỗi hàm calculate_*_metrics(df_snapshot, df_fin) nhận:
  - df_snapshot : DataFrame 1 dòng/ticker (đã merge giá + BCTC kỳ mới nhất)
                  → đây là df từ get_latest_snapshot()
  - df_fin      : DataFrame TOÀN BỘ lịch sử BCTC (nhiều dòng/ticker, có cột Date)
                  → load_financial_data('yearly')

Chiến lược:
  1. STRAT_VALUE      – Đầu tư giá trị (Graham)
  2. STRAT_TURNAROUND – Đầu tư phục hồi (Templeton)
  3. STRAT_QUALITY    – Đầu tư chất lượng (Munger / Terry Smith)
  4. STRAT_GARP       – GARP (Peter Lynch)
  5. STRAT_DIVIDEND   – Cổ tức & Thu nhập (John Neff)
  6. STRAT_PIOTROSKI  – F-Score (Piotroski)
  7. STRAT_CANSLIM    – CANSLIM (William O'Neil)
  8. STRAT_GROWTH     – Tăng trưởng bền vững (Philip Fisher)
"""

import pandas as pd
import numpy as np
import logging

logger = logging.getLogger(__name__)

# ===================== Thresholds / Filter parameters =====================
# Each strategy has a list of thresholds; indexes below document each position.

# VALUE thresholds (indexes)
VALUE_IDX_CURRENT_RATIO_MIN = 0
VALUE_IDX_EPS_GROWTH_5Y_MIN = 1
VALUE_IDX_PE_MAX = 2
VALUE_IDX_PB_MAX = 3
VALUE_IDX_DEBT_TO_WC_MAX = 4
VALUE_IDX_NET_INCOME_MIN = 5
VALUE_THRESHOLDS = [
    1.0,  # current_ratio >=
    0.0,  # eps_growth_5y >
    20.0,  # P/E <=
    2.5,  # P/B <=
    2.0,  # debt_to_wc <
    0.0,  # net_income >
]

# TURNAROUND thresholds
TURNAROUND_IDX_PE_HIST_NORM_MAX = 0
TURNAROUND_IDX_OPERATING_MARGIN_MIN = 1
TURNAROUND_IDX_PEG_MIN = 2
TURNAROUND_IDX_PEG_MAX = 3
TURNAROUND_THRESHOLDS = [
    0.9,  # pe_historical_norm <
    3.0,  # operating_margin >=
    0.1,  # peg >=
    1.2,  # peg <=
]

# QUALITY thresholds
QUALITY_IDX_ROE_MIN = 0
QUALITY_IDX_GROSS_MARGIN_MIN = 1
QUALITY_IDX_RE_GROWTH_MIN = 2
QUALITY_IDX_FCF_MARGIN_MIN = 3
QUALITY_THRESHOLDS = [
    12.0,  # ROE >=
    15.0,  # gross_margin >=
    5.0,  # re_growth >=
    0.0,  # fcf_margin >
]

# GARP thresholds
GARP_IDX_EPS_GROWTH_MIN = 0
GARP_IDX_EPS_GROWTH_MAX = 1
GARP_IDX_PE_MAX = 2
GARP_IDX_PEG_MIN = 3
GARP_IDX_PEG_MAX = 4
GARP_IDX_D_E_MAX = 5
GARP_IDX_SGR_MIN_PCT = 6
GARP_IDX_MC_QUANTILE = 7
GARP_THRESHOLDS = [
    5.0,  # eps_growth_1y >=
    40.0,  # eps_growth_1y <=
    25.0,  # P/E <=
    0.0,  # peg >=
    1.5,  # peg <=
    1.5,  # d_e_ratio <=
    5.0,  # sgr*100 >= (percent)
    0.50,  # market cap percentile threshold
]

# DIVIDEND thresholds
DIV_IDX_MC_QUANTILE = 0
DIV_IDX_YIELD_MIN = 1
DIV_IDX_PAYOUT_MAX = 2
DIVIDEND_THRESHOLDS = [
    0.4,  # Market Cap >= quantile
    0.04,  # dividend_yield >=
    0.90,  # payout_ratio <=
]

# PIOTROSKI thresholds
PIOTROSKI_IDX_F_MIN = 0
PIOTROSKI_IDX_F_MAX = 1  # 🟢 Thêm index cho Max
PIOTROSKI_THRESHOLDS = [6, 9]  # f ≥ 6 = strong, f ≤ 3 = weak (9 tiêu chí chuẩn)

# CANSLIM thresholds
CANSLIM_IDX_EPS_GROWTH_Q_MIN = 0
CANSLIM_IDX_REV_GROWTH_Q_MIN = 1
CANSLIM_IDX_EPS_GROWTH_Y_MIN = 2
CANSLIM_IDX_ROE_MIN = 3
CANSLIM_IDX_RS_MIN = 4
CANSLIM_IDX_VOL_MULT = 5
CANSLIM_IDX_AVG_VOL_MIN = 6
CANSLIM_IDX_QUICK_RATIO_MIN = 7
CANSLIM_IDX_DEBT_EQUITY_MAX = 8
CANSLIM_THRESHOLDS = [
    15.0,  # eps_growth_q >=
    10.0,  # rev_growth_q >=
    15.0,  # eps_growth_y >=
    12.0,  # ROE >=
    60.0,  # rs_rating >
    1.1,  # vol > avg_vol *
    20000,  # avg_vol minimum
    0.8,  # quick_ratio >
    2.0,  # debt_equity <
]

# FISHER thresholds
FISHER_IDX_REV_GROWTH_5Y_MIN = 0
FISHER_IDX_DILUTION_RATE_MAX = 1
FISHER_IDX_ROE_MIN = 2
FISHER_IDX_OPEX_EFF_MAX = 3
FISHER_IDX_TURNOVER_MIN = 4
FISHER_IDX_REINVEST_MIN = 5
FISHER_THRESHOLDS = [
    7.0,  # rev_growth_5y >
    5.0,  # dilution_rate <
    12.0,  # ROE >
    1.0,  # opex_efficiency <
    20000,  # turnover_avg_50d >
    5.0,  # reinvest_rate >
]

# NCN – KHẨU VỊ PHÒNG THỦ (Ngô Cao Nguyên K16)
# ── Tầng 1: Chặn cứng (Red Flag) ──
NCN_IDX_CFO_NI_MIN          = 0   # CFO/NetIncome trung bình 3 năm >= ngưỡng này
NCN_IDX_DILUTION_MAX        = 1   # Tốc độ tăng số CP lưu hành <= (% mỗi năm)
# ── Tầng 2: Chất lượng dòng tiền ──
NCN_IDX_FCF_DEBT_MIN        = 2   # FCF/TotalDebt >= 0 (dương = an toàn)
NCN_IDX_STD_CASH_MAX        = 3   # NợNgắnHạn/TiềnMặt <= ngưỡng (thanh khoản)
# ── Tầng 2: Lợi thế cạnh tranh ──
NCN_IDX_ROIC_MIN            = 4   # ROIC (%) >= 12%
NCN_IDX_GM_STABILITY_MIN    = 5   # Gross Margin (%) >= ngưỡng tối thiểu
# ── Tầng 3: Định lượng bổ trợ (lấy từ bảng) ──
NCN_IDX_ROE_MIN             = 6   # ROE >= 15% (Nhóm III: Lợi nhuận)
NCN_IDX_NET_MARGIN_MIN      = 7   # Net Margin >= 8% (dòng tiền từ bán hàng thật)
NCN_IDX_DE_MAX              = 8   # D/E <= 1.0 (sức khỏe nợ vay)
NCN_IDX_TOP_N               = 9   # Lấy top N mã sau khi xếp hạng tổng hợp
NCN_THRESHOLDS = [
    0.8,    # CFO/NI >= 0.8 (< 0.8 → lợi nhuận giấy, loại ngay)
    8.0,    # Dilution <= 8%/năm (phát hành CP liên tục bất thường)
    0.0,    # FCF/TotalDebt >= 0 (dương = không đốt tiền)
    3.0,    # NợNgắnHạn/TiềnMặt <= 3.0 (thanh khoản thực)
    12.0,   # ROIC >= 12% (lợi thế cạnh tranh bền vững)
    15.0,   # Gross Margin >= 15% (pricing power)
    15.0,   # ROE >= 15%
    5.0,    # Net Margin >= 5%
    1.5,    # D/E <= 1.5
    40,     # Top 40 mã cuối cùng
]


# ========================================================================
# ══════════════════════════════════════════════════════════════════════════════
# HELPERS DÙNG CHUNG
# ══════════════════════════════════════════════════════════════════════════════

def _col(df, candidates):
    for c in candidates:
        if c in df.columns:
            return c
    return None


def _num(df, col):
    if col and col in df.columns:
        return pd.to_numeric(df[col], errors='coerce')
    return pd.Series(np.nan, index=df.index)


# ─────────────────────────────────────────────────────────────────────────────
# HELPER TÍNH GROWTH ĐA KỲ TỪ df_fin
# ─────────────────────────────────────────────────────────────────────────────

def _compute_cagr(df_fin, value_col, years):
    """
    CAGR qua 'years' năm cho từng Ticker.
    Trả về Series index=Ticker.
    OPTIMIZED: dùng groupby vectorized thay vì Python loop.
    """
    if df_fin is None or df_fin.empty or value_col not in df_fin.columns:
        return pd.Series(dtype=float)

    df = df_fin[['Ticker', 'Date', value_col]].copy()
    df[value_col] = pd.to_numeric(df[value_col], errors='coerce')
    df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
    df = df.dropna(subset=['Ticker', 'Date', value_col])
    df = df.drop_duplicates(['Ticker', 'Date']).sort_values(['Ticker', 'Date'])

    # Lấy giá trị kỳ mới nhất (T)
    latest = df.groupby('Ticker').last().reset_index()[['Ticker', 'Date', value_col]]
    latest.columns = ['Ticker', 'latest_date', 'v_t']

    # Với mỗi ticker, tìm kỳ gần nhất với (latest_date - years)
    def find_base(grp):
        ticker = grp['Ticker'].iloc[0]
        lat_row = latest[latest['Ticker'] == ticker]
        if lat_row.empty:
            return None
        latest_date = lat_row['latest_date'].values[0]
        target_date = pd.Timestamp(latest_date) - pd.DateOffset(years=years)
        diff = (grp['Date'] - target_date).abs()
        idx = diff.idxmin()
        if diff[idx] > pd.Timedelta(days=548):
            return None
        v_old = grp.loc[idx, value_col]
        v_new = lat_row['v_t'].values[0]
        if pd.isna(v_old) or v_old <= 0 or pd.isna(v_new) or v_new <= 0:
            return None
        return (v_new / v_old) ** (1.0 / years) - 1

    # Dùng groupby + apply (nhanh hơn loop thuần vì pandas optimize groupby)
    result = df.groupby('Ticker', group_keys=False).apply(find_base)
    result = result.dropna()
    return result


def _compute_yoy(df_fin, value_col):
    """
    YoY growth: (V_T - V_{T-1}) / |V_{T-1}|
    ĐÃ FIX LỖI LỆCH INDEX CỦA PANDAS.
    """
    if df_fin is None or df_fin.empty or value_col not in df_fin.columns:
        return pd.Series(dtype=float)

    df = df_fin[['Ticker', 'Date', value_col]].copy()
    df[value_col] = pd.to_numeric(df[value_col], errors='coerce')
    df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
    df = df.dropna(subset=['Ticker', 'Date', value_col])
    df = df.drop_duplicates(['Ticker', 'Date']).sort_values(['Ticker', 'Date'])

    # Cách lấy T-1 chuẩn xác không bị mất Index (Tránh cảnh báo FutureWarning)
    grp = df.groupby('Ticker')[value_col]
    v_t = grp.last()
    v_tm1 = grp.apply(lambda x: x.iloc[-2] if len(x) > 1 else np.nan)

    valid = (v_tm1 != 0) & v_tm1.notna() & v_t.notna()
    result = (v_t[valid] - v_tm1[valid]) / v_tm1[valid].abs()
    return result


def _compute_latest_ratio(df_fin, num_col, den_col, scale=1.0):
    """Tính num/den từ kỳ mới nhất. Trả về Series index=Ticker."""
    if df_fin is None or df_fin.empty:
        return pd.Series(dtype=float)
    if num_col not in df_fin.columns or den_col not in df_fin.columns:
        return pd.Series(dtype=float)

    df = df_fin[['Ticker', 'Date', num_col, den_col]].copy()
    df[num_col] = pd.to_numeric(df[num_col], errors='coerce')
    df[den_col] = pd.to_numeric(df[den_col], errors='coerce')
    df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
    df = df.dropna(subset=['Ticker', 'Date']).sort_values(['Ticker', 'Date'])
    df_latest = df.groupby('Ticker').last().reset_index()
    ratio = np.where(df_latest[den_col] != 0,
                     df_latest[num_col] / df_latest[den_col] * scale, np.nan)
    return pd.Series(ratio, index=df_latest['Ticker'])


def _merge_series(df_snapshot, series, col_name):
    """Merge Series (index=Ticker) vào df theo cột Ticker."""
    if series is None or series.empty:
        df_snapshot[col_name] = np.nan
        return df_snapshot
    df_snapshot[col_name] = df_snapshot['Ticker'].map(series.to_dict())
    return df_snapshot


# Alias tên cột dùng chung
_REV_CANDIDATES = ['Revenue from Business Activities - Total_x',
                   'Revenue from Business Activities - Total', 'Sales', 'Total Revenue']
_NI_CANDIDATES = ['Net Income after Minority Interest', 'Net Income - Total',
                  'Net Income', 'Net Income - Total_x']
_EPS_CANDIDATES = ['EPS - Basic - excl Extraordinary Items - Common - Total', 'EPS']
_EQUITY_CANDIDATES = ["Shareholders' Equity - Attributable to Parent ShHold - Total",
                      "Common Equity - Total",
                      "Shareholders' Equity - Attributable to Parent ShHold - Total_x"]
_ASSETS_CANDIDATES = ['Total Assets', 'Assets - Total', 'Total Assets_x']
_GP_CANDIDATES = ['Gross Profit - Industrials/Property - Total', 'Gross Profit']
_DPS_CANDIDATES = ['DPS - Common - Gross - Issue - By Announcement Date', 'DPS']
_SHARES_CANDIDATES = ['Common Shares - Outstanding - Total_x',
                      'Common Shares - Outstanding - Total']
_CFO_CANDIDATES = ['Net Cash Flow from Operating Activities', 'FreeCashFlow', 'Free Cash Flow']
_RE_CANDIDATES = ['Retained Earnings - Total', 'Retained Earnings']
_LTD_CANDIDATES = ['Debt - Long-Term - Total', 'Long-Term Debt']
_CUR_A_CANDIDATES = ['Total Current Assets', 'Current Assets - Total']
_CUR_L_CANDIDATES = ['Total Current Liabilities', 'Current Liabilities - Total']
_INV_CANDIDATES = ['Inventories - Total', 'Inventories']
_EBIT_CANDIDATES = ['EBIT', 'Operating Income', 'Operating Profit/Loss - Total']
_OPEX_CANDIDATES = ['Operating Expenses - Total', 'Total Operating Expenses']
_PPE_CANDIDATES = ['Property Plant & Equipment Net', 'PP&E Net']
_RECV_CANDIDATES = ['Accounts Receivable - Trade - Total', 'Receivables - Total']
_DEBT_CANDIDATES = ['Debt - Total', 'Total Debt', 'Total Liabilities']
_LIAB_CANDIDATES = ['Total Liabilities', 'Liabilities - Total']


# ══════════════════════════════════════════════════════════════════════════════
# 1. ĐẦU TƯ GIÁ TRỊ – VALUE INVESTING (Benjamin Graham)
# ══════════════════════════════════════════════════════════════════════════════

def calculate_value_metrics(df, df_fin=None):
    df = df.copy()

    ca_col = _col(df_fin, _CUR_A_CANDIDATES) if df_fin is not None else None
    cl_col = _col(df_fin, _CUR_L_CANDIDATES) if df_fin is not None else None
    ltd_col = _col(df_fin, _LTD_CANDIDATES) if df_fin is not None else None
    ast_col = _col(df_fin, _ASSETS_CANDIDATES) if df_fin is not None else None

    # current_ratio = CA / CL (kỳ mới nhất)
    if ca_col and cl_col and df_fin is not None:
        df = _merge_series(df, _compute_latest_ratio(df_fin, ca_col, cl_col), 'current_ratio')
    else:
        df['current_ratio'] = np.nan

    # debt_to_wc = Long-Term Debt / Working Capital
    if ltd_col and ca_col and cl_col and df_fin is not None:
        df_tmp = df_fin[['Ticker', 'Date', ltd_col, ca_col, cl_col]].copy()
        for c in [ltd_col, ca_col, cl_col]:
            df_tmp[c] = pd.to_numeric(df_tmp[c], errors='coerce')
        df_tmp['Date'] = pd.to_datetime(df_tmp['Date'], errors='coerce')
        df_tmp = df_tmp.dropna(subset=['Ticker', 'Date']).sort_values(['Ticker', 'Date'])
        dl = df_tmp.groupby('Ticker').last().reset_index()
        wc = dl[ca_col] - dl[cl_col]
        ratio = np.where(wc != 0, dl[ltd_col] / wc, np.nan)
        df = _merge_series(df, pd.Series(ratio, index=dl['Ticker']), 'debt_to_wc')
    else:
        df['debt_to_wc'] = np.nan

    # eps_growth_10y: CAGR Net Income 10 năm
    ni_col = _col(df_fin, _NI_CANDIDATES) if df_fin is not None else None
    if ni_col and df_fin is not None:
        cagr = _compute_cagr(df_fin, ni_col, years=5)  # <--- SỬA SỐ 10 THÀNH 5
        df = _merge_series(df, cagr, 'eps_growth_5y')  # <--- SỬA TÊN
    else:
        df['eps_growth_5y'] = np.nan

    logger.info("[VALUE] Đã tính: current_ratio, debt_to_wc, eps_growth_10y (CAGR 10Y)")
    return df


def apply_value_filter(df):
    # ── Điều chỉnh cho thị trường IDX ──────────────────────────────────────
    # IDX median P/E ~11–16x, P/B trung bình nhiều ngành > 1.5x,
    # current_ratio nhiều doanh nghiệp IDX thường 1.0–1.5x (thấp hơn chuẩn Graham)
    mask = pd.Series(True, index=df.index)
    if 'current_ratio' in df.columns:
        mask &= df['current_ratio'].fillna(0) >= VALUE_THRESHOLDS[VALUE_IDX_CURRENT_RATIO_MIN]
    if 'eps_growth_5y' in df.columns and df['eps_growth_5y'].notna().any():  # <--- SỬA TÊN
        mask &= df['eps_growth_5y'].fillna(0) > VALUE_THRESHOLDS[VALUE_IDX_EPS_GROWTH_5Y_MIN]
    elif 'ROE (%)' in df.columns:
        mask &= df['ROE (%)'].fillna(0) > VALUE_THRESHOLDS[VALUE_IDX_EPS_GROWTH_5Y_MIN]
    if 'P/E' in df.columns:
        pe = df['P/E'].fillna(999)
        mask &= (pe > 0) & (pe <= VALUE_THRESHOLDS[VALUE_IDX_PE_MAX])
    if 'P/B' in df.columns:
        mask &= df['P/B'].fillna(999) <= VALUE_THRESHOLDS[VALUE_IDX_PB_MAX]
    if 'debt_to_wc' in df.columns:
        mask &= df['debt_to_wc'].fillna(999) < VALUE_THRESHOLDS[VALUE_IDX_DEBT_TO_WC_MAX]
    if 'net_income' in df.columns:
        mask &= pd.to_numeric(df['net_income'], errors='coerce').fillna(0) > VALUE_THRESHOLDS[VALUE_IDX_NET_INCOME_MIN]
    result = df[mask].copy()
    logger.info(f"[VALUE] Lọc: {len(result)}/{len(df)} mã")
    return result


# ══════════════════════════════════════════════════════════════════════════════
# 2. ĐẦU TƯ PHỤC HỒI – TURNAROUND INVESTING (Templeton)
# ══════════════════════════════════════════════════════════════════════════════

def calculate_turnaround_metrics(df, df_fin=None):
    df = df.copy()

    # peak_drawdown từ Price High trong snapshot
    ph_col = _col(df, ['Price High', 'High'])
    if ph_col and 'Price Close' in df.columns:
        ph = pd.to_numeric(df[ph_col], errors='coerce')
        pc = pd.to_numeric(df['Price Close'], errors='coerce')
        df['peak_drawdown'] = np.where(ph > 0, (pc - ph) / ph * 100, np.nan)
    else:
        df['peak_drawdown'] = np.nan

    # operating_margin = EBIT / Revenue (kỳ mới nhất từ df_fin)
    if df_fin is not None:
        ebit_col = _col(df_fin, _EBIT_CANDIDATES)
        rev_col = _col(df_fin, _REV_CANDIDATES)
        if ebit_col and rev_col:
            om = _compute_latest_ratio(df_fin, ebit_col, rev_col, scale=100)
            df = _merge_series(df, om, 'operating_margin')
        else:
            df['operating_margin'] = df.get('Net Margin (%)', pd.Series(np.nan, index=df.index))
    else:
        df['operating_margin'] = df.get('Net Margin (%)', pd.Series(np.nan, index=df.index))

    # pe_historical_norm = EPS_median_5y / EPS_current
    # (< 1 nghĩa là hiện tại kiếm tiền nhiều hơn lịch sử → giá rẻ hơn so với EPS)
    if df_fin is not None:
        ni_col = _col(df_fin, _NI_CANDIDATES)
        sh_col = _col(df_fin, _SHARES_CANDIDATES)
        if ni_col and sh_col:
            df_pe = df_fin[['Ticker', 'Date', ni_col, sh_col]].copy()
            df_pe[ni_col] = pd.to_numeric(df_pe[ni_col], errors='coerce')
            df_pe[sh_col] = pd.to_numeric(df_pe[sh_col], errors='coerce')
            df_pe['Date'] = pd.to_datetime(df_pe['Date'], errors='coerce')
            df_pe = df_pe.dropna(subset=['Ticker', 'Date'])
            cutoff = df_pe['Date'].max() - pd.DateOffset(years=5)
            df_pe = df_pe[df_pe['Date'] >= cutoff].sort_values(['Ticker', 'Date'])
            df_pe['eps_hist'] = np.where(df_pe[sh_col] > 0,
                                         df_pe[ni_col] / df_pe[sh_col], np.nan)
            med_eps = df_pe.groupby('Ticker')['eps_hist'].median()
            # Vectorized map thay vì loop
            eps_curr_map = df.set_index('Ticker')['EPS'] if 'EPS' in df.columns else pd.Series(dtype=float)
            valid_tickers = med_eps.index.intersection(eps_curr_map.index)
            eps_curr_v = eps_curr_map.reindex(valid_tickers)
            eps_med_v = med_eps.reindex(valid_tickers)
            norm = pd.Series(np.where(
                (eps_curr_v != 0) & eps_curr_v.notna() & (eps_med_v != 0) & eps_med_v.notna(),
                eps_med_v / eps_curr_v, np.nan
            ), index=valid_tickers)
            df['pe_historical_norm'] = df['Ticker'].map(norm.to_dict())
            logger.info(f"[TURNAROUND] pe_historical_norm: {norm.notna().sum()} tickers")
        else:
            df['pe_historical_norm'] = np.nan
    else:
        df['pe_historical_norm'] = np.nan

    # liquidation_value = Cash + 0.7*Recv + 0.5*Inv
    if df_fin is not None:
        cash_col = _col(df_fin, ['Cash & Cash Equivalents - Total_x',
                                 'Cash & Cash Equivalents - Total'])
        recv_col = _col(df_fin, _RECV_CANDIDATES)
        inv_col = _col(df_fin, _INV_CANDIDATES)
        if cash_col:
            cols = ['Ticker', 'Date', cash_col]
            if recv_col: cols.append(recv_col)
            if inv_col:  cols.append(inv_col)
            df_liq = df_fin[cols].copy()
            for c in cols[2:]:
                df_liq[c] = pd.to_numeric(df_liq[c], errors='coerce').fillna(0)
            df_liq['Date'] = pd.to_datetime(df_liq['Date'], errors='coerce')
            df_liq = df_liq.dropna(subset=['Ticker', 'Date']).sort_values(['Ticker', 'Date'])
            dl = df_liq.groupby('Ticker').last().reset_index()
            lv = dl[cash_col].copy()
            if recv_col and recv_col in dl.columns: lv += 0.7 * dl[recv_col]
            if inv_col and inv_col in dl.columns: lv += 0.5 * dl[inv_col]
            df = _merge_series(df, pd.Series(lv.values, index=dl['Ticker']), 'liquidation_value')
        else:
            df['liquidation_value'] = np.nan
    else:
        df['liquidation_value'] = np.nan

    # peg_ratio = P/E / eps_growth_1y%
    if df_fin is not None:
        ni_col = _col(df_fin, _NI_CANDIDATES)
        if ni_col:
            g1y = _compute_yoy(df_fin, ni_col) * 100
            df = _merge_series(df, g1y, '_g1y_pct')
            pe = pd.to_numeric(df.get('P/E', 0), errors='coerce').fillna(0)
            df['peg_ratio'] = np.where(df['_g1y_pct'].fillna(0) > 0,
                                       pe / df['_g1y_pct'], np.nan)
            df.drop(columns=['_g1y_pct'], inplace=True)
        else:
            df['peg_ratio'] = np.nan
    else:
        df['peg_ratio'] = np.nan

    logger.info(
        "[TURNAROUND] Đã tính: peak_drawdown, operating_margin, pe_historical_norm (5Y), liquidation_value, peg_ratio")
    return df


def apply_turnaround_filter(df):
    mask = pd.Series(True, index=df.index)

    # BỎ TẠM peak_drawdown vì snapshot không có đỉnh 52 tuần.
    # Thay vào đó, Turnaround thực chất là: Lợi nhuận gộp/HĐKD đang dương, P/E lịch sử đang rẻ.
    if 'pe_historical_norm' in df.columns and df['pe_historical_norm'].notna().any():
        mask &= df['pe_historical_norm'].fillna(999) < TURNAROUND_THRESHOLDS[TURNAROUND_IDX_PE_HIST_NORM_MAX]
    if 'operating_margin' in df.columns:
        mask &= df['operating_margin'].fillna(-999) >= TURNAROUND_THRESHOLDS[TURNAROUND_IDX_OPERATING_MARGIN_MIN]
    if 'peg_ratio' in df.columns:
        peg = df['peg_ratio'].fillna(-1)
        mask &= (peg >= TURNAROUND_THRESHOLDS[TURNAROUND_IDX_PEG_MIN]) & (
                    peg <= TURNAROUND_THRESHOLDS[TURNAROUND_IDX_PEG_MAX])

    result = df[mask].copy()
    logger.info(f"[TURNAROUND] Lọc: {len(result)}/{len(df)} mã")
    return result


# ══════════════════════════════════════════════════════════════════════════════
# 3. ĐẦU TƯ CHẤT LƯỢNG – QUALITY INVESTING (Munger / Terry Smith)
# ══════════════════════════════════════════════════════════════════════════════

def calculate_quality_metrics(df, df_fin=None):
    df = df.copy()

    if df_fin is not None:
        gp_col = _col(df_fin, _GP_CANDIDATES)
        rev_col = _col(df_fin, _REV_CANDIDATES)
        re_col = _col(df_fin, _RE_CANDIDATES)
        cfo_col = _col(df_fin, _CFO_CANDIDATES)
        ni_col = _col(df_fin, _NI_CANDIDATES)
        ppe_col = _col(df_fin, _PPE_CANDIDATES)

        # gross_margin kỳ mới nhất
        if gp_col and rev_col:
            df = _merge_series(df,
                               _compute_latest_ratio(df_fin, gp_col, rev_col, scale=100), 'gross_margin')
        else:
            df['gross_margin'] = np.nan

        # re_growth: CAGR Retained Earnings 3 năm
        if re_col:
            cagr_re = _compute_cagr(df_fin, re_col, years=3) * 100
            df = _merge_series(df, cagr_re, 're_growth')
            logger.info(f"[QUALITY] re_growth (CAGR 3Y): {cagr_re.notna().sum()} tickers")
        else:
            df['re_growth'] = np.nan

        # fcf_margin = CFO / Net Income (kỳ mới nhất)
        if cfo_col and ni_col:
            df_fcf = df_fin[['Ticker', 'Date', cfo_col, ni_col]].copy()
            df_fcf[cfo_col] = pd.to_numeric(df_fcf[cfo_col], errors='coerce')
            df_fcf[ni_col] = pd.to_numeric(df_fcf[ni_col], errors='coerce')
            df_fcf['Date'] = pd.to_datetime(df_fcf['Date'], errors='coerce')
            df_fcf = df_fcf.dropna(subset=['Ticker', 'Date']).sort_values(['Ticker', 'Date'])
            dl = df_fcf.groupby('Ticker').last().reset_index()
            fcm = np.where(dl[ni_col] != 0, dl[cfo_col] / dl[ni_col], np.nan)
            df = _merge_series(df, pd.Series(fcm, index=dl['Ticker']), 'fcf_margin')
        else:
            df['fcf_margin'] = np.nan

        # ppe_turnover = Revenue / PP&E và xu hướng tăng
        if ppe_col and rev_col:
            df_ppe = df_fin[['Ticker', 'Date', rev_col, ppe_col]].copy()
            for c in [rev_col, ppe_col]:
                df_ppe[c] = pd.to_numeric(df_ppe[c], errors='coerce')
            df_ppe['Date'] = pd.to_datetime(df_ppe['Date'], errors='coerce')
            df_ppe = df_ppe.dropna(subset=['Ticker', 'Date']).sort_values(['Ticker', 'Date'])
            df_ppe['_pt'] = np.where(df_ppe[ppe_col] > 0,
                                     df_ppe[rev_col] / df_ppe[ppe_col], np.nan)
            dl_latest = df_ppe.groupby('Ticker').last()[['_pt']].reset_index()
            df = _merge_series(df,
                               pd.Series(dl_latest['_pt'].values, index=dl_latest['Ticker']), 'ppe_turnover')
            # Vectorized: so sánh kỳ T vs T-1
            pt_last = df_ppe.groupby('Ticker')['_pt'].last()
            pt_last2 = df_ppe.groupby('Ticker')['_pt'].nth(-2)
            improving = (pt_last > pt_last2).fillna(False).astype(int)
            df['ppe_turnover_improving'] = df['Ticker'].map(improving.to_dict()).fillna(0).astype(int)
        else:
            df['ppe_turnover'] = np.nan
            df['ppe_turnover_improving'] = 0
    else:
        for c in ['gross_margin', 're_growth', 'fcf_margin', 'ppe_turnover', 'ppe_turnover_improving']:
            df[c] = np.nan

    logger.info("[QUALITY] Đã tính: gross_margin, re_growth (CAGR 3Y), fcf_margin, ppe_turnover_improving")
    return df


def apply_quality_filter(df):
    mask = pd.Series(True, index=df.index)
    if 'ROE (%)' in df.columns:
        mask &= df['ROE (%)'].fillna(0) >= QUALITY_THRESHOLDS[QUALITY_IDX_ROE_MIN]
    if 'gross_margin' in df.columns:
        mask &= df['gross_margin'].fillna(0) >= QUALITY_THRESHOLDS[QUALITY_IDX_GROSS_MARGIN_MIN]
    if 're_growth' in df.columns and df['re_growth'].notna().any():
        mask &= df['re_growth'].fillna(0) >= QUALITY_THRESHOLDS[QUALITY_IDX_RE_GROWTH_MIN]
    if 'fcf_margin' in df.columns:
        mask &= df['fcf_margin'].fillna(-999) > QUALITY_THRESHOLDS[QUALITY_IDX_FCF_MARGIN_MIN]

    # BỎ TẠM ppe_turnover_improving vì quá ngặt nghèo

    result = df[mask].copy()
    logger.info(f"[QUALITY] Lọc: {len(result)}/{len(df)} mã")
    return result


# ══════════════════════════════════════════════════════════════════════════════
# 4. GARP – GROWTH AT A REASONABLE PRICE (Peter Lynch)
# ══════════════════════════════════════════════════════════════════════════════

def calculate_garp_metrics(df, df_fin=None):
    df = df.copy()

    if df_fin is not None:
        eps_col = _col(df_fin, _EPS_CANDIDATES)
        ni_col = _col(df_fin, _NI_CANDIDATES)
        liab_col = _col(df_fin, _LIAB_CANDIDATES)
        eq_col = _col(df_fin, _EQUITY_CANDIDATES)
        dps_col = _col(df_fin, _DPS_CANDIDATES)

        # eps_growth_1y: YoY EPS (ưu tiên EPS, fallback Net Income)
        target = eps_col if eps_col else ni_col
        if target:
            g1y = _compute_yoy(df_fin, target) * 100
            df = _merge_series(df, g1y, 'eps_growth_1y')
            logger.info(f"[GARP] eps_growth_1y (YoY): {g1y.notna().sum()} tickers")
        else:
            df['eps_growth_1y'] = np.nan

        # peg_ratio = P/E / eps_growth_1y
        pe = pd.to_numeric(df.get('P/E', 0), errors='coerce').fillna(0)
        g = df.get('eps_growth_1y', pd.Series(0, index=df.index)).fillna(0)
        df['peg_ratio'] = np.where(g > 0, pe / g, np.nan)

        # d_e_ratio = Total Liabilities / Equity
        if liab_col and eq_col:
            df = _merge_series(df,
                               _compute_latest_ratio(df_fin, liab_col, eq_col), 'd_e_ratio')
        else:
            df['d_e_ratio'] = np.nan

        # sgr = ROE * (1 - payout_ratio)
        eps2_col = _col(df_fin, _EPS_CANDIDATES)
        if dps_col and eps2_col:
            df_p = df_fin[['Ticker', 'Date', dps_col, eps2_col]].copy()
            df_p[dps_col] = pd.to_numeric(df_p[dps_col], errors='coerce')
            df_p[eps2_col] = pd.to_numeric(df_p[eps2_col], errors='coerce')
            df_p['Date'] = pd.to_datetime(df_p['Date'], errors='coerce')
            df_p = df_p.dropna(subset=['Ticker', 'Date']).sort_values(['Ticker', 'Date'])
            dl = df_p.groupby('Ticker').last().reset_index()
            payout = np.clip(
                np.where(dl[eps2_col] != 0, dl[dps_col] / dl[eps2_col], 0.3), 0, 1)
            retention = 1 - payout
            roe_map = df.set_index('Ticker')['ROE (%)'].to_dict() if 'ROE (%)' in df.columns else {}
            sgr_map = {}
            for i, t in enumerate(dl['Ticker']):
                roe = roe_map.get(t, np.nan)
                sgr_map[t] = roe * retention[i] / 100 if not pd.isna(roe) else np.nan
            df['sgr'] = df['Ticker'].map(sgr_map)
        else:
            df['sgr'] = pd.to_numeric(df.get('ROE (%)', 0), errors='coerce').fillna(0) * 0.7 / 100
    else:
        df['eps_growth_1y'] = np.nan
        df['peg_ratio'] = np.nan
        df['d_e_ratio'] = np.nan
        df['sgr'] = pd.to_numeric(df.get('ROE (%)', 0), errors='coerce').fillna(0) * 0.7 / 100

    logger.info("[GARP] Đã tính: eps_growth_1y (YoY), peg_ratio, d_e_ratio, sgr (thật)")
    return df


def apply_garp_filter(df):
    # ── Điều chỉnh cho thị trường IDX ──────────────────────────────────────
    # Tăng trưởng EPS 10–25% khắt khe, IDX nhiều công ty tăng 5–15% ổn định
    # P/E <= 20 hợp lý hơn với IDX P/E median ~15–16x
    # d_e_ratio IDX thường cao hơn do cấu trúc vốn vay ngân hàng phổ biến
    mask = pd.Series(True, index=df.index)
    if 'eps_growth_1y' in df.columns and df['eps_growth_1y'].notna().any():
        g = df['eps_growth_1y'].fillna(0)
        mask &= (g >= GARP_THRESHOLDS[GARP_IDX_EPS_GROWTH_MIN]) & (g <= GARP_THRESHOLDS[GARP_IDX_EPS_GROWTH_MAX])
    if 'P/E' in df.columns:
        pe = df['P/E'].fillna(999)
        mask &= (pe > 0) & (pe <= GARP_THRESHOLDS[GARP_IDX_PE_MAX])
    if 'peg_ratio' in df.columns:
        peg = df['peg_ratio'].fillna(-1)
        mask &= (peg > GARP_THRESHOLDS[GARP_IDX_PEG_MIN]) & (peg <= GARP_THRESHOLDS[GARP_IDX_PEG_MAX])
    if 'd_e_ratio' in df.columns:
        mask &= df['d_e_ratio'].fillna(999) <= GARP_THRESHOLDS[GARP_IDX_D_E_MAX]
    if 'sgr' in df.columns:
        mask &= df['sgr'].fillna(0) * 100 >= GARP_THRESHOLDS[GARP_IDX_SGR_MIN_PCT]
    if 'Market Cap' in df.columns:
        mc = pd.to_numeric(df['Market Cap'], errors='coerce')
        mc_q = mc.quantile(GARP_THRESHOLDS[GARP_IDX_MC_QUANTILE])
        mask &= mc.fillna(0) >= mc_q
    result = df[mask].copy()
    logger.info(f"[GARP] Lọc: {len(result)}/{len(df)} mã")
    return result


# ══════════════════════════════════════════════════════════════════════════════
# 5. CỔ TỨC & THU NHẬP – DIVIDEND INVESTING (John Neff)
# ══════════════════════════════════════════════════════════════════════════════
def calculate_dividend_metrics(df, df_fin=None):
    logger.info("▶ Chạy chiến lược: STRAT_DIVIDEND")

    _DPS_CANDIDATES = [
        'DPS - Common - Gross - Issue - By Announcement Date',
        'Dividends Per Share',
        'Dividends Paid - Cash - Total - Cash Flow_x',
        'Dividends Paid - Cash - Total - Cash Flow_y',
        'Dividends Provided/Paid - Common',
        'Cash Dividends Paid & Common Stock Buyback - Net'
    ]

    dps_col = _col(df_fin, _DPS_CANDIDATES) if df_fin is not None else None

    if dps_col:
        # Tự động nhận diện Đơn vị (Per share) hay Tổng (Total)
        is_per_share = ('DPS' in dps_col.upper() or 'PER SHARE' in dps_col.upper())
        logger.info(f"   [DIVIDEND] Dùng cột: {dps_col} | Tính theo Per Share: {is_per_share}")

        df_dps2 = df_fin[['Ticker', 'Date', dps_col]].copy()
        df_dps2[dps_col] = pd.to_numeric(df_dps2[dps_col], errors='coerce').fillna(0)
        df_dps2['Date'] = pd.to_datetime(df_dps2['Date'], errors='coerce')
        df_dps2 = df_dps2.dropna(subset=['Ticker', 'Date']).sort_values(['Ticker', 'Date'])

        grp_dps = df_dps2.groupby('Ticker')[dps_col]

        dps_last = grp_dps.last()
        dps_last2 = grp_dps.apply(lambda x: x.iloc[-2] if len(x) > 1 else 0)
        dps_last3 = grp_dps.apply(lambda x: x.iloc[-3] if len(x) > 2 else 0)

        # Trị tuyệt đối để chống số âm
        stable_3 = (dps_last.abs() > 0) & (dps_last2.abs() > 0) & (dps_last3.abs() > 0)
        stable_2 = (dps_last.abs() > 0) & (dps_last2.abs() > 0)

        stab = pd.Series(0, index=dps_last.index, dtype=int)
        stab[stable_3 | stable_2] = 1

        df['dividend_stability'] = df['Ticker'].map(stab.to_dict()).fillna(0).astype(int)
        df['DPS_Last_Raw'] = df['Ticker'].map(dps_last.to_dict()).fillna(0)

        # --- TÍNH YIELD & PAYOUT CỰC CHUẨN DỰA THEO LOẠI DỮ LIỆU ---
        if is_per_share:
            # 1. Yield = Cổ tức 1 CP / Giá 1 CP
            if 'Price Close' in df.columns:
                df['dividend_yield'] = (df['DPS_Last_Raw'].abs() / df['Price Close']).replace([np.inf, -np.inf], np.nan)
            else:
                df['dividend_yield'] = 0

            # 2. Payout = Cổ tức 1 CP / Lợi nhuận 1 CP (EPS)
            if 'EPS' in df.columns:
                df['payout_ratio'] = (df['DPS_Last_Raw'].abs() / df['EPS'].abs()).replace([np.inf, -np.inf], np.nan)
            else:
                df['payout_ratio'] = np.nan

        else:
            # Dữ liệu là dạng TỔNG SỐ TIỀN
            if 'net_income' in df.columns:
                df['payout_ratio'] = (df['DPS_Last_Raw'].abs() / df['net_income'].abs()).replace([np.inf, -np.inf],
                                                                                                 np.nan)
            else:
                df['payout_ratio'] = np.nan

            if 'payout_ratio' in df.columns and 'P/E' in df.columns:
                pe_valid = df['P/E'].where(df['P/E'] > 0, np.nan)
                df['dividend_yield'] = (df['payout_ratio'] / pe_valid).replace([np.inf, -np.inf], np.nan)
            else:
                df['dividend_yield'] = 0

    else:
        df['dividend_stability'] = 0
        df['dividend_yield'] = 0
        df['payout_ratio'] = np.nan

    # Chỉ số phụ
    rev_col = _col(df_fin, _REV_CANDIDATES) if df_fin is not None else None
    df = _merge_series(df, _compute_yoy(df_fin, rev_col), 'rev_growth_y')

    if 'liabilities' in df.columns and 'assets' in df.columns:
        df['debt_ratio'] = (df['liabilities'] / df['assets']).replace([np.inf, -np.inf], np.nan)
    else:
        df['debt_ratio'] = np.nan

    return df


def apply_dividend_filter(df):
    mask = pd.Series(True, index=df.index)

    # 1. Vốn hóa
    c1 = pd.Series(True, index=df.index)
    if 'Market Cap' in df.columns:
        mc = pd.to_numeric(df['Market Cap'], errors='coerce').fillna(0)
        c1 = mc >= mc.quantile(DIVIDEND_THRESHOLDS[DIV_IDX_MC_QUANTILE])

    # 2. Yield >= 4%
    c2 = pd.Series(True, index=df.index)
    if 'dividend_yield' in df.columns:
        c2 = df['dividend_yield'].abs().fillna(0) >= DIVIDEND_THRESHOLDS[DIV_IDX_YIELD_MIN]

    # 3. Payout <= 90%
    c3 = pd.Series(True, index=df.index)
    if 'payout_ratio' in df.columns:
        # Payout ratio phải > 0 (tức là có trả cổ tức từ lợi nhuận dương)
        c3 = (df['payout_ratio'].abs().fillna(999) <= DIVIDEND_THRESHOLDS[DIV_IDX_PAYOUT_MAX]) & (
                    df['payout_ratio'] > 0)

    # 4. Trả đều đặn
    c4 = pd.Series(True, index=df.index)
    if 'dividend_stability' in df.columns:
        c4 = df['dividend_stability'].fillna(0) == 1

    # TẠM BỎ QUA CỬA NỢ DO LỆCH ĐƠN VỊ DATA GỐC
    # c5 = pd.Series(True, index=df.index)
    # if 'debt_ratio' in df.columns:
    #     c5 = df['debt_ratio'].fillna(999) <= 0.80

    # GHI LOG RADAR
    logger.info(
        f"   [RADAR] Qua cửa Vốn hóa: {c1.sum()} | Yield>=4%: {c2.sum()} | Payout(0-90%): {c3.sum()} | Đều đặn: {c4.sum()}")

    # Gộp 4 điều kiện
    mask = c1 & c2 & c3 & c4
    result = df[mask].copy()

    # Sắp xếp từ Yield cao xuống thấp
    if not result.empty and 'dividend_yield' in result.columns:
        result = result.sort_values(by='dividend_yield', ascending=False)

    logger.info(f"[DIVIDEND] Lọc: {len(result)}/{len(df)} mã")
    return result


# ══════════════════════════════════════════════════════════════════════════════
# 6. PIOTROSKI F-SCORE (9 tiêu chí thật từ df_fin lịch sử)
# ══════════════════════════════════════════════════════════════════════════════

def calculate_piotroski_metrics(df, df_fin=None):
    """
    PIOTROSKI F-SCORE (9 tiêu chí thật từ df_fin lịch sử)
    OPTIMIZED: vectorized groupby thay vì Python loop qua từng ticker.
    """
    df = df.copy()

    # Piotroski (2000) đúng chuẩn: 9 tiêu chí, 3 nhóm
    # Profitability (F1-F4): ROA dương, CFO dương, ΔROAchange, Accrual (CFO > ROA)
    # Leverage/Liquidity (F5-F7): Lever giảm, Liquidity tăng, No dilution
    # Operating efficiency (F8-F9): Gross Margin tăng, Asset Turnover tăng
    SCORE_COLS = ['roa_pos', 'cfo_pos', 'roa_growth', 'accrual',
                  'leverage', 'liquidity', 'no_dilution',
                  'gross_margin_growth', 'asset_turnover_growth']

    if df_fin is None or df_fin.empty:
        for c in SCORE_COLS + ['f_score']:
            df[c] = 0
        return df

    df_f = df_fin.copy()
    df_f['Date'] = pd.to_datetime(df_f['Date'], errors='coerce')
    df_f = df_f.dropna(subset=['Ticker', 'Date']).sort_values(['Ticker', 'Date'])

    ni_col = _col(df_f, _NI_CANDIDATES)
    ast_col = _col(df_f, _ASSETS_CANDIDATES)
    cfo_col = _col(df_f, _CFO_CANDIDATES)
    ltd_col = _col(df_f, _LTD_CANDIDATES)
    ca_col = _col(df_f, _CUR_A_CANDIDATES)
    cl_col = _col(df_f, _CUR_L_CANDIDATES)
    sh_col = _col(df_f, _SHARES_CANDIDATES)
    gp_col = _col(df_f, _GP_CANDIDATES)
    rev_col = _col(df_f, _REV_CANDIDATES)

    for c in [ni_col, ast_col, cfo_col, ltd_col, ca_col, cl_col, sh_col, gp_col, rev_col]:
        if c: df_f[c] = pd.to_numeric(df_f[c], errors='coerce')

    # Lấy kỳ T (mới nhất) và T-1 (áp cuối) bằng vectorized groupby
    # ĐÃ FIX: Lấy kỳ T và T-1 đồng bộ Index
    def get_last_two(col_name):
        if not col_name:
            return None, None

        grp = df_f.groupby('Ticker')[col_name]
        T = grp.last()
        T1 = grp.apply(lambda x: x.iloc[-2] if len(x) > 1 else np.nan)
        return T, T1

    ni_T, ni_T1 = get_last_two(ni_col)
    ast_T, ast_T1 = get_last_two(ast_col)
    cfo_T, _ = get_last_two(cfo_col)
    ltd_T, ltd_T1 = get_last_two(ltd_col)
    ca_T, ca_T1 = get_last_two(ca_col)
    cl_T, cl_T1 = get_last_two(cl_col)
    sh_T, sh_T1 = get_last_two(sh_col)
    gp_T, gp_T1 = get_last_two(gp_col)
    rev_T, rev_T1 = get_last_two(rev_col)

    # Tính các chỉ số vectorized
    all_tickers = df_f['Ticker'].unique()
    idx = pd.Index(all_tickers)

    def safe_div(num, den):
        """Chia an toàn, trả về NaN khi den=0."""
        return pd.Series(
            np.where(den.reindex(idx).fillna(0) != 0,
                     num.reindex(idx) / den.reindex(idx), np.nan),
            index=idx
        )

    roa_T = safe_div(ni_T, ast_T)
    roa_T1 = safe_div(ni_T1, ast_T1)

    # F1. roa_pos (ROA > 0, thay net_income_pos — chặt hơn vì tính tương đối với assets)
    roa_pos = (roa_T.fillna(np.nan) > 0).astype(int)

    # F2. cfo_pos
    cfo_pos = (cfo_T.reindex(idx).fillna(np.nan) > 0).astype(int)

    # F4. accrual = CFO > NI (chất lượng thu nhập)
    accrual = (cfo_T.reindex(idx) > ni_T.reindex(idx)).astype(int)

    # F3. roa_growth (ΔROA)
    roa_growth = (roa_T > roa_T1).fillna(False).astype(int)

    # F5. leverage = LTD/Assets giảm
    lev_T = safe_div(ltd_T, ast_T)
    lev_T1 = safe_div(ltd_T1, ast_T1)
    leverage = (lev_T < lev_T1).fillna(False).astype(int)

    # F6. liquidity = current ratio tăng
    cr_T = safe_div(ca_T, cl_T)
    cr_T1 = safe_div(ca_T1, cl_T1)
    liquidity = (cr_T > cr_T1).fillna(False).astype(int)

    # F7. no_dilution = shares không tăng
    no_dilution = (sh_T.reindex(idx) <= sh_T1.reindex(idx)).fillna(False).astype(int)

    # F8. gross_margin_growth (ΔGross Margin)
    gm_T = safe_div(gp_T, rev_T)
    gm_T1 = safe_div(gp_T1, rev_T1)
    gross_margin_growth = (gm_T > gm_T1).fillna(False).astype(int)

    # 10. asset_turnover_growth
    at_T = safe_div(rev_T, ast_T)
    at_T1 = safe_div(rev_T1, ast_T1)
    # F9. asset_turnover_growth (ΔAsset Turnover)
    asset_turnover_growth = (at_T > at_T1).fillna(False).astype(int)

    score_map = {
        'net_income_pos': net_income_pos,
        'roa_pos': roa_pos,
        'roa_growth': roa_growth,
        'cfo_pos': cfo_pos,
        'accrual': accrual,
        'leverage': leverage,
        'liquidity': liquidity,
        'no_dilution': no_dilution,
        'gross_margin_growth': gross_margin_growth,
        'asset_turnover_growth': asset_turnover_growth,
    }

    for col, series in score_map.items():
        df[col] = df['Ticker'].map(series.to_dict()).fillna(0).astype(int)

    df['f_score'] = df[SCORE_COLS].sum(axis=1)
    logger.info(f"[PIOTROSKI] f_score Piotroski 2000 (9 tiêu chí F1-F9): {df['f_score'].value_counts().sort_index().to_dict()}")
    return df


def apply_piotroski_filter(df):
    # ── Điều chỉnh cho thị trường IDX ──────────────────────────────────────
    # F-Score >= 7 (từ 9 tiêu chí) rất khắt khe ngay cả ở thị trường phát triển
    # IDX: F >= 6 là "mạnh", F >= 5 là "trung bình tốt"
    if 'f_score' not in df.columns:
        return df

    # 🟢 CẬP NHẬT: Lọc lấy điểm từ Min (6) đến Max (9)
    # Nếu bạn đã cấu hình PIOTROSKI_THRESHOLDS = [6, 9]
    f_min = PIOTROSKI_THRESHOLDS[PIOTROSKI_IDX_F_MIN]
    f_max = PIOTROSKI_THRESHOLDS[PIOTROSKI_IDX_F_MAX]

    # 💡 LƯU Ý: Nếu bạn chưa khai báo biến PIOTROSKI_IDX_F_MAX ở trên,
    # bạn có thể fix cứng luôn ở đây cho lẹ:
    f_min = 6
    f_max = 9

    # Điều kiện: f_score lớn hơn hoặc bằng f_min VÀ nhỏ hơn hoặc bằng f_max
    mask = (df['f_score'].fillna(0) >= f_min) & (df['f_score'].fillna(0) <= f_max)
    result = df[mask].copy()

    logger.info(f"[PIOTROSKI] Lọc ({f_min} <= f_score <= {f_max}): {len(result)}/{len(df)} mã")
    return result


# ══════════════════════════════════════════════════════════════════════════════
# 7. CANSLIM (William J. O'Neil)
# ══════════════════════════════════════════════════════════════════════════════

def calculate_canslim_metrics(df, df_fin=None):
    df = df.copy()

    if df_fin is not None:
        eps_col = _col(df_fin, _EPS_CANDIDATES)
        ni_col = _col(df_fin, _NI_CANDIDATES)
        rev_col = _col(df_fin, _REV_CANDIDATES)
        sh_col = _col(df_fin, _SHARES_CANDIDATES)
        ca_col = _col(df_fin, _CUR_A_CANDIDATES)
        cl_col = _col(df_fin, _CUR_L_CANDIDATES)
        inv_col = _col(df_fin, _INV_CANDIDATES)
        liab_col = _col(df_fin, _LIAB_CANDIDATES)
        eq_col = _col(df_fin, _EQUITY_CANDIDATES)

        # eps_growth_y (annual YoY)
        target = eps_col if eps_col else ni_col
        if target:
            gy = _compute_yoy(df_fin, target) * 100
            df = _merge_series(df, gy, 'eps_growth_y')
            logger.info(f"[CANSLIM] eps_growth_y (YoY): {gy.notna().sum()} tickers")
        else:
            df['eps_growth_y'] = np.nan

        # eps_growth_q — ưu tiên quarterly YoY, fallback annual
        # O'Neil yêu cầu current quarterly EPS vs cùng kỳ năm ngoái
        # Nếu df_fin là quarterly thì _compute_yoy tự động lấy T vs T-4
        try:
            from src.backend.data_loader import load_financial_data_nocache
            df_fin_q = load_financial_data_nocache('quarterly')
            if df_fin_q is not None and not df_fin_q.empty:
                eps_col_q = _col(df_fin_q, _EPS_CANDIDATES)
                ni_col_q  = _col(df_fin_q, _NI_CANDIDATES)
                rev_col_q = _col(df_fin_q, _REV_CANDIDATES)
                target_q  = eps_col_q if eps_col_q else ni_col_q
                if target_q:
                    # YoY quarterly: so quý T vs quý T-4 (cùng kỳ năm trước)
                    df_q = df_fin_q[['Ticker','Date', target_q]].copy()
                    df_q['Date'] = pd.to_datetime(df_q['Date'], errors='coerce')
                    df_q[target_q] = pd.to_numeric(df_q[target_q], errors='coerce')
                    df_q = df_q.dropna().sort_values(['Ticker','Date'])
                    def _yoy_q(grp):
                        if len(grp) < 5: return np.nan
                        v_t = grp[target_q].iloc[-1]
                        v_t4 = grp[target_q].iloc[-5]
                        if v_t4 == 0 or pd.isna(v_t4): return np.nan
                        return (v_t - v_t4) / abs(v_t4) * 100
                    qyoy = df_q.groupby('Ticker').apply(_yoy_q)
                    df = _merge_series(df, qyoy, 'eps_growth_q')
                    logger.info(f"[CANSLIM] eps_growth_q (quarterly YoY): {qyoy.notna().sum()} tickers")
                else:
                    df['eps_growth_q'] = df.get('eps_growth_y', pd.Series(np.nan, index=df.index))
                if rev_col_q:
                    df_q2 = df_fin_q[['Ticker','Date', rev_col_q]].copy()
                    df_q2['Date'] = pd.to_datetime(df_q2['Date'], errors='coerce')
                    df_q2[rev_col_q] = pd.to_numeric(df_q2[rev_col_q], errors='coerce')
                    df_q2 = df_q2.dropna().sort_values(['Ticker','Date'])
                    def _yoy_rev_q(grp):
                        if len(grp) < 5: return np.nan
                        v_t = grp[rev_col_q].iloc[-1]
                        v_t4 = grp[rev_col_q].iloc[-5]
                        if v_t4 == 0 or pd.isna(v_t4): return np.nan
                        return (v_t - v_t4) / abs(v_t4) * 100
                    qrev = df_q2.groupby('Ticker').apply(_yoy_rev_q)
                    df = _merge_series(df, qrev, 'rev_growth_q')
                    logger.info(f"[CANSLIM] rev_growth_q (quarterly YoY): {qrev.notna().sum()} tickers")
                else:
                    if rev_col:
                        gr = _compute_yoy(df_fin, rev_col) * 100
                        df = _merge_series(df, gr, 'rev_growth_q')
                    else:
                        df['rev_growth_q'] = np.nan
            else:
                raise ValueError("quarterly data empty")
        except Exception as _e:
            logger.warning(f"[CANSLIM] Fallback to annual proxy for quarterly: {_e}")
            df['eps_growth_q'] = df.get('eps_growth_y', pd.Series(np.nan, index=df.index))
            if rev_col:
                gr = _compute_yoy(df_fin, rev_col) * 100
                df = _merge_series(df, gr, 'rev_growth_q')
            else:
                df['rev_growth_q'] = np.nan

        # quick_ratio = (CA - Inventory) / CL (kỳ mới nhất)
        if ca_col and cl_col:
            df_qr = df_fin[['Ticker', 'Date', ca_col, cl_col]].copy()
            if inv_col and inv_col in df_fin.columns:
                df_qr[inv_col] = pd.to_numeric(df_fin[inv_col], errors='coerce').fillna(0)
            for c in [ca_col, cl_col]:
                df_qr[c] = pd.to_numeric(df_qr[c], errors='coerce')
            df_qr['Date'] = pd.to_datetime(df_qr['Date'], errors='coerce')
            df_qr = df_qr.dropna(subset=['Ticker', 'Date']).sort_values(['Ticker', 'Date'])
            dl = df_qr.groupby('Ticker').last().reset_index()
            num = dl[ca_col].copy()
            if inv_col and inv_col in dl.columns:
                num -= dl[inv_col].fillna(0)
            qr = np.where(dl[cl_col] != 0, num / dl[cl_col], np.nan)
            df = _merge_series(df, pd.Series(qr, index=dl['Ticker']), 'quick_ratio')
        else:
            df['quick_ratio'] = np.nan

        # debt_equity = Total Liabilities / Equity
        if liab_col and eq_col:
            df = _merge_series(df,
                               _compute_latest_ratio(df_fin, liab_col, eq_col), 'debt_equity')
        else:
            df['debt_equity'] = np.nan

        # dilution_rate = YoY Shares growth %
        if sh_col:
            dil = _compute_yoy(df_fin, sh_col) * 100
            df = _merge_series(df, dil, 'dilution_rate')
            logger.info(f"[CANSLIM] dilution_rate (YoY): {dil.notna().sum()} tickers")
        else:
            df['dilution_rate'] = 0.0
    else:
        for c in ['eps_growth_y', 'eps_growth_q', 'rev_growth_q',
                  'quick_ratio', 'debt_equity', 'dilution_rate']:
            df[c] = np.nan

    # rs_rating: rank tổng hợp (không cần df_fin)
    vol = pd.to_numeric(df.get('Volume', 0), errors='coerce').fillna(0)
    if 'RS_Avg' in df.columns:
        df['rs_rating'] = (pd.to_numeric(df['RS_Avg'], errors='coerce').rank(pct=True) * 100).round(1)
    elif 'RS_1M' in df.columns:
        df['rs_rating'] = (pd.to_numeric(df['RS_1M'], errors='coerce').rank(pct=True) * 100).round(1)
    else:
        # Fallback: dùng MC + Vol nếu không có RS columns
        mc = pd.to_numeric(df.get('Market Cap', 0), errors='coerce').fillna(0)
        df['rs_rating'] = (mc.rank(pct=True) * 40 + vol.rank(pct=True) * 60).round(1)
    df['avg_vol_50d'] = vol * 0.9 # Giả định avg_vol_50d = vol ngày cuối * 0.9 (nếu không có Avg_Vol_20D)

    # dist_high_52w
    ph_col = _col(df, ['Price High', 'High'])
    if ph_col and 'Price Close' in df.columns:
        ph = pd.to_numeric(df[ph_col], errors='coerce')
        pc = pd.to_numeric(df['Price Close'], errors='coerce')
        df['dist_high_52w'] = np.where(ph > 0, (pc / ph - 1) * 100, np.nan)
    else:
        df['dist_high_52w'] = np.nan

    logger.info("[CANSLIM] Đã tính: eps_growth_y/q, rev_growth_q, quick_ratio, debt_equity, dilution_rate (thật)")
    return df


def apply_canslim_filter(df):
    """
    FIX: Mã KHÔNG CÓ dữ liệu BCTC (NaN) sẽ bị LOẠI khỏi kết quả thay vì
    bị fillna(0) rồi fail ngưỡng — điều đó đảm bảo chỉ giữ lại mã thật sự
    thoả mãn đủ điều kiện, không phải mã không có số liệu.

    Logic: với mỗi điều kiện numeric:
      - Nếu cột không tồn tại   → bỏ qua điều kiện (không lọc)
      - Nếu mã có giá trị       → phải >= threshold
      - Nếu mã là NaN           → loại (coi như không đủ điều kiện)
    """
    mask = pd.Series(True, index=df.index)

    def _cond_ge(col, threshold):
        """Trả về mask: notna AND >= threshold."""
        s = pd.to_numeric(df[col], errors='coerce')
        return s.notna() & (s >= threshold)

    def _cond_gt(col, threshold):
        s = pd.to_numeric(df[col], errors='coerce')
        return s.notna() & (s > threshold)

    def _cond_lt(col, threshold):
        s = pd.to_numeric(df[col], errors='coerce')
        return s.notna() & (s < threshold)

    if 'eps_growth_q' in df.columns and df['eps_growth_q'].notna().any():
        mask &= _cond_ge('eps_growth_q', CANSLIM_THRESHOLDS[CANSLIM_IDX_EPS_GROWTH_Q_MIN])
    if 'rev_growth_q' in df.columns and df['rev_growth_q'].notna().any():
        mask &= _cond_ge('rev_growth_q', CANSLIM_THRESHOLDS[CANSLIM_IDX_REV_GROWTH_Q_MIN])
    if 'eps_growth_y' in df.columns and df['eps_growth_y'].notna().any():
        mask &= _cond_ge('eps_growth_y', CANSLIM_THRESHOLDS[CANSLIM_IDX_EPS_GROWTH_Y_MIN])
    if 'ROE (%)' in df.columns:
        mask &= _cond_ge('ROE (%)', CANSLIM_THRESHOLDS[CANSLIM_IDX_ROE_MIN])
    if 'rs_rating' in df.columns:
        mask &= _cond_gt('rs_rating', CANSLIM_THRESHOLDS[CANSLIM_IDX_RS_MIN])

    # Volume: mã phải có avg_vol > min AND vol ngày cuối > avg_vol * multiplier
    if 'Volume' in df.columns and 'Avg_Vol_20D' in df.columns:
        vol = pd.to_numeric(df['Volume'], errors='coerce')
        avg_vol = pd.to_numeric(df['Avg_Vol_20D'], errors='coerce')
        mask &= (
                avg_vol.notna() & (avg_vol > CANSLIM_THRESHOLDS[CANSLIM_IDX_AVG_VOL_MIN]) &
                vol.notna() & (vol > avg_vol * CANSLIM_THRESHOLDS[CANSLIM_IDX_VOL_MULT])
        )

    if 'quick_ratio' in df.columns:
        mask &= _cond_gt('quick_ratio', CANSLIM_THRESHOLDS[CANSLIM_IDX_QUICK_RATIO_MIN])
    if 'debt_equity' in df.columns:
        mask &= _cond_lt('debt_equity', CANSLIM_THRESHOLDS[CANSLIM_IDX_DEBT_EQUITY_MAX])

    # --- Log radar từng cửa để debug ---
    def _count(col, fn, thr):
        if col not in df.columns: return 'N/A'
        s = pd.to_numeric(df[col], errors='coerce')
        return int(fn(s, thr).sum()) if s.notna().any() else 'no-data'

    logger.info(
        f"[CANSLIM RADAR] "
        f"eps_growth_q>={CANSLIM_THRESHOLDS[CANSLIM_IDX_EPS_GROWTH_Q_MIN]}%: {_count('eps_growth_q', lambda s, t: s.notna() & (s >= t), CANSLIM_THRESHOLDS[CANSLIM_IDX_EPS_GROWTH_Q_MIN])} | "
        f"rev_growth_q>={CANSLIM_THRESHOLDS[CANSLIM_IDX_REV_GROWTH_Q_MIN]}%: {_count('rev_growth_q', lambda s, t: s.notna() & (s >= t), CANSLIM_THRESHOLDS[CANSLIM_IDX_REV_GROWTH_Q_MIN])} | "
        f"eps_growth_y>={CANSLIM_THRESHOLDS[CANSLIM_IDX_EPS_GROWTH_Y_MIN]}%: {_count('eps_growth_y', lambda s, t: s.notna() & (s >= t), CANSLIM_THRESHOLDS[CANSLIM_IDX_EPS_GROWTH_Y_MIN])} | "
        f"ROE>={CANSLIM_THRESHOLDS[CANSLIM_IDX_ROE_MIN]}%: {_count('ROE (%)', lambda s, t: s.notna() & (s >= t), CANSLIM_THRESHOLDS[CANSLIM_IDX_ROE_MIN])} | "
        f"quick_ratio>{CANSLIM_THRESHOLDS[CANSLIM_IDX_QUICK_RATIO_MIN]}: {_count('quick_ratio', lambda s, t: s.notna() & (s > t), CANSLIM_THRESHOLDS[CANSLIM_IDX_QUICK_RATIO_MIN])} | "
        f"debt_equity<{CANSLIM_THRESHOLDS[CANSLIM_IDX_DEBT_EQUITY_MAX]}: {_count('debt_equity', lambda s, t: s.notna() & (s < t), CANSLIM_THRESHOLDS[CANSLIM_IDX_DEBT_EQUITY_MAX])}"
    )

    result = df[mask].copy()
    logger.info(f"[CANSLIM] Lọc: {len(result)}/{len(df)} mã")
    return result


# ══════════════════════════════════════════════════════════════════════════════
# 8. TĂNG TRƯỞNG BỀN VỮNG – FISHER'S CONSERVATIVE GROWTH (Philip Fisher)
# ══════════════════════════════════════════════════════════════════════════════

def calculate_fisher_metrics(df, df_fin=None):
    df = df.copy()

    if df_fin is not None:
        rev_col = _col(df_fin, _REV_CANDIDATES)
        ni_col = _col(df_fin, _NI_CANDIDATES)
        gp_col = _col(df_fin, _GP_CANDIDATES)
        ast_col = _col(df_fin, _ASSETS_CANDIDATES)
        sh_col = _col(df_fin, _SHARES_CANDIDATES)
        opex_col = _col(df_fin, _OPEX_CANDIDATES)
        dps_col = _col(df_fin, _DPS_CANDIDATES)
        eps_col = _col(df_fin, _EPS_CANDIDATES)

        # rev_growth_5y: CAGR Revenue 5 năm (THẬT)
        if rev_col:
            rc5 = _compute_cagr(df_fin, rev_col, years=5) * 100
            df = _merge_series(df, rc5, 'rev_growth_5y')
            logger.info(f"[FISHER] rev_growth_5y (CAGR 5Y): {rc5.notna().sum()} tickers")
        else:
            df['rev_growth_5y'] = np.nan

        # gross_margin kỳ mới nhất
        if gp_col and rev_col:
            df = _merge_series(df,
                               _compute_latest_ratio(df_fin, gp_col, rev_col, scale=100), 'gross_margin')
        else:
            df['gross_margin'] = df.get('Net Margin (%)', pd.Series(np.nan, index=df.index))

        # avg_net_margin_3y: trung bình 3 kỳ gần nhất (THẬT)
        if ni_col and rev_col:
            df_nm = df_fin[['Ticker', 'Date', ni_col, rev_col]].copy()
            df_nm[ni_col] = pd.to_numeric(df_nm[ni_col], errors='coerce')
            df_nm[rev_col] = pd.to_numeric(df_nm[rev_col], errors='coerce')
            df_nm['Date'] = pd.to_datetime(df_nm['Date'], errors='coerce')
            df_nm = df_nm.dropna(subset=['Ticker', 'Date']).sort_values(['Ticker', 'Date'])
            df_nm['_nm'] = np.where(df_nm[rev_col] != 0,
                                    df_nm[ni_col] / df_nm[rev_col] * 100, np.nan)
            avg3 = (df_nm.groupby('Ticker')
                    .apply(lambda g: g['_nm'].dropna().iloc[-3:].mean())
                    .to_dict())
            df['avg_net_margin_3y'] = df['Ticker'].map(avg3)
            logger.info(f"[FISHER] avg_net_margin_3y (3 kỳ thật): {len(avg3)} tickers")
        else:
            df['avg_net_margin_3y'] = df.get('Net Margin (%)', pd.Series(np.nan, index=df.index))

        df['net_margin'] = df.get('Net Margin (%)', pd.Series(np.nan, index=df.index))

        # opex_efficiency = Opex / Revenue (THẬT)
        if opex_col and rev_col:
            df = _merge_series(df,
                               _compute_latest_ratio(df_fin, opex_col, rev_col), 'opex_efficiency')
        else:
            df['opex_efficiency'] = (1 - df.get('Net Margin (%)',
                                                pd.Series(0, index=df.index)).fillna(0) / 100)

        # dilution_rate: YoY Shares growth (THẬT)
        if sh_col:
            dil = _compute_yoy(df_fin, sh_col) * 100
            df = _merge_series(df, dil, 'dilution_rate')
        else:
            df['dilution_rate'] = 0.0

        # reinvest_rate = ROE * (1 - payout) (THẬT)
        if dps_col and eps_col:
            df_ri = df_fin[['Ticker', 'Date', dps_col, eps_col]].copy()
            df_ri[dps_col] = pd.to_numeric(df_ri[dps_col], errors='coerce')
            df_ri[eps_col] = pd.to_numeric(df_ri[eps_col], errors='coerce')
            df_ri['Date'] = pd.to_datetime(df_ri['Date'], errors='coerce')
            df_ri = df_ri.dropna(subset=['Ticker', 'Date']).sort_values(['Ticker', 'Date'])
            dl = df_ri.groupby('Ticker').last().reset_index()
            payout = np.clip(
                np.where(dl[eps_col] != 0, dl[dps_col] / dl[eps_col], 0.3), 0, 1)
            retention = 1 - payout
            roe_map = df.set_index('Ticker')['ROE (%)'].to_dict() if 'ROE (%)' in df.columns else {}
            ri_map = {}
            for i, t in enumerate(dl['Ticker']):
                roe = roe_map.get(t, np.nan)
                ri_map[t] = roe * retention[i] if not pd.isna(roe) else np.nan
            df['reinvest_rate'] = df['Ticker'].map(ri_map)
        else:
            df['reinvest_rate'] = pd.to_numeric(
                df.get('ROE (%)', 0), errors='coerce').fillna(0) * 0.7

        # asset_turnover = Revenue / Assets (kỳ mới nhất)
        if rev_col and ast_col:
            df = _merge_series(df,
                               _compute_latest_ratio(df_fin, rev_col, ast_col), 'asset_turnover')
        else:
            df['asset_turnover'] = np.nan
    else:
        for c in ['rev_growth_5y', 'gross_margin', 'avg_net_margin_3y', 'net_margin',
                  'opex_efficiency', 'dilution_rate', 'reinvest_rate', 'asset_turnover']:
            df[c] = np.nan

    # industry_avg_gm từ snapshot (Sector)
    if 'Sector' in df.columns and 'gross_margin' in df.columns:
        df['industry_avg_gm'] = df.groupby('Sector')['gross_margin'].transform('median')
    else:
        df['industry_avg_gm'] = pd.to_numeric(
            df.get('gross_margin', np.nan), errors='coerce').fillna(np.nan)

    df['turnover_avg_50d'] = pd.to_numeric(df.get('Volume', 0), errors='coerce').fillna(0)

    logger.info(
        "[FISHER] Đã tính: rev_growth_5y (CAGR 5Y), gross_margin, avg_net_margin_3y (3 kỳ thật), opex_efficiency, dilution_rate, reinvest_rate")
    return df


def apply_fisher_filter(df):
    # ── Điều chỉnh cho thị trường IDX ──────────────────────────────────────
    # rev_growth CAGR 5Y > 15% rất khắt khe, nhiều blue chip IDX chỉ ~8–12%
    # reinvest_rate > 50 nghĩa là ROE * retention > 50 — gần như không thể nếu ROE < 60%
    # turnover_avg_50d > 100k rất cao với mid cap IDX
    mask = pd.Series(True, index=df.index)
    if 'rev_growth_5y' in df.columns and df['rev_growth_5y'].notna().any():
        mask &= df['rev_growth_5y'].fillna(0) > FISHER_THRESHOLDS[FISHER_IDX_REV_GROWTH_5Y_MIN]
    if 'gross_margin' in df.columns and 'industry_avg_gm' in df.columns:
        mask &= df['gross_margin'].fillna(0) >= df['industry_avg_gm'].fillna(0)
    if 'net_margin' in df.columns and 'avg_net_margin_3y' in df.columns:
        mask &= df['net_margin'].fillna(0) >= df['avg_net_margin_3y'].fillna(0)
    if 'dilution_rate' in df.columns:
        mask &= df['dilution_rate'].fillna(100) < FISHER_THRESHOLDS[FISHER_IDX_DILUTION_RATE_MAX]
    if 'ROE (%)' in df.columns:
        mask &= df['ROE (%)'].fillna(0) > FISHER_THRESHOLDS[FISHER_IDX_ROE_MIN]
    if 'opex_efficiency' in df.columns:
        mask &= df['opex_efficiency'].fillna(999) < FISHER_THRESHOLDS[FISHER_IDX_OPEX_EFF_MAX]
    if 'turnover_avg_50d' in df.columns:
        mask &= df['turnover_avg_50d'].fillna(0) > FISHER_THRESHOLDS[FISHER_IDX_TURNOVER_MIN]
    if 'reinvest_rate' in df.columns:
        mask &= df['reinvest_rate'].fillna(0) > FISHER_THRESHOLDS[FISHER_IDX_REINVEST_MIN]
    result = df[mask].copy()
    logger.info(f"[FISHER] Lọc: {len(result)}/{len(df)} mã")
    return result


# ============================================================================
# MAGIC FORMULA STRATEGY - Added by Assistant
# ============================================================================

def _get_column_safe(df, candidates):
    """Tìm column từ list candidates, return column name hoặc None"""
    for col in candidates:
        if col in df.columns:
            return col
    return None


def calculate_magic_formula_metrics(df_snapshot, df_fin=None):
    """
    Tính toán ROC và Earnings Yield cho Magic Formula

    Magic Formula của Joel Greenblatt tìm công ty "tốt" (ROC cao)
    với giá "rẻ" (Earnings Yield cao)
    """
    logger.info("🪄 Tính toán Magic Formula metrics...")

    df = df_snapshot.copy()

    # Column candidates
    EBIT_CANDIDATES = ['Earnings before Interest & Taxes (EBIT)', 'ebit', 'EBIT', 'Operating Income']
    CUR_ASSETS_CAND = ['Total Current Assets', 'current_assets', 'Current Assets - Total']
    CASH_CAND = ['Cash & Cash Equivalents - Total_x', 'Cash & Cash Equivalents - Total_y',
                 'cash', 'Cash & Short Term Investments', 'Cash & Equivalents']
    CUR_LIAB_CAND = ['Total Current Liabilities', 'current_liabilities', 'Current Liabilities - Total']
    ST_DEBT_CAND = ['Short-Term Debt & Current Portion of Long-Term Debt', 'Short-Term Debt & Notes Payable']
    PPE_CAND = ['Property Plant & Equipment - Net - Total', 'Property Plant & Equipment Net',
                'Property Plant & Equipment - Purchased - Cash Flow']
    TOTAL_DEBT_CAND = ['Debt - Total', 'total_debt', 'Net Debt', 'Debt - Long-Term - Total']

    # Find columns
    ebit_col = _get_column_safe(df, EBIT_CANDIDATES)
    cur_assets_col = _get_column_safe(df, CUR_ASSETS_CAND)
    cash_col = _get_column_safe(df, CASH_CAND)
    cur_liab_col = _get_column_safe(df, CUR_LIAB_CAND)
    st_debt_col = _get_column_safe(df, ST_DEBT_CAND)
    ppe_col = _get_column_safe(df, PPE_CAND)
    total_debt_col = _get_column_safe(df, TOTAL_DEBT_CAND)

    # 1. EBIT — ưu tiên cột gốc, fallback: EBIT Margin % × Revenue
    if ebit_col:
        df['EBIT_MF'] = pd.to_numeric(df[ebit_col], errors='coerce')
    elif 'EBIT Margin (%)' in df.columns and 'Revenue' in df.columns:
        ebit_margin = pd.to_numeric(df['EBIT Margin (%)'], errors='coerce') / 100
        revenue = pd.to_numeric(df['Revenue'], errors='coerce')
        df['EBIT_MF'] = ebit_margin * revenue
    elif 'EBIT Margin (%)' in df.columns and 'Revenue from Business Activities - Total_x' in df.columns:
        ebit_margin = pd.to_numeric(df['EBIT Margin (%)'], errors='coerce') / 100
        revenue = pd.to_numeric(df['Revenue from Business Activities - Total_x'], errors='coerce')
        df['EBIT_MF'] = ebit_margin * revenue
    else:
        df['EBIT_MF'] = np.nan

    # 2. Net Working Capital
    current_assets = pd.to_numeric(df[cur_assets_col], errors='coerce') if cur_assets_col else 0
    cash = pd.to_numeric(df[cash_col], errors='coerce') if cash_col else 0
    current_liab = pd.to_numeric(df[cur_liab_col], errors='coerce') if cur_liab_col else 0
    st_debt = pd.to_numeric(df[st_debt_col], errors='coerce') if st_debt_col else 0

    df['Net_Working_Capital'] = current_assets - cash - (current_liab - st_debt)

    # 3. Net Fixed Assets — fallback: Total Assets - Current Assets nếu không có PPE
    if ppe_col:
        df['Net_Fixed_Assets'] = pd.to_numeric(df[ppe_col], errors='coerce')
    elif 'Total Assets' in df.columns:
        total_assets = pd.to_numeric(df['Total Assets'], errors='coerce')
        df['Net_Fixed_Assets'] = (total_assets - current_assets).clip(lower=0)
    else:
        df['Net_Fixed_Assets'] = np.nan

    # 4. ROC = EBIT / (NWC + NFA)
    capital_employed = df['Net_Working_Capital'] + df['Net_Fixed_Assets']
    df['ROC_MF'] = np.where(
        capital_employed > 0,
        (df['EBIT_MF'] / capital_employed) * 100,
        np.nan
    )

    # 5. Enterprise Value
    # SỬA LỖI: Đổi thành 'Market Cap' viết hoa cho khớp với dữ liệu gốc
    if 'Market Cap' in df.columns:
        df['Market_Cap_MF'] = pd.to_numeric(df['Market Cap'], errors='coerce')
    elif 'market_cap' in df.columns:
        df['Market_Cap_MF'] = pd.to_numeric(df['market_cap'], errors='coerce')
    else:
        df['Market_Cap_MF'] = 0

    total_debt = pd.to_numeric(df[total_debt_col], errors='coerce') if total_debt_col else 0
    df['EV_MF'] = df['Market_Cap_MF'] + total_debt - cash

    # 6. Earnings Yield = EBIT / EV
    df['Earnings_Yield_MF'] = np.where(
        df['EV_MF'] > 0,
        (df['EBIT_MF'] / df['EV_MF']) * 100,
        np.nan
    )

    logger.info(f"   ✅ Magic Formula: ROC_MF, Earnings_Yield_MF cho {len(df)} mã")
    return df


def apply_magic_formula_filter(df):
    """
    Áp dụng Magic Formula filter:
    1. Loại Financials & Utilities
    2. Market cap >= 1T VND
    3. ROC > 0
    4. Rank ROC + Rank EY
    5. Top 30 lowest total score
    """
    logger.info("🪄 Áp dụng Magic Formula filter...")

    df = df.copy()
    total = len(df)

    # 1. Loại Financials & Utilities
    sector_col = _col(df, ['GICS Sector Name', 'Sector'])
    if sector_col:
        excluded = ['Financials', 'Utilities', 'Tài chính', 'Tiện ích công cộng']
        df = df[~df[sector_col].isin(excluded)]
        logger.info(f"   📊 Loại Financials/Utilities: {total} → {len(df)}")

    # 2. Tạm tắt lọc Market Cap (hạ xuống 0) để test xem cổ phiếu có hiện ra không
    MIN_CAP = 700_000_000_000 # 0.7T VND = 0.7 tỷ VND, bạn có thể điều chỉnh tuỳ thị trường
    if 'Market_Cap_MF' in df.columns:
        # Thêm fillna(0) để các mã thiếu dữ liệu không bị lỗi biến mất
        df = df[df['Market_Cap_MF'].fillna(0) >= MIN_CAP]
        logger.info(f"   💰 Market cap >= {MIN_CAP}: {len(df)} mã")

    # 3. ROC > 0 (Chỉ lấy công ty làm ăn có lãi, loại NaN)
    df = df[df['ROC_MF'].notna() & (df['ROC_MF'] > 0)]
    logger.info(f"   ✅ ROC > 0: {len(df)} mã")

    if len(df) == 0:
        logger.warning("   ⚠️ Không còn mã nào!")
        return df

    # 4. Xếp hạng (Đã gỡ bỏ ép kiểu int và xử lý lỗi dữ liệu trống)
    df['ROC_Rank'] = df['ROC_MF'].rank(ascending=False, method='min', na_option='bottom').fillna(9999)
    df['EY_Rank'] = df['Earnings_Yield_MF'].rank(ascending=False, method='min', na_option='bottom').fillna(9999)
    df['MF_Total_Score'] = df['ROC_Rank'] + df['EY_Rank']

    # 5. Top 30
    df = df.nsmallest(30, 'MF_Total_Score')
    df = df.sort_values('MF_Total_Score')

    logger.info(f"   🎯 Top 30 mã Magic Formula")
    return df

# ══════════════════════════════════════════════════════════════════════════════
# 10. KHẨU VỊ PHÒNG THỦ – Ngô Cao Nguyên K16
#     Lượng hóa framework đầu tư cá nhân thành bộ lọc định lượng 3 tầng:
#       Tầng 1 – Chặn cứng: loại mã có dấu hiệu xào nấu / pha loãng
#       Tầng 2 – Chất lượng: CFO ratio, FCF, ROIC, Gross Margin
#       Tầng 3 – Rank tổng hợp: lấy top N mã có điểm cao nhất
# ══════════════════════════════════════════════════════════════════════════════

def calculate_ncn_metrics(df, df_fin=None):
    df = df.copy()

    cfo_col    = _col(df_fin, _CFO_CANDIDATES)       if df_fin is not None else None
    ni_col     = _col(df_fin, _NI_CANDIDATES)         if df_fin is not None else None
    rev_col    = _col(df_fin, _REV_CANDIDATES)        if df_fin is not None else None
    gp_col     = _col(df_fin, _GP_CANDIDATES)         if df_fin is not None else None
    eq_col     = _col(df_fin, _EQUITY_CANDIDATES)     if df_fin is not None else None
    debt_col   = _col(df_fin, _DEBT_CANDIDATES)       if df_fin is not None else None
    liab_col   = _col(df_fin, _LIAB_CANDIDATES)       if df_fin is not None else None
    shares_col = _col(df_fin, _SHARES_CANDIDATES)     if df_fin is not None else None
    ca_col     = _col(df_fin, _CUR_A_CANDIDATES)      if df_fin is not None else None
    cl_col     = _col(df_fin, _CUR_L_CANDIDATES)      if df_fin is not None else None
    ebit_col   = _col(df_fin, _EBIT_CANDIDATES)       if df_fin is not None else None
    recv_col   = _col(df_fin, _RECV_CANDIDATES)       if df_fin is not None else None

    # ── TẦNG 1A: CFO/Net Income trung bình 3 năm ────────────────────────────
    # Proxy cho chất lượng lợi nhuận — LN kế toán phải đi kèm dòng tiền thật
    if cfo_col and ni_col and df_fin is not None:
        try:
            df_tmp = df_fin[['Ticker', 'Date', cfo_col, ni_col]].copy()
            df_tmp[cfo_col] = pd.to_numeric(df_tmp[cfo_col], errors='coerce')
            df_tmp[ni_col]  = pd.to_numeric(df_tmp[ni_col],  errors='coerce')
            df_tmp['Date']  = pd.to_datetime(df_tmp['Date'], errors='coerce')
            df_tmp = df_tmp.dropna().sort_values(['Ticker', 'Date'])
            # Lấy 3 kỳ gần nhất, tính ratio mỗi kỳ rồi lấy trung bình
            df_tmp['cfo_ni_ratio'] = np.where(
                df_tmp[ni_col].abs() > 0,
                df_tmp[cfo_col] / df_tmp[ni_col].abs(),
                np.nan
            )
            cfo_ni_3y = (
                df_tmp.groupby('Ticker')
                .apply(lambda g: g.tail(3)['cfo_ni_ratio'].mean())
            )
            df = _merge_series(df, cfo_ni_3y, 'cfo_ni_ratio_3y')
        except Exception as e:
            logger.warning(f"[NCN] Lỗi tính CFO/NI: {e}")
            df['cfo_ni_ratio_3y'] = np.nan
    else:
        df['cfo_ni_ratio_3y'] = np.nan

    # ── TẦNG 1B: Tỷ lệ pha loãng (Dilution Rate) ────────────────────────────
    # Tốc độ tăng số CP lưu hành — phát hành quá nhiều → rủi ro pha loãng
    if shares_col and df_fin is not None:
        try:
            dilution = _compute_cagr(df_fin, shares_col, years=3) * 100  # %/năm
            df = _merge_series(df, dilution, 'dilution_rate_3y')
        except Exception as e:
            logger.warning(f"[NCN] Lỗi tính dilution: {e}")
            df['dilution_rate_3y'] = np.nan
    else:
        df['dilution_rate_3y'] = np.nan

    # ── TẦNG 2A: FCF / Total Debt ────────────────────────────────────────────
    # Khả năng trả nợ bằng dòng tiền tự do — âm liên tục là đốt tiền
    if cfo_col and debt_col and df_fin is not None:
        fcf_debt = _compute_latest_ratio(df_fin, cfo_col, debt_col)
        df = _merge_series(df, fcf_debt, 'fcf_debt_ratio')
    else:
        df['fcf_debt_ratio'] = np.nan

    # ── TẦNG 2B: ROIC = EBIT*(1-t) / (Equity + Debt) ────────────────────────
    # Hiệu quả phân bổ vốn — ROIC > 12% qua chu kỳ = có lợi thế cạnh tranh
    if ebit_col and eq_col and df_fin is not None:
        try:
            df_r = df_fin[['Ticker', 'Date', ebit_col, eq_col]].copy()
            # Thêm debt nếu có
            if debt_col and debt_col in df_fin.columns:
                df_r = df_fin[['Ticker', 'Date', ebit_col, eq_col, debt_col]].copy()
                df_r[debt_col] = pd.to_numeric(df_r[debt_col], errors='coerce').fillna(0)
            else:
                df_r[debt_col] = 0.0

            df_r[ebit_col] = pd.to_numeric(df_r[ebit_col], errors='coerce')
            df_r[eq_col]   = pd.to_numeric(df_r[eq_col],   errors='coerce')
            df_r['Date']   = pd.to_datetime(df_r['Date'], errors='coerce')
            df_r = df_r.dropna(subset=['Ticker', 'Date']).sort_values(['Ticker', 'Date'])
            dl = df_r.groupby('Ticker').last().reset_index()

            invested_capital = dl[eq_col] + dl.get(debt_col, 0)
            nopat = dl[ebit_col] * 0.78   # giả định thuế suất ~22% cho VN
            roic = np.where(
                invested_capital.abs() > 0,
                nopat / invested_capital.abs() * 100,
                np.nan
            )
            df = _merge_series(df, pd.Series(roic, index=dl['Ticker']), 'roic_pct')
        except Exception as e:
            logger.warning(f"[NCN] Lỗi tính ROIC: {e}")
            df['roic_pct'] = np.nan
    else:
        df['roic_pct'] = np.nan

    # ── TẦNG 2C: Gross Margin (%) ────────────────────────────────────────────
    # Dùng Gross Margin (%) có sẵn trong snapshot nếu được; fallback tính lại
    if 'Gross Margin (%)' in df.columns:
        df['gross_margin_pct'] = pd.to_numeric(df['Gross Margin (%)'], errors='coerce')
    elif gp_col and rev_col and df_fin is not None:
        gm = _compute_latest_ratio(df_fin, gp_col, rev_col, scale=100)
        df = _merge_series(df, gm, 'gross_margin_pct')
    else:
        df['gross_margin_pct'] = np.nan

    # ── ĐIỂM TỔNG HỢP (dùng để rank ở Tầng 3) ───────────────────────────────
    # Normalize từng chỉ số về [0, 1] rồi cộng có trọng số
    roe_s  = pd.to_numeric(df.get('ROE (%)', np.nan), errors='coerce').fillna(0)
    nm_s   = pd.to_numeric(df.get('Net Margin (%)', np.nan), errors='coerce').fillna(0)
    roic_s = df.get('roic_pct', pd.Series(0.0, index=df.index)).fillna(0)
    gm_s   = df.get('gross_margin_pct', pd.Series(0.0, index=df.index)).fillna(0)
    cfo_s  = df.get('cfo_ni_ratio_3y', pd.Series(0.0, index=df.index)).fillna(0)

    # Trọng số theo bảng: Lợi nhuận 15%, Quản trị 15%, Moat 15%
    df['ncn_score'] = (
        roe_s  * 0.20 +
        nm_s   * 0.15 +
        roic_s * 0.30 +   # ROIC được coi trọng nhất (moat thực sự)
        gm_s   * 0.20 +
        cfo_s  * 0.15     # Chất lượng lợi nhuận
    )

    logger.info("[NCN] Đã tính: cfo_ni_ratio_3y, dilution_rate_3y, fcf_debt_ratio, roic_pct, gross_margin_pct, ncn_score")
    return df


def apply_ncn_filter(df):
    logger.info(f"[NCN] Bắt đầu lọc từ {len(df)} mã")

    # ── TẦNG 1: CHẶN CỨNG (Red Flag — loại ngay) ────────────────────────────
    mask = pd.Series(True, index=df.index)

    # 1A. Chất lượng lợi nhuận: CFO/NI < 0.8 → lợi nhuận giấy
    if 'cfo_ni_ratio_3y' in df.columns and df['cfo_ni_ratio_3y'].notna().sum() > 10:
        mask &= df['cfo_ni_ratio_3y'].fillna(0) >= NCN_THRESHOLDS[NCN_IDX_CFO_NI_MIN]

    # 1B. Pha loãng: tăng CP > 8%/năm trong 3 năm → rủi ro
    if 'dilution_rate_3y' in df.columns and df['dilution_rate_3y'].notna().sum() > 10:
        mask &= df['dilution_rate_3y'].fillna(99) <= NCN_THRESHOLDS[NCN_IDX_DILUTION_MAX]

    df = df[mask].copy()
    logger.info(f"[NCN] Sau Tầng 1 (Red Flag): {len(df)} mã")

    # ── TẦNG 2: BỘ LỌC ĐỊNH LƯỢNG ───────────────────────────────────────────
    mask2 = pd.Series(True, index=df.index)

    # 2A. FCF/Debt >= 0 (dòng tiền dương sau trả nợ)
    if 'fcf_debt_ratio' in df.columns and df['fcf_debt_ratio'].notna().sum() > 10:
        mask2 &= df['fcf_debt_ratio'].fillna(-999) >= NCN_THRESHOLDS[NCN_IDX_FCF_DEBT_MIN]

    # 2B. ROIC >= 12%
    if 'roic_pct' in df.columns and df['roic_pct'].notna().sum() > 10:
        mask2 &= df['roic_pct'].fillna(0) >= NCN_THRESHOLDS[NCN_IDX_ROIC_MIN]

    # 2C. Gross Margin >= 15%
    if 'gross_margin_pct' in df.columns and df['gross_margin_pct'].notna().sum() > 10:
        mask2 &= df['gross_margin_pct'].fillna(0) >= NCN_THRESHOLDS[NCN_IDX_GM_STABILITY_MIN]

    # 2D. ROE >= 15% (Nhóm III bảng)
    if 'ROE (%)' in df.columns:
        mask2 &= pd.to_numeric(df['ROE (%)'], errors='coerce').fillna(0) >= NCN_THRESHOLDS[NCN_IDX_ROE_MIN]

    # 2E. Net Margin >= 5%
    if 'Net Margin (%)' in df.columns:
        mask2 &= pd.to_numeric(df['Net Margin (%)'], errors='coerce').fillna(-999) >= NCN_THRESHOLDS[NCN_IDX_NET_MARGIN_MIN]

    # 2F. D/E <= 1.5 (sức khỏe nợ vay từ Nhóm III)
    if 'D/E' in df.columns:
        mask2 &= pd.to_numeric(df['D/E'], errors='coerce').fillna(999) <= NCN_THRESHOLDS[NCN_IDX_DE_MAX]

    df = df[mask2].copy()
    logger.info(f"[NCN] Sau Tầng 2 (Định lượng): {len(df)} mã")

    # ── TẦNG 3: RANK & TOP N ─────────────────────────────────────────────────
    if 'ncn_score' in df.columns and len(df) > NCN_THRESHOLDS[NCN_IDX_TOP_N]:
        df = df.nlargest(int(NCN_THRESHOLDS[NCN_IDX_TOP_N]), 'ncn_score')

    logger.info(f"[NCN] Kết quả cuối: {len(df)} mã")
    return df

# ══════════════════════════════════════════════════════════════════════════════
# DISPATCHER
# ══════════════════════════════════════════════════════════════════════════════

STRATEGY_MAP = {
    "STRAT_VALUE": (calculate_value_metrics, apply_value_filter),
    "STRAT_TURNAROUND": (calculate_turnaround_metrics, apply_turnaround_filter),
    "STRAT_QUALITY": (calculate_quality_metrics, apply_quality_filter),
    "STRAT_GARP": (calculate_garp_metrics, apply_garp_filter),
    "STRAT_DIVIDEND": (calculate_dividend_metrics, apply_dividend_filter),
    "STRAT_PIOTROSKI": (calculate_piotroski_metrics, apply_piotroski_filter),
    "STRAT_CANSLIM": (calculate_canslim_metrics, apply_canslim_filter),
    "STRAT_GROWTH": (calculate_fisher_metrics, apply_fisher_filter),
    "STRAT_MAGIC": (calculate_magic_formula_metrics, apply_magic_formula_filter),  # ← THÊM MỚI
    "STRAT_NCN":    (calculate_ncn_metrics,    apply_ncn_filter),
}

STRATEGY_META = {
    "STRAT_NCN":    {"name": "Khẩu Vị Phòng Thủ (NCN K16)", "icon": "🛡️"},
    "STRAT_VALUE": {"name": "Đầu tư giá trị (Graham)", "icon": "📦"},
    "STRAT_TURNAROUND": {"name": "Đầu tư phục hồi (Templeton)", "icon": "🔄"},
    "STRAT_QUALITY": {"name": "Đầu tư chất lượng (Munger/Smith)", "icon": "🏰"},
    "STRAT_GARP": {"name": "GARP – Giá hợp lý (Lynch)", "icon": "⚖️"},
    "STRAT_DIVIDEND": {"name": "Cổ tức & Thu nhập (Neff)", "icon": "💰"},
    "STRAT_PIOTROSKI": {"name": "Piotroski F-Score", "icon": "📊"},
    "STRAT_CANSLIM": {"name": "CANSLIM (O'Neil)", "icon": "🚀"},
    "STRAT_GROWTH": {"name": "Tăng trưởng bền vững (Fisher)", "icon": "💎"},
    "STRAT_MAGIC": {"name": "Công Thức Kỳ Diệu (Greenblatt)", "icon": "🪄"},
}

def run_strategy(df_snapshot, strategy_id, df_fin=None):
    """
    Hàm chính. Gọi từ strategy_callbacks.py.
      df_snapshot : 1 dòng/ticker (từ get_latest_snapshot)
      strategy_id : 'STRAT_VALUE', v.v.
      df_fin      : toàn bộ lịch sử BCTC năm (load_financial_data('yearly'))

    CANSLIM tự load quarterly data bên trong calculate_canslim_metrics.
    """
    if strategy_id not in STRATEGY_MAP:
        logger.warning(f"Không nhận ra strategy_id: {strategy_id}")
        return df_snapshot

    calc_fn, apply_fn = STRATEGY_MAP[strategy_id]
    logger.info(f"▶ Chạy chiến lược: {strategy_id}")
    df_enriched = calc_fn(df_snapshot, df_fin=df_fin)
    return apply_fn(df_enriched)