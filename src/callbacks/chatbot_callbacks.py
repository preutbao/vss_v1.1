# src/callbacks/chatbot_callbacks.py
"""
VinanceAI — Trợ lý đầu tư chứng khoán Việt Nam
IDX Smart Screener · Floating Investment Assistant
Powered by OpenAI GPT
"""
import os
import json
import logging
from datetime import datetime
from dash import Input, Output, State, html, dcc, no_update, callback_context, ALL, clientside_callback
from src.app_instance import app
# import google.generativeai as genai

logger = logging.getLogger(__name__)

# ── CẤU HÌNH GEMINI ──────────────────────────────────────────────────────────
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL   = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash-lite")

# ── SYSTEM PROMPT VINANCEAI ───────────────────────────────────────────────────
VINANCE_SYSTEM_PROMPT = """
Bạn là **VinanceAI** – chuyên gia tài chính và chứng khoán hàng đầu Việt Nam (HOSE, HNX, UPCOM) với hơn 20 năm kinh nghiệm thực chiến.
Nhiệm vụ của bạn là phân tích dữ liệu thị trường và cung cấp lời khuyên dựa trên Hồ sơ đầu tư của người dùng đã được cung cấp.

# YÊU CẦU BẮT BUỘC VỀ VĂN PHONG (CRITICAL RULES):
1. **TRẢ LỜI TRỰC DIỆN:** ĐI THẲNG VÀO VẤN ĐỀ ngay câu đầu tiên. KHÔNG chào hỏi vòng vo, KHÔNG lặp lại câu hỏi của người dùng, KHÔNG dùng các câu rườm rà như "Dựa trên dữ liệu bạn cung cấp...".
2. **NGẮN GỌN & SÚC TÍCH:** Cung cấp đúng thông tin được hỏi. Ưu tiên sử dụng gạch đầu dòng (bullet points).
3. **BÁM SÁT DỮ LIỆU:** Chỉ phân tích dựa trên dữ liệu Screener và Mã cổ phiếu được truyền vào. Không bịa đặt số liệu.
4. **CÁ NHÂN HÓA TỰ ĐỘNG:** Phân tích DỰA TRÊN hồ sơ rủi ro và trình độ của người dùng được cung cấp trong context. NẾU họ là F0: Giải thích ngắn gọn thuật ngữ khó. NẾU họ là Chuyên nghiệp: Dùng trực tiếp thuật ngữ tài chính.
5. **KHÔNG HỎI LẠI:** TUYỆT ĐỐI KHÔNG được hỏi người dùng về trình độ (F0/F1), số vốn, hay khẩu vị rủi ro. Tất cả đã có sẵn.
6. **TƯ VẤN MỞ TÀI KHOẢN:** Nếu được hỏi về tài khoản giao dịch, hãy tư vấn quy trình mở tài khoản tại công ty chứng khoán Vietcap.

# CẤU TRÚC PHÂN TÍCH CỔ PHIẾU (Nếu người dùng hỏi về 1 mã cụ thể):
- Cập nhật theo số liệu mới nhất có trên hệ thống
- 🏢 **Tổng quan & Định giá:** [P/E, P/B, ROE... Đắt hay rẻ?]
- 📉 **Kỹ thuật & Dòng tiền:** [RSI, Trend, Động lượng]
- ⚖️ **Cơ hội & Rủi ro:** [Điểm mạnh, điểm yếu theo tiêu chí]
- 🎯 **Hành động (Khuyến nghị tham khảo):** [Vùng mua/Bán/Cắt lỗ theo Hồ sơ rủi ro của người dùng]
"""
def _call_gemini(messages: list, stock_context: dict = None, screener_context: str = "") -> str:
    """Gọi Gemini API — đơn giản, không double-retry."""
    if not GEMINI_API_KEY:
        return "⚠️ Chưa cấu hình GEMINI_API_KEY."

    try:
        from google import genai
        from google.genai import types
    except ImportError:
        return "Chưa cài google-genai. Chạy: pip install google-genai"

    # ── Xây dựng system prompt ──
    system_text = VINANCE_SYSTEM_PROMPT

    if screener_context:
        system_text += screener_context

    if stock_context:
        ticker  = stock_context.get('Ticker', 'N/A')
        company = stock_context.get('Company Common Name', 'N/A')
        sector  = stock_context.get('Sector', 'N/A')
        pe      = stock_context.get('P/E', 'N/A')
        pb      = stock_context.get('P/B', 'N/A')
        roe     = stock_context.get('ROE (%)', 'N/A')
        rsi     = stock_context.get('RSI_14', 'N/A')
        vgm     = stock_context.get('VGM Score', 'N/A')
        p1w     = stock_context.get('Perf_1W', 'N/A')
        p1m     = stock_context.get('Perf_1M', 'N/A')
        price   = stock_context.get('Price Close', 'N/A')
        system_text += f"""

## CỔ PHIẾU ĐANG CHỌN TRONG SCREENER
- Mã: {ticker} | Tên: {company} | Ngành: {sector}
- Giá: {price} | P/E: {pe} | P/B: {pb} | ROE: {roe}%
- RSI(14): {rsi} | VGM Score: {vgm}
- Hiệu suất: 1W={p1w}% | 1M={p1m}%
Ưu tiên phân tích mã {ticker} khi user hỏi về cổ phiếu.
"""

    # ── Chuyển đổi history sang format Gemini ──
    # Gemini dùng role "user" / "model", không có "system"
    # → Ghép system prompt vào tin nhắn đầu tiên của user
    gemini_history = []
    for i, msg in enumerate(messages):
        role = msg.get("role", "user")
        if role == "assistant":
            role = "model"
        
        parts = msg.get("parts", [])
        if parts and isinstance(parts, list):
            text = parts[0].get("text", "")
        else:
            text = str(msg.get("content", ""))
        
        if not text:
            continue
            
        # Ghép system prompt vào message user đầu tiên
        if i == 0 and role == "user":
            text = f"{system_text}\n\n---\n\nCâu hỏi của người dùng: {text}"
        
        gemini_history.append({
            "role": role,
            "parts": [{"text": text}]
        })

    if not gemini_history:
        return "Vui lòng nhập câu hỏi."

    try:
        client = genai.Client(api_key=GEMINI_API_KEY)

        # Chuyển đổi history sang format mới (Content objects)
        contents = []
        for msg in gemini_history:
            role = msg["role"]  # "user" hoặc "model"
            text = msg["parts"][0]["text"]
            contents.append(
                types.Content(
                    role=role,
                    parts=[types.Part(text=text)]
                )
            )

        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=contents,
            config=types.GenerateContentConfig(
                max_output_tokens=600,
                temperature=0.7,
            ),
        )
        return response.text

    except Exception as e:
        print(f"🔴 Lỗi Gemini API: {e}") # Thêm dòng này để debug
        err = str(e).lower()
        if "quota" in err or "429" in err or "resource" in err:
            return "⚠️ Gemini API đang bận. Vui lòng thử lại sau 10 giây."
        if "api_key" in err or "invalid" in err:
            return "❌ GEMINI_API_KEY không hợp lệ. Kiểm tra lại."
        logger.error(f"Gemini error: {e}")
        return f"❌ Lỗi kết nối Gemini: {str(e)[:100]}"


# ── DỮ LIỆU SCREENER CHO CHATBOT (cached, rebuild mỗi 5 phút) ────────────────
_screener_context_cache: dict = {"text": "", "ts": 0.0}
_SCREENER_CACHE_TTL = 300  # giây


def _build_screener_context() -> str:
    """Tóm tắt dữ liệu screener cho system prompt. Cache 5 phút."""
    import time as _time
    import pandas as pd

    now = _time.time()
    if now - _screener_context_cache["ts"] < _SCREENER_CACHE_TTL and _screener_context_cache["text"]:
        return _screener_context_cache["text"]

    try:
        from src.backend.data_loader import get_snapshot_df
        df = get_snapshot_df()
        if df is None or df.empty:
            return ""

        # LƯU Ý: "VGM Score" lưu dạng CHỮ (A/B/C/D/F), không phải số.
        # pd.to_numeric("A", errors="coerce") → NaN cho MỌI dòng, khiến
        # nlargest() ở dưới trả về top 15 vô nghĩa (thứ tự ngẫu nhiên/rỗng).
        # May mắn là quant_engine.py đã tính sẵn cột số "VGM_Score_Num" TRƯỚC
        # KHI chuyển thành chữ (xem calculate_vgm_score()) — dùng đúng cột đó
        # để sắp xếp, chỉ dùng "VGM Score" (chữ) để hiển thị cho người dùng.
        score_col      = next((c for c in ["VGM Score", "VGM_Score", "vgm_score"] if c in df.columns), None)
        score_rank_col = next((c for c in ["VGM_Score_Num", "VGM Score Num"] if c in df.columns), None)
        price_col = next((c for c in ["Price Close", "Price", "price_close"] if c in df.columns), None)
        pe_col    = next((c for c in ["P/E", "PE", "pe"] if c in df.columns), None)
        pb_col    = next((c for c in ["P/B", "PB", "pb"] if c in df.columns), None)
        roe_col   = next((c for c in ["ROE (%)", "ROE", "roe"] if c in df.columns), None)
        rsi_col   = next((c for c in ["RSI_14", "RSI", "rsi"] if c in df.columns), None)
        tick_col  = next((c for c in ["Ticker", "ticker", "Symbol"] if c in df.columns), None)
        sect_col  = next((c for c in ["Sector", "sector"] if c in df.columns), None)

        lines = ["\n## DỮ LIỆU SCREENER THỰC TẾ"]
        lines.append(f"Tổng số mã: {len(df)}")

        if "Exchange" in df.columns:
            exch = df["Exchange"].value_counts().to_dict()
            lines.append(f"Sàn: {exch}")

        # Cột dùng để SẮP XẾP phải là cột SỐ. Nếu không có VGM_Score_Num
        # (trường hợp hiếm/dữ liệu cũ), fallback về ép kiểu số trên score_col
        # nhưng cảnh báo rõ trong log vì kết quả có thể toàn NaN.
        rank_col = score_rank_col
        if not rank_col and score_col:
            df = df.copy()
            df[score_col] = pd.to_numeric(df[score_col], errors='coerce')
            if df[score_col].notna().any():
                rank_col = score_col
            else:
                logger.warning("⚠️ Không tìm thấy VGM_Score_Num và score_col không ép kiểu số được — bỏ qua top15.")

        if rank_col and tick_col:
            df_sorted = df.copy()
            df_sorted[rank_col] = pd.to_numeric(df_sorted[rank_col], errors='coerce')
            top_df = df_sorted.nlargest(15, rank_col)
            rows = []
            for _, row in top_df.iterrows():
                parts = [str(row.get(tick_col, ""))]
                if sect_col:  parts.append(str(row.get(sect_col, ""))[:12])
                if score_col: parts.append(f"VGM={row.get(score_col,'')}")
                if price_col: parts.append(f"P={row.get(price_col,'')}")
                if pe_col:    parts.append(f"PE={row.get(pe_col,'')}")
                if roe_col:   parts.append(f"ROE={row.get(roe_col,'')}%")
                if rsi_col:   parts.append(f"RSI={row.get(rsi_col,'')}")
                rows.append("|".join(parts))
                if len(rows) >= 15:  # Chỉ lấy top 15 thay vì 8
                    break
            lines.append("Top15VGM: " + "; ".join(rows))


        if sect_col and rank_col:
            df_sector = df.copy()
            df_sector[rank_col] = pd.to_numeric(df_sector[rank_col], errors='coerce')
            sector_stats = df_sector.groupby(sect_col)[rank_col].mean().sort_values(ascending=False).head(8)
            stats = [f"{s}:{v:.1f}({(df[sect_col]==s).sum()})" for s, v in sector_stats.items()]
            lines.append("Ngành(avgVGM): " + ", ".join(stats))

        lines.append("Dùng dữ liệu trên khi trả lời câu hỏi về thị trường.")
        result = "\n".join(lines)[:600]  # Giới hạn 600 ký tự

        _screener_context_cache["text"] = result
        _screener_context_cache["ts"]   = now
        logger.info("Screener context cache updated")
        return result

    except Exception as e:
        logger.warning(f"Không lấy được screener context: {e}")
        return ""


# ── RENDER TIN NHẮN ───────────────────────────────────────────────────────────
def _render_messages(history: list) -> list:
    bubbles = []

    for msg in history:
        role     = msg.get("role")
        text     = msg.get("parts", [{}])[0].get("text", "")
        time_str = msg.get("time", "")

        if role == "user":
            bubbles.append(
                html.Div([
                    html.Div([
                        html.Div(text, style={
                            "background": "linear-gradient(135deg, #1e40af, #1d4ed8)",
                            "color": "#e0f2fe",
                            "padding": "10px 14px",
                            "borderRadius": "18px 18px 4px 18px",
                            "fontSize": "13px",
                            "lineHeight": "1.6",
                            "maxWidth": "80%",
                            "wordBreak": "break-word",
                            "boxShadow": "0 2px 8px rgba(29,78,216,0.35)",
                        }),
                        html.Span(time_str, style={
                            "fontSize": "10px", "color": "#475569",
                            "marginTop": "4px", "display": "block",
                            "textAlign": "right",
                        }),
                    ], style={
                        "display": "flex", "flexDirection": "column",
                        "alignItems": "flex-end", "maxWidth": "85%",
                    }),
                ], style={
                    "display": "flex", "justifyContent": "flex-end",
                    "marginBottom": "12px", "padding": "0 14px",
                })
            )
        else:
            bubbles.append(
                html.Div([
                    html.Img(src="/assets/VinanceAI.png", style={
                        "width": "32px", "height": "32px", "borderRadius": "50%",
                        "objectFit": "cover",
                        "flexShrink": "0",
                        "boxShadow": "0 2px 8px rgba(14,165,233,0.4)",
                    }),
                    html.Div([
                        html.Div(
                            dcc.Markdown(
                                children=text,
                                dangerously_allow_html=False,
                                style={"fontSize": "13px", "lineHeight": "1.65", "color": "#cbd5e1",
                                       "margin": "0"}
                            ),
                            style={
                                "background": "#1e293b",
                                "padding": "10px 14px",
                                "borderRadius": "4px 18px 18px 18px",
                                "maxWidth": "100%",
                                "wordBreak": "break-word",
                                "boxShadow": "0 2px 8px rgba(0,0,0,0.25)",
                                "border": "1px solid rgba(148,163,184,0.1)",
                            }
                        ),
                        html.Span(time_str, style={
                            "fontSize": "10px", "color": "#475569",
                            "marginTop": "4px", "display": "block",
                        }),
                    ], style={"maxWidth": "85%"}),
                ], style={
                    "display": "flex", "gap": "10px", "alignItems": "flex-start",
                    "marginBottom": "12px", "padding": "0 14px",
                })
            )

    return bubbles


# ── UI LAYOUT ─────────────────────────────────────────────────────────────────
def create_chatbot_layout():
    quick_prompts = [
        ("🔍 Sàng lọc Giá Trị",   "Hãy hướng dẫn tôi sàng lọc cổ phiếu theo chiến lược Đầu tư Giá Trị (Value Investing) trên thị trường Việt Nam"),
        ("📈 Swing Trade",          "Tiêu chí nào để lọc cổ phiếu phù hợp cho chiến lược Swing Trade 3-30 ngày?"),
        ("💰 Cổ tức cao",          "Cổ phiếu nào trên HOSE có tỷ suất cổ tức > 6% và tài chính lành mạnh?"),
        ("🛡️ Phòng thủ",          "Tư vấn danh mục phòng thủ, rủi ro thấp cho thị trường biến động"),
        ("📊 Phân tích cổ phiếu", "Phân tích chi tiết cổ phiếu đang được chọn trong screener"),
        ("⚖️ Quản lý rủi ro",     "Tôi có vốn 100 triệu, muốn mua cổ phiếu với stop-loss 5%, hỏi về position sizing"),
        ("🎓 Hướng dẫn F0",       "Tôi là nhà đầu tư mới (F0), cần lộ trình học đầu tư chứng khoán từ đầu"),
        ("📰 Tin tức thị trường", "Cập nhật tin tức thị trường chứng khoán Việt Nam mới nhất hôm nay"),
    ]

    return html.Div([
        dcc.Store(id="chat-history-store", data=[], storage_type="session"),
        dcc.Store(id="chat-quick-prompts-store", data=[p[1] for p in quick_prompts]),
        dcc.Store(id="chat-pending-msg-store", data=None),
        # ── THÊM BƯỚC 3: POPUP BONG BÓNG CHAT (MẶC ĐỊNH ẨN) ───────────────
        html.Div(
            id="vinance-ai-popup",
            style={
                "position": "fixed",         # 🟢 Fix cứng vào màn hình giống nút Chat
                "bottom": "28px",            # 🟢 Bằng đúng lề dưới của nút Chat
                "right": "95px",             # 🟢 Lề phải 28px + Nút chat 56px + Khoảng cách 11px = 95px
                "backgroundColor": "#1e293b",
                "border": "1px solid rgba(14,165,233,0.3)",
                "borderRadius": "16px 16px 4px 16px",
                "padding": "12px",
                "width": "290px",
                "boxShadow": "0 10px 25px rgba(0,0,0,0.5), 0 0 0 1px rgba(14,165,233,0.1)",
                "zIndex": "9999",
                "display": "none",           # Ẩn đi, chỉ hiện khi có data
                "color": "#c9d1d9",
                "fontSize": "13px",
                "fontFamily": "'Inter', 'Segoe UI', sans-serif",
                "animation": "fadeInUp 0.3s ease-out",
            }
        ),

        # ── FLOATING BUTTON ───────────────────────────────────────────────────
        html.Div([
            html.Div(style={
                "position": "absolute", "inset": "-6px", "borderRadius": "50%",
                "border": "2px solid rgba(14,165,233,0.4)",
                "animation": "vinance-pulse 2.5s ease-in-out infinite",
            }),
            html.Div([
                html.Img(src="/assets/VinanceAI.png", style={
                    "width": "100%", "height": "100%",
                    "borderRadius": "50%", "objectFit": "cover",
                }),
            ], className="vinance-fab-inner", style={
                "width": "56px", "height": "56px", "borderRadius": "50%",
                "background": "linear-gradient(135deg, #0ea5e9 0%, #6366f1 100%)",
                "display": "flex", "alignItems": "center", "justifyContent": "center",
                "cursor": "pointer", "overflow": "hidden",
                "boxShadow": "0 4px 20px rgba(14,165,233,0.5), 0 2px 8px rgba(0,0,0,0.3)",
                "position": "relative", "zIndex": "1",
                "transition": "transform 0.2s ease, box-shadow 0.2s ease",
            }),
            html.Div("AI", style={
                "position": "absolute", "top": "-2px", "right": "-2px",
                "background": "#10b981", "color": "#fff",
                "fontSize": "8px", "fontWeight": "700",
                "padding": "2px 5px", "borderRadius": "4px",
                "letterSpacing": "0.5px",
                "fontFamily": "'Inter', sans-serif", "zIndex": "2",
            }),
        ], id="chat-toggle-btn", n_clicks=0, style={
            "position": "fixed", "bottom": "28px", "right": "28px",
            "zIndex": "9998", "cursor": "pointer",
            "width": "56px", "height": "56px",
        }),

        # ── CHAT PANEL ────────────────────────────────────────────────────────
        html.Div(
            id="chat-panel-premium-wrapper",
            children=[
                html.Div([

                    # Header
                    html.Div([
                        html.Div([
                            html.Img(src="/assets/VinanceAI.png", style={
                                "width": "38px", "height": "38px", "borderRadius": "50%",
                                "objectFit": "cover",
                                "boxShadow": "0 2px 8px rgba(14,165,233,0.4)", "flexShrink": "0",
                            }),
                            html.Div([
                                html.Div("VinanceAI - Trợ lý phân tích đầu tư", style={
                                    "fontSize": "12px", "fontWeight": "700", "color": "#f1f5f9",
                                    "fontFamily": "'Inter', 'Segoe UI', sans-serif",
                                    "letterSpacing": "-0.3px",
                                }),
                                html.Div([
                                    html.Span(className="vinance-status-dot"),
                                    html.Span("Không phải khuyến nghị mua/bán.", style={
                                        "fontSize": "10px", "color": "#64748b",
                                        "fontFamily": "'Inter', sans-serif",
                                    }),
                                ], style={"display": "flex", "alignItems": "center", "gap": "5px"}),
                            ]),
                        ], style={"display": "flex", "gap": "10px", "alignItems": "center"}),

                        html.Div([
                            html.Span("🗑", id="chat-clear-btn", n_clicks=0, title="Xóa lịch sử", style={
                                "cursor": "pointer", "fontSize": "14px", "color": "#475569",
                                "marginRight": "12px", "transition": "color .2s", "userSelect": "none",
                            }),
                            html.Span("✕", id="chat-close-btn", n_clicks=0, style={
                                "cursor": "pointer", "fontSize": "16px", "color": "#475569",
                                "transition": "color .2s", "fontWeight": "300", "userSelect": "none",
                            }),
                        ], style={"display": "flex", "alignItems": "center"}),
                    ], style={
                        "display": "flex", "justifyContent": "space-between", "alignItems": "center",
                        "padding": "14px 16px", "background": "#0f172a",
                        "borderBottom": "1px solid rgba(148,163,184,0.08)",
                    }),

                    # Context bar
                    html.Div(id="chat-stock-context-bar", children=[]),

                    # Messages area
                    html.Div(
                        id="chat-messages-area",
                        children=[
                            html.Div([
                                html.Img(src="/assets/VinanceAI.png", style={
                                    "width": "32px", "height": "32px", "borderRadius": "50%",
                                    "objectFit": "cover",
                                    "flexShrink": "0",
                                }),
                                html.Div([
                                    html.Div([
                                        html.Div("Xin chào! Tôi là VinanceAI 👋", style={
                                            "fontSize": "13px", "fontWeight": "600",
                                            "color": "#e2e8f0", "marginBottom": "8px",
                                        }),
                                        html.Div("Tôi là trợ lý phân tích theo ngữ cảnh của FSS, giúp bạn:", style={
                                            "fontSize": "12px", "color": "#94a3b8",
                                            "marginBottom": "10px", "lineHeight": "1.6",
                                        }),
                                        html.Div([
                                            html.Div("📊 Giải thích FSS Score, chỉ số định lượng",       style={"fontSize": "12px", "color": "#cbd5e1", "marginBottom": "4px"}),
                                            html.Div("⚖️ Tóm tắt tăng trưởng, chất lượng và động lượng",       style={"fontSize": "12px", "color": "#cbd5e1", "marginBottom": "4px"}),
                                            html.Div("🎯 Phân tích theo 10 chiến lược đầu tư", style={"fontSize": "12px", "color": "#cbd5e1"}),
                                            html.Div("⚠️ Làm rõ các lưu ý từ dữ liệu doanh nghiệp", style={"fontSize": "12px", "color": "#cbd5e1"}),
                                        ], style={"paddingLeft": "4px"}),
                                        html.Div("Chọn một mã cổ phiếu trong bảng, tôi phân tích theo đúng ngữ cảnh bạn đang xem!", style={
                                            "fontSize": "12px", "color": "#7dd3fc",
                                            "marginTop": "10px", "fontStyle": "italic",
                                        }),
                                    ], style={
                                        "background": "#1e293b", "padding": "12px 14px",
                                        "borderRadius": "4px 18px 18px 18px",
                                        "border": "1px solid rgba(148,163,184,0.1)",
                                        "boxShadow": "0 2px 8px rgba(0,0,0,0.2)",
                                    }),
                                ], style={"flex": "1"}),
                            ], style={"display": "flex", "gap": "10px", "alignItems": "flex-start", "padding": "16px 14px"}),
                        ],
                        style={
                            "flex": "1", "overflowY": "auto", "padding": "8px 0",
                            "background": "#0f172a",
                            "scrollbarWidth": "thin",
                            "scrollbarColor": "#334155 #0f172a",
                        }
                    ),

                    # Typing indicator
                    html.Div(id="chat-typing-indicator", children=[], style={"minHeight": "0"}),

                    # Quick prompts
                    html.Div([
                        *[html.Button(
                            label,
                            id={"type": "chat-quick-btn", "index": i},
                            n_clicks=0,
                            style={
                                "background": "rgba(30,41,59,0.8)",
                                "border": "1px solid rgba(148,163,184,0.15)",
                                "color": "#94a3b8", "fontSize": "11px",
                                "padding": "5px 10px", "cursor": "pointer",
                                "whiteSpace": "nowrap", "borderRadius": "20px",
                                "transition": "all 0.2s ease",
                                "fontFamily": "'Inter', 'Segoe UI', sans-serif",
                            }
                        ) for i, (label, _) in enumerate(quick_prompts)]
                    ], id="chat-quick-prompts-bar", style={
                        "display": "flex", "gap": "6px", "padding": "8px 12px",
                        "overflowX": "auto", "borderTop": "1px solid rgba(148,163,184,0.08)",
                        "background": "#0f172a",
                    }),

                    # Input row
                    html.Div([
                        dcc.Input(
                            id="chat-input",
                            placeholder="Trò chuyện với VinanceAI...",
                            debounce=False, type="text",
                            style={
                                "flex": "1", "background": "#1e293b",
                                "border": "1px solid rgba(148,163,184,0.2)",
                                "color": "#e2e8f0", "padding": "10px 14px",
                                "fontSize": "13px",
                                "fontFamily": "'Inter', 'Segoe UI', sans-serif",
                                "outline": "none", "borderRadius": "12px",
                                "transition": "border-color 0.2s",
                            },
                            n_submit=0,
                        ),
                        html.Button(
                            "➤", id="chat-send-btn", n_clicks=0,
                            style={
                                "width": "42px", "height": "42px",
                                "background": "linear-gradient(135deg, #0ea5e9, #6366f1)",
                                "border": "none", "color": "#fff", "cursor": "pointer",
                                "fontSize": "16px", "fontWeight": "700",
                                "display": "flex", "alignItems": "center", "justifyContent": "center",
                                "flexShrink": "0", "borderRadius": "12px",
                                "boxShadow": "0 2px 8px rgba(14,165,233,0.4)",
                                "transition": "all .15s ease",
                            }
                        ),
                    ], style={
                        "display": "flex", "gap": "8px", "alignItems": "center",
                        "padding": "10px 12px", "borderTop": "1px solid rgba(148,163,184,0.08)",
                        "background": "#0f172a",
                    }),

                    # Footer
                    html.Div(
                        "Powered by Gemini · Model: {}".format(GEMINI_MODEL),
                        style={
                            "textAlign": "center", "fontSize": "10px",
                            "color": "#334155", "padding": "5px", "background": "#0a1120",
                            "letterSpacing": "0.3px", "fontFamily": "'Inter', sans-serif",
                        }
                    ),

                ], id="chat-panel", style={
                    "position": "fixed", "bottom": "96px", "right": "28px",
                    "width": "380px", "height": "600px",
                    "background": "#0f172a",
                    "border": "1px solid rgba(148,163,184,0.12)",
                    "boxShadow": "0 20px 60px rgba(0,0,0,0.6), 0 0 0 1px rgba(14,165,233,0.1)",
                    "display": "flex", "flexDirection": "column",
                    "overflow": "hidden", "zIndex": "99999",
                    "transform": "scale(0.85) translateY(20px)",
                    "opacity": "0", "pointerEvents": "none",
                    "transition": "all 0.25s cubic-bezier(0.34, 1.56, 0.64, 1)",
                    "borderRadius": "20px",
                }),
                # ── PAYWALL (hiện khi chưa VIP) ──
                html.Div([
                    html.Div([
                        # ── Nút X đóng paywall ──
                        html.Span(
                            "✕",
                            id="chat-paywall-close-btn",
                            n_clicks=0,
                            style={
                                "position": "absolute", "top": "12px", "right": "14px",
                                "cursor": "pointer", "fontSize": "16px", "color": "#475569",
                                "fontWeight": "300", "userSelect": "none",
                                "transition": "color .2s",
                            },
                        ),
                        html.I(className="fas fa-lock",
                               style={"fontSize": "28px", "color": "#0ea5e9",
                                      "marginBottom": "12px", "display": "block"}),
                        html.Div("VinanceAI · Chuyên gia đầu tư",
                                 style={"fontSize": "14px", "fontWeight": "700",
                                        "color": "#f1f5f9", "marginBottom": "6px"}),
                        html.Div("Tính năng dành riêng cho thành viên VIP.",
                                 style={"fontSize": "12px", "color": "#64748b",
                                        "marginBottom": "16px", "lineHeight": "1.6"}),
                        html.Div([
                            html.Div("✓  Phân tích cổ phiếu cá nhân hóa",
                                     style={"fontSize": "12px", "color": "#94a3b8",
                                            "marginBottom": "5px"}),
                            html.Div("✓  Tư vấn chiến lược theo hồ sơ IPS",
                                     style={"fontSize": "12px", "color": "#94a3b8",
                                            "marginBottom": "5px"}),
                            html.Div("✓  Cảnh báo rủi ro danh mục real-time",
                                     style={"fontSize": "12px", "color": "#94a3b8"}),
                        ], style={"marginBottom": "18px", "textAlign": "left",
                                  "width": "100%"}),
                        html.Button(
                            [html.I(className="fas fa-sign-in-alt",
                                    style={"marginRight": "8px"}),
                             "Đăng nhập để mở khóa"],
                            id="chat-paywall-login-btn",
                            n_clicks=0,
                            style={
                                "width": "100%", "padding": "10px",
                                "background": "linear-gradient(135deg, #0ea5e9, #6366f1)",
                                "border": "none", "borderRadius": "8px",
                                "color": "#fff", "fontSize": "13px",
                                "fontWeight": "700", "cursor": "pointer",
                            }
                        ),
                    ], style={
                        "display": "flex", "flexDirection": "column",
                        "alignItems": "center", "textAlign": "center",
                        "padding": "28px 20px",
                        "position": "relative",   # ← thêm dòng này
                    }),
                ], id="chat-paywall", style={"display": "none"}),

            ],
        ),
    ])


# ── CALLBACKS ─────────────────────────────────────────────────────────────────
app.clientside_callback(
    """
    function(n_open, n_close, chat_style, zalo_style, auth_data) {
        if (!n_open && !n_close) return [
            window.dash_clientside.no_update,
            window.dash_clientside.no_update,
            window.dash_clientside.no_update,
        ];

        var ctx = window.dash_clientside.callback_context;
        if (!ctx || !ctx.triggered || !ctx.triggered.length)
            return [window.dash_clientside.no_update,
                    window.dash_clientside.no_update,
                    window.dash_clientside.no_update];

        var trigger = ctx.triggered[0].prop_id;
        var zalo_hidden = Object.assign({}, zalo_style, {display: 'none'});

        var style_open = Object.assign({}, chat_style, {
            transform: 'scale(1) translateY(0)',
            opacity: '1',
            pointerEvents: 'auto'
        });
        var style_closed = Object.assign({}, chat_style, {
            transform: 'scale(0.85) translateY(20px)',
            opacity: '0',
            pointerEvents: 'none'
        });

        var is_closed = (chat_style.opacity === '0' || chat_style.opacity === 0
                         || chat_style.pointerEvents === 'none');

        // Nút close → đóng panel, ẩn paywall
        if (trigger.indexOf('chat-close-btn') !== -1) {
            return [style_closed, zalo_hidden, {display: 'none'}];
        }

        // Nút toggle (icon V)
        if (trigger.indexOf('chat-toggle-btn') !== -1) {
            if (!is_closed) {
                // Đang mở → đóng
                return [style_closed, window.dash_clientside.no_update,
                        {display: 'none'}];
            }

            // Đang đóng → kiểm tra VIP
            var isVip = auth_data && auth_data.logged_in
                        && (auth_data.tier === 'pro' || auth_data.tier === 'b2b');

            if (isVip) {
                // VIP: mở chat panel, ẩn paywall, đóng zalo
                return [style_open, zalo_hidden, {display: 'none'}];
            } else {
                // Non-VIP: KHÔNG mở chat panel, hiện paywall, đóng zalo
                return [
                    window.dash_clientside.no_update,
                    zalo_hidden,
                    {
                        display: 'block',
                        position: 'fixed',
                        bottom: '96px',
                        right: '28px',
                        width: '360px',
                        backgroundColor: '#0f172a',
                        border: '1px solid rgba(14,165,233,0.25)',
                        borderRadius: '16px',
                        boxShadow: '0 20px 60px rgba(0,0,0,0.6)',
                        zIndex: '10001',
                        fontFamily: "'Inter', 'Segoe UI', sans-serif",
                    }
                ];
            }
        }

        return [window.dash_clientside.no_update,
                window.dash_clientside.no_update,
                window.dash_clientside.no_update];
    }
    """,
    Output("chat-panel",       "style"),
    Output("zalo-chat-window", "style", allow_duplicate=True),
    Output("chat-paywall",     "style"),
    Input("chat-toggle-btn",   "n_clicks"),
    Input("chat-close-btn",    "n_clicks"),
    State("chat-panel",        "style"),
    State("zalo-chat-window",  "style"),
    State("auth-store",        "data"),
    prevent_initial_call=True,
)
def toggle_chat_panel(n_open, n_close, chat_style, zalo_style):
    ctx = callback_context
    is_chat_closed = (chat_style.get("opacity", "0") in ("0", 0) or
                      chat_style.get("pointerEvents") == "none")

    zalo_hidden = {**(zalo_style or {}), "display": "none"}
    
    style_open   = {**chat_style, "transform": "scale(1) translateY(0)",
                    "opacity": "1", "pointerEvents": "auto"}
    style_closed = {**chat_style, "transform": "scale(0.85) translateY(20px)",
                    "opacity": "0", "pointerEvents": "none"}

    if "chat-toggle-btn" in ctx.triggered[0]["prop_id"]:
        if is_chat_closed:
            # Mở vinance → đóng zalo
            return style_open, zalo_hidden
        else:
            return style_closed, no_update
    return style_closed, no_update


@app.callback(
    Output("chat-stock-context-bar", "children"),
    Input("screener-table", "selectedRows"),
    prevent_initial_call=False,
)
def update_stock_context_bar(selected_rows):
    if not selected_rows:
        return []
    stock   = selected_rows[0]
    ticker  = stock.get("Ticker", "")
    company = stock.get("Company Common Name", stock.get("Name", ""))
    price   = stock.get("Price Close", stock.get("Price", ""))
    vgm     = stock.get("VGM Score", "")
    p1w     = stock.get("Perf_1W", None)

    p1w_color = "#10b981" if (p1w or 0) >= 0 else "#ef4444"
    p1w_str = (f"+{p1w:.1f}%" if isinstance(p1w, (int, float)) and p1w >= 0
               else f"{p1w:.1f}%" if isinstance(p1w, (int, float)) else "–")

    return html.Div([
        html.Div([
            html.Span(ticker, style={
                "color": "#38bdf8", "fontWeight": "700", "fontSize": "12px",
                "marginRight": "8px", "letterSpacing": "0.5px",
                "fontFamily": "'Inter', sans-serif",
            }),
            html.Span(company[:24], style={
                "color": "#64748b", "fontSize": "11px", "flex": "1",
                "overflow": "hidden", "textOverflow": "ellipsis", "whiteSpace": "nowrap",
                "fontFamily": "'Inter', sans-serif",
            }),
        ], style={"display": "flex", "alignItems": "center", "flex": "1", "minWidth": "0"}),
        html.Div([
            html.Span(f"{int(price):,}đ" if isinstance(price, (int, float)) else "",
                      style={"color": "#fbbf24", "fontSize": "11px", "fontWeight": "600", "marginRight": "6px"}),
            html.Span(p1w_str, style={"color": p1w_color, "fontSize": "11px", "fontWeight": "600", "marginRight": "6px"}),
            html.Span(f"Xếp hạng:{vgm}", style={
                "background": "rgba(14,165,233,0.1)",
                "border": "1px solid rgba(14,165,233,0.25)",
                "color": "#38bdf8", "fontSize": "10px",
                "padding": "1px 6px", "borderRadius": "4px",
                "fontFamily": "'Inter', sans-serif",
            }),
        ], style={"display": "flex", "alignItems": "center", "flexShrink": "0"}),
    ], style={
        "display": "flex", "alignItems": "center", "padding": "7px 14px",
        "background": "rgba(14,165,233,0.05)",
        "borderBottom": "1px solid rgba(14,165,233,0.1)",
        "gap": "8px",
    })


# # ── CALLBACK 1: Quick button → ghi vào store (KHÔNG gọi API) ─────────────────
# @app.callback(
#     Output("chat-pending-msg-store", "data"),
#     Input({"type": "chat-quick-btn", "index": ALL}, "n_clicks"),
#     State("chat-quick-prompts-store", "data"),
#     prevent_initial_call=True,
# )
# def stage_quick_message(quick_clicks, quick_prompts_list):
#     """Chỉ ghi message vào store — KHÔNG gọi API."""
#     ctx = callback_context
#     if not ctx.triggered or not any(c for c in (quick_clicks or []) if c):
#         return no_update

#     trigger = ctx.triggered[0]["prop_id"]
#     if "chat-quick-btn" not in trigger:
#         return no_update

#     try:
#         idx = json.loads(trigger.split(".")[0])["index"]
#         if 0 <= idx < len(quick_prompts_list or []):
#             return {
#                 "msg": quick_prompts_list[idx],
#                 "ts":  datetime.now().isoformat(),
#             }
#     except Exception:
#         pass

#     return no_update

# ── CALLBACK 2: Xử lý chat chính — gọi OpenAI ────────────────────────────────
@app.callback(
    Output("chat-messages-area",    "children"),
    Output("chat-history-store",    "data"),
    Output("chat-input",            "value"),
    # XOÁ Output("chat-typing-indicator", "children") ở đây, vì 'running' sẽ quản lý nó

    Input("chat-send-btn",          "n_clicks"),
    Input("chat-input",             "n_submit"),
    Input("chat-clear-btn",         "n_clicks"),
    Input({"type": "chat-quick-btn", "index": ALL}, "n_clicks"),
    State("chat-input",             "value"),
    State("chat-history-store",     "data"),
    State("screener-table",         "selectedRows"),
    State("chat-quick-prompts-store", "data"),
    State("auth-store",             "data"),
    
    # --- CẤU HÌNH BACKGROUND CALLBACK ---
    background=True,
    running=[
        # 1. Disable nút gửi (để user ko bấm liên tục)
        (Output("chat-send-btn", "disabled"), True, False),
        
        # 2. Disable ô nhập liệu
        (Output("chat-input", "disabled"), True, False),
        
        # 3. Hiện bong bóng "Đang gõ..." trong khi chờ, và xoá đi khi xong
        (
            Output("chat-typing-indicator", "children"),
            html.Div([
                html.Img(src="/assets/VinanceAI.png", style={
                    "width": "32px", "height": "32px", "borderRadius": "50%",
                    "objectFit": "cover", "opacity": "0.6",
                    "flexShrink": "0",
                }),
                html.Div(
                    "VinanceAI đang suy nghĩ...", 
                    style={
                        "background": "#1e293b", "padding": "10px 14px",
                        "borderRadius": "4px 18px 18px 18px", "fontSize": "13px",
                        "color": "#94a3b8", "fontStyle": "italic"
                    }
                )
            ], style={"display": "flex", "gap": "10px", "alignItems": "flex-start", "padding": "0 14px 12px 14px", "animation": "pulse 2s infinite"}),
            [] # Trả về list rỗng (ẩn đi) khi callback hoàn thành
        )
    ],
    prevent_initial_call=True,
)
def handle_chat(n_send, n_enter, n_clear, quick_clicks, user_input,
                history, selected_rows, quick_prompts_list, auth_data):
    
    # --- (GIỮ NGUYÊN TOÀN BỘ LOGIC BÊN TRONG CỦA BẠN) ---
    ctx = callback_context
    if not ctx.triggered:
        return no_update, no_update, no_update

    trigger = ctx.triggered[0]["prop_id"]
    history = history or []

    # ── Xóa lịch sử ──
    if "chat-clear-btn" in trigger:
        welcome = html.Div([
            # ... (Giữ nguyên phần vẽ UI welcome của bạn) ...
            html.Div("Đã xóa lịch sử 🗑️ Tôi có thể giúp gì cho bạn?", style={"color": "#cbd5e1"})
        ])
        return [welcome], [], ""

    # ── BẢO VỆ SERVER-SIDE: chặn gọi Gemini API nếu không phải VIP ──────────
    # AUDIT FIX (mục 4 - Major Issue): dùng chung require_entitlement()
    # (src/callbacks/auth_callbacks.py) thay vì tự viết lại logic re-check
    # server-side ở đây — tránh 2 bản sao có thể lệch nhau.
    from src.callbacks.auth_callbacks import require_entitlement
    is_vip_serverside = require_entitlement(auth_data, allowed_tiers=["pro", "b2b"])

    if not is_vip_serverside:
        history.append({
            "role": "model",
            "parts": [{"text": "🔒 Tính năng VinanceAI Chat chỉ dành cho tài khoản VIP. Vui lòng đăng nhập và kích hoạt VIP để sử dụng."}],
            "time": datetime.now().strftime("%H:%M"),
        })
        bubbles = _render_messages(history)
        return bubbles, history, ""

    message = ""

    # ── Xử lý khi nhấn nút gửi hoặc Enter ──
    if "chat-send-btn" in trigger or "chat-input" in trigger:
        if user_input and user_input.strip():
            message = user_input.strip()

    # ── Xử lý khi nhấn Quick Prompt ──
    elif "chat-quick-btn" in trigger:
        # Kiểm tra xem có click thật sự không, tránh auto-trigger lúc mount
        if not any(c for c in (quick_clicks or []) if c):
            return no_update, no_update, no_update
            
        try:
            # Lấy index của nút vừa nhấn
            idx = json.loads(trigger.split(".")[0])["index"]
            if 0 <= idx < len(quick_prompts_list or []):
                message = quick_prompts_list[idx]
        except Exception as e:
            logger.error(f"Lỗi đọc Quick Prompt: {e}")
            return no_update, no_update, no_update

    # Nếu không có tin nhắn hợp lệ thì không làm gì cả
    if not message:
        return no_update, no_update, no_update

    # ── Thêm user message vào history ──
    time_now = datetime.now().strftime("%H:%M")
    history.append({"role": "user", "parts": [{"text": message}], "time": time_now})

    # ── Gọi OpenAI ──
    stock_context = selected_rows[0] if selected_rows else None
    screener_ctx  = _build_screener_context()

    # Chỉ truyền các message có role hợp lệ
    api_msgs = [
        {"role": m["role"], "parts": m["parts"]}
        for m in history if m["role"] in ("user", "model")
    ]
    ai_text = _call_gemini(history, stock_context, screener_ctx)

    # ── Thêm AI response ──
    history.append({"role": "model", "parts": [{"text": ai_text}], "time": datetime.now().strftime("%H:%M")})

    bubbles = _render_messages(history)
    auto_scroll = html.Script("""
        setTimeout(function(){
            var el = document.getElementById('chat-messages-area');
            if (el) el.scrollTop = el.scrollHeight;
        }, 80);
    """)
    return bubbles + [auto_scroll], history, ""

# ── CALLBACK 3: TÍNH TOÁN NAV VÀ HIỂN THỊ POPUP KHUYẾN NGHỊ ──────

@app.callback(
    [Output("vinance-ai-popup", "children"),
     Output("vinance-ai-popup", "style")],
    # 🟢 SỬA: Đổi rowData thành virtualRowData để lấy list cổ phiếu ĐÃ LỌC & SẮP XẾP trên UI
    [Input("screener-table", "virtualRowData"), 
     Input("nav-input", "value")],
    [State("vinance-ai-popup", "style")],
    prevent_initial_call=True
)
def trigger_vinance_popup(grid_data, nav_str, current_style):
    from dash import no_update, html # Đảm bảo đã import
    if not grid_data or not nav_str:
        return no_update, no_update
    try:
        nav = int(str(nav_str).replace(',', ''))
    except Exception as e:
        print(f"❌ Lỗi format NAV: {e}") 
        return no_update, no_update
        
    if nav < 1000000: 
        return no_update, no_update
        
    import pandas as pd
    from src.backend.quant_engine import calculate_robo_allocation
    df = pd.DataFrame(grid_data)

    # LƯU Ý: Trước đây gọi calculate_robo_allocation(df, nav) KHÔNG truyền
    # df_price (giá lịch sử) → hàm luôn rơi vào nhánh fallback "chia đều"
    # (xem comment trong quant_engine.py: "Không có dữ liệu lịch sử giá, chia
    # tỷ trọng đều"), dù tên gọi UI là "AI đề xuất danh mục" khiến người dùng
    # tưởng đã chạy tối ưu hóa Markowitz thật. Giờ load giá lịch sử để hàm có
    # thể chạy đúng thuật toán Markowitz + Monte Carlo stress test.
    df_price_hist = None
    try:
        from src.backend.data_loader import load_market_data
        df_price_hist = load_market_data()
    except Exception as e:
        logger.warning(f"⚠️ Không load được lịch sử giá cho Robo Allocation, dùng fallback chia đều: {e}")

    allocations, remaining = calculate_robo_allocation(df, nav, df_price=df_price_hist)
    
    if not allocations:
        return no_update, no_update
        
    # Xây dựng giao diện tin nhắn Popup
    msg_elements = [
        html.Div([
            html.Div([
                html.I(className="fas fa-robot", style={"marginRight": "6px", "color": "#0ea5e9"}),
                "VinanceAI Đề xuất:"
            ]),
            html.I(className="fas fa-times", id="close-vinance-popup", 
                   style={"cursor": "pointer", "color": "#94a3b8", "fontSize": "16px", "padding": "0 4px"})
        ], style={"display": "flex", "justifyContent": "space-between", "alignItems": "center", 
                  "fontWeight": "700", "color": "#38bdf8", "marginBottom": "8px", "fontSize": "14px"}),
        
        html.Div(f"💰 Vốn: {nav:,.0f} đ", style={"fontSize": "11px", "color": "#94a3b8", "marginBottom": "6px"})
    ]
    
    for item in allocations:
        # 🟢 SỬA LỖI GIAO DIỆN: Render số sao thay vì chữ
        star_val = item.get('Score', 0)
        stars_str = "⭐" * int(star_val) if pd.notna(star_val) and int(star_val) > 0 else "N/A"

        msg_elements.append(
            html.Div([
                html.Span(f"{item['Ticker']}", style={"fontWeight": "bold", "color": "#e2e8f0"}),
                html.Span(f" ({stars_str}): ", style={"color": "#fbbf24", "fontSize": "10px"}), # Đổi sang màu vàng cho sao
                html.Span(f"Mua {item['Volume']:,} cp", style={"color": "#10b981", "fontWeight": "600"})
            ], style={"marginBottom": "4px", "padding": "4px", "background": "rgba(255,255,255,0.03)", "borderRadius": "4px"})
        )
        
    msg_elements.append(
        html.Div(f"💵 Sức mua dư: {remaining:,.0f} đ", 
                 style={"marginTop": "8px", "color": "#fbbf24", "fontWeight": "bold", "fontSize": "12px"})
    )
    
    msg_elements.append(
        html.Div("Sẽ tự động đóng sau 1 phút...", style={"fontSize": "9px", "color": "#475569", "marginTop": "6px", "textAlign": "right"})
    )
    
    new_style = current_style.copy() if current_style else {}
    new_style["display"] = "block"
    
    return msg_elements, new_style

# ── CALLBACK 4: XỬ LÝ NÚT X VÀ HẸN GIỜ TẮT SAU 1 PHÚT ──────
clientside_callback(
    """
    function(popup_children) {
        if (popup_children) {
            var popup = document.getElementById('vinance-ai-popup');
            if (!popup) return window.dash_clientside.no_update;

            // 1. XỬ LÝ LẮNG NGHE NÚT X (ĐÓNG POPUP BẰNG TAY)
            var closeBtn = document.getElementById('close-vinance-popup');
            if (closeBtn) {
                closeBtn.onclick = function() {
                    popup.style.display = 'none';
                    // Clear luôn cái đồng hồ đếm ngược nếu user đã tự đóng
                    if (window.vinancePopupTimeout) {
                        clearTimeout(window.vinancePopupTimeout);
                    }
                };
            }

            // 2. XỬ LÝ AUTO-CLOSE 1 PHÚT (60,000 ms)
            if (window.vinancePopupTimeout) {
                clearTimeout(window.vinancePopupTimeout);
            }
            
            window.vinancePopupTimeout = setTimeout(function() {
                if (popup.style.display !== 'none') { // Chỉ chạy hiệu ứng nếu popup đang mở
                    popup.style.opacity = '0';
                    popup.style.transition = 'opacity 0.5s ease';
                    setTimeout(function() { 
                        popup.style.display = 'none'; 
                        popup.style.opacity = '1'; // Reset opacity cho lần mở sau
                    }, 500);
                }
            }, 60000); 
        }
        return window.dash_clientside.no_update;
    }
    """,
    Output("vinance-ai-popup", "id"), 
    Input("vinance-ai-popup", "children"),
    prevent_initial_call=True
)