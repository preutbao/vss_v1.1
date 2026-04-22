"""
check_parquet.py — Chạy ở thư mục gốc dự án (cùng chỗ với main.py)
python check_parquet.py
"""
import os
import pandas as pd

PROCESSED = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "processed")

FILES = {
    "price":      "market_prices.parquet",
    "fin_y":      "financial_yearly.parquet",
    "snapshot":   "snapshot_cache.parquet",
}

SEP = "=" * 65

def check(label, path):
    print(f"\n{SEP}")
    print(f"  {label}")
    print(f"  {path}")
    print(SEP)
    if not os.path.exists(path):
        print("  ❌ FILE KHÔNG TỒN TẠI")
        return

    df = pd.read_parquet(path)
    print(f"  Rows   : {len(df):,}")
    print(f"  Columns: {len(df.columns)}")

    # Tìm cột liên quan đến ngành
    sector_cols = [c for c in df.columns
                   if any(k in c.lower() for k in
                          ['sector','industry','gics','trbc','icb','ngành','nganh'])]
    print(f"\n  ── Cột ngành/sector tìm được ({len(sector_cols)}): ──")
    for col in sector_cols:
        vals = df[col].dropna().unique()
        sample = list(vals[:8])
        print(f"    [{col}]  ({len(vals)} giá trị khác nhau)")
        print(f"       Sample: {sample}")

    if not sector_cols:
        print("  ⚠️  Không tìm thấy cột ngành nào!")

    # Kiểm tra Ticker
    if 'Ticker' in df.columns:
        sample_tickers = df['Ticker'].dropna().head(6).tolist()
        print(f"\n  ── Ticker sample: {sample_tickers}")
        has_suffix = df['Ticker'].astype(str).str.contains(r'\.(HM|HN|HNO)$', regex=True)
        n_suffix = has_suffix.sum()
        print(f"     Tickers còn đuôi sàn (.HM/.HN/.HNO): {n_suffix} / {len(df)}")

    # Kiểm tra ngày
    for date_col in ['Date', 'date']:
        if date_col in df.columns:
            print(f"\n  ── Ngày ({date_col}): min={df[date_col].min()}  max={df[date_col].max()}")
            break

for key, fname in FILES.items():
    check(key.upper(), os.path.join(PROCESSED, fname))

print(f"\n{SEP}\n  XONG\n{SEP}\n")