# src/callbacks/pdf_export_callback.py
# ============================================================
# PDF EXPORT – 8-trang PHONG CÁCH Vietcap Smart ScreeneR
# ============================================================

import io, logging, traceback, math
from datetime import datetime
from dash import html
import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import matplotlib.font_manager as fm

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from dash import Input, Output, State, no_update, dcc
from src.app_instance import app
from src.backend.data_loader import (
    load_market_data, load_financial_data, get_latest_snapshot
)

logger = logging.getLogger(__name__)


# ── CẤU HÌNH PHÔNG CHỮ TIẾNG VIỆT ──────────────────────────────
def setup_fonts():
    font_path = None
    bold_font_path = None
    for f in ['Arial', 'Roboto', 'DejaVu Sans', 'Tahoma', 'Segoe UI']:
        try:
            font_path = fm.findfont(f, fallback_to_default=False)
            bold_font_path = fm.findfont(fm.FontProperties(family=f, weight='bold'), fallback_to_default=False)
            if font_path: break
        except:
            continue

    if not font_path:
        font_path = fm.findfont('DejaVu Sans')
        bold_font_path = fm.findfont(fm.FontProperties(family='DejaVu Sans', weight='bold'))

    try:
        pdfmetrics.registerFont(TTFont('VnFont', font_path))
        pdfmetrics.registerFont(TTFont('VnFont-Bold', bold_font_path))
        plt.rcParams['font.family'] = fm.FontProperties(fname=font_path).get_name()
    except Exception as e:
        logger.warning(f"Không thể thiết lập phông chữ: {e}")
        pdfmetrics.registerFont(TTFont('VnFont', fm.findfont('DejaVu Sans')))
        pdfmetrics.registerFont(TTFont('VnFont-Bold', fm.findfont('DejaVu Sans')))


setup_fonts()

# ── TRANG A4 PORTRAIT ─────────────────────────────────────────
PW, PH = A4  # 595.28 × 841.89 pt
MARGIN = 28
CW = PW - 2 * MARGIN  # content width ≈ 539 pt

# ── BẢNG MÀU CHUẨN IDX ───────────────────────────────────────
C_BG = colors.white
C_HEADER = colors.HexColor("#0a1628")  # Text chính - Navy IDX
C_TEXT = colors.HexColor("#1a2f4a")  # Text phụ
C_GREY = colors.HexColor("#5a7a99")  # Text mờ
C_LIGHT_GREY = colors.HexColor("#dce8f0")  # Viền, Grid
C_RED = colors.HexColor("#D32F2F")  # Số âm, Nến giảm (giữ cho tài chính)
C_GREEN = colors.HexColor("#00875a")  # Số dương, Nến tăng - IDX Green
C_BLUE = colors.HexColor("#0057b8")  # Line giá chính
C_ACCENT = colors.HexColor("#0090ff")  # Accent chính IDX
C_ACCENT2 = colors.HexColor("#00d4ff")  # Cyan IDX

GRADE_MAP = {"A": 5.0, "B": 4.0, "C": 3.0, "D": 2.0, "F": 1.0}


# ─────────────────────────────────────────────────────────────
# UTILITY HELPERS
# ─────────────────────────────────────────────────────────────

def _fmt(v, pct=False, bn=True, dec=1):
    try:
        if v is None or (isinstance(v, float) and math.isnan(v)): return "---"
        v = float(v)
        if pct: return f"{v:+.{dec}f}%"
        if bn and abs(v) >= 1e9: return f"{v / 1e9:,.{dec}f}B"
        if bn and abs(v) >= 1e6: return f"{v / 1e6:,.{dec}f}M"
        if bn and abs(v) >= 1e3: return f"{v / 1e3:,.{dec}f}K"
        return f"{v:,.{dec}f}"
    except:
        return str(v) if v is not None else "---"


def _img(fig, dpi=120):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight", facecolor=fig.get_facecolor())
    buf.seek(0)
    return ImageReader(buf)


def _safe(df, col):
    if df is None: return pd.Series(dtype=float)
    if col not in df.columns: return pd.Series([0.0] * len(df), index=df.index)
    return pd.to_numeric(df[col], errors="coerce")


def _pct_chg(new, old):
    try:
        if float(old) == 0: return 0
        return (float(new) - float(old)) / abs(float(old)) * 100
    except:
        return 0


def get_kpis(stock):
    val_cap = stock.get("Market Cap", 0)
    cap_str = f"{val_cap / 1e9:,.0f}" if pd.notnull(val_cap) and val_cap else "---"

    vol = stock.get("Volume", 0)
    price = stock.get("Price Close", 0)
    gtgd = (vol * price) / 1e9 if pd.notnull(vol) and pd.notnull(price) else 0
    gtgd_str = f"{gtgd:,.1f}" if gtgd else "---"

    return {
        "Vốn hóa (Tỷ)": cap_str,
        "GTGD (Tỷ)": gtgd_str,
        "P/E": _fmt(stock.get("P/E"), bn=False, dec=1),
        "P/B": _fmt(stock.get("P/B"), bn=False, dec=1),
        "Cổ tức (%)": f"{_fmt(stock.get('Dividend Yield (%)', 0), bn=False, dec=1)}",
        "Giá": _fmt(stock.get("Price Close"), bn=False, dec=1),
        "Vietcap Score": f"{GRADE_MAP.get(str(stock.get('VGM Score', 'C')), 3.0)}/5",
    }


# ─────────────────────────────────────────────────────────────
# CANVAS PRIMITIVES
# ─────────────────────────────────────────────────────────────

def _bg(c):
    c.setFillColor(C_BG)
    c.rect(0, 0, PW, PH, fill=1, stroke=0)


def _header(c, ticker, company, exchange, title: str, stock: dict):
    """Header có nền (background) siêu sang trọng và khối KPI bo góc (Card)"""

    # 1. Nền Header tổng thể
    c.setFillColor(colors.HexColor("#f0f7ff"))  # Nền xanh nhạt IDX
    c.rect(0, PH - 145, PW, 145, fill=1, stroke=0)

    # Đường viền phân cách mỏng bên dưới Header
    c.setStrokeColor(colors.HexColor("#b8d4f0"))
    c.setLineWidth(1)
    c.line(0, PH - 145, PW, PH - 145)

    # Dải màu accent ở đỉnh Header (Branding IDX Style)
    c.setFillColor(C_ACCENT)
    c.rect(0, PH - 4, PW, 4, fill=1, stroke=0)

    y_top = PH - 25

    # 2. Logo Text & Info (Top Row)
    c.setFont("VnFont-Bold", 12)
    c.setFillColor(C_ACCENT)
    c.drawString(MARGIN, y_top, "VSS")

    ticker_logo_w = pdfmetrics.stringWidth("VSS", "VnFont-Bold", 12)
    c.setFont("VnFont", 12)
    c.setFillColor(C_HEADER)
    c.drawString(MARGIN + ticker_logo_w + 3, y_top, " Smart Screener")

    c.setFont("VnFont", 8)
    c.setFillColor(C_TEXT)
    c.drawString(MARGIN + 145, y_top, "Phân tích cổ phiếu chuyên sâu - Thị trường Indonesia")

    # Góc phải: Tên báo cáo & Giờ cập nhật
    c.setFont("VnFont-Bold", 9)
    c.setFillColor(C_ACCENT)
    c.drawRightString(PW - MARGIN, y_top, title.upper())

    c.setFont("VnFont", 7.5)
    c.setFillColor(C_GREY)
    c.drawRightString(PW - MARGIN, y_top - 12, datetime.now().strftime('%d/%m/%Y %H:%M'))

    y_top -= 35

    # 3. Ticker (Cực lớn), Tên cty, Ngành
    ticker_size = 32
    c.setFont("VnFont-Bold", ticker_size)
    c.setFillColor(C_HEADER)
    c.drawString(MARGIN, y_top - 10, ticker)

    # Tính toán độ rộng của mã cổ phiếu để dịch chuyển thông tin công ty linh hoạt
    ticker_width = pdfmetrics.stringWidth(ticker, "VnFont-Bold", ticker_size)
    info_x = MARGIN + ticker_width + 15

    c.setFont("VnFont-Bold", 11)
    c.setFillColor(C_TEXT)
    c.drawString(info_x, y_top + 8, (company or "")[:60])

    c.setFont("VnFont", 8.5)
    c.setFillColor(C_GREY)
    sector = stock.get('Sector', '---')
    c.drawString(info_x, y_top - 6, f"{exchange}   |   {sector}")

    # 4. Nền khối KPI (Dạng Card bo góc màu trắng)
    kpi_y = PH - 135
    kpi_h = 45
    c.setFillColor(colors.white)
    c.setStrokeColor(colors.HexColor("#b8d4f0"))  # Viền xanh nhạt IDX
    c.setLineWidth(0.8)
    c.roundRect(MARGIN, kpi_y, PW - 2 * MARGIN, kpi_h, radius=6, fill=1, stroke=1)

    # 5. Render KPI Grid bên trong Card
    kpis = get_kpis(stock)
    if kpis:
        slot_w = (PW - 2 * MARGIN) / len(kpis)
        for i, (k, v) in enumerate(kpis.items()):
            x_center = MARGIN + i * slot_w + slot_w / 2

            # Label mờ (Size 7 nhỏ gọn để tránh đè vạch)
            c.setFont("VnFont", 7)
            c.setFillColor(C_GREY)
            c.drawCentredString(x_center, kpi_y + kpi_h - 14, str(k))

            # Value to đậm (Size 12.5 vừa vặn không tràn)
            c.setFont("VnFont-Bold", 12.5)
            fc = C_HEADER
            vs = str(v)
            if "%" in vs and k not in ["Cổ tức (%)", "ROE", "Biên ròng", "Biên gộp", "NĐTNN %"]:
                try:
                    fv = float(vs.replace('%', '').replace(',', '').replace('+', ''))
                    if fv > 0:
                        fc = C_GREEN
                    elif fv < 0:
                        fc = C_RED
                except:
                    pass

            c.setFillColor(fc)
            c.drawCentredString(x_center, kpi_y + 10, vs[:18])

            # Line phân cách dọc (Vertical separator line) giữa các chỉ số KPI
            if i < len(kpis) - 1:
                c.setStrokeColor(colors.HexColor("#E2E8F0"))
                c.setLineWidth(0.5)
                c.line(MARGIN + (i + 1) * slot_w, kpi_y + 8, MARGIN + (i + 1) * slot_w, kpi_y + kpi_h - 8)


def _footer(c, page_num):
    # Dải màu mỏng ở đáy trang
    c.setFillColor(C_ACCENT)
    c.rect(0, 0, PW, 3, fill=1, stroke=0)
    c.setFont("VnFont", 7)
    c.setFillColor(C_GREY)
    c.drawString(MARGIN, 8, "Vietcap Smart Screener – Dữ liệu mang tính tham khảo, không phải khuyến nghị đầu tư.")
    c.drawRightString(PW - MARGIN, 8, f"Trang {page_num} | idx-screener.com")


def _sec(c, text, x, y, width=None):
    """Tiêu đề section cực kỳ hiện đại với nét đỏ accent"""
    width = width or CW
    c.setFont("VnFont-Bold", 10)
    c.setFillColor(C_HEADER)
    c.drawString(x, y, text)

    # Dải viền mỏng bên dưới title
    c.setStrokeColor(C_ACCENT)  # Nét nhấn màu xanh IDX
    c.setLineWidth(1.5)
    c.line(x, y - 6, x + 25, y - 6)

    c.setStrokeColor(C_LIGHT_GREY)
    c.setLineWidth(0.5)
    c.line(x + 25, y - 6, x + width, y - 6)


def _table(c, headers, rows, x, y, widths, row_h=15, hdr_h=17, font_sz=7.5):
    """Bảng biểu có SO LE MÀU SẮC (Zebra striping) và chống đè chữ"""
    tw = sum(widths)

    # Nền Header của bảng (Xanh navy nhạt IDX)
    c.setFillColor(colors.HexColor("#eaf4ff"))
    c.rect(x, y - hdr_h, tw, hdr_h, fill=1, stroke=0)

    # Top border for header - xanh IDX
    c.setStrokeColor(C_ACCENT)
    c.setLineWidth(1.2)
    c.line(x, y, x + tw, y)
    c.setStrokeColor(colors.HexColor("#b8d4f0"))
    c.setLineWidth(0.5)
    c.line(x, y - hdr_h, x + tw, y - hdr_h)

    cx = x
    for i, (h, w) in enumerate(zip(headers, widths)):
        c.setFont("VnFont-Bold", font_sz)
        c.setFillColor(C_TEXT)
        # Tăng lề (padding) lên 4pt để tránh chữ sát mép
        if i == 0:
            c.drawString(cx + 4, y - hdr_h + 5, str(h)[:30])
        else:
            c.drawRightString(cx + w - 4, y - hdr_h + 5, str(h)[:15])
        cx += w
    y -= hdr_h

    c.setLineWidth(0.3)
    for ri, row in enumerate(rows):

        # Zebra striping: Bôi nền xám cực nhạt cho các hàng chẵn
        if ri % 2 == 0:
            c.setFillColor(colors.HexColor("#f5faff"))  # Slate 50
            c.rect(x, y - row_h, tw, row_h, fill=1, stroke=0)

        cx = x
        for ci, (cell, w) in enumerate(zip(row, widths)):
            txt = str(cell) if cell is not None else "---"
            c.setFont("VnFont", font_sz)

            fc = C_TEXT
            if ci > 0:  # Cột số liệu nếu âm thì đổi màu đỏ
                try:
                    if "-" in txt and ("%" in txt or "lần" not in txt):
                        fc = C_RED
                    elif float(txt.replace('%', '').replace(',', '')) < 0:
                        fc = C_RED
                except:
                    pass

            c.setFillColor(fc)
            # Giới hạn độ dài và canh lề chuẩn để không bị đè
            if ci == 0:
                c.drawString(cx + 4, y - row_h + 4.5, txt[:35])
            else:
                c.drawRightString(cx + w - 4, y - row_h + 4.5, txt[:20])
            cx += w

        c.setStrokeColor(C_LIGHT_GREY)
        c.line(x, y - row_h, x + tw, y - row_h)
        y -= row_h
    return y


def _embed(c, fig, x, y, w, h):
    c.drawImage(_img(fig), x, y, width=w, height=h, preserveAspectRatio=True, anchor="nw")
    plt.close(fig)


# ─────────────────────────────────────────────────────────────
# CHART BUILDERS (Chuẩn thiết kế IDX, sạch, ít màu thừa)
# ─────────────────────────────────────────────────────────────

def _format_ax(ax, title=""):
    """Định dạng trục biểu đồ VSS style"""
    ax.set_facecolor("#f8fbff")  # Nền xanh cực nhạt
    for spine in ['top', 'right']: ax.spines[spine].set_visible(False)
    for spine in ['left', 'bottom']: ax.spines[spine].set_color('#b8d4f0')
    ax.grid(True, axis='y', color='#e4f0fb', linestyle='-', linewidth=0.8)
    ax.grid(False, axis='x')
    ax.tick_params(labelsize=6.5, colors='#3a6080', length=0)
    if title:
        ax.set_title(title, fontsize=8.5, color='#0a1628', fontweight='bold', loc='left', pad=6)


def _ch_price1y(df, ticker):
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(6.0, 3.2), gridspec_kw={"height_ratios": [3, 1]}, facecolor="#ffffff")
    df = df.tail(252)
    cl = _safe(df, "Price Close").values
    vol = _safe(df, "Volume").values
    idx = range(len(cl))

    if len(cl) > 0:
        ax1.plot(idx, cl, color="#0057b8", lw=1.5, label="Giá")
        ax1.fill_between(idx, cl, min(cl) * 0.95 if min(cl) > 0 else 0, color="#0057b8", alpha=0.08)
        if len(cl) >= 20: ax1.plot(idx, pd.Series(cl).rolling(20).mean(), color="#FBC02D", lw=1.0, label="SMA20")
        if len(cl) >= 50: ax1.plot(idx, pd.Series(cl).rolling(50).mean(), color="#7c3aed", lw=1.0, label="SMA50")

    _format_ax(ax1, f"Giá cổ phiếu 1 năm")
    ax1.legend(fontsize=6, loc="best", frameon=False)
    ax1.set_xticks([])
    ax1.spines['bottom'].set_visible(False)
    ax1.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{v / 1000:.0f}K" if v >= 1000 else f"{v:.0f}"))

    if len(cl) > 0:
        vc = ["#00875a" if i == 0 or cl[i] >= cl[i - 1] else "#D32F2F" for i in range(len(vol))]
        ax2.bar(idx, vol, color=vc, alpha=0.85, width=0.8)

    _format_ax(ax2)
    ax2.set_title("Khối lượng GD", fontsize=7, color='#777777', loc='left', pad=2)
    ax2.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{v / 1e6:.0f}M"))

    fig.tight_layout(pad=0.2, h_pad=0.1)
    return fig


def _ch_candle(df):
    df = df.tail(22)
    fig, ax = plt.subplots(figsize=(6.0, 2.0), facecolor="#ffffff")
    _format_ax(ax, "1-tháng nến")
    for i, (_, r) in enumerate(df.iterrows()):
        o = float(r.get("Price Open", r.get("Price Close", 0)) or 0)
        h = float(r.get("Price High", r.get("Price Close", 0)) or 0)
        l = float(r.get("Price Low", r.get("Price Close", 0)) or 0)
        cv = float(r.get("Price Close", 0) or 0)
        col = "#00875a" if cv >= o else "#D32F2F"
        ax.plot([i, i], [l, h], color=col, lw=1.2)
        ax.add_patch(plt.Rectangle((i - 0.35, min(o, cv)), 0.7, abs(cv - o) + 0.001, color=col, alpha=0.9))
    ax.set_xticks([])
    fig.tight_layout(pad=0.2)
    return fig


def _ch_rsi(df, n=100):
    cl = _safe(df.tail(n), "Price Close")
    fig, ax = plt.subplots(figsize=(6.0, 2.0), facecolor="#ffffff")
    _format_ax(ax, "RSI(14)")
    if len(cl) > 14:
        delta = cl.diff()
        gain = delta.clip(lower=0).rolling(14).mean()
        loss = (-delta.clip(upper=0)).rolling(14).mean()
        rsi = 100 - 100 / (1 + gain / loss.replace(0, np.nan))
        ax.plot(range(len(rsi)), rsi, color="#7c3aed", lw=1.5)
        ax.axhline(70, color="#D32F2F", lw=1.0, ls="--", alpha=0.5)
        ax.axhline(30, color="#00875a", lw=1.0, ls="--", alpha=0.5)
        ax.fill_between(range(len(rsi)), rsi, 70, where=rsi >= 70, alpha=0.1, color="#D32F2F")
        ax.fill_between(range(len(rsi)), rsi, 30, where=rsi <= 30, alpha=0.1, color="#00875a")
        ax.set_ylim(0, 100)
    ax.set_xticks([])
    fig.tight_layout(pad=0.2)
    return fig


def _ch_macd(df, n=120):
    cl = _safe(df.tail(n), "Price Close")
    fig, ax = plt.subplots(figsize=(3.0, 2.0), facecolor="#ffffff")
    _format_ax(ax, "MACD")
    if len(cl) > 26:
        macd = cl.ewm(span=12, adjust=False).mean() - cl.ewm(span=26, adjust=False).mean()
        sig = macd.ewm(span=9, adjust=False).mean()
        hist = macd - sig
        idx = range(len(macd))
        ax.plot(idx, macd, color="#0057b8", lw=1.2, label="MACD")
        ax.plot(idx, sig, color="#FBC02D", lw=1.0, label="Signal")
        ax.bar(idx, hist, color=["#00875a" if h >= 0 else "#D32F2F" for h in hist], alpha=0.7, width=0.8)
        ax.axhline(0, color="#E0E0E0", lw=0.8)
        ax.legend(fontsize=6, frameon=False, loc="upper left")
    ax.set_xticks([])
    fig.tight_layout(pad=0.2)
    return fig


def _ch_mini(vals, labels, title, pct=False):
    safe = [float(v) if v is not None and not (isinstance(v, float) and math.isnan(v)) else 0 for v in vals]
    fig, ax = plt.subplots(figsize=(2.8, 1.8), facecolor="#ffffff")
    _format_ax(ax, title)
    x = range(len(safe))
    if len(safe) > 0:
        ax.bar(x, safe, color=["#00875a" if v >= 0 else "#D32F2F" for v in safe], alpha=0.85, width=0.6)
        if len(safe) >= 2:
            z = np.polyfit(range(len(safe)), safe, 1)
            ax.plot(range(len(safe)), np.poly1d(z)(range(len(safe))), color="#FBC02D", lw=1.5, ls="--", alpha=0.9)

    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, fontsize=6, rotation=30, ha="right")
    if pct: ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{v:.0f}%"))
    fig.tight_layout(pad=0.2)
    return fig


def _ch_waterfall(items, title):
    if not items: return _ch_mini([0], [""], title)
    labels, values = zip(*items)
    fig, ax = plt.subplots(figsize=(3.6, 2.2), facecolor="#ffffff")
    _format_ax(ax, title)
    running = 0
    bottoms, tops, cols = [], [], []
    for v in values:
        bottoms.append(min(running, running + v))
        tops.append(abs(v))
        cols.append("#00875a" if v >= 0 else "#D32F2F")
        running += v
    ax.bar(range(len(values)), tops, bottom=bottoms, color=cols, alpha=0.85, width=0.6)
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, fontsize=6.5, rotation=40, ha="right")
    ax.axhline(0, color="#777777", lw=0.8)
    fig.tight_layout(pad=0.2)
    return fig


def _ch_radar(cats, vals_s, vals_i):
    N = len(cats)
    angles = [n / N * 2 * math.pi for n in range(N)] + [0]
    fig, ax = plt.subplots(figsize=(3.0, 3.0), subplot_kw={"polar": True}, facecolor="#ffffff")
    ax.set_facecolor("#ffffff")

    for vals, color, label in [(vals_i, "#b8d4f0", "Ngành"), (vals_s, "#0057b8", "Cổ phiếu")]:
        v = list(vals) + [vals[0]]
        ax.plot(angles, v, color=color, lw=2.0 if label == "Cổ phiếu" else 1.5, label=label,
                linestyle='solid' if label == "Cổ phiếu" else '--')
        if label == "Cổ phiếu": ax.fill(angles, v, alpha=0.1, color=color)

    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(cats, fontsize=6.5, color="#333333")
    ax.set_ylim(0, 5);
    ax.set_yticks([1, 2, 3, 4, 5])
    ax.set_yticklabels([])  # Giấu số cho gọn
    ax.spines['polar'].set_visible(False)
    ax.grid(color='#F0F0F0', linestyle='-')
    ax.set_title("IDX Score Tổng Hợp", fontsize=9, color='#0a1628', fontweight="bold", pad=15)
    ax.legend(fontsize=6.5, loc="upper right", bbox_to_anchor=(1.35, 1.1), frameon=False)
    fig.tight_layout(pad=0.2)
    return fig


def _ch_stacked(data_dict, quarters, title):
    palette = ["#0057b8", "#00a8e8", "#00875a", "#FBC02D", "#D32F2F", "#7c3aed"]
    fig, ax = plt.subplots(figsize=(3.8, 2.2), facecolor="#ffffff")
    _format_ax(ax, title)
    x = range(len(quarters))
    bottom = np.zeros(len(quarters))
    for i, (k, vals) in enumerate(data_dict.items()):
        safe = np.array([float(v or 0) for v in vals])
        ax.bar(x, safe, bottom=bottom, label=k, color=palette[i % len(palette)], alpha=0.9, width=0.6)
        bottom += safe
    ax.set_xticks(range(len(quarters)))
    ax.set_xticklabels(quarters, fontsize=6.5, rotation=30, ha="right")
    ax.legend(fontsize=6, loc="upper left", ncol=2, frameon=False)
    fig.tight_layout(pad=0.2)
    return fig


def _ch_hbar(labels, values, title):
    palette = ["#0057b8", "#00a8e8", "#00875a", "#FBC02D", "#D32F2F", "#7c3aed", "#757575"]
    fig, ax = plt.subplots(figsize=(4.0, max(2.2, len(labels) * 0.35)), facecolor="#ffffff")
    _format_ax(ax, title)
    for i, (lbl, val) in enumerate(zip(labels, values)):
        sv = float(val or 0)
        ax.barh(i, sv, color=palette[i % len(palette)], alpha=0.85, height=0.6)
        ax.text(sv * 1.02, i, f"{sv:,.1f}", va="center", fontsize=7, color="#333333")
    ax.set_yticks(range(len(labels)))
    ax.set_yticklabels(labels, fontsize=7)
    fig.tight_layout(pad=0.2)
    return fig


def _ch_gauge(value, max_val=5, title="VGM"):
    fig, ax = plt.subplots(figsize=(2.8, 2.0), subplot_kw={"polar": True}, facecolor="#ffffff")
    theta = np.linspace(0, math.pi, 200)
    ax.plot(theta, [1] * 200, color="#F0F0F0", lw=14, solid_capstyle="round")
    ratio = min(float(value) / max_val, 1.0)
    theta_v = np.linspace(0, math.pi * ratio, 100)
    col = "#00875a" if ratio >= 0.6 else ("#D32F2F" if ratio < 0.4 else "#FBC02D")
    ax.plot(theta_v, [1] * 100, color=col, lw=14, solid_capstyle="round")
    ax.set_ylim(0, 1.5);
    ax.axis("off")
    ax.text(math.pi / 2, 0.2, f"{value:.1f}/{max_val}", ha="center", va="center", fontsize=15, fontweight="bold",
            color=col)
    ax.text(math.pi / 2, -0.2, title, ha="center", va="center", fontsize=8, color="#777777", fontweight="bold")
    fig.tight_layout(pad=0.1)
    return fig


# ─────────────────────────────────────────────────────────────
# DATA LOADERS & CALCULATORS
# ─────────────────────────────────────────────────────────────

def _prices(ticker):
    try:
        df = load_market_data()
        if df is None or df.empty: return pd.DataFrame()
        tc = next((c for c in ["ticker", "Ticker", "symbol", "Symbol"] if c in df.columns), None)
        if not tc: return pd.DataFrame()
        dc = next((c for c in ["date", "Date", "trading_date"] if c in df.columns), df.columns[0])
        return df[df[tc] == ticker].sort_values(dc).copy()
    except Exception as e:
        logger.warning(f"prices: {e}");
        return pd.DataFrame()


def _fin(ticker, period="yearly"):
    try:
        df = load_financial_data(period)
        if df is None or df.empty: return pd.DataFrame()
        tc = next((c for c in ["ticker", "Ticker", "symbol", "Symbol"] if c in df.columns), None)
        if not tc: return pd.DataFrame()

        df_res = df[df[tc] == ticker].copy()

        # --- Tự động tính toán các chỉ số phái sinh ---
        rev = _safe(df_res, "Revenue from Business Activities - Total_x")
        gp = _safe(df_res, "Gross Profit - Industrials/Property - Total")
        ni = _safe(df_res, "Net Income after Minority Interest")

        eq = _safe(df_res, "Total Shareholders' Equity incl Minority Intr & Hybrid Debt")
        if eq.sum() == 0: eq = _safe(df_res, "Common Equity - Total")

        ca = _safe(df_res, "Total Current Assets")
        cl = _safe(df_res, "Total Current Liabilities")
        std = _safe(df_res, "Short-Term Debt & Current Portion of Long-Term Debt")
        ltd = _safe(df_res, "Debt - Long-Term - Total")
        eps_col = _safe(df_res, "EPS - Basic - excl Extraordinary Items, Common - Total")

        df_res["Gross Margin"] = (gp / rev.replace(0, np.nan)) * 100
        df_res["Net Margin"] = (ni / rev.replace(0, np.nan)) * 100
        df_res["ROE"] = (ni / eq.replace(0, np.nan)) * 100
        df_res["Current Ratio"] = ca / cl.replace(0, np.nan)
        df_res["Debt to Equity"] = (std + ltd) / eq.replace(0, np.nan)
        df_res["EPS"] = eps_col

        # Xử lý Date và Period
        if 'Date' in df_res.columns:
            df_res['Date'] = pd.to_datetime(df_res['Date'], errors='coerce')
            df_res = df_res.dropna(subset=['Date']).sort_values('Date', ascending=True)
            if period == "yearly":
                df_res['Period'] = df_res['Date'].dt.year.astype(str)
            else:
                df_res['Period'] = df_res['Date'].dt.year.astype(str) + "-Q" + df_res['Date'].dt.quarter.astype(str)

        return df_res
    except Exception as e:
        logger.warning(f"fin {period}: {e}");
        return pd.DataFrame()


def _period_col(df):
    return next(
        (c for c in ["Period", "period", "Year_Quarter", "year_quarter", "Year", "year", "Quarter", "fiscal_year"] if
         c in df.columns), None)


def _periods(df, n=None):
    pc = _period_col(df)
    s = df[pc].astype(str) if pc else pd.Series([f"P{i}" for i in range(len(df))])
    return list(s.tail(n).values) if n else list(s.values)


def _col_vals(df, col, n=None, scale=1.0):
    s = _safe(df, col)
    if n: s = s.tail(n)
    return [v / scale if not math.isnan(v) else 0 for v in s.values]


# ─────────────────────────────────────────────────────────────
# PAGE FUNCTIONS
# ─────────────────────────────────────────────────────────────

def _p1(c, stock, prices_df, qtr_df):
    """Trang 1 – Phân tích kỹ thuật"""
    ticker = stock.get("Ticker", "---")
    company = stock.get("Company Common Name", "")
    _bg(c);
    _header(c, ticker, company, stock.get("Exchange", "IDX"), "Phân tích kỹ thuật", stock)

    y0 = PH - 160  # Dành nhiều không gian cho Header
    _sec(c, "Giá & Khối lượng giao dịch", MARGIN, y0)
    y0 -= 15

    left_w = CW * 0.54
    right_w = CW - left_w - 6

    # Giá 1 năm (large left)
    if not prices_df.empty:
        _embed(c, _ch_price1y(prices_df, ticker), MARGIN, y0 - 180, left_w, 180)

    # Nến & RSI (right)
    rx = MARGIN + left_w + 6
    if not prices_df.empty:
        _embed(c, _ch_candle(prices_df), rx, y0 - 85, right_w, 85)
        _embed(c, _ch_rsi(prices_df), rx, y0 - 180, right_w, 85)

    y0 -= 200

    # MACD + 3 mini financial
    _sec(c, "Chỉ báo kỹ thuật & Chỉ tiêu tài chính quý", MARGIN, y0)
    y0 -= 15

    cw4 = CW / 4 - 4
    ch = 100

    if not prices_df.empty:
        _embed(c, _ch_macd(prices_df), MARGIN, y0 - ch, cw4, ch)

    pc = _period_col(qtr_df)
    qlabs = [str(v)[-6:] for v in qtr_df[pc].tail(6).values] if pc and not qtr_df.empty else []

    FIN3 = [
        ("Revenue from Business Activities - Total_x", "Doanh thu", False),
        ("Net Income after Minority Interest", "LNST", False),
        ("Gross Margin", "Biên gộp", True),
    ]
    for i, (col, lbl, is_pct) in enumerate(FIN3):
        xi = MARGIN + (i + 1) * (cw4 + 4)
        if not qtr_df.empty and col in qtr_df.columns:
            vals = _col_vals(qtr_df, col, n=6)
            labs = qlabs if qlabs else [f"Q{j + 1}" for j in range(len(vals))]
            _embed(c, _ch_mini(vals, labs, lbl, pct=is_pct), xi, y0 - ch, cw4, ch)

    y0 -= ch + 20

    # 8 mini charts (2x4)
    _sec(c, "Xu hướng chỉ tiêu tài chính theo quý", MARGIN, y0)
    y0 -= 15

    MINIS = [
        ("Net Margin", "Biên ròng %", True),
        ("ROE", "ROE %", True),
        ("Debt to Equity", "D/E", False),
        ("Cash & Cash Equivalents - Total_x", "Tiền & TĐ", False),
        ("Trade Accounts & Trade Notes Receivable - Net", "Phải thu KH", False),
        ("Inventories - Total", "Tồn kho", False),
        ("Net Cash Flow from Operating Activities", "CFO", False),
        ("Free Cash Flow", "FCF", False),
    ]
    mw = CW / 4 - 4;
    mh = 85
    for i, (col, lbl, is_pct) in enumerate(MINIS):
        row_i = i // 4;
        col_i = i % 4
        xi = MARGIN + col_i * (mw + 4)
        yi = y0 - row_i * (mh + 15)
        if not qtr_df.empty and col in qtr_df.columns:
            vals = _col_vals(qtr_df, col, n=6)
            labs = qlabs if qlabs else [f"Q{j + 1}" for j in range(len(vals))]
        else:
            vals, labs = [0] * 6, ["---"] * 6
        _embed(c, _ch_mini(vals, labs, lbl, pct=is_pct), xi, yi - mh, mw, mh)

    _footer(c, 1)


def _p2(c, stock, yearly_df):
    """Trang 2 – Phân tích tài chính năm"""
    ticker = stock.get("Ticker", "---")
    company = stock.get("Company Common Name", "")
    _bg(c);
    _header(c, ticker, company, stock.get("Exchange", "IDX"), "Phân tích tài chính năm", stock)

    y0 = PH - 160

    if yearly_df.empty:
        c.setFont("VnFont", 10);
        c.setFillColor(C_GREY)
        c.drawCentredString(PW / 2, PH / 2, "Không có dữ liệu tài chính năm")
        _footer(c, 2);
        return

    years = _periods(yearly_df, n=7)
    df7 = yearly_df.tail(7)

    # ── Bảng KQKD ──────────────────────────────────────────────
    _sec(c, "Kết quả kinh doanh theo năm (đơn vị: Tỷ VND)", MARGIN, y0)
    y0 -= 15
    qw = min(56, (CW - 110) / max(len(years), 1))
    hdrs = ["Chỉ tiêu"] + [str(y)[-4:] for y in years]
    wids = [110] + [qw] * len(years)

    IS_ROWS = [
        ("Revenue from Business Activities - Total_x", "Doanh thu thuần", 1e9, False),
        ("Gross Profit - Industrials/Property - Total", "Lợi nhuận gộp", 1e9, False),
        ("Earnings before Interest Taxes Depreciation & Amortization", "EBITDA", 1e9, False),
        ("Net Income after Minority Interest", "LNST", 1e9, False),
        ("Gross Margin", "Biên gộp (%)", 1, True),
        ("Net Margin", "Biên ròng (%)", 1, True),
        ("ROE", "ROE (%)", 1, True),
        ("EPS", "EPS", 1, False),
        ("Debt to Equity", "D/E", 1, False),
        ("Current Ratio", "Current Ratio", 1, False),
    ]
    rows = []
    for col, lbl, scale, is_pct in IS_ROWS:
        row = [lbl]
        for _, r in df7.iterrows():
            try:
                v = float(r.get(col, 0) or 0) / scale
                row.append(f"{v:.1f}%" if is_pct else f"{v:,.1f}")
            except:
                row.append("---")
        rows.append(row)
    # Dùng font_sz nhỏ hơn xíu cho bảng nhiều cột
    y0 = _table(c, hdrs, rows, MARGIN, y0, wids, row_h=16, hdr_h=18, font_sz=7.0)
    y0 -= 20

    # ── Bảng BCĐKT ─────────────────────────────────────────────
    _sec(c, "Bảng cân đối kế toán theo năm (đơn vị: Tỷ VND)", MARGIN, y0)
    y0 -= 15
    BS_ROWS = [
        ("Cash & Cash Equivalents - Total_x", "Tiền & TĐ tiền", 1e9),
        ("Total Current Assets", "TS ngắn hạn", 1e9),
        ("Total Assets", "Tổng tài sản", 1e9),
        ("Total Current Liabilities", "Nợ ngắn hạn", 1e9),
        ("Total Liabilities", "Tổng nợ", 1e9),
        ("Total Shareholders' Equity incl Minority Intr & Hybrid Debt", "Vốn CSH", 1e9),
    ]
    bs_rows = []
    for col, lbl, scale in BS_ROWS:
        row = [lbl]
        for _, r in df7.iterrows():
            try:
                row.append(f"{float(r.get(col, 0) or 0) / scale:,.1f}")
            except:
                row.append("---")
        bs_rows.append(row)
    y0 = _table(c, hdrs, bs_rows, MARGIN, y0, wids, row_h=16, hdr_h=18, font_sz=7.0)
    y0 -= 20

    # ── 3 mini bar charts năm ───────────────────────────────────
    _sec(c, "Xu hướng tài chính theo năm", MARGIN, y0)
    y0 -= 15
    ylab = [str(y)[-4:] for y in years]
    ch_a = min(y0 - 50, 160)
    cw3 = CW / 3 - 4
    ANN = [
        ("Revenue from Business Activities - Total_x", "Doanh thu (Tỷ)", 1e9, False),
        ("Net Income after Minority Interest", "LNST (Tỷ)", 1e9, False),
        ("ROE", "ROE %", 1, True),
    ]
    for i, (col, lbl, sc, isp) in enumerate(ANN):
        xi = MARGIN + i * (cw3 + 6)
        vals = [float(v or 0) / sc for v in df7.get(col, pd.Series([0] * 7))]
        _embed(c, _ch_mini(vals, ylab, lbl, pct=isp), xi, y0 - ch_a, cw3, ch_a)

    _footer(c, 2)


def _p3(c, stock, qtr_df):
    """Trang 3 – Báo cáo quý"""
    ticker = stock.get("Ticker", "---")
    company = stock.get("Company Common Name", "")
    _bg(c);
    _header(c, ticker, company, stock.get("Exchange", "IDX"), "Báo cáo quý", stock)

    y0 = PH - 160
    if qtr_df.empty:
        c.setFont("VnFont", 10);
        c.setFillColor(C_GREY)
        c.drawCentredString(PW / 2, PH / 2, "Không có dữ liệu quý")
        _footer(c, 3);
        return

    df10 = qtr_df.tail(10)
    qtrs = _periods(df10)
    qtrs_s = [q[-6:] for q in qtrs]
    qw = min(42, (CW - 110) / max(len(qtrs), 1))
    hdrs = ["Chỉ tiêu"] + qtrs_s
    wids = [110] + [qw] * len(qtrs)

    _sec(c, "Kết quả kinh doanh theo quý (đơn vị: Tỷ VND)", MARGIN, y0)
    y0 -= 15
    QTR_ROWS = [
        ("Revenue from Business Activities - Total_x", "Doanh thu thuần", 1e9, False),
        ("Gross Profit - Industrials/Property - Total", "LN gộp", 1e9, False),
        ("Net Income after Minority Interest", "LNST", 1e9, False),
        ("Gross Margin", "Biên gộp %", 1, True),
        ("Net Margin", "Biên ròng %", 1, True),
        ("ROE", "ROE %", 1, True),
        ("Total Assets", "Tổng tài sản", 1e9, False),
        ("Total Current Liabilities", "Nợ ngắn hạn", 1e9, False),
        ("Total Shareholders' Equity incl Minority Intr & Hybrid Debt", "Vốn CSH", 1e9, False),
        ("Cash & Cash Equivalents - Total_x", "Tiền & TĐ", 1e9, False),
        ("Debt to Equity", "D/E", 1, False),
        ("Current Ratio", "Thanh toán HH", 1, False),
        ("Net Cash Flow from Operating Activities", "CFO", 1e9, False),
        ("Free Cash Flow", "FCF", 1e9, False),
    ]
    rows = []
    for col, lbl, sc, isp in QTR_ROWS:
        row = [lbl]
        for _, r in df10.iterrows():
            try:
                v = float(r.get(col, 0) or 0) / sc
                row.append(f"{v:.1f}%" if isp else f"{v:,.1f}")
            except:
                row.append("---")
        rows.append(row)
    # Bảng quý 10 cột cực hẹp nên dùng font size 6.5 để tuyệt đối tránh đè chữ
    y0 = _table(c, hdrs, rows, MARGIN, y0, wids, row_h=16, hdr_h=18, font_sz=6.5)
    y0 -= 20

    # ── 4 mini charts ──────────────────────────────────────────
    _sec(c, "Xu hướng quý", MARGIN, y0)
    y0 -= 15
    ch_q = min(y0 - 50, 160)
    cw4 = CW / 4 - 4
    Q4 = [
        ("Revenue from Business Activities - Total_x", "Doanh thu (Tỷ)", 1e9, False),
        ("Net Income after Minority Interest", "LNST (Tỷ)", 1e9, False),
        ("Gross Margin", "Biên gộp %", 1, True),
        ("Net Margin", "Biên ròng %", 1, True),
    ]
    for i, (col, lbl, sc, isp) in enumerate(Q4):
        xi = MARGIN + i * (cw4 + 4)
        vals = [float(v or 0) / sc for v in
                qtr_df.tail(10).get(col, pd.Series([0] * 10))] if col in qtr_df.columns else [0] * 10
        _embed(c, _ch_mini(vals, qtrs_s, lbl, pct=isp), xi, y0 - ch_q, cw4, ch_q)

    _footer(c, 3)


def _p4(c, stock, qtr_df):
    """Trang 4 – Phân tích Bridge"""
    ticker = stock.get("Ticker", "---")
    company = stock.get("Company Common Name", "")
    _bg(c);
    _header(c, ticker, company, stock.get("Exchange", "IDX"), "Phân tích Bridge", stock)

    y0 = PH - 160
    _sec(c, "Dòng tiền tự do (FCF) theo kỳ", MARGIN, y0)
    y0 -= 15

    cw4 = CW / 4 - 4;
    ch_wf = 120

    pc = _period_col(qtr_df)
    pds = (_periods(qtr_df.tail(3)) if not qtr_df.empty else ["Q-2", "Q-1", "YTD"])

    FCF_C = "Free Cash Flow"
    CFO_C = "Net Cash Flow from Operating Activities"
    CAP_C = "Capital Expenditures - Total_x"
    NI_C = "Net Income after Minority Interest"

    if not qtr_df.empty:
        df3 = qtr_df.tail(3)
        for i, (_, row) in enumerate(df3.iterrows()):
            ni = float(row.get(NI_C, 0) or 0) / 1e9
            cfo = float(row.get(CFO_C, 0) or 0) / 1e9
            capx = float(row.get(CAP_C, 0) or 0) / 1e9
            fcf = float(row.get(FCF_C, 0) or 0) / 1e9
            items = [("LNST", ni), ("+ CFO", cfo - ni), ("- CapEx", -abs(capx)), ("FCF", fcf)]
            xi = MARGIN + i * (cw4 + 4)
            _embed(c, _ch_waterfall(items, f"FCF {pds[i][-6:]}"), xi, y0 - ch_wf, cw4, ch_wf)

        # VLĐ bridge
        if len(qtr_df) >= 2:
            r_now = qtr_df.iloc[-1]
            r_prev = qtr_df.iloc[-2]
            CA_C = "Total Current Assets"
            CL_C = "Total Current Liabilities"
            RCV_C = "Trade Accounts & Trade Notes Receivable - Net"
            INV_C = "Inventories - Total"
            PAY_C = "Trade Accounts & Trade Notes Payable - Short-Term"
            wc_prev = float(r_prev.get(CA_C, 0) or 0) - float(r_prev.get(CL_C, 0) or 0)
            wc_now = float(r_now.get(CA_C, 0) or 0) - float(r_now.get(CL_C, 0) or 0)
            d_recv = float(r_now.get(RCV_C, 0) or 0) - float(r_prev.get(RCV_C, 0) or 0)
            d_inv = float(r_now.get(INV_C, 0) or 0) - float(r_prev.get(INV_C, 0) or 0)
            d_pay = float(r_prev.get(PAY_C, 0) or 0) - float(r_now.get(PAY_C, 0) or 0)
            wc_items = [
                ("VLĐ đầu", wc_prev / 1e9), ("Δ Phải thu", d_recv / 1e9),
                ("Δ Tồn kho", d_inv / 1e9), ("Δ Phải trả", d_pay / 1e9),
                ("VLĐ cuối", wc_now / 1e9),
            ]
            xi_wc = MARGIN + 3 * (cw4 + 4)
            _embed(c, _ch_waterfall(wc_items, "Thay đổi VLĐ"), xi_wc, y0 - ch_wf, cw4, ch_wf)

    y0 -= ch_wf + 20

    # ── Row 2: 4 CF mini bars ──────────────────────────────────
    _sec(c, "Xu hướng dòng tiền 6 quý gần nhất (đơn vị: Tỷ VND)", MARGIN, y0)
    y0 -= 15
    ch_b = 120
    cw3 = CW / 4 - 4
    CF4 = [
        ("Net Cash Flow from Operating Activities", "CFO"),
        ("Net Cash Flow from Investing Activities", "CFI"),
        ("Capital Expenditures - Total_x", "CapEx"),
        ("Free Cash Flow", "FCF"),
    ]
    if not qtr_df.empty and pc:
        qlabs6 = [q[-5:] for q in _periods(qtr_df.tail(6))]
        for i, (col, lbl) in enumerate(CF4):
            xi = MARGIN + i * (cw3 + 4)
            vals = [float(v or 0) / 1e9 for v in _safe(qtr_df.tail(6), col).values]
            _embed(c, _ch_mini(vals, qlabs6, lbl), xi, y0 - ch_b, cw3, ch_b)

    # ── Row 3: Phân tích lợi nhuận waterfall ───────────────────
    y0 -= ch_b + 20
    _sec(c, "Phân tích lợi nhuận quý gần nhất (Tỷ VND)", MARGIN, y0)
    y0 -= 15
    ch_wf2 = min(y0 - 50, 150)
    if not qtr_df.empty:
        last = qtr_df.iloc[-1]
        rev_ = float(last.get("Revenue from Business Activities - Total_x", 0) or 0) / 1e9
        cogs = float(last.get("Cost of Revenues - Total", 0) or 0) / 1e9
        gp_ = float(last.get("Gross Profit - Industrials/Property - Total", 0) or 0) / 1e9
        opex_ = float(last.get("Operating Expenses - Total", 0) or 0) / 1e9
        ni_ = float(last.get("Net Income after Minority Interest", 0) or 0) / 1e9
        items = [("Doanh thu", rev_), ("- COGS", -abs(cogs)), ("LN gộp", gp_),
                 ("- OPEX", -abs(opex_)), ("LNST", ni_)]
        _embed(c, _ch_waterfall(items, "Cầu nối DT→LNST"), MARGIN, y0 - ch_wf2, CW * 0.5, ch_wf2)

    _footer(c, 4)


def _p5(c, stock, qtr_df):
    """Trang 5 – Phân tích Bảng cân đối kế toán"""
    ticker = stock.get("Ticker", "---")
    company = stock.get("Company Common Name", "")
    _bg(c);
    _header(c, ticker, company, stock.get("Exchange", "IDX"), "Phân tích Bảng cân đối kế toán", stock)

    y0 = PH - 160
    half = CW / 2 - 4

    _sec(c, "Cơ cấu Tài sản theo quý", MARGIN, y0, width=half)
    _sec(c, "Cơ cấu Nguồn vốn theo quý", MARGIN + half + 8, y0, width=half)
    y0 -= 15

    ch_s = 130
    pc = _period_col(qtr_df)
    if not qtr_df.empty:
        df5 = qtr_df.tail(5)
        qlbs = [q[-6:] for q in _periods(df5)]

        ASSET_COLS = {
            "ĐT TC DH": "Investments - Long-Term",
            "ĐT TC NH": "Short-Term Investments - Total",
            "Phải thu": "Trade Accounts & Trade Notes Receivable - Net",
            "Tiền": "Cash & Cash Equivalents - Total_x",
            "TSCĐ": "Property Plant & Equipment - Net - Total",
        }
        LIAB_COLS = {
            "Nợ DH": "Debt - Long-Term - Total",
            "Phải trả": "Trade Accounts & Trade Notes Payable - Short-Term",
            "Nợ NH": "Short-Term Debt & Current Portion of Long-Term Debt",
            "Vốn ĐL": "Common Equity - Total",
            "LN GL": "Retained Earnings - Total",
        }
        asset_d = {k: [float(v or 0) / 1e9 for v in _safe(df5, col).values]
                   for k, col in ASSET_COLS.items() if col in df5.columns}
        liab_d = {k: [float(v or 0) / 1e9 for v in _safe(df5, col).values]
                  for k, col in LIAB_COLS.items() if col in df5.columns}

        if asset_d: _embed(c, _ch_stacked(asset_d, qlbs, "Cơ cấu Tài sản"), MARGIN, y0 - ch_s, half, ch_s)
        if liab_d:  _embed(c, _ch_stacked(liab_d, qlbs, "Cơ cấu Nguồn vốn"), MARGIN + half + 8, y0 - ch_s, half, ch_s)

    y0 -= ch_s + 20

    # ── Vốn lưu động ──────────────────────────────────────────
    _sec(c, "Vốn lưu động", MARGIN, y0, width=half)
    y0 -= 15
    ch_wc = 130

    if not qtr_df.empty:
        df6 = qtr_df.tail(6)
        qlbs6 = [q[-6:] for q in _periods(df6)]
        ca_v = [float(v or 0) / 1e9 for v in _safe(df6, "Total Current Assets").values]
        cl_v = [float(v or 0) / 1e9 for v in _safe(df6, "Total Current Liabilities").values]
        wc_v = [a - l for a, l in zip(ca_v, cl_v)]

        fig_wc, ax = plt.subplots(figsize=(3.6, 2.2), facecolor="#ffffff")
        _format_ax(ax)
        x = range(len(ca_v))
        ax.bar([i - 0.2 for i in x], ca_v, 0.35, color="#0057b8", alpha=0.85, label="TS NH")
        ax.bar([i + 0.2 for i in x], cl_v, 0.35, color="#D32F2F", alpha=0.85, label="Nợ NH")
        ax.plot(x, wc_v, color="#00875a", lw=1.5, marker="o", ms=4, label="VLĐ")
        ax.axhline(0, color="#777777", lw=0.8)
        ax.legend(fontsize=6, loc="best", frameon=False);
        ax.set_xticks(list(x));
        ax.set_xticklabels(qlbs6, fontsize=6.5, rotation=30)
        ax.set_title("Vốn lưu động (Tỷ)", fontsize=8.5, color="#222222", fontweight="bold", loc='left')
        fig_wc.tight_layout(pad=0.2)
        _embed(c, fig_wc, MARGIN, y0 - ch_wc, half, ch_wc)

        # Horizontal bar cấu trúc
        _sec(c, "Cấu trúc CĐKT kỳ gần nhất", MARGIN + half + 8, y0 + 15, width=half)
        last = qtr_df.iloc[-1]
        a_items = [
            ("ĐT TC DH", "Investments - Long-Term"),
            ("ĐT TC NH", "Short-Term Investments - Total"),
            ("Phải thu", "Trade Accounts & Trade Notes Receivable - Net"),
            ("Tiền & TĐ", "Cash & Cash Equivalents - Total_x"),
            ("TSCĐ", "Property Plant & Equipment - Net - Total"),
        ]
        al = [l for l, _ in a_items]
        av = [float(last.get(col, 0) or 0) / 1e9 for _, col in a_items]
        _embed(c, _ch_hbar(al, av, "Tài sản (Tỷ VND)"), MARGIN + half + 8, y0 - ch_wc, half, ch_wc)

    y0 -= ch_wc + 20

    # ── Bảng tóm tắt CĐKT 4 kỳ gần nhất ──────────────────────
    _sec(c, "Tóm tắt CĐKT (đơn vị: Tỷ VND)", MARGIN, y0)
    y0 -= 15
    if not qtr_df.empty:
        df4 = qtr_df.tail(4)
        q4lb = [q[-6:] for q in _periods(df4)]
        BS_SUM = [
            ("Total Assets", "Tổng tài sản"),
            ("Total Current Assets", "TS ngắn hạn"),
            ("Total Current Liabilities", "Nợ ngắn hạn"),
            ("Total Liabilities", "Tổng nợ"),
            ("Total Shareholders' Equity incl Minority Intr & Hybrid Debt", "Vốn CSH"),
            ("Debt to Equity", "D/E"),
        ]
        rows = []
        for col, lbl in BS_SUM:
            row = [lbl]
            for _, r in df4.iterrows():
                try:
                    v = float(r.get(col, 0) or 0)
                    if col == "Debt to Equity":
                        row.append(f"{v:.2f}")
                    else:
                        row.append(f"{v / 1e9:,.1f}")
                except:
                    row.append("---")
            rows.append(row)
        cw_bs = (CW - 110) / 4
        _table(c, ["Chỉ tiêu"] + q4lb, rows, MARGIN, y0, [110] + [cw_bs] * 4, row_h=16, hdr_h=18, font_sz=7.5)

    _footer(c, 5)


def _p6(c, stock, qtr_df):
    """Trang 6 – Phân tích Kết quả kinh doanh"""
    ticker = stock.get("Ticker", "---")
    company = stock.get("Company Common Name", "")
    _bg(c);
    _header(c, ticker, company, stock.get("Exchange", "IDX"), "Phân tích Kết quả kinh doanh", stock)

    y0 = PH - 160

    # ── Bảng lũy kế (TTM) ──────────────────────────────────────
    _sec(c, "Kết quả kinh doanh lũy kế 4 quý gần nhất (TTM)", MARGIN, y0)
    y0 -= 15

    if not qtr_df.empty:
        df4 = qtr_df.tail(4);
        df4p = qtr_df.iloc[-8:-4] if len(qtr_df) >= 8 else pd.DataFrame()
        TTM = [
            ("Revenue from Business Activities - Total_x", "Doanh thu thuần"),
            ("Gross Profit - Industrials/Property - Total", "Lợi nhuận gộp"),
            ("Earnings before Interest Taxes Depreciation & Amortization", "EBITDA"),
            ("Net Income after Minority Interest", "Lợi nhuận sau thuế"),
        ]
        for lbl_col, lbl in TTM:
            cur = _safe(df4, lbl_col).sum()
            prev = _safe(df4p, lbl_col).sum() if not df4p.empty else 0
            chg = _pct_chg(cur, prev)
            c.setFont("VnFont-Bold", 8);
            c.setFillColor(C_TEXT)
            c.drawString(MARGIN, y0, lbl)
            c.setFont("VnFont", 8)
            c.drawString(MARGIN + 145, y0, _fmt(cur))
            c.setFillColor(C_GREEN if chg > 0 else C_RED)
            c.drawString(MARGIN + 230, y0, f"{chg:+.1f}%" if prev else "---")
            y0 -= 18
        y0 -= 6

    # ── 4 chart quý: DT, LNST, Biên gộp, Biên ròng ───────────
    _sec(c, "Xu hướng quý", MARGIN, y0)
    y0 -= 15
    cw4 = CW / 4 - 4;
    ch4 = 130
    pc = _period_col(qtr_df)
    df_tail10 = qtr_df.tail(10) if not qtr_df.empty else pd.DataFrame()
    n_rows = len(df_tail10)
    ql10 = [q[-5:] for q in _periods(df_tail10)] if n_rows > 0 else []
    Q4C = [
        ("Revenue from Business Activities - Total_x", "Doanh thu (Tỷ)", 1e9, False),
        ("Net Income after Minority Interest", "LNST (Tỷ)", 1e9, False),
        ("Gross Margin", "Biên gộp %", 1, True),
        ("Net Margin", "Biên ròng %", 1, True),
    ]
    for i, (col, lbl, sc, isp) in enumerate(Q4C):
        xi = MARGIN + i * (cw4 + 4)
        if not qtr_df.empty and col in qtr_df.columns:
            vals = [float(v or 0) / sc for v in _safe(df_tail10, col).values]
        else:
            vals = [0] * n_rows  # match actual row count, not hardcoded 10
        labs = ql10 if ql10 else [f"Q{j}" for j in range(len(vals))]
        # Guard: ensure vals and labs have same length
        min_len = min(len(vals), len(labs))
        _embed(c, _ch_mini(vals[:min_len], labs[:min_len], lbl, pct=isp), xi, y0 - ch4, cw4, ch4)
    y0 -= ch4 + 20

    # ── Hiệu quả kinh doanh combo chart ───────────────────────
    _sec(c, "Lợi nhuận gộp & biên lợi nhuận theo quý", MARGIN, y0)
    y0 -= 15
    ch5 = min(y0 - 50, 180)
    if not qtr_df.empty and n_rows > 0:
        df10 = df_tail10
        gp_v = [float(v or 0) / 1e9 for v in _safe(df10, "Gross Profit - Industrials/Property - Total").values]
        ni_v = [float(v or 0) / 1e9 for v in _safe(df10, "Net Income after Minority Interest").values]
        gm_v = [float(v) if not (v != v) else 0.0 for v in _safe(df10, "Gross Margin").values]
        nm_v = [float(v) if not (v != v) else 0.0 for v in _safe(df10, "Net Margin").values]

        # Guard: all series must have same length
        n = min(len(gp_v), len(ni_v), len(gm_v), len(nm_v), len(ql10)) if ql10 else \
            min(len(gp_v), len(ni_v), len(gm_v), len(nm_v))
        gp_v, ni_v, gm_v, nm_v = gp_v[:n], ni_v[:n], gm_v[:n], nm_v[:n]
        x_labels = ql10[:n] if ql10 else [f"Q{j}" for j in range(n)]

        fig_combo, ax1 = plt.subplots(figsize=(6.0, 3.0), facecolor="#ffffff")
        ax2 = ax1.twinx()
        _format_ax(ax1)
        ax2.spines['top'].set_visible(False)
        ax2.spines['bottom'].set_visible(False)
        ax2.spines['left'].set_visible(False)
        ax2.spines['right'].set_visible(False)

        x = range(n)
        ax1.bar([i - 0.2 for i in x], gp_v, 0.35, color="#0057b8", alpha=0.85, label="LN gộp (Tỷ)")
        ax1.bar([i + 0.2 for i in x], ni_v, 0.35, color="#00a8e8", alpha=0.85, label="LNST (Tỷ)")
        ax2.plot(list(x), gm_v, color="#D32F2F", lw=1.5, ls="--", label="Biên gộp %")
        ax2.plot(list(x), nm_v, color="#00875a", lw=1.5, ls="-", label="Biên ròng %")
        ax1.set_xticks(list(x));
        ax1.set_xticklabels(x_labels, fontsize=6.5, rotation=30)
        ax2.tick_params(labelsize=6.5, length=0, colors="#555555")
        ax1.set_title("Lợi nhuận & Biên lợi nhuận", fontsize=8.5, color="#222222", fontweight="bold", loc='left')
        lines1, labels1 = ax1.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax1.legend(lines1 + lines2, labels1 + labels2, fontsize=6, loc="upper left", frameon=False)
        fig_combo.tight_layout(pad=0.2)
        _embed(c, fig_combo, MARGIN, y0 - ch5, CW * 0.7, ch5)

    _footer(c, 6)


def _p7(c, stock):
    """Trang 7 – Xếp hạng & Định giá"""
    ticker = stock.get("Ticker", "---")
    company = stock.get("Company Common Name", "")
    _bg(c);
    _header(c, ticker, company, stock.get("Exchange", "IDX"), "Xếp hạng & Định giá", stock)

    y0 = PH - 160
    half = CW / 2 - 4

    # ── Radar + bảng rating ────────────────────────────────────
    _sec(c, "Xếp hạng doanh nghiệp", MARGIN, y0, width=half)
    y0 -= 15

    sv = [GRADE_MAP.get(str(stock.get("Value Score", "C")), 3.0),
          GRADE_MAP.get(str(stock.get("Growth Score", "C")), 3.0),
          GRADE_MAP.get(str(stock.get("Momentum Score", "C")), 3.0),
          GRADE_MAP.get(str(stock.get("VGM Score", "C")), 3.0), 3.0, 3.0]
    ia = [3.0] * 6

    rh = 150
    _embed(c, _ch_radar(["Giá trị", "Tăng trưởng", "Momentum", "VGM", "Rev Gr.", "EPS Gr."], sv, ia), MARGIN, y0 - rh,
           half * 0.58, rh)

    RATING = [
        ["Value Score", str(stock.get("Value Score", "---"))],
        ["Growth Score", str(stock.get("Growth Score", "---"))],
        ["Momentum Score", str(stock.get("Momentum Score", "---"))],
        ["VGM Score", str(stock.get("VGM Score", "---"))],
        ["IDX Score", f"{GRADE_MAP.get(str(stock.get('VGM Score', 'C')), 3.0)}/5"],
        ["Beta", _fmt(stock.get("Beta"), bn=False)],
        ["RS 1M %", _fmt(stock.get("RS_1M"), bn=False, pct=True)],
        ["RS 3M %", _fmt(stock.get("RS_3M"), bn=False, pct=True)],
        ["RS 1Y %", _fmt(stock.get("RS_1Y"), bn=False, pct=True)],
    ]
    _table(c, ["Chỉ tiêu", "Giá trị"], RATING, MARGIN + half * 0.55, y0, [half * 0.28, half * 0.17], row_h=16, hdr_h=18,
           font_sz=7.5)

    y0 -= rh + 20

    # ── Định giá (left) + Cơ bản (right) ─────────────────────
    _sec(c, "Chỉ số định giá", MARGIN, y0, width=half)
    _sec(c, "Chỉ tiêu cơ bản", MARGIN + half + 8, y0, width=half)
    y0 -= 15

    VAL = [
        ["P/E", _fmt(stock.get("P/E"), bn=False), "lần"],
        ["P/B", _fmt(stock.get("P/B"), bn=False), "lần"],
        ["EV/EBITDA", _fmt(stock.get("EV/EBITDA"), bn=False), "lần"],
        ["Div. Yield", _fmt(stock.get("Dividend Yield (%)"), bn=False), "%"],
        ["P/S", _fmt(stock.get("P/S"), bn=False), "lần"],
        ["EPS", _fmt(stock.get("EPS"), bn=False), "VND"],
        ["BVPS", _fmt(stock.get("BVPS"), bn=False), "VND"],
        ["Market Cap", _fmt(stock.get("Market Cap")), ""],
    ]
    yw_v = y0
    _table(c, ["Chỉ số", "Giá trị", "ĐV"], VAL, MARGIN, yw_v, [half * 0.45, half * 0.35, half * 0.2], row_h=16,
           hdr_h=18, font_sz=7.5)

    FUND = [
        ["ROE", f"{_fmt(stock.get('ROE (%)'), bn=False)}%"],
        ["ROA", f"{_fmt(stock.get('ROA'), bn=False)}%"],
        ["Biên gộp", f"{_fmt(stock.get('Gross Margin (%)'), bn=False)}%"],
        ["Biên ròng", f"{_fmt(stock.get('Net Margin (%)'), bn=False)}%"],
        ["D/E", _fmt(stock.get("D/E"), bn=False)],
        ["Current Ratio", _fmt(stock.get("Current Ratio"), bn=False)],
        ["Rev Growth YoY", f"{_fmt(stock.get('Revenue Growth YoY (%)'), bn=False)}%"],
        ["EPS Growth YoY", f"{_fmt(stock.get('EPS Growth YoY (%)'), bn=False)}%"],
        ["CANSLIM Score", str(round(stock.get("CANSLIM Score", 0) or 0, 1))],
        ["Perf 1W", f"{_fmt(stock.get('Perf_1W'), bn=False)}%"],
    ]
    _table(c, ["Chỉ tiêu", "Giá trị"], FUND, MARGIN + half + 8, yw_v, [half * 0.6, half * 0.4], row_h=16, hdr_h=18,
           font_sz=7.5)

    y0 -= (max(len(VAL), len(FUND)) * 16 + 18) + 20

    # ── Gauge VGM + thông tin tóm tắt ─────────────────────────
    _sec(c, "Điểm tổng hợp VSS Score", MARGIN, y0)
    y0 -= 15
    vgm_n = GRADE_MAP.get(str(stock.get("VGM Score", "C")), 3.0)
    _embed(c, _ch_gauge(vgm_n, 5, "VSS Score"), MARGIN, y0 - 100, 140, 100)

    c.setFont("VnFont", 9)
    c.setFillColor(C_TEXT)
    info_lines = [
        f"Ngành: {stock.get('Sector', '')} / {stock.get('Industry', '')}",
        f"Sàn: {stock.get('Exchange', 'IDX')}",
        f"Vốn hóa: {_fmt(stock.get('Market Cap'))} VND",
        f"Giá hiện tại: {_fmt(stock.get('Price Close'), bn=False)} VND",
        f"52W Hi: {_fmt(stock.get('High_52W'), bn=False)} | Lo: {_fmt(stock.get('Low_52W'), bn=False)}",
    ]
    for ln in info_lines:
        c.drawString(MARGIN + 160, y0 - 20, ln);
        y0 -= 18

    _footer(c, 7)


def _p8(c, stock, prices_df):
    """Trang 8 – Tổng hợp tín hiệu kỹ thuật"""
    ticker = stock.get("Ticker", "---")
    company = stock.get("Company Common Name", "")
    _bg(c);
    _header(c, ticker, company, stock.get("Exchange", "IDX"), "Tổng hợp tín hiệu kỹ thuật", stock)

    y0 = PH - 160
    half = CW / 2 - 4

    # ── Bảng tín hiệu + MA ────────────────────────────────────
    _sec(c, "Tín hiệu kỹ thuật", MARGIN, y0, width=half)
    _sec(c, "Đường trung bình động", MARGIN + half + 8, y0, width=half)
    y0 -= 15

    price_now = float(stock.get("Price Close", 0) or 0)

    def ma_sig(ma_key):
        mv = float(stock.get(ma_key, 0) or 0)
        return "Mua" if price_now > mv and mv > 0 else "Bán"

    SIG_ROWS = [
        ["RSI(14)", _fmt(stock.get("RSI_14"), bn=False),
         "Mua" if float(stock.get("RSI_14", 50) or 50) < 30 else (
             "Bán" if float(stock.get("RSI_14", 50) or 50) > 70 else "Tr.Tính")],
        ["MACD Hist.", _fmt(stock.get("MACD_Histogram"), bn=False),
         "Mua" if float(stock.get("MACD_Histogram", 0) or 0) > 0 else "Bán"],
        ["BB Width", _fmt(stock.get("BB_Width"), bn=False), "Tr.Tính"],
        ["Consec. Up", str(int(stock.get("Consec_Up", 0) or 0)),
         "Mua" if int(stock.get("Consec_Up", 0) or 0) > 2 else "---"],
        ["Consec.Down", str(int(stock.get("Consec_Down", 0) or 0)),
         "Bán" if int(stock.get("Consec_Down", 0) or 0) > 2 else "---"],
        ["RS 1M %", _fmt(stock.get("RS_1M"), bn=False, pct=True),
         "Mua" if float(stock.get("RS_1M", 0) or 0) > 0 else "Bán"],
        ["RS 3M %", _fmt(stock.get("RS_3M"), bn=False, pct=True),
         "Mua" if float(stock.get("RS_3M", 0) or 0) > 0 else "Bán"],
    ]
    MA_ROWS = [
        ["SMA5", _fmt(stock.get("SMA5"), bn=False), ma_sig("SMA5")],
        ["SMA10", _fmt(stock.get("SMA10"), bn=False), ma_sig("SMA10")],
        ["SMA20", _fmt(stock.get("SMA20"), bn=False), ma_sig("SMA20")],
        ["SMA50", _fmt(stock.get("SMA50"), bn=False), ma_sig("SMA50")],
        ["SMA100", _fmt(stock.get("SMA100"), bn=False), ma_sig("SMA100")],
        ["SMA200", _fmt(stock.get("SMA200"), bn=False), ma_sig("SMA200")],
    ]

    _table(c, ["Chỉ báo", "Giá trị", "Tín hiệu"], SIG_ROWS, MARGIN, y0, [half * 0.42, half * 0.28, half * 0.3],
           row_h=16, hdr_h=18, font_sz=7.5)
    _table(c, ["MA", "Giá trị", "Tín hiệu"], MA_ROWS, MARGIN + half + 8, y0, [half * 0.34, half * 0.36, half * 0.3],
           row_h=16, hdr_h=18, font_sz=7.5)

    y0 -= (max(len(SIG_ROWS), len(MA_ROWS)) * 16 + 18) + 20

    # ── 3 charts row 1: Giá vs MA, RSI, MACD ─────────────────
    if not prices_df.empty and len(prices_df) >= 30:
        cw3 = CW / 3 - 4;
        ch3 = 120

        _sec(c, "Giá vs MA(5) & MA(20)", MARGIN, y0)
        _sec(c, "RSI(14)", MARGIN + cw3 + 4, y0)
        _sec(c, "MACD", MARGIN + 2 * (cw3 + 4), y0)
        y0 -= 15

        df60 = prices_df.tail(60)
        cl = _safe(df60, "Price Close").values
        fig_pma, ax = plt.subplots(figsize=(3.6, 2.5), facecolor="#ffffff")
        _format_ax(ax)
        ax.plot(range(len(cl)), cl, color="#0057b8", lw=1.5, label="Giá")
        if len(cl) >= 5: ax.plot(range(len(cl)), pd.Series(cl).rolling(5).mean(), color="#00875a", lw=1.2, ls="--",
                                 label="MA5")
        if len(cl) >= 20: ax.plot(range(len(cl)), pd.Series(cl).rolling(20).mean(), color="#D32F2F", lw=1.2, ls="--",
                                  label="MA20")
        ax.legend(fontsize=6, frameon=False);
        ax.set_xticks([])
        fig_pma.tight_layout(pad=0.2)
        _embed(c, fig_pma, MARGIN, y0 - ch3, cw3, ch3)
        _embed(c, _ch_rsi(prices_df.tail(60)), MARGIN + cw3 + 4, y0 - ch3, cw3, ch3)
        _embed(c, _ch_macd(prices_df.tail(80)), MARGIN + 2 * (cw3 + 4), y0 - ch3, cw3, ch3)
        y0 -= ch3 + 20

        # ── 3 charts row 2: STOCH, Bollinger, ADX ────────────
        _sec(c, "STOCH(14,3)", MARGIN, y0)
        _sec(c, "Giá vs Bollinger Band", MARGIN + cw3 + 4, y0)
        _sec(c, "ADX(14)", MARGIN + 2 * (cw3 + 4), y0)
        y0 -= 15
        ch3b = 120
        cl60 = _safe(prices_df.tail(60), "Price Close")
        hi60 = _safe(prices_df.tail(60), "Price High")
        lo60 = _safe(prices_df.tail(60), "Price Low")

        # STOCH
        try:
            lo14 = lo60.rolling(14).min();
            hi14 = hi60.rolling(14).max()
            sk = 100 * (cl60 - lo14) / (hi14 - lo14 + 1e-9)
            sd = sk.rolling(3).mean()
            fig_st, ax = plt.subplots(figsize=(3.6, 2.5), facecolor="#ffffff")
            _format_ax(ax)
            ax.plot(range(len(sk)), sk, color="#0057b8", lw=1.5, label="%K")
            ax.plot(range(len(sd)), sd, color="#D32F2F", lw=1.2, ls="--", label="%D")
            ax.axhline(80, color="#D32F2F", lw=1.0, ls="--", alpha=0.5)
            ax.axhline(20, color="#00875a", lw=1.0, ls="--", alpha=0.5)
            ax.set_ylim(0, 100);
            ax.legend(fontsize=6, frameon=False);
            ax.set_xticks([])
            fig_st.tight_layout(pad=0.2)
            _embed(c, fig_st, MARGIN, y0 - ch3b, cw3, ch3b)
        except:
            pass

        # Bollinger
        try:
            s20 = cl60.rolling(20).mean();
            sd20 = cl60.rolling(20).std()
            ub = s20 + 2 * sd20;
            lb = s20 - 2 * sd20
            fig_bb, ax = plt.subplots(figsize=(3.6, 2.5), facecolor="#ffffff")
            _format_ax(ax)
            idx = range(len(cl60))
            ax.plot(idx, cl60, color="#0057b8", lw=1.5)
            ax.plot(idx, ub, color="#777777", lw=1.0, ls="--")
            ax.plot(idx, lb, color="#777777", lw=1.0, ls="--")
            ax.fill_between(idx, lb, ub, alpha=0.1, color="#0057b8")
            ax.set_xticks([])
            fig_bb.tight_layout(pad=0.2)
            _embed(c, fig_bb, MARGIN + cw3 + 4, y0 - ch3b, cw3, ch3b)
        except:
            pass

        # ADX
        try:
            hv = hi60.values;
            lv = lo60.values;
            cv = cl60.values
            tr = np.maximum.reduce([hv[1:] - lv[1:], np.abs(hv[1:] - cv[:-1]), np.abs(lv[1:] - cv[:-1])])
            atr = pd.Series(tr).rolling(14).mean()
            adx = atr / (cv[1:].mean() + 1e-9) * 100
            fig_adx, ax = plt.subplots(figsize=(3.6, 2.5), facecolor="#ffffff")
            _format_ax(ax)
            ax.plot(range(len(adx)), adx, color="#7c3aed", lw=1.5)
            ax.axhline(25, color="#D32F2F", lw=1.0, ls="--", alpha=0.5)
            ax.set_xticks([])
            fig_adx.tight_layout(pad=0.2)
            _embed(c, fig_adx, MARGIN + 2 * (cw3 + 4), y0 - ch3b, cw3, ch3b)
        except:
            pass

    _footer(c, 8)


# ─────────────────────────────────────────────────────────────
# MAIN GENERATOR
# ─────────────────────────────────────────────────────────────

def generate_pdf(stock: dict) -> bytes:
    ticker = stock.get("Ticker", "STOCK")
    logger.info(f"PDF export: {ticker}")
    prices_df = _prices(ticker)
    yearly_df = _fin(ticker, "yearly")
    qtr_df = _fin(ticker, "quarterly")

    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=A4)
    c.setTitle(f"Vietcap Smart Screener – Báo cáo phân tích {ticker}")
    c.setAuthor("Vietcap Smart Screener")
    c.setSubject(f"Phân tích cổ phiếu {ticker} – Vietnamese Stock Exchange")

    PAGE_FNS = [
        lambda: _p1(c, stock, prices_df, qtr_df),
        lambda: _p2(c, stock, yearly_df),
        lambda: _p3(c, stock, qtr_df),
        lambda: _p4(c, stock, qtr_df),
        lambda: _p5(c, stock, qtr_df),
        lambda: _p6(c, stock, qtr_df),
        lambda: _p7(c, stock),
        lambda: _p8(c, stock, prices_df),
    ]

    for i, fn in enumerate(PAGE_FNS):
        try:
            fn()
        except Exception as e:
            logger.error(f"Page {i + 1} error: {e}");
            traceback.print_exc()
            _bg(c)
            c.setFont("VnFont", 11)
            c.setFillColor(C_RED)
            c.drawCentredString(PW / 2, PH / 2, f"Lỗi trang {i + 1}: {str(e)[:80]}")
        c.showPage()

    c.save()
    buf.seek(0)
    return buf.read()


# ─────────────────────────────────────────────────────────────
# DASH CALLBACK
# ─────────────────────────────────────────────────────────────

@app.callback(
    [Output("pdf-download", "data"),
     Output("pdf-export-status", "children")],
    Input("btn-export-pdf", "n_clicks"),
    State("screener-table", "selectedRows"),
    prevent_initial_call=True,
    # 🟢 TUYỆT CHIÊU RUNNING: Tự động đổi giao diện khi đang xử lý
    # ================================================================
    running=[
        # 1. KHÓA NÚT: Chống người dùng spam click đúp làm sập server
        (Output("btn-export-pdf", "disabled"), True, False),

        # 2. ĐỔI NỘI DUNG: Chữ "PDF" -> Icon vòng xoay mượt mà
        (Output("btn-export-pdf", "children"),
         html.I(className="fas fa-spinner fa-spin", style={"fontSize": "15px"}),  # Lúc đang chạy
         "PDF"),  # Trả về khi xong

        # 3. LÀM MỜ NÚT: Đổi Style giảm opacity (độ sáng) xuống 50%
        (Output("btn-export-pdf", "style"),
         {
             "width": "30px", "height": "30px", "backgroundColor": "#D32F2F",
             "color": "#fff", "border": "none", "borderRadius": "4px",
             "fontSize": "13px", "fontWeight": "700", "flexShrink": "0",
             "marginRight": "10px", "display": "inline-flex",
             "alignItems": "center", "justifyContent": "center", "verticalAlign": "middle",
             "opacity": "0.5", "cursor": "wait", "boxShadow": "none"  # 🔴 Nút mờ đi và tắt bóng đổ
         },
         {
             "width": "30px", "height": "30px", "backgroundColor": "#D32F2F",
             "color": "#fff", "border": "none", "borderRadius": "4px",
             "fontSize": "13px", "fontWeight": "700", "cursor": "pointer",
             "flexShrink": "0", "marginRight": "10px", "display": "inline-flex",
             "alignItems": "center", "justifyContent": "center", "verticalAlign": "middle",
             "boxShadow": "0 2px 8px rgba(211,47,47,0.45)", "opacity": "1"  # 🟢 Trở lại bình thường
         })
    ]
)
def export_pdf_report(n_clicks, selected_rows):
    if not selected_rows:
        return no_update, "⚠️ Vui lòng chọn một cổ phiếu trong bảng để xuất PDF"
    stock = selected_rows[0]
    ticker = stock.get("Ticker", "STOCK")
    try:
        pdf_bytes = generate_pdf(stock)
        fname = f"BaoCaoTVDT_Vietcap_{ticker}_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
        return dcc.send_bytes(pdf_bytes, fname), f"✅ Đã xuất: {fname}"
    except Exception as e:
        logger.error(f"PDF export fail: {e}");
        traceback.print_exc()
        return no_update, f"❌ Lỗi xuất PDF: {str(e)[:120]}"