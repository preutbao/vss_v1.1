# src/callbacks/chart_callbacks.py
"""
Callback xử lý hiển thị biểu đồ nến trong Detail Tabs
Tích hợp vào tab "BIẾN ĐỘNG GIÁ" của screener
Mang phong cách Glassmorphism & Dashboard của VnStock Pro
"""

from dash import Input, Output, State, html, dcc
import dash_bootstrap_components as dbc
from src.app_instance import app
from src.backend.data_loader import load_market_data, load_index_data
from src.utils.chart_module import create_fireant_candlestick, format_volume_short
import pandas as pd
import numpy as np
import logging

logger = logging.getLogger(__name__)


# ============================================================================
# HELPER: HIỂN THỊ THÔNG BÁO KHI KHÔNG CÓ DỮ LIỆU
# ============================================================================
def _no_data_div(ticker="", reason="Dữ liệu giá của mã này chưa có trong hệ thống hoặc chưa được cập nhật."):
    return html.Div([
        html.Div("📭", style={"fontSize": "52px", "marginBottom": "14px"}),
        html.P(
            f"Công ty chưa có dữ liệu giá cổ phiếu" + (f" ({ticker})" if ticker else ""),
            style={"color": "#f8fafc", "fontSize": "17px", "fontWeight": "700", "margin": "0 0 8px 0"}
        ),
        html.P(reason, style={"color": "#94a3b8", "fontSize": "13px", "margin": "0"})
    ], style={
        "display": "flex", "flexDirection": "column", "alignItems": "center",
        "justifyContent": "center", "height": "400px", "textAlign": "center",
        "backgroundColor": "#1e293b", "borderRadius": "15px",
        "border": "1px solid rgba(239, 68, 68, 0.25)"
    })


@app.callback(
    Output("candlestick-chart-container", "children"),
    [Input("screener-table", "selectedRows"),
     Input("ma-selector", "value"),
     Input("show-volume-toggle", "on"),
     Input("show-rsi-toggle", "on"),
     Input("show-macd-toggle", "on"),
     Input("show-index-toggle", "on"),
     Input("chart-type-selector", "value"),
     Input("period-1w", "n_clicks"),
     Input("period-1m", "n_clicks"),
     Input("period-3m", "n_clicks"),
     Input("period-6m", "n_clicks"),
     Input("period-1y", "n_clicks"),
     Input("period-ytd", "n_clicks"),
     Input("period-all", "n_clicks"),
     Input("chart-refresh-store", "data")],
    prevent_initial_call=True
)
def update_candlestick_chart(selected_rows, ma_periods, show_volume, show_rsi, show_macd, show_index, chart_type,
                             n_1w, n_1m, n_3m, n_6m, n_1y, n_ytd, n_all, _refresh):
    """
    Tạo biểu đồ nến khi người dùng chọn một dòng trong bảng
    """
    if not selected_rows or len(selected_rows) == 0:
        return html.Div([
            html.I(className="fas fa-chart-line", style={
                "fontSize": "48px",
                "color": "#475569",
                "marginBottom": "15px"
            }),
            html.P("Chọn một mã cổ phiếu từ bảng để xem biểu đồ", style={
                "color": "#8b949e",
                "fontSize": "14px"
            })
        ], style={
            "display": "flex",
            "flexDirection": "column",
            "alignItems": "center",
            "justifyContent": "center",
            "padding": "50px",
            "textAlign": "center"
        })

    try:
        # Lấy ticker đã chọn
        selected_ticker = selected_rows[0]['Ticker']
        logger.info(f"Creating chart for ticker: {selected_ticker}")

        # Load dữ liệu giá
        df_price = load_market_data()

        if df_price.empty:
            return html.Div("⚠️ Không có dữ liệu giá", style={"color": "#ef4444", "padding": "20px"})

        # Lọc dữ liệu theo ticker
        df_ticker = df_price[df_price['Ticker'] == selected_ticker].copy()

        if df_ticker.empty:
            return _no_data_div(selected_ticker)

        # Sắp xếp theo ngày
        df_ticker = df_ticker.sort_values('Date')

        # ====================================================================
        # 🟢 VALIDATE DỮ LIỆU - kiểm tra cột giá hợp lệ (trước filter thời gian)
        # ====================================================================
        price_col = next((c for c in ['Price Close', 'close', 'Close'] if c in df_ticker.columns), None)
        if price_col is None:
            return _no_data_div(selected_ticker, reason="Dữ liệu không có cột giá hợp lệ.")

        # Loại bỏ toàn bộ dòng NaN hoặc giá <= 0 ngay từ đầu
        df_ticker = df_ticker[df_ticker[price_col].notna() & (df_ticker[price_col] > 0)].copy()
        if df_ticker.empty:
            return _no_data_div(selected_ticker)

        # ====================================================================
        # 🟢 XÁC ĐỊNH NÚT THỜI GIAN NÀO ĐƯỢC BẤM GẦN NHẤT (ctx)
        # ====================================================================
        from dash import ctx as dash_ctx
        period_map = {
            'period-1w': '1T', 'period-1m': '1M', 'period-3m': '3M',
            'period-6m': '6M', 'period-1y': '1Y', 'period-ytd': 'YTD', 'period-all': 'All'
        }
        triggered_id = dash_ctx.triggered_id if dash_ctx.triggered_id else 'period-6m'
        # Nếu trigger là chọn mã mới hoặc toggle khác (không phải nút period) → reset về 3M
        if triggered_id not in period_map:
            triggered_id = 'period-6m'
        time_range = period_map.get(triggered_id, '1Y')

        today = pd.Timestamp.today().normalize()

        time_map = {
            '1T': today - pd.DateOffset(weeks=1),
            '1M': today - pd.DateOffset(months=1),
            '3M': today - pd.DateOffset(months=3),
            '6M': today - pd.DateOffset(months=6),
            '1Y': today - pd.DateOffset(years=1),
            'YTD': pd.Timestamp(today.year, 1, 1),
            'All': None
        }

        start_date = time_map.get(time_range, None)
        if start_date is not None:
            df_ticker = df_ticker[df_ticker['Date'] >= start_date]

        if df_ticker.empty:
            return html.Div([
                html.Div("📅", style={"fontSize": "48px", "marginBottom": "12px"}),
                html.P(
                    f"Không có dữ liệu trong khoảng thời gian đã chọn ({time_range})",
                    style={"color": "#f8fafc", "fontSize": "16px", "fontWeight": "600", "margin": "0 0 6px 0"}
                ),
                html.P(
                    "Hãy thử chọn khoảng thời gian rộng hơn (6M, 1Y hoặc All).",
                    style={"color": "#94a3b8", "fontSize": "13px", "margin": "0"}
                )
            ], style={
                "display": "flex", "flexDirection": "column", "alignItems": "center",
                "justifyContent": "center", "padding": "60px 20px", "textAlign": "center",
                "backgroundColor": "#1e293b", "borderRadius": "15px",
                "border": "1px solid rgba(251, 191, 36, 0.3)"
            })

        # Lấy tên công ty nếu có
        company_name = selected_rows[0].get('Company Common Name', selected_ticker)

        # Tiêu đề biểu đồ (cập nhật theo khoảng thời gian)
        range_label_map = {
            '1T': '1 tuần gần nhất', '1M': '1 tháng gần nhất', '3M': '3 tháng gần nhất',
            '6M': '6 tháng gần nhất', '1Y': '12 tháng gần nhất',
            'YTD': f'Từ đầu năm {today.year}', 'All': 'Toàn bộ lịch sử'
        }
        title = f"{selected_ticker} - {company_name} ({range_label_map.get(time_range, '12 tháng gần nhất')})"

        # Xử lý MA periods
        ma_list = []
        show_ma = False
        if ma_periods:
            if isinstance(ma_periods, list):
                ma_list = [int(p) for p in ma_periods]
                show_ma = len(ma_list) > 0
            else:
                ma_list = [int(ma_periods)]
                show_ma = True

        # Load index data for overlay
        df_idx = None
        if show_index:
            try:
                df_idx = load_index_data()
            except Exception:
                df_idx = None

        # Gọi module tạo biểu đồ nến chuyên nghiệp
        fig = create_fireant_candlestick(
            df=df_ticker,
            title=title,
            theme='dark',
            chart_type=chart_type,
            show_volume=show_volume if show_volume is not None else True,
            show_ma=show_ma,
            ma_periods=ma_list if ma_list else [20],
            show_rsi=show_rsi if show_rsi is not None else False,
            rsi_period=14,
            show_macd=show_macd if show_macd is not None else False,
            show_index=show_index if show_index is not None else False,
            df_index=df_idx,
        )

        # ====================================================================
        # 🟢 ZOOM & PAN MẶC ĐỊNH
        # ====================================================================
        total_rows = len(df_ticker)
        start_idx = 0  # Toàn bộ khoảng đã lọc
        end_idx = total_rows - 1

        fig.update_xaxes(range=[start_idx, end_idx])
        # Đặt công cụ mặc định là Pan
        fig.update_layout(dragmode='pan')

        # ====================================================================
        # 🟢 TÍNH TOÁN DỮ LIỆU CHO 3 KHỐI INFO CARDS (Giao diện VnStock Pro)
        # Lấy dữ liệu 52 tuần gần nhất (250 phiên) để phân tích
        # ====================================================================
        df_52w = df_ticker  # Đã lọc theo time_range rồi, dùng thẳng

        # Card 1: Biên độ giá
        high_52w = df_52w['Price High'].max()
        low_52w = df_52w['Price Low'].min()
        amplitude = ((high_52w - low_52w) / low_52w * 100) if low_52w > 0 else 0

        # Card 2: Khối lượng
        avg_volume = df_52w['Volume'].mean()
        total_volume = df_52w['Volume'].sum()
        current_vol = df_52w['Volume'].iloc[-1]
        vol_trend_icon = "📈" if current_vol > avg_volume else "📉"

        # Card 3: Phân tích xu hướng
        volatility = df_52w['Price Close'].pct_change().std() * 100
        price_trend = "Tăng" if df_52w['Price Close'].iloc[-1] > df_52w['Price Close'].iloc[0] else "Giảm"
        trend_icon = "📈" if price_trend == "Tăng" else "📉"
        vol_eval = "Cao" if volatility > 3 else "Trung bình" if volatility > 1.5 else "Thấp"

        # ====================================================================
        # 🟢 THIẾT KẾ UI - BLOOMBERG TERMINAL PREMIUM
        # ====================================================================

        # Helper: metric chip cho info bar
        def _metric_chip(label, value, accent="#00d4ff", icon=""):
            return html.Div([
                html.Div([
                    html.Span(icon + " " if icon else "", style={"marginRight": "4px"}),
                    html.Span(label, style={
                        "fontSize": "0.68rem", "fontWeight": "700", "letterSpacing": "0.1em",
                        "textTransform": "uppercase", "color": "#3d6a8a",
                        "fontFamily": "JetBrains Mono, monospace"
                    })
                ], style={"marginBottom": "6px"}),
                html.Div(value, style={
                    "fontSize": "1.05rem", "fontWeight": "800", "color": accent,
                    "fontFamily": "JetBrains Mono, monospace", "letterSpacing": "-0.02em",
                    "textShadow": f"0 0 12px {accent}44"
                })
            ], style={
                "padding": "12px 18px",
                "background": "linear-gradient(135deg, rgba(9,21,38,0.9), rgba(12,30,51,0.7))",
                "borderRadius": "10px",
                "border": f"1px solid {accent}22",
                "borderTop": f"2px solid {accent}66",
                "minWidth": "130px",
                "flex": "1",
            })

        # Tính % thay đổi so với đầu kỳ
        price_change_pct = ((df_ticker['Price Close'].iloc[-1] - df_ticker['Price Close'].iloc[0])
                            / df_ticker['Price Close'].iloc[0] * 100) if df_ticker['Price Close'].iloc[0] > 0 else 0
        price_change_color = "#00e676" if price_change_pct >= 0 else "#ff3d57"
        price_change_str = f"{price_change_pct:+.2f}%"

        vol_ratio = current_vol / avg_volume if avg_volume > 0 else 0
        vol_ratio_color = "#00e676" if vol_ratio >= 1.5 else "#ffb703" if vol_ratio >= 0.8 else "#ff3d57"

        info_bar = html.Div([
            _metric_chip("CAO NHẤT KỲ", f"{high_52w:,.0f}", "#00d4ff"),
            _metric_chip("THẤP NHẤT KỲ", f"{low_52w:,.0f}", "#58a6ff"),
            _metric_chip("BIÊN ĐỘ", f"{amplitude:.1f}%", "#b388ff"),
            _metric_chip(f"TĂNG/GIẢM KỲ", price_change_str, price_change_color),
            _metric_chip("VOL HÔM NAY", f"{format_volume_short(current_vol)}", vol_ratio_color),
            _metric_chip("TB KHỐI LƯỢNG", f"{format_volume_short(avg_volume)}", "#7fa8cc"),
            _metric_chip("BIẾN ĐỘNG", f"{volatility:.2f}%", "#ffb703"),
        ], style={
            "display": "flex", "gap": "10px", "padding": "14px 4px",
            "overflowX": "auto", "flexWrap": "nowrap",
        })

        # ====================================================================
        # RENDER TOÀN BỘ TAB
        # ====================================================================
        chart_component = dcc.Graph(
            id="main-candlestick-chart",
            figure=fig,
            config={
                'displayModeBar': True,
                'displaylogo': False,
                'modeBarButtonsToRemove': ['lasso2d', 'select2d', 'toImage'],
                'modeBarButtonsToAdd': ['drawline', 'drawopenpath', 'drawclosedpath', 'drawcircle', 'drawrect',
                                        'eraseshape'],
                'scrollZoom': True,
                'doubleClick': 'reset',
                'doubleClickDelay': 300,
                'editable': True,
                'edits': {
                    'shapePosition': True, 'annotationPosition': True, 'annotationTail': True,
                    'annotationText': True, 'axisTitleText': False, 'colorbarPosition': False,
                    'colorbarTitleText': False, 'legendPosition': True, 'legendText': False, 'titleText': False
                },
                'responsive': True,
                'autosizable': True
            },
            style={
                "height": "100%", "width": "100%", "minHeight": "580px",
            },
            className="fireant-candlestick-chart"
        )

        return html.Div([
            # Info bar trên cùng
            html.Div([info_bar], style={
                "background": "linear-gradient(135deg, rgba(6,15,30,0.95), rgba(9,21,38,0.9))",
                "borderRadius": "12px",
                "border": "1px solid rgba(0,212,255,0.1)",
                "marginBottom": "12px",
                "boxShadow": "0 4px 16px rgba(0,0,0,0.4)",
            }),
            # Biểu đồ
            html.Div([chart_component], style={
                "background": "rgba(2,8,16,0.98)",
                "borderRadius": "12px",
                "border": "1px solid rgba(0,212,255,0.12)",
                "overflow": "hidden",
                "boxShadow": "0 8px 32px rgba(0,0,0,0.5)",
                "padding": "8px 4px 4px 4px",
            }),
        ], style={"padding": "4px"})

    except ValueError as e:
        if "NO_VALID_DATA" in str(e):
            return _no_data_div(
                selected_rows[0].get('Ticker', '') if selected_rows else '',
                reason="Dữ liệu giá của mã này toàn bộ là NaN hoặc 0 — chưa được cập nhật."
            )
        logger.error(f"ValueError: {e}")
        return _no_data_div()
    except Exception as e:
        logger.error(f"Error creating candlestick chart: {e}")
        import traceback
        traceback.print_exc()
        # Phân loại lỗi: nếu liên quan dữ liệu thì hiện thông báo thân thiện
        err_str = str(e).lower()
        if any(k in err_str for k in ['keyerror', 'column', 'empty', 'nan', 'none']):
            msg = "Dữ liệu giá cổ phiếu không đầy đủ hoặc bị lỗi định dạng."
        else:
            msg = "Đã xảy ra lỗi khi tải biểu đồ. Vui lòng thử lại."
        return html.Div([
            html.Div("⚠️", style={"fontSize": "48px", "marginBottom": "12px"}),
            html.P(msg, style={"color": "#f8fafc", "fontSize": "15px", "fontWeight": "600", "margin": "0 0 6px 0"}),
            html.P(f"Chi tiết: {str(e)}", style={"color": "#64748b", "fontSize": "11px", "margin": "0"})
        ], style={
            "display": "flex", "flexDirection": "column", "alignItems": "center",
            "justifyContent": "center", "padding": "60px 20px", "textAlign": "center",
            "backgroundColor": "#1e293b", "borderRadius": "15px",
            "border": "1px solid rgba(239, 68, 68, 0.3)"
        })


from dash import ClientsideFunction

from dash import ClientsideFunction

# ============================================================================
# CALLBACK: HIGHLIGHT NÚT THỜI GIAN ĐANG ACTIVE
# ============================================================================
PERIOD_BUTTON_IDS = ['period-1w', 'period-1m', 'period-3m', 'period-6m', 'period-1y', 'period-ytd', 'period-all']


@app.callback(
    [Output(btn_id, "color") for btn_id in PERIOD_BUTTON_IDS] +
    [Output(btn_id, "outline") for btn_id in PERIOD_BUTTON_IDS],
    [Input(btn_id, "n_clicks") for btn_id in PERIOD_BUTTON_IDS] +
    [Input("screener-table", "selectedRows")],
    prevent_initial_call=False
)
def highlight_active_period(*args):
    from dash import ctx as dash_ctx
    triggered_id = dash_ctx.triggered_id if dash_ctx.triggered_id else 'period-6m'
    if triggered_id not in PERIOD_BUTTON_IDS:
        triggered_id = 'period-6m'
    colors = ["primary" if btn_id == triggered_id else "secondary" for btn_id in PERIOD_BUTTON_IDS]
    outlines = [False if btn_id == triggered_id else True for btn_id in PERIOD_BUTTON_IDS]
    return colors + outlines


# ============================================================================
# CALLBACK: NÚT LÀM MỚI — reload lại biểu đồ bằng cách increment store
# ============================================================================
@app.callback(
    Output("chart-refresh-store", "data"),
    Input("refresh-chart-btn", "n_clicks"),
    prevent_initial_call=True
)
def refresh_chart(n_clicks):
    return n_clicks or 0


# ============================================================================
# CALLBACK: NÚT TOÀN MÀN HÌNH — mở chart container trong fullscreen
# ============================================================================
app.clientside_callback(
    """
    function(n_clicks) {
        if (!n_clicks) return window.dash_clientside.no_update;
        var el = document.getElementById('candlestick-chart-container');
        if (!el) return window.dash_clientside.no_update;
        if (document.fullscreenElement) {
            document.exitFullscreen();
        } else if (el.requestFullscreen) {
            el.requestFullscreen();
        } else if (el.webkitRequestFullscreen) {
            el.webkitRequestFullscreen();
        }
        return window.dash_clientside.no_update;
    }
    """,
    Output("fullscreen-chart-btn", "n_clicks"),
    Input("fullscreen-chart-btn", "n_clicks"),
    prevent_initial_call=True,
)