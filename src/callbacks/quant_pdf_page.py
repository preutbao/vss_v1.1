# src/callbacks/quant_pdf_page.py
# ============================================================
# VSS PREDICTIVE 2.0 – Stage 4: PDF Quant Page
# ============================================================
# File STANDALONE – tự chứa toàn bộ helpers cần thiết.
# Không phụ thuộc ngược lại screener_pdf_callback.py để
# tránh circular import.
#
# Cách dùng (trong screener_pdf_callback.py):
#   from src.callbacks.quant_pdf_page import _render_quant_page
#
# Font "VnFont" / "VnFont-Bold" được đăng ký bởi
# screener_pdf_callback.py khi import – file này chỉ dùng lại.
# ============================================================

import io, os, math, logging
from datetime import datetime
from typing import Optional

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics

logger = logging.getLogger(__name__)

# ── QuantResult import (fallback nếu portfolio_optimizer chưa có) ──
try:
    from src.backend.portfolio_optimizer import QuantResult
except ImportError:
    from dataclasses import dataclass, field
    @dataclass
    class QuantResult:           # type: ignore
        status: str = "error"
        tickers: list = field(default_factory=list)
        weights: list = field(default_factory=list)
        quantities: list = field(default_factory=list)
        investment_values: list = field(default_factory=list)
        prices: list = field(default_factory=list)
        companies: list = field(default_factory=list)
        exchanges: list = field(default_factory=list)
        expected_return: float = 0.0
        expected_return_1m: float = 0.0
        var_95: float = 0.0
        max_drawdown: float = 0.0
        sharpe_ratio: float = 0.0
        portfolio_vol: float = 0.0
        mc_returns: Optional[np.ndarray] = None
        seasonality_scores: dict = field(default_factory=dict)
        nav: float = 1_000_000_000.0
        guillotine_iterations: int = 0
        error_message: str = ""


# ══════════════════════════════════════════════════════════════
# CONSTANTS
# ══════════════════════════════════════════════════════════════
PW, PH   = A4           # 595.28 × 841.89 pt
MARGIN   = 28
CW       = PW - 2 * MARGIN
FOOTER_H = 22
Y_MIN    = FOOTER_H + 16
N_SCENARIOS = 10_000

# ── Color palette (đồng bộ với screener_pdf_callback) ─────────
C_BG         = colors.white
C_HEADER     = colors.HexColor("#0a1628")
C_TEXT       = colors.HexColor("#1a2f4a")
C_GREY       = colors.HexColor("#5a7a99")
C_LIGHT_GREY = colors.HexColor("#dce8f0")
C_RED        = colors.HexColor("#D32F2F")
C_GREEN      = colors.HexColor("#00875a")
C_BLUE       = colors.HexColor("#0057b8")
C_ACCENT     = colors.HexColor("#0090ff")
C_AMBER      = colors.HexColor("#f59e0b")
C_PURPLE     = colors.HexColor("#7c3aed")
C_DARK_GREEN = colors.HexColor("#065f46")

# ── Dark theme riêng cho trang Quant ──────────────────────────
C_Q_DARK   = colors.HexColor("#0d1b2a")
C_Q_DARKER = colors.HexColor("#091526")
C_Q_BORDER = colors.HexColor("#1e3a5f")
C_Q_GOLD   = colors.HexColor("#f57f17")
C_Q_TEXT   = colors.HexColor("#d6eaf8")
C_Q_MUTED  = colors.HexColor("#7fa8cc")

VGM_COLOR = {
    "A": colors.HexColor("#00875a"),
    "B": colors.HexColor("#0057b8"),
    "C": colors.HexColor("#f59e0b"),
    "D": colors.HexColor("#ff7043"),
    "F": colors.HexColor("#D32F2F"),
}


# ══════════════════════════════════════════════════════════════
# HELPER UTILITIES
# (bản sao nhỏ gọn, không đụng đến screener_pdf_callback)
# ══════════════════════════════════════════════════════════════

def _sv(v, mode="dec1", suffix="") -> str:
    try:
        if v is None or (isinstance(v, float) and math.isnan(v)):
            return "—"
        if mode == "dec1":  return f"{float(v):.1f}{suffix}"
        if mode == "dec2":  return f"{float(v):.2f}{suffix}"
        if mode == "pct":   return f"{float(v):+.1f}{suffix}"
        if mode == "int":   return str(int(float(v)))
        return str(v)
    except Exception:
        return "—"


def _img(fig, dpi: int = 130) -> ImageReader:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi,
                bbox_inches="tight", facecolor=fig.get_facecolor())
    buf.seek(0)
    return ImageReader(buf)


def _embed(c, fig, x: float, y: float, w: float, h: float):
    c.drawImage(_img(fig), x, y, width=w, height=h,
                preserveAspectRatio=True, anchor="nw")
    plt.close(fig)


def _format_ax(ax, dark: bool = False):
    if dark:
        ax.set_facecolor("#0d1b2a")
        for sp in ax.spines.values():
            sp.set_color("#2a3f55")
        ax.tick_params(colors="#90aac0", labelsize=6.5)
        ax.grid(True, axis="y", color="#1a2f45", linewidth=0.5)
    else:
        ax.set_facecolor("#f8fbff")
        for sp in ["top", "right"]:   ax.spines[sp].set_visible(False)
        for sp in ["left", "bottom"]: ax.spines[sp].set_color("#b8d4f0")
        ax.tick_params(labelsize=6.5, colors="#3a6080", length=0)
        ax.grid(True, axis="y", color="#e4f0fb", linewidth=0.7)
    ax.grid(False, axis="x")


def _bg(c):
    c.setFillColor(C_BG)
    c.rect(0, 0, PW, PH, fill=1, stroke=0)


def _footer(c, page_num: int):
    c.setFillColor(C_ACCENT)
    c.rect(0, 0, PW, 3, fill=1, stroke=0)
    c.setFont("VnFont", 6.5)
    c.setFillColor(C_GREY)
    c.drawString(MARGIN, 9,
        "Vietcap Smart Screener – Du lieu mang tinh tham khao, "
        "khong phai khuyen nghi dau tu.")
    c.drawRightString(PW - MARGIN, 9, f"Trang {page_num}")


def _page_header_quant(c, subtitle: str = ""):
    """Header tối màu đặc trưng cho trang Quant."""
    c.setFillColor(C_Q_DARK)
    c.rect(0, PH - 44, PW, 44, fill=1, stroke=0)
    # Gold accent top & left
    c.setFillColor(C_Q_GOLD)
    c.rect(0, PH - 4, PW, 4, fill=1, stroke=0)
    c.rect(0, PH - 44, 4, 44, fill=1, stroke=0)
    # Separator bottom
    c.setStrokeColor(C_Q_BORDER); c.setLineWidth(0.8)
    c.line(0, PH - 44, PW, PH - 44)

    c.setFont("VnFont-Bold", 10.5)
    c.setFillColor(colors.white)
    c.drawString(MARGIN, PH - 22,
        "VSS Predictive 2.0 – Phan bo Danh muc Toi uu")
    if subtitle:
        c.setFont("VnFont", 7.5)
        c.setFillColor(C_Q_MUTED)
        c.drawString(MARGIN, PH - 35, subtitle)
    c.setFont("VnFont", 7)
    c.setFillColor(C_Q_MUTED)
    c.drawRightString(PW - MARGIN, PH - 22,
                      datetime.now().strftime("%d/%m/%Y %H:%M"))


def _sec(c, text: str, x: float, y: float, width: float = None):
    width = width or CW
    c.setFont("VnFont-Bold", 8.5)
    c.setFillColor(C_Q_GOLD)
    c.drawString(x, y, text)
    c.setStrokeColor(C_Q_GOLD); c.setLineWidth(1.5)
    c.line(x, y - 5, x + 22, y - 5)
    c.setStrokeColor(C_Q_BORDER); c.setLineWidth(0.5)
    c.line(x + 22, y - 5, x + width, y - 5)


def _kpi_card(c, x: float, y: float, w: float, h: float,
              label: str, value: str, col=None, dark: bool = True):
    col = col or C_ACCENT
    if dark:
        c.setFillColor(C_Q_DARKER)
        c.setStrokeColor(C_Q_BORDER)
    else:
        c.setFillColor(colors.HexColor("#f5f9ff"))
        c.setStrokeColor(C_LIGHT_GREY)
    c.setLineWidth(0.6)
    c.roundRect(x, y, w, h, radius=4, fill=1, stroke=1)
    c.setFillColor(col)
    c.roundRect(x, y + h - 4, w, 4, radius=2, fill=1, stroke=0)
    c.setFont("VnFont", 6.5)
    c.setFillColor(C_Q_MUTED if dark else C_GREY)
    c.drawCentredString(x + w / 2, y + h - 15, label.upper()[:22])
    c.setFont("VnFont-Bold", 11)
    c.setFillColor(col)
    c.drawCentredString(x + w / 2, y + 7, str(value)[:12])


def _draw_vgm_badge(c, x: float, y: float, w: float, h: float, grade: str):
    grade  = str(grade).strip().upper()
    bg_col = VGM_COLOR.get(grade, C_GREY)
    r  = min(w, h) / 2 - 1
    cx = x + w / 2
    cy = y + h / 2
    c.setFillColor(bg_col)
    c.circle(cx, cy, r, fill=1, stroke=0)
    c.setFont("VnFont-Bold", min(8, r * 1.4))
    c.setFillColor(colors.white)
    c.drawCentredString(cx, cy - 3, grade)


def _table(c, headers: list, rows: list, x: float, y: float,
           widths: list, row_h: int = 14, hdr_h: int = 16,
           font_sz: float = 7.5, right_cols: set = None,
           center_cols: set = None, vgm_col_idx: int = None,
           dark: bool = True) -> float:
    """
    Bảng zebra-striped, hỗ trợ dark/light theme và VGM badge.
    Trả về y sau hàng cuối cùng.
    """
    right_cols  = right_cols  or set()
    center_cols = center_cols or set()
    tw = sum(widths)

    # ── Header row ──────────────────────────────────────────
    hdr_bg = colors.HexColor("#1a3a5c") if dark else colors.HexColor("#eaf4ff")
    c.setFillColor(hdr_bg)
    c.rect(x, y - hdr_h, tw, hdr_h, fill=1, stroke=0)
    c.setStrokeColor(C_Q_GOLD if dark else C_ACCENT)
    c.setLineWidth(1.2)
    c.line(x, y, x + tw, y)
    c.setStrokeColor(C_Q_BORDER if dark else colors.HexColor("#b8d4f0"))
    c.setLineWidth(0.5)
    c.line(x, y - hdr_h, x + tw, y - hdr_h)

    cx = x
    for i, (h, w) in enumerate(zip(headers, widths)):
        c.setFont("VnFont-Bold", font_sz)
        c.setFillColor(C_Q_TEXT if dark else C_TEXT)
        lbl = str(h)[:20]
        if i in center_cols or i == vgm_col_idx:
            c.drawCentredString(cx + w / 2, y - hdr_h + 5, lbl)
        elif i in right_cols:
            c.drawRightString(cx + w - 4, y - hdr_h + 5, lbl)
        else:
            c.drawString(cx + 4, y - hdr_h + 5, lbl)
        cx += w
    y -= hdr_h

    # ── Data rows ────────────────────────────────────────────
    c.setLineWidth(0.3)
    for ri, row in enumerate(rows):
        # Zebra stripe
        if ri % 2 == 0:
            stripe = colors.HexColor("#0f2035") if dark else colors.HexColor("#f5faff")
            c.setFillColor(stripe)
            c.rect(x, y - row_h, tw, row_h, fill=1, stroke=0)

        # Dòng tổng cuối bảng → nền đậm hơn
        is_total = (ri == len(rows) - 1 and
                    str(rows[ri][0]).upper() in {"TONG", "TOTAL", "TỔNG"})
        if is_total:
            c.setFillColor(colors.HexColor("#1a3a5c") if dark
                           else colors.HexColor("#eaf4ff"))
            c.rect(x, y - row_h, tw, row_h, fill=1, stroke=0)

        cx = x
        for ci, (cell, w) in enumerate(zip(row, widths)):
            txt = str(cell) if cell is not None else "—"

            if ci == vgm_col_idx:
                pad = 2
                _draw_vgm_badge(c, cx + pad, y - row_h + pad,
                                 w - 2 * pad, row_h - 2 * pad, txt)
                cx += w
                continue

            c.setFont("VnFont-Bold" if is_total else "VnFont", font_sz)
            fc = C_Q_TEXT if dark else C_TEXT

            # Tô màu số dương/âm
            if ci in right_cols:
                try:
                    num = float(
                        txt.replace("%","").replace(",","").replace("+","")
                    )
                    if num < 0:
                        fc = colors.HexColor("#ef9a9a") if dark else C_RED
                    elif num > 0 and "%" in txt:
                        fc = colors.HexColor("#a5d6a7") if dark else C_GREEN
                except Exception:
                    pass

            c.setFillColor(fc)
            if ci in center_cols:
                c.drawCentredString(cx + w / 2, y - row_h + 4.5, txt[:18])
            elif ci in right_cols:
                c.drawRightString(cx + w - 4, y - row_h + 4.5, txt[:18])
            else:
                c.drawString(cx + 4, y - row_h + 4.5, txt[:32])
            cx += w

        c.setStrokeColor(C_Q_BORDER if dark else C_LIGHT_GREY)
        c.line(x, y - row_h, x + tw, y - row_h)
        y -= row_h

    return y


# ══════════════════════════════════════════════════════════════
# CHART: Monte Carlo Histogram  (dark theme)
# ══════════════════════════════════════════════════════════════
def _chart_mc_histogram(
    mc_returns: np.ndarray,
    var_95:     float,
    expected_1m:float,
    max_dd:     float,
) -> object:
    """
    Histogram phân phối 10,000 kịch bản Monte Carlo.
    - Bins trái VaR 95% → đỏ
    - Đường kỳ vọng và VaR dạng dashed
    - Dark theme nhất quán với trang Quant
    """
    if mc_returns is None or len(mc_returns) == 0:
        return None
    try:
        pct     = mc_returns * 100
        var_pct = var_95 * 100
        er_pct  = expected_1m * 100

        fig, ax = plt.subplots(figsize=(8.8, 3.0),
                               facecolor="#0d1b2a")
        _format_ax(ax, dark=True)
        ax.set_facecolor("#091526")

        # ── Histogram toàn bộ ────────────────────────────────
        n, bins, patches = ax.hist(
            pct, bins=90,
            color="#1565c0", alpha=0.82,
            edgecolor="#0d1b2a", linewidth=0.2,
        )
        y_max = max(n) * 1.18

        # Tô đỏ phần < VaR
        for patch, left in zip(patches, bins[:-1]):
            if left < var_pct:
                patch.set_facecolor("#c62828")
                patch.set_alpha(0.90)

        # ── Đường tham chiếu ─────────────────────────────────
        ax.axvline(var_pct,
                   color="#ef5350", lw=1.8, ls="--", zorder=5,
                   label=f"VaR 95% = {var_pct:.1f}%")
        ax.axvline(er_pct,
                   color="#66bb6a", lw=1.8, ls="--", zorder=5,
                   label=f"Ky vong = {er_pct:.1f}%")
        ax.axvline(0,
                   color="#78909c", lw=1.0, ls="-",
                   alpha=0.55, zorder=4)

        ax.set_ylim(0, y_max)

        # ── Chú thích vùng rủi ro ────────────────────────────
        x_risk = (pct.min() + var_pct) / 2
        ax.text(x_risk, y_max * 0.45,
                "Vung rui ro\n(5% XS)",
                fontsize=6.5, color="#ef9a9a",
                ha="center", va="center", alpha=0.85)

        # Annotation VaR phía trên đường
        ax.text(var_pct - 0.3, y_max * 0.92,
                f"VaR 95%\n{var_pct:.1f}%",
                fontsize=6.5, color="#ef9a9a",
                ha="right", va="top")

        # Annotation kỳ vọng
        ax.text(er_pct + 0.3, y_max * 0.92,
                f"Ky vong\n{er_pct:+.1f}%",
                fontsize=6.5, color="#a5d6a7",
                ha="left", va="top")

        # ── Max Drawdown badge ───────────────────────────────
        ax.text(0.98, 0.96,
                f"Max Drawdown (uo tinh): {max_dd*100:.1f}%",
                transform=ax.transAxes,
                fontsize=6.5, color="#ffcc80",
                ha="right", va="top",
                bbox=dict(boxstyle="round,pad=0.3",
                          fc="#1a2a3a", ec="#f57f17", alpha=0.88))

        # ── Labels & styling ─────────────────────────────────
        ax.set_xlabel("Loi nhuan danh muc 1 thang (%)",
                      fontsize=7, color="#90aac0")
        ax.set_ylabel(f"So kich ban / {N_SCENARIOS:,}",
                      fontsize=7, color="#90aac0")
        ax.set_title(
            "Phan phoi rui ro – Historical Bootstrap MC "
            f"({N_SCENARIOS:,} kich ban, khong dung Gaussian)",
            fontsize=7.8, fontweight="bold",
            color="#e3f2fd", pad=6,
        )

        # Legend
        legend_patches = [
            mpatches.Patch(color="#1565c0", alpha=0.82,
                           label="Kich ban loi nhuan"),
            mpatches.Patch(color="#c62828", alpha=0.9,
                           label=f"Vung VaR (<{var_pct:.1f}%)"),
        ]
        ax.legend(handles=legend_patches,
                  fontsize=6.5, frameon=False,
                  loc="upper left", labelcolor="#cfd8dc")

        # Xác suất thua lỗ
        prob_loss = (mc_returns < 0).mean() * 100
        ax.text(0.01, 0.96,
                f"XS thua lo: {prob_loss:.1f}%",
                transform=ax.transAxes,
                fontsize=6.5, color="#ffa726",
                ha="left", va="top",
                bbox=dict(boxstyle="round,pad=0.3",
                          fc="#1a2a3a", ec="#f59e0b", alpha=0.85))

        fig.tight_layout(pad=0.3)
        return fig

    except Exception as e:
        logger.warning(f"[quant_pdf_page] MC histogram error: {e}")
        return None


# ══════════════════════════════════════════════════════════════
# CHART: Seasonality Scores bar
# ══════════════════════════════════════════════════════════════
def _chart_seasonality(season_scores: dict) -> object:
    """Bar chart Seasonality Score theo mã – hiển thị trong trang Quant."""
    if not season_scores:
        return None
    try:
        tickers = list(season_scores.keys())[:8]
        scores  = [season_scores[t] for t in tickers]

        fig, ax = plt.subplots(figsize=(4.5, 2.8), facecolor="#0d1b2a")
        _format_ax(ax, dark=True)

        clrs = ["#66bb6a" if s >= 0.6 else "#ffa726" if s >= 0.45
                else "#ef5350" for s in scores]
        bars = ax.bar(tickers, scores, color=clrs,
                      alpha=0.85, edgecolor="#0d1b2a", width=0.6)

        for bar, val in zip(bars, scores):
            ax.text(bar.get_x() + bar.get_width() / 2,
                    bar.get_height() + 0.01,
                    f"{val:.2f}",
                    ha="center", va="bottom",
                    fontsize=7, fontweight="bold",
                    color="#e3f2fd")

        ax.set_ylim(0, 1.0)
        ax.axhline(0.5, color="#78909c", lw=0.8, ls="--", alpha=0.6)
        ax.set_xlabel("Ma CK", fontsize=7, color="#90aac0")
        ax.set_ylabel("Score (0–1)", fontsize=7, color="#90aac0")
        ax.set_title("Seasonality Score (Win Rate + Momentum)",
                     fontsize=7.5, fontweight="bold",
                     color="#e3f2fd", pad=5)
        fig.tight_layout(pad=0.3)
        return fig
    except Exception as e:
        logger.warning(f"[quant_pdf_page] Seasonality chart error: {e}")
        return None


# ══════════════════════════════════════════════════════════════
# MAIN: Render Trang 4 PDF
# ══════════════════════════════════════════════════════════════
def _render_quant_page(c, qr: "QuantResult", nav: float, page_num: int = 4):
    """
    Vẽ toàn bộ Trang Quant (trang 4) lên ReportLab Canvas.

    Layout:
    ┌─ Dark header (VSS Predictive 2.0) ──────────────────────┐
    ├─ 5 KPI: Kỳ vọng 1T | VaR 95% | MDD | Sharpe | NAV      ┤
    ├─ [PASS] Bảng phân bổ vốn 7 cột                          ┤
    │  hoặc [FAIL] Error card                                  │
    ├─ [Seasonality + MC Histogram] cạnh nhau                  ┤
    └─ Disclaimer                                              ─┘

    Args:
        c:        ReportLab Canvas đang được vẽ
        qr:       QuantResult từ portfolio_optimizer.run_full_pipeline()
        nav:      Vốn đầu tư (VND)
        page_num: Số trang hiển thị ở footer (mặc định 4)
    """
    _bg(c)

    # ── Header ───────────────────────────────────────────────
    subtitle = (
        f"Markowitz + Historical Bootstrap ({N_SCENARIOS:,} kich ban) "
        f"| Guillotine MDD<=15% | NAV: {nav/1e9:.2f} ty VND"
    )
    _page_header_quant(c, subtitle)
    y0 = PH - 52

    # ══════════════════════════════════════════════════════════
    # FALLBACK: Status != "ok"
    # ══════════════════════════════════════════════════════════
    if not qr or qr.status != "ok" or not qr.tickers:
        err = (getattr(qr, "error_message", "") or
               "Khong du lieu lich su gia.") if qr else "Loi pipeline."

        # Error card
        card_h = 80
        c.setFillColor(C_Q_DARKER)
        c.setStrokeColor(colors.HexColor("#7f1d1d"))
        c.setLineWidth(1.0)
        c.roundRect(MARGIN, y0 - card_h, CW, card_h,
                    radius=5, fill=1, stroke=1)
        c.setFillColor(colors.HexColor("#fca5a5"))
        c.rect(MARGIN, y0 - card_h, 4, card_h, fill=1, stroke=0)
        c.setFont("VnFont-Bold", 10)
        c.setFillColor(colors.HexColor("#fca5a5"))
        c.drawString(MARGIN + 12, y0 - 22,
                     "Khong the chay toi uu hoa danh muc")
        c.setFont("VnFont", 8.5)
        c.setFillColor(C_Q_TEXT)
        c.drawString(MARGIN + 12, y0 - 38, f"Ly do: {err[:90]}")
        c.setFont("VnFont", 8)
        c.setFillColor(C_Q_MUTED)
        lines = [
            "He thong can it nhat 2 ma NCN co du lieu lich su gia >= 6 thang",
            "trong file market_prices.parquet. Hay kiem tra data pipeline.",
            "PDF nay van hien thi day du Trang 1-3 (screener hien tai).",
        ]
        for i, ln in enumerate(lines):
            c.drawString(MARGIN + 12, y0 - 54 - i * 13, ln)

        _footer(c, page_num)
        return

    # ══════════════════════════════════════════════════════════
    # KPI STRIP (5 thẻ)
    # ══════════════════════════════════════════════════════════
    er_col  = C_GREEN if qr.expected_return_1m >= 0 else C_RED
    mdd_col = C_AMBER if qr.max_drawdown < 0.15 else C_RED

    kpi_items = [
        ("Ky vong 1T",
         f"{qr.expected_return_1m*100:+.1f}%", er_col),
        ("VaR 95% (1T)",
         f"{qr.var_95*100:.1f}%",              C_RED),
        ("Max Drawdown",
         f"{qr.max_drawdown*100:.1f}%",        mdd_col),
        ("Sharpe (nam)",
         f"{qr.sharpe_ratio:.2f}",             C_BLUE),
        ("Guillotine iter",
         str(qr.guillotine_iterations),         C_GREY),
    ]
    kpi_h = 42
    kw    = (CW - 4 * 6) / 5
    for i, (lbl, val, col) in enumerate(kpi_items):
        _kpi_card(c, MARGIN + i * (kw + 6), y0 - kpi_h,
                  kw, kpi_h, lbl, val, col, dark=True)
    y0 -= kpi_h + 13

    # ══════════════════════════════════════════════════════════
    # BẢNG PHÂN BỔ VỐN
    # ══════════════════════════════════════════════════════════
    _sec(c, "Ma tran Phan bo Von – Danh muc Toi uu Markowitz", MARGIN, y0)
    y0 -= 12

    # Cột: Mã | Tên CT | Sàn | VGM | % Tỷ trọng | Số CP | Giá HT | Giá trị VND
    col_cfg = [
        ("Ma CK",          0.08),
        ("Ten cong ty",    0.20),
        ("San",            0.06),
        ("VGM",            0.05),
        ("% Ty trong",     0.09),
        ("So CP mua",      0.10),
        ("Gia HT (VND)",   0.13),
        ("Gia tri (VND)",  0.17),
        ("Season Score",   0.12),
    ]
    alloc_hdrs   = [h for h, _ in col_cfg]
    raw_ratios   = [r for _, r in col_cfg]
    total_r      = sum(raw_ratios)
    alloc_widths = [CW * r / total_r for r in raw_ratios]

    alloc_rows = []
    for i, t in enumerate(qr.tickers):
        w   = qr.weights[i]           if i < len(qr.weights) else 0.0
        qty = qr.quantities[i]        if i < len(qr.quantities) else 0
        prc = qr.prices[i]            if i < len(qr.prices) else 0.0
        inv = qr.investment_values[i] if i < len(qr.investment_values) else 0.0
        cmp = (qr.companies[i][:22]   if i < len(qr.companies) else t)
        exch= qr.exchanges[i]         if i < len(qr.exchanges) else "—"
        vgm = "A"   # placeholder – thêm vào QuantResult nếu cần
        ss  = qr.seasonality_scores.get(t, 0.0)

        alloc_rows.append([
            t,
            cmp,
            exch,
            vgm,
            f"{w*100:.1f}%",
            f"{qty:,}",
            f"{prc:,.0f}",
            f"{inv/1e6:,.0f}M",
            f"{ss:.2f}",
        ])

    # Dòng tổng
    total_inv = sum(qr.investment_values)
    alloc_rows.append(
        ["TONG", "", "", "", "100%", "", "",
         f"{total_inv/1e6:,.0f}M", ""]
    )

    y0 = _table(
        c, alloc_hdrs, alloc_rows,
        MARGIN, y0, alloc_widths,
        row_h=14, hdr_h=16, font_sz=7.2,
        right_cols={4, 5, 6, 7, 8},
        center_cols={2},
        vgm_col_idx=3,
        dark=True,
    )
    y0 -= 12

    # ══════════════════════════════════════════════════════════
    # CHARTS: Seasonality (trái) + MC Histogram (phải)
    # ══════════════════════════════════════════════════════════
    y_remain = y0 - Y_MIN - 36     # dành cho disclaimer

    if y_remain > 80:
        _sec(c, "Phan tich Rui ro & Seasonality", MARGIN, y0)
        y0 -= 12
        chart_h = min(140, y_remain - 14)

        # ── Seasonality bar (chiếm ~35% width) ───────────────
        has_season = bool(qr.seasonality_scores)
        if has_season:
            fig_s = _chart_seasonality(qr.seasonality_scores)
            if fig_s:
                sw = CW * 0.34
                _embed(c, fig_s, MARGIN, y0 - chart_h, sw, chart_h)
                mc_x = MARGIN + sw + 8
                mc_w = CW - sw - 8
            else:
                mc_x, mc_w = MARGIN, CW
        else:
            mc_x, mc_w = MARGIN, CW

        # ── MC Histogram (chiếm phần còn lại) ────────────────
        if qr.mc_returns is not None and len(qr.mc_returns) > 0:
            fig_mc = _chart_mc_histogram(
                qr.mc_returns,
                qr.var_95,
                qr.expected_return_1m,
                qr.max_drawdown,
            )
            if fig_mc:
                _embed(c, fig_mc, mc_x, y0 - chart_h, mc_w, chart_h)

        y0 -= chart_h + 8

    # ══════════════════════════════════════════════════════════
    # DISCLAIMER
    # ══════════════════════════════════════════════════════════
    disc_h = 34
    if y0 - disc_h > Y_MIN:
        c.setFillColor(C_Q_DARKER)
        c.setStrokeColor(C_Q_GOLD)
        c.setLineWidth(0.8)
        c.roundRect(MARGIN, y0 - disc_h, CW, disc_h,
                    radius=4, fill=1, stroke=1)
        c.setFillColor(C_Q_GOLD)
        c.rect(MARGIN, y0 - disc_h, 4, disc_h, fill=1, stroke=0)
        c.setFont("VnFont-Bold", 7)
        c.setFillColor(C_Q_GOLD)
        c.drawString(MARGIN + 10, y0 - 11,
                     "Tuyen bo Minh bach (Transparency Disclosure)")
        c.setFont("VnFont", 6.8)
        c.setFillColor(C_Q_MUTED)
        c.drawString(
            MARGIN + 10, y0 - 22,
            f"Danh muc da vuot qua Stress-test {N_SCENARIOS:,} kich ban lich su "
            f"({qr.guillotine_iterations} vong Guillotine). "
            f"MDD uoc tinh {qr.max_drawdown*100:.1f}% | "
            f"Ky vong 1T: {qr.expected_return_1m*100:+.1f}% | "
            f"VaR 95%: {qr.var_95*100:.1f}%.",
        )
        c.drawString(
            MARGIN + 10, y0 - 32,
            "Day la phan tich dinh luong tu dong. "
            "KHONG phai khuyen nghi mua/ban chinh thuc cua Vietcap Securities.",
        )

    _footer(c, page_num)