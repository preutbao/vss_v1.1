# src/callbacks/home_callbacks.py
import dash_bootstrap_components as dbc
from dash import Input, Output, State, dash_table, html, no_update, callback_context
import plotly.graph_objects as go

from src.app_instance import app
from src.backend.data_loader import load_market_data, load_index_data, get_snapshot_df, get_company_name_vi
from src.components.header import _pick_card  # tái dùng đúng markup/CSS class đã dựng ở Bước 3
import pandas as pd

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
import plotly.graph_objects as go
from dash import no_update

@app.callback(
    [Output("stock-title", "children"),
     Output("price-chart", "figure"),
     Output("data-table-container", "children")],
    [Input("ticker-dropdown", "value")]
)
def update_dashboard(selected_ticker):
    # 🌟 THUỐC GIẢI: Tạo một biểu đồ tàng hình, tắt luôn trục X, Y để Plotly không bao giờ bị lỗi scale
    empty_fig = go.Figure(layout=dict(
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=0, r=0, t=0, b=0)
    ))

    # 1. BẮT LỖI KHI CHƯA CHỌN MÃ
    if not selected_ticker:
        # Thay vì no_update, truyền thẳng empty_fig vào để đè bẹp lỗi
        return "Chưa chọn mã", empty_fig, no_update

    df = load_market_data()
    
    # 2. BẮT LỖI KHI DATA TỔNG BỊ RỖNG
    if df is None or df.empty:
        return "Dữ liệu đang cập nhật...", empty_fig, no_update

    dff = df[df[COL_TICKER] == selected_ticker].copy()
    
    # 3. BẮT LỖI KHI MÃ CỔ PHIẾU NÀY KHÔNG CÓ DATA (HOẶC CHỈ CÓ 1 NGÀY)
    if dff.empty or len(dff) < 2:
        return f"Không đủ dữ liệu vẽ nến cho {selected_ticker}", empty_fig, no_update
        
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
        yaxis_title="Giá (VND)",
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
# ============================================================================
# CALLBACK 1: ĐIỀU PHỐI CÁC BƯỚC CỦA TOUR GUIDE
# ============================================================================
@app.callback(
    # Output("hint-modal", "is_open"), # tat modal khi bấm X hoặc hoàn tất
    Output("hint-modal", "children"),       
    Output("hint-shown-store", "data"),     
    Output("tour-step-store", "data"),      
    # BỎ Output của tour-selected-mode ở đây
    Input("hint-modal-ok", "n_clicks"),     
    Input("hint-modal-close", "n_clicks"),  
    Input("hint-shown-store", "data"),      
    State("hint-modal", "is_open"),
    State("tour-step-store", "data"),
    # BỎ State của tour-quiz-radio ở đây để tránh lỗi DOM
    prevent_initial_call=False,
)
def manage_tour(ok_clicks, close_clicks, already_shown, is_open, current_step):
    ctx = callback_context
    triggered = ctx.triggered[0]["prop_id"] if ctx.triggered else ""

    # ── Tự động mở khi trang mới load ──
    if triggered == "hint-shown-store.data" or not triggered:
        if already_shown is True:
            # return False, no_update, True, current_step 
            return no_update, True, current_step 
        else:
            # Nếu trước đây là:
            # return True, _build_tour_step(1), False, 1

            # Sửa lại thành 3 giá trị (Ví dụ loại bỏ giá trị True ban đầu vốn dành cho 'is_open'):
            return _build_tour_step(1), False, 1

    # ── Bấm X → Đóng hẳn ──
    if "hint-modal-close" in triggered:
        return False, no_update, True, 1

    # ── Bấm Tiếp / Kết thúc ──
    if "hint-modal-ok" in triggered:
        step = current_step or 1
        
        if step == 3:
            return True, _build_tour_step(4), False, 4
            
        elif step >= 4:
            # Hoàn tất -> Chỉ đóng modal và lưu trạng thái đã xem
            return False, no_update, True, 1 
            
        next_step = step + 1
        return True, _build_tour_step(next_step), False, next_step

    return no_update, no_update, no_update, no_update

# ============================================================================
# CALLBACK 2: LẮNG NGHE BÀI QUIZ (Không gây lỗi)
# ============================================================================
@app.callback(
    Output("tour-selected-mode", "data"),
    Input("tour-quiz-radio", "value"),
    prevent_initial_call=True
)
def update_mode_from_quiz(quiz_val):
    if quiz_val:
        return quiz_val
    return no_update

def _build_tour_step(step: int):
    """Tạo nội dung Modal theo từng bước tour."""

    # ── Style chung (Đã tối ưu lại chiều cao và chiều ngang) ──
    modal_style = {
        "backgroundColor": "#0d1117",
        "border": "1px solid #21262d",
        "borderRadius": "12px",
        "padding": "24px 40px 16px", # Giảm padding dọc, tăng padding ngang
    }
    
    _dot_active = {"width": "8px", "height": "8px", "borderRadius": "50%", "backgroundColor": "#1E88E5", "display": "inline-block", "margin": "0 3px"}
    _dot_inactive = {"width": "8px", "height": "8px", "borderRadius": "50%", "backgroundColor": "#30363d", "display": "inline-block", "margin": "0 3px"}

    def _dots(active):
        return html.Div([html.Span(style=_dot_active if i == active else _dot_inactive) for i in range(1, 5)], style={"textAlign": "center", "marginBottom": "15px"})

    def _close_btn():
        return html.Button("×", id="hint-modal-close", n_clicks=0, style={
            "position": "absolute", "top": "14px", "right": "18px", "background": "none", 
            "border": "none", "color": "#484f58", "fontSize": "22px", "cursor": "pointer", "zIndex": "10",
        })

    def _action_row(label, icon="fas fa-arrow-right", is_last=False):
        grad = "linear-gradient(135deg, #f59e0b, #f97316)" if is_last else "linear-gradient(135deg, #0057D9, #1E88E5)"
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
                        "background": "linear-gradient(135deg, #0057D922, #1E88E533)",
                        "border": "2px solid #1E88E555",
                        "display": "flex", "alignItems": "center", "justifyContent": "center",
                        "margin": "0 auto 16px",
                        "animation": "pulse 2s infinite",
                    }, children=[
                        html.I(className="fas fa-chart-line",
                               style={"fontSize": "24px", "color": "#1E88E5"}),
                    ]),
                ]),
                # Badge
                html.Div("FINSMARTSCREENER", style={
                    "fontFamily": "'JetBrains Mono', monospace",
                    "fontSize": "9px", "fontWeight": "700",
                    "color": "#1E88E5", "letterSpacing": "3px",
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
                    (1, "linear-gradient(135deg,#0057D9,#1E88E5)",
                     "#0a1929", "#0057D933",
                     "Chọn Trường phái",
                     "Mở dropdown 'Trường phái' → chọn phong cách phù hợp. "
                     "Các thẻ chỉ tiêu 'Tham khảo' sẽ hiện ngay."),
                    (2, "linear-gradient(135deg,#3fb950,#1E88E5)",
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
                _action_row("Bắt đầu khám phá khẩu vị đầu tư của bạn!", "fas fa-rocket", is_last=True),
            ]),
        ], style={
            "backgroundColor": "#0d1117",
            "border": "1px solid #21262d",
            "borderRadius": "12px",
            "padding": "28px 24px 20px",
        })
    # ════════════════════════════════════════════════════════════════════════
    # BƯỚC 4 (FINAL UI UPGRADE) – ĐỊNH VỊ KHẨU VỊ (PERSONA CARDS)
    # ════════════════════════════════════════════════════════════════════════
    else:
        # Style riêng cho các thẻ Persona
        card_style = {
            "padding": "20px", 
            "borderRadius": "10px", 
            "border": "1px solid #30363d", 
            "backgroundColor": "#161b22", 
            "cursor": "pointer",
            "transition": "all 0.2s ease-in-out",
            "display": "flex",
            "alignItems": "flex-start",
            "gap": "15px",
            "marginBottom": "16px",
        }

        # Helper function để tạo label chất lượng cao cho RadioItem
        def _build_persona_label(icon, title, subtitle, color):
            return html.Div([
                # Dòng tiêu đề + màu nhấn mạnh
                html.Div([
                    html.Span(icon, style={"marginRight": "10px", "fontSize": "16px"}),
                    html.Span(title, style={"fontWeight": "700", "fontSize": "14px", "color": color}),
                ], style={"marginBottom": "6px", "display": "flex", "alignItems": "center"}),
                # Mô tả chi tiết
                html.P(subtitle, style={
                    "fontSize": "12.5px", "color": "#8b949e", "margin": "0", 
                    "lineHeight": "1.6", "fontWeight": "400"
                }),
            ], style={"flex": "1"})

        content = dbc.ModalBody([
            html.Div(style={"position": "relative"}, children=[
                _close_btn(),
                
                # SECTION 1: HEADER & AVATAR (Sinh động hơn)
                html.Div([
                    # Hình Avatar Trader (đổi màu border theo mode để sinh động)
                    html.Img(src="https://cdn-icons-png.flaticon.com/512/7564/7564870.png", style={
                        "height": "65px", "borderRadius": "50%", 
                        "border": "2px solid #30363d", "backgroundColor": "#0d1117", 
                        "padding": "5px", "boxShadow": "0 4px 15px rgba(0,0,0,0.3)"
                    }),
                    html.Div([
                        html.H5("Định hình Khẩu vị Đầu tư", style={
                            "color": "#e6edf3", "fontWeight": "800", "margin": "0", 
                            "fontFamily": "'Sora', sans-serif", "letterSpacing": "-0.5px"
                        }),
                        html.P("Hệ thống FinSmartScreener sẽ tự động tối ưu giao diện phù hợp nhất với bạn:", style={
                            "fontSize": "13px", "color": "#8b949e", "margin": "4px 0 0"
                        }),
                    ], style={"flex": "1"})
                ], style={"display": "flex", "alignItems": "center", "gap": "20px", "marginBottom": "28px"}),
                
                # SECTION 2: BỘ CÂU HỎI PERSONA CARDS (Lõi thiết kế mới)
                html.Div([
                    dbc.RadioItems(
                        id="tour-quiz-radio",
                        options=[
                            # Thẻ 1: Toàn thị trường (chuyển lên đầu)
                            {"label": _build_persona_label(
                                "🌐", "Toàn thị trường — Tầng 1: Chuyên gia & Tự do",
                                "Broker, Data Analyst, nhà đầu tư chuyên nghiệp muốn quét thô toàn bộ ~1.500 mã để tự build chiến lược riêng.",
                                "#a5a7a9"
                            ), "value": "all_market"},

                            # Thẻ 2: Lướt sóng
                            {"label": _build_persona_label(
                                "⚡", "Lướt sóng T+ — Tầng 2: Năng động & Dòng tiền",
                                "Canh bảng điện thường xuyên, thích cảm giác mạnh, tìm điểm nổ Volume, Breakout SMA20.",
                                "#f59e0b"
                            ), "value": "trading"},

                            # Thẻ 3: Tích sản (chuyển xuống cuối)
                            {"label": _build_persona_label(
                                "📊", "Tích sản — Tầng 3: Bền vững & An toàn",
                                "NĐT bận rộn, Buy & Hold trung-dài hạn. Ưu tiên DN cơ bản tốt, nợ thấp, cổ tức đều.",
                                "#10b981"
                            ), "value": "investing"},
                        ],
                        value="investing",  # Đổi default thành investing để phù hợp với hướng dẫn
                        style={"display": "flex", "flexDirection": "column", "gap": "16px"},
                        labelClassName="persona-card-label",
                        inputClassName="persona-card-input",
                    )
                ], style={"marginBottom": "30px"}),
                
                _dots(4),
                _action_row("Hoàn tất & Bắt đầu", "fas fa-rocket", is_last=True),
            ]),
        ], style=modal_style)

    return content
from dash import Input, Output, State, no_update

@app.callback(
    Output("zalo-chat-window",     "style"),
    Output("zalo-bubble-container","style"),
    Output("chat-panel",           "style", allow_duplicate=True),  # THÊM
    Input("zalo-icon-btn",    "n_clicks"),
    Input("zalo-chat-close",  "n_clicks"),
    Input("zalo-bubble-close","n_clicks"),
    State("zalo-chat-window",      "style"),
    State("zalo-bubble-container", "style"),
    State("chat-panel",            "style"),  # THÊM
    prevent_initial_call=True,
)
def toggle_zalo(icon_clicks, chat_close, bubble_close, chat_style, bubble_style, vinance_style):
    triggered = callback_context.triggered[0]["prop_id"]
    
    # Style đóng cho VinanceAI
    vinance_closed = {**vinance_style, 
                      "transform": "scale(0.85) translateY(20px)",
                      "opacity": "0", "pointerEvents": "none"}

    base_bubble = {
        "position": "fixed", "bottom": "96px", "right": "28px",
        "zIndex": "10000", "display": "flex", "flexDirection": "column",
        "alignItems": "center",
    }
    base_chat_shown = {
        "display": "block", "position": "fixed",
        "bottom": "164px", "right": "28px",
        "width": "380px",
        "border": "1px solid #30363d", "borderRadius": "12px",
        "boxShadow": "0 8px 32px rgba(0,0,0,0.6)", "zIndex": "9999",
        "fontFamily": "'Sora', sans-serif",
    }
    base_chat_hidden = {**base_chat_shown, "display": "none"}

    if "zalo-bubble-close" in triggered:
        return no_update, {**base_bubble, "display": "none"}, no_update
    if "zalo-icon-btn" in triggered:
        # Mở zalo → đóng vinance
        return base_chat_shown, base_bubble, vinance_closed
    if "zalo-chat-close" in triggered:
        return base_chat_hidden, base_bubble, no_update
    return no_update, no_update, no_update

import plotly.graph_objects as go
from dash import Input, Output, callback, no_update
import pandas as pd
import numpy as np

def create_mini_chart(y_data, color="#10b981", is_bar=False):
    """Vẽ sparkline (line) hoặc bar chart mini, nền trong suốt."""
    
    # 🔴 BƯỚC FIX LỖI 1: Bọc xử lý data an toàn
    # Đảm bảo có ít nhất 2 điểm. Nếu mảng trống hoặc < 2 phần tử, chèn thêm điểm giả bằng 0
    safe_y = list(y_data) if y_data is not None else []
    if len(safe_y) < 2:
        safe_y = [0, 0]
        
    # 🔴 BƯỚC FIX LỖI 2: Xử lý trục Y bằng phẳng (min = max)
    # Plotly bị lỗi "axis scaling" nếu tất cả các điểm có giá trị y bằng nhau.
    min_v, max_v = min(safe_y), max(safe_y)
    y_range_kwargs = {}
    if min_v == max_v:
        # Nếu đường thẳng băng, ép buộc range trục Y dao động +/- 1% quanh giá trị đó (hoặc [0, 1] nếu = 0)
        padding = abs(min_v) * 0.01 if min_v != 0 else 1
        y_range_kwargs = {"range": [min_v - padding, max_v + padding]}

    fig = go.Figure()
    if is_bar:
        fig.add_trace(go.Bar(y=safe_y, marker_color=color, hoverinfo='skip'))
    else:
        fig.add_trace(go.Scatter(y=safe_y, mode='lines', line=dict(color=color, width=2), hoverinfo='skip'))
    
    fig.update_layout(
        margin=dict(l=0, r=0, t=0, b=0),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        showlegend=False,
        xaxis=dict(visible=False, fixedrange=True),
        # 🔴 BƯỚC FIX LỖI 3: Truyền range an toàn vào trục Y nếu bị bằng phẳng
        yaxis=dict(visible=False, fixedrange=True, **y_range_kwargs)
    )
    return fig

@app.callback(
    # --- VN-INDEX ---
    Output('home-mkt-vnindex-value', 'children'),
    Output('home-mkt-vnindex-badge', 'children'),
    Output('home-mkt-vnindex-badge', 'className'),
    Output('home-mkt-vnindex-pts', 'children'),
    Output('home-mkt-vnindex-pts', 'className'),
    Output('home-mkt-vnindex-spark', 'figure'),
    
    Output('home-mkt-hnxindex-value', 'children'),
    Output('home-mkt-hnxindex-badge', 'children'),
    Output('home-mkt-hnxindex-badge', 'className'),
    Output('home-mkt-hnxindex-pts', 'children'),
    Output('home-mkt-hnxindex-pts', 'className'),
    Output('home-mkt-hnxindex-spark', 'figure'),
    
    # --- VN30-INDEX ---
    Output('home-mkt-vn30index-value', 'children'),
    Output('home-mkt-vn30index-badge', 'children'),
    Output('home-mkt-vn30index-badge', 'className'),
    Output('home-mkt-vn30index-pts', 'children'),
    Output('home-mkt-vn30index-pts', 'className'),
    Output('home-mkt-vn30index-spark', 'figure'),
    
    # --- TOTAL VOLUME ---
    Output('home-mkt-volume-value', 'children'),
    Output('home-mkt-volume-badge', 'children'),
    Output('home-mkt-volume-spark', 'figure'),
    
    # Dùng id của tiêu đề hero để kích hoạt khi trang load xong
    Input('home-hero', 'children'),
    Input('header-realtime-interval', 'n_intervals'),
    prevent_initial_call=False
)
def update_market_overview_cards(pathname, n_intervals):
    # ==========================================
    # 1. HELPER — format số + màu tăng/giảm, dùng chung cho 3 thẻ index
    # ==========================================
    def format_index_data(current_val, change_pct, change_pts, chart_data):
        is_up = change_pct >= 0
        color_class = "home-market-badge is-positive" if is_up else "home-market-badge is-negative"
        chart_color = "#10b981" if is_up else "#ef4444"

        val_str = f"{current_val:,.2f}"
        badge_str = f"{'+' if is_up else ''}{change_pct:.2f}%"
        pts_str = f"{'▲ ' if is_up else '▼ '} {abs(change_pts):.2f} điểm"

        fig = create_mini_chart(chart_data, color=chart_color, is_bar=False)
        return val_str, badge_str, color_class, pts_str, color_class, fig

    def _index_series(df, col, n=30, symbol_key=None):
        if df is None or df.empty or col not in df.columns:
            return 0.0, 0.0, 0.0, [0.0, 0.0]
        d = df.dropna(subset=[col]).sort_values("Date")
        if d.empty:
            return 0.0, 0.0, 0.0, [0.0, 0.0]

        last_val = float(d[col].iloc[-1])
        prev_val = float(d[col].iloc[-2]) if len(d) >= 2 else last_val
        pts = last_val - prev_val
        pct = (pts / prev_val * 100) if prev_val else 0.0
        spark = d[col].tail(n).tolist()

        # ── Ưu tiên realtime nếu có (giống logic bảng lọc dùng get_realtime_snapshot) ──
        if symbol_key:
            try:
                from src.backend.wifeed_updater import get_realtime_index
                rt = get_realtime_index().get(symbol_key)
                if rt and rt.get("close") is not None:
                    rt_close = float(rt["close"])
                    rt_pct = float(rt.get("change_pct", pct) or 0)
                    rt_pts = rt_close - prev_val if prev_val else pts

                    last_val = rt_close
                    pct = rt_pct
                    pts = rt_pts
                    if spark:
                        spark[-1] = rt_close  # cập nhật điểm cuối sparkline theo giá live
                    else:
                        spark = [rt_close, rt_close]
            except Exception:
                pass

        if len(spark) < 2:
            spark = [last_val, last_val]

        return last_val, pts, pct, spark

    # ==========================================
    # 2. VN-INDEX & VN30-INDEX
    # ==========================================
    try:
        df_idx = load_index_data()
    except Exception:
        df_idx = pd.DataFrame()

    vn_current, vn_pts_raw, vn_pct, vn_spark = _index_series(df_idx, "VNINDEX_Close", symbol_key="VNINDEX")

    vn_val, vn_badge, vn_badge_cls, vn_pts, vn_pts_cls, vn_fig = format_index_data(
        current_val=vn_current, change_pct=vn_pct, change_pts=vn_pts_raw, chart_data=vn_spark
    )

    vn30_current, vn30_pts_raw, vn30_pct, vn30_spark = _index_series(df_idx, "VN30_Close", symbol_key="VN30")

    vn30_val, vn30_badge, vn30_badge_cls, vn30_pts, vn30_pts_cls, vn30_fig = format_index_data(
        current_val=vn30_current, change_pct=vn30_pct, change_pts=vn30_pts_raw, chart_data=vn30_spark
    )

    # 3. HNX-INDEX
    hnx_current, hnx_pts_raw, hnx_pct, hnx_spark = _index_series(df_idx, "HNXINDEX_Close", symbol_key="HNXINDEX")
    if hnx_current == 0.0:
        HNX_MOCK_SERIES = [241.10, 239.85, 238.40, 237.90, 236.55, 238.20, 239.00,
                           237.65, 236.10, 234.80, 233.95, 232.40, 231.85, 230.60,
                           229.75, 231.20, 232.85, 234.10, 235.95, 237.40, 236.80,
                           235.20, 233.75, 232.90, 234.15, 235.60, 236.85, 235.40,
                           234.60, 235.80]
        hnx_current = HNX_MOCK_SERIES[-1]
        hnx_pts_raw = hnx_current - HNX_MOCK_SERIES[-2]
        hnx_pct     = (hnx_pts_raw / HNX_MOCK_SERIES[-2] * 100) if HNX_MOCK_SERIES[-2] else 0.0
        hnx_spark   = HNX_MOCK_SERIES

    hnx_val, hnx_badge, hnx_badge_cls, hnx_pts, hnx_pts_cls, hnx_fig = format_index_data(
        current_val=hnx_current, change_pct=hnx_pct, change_pts=hnx_pts_raw, chart_data=hnx_spark
    )

    # ==========================================
    # 4. TỔNG GIÁ TRỊ GIAO DỊCH (Turnover)
    # ==========================================
    try:
        df_mkt = load_market_data()
    except Exception:
        df_mkt = pd.DataFrame()

    if df_mkt is not None and not df_mkt.empty and COL_DATE in df_mkt.columns:
        d = df_mkt.copy()
        if "Turnover" not in d.columns:
            d["Turnover"] = pd.to_numeric(d.get(COL_VOLUME, 0), errors="coerce") * \
                             pd.to_numeric(d.get(COL_CLOSE, 0), errors="coerce")
        daily_turnover = (
            d.dropna(subset=[COL_DATE])
             .groupby(COL_DATE)["Turnover"]
             .sum()
             .sort_index()
        )
    else:
        daily_turnover = pd.Series(dtype="float64")

    # ── [MỚI] Patch LIVE — cộng "Turnover" (giatri_giaodich) từ TOÀN BỘ
    # snapshot realtime Wifeed, chính xác hơn cách ước lượng Volume*Close cũ
    # (Wifeed đã tính sẵn giá trị giao dịch thật cho từng mã). Nếu chưa có
    # snapshot (chưa fetch lần nào / ngoài giờ), giữ nguyên số EOD như cũ.
    live_turnover = None
    live_volume_shares = None   # ← THÊM: tổng khối lượng (cổ phiếu) live
    try:
        from src.backend.wifeed_updater import get_realtime_snapshot
        rt_snapshot = get_realtime_snapshot()
        if rt_snapshot:
            live_turnover = sum(float(rt.get("Turnover") or 0) for rt in rt_snapshot.values())
            live_volume_shares = sum(float(rt.get("Volume") or 0) for rt in rt_snapshot.values())
    except Exception:
        live_turnover = None
        live_volume_shares = None

    # Xác định hôm nay (giờ VN) đã có trong daily_turnover (đã EOD merge) hay
    # chưa — quyết định GHI ĐÈ bar cuối hay THÊM bar mới cho đúng ngày.
    today_vn_str = None
    if live_turnover is not None:
        try:
            import pytz
            from datetime import datetime as _dt
            today_vn_str = _dt.now(pytz.timezone("Asia/Ho_Chi_Minh")).strftime("%Y-%m-%d")
        except Exception:
            today_vn_str = None

    if not daily_turnover.empty:
        if live_turnover is not None and today_vn_str:
            last_date_str = pd.Timestamp(daily_turnover.index.max()).strftime("%Y-%m-%d")
            if last_date_str == today_vn_str:
                # Hôm nay ĐÃ có trong EOD -> LIVE chính xác hơn (có thể có
                # GD thỏa thuận muộn EOD chưa kịp cập nhật) -> ghi đè bar cuối.
                daily_turnover.iloc[-1] = live_turnover
            else:
                # Hôm nay CHƯA có trong EOD (đang trong phiên) -> thêm bar mới.
                daily_turnover.loc[pd.Timestamp(today_vn_str)] = live_turnover
                daily_turnover = daily_turnover.sort_index()

        latest_turnover = float(daily_turnover.iloc[-1])
        avg20 = float(daily_turnover.tail(20).mean())

        vol_chart_data = daily_turnover.tail(15).tolist()
        # [SỬA] Badge giờ hiện KHỐI LƯỢNG (cổ phiếu) live thay vì so sánh TB20 —
        # dùng số live nếu có, fallback ước lượng từ Turnover/giá TB thị trường
        # nếu vì lý do gì đó chưa lấy được snapshot Wifeed (ngoài giờ/mới khởi động).
        if live_volume_shares is not None:
            vol_badge_str = f"{live_volume_shares / 1e6:,.1f}tr CP"
        else:
            vol_badge_str = "—"

        if len(vol_chart_data) > 0:
            min_v = min(vol_chart_data)
            max_v = max(vol_chart_data)
            if max_v > min_v:
                baseline = min_v - (max_v - min_v) * 0.1
                vol_chart_data = [v - baseline for v in vol_chart_data]
            # 🔴 FIX LỖI TOÁN HỌC: Nếu max_v == min_v (các phiên vol y chang nhau hoặc bằng 0), 
            # không làm gì cả, để list như cũ, hàm create_mini_chart sẽ tự handle
    else:
        latest_turnover = live_turnover or 0.0
        vol_chart_data = [0.0, 0.0]
        vol_badge_str = "—"

    vol_val_str = f"{latest_turnover / 1e9:,.0f} Tỷ"  # [SỬA] "B" -> "Tỷ" cho tiếng Việt
    vol_fig = create_mini_chart(vol_chart_data, color="#3b82f6", is_bar=True)

    # ==========================================
    # 5. TRẢ VỀ ĐÚNG THỨ TỰ OUTPUT
    # ==========================================
    return (
        vn_val, vn_badge, vn_badge_cls, vn_pts, vn_pts_cls, vn_fig,
        hnx_val, hnx_badge, hnx_badge_cls, hnx_pts, hnx_pts_cls, hnx_fig,
        vn30_val, vn30_badge, vn30_badge_cls, vn30_pts, vn30_pts_cls, vn30_fig,
        vol_val_str, vol_badge_str, vol_fig
    )

# ============================================================================
# [BƯỚC 3.1] TOP FIN PICKS — Nối dữ liệu thật từ bảng kết quả lọc
# ============================================================================
# Cột "Growth Score"/"Value Score"/"Momentum Score" trong get_snapshot_df()
# lưu dưới dạng XẾP HẠNG CHỮ (A/B/C/D/F), giống hệt cột "VGM Score" đang được
# xử lý ở screener_callbacks.py (grade_order = {'A':1,'B':2,...}). 'A' = tốt
# nhất -> quy đổi ngược lại thành số để "điểm cao nhất thắng" vẫn đúng logic.
_GRADE_TO_SCORE = {"A": 5, "B": 4, "C": 3, "D": 2, "F": 1}


def _grade_to_score(val) -> float:
    """'A' -> 5.0 (tốt nhất) ... 'F' -> 1.0. Giá trị lạ/rỗng -> 0.0 (thấp nhất)."""
    if val is None:
        return 0.0
    s = str(val).strip().upper()
    return float(_GRADE_TO_SCORE.get(s, 0))


def _get_top_fin_picks(n: int = 3) -> list:
    """Lấy đúng n mã đạt chuẩn 5 sao, đứng đầu bảng kết quả lọc thật.

    Nguồn:
    - get_snapshot_df()  -> bảng lọc đầy đủ (điểm số, Star_Rating, giá mới nhất)
      Cách sắp xếp lấy lại ĐÚNG logic gốc đang dùng ở screener_callbacks.py
      (ưu tiên FSS_Smart_Rank, fallback Star_Rating) để đồng nhất thứ hạng
      hiển thị ở Home với bảng Screener chính.
    - load_market_data() -> lịch sử giá đầy đủ, dùng để tính % thay đổi so với
      phiên trước (snapshot chỉ có 1 dòng/mã = phiên mới nhất, không có phiên
      liền trước để so sánh).

    Mỗi item trả về: {key, ticker, price, pct, stars, value_score, growth_score,
    momentum_score, insight}. KHÔNG còn "tag_variant" ở đây — tag Value/Growth/
    Momentum giờ do header.py._pick_card tự suy ra từ value_score/growth_score/
    momentum_score (điểm nào cao nhất thắng), để tag luôn khớp với số breakdown
    hiển thị trên card (trước tính tag từ letter grade A-F, có thể lệch với số
    Pct hiển thị khi 2 thành phần trùng grade).
    (insight ở đây là TÊN DOANH NGHIỆP thật, lấy qua get_company_name_vi())
    """
    try:
        df = get_snapshot_df()
    except Exception:
        df = pd.DataFrame()

    if df is None or df.empty or "Ticker" not in df.columns:
        return []

    df = df.copy()

    # ── Sắp xếp — đồng bộ với logic ở screener_callbacks.py ──
    if "FSS_Smart_Rank" in df.columns:
        df = df.sort_values("FSS_Smart_Rank", ascending=False)
    elif "Star_Rating" in df.columns:
        df = df.sort_values("Star_Rating", ascending=False)
    else:
        return []  # không có cột xếp hạng nào -> không đủ cơ sở chọn "top"

    # ── Lọc đúng chuẩn 5 sao nếu có cột Star_Rating; nếu chưa đủ n mã 5 sao
    # thì fallback lấy top n theo thứ hạng chung (tránh trả về rỗng) ──
    if "Star_Rating" in df.columns:
        df_5star = df[pd.to_numeric(df["Star_Rating"], errors="coerce") >= 5]
        df_top = df_5star if len(df_5star) >= n else df
    else:
        df_top = df

    top_rows = df_top.head(n).to_dict("records")
    if not top_rows:
        return []

    # ── Lịch sử giá đầy đủ để tính % thay đổi thật so với phiên trước ──
    try:
        df_price = load_market_data()
    except Exception:
        df_price = pd.DataFrame()

    picks = []
    for row in top_rows:
        ticker = str(row.get("Ticker", "")).strip().upper()
        if not ticker:
            continue

        price = float(row.get("Price Close", 0) or 0)
        pct = 0.0

        # 1) Baseline: tính từ lịch sử giá (parquet) trước
        if df_price is not None and not df_price.empty and "Ticker" in df_price.columns:
            d = df_price[df_price["Ticker"].astype(str).str.upper() == ticker].sort_values("Date")
            if len(d) >= 2:
                last_c = float(d["Price Close"].iloc[-1])
                prev_c = float(d["Price Close"].iloc[-2])
                if prev_c:
                    pct = (last_c - prev_c) / prev_c * 100
                price = last_c

        # 2) Patch LIVE từ realtime snapshot SAU CÙNG — để nó là giá trị "thắng"
        try:
            from src.backend.wifeed_updater import get_realtime_snapshot
            rt = get_realtime_snapshot().get(ticker)
            if rt:
                if rt.get("Price Close"):
                    price = float(rt["Price Close"])
                if rt.get("Price_Change_Pct") is not None:
                    pct = float(rt["Price_Change_Pct"])
        except Exception:
            pass

        # ── Tên doanh nghiệp thật (thay cho câu nhận xét) — ưu tiên get_company_name_vi(),
        # fallback cột "Company Common Name" nếu có sẵn trong snapshot, cuối cùng để trống ──
        company_name = get_company_name_vi(ticker)
        if not company_name:
            company_name = str(row.get("Company Common Name", "") or "").strip()

        stars_raw = row.get("Star_Rating", 5)
        try:
            stars_filled = int(round(float(stars_raw)))
        except (TypeError, ValueError):
            stars_filled = 5
        stars_filled = max(0, min(5, stars_filled))

        # ── Tag Growth/Value/Momentum: KHÔNG tự tính ở đây nữa. Trước dùng
        # letter grade (A-F, _grade_to_score) để so hạng cao nhất — nhưng đó
        # là thang RỜI RẠC 5 mức, trong khi số hiển thị trên card (bên dưới)
        # là Value_Score_Pct/Growth_Score_Pct/Momentum_Score_Pct (thang liên
        # tục 0-100). Hai nguồn khác nhau có thể lệch: vd Value=86 và
        # Growth=72 cùng rơi vào grade 'A' (bell curve rộng) -> tie letter
        # grade -> code cũ mặc định chọn "growth" (key đầu tiên trong dict)
        # dù Value_Score_Pct rõ ràng cao hơn -> tag hiển thị SAI so với số
        # breakdown ngay bên dưới nó, y hệt kiểu lệch số 87-vs-96 đã gặp ở
        # phần FSS Smart Rank. Giờ để header.py._pick_card tự suy ra tag từ
        # ĐÚNG 3 số Pct đã gửi xuống dưới đây (value_score/growth_score/
        # momentum_score) — 1 nguồn sự thật duy nhất, tag không thể lệch số.
        picks.append({
            "key": ticker.lower(),
            "ticker": ticker,
            "price": price,
            "pct": pct,
            "stars": stars_filled,
            "value_score": row.get("Value_Score_Pct"),       # ← THÊM
            "growth_score": row.get("Growth_Score_Pct"),     # ← THÊM
            "momentum_score": row.get("Momentum_Score_Pct"), # ← THÊM
            "insight": company_name,  # hiển thị tên doanh nghiệp thay cho câu nhận xét
        })

    return picks





# ============================================================================
# [BƯỚC 3.2] MARKET PULSE — Nối dữ liệu thật (Market Breadth + cảnh báo ngành)
# ============================================================================
def _build_alert_li(icon_class: str, icon_variant: str, title: str, desc: str) -> html.Li:
    """1 dòng cảnh báo trong Market Pulse — giữ đúng className đã dựng ở Bước 3
    (home-pulse-alert-item / -icon / -title / -desc), chỉ đổi nội dung động."""
    return html.Li(className="home-pulse-alert-item", children=[
        html.I(className=f"fa-solid {icon_class} home-pulse-alert-icon home-pulse-alert-icon-{icon_variant}"),
        html.Div(children=[
            html.Div(title, className="home-pulse-alert-title"),
            html.Div(desc, className="home-pulse-alert-desc"),
        ]),
    ])


def _compute_market_pulse() -> dict:
    """Tính Market Breadth (%mã tăng/giảm hôm nay) + 3 ngành nổi bật nhất phiên
    (dựa trên % thay đổi giá TB ngành + tỉ lệ khối lượng so với TB 20 phiên).
    Trả về None nếu không đủ dữ liệu để tính (caller giữ nguyên UI cũ, không update).
    """
    try:
        df_price = load_market_data()
    except Exception:
        df_price = pd.DataFrame()

    if df_price is None or df_price.empty or "Ticker" not in df_price.columns:
        return None

    d = df_price.sort_values(["Ticker", "Date"])

    def _last_pct(g):
        if len(g) < 2:
            return np.nan
        last_c = g["Price Close"].iloc[-1]
        prev_c = g["Price Close"].iloc[-2]
        return (last_c - prev_c) / prev_c * 100 if prev_c else np.nan

    pct_series = d.groupby("Ticker").apply(_last_pct, include_groups=False).dropna()
    if pct_series.empty:
        return None

    # ── [MỚI] Patch LIVE từ realtime snapshot — cùng pattern đã dùng ở
    # _get_top_fin_picks() (baseline EOD trước, ghi đè bằng giá/pct realtime
    # sau cùng để nó "thắng"). Nếu không có realtime (ngoài giờ, chưa fetch
    # lần nào), pct_series giữ nguyên baseline EOD như cũ — không lỗi.
    try:
        from src.backend.wifeed_updater import get_realtime_snapshot
        rt_snapshot = get_realtime_snapshot()
    except Exception:
        rt_snapshot = {}

    if rt_snapshot:
        for rt_ticker, rt in rt_snapshot.items():
            t = str(rt_ticker).strip().upper()
            pct_val = rt.get("Price_Change_Pct")
            if pct_val is not None:
                try:
                    pct_series.loc[t] = float(pct_val)
                except (TypeError, ValueError):
                    pass

    # ── Market Breadth: đếm mã tăng / giảm / đứng giá ──
    up_count   = int((pct_series > 0).sum())
    down_count = int((pct_series < 0).sum())
    flat_count = int((pct_series == 0).sum())
    total_ud   = up_count + down_count
    bullish_pct = (up_count / total_ud * 100) if total_ud else 50.0
    bearish_pct = 100 - bullish_pct

    # ── Khối lượng phiên gần nhất mỗi mã (dùng để tính tỉ lệ KL theo ngành) ──
    latest_vol = d.groupby("Ticker")["Volume"].last()

    try:
        df_snap = get_snapshot_df()
    except Exception:
        df_snap = pd.DataFrame()

    sector_col = None
    if df_snap is not None and not df_snap.empty:
        for c in ("Sector", "GICS Sector Name"):
            if c in df_snap.columns:
                sector_col = c
                break

    alerts = []
    if sector_col:
        cols_needed = ["Ticker", sector_col] + (["Avg_Vol_20D"] if "Avg_Vol_20D" in df_snap.columns else [])
        df_s = df_snap[cols_needed].copy().rename(columns={sector_col: "Sector"})
        df_s["Ticker"] = df_s["Ticker"].astype(str).str.upper()
        df_s["pct_change"] = df_s["Ticker"].map(pct_series)
        df_s["latest_vol"] = df_s["Ticker"].map(latest_vol)
        if "Avg_Vol_20D" in df_s.columns:
            df_s["vol_ratio"] = df_s["latest_vol"] / df_s["Avg_Vol_20D"].replace(0, np.nan)
        else:
            df_s["vol_ratio"] = np.nan

        df_s = df_s.dropna(subset=["pct_change"])
        df_s = df_s[df_s["Sector"].notna() & (df_s["Sector"] != "") & (df_s["Sector"] != "Chưa phân loại")]

        sector_stats = (
            df_s.groupby("Sector")
                .agg(avg_pct=("pct_change", "mean"), avg_vol_ratio=("vol_ratio", "mean"), n=("Ticker", "count"))
                .reset_index()
        )
        sector_stats = sector_stats[sector_stats["n"] >= 3]  # đủ mẫu ngành mới đáng tin

        if not sector_stats.empty:
            used = set()

            # 1. Strong Accumulation — tăng giá TB mạnh nhất, ưu tiên ngành có KL >= TB
            acc_pool = sector_stats[sector_stats["avg_vol_ratio"] >= 1.0]
            if acc_pool.empty:
                acc_pool = sector_stats
            acc_row = acc_pool.sort_values("avg_pct", ascending=False).iloc[0]
            used.add(acc_row["Sector"])
            vol_txt = f", KL x{acc_row['avg_vol_ratio']:.1f} TB" if pd.notna(acc_row["avg_vol_ratio"]) else ""
            alerts.append(_build_alert_li(
                "fa-bolt", "positive", "Tích lũy mạnh",
                f"Dòng tiền vào {acc_row['Sector']} (+{acc_row['avg_pct']:.2f}%{vol_txt})",
            ))

            # 2. Sector Consolidation — |%thay đổi TB| nhỏ nhất trong các ngành còn lại
            remain = sector_stats[~sector_stats["Sector"].isin(used)].copy()
            if not remain.empty:
                remain["abs_pct"] = remain["avg_pct"].abs()
                con_row = remain.sort_values("abs_pct", ascending=True).iloc[0]
                used.add(con_row["Sector"])
                alerts.append(_build_alert_li(
                    "fa-arrow-right", "neutral", "Tích lũy ngành",
                    f"Nhóm {con_row['Sector']} đi ngang ({con_row['avg_pct']:+.2f}%), tích lũy",
                ))

            # 3. Volatile Resistance — %thay đổi TB thấp nhất (áp lực bán) trong các ngành còn lại
            remain2 = sector_stats[~sector_stats["Sector"].isin(used)]
            if not remain2.empty:
                neg_row = remain2.sort_values("avg_pct", ascending=True).iloc[0]
                alerts.append(_build_alert_li(
                    "fa-triangle-exclamation", "negative", "Gặp vùng cản",
                    f"Áp lực bán ở nhóm {neg_row['Sector']} ({neg_row['avg_pct']:.2f}%)",
                ))

    return {
        "bullish_pct": bullish_pct,
        "bearish_pct": bearish_pct,
        "up_count": up_count,
        "down_count": down_count,
        "flat_count": flat_count,
        "alerts": alerts,
    }


@app.callback(
    Output("home-pulse-breadth-label", "children"),
    Output("home-pulse-breadth-counts", "children"),  # [MỚI]
    Output("home-pulse-breadth-fill-bull", "style"),
    Output("home-pulse-breadth-fill-bear", "style"),
    Output("home-pulse-alerts-list", "children"),
    Input("home-market-overview", "id"),        # trigger lần đầu load
    Input("header-realtime-interval", "n_intervals"),  # [MỚI] refresh mỗi 60s
    prevent_initial_call=False,
)
def update_market_pulse(_, n_intervals):
    result = _compute_market_pulse()

    # 🔴 NẾU KHÔNG CÓ DATA THẬT -> TRẢ VỀ PLACEHOLDER TẠI ĐÂY
    if not result:
        mock_label = "62% TĂNG"
        mock_counts = [
            html.Span([html.Strong("312"), " tăng"], className="home-pulse-breadth-count-item"),
            html.Span([html.Strong("180"), " giảm"], className="home-pulse-breadth-count-item"),
            html.Span("42 đứng giá", className="home-pulse-breadth-count-item"),
        ]
        mock_bull = {"width": "62%"}
        mock_bear = {"width": "38%"}
        mock_alerts = [
            _build_alert_li("fa-bolt", "positive", "Tích lũy mạnh", "Dòng tiền mạnh đổ vào nhóm ..."),
            _build_alert_li("fa-arrow-right", "neutral", "Tích lũy ngành", "Nhóm ... đang tích lũy ổn định"),
            _build_alert_li("fa-triangle-exclamation", "negative", "Gặp vùng cản", "Nhóm ... chạm kháng cự 52 tuần"),
        ]
        return mock_label, mock_counts, mock_bull, mock_bear, mock_alerts

    # 🟢 NẾU CÓ DATA THẬT -> XỬ LÝ BÌNH THƯỜNG
    bullish_pct = result["bullish_pct"]
    bearish_pct = result["bearish_pct"]
    up_count    = result["up_count"]
    down_count  = result["down_count"]
    flat_count  = result["flat_count"]

    label  = f"{bullish_pct:.0f}% TĂNG"
    counts = [
        html.Span([html.Strong(f"{up_count}"), " tăng"], className="home-pulse-breadth-count-item"),
        html.Span([html.Strong(f"{down_count}"), " giảm"], className="home-pulse-breadth-count-item"),
        html.Span(f"{flat_count} đứng giá", className="home-pulse-breadth-count-item"),
    ]  # [MỚI]
    bull_style = {"width": f"{bullish_pct:.1f}%"}
    bear_style = {"width": f"{bearish_pct:.1f}%"}

    alerts = result["alerts"]
    if not alerts:
        alerts = [html.Li(
            "Chưa đủ dữ liệu ngành (cột Sector) để đưa ra nhận định.",
            className="home-pulse-alert-item",
        )]
    return label, counts, bull_style, bear_style, alerts

# ============================================================================
# CALLBACK: REALTIME UPDATE — Header market overview + top picks
# Trigger: header-realtime-interval (60s) + lần đầu load trang
# ============================================================================
@app.callback(
    Output("home-picks-grid", "children"),
    Input("header-realtime-interval", "n_intervals"),
    prevent_initial_call=False,
)
def update_header_picks(n_intervals):
    picks = _get_top_fin_picks(n=3)
    if not picks:
        return html.Div(
            "Chưa có mã nào đạt chuẩn 5 sao.",
            className="home-picks-empty",
        )

    cards = []
    for p in picks:
        cards.append(_pick_card(
            key=p["key"],
            ticker=p["ticker"],
            price_str=f"{p['price']:,.0f}",
            change_str=f"{'+' if p['pct'] >= 0 else ''}{p['pct']:.2f}%",
            is_positive=p["pct"] >= 0,
            stars_filled=p["stars"],
            value_score=p["value_score"],       # ← THÊM
            growth_score=p["growth_score"],     # ← THÊM
            momentum_score=p["momentum_score"], # ← THÊM
            insight_text=p["insight"],
        ))
    return cards

# ============================================================================
# CALLBACK: CLICK VÀO TOP PICK CARD → MỞ DETAIL MODAL (giống double-click bảng)
# ============================================================================
from dash import callback_context, no_update, ALL
import json

@app.callback(
    Output("detail-modal",          "is_open",  allow_duplicate=True),
    Output("modal-title",           "children", allow_duplicate=True),
    Output("selected-stock-store",  "data",     allow_duplicate=True),
    Output("selected-ticker-store", "data",     allow_duplicate=True),
    Input({"type": "pick-card-click", "ticker": ALL}, "n_clicks"),
    prevent_initial_call=True,
)
def open_modal_from_pick_card(n_clicks_list):
    ctx = callback_context
    if not ctx.triggered or not any(n_clicks_list):
        return no_update, no_update, no_update, no_update

    # Lấy ticker từ id của card vừa bị click
    triggered_prop = ctx.triggered[0]["prop_id"].split(".")[0]
    try:
        triggered_id = json.loads(triggered_prop)
        ticker = triggered_id.get("ticker")
    except Exception:
        return no_update, no_update, no_update, no_update

    if not ticker:
        return no_update, no_update, no_update, no_update

    # Lấy đầy đủ dữ liệu dòng đó từ snapshot (không có sẵn rowData ở đây
    # như bảng screener, nên đọc thẳng từ get_snapshot_df())
    from src.backend.data_loader import get_snapshot_df
    df = get_snapshot_df()
    row = df[df["Ticker"] == ticker]
    if row.empty:
        return no_update, no_update, no_update, no_update

    stock = row.iloc[0].to_dict()

    # ── Tên công ty tiếng Việt — tái dùng đúng logic của open_detail_modal_fast ──
    from src.callbacks.screener_callbacks import df_comp_info
    company_name = stock.get('Company Common Name', '')
    company_name_vn = company_name
    if not df_comp_info.empty:
        match = df_comp_info[df_comp_info['Ticker'] == ticker]
        if not match.empty:
            for col in ['organ_name', 'company_name_vi', 'ten_cong_ty', 'name_vi']:
                if col in match.columns:
                    val = str(match[col].values[0]).strip()
                    if val and val.lower() not in ('nan', 'none', ''):
                        company_name_vn = val
                        break
    if company_name_vn == company_name or not company_name_vn:
        company_name_vn = company_name or ticker

    title_text = f"Cổ phiếu {ticker} – {company_name_vn}"

    return True, title_text, stock, ticker