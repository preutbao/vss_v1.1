# src/callbacks/home_callbacks.py
import dash_bootstrap_components as dbc
from dash import Input, Output, State, dash_table, html, no_update, callback_context
import plotly.graph_objects as go

from src.app_instance import app
from src.backend.data_loader import load_market_data

# ============================================================================
# CẤU HÌNH TÊN CỘT DỮ LIỆU
# ============================================================================
COL_TICKER = "Ticker"
COL_DATE = "Date"
COL_CLOSE = "Price Close"   
COL_OPEN = "Price Open"
COL_HIGH = "Price High"
COL_LOW = "Price Low"
COL_VOLUME = "Volume"

# ============================================================================
# CALLBACK: CẬP NHẬT BIỂU ĐỒ VÀ BẢNG DỮ LIỆU (DASHBOARD CHÍNH)
# ============================================================================
@app.callback(
    [Output("stock-title", "children"),
     Output("price-chart", "figure"),
     Output("data-table-container", "children")],
    [Input("ticker-dropdown", "value")]
)
def update_dashboard(selected_ticker):
    # 1. Load và Lọc dữ liệu
    df = load_market_data()
    
    if selected_ticker is None:
        return "Chưa chọn mã", {}, ""

    # Lọc lấy đúng mã user chọn
    dff = df[df[COL_TICKER] == selected_ticker].copy()
    
    # Sắp xếp theo ngày tăng dần để vẽ cho đúng
    dff = dff.sort_values(by=COL_DATE)

    # 2. Vẽ biểu đồ Nến (Candlestick)
    fig = go.Figure(data=[go.Candlestick(
        x=dff[COL_DATE],
        open=dff[COL_OPEN],
        high=dff[COL_HIGH],
        low=dff[COL_LOW],
        close=dff[COL_CLOSE]
    )])

    fig.update_layout(
        title=f"Diễn biến giá {selected_ticker}",
        yaxis_title="Giá (IDR)",
        xaxis_rangeslider_visible=False, # Tắt thanh trượt dưới cho gọn
        template="plotly_white",
        margin=dict(l=0, r=0, t=30, b=0)
    )

    # 3. Tạo bảng dữ liệu (Hiển thị 10 ngày gần nhất)
    # Lấy 10 dòng cuối và đảo ngược để ngày mới nhất lên đầu
    df_table = dff.tail(10).sort_values(by=COL_DATE, ascending=False)
    
    # Format lại ngày tháng cho đẹp (chỉ lấy yyyy-mm-dd)
    df_table[COL_DATE] = df_table[COL_DATE].dt.strftime('%Y-%m-%d')

    table = dash_table.DataTable(
        data=df_table.to_dict('records'),
        columns=[{"name": i, "id": i} for i in df_table.columns],
        style_table={'overflowX': 'auto'},
        style_cell={'textAlign': 'left', 'padding': '10px'},
        style_header={'backgroundColor': '#1a252f', 'color': 'white', 'fontWeight': 'bold'},
        page_size=10
    )

    return f"Phân tích: {selected_ticker}", fig, table

# ============================================================================
# CALLBACK: TOUR GUIDE — 4 bước (Đã thêm Phân loại khách hàng)
# ============================================================================
@app.callback(
    Output("hint-modal", "is_open"),
    Output("hint-modal", "children"),       
    Output("hint-shown-store", "data"),     
    Output("tour-step-store", "data"),      
    Output("tour-selected-mode", "data"),   # <-- NEW: Lưu kết quả bài test
    Input("hint-modal-ok", "n_clicks"),     
    Input("hint-modal-close", "n_clicks"),  
    Input("hint-shown-store", "data"),      
    State("hint-modal", "is_open"),
    State("tour-step-store", "data"),
    State("tour-quiz-radio", "value"),      # <-- NEW: Đọc đáp án user chọn
    prevent_initial_call=False,
)
def manage_tour(ok_clicks, close_clicks, already_shown, is_open, current_step, quiz_value):
    ctx = callback_context
    triggered = ctx.triggered[0]["prop_id"] if ctx.triggered else ""

    # ── Tự động mở khi trang mới load ──
    if triggered == "hint-shown-store.data" or not triggered:
        if already_shown is True:
            return False, no_update, True, current_step, no_update 
        else:
            return True, _build_tour_step(1), False, 1, no_update

    # ── Bấm X → Đóng hẳn ──
    if "hint-modal-close" in triggered:
        return False, no_update, True, 1, no_update

    # ── Bấm Tiếp / Kết thúc ──
    if "hint-modal-ok" in triggered:
        step = current_step or 1
        
        if step == 3:
            # Từ bước 3 chuyển sang bước 4 (Bài test)
            return True, _build_tour_step(4), False, 4, no_update
            
        elif step >= 4:
            # Hoàn tất bài test -> Đóng form, đánh dấu đã xem, phát tín hiệu Mode
            selected_mode = quiz_value if quiz_value else "investing"
            return False, no_update, True, 1, selected_mode 
            
        # Các bước khác -> Sang bước tiếp theo
        next_step = step + 1
        return True, _build_tour_step(next_step), False, next_step, no_update

    return no_update, no_update, no_update, no_update, no_update


def _build_tour_step(step: int):
    """Tạo nội dung Modal theo từng bước tour."""

    # ── Style chung (Đã tối ưu lại chiều cao và chiều ngang) ──
    modal_style = {
        "backgroundColor": "#0d1117",
        "border": "1px solid #21262d",
        "borderRadius": "12px",
        "padding": "24px 40px 16px", # Giảm padding dọc, tăng padding ngang
    }
    
    _dot_active = {"width": "8px", "height": "8px", "borderRadius": "50%", "backgroundColor": "#00d4ff", "display": "inline-block", "margin": "0 3px"}
    _dot_inactive = {"width": "8px", "height": "8px", "borderRadius": "50%", "backgroundColor": "#30363d", "display": "inline-block", "margin": "0 3px"}

    def _dots(active):
        return html.Div([html.Span(style=_dot_active if i == active else _dot_inactive) for i in range(1, 5)], style={"textAlign": "center", "marginBottom": "15px"})

    def _close_btn():
        return html.Button("×", id="hint-modal-close", n_clicks=0, style={
            "position": "absolute", "top": "14px", "right": "18px", "background": "none", 
            "border": "none", "color": "#484f58", "fontSize": "22px", "cursor": "pointer", "zIndex": "10",
        })

    def _action_row(label, icon="fas fa-arrow-right", is_last=False):
        grad = "linear-gradient(135deg, #f59e0b, #f97316)" if is_last else "linear-gradient(135deg, #0090ff, #00d4ff)"
        text_col = "#1a0800" if is_last else "#001a20"
        return html.Div([
            dbc.Button([html.I(className=f"{icon} me-2"), label], id="hint-modal-ok", n_clicks=0,
                style={"background": grad, "border": "none", "borderRadius": "8px", "fontFamily": "'JetBrains Mono', monospace",
                       "fontSize": "13px", "fontWeight": "700", "color": text_col, "padding": "9px 35px"}
            ),
        ], style={"textAlign": "center", "marginTop": "15px"})

    # ════════════════════════════════════════════════════════════════════════
    # BƯỚC 1 – Chào mừng & tổng quan hệ thống
    # ════════════════════════════════════════════════════════════════════════
    if step == 1:
        content = dbc.ModalBody([
            html.Div(style={"position": "relative"}, children=[
                _close_btn(),
                # Pulse icon
                html.Div([
                    html.Div(style={
                        "width": "56px", "height": "56px", "borderRadius": "50%",
                        "background": "linear-gradient(135deg, #0090ff22, #00d4ff33)",
                        "border": "2px solid #00d4ff55",
                        "display": "flex", "alignItems": "center", "justifyContent": "center",
                        "margin": "0 auto 16px",
                        "animation": "pulse 2s infinite",
                    }, children=[
                        html.I(className="fas fa-chart-line",
                               style={"fontSize": "24px", "color": "#00d4ff"}),
                    ]),
                ]),
                # Badge
                html.Div("VIETCAP SMART SCREENER", style={
                    "fontFamily": "'JetBrains Mono', monospace",
                    "fontSize": "9px", "fontWeight": "700",
                    "color": "#00d4ff", "letterSpacing": "3px",
                    "textAlign": "center", "marginBottom": "8px",
                }),
                html.H5("Chào mừng bạn 👋", style={
                    "color": "#e6edf3", "fontWeight": "700",
                    "textAlign": "center", "marginBottom": "12px",
                    "fontFamily": "'Sora', sans-serif",
                }),
                html.P(
                    "Nền tảng sàng lọc cổ phiếu chuyên nghiệp với dữ liệu thực tế. "
                    "Hướng dẫn nhanh này sẽ giúp bạn khai thác tối đa công cụ trong 30 giây.",
                    style={"fontSize": "13px", "color": "#8b949e",
                           "lineHeight": "1.7", "textAlign": "center", "marginBottom": "20px",
                           "fontFamily": "'Sora', sans-serif"},
                ),
                html.Hr(style={"borderColor": "#21262d", "margin": "0 0 16px"}),
                # Feature list
                *[html.Div([
                    html.Div(style={
                        "width": "32px", "height": "32px", "borderRadius": "8px",
                        "backgroundColor": bg, "flexShrink": "0",
                        "display": "flex", "alignItems": "center", "justifyContent": "center",
                    }, children=[html.I(className=icon, style={"fontSize": "14px", "color": ic})]),
                    html.Div([
                        html.Div(title, style={"fontSize": "12px", "fontWeight": "700",
                                               "color": "#c9d1d9", "fontFamily": "'Sora', sans-serif"}),
                        html.Div(desc, style={"fontSize": "11px", "color": "#6e7681",
                                              "fontFamily": "'Sora', sans-serif"}),
                    ], style={"marginLeft": "12px"}),
                ], style={"display": "flex", "alignItems": "center", "marginBottom": "12px"})
                  for icon, bg, ic, title, desc in [
                    ("fas fa-filter", "#0d1f2d", "#58a6ff",
                     "Bộ lọc thông minh", "50+ chỉ tiêu tài chính & kỹ thuật"),
                    ("fas fa-chess-queen", "#0d2215", "#3fb950",
                     "9 trường phái đầu tư", "Graham, Lynch, Fisher, Value..."),
                    ("fas fa-file-pdf", "#2d1515", "#f85149",
                     "Xuất báo cáo PDF", "Hồ sơ phân tích từng mã cổ phiếu"),
                ]],
                _dots(1),
                _action_row("Tiếp theo →"),
            ]),
        ], style=modal_style)

    # ════════════════════════════════════════════════════════════════════════
    # BƯỚC 2 – Hướng dẫn sử dụng bộ lọc
    # ════════════════════════════════════════════════════════════════════════
    elif step == 2:
        content = dbc.ModalBody([
            html.Div(style={"position": "relative"}, children=[
                _close_btn(),
                html.Div([
                    html.Div(style={
                        "width": "56px", "height": "56px", "borderRadius": "50%",
                        "background": "linear-gradient(135deg, #3fb95022, #3fb95044)",
                        "border": "2px solid #3fb95066",
                        "display": "flex", "alignItems": "center", "justifyContent": "center",
                        "margin": "0 auto 16px",
                    }, children=[
                        html.I(className="fas fa-sliders",
                               style={"fontSize": "24px", "color": "#3fb950"}),
                    ]),
                ]),
                html.Div("CÁCH SỬ DỤNG", style={
                    "fontFamily": "'JetBrains Mono', monospace",
                    "fontSize": "9px", "fontWeight": "700",
                    "color": "#3fb950", "letterSpacing": "3px",
                    "textAlign": "center", "marginBottom": "8px",
                }),
                html.H5("3 bước để tìm cổ phiếu", style={
                    "color": "#e6edf3", "fontWeight": "700",
                    "textAlign": "center", "marginBottom": "20px",
                    "fontFamily": "'Sora', sans-serif",
                }),
                # Steps
                *[html.Div([
                    html.Div(str(n), style={
                        "width": "28px", "height": "28px", "borderRadius": "50%",
                        "background": grad, "color": "#001a20",
                        "fontWeight": "800", "fontSize": "13px",
                        "display": "flex", "alignItems": "center",
                        "justifyContent": "center", "flexShrink": "0",
                    }),
                    html.Div([
                        html.Div(title, style={"fontSize": "13px", "fontWeight": "700",
                                               "color": "#c9d1d9", "fontFamily": "'Sora', sans-serif"}),
                        html.Div(desc, style={"fontSize": "11px", "color": "#6e7681",
                                              "lineHeight": "1.5", "fontFamily": "'Sora', sans-serif"}),
                    ], style={"marginLeft": "14px"}),
                ], style={
                    "display": "flex", "alignItems": "flex-start",
                    "padding": "12px 14px", "borderRadius": "8px",
                    "backgroundColor": bg, "marginBottom": "10px",
                    "border": f"1px solid {border}",
                })
                  for n, grad, bg, border, title, desc in [
                    (1, "linear-gradient(135deg,#0090ff,#00d4ff)",
                     "#0a1929", "#0090ff33",
                     "Chọn Trường phái",
                     "Mở dropdown 'Trường phái' → chọn phong cách phù hợp. "
                     "Các thẻ chỉ tiêu 'Tham khảo' sẽ hiện ngay."),
                    (2, "linear-gradient(135deg,#3fb950,#00d4ff)",
                     "#0a1f15", "#3fb95033",
                     "Tinh chỉnh bộ lọc",
                     "Kéo thanh trượt hoặc gõ trực tiếp vào ô số để điều chỉnh ngưỡng theo ý muốn."),
                    (3, "linear-gradient(135deg,#f0883e,#f59e0b)",
                     "#1f1200", "#f59e0b33",
                     "Xem & xuất báo cáo",
                     "Double-click vào mã bất kỳ → hồ sơ chi tiết. "
                     "Bấm PDF để xuất báo cáo chuyên nghiệp."),
                ]],
                _dots(2),
                _action_row("Tiếp theo →"),
            ]),
        ], style={
            "backgroundColor": "#0d1117",
            "border": "1px solid #21262d",
            "borderRadius": "12px",
            "padding": "28px 24px 20px",
        })

    # ════════════════════════════════════════════════════════════════════════
    # BƯỚC 3 – CTA: Khẩu vị phòng thủ NCN K16
    # ════════════════════════════════════════════════════════════════════════
    elif step == 3:
        content = dbc.ModalBody([
            html.Div(style={"position": "relative"}, children=[
                _close_btn(),
                # Gradient header banner
                html.Div(style={
                    "background": "linear-gradient(135deg, #1a0f00, #2d1f00)",
                    "border": "1px solid #f59e0b33",
                    "borderRadius": "10px",
                    "padding": "16px",
                    "marginBottom": "16px",
                    "textAlign": "center",
                }, children=[
                    html.Div([
                        html.I(className="fas fa-shield-halved",
                               style={"fontSize": "28px", "color": "#f59e0b",
                                      "filter": "drop-shadow(0 0 8px rgba(245,158,11,0.5))"}),
                    ], style={"marginBottom": "10px"}),
                    html.Div("TRƯỜNG PHÁI MỚI", style={
                        "fontFamily": "'JetBrains Mono', monospace",
                        "fontSize": "9px", "fontWeight": "700",
                        "color": "#f59e0b", "letterSpacing": "3px",
                        "marginBottom": "6px",
                    }),
                    html.H5("Khẩu Vị Phòng Thủ", style={
                        "color": "#e6edf3", "fontWeight": "800",
                        "fontFamily": "'Sora', sans-serif",
                        "marginBottom": "4px", "fontSize": "18px",
                    }),
                    html.Div("Team Chuyên viên Tư vấn Đầu tư Vietcap", style={
                        "fontSize": "11px", "color": "#a37020",
                        "fontFamily": "'Sora', sans-serif",
                    }),
                ]),
                # Pitch
                html.P([
                    "Một bộ lọc được xây dựng từ ",
                    html.Strong("framework đầu tư cá nhân", style={"color": "#f59e0b"}),
                    " của chuyên viên, lượng hóa thành 3 tầng chặt chẽ:",
                ], style={"fontSize": "13px", "color": "#8b949e", "lineHeight": "1.6",
                           "fontFamily": "'Sora', sans-serif", "marginBottom": "12px"}),
                # 3 tầng mini
                *[html.Div([
                    html.I(className=icon, style={"color": ic, "marginRight": "8px",
                                                   "fontSize": "12px", "flexShrink": "0"}),
                    html.Span(txt, style={"fontSize": "12px", "color": "#c9d1d9",
                                         "fontFamily": "'Sora', sans-serif"}),
                ], style={"display": "flex", "alignItems": "center",
                           "marginBottom": "8px", "padding": "8px 12px",
                           "backgroundColor": bg, "borderRadius": "6px",
                           "border": f"1px solid {border}"})
                  for icon, ic, bg, border, txt in [
                    ("fas fa-ban", "#f85149", "#1c1010", "#f8514922",
                     "Tầng 1 · Loại ngay Red Flag: CFO/NI < 0.8, pha loãng > 8%/năm"),
                    ("fas fa-coins", "#3fb950", "#0a1f15", "#3fb95022",
                     "Tầng 2 · Chất lượng: FCF dương, ROIC ≥ 12%, D/E ≤ 1.5"),
                    ("fas fa-trophy", "#f59e0b", "#1f1200", "#f59e0b22",
                     "Tầng 3 · Rank tổng hợp → Top 40 mã ROIC + Moat tốt nhất"),
                ]],
                # CTA hint
                html.Div([
                    html.I(className="fas fa-hand-pointer",
                           style={"color": "#f59e0b", "marginRight": "8px", "fontSize": "13px"}),
                    html.Span("Thử ngay: Dropdown 'Trường phái' → ",
                              style={"fontSize": "12px", "color": "#8b949e"}),
                    html.Strong("🛡️ Khẩu Vị Phòng Thủ",
                                style={"fontSize": "12px", "color": "#f59e0b"}),
                ], style={
                    "display": "flex", "alignItems": "center",
                    "backgroundColor": "#1c1a10",
                    "border": "1px solid #f59e0b44",
                    "borderRadius": "8px", "padding": "10px 14px",
                    "marginTop": "14px", "marginBottom": "4px",
                }),
                _dots(3),
                _action_row("Bắt đầu khám phá!", "fas fa-rocket", is_last=True),
            ]),
        ], style={
            "backgroundColor": "#0d1117",
            "border": "1px solid #21262d",
            "borderRadius": "12px",
            "padding": "28px 24px 20px",
        })

    # ════════════════════════════════════════════════════════════════════════
    # BƯỚC 4 (NEW) – BÀI TEST ĐỊNH VỊ KHÁCH HÀNG
    # ════════════════════════════════════════════════════════════════════════
    else:
        content = dbc.ModalBody([
            html.Div(style={"position": "relative"}, children=[
                _close_btn(),
                html.H5("Định hình Khẩu vị Đầu tư", style={
                    "color": "#e6edf3", "fontWeight": "700", "textAlign": "center", 
                    "marginBottom": "8px", "fontFamily": "'Sora', sans-serif"
                }),
                html.P("Hệ thống sẽ tự động tối ưu giao diện dựa trên câu trả lời của bạn:", 
                       style={"fontSize": "13px", "color": "#8b949e", "textAlign": "center", "marginBottom": "24px"}),
                
                # Bộ câu hỏi trắc nghiệm
                html.Div([
                    dbc.RadioItems(
                        id="tour-quiz-radio",
                        options=[
                            {"label": html.Div(["📊 Chế độ Tích sản", html.Div("Tôi ít thời gian bám bảng, ưu tiên mua giữ trung & dài hạn, an toàn dòng tiền.", style={"fontSize":"11px", "color":"#8b949e", "marginTop":"4px"})], style={"marginLeft": "10px", "marginBottom": "6px"}), "value": "investing"},
                            {"label": html.Div(["⚡ Chế độ Lướt sóng", html.Div("Tôi thường xuyên xem bảng điện, thích đánh T+, tìm điểm Breakout.", style={"fontSize":"11px", "color":"#8b949e", "marginTop":"4px"})], style={"marginLeft": "10px", "marginBottom": "6px"}), "value": "trading"},
                            {"label": html.Div(["🌐 Toàn thị trường", html.Div("Tôi là dân chuyên, muốn xem toàn bộ 1.500 mã không qua bộ lọc.", style={"fontSize":"11px", "color":"#8b949e", "marginTop":"4px"})], style={"marginLeft": "10px"}), "value": "all_market"},
                        ],
                        value="investing", # Mặc định an toàn
                        style={"display": "flex", "flexDirection": "column", "gap": "18px"}
                    )
                ], style={"backgroundColor": "#010409", "padding": "20px", "borderRadius": "8px", "border": "1px solid #30363d"}),
                
                _dots(4),
                _action_row("Hoàn tất & Bắt đầu", "fas fa-rocket", is_last=True),
            ]),
        ], style=modal_style)


    return content

from dash import Input, Output, State, no_update

@app.callback(
    Output("zalo-chat-window",     "style"),
    Output("zalo-bubble-container","style"),
    Input("zalo-icon-btn",    "n_clicks"),
    Input("zalo-chat-close",  "n_clicks"),
    Input("zalo-bubble-close","n_clicks"),
    State("zalo-chat-window",      "style"),
    State("zalo-bubble-container", "style"),
    prevent_initial_call=True,
)
def toggle_zalo(icon_clicks, chat_close, bubble_close, chat_style, bubble_style):
    from dash import callback_context
    triggered = callback_context.triggered[0]["prop_id"]

    base_bubble = {
        "position": "fixed", "bottom": "28px", "right": "28px",
        "zIndex": "10000", "display": "flex", "flexDirection": "column",
        "alignItems": "center",
    }
    base_chat_shown = {
        "display": "block", "position": "fixed", "bottom": "96px", "right": "28px",
        "width": "320px", "border": "1px solid #30363d", "borderRadius": "12px",
        "boxShadow": "0 8px 32px rgba(0,0,0,0.6)", "zIndex": "9999",
        "fontFamily": "'Sora', sans-serif",
    }
    base_chat_hidden = {**base_chat_shown, "display": "none"}

    if "zalo-bubble-close" in triggered:
        return no_update, {**base_bubble, "display": "none"}   # ẩn bubble
    if "zalo-icon-btn" in triggered:
        return base_chat_shown, base_bubble                     # mở chat
    if "zalo-chat-close" in triggered:
        return base_chat_hidden, base_bubble                    # đóng chat
    return no_update, no_update