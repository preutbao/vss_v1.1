# -*- coding: utf-8 -*-
"""
ve_chart_backtest.py
=====================
Vẽ 2 biểu đồ minh họa kết quả Backtest cho báo cáo/đồ án:

  Hình 1 — Equity Curve: FSS VGM Score vs VN-Index (dữ liệu VN-Index THẬT,
           lấy trực tiếp từ vnindex_raw.csv, KHÔNG ước tính bằng CAGR).
  Hình 2 — Biểu đồ phân tán Rủi ro – Lợi nhuận cho toàn bộ 12 cấu hình
           chiến lược (CAGR vs Max Drawdown, màu = Sharpe Ratio,
           kích thước điểm = số vị thế đã đóng).

Định dạng: font Times New Roman (fallback Liberation Serif nếu máy không
có Times New Roman — 2 font này tương thích metric, nhìn gần như giống hệt
nhau), nền trắng, chú thích "Hình X." theo đúng chuẩn trình bày đồ án/tiểu
luận đại học Việt Nam.

Input cần có trong CÙNG THƯ MỤC khi chạy:
    - vnindex_raw.csv
    - equity_VGM.csv
    - summary_all_strategies.csv

Cách chạy:
    python ve_chart_backtest.py

Output:
    - Hinh_1_Equity_Curve_VGM_vs_VNIndex.png
    - Hinh_2_Rui_ro_Loi_nhuan_12_chien_luoc.png
"""
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.font_manager as fm
from matplotlib.patches import FancyBboxPatch
import matplotlib.colors as mcolors
from pathlib import Path

# ═══════════════════════════════════════════════════════════════════════
# 0. CẤU HÌNH FONT — Times New Roman (fallback Liberation Serif)
# ═══════════════════════════════════════════════════════════════════════
# Trên Windows đã cài Times New Roman: matplotlib sẽ tự dùng đúng font đó.
# Trên Linux/Mac không có Times New Roman: tự động rơi xuống Liberation
# Serif (tương thích metric 1-1 với Times New Roman, dùng phổ biến để thay
# thế trên các bản LaTeX/Office không có font gốc của Microsoft).
plt.rcParams["font.family"] = "serif"
plt.rcParams["font.serif"] = ["Times New Roman", "Liberation Serif", "DejaVu Serif"]
plt.rcParams["mathtext.fontset"] = "stix"   # số/công thức cũng theo serif
plt.rcParams["axes.unicode_minus"] = False
plt.rcParams["font.size"] = 11

INITIAL_CAPITAL = 1_000_000_000.0

HERE = Path(__file__).parent
IN_VNINDEX = HERE / "vnindex_raw.csv"
IN_VGM     = HERE / "equity_VGM.csv"
IN_SUMMARY = HERE / "summary_all_strategies.csv"


def caption(fig, text, y=-0.03):
    """Chèn chú thích 'Hình X. ...' bên dưới biểu đồ, đúng chuẩn báo cáo VN."""
    fig.text(0.5, y, text, ha="center", va="top", fontsize=10.5, wrap=True)


# ═══════════════════════════════════════════════════════════════════════
# HÌNH 1 — EQUITY CURVE: FSS VGM SCORE vs VN-INDEX (DỮ LIỆU THẬT)
# ═══════════════════════════════════════════════════════════════════════
def ve_hinh_1():
    vgm = pd.read_csv(IN_VGM, parse_dates=["Date"]).set_index("Date")["Total Value"]
    vni = pd.read_csv(IN_VNINDEX, parse_dates=["Date"]).set_index("Date")["VNINDEX_Close"]

    FIRST_TRADE_DATE = pd.Timestamp("2023-05-16")  # theo summary_all_strategies.csv
    vgm = vgm[vgm.index >= FIRST_TRADE_DATE]

    # Chuẩn hoá VN-Index THẬT về đúng công thức trong backtest.py:
    #   bench_aligned = s.loc[first_exec_day:] / s.loc[first_exec_day] * initial_capital
    vni_aligned = vni.loc[vni.index >= FIRST_TRADE_DATE]
    vni_aligned = vni_aligned / vni_aligned.loc[FIRST_TRADE_DATE] * INITIAL_CAPITAL

    # Quy về hệ "tăng trưởng 1 đồng vốn" cho trực quan
    vgm_norm = vgm / vgm.iloc[0]
    vni_norm = vni_aligned / vni_aligned.iloc[0]

    # Max Drawdown thật của VGM (để khoanh vùng minh hoạ)
    roll_max = vgm_norm.cummax()
    dd = vgm_norm / roll_max - 1
    trough_date = dd.idxmin()
    peak_date = vgm_norm[:trough_date].idxmax()
    mdd_vgm = dd.min() * 100

    roll_max_b = vni_norm.cummax()
    mdd_vni = (vni_norm / roll_max_b - 1).min() * 100

    def cagr(s):
        years = (s.index[-1] - s.index[0]).days / 365.25
        return ((s.iloc[-1] / s.iloc[0]) ** (1 / years) - 1) * 100

    cagr_vgm, cagr_vni = cagr(vgm_norm), cagr(vni_norm)

    fig, ax = plt.subplots(figsize=(9.5, 5.6), dpi=300)

    ax.plot(vgm_norm.index, vgm_norm.values, color="#1B2A4A", linewidth=1.9,
            label="FSS VGM Score")
    ax.plot(vni_norm.index, vni_norm.values, color="#8C1D18", linewidth=1.5,
            linestyle="--", label="VN-Index (Benchmark)")

    ax.axvspan(peak_date, trough_date, color="#8C1D18", alpha=0.07, zorder=0)

    ax.set_ylabel("Tăng trưởng vốn (lần), chuẩn hoá = 1 tại 16/05/2023")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m/%Y"))
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=6))
    ax.grid(True, alpha=0.3, linewidth=0.6)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.legend(loc="upper left", frameon=False, fontsize=10.5)

    # Bảng số liệu nhỏ trong góc biểu đồ (không dùng box màu mè, giữ tối giản
    # học thuật: khung viền đen mảnh, chữ đen, không tô nền màu)
    table_text = (
        f"{'Chỉ tiêu':<16}{'FSS VGM':>12}{'VN-Index':>12}\n"
        f"{'-'*40}\n"
        f"{'CAGR (%)':<16}{cagr_vgm:>12.2f}{cagr_vni:>12.2f}\n"
        f"{'Max Drawdown (%)':<16}{mdd_vgm:>12.2f}{mdd_vni:>12.2f}\n"
        f"{'Sharpe Ratio':<16}{'0.98':>12}{'0.73':>12}"
    )
    ax.text(0.985, 0.03, table_text, transform=ax.transAxes, ha="right", va="bottom",
            fontsize=9, family=["Consolas", "Courier New", "monospace"],
            bbox=dict(boxstyle="square,pad=0.5", fc="white", ec="black", lw=0.8))

    fig.tight_layout(rect=[0, 0.09, 1, 1])
    caption(fig,
        "Hình 1. Đường tăng trưởng vốn (equity curve) của chiến lược FSS VGM Score\n"
        "so với chỉ số VN-Index, giai đoạn 16/05/2023 – 27/08/2026 (Backtest Point-in-Time).\n"
        "Nguồn: Kết quả thực nghiệm của nhóm nghiên cứu; dữ liệu VN-Index trích xuất trực tiếp "
        "từ hệ thống, không ước tính. Vùng tô đỏ thể hiện giai đoạn sụt giảm sâu nhất (drawdown) "
        "của chiến lược VGM. Kết quả quá khứ không đảm bảo hiệu quả tương lai.",
        y=-0.02)

    out = HERE / "Hinh_1_Equity_Curve_VGM_vs_VNIndex.png"
    fig.savefig(out, dpi=300, bbox_inches="tight", facecolor="white")
    print(f"✅ Đã lưu {out}")
    plt.close(fig)


# ═══════════════════════════════════════════════════════════════════════
# HÌNH 2 — BIỂU ĐỒ PHÂN TÁN RỦI RO – LỢI NHUẬN (12 CHIẾN LƯỢC)
# ═══════════════════════════════════════════════════════════════════════
def ve_hinh_2():
    df = pd.read_csv(IN_SUMMARY)
    df.columns = [c.strip() for c in df.columns]

    # Tách riêng dòng benchmark toàn kỳ (chỉ dùng để tham chiếu, không vẽ
    # như 1 "chiến lược" — đúng ghi chú trong file gốc)
    is_bench_row = df["Strategy"].str.contains("VN-Index", na=False)
    bench_row = df[is_bench_row].iloc[0]
    df = df[~is_bench_row].copy()

    # Nhãn hiển thị gọn hơn tên biến kỹ thuật
    ten_hien_thi = {
        "VGM": "VGM", "STRAT_VALUE": "Value", "STRAT_TURNAROUND": "Turnaround",
        "STRAT_QUALITY": "Quality", "STRAT_GARP": "GARP", "STRAT_DIVIDEND": "Dividend",
        "STRAT_PIOTROSKI": "Piotroski", "STRAT_CANSLIM": "CANSLIM*\n(start 15/08/2023)",
        "STRAT_GROWTH": "Growth", "STRAT_MAGIC": "Magic Formula",
        "STRAT_NCN": "NCN", "STRAT_ADX_MOMENTUM": "ADX Momentum",
    }
    df["Nhan"] = df["Strategy"].map(ten_hien_thi).fillna(df["Strategy"])

    x = df["CAGR (%)"].astype(float)
    y = df["Max Drawdown (%)"].astype(float)
    sharpe = df["Sharpe Ratio"].astype(float)
    n_trades = df["N Closed Positions"].astype(float)

    # Kích thước điểm theo số vị thế đã đóng (đại diện độ "chắc chắn" thống
    # kê — càng nhiều giao dịch, kết quả càng ít phụ thuộc may rủi)
    size = 60 + (n_trades / n_trades.max()) * 340

    fig, ax = plt.subplots(figsize=(9.5, 6.3), dpi=300)

    # Đường tham chiếu benchmark (đa số chiến lược canh cùng 1 cửa sổ
    # 16/05/2023, riêng CANSLIM canh cửa sổ khác — đánh dấu * và ghi chú)
    bench_cagr = float(bench_row["Benchmark CAGR (%)"]) if "Benchmark CAGR (%)" in bench_row else 17.93
    bench_mdd = -18.11
    
    # Trục tham chiếu nhạt hơn để không lấn át dữ liệu
    ax.axvline(bench_cagr, color="#555555", linestyle=":", linewidth=0.8, alpha=0.5, zorder=0)
    ax.axhline(bench_mdd, color="#555555", linestyle=":", linewidth=0.8, alpha=0.5, zorder=0)
    
    # Điểm đánh dấu VN-Index
    # Điểm đánh dấu VN-Index
    ax.scatter(bench_cagr, bench_mdd, marker="*", s=200, color="gold", edgecolors="black", linewidths=0.8, zorder=4)
    ax.text(bench_cagr - 0.5, bench_mdd - 0.5, "VN-Index", fontsize=9, fontweight="bold", ha="right", va="top")
    
    # Text điều hướng quadrant
    ax.text(bench_cagr + 0.5, bench_mdd + 0.5, "↑ Lower drawdown / → Higher CAGR", 
            fontsize=8.5, color="#555555", style="italic", ha="left", va="bottom")

    norm = mcolors.TwoSlopeNorm(vcenter=0, vmin=sharpe.min(), vmax=sharpe.max())
    
    sc = ax.scatter(x, y, s=size, c=sharpe, cmap="RdYlGn", norm=norm,
                    edgecolors="black", linewidths=0.7, zorder=3)

    # Gán nhãn từng điểm, tránh đè lên nhau bằng offset thủ công cho vài mã
    # Gán nhãn từng điểm, tinh chỉnh tọa độ offset (dx, dy) để chống lặp
    offsets = {
        "VGM": (10, -5), 
        "Value": (10, -12), 
        "Turnaround": (6, 12),
        "Quality": (-20, 12),
        "GARP": (10, -12), 
        "Dividend": (10, 2), 
        "Piotroski": (10, -12), 
        "CANSLIM*\n(start 15/08/2023)": (10, -5), # Cập nhật đúng key mới
        "Growth": (-35, -15),
        "Magic Formula": (-20, 15),
        "NCN": (10, -15),
        "ADX Momentum": (12, -2),
    }
    for _, row in df.iterrows():
        dx, dy = offsets.get(row["Nhan"], (6, 6))
        ax.annotate(row["Nhan"], (row["CAGR (%)"], row["Max Drawdown (%)"]),
                    textcoords="offset points", xytext=(dx, dy), fontsize=9)

    ax.set_xlabel("CAGR — Tỷ suất sinh lời kép hàng năm (%)")
    ax.set_ylabel("Max Drawdown — Mức sụt giảm tối đa (%)")
    ax.grid(True, alpha=0.3, linewidth=0.6)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    cbar = fig.colorbar(sc, ax=ax, pad=0.02)
    cbar.set_label("Sharpe Ratio", fontsize=10)

    # Chú giải kích thước điểm (legend thủ công cho size)
    for n_val, label in [(20, "20 lệnh"), (150, "150 lệnh")]:
        s_val = 60 + (n_val / n_trades.max()) * 340
        ax.scatter([], [], s=s_val, c="white", edgecolors="black", linewidths=0.7,
                   label=f"Số vị thế đã đóng ≈ {label}")
    ax.legend(loc="lower right", frameon=True, fontsize=8.5, title="Kích thước điểm",
              title_fontsize=9)

    fig.tight_layout(rect=[0, 0.10, 1, 1])
    caption(fig,
        "Hình 2. Phân bố Rủi ro – Lợi nhuận của 12 cấu hình chiến lược định lượng trên FSS\n"
        "(Backtest Point-in-Time, 16/05/2023 – 27/08/2026). Trục hoành: CAGR; trục tung: Max Drawdown;\n"
        "màu điểm: Sharpe Ratio; kích thước điểm: số vị thế đã đóng. (*) STRAT_CANSLIM canh theo cửa sổ\n"
        "thời gian khác (từ 15/08/2023) nên đường tham chiếu VN-Index không áp dụng trực tiếp cho mã này.\n"
        "Kết quả quá khứ không đảm bảo hiệu quả tương lai.",
        y=-0.03)

    out = HERE / "Hinh_2_Rui_ro_Loi_nhuan_12_chien_luoc.png"
    fig.savefig(out, dpi=300, bbox_inches="tight", facecolor="white")
    print(f"✅ Đã lưu {out}")
    plt.close(fig)


if __name__ == "__main__":
    ve_hinh_1()
    ve_hinh_2()
    print("\nHoàn tất. Có thể chèn thẳng 2 file PNG vào báo cáo Word/PDF.")