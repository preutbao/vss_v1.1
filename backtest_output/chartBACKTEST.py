# -*- coding: utf-8 -*-
"""
ve_chart_backtest.py (v2)
==========================
Vẽ 2 biểu đồ minh họa kết quả Backtest cho báo cáo/đồ án:
  Hình 1 — Equity Curve: VGM, Cổ tức, Value so với VN-Index (dữ liệu
           VN-Index THẬT, lấy trực tiếp từ vnindex_raw.csv).
  Hình 2 — Biểu đồ phân tán Rủi ro – Lợi nhuận cho toàn bộ 12 cấu hình
           chiến lược.

Input cần có trong CÙNG THƯ MỤC khi chạy:
    - vnindex_raw.csv, equity_VGM.csv, equity_STRAT_DIVIDEND.csv,
      equity_STRAT_VALUE.csv, summary_all_strategies.csv

Cách chạy:  python ve_chart_backtest.py
Output:     Hinh_1_...png , Hinh_2_...png
"""
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.colors as mcolors
from pathlib import Path

# ═══════════════════════════════════════════════════════════════════════
# 0. CẤU HÌNH FONT — Times New Roman (fallback Liberation Serif)
# ═══════════════════════════════════════════════════════════════════════
plt.rcParams["font.family"] = "serif"
plt.rcParams["font.serif"] = ["Times New Roman", "Liberation Serif", "DejaVu Serif"]
plt.rcParams["mathtext.fontset"] = "stix"
plt.rcParams["axes.unicode_minus"] = False
plt.rcParams["font.size"] = 11

INITIAL_CAPITAL = 1_000_000_000.0
FIRST_TRADE_DATE = pd.Timestamp("2023-05-16")  # theo summary_all_strategies.csv

HERE = Path(__file__).parent
IN_VNINDEX  = HERE / "vnindex_raw.csv"
IN_VGM      = HERE / "equity_VGM.csv"
IN_DIVIDEND = HERE / "equity_STRAT_DIVIDEND.csv"
IN_VALUE    = HERE / "equity_STRAT_VALUE.csv"
IN_SUMMARY  = HERE / "summary_all_strategies.csv"


def caption(fig, text, y=-0.03):
    fig.text(0.5, y, text, ha="center", va="top", fontsize=10.5, wrap=True)


def load_norm(path):
    """Đọc equity_*.csv, cắt từ FIRST_TRADE_DATE, chuẩn hoá về 1.0 tại điểm đầu."""
    s = pd.read_csv(path, parse_dates=["Date"]).set_index("Date")["Total Value"]
    s = s[s.index >= FIRST_TRADE_DATE]
    return s / s.iloc[0]


def cagr_of(s):
    years = (s.index[-1] - s.index[0]).days / 365.25
    return ((s.iloc[-1] / s.iloc[0]) ** (1 / years) - 1) * 100


def mdd_of(s):
    roll_max = s.cummax()
    return (s / roll_max - 1).min() * 100


# ═══════════════════════════════════════════════════════════════════════
# HÌNH 1 — EQUITY CURVE: VGM, CỔ TỨC, VALUE vs VN-INDEX
# ═══════════════════════════════════════════════════════════════════════
def ve_hinh_1():
    vgm_norm = load_norm(IN_VGM)
    div_norm = load_norm(IN_DIVIDEND)
    val_norm = load_norm(IN_VALUE)

    vni = pd.read_csv(IN_VNINDEX, parse_dates=["Date"]).set_index("Date")["VNINDEX_Close"]
    vni_aligned = vni.loc[vni.index >= FIRST_TRADE_DATE]
    vni_norm = vni_aligned / vni_aligned.loc[FIRST_TRADE_DATE]

    roll_max = vgm_norm.cummax()
    dd = vgm_norm / roll_max - 1
    trough_date = dd.idxmin()
    peak_date = vgm_norm[:trough_date].idxmax()

    cagr_vgm, mdd_vgm = cagr_of(vgm_norm), mdd_of(vgm_norm)
    cagr_vni, mdd_vni = cagr_of(vni_norm), mdd_of(vni_norm)
    cagr_div, mdd_div = cagr_of(div_norm), mdd_of(div_norm)
    cagr_val, mdd_val = cagr_of(val_norm), mdd_of(val_norm)

    # [THAY ĐỔI] Mở rộng chiều cao chart 1 một chút để thấy rõ biến động hơn
    fig, ax = plt.subplots(figsize=(9.5, 6.2), dpi=300)

    # [THAY ĐỔI] VN-Index: giữ nguyên đường đứt nét như bản cũ
    ax.plot(vni_norm.index, vni_norm.values, color="#8C1D18", linewidth=1.5,
            linestyle="--", label="VN-Index (Benchmark)", zorder=2)

    # [THAY ĐỔI] Value: đứt nét, mờ, mỏng, cam — nhóm chiến lược kém hiệu quả
    ax.plot(val_norm.index, val_norm.values, color="#E67E22", linewidth=1.1,
            linestyle="--", alpha=0.55, label="Value Investing", zorder=1)

    # [THAY ĐỔI] Cổ tức: nét liền, mỏng, xanh lá — Risk-Adjusted Leader, ít drawdown
    ax.plot(div_norm.index, div_norm.values, color="#1E8449", linewidth=1.4,
            linestyle="-", label="Cổ tức (Risk-Adjusted)", zorder=3)

    # [THAY ĐỔI] VGM: nét liền, đậm, xanh dương NHẠT hơn bản cũ — Return Leader
    ax.plot(vgm_norm.index, vgm_norm.values, color="#3E7CB8", linewidth=2.2,
            linestyle="-", label="VGM (FSS Score - Return Leader)", zorder=4)

    ax.axvspan(peak_date, trough_date, color="#8C1D18", alpha=0.06, zorder=0)

    # [THÊM] Tiêu đề chart — in hoa, in đậm, Times New Roman, sát khu vực vẽ
    ax.set_title("ĐƯỜNG TĂNG TRƯỞNG VỐN CÁC CHIẾN LƯỢC SO VỚI VN-INDEX",
                 fontsize=13, fontweight="bold", pad=10)

    ax.set_ylabel("Tăng trưởng vốn (lần), chuẩn hoá = 1 tại 16/05/2023")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m/%Y"))
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=6))
    ax.grid(True, alpha=0.3, linewidth=0.6)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    # [THAY ĐỔI] Đổi chỗ: legend xuống góc dưới-phải (trước đây ở trên-trái)
    # 1. Cấu hình Legend và tìm đúng chữ VN-Index để in đậm
    leg = ax.legend(loc="lower right", frameon=False, fontsize=10)
    for text in leg.get_texts():
        if "VN-Index" in text.get_text():
            text.set_fontweight("bold")

    # 2. Đọc nhanh Sharpe Ratio từ file summary để không phải gõ tay
    df_summ = pd.read_csv(IN_SUMMARY)
    df_summ.columns = [c.strip() for c in df_summ.columns]
    sr_div = df_summ.loc[df_summ["Strategy"] == "STRAT_DIVIDEND", "Sharpe Ratio"].values[0]
    sr_val = df_summ.loc[df_summ["Strategy"] == "STRAT_VALUE", "Sharpe Ratio"].values[0]

    # 3. Cấu hình bảng số liệu mở rộng (căn lề thẳng cột cho 4 thành phần)
    table_text = (
        f"{'Chỉ tiêu':<16}{'VGM':>9}{'Cổ tức':>10}{'Value':>10}{'VN-Index':>11}\n"
        f"{'-'*56}\n"
        f"{'CAGR (%)':<16}{cagr_vgm:>9.2f}{cagr_div:>10.2f}{cagr_val:>10.2f}{cagr_vni:>11.2f}\n"
        f"{'Max Drawdown (%)':<16}{mdd_vgm:>9.2f}{mdd_div:>10.2f}{mdd_val:>10.2f}{mdd_vni:>11.2f}\n"
        f"{'Sharpe Ratio':<16}{'0.98':>9}{sr_div:>10.2f}{sr_val:>10.2f}{'0.73':>11}"
    )
    ax.text(0.02, 0.97, table_text, transform=ax.transAxes, ha="left", va="top",
            fontsize=9, family=["Consolas", "Courier New", "monospace"],
            bbox=dict(boxstyle="square,pad=0.5", fc="white", ec="black", lw=0.8))

    fig.tight_layout(rect=[0, 0.09, 1, 1])
    caption(fig,
        "Hình 1. Đường tăng trưởng vốn (equity curve) của 3 chiến lược tiêu biểu — VGM (Return\n"
        "Leader), Cổ tức (Risk-Adjusted Leader), Value Investing — so với chỉ số VN-Index, giai đoạn\n"
        "16/05/2023 – 27/08/2026 (Backtest Point-in-Time). Nguồn: kết quả thực nghiệm của nhóm\n"
        "nghiên cứu; dữ liệu VN-Index trích xuất trực tiếp từ hệ thống, không ước tính. Vùng tô đỏ thể\n"
        "hiện giai đoạn sụt giảm sâu nhất (drawdown) của VGM. Kết quả quá khứ không đảm bảo hiệu quả\n"
        "tương lai.",
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

    is_bench_row = df["Strategy"].str.contains("VN-Index", na=False)
    bench_row = df[is_bench_row].iloc[0]
    df = df[~is_bench_row].copy()

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
    size = 60 + (n_trades / n_trades.max()) * 340

    fig, ax = plt.subplots(figsize=(9.5, 6.3), dpi=300)

    bench_cagr = float(bench_row["Benchmark CAGR (%)"]) if "Benchmark CAGR (%)" in bench_row else 17.93
    bench_mdd = -18.11

    ax.axvline(bench_cagr, color="#555555", linestyle=":", linewidth=0.8, alpha=0.5, zorder=0)
    ax.axhline(bench_mdd, color="#555555", linestyle=":", linewidth=0.8, alpha=0.5, zorder=0)

    ax.scatter(bench_cagr, bench_mdd, marker="*", s=200, color="gold",
               edgecolors="black", linewidths=0.8, zorder=4)
    # [THAY ĐỔI] Nhãn VN-Index đưa lên NGANG HÀNG với ngôi sao (va="center"),
    # đặt bên trái để không đè lên đường tham chiếu/điểm dữ liệu khác
    ax.text(bench_cagr - 0.7, bench_mdd, "VN-Index", fontsize=9, fontweight="bold",
            ha="right", va="center")

    # [THAY ĐỔI] Dịch chú thích sang tiếng Việt
    ax.text(bench_cagr + 0.5, bench_mdd + 0.5, "↑ Rủi ro thấp hơn   →  Lợi nhuận cao hơn",
            fontsize=8.5, color="#555555", style="italic", ha="left", va="bottom")

    norm = mcolors.TwoSlopeNorm(vcenter=0, vmin=sharpe.min(), vmax=sharpe.max())
    sc = ax.scatter(x, y, s=size, c=sharpe, cmap="RdYlGn", norm=norm,
                    edgecolors="black", linewidths=0.7, zorder=3)

    offsets = {
        "VGM": (10, -5),
        "Value": (10, -12),
        "Turnaround": (6, 12),
        "Quality": (-20, 12),
        "GARP": (10, -12),
        "Dividend": (10, 2),
        "Piotroski": (10, -12),
        "CANSLIM*\n(start 15/08/2023)": (10, -5),
        "Growth": (-35, -15),
        "Magic Formula": (-20, 9),
        "NCN": (10, -15),
        # [THAY ĐỔI] Dời nhãn ADX Momentum xuống thấp hơn theo chiều dọc
        "ADX Momentum": (12, -12),
    }
    for _, row in df.iterrows():
        dx, dy = offsets.get(row["Nhan"], (6, 6))
        ax.annotate(row["Nhan"], (row["CAGR (%)"], row["Max Drawdown (%)"]),
                    textcoords="offset points", xytext=(dx, dy), fontsize=9)

    # [THÊM] Tiêu đề chart — in hoa, in đậm, Times New Roman, sát khu vực vẽ
    ax.set_title("PHÂN BỔ RỦI RO – LỢI NHUẬN CÁC CHIẾN LƯỢC ĐỊNH LƯỢNG",
                 fontsize=13, fontweight="bold", pad=10)

    ax.set_xlabel("CAGR — Tỷ suất sinh lời kép hàng năm (%)")
    ax.set_ylabel("Max Drawdown — Mức sụt giảm tối đa (%)")
    ax.grid(True, alpha=0.3, linewidth=0.6)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    cbar = fig.colorbar(sc, ax=ax, pad=0.02)
    cbar.set_label("Sharpe Ratio", fontsize=10)

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