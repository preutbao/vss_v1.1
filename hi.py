import os
import pandas as pd
import warnings
warnings.filterwarnings('ignore')

# Import trực tiếp từ core của bạn
from src.backend.data_loader import load_market_data, load_financial_data
from src.backend.quant_engine import calculate_all_scores

print("="*70)
print(" 🚀 SCRIPT DEBUG PIPELINE: TRUY TÌM CỔ PHIẾU BỊ MẤT TÍCH")
print("="*70)

# 1. ĐỌC DỮ LIỆU GIÁ
print("\n[1] Đọc dữ liệu Market Data...")
df_price = load_market_data()
if df_price.empty:
    print("❌ THẤT BẠI: File dữ liệu giá trống!")
    exit()

print(f"✔️ Tổng số mã CK trong file Giá: {df_price['Ticker'].nunique():,}")
print(f"✔️ Ngày giao dịch MỚI NHẤT: {df_price['Date'].max().strftime('%d/%m/%Y')}")

# Chuẩn bị df_latest giống y hệt _build_snapshot_df()
df_price = df_price.sort_values(["Ticker", "Date"])
df_price["Avg_Vol_20D"] = df_price.groupby("Ticker", sort=False)["Volume"].transform(lambda x: x.rolling(20, min_periods=1).mean()).round(0).fillna(0)
df_latest = df_price.drop_duplicates(subset=["Ticker"], keep="last").copy()
print(f"✔️ Số lượng mã sau khi lấy ngày mới nhất: {len(df_latest):,}")

# 2. ĐỌC BCTC
print("\n[2] Đọc dữ liệu Báo Cáo Tài Chính...")
df_fin = load_financial_data("yearly")
print(f"✔️ Tổng số mã CK trong file BCTC: {df_fin['Ticker'].nunique():,}")

# 3. CHẠY QUANT ENGINE
print("\n[3] Chạy Quant Engine (Chấm điểm & Merge)...")
df_snapshot = calculate_all_scores(df_latest, df_fin)
print(f"✔️ Số lượng mã sau khi Quant Engine xử lý: {len(df_snapshot):,} (Nếu số này ~1500 thì Engine không làm mất mã)")

# 4. MÔ PHỎNG BỘ LỌC UI (THỦ PHẠM CHÍNH)
print("\n[4] Mô phỏng bộ lọc Khẩu vị cá nhân (Investor Profile)...")
df_sim = df_snapshot.copy()

# Lọc thanh khoản (Vol > 30k)
df_sim = df_sim[pd.to_numeric(df_sim["Avg_Vol_20D"], errors="coerce").fillna(0) >= 30_000]
print(f"  🔻 Sau khi lọc Thanh khoản (Vol >= 30k): Còn {len(df_sim):,} mã")

# Lọc vốn hóa (Cap > 200 tỷ)
df_sim = df_sim[pd.to_numeric(df_sim["Market Cap"], errors="coerce").fillna(0) >= 200_000_000_000]
print(f"  🔻 Sau khi lọc Vốn hóa (Cap >= 200 Tỷ): Còn {len(df_sim):,} mã")

# Lọc giá (Price >= 3000)
df_sim = df_sim[pd.to_numeric(df_sim["Price Close"], errors="coerce").fillna(0) >= 3_000]
print(f"  🔻 Sau khi lọc Thị giá (Price >= 3k): Còn {len(df_sim):,} mã")

print("\n[5] KẾT LUẬN:")
if len(df_sim) < 500:
    print(f"💡 Đúng như dự đoán! Bộ lọc Khẩu vị cá nhân đã loại bỏ hàng ngàn mã rác/thanh khoản thấp, chỉ giữ lại {len(df_sim)} mã.")
else:
    print("⚠️ Có điều gì đó khác đang làm rơi dữ liệu. Vui lòng gửi output này cho tôi xem.")
print("="*70)