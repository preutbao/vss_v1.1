# src/callbacks/screener_pdf_callback.py
# ============================================================
# PDF XUẤT DANH MỤC LỌC – FinSmartScreener  v8.0
#
# THAY ĐỔI v8.0 (Premium Visual Redesign):
#   - Header trang 1: gradient nền đậm, logo nổi bật, badge strategy,
#     6 KPI card có shadow effect, đường kẻ accent tinh tế
#   - Header trang 2/3: dải màu gradient đa tầng, breadcrumb subtitle
#   - Biểu đồ matplotlib: style Bloomberg-terminal (nền tối xám sang,
#     grid mờ, label rõ, palette chuyên nghiệp), DPI 150
#   - Scatter: bubble size = market cap, color = VGM grade, tooltip đẹp
#   - Donut: legend bên phải thay vì label trực tiếp, % lớn ở tâm
#   - ROE Bar: gradient color, value label căn chỉnh đẹp
#   - Perf Bar: dashed zero line, gradient color bar
#   - Radar: gradient fill, glow effect
#   - Bảng: cột header màu tối sang, zebra rõ, padding thoáng,
#     border radius cho header, icon cảnh báo cho Red Flags
#   - AI box: icon spark + border trái dày + shadow nhẹ
#   - Footer: dải gradient 4pt
# ============================================================

import io, os, math, logging, traceback, json
from datetime import datetime

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch
import matplotlib.colors as mcolors

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from dash import Input, Output, State, no_update, dcc, html
from src.app_instance import app
from src.callbacks.quant_pdf_page import _render_quant_page
import json # Nhớ đảm bảo có import json ở đầu file

# FSS Predictive 2.0 – import quant engine
try:
    from src.backend.portfolio_optimizer import run_full_pipeline, QuantResult
    _QUANT_AVAILABLE = True
except ImportError:
    _QUANT_AVAILABLE = False

# Import Stage 4 PDF page (nếu tách file riêng)
try:
    from src.callbacks.quant_pdf_page import (
        _chart_mc_histogram, _render_quant_page
    )
except ImportError:
    pass  # fallback: paste trực tiếp vào file này
from src.backend.data_loader import get_snapshot_df

logger = logging.getLogger(__name__)

# ── Map tên tiếng Việt từ COMP INFO.csv ──────────────────────────────────────
_VN_NAME_MAP: dict = {}

def _get_vn_name_map() -> dict:
    global _VN_NAME_MAP
    if _VN_NAME_MAP:
        return _VN_NAME_MAP
    try:
        import os, pandas as pd
        BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(
                       os.path.abspath(__file__))))
        csv_path = os.path.join(BASE_DIR, "data", "raw", "COMP INFO.csv")
        if not os.path.exists(csv_path):
            return {}
        df_info = pd.read_csv(csv_path, encoding="utf-8-sig")
        for _, r in df_info.iterrows():
            sym = str(r.get("symbol", r.get("Ticker", ""))).strip()
            sym = sym.replace(".HM","").replace(".HN","").replace(".UPCOM","").strip()
            name = (str(r.get("organ_name", "") or "").strip()
                    or str(r.get("company_name_vi", "") or "").strip()
                    or str(r.get("Company Common Name", "") or "").strip())
            if sym and name and name.lower() not in ("nan","none"):
                _VN_NAME_MAP[sym] = name
    except Exception as e:
        logger.warning(f"[VN name map] {e}")
    return _VN_NAME_MAP


def _company_name(ticker: str, row_dict: dict, max_len: int = 28) -> str:
    """Trả về tên tiếng Việt nếu có, fallback tiếng Anh, cắt tại ranh giới từ."""
    vn_map  = _get_vn_name_map()

    # Ưu tiên 1: tên tiếng Việt từ COMP INFO.csv
    name_vi = vn_map.get(str(ticker).strip(), "")

    # Ưu tiên 2: fallback tiếng Anh từ snapshot
    name_en = str(row_dict.get("Company Common Name",
                  row_dict.get("organ_name", "")) or "").strip()
    if name_en.lower() in ("nan", "none"):
        name_en = ""

    name = name_vi or name_en or "—"

    if len(name) <= max_len:
        return name
    cut = name[:max_len].rsplit(" ", 1)[0]
    return cut.rstrip(",.-(") + "…"


# ══════════════════════════════════════════════════════════════
# PHÔNG CHỮ – Cross-Platform
# ══════════════════════════════════════════════════════════════
_FONT_CANDIDATES = [
    ("/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
     "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf"),
    ("/usr/share/fonts/opentype/noto/NotoSans-Regular.ttf",
     "/usr/share/fonts/opentype/noto/NotoSans-Bold.ttf"),
    ("/usr/share/fonts/noto/NotoSans-Regular.ttf",
     "/usr/share/fonts/noto/NotoSans-Bold.ttf"),
    ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
     "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    ("C:/Windows/Fonts/arial.ttf",          "C:/Windows/Fonts/arialbd.ttf"),
    ("C:/Windows/Fonts/Tahoma.ttf",         "C:/Windows/Fonts/Tahomabd.ttf"),
    ("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
     "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"),
    ("/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
     "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf"),
]

_MPL_FONT_PATH = None

def _setup_fonts():
    global _MPL_FONT_PATH
    for reg, bold in _FONT_CANDIDATES:
        if os.path.exists(reg):
            b = bold if os.path.exists(bold) else reg
            try:
                pdfmetrics.registerFont(TTFont("VnFont",      reg))
                pdfmetrics.registerFont(TTFont("VnFont-Bold", b))
                _MPL_FONT_PATH = reg
                try:
                    plt.rcParams["font.family"] = fm.FontProperties(fname=reg).get_name()
                except Exception:
                    pass
                logger.info(f"PDF font: {reg}")
                return
            except Exception as e:
                logger.debug(f"Font skip {reg}: {e}")
    for family in ["Noto Sans", "DejaVu Sans", "Arial", "Liberation Sans"]:
        try:
            fp = fm.findfont(family, fallback_to_default=False)
            fb = fm.findfont(fm.FontProperties(family=family, weight="bold"),
                             fallback_to_default=False)
            if fp and os.path.exists(fp):
                bb = fb if (fb and os.path.exists(fb)) else fp
                pdfmetrics.registerFont(TTFont("VnFont",      fp))
                pdfmetrics.registerFont(TTFont("VnFont-Bold", bb))
                _MPL_FONT_PATH = fp
                return
        except Exception:
            continue
    dv  = fm.findfont("DejaVu Sans")
    dvb = fm.findfont(fm.FontProperties(family="DejaVu Sans", weight="bold"))
    pdfmetrics.registerFont(TTFont("VnFont",      dv))
    pdfmetrics.registerFont(TTFont("VnFont-Bold", dvb))
    _MPL_FONT_PATH = dv

_setup_fonts()

# ══════════════════════════════════════════════════════════════
# MATPLOTLIB GLOBAL STYLE – Bloomberg-inspired
# ══════════════════════════════════════════════════════════════
def _apply_mpl_style():
    """Áp dụng style toàn cục cho matplotlib."""
    plt.rcParams.update({
        "figure.facecolor":   "#FFFFFF",
        "axes.facecolor":     "#F7FAFD",
        "axes.edgecolor":     "#CBD8E8",
        "axes.linewidth":     0.8,
        "axes.grid":          True,
        "grid.color":         "#E2EBF5",
        "grid.linewidth":     0.5,
        "grid.linestyle":     "-",
        "axes.spines.top":    False,
        "axes.spines.right":  False,
        "xtick.color":        "#4A6580",
        "ytick.color":        "#4A6580",
        "xtick.labelsize":    8,
        "ytick.labelsize":    8,
        "xtick.major.size":   0,
        "ytick.major.size":   0,
        "text.color":         "#1A2F4A",
        "axes.labelcolor":    "#1A2F4A",
        "axes.labelsize":     9,
        "axes.titlesize":     10,
        "axes.titleweight":   "bold",
        "axes.titlecolor":    "#0A1628",
        "legend.frameon":     False,
        "legend.fontsize":    7.5,
        "figure.dpi":         150,
    })

_apply_mpl_style()

# ══════════════════════════════════════════════════════════════
# HẰNG SỐ & MÀU SẮC
# ══════════════════════════════════════════════════════════════
PW, PH   = A4
MARGIN   = 28
CW       = PW - 2 * MARGIN
FOOTER_H = 20
Y_MIN    = FOOTER_H + 10

# ── ReportLab Colors ──
C_BG           = colors.white
C_HEADER_DARK  = colors.HexColor("#0A1628")   # Navy đậm
C_HEADER_MID   = colors.HexColor("#0E2040")   # Navy vừa
C_TEXT         = colors.HexColor("#1A2F4A")
C_GREY         = colors.HexColor("#5A7A99")
C_LIGHT_GREY   = colors.HexColor("#D8E8F2")
C_RED          = colors.HexColor("#C62828")
C_RED_SOFT     = colors.HexColor("#FFF3F3")
C_RED_BORDER   = colors.HexColor("#FFCDD2")
C_GREEN        = colors.HexColor("#1B7A4A")
C_GREEN_SOFT   = colors.HexColor("#F0FBF5")
C_GREEN_BORDER = colors.HexColor("#A5D6B8")
C_BLUE         = colors.HexColor("#1565C0")
C_BLUE_SOFT    = colors.HexColor("#EEF4FF")
C_BLUE_BORDER  = colors.HexColor("#BBDEFB")
C_ACCENT       = colors.HexColor("#0078D4")
C_ACCENT2      = colors.HexColor("#00B4D8")
C_AMBER        = colors.HexColor("#E65100")
C_AMBER_SOFT   = colors.HexColor("#FFF8F0")
C_AMBER_BORDER = colors.HexColor("#FFCC80")
C_PURPLE       = colors.HexColor("#6A0DAD")
C_PURPLE_SOFT  = colors.HexColor("#F5F0FF")
C_PURPLE_BORDER= colors.HexColor("#D1B3F8")
C_ORANGE       = colors.HexColor("#E65100")
C_STRIPE_EVEN  = colors.HexColor("#F4F9FF")
C_STRIPE_ODD   = colors.white
C_HDR_TABLE    = colors.HexColor("#0E2040")
C_HDR_TEXT     = colors.white
C_CARD_BG      = colors.HexColor("#EEF4FF")
C_CARD_BORDER  = colors.HexColor("#C5D8F0")
C_PAGE2_HDR    = colors.HexColor("#082040")

VGM_COLORS_RL = {
    "A": colors.HexColor("#1B7A4A"),
    "B": colors.HexColor("#1565C0"),
    "C": colors.HexColor("#F59E0B"),
    "D": colors.HexColor("#E65100"),
    "F": colors.HexColor("#C62828"),
}
# ── Matplotlib palette ──
MPL_PALETTE = ["#0078D4","#1B7A4A","#7C3AED","#E65100","#00B4D8",
               "#C62828","#F59E0B","#2196F3","#4CAF50","#FF5722"]
MPL_GREEN   = "#1B7A4A"
MPL_RED     = "#C62828"
MPL_BLUE    = "#0078D4"
MPL_PURPLE  = "#6A0DAD"
MPL_ORANGE  = "#E65100"
MPL_AMBER   = "#F59E0B"

EXCLUDE_SECTORS_NCN = {"Tài chính","Financial","Financials","Banks","Ngân hàng","Bảo hiểm","Insurance"}
MIN_LIQUIDITY = 300_000  # 🟢 Tăng gấp 10 lần: Thanh khoản tối thiểu 300k cp/phiên
# 🟢 THÊM BLACKLIST chặn vĩnh viễn các mã có rủi ro pháp lý/thao túng/thanh khoản ảo
BLACKLIST_TICKERS = {
    "TDH", "L40", "FLC", "ROS", "HNG", "DL1", "TOS", "HAG", "HQC", "ITA", "AMD", "HAI",
    "HHS", "TCH", "NVL", "PDR", "HPX", "IBC", "LDG", "QCG", "TTF", "JVC"
}


# ══════════════════════════════════════════════════════════════
# UTILITY HELPERS
# ══════════════════════════════════════════════════════════════
def _fmt(v, dec=1, pct=False, sign=False):
    try:
        if v is None or (isinstance(v, float) and math.isnan(v)): return "---"
        v = float(v)
        pfx = "+" if (sign and v > 0) else ""
        if pct: return f"{pfx}{v:.{dec}f}%"
        if abs(v) >= 1e9: return f"{pfx}{v/1e9:,.{dec}f}B"
        if abs(v) >= 1e6: return f"{pfx}{v/1e6:,.{dec}f}M"
        if abs(v) >= 1e3: return f"{pfx}{v/1e3:,.{dec}f}K"
        return f"{pfx}{v:,.{dec}f}"
    except Exception:
        return str(v) if v is not None else "---"

def _sv(v, mode="str", suffix=""):
    try:
        if v is None or (isinstance(v, float) and math.isnan(v)): return "—"
        if mode == "dec1": return f"{float(v):.1f}{suffix}"
        if mode == "dec2": return f"{float(v):.2f}{suffix}"
        if mode == "dec0": return f"{float(v):.0f}{suffix}"
        if mode == "int":  return str(int(float(v)))
        if mode == "pct":  return f"{float(v):+.1f}{suffix}"
        return str(v)
    except Exception:
        return "—"

def _img(fig, dpi=150):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight",
                facecolor=fig.get_facecolor(), edgecolor="none")
    buf.seek(0)
    return ImageReader(buf)

def _embed(c, fig, x, y, w, h):
    c.drawImage(_img(fig), x, y, width=w, height=h,
                preserveAspectRatio=True, anchor="nw")
    plt.close(fig)


# ══════════════════════════════════════════════════════════════
# CANVAS PRIMITIVES  (ReportLab)
# ══════════════════════════════════════════════════════════════
def _bg(c):
    c.setFillColor(C_BG)
    c.rect(0, 0, PW, PH, fill=1, stroke=0)

def _footer(c, page_num, total=4):
    # 1. Dải màu trang trí dưới cùng
    c.setFillColor(C_ACCENT)
    c.rect(0, 0, PW * 0.6, 4, fill=1, stroke=0)
    c.setFillColor(C_ACCENT2)
    c.rect(PW * 0.6, 0, PW * 0.4, 4, fill=1, stroke=0)

    # =====================================================================
    # 2. CHÈN CALL-TO-ACTION (LEAD GEN) - GIAO DIỆN NÚT BẤM (BUTTON PILL)
    # =====================================================================
    url_link = "https://huggingface.co/spaces/preut/FinSmartScreener"
    cta_label = "Tự tạo danh mục đầu tư theo gu của bạn tại: "
    cta_link_text = "FSS Live Web App" # Rút gọn text hiển thị cho sang trọng

    # Tính toán kích thước Nút bấm
    c.setFont("VnFont", 7.5)
    label_w = pdfmetrics.stringWidth(cta_label, "VnFont", 7.5)
    c.setFont("VnFont-Bold", 7.5)
    link_w = pdfmetrics.stringWidth(cta_link_text, "VnFont-Bold", 7.5)
    
    box_padding_x = 12
    box_h = 16
    box_w = label_w + link_w + (box_padding_x * 2)
    
    box_x = (PW - box_w) / 2
    box_y = 15 # Nâng box lên để không sát mép dưới
    
    # 2.1 Vẽ nền Nút bấm (Pill background) - Nền xanh nhạt, viền xanh dương
    c.setFillColor(colors.HexColor("#EFF1FF"))
    c.setStrokeColor(colors.HexColor("#C7BFFE"))
    c.setLineWidth(0.5)
    c.roundRect(box_x, box_y, box_w, box_h, radius=box_h/2, fill=1, stroke=1)
    
    # 2.2 In chữ Label (Màu xám than chuyên nghiệp)
    text_y = box_y + 4.5 # Căn giữa chữ theo chiều dọc
    c.setFillColor(colors.HexColor("#374151")) 
    c.setFont("VnFont", 7.5)
    c.drawString(box_x + box_padding_x, text_y, cta_label)
    
    # 2.3 In chữ Link (Màu xanh dương đậm, Font Bold)
    c.setFillColor(colors.HexColor("#2563EB")) 
    c.setFont("VnFont-Bold", 7.5)
    c.drawString(box_x + box_padding_x + label_w, text_y, cta_link_text)
    
    # 2.4 Gạch chân chữ Link (Tạo cảm giác "Có thể Click" của giao diện Web)
    c.setStrokeColor(colors.HexColor("#2563EB"))
    c.setLineWidth(0.5)
    c.line(box_x + box_padding_x + label_w, text_y - 1, 
           box_x + box_padding_x + label_w + link_w, text_y - 1)

    # 2.5 Tạo vùng Click Box bọc toàn bộ Nút bấm
    c.linkURL(url_link, (box_x, box_y, box_x + box_w, box_y + box_h), relative=0)

    # =====================================================================
    # 3. Disclaimer và Phân trang
    # =====================================================================
    c.setFont("VnFont", 6.5)
    c.setFillColor(colors.HexColor("#9CA3AF")) # Chuyển màu xám mờ để tập trung mắt vào CTA
    c.drawString(MARGIN, 8, "FinSmartScreener – Báo cáo VIP NAV Edition.")
    
    c.drawRightString(PW - MARGIN, 8, f"Trang {page_num}/{total}  ·  {datetime.now().strftime('%d/%m/%Y %H:%M')}")

def _draw_vgm_badge(c, x, y, w, h, grade):
    grade  = str(grade).strip().upper()
    bg_col = VGM_COLORS_RL.get(grade, C_GREY)
    r = min(w, h) / 2 - 0.5
    cx = x + w / 2; cy = y + h / 2
    c.setFillColor(bg_col)
    c.circle(cx, cy, r, fill=1, stroke=0)
    # Tiny inner ring
    c.setStrokeColor(colors.HexColor("#FFFFFF")); c.setLineWidth(0.5)
    c.circle(cx, cy, r - 0.5, fill=0, stroke=1)
    c.setFont("VnFont-Bold", min(8.5, r * 1.45))
    c.setFillColor(colors.white)
    c.drawCentredString(cx, cy - 3, grade)

def _kpi_card(c, x, y, w, h, label, value, accent_color, icon=""):
    """
    KPI card: nền trắng sáng, viền nhạt, accent bar trên màu nổi,
    label xám nhỏ, value lớn đậm màu accent.
    """
    # Nền trắng
    c.setFillColor(colors.white)
    c.setStrokeColor(colors.HexColor("#C8DDEF")); c.setLineWidth(0.6)
    c.roundRect(x, y, w, h, radius=5, fill=1, stroke=1)
    # Accent bar trên 4pt
    c.setFillColor(accent_color)
    c.roundRect(x, y + h - 4, w, 4, radius=3, fill=1, stroke=0)
    # Label — xám nhạt nhỏ
    c.setFont("VnFont", 6); c.setFillColor(colors.HexColor("#6B8FAD"))
    c.drawCentredString(x + w/2, y + h - 15, label[:22])
    # Value — màu accent, to, bold
    val_str = str(value)[:10]
    sz = 15 if len(val_str) <= 5 else 11
    c.setFont("VnFont-Bold", sz); c.setFillColor(accent_color)
    c.drawCentredString(x + w/2, y + 8, val_str)

def _sec_title(c, text, x, y, width=None, color=None, size=9.0):
    """Section title với underline hai màu."""
    width = width or CW
    color = color or C_HEADER_DARK
    c.setFont("VnFont-Bold", size); c.setFillColor(color)
    c.drawString(x, y, text)
    # Underline: 24pt màu accent + phần còn lại nhạt
    c.setStrokeColor(C_ACCENT); c.setLineWidth(2.0)
    c.line(x, y - 4, x + 24, y - 4)
    c.setStrokeColor(C_LIGHT_GREY); c.setLineWidth(0.5)
    c.line(x + 24, y - 4, x + width, y - 4)

def _page2_mini_header(c, title, subtitle, page_color=None):
    """Header trang 2 & 3: tone sáng, đồng bộ trang 1."""
    hh = 46
    # Nền xanh nhạt
    c.setFillColor(colors.HexColor("#EBF4FF"))
    c.rect(0, PH - hh, PW, hh, fill=1, stroke=0)
    # Accent bar trên 4pt xanh đậm
    c.setFillColor(colors.HexColor("#0057B8"))
    c.rect(0, PH - 4, PW, 4, fill=1, stroke=0)
    # Viền dưới
    c.setStrokeColor(colors.HexColor("#BDD6F0")); c.setLineWidth(1.0)
    c.line(0, PH - hh, PW, PH - hh)

    # Logo trái
    c.setFont("VnFont-Bold", 11); c.setFillColor(colors.HexColor("#0057B8"))
    c.drawString(MARGIN, PH - 20, "FSS")
    lw = pdfmetrics.stringWidth("FSS", "VnFont-Bold", 11)
    c.setStrokeColor(colors.HexColor("#BDD6F0")); c.setLineWidth(1.0)
    c.line(MARGIN + lw + 5, PH - 24, MARGIN + lw + 5, PH - 10)
    c.setFont("VnFont", 9); c.setFillColor(colors.HexColor("#1A3A5C"))
    c.drawString(MARGIN + lw + 10, PH - 20, "Smart Screener")

    # Title trang ở giữa — đậm, tối
    c.setFont("VnFont-Bold", 12); c.setFillColor(colors.HexColor("#0A1E35"))
    c.drawCentredString(PW / 2, PH - 20, title)

    # Datetime phải
    c.setFont("VnFont", 7); c.setFillColor(colors.HexColor("#4A7090"))
    c.drawRightString(PW - MARGIN, PH - 16, datetime.now().strftime("%d/%m/%Y %H:%M"))

    # Subtitle nhỏ giữa
    c.setFont("VnFont", 6.8); c.setFillColor(colors.HexColor("#5A80A0"))
    c.drawCentredString(PW / 2, PH - 34, subtitle)

    # Breadcrumb trái
    c.setFont("VnFont", 6.5); c.setFillColor(colors.HexColor("#7A9FBF"))
    c.drawString(MARGIN, PH - 38, "FinSmartScreener  ·  Báo cáo danh mục lọc")

def _ai_box(c, text, x, y, w,
            box_color, border_color, accent_color,
            badge_label, badge_color=None):
    """AI insight box: border trái 4pt, nền nhạt, badge pill."""
    badge_color = badge_color or accent_color
    FONT_AI  = 7.5
    LINE_H   = 11.5
    MAX_W    = w - 28
    text = str(text).strip()
    
    def _wrap(txt):
        words = txt.split()
        wrapped, cur = [], ""
        for wrd in words:
            test = (cur + " " + wrd).strip()
            if pdfmetrics.stringWidth(test, "VnFont", FONT_AI) <= MAX_W:
                cur = test
            else:
                if cur: wrapped.append(cur)
                cur = wrd
        if cur: wrapped.append(cur)
        return wrapped or [""]

    lines = [l.strip() for l in text.split("\n") if l.strip()]
    wrapped_lines = []
    for line in lines[:4]:
        wrapped_lines.extend(_wrap(line))
        wrapped_lines.append(None)
    while wrapped_lines and wrapped_lines[-1] is None:
        wrapped_lines.pop()

    # 🟢 SỬA Ở ĐÂY: Tính toán chiều cao chính xác (Dòng chữ = 11.5pt, Khoảng ngắt ý = 4pt)
    content_h = sum(LINE_H if line is not None else 4 for line in wrapped_lines)
    ai_h = 26 + content_h + 8  # 26 là khoảng trống phía trên (chứa badge), 8 là padding ôm sát đáy

    # Shadow
    c.setFillColor(colors.HexColor("#D8E8F2"))
    c.roundRect(x + 1.5, y - ai_h - 1.5, w, ai_h, radius=4, fill=1, stroke=0)
    # Box
    c.setFillColor(box_color)
    c.setStrokeColor(border_color); c.setLineWidth(0.6)
    c.roundRect(x, y - ai_h, w, ai_h, radius=4, fill=1, stroke=1)
    # Left bar 4pt
    c.setFillColor(accent_color)
    c.roundRect(x, y - ai_h, 4, ai_h, radius=2, fill=1, stroke=0)

    # Badge pill
    badge_lbl_w = pdfmetrics.stringWidth(badge_label, "VnFont-Bold", 6.8)
    bw = 26 + badge_lbl_w + 6
    bx, by = x + 8, y - 16
    c.setFillColor(badge_color)
    c.roundRect(bx, by, bw, 13, radius=6, fill=1, stroke=0)
    # Spark icon (simple star shape via text)
    c.setFont("VnFont-Bold", 6.5); c.setFillColor(colors.white)
    c.drawString(bx + 4, by + 3.5, "AI")
    # Divider dot
    c.setFillColor(colors.HexColor("#FFFFFF88"))
    c.circle(bx + 17, by + 6.5, 1.2, fill=1, stroke=0)
    c.setFont("VnFont-Bold", 6.8); c.setFillColor(colors.white)
    c.drawString(bx + 20, by + 3.5, badge_label)

    # Text lines
    ty = y - 26
    is_first_in_bullet = True
    for wline in wrapped_lines:
        if wline is None:
            ty -= 4; is_first_in_bullet = True; continue
        # Bullet dot cho dòng đầu của mỗi bullet
        if is_first_in_bullet and wline.startswith("- "):
            c.setFillColor(accent_color)
            c.circle(x + 10, ty + 3, 2, fill=1, stroke=0)
            c.setFont("VnFont", FONT_AI); c.setFillColor(C_TEXT)
            c.drawString(x + 16, ty, wline[2:])
            is_first_in_bullet = False
        else:
            c.setFont("VnFont", FONT_AI); c.setFillColor(C_TEXT)
            c.drawString(x + 16, ty, wline)
            is_first_in_bullet = False
        ty -= LINE_H

    return y - ai_h

def _table_draw(c, headers, rows, x, y, widths,
                row_h=14, hdr_h=17, font_sz=7.0,
                right_cols=None, center_cols=None, vgm_col_idx=None,
                bold_red_cols=None, alt_row_start=True):
    """
    Bảng chuyên nghiệp: header nền đậm trắng, zebra sọc, border tinh tế.
    bold_red_cols: set of (row_idx, col_idx)
    """
    right_cols    = right_cols    or set()
    center_cols   = center_cols   or set()
    bold_red_cols = bold_red_cols or set()
    tw = sum(widths)

    # === HEADER ===
    # Nền header tối
    c.setFillColor(C_HDR_TABLE)
    c.roundRect(x, y - hdr_h, tw, hdr_h, radius=0, fill=1, stroke=0)
    # Accent line trên header
    c.setFillColor(C_ACCENT)
    c.rect(x, y, tw, 2, fill=1, stroke=0)

    cx = x
    for i, (h, w) in enumerate(zip(headers, widths)):
        lbl = str(h)[:24]
        c.setFont("VnFont-Bold", font_sz - 0.2)
        c.setFillColor(C_HDR_TEXT)
        if i in center_cols or i == vgm_col_idx:
            c.drawCentredString(cx + w/2, y - hdr_h + 5, lbl)
        elif i in right_cols:
            c.drawRightString(cx + w - 4, y - hdr_h + 5, lbl)
        else:
            c.drawString(cx + 5, y - hdr_h + 5, lbl)
        # Divider dọc nhạt giữa các cột
        if i < len(headers) - 1:
            c.setStrokeColor(colors.HexColor("#1E3A6A"))
            c.setLineWidth(0.4)
            c.line(cx + w, y - hdr_h + 3, cx + w, y - 1)
        cx += w
    y -= hdr_h

    # === ROWS ===
    for ri, row in enumerate(rows):
        # Zebra
        row_bg = C_STRIPE_EVEN if ri % 2 == 0 else C_STRIPE_ODD
        c.setFillColor(row_bg)
        c.rect(x, y - row_h, tw, row_h, fill=1, stroke=0)

        # Bottom border nhạt
        c.setStrokeColor(C_LIGHT_GREY); c.setLineWidth(0.3)
        c.line(x, y - row_h, x + tw, y - row_h)

        cx = x
        for ci, (cell, w) in enumerate(zip(row, widths)):
            txt = str(cell) if cell is not None else "—"

            if ci == vgm_col_idx:
                pad = 3
                _draw_vgm_badge(c, cx + pad, y - row_h + pad, w - 2*pad, row_h - 2*pad, txt)
                cx += w; continue

            is_bold_red = (ri, ci) in bold_red_cols
            if is_bold_red:
                c.setFont("VnFont-Bold", font_sz)
                fc = C_RED
            else:
                c.setFont("VnFont", font_sz)
                fc = C_TEXT
                # Auto-color số âm/dương
                try:
                    raw = txt.replace("%","").replace(",","").replace("+","").replace("x","")
                    num = float(raw)
                    if num < 0 and ci in right_cols: fc = C_RED
                    elif num > 0 and "%" in txt and ci in right_cols: fc = C_GREEN
                except Exception:
                    pass

            c.setFillColor(fc)
            if ci in center_cols:
                c.drawCentredString(cx + w/2, y - row_h + 4, txt[:24])
            elif ci in right_cols:
                c.drawRightString(cx + w - 4, y - row_h + 4, txt[:24])
            else:
                c.drawString(cx + 5, y - row_h + 4, txt[:34])
            cx += w

        y -= row_h

    # Outer border bottom
    c.setStrokeColor(C_CARD_BORDER); c.setLineWidth(0.6)
    c.line(x, y, x + tw, y)
    return y


# ══════════════════════════════════════════════════════════════
# BIỂU ĐỒ – Premium Style
# ══════════════════════════════════════════════════════════════

def _styled_ax(ax, title="", xlabel="", ylabel="", grid_axis="y"):
    """Áp dụng style Bloomberg cho axes."""
    ax.set_facecolor("#F5F9FD")
    for sp in ["top", "right"]:
        ax.spines[sp].set_visible(False)
    for sp in ["left", "bottom"]:
        ax.spines[sp].set_color("#C5D8EC")
        ax.spines[sp].set_linewidth(0.8)
    ax.grid(True, axis=grid_axis, color="#E0EBF5",
            linestyle="--", linewidth=0.5, alpha=0.8)
    if grid_axis == "both":
        ax.grid(True, axis="x", color="#E0EBF5",
                linestyle="--", linewidth=0.5, alpha=0.8)
    ax.tick_params(labelsize=7.5, colors="#4A6580", length=0, pad=3)
    if title:
        ax.set_title(title, fontsize=9.5, fontweight="bold",
                     color="#0A1628", loc="left", pad=8)
    if xlabel:
        ax.set_xlabel(xlabel, fontsize=8.5, color="#2A4A6A", labelpad=4)
    if ylabel:
        ax.set_ylabel(ylabel, fontsize=8.5, color="#2A4A6A", labelpad=4)


def _chart_scatter_pe_roe(df: pd.DataFrame, highlight_tickers=None):
    """Scatter P/E vs ROE — premium full-width."""
    try:
        needed = ["Ticker", "P/E", "ROE (%)"]
        if not all(c in df.columns for c in needed): return None
        sub = df[needed].copy()
        sub["P/E"]     = pd.to_numeric(sub["P/E"],     errors="coerce")
        sub["ROE (%)"] = pd.to_numeric(sub["ROE (%)"], errors="coerce")
        sub = sub.dropna()
        sub = sub[(sub["P/E"] > 0) & (sub["P/E"] < 65) & (sub["ROE (%)"] > -5)]
        if sub.empty: return None

        fig, ax = plt.subplots(figsize=(9.0, 4.2), facecolor="#FFFFFF")
        _styled_ax(ax, "Định Vị P/E vs ROE — Danh Mục",
                   xlabel="Chỉ số P/E (thấp = rẻ hơn)",
                   ylabel="ROE (%) — Sinh lời vốn chủ",
                   grid_axis="both")

        highlight = set(highlight_tickers or [])
        mask_h = sub["Ticker"].isin(highlight)

        # Non-highlight scatter: blue gradient by ROE
        sc = ax.scatter(sub.loc[~mask_h, "P/E"],
                        sub.loc[~mask_h, "ROE (%)"],
                        s=38, c=sub.loc[~mask_h, "ROE (%)"],
                        cmap="Blues", vmin=-5, vmax=40,
                        alpha=0.80, edgecolors="#3A7CBF",
                        linewidths=0.6, zorder=3)

        # Highlight (Defensive Pick) — diamond green
        if mask_h.any():
            ax.scatter(sub.loc[mask_h, "P/E"],
                       sub.loc[mask_h, "ROE (%)"],
                       s=140, c=MPL_GREEN, alpha=0.95, zorder=5,
                       marker="D", edgecolors="#0A3D1F", linewidths=0.9)
            for _, row in sub.loc[mask_h].iterrows():
                ax.annotate(
                    row["Ticker"],
                    (row["P/E"], row["ROE (%)"]),
                    fontsize=8, fontweight="bold", color="#0A3D1F",
                    xytext=(6, 5), textcoords="offset points",
                    bbox=dict(boxstyle="round,pad=0.2", fc="#E8F5E9",
                              ec="#81C784", alpha=0.85, lw=0.6))

        # Label non-highlight nổi bật
        for _, row in sub.loc[~mask_h].iterrows():
            if row["P/E"] > 22 or row["ROE (%)"] > 16 or row["P/E"] < 8:
                ax.annotate(
                    row["Ticker"],
                    (row["P/E"], row["ROE (%)"]),
                    fontsize=7, color="#4A6A90",
                    xytext=(3, 3), textcoords="offset points")

        # Quadrant reference lines
        ax.axvline(15, color=MPL_RED, lw=1.1, ls="--", alpha=0.5)
        ax.axhline(15, color=MPL_RED, lw=1.1, ls="--", alpha=0.5)

        # Ideal quadrant shading
        ylim = ax.get_ylim(); xlim = ax.get_xlim()
        ax.fill_betweenx([15, ylim[1]], xlim[0], 15,
                         color=MPL_GREEN, alpha=0.05)
        ax.text(0.013, 0.97, "▲ Vùng Lý Tưởng\n   (P/E thấp · ROE cao)",
                transform=ax.transAxes, fontsize=7.5,
                color="#1B5E20", ha="left", va="top", fontweight="bold",
                bbox=dict(boxstyle="round,pad=0.4", fc="#F1F8F4",
                          ec="#A5D6A7", alpha=0.92, lw=0.7))

        # Label P/E=15, ROE=15 trục
        ax.text(15.3, ylim[0] + 0.5, "P/E = 15×",
                fontsize=7, color=MPL_RED, alpha=0.7)
        ax.text(xlim[0] + 0.3, 15.4, "ROE = 15%",
                fontsize=7, color=MPL_RED, alpha=0.7)

        # Colorbar nhỏ
        cbar = fig.colorbar(sc, ax=ax, pad=0.01, shrink=0.75, aspect=20)
        cbar.set_label("ROE (%)", fontsize=7.5, color="#4A6580")
        cbar.ax.tick_params(labelsize=7, colors="#4A6580")
        cbar.outline.set_linewidth(0.5)

        from matplotlib.lines import Line2D
        legend_elements = [
            Line2D([0],[0], marker="o", color="w", markerfacecolor="#4A90D9",
                   markersize=8, label="Danh mục"),
            Line2D([0],[0], marker="D", color="w", markerfacecolor=MPL_GREEN,
                   markersize=9, label="Defensive Pick"),
        ]
        ax.legend(handles=legend_elements, fontsize=7.5, loc="lower right",
                  frameon=True, framealpha=0.92, edgecolor="#CBD8E8",
                  facecolor="white", borderpad=0.5)

        fig.tight_layout(pad=0.5)
        return fig
    except Exception as e:
        logger.warning(f"Scatter: {e}"); return None


def _chart_sector_donut(df: pd.DataFrame):
    """Donut chart ngành — professional: legend phải, % ở tâm."""
    try:
        sec_col = next((c for c in ["Sector","GICS Sector Name"] if c in df.columns), None)
        if not sec_col: return None
        counts = df[sec_col].value_counts().head(8)
        if counts.empty: return None

        pal = ["#0078D4","#1B7A4A","#7C3AED","#E65100",
               "#00B4D8","#C62828","#F59E0B","#2196F3"]
        fig, ax = plt.subplots(figsize=(4.2, 3.6), facecolor="#FFFFFF")

        wedges, _, autotexts = ax.pie(
            counts.values,
            autopct="%1.1f%%",
            colors=pal[:len(counts)],
            startangle=90,
            pctdistance=0.75,
            wedgeprops={"linewidth": 2.0, "edgecolor": "white", "width": 0.62})

        for at in autotexts:
            at.set_fontsize(7.5)
            at.set_fontweight("bold")
            at.set_color("white")

        # Số % lớn ở tâm hình tròn
        total = counts.sum()
        ax.text(0, 0, f"{len(counts)}\nNgành", ha="center", va="center",
                fontsize=9, fontweight="bold", color="#0A1628",
                linespacing=1.4)

        # Legend bên phải với colored patches
        patches = [mpatches.Patch(color=pal[i], label=f"{name} ({v/total*100:.0f}%)")
                   for i, (name, v) in enumerate(counts.items())]
        ax.legend(handles=patches, loc="center left",
                  bbox_to_anchor=(1.02, 0.5), fontsize=6.5,
                  frameon=False, handlelength=0.9, handleheight=0.9)

        ax.set_title("Phân Bổ Ngành", fontsize=9.5, fontweight="bold",
                     color="#0A1628", pad=8, loc="left")
        fig.tight_layout(pad=0.3)
        return fig
    except Exception as e:
        logger.warning(f"Sector donut: {e}"); return None


def _chart_roe_sector_bar(df: pd.DataFrame):
    """ROE trung bình theo ngành — horizontal bar với gradient color."""
    try:
        sec_col = next((c for c in ["Sector","GICS Sector Name"] if c in df.columns), None)
        if not sec_col or "ROE (%)" not in df.columns: return None
        grp = (df.groupby(sec_col)["ROE (%)"]
                 .mean().dropna().sort_values(ascending=True))
        if grp.empty: return None

        fig, ax = plt.subplots(figsize=(4.2, 3.6), facecolor="#FFFFFF")
        _styled_ax(ax, "ROE Trung Bình Theo Ngành",
                   xlabel="ROE (%)", grid_axis="x")
        ax.grid(True, axis="x", color="#E0EBF5",
                linestyle="--", linewidth=0.5, alpha=0.8)
        ax.grid(False, axis="y")

        # Color gradient: giá trị cao = xanh đậm hơn
        norm = plt.Normalize(vmin=grp.values.min(), vmax=max(grp.values.max(), 1))
        clrs = plt.cm.RdYlGn(norm(grp.values))  # Red-Yellow-Green colormap

        bars = ax.barh(grp.index, grp.values,
                       color=clrs, alpha=0.88,
                       edgecolor="white", linewidth=1.0,
                       height=0.65)

        for bar, val in zip(bars, grp.values):
            ha = "left" if val >= 0 else "right"
            offset = 0.3 if val >= 0 else -0.3
            color = "#1B5E20" if val >= 10 else ("#C62828" if val < 0 else "#333")
            ax.text(val + offset, bar.get_y() + bar.get_height()/2,
                    f"{val:.1f}%", va="center", fontsize=7.5,
                    fontweight="bold", color=color, ha=ha)

        ax.tick_params(axis="y", labelsize=7)
        ax.spines["left"].set_visible(False)
        ax.tick_params(left=False)
        fig.tight_layout(pad=0.4)
        return fig
    except Exception as e:
        logger.warning(f"ROE sector bar: {e}"); return None


def _chart_perf_grouped(df: pd.DataFrame):
    """Grouped bar: Hiệu suất 1T & 3T — styled."""
    try:
        cols_check = [c for c in ["Perf_1M", "Perf_3M"] if c in df.columns]
        if not cols_check or "Ticker" not in df.columns: return None

        sub = df[["Ticker"] + cols_check].copy()
        for c in cols_check:
            sub[c] = pd.to_numeric(sub[c], errors="coerce")
        sub = sub.dropna(subset=cols_check[:1]).head(14)
        if sub.empty: return None

        tickers = sub["Ticker"].tolist()
        x = np.arange(len(tickers))
        bw = 0.38

        fig, ax = plt.subplots(figsize=(4.2, 3.6), facecolor="#FFFFFF")
        _styled_ax(ax, "Hiệu Suất Ngắn Hạn (%)",
                   ylabel="Hiệu suất (%)")

        if "Perf_1M" in cols_check:
            v1 = sub["Perf_1M"].fillna(0).values
            c1 = [MPL_GREEN if v >= 0 else MPL_RED for v in v1]
            rects1 = ax.bar(x - bw/2, v1, width=bw, color=c1,
                            alpha=0.85, edgecolor="white",
                            linewidth=0.6, label="1 Tháng", zorder=3)

        if "Perf_3M" in cols_check:
            v3 = sub["Perf_3M"].fillna(0).values
            c3 = [MPL_BLUE if v >= 0 else MPL_ORANGE for v in v3]
            rects3 = ax.bar(x + bw/2, v3, width=bw, color=c3,
                            alpha=0.75, edgecolor="white",
                            linewidth=0.6, label="3 Tháng", zorder=3)

        # Zero line prominent
        ax.axhline(0, color="#555", lw=1.2, zorder=4)

        ax.set_xticks(x)
        ax.set_xticklabels(tickers, rotation=40, ha="right",
                           fontsize=7, fontweight="bold")
        ax.legend(fontsize=7.5, loc="upper right",
                  frameon=True, framealpha=0.9, edgecolor="#CBD8E8")
        fig.tight_layout(pad=0.4)
        return fig
    except Exception as e:
        logger.warning(f"Perf grouped: {e}"); return None


def _chart_vgm_radar_or_bar(df: pd.DataFrame):
    """Radar chart VGM hoặc Bar fallback — premium style."""
    radar_cols = {
        "Value":    ["P/E", "P/B"],
        "Growth":   ["Perf_3M", "Perf_1M"],
        "Momentum": ["RSI_14", "RS_1M"],
        "Quality":  ["ROE (%)", "Net Margin (%)"],
    }
    try:
        scores = {}
        for dim, cols in radar_cols.items():
            vals = []
            for col in cols:
                if col in df.columns:
                    s = pd.to_numeric(df[col], errors="coerce").dropna()
                    if not s.empty:
                        mn, mx = s.min(), s.max()
                        if mx > mn:
                            norm = (s - mn) / (mx - mn)
                            if col in ["P/E", "P/B"]:
                                norm = 1 - norm
                            vals.append(norm.mean() * 10)
            if vals:
                scores[dim] = round(float(np.mean(vals)), 1)

        if len(scores) >= 3:
            categories = list(scores.keys())
            values     = [scores[c] for c in categories]
            N = len(categories)
            angles = [n / float(N) * 2 * math.pi for n in range(N)]
            angles += angles[:1]
            values_plot = values + values[:1]

            fig, ax = plt.subplots(figsize=(4.2, 3.6),
                                   subplot_kw={"polar": True},
                                   facecolor="#FFFFFF")
            ax.set_facecolor("#F5F9FD")
            ax.set_theta_offset(math.pi / 2)
            ax.set_theta_direction(-1)
            ax.set_ylim(0, 10)

            # Grid rings
            for r in [2, 4, 6, 8, 10]:
                ax.plot(angles, [r] * len(angles), color="#C5D8EC",
                        lw=0.6, linestyle="--")

            ax.set_yticks([2, 4, 6, 8, 10])
            ax.set_yticklabels(["2","4","6","8","10"],
                               fontsize=6, color="#8899AA")
            ax.set_xticks(angles[:-1])
            ax.set_xticklabels(categories, fontsize=8.5,
                               fontweight="bold", color="#0A1628")
            ax.tick_params(axis='y', colors='#8899AA')

            # Gradient fill effect (draw 3 layers)
            for alpha, lw in [(0.10, 0), (0.18, 0), (0.0, 2.2)]:
                if alpha > 0:
                    ax.fill(angles, values_plot, alpha=alpha, color=MPL_BLUE)
                else:
                    ax.plot(angles, values_plot, "o-", linewidth=lw,
                            color=MPL_BLUE, zorder=5)

            ax.fill(angles, values_plot, alpha=0.18, color=MPL_BLUE)
            ax.plot(angles, values_plot, "o-", linewidth=2.2,
                    color=MPL_BLUE, zorder=5)

            # Point markers lớn hơn
            ax.scatter(angles[:-1], values,
                       s=50, color=MPL_BLUE,
                       edgecolors="white", linewidths=1.2, zorder=6)

            # Score labels
            for angle, val in zip(angles[:-1], values):
                ax.annotate(f"{val:.1f}",
                            xy=(angle, val),
                            xytext=(0, 9), textcoords="offset points",
                            ha="center", fontsize=8,
                            fontweight="bold", color=MPL_BLUE)

            ax.set_title("VGM Score Radar\n(Trung bình danh mục)",
                         fontsize=9, fontweight="bold",
                         pad=16, color="#0A1628")
            ax.spines["polar"].set_color("#C5D8EC")
            ax.spines["polar"].set_linewidth(0.6)
            fig.tight_layout(pad=0.4)
            return fig
    except Exception as e:
        logger.warning(f"Radar attempt: {e}")

    # Fallback: VGM Grade Bar
    try:
        if "VGM Score" not in df.columns: return None
        counts = df["VGM Score"].value_counts().reindex(
            ["A","B","C","D","F"], fill_value=0)
        pal_vgm = {"A":MPL_GREEN,"B":MPL_BLUE,"C":MPL_AMBER,
                   "D":MPL_ORANGE,"F":MPL_RED}
        fig, ax = plt.subplots(figsize=(4.2, 3.6), facecolor="#FFFFFF")
        _styled_ax(ax, "Phân Bổ VGM Score", ylabel="Số mã")

        clrs = [pal_vgm.get(g, "#888") for g in counts.index]
        bars = ax.bar(counts.index, counts.values,
                      color=clrs, edgecolor="white",
                      linewidth=1.2, width=0.55, zorder=3)
        for bar, val in zip(bars, counts.values):
            if val > 0:
                ax.text(bar.get_x() + bar.get_width()/2,
                        bar.get_height() + 0.15, str(val),
                        ha="center", va="bottom",
                        fontsize=9, fontweight="bold", color="#333")
        ax.set_ylim(0, counts.max() * 1.25)
        fig.tight_layout(pad=0.3)
        return fig
    except Exception as e:
        logger.warning(f"VGM bar fallback: {e}"); return None


# ============================================================
# AI SUMMARY (Gemini) – JSON format 4 keys (VIP CLIENT MINDSET)
# ============================================================
import json

# ============================================================
# AI SUMMARY (Gemini) – JSON format 3 keys (VIP CLIENT MINDSET - 4 BULLETS/KEY)
# ============================================================
def _gemini_summary(df_top: pd.DataFrame, ncn_tickers: list,
                    strategy_label: str = "Phong Thu") -> dict:
    # 1. Cập nhật Default Fallback: THÊM Ý THỨ 4 CHO MỖI MỤC
    default = {
        "market": (
            "- Ưu tiên bảo toàn vốn lên hàng đầu trong bối cảnh vĩ mô biến động.\n"
            "- Dòng tiền hoạt động kinh doanh (CFO) dương liên tục là bộ lọc thép để loại bỏ lợi nhuận ảo.\n"
            "- Phân bổ trọng tâm vào nhóm doanh nghiệp chia cổ tức tiền mặt đều đặn, không pha loãng vốn.\n"
            "- Khuyến nghị: Duy trì tỷ trọng tiền mặt dự phòng 15-20% để sẵn sàng gom hàng khi thị trường rung lắc." # <== Ý 4
        ),
        "valuation": (
            "- P/E trung bình danh mục được ép chặt, loại bỏ hoàn toàn bẫy định giá đắt.\n"
            "- Tỷ suất cổ tức cao đóng vai trò là 'tấm đệm an toàn' (Yield Cushion) bảo vệ NAV.\n"
            "- Lợi thế cạnh tranh được chứng minh bằng ROE thực, không đến từ đòn bẩy D/E.\n"
            "- Hành động: Kiên nhẫn chờ đợi cổ phiếu điều chỉnh về vùng mua an toàn, tuyệt đối không FOMO mua đuổi." # <== Ý 4
        ),
        "risk": (
            "- Rủi ro kẹp thanh khoản là án tử với NAV lớn, tuyệt đối né các mã có Vol < 500,000 cp/phiên.\n"
            "- Các mã có tỷ lệ D/E > 1.5x đang bị cảnh báo đỏ (Red Flags), cần cơ cấu giảm tỷ trọng.\n"
            "- Đứng ngoài các game thao túng giá, tập trung vào tài sản có tính minh bạch cao.\n"
            "- Kỷ luật: Tuân thủ chặt chẽ các mốc cắt lỗ tự động để bảo vệ tài khoản khỏi những sự cố bất ngờ." # <== Ý 4
        ),
    }
    
    try:
        import google.generativeai as genai
        api_key = os.environ.get("GEMINI_API_KEY", "")
        if not api_key: raise ValueError("No GEMINI_API_KEY")
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-2.5-flash-lite")
        
        # 2. Xử lý dữ liệu định lượng
        avg_pe  = df_top["P/E"].dropna().mean()     if "P/E"     in df_top.columns else None
        avg_roe = df_top["ROE (%)"].dropna().mean() if "ROE (%)" in df_top.columns else None
        avg_de  = df_top["D/E"].dropna().mean()     if "D/E"     in df_top.columns else None
        ncn_str = ", ".join(ncn_tickers[:3]) if ncn_tickers else "N/A"
        
        # 3. Ép số liệu thực tế
        top3_stats_str = "N/A"
        if ncn_tickers and "Ticker" in df_top.columns:
            df_top3 = df_top[df_top["Ticker"].isin(ncn_tickers[:3])]
            stats_list = []
            for _, row in df_top3.iterrows():
                tk = row.get("Ticker", "")
                pe = row.get("P/E", 0)
                roe = row.get("ROE (%)", 0)
                cfo = row.get("CFO", "Dương") 
                div = row.get("Dividend_Yield", ">5%")
                stats_list.append(f"{tk} (P/E:{pe:.1f}, ROE:{roe:.1f}%, Cổ tức:{div}, CFO:{cfo})")
            top3_stats_str = " | ".join(stats_list)

        # 4. Prompt Engineering: Yêu cầu AI viết 4 gạch đầu dòng và cấm text rác
        prompt = f"""Đóng vai trò là Giám đốc Tư vấn Đầu tư cấp cao tại Vietcap, đang thuyết trình cho tệp khách VIP (NAV > 50 tỷ).
Chiến lược hiện tại: [{strategy_label}]. Triết lý: Lợi nhuận có thể là giả, nhưng dòng tiền (CFO) phải là thật.
Dữ liệu tổng quan: P/E TB: {f'{avg_pe:.1f}' if avg_pe else 'N/A'}x, ROE TB: {f'{avg_roe:.1f}' if avg_roe else 'N/A'}%, D/E TB: {f'{avg_de:.2f}' if avg_de else 'N/A'}x.
Dữ liệu Top 3 Phòng Thủ: {top3_stats_str}.

Yêu cầu: Viết BẰNG TIẾNG VIỆT CÓ DẤU, giọng văn thực chiến, sắc bén, dứt khoát.

QUAN TRỌNG NHẤT BẮT BUỘC PHẢI TUÂN THỦ:
1. TRẢ VỀ DUY NHẤT MỘT OBJECT JSON.
2. KHÔNG BAO GIỜ thêm các câu giao tiếp như "Dưới đây là...", "Tuyệt vời!".
3. KHÔNG sử dụng thẻ markdown (như ```json hay ```).

TRẢ VỀ ĐÚNG ĐỊNH DẠNG OBJECT JSON NHƯ SAU (Bắt buộc phải có 3 keys, mỗi key phải có đúng 4 gạch đầu dòng):
{{
  "market": "- (Viết 4 gạch đầu dòng, mỗi gạch dưới 25 chữ. 3 ý đầu đánh giá vĩ mô/bảo toàn vốn, ý 4 đưa ra lời khuyên tỷ trọng nắm giữ tiền mặt dự phòng hợp lý)",
  "valuation": "- (Viết 4 gạch đầu dòng. 3 ý đầu BẮT BUỘC dùng số liệu P/E, ROE, Cổ tức của {ncn_str} làm dẫn chứng, ý 4 khuyên khách hàng kiên nhẫn chờ điểm mua an toàn, không FOMO)",
  "risk": "- (Viết 4 gạch đầu dòng. 3 ý đầu chỉ ra rủi ro thanh khoản yếu/đòn bẩy D/E cao ở các mã rác, ý 4 chốt lại kỷ luật tuân thủ vùng cắt lỗ tự động)"
}}"""
        
        # 5. Parsing & Error Handling (Bộ giáp chống lỗi "Tuyệt vời! Dưới đây là...")
        raw  = model.generate_content(prompt).text or ""
        
        # Tiền xử lý: Cắt gọt text rác
        cleaned_text = raw.replace("```json", "").replace("```", "").strip()
        start_idx = cleaned_text.find('{')
        end_idx = cleaned_text.rfind('}')
        
        if start_idx != -1 and end_idx != -1:
            cleaned_text = cleaned_text[start_idx:end_idx+1]
        else:
            cleaned_text = "" 

        if not cleaned_text or not cleaned_text.startswith("{"):
            logger.warning(f"Gemini trả về text không hợp lệ. Raw: {repr(raw[:80])}")
            return default

        # Bóc tách JSON
        parsed = json.loads(cleaned_text)
        
        for k in ("market", "valuation", "risk"):
            if k not in parsed or not parsed[k]:
                parsed[k] = default[k]
                
        return parsed
        
    except json.JSONDecodeError as e:
        logger.error(f"Lỗi JSON Decode từ Gemini: {e}. Cleaned text: {cleaned_text}")
        return default
    except Exception as e:
        logger.warning(f"Gemini API Error/Skip: {e}")
        return default

# ══════════════════════════════════════════════════════════════
# DETECT STRATEGY
# ══════════════════════════════════════════════════════════════
def _detect_strategy(active_filters: dict) -> tuple:
    if not active_filters:
        return "Phòng Thủ", "Chiến lược Phòng Thủ"
    pe_val = roe_val = div_val = None
    for fid, entry in active_filters.items():
        if not isinstance(entry, dict): continue
        val = entry.get("value")
        if isinstance(val, list) and len(val) == 2:
            if "pe"  in fid.lower(): pe_val  = val[1]
            if "roe" in fid.lower(): roe_val = val[0]
            if "div" in fid.lower(): div_val = val[0]
    if pe_val  is not None and float(pe_val)  > 20: return "Tăng Trưởng / Khám Phá", "Chiến lược Tăng Trưởng – Khám Phá Cơ Hội"
    if div_val is not None and float(div_val) >= 4:  return "Thu Nhập Cổ Tức", "Chiến lược Thu Nhập – Cổ Tức Cao"
    if roe_val is not None and float(roe_val) >= 15: return "Chất Lượng Cao", "Chiến lược Chất Lượng – ROE Vượt Trội"
    return "Phòng Thủ", "Chiến lược Phòng Thủ – Bảo Toàn Vốn"


# ══════════════════════════════════════════════════════════════
# DATA PREP
# ══════════════════════════════════════════════════════════════
def _calc_target_stoploss(price, sma20=None, sma50=None):
    try:
        p = float(price)
        if p <= 0: return "—","—"
        target = f"{p*0.97:,.0f}–{p:,.0f}"
        sl_val = (float(sma20)*0.99 if sma20 and float(sma20) > 0 else
                  float(sma50)*0.99 if sma50 and float(sma50) > 0 else p*0.92)
        return target, f"{sl_val:,.0f}"
    except Exception:
        return "—","—"

def _recommend_action(roe, pe, rsi, de, vgm):
    try:
        rsi_v = float(rsi) if rsi else 50
        pe_v  = float(pe)  if pe  else 99
        roe_v = float(roe) if roe else 0
        vgm_s = str(vgm).strip().upper()
        if rsi_v > 72: return "Hạn chế mua"
        if rsi_v < 35 and vgm_s in ("A","B"): return "Có thể mua thêm"
        if pe_v < 12 and roe_v > 20 and vgm_s in ("A","B"): return "Tích lũy"
        if vgm_s in ("D","F"): return "Cẩn thận"
        if pe_v < 15 and roe_v > 15: return "Mua / Tích lũy"
        return "Theo dõi"
    except Exception:
        return "—"

# 🟢 THÊM THAM SỐ red_flags
def _prepare_main_table(df: pd.DataFrame, max_rows: int = 20, red_flags: set = None) -> list:
    if red_flags is None: red_flags = set()
    rows = []
    num_cols = ["Price Close","P/E","ROE (%)","D/E","RSI_14","RS_1M","SMA20","SMA50","Avg_Vol_20D"]
    for col in num_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    if "Avg_Vol_20D" in df.columns:
        df = df[df["Avg_Vol_20D"].fillna(0) >= MIN_LIQUIDITY]
    if "Price Close" in df.columns:
        df = df[df["Price Close"].fillna(0) >= 3000]
    if "P/E" in df.columns:
        pe_s = df["P/E"]
        df = df[pe_s.isna() | ((pe_s > 0) & (pe_s < 150))]
    grade_order = {"A":1,"B":2,"C":3,"D":4,"F":5}
    if "VGM Score" in df.columns:
        df["_sort"] = df["VGM Score"].map(grade_order).fillna(6)
        df = df.sort_values("_sort").drop(columns=["_sort"])
    for _, r in df.head(max_rows).iterrows():
        ticker  = str(r.get("Ticker","—"))
        company = _company_name(ticker, r.to_dict(), max_len=30)
        vgm     = str(r.get("VGM Score","—")).strip().upper()
        price   = r.get("Price Close")
        target, stoploss = _calc_target_stoploss(price, r.get("SMA20"), r.get("SMA50"))
        action  = _recommend_action(r.get("ROE (%)"), r.get("P/E"),
                                    r.get("RSI_14"), r.get("D/E"), vgm)
        # 🟢 GHI ĐÈ KHUYẾN NGHỊ: Nếu mã nằm trong Red Flags, tuyệt đối không cho Mua
        if ticker in red_flags:
            action = "Theo dõi (Có Rủi Ro)"
        rows.append([
            vgm, ticker, company, action, target, stoploss,
            _sv(r.get("P/E"),     "dec1"),
            _sv(r.get("ROE (%)"), "dec1", "%"),
        ])
    return rows

# 🟢 THÊM THAM SỐ red_flags
def _prepare_ncn_rows(df: pd.DataFrame, top_n: int = 3, red_flags: set = None) -> list:
    if red_flags is None: red_flags = set()
    try:
        df_ncn = df.copy()
        
        # 🟢 LỌC BỎ NGAY CÁC MÃ DÍNH RED FLAG KHỎI DANH MỤC PHÒNG THỦ
        if "Ticker" in df_ncn.columns:
            df_ncn = df_ncn[~df_ncn["Ticker"].isin(red_flags)]
        for col in ["ROE (%)","D/E","Net Margin (%)","Price Close","SMA20","SMA50","Avg_Vol_20D"]:
            if col in df_ncn.columns:
                df_ncn[col] = pd.to_numeric(df_ncn[col], errors="coerce")
        sec_col = next((c for c in ["Sector","GICS Sector Name"] if c in df_ncn.columns), None)
        if sec_col: df_ncn = df_ncn[~df_ncn[sec_col].isin(EXCLUDE_SECTORS_NCN)]
        if "Avg_Vol_20D"   in df_ncn.columns: df_ncn = df_ncn[df_ncn["Avg_Vol_20D"].fillna(0)  >= MIN_LIQUIDITY]
        if "ROE (%)"       in df_ncn.columns: df_ncn = df_ncn[df_ncn["ROE (%)"].fillna(0)       >= 15]
        if "D/E"           in df_ncn.columns: df_ncn = df_ncn[df_ncn["D/E"].fillna(999)         <= 1.5]
        if "Net Margin (%)" in df_ncn.columns: df_ncn = df_ncn[df_ncn["Net Margin (%)"].fillna(0) >= 5]
        grade_order = {"A":1,"B":2,"C":3,"D":4,"F":5}
        df_ncn["_g"]   = df_ncn.get("VGM Score", pd.Series(dtype=str)).map(grade_order).fillna(6)
        df_ncn["_roe"] = df_ncn["ROE (%)"].fillna(0) if "ROE (%)" in df_ncn.columns else 0
        df_ncn = df_ncn.sort_values(["_g","_roe"], ascending=[True,False])
        rows = []
        for _, r in df_ncn.head(top_n).iterrows():
            price = r.get("Price Close")
            _, stoploss = _calc_target_stoploss(price, r.get("SMA20"), r.get("SMA50"))
            rows.append({
                "ticker":   str(r.get("Ticker","—")),
                "company":  _company_name(str(r.get("Ticker","—")), r.to_dict(), max_len=26),
                "exchange": str(r.get("Exchange","") or "")[:5],
                "vgm":      str(r.get("VGM Score","—")),
                "roe":      _sv(r.get("ROE (%)"), "dec1", "%"),
                "pe":       _sv(r.get("P/E"), "dec1"),
                "stoploss": stoploss,
            })
        return rows
    except Exception as e:
        logger.warning(f"NCN rows: {e}"); return []

def _prepare_flag_rows(df: pd.DataFrame, max_flags: int = 12) -> list:
    flags_de, flags_pe, flags_rsi, flags_mom = [], [], [], []
    seen = set()
    def _action(reason):
        if "D/E"      in reason: return "Giảm tỷ trọng, kiểm tra nợ vay"
        if "P/E <"    in reason: return "Nghi ngờ xào nấu BCTC" # Thêm dòng này
        if "P/E"      in reason: return "Hạn chế mua đuổi, chờ điều chỉnh"
        if "RSI"      in reason: return "Tránh mua đuổi, đặt stop-loss"
        if "Momentum" in reason: return "Theo dõi, chưa vào thêm"
        return "Cẩn thận"
    for _, r in df.iterrows():
        ticker = str(r.get("Ticker","—"))
        if ticker in seen: continue
        try:
            de = float(r.get("D/E")) if pd.notnull(r.get("D/E")) else None
            if de and de > 2.0:
                flags_de.append((ticker,"D/E cao",f"{de:.2f}x","≤2.0x","(!) Đòn bẩy cao",_action("D/E")))
                seen.add(ticker); continue
        except: pass
        try:
            rsi = float(r.get("RSI_14")) if pd.notnull(r.get("RSI_14")) else None
            if rsi and rsi > 72:
                flags_rsi.append((ticker,"RSI > 72",f"{rsi:.0f}","≤70","(!) Quá mua",_action("RSI")))
                seen.add(ticker); continue
        except: pass
        try:
            pe = float(r.get("P/E")) if pd.notnull(r.get("P/E")) else None
            # 🟢 FIX: Bắt bẫy giá trị (Value Trap) khi P/E quá thấp một cách vô lý
            if pe and 0 < pe < 3.5:
                flags_pe.append((ticker, "P/E < 3.5x", f"{pe:.1f}x", "> 5.0x", "(!) Lợi nhuận đột biến", "Tránh bẫy giá trị, soi LN khác"))
                seen.add(ticker); continue
        except: pass
        try:
            pm = float(r.get("Perf_1M")) if pd.notnull(r.get("Perf_1M")) else None
            if pm is not None and pm < 0:
                flags_mom.append((ticker,"Momentum âm",f"{pm:+.1f}%",">0%","(!) Giảm 1 tháng",_action("Momentum")))
                seen.add(ticker)
        except: pass
    return (flags_de + flags_rsi + flags_pe + flags_mom)[:max_flags]


# ══════════════════════════════════════════════════════════════
# TRANG 1 – THE PITCH & THE PORTFOLIO
# ══════════════════════════════════════════════════════════════
# 🟢 Thêm red_flags vào tham số
def _render_page1(c, stats, ai_texts, filter_params, strategy_title, df_top, red_flags):
    _bg(c)

    # ══════════════════════════════════════════════════════
    # HEADER TRANG 1 — Light professional style
    # Nền trắng xanh nhạt, chữ tối rõ ràng, 3 dòng tách biệt
    # ══════════════════════════════════════════════════════
    HDR_BAND_H = 68

    # Nền header xanh nhạt gradient-ish (2 rect để tạo hiệu ứng)
    c.setFillColor(colors.HexColor("#EBF4FF"))
    c.rect(0, PH - HDR_BAND_H, PW, HDR_BAND_H, fill=1, stroke=0)
    c.setFillColor(colors.HexColor("#F5F9FF"))
    c.rect(0, PH - HDR_BAND_H + 20, PW, 20, fill=1, stroke=0)

    # Accent bar trên 4pt xanh đậm
    c.setFillColor(colors.HexColor("#0057B8"))
    c.rect(0, PH - 4, PW, 4, fill=1, stroke=0)

    # Đường kẻ dưới header
    c.setStrokeColor(colors.HexColor("#BDD6F0")); c.setLineWidth(1.0)
    c.line(0, PH - HDR_BAND_H, PW, PH - HDR_BAND_H)

    # ── DÒNG 1 (y=PH-22): Logo FSS | tagline | "BÁO CÁO" | datetime ──
    y1 = PH - 21

    # "FSS" xanh đậm bold
    c.setFont("VnFont-Bold", 14); c.setFillColor(colors.HexColor("#0057B8"))
    c.drawString(MARGIN, y1, "FSS")
    lw_fss = pdfmetrics.stringWidth("FSS", "VnFont-Bold", 14)

    # Divider dọc
    c.setStrokeColor(colors.HexColor("#BDD6F0")); c.setLineWidth(1.2)
    c.line(MARGIN + lw_fss + 6, y1 - 2, MARGIN + lw_fss + 6, y1 + 12)

    # "Smart Screener" xám đậm
    c.setFont("VnFont", 11); c.setFillColor(colors.HexColor("#1A3A5C"))
    c.drawString(MARGIN + lw_fss + 12, y1, "Smart Screener")
    sw_ss = pdfmetrics.stringWidth("Smart Screener", "VnFont", 11)

    # Tagline nhỏ xám nhạt
    c.setFont("VnFont", 7.5); c.setFillColor(colors.HexColor("#5A80A0"))
    c.drawString(MARGIN + lw_fss + sw_ss + 20, y1 + 1,
                 "Phân tích cổ phiếu chuyên sâu · Thị trường VN")

    # Góc phải: "BÁO CÁO DANH MỤC LỌC" xanh đậm bold
    c.setFont("VnFont-Bold", 8.5); c.setFillColor(colors.HexColor("#0057B8"))
    c.drawRightString(PW - MARGIN, y1, "BÁO CÁO DANH MỤC LỌC")

    # ── DÒNG 2 (y=PH-41): Tên chiến lược to + datetime bên phải ──
    y2 = PH - 41

    # Tên chiến lược — đen đậm lớn, nổi bật
    c.setFont("VnFont-Bold", 16); c.setFillColor(colors.HexColor("#0A1E35"))
    c.drawString(MARGIN, y2, strategy_title[:48])

    # Datetime — góc phải, xám nhạt
    c.setFont("VnFont", 7.5); c.setFillColor(colors.HexColor("#4A7090"))
    c.drawRightString(PW - MARGIN, y2,
                      datetime.now().strftime("%d/%m/%Y  %H:%M"))

    # ── DÒNG 3 (y=PH-57): Số mã phù hợp + Exchange badges ──
    y3 = PH - 57

    # Số mã — xám đậm vừa
    c.setFont("VnFont", 7.5); c.setFillColor(colors.HexColor("#3A6080"))
    c.drawString(MARGIN, y3,
                 f"{stats['total']:,} mã phù hợp bộ lọc  ·  Top {stats['display']} mã hiển thị")

    # Exchange badges nhỏ — căn phải, KHÔNG đè lên chữ
    badge_items = [
        ("HOSE",  "#0057B8"),
        ("HNX",   "#1B7A4A"),
        ("UPCoM", "#6A0DAD"),
    ]
    bx_right = PW - MARGIN
    for exch, bg_hex in reversed(badge_items):
        bw = pdfmetrics.stringWidth(exch, "VnFont-Bold", 6.5) + 12
        bx_right -= bw
        c.setFillColor(colors.HexColor(bg_hex))
        c.roundRect(bx_right, y3 - 2, bw, 13, radius=3, fill=1, stroke=0)
        c.setFont("VnFont-Bold", 6.5); c.setFillColor(colors.white)
        c.drawCentredString(bx_right + bw/2, y3 + 2, exch)
        bx_right -= 5

    # ══════════════════════════════════════════════════════
    # 6 KPI CARDS — nền trắng, viền nhạt, số đậm màu
    # ══════════════════════════════════════════════════════
    kpi_h = 42; kpi_gap = 6
    kpi_y_top = PH - HDR_BAND_H - 8
    kpi_w = (CW - 5 * kpi_gap) / 6

    kpi_data = [
        ("TỔNG MÃ LỌC",    f"{stats['total']:,}",      colors.HexColor("#0057B8")),
        ("HIỂN THỊ",        str(stats["display"]),       colors.HexColor("#0284C7")),
        ("SỐ MÃ ĐIỂM A (5 SAO)",        str(stats["grade_a_count"]), colors.HexColor("#059669")),
        ("P/E TRUNG BÌNH",  stats["avg_pe"],             colors.HexColor("#D97706")),
        ("ROE TRUNG BÌNH",  stats["avg_roe"],            colors.HexColor("#16A34A")),
        ("SỐ NGÀNH (GICS)",        str(stats["sectors_count"]), colors.HexColor("#7C3AED")),
    ]
    for i, (lbl, val, col) in enumerate(kpi_data):
        _kpi_card(c,
                  MARGIN + i * (kpi_w + kpi_gap),
                  kpi_y_top - kpi_h,
                  kpi_w, kpi_h, lbl, val, col)

    y0 = kpi_y_top - kpi_h - 14

    # ── Filter tags ──
    if filter_params:
        n_rows = max(1, math.ceil(len(filter_params) / 6))
        box_h  = 18 + n_rows * 13
        c.setFillColor(colors.HexColor("#F0F7FF"))
        c.setStrokeColor(C_CARD_BORDER); c.setLineWidth(0.5)
        c.roundRect(MARGIN, y0 - box_h, CW, box_h, radius=3, fill=1, stroke=1)
        c.setFillColor(C_BLUE)
        c.rect(MARGIN, y0-box_h, 3, box_h, fill=1, stroke=0)
        c.setFont("VnFont-Bold", 7); c.setFillColor(C_BLUE)
        c.drawString(MARGIN+7, y0-11, "Bộ lọc đang áp dụng:")
        tx, ty = MARGIN + 110, y0 - 11
        for param in filter_params:
            tw_p = pdfmetrics.stringWidth(param,"VnFont",6.5) + 10
            if tx + tw_p > PW - MARGIN - 4:
                tx = MARGIN + 7; ty -= 13
            c.setFillColor(colors.HexColor("#DCE8F8"))
            c.roundRect(tx, ty-7, tw_p, 11, radius=3, fill=1, stroke=0)
            c.setFont("VnFont", 6.5); c.setFillColor(C_TEXT)
            c.drawString(tx+4, ty-4, param)
            tx += tw_p + 4
        y0 -= box_h + 10

    # ── AI Market Overview ──
    _sec_title(c, "Bối Cảnh Vĩ Mô & Chiến Lược Chung  ·  AI Market Overview",
               MARGIN, y0, color=C_PURPLE)
    y0 -= 11
    y0 = _ai_box(c, ai_texts.get("market",""),
                 MARGIN, y0, CW,
                 box_color=C_PURPLE_SOFT,
                 border_color=C_PURPLE_BORDER,
                 accent_color=C_PURPLE,
                 badge_label="Gemini 2.5 Flash Lite",
                 badge_color=C_PURPLE)
    y0 -= 13

    # ── Bảng Danh Mục Chính ──
    n_show = min(stats["display"], 20)
    _sec_title(c, f"Danh Mục Cổ Phiếu Lọc  ·  Top {n_show} mã  ·  Đã lọc thanh khoản",
               MARGIN, y0)
    y0 -= 12

    col_props = [
        ("VGM",        0.050),
        ("Mã CK",      0.080),
        ("Tên công ty",0.218),
        ("Khuyến nghị",0.118),
        ("Vùng mua",   0.145),
        ("Cắt lỗ",     0.100),
        ("P/E",        0.068),
        ("ROE %",      0.082),
    ]
    tot_w = sum(p for _,p in col_props)
    main_widths = [CW * p / tot_w for _,p in col_props]
    main_hdrs   = [h for h,_ in col_props]

    available_h = y0 - Y_MIN
    row_h = 20; hdr_h = 19
    max_rows = max(3, int((available_h - hdr_h) / row_h))
    # Kéo xuống phần gọi _prepare_main_table, thêm red_flags vào:
    table_rows = _prepare_main_table(df_top, max_rows=min(max_rows, n_show), red_flags=red_flags)

    if table_rows:
        _table_draw(c, main_hdrs, table_rows, MARGIN, y0, main_widths,
                    row_h=row_h, hdr_h=hdr_h, font_sz=6.8,
                    right_cols={6,7}, center_cols={3}, vgm_col_idx=0)
    else:
        c.setFont("VnFont", 9); c.setFillColor(C_GREY)
        c.drawCentredString(PW/2, y0-22, "Không có mã nào phù hợp sau khi lọc thanh khoản.")

    _footer(c, 1)


# ══════════════════════════════════════════════════════════════
# TRANG 2 – VALUATION & FUNDAMENTALS
# ══════════════════════════════════════════════════════════════
def _render_page2(c, df_top, ncn_tickers, ai_texts):
    _bg(c)
    _page2_mini_header(c,
        "Phân Tích Định Giá & Sức Khỏe Tài Chính",
        "Định vị P/E vs ROE  ·  Phân bổ ngành  ·  ROE theo ngành",
        page_color=colors.HexColor("#071830"))

    y0 = PH - 58

    # AI Valuation Insight
    _sec_title(c, "Nhận Xét Định Giá & ROE  ·  AI Valuation Insight",
               MARGIN, y0, color=C_BLUE)
    y0 -= 11
    y0 = _ai_box(c, ai_texts.get("valuation",""),
                 MARGIN, y0, CW,
                 box_color=C_BLUE_SOFT,
                 border_color=C_BLUE_BORDER,
                 accent_color=C_BLUE,
                 badge_label="Gemini 2.5 Flash Lite",
                 badge_color=C_BLUE)
    y0 -= 13

    # Scatter full-width
    # 1. Vẽ tiêu đề chính (Cắt bỏ đoạn text bị lỗi ở phía sau)
    _sec_title(c, "Định Vị P/E vs ROE", MARGIN, y0)

    # 2. Tính toán khoảng cách để vẽ phần Legend (Chú thích) ngay sau tiêu đề
    # Tính chiều rộng chữ tiêu đề để biết chỗ bắt đầu vẽ tiếp
    title_w = pdfmetrics.stringWidth("Định Vị P/E vs ROE", "VnFont-Bold", 9)
    legend_x = MARGIN + title_w + 12
    
    # Vẽ dấu ngoặc đơn mở
    c.setFont("VnFont", 7.5)
    c.setFillColor(colors.HexColor("#5A7A99")) # Màu xám cho chữ chú thích
    c.drawString(legend_x, y0, "(")
    
    # 3. VẼ HÌNH THOI (DIAMOND) MÀU XANH BẰNG TỌA ĐỘ
    dia_x = legend_x + 9  # Tọa độ X tâm hình thoi
    dia_y = y0 + 2.5      # Tọa độ Y tâm hình thoi
    dia_r = 2.5           # Bán kính (Kích thước) hình thoi
    
    c.setFillColor(colors.HexColor("#1B7A4A")) # Màu C_GREEN
    # Dùng công cụ Path của ReportLab để vẽ đa giác
    p = c.beginPath()
    p.moveTo(dia_x, dia_y + dia_r)    # Điểm 1: Đỉnh trên
    p.lineTo(dia_x + dia_r, dia_y)    # Điểm 2: Đỉnh phải
    p.lineTo(dia_x, dia_y - dia_r)    # Điểm 3: Đỉnh dưới
    p.lineTo(dia_x - dia_r, dia_y)    # Điểm 4: Đỉnh trái
    p.close()                         # Nối điểm cuối về điểm đầu
    
    # Tô màu và in ra PDF
    c.drawPath(p, fill=1, stroke=0)
    
    # 4. Vẽ nốt đoạn chữ còn lại
    c.setFillColor(colors.HexColor("#5A7A99")) # Đổi lại màu xám
    c.drawString(dia_x + 6, y0, "= Defensive Pick )")
    y0 -= 10
    scatter_h = 268
    fig_scatter = _chart_scatter_pe_roe(df_top, highlight_tickers=ncn_tickers)
    if fig_scatter:
        _embed(c, fig_scatter, MARGIN, y0 - scatter_h, CW, scatter_h)
    y0 -= scatter_h + 14

    # 2-col: Donut | ROE Bar
    half_w   = (CW - 12) / 2
    chart2_h = 210

    _sec_title(c, "Phân Bổ Ngành", MARGIN, y0, width=half_w, color=C_PURPLE)
    _sec_title(c, "ROE Trung Bình Theo Ngành",
               MARGIN + half_w + 12, y0, width=half_w, color=C_GREEN)
    y0 -= 10

    fig_donut = _chart_sector_donut(df_top)
    fig_roe   = _chart_roe_sector_bar(df_top)
    if fig_donut:
        _embed(c, fig_donut, MARGIN, y0 - chart2_h, half_w, chart2_h)
    if fig_roe:
        _embed(c, fig_roe, MARGIN + half_w + 12, y0 - chart2_h, half_w, chart2_h)

    _footer(c, 2)


# ══════════════════════════════════════════════════════════════
# TRANG 3 – RISK MANAGEMENT & MOMENTUM
# ══════════════════════════════════════════════════════════════
def _render_page3(c, df_top, ncn_rows, flag_rows, ai_texts):
    _bg(c)
    _page2_mini_header(c,
        "Quản Trị Rủi Ro & Động Lượng Ngắn Hạn",
        "Red Flags X-Ray  ·  Hiệu suất  ·  VGM Radar  ·  Defensive Pick",
        page_color=colors.HexColor("#1A0A0A"))

    y0 = PH - 58

    # AI Risk Assessment
    _sec_title(c, "Cảnh Báo Rủi Ro & Xu Hướng Dòng Tiền  ·  AI Risk Assessment",
               MARGIN, y0, color=C_RED)
    y0 -= 11
    y0 = _ai_box(c, ai_texts.get("risk",""),
                 MARGIN, y0, CW,
                 box_color=C_RED_SOFT,
                 border_color=C_RED_BORDER,
                 accent_color=C_ORANGE,
                 badge_label="Gemini 2.5 Flash Lite",
                 badge_color=C_RED)
    y0 -= 13

    # 2-col: Perf Bar | Radar
    half_w   = (CW - 12) / 2
    chart3_h = 205

    _sec_title(c, "Hiệu Suất 1T & 3T (%)",
               MARGIN, y0, width=half_w, color=C_BLUE)
    _sec_title(c, "VGM Score Radar  (Điểm TB danh mục)",
               MARGIN + half_w + 12, y0, width=half_w, color=C_PURPLE)
    y0 -= 10

    fig_perf  = _chart_perf_grouped(df_top)
    fig_radar = _chart_vgm_radar_or_bar(df_top)
    if fig_perf:
        _embed(c, fig_perf,  MARGIN, y0 - chart3_h, half_w, chart3_h)
    if fig_radar:
        _embed(c, fig_radar, MARGIN + half_w + 12, y0 - chart3_h, half_w, chart3_h)
    y0 -= chart3_h + 14

    # Red Flags table
    _sec_title(c, "Cảnh Báo Rủi Ro  ·  Red Flags X-Ray", MARGIN, y0, color=C_RED)
    y0 -= 11

    if flag_rows:
        fw = [CW * p for p in [0.086, 0.120, 0.105, 0.105, 0.210, 0.374]]
        fh = ["Mã CK","Tiêu chí","Giá trị HT","Ngưỡng AT","Đánh giá","Hành động đề xuất"]
        flag_data = [list(row) for row in flag_rows]
        bold_red = set()
        for ri, row in enumerate(flag_data):
            criteria = str(row[1]) if len(row) > 1 else ""
            if "D/E" in criteria or "P/E" in criteria:
                bold_red.add((ri, 2)); bold_red.add((ri, 4))
        _table_draw(c, fh, flag_data, MARGIN, y0, fw,
                    row_h=14, hdr_h=16, font_sz=6.8,
                    right_cols={2,3}, bold_red_cols=bold_red)
        y0 -= (len(flag_rows) * 14 + 16 + 10)
    else:
        c.setFont("VnFont", 8); c.setFillColor(C_GREY)
        c.drawString(MARGIN, y0-12, "✓  Không phát hiện red flag trong danh mục hiện tại.")
        y0 -= 22

    # Defensive Pick
    if ncn_rows and y0 > Y_MIN + 65:
        _sec_title(c, "Vietcap Defensive Pick  ·  Top 3 Mã Phòng Thủ",
                   MARGIN, y0, color=C_GREEN)
        y0 -= 11

        # Criteria info box
        info_h = 24
        c.setFillColor(C_GREEN_SOFT)
        c.setStrokeColor(C_GREEN_BORDER); c.setLineWidth(0.5)
        c.roundRect(MARGIN, y0 - info_h, CW * 0.65, info_h, radius=3, fill=1, stroke=1)
        c.setFillColor(C_GREEN)
        c.roundRect(MARGIN, y0-info_h, 4, info_h, radius=2, fill=1, stroke=0)
        c.setFont("VnFont-Bold", 6.8); c.setFillColor(colors.HexColor("#1B5E20"))
        c.drawString(MARGIN+8, y0-9, "Tiêu chuẩn sàng lọc:  ROE ≥ 15%  ·  D/E ≤ 1.5  ·  Net Margin ≥ 5%")
        c.setFont("VnFont", 6.3); c.setFillColor(C_TEXT)
        c.drawString(MARGIN+8, y0-19, "Loại ngành Tài chính  ·  Lọc thanh khoản Avg_Vol ≥ 300,000 cp/ngày")
        y0 -= info_h + 6

        ncn_prop = [
            ("Mã",0.11),("Tên công ty",0.34),("Sàn",0.08),
            ("VGM",0.09),("ROE",0.12),("P/E",0.10),("Cắt lỗ",0.16),
        ]
        tot_n   = sum(p for _,p in ncn_prop)
        ncn_w   = [CW * p / tot_n for _,p in ncn_prop]
        ncn_hdr = [h for h,_ in ncn_prop]
        ncn_data = [[
            r["ticker"], r["company"],   # đã cắt đúng trong _prepare_ncn_rows
            r["exchange"],
            r["vgm"], r["roe"], r["pe"], r["stoploss"]
        ] for r in ncn_rows]
        _table_draw(c, ncn_hdr, ncn_data, MARGIN, y0, ncn_w,
                    row_h=15, hdr_h=16, font_sz=7.2,
                    right_cols={4,5,6}, center_cols={2}, vgm_col_idx=3)
        y0 -= len(ncn_rows) * 15 + 16 + 8

    # Disclaimer
    if y0 > Y_MIN + 16:
        disc_y = max(Y_MIN + 6, y0 - 16)
        c.setFillColor(C_AMBER_SOFT)
        c.setStrokeColor(C_AMBER_BORDER); c.setLineWidth(0.5)
        c.roundRect(MARGIN, disc_y, CW, 14, radius=2, fill=1, stroke=1)
        c.setFillColor(C_AMBER)
        c.roundRect(MARGIN, disc_y, 4, 14, radius=2, fill=1, stroke=0)
        c.setFont("VnFont-Bold", 6.2); c.setFillColor(C_AMBER)
        c.drawString(MARGIN+8, disc_y+4.5, "Lưu ý: ")
        c.setFont("VnFont", 6.2); c.setFillColor(C_TEXT)
        c.drawString(MARGIN+40, disc_y+4.5,
            "P/E cao không nhất thiết xấu nếu EPS tăng trưởng mạnh (PEG < 1.5). "
            "D/E cao có thể chấp nhận với ngành Tài chính, BĐS. "
            "Không là khuyến nghị mua/bán.")

    _footer(c, 3)

# ══════════════════════════════════════════════════════════════
# MODAL CONTENT BUILDERS (PREMIUM DARK THEME TỐI ƯU CHO WEB)
# ══════════════════════════════════════════════════════════════

def _modal_kpi_strip(row_data: list) -> html.Div:
    """Tạo KPI strip 5 thẻ cho modal overview - Dark Theme."""
    if not row_data:
        return html.Div("Không có dữ liệu", style={"color":"#8b949e","fontSize":"12px"})

    df = pd.DataFrame(row_data)
    for col in ["P/E","ROE (%)","Perf_1M","Market Cap"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    total      = len(df)
    avg_pe     = df["P/E"].dropna().mean()     if "P/E"     in df.columns else None
    avg_roe    = df["ROE (%)"].dropna().mean() if "ROE (%)" in df.columns else None
    n_sectors  = df["Sector"].nunique()        if "Sector"  in df.columns else 0
    n_grade_a  = int((df["VGM Score"]=="A").sum()) if "VGM Score" in df.columns else 0

    def _card(label, value, color="#0057D9"):
        return html.Div([
            html.Div(label, style={"fontSize":"9px","color":"#8b949e",
                                   "textTransform":"uppercase","letterSpacing":"0.3px"}),
            html.Div(value, style={"fontSize":"18px","fontWeight":"900",
                                   "color":color,"lineHeight":"1.1"}),
        ], style={
            "flex":"1","textAlign":"center",
            "border":"1px solid #1E3A6A","borderTop":f"3px solid {color}",
            "borderRadius":"6px","padding":"8px 6px","background":"#112340", # Nền Navy đậm
        })

    return html.Div([
        _card("Tổng mã lọc",  str(total),                          "#38bdf8"), # Xanh cyan
        _card("SỐ MÃ ĐIỂM A (5 SAO)",     str(n_grade_a),                      "#10b981"), # Xanh lá ngọc
        _card("P/E TB",       f"{avg_pe:.1f}"  if avg_pe  else "—","#3b82f6"), # Xanh blue
        _card("ROE TB",       f"{avg_roe:.1f}%" if avg_roe else "—","#10b981"),
        _card("Số ngành (GICS)",     str(n_sectors),                       "#8b5cf6"), # Tím
    ], style={"display":"flex","gap":"8px","flexWrap":"wrap"})


def _modal_ncn_table(row_data: list):
    """Mini table NCN Top 3 cho modal - Dark Theme."""
    if not row_data:
        return html.Div("—", style={"color": "#8b949e", "fontSize": "11px"})

    df_src = pd.DataFrame(row_data)
    ncn = _prepare_ncn_rows(df_src, top_n=3)

    if not ncn:
        return html.Div(
            "Không có mã đạt chuẩn NCN (ROE≥15%, D/E≤1.5, Net Margin≥5%)",
            style={"color": "#8b949e", "fontSize": "11px", "fontStyle": "italic"},
        )

    VGM_COLOR_MAP = {
        "A": "#10b981", "B": "#3b82f6", "C": "#f59e0b",
        "D": "#f97316", "F": "#ef4444",
    }
    col_style = {"padding": "6px 8px", "fontSize": "11px", "whiteSpace": "nowrap", "borderBottom": "1px solid #1E3A6A"}
    hdr_style = {**col_style, "fontWeight": "700", "background": "#064e3b", # Nền xanh lá cực đậm
                 "color": "#a7f3d0", "textTransform": "uppercase", "fontSize": "10px", "borderBottom": "none"}

    header_row = html.Tr([
        html.Th("Mã CK",    style=hdr_style),
        html.Th("Tên CT",   style=hdr_style),
        html.Th("ĐIỂM",      style={**hdr_style, "textAlign": "center"}),
        html.Th("ROE %",    style={**hdr_style, "textAlign": "right"}),
        html.Th("Biên gộp", style={**hdr_style, "textAlign": "right"}),
        html.Th("D/E",      style={**hdr_style, "textAlign": "right"}),
        html.Th("P/E",      style={**hdr_style, "textAlign": "right"}),
    ])

    data_rows = []
    for r in ncn:
        g  = str(r.get("vgm", "—")).upper()
        gc = VGM_COLOR_MAP.get(g, "#999")
        data_rows.append(html.Tr([
            html.Td(
                html.B(r.get("ticker", "—"),
                       style={"color": "#34d399", "fontSize": "12px"}), # Màu xanh lá nổi bật
                style=col_style,
            ),
            html.Td(
                str(r.get("company", "—")),
                style={**col_style, "color": "#c9d1d9"}, # Chữ trắng xám
            ),
            html.Td(
                html.Span(g, style={
                    "background": gc, "color": "white",
                    "borderRadius": "50%",
                    "width": "20px", "height": "20px",
                    "display": "inline-flex",
                    "alignItems": "center", "justifyContent": "center",
                    "fontWeight": "900", "fontSize": "10px",
                }),
                style={**col_style, "textAlign": "center"},
            ),
            html.Td(
                r.get("roe", "—"),
                style={**col_style, "textAlign": "right",
                       "color": "#10b981", "fontWeight": "700"},
            ),
            html.Td(
                r.get("gross_margin", r.get("bien_gop", "—")),
                style={**col_style, "textAlign": "right", "color": "#c9d1d9"},
            ),
            html.Td(
                r.get("de", "—"),
                style={**col_style, "textAlign": "right", "color": "#c9d1d9"},
            ),
            html.Td(
                r.get("pe", "—"),
                style={**col_style, "textAlign": "right", "color": "#c9d1d9"},
            ),
        ], style={"background": "#0d1117"})) # Nền dòng màu đen

    return html.Div(
        html.Table(
            [header_row] + data_rows,
            style={
                "width": "100%", "borderCollapse": "collapse",
                "border": "1px solid #1E3A6A", "borderRadius": "6px",
                "overflow": "hidden"
            },
        ),
        style={"overflowX": "auto", "borderRadius": "6px"}
    )


def _modal_flag_table(row_data: list) -> html.Div:
    """Mini Red Flags table cho modal - Dark Theme."""
    if not row_data:
        return html.Div("—", style={"color":"#8b949e"})

    df_src = pd.DataFrame(row_data)
    for col in ["P/E","D/E","Perf_1M"]:
        if col in df_src.columns:
            df_src[col] = pd.to_numeric(df_src[col], errors="coerce")
    df_top = df_src.head(30)
    flags  = _prepare_flag_rows(df_top, max_flags=6)

    if not flags:
        return html.Div(
            "✅ Không phát hiện red flag trong top 30 mã",
            style={"color":"#10b981","fontSize":"11px","fontWeight":"600"},
        )

    col_style = {"padding":"6px 8px","fontSize":"11px", "borderBottom": "1px solid #450a0a", "color": "#c9d1d9"}
    hdr_style = {**col_style,"fontWeight":"700","background":"#450a0a", # Đỏ đô cực tối
                 "color":"#fca5a5","textTransform":"uppercase","fontSize":"10px", "borderBottom": "none"}

    rows = [html.Tr([
        html.Th("Mã CK",    style=hdr_style),
        html.Th("Tiêu chí", style=hdr_style),
        html.Th("Giá trị",  style={**hdr_style,"textAlign":"right"}),
        html.Th("Ngưỡng",   style={**hdr_style,"textAlign":"right"}),
        html.Th("Đánh giá", style=hdr_style),
    ])]
    for f in flags:
        rows.append(html.Tr([
            html.Td(html.B(f[0], style={"color":"#60a5fa"}), style=col_style), # Xanh sáng
            html.Td(f[1],  style=col_style),
            html.Td(f[2],  style={**col_style,"textAlign":"right",
                                  "color":"#f87171","fontWeight":"700", # Đỏ sáng
                                  "fontFamily":"monospace"}),
            html.Td(f[3],  style={**col_style,"textAlign":"right"}),
            html.Td(f[4],  style={**col_style,"color":"#f87171","fontWeight":"700"}),
        ], style={"background": "#0d1117"}))

    return html.Div(
        html.Table(rows, style={"width":"100%","borderCollapse":"collapse",
                                "border":"1px solid #7f1d1d", "borderRadius": "6px"}),
        style={"overflowX":"auto", "borderRadius": "6px"},
    )


def _modal_mc_results(qr) -> html.Div:
    """Hiển thị kết quả Monte Carlo trong modal - Dark Theme."""
    if qr is None or qr.status != "ok":
        msg = getattr(qr, "error_message", "Không đủ dữ liệu.") if qr else "Lỗi pipeline."
        return html.Div([
            html.Span("⚠️ ", style={"fontSize":"16px"}),
            html.Span(msg, style={"color":"#fca5a5","fontSize":"12px"}),
        ], style={"padding":"12px","background":"#450a0a", # Nền đỏ cực tối
                  "border":"1px solid #7f1d1d","borderRadius":"6px"})

    def _metric(label, value, color, note=""):
        return html.Div([
            html.Div(label,  style={"fontSize":"9px","color":"#8b949e",
                                    "textTransform":"uppercase"}),
            html.Div(value,  style={"fontSize":"20px","fontWeight":"900",
                                    "color":color,"lineHeight":"1.1", "margin": "4px 0"}),
            html.Div(note,   style={"fontSize":"9px","color":"#64748b"}),
        ], style={
            "flex":"1","textAlign":"center","padding":"10px 8px",
            "border":f"1px solid #1E3A6A","borderTop":f"3px solid {color}",
            "borderRadius":"6px","background":"#112340", # Nền xanh navy tối
        })

    er_color  = "#10b981" if qr.expected_return_1m >= 0 else "#ef4444"
    mdd_color = "#f59e0b" if qr.max_drawdown < 0.15 else "#ef4444"

    metrics_row = html.Div([
        _metric("Kỳ vọng 1T",
                f"{qr.expected_return_1m*100:+.1f}%",
                er_color, "Trung bình 10K kịch bản"),
        _metric("VaR 95% (1T)",
                f"{qr.var_95*100:.1f}%",
                "#ef4444", "Mức lỗ tối đa 95% trường hợp"),
        _metric("Max Drawdown",
                f"{qr.max_drawdown*100:.1f}%",
                mdd_color, "Guillotine ≤15%"),
        _metric("Sharpe Ratio",
                f"{qr.sharpe_ratio:.2f}",
                "#38bdf8", "Annualized"),
    ], style={"display":"flex","gap":"8px","marginBottom":"10px", "flexWrap": "wrap"})

    # Allocation mini table
    alloc_rows_html = []
    for i, t in enumerate(qr.tickers):
        w   = qr.weights[i] if i < len(qr.weights) else 0
        qty = qr.quantities[i] if i < len(qr.quantities) else 0
        inv = qr.investment_values[i] if i < len(qr.investment_values) else 0
        alloc_rows_html.append(html.Tr([
            html.Td(html.B(t, style={"color":"#60a5fa"}),
                    style={"padding":"6px 8px","fontSize":"11px", "borderBottom": "1px solid #1E3A6A"}),
            html.Td(f"{w*100:.1f}%",
                    style={"padding":"6px 8px","fontSize":"11px",
                           "textAlign":"right","fontWeight":"700", "color": "#c9d1d9", "borderBottom": "1px solid #1E3A6A"}),
            html.Td(f"{qty:,} cp",
                    style={"padding":"6px 8px","fontSize":"11px",
                           "textAlign":"right","fontFamily":"monospace", "color": "#c9d1d9", "borderBottom": "1px solid #1E3A6A"}),
            html.Td(f"{inv/1e6:,.0f}M VND",
                    style={"padding":"6px 8px","fontSize":"11px",
                           "textAlign":"right","color":"#34d399",
                           "fontWeight":"600", "borderBottom": "1px solid #1E3A6A"}),
        ], style={"background": "#0d1117"}))

    alloc_table = html.Table([
        html.Thead(html.Tr([
            html.Th(h, style={"padding":"6px 8px","fontSize":"10px",
                              "background":"#0a1628","color":"#c9d1d9",
                              "fontWeight":"700","textTransform":"uppercase",
                              "textAlign": "right" if i>0 else "left"})
            for i,h in enumerate(["Mã CK","% Tỷ trọng","Số CP","Giá trị VND"])
        ])),
        html.Tbody(alloc_rows_html),
    ], style={"width":"100%","borderCollapse":"collapse",
              "border":"1px solid #1E3A6A","marginBottom":"10px", "borderRadius": "6px", "overflow": "hidden"})

    guilotine_note = html.Div(
        f"ℹ️ Guillotine Rule chạy {qr.guillotine_iterations} vòng · Danh mục tối ưu: {', '.join(qr.tickers)}",
        style={"fontSize":"10px","color":"#93c5fd",
               "padding":"8px 10px","background":"#082f49", # Xanh dương cực tối
               "borderLeft":"3px solid #38bdf8","borderRadius":"4px"},
    )

    return html.Div([
        html.Div([
            html.Span("🧮 ", style={"fontSize":"14px"}),
            html.B("Kết quả Markowitz + Monte Carlo Bootstrap (10,000 kịch bản)",
                   style={"fontSize":"13px","color":"#e8f4ff"}), # Chữ trắng sáng
        ], style={"marginBottom":"10px"}),
        metrics_row,
        html.Div(alloc_table, style={"borderRadius": "6px", "overflow": "hidden"}),
        guilotine_note,
    ], style={"padding":"16px","background":"#0d1117", # Nền trùng với web
              "border":"1px solid #1E3A6A","borderRadius":"8px", "boxShadow": "0 4px 12px rgba(0,0,0,0.5)"})

# ══════════════════════════════════════════════════════════════
# MAIN GENERATOR
# ══════════════════════════════════════════════════════════════
def generate_screener_pdf(
    row_data: list,
    active_filters: dict = None,
    nav: float = 1_000_000_000.0,
    include_quant: bool = False,   # ← True khi toggle MC bật
) -> bytes:
    df = pd.DataFrame(row_data) if row_data else pd.DataFrame()
    
    if not df.empty:
        # 1. CHẶN BLACKLIST VĨNH VIỄN (Loại bỏ hàng rác, dính án)
        BLACKLIST_TICKERS = {
            "TDH", "L40", "FLC", "ROS", "HNG", "DL1", "TOS", "HAG", "HQC", "ITA", "AMD", "HAI",
            "HHS", "TCH", "NVL", "PDR", "HPX", "IBC", "LDG", "QCG", "TTF", "JVC"
        }
        if "Ticker" in df.columns:
            df = df[~df["Ticker"].isin(BLACKLIST_TICKERS)]
            
        # 2. SIẾT THANH KHOẢN & VỐN HÓA (Chuẩn Khách VIP)
        if "Avg_Vol_20D" in df.columns:
            df["Avg_Vol_20D"] = pd.to_numeric(df["Avg_Vol_20D"], errors="coerce").fillna(0)
            df = df[df["Avg_Vol_20D"] >= 500000]
            
        if "Market Cap" in df.columns: # Lưu ý: File của em đang dùng tên cột "Market Cap" có khoảng trắng
            df["Market Cap"] = pd.to_numeric(df["Market Cap"], errors="coerce").fillna(0)
            df = df[df["Market Cap"] >= 5000]
            
        # 3. SIẾT ĐỊNH GIÁ & DÒNG TIỀN (Chỉ lọc nếu cột tồn tại để tránh lỗi mảng rỗng 0 mã)
        if "P/E" in df.columns:
            df["P/E"] = pd.to_numeric(df["P/E"], errors="coerce")
            df = df[(df["P/E"] > 0) & (df["P/E"] < 15)]
            
        if "Dividend_Yield" in df.columns:
            df["Dividend_Yield"] = pd.to_numeric(df["Dividend_Yield"], errors="coerce")
            df = df[df["Dividend_Yield"] >= 5.0]
        elif "Div Yield" in df.columns: # Dự phòng nếu cột tên là Div Yield
            df["Div Yield"] = pd.to_numeric(df["Div Yield"], errors="coerce")
            df = df[df["Div Yield"] >= 5.0]
            
        if "CFO" in df.columns:
            df["CFO"] = pd.to_numeric(df["CFO"], errors="coerce")
            df = df[df["CFO"] > 0]

    # 4. CHUẨN HÓA CÁC CỘT SỐ LIỆU KHÁC (Code cũ của em)
    num_cols = ["Price Close","P/E","P/B","ROE (%)","D/E","Net Margin (%)",
                "Perf_1W","Perf_1M","Perf_3M","RS_1M","Market Cap",
                "CANSLIM Score","Gross Margin (%)","SMA20","SMA50",
                "Avg_Vol_20D","RSI_14"]
    for col in num_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    grade_order = {"A":1,"B":2,"C":3,"D":4,"F":5}
    if "VGM Score" in df.columns:
        df["_sort"] = df["VGM Score"].map(grade_order).fillna(6)
        df = df.sort_values("_sort").drop(columns=["_sort"])
        
    # Lúc này total_count sẽ phản ánh ĐÚNG số lượng mã thật sự có thể đầu tư
    total_count = len(df)
    df_top = df.head(30).copy()

    stats = {
        "total":         total_count,
        "display":       min(20, total_count),
        "avg_pe":        _sv(df_top["P/E"].dropna().mean()       if "P/E"     in df_top.columns else None, "dec1"),
        "avg_roe":       _sv(df_top["ROE (%)"].dropna().mean()   if "ROE (%)" in df_top.columns else None, "dec1", "%"),
        "grade_a_count": int((df_top["VGM Score"]=="A").sum())   if "VGM Score" in df_top.columns else 0,
        "sectors_count": int(df_top["Sector"].nunique())         if "Sector"   in df_top.columns else 0,
    }

    strategy_label, strategy_title = _detect_strategy(active_filters)
    
    # ============================================================
    # 🟢 FIX LUỒNG DỮ LIỆU ĐỒNG BỘ (ORDER OF EXECUTION)
    # ============================================================
    
    # Bước 1: Quét và lập danh sách Red Flags (Cảnh báo rủi ro) trước
    flag_rows = _prepare_flag_rows(df_top, max_flags=12)
    red_flag_tickers = {row[0] for row in flag_rows} # Trích xuất các Ticker dính cờ đỏ

    # Bước 2: Truyền Red Flags vào hàm lọc danh mục Phòng thủ (NCN) 
    # để chặn đứng không cho các mã xấu lọt vào Top khuyến nghị
    ncn_rows = _prepare_ncn_rows(df, top_n=3, red_flags=red_flag_tickers)
    ncn_tickers = [r["ticker"] for r in ncn_rows]

    # Bước 3: Đẩy danh sách đã sạch rủi ro vào lõi tối ưu hóa Markowitz
    qr = None
    if _QUANT_AVAILABLE and ncn_rows:
        try:
            qr = run_full_pipeline(
                ncn_rows=ncn_rows,
                nav=nav,
                target_month=datetime.now().month,
                max_picks=min(5, len(ncn_rows)),
            )
        except Exception as _qe:
            logger.warning(f"❌ Lỗi tối ưu hóa danh mục PDF: {_qe}")

    # Bước 4: Chỉ gọi AI Gemini ĐÚNG 1 LẦN để nhận xét dựa trên danh mục đã tối ưu
    # Tránh việc gọi lặp đi lặp lại làm giảm tốc độ xuất file
    ai_texts = _gemini_summary(df_top, ncn_tickers, strategy_label)

    # 6. HIỂN THỊ THAM SỐ LỌC
    filter_params = []
    if active_filters:
        label_map = {
            "filter-pe":"P/E","filter-pb":"P/B","filter-roe":"ROE(%)","filter-de":"D/E",
            "filter-market-cap":"Vốn hóa","filter-vgm-score":"VGM Score",
            "filter-canslim":"CANSLIM","filter-perf-1m":"Hiệu suất 1T",
            "filter-net-margin":"Net Margin","filter-div-yield":"Div Yield",
            "filter-current-ratio":"Current Ratio","filter-rsi14":"RSI",
        }
        for fid, entry in active_filters.items():
            if not isinstance(entry, dict): continue
            label = entry.get("label") or label_map.get(fid, fid.replace("filter-","").replace("-"," ").title())
            val   = entry.get("value")
            if isinstance(val, list) and len(val) == 2:
                filter_params.append(f"{label}: {val[0]} → {val[1]}")
            elif val is not None:
                filter_params.append(f"{label}: {val}")

    # 7. VẼ BÁO CÁO PDF BẰNG REPORTLAB
    buf = io.BytesIO()
    c   = rl_canvas.Canvas(buf, pagesize=A4)
    c.setTitle("FinSmartScreener - Báo Cáo Danh Mục Lọc")
    c.setAuthor("FinSmartScreener")
    c.setSubject(f"Chiến lược {strategy_label} - {datetime.now().strftime('%d/%m/%Y')}")

    try:
        # NHỚ TRUYỀN red_flag_tickers VÀO _render_page1 NHƯ ĐÃ SỬA Ở TRƯỚC
        _render_page1(c, stats, ai_texts, filter_params, strategy_title, df_top, red_flag_tickers)
        c.showPage()
        _render_page2(c, df_top, ncn_tickers, ai_texts)
        c.showPage()
        _render_page3(c, df_top, ncn_rows, flag_rows, ai_texts)
        c.showPage()
        # Trang 4: FSS Predictive – chỉ render khi include_quant=True
        if include_quant and _QUANT_AVAILABLE:
            try:
                _qr_for_pdf = run_full_pipeline(
                    ncn_rows=ncn_rows,
                    nav=nav,
                    target_month=datetime.now().month,
                    max_picks=5,
                )
                _render_quant_page(c, _qr_for_pdf, nav)
                c.showPage()
            except Exception as _qe:
                logger.warning(f"[Quant page PDF] Skip: {_qe}")
    except Exception as e:
        logger.error(f"Screener PDF render error: {e}")
        traceback.print_exc()
        _bg(c)
        c.setFont("VnFont", 11)
        # Sử dụng màu đỏ thuần nếu biến C_RED chưa được import đúng cách
        c.setFillColorRGB(0.8, 0.1, 0.1) 
        c.drawCentredString(PW/2, PH/2, f"Loi render: {str(e)[:90]}")
        c.showPage()

    c.save()
    buf.seek(0)
    return buf.read()


# ══════════════════════════════════════════════════════════════
# CALLBACK 1: Nút PDF → Mở modal (instant, không generate PDF)
# ══════════════════════════════════════════════════════════════
@app.callback(
    Output("screener-pdf-modal", "is_open"),
    Output("modal-kpi-strip",    "children"),
    Output("modal-ncn-table",    "children"),
    Output("modal-flag-table",   "children"),
    [Input("btn-export-screener-pdf", "n_clicks"),
     Input("btn-modal-close",         "n_clicks")],
    [State("screener-table",       "rowData"),
     State("active-filters-store", "data"),
     State("screener-pdf-modal",   "is_open"),
     State("auth-store",           "data")],   # [FIX] thêm — trước đây không check quyền
    prevent_initial_call=True,
)
def toggle_screener_modal(open_click, close_click, row_data, active_filters, is_open, auth_data):
    from dash import callback_context
    triggered = callback_context.triggered[0]["prop_id"].split(".")[0]

    if triggered == "btn-modal-close":
        return False, no_update, no_update, no_update

    if triggered == "btn-export-screener-pdf" and row_data:
        # [FIX] BẢO VỆ SERVER-SIDE: trước đây callback này (và 2 callback
        # bên dưới cùng file) không hề check auth-store — premium-overlay
        # ở UI chỉ là lớp che hình thức, ai gọi trực tiếp callback (DevTools/
        # curl vào endpoint _dash-update-component) đều dùng được free.
        from src.callbacks.auth_callbacks import require_entitlement
        if not require_entitlement(auth_data, allowed_tiers=["pro", "b2b"]):
            return False, no_update, no_update, no_update

        return (
            True,
            _modal_kpi_strip(row_data),
            _modal_ncn_table(row_data),
            _modal_flag_table(row_data),
        )

    return False, no_update, no_update, no_update


# ══════════════════════════════════════════════════════════════
# CALLBACK 2: Toggle MC → Tính toán và hiển thị kết quả
# ══════════════════════════════════════════════════════════════
@app.callback(
    Output("modal-mc-section", "style"),
    Output("modal-mc-section", "children"),
    Input("modal-mc-toggle", "value"),
    [State("screener-table",  "rowData"),
     State("modal-nav-input", "value"),
     State("auth-store",      "data")],   # [FIX] thêm — trước đây không check quyền
    prevent_initial_call=True,
    running=[
        (Output("modal-mc-toggle", "disabled"), True, False),
        (Output("btn-modal-download-pdf", "disabled"), True, False),
    ],
)
def compute_mc_preview(toggle_on, row_data, nav_raw, auth_data):
    # Toggle OFF → ẩn section
    if not toggle_on:
        return {"display": "none"}, []

    # [FIX] BẢO VỆ SERVER-SIDE — QUAN TRỌNG NHẤT trong file này: đây là nơi
    # chạy run_full_pipeline() (Markowitz + Monte Carlo 10.000 kịch bản),
    # tốn CPU đáng kể. Trước đây bất kỳ ai bật toggle này đều chạy được,
    # không cần đăng nhập, không giới hạn tier — vừa hở doanh thu vừa là
    # rủi ro DoS (spam toggle để ép server tính Monte Carlo liên tục).
    from src.callbacks.auth_callbacks import require_entitlement
    if not require_entitlement(auth_data, allowed_tiers=["pro", "b2b"]):
        return (
            {"display": "block"},
            html.Div(
                "🔒 Tính năng Tối ưu hóa Danh mục (Markowitz + Monte Carlo) "
                "chỉ dành cho gói Pro trở lên.",
                style={"color": "#B45309", "fontSize": "12px",
                       "padding": "10px", "background": "#fffbeb",
                       "border": "1px solid #fde68a", "borderRadius": "5px"},
            ),
        )

    # Parse NAV
    try:
        nav = max(100_000_000.0, float(nav_raw)) if nav_raw not in (None, "") else 1_000_000_000.0
    except Exception:
        nav = 1_000_000_000.0

    # Chạy pipeline nếu có module
    if not _QUANT_AVAILABLE or not row_data:
        return (
            {"display": "block"},
            html.Div(
                "⚠️ Module portfolio_optimizer chưa được cài đặt "
                "hoặc bảng đang trống.",
                style={"color":"#D32F2F","fontSize":"12px",
                       "padding":"10px","background":"#fff5f5",
                       "border":"1px solid #fecaca","borderRadius":"5px"},
            ),
        )

    try:
        df_src = pd.DataFrame(row_data)
        # Reuse NCN rows đã compute
        red_flag_tickers = set()  # simplified cho preview
        ncn_rows_for_mc  = _prepare_ncn_rows(
            df_src, top_n=5, red_flags=red_flag_tickers
        )
        qr = run_full_pipeline(
            ncn_rows=ncn_rows_for_mc,
            nav=nav,
            target_month=datetime.now().month,
            max_picks=5,
        )
    except Exception as e:
        logger.error(f"[Modal MC] Pipeline error: {e}")
        qr = None

    return {"display": "block"}, _modal_mc_results(qr)


# ══════════════════════════════════════════════════════════════
# CALLBACK 3: Nút "Tải PDF" trong modal → Generate & Download
# ══════════════════════════════════════════════════════════════
@app.callback(
    Output("screener-pdf-download", "data"),
    Output("screener-pdf-status",   "children"),
    Input("btn-modal-download-pdf", "n_clicks"),
    [State("screener-table",       "rowData"),
     State("active-filters-store", "data"),
     State("modal-mc-toggle",      "value"),
     State("modal-nav-input",      "value"),
     State("auth-store",           "data")],   # [FIX] thêm — trước đây không check quyền
    prevent_initial_call=True,
    running=[
        (Output("btn-modal-download-pdf", "disabled"), True, False),
        (Output("btn-modal-download-pdf", "children"),
         [html.I(className="fas fa-spinner fa-spin",
                 style={"marginRight":"5px"}), "Đang tạo PDF..."],
         [html.I(className="fas fa-file-pdf",
                 style={"marginRight":"5px"}), "Tải Báo cáo PDF"]),
    ],
)
def download_pdf_from_modal(n_clicks, row_data, active_filters,
                            use_quant, nav_raw, auth_data):
    if not row_data:
        return no_update, "⚠️ Bảng đang trống"

    # [FIX] BẢO VỆ SERVER-SIDE — xem chú thích ở compute_mc_preview() phía
    # trên. Trước đây callback này không hề kiểm tra auth-store, ai cũng
    # tải được PDF (kể cả trang Quant/Monte Carlo nếu use_quant=True).
    from src.callbacks.auth_callbacks import require_entitlement
    if not require_entitlement(auth_data, allowed_tiers=["pro", "b2b"]):
        return no_update, "🔒 Tính năng này chỉ dành cho gói Pro trở lên."

    try:
        nav = max(100_000_000.0, float(nav_raw)) if nav_raw not in (None, "") else 1_000_000_000.0
    except Exception:
        nav = 1_000_000_000.0

    try:
        # use_quant=True → PDF có trang Monte Carlo
        # use_quant=False/None → PDF cũ như thường
        pdf_bytes = generate_screener_pdf(
            row_data,
            active_filters,
            nav=nav,
            include_quant=bool(use_quant),
        )
        fname = (
            f"Vietcap_DanhMucLoc"
            f"{'_MC' if use_quant else ''}"
            f"_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
        )
        return dcc.send_bytes(pdf_bytes, fname), f"✔ Đã tải: {fname}"
    except Exception as e:
        logger.error(f"Modal PDF error: {e}")
        traceback.print_exc()
        return no_update, f"❌ Lỗi: {str(e)[:80]}"

@app.callback(
    Output("theory-modal", "is_open"),
    Input("btn-open-theory-modal", "n_clicks"),
    State("theory-modal", "is_open"),
    prevent_initial_call=True
)
def toggle_theory_modal(n_clicks, is_open):
    if n_clicks:
        return not is_open
    return is_open