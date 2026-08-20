# src/schema.py
"""
SCHEMA REGISTRY — nguồn sự thật DUY NHẤT cho tên cột dữ liệu tài chính.

Vấn đề trước khi có file này:
    Toàn bộ project (data_loader, quant_engine, callbacks, pdf export...)
    hardcode trực tiếp các chuỗi như "P/E", "P/B", "EV/EBITDA", "ROE (%)"...
    tại hàng chục vị trí khác nhau. Không có lỗi mapping nào được phát hiện
    khi audit (các chuỗi đang nhất quán), NHƯNG việc hardcode rải rác là một
    rủi ro bảo trì nghiêm trọng: chỉ cần một nơi gõ sai ("P/E" vs "PE") là
    silently tạo ra cột NaN / filter sai mà không có lỗi runtime nào cả.

Giải pháp:
    Mọi tên cột phải được định nghĩa Ở ĐÂY một lần duy nhất, dưới dạng hằng số
    COL_*, rồi toàn bộ project import từ module này thay vì gõ lại chuỗi.

Cách migrate an toàn (không phá vỡ app đang chạy production):
    1. File này được tạo mới, KHÔNG đổi bất kỳ giá trị chuỗi nào đang dùng
       trong hệ thống — mỗi COL_* dưới đây copy chính xác giá trị đã được
       xác minh có bằng chứng trong src/backend/data_loader.py
       (FILTER_COL_MAP, dòng ~1093-1151).
    2. `src/backend/data_loader.py` đã được cập nhật để derive
       FILTER_COL_MAP TỪ registry này (xem FILTER_TO_SCHEMA_COL bên dưới),
       thay vì định nghĩa chuỗi độc lập — loại bỏ một điểm trùng lặp.
    3. Các module còn lại (quant_engine.py, screener_callbacks.py,
       pdf_export_callback.py, financial_charts_callbacks.py, ...) vẫn còn
       hardcode string literal tại thời điểm audit này (xem Audit Report,
       mục 1 — trạng thái PARTIAL). Migrate toàn bộ ~150+ vị trí đó bằng
       tìm–thay tự động trên một codebase 39.000 dòng KHÔNG có test coverage
       đầy đủ là rủi ro cao (một "P/E" bên trong f-string định dạng % khác
       hoàn toàn một "P/E" là tên cột — thay nhầm sẽ phá vỡ UI mà không có
       lỗi rõ ràng). Khuyến nghị: migrate theo từng PR nhỏ, mỗi PR kèm test
       hồi quy so sánh output trước/sau, thay vì một lần sửa toàn bộ.
       Registry này là bước nền tảng bắt buộc để làm việc đó an toàn.

Cách dùng:
    from src.schema import COL_PE, COL_PB, COL_ROE

    df[COL_PE]  # thay vì df["P/E"]
"""

# ──────────────────────────────────────────────
# ĐỊNH GIÁ (Valuation)
# ──────────────────────────────────────────────
COL_PE              = "P/E"
COL_PE_FORWARD      = "Forward P/E"          # ước tính — xem lưu ý ở mục 3 của audit report
COL_PB              = "P/B"
COL_PS              = "P/S"
COL_EV_EBITDA       = "EV/EBITDA"
COL_DIV_YIELD       = "Dividend Yield (%)"

# ──────────────────────────────────────────────
# QUY MÔ / GIÁ
# ──────────────────────────────────────────────
COL_PRICE_CLOSE     = "Price Close"
COL_VOLUME          = "Volume"
COL_MARKET_CAP      = "Market Cap"
COL_EPS             = "EPS"
COL_BOOK_VALUE      = "Book Value"

# ──────────────────────────────────────────────
# HIỆU SUẤT / TĂNG TRƯỞNG
# ──────────────────────────────────────────────
COL_PERF_1W         = "Perf_1W"
COL_PERF_1M         = "Perf_1M"
COL_REV_GROWTH_YOY  = "Revenue Growth YoY (%)"
COL_REV_CAGR_5Y     = "Revenue CAGR 5Y (%)"
COL_EPS_GROWTH_YOY  = "EPS Growth YoY (%)"
COL_EPS_CAGR_5Y     = "EPS CAGR 5Y (%)"
COL_FCF             = "Free Cash Flow"
COL_REVENUE         = "Revenue"

# ──────────────────────────────────────────────
# LỢI NHUẬN / HIỆU QUẢ
# ──────────────────────────────────────────────
COL_ROE             = "ROE (%)"
COL_ROA             = "ROA (%)"
COL_GROSS_MARGIN    = "Gross Margin (%)"
COL_NET_MARGIN      = "Net Margin (%)"
COL_EBIT_MARGIN     = "EBIT Margin (%)"

# ──────────────────────────────────────────────
# SỨC KHỎE TÀI CHÍNH
# ──────────────────────────────────────────────
COL_DE              = "D/E"
COL_CURRENT_RATIO   = "Current Ratio"
COL_NET_CASH_CAP    = "Net Cash / Market Cap (%)"
COL_NET_CASH_ASSETS = "Net Cash / Assets (%)"

# ──────────────────────────────────────────────
# KỸ THUẬT — GIÁ vs SMA
# ──────────────────────────────────────────────
COL_PRICE_VS_SMA5   = "Price_vs_SMA5"
COL_PRICE_VS_SMA10  = "Price_vs_SMA10"
COL_PRICE_VS_SMA20  = "Price_vs_SMA20"
COL_PRICE_VS_SMA50  = "Price_vs_SMA50"
COL_PRICE_VS_SMA100 = "Price_vs_SMA100"
COL_PRICE_VS_SMA200 = "Price_vs_SMA200"

# ──────────────────────────────────────────────
# KỸ THUẬT — 52W / ALL-TIME
# ──────────────────────────────────────────────
COL_PCT_FROM_HIGH_1Y  = "Pct_From_High_1Y"
COL_PCT_FROM_LOW_1Y   = "Pct_From_Low_1Y"
COL_PCT_FROM_HIGH_ALL = "Pct_From_High_All"
COL_PCT_FROM_LOW_ALL  = "Pct_From_Low_All"

# ──────────────────────────────────────────────
# KỸ THUẬT — MOMENTUM / OSCILLATOR
# ──────────────────────────────────────────────
COL_RSI_14          = "RSI_14"
COL_MACD_HIST       = "MACD_Histogram"
COL_BB_WIDTH        = "BB_Width"
COL_CONSEC_UP       = "Consec_Up"
COL_CONSEC_DOWN     = "Consec_Down"
COL_ADX_14          = "ADX_14"
COL_PLUS_DI_14      = "Plus_DI_14"
COL_MINUS_DI_14     = "Minus_DI_14"

# ──────────────────────────────────────────────
# KỸ THUẬT — BETA / ALPHA / RELATIVE STRENGTH
# ──────────────────────────────────────────────
COL_BETA            = "Beta"
COL_ALPHA           = "Alpha"
COL_RS_3D           = "RS_3D"
COL_RS_1M           = "RS_1M"
COL_RS_3M           = "RS_3M"
COL_RS_1Y           = "RS_1Y"
COL_RS_AVG          = "RS_Avg"

# ──────────────────────────────────────────────
# KỸ THUẬT — VOLUME
# ──────────────────────────────────────────────
COL_VOL_VS_SMA5     = "Vol_vs_SMA5"
COL_VOL_VS_SMA10    = "Vol_vs_SMA10"
COL_VOL_VS_SMA20    = "Vol_vs_SMA20"
COL_VOL_VS_SMA50    = "Vol_vs_SMA50"
COL_AVG_VOL_5D      = "Avg_Vol_5D"
COL_AVG_VOL_10D     = "Avg_Vol_10D"
COL_AVG_VOL_50D     = "Avg_Vol_50D"

# ──────────────────────────────────────────────
# SCORING / RANKING
# ──────────────────────────────────────────────
COL_VALUE_SCORE     = "Value Score"
COL_GROWTH_SCORE    = "Growth Score"
COL_MOMENTUM_SCORE  = "Momentum Score"
COL_VGM_SCORE       = "VGM Score"
COL_VGM_SCORE_NUM   = "VGM_Score_Num"
COL_CANSLIM_SCORE   = "CANSLIM Score"

# ──────────────────────────────────────────────
# ĐỊNH DANH
# ──────────────────────────────────────────────
COL_TICKER          = "Ticker"
COL_DATE            = "Date"


# ──────────────────────────────────────────────
# Ánh xạ filter-id (Dash component id) -> tên cột chuẩn.
# Đây là bản sao chính xác của FILTER_COL_MAP gốc trong data_loader.py.
# data_loader.py giờ import FILTER_COL_MAP từ đây (xem ghi chú migrate ở đầu file)
# thay vì định nghĩa độc lập, để tránh 2 nguồn sự thật.
# ──────────────────────────────────────────────
FILTER_TO_SCHEMA_COL = {
    "filter-price":              COL_PRICE_CLOSE,
    "filter-volume":              COL_VOLUME,
    "filter-market-cap":          COL_MARKET_CAP,
    "filter-eps":                 COL_EPS,
    "filter-perf-1w":             COL_PERF_1W,
    "filter-perf-1m":             COL_PERF_1M,
    "filter-pe":                  COL_PE,
    "filter-pb":                  COL_PB,
    "filter-ps":                  COL_PS,
    "filter-ev-ebitda":           COL_EV_EBITDA,
    "filter-div-yield":           COL_DIV_YIELD,
    "filter-roe":                 COL_ROE,
    "filter-roa":                 COL_ROA,
    "filter-gross-margin":        COL_GROSS_MARGIN,
    "filter-net-margin":          COL_NET_MARGIN,
    "filter-ebit-margin":         COL_EBIT_MARGIN,
    "filter-rev-growth-yoy":      COL_REV_GROWTH_YOY,
    "filter-rev-cagr-5y":         COL_REV_CAGR_5Y,
    "filter-eps-growth-yoy":      COL_EPS_GROWTH_YOY,
    "filter-eps-cagr-5y":         COL_EPS_CAGR_5Y,
    "filter-de":                  COL_DE,
    "filter-current-ratio":       COL_CURRENT_RATIO,
    "filter-net-cash-cap":        COL_NET_CASH_CAP,
    "filter-net-cash-assets":     COL_NET_CASH_ASSETS,
    "filter-price-vs-sma5":       COL_PRICE_VS_SMA5,
    "filter-price-vs-sma10":      COL_PRICE_VS_SMA10,
    "filter-price-vs-sma20":      COL_PRICE_VS_SMA20,
    "filter-price-vs-sma50":      COL_PRICE_VS_SMA50,
    "filter-price-vs-sma100":     COL_PRICE_VS_SMA100,
    "filter-price-vs-sma200":     COL_PRICE_VS_SMA200,
    "filter-pct-from-high-1y":    COL_PCT_FROM_HIGH_1Y,
    "filter-pct-from-low-1y":     COL_PCT_FROM_LOW_1Y,
    "filter-pct-from-high-all":   COL_PCT_FROM_HIGH_ALL,
    "filter-pct-from-low-all":    COL_PCT_FROM_LOW_ALL,
    "filter-rsi14":               COL_RSI_14,
    "filter-macd-hist":           COL_MACD_HIST,
    "filter-bb-width":            COL_BB_WIDTH,
    "filter-consec-up":           COL_CONSEC_UP,
    "filter-consec-down":         COL_CONSEC_DOWN,
    "filter-beta":                COL_BETA,
    "filter-alpha":               COL_ALPHA,
    "filter-rs-3d":               COL_RS_3D,
    "filter-rs-1m":               COL_RS_1M,
    "filter-rs-3m":               COL_RS_3M,
    "filter-rs-1y":               COL_RS_1Y,
    "filter-rs-avg":              COL_RS_AVG,
    "filter-vol-vs-sma5":         COL_VOL_VS_SMA5,
    "filter-vol-vs-sma10":        COL_VOL_VS_SMA10,
    "filter-vol-vs-sma20":        COL_VOL_VS_SMA20,
    "filter-vol-vs-sma50":        COL_VOL_VS_SMA50,
    "filter-avg-vol-5d":          COL_AVG_VOL_5D,
    "filter-avg-vol-10d":         COL_AVG_VOL_10D,
    "filter-avg-vol-50d":         COL_AVG_VOL_50D,
    "filter-canslim":             COL_CANSLIM_SCORE,
    "filter-adx14":               COL_ADX_14,
    "filter-plus-di14":           COL_PLUS_DI_14,
    "filter-minus-di14":          COL_MINUS_DI_14,
}
