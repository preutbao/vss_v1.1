# src/callbacks/screener_pdf_callback.py
# ============================================================
# PDF XUẤT DANH MỤC LỌC – Vietcap Smart Screener  v5.0
#
# THAY ĐỔI v5.0:
#   [1] Font: Thêm explicit path cho Linux (HuggingFace) + Windows
#       Chain: Arial(Win) → Liberation(Linux) → Noto(Linux) → DejaVu
#   [2] VGM: Bỏ Unicode ★ (vỡ PDF) → dùng badge chữ màu
#   [3] NCN: Chỉ Top 3, loại ngành Tài chính, thêm tên công ty + sàn
#       Thay cột "Perf 1T" → "Vùng mua" + "Cắt lỗ" (SMA-based)
#   [4] Bỏ "Bảng Sàng Lọc Chi Tiết" trùng lặp khỏi Trang 2
#       → Trang 2: NCN Top3 | Red Flags | ROE Chart
#   [5] Fix Trang 1 đè chữ: cap ai_box_h, tính đúng y0 trước khi vẽ chart
#   [6] Dual-Track: PDF tiêu đề & AI prompt bám theo khẩu vị thực của user
#   [7] Red Flags quét TOÀN BỘ df_top (không dừng sau 10), hiển thị ≤8 flag
# ============================================================

import io, os, math, logging, traceback
from datetime import datetime

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from dash import Input, Output, State, no_update, dcc, html
from src.app_instance import app
from src.backend.data_loader import get_snapshot_df

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════
# PHÔNG CHỮ – Cross-Platform (Windows + Linux/HuggingFace)
# ──────────────────────────────────────────────────────────────
# Chiến lược:
#   1. Thử các path cụ thể theo OS (nhanh, chắc chắn)
#   2. Dùng matplotlib.font_manager để tìm (fallback rộng)
#   3. Hardcoded DejaVu từ matplotlib bundle (luôn có)
# DejaVu Sans HỖ TRỢ đầy đủ ký tự tiếng Việt có dấu.
# ══════════════════════════════════════════════════════════════
_FONT_CANDIDATES = [
    # Windows
    ("C:/Windows/Fonts/arial.ttf",          "C:/Windows/Fonts/arialbd.ttf"),
    ("C:/Windows/Fonts/Tahoma.ttf",         "C:/Windows/Fonts/Tahomabd.ttf"),
    # Linux / HuggingFace – Liberation Sans (bản sao Arial, hỗ trợ Việt)
    ("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
     "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"),
    ("/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
     "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf"),
    # Noto Sans – hỗ trợ toàn bộ Unicode
    ("/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
     "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf"),
    ("/usr/share/fonts/opentype/noto/NotoSans-Regular.ttf",
     "/usr/share/fonts/opentype/noto/NotoSans-Bold.ttf"),
    # DejaVu Sans – luôn có trên mọi Linux/matplotlib
    ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
     "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
]


def _setup_fonts():
    # 1. Thử từng path cụ thể
    for reg, bold in _FONT_CANDIDATES:
        if os.path.exists(reg):
            b = bold if os.path.exists(bold) else reg
            try:
                pdfmetrics.registerFont(TTFont("VnFont",      reg))
                pdfmetrics.registerFont(TTFont("VnFont-Bold", b))
                try:
                    plt.rcParams["font.family"] = (
                        fm.FontProperties(fname=reg).get_name()
                    )
                except Exception:
                    pass
                logger.info(f"PDF font: {reg}")
                return
            except Exception as e:
                logger.debug(f"Font skip {reg}: {e}")

    # 2. Fallback qua matplotlib font_manager
    for family in ["Arial", "Liberation Sans", "Noto Sans",
                   "DejaVu Sans", "Tahoma"]:
        try:
            fp = fm.findfont(family, fallback_to_default=False)
            fb = fm.findfont(
                fm.FontProperties(family=family, weight="bold"),
                fallback_to_default=False,
            )
            if fp and os.path.exists(fp):
                bb = fb if (fb and os.path.exists(fb)) else fp
                pdfmetrics.registerFont(TTFont("VnFont",      fp))
                pdfmetrics.registerFont(TTFont("VnFont-Bold", bb))
                try:
                    plt.rcParams["font.family"] = (
                        fm.FontProperties(fname=fp).get_name()
                    )
                except Exception:
                    pass
                logger.info(f"PDF font (fm): {fp}")
                return
        except Exception:
            continue

    # 3. Hardcoded DejaVu từ matplotlib bundle – KHÔNG BAO GIỜ THIẾU
    dv  = fm.findfont("DejaVu Sans")
    dvb = fm.findfont(fm.FontProperties(family="DejaVu Sans", weight="bold"))
    pdfmetrics.registerFont(TTFont("VnFont",      dv))
    pdfmetrics.registerFont(TTFont("VnFont-Bold", dvb))
    logger.info(f"PDF font (dejavu fallback): {dv}")


_setup_fonts()

# ══════════════════════════════════════════════════════════════
# HẰNG SỐ
# ══════════════════════════════════════════════════════════════
PW, PH   = A4          # 595 × 842 pt
MARGIN   = 28
CW       = PW - 2 * MARGIN   # ~539 pt
FOOTER_H = 22
Y_MIN    = FOOTER_H + 16

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

# VGM: dùng chữ + màu, KHÔNG dùng Unicode ★ (vỡ PDF với nhiều font)
VGM_COLOR = {
    "A": colors.HexColor("#00875a"),
    "B": colors.HexColor("#0057b8"),
    "C": colors.HexColor("#f59e0b"),
    "D": colors.HexColor("#ff7043"),
    "F": colors.HexColor("#D32F2F"),
}

# Ngành cần loại khỏi NCN (lợi nhuận chu kỳ tài chính, không phải dòng tiền lõi)
EXCLUDE_SECTORS_NCN = {"Tài chính", "Financial", "Financials",
                       "Banks", "Ngân hàng", "Bảo hiểm", "Insurance"}


# ══════════════════════════════════════════════════════════════
# UTILITY
# ══════════════════════════════════════════════════════════════
def _fmt(v, dec=1, pct=False, bn=True, sign=False):
    try:
        if v is None or (isinstance(v, float) and math.isnan(v)):
            return "---"
        v   = float(v)
        pfx = "+" if (sign and v > 0) else ""
        if pct:
            return f"{pfx}{v:.{dec}f}%"
        if bn and abs(v) >= 1e9:
            return f"{pfx}{v/1e9:,.{dec}f}B"
        if bn and abs(v) >= 1e6:
            return f"{pfx}{v/1e6:,.{dec}f}M"
        if bn and abs(v) >= 1e3:
            return f"{pfx}{v/1e3:,.{dec}f}K"
        return f"{pfx}{v:,.{dec}f}"
    except Exception:
        return str(v) if v is not None else "---"


def _sv(v, mode="str", suffix=""):
    try:
        if v is None or (isinstance(v, float) and math.isnan(v)):
            return "—"
        if mode == "dec1":  return f"{float(v):.1f}{suffix}"
        if mode == "dec2":  return f"{float(v):.2f}{suffix}"
        if mode == "int":   return str(int(float(v)))
        if mode == "pct":   return f"{float(v):+.1f}{suffix}"
        return str(v)
    except Exception:
        return "—"


def _img(fig, dpi=130):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight",
                facecolor=fig.get_facecolor())
    buf.seek(0)
    return ImageReader(buf)


def _embed(c, fig, x, y, w, h):
    c.drawImage(_img(fig), x, y, width=w, height=h,
                preserveAspectRatio=True, anchor="nw")
    plt.close(fig)


def _format_ax(ax):
    ax.set_facecolor("#f8fbff")
    for sp in ["top", "right"]:   ax.spines[sp].set_visible(False)
    for sp in ["left", "bottom"]: ax.spines[sp].set_color("#b8d4f0")
    ax.grid(True, axis="y", color="#e4f0fb", linestyle="-", linewidth=0.7)
    ax.grid(False, axis="x")
    ax.tick_params(labelsize=6.5, colors="#3a6080", length=0)


def _wrap_text(c, text, x, y, max_w, font="VnFont", size=7.5,
               line_h=11, max_lines=99):
    c.setFont(font, size)
    words, current, lines = text.split(), "", []
    for w in words:
        test = (current + " " + w).strip()
        if pdfmetrics.stringWidth(test, font, size) <= max_w:
            current = test
        else:
            if current: lines.append(current)
            current = w
    if current: lines.append(current)
    for i, line in enumerate(lines[:max_lines]):
        c.drawString(x, y - i * line_h, line)
    return y - len(lines[:max_lines]) * line_h


# ══════════════════════════════════════════════════════════════
# CANVAS PRIMITIVES
# ══════════════════════════════════════════════════════════════
def _bg(c):
    c.setFillColor(C_BG)
    c.rect(0, 0, PW, PH, fill=1, stroke=0)


def _footer(c, page_num):
    c.setFillColor(C_ACCENT)
    c.rect(0, 0, PW, 3, fill=1, stroke=0)
    c.setFont("VnFont", 6.5)
    c.setFillColor(C_GREY)
    c.drawString(MARGIN, 9,
        "Vietcap Smart Screener – Dữ liệu mang tính tham khảo, không phải khuyến nghị đầu tư.")
    c.drawRightString(PW - MARGIN, 9, f"Trang {page_num}")


def _page_header_mini(c, title: str, subtitle: str = ""):
    c.setFillColor(colors.HexColor("#f0f7ff"))
    c.rect(0, PH - 40, PW, 40, fill=1, stroke=0)
    c.setFillColor(C_ACCENT)
    c.rect(0, PH - 4, PW, 4, fill=1, stroke=0)
    c.setStrokeColor(colors.HexColor("#b8d4f0"))
    c.setLineWidth(0.8)
    c.line(0, PH - 40, PW, PH - 40)
    c.setFont("VnFont-Bold", 10); c.setFillColor(C_HEADER)
    c.drawString(MARGIN, PH - 22, title)
    if subtitle:
        c.setFont("VnFont", 7.5); c.setFillColor(C_GREY)
        c.drawString(MARGIN, PH - 34, subtitle)
    c.setFont("VnFont", 7.5); c.setFillColor(C_GREY)
    c.drawRightString(PW - MARGIN, PH - 22,
                      datetime.now().strftime("%d/%m/%Y %H:%M"))


def _sec(c, text, x, y, width=None):
    width = width or CW
    c.setFont("VnFont-Bold", 9); c.setFillColor(C_HEADER)
    c.drawString(x, y, text)
    c.setStrokeColor(C_ACCENT); c.setLineWidth(1.5)
    c.line(x, y - 5, x + 22, y - 5)
    c.setStrokeColor(C_LIGHT_GREY); c.setLineWidth(0.5)
    c.line(x + 22, y - 5, x + width, y - 5)


def _kpi_card(c, x, y, w, h, label, value, col=None):
    col = col or C_ACCENT
    c.setFillColor(colors.HexColor("#f5f9ff"))
    c.setStrokeColor(C_LIGHT_GREY); c.setLineWidth(0.6)
    c.roundRect(x, y, w, h, radius=4, fill=1, stroke=1)
    c.setFillColor(col)
    c.roundRect(x, y + h - 4, w, 4, radius=2, fill=1, stroke=0)
    c.setFont("VnFont", 6.5); c.setFillColor(C_GREY)
    c.drawCentredString(x + w/2, y + h - 15, label.upper()[:22])
    c.setFont("VnFont-Bold", 12); c.setFillColor(col)
    c.drawCentredString(x + w/2, y + 7, str(value)[:12])


def _draw_vgm_badge(c, x, y, w, h, grade):
    """Vẽ badge chữ VGM (A/B/C/D/F) với màu nền – KHÔNG dùng Unicode star."""
    grade  = str(grade).strip().upper()
    bg_col = VGM_COLOR.get(grade, C_GREY)
    r = min(w, h) / 2 - 1
    cx = x + w / 2
    cy = y + h / 2
    c.setFillColor(bg_col)
    c.circle(cx, cy, r, fill=1, stroke=0)
    c.setFont("VnFont-Bold", min(8, r * 1.4))
    c.setFillColor(colors.white)
    c.drawCentredString(cx, cy - 3, grade)


def _table(c, headers, rows, x, y, widths,
           row_h=14, hdr_h=16, font_sz=7.5,
           right_cols=None, center_cols=None, vgm_col_idx=None):
    """
    Bảng zebra-striped.
    vgm_col_idx: cột VGM – dùng _draw_vgm_badge thay vì text thường.
    """
    right_cols  = right_cols  or set()
    center_cols = center_cols or set()
    tw = sum(widths)

    # Header row
    c.setFillColor(colors.HexColor("#eaf4ff"))
    c.rect(x, y - hdr_h, tw, hdr_h, fill=1, stroke=0)
    c.setStrokeColor(C_ACCENT); c.setLineWidth(1.2)
    c.line(x, y, x + tw, y)
    c.setStrokeColor(colors.HexColor("#b8d4f0")); c.setLineWidth(0.5)
    c.line(x, y - hdr_h, x + tw, y - hdr_h)

    cx = x
    for i, (h, w) in enumerate(zip(headers, widths)):
        c.setFont("VnFont-Bold", font_sz); c.setFillColor(C_TEXT)
        lbl = str(h)[:20]
        if i in center_cols or i == vgm_col_idx:
            c.drawCentredString(cx + w/2, y - hdr_h + 5, lbl)
        elif i in right_cols:
            c.drawRightString(cx + w - 4, y - hdr_h + 5, lbl)
        else:
            c.drawString(cx + 4, y - hdr_h + 5, lbl)
        cx += w
    y -= hdr_h

    c.setLineWidth(0.3)
    for ri, row in enumerate(rows):
        if ri % 2 == 0:
            c.setFillColor(colors.HexColor("#f5faff"))
            c.rect(x, y - row_h, tw, row_h, fill=1, stroke=0)

        cx = x
        for ci, (cell, w) in enumerate(zip(row, widths)):
            txt = str(cell) if cell is not None else "—"

            # VGM badge column
            if ci == vgm_col_idx:
                pad = 2
                _draw_vgm_badge(c, cx + pad, y - row_h + pad,
                                 w - 2*pad, row_h - 2*pad, txt)
                cx += w; continue

            c.setFont("VnFont", font_sz)
            fc = C_TEXT
            if ci in right_cols or ci in center_cols:
                try:
                    num = float(
                        txt.replace("%","").replace(",","").replace("+","")
                    )
                    if num < 0: fc = C_RED
                    elif num > 0 and "%" in txt: fc = C_GREEN
                except Exception: pass
            c.setFillColor(fc)
            if ci in center_cols:
                c.drawCentredString(cx + w/2, y - row_h + 4.5, txt[:18])
            elif ci in right_cols:
                c.drawRightString(cx + w - 4, y - row_h + 4.5, txt[:18])
            else:
                c.drawString(cx + 4, y - row_h + 4.5, txt[:30])
            cx += w

        c.setStrokeColor(C_LIGHT_GREY)
        c.line(x, y - row_h, x + tw, y - row_h)
        y -= row_h
    return y


# ══════════════════════════════════════════════════════════════
# BIỂU ĐỒ
# ══════════════════════════════════════════════════════════════
def _chart_sector_pie(df: pd.DataFrame):
    try:
        sec_col = next(
            (c for c in ["Sector", "GICS Sector Name"] if c in df.columns), None
        )
        if not sec_col: return None
        counts = df[sec_col].value_counts().head(8)
        if counts.empty: return None
        pal = ["#0057b8","#00875a","#D32F2F","#f59e0b",
               "#7c3aed","#0090ff","#00d4ff","#e91e63"]
        fig, ax = plt.subplots(figsize=(4.2, 3.2), facecolor="#ffffff")
        wedges, texts, autotexts = ax.pie(
            counts.values, labels=counts.index, autopct="%1.0f%%",
            colors=pal[:len(counts)], startangle=140, pctdistance=0.82,
            wedgeprops={"linewidth": 1.5, "edgecolor": "white"})
        for t in texts:      t.set_fontsize(6.5)
        for at in autotexts: at.set_fontsize(6.5); at.set_fontweight("bold")
        ax.set_title("Phân bổ ngành", fontsize=8, fontweight="bold", pad=6)
        fig.tight_layout(pad=0.2)
        return fig
    except Exception as e:
        logger.warning(f"Sector pie: {e}"); return None


def _chart_vgm_bar(df: pd.DataFrame):
    try:
        if "VGM Score" not in df.columns: return None
        counts = df["VGM Score"].value_counts().reindex(
            ["A","B","C","D","F"], fill_value=0)
        pal = {"A":"#00875a","B":"#0090ff","C":"#f59e0b","D":"#ff7043","F":"#D32F2F"}
        fig, ax = plt.subplots(figsize=(3.5, 3.0), facecolor="#ffffff")
        bars = ax.bar(counts.index, counts.values,
                      color=[pal.get(g,"#999") for g in counts.index],
                      edgecolor="white", linewidth=1.2, width=0.6)
        for bar, val in zip(bars, counts.values):
            if val > 0:
                ax.text(bar.get_x()+bar.get_width()/2,
                        bar.get_height()+0.2, str(val),
                        ha="center", va="bottom",
                        fontsize=7.5, fontweight="bold", color="#333")
        _format_ax(ax)
        ax.set_xlabel("VGM Score", fontsize=6.5)
        ax.set_ylabel("Số mã", fontsize=6.5)
        ax.set_title("Phân bổ VGM Score", fontsize=7.5,
                     fontweight="bold", loc="left")
        fig.tight_layout(pad=0.2)
        return fig
    except Exception as e:
        logger.warning(f"VGM bar: {e}"); return None


def _chart_perf_bar(df: pd.DataFrame):
    try:
        cols  = [("Perf_1W","1 tuần"),("Perf_1M","1 tháng"),("Perf_3M","3 tháng")]
        avail = [(c,l) for c,l in cols if c in df.columns]
        if not avail: return None
        labels = [l for _,l in avail]
        values = [df[c].dropna().mean() for c,_ in avail]
        clrs   = ["#00875a" if v >= 0 else "#D32F2F" for v in values]
        fig, ax = plt.subplots(figsize=(3.5, 3.0), facecolor="#ffffff")
        _format_ax(ax)
        bars = ax.bar(labels, values, color=clrs, alpha=0.88,
                      width=0.5, edgecolor="white")
        for bar, val in zip(bars, values):
            ax.text(bar.get_x()+bar.get_width()/2,
                    bar.get_height() + (0.15 if val >= 0 else -0.8),
                    f"{val:+.1f}%", ha="center", va="bottom",
                    fontsize=7.5, fontweight="bold",
                    color="#00875a" if val >= 0 else "#D32F2F")
        ax.axhline(0, color="#777", lw=0.8)
        ax.set_title("Hiệu suất TB danh mục", fontsize=7.5,
                     fontweight="bold", loc="left")
        ax.set_ylabel("%", fontsize=6.5)
        fig.tight_layout(pad=0.2)
        return fig
    except Exception as e:
        logger.warning(f"Perf bar: {e}"); return None


def _chart_pe_roe_scatter(df: pd.DataFrame, highlight_tickers=None):
    try:
        needed = ["Ticker","P/E","ROE (%)"]
        if not all(c in df.columns for c in needed): return None
        sub = df[needed].dropna()
        sub = sub[(sub["P/E"] > 0) & (sub["P/E"] < 60)
                  & (sub["ROE (%)"] > -10)]
        if sub.empty: return None

        fig, ax = plt.subplots(figsize=(8.5, 5.5), facecolor="#ffffff")
        _format_ax(ax)

        highlight = set(highlight_tickers or [])
        mask_h = sub["Ticker"].isin(highlight)

        ax.scatter(sub.loc[~mask_h,"P/E"], sub.loc[~mask_h,"ROE (%)"],
                   s=28, color="#b8d4f0", alpha=0.75, zorder=2,
                   edgecolors="white", linewidths=0.5,
                   label="Mã trong danh sách")

        if mask_h.any():
            ax.scatter(sub.loc[mask_h,"P/E"], sub.loc[mask_h,"ROE (%)"],
                       s=110, color="#00875a", alpha=0.95, zorder=4,
                       marker="D", edgecolors="#003d22", linewidths=0.8,
                       label="Defensive Pick")
            for _, row in sub.loc[mask_h].iterrows():
                ax.annotate(
                    row["Ticker"],
                    (row["P/E"], row["ROE (%)"]),
                    fontsize=7.5, fontweight="bold", color="#003d22",
                    xytext=(5, 5), textcoords="offset points",
                )

        for _, row in sub.loc[~mask_h].iterrows():
            if row["P/E"] > 35 or row["ROE (%)"] > 20:
                ax.annotate(row["Ticker"],
                            (row["P/E"], row["ROE (%)"]),
                            fontsize=5.5, color="#5a7a99",
                            xytext=(3, 3), textcoords="offset points")

        ax.axvline(15, color="#D32F2F", lw=0.9, ls="--", alpha=0.55)
        ax.axhline(15, color="#D32F2F", lw=0.9, ls="--", alpha=0.55)

        ymax = sub["ROE (%)"].max()
        ax.text(15.3, ymax * 0.96, "P/E=15x",
                fontsize=6, color="#D32F2F", alpha=0.75)
        ax.text(sub["P/E"].min() + 0.5, 15.4, "ROE=15%",
                fontsize=6, color="#D32F2F", alpha=0.75)

        ax.text(0.02, 0.97,
                "Vùng lý tưởng:\nP/E thấp + ROE cao",
                transform=ax.transAxes, fontsize=6.5,
                color="#00875a", ha="left", va="top",
                bbox=dict(boxstyle="round,pad=0.3", fc="#f0faf5",
                          ec="#b2dfdb", alpha=0.85))

        ax.set_xlabel("P/E", fontsize=8, color="#1a2f4a")
        ax.set_ylabel("ROE (%)", fontsize=8, color="#1a2f4a")
        ax.set_title(
            "Định vị danh mục: P/E vs ROE  (◆ = Defensive Pick)",
            fontsize=9, fontweight="bold", color="#0a1628", pad=10,
        )
        ax.legend(fontsize=7, frameon=False, loc="lower right")
        fig.tight_layout(pad=0.4)
        return fig
    except Exception as e:
        logger.warning(f"Scatter: {e}"); return None


def _chart_sector_roe(df: pd.DataFrame):
    try:
        sec_col = next(
            (c for c in ["Sector","GICS Sector Name"] if c in df.columns), None
        )
        if not sec_col or "ROE (%)" not in df.columns: return None
        grp = (df.groupby(sec_col)["ROE (%)"]
                 .mean().dropna().sort_values(ascending=True))
        if grp.empty: return None
        fig, ax = plt.subplots(
            figsize=(7.5, max(2.5, len(grp)*0.36)), facecolor="#ffffff"
        )
        _format_ax(ax)
        clrs = ["#00875a" if v >= 0 else "#D32F2F" for v in grp.values]
        bars = ax.barh(grp.index, grp.values, color=clrs,
                       alpha=0.82, edgecolor="white")
        for bar, val in zip(bars, grp.values):
            ax.text(val + (0.3 if val >= 0 else -0.3),
                    bar.get_y() + bar.get_height()/2,
                    f"{val:.1f}%", va="center", fontsize=6.5,
                    color="#333", ha="left" if val >= 0 else "right")
        ax.set_xlabel("ROE TB (%)", fontsize=7)
        ax.set_title("ROE trung bình theo ngành (danh mục lọc)",
                     fontsize=7.5, fontweight="bold", loc="left")
        fig.tight_layout(pad=0.3)
        return fig
    except Exception as e:
        logger.warning(f"Sector ROE: {e}"); return None


# ══════════════════════════════════════════════════════════════
# AI SUMMARY – Bám theo khẩu vị thực của user
# ══════════════════════════════════════════════════════════════
def _gemini_summary(df_top: pd.DataFrame, ncn_tickers: list,
                    strategy_label: str = "Phòng thủ") -> str:
    try:
        import google.generativeai as genai
        api_key = os.environ.get("GEMINI_API_KEY", "")
        if not api_key:
            raise ValueError("No GEMINI_API_KEY")
        genai.configure(api_key=api_key)
        model   = genai.GenerativeModel("gemini-2.5-flash-lite")
        sectors = (df_top["Sector"].value_counts().head(3).to_dict()
                   if "Sector" in df_top.columns else {})
        avg_pe  = df_top["P/E"].dropna().mean()    if "P/E"     in df_top.columns else None
        avg_roe = df_top["ROE (%)"].dropna().mean() if "ROE (%)" in df_top.columns else None
        ncn_str = ", ".join(ncn_tickers[:3]) if ncn_tickers else "N/A"

        prompt = (
            f"Bạn là chuyên gia tư vấn đầu tư tại Vietcap Securities. "
            f"Khẩu vị lọc hiện tại của khách hàng: [{strategy_label}].\n"
            "Hãy viết đúng 3 gạch đầu dòng ngắn gọn "
            "(mỗi gạch 1 câu, TIẾNG VIỆT CÓ DẤU, văn phong tư vấn viên chuyên nghiệp, "
            "KHÔNG khuyến nghị mua/bán cụ thể):\n"
            "Gạch 1: Bối cảnh thị trường và áp lực vĩ mô hiện tại\n"
            "Gạch 2: Vì sao chiến lược phù hợp với khẩu vị này?\n"
            "Gạch 3: Khu vực giải ngân tối ưu: CFO dương, P/E < 15, ROE > 15%\n"
            f"Dữ liệu: Ngành chính: {sectors}, "
            f"P/E TB: {f'{avg_pe:.1f}' if avg_pe else 'N/A'}, "
            f"ROE TB: {f'{avg_roe:.1f}' if avg_roe else 'N/A'}%, "
            f"Top Defensive Pick: {ncn_str}\n"
            "Chỉ trả về 3 dòng, mỗi dòng bắt đầu bằng '- '"
        )
        return model.generate_content(prompt).text.strip()
    except Exception as e:
        logger.warning(f"Gemini skip: {e}")
        return (
            "- Thị trường VN đang trong giai đoạn phân hóa, "
            "áp lực lãi suất và tỷ giá duy trì.\n"
            "- Chiến lược phòng thủ giúp bảo toàn vốn, "
            "ưu tiên DN có dòng tiền hoạt động dương và nợ vay thấp.\n"
            "- Khu vực giải ngân: DN có CFO dương liên tục, "
            "P/E < 15x, ROE > 15%, D/E ≤ 1.5x."
        )


# ══════════════════════════════════════════════════════════════
# DETECT STRATEGY LABEL từ active_filters
# ══════════════════════════════════════════════════════════════
def _detect_strategy(active_filters: dict) -> tuple:
    """
    Trả về (strategy_label, title_suffix).
    Phân tích bộ lọc để đặt tên chiến lược phù hợp với khẩu vị user.
    """
    if not active_filters:
        return "Phòng thủ", "Chiến lược Phòng thủ"

    pe_val  = None
    roe_val = None
    div_val = None

    for fid, entry in active_filters.items():
        if not isinstance(entry, dict): continue
        val = entry.get("value")
        if isinstance(val, list) and len(val) == 2:
            if "pe" in fid.lower():   pe_val  = val[1]
            if "roe" in fid.lower():  roe_val = val[0]
            if "div" in fid.lower():  div_val = val[0]

    if pe_val is not None and float(pe_val) > 20:
        return "Tăng trưởng / Khám phá", "Chiến lược Tăng trưởng – Khám phá Cơ hội"
    if div_val is not None and float(div_val) >= 4:
        return "Thu nhập cổ tức", "Chiến lược Thu nhập – Cổ tức cao"
    if roe_val is not None and float(roe_val) >= 15:
        return "Chất lượng cao", "Chiến lược Chất lượng – ROE vượt trội"
    return "Phòng thủ", "Chiến lược Phòng thủ – Bảo toàn Vốn"


# ══════════════════════════════════════════════════════════════
# CHUẨN BỊ DATA
# ══════════════════════════════════════════════════════════════
def _calc_target_stoploss(price: float, sma20=None, sma50=None) -> tuple:
    """
    Tính vùng giá mua và ngưỡng cắt lỗ kỹ thuật.
    - Target Zone: Price ×0.97 – Price (hỗ trợ ±3%)
    - Stop-loss: SMA20 nếu có, không thì price × 0.92
    Trả về (target_str, stoploss_str) dạng string.
    """
    try:
        p = float(price)
        if p <= 0: return "—", "—"

        lo     = p * 0.97
        target = f"{lo:,.0f}-{p:,.0f}"

        if sma20 and float(sma20) > 0:
            sl_val = float(sma20) * 0.99
        elif sma50 and float(sma50) > 0:
            sl_val = float(sma50) * 0.99
        else:
            sl_val = p * 0.92
        stoploss = f"{sl_val:,.0f}"

        return target, stoploss
    except Exception:
        return "—", "—"


def _prepare_ncn_rows(df_source: pd.DataFrame, top_n: int = 3) -> list:
    """
    NCN Defensive Pick:
    - Loại ngành Tài chính (lợi nhuận chu kỳ, không phải dòng tiền lõi)
    - Lọc: ROE>=15%, D/E<=1.5, Net Margin>=5%, Gross Margin>=15%
    - Sort: VGM > ROE
    - Top n (mặc định 3)
    - Thêm: tên công ty (Company Common Name), sàn (Exchange)
    - Thêm: Vùng mua (Target Zone), Cắt lỗ (Stop-loss)
    - Bỏ cột Perf 1T
    """
    try:
        df_ncn = df_source.copy()
        num_cols = ["ROE (%)","D/E","Net Margin (%)","Gross Margin (%)","Price Close",
                    "SMA20","SMA50"]
        for col in num_cols:
            if col in df_ncn.columns:
                df_ncn[col] = pd.to_numeric(df_ncn[col], errors="coerce")

        # [v5] Loại ngành Tài chính
        sec_col = next((c for c in ["Sector","GICS Sector Name"] if c in df_ncn.columns), None)
        if sec_col:
            df_ncn = df_ncn[~df_ncn[sec_col].isin(EXCLUDE_SECTORS_NCN)]

        if "ROE (%)"          in df_ncn.columns:
            df_ncn = df_ncn[df_ncn["ROE (%)"].fillna(0)        >= 15]
        if "D/E"              in df_ncn.columns:
            df_ncn = df_ncn[df_ncn["D/E"].fillna(999)          <= 1.5]
        if "Net Margin (%)"   in df_ncn.columns:
            df_ncn = df_ncn[df_ncn["Net Margin (%)"].fillna(0) >= 5]
        if "Gross Margin (%)" in df_ncn.columns:
            gm = df_ncn["Gross Margin (%)"]
            df_ncn = df_ncn[gm.isna() | (gm >= 15)]

        grade_order = {"A":1,"B":2,"C":3,"D":4,"F":5}
        if "VGM Score" in df_ncn.columns:
            df_ncn["_sort_vgm"] = df_ncn["VGM Score"].map(grade_order).fillna(6)
        else:
            df_ncn["_sort_vgm"] = 6
        df_ncn["_sort_roe"] = (df_ncn["ROE (%)"] if "ROE (%)" in df_ncn.columns
                               else pd.Series([0]*len(df_ncn))).fillna(0)
        df_ncn = df_ncn.sort_values(["_sort_vgm","_sort_roe"],
                                     ascending=[True, False])

        rows = []
        for _, r in df_ncn.head(top_n).iterrows():
            ticker = str(r.get("Ticker","—"))

            cs_raw = r.get("CANSLIM Score")
            try:    cs_str = f"{int(float(cs_raw))}/7"
            except: cs_str = "—"

            company_raw = (r.get("Company Common Name") or
                           r.get("company_name_vi") or
                           r.get("organ_name") or "")
            company = str(company_raw).strip()[:30] or "—"

            exchange = str(r.get("Exchange","") or "").strip() or "—"

            price   = r.get("Price Close")
            sma20   = r.get("SMA20")
            sma50   = r.get("SMA50")
            target, stoploss = _calc_target_stoploss(price, sma20, sma50)

            rows.append({
                "ticker":       ticker,
                "company":      company,
                "exchange":     exchange,
                "vgm":          str(r.get("VGM Score","—")),
                "canslim":      cs_str,
                "roe":          _sv(r.get("ROE (%)"),          "dec1", "%"),
                "gross_margin": _sv(r.get("Gross Margin (%)"), "dec1", "%"),
                "de":           _sv(r.get("D/E"),              "dec2"),
                "net_margin":   _sv(r.get("Net Margin (%)"),   "dec1", "%"),
                "pe":           _sv(r.get("P/E"),              "dec1"),
                "target":       target,
                "stoploss":     stoploss,
            })
        return rows
    except Exception as e:
        logger.warning(f"NCN rows: {e}"); return []


def _prepare_flag_rows(df: pd.DataFrame, max_flags: int = 8) -> list:
    """
    Red Flags – quét TOÀN BỘ df, ưu tiên: D/E cao > P/E cao > Momentum âm
    Trả về danh sách tuple (ticker, tiêu_chí, giá_trị, ngưỡng, đánh_giá)
    """
    flags_de, flags_pe, flags_mom = [], [], []
    seen = set()

    for _, r in df.iterrows():
        ticker = str(r.get("Ticker","—"))
        if ticker in seen: continue

        try:
            de = float(r.get("D/E")) if pd.notnull(r.get("D/E")) else None
            if de and de > 2.0:
                flags_de.append(
                    (ticker, "D/E cao", f"{de:.2f}x", "<= 2.0x",
                     "[!] Đòn bẩy cao")
                )
                seen.add(ticker); continue
        except: pass
        try:
            pe = float(r.get("P/E")) if pd.notnull(r.get("P/E")) else None
            if pe and pe > 30:
                flags_pe.append(
                    (ticker, "P/E cao", f"{pe:.1f}x", "<= 30x",
                     "[!] Định giá đắt")
                )
                seen.add(ticker); continue
        except: pass
        try:
            pm = float(r.get("Perf_1M")) if pd.notnull(r.get("Perf_1M")) else None
            if pm is not None and pm < 0:
                flags_mom.append(
                    (ticker, "Momentum âm", f"{pm:+.1f}%", "> 0%",
                     "[!] Đã giảm 1T")
                )
                seen.add(ticker)
        except: pass

    combined = flags_de + flags_pe + flags_mom
    return combined[:max_flags]


# ══════════════════════════════════════════════════════════════
# TRANG 1: HOOK
# ══════════════════════════════════════════════════════════════
def _render_cover(c, stats, ai_text, filter_params, strategy_title,
                  fig_sector, fig_vgm, fig_perf):
    _bg(c)

    c.setFillColor(C_ACCENT)
    c.rect(0, PH - 4, PW, 4, fill=1, stroke=0)

    c.setFillColor(colors.HexColor("#f0f7ff"))
    c.rect(0, PH - 80, PW, 76, fill=1, stroke=0)
    c.setStrokeColor(colors.HexColor("#b8d4f0")); c.setLineWidth(0.8)
    c.line(0, PH - 80, PW, PH - 80)

    y_top = PH - 24
    c.setFont("VnFont-Bold", 11); c.setFillColor(C_ACCENT)
    c.drawString(MARGIN, y_top, "VSS")
    lw = pdfmetrics.stringWidth("VSS","VnFont-Bold",11)
    c.setFont("VnFont", 11); c.setFillColor(C_HEADER)
    c.drawString(MARGIN + lw + 3, y_top, " Smart Screener")
    c.setFont("VnFont", 7.5); c.setFillColor(C_TEXT)
    c.drawString(MARGIN + 140, y_top,
                 "Phân tích danh mục định lượng – Thị trường VN")
    c.setFont("VnFont-Bold", 8.5); c.setFillColor(C_ACCENT)
    c.drawRightString(PW - MARGIN, y_top, "BÁO CÁO DANH MỤC LỌC")
    c.setFont("VnFont", 7); c.setFillColor(C_GREY)
    c.drawRightString(PW - MARGIN, y_top - 11,
                      datetime.now().strftime("%d/%m/%Y %H:%M"))

    c.setFont("VnFont-Bold", 17); c.setFillColor(C_HEADER)
    c.drawString(MARGIN, PH - 54, strategy_title[:55])
    c.setFont("VnFont", 8.5); c.setFillColor(C_GREY)
    c.drawString(MARGIN, PH - 67,
        f"Xuất từ Vietcap Smart Screener  ·  {stats['total']} mã phù hợp bộ lọc")

    card_h = 46
    y_kpi  = PH - 80 - 8
    kpi_data = [
        ("Tổng mã lọc",  str(stats["total"]),           C_ACCENT),
        ("Hiển thị PDF", str(stats["display"]),          C_BLUE),
        ("Mã VGM A",     str(stats["grade_a_count"]),    C_GREEN),
        ("P/E TB",       stats["avg_pe"],                C_HEADER),
        ("ROE TB",       stats["avg_roe"],               C_GREEN),
        ("Số ngành",     str(stats["sectors_count"]),    C_PURPLE),
    ]
    card_w = (CW - 5*5) / 6
    for i, (lbl, val, col) in enumerate(kpi_data):
        _kpi_card(c, MARGIN + i*(card_w+5), y_kpi - card_h,
                  card_w, card_h, lbl, val, col)

    y0 = y_kpi - card_h - 12

    if filter_params:
        n_rows  = max(1, math.ceil(len(filter_params) / 5))
        box_h   = 18 + n_rows * 13
        c.setFillColor(colors.HexColor("#f0f7ff"))
        c.setStrokeColor(colors.HexColor("#b8d4f0")); c.setLineWidth(0.6)
        c.roundRect(MARGIN, y0 - box_h, CW, box_h, radius=4, fill=1, stroke=1)
        c.setFillColor(C_BLUE)
        c.rect(MARGIN, y0 - box_h, 3, box_h, fill=1, stroke=0)
        c.setFont("VnFont-Bold", 7.5); c.setFillColor(C_BLUE)
        c.drawString(MARGIN+8, y0-12, "Thông số bộ lọc đang áp dụng:")
        tx, ty = MARGIN+8, y0-24
        for param in filter_params:
            tw_p = pdfmetrics.stringWidth(param,"VnFont",6.8)+10
            if tx + tw_p > PW - MARGIN:
                tx = MARGIN+8; ty -= 13
            c.setFillColor(colors.HexColor("#dce8f0"))
            c.roundRect(tx, ty-8, tw_p, 11, radius=3, fill=1, stroke=0)
            c.setFont("VnFont", 6.8); c.setFillColor(C_HEADER)
            c.drawString(tx+4, ty-5, param)
            tx += tw_p + 4
        y0 -= box_h + 10

    # ── AI Executive Summary ──────────────────────────────────
    _sec(c, "Chiến lược & Góc nhìn (AI Executive Summary)", MARGIN, y0)
    y0 -= 12

    lines = [l.strip() for l in ai_text.split("\n") if l.strip()]
    n_ai_lines = min(4, max(3, len(lines)))
    ai_box_h   = 16 + n_ai_lines * 13

    c.setFillColor(colors.HexColor("#f5f0ff"))
    c.setStrokeColor(colors.HexColor("#c7d8f0")); c.setLineWidth(0.6)
    c.roundRect(MARGIN, y0 - ai_box_h, CW, ai_box_h, radius=4, fill=1, stroke=1)
    c.setFillColor(C_PURPLE)
    c.rect(MARGIN, y0 - ai_box_h, 3, ai_box_h, fill=1, stroke=0)

    c.setFillColor(C_PURPLE)
    c.roundRect(MARGIN+8, y0-15, 18, 12, radius=3, fill=1, stroke=0)
    c.setFont("VnFont-Bold", 6.5); c.setFillColor(colors.white)
    c.drawCentredString(MARGIN+17, y0-11, "AI")
    c.setFont("VnFont-Bold", 7.5); c.setFillColor(C_PURPLE)
    c.drawString(MARGIN+30, y0-11, "Gemini 2.5 Flash Lite")

    ty = y0 - 26
    c.setFont("VnFont", 7.5); c.setFillColor(C_TEXT)
    for line in lines[:n_ai_lines]:
        ty = _wrap_text(c, line, MARGIN+10, ty,
                        max_w=CW-18, font="VnFont", size=7.5,
                        line_h=10.5, max_lines=2)
        ty -= 2

    y0 -= ai_box_h + 12

    # ── Biểu đồ ──────────────────────────────────────────────
    avail_h = y0 - Y_MIN - 14
    if avail_h > 70:
        _sec(c, "Phân tích trực quan", MARGIN, y0)
        y0 -= 12
        chart_figs = [f for f in [fig_sector, fig_vgm, fig_perf] if f is not None]
        if chart_figs:
            ch_h = max(80, y0 - Y_MIN)
            ch_w = (CW - (len(chart_figs)-1)*8) / len(chart_figs)
            for i, fig in enumerate(chart_figs):
                _embed(c, fig,
                       MARGIN + i*(ch_w+8), y0 - ch_h,
                       ch_w, ch_h)

    _footer(c, 1)


# ══════════════════════════════════════════════════════════════
# TRANG 2: CORE – NCN Top3 | Red Flags | ROE Chart
# ══════════════════════════════════════════════════════════════
def _render_core_page(c, ncn_rows, flag_rows, fig_sector_roe):
    _bg(c)
    _page_header_mini(c,
        "Vietcap Defensive Pick & Cảnh Báo Rủi Ro",
        "Top 3 mã chất lượng cao  ·  Red Flags tự động  ·  ROE theo ngành")

    y0 = PH - 54

    # ── PHẦN 1: NCN Top 3 ────────────────────────────────────
    _sec(c, "Vietcap Defensive Pick – Top 3 Cổ Phiếu Chất Lượng (không Tài chính)",
         MARGIN, y0)
    y0 -= 11

    box_h = 28
    c.setFillColor(colors.HexColor("#f0faf5"))
    c.setStrokeColor(colors.HexColor("#b2dfdb")); c.setLineWidth(0.6)
    c.roundRect(MARGIN, y0-box_h, CW, box_h, radius=4, fill=1, stroke=1)
    c.setFillColor(C_GREEN); c.rect(MARGIN, y0-box_h, 3, box_h, fill=1, stroke=0)
    c.setFont("VnFont-Bold", 7.2); c.setFillColor(C_DARK_GREEN)
    c.drawString(MARGIN+8, y0-11,
        "Bộ lọc: ROE >= 15%  ·  D/E <= 1.5  ·  Net Margin >= 5%  ·  Loại ngành Tài chính")
    c.setFont("VnFont", 7); c.setFillColor(C_TEXT)
    c.drawString(MARGIN+8, y0-22,
        "Tập trung DN chất lượng lợi nhuận lõi, dòng tiền hoạt động bền vững, "
        "nợ vay thấp. Kèm vùng giá mua & cắt lỗ kỹ thuật.")
    y0 -= box_h + 7

    if ncn_rows:
        col_props = [
            ("Mã CK",       0.08),
            ("Tên công ty", 0.18),
            ("Sàn",         0.06),
            ("VGM",         0.05),
            ("CANSLIM",     0.08),
            ("ROE %",       0.08),
            ("Biên Gộp",    0.08),
            ("D/E",         0.07),
            ("Biên Ròng",   0.08),
            ("P/E",         0.06),
            ("Vùng mua",    0.12),
            ("Cắt lỗ",      0.08),
        ]
        ncn_hdrs   = [h for h,_ in col_props]
        ncn_widths = [CW * p for _,p in col_props]
        tot = sum(ncn_widths)
        ncn_widths = [w * CW / tot for w in ncn_widths]

        ncn_data = [[
            r["ticker"],
            r["company"],
            r["exchange"],
            r["vgm"],
            r["canslim"],
            r["roe"],
            r["gross_margin"],
            r["de"],
            r["net_margin"],
            r["pe"],
            r["target"],
            r["stoploss"],
        ] for r in ncn_rows]

        y0 = _table(c, ncn_hdrs, ncn_data, MARGIN, y0, ncn_widths,
                    row_h=16, hdr_h=17, font_sz=7.2,
                    right_cols={4,5,6,7,8,9,10,11},
                    center_cols={2},
                    vgm_col_idx=3)
    else:
        c.setFont("VnFont", 8); c.setFillColor(C_GREY)
        c.drawString(MARGIN, y0-16,
            "Không có mã nào đạt chuẩn NCN trong danh mục hiện tại.")
        y0 -= 30

    y0 -= 13

    # ── PHẦN 2: Red Flags ────────────────────────────────────
    _sec(c, "Cảnh Báo Rủi Ro (Red Flags)", MARGIN, y0)
    y0 -= 11

    if flag_rows:
        fw  = [CW*p for p in [0.10, 0.16, 0.14, 0.14, 0.46]]
        fh2 = ["Mã CK", "Tiêu chí", "Giá trị HT", "Ngưỡng AT", "Đánh giá"]
        y0  = _table(c, fh2, flag_rows, MARGIN, y0, fw,
                     row_h=13, hdr_h=15, font_sz=7.2, right_cols={2,3})
    else:
        c.setFont("VnFont", 8); c.setFillColor(C_GREY)
        c.drawString(MARGIN, y0-14, "Không phát hiện red flag trong danh mục hiện tại.")
        y0 -= 24

    y0 -= 8

    disc_h = 24
    if y0 - disc_h > Y_MIN + 50:
        c.setFillColor(colors.HexColor("#fffbeb"))
        c.setStrokeColor(colors.HexColor("#fde68a")); c.setLineWidth(0.5)
        c.roundRect(MARGIN, y0-disc_h, CW, disc_h, radius=3, fill=1, stroke=1)
        c.setFillColor(C_AMBER); c.rect(MARGIN, y0-disc_h, 3, disc_h, fill=1, stroke=0)
        c.setFont("VnFont-Bold", 6.8); c.setFillColor(colors.HexColor("#78350f"))
        c.drawString(MARGIN+8, y0-9, "Lưu ý:")
        c.setFont("VnFont", 6.5)
        c.drawString(MARGIN+8, y0-20,
            "P/E cao không nhất thiết xấu nếu EPS tăng trưởng mạnh (PEG < 1.5). "
            "D/E cao có thể chấp nhận với ngành Tài chính, BĐS.")
        y0 -= disc_h + 10

    # ── PHẦN 3: ROE theo ngành ───────────────────────────────
    y_remain = y0 - Y_MIN
    if fig_sector_roe and y_remain > 80:
        _sec(c, "ROE trung bình theo ngành (danh mục lọc)", MARGIN, y0)
        y0 -= 12
        chart_h = min(170, y_remain - 14)
        _embed(c, fig_sector_roe, MARGIN, y0 - chart_h, CW, chart_h)

    _footer(c, 2)


# ══════════════════════════════════════════════════════════════
# TRANG 3: PROOF – Scatter P/E vs ROE
# ══════════════════════════════════════════════════════════════
def _render_proof_page(c, fig_scatter):
    _bg(c)
    _page_header_mini(c,
        "Định Vị Danh Mục – Bằng Chứng Định Lượng",
        "Phân tích P/E vs ROE  ·  Góc phần tư lý tưởng = P/E thấp + ROE cao")

    y0 = PH - 54

    _sec(c, "Định vị danh mục: P/E vs ROE  (◆ = Defensive Pick)", MARGIN, y0)
    y0 -= 12

    note_h = 34
    c.setFillColor(colors.HexColor("#f0f7ff"))
    c.setStrokeColor(C_LIGHT_GREY); c.setLineWidth(0.5)
    c.roundRect(MARGIN, y0-note_h, CW, note_h, radius=4, fill=1, stroke=1)
    c.setFillColor(C_ACCENT); c.rect(MARGIN, y0-note_h, 3, note_h, fill=1, stroke=0)
    c.setFont("VnFont", 7.5); c.setFillColor(C_TEXT)
    c.drawString(MARGIN+10, y0-11,
        "Biểu đồ chứng minh vị thế áp đảo của các mã Defensive Pick (◆ xanh lá):")
    c.drawString(MARGIN+10, y0-22,
        "ROE cao hơn rõ rệt và định giá (P/E) ở mức hợp lý so với phần còn lại.")
    c.drawString(MARGIN+10, y0-32,
        "Đường đỏ đứt: ROE = 15% và P/E = 15x – ngưỡng tối thiểu chiến lược phòng thủ.")
    y0 -= note_h + 10

    y_remain = y0 - Y_MIN
    if fig_scatter and y_remain > 100:
        _embed(c, fig_scatter, MARGIN, Y_MIN, CW, y_remain)

    _footer(c, 3)


# ══════════════════════════════════════════════════════════════
# MAIN GENERATOR
# ══════════════════════════════════════════════════════════════
def generate_screener_pdf(row_data: list, active_filters: dict = None) -> bytes:
    df = pd.DataFrame(row_data) if row_data else pd.DataFrame()

    num_cols = ["Price Close","P/E","P/B","ROE (%)","D/E","Net Margin (%)",
                "Perf_1W","Perf_1M","Perf_3M","RS_1M","Market Cap",
                "CANSLIM Score","Gross Margin (%)","SMA20","SMA50"]
    for col in num_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Loại mã rác: penny (< 3000 VND) & ROE cực âm
    if "Price Close" in df.columns:
        df = df[pd.to_numeric(df["Price Close"], errors="coerce").fillna(0) >= 3000]
    if "ROE (%)" in df.columns:
        roe_num = pd.to_numeric(df["ROE (%)"], errors="coerce")
        df = df[roe_num.isna() | (roe_num >= -50)]

    grade_order = {"A":1,"B":2,"C":3,"D":4,"F":5}
    if "VGM Score" in df.columns:
        df["_sort_vgm"] = df["VGM Score"].map(grade_order).fillna(6)
        df = df.sort_values("_sort_vgm").drop(columns=["_sort_vgm"])

    total_count = len(df)
    df_top      = df.head(30)

    stats = {
        "total":         total_count,
        "display":       min(30, total_count),
        "avg_pe":        _sv(df_top["P/E"].dropna().mean()     if "P/E"     in df_top.columns else None, "dec1"),
        "avg_roe":       _sv(df_top["ROE (%)"].dropna().mean() if "ROE (%)" in df_top.columns else None, "dec1", "%"),
        "avg_perf_1m":   _sv(df_top["Perf_1M"].dropna().mean() if "Perf_1M" in df_top.columns else None, "pct", "%"),
        "grade_a_count": int((df_top["VGM Score"]=="A").sum()) if "VGM Score" in df_top.columns else 0,
        "sectors_count": int(df_top["Sector"].nunique())       if "Sector"   in df_top.columns else 0,
    }

    strategy_label, strategy_title = _detect_strategy(active_filters)

    # NCN Top 3 từ TOÀN BỘ df
    ncn_rows    = _prepare_ncn_rows(df, top_n=3)
    ncn_tickers = [r["ticker"] for r in ncn_rows]

    flag_rows   = _prepare_flag_rows(df_top, max_flags=8)
    ai_text     = _gemini_summary(df_top, ncn_tickers, strategy_label)

    filter_params = []
    if active_filters:
        label_map = {
            "filter-pe":            "P/E",
            "filter-pb":            "P/B",
            "filter-roe":           "ROE (%)",
            "filter-de":            "D/E",
            "filter-market-cap":    "Vốn hóa",
            "filter-vgm-score":     "VGM Score",
            "filter-canslim":       "CANSLIM",
            "filter-perf-1m":       "Hiệu suất 1T",
            "filter-net-margin":    "Net Margin",
            "filter-div-yield":     "Div Yield",
            "filter-current-ratio": "Current Ratio",
        }
        for fid, entry in active_filters.items():
            if isinstance(entry, dict):
                label = entry.get("label") or label_map.get(fid, fid)
                val   = entry.get("value")
                if isinstance(val, list) and len(val) == 2:
                    filter_params.append(f"{label}: {val[0]} -> {val[1]}")
                elif isinstance(val, list):
                    filter_params.append(f"{label}: {', '.join(str(v) for v in val)}")
                elif val is not None:
                    filter_params.append(f"{label}: {val}")

    fig_sector  = _chart_sector_pie(df_top)
    fig_vgm     = _chart_vgm_bar(df_top)
    fig_perf    = _chart_perf_bar(df_top)
    fig_sec_roe = _chart_sector_roe(df_top)
    fig_scatter = _chart_pe_roe_scatter(df_top, highlight_tickers=ncn_tickers)

    buf = io.BytesIO()
    c   = rl_canvas.Canvas(buf, pagesize=A4)
    c.setTitle("Vietcap Smart Screener - Báo cáo Danh mục Lọc")
    c.setAuthor("Vietcap Smart Screener")

    pages = [
        lambda: _render_cover(c, stats, ai_text, filter_params, strategy_title,
                               fig_sector, fig_vgm, fig_perf),
        lambda: _render_core_page(c, ncn_rows, flag_rows, fig_sec_roe),
        lambda: _render_proof_page(c, fig_scatter),
    ]

    for i, fn in enumerate(pages, start=1):
        try:
            fn()
        except Exception as e:
            logger.error(f"Screener PDF trang {i}: {e}")
            traceback.print_exc()
            _bg(c)
            c.setFont("VnFont", 11); c.setFillColor(C_RED)
            c.drawCentredString(PW/2, PH/2, f"Lỗi trang {i}: {str(e)[:80]}")
        c.showPage()

    c.save()
    buf.seek(0)
    return buf.read()


# ══════════════════════════════════════════════════════════════
# DASH CALLBACK
# ══════════════════════════════════════════════════════════════
@app.callback(
    [Output("screener-pdf-download", "data"),
     Output("screener-pdf-status",   "children")],
    Input("btn-export-screener-pdf", "n_clicks"),
    [State("screener-table",        "rowData"),
     State("active-filters-store",  "data")],
    prevent_initial_call=True,
    running=[
        (Output("btn-export-screener-pdf", "disabled"), True, False),
        (Output("btn-export-screener-pdf", "children"),
         [html.I(className="fas fa-spinner fa-spin",
                 style={"marginRight": "5px"}), "Đang tạo PDF..."],
         [html.I(className="fas fa-file-pdf",
                 style={"marginRight": "5px"}), "PDF Danh mục"]),
        (Output("btn-export-screener-pdf", "style"),
         {"borderRadius":"6px","fontSize":"11px","padding":"4px 10px",
          "opacity":"0.6","cursor":"wait","whiteSpace":"nowrap"},
         {"borderRadius":"6px","fontSize":"11px","padding":"4px 10px",
          "opacity":"1","cursor":"pointer","whiteSpace":"nowrap"}),
    ]
)
def export_screener_pdf(n_clicks, row_data, active_filters):
    if not row_data:
        return no_update, "Bảng đang trống — hãy lọc dữ liệu trước"
    try:
        pdf_bytes = generate_screener_pdf(row_data, active_filters)
        fname = f"Vietcap_DanhMucLoc_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
        return dcc.send_bytes(pdf_bytes, fname), f"Đã xuất {len(row_data)} mã"
    except Exception as e:
        logger.error(f"Screener PDF error: {e}")
        traceback.print_exc()
        return no_update, f"Lỗi: {str(e)[:100]}"