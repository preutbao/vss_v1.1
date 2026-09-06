"""
export_vnindex_raw.py
======================
Trích xuất dữ liệu VNINDEX thô (Date + VNINDEX_Close) từ index.parquet,
đúng khoảng thời gian đã dùng trong backtest.py (theo MODEL_VALIDATION_MANIFEST.txt:
2023-01-03 -> 2026-08-28), để dựng lại benchmark equity curve THẬT (không
phải ước tính bằng CAGR) cho chart minh họa báo cáo.

Không phụ thuộc module riêng của dự án (data_loader.py...) — chỉ cần
pandas + pyarrow, chạy độc lập từ bất kỳ đâu, miễn trỏ đúng đường dẫn
INDEX_PARQUET_PATH bên dưới.

Cách chạy:
    python export_vnindex_raw.py

Kết quả: file vnindex_raw.csv (2 cột: Date, VNINDEX_Close) — gửi lại
file này để dựng chart equity curve chính xác 100% (không còn phải
ước tính đường VN-Index bằng compound CAGR như lần trước).
"""
import pandas as pd
from pathlib import Path

# ── CHỈNH LẠI ĐƯỜNG DẪN NÀY cho đúng máy bạn nếu cần ────────────────────
INDEX_PARQUET_PATH = "data/processed/index.parquet"

# Khoảng thời gian khớp đúng MODEL_VALIDATION_MANIFEST.txt đã gửi trước đó
# ("Price date range : 2023-01-03 -> 2026-08-28"). Nới rộng thêm vài ngày
# 2 đầu cho chắc, lọc lại chính xác bằng code bên dưới.
START_DATE = "2023-01-01"
END_DATE   = "2026-08-31"

OUT_PATH = "vnindex_raw.csv"


def main():
    p = Path(INDEX_PARQUET_PATH)
    if not p.exists():
        raise FileNotFoundError(
            f"Không tìm thấy file {p.resolve()}. "
            f"Sửa biến INDEX_PARQUET_PATH ở đầu script cho đúng đường dẫn thật."
        )

    df = pd.read_parquet(p, columns=["Date", "VNINDEX_Close"])
    df["Date"] = pd.to_datetime(df["Date"])
    df = df.dropna(subset=["Date", "VNINDEX_Close"]).sort_values("Date")

    mask = (df["Date"] >= START_DATE) & (df["Date"] <= END_DATE)
    df = df.loc[mask, ["Date", "VNINDEX_Close"]].drop_duplicates(subset=["Date"])

    if df.empty:
        raise RuntimeError(
            "Lọc xong nhưng DataFrame rỗng — kiểm tra lại cột VNINDEX_Close "
            "có đúng tên trong file parquet của bạn không (in ra df.columns để xem)."
        )

    df.to_csv(OUT_PATH, index=False)
    print(f"✅ Đã xuất {len(df)} phiên VNINDEX ({df['Date'].min().date()} -> "
          f"{df['Date'].max().date()}) ra file: {OUT_PATH}")
    print(df.head(3))
    print("...")
    print(df.tail(3))


if __name__ == "__main__":
    main()