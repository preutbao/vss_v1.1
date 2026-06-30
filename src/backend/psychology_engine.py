# src/backend/psychology_engine.py
"""
Backend xử lý dữ liệu cho tính năng "Trạm Cứu Viện Tâm Lý" (Rumor Check).
Bám sát Framework 4 Trụ Cột (Vi mô): Cơ cấu vốn, Cơ cấu cổ đông,
Mô hình kinh doanh, Định giá.
"""

import logging
import math
import copy
import pandas as pd

from src.backend.data_loader import get_snapshot_df, load_financial_data_nocache

logger = logging.getLogger(__name__)

_REV_COL_CANDIDATES = [
    'Revenue from Business Activities - Total_x',
    'Revenue from Business Activities - Total',
    'Sales of Goods & Services - Net - Unclassified',
]
_GROSS_PROFIT_COL_CANDIDATES = [
    'Gross Profit - Industrials/Property - Total',
    'Gross Profit',
    'Gross Profit - Total',
]

def _find_col(df, candidates):
    for c in candidates:
        if c in df.columns:
            return c
    return None

# Ngưỡng tham chiếu MẶC ĐỊNH
DEFAULT_THRESHOLDS = {
    "current_ratio": {"safe": 1.5, "watch": 1.0},
    "de":            {"safe": 1.0, "watch": 2.0},
    "valuation_premium": 1.3,
    "profitability_ratio": {"watch": 0.8, "risk": 0.5},
    "net_cash_pct": {"safe": 0.0, "watch": -20.0},
    "pct_from_high_1y": {"safe": -15.0, "watch": -35.0},
    "pct_from_low_1y_alert": 10.0,
    "price_vs_ma": {"safe": 0.0, "watch": -5.0},
    # Ngưỡng 5 tỷ VND/ngày lấy ĐÚNG từ logic chấm điểm thanh khoản gốc
    # trong quant_engine.py (xem "gtgd_penalty ... < 5_000_000_000") để
    # nhất quán với phần còn lại của hệ thống, không tự đặt ngưỡng mới.
    "gtgd_vnd": {"safe": 10_000_000_000, "watch": 5_000_000_000},
    "beta": {"safe": 1.0, "watch": 1.5},
    "eps_cagr_pct": {"watch": 0.0},
    "dividend_yield_pct": {"safe": 2.0},
}

def _get_dynamic_thresholds(profile_data):
    t = copy.deepcopy(DEFAULT_THRESHOLDS)
    if not profile_data:
        return t

    prof_str = str(profile_data).lower()
    
    # Nhóm BẢO THỦ / AN TOÀN
    if any(k in prof_str for k in ["bảo thủ", "an toàn", "conservative", "thấp", "low"]):
        t["pct_from_high_1y"]["safe"] = -7.0   
        t["pct_from_high_1y"]["watch"] = -15.0 
        t["price_vs_ma"]["watch"] = 0.0        

    # Nhóm MẠO HIỂM / TĂNG TRƯỞNG
    elif any(k in prof_str for k in ["mạo hiểm", "tăng trưởng", "aggressive", "cao", "high"]):
        t["pct_from_high_1y"]["safe"] = -20.0  
        t["pct_from_high_1y"]["watch"] = -40.0 
        t["price_vs_ma"]["watch"] = -10.0      

    return t

FEAR_LABELS = {
    "A1": "Vỡ nợ / mất khả năng thanh toán ngắn hạn",
    "A2": "Nợ vay đầm đìa, rủi ro cao",
    "A3": "Kinh doanh cốt lõi đi lùi",
    "A4": "Bong bóng định giá",
    "B1": "Hiệu quả sinh lời (ROE/ROA) yếu",
    "B2": "Hết tiền mặt / không chống chọi nổi khó khăn",
    "C1": "Giá giảm quá sâu, không rõ đáy",
    "C2": "Xu hướng giá đã gãy",
    "D1": "FOMO — sợ mua đu đỉnh",
    "E1": "Thanh khoản thấp, sợ kẹp hàng không bán được",
    "E2": "Biến động mạnh hơn thị trường chung",
    "F1": "Tăng trưởng dài hạn ì ạch",
    "F2": "Không có cổ tức, không có dòng tiền thụ động",
}

# ─────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────
def _is_nan(val) -> bool:
    return val is None or (isinstance(val, float) and math.isnan(val))

def _fmt(val, suffix="", digits=2) -> str:
    if _is_nan(val): return "N/A"
    return f"{val:,.{digits}f}{suffix}"

def _get_ticker_row(ticker: str):
    df = get_snapshot_df()
    if df is None or df.empty or "Ticker" not in df.columns: return None, None
    df = df.copy()
    df["Ticker"] = df["Ticker"].astype(str).str.upper()
    row_df = df.loc[df["Ticker"] == ticker]
    if row_df.empty: return None, df
    return row_df.iloc[0], df

def _sector_median(df_all, sector, col, positive_only: bool = False):
    if not sector or df_all is None or col not in df_all.columns or "GICS Sector Name" not in df_all.columns:
        return None
    peers = df_all[df_all["GICS Sector Name"] == sector]
    s = pd.to_numeric(peers[col], errors="coerce")
    s = s[s.notna()]
    if positive_only: s = s[s > 0]
    if s.empty: return None
    return s.median()

# ─────────────────────────────────────────────────────────────────────────
# Các hàm phân tích A1 -> B2 (Dùng DEFAULT_THRESHOLDS)
# ─────────────────────────────────────────────────────────────────────────
def _analyze_a1(row):
    cr = row.get("Current Ratio")
    t = DEFAULT_THRESHOLDS["current_ratio"]

    if _is_nan(cr):
        verdict = "neutral"
        conclusion = "Chưa có đủ dữ liệu Tài sản/Nợ ngắn hạn để tính Current Ratio cho mã này."
    elif cr >= t["safe"]:
        verdict = "safe"
        conclusion = f"Current Ratio đạt {_fmt(cr, 'x')}, tài sản ngắn hạn dư sức bao phủ nợ ngắn hạn (ngưỡng an toàn ≥ {t['safe']}x). Rủi ro mất khả năng thanh toán trong ngắn hạn ở mức thấp."
    elif cr >= t["watch"]:
        verdict = "watch"
        conclusion = f"Current Ratio ở mức {_fmt(cr, 'x')} — quanh vùng cân bằng ({t['watch']}x–{t['safe']}x). Doanh nghiệp vẫn xoay vòng được vốn ngắn hạn nhưng nên theo dõi thêm dòng tiền hoạt động."
    else:
        verdict = "risk"
        conclusion = f"Current Ratio chỉ {_fmt(cr, 'x')}, thấp hơn {t['watch']}x — tài sản ngắn hạn không đủ bù đắp nợ ngắn hạn trên sổ sách. Đây là điểm cần thận trọng thật sự."

    return {"fear": "A1", "title": FEAR_LABELS["A1"], "verdict": verdict, "metrics": [("Current Ratio", _fmt(cr, "x"))], "conclusion": conclusion}

def _analyze_a2(row):
    de = row.get("D/E")
    t = DEFAULT_THRESHOLDS["de"]

    if _is_nan(de):
        verdict = "neutral"
        conclusion = "Chưa có đủ dữ liệu Nợ vay/Vốn chủ sở hữu để tính D/E cho mã này."
    elif de <= t["safe"]:
        verdict = "safe"
        conclusion = f"D/E hiện tại chỉ {_fmt(de, 'x')}, thấp hơn ngưỡng nguy hiểm {t['watch']}x. Nền tảng vốn vẫn an toàn, doanh nghiệp không dùng đòn bẩy quá mức."
    elif de <= t["watch"]:
        verdict = "watch"
        conclusion = f"D/E ở mức {_fmt(de, 'x')} — đòn bẩy trung bình, vẫn trong tầm kiểm soát nhưng nên theo dõi thêm."
    else:
        verdict = "risk"
        conclusion = f"D/E lên tới {_fmt(de, 'x')}, vượt ngưỡng {t['watch']}x — doanh nghiệp đang dùng đòn bẩy tài chính khá cao. Đây là rủi ro thật."

    return {"fear": "A2", "title": FEAR_LABELS["A2"], "verdict": verdict, "metrics": [("D/E", _fmt(de, "x"))], "conclusion": conclusion}

def _get_quarterly_a3_metrics(ticker: str):
    try: df_q = load_financial_data_nocache("quarterly")
    except: return None, None, None
    if df_q is None or df_q.empty or "Ticker" not in df_q.columns or "Date" not in df_q.columns: return None, None, None
    
    df_q = df_q.copy()
    df_q["Ticker"] = df_q["Ticker"].astype(str).str.upper()
    grp = df_q[df_q["Ticker"] == ticker].copy()
    if grp.empty: return None, None, None

    grp["Date"] = pd.to_datetime(grp["Date"], errors="coerce")
    grp = grp.dropna(subset=["Date"]).sort_values("Date")
    if grp.empty: return None, None, None

    rev_col = _find_col(grp, _REV_COL_CANDIDATES)
    gp_col = _find_col(grp, _GROSS_PROFIT_COL_CANDIDATES)

    rev_growth_yoy = gross_margin = None
    last_date = grp["Date"].iloc[-1]
    quarter_label = f"Q{last_date.quarter}/{last_date.year}"

    if rev_col:
        rev_series = pd.to_numeric(grp[rev_col], errors="coerce").reset_index(drop=True)
        if len(rev_series) >= 5:
            v_last, v_yoy = rev_series.iloc[-1], rev_series.iloc[-5]
            if pd.notna(v_last) and pd.notna(v_yoy) and v_yoy > 0: rev_growth_yoy = round((v_last - v_yoy) / abs(v_yoy) * 100, 2)
        if gp_col:
            gp_series = pd.to_numeric(grp[gp_col], errors="coerce").reset_index(drop=True)
            if len(gp_series) == len(rev_series):
                v_rev_last, v_gp_last = rev_series.iloc[-1], gp_series.iloc[-1]
                if pd.notna(v_rev_last) and v_rev_last > 0 and pd.notna(v_gp_last): gross_margin = round(v_gp_last / v_rev_last * 100, 2)
    return rev_growth_yoy, gross_margin, quarter_label

def _analyze_a3(row, ticker: str):
    rev_g, gm, quarter_label = _get_quarterly_a3_metrics(ticker)
    period_tag = f" ({quarter_label})" if quarter_label else " (quý)"
    used_fallback = False
    
    if _is_nan(rev_g) and _is_nan(gm):
        rev_g = row.get("Revenue Growth YoY (%)")
        gm = row.get("Gross Margin (%)")
        period_tag = " (năm gần nhất — thiếu dữ liệu quý)"
        used_fallback = True

    rev_ok, gm_ok = not _is_nan(rev_g), not _is_nan(gm)

    if not rev_ok and not gm_ok:
        verdict, conclusion = "neutral", "Chưa có đủ dữ liệu tăng trưởng doanh thu/biên lợi nhuận gộp gần nhất cho mã này."
    else:
        if rev_ok and rev_g > 0:
            verdict, growth_txt = "safe", f"doanh thu vẫn tăng trưởng {_fmt(rev_g, '%')} so với cùng kỳ"
        elif rev_ok:
            verdict, growth_txt = "watch", f"doanh thu giảm {_fmt(abs(rev_g), '%')} so với cùng kỳ"
        else:
            verdict, growth_txt = "neutral", "chưa có dữ liệu tăng trưởng doanh thu"

        gm_txt = f"biên lợi nhuận gộp đạt {_fmt(gm, '%')}" if gm_ok else "chưa có dữ liệu biên lợi nhuận gộp"
        if verdict == "watch" and gm_ok and gm > 0:
            conclusion = f"Số liệu{period_tag} cho thấy {growth_txt}, tuy nhiên {gm_txt} — biên lợi nhuận gộp vẫn dương cho thấy hoạt động lõi chưa mất khả năng sinh lời."
        else:
            conclusion = f"Số liệu{period_tag} cho thấy {growth_txt}, {gm_txt}."
            if verdict == "safe": conclusion += " Mô hình kinh doanh cốt lõi chưa cho thấy dấu hiệu suy yếu như tin đồn."

    metric_suffix = " (năm)" if used_fallback else " (quý)"
    return {"fear": "A3", "title": FEAR_LABELS["A3"], "verdict": verdict, "metrics": [(f"Tăng trưởng DT YoY{metric_suffix}", _fmt(rev_g, "%") if rev_ok else "N/A"), (f"Biên LN gộp{metric_suffix}", _fmt(gm, "%") if gm_ok else "N/A")], "conclusion": conclusion}

def _analyze_a4(row, df_all):
    pe, pb, sector = row.get("P/E"), row.get("P/B"), row.get("GICS Sector Name")
    pe_ok, pb_ok = not _is_nan(pe) and pe > 0, not _is_nan(pb) and pb > 0
    sector_pe, sector_pb = _sector_median(df_all, sector, "P/E", True), _sector_median(df_all, sector, "P/B", True)

    if not pe_ok and not pb_ok:
        verdict, conclusion = "neutral", "Chưa có đủ dữ liệu P/E hoặc P/B để so sánh định giá cho mã này."
    else:
        premium = DEFAULT_THRESHOLDS["valuation_premium"]
        parts, verdict = [], "safe"

        if pe_ok:
            parts.append(f"P/E = {_fmt(pe, 'x')}")
            if sector_pe and not _is_nan(sector_pe):
                parts.append(f"(trung vị ngành ≈ {_fmt(sector_pe, 'x')})")
                if pe > sector_pe * premium: verdict = "watch"
        if pb_ok:
            parts.append(f"P/B = {_fmt(pb, 'x')}")
            if sector_pb and not _is_nan(sector_pb):
                parts.append(f"(trung vị ngành ≈ {_fmt(sector_pb, 'x')})")
                if pb > sector_pb * premium: verdict = "watch"

        if verdict == "safe":
            conclusion = "Định giá hiện tại " + ", ".join(parts) + " — không cho thấy mức chênh lệch bất thường so với mặt bằng cùng ngành, chưa đủ cơ sở để gọi đây là 'bong bóng'."
        else:
            conclusion = "Định giá hiện tại " + ", ".join(parts) + " — đang cao hơn đáng kể so với trung vị ngành. Mức premium này cần được lý giải bằng câu chuyện tăng trưởng cụ thể."

    return {"fear": "A4", "title": FEAR_LABELS["A4"], "verdict": verdict, "metrics": [("P/E", _fmt(pe, "x") if pe_ok else "N/A"), ("P/B", _fmt(pb, "x") if pb_ok else "N/A")], "conclusion": conclusion}

def _analyze_b1(row, df_all):
    roe, roa, sector = row.get("ROE (%)"), row.get("ROA (%)"), row.get("GICS Sector Name")
    roe_ok, roa_ok = not _is_nan(roe), not _is_nan(roa)
    t = DEFAULT_THRESHOLDS["profitability_ratio"]

    if not roe_ok and not roa_ok:
        verdict, conclusion = "neutral", "Chưa có đủ dữ liệu ROE/ROA để đánh giá hiệu quả sinh lời cho mã này."
    else:
        sector_roe, sector_roa = _sector_median(df_all, sector, "ROE (%)"), _sector_median(df_all, sector, "ROA (%)")
        parts, verdict = [], "safe"

        def _grade(val, sector_val):
            if sector_val is None: return "safe"
            if val < 0 or val < sector_val * t["risk"]: return "risk"
            if val < sector_val * t["watch"]: return "watch"
            return "safe"

        worst = "safe"
        if roe_ok:
            parts.append(f"ROE = {_fmt(roe, '%')}")
            if sector_roe is not None:
                parts.append(f"(trung vị ngành ≈ {_fmt(sector_roe, '%')})")
                g = _grade(roe, sector_roe)
                worst = g if g != "safe" else worst
        if roa_ok:
            parts.append(f"ROA = {_fmt(roa, '%')}")
            if sector_roa is not None:
                parts.append(f"(trung vị ngành ≈ {_fmt(sector_roa, '%')})")
                g = _grade(roa, sector_roa)
                worst = "risk" if g == "risk" else (worst if worst == "risk" else g)

        verdict = worst
        joined = ", ".join(parts)
        if verdict == "safe": conclusion = f"Hiệu quả sinh lời hiện tại: {joined} — ngang bằng hoặc tốt hơn mặt bằng ngành, chưa có dấu hiệu 'làm ăn sa sút' như tin đồn."
        elif verdict == "watch": conclusion = f"Hiệu quả sinh lời hiện tại: {joined} — thấp hơn phần nào so với ngành, nên theo dõi thêm các quý tới."
        else: conclusion = f"Hiệu quả sinh lời hiện tại: {joined} — thấp hơn đáng kể (hoặc âm) so với ngành. Đây là tín hiệu thật cần lưu ý."

    return {"fear": "B1", "title": FEAR_LABELS["B1"], "verdict": verdict, "metrics": [("ROE", _fmt(roe, "%") if roe_ok else "N/A"), ("ROA", _fmt(roa, "%") if roa_ok else "N/A")], "conclusion": conclusion}

def _analyze_b2(row):
    ncm, nca = row.get("Net Cash / Market Cap (%)"), row.get("Net Cash / Assets (%)")
    ncm_ok, nca_ok = not _is_nan(ncm), not _is_nan(nca)
    t = DEFAULT_THRESHOLDS["net_cash_pct"]

    if not ncm_ok and not nca_ok:
        verdict, conclusion = "neutral", "Chưa có đủ dữ liệu tiền mặt ròng (Net Cash) cho mã này."
    else:
        ref = ncm if ncm_ok else nca
        ncm_txt = _fmt(ncm, "%") if ncm_ok else "N/A"
        nca_txt = _fmt(nca, "%") if nca_ok else "N/A"

        if ref >= t["safe"]:
            verdict, conclusion = "safe", f"Doanh nghiệp đang ở vị thế tiền mặt ròng dương (Net Cash/Vốn hóa = {ncm_txt}, Net Cash/Tổng tài sản = {nca_txt}). Rủi ro 'hết tiền mặt' gần như không có cơ sở."
        elif ref >= t["watch"]:
            verdict, conclusion = "watch", f"Net Cash/Vốn hóa = {ncm_txt}, Net Cash/Tổng tài sản = {nca_txt} — doanh nghiệp đang có nợ vay ròng ở mức vừa phải, vẫn trong tầm kiểm soát."
        else:
            verdict, conclusion = "risk", f"Net Cash/Vốn hóa = {ncm_txt}, Net Cash/Tổng tài sản = {nca_txt} — nợ vay ròng đang ở mức cao so với quy mô doanh nghiệp. Cần đánh giá kỹ."

    return {"fear": "B2", "title": FEAR_LABELS["B2"], "verdict": verdict, "metrics": [("Net Cash/Vốn hóa", _fmt(ncm, "%") if ncm_ok else "N/A"), ("Net Cash/Tổng TS", _fmt(nca, "%") if nca_ok else "N/A")], "conclusion": conclusion}


# ─────────────────────────────────────────────────────────────────────────
# Nhóm C — Cần nhận tham số custom_thresholds đã qua profile khách hàng
# ─────────────────────────────────────────────────────────────────────────
def _analyze_c1(row, custom_thresholds):
    pfh, pfl = row.get("Pct_From_High_1Y"), row.get("Pct_From_Low_1Y")
    pfh_ok, pfl_ok = not _is_nan(pfh), not _is_nan(pfl)
    t = custom_thresholds["pct_from_high_1y"]

    if not pfh_ok and not pfl_ok:
        verdict, conclusion = "neutral", "Chưa có đủ dữ liệu giá 52 tuần để đánh giá mức độ điều chỉnh."
    else:
        if pfh_ok: verdict = "safe" if pfh >= t["safe"] else ("watch" if pfh >= t["watch"] else "risk")
        else: verdict = "neutral"

        near_low_note = ""
        if pfl_ok and pfl <= custom_thresholds["pct_from_low_1y_alert"]:
            near_low_note = " Giá hiện đang sát vùng đáy 1 năm, biến động có thể còn mạnh trong ngắn hạn."

        pfh_txt = _fmt(abs(pfh), "%") if pfh_ok else "N/A"
        if verdict == "safe": conclusion = f"Giá hiện chỉ cách đỉnh 1 năm {pfh_txt} — đây là mức điều chỉnh bình thường trong một xu hướng, chưa phải dấu hiệu 'sụp đổ' như tin đồn." + near_low_note
        elif verdict == "watch": conclusion = f"Giá đã giảm {pfh_txt} so với đỉnh 1 năm — mức điều chỉnh đáng kể, nên theo dõi thêm thanh khoản." + near_low_note
        elif verdict == "risk": conclusion = f"Giá đã giảm sâu {pfh_txt} so với đỉnh 1 năm — đây là vùng biến động mạnh thật sự, chạm ngưỡng cắt lỗ/cảnh báo rủi ro của bạn." + near_low_note
        else: conclusion = "Chưa đủ dữ liệu đỉnh 1 năm để kết luận." + near_low_note

    return {"fear": "C1", "title": FEAR_LABELS["C1"], "verdict": verdict, "metrics": [("Cách đỉnh 1 năm", _fmt(pfh, "%") if pfh_ok else "N/A"), ("Cách đáy 1 năm", _fmt(pfl, "%") if pfl_ok else "N/A")], "conclusion": conclusion}

def _analyze_c2(row, custom_thresholds):
    vs50, vs200 = row.get("Price_vs_SMA50"), row.get("Price_vs_SMA200")
    vs50_ok, vs200_ok = not _is_nan(vs50), not _is_nan(vs200)
    t = custom_thresholds["price_vs_ma"]

    if not vs50_ok and not vs200_ok:
        verdict, conclusion = "neutral", "Chưa có đủ dữ liệu đường trung bình động (MA) để đánh giá xu hướng giá."
    else:
        ref = vs200 if vs200_ok else vs50
        verdict = "safe" if ref >= t["safe"] else ("watch" if ref >= t["watch"] else "risk")

        parts = []
        if vs50_ok: parts.append(f"so với MA50: {_fmt(vs50, '%')}")
        if vs200_ok: parts.append(f"so với MA200: {_fmt(vs200, '%')}")
        joined = ", ".join(parts)

        if verdict == "safe": conclusion = f"Giá hiện tại {joined} — vẫn nằm trên đường xu hướng dài hạn, chưa có dấu hiệu 'gãy' xu hướng tăng."
        elif verdict == "watch": conclusion = f"Giá hiện tại {joined} — vừa thủng nhẹ đường trung bình dài hạn, cần theo dõi thêm."
        else: conclusion = f"Giá hiện tại {joined} — đã gãy hẳn xu hướng dài hạn. Đây là tín hiệu kỹ thuật xấu đối với hồ sơ đầu tư của bạn."

    return {"fear": "C2", "title": FEAR_LABELS["C2"], "verdict": verdict, "metrics": [("Giá vs MA50", _fmt(vs50, "%") if vs50_ok else "N/A"), ("Giá vs MA200", _fmt(vs200, "%") if vs200_ok else "N/A")], "conclusion": conclusion}


# ─────────────────────────────────────────────────────────────────────────
# D1 — FOMO ngược (sợ bỏ lỡ / sợ mua đu đỉnh)
# Dùng RSI_14 (quá mua/quá bán), hiệu suất 1 tháng (Perf_1M), và P/E so với
# trung vị ngành — đều là cột đã xác nhận tồn tại trong snapshot.
# ─────────────────────────────────────────────────────────────────────────
def _analyze_d1(row, df_all):
    rsi = row.get("RSI_14")
    perf_1m = row.get("Perf_1M")
    pe = row.get("P/E")
    sector = row.get("GICS Sector Name")

    rsi_ok = not _is_nan(rsi)
    perf_ok = not _is_nan(perf_1m)
    pe_ok = not _is_nan(pe) and pe > 0
    sector_pe = _sector_median(df_all, sector, "P/E", positive_only=True) if pe_ok else None

    if not rsi_ok and not perf_ok and not pe_ok:
        return {
            "fear": "D1", "title": FEAR_LABELS["D1"], "verdict": "neutral", "metrics": [],
            "conclusion": "Chưa có đủ dữ liệu RSI/hiệu suất/định giá gần đây để đánh giá rủi ro 'đu đỉnh'.",
        }

    notes, overheat_signals = [], 0

    if rsi_ok:
        notes.append(f"RSI(14) = {_fmt(rsi, '', 1)}")
        if rsi >= 70:
            overheat_signals += 1
    if perf_ok:
        notes.append(f"Hiệu suất 1 tháng = {_fmt(perf_1m, '%')}")
        if perf_1m >= 20:
            overheat_signals += 1
    if pe_ok and sector_pe:
        notes.append(f"P/E = {_fmt(pe, 'x')} (trung vị ngành ≈ {_fmt(sector_pe, 'x')})")
        if pe > sector_pe * DEFAULT_THRESHOLDS["valuation_premium"]:
            overheat_signals += 1

    joined = ", ".join(notes)
    if overheat_signals >= 2:
        verdict = "risk"
        conclusion = (
            f"Tổng hợp {joined} — nhiều tín hiệu cho thấy cổ phiếu đang ở vùng QUÁ MUA và định giá đã "
            "chạy khá xa. Nỗi sợ 'mua đu đỉnh' ở đây CÓ cơ sở thật — nên cân nhắc chờ một nhịp điều "
            "chỉnh hoặc giải ngân từng phần (DCA) thay vì mua đuổi toàn bộ ngay lúc này. Chặn một lệnh "
            "mua sai cũng quan trọng như chặn một lệnh bán tháo."
        )
    elif overheat_signals == 1:
        verdict = "watch"
        conclusion = (
            f"Tổng hợp {joined} — có 1 tín hiệu nóng nhưng chưa đồng thuận rõ rệt. Có thể giải ngân "
            "thận trọng, chia nhỏ lệnh thay vì FOMO mua dồn một lần."
        )
    else:
        verdict = "safe"
        conclusion = (
            f"Tổng hợp {joined} — chưa có dấu hiệu quá nóng rõ rệt cả về kỹ thuật lẫn định giá. Cảm "
            "giác 'sợ bỏ lỡ' hiện tại chưa hẳn phản ánh đúng thực trạng, không cần vội vàng."
        )

    return {
        "fear": "D1", "title": FEAR_LABELS["D1"], "verdict": verdict,
        "metrics": [
            ("RSI(14)", _fmt(rsi, "", 1) if rsi_ok else "N/A"),
            ("Hiệu suất 1 tháng", _fmt(perf_1m, "%") if perf_ok else "N/A"),
            ("P/E", _fmt(pe, "x") if pe_ok else "N/A"),
        ],
        "conclusion": conclusion,
    }


# ─────────────────────────────────────────────────────────────────────────
# E1 — Thanh khoản (GTGD bình quân 1 tháng) — sợ kẹp hàng không bán được
# ─────────────────────────────────────────────────────────────────────────
def _analyze_e1(row):
    gtgd = row.get("GTGD_1M")
    t = DEFAULT_THRESHOLDS["gtgd_vnd"]

    if _is_nan(gtgd):
        return {
            "fear": "E1", "title": FEAR_LABELS["E1"], "verdict": "neutral", "metrics": [],
            "conclusion": "Chưa có đủ dữ liệu giá trị giao dịch bình quân để đánh giá thanh khoản.",
        }

    gtgd_ty = gtgd / 1_000_000_000  # quy đổi sang tỷ VND cho dễ đọc
    if gtgd >= t["safe"]:
        verdict = "safe"
        conclusion = (
            f"Giá trị giao dịch bình quân 1 tháng đạt khoảng {gtgd_ty:,.1f} tỷ VND/ngày — thanh khoản "
            "tốt, lệnh mua/bán với khối lượng thông thường gần như không gặp khó khăn."
        )
    elif gtgd >= t["watch"]:
        verdict = "watch"
        conclusion = (
            f"Giá trị giao dịch bình quân 1 tháng khoảng {gtgd_ty:,.1f} tỷ VND/ngày — thanh khoản ở "
            "mức trung bình, vẫn giao dịch được nhưng nên tránh đặt lệnh khối lượng quá lớn cùng lúc "
            "để hạn chế trượt giá."
        )
    else:
        verdict = "risk"
        conclusion = (
            f"Giá trị giao dịch bình quân 1 tháng chỉ khoảng {gtgd_ty:,.1f} tỷ VND/ngày, dưới ngưỡng "
            f"{t['watch']/1_000_000_000:.0f} tỷ VND mà hệ thống dùng để đánh giá thanh khoản an toàn. "
            "Nỗi lo 'kẹp hàng khó bán' ở đây CÓ cơ sở thật — nên giải ngân/thoái vốn theo từng phần "
            "nhỏ, tránh đặt lệnh lớn một lần."
        )

    return {
        "fear": "E1", "title": FEAR_LABELS["E1"], "verdict": verdict,
        "metrics": [("GTGD bình quân 1 tháng", f"{gtgd_ty:,.1f} tỷ/ngày")],
        "conclusion": conclusion,
    }


# ─────────────────────────────────────────────────────────────────────────
# E2 — Biến động so với thị trường chung (Beta)
# ─────────────────────────────────────────────────────────────────────────
def _analyze_e2(row):
    beta = row.get("Beta")
    t = DEFAULT_THRESHOLDS["beta"]

    if _is_nan(beta):
        return {
            "fear": "E2", "title": FEAR_LABELS["E2"], "verdict": "neutral", "metrics": [],
            "conclusion": "Chưa có đủ dữ liệu Beta để so sánh mức biến động với thị trường chung.",
        }

    if beta <= t["safe"]:
        verdict = "safe"
        conclusion = (
            f"Beta = {_fmt(beta, '', 2)} — cổ phiếu biến động NHẸ HƠN hoặc tương đương thị trường "
            "chung (VN-Index). Đây không phải nhóm cổ phiếu 'sóng mạnh', phù hợp với khách hàng ưu "
            "tiên sự ổn định."
        )
    elif beta <= t["watch"]:
        verdict = "watch"
        conclusion = (
            f"Beta = {_fmt(beta, '', 2)} — biến động cao hơn thị trường chung một chút. Khi thị "
            "trường tăng/giảm mạnh, mã này thường dao động mạnh hơn VN-Index tương ứng, cần khách "
            "hàng có khẩu vị rủi ro phù hợp."
        )
    else:
        verdict = "risk"
        conclusion = (
            f"Beta = {_fmt(beta, '', 2)} — biến động MẠNH HƠN ĐÁNG KỂ so với thị trường chung. Đây là "
            "đặc tính có thật của cổ phiếu (biên độ dao động lớn theo cả 2 chiều), không phải tin đồn — "
            "khách hàng cần được giải thích rõ trước khi nắm giữ với tỷ trọng lớn."
        )

    return {
        "fear": "E2", "title": FEAR_LABELS["E2"], "verdict": verdict,
        "metrics": [("Beta", _fmt(beta, "", 2))],
        "conclusion": conclusion,
    }


# ─────────────────────────────────────────────────────────────────────────
# F1 — Tăng trưởng dài hạn (EPS CAGR 5 năm) so với trung vị ngành
# ─────────────────────────────────────────────────────────────────────────
def _analyze_f1(row, df_all):
    eps_cagr = row.get("EPS CAGR 5Y (%)")
    sector = row.get("GICS Sector Name")

    if _is_nan(eps_cagr):
        return {
            "fear": "F1", "title": FEAR_LABELS["F1"], "verdict": "neutral", "metrics": [],
            "conclusion": "Chưa có đủ dữ liệu EPS 5 năm để đánh giá tốc độ tăng trưởng dài hạn.",
        }

    sector_cagr = _sector_median(df_all, sector, "EPS CAGR 5Y (%)")
    sector_txt = f" (trung vị ngành ≈ {_fmt(sector_cagr, '%')})" if sector_cagr is not None else ""

    if eps_cagr < DEFAULT_THRESHOLDS["eps_cagr_pct"]["watch"]:
        verdict = "risk"
        conclusion = (
            f"EPS CAGR 5 năm = {_fmt(eps_cagr, '%')}{sector_txt} — lợi nhuận/cổ phần tăng trưởng ÂM "
            "trong dài hạn. Nỗi lo 'ì ạch, hết động lực tăng trưởng' ở đây có cơ sở thật, nên tìm hiểu "
            "thêm câu chuyện tái cấu trúc/chuyển đổi mô hình kinh doanh nếu có."
        )
    elif sector_cagr is not None and eps_cagr < sector_cagr * 0.5:
        verdict = "watch"
        conclusion = (
            f"EPS CAGR 5 năm = {_fmt(eps_cagr, '%')}{sector_txt} — tăng trưởng dương nhưng chậm hơn "
            "đáng kể so với mặt bằng ngành, nên theo dõi thêm động lực tăng trưởng sắp tới."
        )
    else:
        verdict = "safe"
        conclusion = (
            f"EPS CAGR 5 năm = {_fmt(eps_cagr, '%')}{sector_txt} — doanh nghiệp vẫn duy trì tăng "
            "trưởng lợi nhuận/cổ phần dương trong dài hạn, chưa cho thấy dấu hiệu 'hết động lực' như "
            "lo ngại."
        )

    return {
        "fear": "F1", "title": FEAR_LABELS["F1"], "verdict": verdict,
        "metrics": [("EPS CAGR 5 năm", _fmt(eps_cagr, "%"))],
        "conclusion": conclusion,
    }


# ─────────────────────────────────────────────────────────────────────────
# F2 — Tỷ suất cổ tức (Dividend Yield)
# ─────────────────────────────────────────────────────────────────────────
def _analyze_f2(row):
    dy = row.get("Dividend Yield (%)")
    t = DEFAULT_THRESHOLDS["dividend_yield_pct"]

    if _is_nan(dy):
        return {
            "fear": "F2", "title": FEAR_LABELS["F2"], "verdict": "neutral", "metrics": [],
            "conclusion": "Chưa có đủ dữ liệu tỷ suất cổ tức cho mã này.",
        }

    if dy >= t["safe"]:
        verdict = "safe"
        conclusion = (
            f"Tỷ suất cổ tức hiện tại = {_fmt(dy, '%')} — doanh nghiệp vẫn đều đặn chia cổ tức ở mức "
            "đáng kể, có dòng tiền thụ động bên cạnh kỳ vọng chênh lệch giá."
        )
    elif dy > 0:
        verdict = "watch"
        conclusion = (
            f"Tỷ suất cổ tức hiện tại = {_fmt(dy, '%')} — có chia cổ tức nhưng ở mức khiêm tốn, dòng "
            "tiền thụ động không lớn, lợi nhuận chủ yếu phải kỳ vọng vào chênh lệch giá."
        )
    else:
        verdict = "watch"
        conclusion = (
            "Doanh nghiệp hiện không chia cổ tức bằng tiền. Đây có thể là chiến lược giữ lại lợi "
            "nhuận để tái đầu tư/mở rộng (thường gặp ở cổ phiếu tăng trưởng) chứ không hẳn là dấu hiệu "
            "xấu — nhưng nếu khách hàng cần dòng tiền thụ động đều đặn thì đây là điểm thực sự cần "
            "lưu ý khi lựa chọn mã này."
        )

    return {
        "fear": "F2", "title": FEAR_LABELS["F2"], "verdict": verdict,
        "metrics": [("Tỷ suất cổ tức", _fmt(dy, "%"))],
        "conclusion": conclusion,
    }


# ─────────────────────────────────────────────────────────────────────────
# WOW FACTOR 1 — "Đồng cảnh ngộ" (Peer Context)
# Tự động sinh thêm (không cần tick riêng) khi khách hàng chọn C1/C2 — so
# hiệu suất 1 tuần (Perf_1W) của mã với trung vị cùng ngành, giúp phân biệt
# rủi ro hệ thống/ngành với rủi ro riêng của doanh nghiệp.
# ─────────────────────────────────────────────────────────────────────────
def _peer_context(row, df_all):
    perf = row.get("Perf_1W")
    sector = row.get("GICS Sector Name")
    ticker = row.get("Ticker")
    if _is_nan(perf) or not sector or perf >= 0:
        return None  # chỉ có ý nghĩa trấn an khi mã đang giảm

    sector_perf = _sector_median(df_all, sector, "Perf_1W")
    if sector_perf is None:
        return None

    diff = perf - sector_perf
    perf_txt, sector_txt = _fmt(abs(perf), "%"), _fmt(abs(sector_perf), "%")

    if sector_perf < 0 and abs(diff) <= 1.5:
        tone, message = "reassure", (
            f"Trong 1 tuần qua, {ticker} giảm {perf_txt}, trong khi trung vị toàn ngành {sector} cũng "
            f"giảm {sector_txt} — mức giảm gần như tương đồng mặt bằng chung. Đây nhiều khả năng là "
            "rủi ro hệ thống/ngành, không phải dấu hiệu riêng có vấn đề của doanh nghiệp."
        )
    elif diff < -1.5:
        tone, message = "caution", (
            f"Trong 1 tuần qua, {ticker} giảm {perf_txt}, MẠNH HƠN đáng kể so với trung vị ngành "
            f"{sector} ({sector_txt}). Mức giảm vượt trội này đáng được tìm hiểu thêm nguyên nhân "
            "riêng của doanh nghiệp, không nên quy hết cho thị trường chung."
        )
    else:
        tone, message = "reassure", (
            f"Trong 1 tuần qua, {ticker} giảm {perf_txt}, NHẸ HƠN trung vị ngành {sector} ({sector_txt}) "
            "— diễn biến giá tương đối ổn so với mặt bằng chung."
        )

    return {"tone": tone, "message": message}


# ─────────────────────────────────────────────────────────────────────────
# WOW FACTOR 2 — "Kịch bản chống chịu" (Stress Test)
# Tự động sinh thêm khi chọn B2 — ước tính số tháng cầm cự bằng đệm tiền mặt
# ròng nếu doanh thu giảm 50% và chi phí giữ nguyên (kịch bản thận trọng).
# Dùng 'Net Cash' (giá trị tuyệt đối), 'Revenue_TTM', 'Net_Income_TTM' — đều
# đã xác nhận có trong snapshot cuối của quant_engine.py.
# ⚠️ Đây là mô hình ĐƠN GIẢN HÓA mang tính minh họa (giả định chi phí cố
# định, không tính khả năng cắt giảm chi phí/tái cấp vốn), không thay thế mô
# hình dòng tiền chi tiết — cần ghi rõ caveat này trên UI.
# ─────────────────────────────────────────────────────────────────────────
def _stress_test(row):
    net_cash = row.get("Net Cash")
    revenue_ttm = row.get("Revenue_TTM")
    net_income_ttm = row.get("Net_Income_TTM")
    gross_margin = row.get("Gross Margin (%)")

    if _is_nan(net_cash) or _is_nan(revenue_ttm) or _is_nan(net_income_ttm) or revenue_ttm <= 0:
        return None

    if net_cash <= 0:
        return {
            "applicable": False, "still_profitable": False, "runway_months": None,
            "message": (
                "Doanh nghiệp hiện không có đệm tiền mặt ròng (nợ vay ròng > tiền mặt), nên bài kiểm "
                "tra 'chống chịu bằng tiền mặt' không áp dụng được — rủi ro ở đây phụ thuộc nhiều hơn "
                "vào khả năng tái cấp vốn/đảo nợ hơn là tiền mặt sẵn có."
            ),
        }

    # Giả định: chi phí vốn hàng bán (COGS) co giãn theo doanh thu (tỷ lệ
    # thuận với Gross Margin), còn chi phí dưới lợi nhuận gộp (SG&A, lãi
    # vay...) giữ nguyên — hợp lý hơn nhiều so với giả định "mất 100% doanh
    # thu là lỗ ròng", vốn cho ra số tháng cầm cự phi thực tế ở các ngành
    # biên lợi nhuận mỏng (thép, bán lẻ...). Nếu thiếu Gross Margin, fallback
    # thận trọng nhất về margin=0% (coi như mất trắng phần doanh thu hụt).
    margin = gross_margin if not _is_nan(gross_margin) else 0.0
    margin = max(0.0, min(100.0, margin)) / 100.0

    lost_gross_profit_annual = (revenue_ttm / 2) * margin
    stressed_annual_income = net_income_ttm - lost_gross_profit_annual

    if stressed_annual_income >= 0:
        return {
            "applicable": True, "still_profitable": True, "runway_months": None,
            "message": (
                "Ngay cả trong kịch bản doanh thu giảm 50% (giả định chi phí vốn hàng bán co giãn theo "
                "doanh thu, chi phí khác giữ nguyên), doanh nghiệp ước tính vẫn có lãi — gần như không "
                "cần dùng tới đệm tiền mặt dự trữ."
            ),
        }

    monthly_burn = abs(stressed_annual_income) / 12
    runway_months = round(net_cash / monthly_burn, 1)
    return {
        "applicable": True, "still_profitable": False, "runway_months": runway_months,
        "message": (
            f"Với vị thế tiền mặt ròng hiện tại, nếu doanh thu giảm 50% (giả định chi phí vốn hàng bán "
            f"co giãn theo doanh thu, chi phí khác giữ nguyên — kịch bản thận trọng), doanh nghiệp ước "
            f"tính cầm cự được khoảng {runway_months} tháng trước khi cạn đệm tiền mặt dự trữ."
        ),
    }


_ANALYZERS = {
    "A1": _analyze_a1, "A2": _analyze_a2, "A3": _analyze_a3, "A4": _analyze_a4,
    "B1": _analyze_b1, "B2": _analyze_b2,
    "C1": _analyze_c1, "C2": _analyze_c2,
    "D1": _analyze_d1,
    "E1": _analyze_e1, "E2": _analyze_e2,
    "F1": _analyze_f1, "F2": _analyze_f2,
}

_NEEDS_SECTOR_DF = {"A4", "B1", "D1", "F1"}
_NEEDS_TICKER = {"A3"}
_NEEDS_THRESHOLDS = {"C1", "C2"}

# ─────────────────────────────────────────────────────────────────────────
# Hàm cốt lõi (Entry Point) được gọi từ callbacks
# ─────────────────────────────────────────────────────────────────────────
def analyze_fear(ticker: str, selected_fears: list, profile_data=None) -> dict:
    """
    Phân tích các nỗi sợ được chọn cho 1 mã cổ phiếu, kết hợp hồ sơ rủi ro.
    """
    ticker = (ticker or "").strip().upper()
    if not ticker:
        return {"status": "no_ticker", "ticker": "", "results": []}
    if not selected_fears:
        return {"status": "empty_fear", "ticker": ticker, "results": []}

    try:
        row, df_all = _get_ticker_row(ticker)
    except Exception as e:
        logger.error(f"[psychology_engine] Lỗi đọc snapshot cho {ticker}: {e}")
        return {"status": "error", "ticker": ticker, "results": [], "error": str(e)}

    if row is None:
        return {"status": "not_found", "ticker": ticker, "results": []}

    # Sinh ngưỡng động từ thông tin khẩu vị rủi ro
    custom_thresholds = _get_dynamic_thresholds(profile_data) 
    
    company = row.get("Company Common Name") or ticker
    results = []

    for fear_code in selected_fears:
        analyzer = _ANALYZERS.get(fear_code)
        if not analyzer:
            continue
            
        try:
            if fear_code in _NEEDS_SECTOR_DF:
                item = analyzer(row, df_all)
            elif fear_code in _NEEDS_TICKER:
                item = analyzer(row, ticker)
            elif fear_code in _NEEDS_THRESHOLDS:
                item = analyzer(row, custom_thresholds)
            else:
                item = analyzer(row)
        except Exception as e:
            logger.error(f"[psychology_engine] Lỗi phân tích {fear_code} cho {ticker}: {e}")
            item = {
                "fear": fear_code, "title": FEAR_LABELS.get(fear_code, fear_code),
                "verdict": "neutral", "metrics": [],
                "conclusion": "Có lỗi khi tính toán chỉ số này, vui lòng thử lại.",
            }
            
        results.append(item)

    # ── Wow factors: tự động sinh thêm context, không cần tick riêng ──────
    peer_context = _peer_context(row, df_all) if ("C1" in selected_fears or "C2" in selected_fears) else None
    stress_test = _stress_test(row) if "B2" in selected_fears else None

    return {
        "status": "ok", "ticker": ticker, "company": company, "results": results,
        "peer_context": peer_context, "stress_test": stress_test,
    }