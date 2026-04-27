# src/utils/chart_module.py
"""
Module vẽ biểu đồ kỹ thuật theo phong cách FireAnt/VnStock Pro
Hỗ trợ đa dạng loại biểu đồ (Nến, Đường, Vùng) và các chỉ báo kỹ thuật
"""

import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np


# ============================================================================
# THEME COLORS - GIỐNG HỆT VNSTOCK PRO
# ============================================================================

def get_chart_theme_colors(theme='dark'):
    """
    Lấy mã màu dựa trên giao diện hiện tại
    theme: 'dark' hoặc 'light'
    """
    if theme == 'light':
        return {
            'background': '#f8fafc',
            'card_bg': '#ffffff',
            'border': '#e2e8f0',
            'text': '#1e293b',
            'text_secondary': '#475569',
            'primary': '#3b82f6',
            'primary_dark': '#1d4ed8',
            'primary_light': '#60a5fa',
            'positive': '#10b981',
            'negative': '#ef4444',
            'neutral': '#374151',
            'gradient': 'linear-gradient(135deg, #f8fafc 0%, #e2e8f0 100%)',
            'chart_bg': '#ffffff',
            'grid_color': 'rgba(30, 41, 59, 0.15)',
            'header_bg': 'linear-gradient(135deg, #0f172a 0%, #1e3a5f 50%, #334d73 100%)',
            'accent1': '#f59e0b',
            'accent2': '#8b5cf6',
            'accent3': '#06b6d4',
            'area_fill': 'rgba(59, 130, 246, 0.1)'  # Màu nền cho biểu đồ vùng
        }
    else:  # Dark theme - Bloomberg Terminal signature
        return {
            'background': '#020810',
            'card_bg': '#091526',
            'border': '#1d4d80',
            'text': '#d6eaf8',
            'text_secondary': '#7fa8cc',
            'primary': '#00d4ff',
            'primary_dark': '#0090ff',
            'primary_light': '#60d4ff',
            'positive': '#00e676',
            'negative': '#ff3d57',
            'neutral': '#3d6a8a',
            'gradient': 'linear-gradient(135deg, #020810 0%, #091526 100%)',
            'chart_bg': '#020810',
            'grid_color': 'rgba(0, 212, 255, 0.055)',
            'header_bg': 'linear-gradient(135deg, #020810 0%, #071828 50%, #091e35 100%)',
            'accent1': '#ffb703',
            'accent2': '#b388ff',
            'accent3': '#00d4ff',
            'area_fill': 'rgba(0, 212, 255, 0.08)'
        }


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def filter_trading_days(df):
    """Lọc chỉ các ngày có giao dịch (volume > 0)"""
    if 'Volume' in df.columns:
        return df[df['Volume'] > 0].copy()
    if 'volume' in df.columns:
        return df[df['volume'] > 0].copy()
    return df.copy()


def create_smart_ticks(dates):
    """Tạo danh sách ngày tháng hiển thị thông minh như FireAnt"""
    if len(dates) <= 10:
        return dates, [d.strftime('%d/%m/%y') for d in dates]  # Thêm năm cho dễ nhìn

    num_ticks = min(10, max(5, len(dates) // 20))
    tick_indices = np.linspace(0, len(dates) - 1, num_ticks, dtype=int)
    tick_dates = [dates[i] for i in tick_indices]
    tick_labels = [d.strftime('%d/%m/%y') for d in tick_dates]

    if 0 not in tick_indices:
        tick_indices = np.append([0], tick_indices)
        tick_dates = [dates[0]] + tick_dates
        tick_labels = [dates[0].strftime('%d/%m/%y')] + tick_labels

    if len(dates) - 1 not in tick_indices:
        tick_indices = np.append(tick_indices, len(dates) - 1)
        tick_dates.append(dates[-1])
        tick_labels.append(dates[-1].strftime('%d/%m/%y'))

    return tick_dates, tick_labels


def calculate_rsi(prices, period=14):
    """Tính chỉ số RSI"""
    delta = prices.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi


def calculate_macd(prices, fast=12, slow=26, signal=9):
    """Tính MACD"""
    ema_fast = prices.ewm(span=fast).mean()
    ema_slow = prices.ewm(span=slow).mean()
    macd = ema_fast - ema_slow
    signal_line = macd.ewm(span=signal).mean()
    histogram = macd - signal_line
    return macd, signal_line, histogram


def format_volume_short(value):
    """Format volume thành dạng ngắn gọn"""
    if pd.isna(value) or value == 0: return "0"
    abs_value = abs(value)
    if abs_value >= 1_000_000_000:
        return f"{value / 1_000_000_000:.1f}B"
    elif abs_value >= 1_000_000:
        return f"{value / 1_000_000:.0f}M"
    elif abs_value >= 1_000:
        return f"{value / 1_000:.0f}K"
    else:
        return f"{value:.0f}"


# ============================================================================
# MAIN CHART FUNCTION - NÂNG CẤP ĐA BIỂU ĐỒ
# ============================================================================

def create_fireant_candlestick(
        df,
        title="Biểu đồ giá",
        theme='dark',
        chart_type='candlestick',
        show_volume=True,
        show_ma=False,
        ma_periods=[20],
        show_rsi=False,
        rsi_period=14,
        show_macd=False,
        show_index=False,  # VĐ4: overlay JCI index normalized to 100
        df_index=None,  # VĐ4: DataFrame with Date + JCI_Close columns
):
    colors = get_chart_theme_colors(theme)

    # 1. Chuẩn hóa Data
    df_plot = df.copy()
    column_mapping = {
        'Date': 'date', 'Open': 'open', 'High': 'high', 'Low': 'low', 'Close': 'close', 'Volume': 'volume',
        'Price Open': 'open', 'Price High': 'high', 'Price Low': 'low', 'Price Close': 'close'
    }
    for old_col, new_col in column_mapping.items():
        if old_col in df_plot.columns and new_col not in df_plot.columns:
            df_plot.rename(columns={old_col: new_col}, inplace=True)

    if 'date' in df_plot.columns:
        df_plot['date'] = pd.to_datetime(df_plot['date'])

    df_plot = filter_trading_days(df_plot)

    # Guard: nếu sau khi lọc không còn dữ liệu hợp lệ thì raise luôn
    if df_plot.empty or 'close' not in df_plot.columns:
        raise ValueError("NO_VALID_DATA")

    df_plot = df_plot.sort_values('date')
    df_plot['date_str'] = df_plot['date'].dt.strftime('%Y-%m-%d')

    # 2. Tính toán MA
    ma_traces = []
    if show_ma and ma_periods:
        ma_colors = [colors['accent1'], colors['accent2'], colors['accent3'],
                     colors['primary'], colors['positive'], colors['negative']]
        for i, period in enumerate(ma_periods):
            if len(df_plot) >= period:
                df_plot[f'MA{period}'] = df_plot['close'].rolling(window=period).mean()
                ma_traces.append({
                    'period': period, 'data': df_plot[f'MA{period}'], 'color': ma_colors[i % len(ma_colors)]
                })

    # 3. Bố cục Subplots
    rows = 1
    row_heights = [1.0]
    subplot_titles = [title]

    if show_volume:
        rows += 1
        row_heights = [0.75, 0.25]
        subplot_titles.append('Khối lượng')

    if show_rsi:
        rows += 1
        if len(row_heights) == 1:
            row_heights = [0.6, 0.4]
        else:
            row_heights = [0.5, 0.25, 0.25]
        subplot_titles.append(f'RSI ({rsi_period})')

    if show_macd:
        rows += 1
        if len(row_heights) == 1:
            row_heights = [0.6, 0.4]
        elif len(row_heights) == 2:
            row_heights = [0.45, 0.25, 0.3]
        else:
            row_heights = [0.4, 0.2, 0.2, 0.2]
        subplot_titles.append('MACD')

    fig = make_subplots(
        rows=rows, cols=1, shared_xaxes=True,
        vertical_spacing=0.02,  # Tăng nhẹ khoảng cách để không bị dính chữ
        subplot_titles=subplot_titles, row_heights=row_heights
    )

    # ====================================================================
    # 🟢 VẼ BIỂU ĐỒ CHÍNH (NẾN / ĐƯỜNG / VÙNG)
    # ====================================================================
    if chart_type == 'line':
        fig.add_trace(go.Scatter(
            x=df_plot['date_str'], y=df_plot['close'],
            mode='lines', name="Giá Đóng cửa",
            line=dict(color=colors['primary'], width=2),
            hovertemplate='<b>Ngày:</b> %{x}<br><b>Giá:</b> %{y:,.0f}<extra></extra>'
        ), row=1, col=1)

    elif chart_type == 'area':
        fig.add_trace(go.Scatter(
            x=df_plot['date_str'], y=df_plot['close'],
            mode='lines', name="Giá Đóng cửa",
            fill='tozeroy', fillcolor=colors['area_fill'],
            line=dict(color=colors['primary'], width=2),
            hovertemplate='<b>Ngày:</b> %{x}<br><b>Giá:</b> %{y:,.0f}<extra></extra>'
        ), row=1, col=1)

    else:  # Mặc định là Candlestick
        fig.add_trace(go.Candlestick(
            x=df_plot['date_str'], open=df_plot['open'], high=df_plot['high'],
            low=df_plot['low'], close=df_plot['close'], name="Giá",
            increasing_line_color=colors['positive'], decreasing_line_color=colors['negative'],
            increasing_fillcolor=colors['positive'], decreasing_fillcolor=colors['negative'],
            line=dict(width=1.2), whiskerwidth=0.9, opacity=0.95
        ), row=1, col=1)

    # VẼ MA
    for ma_trace in ma_traces:
        fig.add_trace(go.Scatter(
            x=df_plot['date_str'], y=ma_trace['data'],
            mode='lines', name=f"MA{ma_trace['period']}",
            line=dict(color=ma_trace['color'], width=1.5), opacity=0.8
        ), row=1, col=1)

    current_row = 2

    # VẼ VOLUME
    if show_volume:
        vol_colors = [colors['positive'] if c >= o else colors['negative'] for c, o in
                      zip(df_plot['close'], df_plot['open'])]
        fig.add_trace(go.Bar(
            x=df_plot['date_str'], y=df_plot['volume'], name="Khối lượng",
            marker_color=vol_colors, opacity=0.8, marker_line_width=0
        ), row=current_row, col=1)
        current_row += 1

    # VẼ RSI
    if show_rsi:
        df_plot['RSI'] = calculate_rsi(df_plot['close'], rsi_period)
        fig.add_trace(go.Scatter(
            x=df_plot['date_str'], y=df_plot['RSI'], mode='lines',
            name=f"RSI", line=dict(color=colors['accent3'], width=1.5)
        ), row=current_row, col=1)

        # Vùng an toàn của RSI
        fig.add_hrect(y0=30, y1=70, fillcolor='rgba(255,255,255,0.07)', opacity=1, line_width=0, row=current_row, col=1)
        fig.add_hline(y=70, line=dict(color=colors['negative'], width=1, dash="dash"), row=current_row, col=1)
        fig.add_hline(y=30, line=dict(color=colors['positive'], width=1, dash="dash"), row=current_row, col=1)
        current_row += 1

    # VẼ MACD
    if show_macd:
        macd, signal, hist = calculate_macd(df_plot['close'])
        hist_colors = [colors['positive'] if h >= 0 else colors['negative'] for h in hist]

        fig.add_trace(go.Bar(x=df_plot['date_str'], y=hist, name="Histogram", marker_color=hist_colors, opacity=0.5,
                             marker_line_width=0), row=current_row, col=1)
        fig.add_trace(go.Scatter(x=df_plot['date_str'], y=macd, mode='lines', name="MACD",
                                 line=dict(color=colors['primary'], width=1.5)), row=current_row, col=1)
        fig.add_trace(go.Scatter(x=df_plot['date_str'], y=signal, mode='lines', name="Signal",
                                 line=dict(color=colors['accent1'], width=1.5)), row=current_row, col=1)

    # ====================================================================
    # 🟢 CẤU HÌNH LAYOUT CHUẨN TRADINGVIEW
    # ====================================================================
    fig.update_layout(
        title=None,
        template="plotly_dark" if theme == 'dark' else "plotly_white",
        height=800 if rows > 2 else 580,
        margin=dict(l=10, r=65, t=12, b=20),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor=colors['chart_bg'],
        font=dict(color=colors['text_secondary'], family="JetBrains Mono"),
        hovermode='closest',
        showlegend=False,
        xaxis_rangeslider_visible=False,
        hoverlabel=dict(
            bgcolor='#091526',
            bordercolor='#1d4d80',
            font=dict(family='JetBrains Mono', size=12, color='#d6eaf8'),
        ),
    )

    # 🟢 TRỤC X & Y SMART FORMATTING
    dates = df_plot['date'].tolist()
    tick_dates, tick_labels = create_smart_ticks(dates)

    for i in range(1, rows + 1):
        # Trục X
        fig.update_xaxes(
            showgrid=False,
            showspikes=True,
            spikethickness=1,
            spikedash="dot",
            spikecolor='rgba(0,212,255,0.4)',
            spikemode="across",
            showline=True,
            linewidth=1,
            linecolor='rgba(29, 77, 128, 0.5)',
            type='category',
            tickmode='array',
            tickvals=[d.strftime('%Y-%m-%d') for d in tick_dates],
            ticktext=tick_labels,
            tickangle=-45,
            tickfont=dict(
                family="JetBrains Mono",
                size=10,
                color='#3d6a8a'
            ),
            row=i, col=1
        )
        # Trục Y
        fig.update_yaxes(
            gridcolor='rgba(0, 212, 255, 0.055)',
            gridwidth=1,
            showspikes=True,
            spikethickness=1,
            spikedash="dot",
            spikecolor='rgba(0,212,255,0.4)',
            showline=False,
            tickfont=dict(
                family="JetBrains Mono",
                size=10,
                color='#3d6a8a'
            ),
            row=i, col=1
        )

    # Trục Y riêng cho RSI
    if show_rsi:
        rsi_row = 2 if not show_volume else 3
        if rsi_row <= rows:
            fig.update_yaxes(range=[0, 100], tickvals=[30, 50, 70], row=rsi_row, col=1)

    # Trục Y riêng cho Volume (Rút gọn số)
    if show_volume:
        vol_row = 2
        max_vol = df_plot['volume'].max()
        if max_vol >= 1_000_000:
            step = (max_vol // 4) // 1_000_000 * 1_000_000
            step = max(step, 1_000_000)
            v_ticks = [i * step for i in range(5)]
            fig.update_yaxes(tickmode='array', tickvals=v_ticks, ticktext=[format_volume_short(v) for v in v_ticks],
                             row=vol_row, col=1)

    # ── VĐ4: JCI INDEX OVERLAY (normalized to 100 at chart start) ──────────
    if show_index and df_index is not None and not df_index.empty:
        try:
            idx = df_index.copy()
            # Support both Date/JCI_Close and date/jci_close column names
            date_col = next((c for c in idx.columns if c.lower() == 'date'), None)
            price_col_idx = next((c for c in idx.columns if 'jci' in c.lower() or 'close' in c.lower()), None)
            if date_col and price_col_idx:
                idx[date_col] = pd.to_datetime(idx[date_col], errors='coerce')
                idx = idx.dropna(subset=[date_col, price_col_idx]).sort_values(date_col)
                idx['date_str'] = idx[date_col].dt.strftime('%Y-%m-%d')

                # Filter index to match chart date range
                chart_dates = set(df_plot['date_str'].tolist())
                idx_filtered = idx[idx['date_str'].isin(chart_dates)].copy()

                if not idx_filtered.empty:
                    # Normalize: set first value = 100
                    base_val = float(idx_filtered[price_col_idx].iloc[0])
                    if base_val > 0:
                        idx_filtered['jci_norm'] = idx_filtered[price_col_idx] / base_val * 100

                        # Get stock price range to scale index overlay to same y-axis
                        price_min = df_plot['close'].min()
                        price_max = df_plot['close'].max()
                        price_range = price_max - price_min if price_max != price_min else price_max * 0.5

                        stock_base = float(
                            df_plot[df_plot['date_str'] == idx_filtered['date_str'].iloc[0]]['close'].iloc[0]) \
                            if idx_filtered['date_str'].iloc[0] in chart_dates else df_plot['close'].iloc[0]

                        # Scale index to stock price space: same % change from first point
                        idx_filtered['jci_scaled'] = stock_base * (idx_filtered['jci_norm'] / 100)

                        fig.add_trace(go.Scatter(
                            x=idx_filtered['date_str'],
                            y=idx_filtered['jci_scaled'],
                            mode='lines',
                            name='VNINDEX',
                            line=dict(color='#fbbf24', width=1.5, dash='dot'),
                            opacity=0.75,
                            hovertemplate='<b>VNINDEX:</b> %{customdata:.1f} pts<extra></extra>',
                            customdata=idx_filtered[price_col_idx],
                            yaxis='y1',
                        ), row=1, col=1)
        except Exception as e:
            pass  # Fail silently — index overlay is optional

    return fig