import pandas as pd
import numpy as np
import logging

# Cấu hình Logging
logger = logging.getLogger(__name__)

# ==============================================================================
# 1. CẤU HÌNH MAPPING THÔNG MINH (SMART MAPPING)
# ==============================================================================
# Danh sách các tên cột có thể xuất hiện trong file dữ liệu (do merge hoặc đổi tên)

# ==============================================================================
# 1. CẤU HÌNH MAPPING THÔNG MINH (SMART MAPPING) - PHIÊN BẢN FIX LỖI DATA INDO
# ==============================================================================
SMART_MAPPING = {
    "net_income": [
        "Net Income after Minority Interest",
        "Net Income after Tax",
        "Net Income before Minority Interest",
        "Net Income - Total",
        "Profit/Loss",
        "Net Income - Total_x",
        "Net Income - Total_y",
        "Net Income after Minority Interest_x",
        "Net Income after Tax_x",
    ],
    "revenue": [
        "Revenue from Business Activities - Total",
        "Gross Revenue from Business Activities - Total",
        "Revenue from Business Activities - Total_x",
        "Revenue from Business Activities - Total_y",
        "Sales of Goods & Services - Net - Unclassified",
        "Total Revenue"
    ],
    "equity": [
        "Common Equity - Total",
        "Shareholders' Equity - Attributable to Parent ShHold - Total",
        "Total Shareholders' Equity incl Minority Intr & Hybrid Debt",
        "Common Equity Attributable to Parent Shareholders",
        "Common Equity - Total_x",
        "Total Equity"
    ],
    "eps": [
        "EPS - Basic - excl Extraordinary Items, Common - Total",
        "EPS - Basic - incl Extraordinary Items, Common - Total",
        "EPS - Basic - excl Extraordinary Items - Normalized - Total",
        "EPS - Basic - excl Extraordinary Items, Common - Total_x",
        "EPS - Basic - incl Extraordinary Items, Common - Total_x",
    ],
    "fcf": [
        "Free Cash Flow",
        "Net Cash Flow from Operating Activities",
        "Net Cash Flow from Operating Activities_x"
    ],
    "shares": [
        "Common Shares - Outstanding - Total_x",
        "Common Shares - Outstanding - Total",
        "Common Shares - Outstanding - Total_y",
        "Common Shares - Issued - Total",
        "Shares used to calculate Basic EPS - Total"
    ],
    "assets": [
        "Total Assets",
        "Total Assets_x",
        "Assets - Total"
    ],
    "liabilities": [
        "Total Liabilities",
        "Total Liabilities_x"
    ],
    "current_assets": [
        "Total Current Assets",
        "Total Current Assets_x"
    ],
    "current_liabilities": [
        "Total Current Liabilities",
        "Total Current Liabilities_x"
    ]
}


def finalize_and_clean_data(df):
    """
    Chạy hàm này sau khi đã Merge xong các file BCTC và Giá.
    """
    # 1. Ép kiểu số cho tất cả các cột mapping (Xử lý lỗi 2026-05-01 và "Unable to collect...")
    for target_col in SMART_MAPPING.keys():
        if target_col in df.columns:
            # errors='coerce' sẽ biến đống ngày tháng và chữ rác thành NaN
            df[target_col] = pd.to_numeric(df[target_col], errors='coerce')

    # 2. Xử lý giá trị trống (NaN) để không bị kẹt logic AND
    # Tăng trưởng/ROE rỗng thì coi như = 0
    cols_to_fill_zero = ['roe', 'net_income', 'revenue', 'eps', 'fcf']
    for col in cols_to_fill_zero:
        if col in df.columns:
            df[col] = df[col].fillna(0)

    # Các chỉ số định giá rỗng thì lấp số cực lớn để bộ lọc "Rẻ" tự loại
    if 'pe_ratio' in df.columns: df['pe_ratio'] = df['pe_ratio'].fillna(999)
    if 'pb_ratio' in df.columns: df['pb_ratio'] = df['pb_ratio'].fillna(99)

    return df

def find_best_column(df, candidates):
    """
    Hàm 'Thợ săn cột': Tìm cột tồn tại trong DF dựa trên danh sách ứng viên.
    """
    for col in candidates:
        if col in df.columns:
            return col
    return None

# ==============================================================================
# 2. TÍNH TOÁN CHỈ SỐ CƠ BẢN (FINANCIAL METRICS)
# ==============================================================================

def calculate_financial_metrics(df_price_latest, df_fin_latest):
    """
    Tính toán các chỉ số tài chính cơ bản: P/E, ROE, ROA, Market Cap...
    """
    logger.info("🧮 Bắt đầu tính toán chỉ số tài chính (Basic Metrics)...")

    try:
        df_p = df_price_latest.copy()
        df_f = df_fin_latest.copy()

        # --- BƯỚC 1: LỌC BCTC MỚI NHẤT ---
        if 'Date' in df_f.columns:
            # Sắp xếp theo ngày giảm dần để lấy dòng mới nhất
            df_f = df_f.sort_values('Date').drop_duplicates('Ticker', keep='last')
            logger.info(f"   📅 Đã lọc lấy báo cáo tài chính mới nhất cho {len(df_f)} mã")

        # --- BƯỚC 2: MAPPING CỘT (QUAN TRỌNG) ---
        # Tìm cột tốt nhất trong df_f và tạo cột chuẩn hoá TRƯỚC KHI MERGE
        found_metrics = []
        for metric_name, candidates in SMART_MAPPING.items():
            best_col = find_best_column(df_f, candidates)
            if best_col:
                df_f[metric_name] = pd.to_numeric(df_f[best_col], errors='coerce')
                found_metrics.append(f"{metric_name} (từ '{best_col}')")
            else:
                df_f[metric_name] = np.nan
                logger.warning(f"   ⚠️ Không tìm thấy cột cho: {metric_name}")

        logger.info(f"   ✅ Đã map thành công: {', '.join(found_metrics)}")

        # --- BƯỚC 3: MERGE DỮ LIỆU ---
        # Chỉ giữ lại các cột cần thiết từ df_f để tránh conflict tên cột
        fin_keep_cols = ['Ticker'] + list(SMART_MAPPING.keys()) + [
            c for c in df_f.columns
            if any(kw in c for kw in [
                'GICS', 'Company', 'Gross Profit', 'Debt', 'Cash',
                'EBITDA', 'EBIT', 'Current Assets', 'Current Liabilities',
                'DPS', 'EPS', 'Dividend', 'Sector', 'Auditor', 'Founded', 'Date Became'
            ])
        ]
        fin_keep_cols = list(dict.fromkeys(fin_keep_cols))  # dedup
        df_f_slim = df_f[[c for c in fin_keep_cols if c in df_f.columns]]

        df_merged = pd.merge(df_p, df_f_slim, on="Ticker", how="left")

        # --- BƯỚC 4: TÍNH TOÁN ---
        cols_to_numeric = ['Price Close', 'Volume', 'net_income', 'revenue', 'equity', 'assets', 'shares']
        for col in cols_to_numeric:
            if col in df_merged.columns:
                df_merged[col] = pd.to_numeric(df_merged[col], errors='coerce')
                # Chỉ fillna(0) cho Price/Volume, để NaN cho BCTC
                if col in ['Price Close', 'Volume']:
                    df_merged[col] = df_merged[col].fillna(0)

        # 1. Market Cap (Vốn hóa)
        # Nếu có số lượng cổ phiếu: Market Cap = Giá * Số lượng CP
        if 'shares' in df_merged.columns and df_merged['shares'].sum() > 0:
            df_merged['Market Cap'] = df_merged['Price Close'] * df_merged['shares']
        else:
             # Fallback: Nếu không có cột shares, thử tìm cột Market Cap có sẵn
             mc_col = find_best_column(df_merged, ['Market Cap', 'Market Capitalization'])
             if mc_col:
                 df_merged['Market Cap'] = pd.to_numeric(df_merged[mc_col], errors='coerce').fillna(0)
             else:
                 df_merged['Market Cap'] = 0

        # 2. P/E (Price / EPS) — dùng Price/EPS trực tiếp, an toàn hơn MC/NI
        # Ưu tiên cột EPS đã có sẵn trong df_f; nếu chưa có thì tính NI/Shares
        eps_source_col = find_best_column(df_f, [
            'EPS - Basic - excl Extraordinary Items, Common - Total',
            'EPS - Basic - incl Extraordinary Items, Common - Total',
            'EPS - Basic - excl Extraordinary Items, Common - Total_x',
        ])
        if eps_source_col and eps_source_col in df_merged.columns:
            df_merged['_eps_for_pe'] = pd.to_numeric(df_merged[eps_source_col], errors='coerce')
        elif 'shares' in df_merged.columns and df_merged['shares'].sum() > 0:
            df_merged['_eps_for_pe'] = np.where(
                df_merged['shares'] > 0,
                df_merged['net_income'] / df_merged['shares'],
                np.nan
            )
        else:
            # Fallback cuối: MC/NI
            df_merged['_eps_for_pe'] = np.where(
                df_merged['net_income'] > 0,
                df_merged['Market Cap'] / df_merged['net_income'],
                np.nan
            )
        df_merged['P/E'] = np.where(
            df_merged['_eps_for_pe'] > 0,
            df_merged['Price Close'] / df_merged['_eps_for_pe'],
            np.nan
        )
        df_merged.drop(columns=['_eps_for_pe'], inplace=True, errors='ignore')

        # 3. ROE (Return on Equity)
        # ROE = (Net Income / Equity) * 100
        df_merged['ROE (%)'] = np.where(
            df_merged['equity'] > 0,
            (df_merged['net_income'] / df_merged['equity']) * 100,
            0
        )

        # 4. ROA (Return on Assets)
        df_merged['ROA (%)'] = np.where(
            df_merged['assets'] > 0,
            (df_merged['net_income'] / df_merged['assets']) * 100,
            0
        )

        # 5. Net Margin (%)
        df_merged['Net Margin (%)'] = np.where(
            df_merged['revenue'] > 0,
            (df_merged['net_income'] / df_merged['revenue']) * 100,
            0
        )

        # 6. P/B (Price / Book Value)
        df_merged['P/B'] = np.where(
            df_merged['equity'] > 0,
            df_merged['Market Cap'] / df_merged['equity'],
            0
        )

        # ================================================================
        # 7. CÁC CHỈ SỐ MỚI BỔ SUNG
        # ================================================================

        # --- 7a. GROSS MARGIN (Biên LN gộp) ---
        gross_profit_col = find_best_column(df_f, [
            'Gross Profit - Industrials/Property - Total',
            'Gross Profit',
            'Gross Profit - Total'
        ])
        if gross_profit_col:
            df_merged['gross_profit'] = pd.to_numeric(
                df_merged[gross_profit_col] if gross_profit_col in df_merged.columns
                else df_f[gross_profit_col].reindex(df_merged.index),
                errors='coerce').fillna(0)
        else:
            df_merged['gross_profit'] = 0

        df_merged['Gross Margin (%)'] = np.where(
            df_merged['revenue'] > 0,
            (df_merged['gross_profit'] / df_merged['revenue']) * 100,
            0
        )

        # --- 7b. D/E (Debt to Equity) ---
        total_debt_col = find_best_column(df_f, ['Debt - Total', 'Net Debt'])
        short_debt_col = find_best_column(df_f, [
            'Short-Term Debt & Current Portion of Long-Term Debt',
            'Short-Term Debt & Notes Payable'
        ])
        long_debt_col  = find_best_column(df_f, ['Debt - Long-Term - Total'])

        # Ưu tiên Debt - Total, fallback tính tay
        if total_debt_col and total_debt_col in df_merged.columns:
            df_merged['total_debt'] = pd.to_numeric(
                df_merged[total_debt_col], errors='coerce').fillna(0).abs()
        else:
            short_d = pd.to_numeric(df_merged.get(short_debt_col, 0), errors='coerce').fillna(0).abs()
            long_d  = pd.to_numeric(df_merged.get(long_debt_col,  0), errors='coerce').fillna(0).abs()
            df_merged['total_debt'] = short_d + long_d

        df_merged['D/E'] = np.where(
            df_merged['equity'] > 0,
            df_merged['total_debt'] / df_merged['equity'],
            0
        )

        # --- 7c. CASH & CASH NET ---
        cash_col = find_best_column(df_f, [
            'Cash & Cash Equivalents - Total_x',
            'Cash & Cash Equivalents - Total',
            'Cash & Short Term Investments'
        ])
        if cash_col and cash_col in df_merged.columns:
            df_merged['cash'] = pd.to_numeric(df_merged[cash_col], errors='coerce').fillna(0)
        else:
            df_merged['cash'] = 0

        df_merged['Net Cash'] = df_merged['cash'] - df_merged['total_debt']

        df_merged['Net Cash / Market Cap (%)'] = np.where(
            df_merged['Market Cap'] > 0,
            df_merged['Net Cash'] / df_merged['Market Cap'] * 100,
            0
        )
        df_merged['Net Cash / Assets (%)'] = np.where(
            df_merged['assets'] > 0,
            df_merged['Net Cash'] / df_merged['assets'] * 100,
            0
        )

        # --- 7d. EV (Enterprise Value) = Market Cap + Total Debt - Cash ---
        ebitda_col = find_best_column(df_f, [
            'Earnings before Interest Taxes Depreciation & Amortization',
            'EBITDA'
        ])
        if ebitda_col and ebitda_col in df_merged.columns:
            df_merged['ebitda'] = pd.to_numeric(df_merged[ebitda_col], errors='coerce').fillna(0)
        else:
            df_merged['ebitda'] = 0

        df_merged['EV'] = df_merged['Market Cap'] + df_merged['total_debt'] - df_merged['cash']
        df_merged['EV/EBITDA'] = np.where(
            df_merged['ebitda'] > 0,
            df_merged['EV'] / df_merged['ebitda'],
            0
        )

        # --- 7e. P/S (Price to Sales) ---
        df_merged['P/S'] = np.where(
            df_merged['revenue'] > 0,
            df_merged['Market Cap'] / df_merged['revenue'],
            0
        )

        # --- 7f. DIVIDEND YIELD (Tỷ suất Cổ tức %) ---
        dps_col = find_best_column(df_f, [
            'DPS - Common - Net - Issue - By Announcement Date',
            'DPS - Common - Gross - Issue - By Announcement Date',
            'Dividends Provided/Paid - Common'
        ])
        if dps_col and dps_col in df_merged.columns:
            df_merged['dps'] = pd.to_numeric(df_merged[dps_col], errors='coerce').fillna(0)
        else:
            df_merged['dps'] = 0

        df_merged['Dividend Yield (%)'] = np.where(
            df_merged['Price Close'] > 0,
            df_merged['dps'] / df_merged['Price Close'] * 100,
            0
        )

        # --- 7g. EBIT MARGIN ---
        ebit_col = find_best_column(df_f, [
            'Earnings before Interest & Taxes (EBIT)',
            'EBIT'
        ])
        if ebit_col and ebit_col in df_merged.columns:
            df_merged['ebit'] = pd.to_numeric(df_merged[ebit_col], errors='coerce').fillna(0)
        else:
            df_merged['ebit'] = 0

        df_merged['EBIT Margin (%)'] = np.where(
            df_merged['revenue'] > 0,
            df_merged['ebit'] / df_merged['revenue'] * 100,
            0
        )

        # --- 7h. CURRENT RATIO (Thanh toán hiện hành) ---
        curr_assets_col = find_best_column(df_f, ['Total Current Assets'])
        curr_liab_col   = find_best_column(df_f, ['Total Current Liabilities'])
        if curr_assets_col and curr_assets_col in df_merged.columns:
            df_merged['current_assets'] = pd.to_numeric(df_merged[curr_assets_col], errors='coerce').fillna(0)
        else:
            df_merged['current_assets'] = 0
        if curr_liab_col and curr_liab_col in df_merged.columns:
            df_merged['current_liabilities'] = pd.to_numeric(df_merged[curr_liab_col], errors='coerce').fillna(0)
        else:
            df_merged['current_liabilities'] = 0

        df_merged['Current Ratio'] = np.where(
            df_merged['current_liabilities'] > 0,
            df_merged['current_assets'] / df_merged['current_liabilities'],
            0
        )

        # ================================================================
        # CLEAN UP
        # ================================================================
        df_merged = df_merged.replace([np.inf, -np.inf], np.nan)

        # Chỉ fillna(0) cho các cột price/volume — KHÔNG fillna cho chỉ số tài chính
        # để tránh kéo lệch percentile rank trong scoring
        safe_fill_cols = ['Price Close', 'Price Open', 'Price High', 'Price Low',
                          'Volume', 'Market Cap', 'Avg_Vol_20D']
        for col in safe_fill_cols:
            if col in df_merged.columns:
                df_merged[col] = df_merged[col].fillna(0)

        # Các chỉ số tài chính: NaN → để nguyên NaN (hiện "–" trên UI)
        # Chỉ replace 0 bằng NaN cho các chỉ số định giá/sinh lời
        # (vì np.where(..., 0) ở trên tạo ra 0 cho mã thiếu data)
        ratio_cols = ['P/E', 'P/B', 'P/S', 'EV/EBITDA', 'D/E',
                      'ROE (%)', 'ROA (%)', 'Net Margin (%)', 'Gross Margin (%)',
                      'EBIT Margin (%)', 'Dividend Yield (%)', 'Current Ratio',
                      'Net Cash / Market Cap (%)', 'Net Cash / Assets (%)']
        for col in ratio_cols:
            if col in df_merged.columns:
                df_merged[col] = df_merged[col].replace(0, np.nan)

        round_cols = {
            'P/E': 2, 'P/B': 2, 'P/S': 2, 'D/E': 2, 'EV/EBITDA': 2,
            'ROE (%)': 2, 'ROA (%)': 2, 'Net Margin (%)': 2,
            'Gross Margin (%)': 2, 'EBIT Margin (%)': 2,
            'Dividend Yield (%)': 2, 'Current Ratio': 2,
            'Net Cash / Market Cap (%)': 2, 'Net Cash / Assets (%)': 2
        }
        for c, decimals in round_cols.items():
            if c in df_merged.columns:
                df_merged[c] = df_merged[c].round(decimals)

        logger.info(f"   ✅ Tính toán xong Metrics cho {len(df_merged)} mã.")
        return df_merged

    except Exception as e:
        logger.error(f"❌ Lỗi nghiêm trọng trong calculate_financial_metrics: {e}")
        import traceback
        traceback.print_exc()
        return pd.DataFrame()

# ==============================================================================
# 3. HỆ THỐNG CHẤM ĐIỂM (SCORING SYSTEM)
# ==============================================================================

def assign_grade(value, percentiles, ascending=True):
    """
    Hàm chấm điểm A-F dựa trên phân vị (Percentile) của toàn thị trường.
    """
    if pd.isna(value): return 'F'

    try:
        if ascending: # Giá trị càng CAO càng tốt (Ví dụ: ROE, ROA, Net Margin)
            if value >= percentiles[0.8]: return 'A'   # Top 20%
            elif value >= percentiles[0.6]: return 'B' # Top 40%
            elif value >= percentiles[0.4]: return 'C'
            elif value >= percentiles[0.2]: return 'D'
            else: return 'F'
        else: # Giá trị càng THẤP càng tốt (Ví dụ: P/E, P/B)
            if value <= percentiles[0.2]: return 'A'   # Top 20% rẻ nhất
            elif value <= percentiles[0.4]: return 'B'
            elif value <= percentiles[0.6]: return 'C'
            elif value <= percentiles[0.8]: return 'D'
            else: return 'F'
    except:
        return 'F'

def _assign_grade_series(series, percentiles, ascending=True):
    """Vectorized version của assign_grade - xử lý cả Series cùng lúc."""
    p20, p40, p60, p80 = percentiles[0.2], percentiles[0.4], percentiles[0.6], percentiles[0.8]
    s = series.copy()
    if ascending:
        result = np.select(
            [s >= p80, s >= p60, s >= p40, s >= p20],
            ['A',      'B',      'C',      'D'],
            default='F'
        )
    else:
        result = np.select(
            [s <= p20, s <= p40, s <= p60, s <= p80],
            ['A',      'B',      'C',      'D'],
            default='F'
        )
    # NaN → F
    result = pd.array(result, dtype=object)
    result[series.isna()] = 'F'
    return pd.Series(result, index=series.index)


def calculate_value_score(df):
    """
    VALUE SCORE: Đánh giá độ rẻ của cổ phiếu.
    Trọng số: P/E 35% | P/B 30% | EV/EBITDA 20% | P/S 15%
    Chỉ dùng mã có giá trị dương (loại mã lỗ / thiếu data).
    """
    logger.info("📊 Đang tính Value Score (P/E + P/B + EV/EBITDA + P/S)...")
    try:
        df = df.copy()
        grade_map = {'A': 5, 'B': 4, 'C': 3, 'D': 2, 'F': 1}

        component_grades = []
        weights          = []

        def _grade_valuation(col, w):
            """Helper: grade cho cột định giá (càng thấp càng tốt, loại <= 0)."""
            if col not in df.columns:
                return
            series = pd.to_numeric(df[col], errors='coerce')
            valid  = series[series > 0]
            if len(valid) < 10:
                return
            pct = valid.quantile([0.2, 0.4, 0.6, 0.8]).to_dict()
            masked = series.where(series > 0)  # NaN cho mã thiếu/âm
            g = _assign_grade_series(masked, pct, ascending=False)
            g[series <= 0] = 'F'
            component_grades.append(g)
            weights.append(w)

        _grade_valuation('P/E',       0.35)
        _grade_valuation('P/B',       0.30)
        _grade_valuation('EV/EBITDA', 0.20)
        _grade_valuation('P/S',       0.15)

        # Giữ lại grade sub-components cho Score Breakdown UI
        df['Value_PE_Grade'] = component_grades[0] if len(component_grades) > 0 else 'F'
        df['Value_PB_Grade'] = component_grades[1] if len(component_grades) > 1 else 'F'

        if not component_grades:
            df['Value Score'] = 'F'
            return df

        # Normalize weights
        total_w = sum(weights)
        weights = [w / total_w for w in weights]

        score_num = pd.Series(0.0, index=df.index)
        for grade_series, w in zip(component_grades, weights):
            score_num += grade_series.map(grade_map).fillna(1) * w

        df['Value_Score_Num'] = score_num
        df['Value Score'] = pd.cut(
            score_num,
            bins=[0, 1.5, 2.5, 3.5, 4.5, 6],
            labels=['F', 'D', 'C', 'B', 'A']
        ).astype(str)

        a_count = (df['Value Score'] == 'A').sum()
        logger.info(f"   ✅ Value Score xong — {a_count} mã đạt A")
        return df

    except Exception as e:
        logger.error(f"Lỗi tính Value Score: {e}")
        import traceback; traceback.print_exc()
        df['Value Score'] = 'F'
        return df

def calculate_growth_score(df):
    """
    GROWTH SCORE: Đánh giá tăng trưởng thực sự (Revenue Growth, EPS Growth, ROE, ROA).
    - Revenue Growth YoY: 30%
    - EPS Growth YoY:     30%
    - ROE:                25%
    - ROA:                15%

    Dùng percentile rank TRONG NGÀNH (sector-relative) nếu có cột Sector,
    fallback về toàn thị trường. Lý do: ROE ngân hàng 15% bình thường,
    ROE tech 15% thấp — so sánh cross-sector tạo bias lớn.
    """
    logger.info("📊 Đang tính Growth Score (Revenue+EPS+ROE+ROA)...")
    try:
        df = df.copy()
        grade_map = {'A': 5, 'B': 4, 'C': 3, 'D': 2, 'F': 1}

        component_grades = []
        weights          = []

        # ── 1. Revenue Growth YoY (30%) ────────────────────────────────────
        if 'Revenue Growth YoY (%)' in df.columns:
            rev_g = pd.to_numeric(df['Revenue Growth YoY (%)'], errors='coerce')
            valid = rev_g.dropna()
            if len(valid) >= 10:
                pct = valid.quantile([0.2, 0.4, 0.6, 0.8]).to_dict()
                component_grades.append(_assign_grade_series(rev_g, pct, ascending=True))
                weights.append(0.30)

        # ── 2. EPS Growth YoY (30%) ────────────────────────────────────────
        if 'EPS Growth YoY (%)' in df.columns:
            eps_g = pd.to_numeric(df['EPS Growth YoY (%)'], errors='coerce')
            # Chỉ lấy mã có EPS dương (loại mã lỗ)
            eps_g_valid = eps_g.where(df.get('EPS', pd.Series(0, index=df.index)) > 0)
            valid = eps_g_valid.dropna()
            if len(valid) >= 10:
                pct = valid.quantile([0.2, 0.4, 0.6, 0.8]).to_dict()
                component_grades.append(_assign_grade_series(eps_g_valid, pct, ascending=True))
                weights.append(0.30)

        # ── 3. ROE (25%) ───────────────────────────────────────────────────
        if 'ROE (%)' in df.columns:
            roe = pd.to_numeric(df['ROE (%)'], errors='coerce')
            roe_valid = roe.where(roe > 0)
            valid = roe_valid.dropna()
            if len(valid) >= 10:
                pct = valid.quantile([0.2, 0.4, 0.6, 0.8]).to_dict()
                g = _assign_grade_series(roe_valid, pct, ascending=True)
                g[roe <= 0] = 'F'
                component_grades.append(g)
                weights.append(0.25)

        # ── 4. ROA (15%) ───────────────────────────────────────────────────
        if 'ROA (%)' in df.columns:
            roa = pd.to_numeric(df['ROA (%)'], errors='coerce')
            roa_valid = roa.where(roa > 0)
            valid = roa_valid.dropna()
            if len(valid) >= 10:
                pct = valid.quantile([0.2, 0.4, 0.6, 0.8]).to_dict()
                g = _assign_grade_series(roa_valid, pct, ascending=True)
                g[roa <= 0] = 'F'
                component_grades.append(g)
                weights.append(0.15)

        # Giữ lại grade sub-components cho Score Breakdown UI
        if len(component_grades) >= 3:
            df['Growth_ROE_Grade'] = component_grades[-2] if len(component_grades) >= 2 else 'F'
            df['Growth_ROA_Grade'] = component_grades[-1]
        elif len(component_grades) >= 2:
            df['Growth_ROE_Grade'] = component_grades[0]
            df['Growth_ROA_Grade'] = component_grades[1]
        else:
            df['Growth_ROE_Grade'] = 'F'
            df['Growth_ROA_Grade'] = 'F'

        if not component_grades:
            logger.warning("   ⚠️ Không có data growth → fallback ROE/ROA only")
            df['Growth Score'] = 'F'
            return df

        # Normalize weights
        total_w = sum(weights)
        weights = [w / total_w for w in weights]

        score_num = pd.Series(0.0, index=df.index)
        for grade_series, w in zip(component_grades, weights):
            score_num += grade_series.map(grade_map).fillna(1) * w

        # ── Sector-relative bonus: blend market + sector percentile ───────
        # Nếu có Sector, tính thêm sector-relative ROE rank và blend 50/50
        if 'Sector' in df.columns and 'ROE (%)' in df.columns:
            try:
                roe = pd.to_numeric(df['ROE (%)'], errors='coerce')
                # Sector-relative rank (0-1)
                sector_rank = df.groupby('Sector')['ROE (%)'].transform(
                    lambda x: pd.to_numeric(x, errors='coerce').rank(pct=True)
                ).fillna(0.5)
                # Market-relative rank (0-1)
                market_rank = roe.rank(pct=True).fillna(0.5)
                # Blend 50/50, scale to 1-5 grade range
                blended = (sector_rank * 0.5 + market_rank * 0.5) * 4 + 1
                # Nhẹ nhàng điều chỉnh score_num (±0.3 max để không override hoàn toàn)
                adjustment = (blended - score_num).clip(-0.3, 0.3)
                score_num = score_num + adjustment
                logger.info("   ✅ Sector-relative adjustment applied to Growth Score")
            except Exception as e:
                logger.warning(f"   ⚠️ Sector adjustment failed: {e}")

        df['Growth_Score_Num'] = score_num
        df['Growth Score'] = pd.cut(
            score_num,
            bins=[0, 1.5, 2.5, 3.5, 4.5, 6],
            labels=['F', 'D', 'C', 'B', 'A']
        ).astype(str)

        a_count = (df['Growth Score'] == 'A').sum()
        logger.info(f"   ✅ Growth Score xong — {a_count} mã đạt A")
        return df

    except Exception as e:
        logger.error(f"Lỗi tính Growth Score: {e}")
        import traceback; traceback.print_exc()
        df['Growth Score'] = 'F'
        return df

def calculate_momentum_score(df):
    """
    MOMENTUM SCORE: Đánh giá động lượng giá dựa trên RS_1M, RS_3M, Perf_1W, Perf_1M.
    - RS (Relative Strength) so với JCI: càng cao càng tốt
    - Perf ngắn hạn: hỗ trợ thêm
    Dùng percentile rank toàn thị trường — cùng logic với Value/Growth.
    """
    logger.info("📊 Đang tính Momentum Score (RS + Perf based)...")
    try:
        df = df.copy()
        grade_points_map = {'A': 5, 'B': 4, 'C': 3, 'D': 2, 'F': 1}

        momentum_grades = []
        weights         = []

        # ── Tín hiệu 1: RS_1M (trọng số 35%) ──────────────────────────────
        if 'RS_1M' in df.columns:
            rs1m = pd.to_numeric(df['RS_1M'], errors='coerce')
            valid = rs1m.dropna()
            if len(valid) >= 10:
                pct = valid.quantile([0.2, 0.4, 0.6, 0.8]).to_dict()
                momentum_grades.append(_assign_grade_series(rs1m, pct, ascending=True))
                weights.append(0.35)

        # ── Tín hiệu 2: RS_3M (trọng số 30%) ──────────────────────────────
        if 'RS_3M' in df.columns:
            rs3m = pd.to_numeric(df['RS_3M'], errors='coerce')
            valid = rs3m.dropna()
            if len(valid) >= 10:
                pct = valid.quantile([0.2, 0.4, 0.6, 0.8]).to_dict()
                momentum_grades.append(_assign_grade_series(rs3m, pct, ascending=True))
                weights.append(0.30)

        # ── Tín hiệu 3: Perf_1M (trọng số 20%) ────────────────────────────
        if 'Perf_1M' in df.columns:
            p1m = pd.to_numeric(df['Perf_1M'], errors='coerce')
            valid = p1m.dropna()
            if len(valid) >= 10:
                pct = valid.quantile([0.2, 0.4, 0.6, 0.8]).to_dict()
                momentum_grades.append(_assign_grade_series(p1m, pct, ascending=True))
                weights.append(0.20)

        # ── Tín hiệu 4: Perf_1W (trọng số 15%) ────────────────────────────
        if 'Perf_1W' in df.columns:
            p1w = pd.to_numeric(df['Perf_1W'], errors='coerce')
            valid = p1w.dropna()
            if len(valid) >= 10:
                pct = valid.quantile([0.2, 0.4, 0.6, 0.8]).to_dict()
                momentum_grades.append(_assign_grade_series(p1w, pct, ascending=True))
                weights.append(0.15)

        if not momentum_grades:
            # Fallback: không có data momentum → C
            logger.warning("   ⚠️ Không có data momentum, gán C mặc định")
            df['Momentum Score'] = 'C'
            return df

        # Normalize weights về tổng = 1
        total_w = sum(weights)
        weights = [w / total_w for w in weights]

        # Tính điểm số có trọng số
        grade_map = {'A': 5, 'B': 4, 'C': 3, 'D': 2, 'F': 1}
        score_num = pd.Series(0.0, index=df.index)
        for grade_series, w in zip(momentum_grades, weights):
            score_num += grade_series.map(grade_map).fillna(3) * w

        df['Momentum_Score_Num'] = score_num
        df['Momentum Score'] = pd.cut(
            score_num,
            bins=[0, 1.5, 2.5, 3.5, 4.5, 6],
            labels=['F', 'D', 'C', 'B', 'A']
        ).astype(str)

        # Mã thiếu data momentum → C (neutral)
        missing_mask = (
            df.get('RS_1M', pd.Series(dtype=float)).isna() &
            df.get('RS_3M', pd.Series(dtype=float)).isna() &
            df.get('Perf_1M', pd.Series(dtype=float)).isna()
        )
        df.loc[missing_mask, 'Momentum Score'] = 'C'

        a_count = (df['Momentum Score'] == 'A').sum()
        logger.info(f"   ✅ Momentum Score xong — {a_count} mã đạt A")
        return df

    except Exception as e:
        logger.error(f"Lỗi tính Momentum Score: {e}")
        import traceback; traceback.print_exc()
        df['Momentum Score'] = 'C'
        return df

def calculate_vgm_score(df):
    """
    VGM SCORE: Tổng hợp Value + Growth + Momentum.

    Trọng số cơ bản: Value 30% | Growth 40% | Momentum 30%
    (Growth ưu tiên vì IDX là thị trường tăng trưởng)

    Staleness adjustment: nếu BCTC > 9 tháng chưa cập nhật,
    giảm trọng số V+G và tăng trọng số M để tránh stale fundamental
    kéo score sai. Đây là vấn đề thực tế khi annual data lag 12 tháng.
    """
    logger.info("📊 Đang tính VGM Score (with staleness adjustment)...")
    try:
        df = df.copy()
        grade_points = {'A': 5, 'B': 4, 'C': 3, 'D': 2, 'F': 1}

        v_points = df['Value Score'].map(grade_points).fillna(1)
        g_points = df['Growth Score'].map(grade_points).fillna(1)
        m_points = df['Momentum Score'].map(grade_points).fillna(3)

        # ── Staleness check: nếu có cột Date BCTC ─────────────────────────
        w_v, w_g, w_m = 0.30, 0.40, 0.30   # default weights

        if 'Date' in df.columns:
            try:
                fin_date = pd.to_datetime(df['Date'], errors='coerce')
                now = pd.Timestamp.now()
                months_stale = ((now - fin_date).dt.days / 30).fillna(12)
                # Nếu BCTC > 9 tháng: giảm V+G, tăng M
                stale_mask = months_stale > 9
                stale_count = stale_mask.sum()
                if stale_count > 0:
                    logger.info(f"   ⚠️ {stale_count} mã có BCTC > 9 tháng → giảm V/G weight")
                # Vectorized weight adjustment per ticker
                w_v_arr = np.where(stale_mask, 0.20, 0.30)
                w_g_arr = np.where(stale_mask, 0.25, 0.40)
                w_m_arr = np.where(stale_mask, 0.55, 0.30)
                df['VGM_Score_Num'] = (
                    v_points.values * w_v_arr +
                    g_points.values * w_g_arr +
                    m_points.values * w_m_arr
                )
            except Exception:
                df['VGM_Score_Num'] = v_points * w_v + g_points * w_g + m_points * w_m
        else:
            df['VGM_Score_Num'] = v_points * w_v + g_points * w_g + m_points * w_m

        df['VGM Score'] = pd.cut(
            df['VGM_Score_Num'],
            bins=[0, 1.5, 2.5, 3.5, 4.5, 6],
            labels=['F', 'D', 'C', 'B', 'A']
        ).astype(str)

        dist = df['VGM Score'].value_counts().to_dict()
        logger.info(f"   ✅ VGM Score xong — phân bổ: {dist}")
        return df

    except Exception as e:
        logger.error(f"Lỗi tính VGM Score: {e}")
        df['VGM Score'] = 'F'
        return df

def calculate_canslim_score(df):
    """
    CANSLIM SCORE (0-7): Tiêu chí đầu tư tăng trưởng của William O'Neil.
    7 tiêu chí chấm được từ market data (bỏ U=Uptend institutions, M=Market direction
    vì cần macro data):

    C - Current Quarterly EPS tăng ≥25% so với cùng kỳ năm ngoái
        (proxy: EPS Growth YoY hoặc ROE > 17%)
    A - Annual EPS tăng ≥25% liên tiếp trong 3-5 năm
        (proxy: Revenue Growth YoY ≥25% hoặc Net Margin > 15%)
    N - New 52W high — giá phá đỉnh hoặc cách đỉnh không quá 10%
        (chặt hơn cũ: -10% thay vì -15%)
    S - Supply/Demand — volume đột biến ≥1.5x MA50
    L - Leader — RS_1M top 20% thị trường (percentile ≥80, chặt hơn cũ 70%)
    I - Institutional sponsorship — Market Cap ≥ median thị trường
    Bonus - ROE > 17% (thêm 1 điểm chất lượng)
    """
    logger.info("📊 Đang tính CANSLIM Score (O'Neil chuẩn hóa)...")
    try:
        df = df.copy()
        score = pd.Series(0, index=df.index)

        # ── C: Current Quarterly EPS growth ≥25% ──────────────────────────
        if 'EPS Growth YoY (%)' in df.columns:
            eps_g = pd.to_numeric(df['EPS Growth YoY (%)'], errors='coerce').fillna(0)
            score += (eps_g >= 25).astype(int)
        elif 'ROE (%)' in df.columns:
            roe = pd.to_numeric(df['ROE (%)'], errors='coerce').fillna(0)
            score += (roe > 17).astype(int)

        # ── A: Annual EPS/Revenue growth ≥25% ─────────────────────────────
        if 'Revenue Growth YoY (%)' in df.columns:
            rev_g = pd.to_numeric(df['Revenue Growth YoY (%)'], errors='coerce').fillna(0)
            score += (rev_g >= 25).astype(int)
        elif 'Net Margin (%)' in df.columns:
            nm = pd.to_numeric(df['Net Margin (%)'], errors='coerce').fillna(0)
            score += (nm > 15).astype(int)

        # ── N: New High — cách đỉnh 52W không quá 10% (chặt hơn cũ) ──────
        if 'Pct_From_High_1Y' in df.columns:
            pct_h = pd.to_numeric(df['Pct_From_High_1Y'], errors='coerce').fillna(-100)
            score += (pct_h >= -10).astype(int)
        elif 'Break_High_52W' in df.columns:
            score += pd.to_numeric(df['Break_High_52W'], errors='coerce').fillna(0).astype(int)

        # ── S: Supply & Demand — volume đột biến ≥1.5x ───────────────────
        if 'Vol_vs_SMA50' in df.columns:
            score += (pd.to_numeric(df['Vol_vs_SMA50'], errors='coerce').fillna(0) >= 1.5).astype(int)
        elif 'Vol_vs_SMA20' in df.columns:
            score += (pd.to_numeric(df['Vol_vs_SMA20'], errors='coerce').fillna(0) >= 1.5).astype(int)

        # ── L: Leader — RS top 20% (p80+, chặt hơn cũ p70) ──────────────
        rs_col = 'RS_1M' if 'RS_1M' in df.columns else ('RS_Avg' if 'RS_Avg' in df.columns else None)
        if rs_col:
            rs = pd.to_numeric(df[rs_col], errors='coerce')
            score += (rs >= rs.quantile(0.80)).astype(int)

        # ── I: Institutional — Market Cap ≥ median ────────────────────────
        if 'Market Cap' in df.columns:
            mc = pd.to_numeric(df['Market Cap'], errors='coerce').fillna(0)
            mc_med = mc[mc > 0].median()
            score += (mc >= mc_med).astype(int)

        # ── Bonus: ROE > 17% (chất lượng thu nhập) ───────────────────────
        if 'ROE (%)' in df.columns:
            roe = pd.to_numeric(df['ROE (%)'], errors='coerce').fillna(0)
            score += (roe > 17).astype(int)

        df['CANSLIM Score'] = score.clip(0, 7)
        high = (df['CANSLIM Score'] >= 5).sum()
        logger.info(f"   ✅ CANSLIM Score xong — {high} mã đạt ≥5/7")
        return df

    except Exception as e:
        logger.error(f"Lỗi tính CANSLIM Score: {e}")
        import traceback; traceback.print_exc()
        df['CANSLIM Score'] = 0
        return df

# ==============================================================================
# 4. HÀM CHÍNH (ORCHESTRATOR) - ENHANCED VERSION
# ==============================================================================

def calculate_all_scores(df_price, df_financial):
    """
    Hàm chính điều phối toàn bộ quy trình tính toán - ENHANCED VERSION.
    Được gọi từ data_loader.py.

    UPDATES:
    - Thêm cột Sector (từ GICS Sector Name)
    - Tính EPS (Earnings Per Share)
    - Tính BVPS (Book Value Per Share)
    - Thêm Revenue_TTM, Net_Income_TTM, EBIT_Margin
    - Bao gồm Price Open, High, Low cho technical analysis
    """
    logger.info("🚀 Bắt đầu quy trình chấm điểm toàn diện (Full Scoring - Enhanced)...")

    try:
        # 1. Tính toán chỉ số tài chính (Có Smart Mapping)
        df = calculate_financial_metrics(df_price, df_financial)

        if df.empty:
            logger.error("❌ Không thể tính toán chỉ số cơ bản -> Trả về bảng rỗng")
            return pd.DataFrame()

        # ===================================================================
        # 2. THÊM CÁC CỘT MỚI CHO 4-TAB SYSTEM
        # ===================================================================

        # ===================================================================
        # 2.1. Thêm thông tin Sector (Ngành) - SMART FINDER
        # ===================================================================
        # Danh sách các tên cột Ngành có thể xuất hiện (Ưu tiên từ trên xuống)
        # Debug: log thực tế cột nào có trong data để chẩn đoán
        gics_cols_present = [col for col in df.columns if 'GICS' in col or 'Sector' in col or 'Industry' in col]
        logger.info(f"   [DEBUG Sector] Cột GICS/Sector/Industry thực tế: {gics_cols_present}")

        sector_candidates = [
            'GICS Sector Name',       # Ưu tiên 1: Sector lớn chuẩn (Financials, Industrials...)
            'GICS Industry Name',     # Ưu tiên 2: Ngành trung (nếu không có Sector lớn)
            'TRBC Industry Name',     # Ưu tiên 3: Hệ thống TRBC
            'Sector',                 # Ưu tiên 4: Cột generic
            'Industry',               # Ưu tiên 5
            'GICS Sub-Industry Name', # Ưu tiên 6: Cuối cùng mới dùng ngành con (chi tiết nhất)
        ]

        sector_col_found = None

        # 1. Tìm chính xác (Exact Match)
        for col in sector_candidates:
            if col in df.columns:
                sector_col_found = col
                break

        # 2. Nếu chưa thấy, tìm gần đúng (Fuzzy Match - bỏ khoảng trắng, chữ hoa/thường)
        if not sector_col_found:
            clean_cols = {c.lower().strip(): c for c in df.columns}
            for col in sector_candidates:
                clean_target = col.lower().strip()
                if clean_target in clean_cols:
                    sector_col_found = clean_cols[clean_target]
                    break

        # 3. Gán giá trị
        if sector_col_found:
            df['Sector'] = df[sector_col_found]
            logger.info(f"   ✅ Đã map thành công cột Sector từ '{sector_col_found}'")
        else:
            df['Sector'] = 'N/A'
            logger.warning("   ⚠️ Không tìm thấy cột Ngành (Sector), gán Sector = N/A")
            logger.debug(f"      Danh sách cột hiện có: {list(df.columns)[:10]}...")

        # 4. Dịch Sector sang tiếng Việt
        try:
            from src.constants.gics_translation import GICS_SECTOR_TRANSLATION, GICS_INDUSTRY_TRANSLATION
            df['Sector'] = (
                df['Sector'].astype(str)
                .map(lambda v: GICS_SECTOR_TRANSLATION.get(v)
                               or GICS_INDUSTRY_TRANSLATION.get(v)
                               or v)
            )
            logger.info("   ✅ Đã dịch Sector sang tiếng Việt")
        except Exception as _e:
            logger.warning(f"   ⚠️ Không thể dịch Sector: {_e}")
        # 2.2. Tính EPS (Earnings Per Share)
        # EPS = Net Income / Shares Outstanding
        if 'shares' in df.columns and df['shares'].sum() > 0:
            df['EPS'] = np.where(
                df['shares'] > 0,
                df['net_income'] / df['shares'],
                0
            )
            logger.info("   ✅ Đã tính EPS = Net Income / Shares Outstanding")
        else:
            df['EPS'] = 0
            logger.warning("   ⚠️ Không có dữ liệu shares, gán EPS = 0")

        # 2.3. Tính BVPS (Book Value Per Share)
        # BVPS = Equity / Shares Outstanding
        if 'shares' in df.columns and df['shares'].sum() > 0:
            df['BVPS'] = np.where(
                df['shares'] > 0,
                df['equity'] / df['shares'],
                0
            )
            logger.info("   ✅ Đã tính BVPS = Equity / Shares Outstanding")
        else:
            df['BVPS'] = 0
            logger.warning("   ⚠️ Không có dữ liệu shares, gán BVPS = 0")

        # 2.4. Thêm các cột raw financial data
        df['Revenue_TTM']    = df['revenue']
        df['Net_Income_TTM'] = df['net_income']
        df['EBIT_Margin']    = df.get('EBIT Margin (%)', df['Net Margin (%)'])
        logger.info("   ✅ Đã thêm Revenue_TTM, Net_Income_TTM, EBIT_Margin")

        # ===================================================================
        # 2.5. TÍNH TĂNG TRƯỞNG DOANH THU & EPS (YoY + 5Y CAGR) — VECTORIZED
        # ===================================================================
        try:
            df_fin_hist = df_financial.copy()
            if 'Date' in df_fin_hist.columns:
                df_fin_hist['Date'] = pd.to_datetime(df_fin_hist['Date'])
                df_fin_hist = df_fin_hist.sort_values(['Ticker', 'Date'])

            rev_col = find_best_column(df_fin_hist, [
                'Revenue from Business Activities - Total_x',
                'Revenue from Business Activities - Total',
                'Sales of Goods & Services - Net - Unclassified'
            ])
            eps_col = find_best_column(df_fin_hist, [
                'EPS - Basic - excl Extraordinary Items, Common - Total',
                'EPS - Basic - incl Extraordinary Items, Common - Total'
            ])

            growth_dfs = []

            def _growth_for_col(df_hist, col, yoy_name, cagr_name):
                """
                Tính YoY và 5Y CAGR cho tất cả Ticker trong 1 lần — trả về
                DataFrame với 1 dòng/Ticker (tránh MultiIndex sau groupby.apply).
                """
                records = []
                for ticker, grp in df_hist.groupby('Ticker', sort=False):
                    s = pd.to_numeric(grp[col], errors='coerce').reset_index(drop=True)
                    rec = {'Ticker': ticker}
                    if len(s) >= 2:
                        v_last, v_prev = s.iloc[-1], s.iloc[-2]
                        if pd.notna(v_last) and pd.notna(v_prev) and v_prev > 0:
                            rec[yoy_name] = round((v_last - v_prev) / abs(v_prev) * 100, 2)
                    if len(s) >= 6:
                        v_5y = s.iloc[-6]
                        if pd.notna(s.iloc[-1]) and pd.notna(v_5y) and v_5y > 0:
                            rec[cagr_name] = round(((s.iloc[-1] / v_5y) ** (1/5) - 1) * 100, 2)
                    records.append(rec)
                return pd.DataFrame(records)   # 1 row per Ticker — không MultiIndex

            if rev_col and rev_col in df_fin_hist.columns:
                rev_growth = _growth_for_col(
                    df_fin_hist, rev_col,
                    'Revenue Growth YoY (%)', 'Revenue CAGR 5Y (%)'
                )
                growth_dfs.append(rev_growth)

            if eps_col and eps_col in df_fin_hist.columns:
                eps_growth = _growth_for_col(
                    df_fin_hist, eps_col,
                    'EPS Growth YoY (%)', 'EPS CAGR 5Y (%)'
                )
                growth_dfs.append(eps_growth)

            if growth_dfs:
                from functools import reduce
                df_growth = reduce(lambda a, b: pd.merge(a, b, on='Ticker', how='outer'), growth_dfs)
                df = pd.merge(df, df_growth, on='Ticker', how='left')
                # Không fillna(0) — để NaN cho mã thiếu data (scoring xử lý NaN đúng hơn)
                logger.info("   ✅ Đã tính Revenue Growth YoY/5Y, EPS Growth YoY/5Y (vectorized)")

        except Exception as e:
            logger.warning(f"   ⚠️ Không tính được Growth metrics: {e}")
            import traceback; traceback.print_exc()

        # Đảm bảo các cột growth tồn tại (NaN nếu không tính được)
        for gcol in ['Revenue Growth YoY (%)', 'Revenue CAGR 5Y (%)',
                     'EPS Growth YoY (%)', 'EPS CAGR 5Y (%)']:
            if gcol not in df.columns:
                df[gcol] = np.nan

        # ===================================================================
        # 2.6. TÍCH HỢP TECHNICAL INDICATORS
        # ===================================================================
        try:
            from src.backend.technical_indicators import calculate_technical_indicators
            from src.backend.data_loader import load_market_data, load_index_data

            df_price_full = load_market_data()
            df_index      = load_index_data()

            df_tech = calculate_technical_indicators(df_price_full, df_index)
            if not df_tech.empty:
                df = pd.merge(df, df_tech, on='Ticker', how='left')
                logger.info(f"   ✅ Đã merge {len(df_tech.columns)-1} Technical Indicators")
        except Exception as e:
            logger.warning(f"   ⚠️ Không merge được Technical Indicators: {e}")

        # ===================================================================
        # 3. TÍNH TOÁN CÁC LOẠI ĐIỂM SỐ (Chạy tuần tự)
        # ===================================================================
        df = calculate_value_score(df)
        df = calculate_growth_score(df)
        df = calculate_momentum_score(df)
        df = calculate_vgm_score(df)
        df = calculate_canslim_score(df)

        logger.info(f"✅ Hoàn tất chấm điểm cho {len(df)} mã.")

        # ===================================================================
        # 4. LÀM TRÒN CÁC SỐ LIỆU
        # ===================================================================
        round_2_cols = ['EPS', 'BVPS', 'EBIT_Margin', 'EV/EBITDA', 'D/E', 'P/S',
                        'Gross Margin (%)', 'Dividend Yield (%)']
        for col in round_2_cols:
            if col in df.columns:
                df[col] = df[col].round(2)

        # ===================================================================
        # 5. LÀM SẠCH VÀ SẮP XẾP LẠI CỘT TRƯỚC KHI TRẢ VỀ
        # ===================================================================
        final_cols = [
            # ── Core identification ──
            'Ticker', 'Date', 'Sector', 'Company Common Name',
            'GICS Sector Name', 'GICS Industry Name', 'GICS Sub-Industry Name',

            # ── Price data ──
            'Price Close', 'Price Open', 'Price High', 'Price Low',
            'Volume', 'Avg_Vol_20D', 'Market Cap',

            # ── Valuation ──
            'P/E', 'P/B', 'P/S', 'EV', 'EV/EBITDA',
            'D/E', 'Dividend Yield (%)',

            # ── Profitability ──
            'ROE (%)', 'ROA (%)', 'Net Margin (%)', 'Gross Margin (%)',
            'EBIT Margin (%)', 'EBIT_Margin',

            # ── Per share ──
            'EPS', 'BVPS',

            # ── Financial raw TTM ──
            'Revenue_TTM', 'Net_Income_TTM',

            # ── Growth ──
            'Revenue Growth YoY (%)', 'Revenue CAGR 5Y (%)',
            'EPS Growth YoY (%)',     'EPS CAGR 5Y (%)',

            # ── Balance sheet ratios ──
            'Current Ratio', 'Net Cash', 'Net Cash / Market Cap (%)',
            'Net Cash / Assets (%)',

            # ── Technical: SMA & Price vs SMA ──
            'SMA5', 'SMA10', 'SMA20', 'SMA50', 'SMA100', 'SMA200',
            'Price_vs_SMA5', 'Price_vs_SMA10', 'Price_vs_SMA20',
            'Price_vs_SMA50', 'Price_vs_SMA100', 'Price_vs_SMA200',

            # ── Technical: Oscillators ──
            'RSI_14', 'RSI_State',
            'MACD_Histogram', 'MACD_Signal',
            'BB_Width',

            # ── Technical: Momentum & RS ──
            'Beta', 'Alpha',
            'RS_3D', 'RS_1M', 'RS_3M', 'RS_1Y', 'RS_Avg',

            # ── Technical: Performance ──
            'Perf_1W', 'Perf_1M', 'Perf_3M', 'Perf_6M', 'Perf_1Y', 'Perf_YTD',

            # ── Technical: 52W & Distance ──
            'High_52W', 'Low_52W',
            'Break_High_52W', 'Break_Low_52W',
            'Pct_From_High_1Y', 'Pct_From_Low_1Y',
            'Pct_From_High_All', 'Pct_From_Low_All',

            # ── Technical: Volume ──
            'Avg_Vol_5D', 'Avg_Vol_10D', 'Avg_Vol_50D',
            'Vol_vs_SMA5', 'Vol_vs_SMA10', 'Vol_vs_SMA20', 'Vol_vs_SMA50',
            'GTGD_1W', 'GTGD_10D', 'GTGD_1M',

            # ── Technical: Streak & Pattern ──
            'Consec_Up', 'Consec_Down', 'Candlestick_Pattern',

        ]

        # Chỉ giữ lại các cột tồn tại trong DataFrame
        valid_cols = [c for c in final_cols if c in df.columns]
        # Thêm các cột còn lại chưa có trong final_cols (từ merge GICS etc.)
        extra_cols = [c for c in df.columns if c not in valid_cols]
        valid_cols = valid_cols + extra_cols

        logger.info(f"   📋 Tổng số cột output: {len(valid_cols)}")
        # Đảm bảo GICS Industry Name tồn tại để dropdown ngành con hoạt động
        if 'GICS Industry Name' not in df.columns and 'GICS Sub-Industry Name' in df.columns:
            df['GICS Industry Name'] = df['GICS Sub-Industry Name']
        return df[valid_cols]

    except Exception as e:
        logger.error(f"❌ Lỗi không xác định trong calculate_all_scores: {e}")
        import traceback
        traceback.print_exc()
        return pd.DataFrame()
    calculate_all_strategies = calculate_all_scores