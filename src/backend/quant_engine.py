import pandas as pd
import numpy as np
import logging
import scipy.optimize as sco  # <-- THÊM DÒNG NÀY ĐỂ TỐI ƯU HÓA MARKOWITZ

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
    # LƯU Ý QUAN TRỌNG: Nếu nguồn dữ liệu KHÔNG có sẵn cột "Free Cash Flow"
    # (rất có thể xảy ra vì hầu hết vendor dữ liệu tài chính không cung cấp
    # FCF trực tiếp — nó là chỉ tiêu phái sinh = CFO - CapEx), code sẽ TỰ ĐỘNG
    # rơi xuống "Net Cash Flow from Operating Activities" (CFO) và gán nhãn
    # là 'fcf'. CFO ≠ FCF — dùng thẳng CFO sẽ làm FCF bị TÍNH CAO HƠN THỰC TẾ
    # đúng bằng phần CapEx (rất đáng kể với ngành thâm dụng vốn: BĐS, hạ tầng,
    # sản xuất). Cột `_fcf_is_estimated` bên dưới đánh dấu khi nào việc fallback
    # này xảy ra để UI/báo cáo có thể hiển thị cảnh báo minh bạch cho người dùng.
    # TODO: khi xác định được tên cột CapEx thật trong dữ liệu gốc (vd:
    # "Purchase of Fixed Assets", "Capital Expenditures - Total"...), sửa lại
    # thành FCF = CFO - CapEx để có chỉ số đúng nghĩa.
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
                if metric_name == 'fcf' and best_col != 'Free Cash Flow':
                    # Đánh dấu: đây là CFO fallback, KHÔNG PHẢI FCF thật (CFO - CapEx)
                    df_f['_fcf_is_estimated'] = True
                    logger.warning(
                        f"   ⚠️ Không có cột 'Free Cash Flow' thật — dùng fallback "
                        f"'{best_col}' (CFO), giá trị này CAO HƠN FCF thực tế "
                        f"(chưa trừ CapEx)."
                    )
                elif metric_name == 'fcf':
                    df_f['_fcf_is_estimated'] = False
            else:
                df_f[metric_name] = np.nan
                logger.warning(f"   ⚠️ Không tìm thấy cột cho: {metric_name}")

        logger.info(f"   ✅ Đã map thành công: {', '.join(found_metrics)}")

        # --- BƯỚC 3: MERGE DỮ LIỆU ---
        # Chỉ giữ lại các cột cần thiết từ df_f để tránh conflict tên cột
        fin_keep_cols = ['Ticker'] + list(SMART_MAPPING.keys()) + ['_fcf_is_estimated'] + [
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
            df_merged['P/E'] = np.where(
                df_merged['_eps_for_pe'] > 0,
                df_merged['Price Close'] / df_merged['_eps_for_pe'],
                np.nan
            )
        elif 'shares' in df_merged.columns and df_merged['shares'].sum() > 0:
            df_merged['_eps_for_pe'] = np.where(
                df_merged['shares'] > 0,
                df_merged['net_income'] / df_merged['shares'],
                np.nan
            )
            df_merged['P/E'] = np.where(
                df_merged['_eps_for_pe'] > 0,
                df_merged['Price Close'] / df_merged['_eps_for_pe'],
                np.nan
            )
        else:
            # Fallback cuối: P/E = Market Cap / Net Income trực tiếp.
            # LƯU Ý: BUG CŨ đã gán giá trị này vào "_eps_for_pe" rồi lại chia
            # Price Close cho nó lần nữa → về mặt toán học triệt tiêu ngược lại
            # thành Net Income/Shares (~EPS), KHÔNG PHẢI P/E. Giờ gán P/E trực
            # tiếp, không đi vòng qua bước chia thêm lần nữa.
            df_merged['P/E'] = np.where(
                df_merged['net_income'] > 0,
                df_merged['Market Cap'] / df_merged['net_income'],
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
            # LƯU Ý: df_merged.get(col, 0) trả về SỐ NGUYÊN 0 (không phải
            # Series) khi cột không tồn tại — gọi .fillna() lên số nguyên sẽ
            # crash ('int' object has no attribute 'fillna'). Bug này bị phát
            # hiện qua unit test khi dữ liệu thiếu HẾT cả 2 cột nợ ngắn/dài
            # hạn. Dùng Series 0 làm fallback để luôn an toàn gọi .fillna().
            _zero = pd.Series(0, index=df_merged.index)
            short_d = pd.to_numeric(df_merged.get(short_debt_col, _zero), errors='coerce').fillna(0).abs()
            long_d  = pd.to_numeric(df_merged.get(long_debt_col,  _zero), errors='coerce').fillna(0).abs()
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
        # LƯU Ý: 'Dividends Provided/Paid - Common' là TỔNG TIỀN cổ tức đã trả
        # (đơn vị: VNĐ toàn công ty), KHÔNG PHẢI cổ tức/cổ phiếu (DPS). Dùng
        # thẳng cột này làm 'dps' sẽ ra Dividend Yield sai lệch gấp hàng triệu
        # lần (vì tử số chưa chia cho số cổ phiếu đang lưu hành).
        dps_direct_col = find_best_column(df_f, [
            'DPS - Common - Net - Issue - By Announcement Date',
            'DPS - Common - Gross - Issue - By Announcement Date',
        ])
        dps_total_col = find_best_column(df_f, ['Dividends Provided/Paid - Common'])

        if dps_direct_col and dps_direct_col in df_merged.columns:
            df_merged['dps'] = pd.to_numeric(df_merged[dps_direct_col], errors='coerce').fillna(0)
        elif (dps_total_col and dps_total_col in df_merged.columns
              and 'shares' in df_merged.columns):
            # Fallback: tự tính DPS = Tổng cổ tức đã trả / Số cổ phiếu lưu hành
            total_div = pd.to_numeric(df_merged[dps_total_col], errors='coerce').fillna(0).abs()
            shares_safe = pd.to_numeric(df_merged['shares'], errors='coerce')
            df_merged['dps'] = np.where(shares_safe > 0, total_div / shares_safe, 0)
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
    except Exception as _e:  # noqa: audit-fix bare-except
        logger.debug(f"Suppressed non-critical error at src/backend/quant_engine.py:504: {_e}")
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

# Bins phân phối chuẩn: F(15%), D(20%), C(30%), B(20%), A(15%)
BELL_CURVE_BINS = [0, 0.15, 0.35, 0.65, 0.85, 1.001]
BELL_CURVE_LABELS = ['F', 'D', 'C', 'B', 'A']

def calculate_value_score(df):
    """
    VALUE SCORE: Đánh giá độ rẻ của cổ phiếu.
    Trọng số MỚI: EV/EBITDA 35% | P/E 25% | P/B 25% | P/S 15%
    """
    logger.info("📊 Đang tính Value Score (EV/EBITDA + P/E + P/B + P/S)...")
    try:
        df = df.copy()
        grade_map = {'A': 5, 'B': 4, 'C': 3, 'D': 2, 'F': 1}
        component_grades_by_name = {}  # tên cột -> grade series (tránh bug lệch vị trí)
        weights_by_name = {}

        def _grade_valuation(col, w):
            if col not in df.columns: return
            series = pd.to_numeric(df[col], errors='coerce')
            valid = series[series > 0]
            if len(valid) < 10: return
            
            # Giữ nguyên logic chia quintile cho sub-components để tính điểm
            pct = valid.quantile([0.2, 0.4, 0.6, 0.8]).to_dict()
            masked = series.where(series > 0) 
            g = _assign_grade_series(masked, pct, ascending=False)
            g[series <= 0] = 'F'
            component_grades_by_name[col] = g
            weights_by_name[col] = w

        # Ưu tiên EV/EBITDA cho cấu trúc vốn
        # LƯU Ý: Tên cột PHẢI khớp với cột thực tế do calculate_financial_metrics() tạo ra
        # (xem 'EV/EBITDA', 'P/E', 'P/B', 'P/S' trong calculate_financial_metrics),
        # nếu không toàn bộ Value Score sẽ rơi vào nhánh fallback 'F'.
        _grade_valuation('EV/EBITDA', 0.35)
        _grade_valuation('P/E',       0.25)
        _grade_valuation('P/B',       0.25)
        _grade_valuation('P/S',       0.15)

        # Lấy đúng grade theo TÊN cột, không phụ thuộc thứ tự chèn vào list
        df['Value_PE_Grade'] = component_grades_by_name.get('P/E', pd.Series('F', index=df.index))
        df['Value_PB_Grade'] = component_grades_by_name.get('P/B', pd.Series('F', index=df.index))

        if not component_grades_by_name:
            df['Value Score'] = 'F'
            return df

        total_w = sum(weights_by_name.values())
        score_num = pd.Series(0.0, index=df.index)
        for col, grade_series in component_grades_by_name.items():
            w = weights_by_name[col] / total_w
            score_num += grade_series.map(grade_map).fillna(1) * w

        df['Value_Score_Num'] = score_num
        pct_rank = score_num.rank(pct=True, na_option='bottom')
        df['Value_Score_Pct'] = (pct_rank * 100).round(0)   # ← THÊM DÒNG NÀY: thang 0–100
        
        # Áp dụng Bell Curve để phân loại
        df['Value Score'] = pd.cut(pct_rank, bins=BELL_CURVE_BINS, labels=BELL_CURVE_LABELS).astype(str)
        df.loc[score_num.isna(), 'Value Score'] = 'F'

        return df

    except Exception as e:
        logger.error(f"Lỗi tính Value Score: {e}")
        df['Value Score'] = 'F'
        return df


def calculate_growth_score(df):
    """
    GROWTH SCORE: 
    Trọng số MỚI: EPS Growth 40% | Rev Growth 30% | ROE 20% | ROA 10%
    """
    logger.info("📊 Đang tính Growth Score (EPS ưu tiên)...")
    try:
        df = df.copy()
        grade_map = {'A': 5, 'B': 4, 'C': 3, 'D': 2, 'F': 1}
        component_grades = []
        weights = []

        # LƯU Ý: Tên cột PHẢI khớp với cột thực tế do calculate_financial_metrics()/
        # calculate_all_scores() tạo ra ('EPS Growth YoY (%)', 'Revenue Growth YoY (%)',
        # 'ROE (%)', 'ROA (%)'), nếu không toàn bộ Growth Score sẽ rơi vào fallback 'F'.

        # EPS Growth YoY (40%) - Driver chính
        if 'EPS Growth YoY (%)' in df.columns:
            eps_g = pd.to_numeric(df['EPS Growth YoY (%)'], errors='coerce')
            valid = eps_g.dropna()
            if len(valid) >= 10:
                pct = valid.quantile([0.2, 0.4, 0.6, 0.8]).to_dict()
                component_grades.append(_assign_grade_series(eps_g, pct, ascending=True))
                weights.append(0.40)

        # Rev Growth YoY (30%)
        if 'Revenue Growth YoY (%)' in df.columns:
            rev_g = pd.to_numeric(df['Revenue Growth YoY (%)'], errors='coerce')
            valid = rev_g.dropna()
            if len(valid) >= 10:
                pct = valid.quantile([0.2, 0.4, 0.6, 0.8]).to_dict()
                component_grades.append(_assign_grade_series(rev_g, pct, ascending=True))
                weights.append(0.30)

        # ROE (20%)
        if 'ROE (%)' in df.columns:
            roe = pd.to_numeric(df['ROE (%)'], errors='coerce')
            roe_valid = roe.where(roe > 0)
            valid = roe_valid.dropna()
            if len(valid) >= 10:
                pct = valid.quantile([0.2, 0.4, 0.6, 0.8]).to_dict()
                g = _assign_grade_series(roe_valid, pct, ascending=True)
                g[roe <= 0] = 'F'
                component_grades.append(g)
                weights.append(0.20)

        # ROA (10%)
        if 'ROA (%)' in df.columns:
            roa = pd.to_numeric(df['ROA (%)'], errors='coerce')
            roa_valid = roa.where(roa > 0)
            valid = roa_valid.dropna()
            if len(valid) >= 10:
                pct = valid.quantile([0.2, 0.4, 0.6, 0.8]).to_dict()
                g = _assign_grade_series(roa_valid, pct, ascending=True)
                g[roa <= 0] = 'F'
                component_grades.append(g)
                weights.append(0.10)

        if not component_grades:
            df['Growth Score'] = 'F'
            return df

        total_w = sum(weights)
        weights = [w / total_w for w in weights]

        score_num = pd.Series(0.0, index=df.index)
        for grade_series, w in zip(component_grades, weights):
            score_num += grade_series.map(grade_map).fillna(1) * w

        # Sector-relative adjustment
        if 'Sector' in df.columns and 'ROE (%)' in df.columns:
            try:
                roe = pd.to_numeric(df['ROE (%)'], errors='coerce')
                sector_rank = df.groupby('Sector')['ROE (%)'].transform(lambda x: pd.to_numeric(x, errors='coerce').rank(pct=True)).fillna(0.5)
                market_rank = roe.rank(pct=True).fillna(0.5)
                blended = (sector_rank * 0.5 + market_rank * 0.5) * 4 + 1
                adjustment = (blended - score_num).clip(-0.3, 0.3)
                score_num = score_num + adjustment
            except: pass

        df['Growth_Score_Num'] = score_num
        pct_rank = score_num.rank(pct=True, na_option='bottom')
        df['Growth_Score_Pct'] = (pct_rank * 100).round(0)   # ← THÊM DÒNG NÀY
        
        # Áp dụng Bell Curve
        df['Growth Score'] = pd.cut(pct_rank, bins=BELL_CURVE_BINS, labels=BELL_CURVE_LABELS).astype(str)
        df.loc[score_num.isna(), 'Growth Score'] = 'F'

        return df
    except Exception as e:
        logger.error(f"Lỗi tính Growth Score: {e}")
        df['Growth Score'] = 'F'
        return df


def calculate_momentum_score(df):
    """
    MOMENTUM SCORE: 
    Bỏ Perf_1W (noise). Dùng Price_vs_SMA50_% để đo lường cấu trúc trend.
    Trọng số MỚI: RS_3M 35% | RS_1M 30% | Price_vs_SMA50 20% | Perf_1M 15%
    """
    logger.info("📊 Đang tính Momentum Score (RS + SMA Trend)...")
    try:
        df = df.copy()
        grade_map = {'A': 5, 'B': 4, 'C': 3, 'D': 2, 'F': 1}
        momentum_grades = []
        weights = []

        if 'RS_3M' in df.columns:
            rs3m = pd.to_numeric(df['RS_3M'], errors='coerce')
            valid = rs3m.dropna()
            if len(valid) >= 10:
                pct = valid.quantile([0.2, 0.4, 0.6, 0.8]).to_dict()
                momentum_grades.append(_assign_grade_series(rs3m, pct, ascending=True))
                weights.append(0.35)

        if 'RS_1M' in df.columns:
            rs1m = pd.to_numeric(df['RS_1M'], errors='coerce')
            valid = rs1m.dropna()
            if len(valid) >= 10:
                pct = valid.quantile([0.2, 0.4, 0.6, 0.8]).to_dict()
                momentum_grades.append(_assign_grade_series(rs1m, pct, ascending=True))
                weights.append(0.30)

        # Thay Perf_1W bằng Price_vs_SMA50_%
        if 'Price_vs_SMA50_%' in df.columns:
            sma50 = pd.to_numeric(df['Price_vs_SMA50_%'], errors='coerce')
            valid = sma50.dropna()
            if len(valid) >= 10:
                pct = valid.quantile([0.2, 0.4, 0.6, 0.8]).to_dict()
                momentum_grades.append(_assign_grade_series(sma50, pct, ascending=True))
                weights.append(0.20)

        if 'Perf_1M_%' in df.columns:
            p1m = pd.to_numeric(df['Perf_1M_%'], errors='coerce')
            valid = p1m.dropna()
            if len(valid) >= 10:
                pct = valid.quantile([0.2, 0.4, 0.6, 0.8]).to_dict()
                momentum_grades.append(_assign_grade_series(p1m, pct, ascending=True))
                weights.append(0.15)

        if not momentum_grades:
            df['Momentum Score'] = 'C'
            return df

        total_w = sum(weights)
        weights = [w / total_w for w in weights]

        score_num = pd.Series(0.0, index=df.index)
        for grade_series, w in zip(momentum_grades, weights):
            score_num += grade_series.map(grade_map).fillna(3) * w

        df['Momentum_Score_Num'] = score_num
        pct_rank = score_num.rank(pct=True, na_option='bottom')
        df['Momentum_Score_Pct'] = (pct_rank * 100).round(0)   # ← THÊM DÒNG NÀY
        
        # Áp dụng Bell Curve
        df['Momentum Score'] = pd.cut(pct_rank, bins=BELL_CURVE_BINS, labels=BELL_CURVE_LABELS).astype(str)
        
        missing_mask = df.get('RS_1M', pd.Series(dtype=float)).isna() & df.get('RS_3M', pd.Series(dtype=float)).isna()
        df.loc[missing_mask, 'Momentum Score'] = 'C'

        return df
    except Exception as e:
        logger.error(f"Lỗi tính Momentum Score: {e}")
        df['Momentum Score'] = 'C'
        return df


def calculate_vgm_score(df, as_of_date=None):
    """
    VGM SCORE: Tổng hợp Value + Growth + Momentum.
    Giữ nguyên logic Staleness adjustment, áp dụng Bell Curve cho kết quả cuối.

    as_of_date : Timestamp | None
        Mốc thời gian dùng để tính "độ cũ" (staleness) của BCTC.
        - None (mặc định) -> dùng pd.Timestamp.now() như cũ, GIỮ NGUYÊN hành vi
          hiện tại của ứng dụng live (KHÔNG đổi gì cho production).
        - Khi được truyền (vd từ backtest, = ngày đang mô phỏng), staleness
          được tính so với đúng ngày lịch sử đó thay vì "hôm nay" thật —
          tránh việc BCTC 2023 bị chấm bằng độ cũ của năm 2026.
    """
    logger.info("📊 Đang tính VGM Score...")
    try:
        df = df.copy()
        grade_points = {'A': 5, 'B': 4, 'C': 3, 'D': 2, 'F': 1}

        v_points = df['Value Score'].map(grade_points).fillna(1)
        g_points = df['Growth Score'].map(grade_points).fillna(1)
        m_points = df['Momentum Score'].map(grade_points).fillna(3)

        w_v, w_g, w_m = 0.30, 0.40, 0.30  

        if 'Date' in df.columns:
            try:
                fin_date = pd.to_datetime(df['Date'], errors='coerce')
                now = pd.Timestamp(as_of_date) if as_of_date is not None else pd.Timestamp.now()
                months_stale = ((now - fin_date).dt.days / 30).fillna(12)
                stale_mask = months_stale > 9
                
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

        pct_rank_vgm = df['VGM_Score_Num'].rank(pct=True, na_option='bottom')
        df['VGM_Score_Pct'] = (pct_rank_vgm * 100).round(0)   # ← THÊM DÒNG NÀY
        
        # Áp dụng Bell Curve cho Final Score
        df['VGM Score'] = pd.cut(pct_rank_vgm, bins=BELL_CURVE_BINS, labels=BELL_CURVE_LABELS).astype(str)
        df.loc[df['VGM_Score_Num'].isna(), 'VGM Score'] = 'F'

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
#Thêm hàm tính điểm vào quant_engine.py
def calculate_tplus_score(df):
    """
    T_PLUS_SCORE (Thang điểm 100): ĐIỂM TÍN HIỆU kỹ thuật ngắn hạn T+2.5
    (KHÔNG PHẢI xác suất đã hiệu chỉnh/backtest — đây là tổng điểm cộng dồn
    theo quy tắc: Dòng tiền, Động lượng MACD/SMA5, Sức mạnh RS 3 ngày, RSI).
    Muốn gọi là "xác suất" cần backtest walk-forward + calibration (Brier
    score, reliability curve) trước — hiện chưa có, nên không dùng từ này
    khi hiển thị cho người dùng.
    """
    logger.info("⚡ Đang tính T+2.5 Score...")
    try:
        df = df.copy()
        score = pd.Series(0.0, index=df.index)

        # 1. Dòng tiền đột biến — 30 điểm
        vol_ratio = pd.to_numeric(df.get('Vol_vs_SMA20', 0), errors='coerce').fillna(0)
        score += np.where(vol_ratio >= 1.5, 30, np.where(vol_ratio >= 1.2, 15, 0))

        # 2. Giá nằm trên SMA5 — 20 điểm
        p_sma5 = pd.to_numeric(df.get('Price_vs_SMA5', 0), errors='coerce').fillna(0)
        score += np.where(p_sma5 > 0, 20, 0)

        # 3. MACD Histogram dương — 20 điểm
        macd_hist = pd.to_numeric(df.get('MACD_Histogram', 0), errors='coerce').fillna(0)
        score += np.where(macd_hist > 0, 20, 0)

        # 4. RS 3 phiên dương — 20 điểm
        rs_3d = pd.to_numeric(df.get('RS_3D', 0), errors='coerce').fillna(0)
        score += np.where(rs_3d > 0, 20, 0)

        # 5. RSI trong vùng 45–65 — 10 điểm
        rsi = pd.to_numeric(df.get('RSI_14', 50), errors='coerce').fillna(50)
        score += np.where((rsi > 45) & (rsi < 65), 10, 0)

        # Penalty: cách đỉnh 1Y quá xa
        pct_from_high = pd.to_numeric(df.get('Pct_From_High_1Y', 0), errors='coerce').fillna(-100)
        score -= np.where(pct_from_high < -30, 10, 0)

        df['T_Plus_Score'] = score.clip(0, 100)
        logger.info(f"   ✅ T+2.5 Score xong — {(df['T_Plus_Score'] >= 80).sum()} mã đạt >= 80đ")
        return df

    except Exception as e:
        logger.error(f"Lỗi tính T+2.5 Score: {e}")
        df['T_Plus_Score'] = 0
        return df

# ==============================================================================
# 4. HÀM CHÍNH (ORCHESTRATOR) - ENHANCED VERSION
# ==============================================================================

def calculate_all_scores(df_price, df_financial, as_of_date=None,
                          df_price_full_override=None, df_index_override=None):
    """
    Hàm chính điều phối toàn bộ quy trình tính toán - ENHANCED VERSION.
    Được gọi từ data_loader.py.

    UPDATES:
    - Thêm cột Sector (từ GICS Sector Name)
    - Tính EPS (Earnings Per Share)
    - Tính BVPS (Book Value Per Share)
    - Thêm Revenue_TTM, Net_Income_TTM, EBIT_Margin
    - Bao gồm Price Open, High, Low cho technical analysis

    POINT-IN-TIME PARAMS (mặc định None -> hành vi live app GIỮ NGUYÊN 100%):
    as_of_date : Timestamp | None
        Ngày đang mô phỏng (backtest). Truyền xuống calculate_vgm_score() để
        staleness của BCTC được tính theo đúng ngày lịch sử, không phải
        pd.Timestamp.now() thật.
    df_price_full_override / df_index_override : DataFrame | None
        Khi được truyền (từ backtest), thay thế HOÀN TOÀN việc tự gọi
        load_market_data()/load_index_data() bên trong hàm này (kể cả ở khối
        Technical Indicators và khối ADX/Lifecycle) — đây chính là điểm rò rỉ
        look-ahead bias gốc: 2 khối đó tự load TOÀN BỘ dữ liệu hiện có trên
        đĩa bất kể df_price truyền vào ở tham số đầu tiên đã được cắt tới
        as_of_date hay chưa. Khi override được cung cấp, dữ liệu ĐÃ được cắt
        point-in-time bởi caller (backtest.py) sẽ được dùng thay thế, đảm bảo
        không có ngày nào > as_of_date lọt vào tính toán kỹ thuật.
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
        # LƯU Ý QUAN TRỌNG VỀ TÊN GỌI: "Revenue_TTM"/"Net_Income_TTM" ở đây
        # thực chất lấy từ df['revenue']/df['net_income'], vốn được build từ
        # load_financial_data("yearly") — tức là DOANH THU/LNST CỦA NĂM TÀI
        # CHÍNH GẦN NHẤT, KHÔNG PHẢI trailing-twelve-months thật (tổng 4 quý
        # gần nhất). TTM thật đã được tính đúng ở nơi khác trong dự án (xem
        # pdf_export_callback.py hàm _p6: TTM = qtr_df.tail(4).sum() theo từng
        # chỉ tiêu) — nhưng pipeline snapshot chính (dùng cho toàn bộ Screener)
        # chỉ load dữ liệu yearly để tiết kiệm RAM khi host (xem comment trong
        # data_loader.py: quarterly ~100MB, tránh giữ mãi trong RAM).
        # Muốn có TTM thật ở đây cần merge thêm quarterly data vào snapshot —
        # đây là đánh đổi hiệu năng/bộ nhớ cần cân nhắc kỹ trước khi đổi,
        # không sửa vội trong bản vá này. Trước mắt, KHÔNG hiển thị các cột
        # này với nhãn "(TTM)" ra UI nếu nguồn thực chất là dữ liệu năm gần
        # nhất — xem sửa nhãn "P/E (TTM)" → "P/E (Năm gần nhất)" bên dưới.
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
                            if v_5y > 0 and s.iloc[-1] > 0:
                                rec[cagr_name] = round(((s.iloc[-1] / v_5y) ** (1/5) - 1) * 100, 2)
                            else:
                                rec[cagr_name] = np.nan
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

            if df_price_full_override is not None:
                df_price_full = df_price_full_override
                df_index      = df_index_override
            else:
                from src.backend.data_loader import load_market_data, load_index_data
                df_price_full = load_market_data()
                df_index      = load_index_data()

            if as_of_date is not None and df_price_full is not None and not df_price_full.empty:
                _max_px_date = pd.to_datetime(df_price_full["Date"], errors="coerce").max()
                assert _max_px_date <= pd.Timestamp(as_of_date), (
                    f"[PIT VIOLATION] Technical indicators nhìn thấy giá tới "
                    f"{_max_px_date.date()} > as_of_date {pd.Timestamp(as_of_date).date()}"
                )

            df_tech = calculate_technical_indicators(df_price_full, df_index)
            if not df_tech.empty:
                df = pd.merge(df, df_tech, on='Ticker', how='left')
                logger.info(f"   ✅ Đã merge {len(df_tech.columns)-1} Technical Indicators")
        except Exception as e:
            logger.warning(f"   ⚠️ Không merge được Technical Indicators: {e}")
        
        # ── ELLIOTT WAVE PROXY ────────────────────────────────────────────
        try:
            # 1. Fibonacci Retracement Level (%) so với range 52W
            #    0% = đáy 52W, 100% = đỉnh 52W
            #    Vùng quan trọng: 38.2%, 50%, 61.8%
            if all(c in df.columns for c in ['Price Close', 'High_52W', 'Low_52W']):
                price  = pd.to_numeric(df['Price Close'], errors='coerce')
                hi52   = pd.to_numeric(df['High_52W'],    errors='coerce')
                lo52   = pd.to_numeric(df['Low_52W'],      errors='coerce')
                rng    = hi52 - lo52
                df['Fib_Position_%'] = np.where(
                    rng > 0,
                    ((price - lo52) / rng * 100).round(1),
                    np.nan
                )
                # Nhãn vùng Fib: xác định đang ở vùng nào
                fib = df['Fib_Position_%']
                df['Fib_Zone'] = np.select(
                    [
                        fib <= 23.6,
                        (fib > 23.6)  & (fib <= 38.2),
                        (fib > 38.2)  & (fib <= 50.0),
                        (fib > 50.0)  & (fib <= 61.8),
                        (fib > 61.8)  & (fib <= 78.6),
                        fib > 78.6,
                    ],
                    [
                        'Zone0_236',    # Dưới 23.6% — gần đáy, sóng C/5 có thể kết thúc
                        'Zone1_382',    # 23.6–38.2% — hồi얕 (sóng 2 nông)
                        'Zone2_500',    # 38.2–50%   — vùng hồi trung bình
                        'Zone3_618',    # 50–61.8%   — vùng hồi sâu lý tưởng (sóng 2/4)
                        'Zone4_786',    # 61.8–78.6% — hồi sâu, test lại
                        'Zone5_Top',    # >78.6%     — gần đỉnh, tiệm cận sóng 3/5
                    ],
                    default='Unknown'
                )

            # 2. Wave Momentum Score (0-100)
            #    Kết hợp các tín hiệu để ước lượng vị trí sóng đẩy hay sóng hồi
            wave_score = pd.Series(0.0, index=df.index)

            # Tín hiệu đang trong sóng đẩy (impulse):
            if 'MACD_Histogram' in df.columns:
                macd = pd.to_numeric(df['MACD_Histogram'], errors='coerce').fillna(0)
                wave_score += np.where(macd > 0, 20, 0)           # MACD dương = đẩy

            if 'Price_vs_SMA20' in df.columns:
                sma20 = pd.to_numeric(df['Price_vs_SMA20'], errors='coerce').fillna(0)
                wave_score += np.where(sma20 > 0, 15, 0)          # Trên SMA20

            if 'Price_vs_SMA50' in df.columns:
                sma50 = pd.to_numeric(df['Price_vs_SMA50'], errors='coerce').fillna(0)
                wave_score += np.where(sma50 > 2, 15, 0)          # Trên SMA50 > 2%

            if 'RSI_14' in df.columns:
                rsi = pd.to_numeric(df['RSI_14'], errors='coerce').fillna(50)
                wave_score += np.where(
                    (rsi >= 50) & (rsi <= 70), 20,                 # RSI 50-70 = sóng đẩy khỏe
                    np.where(rsi > 70, 10, 0)                      # RSI > 70 = cuối sóng 3/5
                )

            if 'Vol_vs_SMA20' in df.columns:
                vol = pd.to_numeric(df['Vol_vs_SMA20'], errors='coerce').fillna(1)
                wave_score += np.where(vol >= 1.5, 15, np.where(vol >= 1.2, 8, 0))

            if 'Consec_Up' in df.columns:
                cu = pd.to_numeric(df['Consec_Up'], errors='coerce').fillna(0)
                wave_score += np.where(cu >= 3, 15, np.where(cu >= 1, 7, 0))

            df['Wave_Momentum_Score'] = wave_score.clip(0, 100).round(1)

            # 3. Corrective Flag — đang trong sóng điều chỉnh (ABC)
            #    True nếu: giá dưới SMA50 VÀ RSI < 50 VÀ MACD âm
            corr_flag = pd.Series(False, index=df.index)
            if all(c in df.columns for c in ['Price_vs_SMA50', 'RSI_14', 'MACD_Histogram']):
                corr_flag = (
                    (pd.to_numeric(df['Price_vs_SMA50'],   errors='coerce').fillna(0)  < 0) &
                    (pd.to_numeric(df['RSI_14'],            errors='coerce').fillna(50) < 50) &
                    (pd.to_numeric(df['MACD_Histogram'],    errors='coerce').fillna(0)  < 0)
                )
            df['Elliott_Corrective'] = corr_flag.astype(int)  # 1 = đang hồi, 0 = có thể đẩy

            logger.info("✅ Elliott Wave proxy columns added: Fib_Position_%, Fib_Zone, Wave_Momentum_Score, Elliott_Corrective")

        except Exception as _ew_err:
            logger.warning(f"Elliott proxy error: {_ew_err}")
        # ── KẾT THÚC ELLIOTT WAVE PROXY ──────────────────────────────────

        # ── ADX(14) + Plus_DI/Minus_DI + RSI(14) — Lifecycle 5 mức độ ───────
        # ADX chỉ đo ĐỘ MẠNH của xu hướng, không đo HƯỚNG.
        # Plus_DI > Minus_DI => xu hướng đang nghiêng về phía TĂNG.
        # Plus_DI < Minus_DI => xu hướng đang nghiêng về phía GIẢM.
        #
        # ADX_State — phân loại trạng thái xu hướng (giữ nguyên, dùng cho cột
        # hiển thị/dropdown filter riêng — KHÔNG liên quan tới Lifecycle dưới đây):
        #   🔄 Đảo chiều Tăng / Giảm (lookback 3 phiên) · 🔥 Siêu Xu Hướng ·
        #   📈 Xu hướng Tăng · 📉 Xu hướng Giảm · ➖ Đi ngang
        #
        # Lifecycle_State — 5 MỨC ĐỘ THEO VÒNG ĐỜI XU HƯỚNG (ADX kết hợp RSI),
        # dùng để loại trừ mã đang ở Mức 4/5 khỏi preset ADX Momentum:
        #   Mức 1 — Setup Chân sóng    : ADX<20 & RSI vừa cắt LÊN 50 (5 phiên gần nhất)
        #   Mức 2 — Breakout Khởi điểm : ADX vừa cắt LÊN 25 (5 phiên) & +DI>-DI & RSI in [60,70]
        #   Mức 3 — Pullback Lành mạnh : ADX>=25 & RSI vừa rớt từ >70 về [45,50] & đang vòng lên
        #   Mức 4 — Phân kỳ Âm        : ADX>=35 & đỉnh giá mới > đỉnh giá cũ (10 phiên)
        #                                NHƯNG đỉnh RSI mới < đỉnh RSI cũ (phân kỳ âm)
        #   Mức 5 — Sideway Trap       : ADX cắm đầu rơi từ >40 xuống <25 & RSI giật cục [40,60]
        _ADX_REVERSAL_LOOKBACK   = 3   # lookback đảo chiều ADX_State (giữ nguyên)
        _LIFECYCLE_CROSS_LB      = 5   # lookback crossover RSI/ADX cho Mức 1, 2
        _LIFECYCLE_PEAK_LB       = 10  # lookback tìm đỉnh giá/RSI cho Mức 4
        try:
            if df_price_full_override is not None:
                _df_px_adx = df_price_full_override
            else:
                from src.backend.data_loader import load_market_data as _load_px
                _df_px_adx = _load_px()
            if as_of_date is not None and _df_px_adx is not None and not _df_px_adx.empty:
                _max_adx_date = pd.to_datetime(_df_px_adx["Date"], errors="coerce").max()
                assert _max_adx_date <= pd.Timestamp(as_of_date), (
                    f"[PIT VIOLATION] ADX nhìn thấy giá tới {_max_adx_date.date()} "
                    f"> as_of_date {pd.Timestamp(as_of_date).date()}"
                )
            if not _df_px_adx.empty:
                _adx_records = []
                for _ticker, _grp in _df_px_adx.groupby("Ticker", sort=False):
                    _g = _grp.sort_values("Date").tail(300).copy()
                    if len(_g) < 30:
                        _adx_records.append({"Ticker": _ticker, "ADX_14": None,
                                              "Plus_DI_14": None, "Minus_DI_14": None,
                                              "ADX_State": None, "Lifecycle_State": None,
                                              "Is_Steady_Uptrend": False,
                                              "Is_Super_Stock_ADX": False,
                                              "Is_Not_Sideway_ADX": False,
                                              "Is_Lifecycle_Excluded": False})
                        continue
                    try:
                        _high  = pd.to_numeric(_g["Price High"],  errors="coerce")
                        _low   = pd.to_numeric(_g["Price Low"],   errors="coerce")
                        _close = pd.to_numeric(_g["Price Close"], errors="coerce")
                        _prev  = _close.shift(1)
                        _tr = pd.concat([
                            (_high - _low).abs(),
                            (_high - _prev).abs(),
                            (_low  - _prev).abs(),
                        ], axis=1).max(axis=1)
                        _up   = _high - _high.shift(1)
                        _down = _low.shift(1) - _low
                        _pdm  = np.where((_up > _down) & (_up > 0), _up,   0.0)
                        _mdm  = np.where((_down > _up) & (_down > 0), _down, 0.0)
                        _a = 1.0 / 14
                        def _rma(s):
                            return pd.Series(s, index=_g.index).ewm(alpha=_a, adjust=False).mean()
                        _atr14 = _rma(_tr.values)
                        _pdi   = 100 * _rma(_pdm) / _atr14.replace(0, np.nan)
                        _mdi   = 100 * _rma(_mdm) / _atr14.replace(0, np.nan)
                        _dx    = 100 * (_pdi - _mdi).abs() / (_pdi + _mdi).replace(0, np.nan)
                        _adx   = _dx.ewm(alpha=_a, adjust=False).mean()
                        _val      = round(float(_adx.iloc[-1]), 2) if not np.isnan(_adx.iloc[-1]) else None
                        _pdi_val  = round(float(_pdi.iloc[-1]), 2) if not np.isnan(_pdi.iloc[-1]) else None
                        _mdi_val  = round(float(_mdi.iloc[-1]), 2) if not np.isnan(_mdi.iloc[-1]) else None
                        # _adx_prev1: dùng cho phân loại ADX_State (đảo chiều, lookback 3 phiên)
                        _adx_prev1 = float(_adx.iloc[-2]) if len(_adx) >= 2 and not np.isnan(_adx.iloc[-2]) else None

                        # RSI(14) — tính cùng lúc với ADX (cần full series cho Lifecycle)
                        _delta = _close.diff()
                        _gain  = _delta.clip(lower=0)
                        _loss  = (-_delta).clip(lower=0)
                        _avg_gain = _gain.ewm(com=13, min_periods=14).mean()
                        _avg_loss = _loss.ewm(com=13, min_periods=14).mean()
                        _rs   = _avg_gain / _avg_loss.replace(0, np.nan)
                        _rsi  = 100 - (100 / (1 + _rs))
                        _rsi_val = round(float(_rsi.iloc[-1]), 2) if not np.isnan(_rsi.iloc[-1]) else None

                        # ── Phân loại ADX_State (lookback đảo chiều: 3 phiên) ──
                        _state = None
                        if _val is not None and _pdi_val is not None and _mdi_val is not None:
                            _lb = min(_ADX_REVERSAL_LOOKBACK, len(_adx) - 1)
                            _diff_recent = (_pdi - _mdi).tail(_lb + 1)
                            _sign_recent = np.sign(_diff_recent.dropna())
                            _crossed_up   = (len(_sign_recent) >= 2) and (_sign_recent.iloc[-1] > 0) and (_sign_recent.iloc[:-1] <= 0).any()
                            _crossed_down = (len(_sign_recent) >= 2) and (_sign_recent.iloc[-1] < 0) and (_sign_recent.iloc[:-1] >= 0).any()
                            _adx_rising  = (_adx_prev1 is not None) and (_val > _adx_prev1)

                            if _crossed_up and _adx_rising:
                                _state = "🔄 Đảo chiều Tăng"
                            elif _crossed_down:
                                _state = "🔄 Đảo chiều Giảm"
                            elif _val >= 50:
                                _state = "🔥 Siêu Xu Hướng"
                            elif _val >= 25 and _pdi_val > _mdi_val:
                                _state = "📈 Xu hướng Tăng"
                            elif _val >= 25 and _mdi_val > _pdi_val:
                                _state = "📉 Xu hướng Giảm"
                            else:
                                _state = "➖ Đi ngang"

                        # ── Lifecycle_State — 5 mức độ ADX + RSI ──────────────────────
                        _lifecycle = None
                        if _val is not None and _rsi_val is not None and len(_adx) >= 15:
                            _lb5  = min(_LIFECYCLE_CROSS_LB, len(_adx) - 1)
                            _lb10 = min(_LIFECYCLE_PEAK_LB, len(_adx) - 1)

                            _rsi_tail5  = _rsi.tail(_lb5 + 1)
                            _adx_tail5  = _adx.tail(_lb5 + 1)

                            # Mức 1: ADX<20 & RSI vừa cắt LÊN 50 trong 5 phiên gần nhất
                            _rsi_crossed_50 = (
                                len(_rsi_tail5.dropna()) >= 2
                                and _rsi_tail5.iloc[-1] > 50
                                and (_rsi_tail5.iloc[:-1] <= 50).any()
                            )
                            _is_m1 = bool(_val < 20 and _rsi_crossed_50)

                            # Mức 2: ADX vừa cắt LÊN 25 trong 5 phiên & +DI>-DI & RSI in [60,70]
                            _adx_crossed_25 = (
                                len(_adx_tail5.dropna()) >= 2
                                and _adx_tail5.iloc[-1] >= 25
                                and (_adx_tail5.iloc[:-1] < 25).any()
                            )
                            _is_m2 = bool(
                                _adx_crossed_25 and _pdi_val is not None and _mdi_val is not None
                                and _pdi_val > _mdi_val and 60 <= _rsi_val <= 70
                            )

                            # Mức 3: ADX>=25 & RSI vừa rớt từ >70 về [45,50] và đang vòng lên
                            # (xét trong 10 phiên gần nhất: từng có RSI>70, hiện tại RSI in [45,50]
                            #  và RSI phiên cuối > RSI phiên trước đó — đã bắt đầu hồi lên)
                            _rsi_tail10 = _rsi.tail(_lb10 + 1)
                            _had_rsi_over_70 = bool((_rsi_tail10 > 70).any())
                            _rsi_turning_up = bool(len(_rsi) >= 2 and _rsi.iloc[-1] > _rsi.iloc[-2])
                            _is_m3 = bool(
                                _val >= 25 and _had_rsi_over_70
                                and 45 <= _rsi_val <= 50 and _rsi_turning_up
                            )

                            # Mức 4: ADX>=35 & đỉnh GIÁ mới (10 phiên) > đỉnh giá cũ trước đó,
                            # NHƯNG đỉnh RSI tương ứng lại thấp hơn (phân kỳ âm — bearish divergence)
                            _close_tail10 = _close.tail(_lb10 + 1)
                            _close_prior  = _close.iloc[:-(_lb10 + 1)] if len(_close) > _lb10 + 1 else pd.Series(dtype=float)
                            _is_m4 = False
                            if _val is not None and _val >= 35 and len(_close_prior) >= 10:
                                _peak_price_recent = _close_tail10.max()
                                _peak_price_prior   = _close_prior.tail(30).max()  # đỉnh trước đó (30 phiên trước nữa)
                                _idx_peak_recent = _close_tail10.idxmax()
                                _idx_peak_prior   = _close_prior.tail(30).idxmax()
                                if (_peak_price_recent > _peak_price_prior
                                        and _idx_peak_recent in _rsi.index and _idx_peak_prior in _rsi.index):
                                    _rsi_at_peak_recent = _rsi.loc[_idx_peak_recent]
                                    _rsi_at_peak_prior  = _rsi.loc[_idx_peak_prior]
                                    if (not np.isnan(_rsi_at_peak_recent) and not np.isnan(_rsi_at_peak_prior)
                                            and _rsi_at_peak_recent < _rsi_at_peak_prior):
                                        _is_m4 = True

                            # Mức 5: ADX cắm đầu rơi từ >40 xuống <25 (trong 10 phiên) &
                            # RSI giật cục trong biên hẹp [40,60] suốt giai đoạn đó
                            _adx_tail10 = _adx.tail(_lb10 + 1)
                            _is_m5 = bool(
                                _val < 25 and len(_adx_tail10.dropna()) >= 2
                                and _adx_tail10.max() > 40
                                and _rsi_tail10.between(40, 60).all()
                            )

                            # Thứ tự ưu tiên gán nhãn: Mức 5 (rủi ro cao nhất) > Mức 4 > 2 > 3 > 1
                            if _is_m5:
                                _lifecycle = "5️⃣ Sideway Trap (Bẫy nhiễu)"
                            elif _is_m4:
                                _lifecycle = "4️⃣ Phân kỳ Âm (Cảnh báo đỉnh)"
                            elif _is_m2:
                                _lifecycle = "2️⃣ Breakout Khởi điểm"
                            elif _is_m3:
                                _lifecycle = "3️⃣ Pullback Lành mạnh"
                            elif _is_m1:
                                _lifecycle = "1️⃣ Setup Chân sóng"

                        _is_lifecycle_excluded = bool(
                            _lifecycle is not None
                            and (_lifecycle.startswith("4️⃣") or _lifecycle.startswith("5️⃣"))
                        )

                        # ── Chiến lược ADX — 3 trụ cột checkbox (Sidebar, BẢN CẢI TIẾN v3) ──
                        # ☐ Xu hướng Tăng vững vàng (Is_Steady_Uptrend):
                        #     +DI > -DI  AND  ADX >= 25  — ĐÚNG CHUẨN WILDER GỐC.
                        # ☐ Siêu Cổ Phiếu Tăng Giá (Is_Super_Stock_ADX):
                        #     (+DI>-DI AND ADX>=50) đúng >=50% trong 20 phiên gần nhất.
                        # ☐ Bỏ qua Sideway (Is_Not_Sideway_ADX): giữ nguyên — ADX >= 25.
                        _is_steady_uptrend = bool(
                            _pdi_val is not None and _mdi_val is not None and _val is not None
                            and _pdi_val > _mdi_val and _val >= 25
                        )
                        _is_not_sideway = bool(_val is not None and _val >= 25)

                        _is_super_stock = False
                        if _val is not None:
                            _lb20 = min(20, len(_adx))
                            _pdi_20 = _pdi.tail(_lb20)
                            _mdi_20 = _mdi.tail(_lb20)
                            _adx_20 = _adx.tail(_lb20)
                            _pillar_ok = (_pdi_20 > _mdi_20) & (_adx_20 >= 50)
                            _n_total = len(_pillar_ok.dropna())
                            if _n_total >= 15:  # cần đủ dữ liệu hợp lệ để đánh giá độ bền
                                _n_ok = int(_pillar_ok.fillna(False).sum())
                                _is_super_stock = bool((_n_ok / _n_total) >= 0.50)
                    except Exception:
                        _val, _pdi_val, _mdi_val, _state = None, None, None, None
                        _lifecycle, _is_lifecycle_excluded = None, False
                        _is_steady_uptrend, _is_super_stock, _is_not_sideway = False, False, False
                    _adx_records.append({"Ticker": _ticker, "ADX_14": _val,
                                          "Plus_DI_14": _pdi_val, "Minus_DI_14": _mdi_val,
                                          "ADX_State": _state, "Lifecycle_State": _lifecycle,
                                          "Is_Steady_Uptrend": _is_steady_uptrend,
                                          "Is_Super_Stock_ADX": _is_super_stock,
                                          "Is_Not_Sideway_ADX": _is_not_sideway,
                                          "Is_Lifecycle_Excluded": _is_lifecycle_excluded})

                _df_adx = pd.DataFrame(_adx_records)
                df = pd.merge(df, _df_adx, on="Ticker", how="left")
                logger.info(f"   ✅ ADX_14 tính xong — {_df_adx['ADX_14'].notna().sum()}/{len(_df_adx)} mã có giá trị")
            else:
                df["ADX_14"] = None
                df["Plus_DI_14"] = None
                df["Minus_DI_14"] = None
                df["ADX_State"] = None
                df["Lifecycle_State"] = None
                df["Is_Steady_Uptrend"] = False
                df["Is_Super_Stock_ADX"] = False
                df["Is_Not_Sideway_ADX"] = False
                df["Is_Lifecycle_Excluded"] = False
        except Exception as _adx_err:
            logger.warning(f"   ⚠️ Không tính được ADX_14: {_adx_err}")
            df["ADX_14"] = None
            df["Plus_DI_14"] = None
            df["Minus_DI_14"] = None
            df["ADX_State"] = None
            df["Lifecycle_State"] = None
            df["Is_Steady_Uptrend"] = False
            df["Is_Super_Stock_ADX"] = False
            df["Is_Not_Sideway_ADX"] = False
            df["Is_Lifecycle_Excluded"] = False
        # ── KẾT THÚC ADX ─────────────────────────────────────────────────

        # ===================================================================
        # 3. TÍNH TOÁN CÁC LOẠI ĐIỂM SỐ (Chạy tuần tự)
        # ===================================================================
        df = calculate_value_score(df)
        df = calculate_growth_score(df)
        df = calculate_momentum_score(df)
        df = calculate_vgm_score(df, as_of_date=as_of_date)
        df = calculate_canslim_score(df)
        df = calculate_star_rating(df)      # ← THÊM
        df = calculate_fss_smart_rank(df)   # ← THÊM
        df = calculate_tplus_score(df)

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

            # ── Elliott Wave Proxy ──
            'Fib_Position_%', 'Fib_Zone',
            'Wave_Momentum_Score', 'Elliott_Corrective',

            # ── ADX ──
            'ADX_14', 'Plus_DI_14', 'Minus_DI_14', 'ADX_State', 'Lifecycle_State',
            'Is_Steady_Uptrend', 'Is_Super_Stock_ADX', 'Is_Not_Sideway_ADX',
            'Is_Lifecycle_Excluded',

            # ── Scores ──
            'T_Plus_Score',

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
    
# ==============================================================================
# 5. STAR RATING & FSS SMART RANK
# ==============================================================================

def calculate_star_rating(df):
    """
    Chuyển VGM Score (A-F) → 1–5 sao.
    Hard Rule phòng thủ: CFO âm hoặc GTGD_20D < 5 tỷ → bị ép tối đa 2 sao.
    """
    star_mapping = {'A': 5, 'B': 4, 'C': 3, 'D': 2, 'F': 1}
    df['Star_Rating'] = df['VGM Score'].map(star_mapping).fillna(1).astype(int)

    # 🟢 FIX: Hard Rule - Chất lượng dòng tiền (CFO / Net Income)
    cfo_penalty = pd.Series(False, index=df.index)
    if 'fcf' in df.columns and 'net_income' in df.columns:
        fcf_series = pd.to_numeric(df['fcf'], errors='coerce').fillna(0)
        ni_series = pd.to_numeric(df['net_income'], errors='coerce').fillna(0)
        
        # Phạt nếu FCF âm HOẶC (Net Income > 0 nhưng FCF < 50% Net Income -> Lợi nhuận nằm trên giấy/Phải thu)
        cfo_penalty = (fcf_series < 0) | ((ni_series > 0) & (fcf_series < 0.5 * ni_series))

    gtgd_penalty = pd.Series(False, index=df.index)
    if 'GTGD_20D' in df.columns:
        gtgd_penalty = pd.to_numeric(df['GTGD_20D'], errors='coerce').fillna(0) < 5_000_000_000
    elif 'Avg_Vol_20D' in df.columns and 'Price Close' in df.columns:
        # Fallback: tính GTGD từ KL TB × Giá
        gtgd_est = (pd.to_numeric(df['Avg_Vol_20D'], errors='coerce').fillna(0)
                    * pd.to_numeric(df['Price Close'], errors='coerce').fillna(0))
        gtgd_penalty = gtgd_est < 5_000_000_000

    penalty_mask = cfo_penalty | gtgd_penalty
    df.loc[penalty_mask, 'Star_Rating'] = df.loc[penalty_mask, 'Star_Rating'].clip(upper=2)

    # =====================================================================
    # 🟢 FIX: ĐỒNG BỘ NGƯỢC LẠI VGM SCORE (Để Trang 1-3 và Trang 4 khớp nhau)
    # =====================================================================
    reverse_star_mapping = {5: 'A', 4: 'B', 3: 'C', 2: 'D', 1: 'F'}
    df['VGM Score'] = df['Star_Rating'].map(reverse_star_mapping)

    logger.info(f"   ✅ Star Rating xong — phân bổ: {df['Star_Rating'].value_counts().sort_index().to_dict()}")
    return df


def calculate_fss_smart_rank(df):
    """
    FSS Smart Rank = điểm tổng hợp để làm Tie-breaker trong cùng nhóm Star.
    Trọng số: Size 30% + Liq 20% + Valuation 20% + Quality (Star) 30%
    Giá trị từ 0.0 → 1.0 (càng cao càng tốt).
    """
    df['_Rank_Size'] = pd.to_numeric(df.get('Market Cap', 0), errors='coerce').fillna(0).rank(pct=True)
    df['_Rank_Liq']  = pd.to_numeric(df.get('GTGD_20D',
                       df.get('Avg_Vol_20D', pd.Series(0, index=df.index))),
                       errors='coerce').fillna(0).rank(pct=True)

    # Valuation: P/E càng thấp (dương) → rank càng cao
    pe = pd.to_numeric(df.get('P/E', np.nan), errors='coerce')
    df['_Rank_Val'] = (1 / pe.where(pe > 0)).rank(pct=True, na_option='bottom')

    # Quality: dùng Star_Rating đã tính
    df['_Rank_Quality'] = (pd.to_numeric(df.get('Star_Rating', 1), errors='coerce').fillna(1) / 5)

    df['FSS_Smart_Rank'] = (
        df['_Rank_Size']    * 0.30 +
        df['_Rank_Liq']     * 0.20 +
        df['_Rank_Val']     * 0.20 +
        df['_Rank_Quality'] * 0.30
    ).round(4)

    # Dọn cột tạm
    df.drop(columns=['_Rank_Size', '_Rank_Liq', '_Rank_Val', '_Rank_Quality'],
            inplace=True, errors='ignore')

    logger.info(f"   ✅ FSS Smart Rank xong — min={df['FSS_Smart_Rank'].min():.3f} max={df['FSS_Smart_Rank'].max():.3f}")
    return df

def calculate_robo_allocation(filtered_df, nav, df_price=None):
    """
    TỐI ƯU HÓA DANH MỤC MARKOWITZ & MONTE CARLO STRESS TEST
    Chuẩn Vietcap IQ: Có ràng buộc tỷ trọng, kiểm soát sàn UPCoM và ưu tiên Tiền mặt nếu rủi ro cao.
    """
    if filtered_df is None or filtered_df.empty or nav <= 0:
        return None, nav

    # 1. Ưu tiên các mã điểm cao nhất (Lọc Top 5 để chạy thuật toán)
    if 'FSS_Smart_Rank' in filtered_df.columns:
        df_top = filtered_df.sort_values(by='FSS_Smart_Rank', ascending=False).head(5)
    else:
        df_top = filtered_df.sort_values(by='Star_Rating', ascending=False).head(5)

    tickers = df_top['Ticker'].tolist()
    
    # KỊCH BẢN FALLBACK: Nếu không có df_price (giá lịch sử) truyền vào, chia đều an toàn
    if df_price is None or df_price.empty:
        logger.warning("⚠️ Không có dữ liệu lịch sử giá, chia tỷ trọng đều (Fallback).")
        weights = [1.0 / len(tickers)] * len(tickers)
        expected_ret, max_dd = 0.0, 0.0
    else:
        logger.info(f"🧠 Đang chạy Markowitz & Monte Carlo cho: {tickers}")
        
        # 2. Xử lý Dữ liệu Lịch sử (Trích xuất chuỗi lợi nhuận ngày)
        df_px = df_price[df_price['Ticker'].isin(tickers)].pivot(index='Date', columns='Ticker', values='Price Close').sort_index()
        returns = df_px.pct_change().dropna()
        
        if returns.empty or len(returns) < 20:
            logger.warning("⚠️ Dữ liệu giá quá ngắn, dùng Fallback.")
            weights = [1.0 / len(tickers)] * len(tickers)
            expected_ret, max_dd = 0.0, 0.0
        else:
            mean_returns = returns.mean() * 20 # Kỳ vọng 1 tháng (20 phiên)
            cov_matrix = returns.cov() * 20

            # 3. THUẬT TOÁN MARKOWITZ: TỐI ĐA HÓA SHARPE RATIO
            num_assets = len(tickers)
            args = (mean_returns, cov_matrix)
            
            def portfolio_performance(weights, mean_returns, cov_matrix):
                returns = np.sum(mean_returns * weights)
                std = np.sqrt(np.dot(weights.T, np.dot(cov_matrix, weights)))
                return returns, std
            
            def negative_sharpe_ratio(weights, mean_returns, cov_matrix, risk_free_rate=0.04/12):
                p_ret, p_std = portfolio_performance(weights, mean_returns, cov_matrix)
                return -(p_ret - risk_free_rate) / (p_std + 1e-9)

            # --- LUẬT VIETCAP (CONSTRAINTS) ---
            # 1. Tổng tỷ trọng <= 1 (Cho phép giữ tiền mặt nếu TT xấu)
            constraints = [{'type': 'ineq', 'fun': lambda x: 1 - np.sum(x)}] 
            
            # 2. Giới hạn sàn UPCoM (Tổng vốn vào UPCoM <= 10%)
            upcom_indices = [i for i, t in enumerate(tickers) if df_top.iloc[i].get('Exchange', '') == 'UPCOM']
            if upcom_indices:
                constraints.append({'type': 'ineq', 'fun': lambda x: 0.10 - np.sum([x[i] for i in upcom_indices])})
            
            # 3. Ràng buộc mỗi mã: Tối thiểu 10%, Tối đa 40%
            bounds = tuple((0.1, 0.4) for asset in range(num_assets))
            
            # Chạy thuật toán tối ưu
            opt_result = sco.minimize(negative_sharpe_ratio, num_assets*[1./num_assets,], args=args,
                                      method='SLSQP', bounds=bounds, constraints=constraints)
            weights = opt_result.x
            
            # 4. MONTE CARLO STRESS TEST (Lõi kiểm tra sức chịu đựng)
            n_scenarios = 10000
            horizon = 20 # 1 tháng
            daily_returns_arr = returns.values
            
            # Vectorized Bootstrapping (Cực nhanh)
            idx = np.random.randint(0, len(daily_returns_arr), size=(n_scenarios, horizon))
            sampled_returns = daily_returns_arr[idx] # Shape: (10000, 20, n_assets)
            portfolio_sim_returns = np.sum(sampled_returns * weights, axis=2) # Shape: (10000, 20)
            
            # Tính Max Drawdown của 10.000 kịch bản
            cum_returns = np.cumprod(1 + portfolio_sim_returns, axis=1)
            peak = np.maximum.accumulate(cum_returns, axis=1)
            drawdown = (cum_returns - peak) / peak
            max_dd = np.abs(np.min(drawdown)) # Giá trị dương
            
            # Tính Expected Return
            expected_ret = np.mean(cum_returns[:, -1] - 1)
            
            # Bơm luật Guillotine: Nếu MDD > 15%, ép giảm tỷ trọng cổ phiếu, tăng tiền mặt
            if max_dd > 0.15:
                logger.warning(f"🚨 Rủi ro sập hầm cao (MDD={max_dd:.1%}). Tự động hạ tỷ trọng cổ phiếu!")
                reduction_factor = 0.15 / max_dd # Ép tỷ trọng xuống mức an toàn
                weights = weights * reduction_factor

    # 5. ĐÓNG GÓI KẾT QUẢ ĐI LỆNH (ACTIONABLE)
    allocations = []
    remaining_cash = nav
    total_invested_pct = np.sum(weights)

    for idx, row in enumerate(df_top.to_dict('records')):
        w = weights[idx]
        if w < 0.05: continue # Bỏ qua nếu tỷ trọng < 5%
        
        price = float(row.get('Price Close', 0))
        if price <= 0: continue
        
        # Mua theo lô 100 cổ phiếu chẵn
        max_shares = int((nav * w) / (price * 100)) * 100
        
        if max_shares > 0:
            cost = max_shares * price
            remaining_cash -= cost
            allocations.append({
                "Ticker": row.get('Ticker', 'N/A'),
                "Volume": max_shares,
                "Price": price,
                "Cost": cost,
                "Weight_Pct": w, # Truyền % ra để UI vẽ
                "Expected_Ret_1M": expected_ret,
                "Max_Drawdown": max_dd,
                "Score": row.get('Star_Rating', 0)
            })
            
    # Ghi nhận tiền mặt (Cash) nếu hệ thống phòng thủ
    if remaining_cash > (nav * 0.05): # Nếu dư hơn 5% tiền
         logger.info(f"🛡️ Hệ thống phòng thủ: Giữ lại {remaining_cash/nav:.1%} Tiền mặt.")
            
    return allocations, remaining_cash

# ============================================================
# SECTOR BREADTH SCORE (SBS)
# ============================================================

_SECTOR_VI = {
    "Energy":                  "Năng lượng",
    "Financials":              "Tài chính",
    "Utilities":               "Tiện ích",
    "Materials":               "Nguyên vật liệu",
    "Industrials":             "Công nghiệp",
    "Consumer Discretionary":  "Tiêu dùng tùy ý",
    "Health Care":             "Y tế",
    "Consumer Staples":        "Tiêu dùng thiết yếu",
    "Information Technology":  "Công nghệ TT",
    "Real Estate":             "Bất động sản",
    "Communication Services":  "Dịch vụ TT",
}

# Ngưỡng phân loại Breadth Regime
_SBS_TIERS = [
    (80, "Xác nhận Uptrend",       "#10b981"),
    (65, "Mạnh — Duy trì tỷ trọng","#34d399"),
    (50, "Trung tính — Chọn lọc",  "#f59e0b"),
    (35, "Yếu — Giảm tỷ trọng",    "#f97316"),
    (0,  "Broad Bear — Rủi ro",    "#ef4444"),
]

def _sbs_tier(score):
    """Trả về (label, color) cho một giá trị SBS."""
    for threshold, label, color in _SBS_TIERS:
        if score >= threshold:
            return label, color
    return "Broad Bear — Rủi ro", "#ef4444"


def calculate_sbs_snapshot(df_snap, df_price,
                            exchange_filter="HOSE",
                            min_vol=100_000,
                            min_price=5_000):
    """
    Tính Sector Breadth Score (SBS) cho snapshot hiện tại.

    SBS = 0.20*P_MA50 + 0.20*P_MA200 + 0.15*AD_20 +
          0.15*HL + 0.10*RSI_D + 0.20*VB_20

    Parameters
    ----------
    df_snap          : DataFrame snapshot từ get_snapshot_df()
    df_price         : DataFrame giá lịch sử (Ticker, Date, Price Close, Volume)
    exchange_filter  : "HOSE" | "HNX" | "UPCOM" | "ALL"
    min_vol          : Lọc thanh khoản tối thiểu (Avg_Vol_20D)
    min_price        : Lọc giá tối thiểu (loại penny)

    Returns
    -------
    dict với keys:
        "sector_sbs"    : DataFrame [Sector, SBS, P_MA50, P_MA200, AD_20,
                                      RSI_D, VB_20, HL, N, SBS_Label, SBS_Color]
        "market_sbs"    : float — Market composite SBS (weighted by N stocks)
        "regime"        : str   — Breadth Regime label
        "regime_color"  : str   — Màu hex tương ứng
        "top_sectors"   : list  — 3 ngành mạnh nhất
        "weak_sectors"  : list  — 3 ngành yếu nhất
    """
    import pandas as pd
    import numpy as np

    df = df_snap.copy()

    # ── Lọc sàn ──────────────────────────────────────────────────────────────
    if exchange_filter != "ALL" and "Exchange" in df.columns:
        df = df[df["Exchange"] == exchange_filter]

    # ── Lọc chống nhiễu penny / thanh khoản thấp ─────────────────────────────
    if "Avg_Vol_20D" in df.columns:
        df = df[pd.to_numeric(df["Avg_Vol_20D"], errors="coerce").fillna(0) >= min_vol]
    if "Price Close" in df.columns:
        df = df[pd.to_numeric(df["Price Close"], errors="coerce").fillna(0) >= min_price]

    if df.empty or "Sector" not in df.columns:
        return None

    df["Sector"] = df["Sector"].fillna("Khác").replace(
        {"nan": "Khác", "None": "Khác", "": "Khác"})

    # ── Cột flag nhị phân từ snapshot (tính được ngay) ───────────────────────
    df["_above_ma50"]  = (
        pd.to_numeric(df.get("Price_vs_SMA50",  pd.Series(dtype=float)),
                      errors="coerce").fillna(0) > 0
    ).astype(int)
    df["_above_ma200"] = (
        pd.to_numeric(df.get("Price_vs_SMA200", pd.Series(dtype=float)),
                      errors="coerce").fillna(0) > 0
    ).astype(int)
    df["_rsi_above50"] = (
        pd.to_numeric(df.get("RSI_14", pd.Series(dtype=float)),
                      errors="coerce").fillna(50) > 50
    ).astype(int)

    # ── AD_20, VB_20, HL từ df_price 20 phiên ────────────────────────────────
    # Lấy 22 phiên gần nhất (bù ngày nghỉ)
    tickers_clean = df["Ticker"].tolist()
    cutoff = df_price["Date"].max() - pd.Timedelta(days=35)
    df_px  = (df_price[
                  (df_price["Ticker"].isin(tickers_clean)) &
                  (df_price["Date"] >= cutoff)
              ][["Ticker", "Date", "Price Close", "Volume"]].copy())
    df_px["Price Close"] = pd.to_numeric(df_px["Price Close"], errors="coerce")
    df_px["Volume"]      = pd.to_numeric(df_px["Volume"],      errors="coerce").fillna(0)
    df_px = df_px.sort_values(["Ticker", "Date"])

    # Tính is_up (close > prev_close) và up_volume vectorized
    df_px["_prev_close"] = df_px.groupby("Ticker")["Price Close"].shift(1)
    df_px["_is_up"]      = (df_px["Price Close"] > df_px["_prev_close"]).astype(int)
    df_px["_up_vol"]     = df_px["_is_up"] * df_px["Volume"]

    # Chỉ lấy 20 phiên gần nhất theo từng ticker
    df_px["_rank"] = df_px.groupby("Ticker")["Date"].rank(method="first", ascending=False)
    df_px20 = df_px[df_px["_rank"] <= 20]

    adv_dec = df_px20.groupby("Ticker").agg(
        _adv=("_is_up", "sum"),
        _dec=("_is_up", lambda x: (x == 0).sum()),
        _up_vol_sum=("_up_vol", "sum"),
        _total_vol=("Volume", "sum"),
    ).reset_index()

    adv_dec["_ad_ratio"] = (
        adv_dec["_adv"] / (adv_dec["_adv"] + adv_dec["_dec"])
    ).fillna(0.5) * 100

    adv_dec["_vb"] = np.where(
        adv_dec["_total_vol"] > 0,
        adv_dec["_up_vol_sum"] / adv_dec["_total_vol"] * 100,
        50.0
    )

    # HL — High-Low Index 52 tuần (dùng cột Break_High_52W nếu có trong snap)
    if "Break_High_52W" in df.columns:
        df["_hl_flag"] = pd.to_numeric(
            df["Break_High_52W"], errors="coerce").fillna(0)
    else:
        df["_hl_flag"] = 0

    # Merge AD/VB vào snap
    df = df.merge(adv_dec[["Ticker", "_ad_ratio", "_vb"]], on="Ticker", how="left")
    df["_ad_ratio"] = df["_ad_ratio"].fillna(50)
    df["_vb"]       = df["_vb"].fillna(50)

    # ── Tính SBS theo ngành (groupby vectorized) ──────────────────────────────
    # 🟢 THÊM **kwargs để hứng các tham số dư thừa do Pandas phiên bản cũ nhả ra
    def sbs_for_group(g, **kwargs):
        n        = len(g)
        p_ma50   = g["_above_ma50"].mean()  * 100
        p_ma200  = g["_above_ma200"].mean() * 100
        ad_20    = g["_ad_ratio"].mean()
        rsi_d    = g["_rsi_above50"].mean() * 100
        vb_20    = g["_vb"].mean()
        hl       = g["_hl_flag"].mean()     * 100

        sbs = (0.20 * p_ma50 + 0.20 * p_ma200 + 0.15 * ad_20 +
               0.15 * hl    + 0.10 * rsi_d   + 0.20 * vb_20)

        return pd.Series({
            "SBS":     round(sbs, 1),
            "P_MA50":  round(p_ma50, 1),
            "P_MA200": round(p_ma200, 1),
            "AD_20":   round(ad_20, 1),
            "RSI_D":   round(rsi_d, 1),
            "VB_20":   round(vb_20, 1),
            "HL":      round(hl, 1),
            "N":       n,
        })

    sector_sbs = df.groupby("Sector").apply(
        sbs_for_group, include_groups=False
    ).reset_index()
    sector_sbs = sector_sbs.sort_values("SBS", ascending=False).reset_index(drop=True)

    # Gắn label + color theo tier
    sector_sbs[["SBS_Label", "SBS_Color"]] = sector_sbs["SBS"].apply(
        lambda s: pd.Series(_sbs_tier(s))
    )

    # Market composite SBS (weighted by N)
    total_n    = sector_sbs["N"].sum()
    market_sbs = (
        (sector_sbs["SBS"] * sector_sbs["N"]).sum() / total_n
        if total_n > 0 else 0
    )
    market_sbs    = round(market_sbs, 1)
    regime, r_clr = _sbs_tier(market_sbs)

    top_sectors  = sector_sbs.head(3)[["Sector","SBS"]].to_dict("records")
    weak_sectors = sector_sbs.tail(3)[["Sector","SBS"]].to_dict("records")

    return {
        "sector_sbs":   sector_sbs,
        "market_sbs":   market_sbs,
        "regime":       regime,
        "regime_color": r_clr,
        "top_sectors":  top_sectors,
        "weak_sectors": weak_sectors,
    }


def calculate_sbs_history(df_price, df_snap,
                           lookback=60,
                           exchange_filter="HOSE",
                           min_vol=100_000,
                           min_price=5_000):
    """
    Tính SBS theo từng phiên giao dịch trong `lookback` phiên gần nhất.
    Dùng để vẽ line chart 60 phiên và heatmap sector×day.

    Lưu kết quả ra market_internals.parquet để tái sử dụng.

    Returns
    -------
    DataFrame với cột: [Date, Sector, SBS, P_MA50, P_MA200, AD_20, RSI_D, VB_20, HL, N]
    """
    import pandas as pd
    import numpy as np
    import os

    df_snap_c = df_snap.copy()
    if exchange_filter != "ALL" and "Exchange" in df_snap_c.columns:
        df_snap_c = df_snap_c[df_snap_c["Exchange"] == exchange_filter]
    if "Avg_Vol_20D" in df_snap_c.columns:
        df_snap_c = df_snap_c[
            pd.to_numeric(df_snap_c["Avg_Vol_20D"], errors="coerce").fillna(0)
            >= min_vol
        ]
    if "Price Close" in df_snap_c.columns:
        df_snap_c = df_snap_c[
            pd.to_numeric(df_snap_c["Price Close"], errors="coerce").fillna(0)
            >= min_price
        ]

    tickers_ok  = df_snap_c["Ticker"].tolist()
    sector_map  = (df_snap_c[["Ticker","Sector"]]
                   .drop_duplicates("Ticker")
                   .set_index("Ticker")["Sector"])

    # Lấy đủ lịch sử: lookback phiên + 200 ngày đệm cho MA200
    # ~200 trading days ≈ 300 calendar days
    buffer_days = lookback + 300
    cutoff = df_price["Date"].max() - pd.Timedelta(days=buffer_days * 1.5)
    df_px  = (df_price[
                  (df_price["Ticker"].isin(tickers_ok)) &
                  (df_price["Date"] >= cutoff)
              ].copy())
    df_px["Price Close"] = pd.to_numeric(df_px["Price Close"], errors="coerce")
    df_px["Volume"]      = pd.to_numeric(df_px["Volume"],      errors="coerce").fillna(0)
    df_px = df_px.sort_values(["Ticker","Date"])
    df_px["Sector"] = df_px["Ticker"].map(sector_map)
    df_px = df_px.dropna(subset=["Sector"])

    # Pivot để tính rolling SMA vectorized
    price_pivot  = df_px.pivot_table(
        index="Date", columns="Ticker", values="Price Close"
    ).sort_index()
    volume_pivot = df_px.pivot_table(
        index="Date", columns="Ticker", values="Volume"
    ).sort_index().fillna(0)

    # SMA50, SMA200 vectorized
    sma50  = price_pivot.rolling(50,  min_periods=25).mean()
    sma200 = price_pivot.rolling(200, min_periods=100).mean()

    above_ma50  = (price_pivot > sma50).astype(float)
    above_ma200 = (price_pivot > sma200).astype(float)

    # RSI_14 vectorized theo từng cột
    delta     = price_pivot.diff()
    gain      = delta.clip(lower=0)
    loss      = (-delta).clip(lower=0)
    avg_gain  = gain.ewm(com=13, min_periods=14).mean()
    avg_loss  = loss.ewm(com=13, min_periods=14).mean()
    rsi_pivot = 100 - (100 / (1 + avg_gain / avg_loss.replace(0, np.nan)))
    above_rsi = (rsi_pivot > 50).astype(float)

    # is_up và volume breadth
    is_up    = (price_pivot > price_pivot.shift(1)).astype(float)
    up_vol   = is_up * volume_pivot
    down_vol = (1 - is_up) * volume_pivot

    # AD_20: rolling 20 phiên advance / (advance+decline)
    adv_roll = is_up.rolling(20, min_periods=10).sum()
    dec_roll = (1 - is_up).rolling(20, min_periods=10).sum()
    ad_ratio = (adv_roll / (adv_roll + dec_roll).replace(0, np.nan)) * 100

    # VB_20: rolling 20 phiên up_vol / total_vol
    up_vol_roll   = up_vol.rolling(20, min_periods=10).sum()
    total_vol_roll = volume_pivot.rolling(20, min_periods=10).sum()
    vb_ratio = (up_vol_roll / total_vol_roll.replace(0, np.nan)) * 100

    # HL: 52-week high/low index (rolling 252 phiên)
    high_52w = price_pivot.rolling(252, min_periods=126).max()
    low_52w  = price_pivot.rolling(252, min_periods=126).min()
    near_high = (price_pivot >= high_52w * 0.99).astype(float)
    near_low  = (price_pivot <= low_52w  * 1.01).astype(float)
    hl_index  = (near_high - near_low).clip(lower=0) * 100

    # Lấy lookback phiên cuối
    all_dates = sorted(price_pivot.index)[-lookback:]

    records = []
    for date in all_dates:
        if date not in price_pivot.index:
            continue

        def _sector_agg(mat_row, weight):
            """Tổng hợp giá trị theo ngành, bỏ NaN."""
            row = pd.Series(mat_row, index=price_pivot.columns)
            row.index.name = "Ticker"
            row_df = row.to_frame("val")
            row_df["Sector"] = row_df.index.map(sector_map)
            return row_df.dropna(subset=["Sector","val"]).groupby("Sector")["val"].mean()

        p50  = _sector_agg(above_ma50.loc[date],  0.20) * 100
        p200 = _sector_agg(above_ma200.loc[date], 0.20) * 100
        ad   = _sector_agg(ad_ratio.loc[date],    0.15)
        rsi  = _sector_agg(above_rsi.loc[date],   0.10) * 100
        vb   = _sector_agg(vb_ratio.loc[date],    0.20)
        hl   = _sector_agg(hl_index.loc[date],    0.15)
        n_df = (pd.Series(price_pivot.loc[date], index=price_pivot.columns)
                .dropna()
                .to_frame("v")
                .assign(Sector=lambda x: x.index.map(sector_map))
                .dropna(subset=["Sector"])
                .groupby("Sector")["v"].count())

        all_sectors = set(p50.index) | set(p200.index) | set(ad.index)
        for sector in all_sectors:
            def _g(s, fallback=50):
                return float(s.get(sector, fallback))
            sbs = (0.20 * _g(p50,  0) +
                   0.20 * _g(p200, 0) +
                   0.15 * _g(ad)      +
                   0.15 * _g(hl,   0) +
                   0.10 * _g(rsi,  0) +
                   0.20 * _g(vb))
            records.append({
                "Date":    date,
                "Sector":  sector,
                "SBS":     round(sbs, 1),
                "P_MA50":  round(_g(p50,  0), 1),
                "P_MA200": round(_g(p200, 0), 1),
                "AD_20":   round(_g(ad),      1),
                "RSI_D":   round(_g(rsi,  0), 1),
                "VB_20":   round(_g(vb),      1),
                "HL":      round(_g(hl,   0), 1),
                "N":       int(_g(n_df,   0)),
            })

    return pd.DataFrame(records)