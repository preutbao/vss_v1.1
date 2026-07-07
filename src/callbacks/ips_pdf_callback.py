# src/callbacks/ips_pdf_callback.py
# ══════════════════════════════════════════════════════════════
# IPS PROFILE PDF  —  Vietcap Smart Screener
# Xuất báo cáo hồ sơ nhà đầu tư 1 trang A4 sau onboarding.
#
# Reuse toàn bộ primitives từ screener_pdf_callback.py:
#   _footer(), _kpi_card(), _sec_title(), _table_draw(),
#   _draw_vgm_badge(), font setup, color constants.
#
# Layout 1 trang:
#   [HEADER]
#   [SECTION 1] Kết quả trắc nghiệm  — 4 KPI card + 2 info row + bucket bar
#   [SECTION 2] Khuyến nghị hệ thống — text box chiến lược + filter tags
#   [SECTION 3] Top 3 cổ phiếu phù hợp — bảng 3 dòng
#   [FOOTER]
# ══════════════════════════════════════════════════════════════

import io, os, math, logging
from datetime import datetime

import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.pdfbase import pdfmetrics

from dash import Input, Output, State, no_update, dcc
from src.app_instance import app

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────
# IMPORT SHARED PRIMITIVES từ screener_pdf_callback
# Tất cả font, màu, helper đều lấy từ đây để đồng bộ template
# ──────────────────────────────────────────────────────────────
try:
    from src.callbacks.screener_pdf_callback import (
        # Font & setup (đã chạy khi import module)
        _setup_fonts, _apply_mpl_style,
        # Canvas primitives
        _footer, _kpi_card, _sec_title, _table_draw,
        _draw_vgm_badge, _bg, _ai_box, _styled_ax, _embed,
        # Helpers
        _fmt, _sv, _company_name, _get_vn_name_map,
        # Constants
        PW, PH, MARGIN, CW, FOOTER_H, Y_MIN,
        C_BG, C_HEADER_DARK, C_HEADER_MID, C_TEXT,
        C_GREY, C_LIGHT_GREY, C_RED, C_GREEN, C_BLUE,
        C_ACCENT, C_ACCENT2, C_AMBER, C_PURPLE,
        C_PURPLE_SOFT, C_PURPLE_BORDER,
        C_BLUE_SOFT, C_BLUE_BORDER,
        C_GREEN_SOFT, C_GREEN_BORDER,
        C_AMBER_SOFT, C_AMBER_BORDER,
        C_RED_SOFT, C_RED_BORDER,
        C_HDR_TABLE, C_HDR_TEXT,
        C_STRIPE_EVEN, C_STRIPE_ODD,
        VGM_COLORS_RL,
    )
    _SHARED_OK = True
except ImportError as _e:
    logger.warning(f"[IPS PDF] Không import được shared primitives: {_e}")
    _SHARED_OK = False

# ──────────────────────────────────────────────────────────────
# FALLBACK nếu import thất bại (tự định nghĩa tối thiểu)
# ──────────────────────────────────────────────────────────────
if not _SHARED_OK:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfbase.ttfonts import TTFont
    import matplotlib; matplotlib.use("Agg")

    PW, PH = A4
    MARGIN = 28
    CW     = PW - 2 * MARGIN
    FOOTER_H = 20
    Y_MIN    = FOOTER_H + 10

    C_BG          = colors.white
    C_HEADER_DARK = colors.HexColor("#0A1628")
    C_TEXT        = colors.HexColor("#1A2F4A")
    C_GREY        = colors.HexColor("#5A7A99")
    C_LIGHT_GREY  = colors.HexColor("#D8E8F2")
    C_RED         = colors.HexColor("#C62828")
    C_GREEN       = colors.HexColor("#1B7A4A")
    C_BLUE        = colors.HexColor("#1565C0")
    C_ACCENT      = colors.HexColor("#0078D4")
    C_ACCENT2     = colors.HexColor("#00B4D8")
    C_AMBER       = colors.HexColor("#E65100")
    C_PURPLE      = colors.HexColor("#6A0DAD")
    C_PURPLE_SOFT   = colors.HexColor("#F5F0FF")
    C_PURPLE_BORDER = colors.HexColor("#D1B3F8")
    C_BLUE_SOFT   = colors.HexColor("#EEF4FF")
    C_BLUE_BORDER = colors.HexColor("#BBDEFB")
    C_GREEN_SOFT  = colors.HexColor("#F0FBF5")
    C_GREEN_BORDER= colors.HexColor("#A5D6B8")
    C_AMBER_SOFT  = colors.HexColor("#FFF8F0")
    C_AMBER_BORDER= colors.HexColor("#FFCC80")
    C_RED_SOFT    = colors.HexColor("#FFF3F3")
    C_RED_BORDER  = colors.HexColor("#FFCDD2")
    C_HDR_TABLE   = colors.HexColor("#0E2040")
    C_HDR_TEXT    = colors.white
    C_STRIPE_EVEN = colors.HexColor("#F4F9FF")
    C_STRIPE_ODD  = colors.white
    VGM_COLORS_RL = {
        "A": C_GREEN, "B": C_BLUE,
        "C": C_AMBER, "D": C_AMBER, "F": C_RED,
    }

    def _setup_fonts():
        _CANDIDATES = [
            ("C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/arialbd.ttf"),
            ("/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
             "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf"),
            ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
             "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
        ]
        for reg, bold in _CANDIDATES:
            if os.path.exists(reg):
                b = bold if os.path.exists(bold) else reg
                try:
                    pdfmetrics.registerFont(TTFont("VnFont",      reg))
                    pdfmetrics.registerFont(TTFont("VnFont-Bold", b))
                    return
                except Exception:
                    continue
    _setup_fonts()

    def _fmt(v, dec=1, pct=False, sign=False):
        try:
            if v is None or (isinstance(v, float) and math.isnan(v)): return "---"
            v = float(v); pfx = "+" if (sign and v > 0) else ""
            if pct: return f"{pfx}{v:.{dec}f}%"
            if abs(v) >= 1e9: return f"{pfx}{v/1e9:,.{dec}f}B"
            if abs(v) >= 1e6: return f"{pfx}{v/1e6:,.{dec}f}M"
            return f"{pfx}{v:,.{dec}f}"
        except Exception:
            return str(v) if v is not None else "---"

    def _bg(c):
        c.setFillColor(C_BG)
        c.rect(0, 0, PW, PH, fill=1, stroke=0)

    def _footer(c, page_num, total=1):
        c.setFillColor(C_ACCENT)
        c.rect(0, 0, PW * 0.6, 4, fill=1, stroke=0)
        c.setFillColor(C_ACCENT2)
        c.rect(PW * 0.6, 0, PW * 0.4, 4, fill=1, stroke=0)
        c.setFont("VnFont", 6.5); c.setFillColor(colors.HexColor("#9CA3AF"))
        c.drawString(MARGIN, 8, "Vietcap Smart Screener – Báo cáo Hồ sơ Nhà đầu tư")
        c.drawRightString(PW - MARGIN, 8,
            f"Trang {page_num}/{total}  ·  {datetime.now().strftime('%d/%m/%Y %H:%M')}")

    def _kpi_card(c, x, y, w, h, label, value, accent_color, icon=""):
        c.setFillColor(colors.white)
        c.setStrokeColor(colors.HexColor("#C8DDEF")); c.setLineWidth(0.6)
        c.roundRect(x, y, w, h, radius=5, fill=1, stroke=1)
        c.setFillColor(accent_color)
        c.roundRect(x, y + h - 4, w, 4, radius=3, fill=1, stroke=0)
        c.setFont("VnFont", 6); c.setFillColor(colors.HexColor("#6B8FAD"))
        c.drawCentredString(x + w/2, y + h - 15, label[:22])
        val_str = str(value)[:10]
        sz = 15 if len(val_str) <= 5 else 11
        c.setFont("VnFont-Bold", sz); c.setFillColor(accent_color)
        c.drawCentredString(x + w/2, y + 8, val_str)

    def _sec_title(c, text, x, y, width=None, color=None, size=9.0):
        width = width or CW; color = color or C_HEADER_DARK
        c.setFont("VnFont-Bold", size); c.setFillColor(color)
        c.drawString(x, y, text)
        c.setStrokeColor(C_ACCENT); c.setLineWidth(2.0)
        c.line(x, y - 4, x + 24, y - 4)
        c.setStrokeColor(C_LIGHT_GREY); c.setLineWidth(0.5)
        c.line(x + 24, y - 4, x + width, y - 4)

    def _draw_vgm_badge(c, x, y, w, h, grade):
        grade = str(grade).strip().upper()
        bg_col = VGM_COLORS_RL.get(grade, C_GREY)
        r = min(w, h) / 2 - 0.5
        cx = x + w/2; cy = y + h/2
        c.setFillColor(bg_col); c.circle(cx, cy, r, fill=1, stroke=0)
        c.setFont("VnFont-Bold", min(8.5, r * 1.45)); c.setFillColor(colors.white)
        c.drawCentredString(cx, cy - 3, grade)

    def _table_draw(c, headers, rows, x, y, widths,
                    row_h=14, hdr_h=17, font_sz=7.0,
                    right_cols=None, center_cols=None, vgm_col_idx=None,
                    bold_red_cols=None, alt_row_start=True):
        right_cols = right_cols or set(); center_cols = center_cols or set()
        tw = sum(widths)
        c.setFillColor(C_HDR_TABLE)
        c.roundRect(x, y - hdr_h, tw, hdr_h, radius=0, fill=1, stroke=0)
        c.setFillColor(C_ACCENT); c.rect(x, y, tw, 2, fill=1, stroke=0)
        cx = x
        for i, (h, w) in enumerate(zip(headers, widths)):
            c.setFont("VnFont-Bold", font_sz - 0.2); c.setFillColor(C_HDR_TEXT)
            if i in center_cols or i == vgm_col_idx:
                c.drawCentredString(cx + w/2, y - hdr_h + 5, str(h)[:20])
            elif i in right_cols:
                c.drawRightString(cx + w - 4, y - hdr_h + 5, str(h)[:20])
            else:
                c.drawString(cx + 5, y - hdr_h + 5, str(h)[:20])
            cx += w
        y -= hdr_h
        for ri, row in enumerate(rows):
            c.setFillColor(C_STRIPE_EVEN if ri % 2 == 0 else C_STRIPE_ODD)
            c.rect(x, y - row_h, tw, row_h, fill=1, stroke=0)
            c.setStrokeColor(C_LIGHT_GREY); c.setLineWidth(0.3)
            c.line(x, y - row_h, x + tw, y - row_h)
            cx = x
            for ci, (cell, w) in enumerate(zip(row, widths)):
                txt = str(cell) if cell is not None else "—"
                if ci == vgm_col_idx:
                    _draw_vgm_badge(c, cx+3, y-row_h+3, w-6, row_h-6, txt)
                    cx += w; continue
                try:
                    raw = txt.replace("%","").replace(",","").replace("+","")
                    num = float(raw)
                    fc = C_RED if (num < 0 and ci in right_cols) else \
                         C_GREEN if (num > 0 and "%" in txt and ci in right_cols) else C_TEXT
                except Exception:
                    fc = C_TEXT
                c.setFont("VnFont", font_sz); c.setFillColor(fc)
                if ci in center_cols:
                    c.drawCentredString(cx + w/2, y - row_h + 4, txt[:24])
                elif ci in right_cols:
                    c.drawRightString(cx + w - 4, y - row_h + 4, txt[:24])
                else:
                    c.drawString(cx + 5, y - row_h + 4, txt[:34])
                cx += w
            y -= row_h
        return y

    def _company_name(ticker, row_dict, max_len=28):
        name = str(row_dict.get("Company Common Name", "") or "").strip()
        if name.lower() in ("nan", "none", ""): name = ticker
        if len(name) <= max_len: return name
        return name[:max_len].rsplit(" ", 1)[0].rstrip(",.-(") + "…"

    def _styled_ax(ax, title="", xlabel="", ylabel="", grid_axis="y"):
        ax.set_facecolor("#F5F9FD")
        for sp in ["top", "right"]:
            ax.spines[sp].set_visible(False)
        for sp in ["left", "bottom"]:
            ax.spines[sp].set_color("#C5D8EC"); ax.spines[sp].set_linewidth(0.8)
        ax.grid(True, axis=grid_axis, color="#E0EBF5", linestyle="--", linewidth=0.5, alpha=0.8)
        ax.tick_params(labelsize=7.5, colors="#4A6580", length=0, pad=3)
        if title:
            ax.set_title(title, fontsize=9.5, fontweight="bold", color="#0A1628", loc="left", pad=8)

    def _img(fig, dpi=150):
        buf_i = io.BytesIO()
        fig.savefig(buf_i, format="png", dpi=dpi, bbox_inches="tight",
                    facecolor=fig.get_facecolor(), edgecolor="none")
        buf_i.seek(0)
        from reportlab.lib.utils import ImageReader
        return ImageReader(buf_i)

    def _embed(c, fig, x, y, w, h):
        c.drawImage(_img(fig), x, y, width=w, height=h,
                    preserveAspectRatio=True, anchor="nw")
        plt.close(fig)

    def _ai_box(c, text, x, y, w, box_color, border_color, accent_color,
                badge_label, badge_color=None):
        badge_color = badge_color or accent_color
        FONT_AI, LINE_H = 7.5, 11.5
        lines = _wrap_text(str(text).strip(), w - 28, "VnFont", FONT_AI)[:6]
        box_h = 26 + len(lines) * LINE_H + 8
        c.setFillColor(box_color); c.setStrokeColor(border_color); c.setLineWidth(0.6)
        c.roundRect(x, y - box_h, w, box_h, radius=4, fill=1, stroke=1)
        c.setFillColor(accent_color)
        c.roundRect(x, y - box_h, 4, box_h, radius=2, fill=1, stroke=0)
        bw = pdfmetrics.stringWidth(badge_label, "VnFont-Bold", 6.8) + 26
        c.setFillColor(badge_color)
        c.roundRect(x + 8, y - 16, bw, 13, radius=6, fill=1, stroke=0)
        c.setFont("VnFont-Bold", 6.8); c.setFillColor(colors.white)
        c.drawString(x + 12, y - 12.5, badge_label)
        ty = y - 26
        for line in lines:
            c.setFont("VnFont", FONT_AI); c.setFillColor(C_TEXT)
            c.drawString(x + 12, ty, line)
            ty -= LINE_H
        return y - box_h


# ══════════════════════════════════════════════════════════════
# MAPPING LABELS
# ══════════════════════════════════════════════════════════════
_RISK_LABEL = {
    "conservative": "Thận trọng",
    "moderate":     "Cân bằng",
    "aggressive":   "Tăng trưởng",
}
_RISK_COLOR_PDF = {
    "conservative": C_GREEN,
    "moderate":     C_BLUE,
    "aggressive":   C_RED,
}
_RISK_COLOR_HEX = {
    "conservative": "#1B7A4A",
    "moderate":     "#1565C0",
    "aggressive":   "#C62828",
}
_GOAL_LABEL = {
    "preserve":  "Bảo toàn vốn",
    "income":    "Thu nhập thụ động",
    "growth":    "Tăng trưởng tài sản",
    "speculate": "Tối đa hóa lợi nhuận",
}
_WILL_LABEL = {
    "panic": "Bán hết (Panic sell)",
    "worry": "Lo lắng, chờ đợi",
    "hold":  "Giữ theo kế hoạch",
    "buy":   "Mua thêm vào đáy",
}
_TIME_LABEL = {
    "short": "Dưới 1 năm",
    "mid":   "1 – 3 năm",
    "long":  "Trên 3 năm",
}
_STRAT_NAME = {
    "STRAT_QUALITY":    "Quality (Munger)",
    "STRAT_GARP":       "GARP (Peter Lynch)",
    "STRAT_PIOTROSKI":  "Piotroski F-Score",
    "STRAT_DIVIDEND":   "Cổ tức (John Neff)",
    "STRAT_VALUE":      "Giá trị (B. Graham)",
    "STRAT_MAGIC":      "Magic Formula",
    "STRAT_TURNAROUND": "Turnaround (Templeton)",
    "STRAT_CANSLIM":    "CANSLIM (O'Neil)",
    "STRAT_GROWTH":     "Growth (P. Fisher)",
    "STRAT_NCN":        "Vietcap Khuyến nghị",
}


# ══════════════════════════════════════════════════════════════
# HELPER: Wrap text đơn giản (không dùng matplotlib)
# ══════════════════════════════════════════════════════════════
def _wrap_text(text: str, max_width: float, font: str, font_size: float) -> list:
    words = str(text).split()
    lines, cur = [], ""
    for w in words:
        test = (cur + " " + w).strip()
        if pdfmetrics.stringWidth(test, font, font_size) <= max_width:
            cur = test
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines or [""]


# ══════════════════════════════════════════════════════════════
# HELPER: Lấy top 3 mã phù hợp với profile
# ══════════════════════════════════════════════════════════════
def _get_top3(profile: dict) -> list:
    """
    Lọc snapshot theo auto_filters của profile,
    sort VGM_Score_Num giảm dần, lấy top 3.
    Trả về list[dict] với các key: Ticker, name, Sector,
    Price Close, VGM Score, P/E, ROE (%), Perf_1M.
    """
    try:
        from src.backend.data_loader import get_snapshot_df
        df = get_snapshot_df()
        if df is None or df.empty:
            return []

        af = profile.get("auto_filters", {})
        min_vol   = af.get("min_vol",   30_000)
        min_cap   = af.get("min_cap",   200_000_000_000)
        min_price = af.get("min_price", 3_000)

        import pandas as _pd
        import math as _m

        def _safe(col, default=0.0):
            if col not in df.columns:
                return _pd.Series(default, index=df.index)
            return _pd.to_numeric(df[col], errors="coerce").fillna(default)

        mask = (
            (_safe("Avg_Vol_20D") >= min_vol) &
            (_safe("Market Cap")  >= min_cap) &
            (_safe("Price Close") >= min_price)
        )
        df2 = df[mask].copy()

        # Ưu tiên VGM A/B
        if "VGM Score" in df2.columns:
            df2 = df2[df2["VGM Score"].isin(["A", "B"])]

        # Sort theo VGM_Score_Num nếu có, else theo VGM Score string
        if "VGM_Score_Num" in df2.columns:
            df2 = df2.sort_values("VGM_Score_Num", ascending=False)
        elif "VGM Score" in df2.columns:
            grade_ord = {"A": 0, "B": 1, "C": 2, "D": 3, "F": 4}
            df2["_g"] = df2["VGM Score"].map(grade_ord).fillna(5)
            df2 = df2.sort_values("_g")

        top3 = df2.head(3)
        vn_map = {}
        try:
            vn_map = _get_vn_name_map()
        except Exception:
            pass

        result = []
        for _, row in top3.iterrows():
            ticker = str(row.get("Ticker", ""))
            result.append({
                "ticker":  ticker,
                "name":    vn_map.get(ticker, _company_name(ticker, row.to_dict())),
                "sector":  str(row.get("Sector", row.get("GICS Sector Name", "—")) or "—"),
                "price":   _fmt(row.get("Price Close"), dec=0),
                "vgm":     str(row.get("VGM Score", "—") or "—"),
                "pe":      _fmt(row.get("P/E"), dec=1),
                "roe":     _fmt(row.get("ROE (%)"), dec=1, pct=True),
                "perf1m":  _fmt(row.get("Perf_1M"), dec=1, pct=True, sign=True),
            })
        return result
    except Exception as e:
        logger.warning(f"[IPS PDF] _get_top3 error: {e}")
        return []


# ══════════════════════════════════════════════════════════════
# CORE: Sinh PDF bytes
# ══════════════════════════════════════════════════════════════
def generate_ips_pdf(profile: dict, quiz_answers: dict) -> bytes:
    """
    Sinh PDF 1 trang A4 báo cáo hồ sơ nhà đầu tư.
    profile    : dict từ investor-profile-store
    quiz_answers: dict với keys goal, will, time_h, liquidity
    """
    profile       = profile or {}
    quiz_answers  = quiz_answers or {}

    buf = io.BytesIO()
    c   = rl_canvas.Canvas(buf, pagesize=A4)

    risk      = profile.get("risk_profile") or "moderate"
    risk_lbl  = _RISK_LABEL.get(risk, risk)
    risk_col  = _RISK_COLOR_PDF.get(risk, C_BLUE)
    risk_hex  = _RISK_COLOR_HEX.get(risk, "#1565C0")

    goal   = quiz_answers.get("goal")   or "growth"
    will   = quiz_answers.get("will")   or "hold"
    time_h = quiz_answers.get("time_h") or "long"

    will_s   = profile.get("will_score")    if profile.get("will_score")    is not None else 0.5
    abil_s   = profile.get("ability_score") if profile.get("ability_score") is not None else 0.5
    final_s  = profile.get("final_score")   if profile.get("final_score")   is not None else 0.5
    t_min, t_max = profile.get("target_return") or (12, 16)
    max_dd   = profile.get("max_drawdown") if profile.get("max_drawdown") is not None else -15
    core_st  = profile.get("core_strategies")      or []
    sat_st   = profile.get("satellite_strategies") or []
    bucket   = profile.get("bucket_alloc") or {"safe": 40, "growth": 45, "speculative": 15}
    num_stocks = profile.get("num_stocks") or (10, 18)

    top3 = _get_top3(profile)

    # ── Metadata PDF (đồng bộ Screener) ──
    c.setTitle("Vietcap Smart Screener - Báo Cáo Hồ Sơ Nhà Đầu Tư")
    c.setAuthor("Vietcap Smart Screener")
    c.setSubject(f"Hồ sơ {risk_lbl} - {datetime.now().strftime('%d/%m/%Y')}")

    # ── Nền trắng ───────────────────────────────────────────────────────────
    _bg(c)

    # ══════════════════════════════════════════════════════════════
    # HEADER — Light professional style (đồng bộ Screener PDF trang 1)
    # Nền trắng xanh nhạt, chữ tối rõ ràng, 3 dòng tách biệt
    # ══════════════════════════════════════════════════════════════
    HDR_BAND_H = 60

    # Nền header xanh nhạt gradient-ish (2 rect để tạo hiệu ứng)
    c.setFillColor(colors.HexColor("#EBF4FF"))
    c.rect(0, PH - HDR_BAND_H, PW, HDR_BAND_H, fill=1, stroke=0)
    c.setFillColor(colors.HexColor("#F5F9FF"))
    c.rect(0, PH - HDR_BAND_H + 18, PW, 18, fill=1, stroke=0)

    # Accent bar trên 4pt xanh đậm
    c.setFillColor(colors.HexColor("#0057B8"))
    c.rect(0, PH - 4, PW, 4, fill=1, stroke=0)

    # Đường kẻ dưới header
    c.setStrokeColor(colors.HexColor("#BDD6F0")); c.setLineWidth(1.0)
    c.line(0, PH - HDR_BAND_H, PW, PH - HDR_BAND_H)

    # ── DÒNG 1: Logo VSS | Smart Screener | tagline  ···  "BÁO CÁO..." ──
    y1 = PH - 19

    c.setFont("VnFont-Bold", 13); c.setFillColor(colors.HexColor("#0057B8"))
    c.drawString(MARGIN, y1, "VSS")
    lw_vss = pdfmetrics.stringWidth("VSS", "VnFont-Bold", 13)

    c.setStrokeColor(colors.HexColor("#BDD6F0")); c.setLineWidth(1.2)
    c.line(MARGIN + lw_vss + 6, y1 - 2, MARGIN + lw_vss + 6, y1 + 11)

    c.setFont("VnFont", 10); c.setFillColor(colors.HexColor("#1A3A5C"))
    c.drawString(MARGIN + lw_vss + 12, y1, "Smart Screener")
    sw_ss = pdfmetrics.stringWidth("Smart Screener", "VnFont", 10)

    c.setFont("VnFont", 7); c.setFillColor(colors.HexColor("#5A80A0"))
    c.drawString(MARGIN + lw_vss + sw_ss + 18, y1 + 1,
                 "Vietcap Securities · IPS Report")

    c.setFont("VnFont-Bold", 8); c.setFillColor(colors.HexColor("#0057B8"))
    c.drawRightString(PW - MARGIN, y1, "BÁO CÁO HỒ SƠ NHÀ ĐẦU TƯ")

    # ── DÒNG 2: Tiêu đề lớn + datetime bên phải ──
    y2 = PH - 35

    c.setFont("VnFont-Bold", 15); c.setFillColor(colors.HexColor("#0A1E35"))
    c.drawString(MARGIN, y2, "Hồ Sơ Nhà Đầu Tư Cá Nhân")

    c.setFont("VnFont", 7); c.setFillColor(colors.HexColor("#4A7090"))
    c.drawRightString(PW - MARGIN, y2,
                      datetime.now().strftime("%d/%m/%Y  %H:%M"))

    # ── DÒNG 3: Khẩu vị rủi ro + Mục tiêu   ···   badges bên phải ──
    y3 = PH - 49

    c.setFont("VnFont", 7); c.setFillColor(colors.HexColor("#3A6080"))
    c.drawString(MARGIN, y3,
                 f"Khẩu vị rủi ro: {risk_lbl}  ·  Mục tiêu: {_GOAL_LABEL.get(goal, goal)}")

    badge_items = [
        (risk_lbl,                         risk_col),
        (_TIME_LABEL.get(time_h, time_h),  colors.HexColor("#6A0DAD")),
    ]
    bx_right = PW - MARGIN
    for lbl_txt, bg_col in reversed(badge_items):
        bw = pdfmetrics.stringWidth(lbl_txt, "VnFont-Bold", 6.5) + 12
        bx_right -= bw
        c.setFillColor(bg_col)
        c.roundRect(bx_right, y3 - 2, bw, 13, radius=3, fill=1, stroke=0)
        c.setFont("VnFont-Bold", 6.5); c.setFillColor(colors.white)
        c.drawCentredString(bx_right + bw/2, y3 + 2, lbl_txt)
        bx_right -= 5

    y = PH - HDR_BAND_H - 14

    # ══════════════════════════════════════════════════════════════
    # SECTION 1 — KẾT QUẢ TRẮC NGHIỆM
    # ══════════════════════════════════════════════════════════════
    _sec_title(c, "① KẾT QUẢ TRẮC NGHIỆM  IPS", MARGIN, y, CW)
    y -= 18

    # 4 KPI cards (cao hơn cho cân đối với screener)
    kpi_w = (CW - 9) / 4
    kpi_h = 52
    kpis = [
        ("Khẩu vị rủi ro",    risk_lbl,
         risk_col),
        ("Điểm tâm lý (Will)",
         f"{will_s*100:.0f}/100",
         colors.HexColor("#7C3AED")),
        ("Năng lực TC (Ability)",
         f"{abil_s*100:.0f}/100",
         C_BLUE),
        ("Final Score (CFA L3)",
         f"{final_s*100:.0f}/100",
         risk_col),
    ]
    kx = MARGIN
    for label, value, acc in kpis:
        _kpi_card(c, kx, y - kpi_h, kpi_w, kpi_h, label, value, acc)
        kx += kpi_w + 3
    y -= kpi_h + 14

    # Info rows (2 cột)
    info_col_w = CW / 2 - 6
    info_pairs = [
        ("Mục tiêu đầu tư",     _GOAL_LABEL.get(goal, goal)),
        ("Phản ứng biến động",  _WILL_LABEL.get(will, will)),
        ("Thời gian đầu tư",    _TIME_LABEL.get(time_h, time_h)),
        ("Lợi nhuận kỳ vọng",   f"{t_min}–{t_max}%/năm"),
        ("Max drawdown",         f"{max_dd}%"),
        ("Số mã trong danh mục",
         f"{num_stocks[0]}–{num_stocks[1]} mã"),
    ]
    # Vẽ 2 cột info
    for i, (lbl, val) in enumerate(info_pairs):
        col = i % 2
        row = i // 2
        ix  = MARGIN + col * (info_col_w + 12)
        iy  = y - row * 16
        c.setFont("VnFont", 8)
        c.setFillColor(C_GREY)
        c.drawString(ix, iy, lbl + ":")
        lbl_w = pdfmetrics.stringWidth(lbl + ": ", "VnFont", 8)
        c.setFont("VnFont-Bold", 8)
        c.setFillColor(C_TEXT)
        c.drawString(ix + lbl_w, iy, val)
    y -= (len(info_pairs) // 2 + 1) * 16 + 14

    # ── Biểu đồ Điểm số IPS (Will / Ability / Final) — style Bloomberg ──
    chart_h = 100
    try:
        fig, ax = plt.subplots(figsize=(CW/72, chart_h/72), facecolor="#FFFFFF")
        _styled_ax(ax, "Phân Tích Điểm Số IPS  ·  Mô hình CFA Level III", grid_axis="x")
        score_labels = ["Final Score", "Năng lực TC (Ability)", "Điểm tâm lý (Will)"]
        score_vals   = [final_s * 100, abil_s * 100, will_s * 100]
        score_colors = [risk_hex, "#0078D4", "#7C3AED"]
        ypos = np.arange(len(score_labels))
        ax.barh(ypos, score_vals, color=score_colors, height=0.52, zorder=3)
        ax.set_yticks(ypos)
        ax.set_yticklabels(score_labels, fontsize=8)
        ax.set_xlim(0, 100)
        for i, v in enumerate(score_vals):
            ax.text(min(v + 2, 92), i, f"{v:.0f}/100", va="center",
                    fontsize=8, fontweight="bold", color="#0A1628")
        fig.subplots_adjust(left=0.24, right=0.97, top=0.78, bottom=0.14)
        _embed(c, fig, MARGIN, y - chart_h, CW, chart_h)
    except Exception as _ce:
        logger.warning(f"[IPS PDF] Chart score error: {_ce}")
    y -= chart_h + 16

    # ── Phân bổ tài sản đề xuất (3 bucket) ──
    _sec_title(c, "Phân Bổ Tài Sản Đề Xuất  ·  3 Bucket Chiến Lược", MARGIN, y,
               CW, color=C_PURPLE, size=8.5)
    y -= 16

    safe_pct   = bucket.get("safe")        if bucket.get("safe")        is not None else 40
    growth_pct = bucket.get("growth")      if bucket.get("growth")      is not None else 45
    spec_pct   = bucket.get("speculative") if bucket.get("speculative") is not None else 15

    bar_h = 16
    bar_y = y - bar_h
    safe_w   = CW * safe_pct   / 100
    growth_w = CW * growth_pct / 100
    spec_w   = CW * spec_pct   / 100

    # Vẽ 3 segment
    c.setFillColor(C_GREEN);  c.rect(MARGIN,              bar_y, safe_w,   bar_h, fill=1, stroke=0)
    c.setFillColor(C_BLUE);   c.rect(MARGIN + safe_w,     bar_y, growth_w, bar_h, fill=1, stroke=0)
    c.setFillColor(C_AMBER);  c.rect(MARGIN + safe_w + growth_w, bar_y, spec_w, bar_h, fill=1, stroke=0)

    # Label trên bar
    c.setFont("VnFont-Bold", 7); c.setFillColor(colors.white)
    def _bar_label(text, bx, bw):
        if bw > 34:
            c.drawCentredString(bx + bw/2, bar_y + 5, text)

    _bar_label(f"Phòng thủ {safe_pct}%",   MARGIN, safe_w)
    _bar_label(f"Tăng trưởng {growth_pct}%", MARGIN + safe_w, growth_w)
    _bar_label(f"Đầu cơ {spec_pct}%",      MARGIN + safe_w + growth_w, spec_w)

    # Legend dưới bar
    y = bar_y - 12
    c.setFont("VnFont", 7)
    for lbl, col, pct in [
        ("Phòng thủ (Dividend/Quality)", C_GREEN,  safe_pct),
        ("Tăng trưởng (GARP/Growth)",    C_BLUE,   growth_pct),
        ("Đầu cơ (CANSLIM/Momentum)",    C_AMBER,  spec_pct),
    ]:
        c.setFillColor(col)
        c.rect(MARGIN, y - 5, 8, 8, fill=1, stroke=0)
        c.setFillColor(C_GREY)
        c.drawString(MARGIN + 11, y, f"{lbl}: {pct}%")
        y -= 13
    y -= 6

    # ══════════════════════════════════════════════════════════════
    # SECTION 2 — KHUYẾN NGHỊ HỆ THỐNG
    # ══════════════════════════════════════════════════════════════
    _sec_title(c, "② KHUYẾN NGHỊ CHIẾN LƯỢC", MARGIN, y, CW)
    y -= 18

    # Text box chiến lược — nền xanh nhạt, viền
    box_h_est = 88
    c.setFillColor(C_BLUE_SOFT)
    c.setStrokeColor(C_BLUE_BORDER)
    c.setLineWidth(0.8)
    c.roundRect(MARGIN, y - box_h_est, CW, box_h_est, radius=5,
                fill=1, stroke=1)
    # Accent bar trái
    c.setFillColor(C_ACCENT)
    c.roundRect(MARGIN, y - box_h_est, 4, box_h_est, radius=2,
                fill=1, stroke=0)

    ty = y - 15
    # Core strategies
    core_names = [_STRAT_NAME.get(s, s) for s in core_st]
    sat_names  = [_STRAT_NAME.get(s, s) for s in sat_st]

    c.setFont("VnFont-Bold", 8)
    c.setFillColor(C_BLUE)
    c.drawString(MARGIN + 12, ty, "CHIẾN LƯỢC CỐT LÕI (Core):")
    core_txt = "  ·  ".join(core_names) if core_names else "—"
    c.setFont("VnFont", 8)
    c.setFillColor(C_TEXT)
    # Wrap nếu dài
    core_lines = _wrap_text(core_txt, CW - 34, "VnFont", 8)
    ty -= 13
    for line in core_lines[:2]:
        c.drawString(MARGIN + 12, ty, line)
        ty -= 11.5

    ty -= 5
    c.setFont("VnFont-Bold", 8)
    c.setFillColor(C_ACCENT)
    c.drawString(MARGIN + 12, ty, "CHIẾN LƯỢC VỆ TINH (Satellite):")
    sat_txt = "  ·  ".join(sat_names) if sat_names else "—"
    c.setFont("VnFont", 8)
    c.setFillColor(C_TEXT)
    sat_lines = _wrap_text(sat_txt, CW - 34, "VnFont", 8)
    ty -= 13
    for line in sat_lines[:2]:
        c.drawString(MARGIN + 12, ty, line)
        ty -= 11.5

    ty -= 5
    # Bộ lọc tự động sẽ áp dụng
    af = profile.get("auto_filters") or {}
    _min_vol   = af.get("min_vol")   if af.get("min_vol")   is not None else 30_000
    _min_cap   = af.get("min_cap")   if af.get("min_cap")   is not None else 200_000_000_000
    _min_price = af.get("min_price") if af.get("min_price") is not None else 3_000
    filter_note = (
        f"Bộ lọc tự động: KL TB ≥ {_min_vol:,.0f} CP/ngày  ·  "
        f"Vốn hóa ≥ {_min_cap/1e9:.0f} tỷ  ·  "
        f"Giá ≥ {_min_price:,.0f} VND"
    )
    c.setFont("VnFont", 7.2)
    c.setFillColor(C_GREY)
    c.drawString(MARGIN + 12, ty, filter_note)

    y = y - box_h_est - 14

    # ══════════════════════════════════════════════════════════════
    # SECTION 3 — TOP 3 CỔ PHIẾU PHÙ HỢP
    # ══════════════════════════════════════════════════════════════
    _sec_title(c, "③ TOP 3 CỔ PHIẾU PHÙ HỢP KHẨU VỊ", MARGIN, y, CW)
    y -= 18

    tbl_row_h, tbl_hdr_h = 20, 19
    if top3:
        headers = ["MÃ", "TÊN CÔNG TY", "NGÀNH", "GIÁ (VND)", "VGM", "P/E", "ROE", "%1TH"]
        widths  = [38,    95,             85,       58,          24,    30,    35,    35]
        rows = []
        for r in top3:
            # Cắt tên cho vừa cột
            name_cut = r["name"][:20] + "…" if len(r["name"]) > 20 else r["name"]
            sec_cut  = r["sector"][:16] + "…" if len(r["sector"]) > 16 else r["sector"]
            rows.append([
                r["ticker"], name_cut, sec_cut,
                r["price"], r["vgm"],
                r["pe"], r["roe"], r["perf1m"],
            ])
        _table_draw(
            c, headers, rows, MARGIN, y, widths,
            row_h=tbl_row_h, hdr_h=tbl_hdr_h, font_sz=7.5,
            right_cols={3, 5, 6, 7},
            center_cols={0, 4},
            vgm_col_idx=4,
        )
        y -= (tbl_hdr_h + tbl_row_h * len(rows) + 10)
    else:
        c.setFont("VnFont", 8)
        c.setFillColor(C_GREY)
        c.drawCentredString(PW / 2, y - 14,
            "Chưa có dữ liệu snapshot — khởi động Screener để tải dữ liệu.")
        y -= 34

    # ── Ghi chú nhỏ dưới bảng ───────────────────────────────────
    c.setFont("VnFont", 6.8)
    c.setFillColor(C_GREY)
    c.drawString(MARGIN, y,
        "* Top 3 được lọc tự động dựa trên điểm VGM và bộ lọc tự động từ hồ sơ. "
        "Không phải khuyến nghị mua/bán.")
    y -= 20

    # ══════════════════════════════════════════════════════════════
    # SECTION 4 — GHI CHÚ VẬN HÀNH  (AI-style note, đồng bộ Screener)
    # ══════════════════════════════════════════════════════════════
    if y - 60 > Y_MIN + 8:
        _sec_title(c, "④ GHI CHÚ VẬN HÀNH & KỶ LUẬT ĐẦU TƯ", MARGIN, y, CW,
                   color=C_PURPLE)
        y -= 15

        _advice_lines = {
            "conservative": (
                "- Ưu tiên bảo toàn vốn: giữ tỷ trọng phòng thủ cao, tránh mua đuổi cổ phiếu biến động mạnh.\n"
                "- Giải ngân theo từng phần (DCA), không all-in một lần để giảm rủi ro thời điểm.\n"
                "- Tuân thủ chặt các mốc cắt lỗ tự động đã cấu hình trong Screener để bảo vệ tài khoản.\n"
                "- Đánh giá lại khẩu vị rủi ro mỗi 6 tháng hoặc khi có biến động thu nhập/tài chính cá nhân."
            ),
            "moderate": (
                "- Cân bằng giữa tăng trưởng và phòng thủ: duy trì kỷ luật tái cân bằng danh mục định kỳ.\n"
                "- Ưu tiên các mã có dòng tiền kinh doanh dương và ROE ổn định trong nhóm core.\n"
                "- Với nhóm satellite, giới hạn tỷ trọng để không ảnh hưởng lớn tới NAV khi biến động.\n"
                "- Theo dõi các cảnh báo Red Flags (D/E, RSI, Momentum) trong báo cáo Danh Mục Lọc."
            ),
            "aggressive": (
                "- Chấp nhận biến động cao hơn để theo đuổi tăng trưởng, nhưng vẫn cần đặt stop-loss rõ ràng.\n"
                "- Kiểm soát tỷ trọng đầu cơ (CANSLIM/Momentum) để tránh rủi ro tập trung quá mức.\n"
                "- Không sử dụng đòn bẩy (margin) vượt quá khả năng chịu đựng rủi ro đã xác định (Max DD).\n"
                "- Chốt lời từng phần khi đạt mục tiêu lợi nhuận, tránh tâm lý FOMO khi thị trường hưng phấn."
            ),
        }
        advice_txt = _advice_lines.get(risk, _advice_lines["moderate"])
        try:
            y = _ai_box(c, advice_txt, MARGIN, y, CW,
                        box_color=C_PURPLE_SOFT,
                        border_color=C_PURPLE_BORDER,
                        accent_color=C_PURPLE,
                        badge_label="VSS Advisory",
                        badge_color=C_PURPLE)
        except Exception as _ae:
            logger.warning(f"[IPS PDF] AI box error: {_ae}")

    # ══════════════════════════════════════════════════════════════
    # FOOTER
    # ══════════════════════════════════════════════════════════════
    _footer(c, 1, 1)

    c.save()
    buf.seek(0)
    return buf.read()


# ══════════════════════════════════════════════════════════════
# CALLBACK: Trigger download khi bấm nút
# ══════════════════════════════════════════════════════════════
@app.callback(
    Output("ips-pdf-download",        "data"),
    Input("ips-btn-download-pdf",     "n_clicks"),
    State("investor-profile-store",   "data"),
    State("ips-goal-store",           "data"),
    State("ips-will-store",           "data"),
    State("ips-time-store",           "data"),
    prevent_initial_call=True,
)
def download_ips_pdf(n_clicks, profile, goal, will, time_h):
    if not n_clicks or not profile:
        return no_update

    quiz = {
        "goal":   goal   or "growth",
        "will":   will   or "hold",
        "time_h": time_h or "long",
    }

    try:
        pdf_bytes = generate_ips_pdf(profile, quiz)
        fname = f"Vietcap_HoSoNhaDauTu_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
        return dcc.send_bytes(pdf_bytes, fname)
    except Exception as e:
        logger.error(f"[IPS PDF] Lỗi generate: {e}", exc_info=True)
        return no_update