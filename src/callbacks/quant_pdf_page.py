# src/callbacks/quant_pdf_page.py
# ============================================================
# VSS PREDICTIVE 2.0 – Stage 4: PDF Quant Page
# Đã Tối Ưu Premium Light Theme (Đồng bộ với Trang 1-3)
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

# ── QuantResult import ──
try:
    from src.backend.portfolio_optimizer import QuantResult
except ImportError:
    from dataclasses import dataclass, field
    @dataclass
    class QuantResult:
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
        scores: list = field(default_factory=list)   # ← THÊM
        guillotine_iterations: int = 0
        error_message: str = ""

# ══════════════════════════════════════════════════════════════
# CONSTANTS & COLORS (LIGHT THEME)
# ══════════════════════════════════════════════════════════════
PW, PH   = A4
MARGIN   = 28
CW       = PW - 2 * MARGIN
FOOTER_H = 22
Y_MIN    = FOOTER_H + 16
N_SCENARIOS = 10_000

C_BG         = colors.white
C_TEXT       = colors.HexColor("#1A2F4A")
C_GREY       = colors.HexColor("#5A7A99")
C_LIGHT_GREY = colors.HexColor("#CBD8E8")
C_RED        = colors.HexColor("#C62828")
C_GREEN      = colors.HexColor("#1B7A4A")
C_BLUE       = colors.HexColor("#1565C0")
C_ACCENT     = colors.HexColor("#0078D4")
C_ACCENT2    = colors.HexColor("#00B4D8")
C_AMBER      = colors.HexColor("#F59E0B")
C_PURPLE     = colors.HexColor("#6A0DAD")

VGM_COLOR = {
    "A": colors.HexColor("#1B7A4A"),
    "B": colors.HexColor("#1565C0"),
    "C": colors.HexColor("#F59E0B"),
    "D": colors.HexColor("#E65100"),
    "F": colors.HexColor("#C62828"),
}

# ══════════════════════════════════════════════════════════════
# HELPER UTILITIES
# ══════════════════════════════════════════════════════════════
def _sv(v, mode="dec1", suffix="") -> str:
    try:
        if v is None or (isinstance(v, float) and math.isnan(v)): return "—"
        if mode == "dec1":  return f"{float(v):.1f}{suffix}"
        if mode == "dec2":  return f"{float(v):.2f}{suffix}"
        if mode == "pct":   return f"{float(v):+.1f}{suffix}"
        if mode == "int":   return str(int(float(v)))
        return str(v)
    except Exception: return "—"

def _img(fig, dpi: int = 150) -> ImageReader:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight", facecolor=fig.get_facecolor())
    buf.seek(0)
    return ImageReader(buf)

def _embed(c, fig, x: float, y: float, w: float, h: float):
    c.drawImage(_img(fig), x, y, width=w, height=h, preserveAspectRatio=True, anchor="nw")
    plt.close(fig)

def _format_ax(ax):
    """Style biểu đồ chuẩn Bloomberg Light Mode"""
    ax.set_facecolor("#F7FAFD")
    for sp in ["top", "right"]:   ax.spines[sp].set_visible(False)
    for sp in ["left", "bottom"]: 
        ax.spines[sp].set_color("#CBD8E8")
        ax.spines[sp].set_linewidth(0.8)
    ax.tick_params(labelsize=7, colors="#4A6580", length=0)
    ax.grid(True, axis="y", color="#E2EBF5", linewidth=0.5, linestyle="-")
    ax.grid(False, axis="x")

def _bg(c):
    c.setFillColor(C_BG)
    c.rect(0, 0, PW, PH, fill=1, stroke=0)

def _page_header_quant(c, subtitle: str = ""):
    """Đồng bộ Header với trang 2 & 3"""
    hh = 46
    c.setFillColor(colors.HexColor("#EBF4FF"))
    c.rect(0, PH - hh, PW, hh, fill=1, stroke=0)
    c.setFillColor(colors.HexColor("#0057B8"))
    c.rect(0, PH - 4, PW, 4, fill=1, stroke=0)
    c.setStrokeColor(colors.HexColor("#BDD6F0")); c.setLineWidth(1.0)
    c.line(0, PH - hh, PW, PH - hh)

    c.setFont("VnFont-Bold", 11); c.setFillColor(colors.HexColor("#0057B8"))
    c.drawString(MARGIN, PH - 20, "VSS")
    lw = pdfmetrics.stringWidth("VSS", "VnFont-Bold", 11)
    c.setStrokeColor(colors.HexColor("#BDD6F0")); c.setLineWidth(1.0)
    c.line(MARGIN + lw + 5, PH - 24, MARGIN + lw + 5, PH - 10)
    c.setFont("VnFont", 9); c.setFillColor(colors.HexColor("#1A3A5C"))
    c.drawString(MARGIN + lw + 10, PH - 20, "Smart Screener")

    c.setFont("VnFont-Bold", 12); c.setFillColor(colors.HexColor("#0A1E35"))

    # 1. Lấy tháng hiện tại
    current_month = datetime.now().month

    # 2. Tính tháng tiếp theo (Nếu là tháng 12 thì quay về tháng 1, ngược lại thì +1)
    next_month = current_month + 1 if current_month < 12 else 1

    # 3. Format chuỗi tiêu đề động
    title = f"DỰ PHÓNG THÁNG {next_month}: Phân Bổ Danh Mục & Monte Carlo"

    # 4. Vẽ lên PDF
    c.drawCentredString(PW / 2, PH - 20, title)

    c.setFont("VnFont", 6.8); c.setFillColor(colors.HexColor("#5A80A0"))
    c.drawCentredString(PW / 2, PH - 34, subtitle)

def _sec(c, text: str, x: float, y: float, width: float = None, color=None):
    width = width or CW
    color = color or C_TEXT
    c.setFont("VnFont-Bold", 9); c.setFillColor(color)
    c.drawString(x, y, text)
    c.setStrokeColor(C_ACCENT); c.setLineWidth(2.0)
    c.line(x, y - 4, x + 24, y - 4)
    c.setStrokeColor(C_LIGHT_GREY); c.setLineWidth(0.5)
    c.line(x + 24, y - 4, x + width, y - 4)

def _kpi_card(c, x: float, y: float, w: float, h: float, label: str, value: str, col=None):
    col = col or C_ACCENT
    c.setFillColor(colors.white)
    c.setStrokeColor(colors.HexColor("#C8DDEF")); c.setLineWidth(0.6)
    c.roundRect(x, y, w, h, radius=5, fill=1, stroke=1)
    
    c.setFillColor(col)
    c.roundRect(x, y + h - 4, w, 4, radius=3, fill=1, stroke=0)
    
    c.setFont("VnFont", 6.5); c.setFillColor(colors.HexColor("#6B8FAD"))
    c.drawCentredString(x + w / 2, y + h - 15, label[:22])
    
    c.setFont("VnFont-Bold", 11); c.setFillColor(col)
    c.drawCentredString(x + w / 2, y + 8, str(value)[:12])

def _draw_vgm_badge(c, x, y, w, h, grade):
    grade = str(grade).strip().upper()
    bg_col = VGM_COLOR.get(grade, C_GREY)
    r = min(w, h) / 2 - 0.5
    cx = x + w / 2; cy = y + h / 2
    c.setFillColor(bg_col)
    c.circle(cx, cy, r, fill=1, stroke=0)
    c.setFont("VnFont-Bold", min(8.5, r * 1.45))
    c.setFillColor(colors.white)
    c.drawCentredString(cx, cy - 3, grade)

def _table(c, headers, rows, x, y, widths, row_h=14, hdr_h=17, font_sz=7.0, right_cols=None, center_cols=None, vgm_col_idx=None) -> float:
    right_cols = right_cols or set()
    center_cols = center_cols or set()
    tw = sum(widths)

    # Header
    c.setFillColor(colors.HexColor("#0E2040"))
    c.roundRect(x, y - hdr_h, tw, hdr_h, radius=0, fill=1, stroke=0)
    c.setFillColor(C_ACCENT)
    c.rect(x, y, tw, 2, fill=1, stroke=0)

    cx = x
    for i, (h, w) in enumerate(zip(headers, widths)):
        lbl = str(h)[:24]
        c.setFont("VnFont-Bold", font_sz - 0.2); c.setFillColor(colors.white)
        if i in center_cols or i == vgm_col_idx:
            c.drawCentredString(cx + w/2, y - hdr_h + 5, lbl)
        elif i in right_cols:
            c.drawRightString(cx + w - 4, y - hdr_h + 5, lbl)
        else:
            c.drawString(cx + 5, y - hdr_h + 5, lbl)
        if i < len(headers) - 1:
            c.setStrokeColor(colors.HexColor("#1E3A6A")); c.setLineWidth(0.4)
            c.line(cx + w, y - hdr_h + 3, cx + w, y - 1)
        cx += w
    y -= hdr_h

    # Rows
    for ri, row in enumerate(rows):
        is_total = (ri == len(rows) - 1 and str(row[0]).upper() in {"TONG", "TOTAL", "TỔNG"})
        row_bg = colors.HexColor("#EBF4FF") if is_total else (colors.HexColor("#F4F9FF") if ri % 2 == 0 else colors.white)
        
        c.setFillColor(row_bg)
        c.rect(x, y - row_h, tw, row_h, fill=1, stroke=0)
        c.setStrokeColor(C_LIGHT_GREY); c.setLineWidth(0.3)
        c.line(x, y - row_h, x + tw, y - row_h)

        cx = x
        for ci, (cell, w) in enumerate(zip(row, widths)):
            txt = str(cell) if cell is not None else "—"

            if ci == vgm_col_idx:
                pad = 3
                # 🟢 FIX: Bỏ vẽ vòng tròn nếu là hàng TỔNG hoặc ô bị trống
                if not is_total and txt.strip() not in ["", "—"]:
                    _draw_vgm_badge(c, cx + pad, y - row_h + pad, w - 2*pad, row_h - 2*pad, txt)
                cx += w; continue

            c.setFont("VnFont-Bold" if is_total else "VnFont", font_sz)
            fc = C_TEXT

            if ci in right_cols:
                try:
                    num = float(txt.replace("%","").replace(",","").replace("+","").replace("M",""))
                    if num < 0: fc = C_RED
                    elif num > 0 and "%" in txt: fc = C_GREEN
                except Exception: pass

            c.setFillColor(fc)
            if ci in center_cols:
                c.drawCentredString(cx + w/2, y - row_h + 4, txt[:24])
            elif ci in right_cols:
                c.drawRightString(cx + w - 4, y - row_h + 4, txt[:24])
            else:
                c.drawString(cx + 5, y - row_h + 4, txt[:34])
            cx += w

        y -= row_h
    
    c.setStrokeColor(C_LIGHT_GREY); c.setLineWidth(0.6)
    c.line(x, y, x + tw, y)
    return y

# ══════════════════════════════════════════════════════════════
# CHARTS (LIGHT THEME)
# ══════════════════════════════════════════════════════════════
def _chart_mc_histogram(mc_returns: np.ndarray, var_95: float, expected_1m: float, max_dd: float) -> object:
    if mc_returns is None or len(mc_returns) == 0: return None
    try:
        pct = mc_returns * 100
        var_pct = var_95 * 100
        er_pct = expected_1m * 100

        fig, ax = plt.subplots(figsize=(8.8, 3.0), facecolor="#FFFFFF")
        _format_ax(ax)

        n, bins, patches = ax.hist(
            pct, bins=90, color="#42A5F5", alpha=0.85, edgecolor="white", linewidth=0.5
        )
        y_max = max(n) * 1.18

        for patch, left in zip(patches, bins[:-1]):
            if left < var_pct:
                patch.set_facecolor("#EF5350")
                patch.set_alpha(0.9)

        ax.axvline(var_pct, color="#C62828", lw=1.5, ls="--", zorder=5)
        ax.axvline(er_pct, color="#1B7A4A", lw=1.5, ls="--", zorder=5)
        ax.axvline(0, color="#78909c", lw=1.0, ls="-", alpha=0.5, zorder=4)

        ax.set_ylim(0, y_max)
        
        # Annotations
        ax.text(var_pct - 0.3, y_max * 0.92, f"VaR 95%\n{var_pct:.1f}%", fontsize=7, color="#C62828", ha="right", va="top", fontweight="bold")
        ax.text(er_pct + 0.3, y_max * 0.92, f"Kỳ vọng\n{er_pct:+.1f}%", fontsize=7, color="#1B7A4A", ha="left", va="top", fontweight="bold")

        ax.text(0.98, 0.96, f"Max Drawdown: {max_dd*100:.1f}%", transform=ax.transAxes, fontsize=7, color="#E65100", ha="right", va="top", bbox=dict(boxstyle="round,pad=0.3", fc="#FFF3E0", ec="#FFB74D", alpha=0.9))

        ax.set_xlabel("Lợi nhuận danh mục 1 tháng (%)", fontsize=8, color="#4A6580")
        ax.set_ylabel(f"Số kịch bản / {N_SCENARIOS:,}", fontsize=8, color="#4A6580")
        ax.set_title(f"Phân phối rủi ro – Historical Bootstrap MC", fontsize=9, fontweight="bold", color="#0A1628", pad=8)

        legend_patches = [
            mpatches.Patch(color="#42A5F5", label="Kịch bản lợi nhuận"),
            mpatches.Patch(color="#EF5350", label=f"Vùng rủi ro (<{var_pct:.1f}%)"),
        ]
        ax.legend(handles=legend_patches, fontsize=7, frameon=False, loc="upper left", labelcolor="#1A2F4A")

        fig.tight_layout(pad=0.3)
        return fig
    except Exception as e:
        logger.warning(f"MC hist error: {e}")
        return None

def _chart_seasonality(season_scores: dict) -> object:
    if not season_scores: return None
    try:
        tickers = list(season_scores.keys())[:8]
        scores = [season_scores[t] for t in tickers]

        fig, ax = plt.subplots(figsize=(4.5, 2.8), facecolor="#FFFFFF")
        _format_ax(ax)

        clrs = ["#4CAF50" if s >= 0.6 else "#FFA726" if s >= 0.45 else "#EF5350" for s in scores]
        bars = ax.bar(tickers, scores, color=clrs, alpha=0.9, edgecolor="white", width=0.6)

        for bar, val in zip(bars, scores):
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.02, f"{val:.2f}", ha="center", va="bottom", fontsize=7.5, fontweight="bold", color="#1A2F4A")

        ax.set_ylim(0, 1.1)
        ax.axhline(0.5, color="#CBD8E8", lw=1.2, ls="--", alpha=0.8)
        ax.set_xlabel("Mã CK", fontsize=8, color="#4A6580")
        ax.set_ylabel("Score (0–1)", fontsize=8, color="#4A6580")
        ax.set_title("Seasonality Score (Win Rate + Momentum)", fontsize=8.5, fontweight="bold", color="#0A1628", pad=8)
        fig.tight_layout(pad=0.3)
        return fig
    except Exception as e:
        logger.warning(f"Seasonality chart error: {e}")
        return None

# ══════════════════════════════════════════════════════════════
# MAIN: Render Trang 4 PDF
# ══════════════════════════════════════════════════════════════
def _render_quant_page(c, qr: "QuantResult", nav: float, page_num: int = 4, ai_texts: dict = None):
    from src.callbacks.screener_pdf_callback import _footer

    _bg(c)
    subtitle = f"Thuật toán Tối ưu hóa Rủi ro (Mô phỏng {N_SCENARIOS:,} kịch bản lịch sử) - Vốn: {nav/1e9:.2f} tỷ VND"
    _page_header_quant(c, subtitle)
    y0 = PH - 58

    if not qr or qr.status != "ok" or not qr.tickers:
        err = (getattr(qr, "error_message", "") or "Không có dữ liệu lịch sử giá.") if qr else "Lỗi pipeline."
        c.setFillColor(colors.HexColor("#FEF2F2")); c.setStrokeColor(colors.HexColor("#FCA5A5")); c.setLineWidth(1.0)
        c.roundRect(MARGIN, y0 - 80, CW, 80, radius=5, fill=1, stroke=1)
        c.setFillColor(C_RED); c.rect(MARGIN, y0 - 80, 4, 80, fill=1, stroke=0)
        c.setFont("VnFont-Bold", 10); c.setFillColor(C_RED)
        c.drawString(MARGIN + 12, y0 - 22, "Không thể chạy tối ưu hóa danh mục")
        c.setFont("VnFont", 8.5); c.setFillColor(C_TEXT)
        c.drawString(MARGIN + 12, y0 - 38, f"Lý do: {err[:90]}")
        
        # Gọi footer bình thường (bỏ dòng import cũ ở đây đi)
        _footer(c, page_num=4, total=4)
        return
    subtitle = f"Thuật toán Tối ưu hóa Rủi ro (Mô phỏng {N_SCENARIOS:,} kịch bản lịch sử) - Vốn: {nav/1e9:.2f} tỷ VND"
    _page_header_quant(c, subtitle)
    y0 = PH - 58

    if not qr or qr.status != "ok" or not qr.tickers:
        err = (getattr(qr, "error_message", "") or "Không có dữ liệu lịch sử giá.") if qr else "Lỗi pipeline."
        c.setFillColor(colors.HexColor("#FEF2F2")); c.setStrokeColor(colors.HexColor("#FCA5A5")); c.setLineWidth(1.0)
        c.roundRect(MARGIN, y0 - 80, CW, 80, radius=5, fill=1, stroke=1)
        c.setFillColor(C_RED); c.rect(MARGIN, y0 - 80, 4, 80, fill=1, stroke=0)
        c.setFont("VnFont-Bold", 10); c.setFillColor(C_RED)
        c.drawString(MARGIN + 12, y0 - 22, "Không thể chạy tối ưu hóa danh mục")
        c.setFont("VnFont", 8.5); c.setFillColor(C_TEXT)
        c.drawString(MARGIN + 12, y0 - 38, f"Lý do: {err[:90]}")
        from src.callbacks.screener_pdf_callback import _footer
        _footer(c, page_num=4, total=4)
        return

    # KPI Strip
    kpi_items = [
        ("Kỳ vọng 1 tháng", f"{qr.expected_return_1m*100:+.1f}%", C_GREEN if qr.expected_return_1m >= 0 else C_RED),
        ("Rủi ro giảm", f"{qr.var_95*100:.1f}%", C_RED),
        ("Mức rủi ro lớn nhất", f"{qr.max_drawdown*100:.1f}%", C_AMBER if qr.max_drawdown < 0.15 else C_RED),
        ("Sharpe (năm)", f"{qr.sharpe_ratio:.2f}", C_BLUE),
    ]
    kpi_h = 42; kw = (CW - 4 * 6) / 4
    for i, (lbl, val, col) in enumerate(kpi_items):
        _kpi_card(c, MARGIN + i * (kw + 6), y0 - kpi_h, kw, kpi_h, lbl, val, col)
    y0 -= kpi_h + 16

    # Bảng phân bổ vốn
    _sec(c, "Ma Trận Phân Bổ Vốn – Danh Mục Tối Ưu Markowitz", MARGIN, y0, color=C_BLUE)
    y0 -= 11

    col_cfg = [
        ("Mã CK", 0.08), ("Tên công ty", 0.20), ("Sàn", 0.06), ("ĐIỂM", 0.05),
        ("% Tỷ trọng", 0.09), ("Số CP mua", 0.10), ("Giá HT (VND)", 0.13),
        ("Giá trị (VND)", 0.17), ("Season Score", 0.12),
    ]
    alloc_hdrs = [h for h, _ in col_cfg]
    alloc_widths = [CW * r / sum([r for _, r in col_cfg]) for _, r in col_cfg]

    alloc_rows = []
    for i, t in enumerate(qr.tickers):
        w = qr.weights[i] if i < len(qr.weights) else 0.0
        qty = qr.quantities[i] if i < len(qr.quantities) else 0
        prc = qr.prices[i] if i < len(qr.prices) else 0.0
        inv = qr.investment_values[i] if i < len(qr.investment_values) else 0.0
        cmp = qr.companies[i][:26] if i < len(qr.companies) else t
        exch = qr.exchanges[i] if i < len(qr.exchanges) else "—"
        # 🟢 FIX: Lấy điểm số thực tế (Score) từ kết quả đi lệnh, không gán chết điểm "A"
        if hasattr(qr, 'scores') and qr.scores and i < len(qr.scores):
            grade = qr.scores[i]
        else:
            grade = "—"   # honest fallback thay vì gán chết "A"
        
        alloc_rows.append([
            t, cmp, exch, grade, f"{w*100:.1f}%", 
            f"{qty:,}", f"{prc:,.0f}", f"{inv/1e6:,.0f}M", 
            f"{qr.seasonality_scores.get(t, 0.0):.2f}"
        ])
    alloc_rows.append(["TỔNG", "", "", "", "100%", "", "", f"{sum(qr.investment_values)/1e6:,.0f}M", ""])

    y0 = _table(c, alloc_hdrs, alloc_rows, MARGIN, y0, alloc_widths, row_h=15, hdr_h=18, font_sz=7.2, right_cols={4, 5, 6, 7, 8}, center_cols={2}, vgm_col_idx=3)
    y0 -= 16

    # ══════════════════════════════════════════════════════════════
    # THÊM MỤC C: KẾT LUẬN CHIẾN LƯỢC (BOTTOM LINE SUMMARY CHO F0)
    # ══════════════════════════════════════════════════════════════
    summary_h = 36
    if y0 - summary_h > Y_MIN:
        # Vẽ box nền màu xanh nhạt tạo sự chú ý
        c.setFillColor(colors.HexColor("#EFF6FF"))
        c.setStrokeColor(colors.HexColor("#BFDBFE"))
        c.setLineWidth(0.5)
        c.roundRect(MARGIN, y0 - summary_h, CW, summary_h, radius=4, fill=1, stroke=1)
        
        # Line viền trái màu xanh đậm
        c.setFillColor(C_BLUE)
        c.rect(MARGIN, y0 - summary_h, 4, summary_h, fill=1, stroke=0)

        # Tiêu đề kết luận
        c.setFont("VnFont-Bold", 8)
        c.setFillColor(C_BLUE)
        c.drawString(MARGIN + 12, y0 - 12, "KẾT LUẬN CHIẾN LƯỢC TỪ HỆ THỐNG VSS:")

        # Nội dung phiên dịch số liệu sang ngôn ngữ Sale
        c.setFont("VnFont", 7.5)
        c.setFillColor(C_TEXT)
        summary_text = (f"Với số vốn {nav/1e9:,.2f} Tỷ VNĐ, hệ thống khuyến nghị phân bổ vào {len(qr.tickers)} mã cổ phiếu có dòng tiền thực mạnh nhất.")
        summary_text_2 = (f"Danh mục được kỳ vọng mang lại lợi nhuận {qr.expected_return_1m*100:+.1f}% trong tháng tới, với rủi ro được kiểm soát "
                          f"chặt chẽ (sức chịu đựng tối đa {qr.max_drawdown*100:.1f}%).")
        
        c.drawString(MARGIN + 12, y0 - 22, summary_text)
        c.drawString(MARGIN + 12, y0 - 32, summary_text_2)

    y0 -= summary_h + 16

    # 2. Ngay bên dưới khối code vẽ Summary (KẾT LUẬN CHIẾN LƯỢC TỪ HỆ THỐNG VSS), em chèn thêm đoạn này:
    if ai_texts and "action" in ai_texts:
        # Import hàm vẽ box từ file kia sang để đồng bộ UI tuyệt đối (Tránh lỗi vòng lặp)
        from src.callbacks.screener_pdf_callback import _ai_box
        
        y0 -= 8
        _sec(c, "Khuyến Nghị Hành Động Thực Chiến (AI Advice)", MARGIN, y0, color=C_PURPLE)
        y0 -= 11
        
        # Vẽ Box AI lấy dữ liệu từ key "action"
        y0 = _ai_box(c, ai_texts.get("action", ""),
                     MARGIN, y0, CW,
                     box_color=colors.HexColor("#F5F3FF"), # Nền tím nhạt sang trọng
                     border_color=colors.HexColor("#DDD6FE"),
                     accent_color=C_PURPLE,
                     badge_label="Gemini Action Plan",
                     badge_color=C_PURPLE)
        y0 -= 16

    # ══════════════════════════════════════════════════════════════
    # Phần Charts bên dưới giữ nguyên
    # ══════════════════════════════════════════════════════════════

    # Charts
    if y0 - Y_MIN > 80:
        _sec(c, "Phân Tích Rủi Ro & Seasonality", MARGIN, y0, color=C_PURPLE)
        y0 -= 11
        chart_h = min(140, y0 - Y_MIN - 14)

        if qr.seasonality_scores:
            fig_s = _chart_seasonality(qr.seasonality_scores)
            if fig_s:
                sw = CW * 0.34
                _embed(c, fig_s, MARGIN, y0 - chart_h, sw, chart_h)
                mc_x, mc_w = MARGIN + sw + 8, CW - sw - 8
            else: mc_x, mc_w = MARGIN, CW
        else: mc_x, mc_w = MARGIN, CW

        if qr.mc_returns is not None and len(qr.mc_returns) > 0:
            fig_mc = _chart_mc_histogram(qr.mc_returns, qr.var_95, qr.expected_return_1m, qr.max_drawdown)
            if fig_mc: _embed(c, fig_mc, mc_x, y0 - chart_h, mc_w, chart_h)

        y0 -= chart_h + 12

    # Disclaimer
    disc_h = 32
    if y0 - disc_h > Y_MIN:
        c.setFillColor(colors.HexColor("#FFF8F0")); c.setStrokeColor(colors.HexColor("#FFCC80")); c.setLineWidth(0.5)
        c.roundRect(MARGIN, y0 - disc_h, CW, disc_h, radius=4, fill=1, stroke=1)
        c.setFillColor(C_AMBER); c.rect(MARGIN, y0 - disc_h, 4, disc_h, fill=1, stroke=0)
        c.setFont("VnFont-Bold", 6.8); c.setFillColor(C_AMBER)
        c.drawString(MARGIN + 10, y0 - 11, "Lưu ý minh bạch (Transparency Disclosure):")
        c.setFont("VnFont", 6.5); c.setFillColor(C_TEXT)
        c.drawString(MARGIN + 10, y0 - 20, f"Danh mục đã vượt qua Stress-test {N_SCENARIOS:,} kịch bản lịch sử. MDD ước tính {qr.max_drawdown*100:.1f}%.")
        c.drawString(MARGIN + 10, y0 - 28, "Đây là phân tích định lượng tự động bằng máy tính, không phải khuyến nghị đầu tư chính thức của Vietcap.")

    # 🟢 Chỉ cần gọi hàm, không cần import lại
    _footer(c, page_num=4, total=4)