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
from dash import Input, Output, State, html, dcc, no_update, callback_context, ALL
from src.app_instance import app

logger = logging.getLogger(__name__)

# ── CẤU HÌNH OPENAI ──────────────────────────────────────────────────────────
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_MODEL   = os.environ.get("OPENAI_MODEL", "gpt-3.5-turbo")

# ── SYSTEM PROMPT VINANCEAI ───────────────────────────────────────────────────
VINANCE_SYSTEM_PROMPT = """Bạn là **VinanceAI** – chuyên gia tài chính và chứng khoán hàng đầu Việt Nam với hơn 20 năm kinh nghiệm thực chiến. Bạn chuyên sâu về thị trường chứng khoán Việt Nam (HOSE, HNX, UPCOM).

Sứ mệnh: Giúp nhà đầu tư Việt Nam – từ F0 đến chuyên nghiệp – đưa ra quyết định đầu tư thông minh, có căn cứ và kiểm soát rủi ro hiệu quả.

## NGUYÊN TẮC CÁ NHÂN HÓA
Khi bắt đầu cuộc hội thoại mới, hỏi người dùng:
1. Trình độ: F0 (mới bắt đầu) / F1 (đã có kinh nghiệm) / Chuyên nghiệp
2. Mục tiêu: Đầu tư dài hạn / Swing trade / Lướt sóng / Tích lũy cổ tức
3. Vốn tham khảo: Dưới 50tr / 50–200tr / 200tr–1 tỷ / Trên 1 tỷ
4. Khẩu vị rủi ro: Thấp / Trung bình / Cao
→ Dựa trên câu trả lời, cá nhân hóa toàn bộ cách tư vấn.

## 6 CHIẾN LƯỢC SÀNG LỌC CỔ PHIẾU
Khi người dùng hỏi về chiến lược hoặc lọc cổ phiếu:

**Chiến lược 1 – GIÁ TRỊ (Value Investing):**
P/E < 15, P/B < 1.5, ROE > 15% liên tục 3 năm, Nợ/VCP < 1, EPS tăng trưởng dương, CFO > 0, cổ tức đều

**Chiến lược 2 – TĂNG TRƯỞNG (Growth Investing):**
Doanh thu tăng > 20% YoY, EPS tăng > 25% YoY, ROE > 20%, biên LN ròng mở rộng, PEG < 1.5

**Chiến lược 3 – CỔ TỨC (Dividend Investing):**
Tỷ suất cổ tức > 6%, lịch sử trả đều ≥ 5 năm, Payout Ratio 40–70%, FCF đủ bao phủ, nợ vay thấp

**Chiến lược 4 – SWING TRADE (3–30 ngày):**
Breakout khỏi vùng tích lũy, Volume > 150% MA20, RSI 45–65, MACD cắt lên, giá trên MA20, Risk/Reward ≥ 1:2

**Chiến lược 5 – LƯỚT SÓNG T+ (1–3 ngày):**
Nến đảo chiều tại hỗ trợ mạnh, RSI < 35 hoặc bullish divergence, Volume ≥ 2x TB10 phiên, Top 50 HoSE theo giá trị khớp

**Chiến lược 6 – PHÒNG THỦ / RỦI RO THẤP:**
VN30, Beta < 0.8, ngành điện/nước/thực phẩm/dược, không dùng margin, cổ tức tiền mặt đều đặn

## TÍNH NĂNG TÍNH TOÁN
Khi người dùng cung cấp số liệu, tự động tính:
- Position sizing theo % vốn và stop-loss
- Tỷ lệ Risk/Reward
- Lãi/lỗ sau phí (0.1% mỗi chiều) và thuế (0.1% khi bán)
- Định giá theo P/E mục tiêu, tỷ suất cổ tức
- Lãi kép, Quy tắc 72

## FORMAT TRẢ LỜI
- Tiếng Việt, chuyên nghiệp nhưng gần gũi
- Với F0: đơn giản, có ví dụ, giải thích thuật ngữ
- Với F1/Pro: kỹ thuật, số liệu, đi thẳng vào vấn đề
- Dùng emoji: 📊 📈 💰 ⚠️ 🎯 để phân biệt phần
- Tối đa ~300 từ mỗi câu trả lời, trừ khi cần phân tích sâu
- Kết thúc phân tích cổ phiếu bằng: ⚠️ Chỉ mang tính tham khảo, không phải lời khuyên đầu tư chính thức.

## CHẾ ĐỘ GIẢNG DẠY F0
Cảnh báo các sai lầm phổ biến:
- Mua đuổi giá sau tăng mạnh
- Không đặt stop-loss
- Dùng margin khi chưa có kinh nghiệm
- "Yêu cổ phiếu" – không chịu cắt lỗ
- Đầu tư theo tin đồn, Zalo group
"""


# ── GỌI OPENAI API ────────────────────────────────────────────────────────────
def _call_openai(messages: list, stock_context: dict = None, screener_context: str = "") -> str:
    """Gọi OpenAI ChatCompletion API với retry khi bị rate limit."""
    import time as _time

    if not OPENAI_API_KEY:
        return "⚠️ Chưa cấu hình OPENAI_API_KEY. Vui lòng thêm API key vào biến môi trường."

    try:
        import openai
    except ImportError:
        return "❌ Thư viện openai chưa được cài. Thêm 'openai>=1.0.0' vào requirements.txt."

    # ── Xây dựng system prompt ──
    system_text = VINANCE_SYSTEM_PROMPT

    if screener_context:
        system_text += screener_context

    if stock_context:
        ticker  = stock_context.get('Ticker', 'N/A')
        company = stock_context.get('Company Common Name', stock_context.get('Name', 'N/A'))
        sector  = stock_context.get('Sector', 'N/A')
        pe      = stock_context.get('P/E', 'N/A')
        pb      = stock_context.get('P/B', 'N/A')
        roe     = stock_context.get('ROE (%)', stock_context.get('ROE', 'N/A'))
        rsi     = stock_context.get('RSI_14', stock_context.get('RSI', 'N/A'))
        vgm     = stock_context.get('VGM Score', 'N/A')
        p1w     = stock_context.get('Perf_1W', 'N/A')
        p1m     = stock_context.get('Perf_1M', 'N/A')
        price   = stock_context.get('Price Close', stock_context.get('Price', 'N/A'))
        system_text += f"""

## THÔNG TIN CỔ PHIẾU ĐANG ĐƯỢC CHỌN TRONG SCREENER
• Mã CK: {ticker}
• Tên công ty: {company}
• Ngành: {sector}
• Giá hiện tại: {price}
• P/E: {pe} | P/B: {pb}
• ROE: {roe}% | RSI(14): {rsi}
• VGM Score: {vgm}
• Hiệu suất 1 tuần: {p1w}% | 1 tháng: {p1m}%

Khi người dùng hỏi về cổ phiếu mà không chỉ rõ mã, hãy ưu tiên phân tích mã {ticker} này.
"""

    # ── Chuyển đổi messages từ format Gemini sang OpenAI ──
    # Gemini dùng role="model", OpenAI dùng role="assistant"
    openai_messages = [{"role": "system", "content": system_text}]
    for msg in messages:
        role = msg.get("role", "user")
        if role == "model":
            role = "assistant"
        text = ""
        parts = msg.get("parts", [])
        if parts and isinstance(parts, list):
            text = parts[0].get("text", "")
        elif isinstance(msg.get("content"), str):
            text = msg["content"]
        if text:
            openai_messages.append({"role": role, "content": text})

    # ── Retry với exponential backoff ──
    client = openai.OpenAI(api_key=OPENAI_API_KEY)
    max_retries = 3

    for attempt in range(max_retries):
        try:
            resp = client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=openai_messages,
                max_tokens=800,
                temperature=0.7,
            )
            return resp.choices[0].message.content

        except openai.RateLimitError:
            wait = 2 ** attempt
            logger.warning(f"OpenAI rate limit, thử lại sau {wait}s (lần {attempt+1}/{max_retries})")
            _time.sleep(wait)
            continue

        except openai.AuthenticationError:
            return "❌ OPENAI_API_KEY không hợp lệ. Kiểm tra lại trong biến môi trường hoặc Hugging Face Secrets."

        except openai.BadRequestError as e:
            logger.error(f"OpenAI BadRequest: {e}")
            return "❌ Request không hợp lệ. Thử xóa lịch sử chat và hỏi lại."

        except openai.APITimeoutError:
            if attempt < max_retries - 1:
                _time.sleep(2)
                continue
            return "⏱️ Kết nối OpenAI quá chậm. Vui lòng thử lại sau."

        except Exception as e:
            logger.error(f"OpenAI error (attempt {attempt+1}): {e}")
            if attempt < max_retries - 1:
                _time.sleep(1)
                continue
            return f"❌ Lỗi kết nối: {str(e)[:120]}"

    return "⏳ OpenAI đang quá tải. Vui lòng đợi 10-15 giây rồi thử lại."


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

        score_col = next((c for c in ["VGM Score", "VGM_Score", "vgm_score"] if c in df.columns), None)
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

        if score_col and tick_col:
            df_sorted = df.copy()
            df_sorted[score_col] = pd.to_numeric(df_sorted[score_col], errors='coerce')
            top_df = df_sorted.nlargest(15, score_col)
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
            lines.append("Top15VGM: " + "; ".join(rows))

        if sect_col and score_col:
            df_sector = df.copy()
            df_sector[score_col] = pd.to_numeric(df_sector[score_col], errors='coerce')
            sector_stats = df_sector.groupby(sect_col)[score_col].mean().sort_values(ascending=False).head(8)
            stats = [f"{s}:{v:.0f}({(df[sect_col]==s).sum()})" for s, v in sector_stats.items()]
            lines.append("Ngành(avgVGM): " + ", ".join(stats))

        lines.append("Dùng dữ liệu trên khi trả lời câu hỏi về thị trường.")
        result = "\n".join(lines)

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
                    html.Div("V", style={
                        "width": "32px", "height": "32px", "borderRadius": "50%",
                        "background": "linear-gradient(135deg, #0ea5e9, #6366f1)",
                        "display": "flex", "alignItems": "center", "justifyContent": "center",
                        "fontSize": "14px", "fontWeight": "900", "color": "#fff",
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

        # ── FLOATING BUTTON ───────────────────────────────────────────────────
        html.Div([
            html.Div(style={
                "position": "absolute", "inset": "-6px", "borderRadius": "50%",
                "border": "2px solid rgba(14,165,233,0.4)",
                "animation": "vinance-pulse 2.5s ease-in-out infinite",
            }),
            html.Div([
                html.Div("V", style={
                    "fontSize": "22px", "fontWeight": "900", "color": "#fff",
                    "letterSpacing": "-1px",
                    "fontFamily": "'Inter', 'Segoe UI', sans-serif",
                }),
            ], className="vinance-fab-inner", style={
                "width": "56px", "height": "56px", "borderRadius": "50%",
                "background": "linear-gradient(135deg, #0ea5e9 0%, #6366f1 100%)",
                "display": "flex", "alignItems": "center", "justifyContent": "center",
                "cursor": "pointer",
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
        html.Div([

            # Header
            html.Div([
                html.Div([
                    html.Div("V", style={
                        "width": "38px", "height": "38px", "borderRadius": "50%",
                        "background": "linear-gradient(135deg, #0ea5e9, #6366f1)",
                        "display": "flex", "alignItems": "center", "justifyContent": "center",
                        "fontSize": "18px", "fontWeight": "900", "color": "#fff",
                        "boxShadow": "0 2px 8px rgba(14,165,233,0.4)", "flexShrink": "0",
                    }),
                    html.Div([
                        html.Div("VinanceAI", style={
                            "fontSize": "15px", "fontWeight": "700", "color": "#f1f5f9",
                            "fontFamily": "'Inter', 'Segoe UI', sans-serif",
                            "letterSpacing": "-0.3px",
                        }),
                        html.Div([
                            html.Span(className="vinance-status-dot"),
                            html.Span("Chuyên gia đầu tư Việt Nam", style={
                                "fontSize": "11px", "color": "#64748b",
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
                        html.Div("V", style={
                            "width": "32px", "height": "32px", "borderRadius": "50%",
                            "background": "linear-gradient(135deg, #0ea5e9, #6366f1)",
                            "display": "flex", "alignItems": "center", "justifyContent": "center",
                            "fontSize": "14px", "fontWeight": "900", "color": "#fff",
                            "flexShrink": "0",
                        }),
                        html.Div([
                            html.Div([
                                html.Div("Xin chào! Tôi là VinanceAI 👋", style={
                                    "fontSize": "13px", "fontWeight": "600",
                                    "color": "#e2e8f0", "marginBottom": "8px",
                                }),
                                html.Div("Chuyên gia đầu tư chứng khoán Việt Nam. Tôi có thể giúp:", style={
                                    "fontSize": "12px", "color": "#94a3b8",
                                    "marginBottom": "10px", "lineHeight": "1.6",
                                }),
                                html.Div([
                                    html.Div("📊 Sàng lọc cổ phiếu theo 6 chiến lược",       style={"fontSize": "12px", "color": "#cbd5e1", "marginBottom": "4px"}),
                                    html.Div("📰 Cập nhật tin tức thị trường real-time",      style={"fontSize": "12px", "color": "#cbd5e1", "marginBottom": "4px"}),
                                    html.Div("⚖️ Tính toán quản lý rủi ro & định giá",       style={"fontSize": "12px", "color": "#cbd5e1", "marginBottom": "4px"}),
                                    html.Div("🎯 Tư vấn cá nhân hóa theo trình độ F0/F1/Pro", style={"fontSize": "12px", "color": "#cbd5e1"}),
                                ], style={"paddingLeft": "4px"}),
                                html.Div("Bạn đang ở trình độ nào? F0, F1, hay Chuyên nghiệp? 🚀", style={
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
                    placeholder="Hỏi VinanceAI về đầu tư chứng khoán...",
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
                "Powered by OpenAI GPT · Chỉ mang tính tham khảo",
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
            "overflow": "hidden", "zIndex": "9997",
            "transform": "scale(0.85) translateY(20px)",
            "opacity": "0", "pointerEvents": "none",
            "transition": "all 0.25s cubic-bezier(0.34, 1.56, 0.64, 1)",
            "borderRadius": "20px",
        }),
    ])


# ── CALLBACKS ─────────────────────────────────────────────────────────────────

# FIX: toggle_chat_panel CHỈ điều khiển chat-panel, KHÔNG output zalo-chat-window
# Tránh duplicate output conflict với toggle_zalo trong home_callbacks.py
@app.callback(
    Output("chat-panel", "style"),
    Input("chat-toggle-btn",   "n_clicks"),
    Input("chat-close-btn",    "n_clicks"),
    State("chat-panel",        "style"),
    prevent_initial_call=True,
)
def toggle_chat_panel(n_open, n_close, chat_style):
    ctx = callback_context
    if not ctx.triggered:
        return no_update

    is_chat_closed = (chat_style.get("opacity", "0") in ("0", 0) or
                      chat_style.get("pointerEvents") == "none")

    style_open   = {**chat_style, "transform": "scale(1) translateY(0)",
                    "opacity": "1", "pointerEvents": "auto"}
    style_closed = {**chat_style, "transform": "scale(0.85) translateY(20px)",
                    "opacity": "0", "pointerEvents": "none"}

    if "chat-toggle-btn" in ctx.triggered[0]["prop_id"]:
        return style_open if is_chat_closed else style_closed
    return style_closed


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
            html.Span(f"VGM:{vgm}", style={
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


# ── CALLBACK 1: Quick button → ghi vào store (KHÔNG gọi API) ─────────────────
@app.callback(
    Output("chat-pending-msg-store", "data"),
    Input({"type": "chat-quick-btn", "index": ALL}, "n_clicks"),
    State("chat-quick-prompts-store", "data"),
    prevent_initial_call=True,
)
def stage_quick_message(quick_clicks, quick_prompts_list):
    """Chỉ ghi message vào store — KHÔNG gọi API."""
    ctx = callback_context
    if not ctx.triggered or not any(c for c in (quick_clicks or []) if c):
        return no_update

    trigger = ctx.triggered[0]["prop_id"]
    if "chat-quick-btn" not in trigger:
        return no_update

    try:
        idx = json.loads(trigger.split(".")[0])["index"]
        if 0 <= idx < len(quick_prompts_list or []):
            return {
                "msg": quick_prompts_list[idx],
                "ts":  datetime.now().isoformat(),
            }
    except Exception:
        pass

    return no_update


# ── CALLBACK 2: Xử lý chat chính — gọi OpenAI ────────────────────────────────
@app.callback(
    Output("chat-messages-area",    "children"),
    Output("chat-history-store",    "data"),
    Output("chat-input",            "value"),
    Output("chat-typing-indicator", "children"),
    Input("chat-send-btn",          "n_clicks"),
    Input("chat-input",             "n_submit"),
    Input("chat-pending-msg-store", "data"),
    Input("chat-clear-btn",         "n_clicks"),
    State("chat-input",             "value"),
    State("chat-history-store",     "data"),
    State("screener-table",         "selectedRows"),
    prevent_initial_call=True,
)
def handle_chat(n_send, n_enter, pending_msg, n_clear, user_input,
                history, selected_rows):
    ctx = callback_context
    if not ctx.triggered:
        return no_update, no_update, no_update, no_update

    trigger = ctx.triggered[0]["prop_id"]
    history = history or []

    # ── Xóa lịch sử ──
    if "chat-clear-btn" in trigger:
        welcome = html.Div([
            html.Div("V", style={
                "width": "32px", "height": "32px", "borderRadius": "50%",
                "background": "linear-gradient(135deg, #0ea5e9, #6366f1)",
                "display": "flex", "alignItems": "center", "justifyContent": "center",
                "fontSize": "14px", "fontWeight": "900", "color": "#fff", "flexShrink": "0",
            }),
            html.Div("Đã xóa lịch sử 🗑️ Tôi có thể giúp gì cho bạn?", style={
                "background": "#1e293b", "padding": "10px 14px",
                "borderRadius": "4px 18px 18px 18px",
                "fontSize": "13px", "color": "#cbd5e1",
                "fontFamily": "'Inter', sans-serif",
                "border": "1px solid rgba(148,163,184,0.1)",
            }),
        ], style={"display": "flex", "gap": "10px", "alignItems": "flex-start", "padding": "16px 14px"})
        return [welcome], [], "", []

    # ── Xác định message ──
    message = ""
    if "chat-pending-msg-store" in trigger:
        if isinstance(pending_msg, dict) and pending_msg.get("msg"):
            message = pending_msg["msg"]
    elif user_input and user_input.strip():
        message = user_input.strip()

    if not message:
        return no_update, no_update, no_update, no_update

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
    ai_text = _call_openai(api_msgs, stock_context, screener_ctx)

    # ── Thêm AI response ──
    history.append({"role": "model", "parts": [{"text": ai_text}], "time": datetime.now().strftime("%H:%M")})

    bubbles = _render_messages(history)
    auto_scroll = html.Script("""
        setTimeout(function(){
            var el = document.getElementById('chat-messages-area');
            if (el) el.scrollTop = el.scrollHeight;
        }, 80);
    """)
    return bubbles + [auto_scroll], history, "", []