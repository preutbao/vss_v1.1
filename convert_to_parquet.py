import pandas as pd
import os
import gc

# --- CẤU HÌNH ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RAW_DIR = os.path.join(BASE_DIR, "data", "raw")
PROCESSED_DIR = os.path.join(BASE_DIR, "data", "processed")
os.makedirs(PROCESSED_DIR, exist_ok=True)

FILES = {
    "yearly": "BCTC THEO NĂM.xlsx",
    "quarterly": "BCTC THEO QUÝ.xlsx",
    "price": "HISTORICAL PRICES.xlsx",
    "index": "INDEX.xlsx",
}

# --- 1. HÀM ĐỌC COMP ---
def load_company_info(file_path):
    try:
        df_comp = pd.read_excel(file_path, "COMP", engine='openpyxl')
        df_comp = df_comp.dropna(axis=1, how='all')
        if len(df_comp.columns) > 0:
            df_comp.rename(columns={df_comp.columns[0]: "Ticker"}, inplace=True)
        
        desired_cols = ['Ticker', 'Company Common Name', 'GICS Sub-Industry Name', 'TRBC Industry Name', 
                        'GICS Industry Name', 'GICS Sector Name', 'Organization Founded Year', 'Date Became Public', 'Auditor Details']
        existing_cols = [c for c in desired_cols if c in df_comp.columns]
        df_comp = df_comp[existing_cols]
        
        if 'Ticker' in df_comp.columns:
            df_comp['Ticker'] = df_comp['Ticker'].astype(str)
            # Loại bỏ trùng lặp Ticker ngay từ nguồn
            df_comp = df_comp.drop_duplicates(subset=['Ticker'])
            
        print(f"   -> Đã load thông tin {len(df_comp)} công ty.")
        return df_comp
    except Exception as e:
        print(f"   ⚠️ Lỗi đọc COMP: {e}")
        return pd.DataFrame()

# --- 2. HÀM ĐỌC THÔNG MINH ---
def smart_read_excel(xls, sheet_name, safe_limit=60):
    try:
        df_header = pd.read_excel(xls, sheet_name, nrows=0)
        cols_to_read = min(len(df_header.columns), safe_limit)
        if cols_to_read == 0: return pd.DataFrame()
        return pd.read_excel(xls, sheet_name, usecols=list(range(cols_to_read)))
    except Exception:
        return pd.DataFrame()

# --- 3. XỬ LÝ BATCH (THÊM DEDUPLICATE) ---
def process_financial_batch_raw(xls, sheet_names, output_filename):
    print(f"   -> Đang xử lý batch số liệu: {output_filename} ({len(sheet_names)} sheets)...")
    master_df = None
    valid_prefixes = ("BS", "IS", "CF")
    
    for i, sheet_name in enumerate(sheet_names):
        if not any(sheet_name.upper().startswith(p) for p in valid_prefixes): continue
        
        try:
            print(f"      Reading: {sheet_name}...", end="\r")
            df_sheet = smart_read_excel(xls, sheet_name, safe_limit=60)
            
            if len(df_sheet.columns) < 3:
                del df_sheet; gc.collect()
                continue

            cols = list(df_sheet.columns)
            if len(cols) >= 2:
                cols[0] = "Ticker"; cols[1] = "Date"
                df_sheet.columns = cols

            df_sheet = df_sheet.loc[:, ~df_sheet.columns.astype(str).str.contains('^Unnamed')]
            df_sheet["Date"] = pd.to_datetime(df_sheet["Date"], errors='coerce')
            df_sheet = df_sheet.dropna(subset=['Ticker', 'Date'])
            df_sheet["Ticker"] = df_sheet["Ticker"].astype(str)

            # --- QUAN TRỌNG: Loại bỏ trùng lặp ngay tại sheet ---
            # Nếu 1 sheet có 2 dòng cùng Ticker+Date -> Giữ dòng cuối
            df_sheet = df_sheet.drop_duplicates(subset=['Ticker', 'Date'], keep='last')

            if master_df is None:
                master_df = df_sheet
            else:
                # Merge Outer
                master_df = pd.merge(master_df, df_sheet, on=["Ticker", "Date"], how="outer")
                
                # --- QUAN TRỌNG: Loại bỏ trùng lặp sau khi Merge ---
                # Đề phòng trường hợp merge sinh ra dòng thừa
                if master_df.duplicated(subset=['Ticker', 'Date']).any():
                     master_df = master_df.drop_duplicates(subset=['Ticker', 'Date'], keep='last')
            
            del df_sheet; gc.collect()

        except Exception as e:
            print(f"\n      ⚠️ Lỗi sheet {sheet_name}: {e}")
            continue
            
    if master_df is not None and not master_df.empty:
        # Check lần cuối trước khi lưu
        master_df = master_df.drop_duplicates(subset=['Ticker', 'Date'], keep='last')
        
        output_path = os.path.join(PROCESSED_DIR, output_filename)
        master_df.to_parquet(output_path)
        print(f"\n      ✅ Đã lưu batch thô: {output_filename} ({len(master_df):,} dòng)")
        del master_df; gc.collect()
        return True
    return False

# --- 4. HÀM CHÍNH (THÊM DEDUPLICATE TRƯỚC KHI MERGE TỔNG) ---
def convert_financial_quarterly_split():
    input_name = FILES["quarterly"]
    input_path = os.path.join(RAW_DIR, input_name)
    if not os.path.exists(input_path): return

    print(f"⏳ Đang xử lý BCTC QUÝ...")
    xls = pd.ExcelFile(input_path)
    
    all_sheets = xls.sheet_names
    mid_point = len(all_sheets) // 2
    batch_1 = all_sheets[:mid_point]
    batch_2 = all_sheets[mid_point:]
    
    # Nếu file part1/part2 chưa có thì tạo, có rồi thì dùng luôn cho nhanh
    p1_path = os.path.join(PROCESSED_DIR, "quarterly_raw_part1.parquet")
    p2_path = os.path.join(PROCESSED_DIR, "quarterly_raw_part2.parquet")

    if not os.path.exists(p1_path):
        process_financial_batch_raw(xls, batch_1, "quarterly_raw_part1.parquet")
        gc.collect()
    else:
        print("   -> Đã có sẵn part 1. Bỏ qua bước tạo.")

    if not os.path.exists(p2_path):
        process_financial_batch_raw(xls, batch_2, "quarterly_raw_part2.parquet")
        gc.collect()
    else:
        print("   -> Đã có sẵn part 2. Bỏ qua bước tạo.")

    # BƯỚC MERGE QUAN TRỌNG
    print("   -> Đang gộp 2 phần số liệu...")
    dfs = []
    if os.path.exists(p1_path): 
        df1 = pd.read_parquet(p1_path)
        # --- CHỐT CHẶN TRÙNG LẶP ---
        df1 = df1.drop_duplicates(subset=['Ticker', 'Date'])
        dfs.append(df1)
        
    if os.path.exists(p2_path): 
        df2 = pd.read_parquet(p2_path)
        # --- CHỐT CHẶN TRÙNG LẶP ---
        df2 = df2.drop_duplicates(subset=['Ticker', 'Date'])
        dfs.append(df2)
    
    if not dfs: return

    # Merge
    final_df = dfs[0]
    if len(dfs) > 1:
        # Vì đã drop_duplicates ở trên, merge này sẽ là 1-1, không bao giờ bùng nổ
        final_df = pd.merge(dfs[0], dfs[1], on=["Ticker", "Date"], how="outer")
    
    # Giải phóng RAM
    del dfs
    gc.collect()

    # Merge COMP
    print("   -> Đang đọc thông tin công ty (COMP)...")
    df_comp = load_company_info(input_path)
    
    if not df_comp.empty:
        print("   -> Đang ghép thông tin công ty vào bảng tổng...")
        final_df = pd.merge(final_df, df_comp, on="Ticker", how="left")
    
    final_path = os.path.join(PROCESSED_DIR, "financial_quarterly.parquet")
    final_df.to_parquet(final_path)
    print(f"   🎉 HOÀN TẤT BCTC QUÝ: {len(final_df):,} dòng.")
    
    # Xóa file tạm
    if os.path.exists(p1_path): os.remove(p1_path)
    if os.path.exists(p2_path): os.remove(p2_path)

def convert_financial_yearly():
    input_name = FILES["yearly"]
    output_name = "financial_yearly.parquet"
    input_path = os.path.join(RAW_DIR, input_name)
    if not os.path.exists(input_path): return
    
    print(f"⏳ Đang xử lý BCTC NĂM...")
    xls = pd.ExcelFile(input_path)
    process_financial_batch_raw(xls, xls.sheet_names, "yearly_raw_temp.parquet")
    
    temp_path = os.path.join(PROCESSED_DIR, "yearly_raw_temp.parquet")
    if os.path.exists(temp_path):
        df_main = pd.read_parquet(temp_path)
        # Drop duplicates cho năm luôn cho chắc
        df_main = df_main.drop_duplicates(subset=['Ticker', 'Date'])
        
        df_comp = load_company_info(input_path)
        if not df_comp.empty:
            df_main = pd.merge(df_main, df_comp, on="Ticker", how="left")
            
        df_main.to_parquet(os.path.join(PROCESSED_DIR, output_name))
        print(f"   ✅ HOÀN TẤT BCTC NĂM: {len(df_main):,} dòng.")
        os.remove(temp_path)

def convert_price_only():
    input_path = os.path.join(RAW_DIR, FILES["price"])
    output_path = os.path.join(PROCESSED_DIR, "market_prices.parquet")
    if not os.path.exists(input_path): return
    if os.path.exists(output_path): 
        print("   ✅ File Giá đã tồn tại. Bỏ qua.")
        return

    print(f"⏳ Đang xử lý GIÁ (Tách biệt)...")
    xls = pd.ExcelFile(input_path)
    
    # ── THÊM: Đọc Sheet1 để lấy thông tin công ty ──
    df_sheet1 = pd.DataFrame()
    if "Sheet1" in xls.sheet_names:
        try:
            df_s1 = pd.read_excel(xls, "Sheet1")
            df_s1 = df_s1.dropna(axis=1, how="all")
            
            # Tìm cột Ticker linh hoạt (không phụ thuộc vào vị trí hay tên chính xác)
            ticker_col = next(
                (c for c in df_s1.columns if str(c).strip().lower() == "ticker"),
                None
            )
            if ticker_col is None:
                # Nếu không tìm thấy đúng tên, lấy cột đầu tiên
                ticker_col = df_s1.columns[0]
            
            if ticker_col != "Ticker":
                df_s1 = df_s1.rename(columns={ticker_col: "Ticker"})
            
            # Tìm linh hoạt theo tên gần đúng (case-insensitive)
            col_map = {str(c).strip().lower(): c for c in df_s1.columns}
            keep = []
            for want in ["Ticker", "Company Common Name",
                        "GICS Sector Name", "GICS Industry Name",
                        "GICS Sub-Industry Name", "TRBC Industry Name"]:
                actual = col_map.get(want.lower())
                if actual:
                    if actual != want:
                        df_s1 = df_s1.rename(columns={actual: want})
                    keep.append(want)
            
            if "Ticker" in keep:
                df_sheet1 = (df_s1[keep]
                            .dropna(subset=["Ticker"])
                            .drop_duplicates("Ticker"))
                df_sheet1["Ticker"] = df_sheet1["Ticker"].astype(str)
                print(f"   -> Sheet1: {len(df_sheet1)} công ty, cột: {list(df_sheet1.columns)}")
            else:
                print(f"   ⚠️ Sheet1 không tìm được cột Ticker. Cột thực tế: {list(df_s1.columns[:6])}")
        except Exception as e:
            print(f"   ⚠️ Không đọc được Sheet1: {e}")
    
    all_dfs = []
    for sheet_name in xls.sheet_names:
        if sheet_name == "Sheet1": continue
        try:
            df_sheet = pd.read_excel(xls, sheet_name)
            cols = list(df_sheet.columns)
            cols[0] = "Ticker"; cols[1] = "Date"
            df_sheet.columns = cols
            df_sheet = df_sheet.loc[:, ~df_sheet.columns.str.contains('^Unnamed')]
            df_sheet["Date"] = pd.to_datetime(df_sheet["Date"], errors='coerce')
            df_sheet = df_sheet.dropna(subset=['Ticker'])
            df_sheet["Ticker"] = df_sheet["Ticker"].astype(str)
            all_dfs.append(df_sheet)
            del df_sheet; gc.collect()
        except: continue
        
    if all_dfs:
        df_final = pd.concat(all_dfs, ignore_index=True)
        df_final = df_final.drop_duplicates(subset=['Ticker', 'Date'])
        
        # ── THÊM: Merge thông tin công ty từ Sheet1 ──
        if not df_sheet1.empty:
            df_final = pd.merge(df_final, df_sheet1, on="Ticker", how="left")
            sector_count = df_final["GICS Sector Name"].notna().sum() if "GICS Sector Name" in df_final.columns else 0
            print(f"   -> Đã merge Sheet1: {sector_count:,} dòng có GICS Sector Name")
        
        df_final.to_parquet(output_path)
        print(f"   ✅ Xong GIÁ: {len(df_final):,} dòng, cột: {len(df_final.columns)}")

def convert_index_only():
    input_path = os.path.join(RAW_DIR, FILES["index"])
    output_path = os.path.join(PROCESSED_DIR, "index.parquet")
    if not os.path.exists(input_path): return
    if os.path.exists(output_path):
        print("   ✅ File Index đã tồn tại. Bỏ qua.")
        return

    print("⏳ Đang xử lý INDEX...")
    try:
        # Header row 0: Date | .VNI (TRDPRC_1) | .VNI30 ... | .VNI100 ...
        # Header row 1: ''   | Close           | Close       | Close
        df = pd.read_excel(input_path, header=0)
        df.columns = df.columns.str.strip()

        # Đổi tên cột về chuẩn nội bộ
        rename_map = {}
        for col in df.columns:
            cl = col.upper()
            if 'DATE' in cl:
                rename_map[col] = 'Date'
            elif 'VNI30' in cl or 'VNI 30' in cl:
                rename_map[col] = 'VN30_Close'
            elif 'VNI100' in cl or 'VNI100' in cl:
                rename_map[col] = 'VN100_Close'
            elif 'VNI' in cl:
                rename_map[col] = 'JCI_Close'   # giữ tên JCI_Close để không đổi code downstream
        df = df.rename(columns=rename_map)

        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
        df["JCI_Close"] = pd.to_numeric(df["JCI_Close"], errors="coerce")
        df = df.dropna(subset=["Date", "JCI_Close"])
        df = df.drop_duplicates(subset=["Date"]).sort_values("Date")
        df.to_parquet(output_path)
        print(f"   ✅ Xong INDEX: {len(df):,} dòng, cột: {list(df.columns)}")
    except Exception as e:
        print(f"   ❌ Lỗi Index: {e}")

if __name__ == "__main__":
    convert_financial_yearly()
    convert_financial_quarterly_split()
    convert_price_only()
    convert_index_only()
    print("\n🎉 ĐÃ XONG TOÀN BỘ!")