# src/callbacks/tplus_callbacks.py
"""
T+2.5 Score toggle — bật/tắt chế độ xem điểm lướt sóng ngắn hạn.
Khi ON: thêm cột T_Plus_Score + các cột kỹ thuật liên quan vào bảng.
"""
from dash import Input, Output, State, no_update, callback_context
from src.app_instance import app

# ── Định nghĩa các cột sẽ inject vào bảng khi toggle ON ─────────
TPLUS_COLS = [
    {
        "field": "T_Plus_Score",
        "headerName": "Điểm T+2.5",
        "headerTooltip": "Điểm tăng T+2.5 (0–100). ≥80 = tín hiệu/xác suất tăng giá mạnh.",
        "type": "rightAligned",
        "sortable": True,
        "width": 110,
        "valueFormatter": {
            "function": "params.value != null ? params.value.toFixed(0) + ' đ' : '-'"
        },
        "cellStyle": {
            "function": """
                if (params.value == null) return {'color':'#484f58'};
                if (params.value >= 80) return {
                    'color': '#00d4ff', 'fontWeight': '800',
                    'backgroundColor': 'rgba(0,212,255,0.08)',
                    'textShadow': '0 0 8px rgba(0,212,255,0.5)'
                };
                if (params.value >= 60) return {'color': '#3b82f6', 'fontWeight': '700'};
                if (params.value >= 40) return {'color': '#f59e0b'};
                return {'color': '#484f58'};
            """
        },
    },
    {
        "field": "Vol_vs_SMA20",
        "headerName": "KL/SMA20",
        "headerTooltip": "Khối lượng hôm nay so với SMA20. ≥1.5 = đột biến dòng tiền.",
        "type": "rightAligned",
        "sortable": True,
        "width": 105,
        "valueFormatter": {
            "function": "params.value != null ? d3.format(',.2f')(params.value) + 'x' : '-'"
        },
        "cellStyle": {
            "function": """
                if (!params.value) return {'color':'#484f58'};
                if (params.value >= 1.5) return {'color':'#10b981','fontWeight':'700'};
                if (params.value >= 1.2) return {'color':'#f59e0b'};
                return {'color':'#484f58'};
            """
        },
    },
    {
        "field": "Price_vs_SMA5",
        "headerName": "vs SMA5",
        "headerTooltip": "% giá so với SMA5. Dương = giá trên MA ngắn hạn.",
        "type": "rightAligned",
        "sortable": True,
        "width": 95,
        "valueFormatter": {
            "function": "params.value != null ? (params.value > 0 ? '+' : '') + d3.format('.1f')(params.value) + '%' : '-'"
        },
        "cellStyle": {
            "function": """
                if (params.value == null) return {'color':'#484f58'};
                return params.value > 0
                    ? {'color':'#10b981','fontWeight':'600'}
                    : {'color':'#ef4444'};
            """
        },
    },
    {
        "field": "MACD_Histogram",
        "headerName": "MACD Hist",
        "headerTooltip": "MACD Histogram. Dương = phe mua kiểm soát.",
        "type": "rightAligned",
        "sortable": True,
        "width": 105,
        "valueFormatter": {
            "function": "params.value != null ? d3.format(',.2f')(params.value) : '-'"
        },
        "cellStyle": {
            "function": """
                if (params.value == null) return {};
                return params.value > 0
                    ? {'color':'#10b981','fontWeight':'600'}
                    : {'color':'#ef4444','fontWeight':'600'};
            """
        },
    },
    {
        "field": "RS_3D",
        "headerName": "RS 3N",
        "headerTooltip": "Sức mạnh tương đối 3 phiên. Dương = khỏe hơn thị trường.",
        "type": "rightAligned",
        "sortable": True,
        "width": 90,
        "valueFormatter": {
            "function": "params.value != null ? (params.value > 0 ? '+' : '') + d3.format('.2f')(params.value) + '%' : '-'"
        },
        "cellStyle": {
            "function": """
                if (params.value == null) return {'color':'#484f58'};
                return params.value > 0
                    ? {'color':'#10b981','fontWeight':'600'}
                    : {'color':'#ef4444'};
            """
        },
    },
    {
        "field": "RSI_14",
        "headerName": "RSI(14)",
        "headerTooltip": "RSI 14 phiên. Vùng 45–65 = dư địa tăng cho T+.",
        "type": "rightAligned",
        "sortable": True,
        "width": 90,
        "valueFormatter": {
            "function": "params.value != null ? d3.format('.1f')(params.value) : '-'"
        },
        "cellStyle": {
            "function": """
                if (params.value == null) return {};
                if (params.value >= 70) return {'color':'#ef4444','fontWeight':'700'};
                if (params.value <= 30) return {'color':'#10b981','fontWeight':'700'};
                if (params.value >= 45 && params.value <= 65)
                    return {'color':'#00d4ff','fontWeight':'600'};
                return {'color':'#c9d1d9'};
            """
        },
    },
]


# ── CALLBACK 1: Toggle ON/OFF — cập nhật store + visual switch ──
@app.callback(
    Output("tplus-mode-store",    "data"),
    Output("tplus-toggle-track",  "style"),
    Output("tplus-toggle-thumb",  "style"),
    Input("tplus-toggle-track",   "n_clicks"),
    State("tplus-mode-store",     "data"),
    prevent_initial_call=True,
)
def toggle_tplus_mode(n_clicks, current_state):
    is_on = not bool(current_state)

    # Style track
    track_on = {
        "width": "36px", "height": "18px", "borderRadius": "9px",
        "backgroundColor": "rgba(0,212,255,0.25)",
        "border": "1px solid rgba(0,212,255,0.6)",
        "position": "relative", "cursor": "pointer",
        "transition": "all 0.2s ease",
        "boxShadow": "0 0 8px rgba(0,212,255,0.3)",
    }
    track_off = {
        "width": "36px", "height": "18px", "borderRadius": "9px",
        "backgroundColor": "#1e2d3d",
        "border": "1px solid #30363d",
        "position": "relative", "cursor": "pointer",
        "transition": "all 0.2s ease",
    }

    # Style thumb
    thumb_on = {
        "width": "12px", "height": "12px", "borderRadius": "50%",
        "backgroundColor": "#00d4ff",
        "position": "absolute", "top": "2px", "left": "20px",
        "transition": "all 0.2s ease",
        "boxShadow": "0 0 6px rgba(0,212,255,0.6)",
    }
    thumb_off = {
        "width": "12px", "height": "12px", "borderRadius": "50%",
        "backgroundColor": "#484f58",
        "position": "absolute", "top": "2px", "left": "2px",
        "transition": "all 0.2s ease",
    }

    return (
        is_on,
        track_on  if is_on else track_off,
        thumb_on  if is_on else thumb_off,
    )


# ── CALLBACK 2: Inject/remove cột T+ vào columnDefs ────────────
@app.callback(
    Output("screener-table", "columnDefs", allow_duplicate=True),
    Input("tplus-mode-store", "data"),
    State("screener-table",   "columnDefs"),
    prevent_initial_call=True,
)
def inject_tplus_columns(is_on, current_cols):
    if current_cols is None:
        return no_update

    # Lấy field names của T+ cols
    tplus_fields = {c["field"] for c in TPLUS_COLS}

    # Xóa hết T+ cols cũ (nếu có) để tránh trùng
    base_cols = [c for c in current_cols if c.get("field") not in tplus_fields]

    if not is_on:
        return base_cols

    # Khi ON: chèn T_Plus_Score ngay sau cột "Star_Rating" (hoặc cột cuối của FIXED_COLS)
    result = []
    inserted = False
    for col in base_cols:
        result.append(col)
        if col.get("field") == "Star_Rating" and not inserted:
            result.extend(TPLUS_COLS)
            inserted = True

    # Fallback: nếu không tìm thấy Star_Rating, append vào cuối
    if not inserted:
        result.extend(TPLUS_COLS)

    return result