# src/callbacks/strategy_callbacks.py
from dash import Input, Output, State, html, no_update, callback_context
import pandas as pd
from src.app_instance import app
from src.backend.data_loader import get_latest_snapshot, load_financial_data
from src.backend.quant_engine_strategies import run_strategy, STRATEGY_META
import logging
from dash.exceptions import PreventUpdate
import json
from dash import ALL

logger = logging.getLogger(__name__)


# @app.callback(
#     [Output("screener-table", "rowData",   allow_duplicate=True),
#      Output("result-count",   "children",  allow_duplicate=True),
#      Output("filter-stats",   "children",  allow_duplicate=True)],
#     Input("strategy-preset-dropdown", "value"),
#     prevent_initial_call=True
# )
# def apply_strategy_preset(strategy_id):
#     if not strategy_id:
#         return no_update, no_update, no_update

#     try:
#         logger.info(f"📊 Áp dụng chiến lược: {strategy_id}")

#         # Load snapshot (giá + BCTC kỳ mới nhất)
#         records = get_latest_snapshot()
#         if not records:
#             return [], "⚠️ Không có dữ liệu", "Vui lòng kiểm tra file data"

#         df = pd.DataFrame(records)
#         total = len(df)

#         # Load TOÀN BỘ lịch sử BCTC để tính growth đa kỳ
#         logger.info("   📂 Đang load lịch sử BCTC để tính chỉ số đa kỳ...")
#         try:
#             df_fin = load_financial_data('yearly')
#             if df_fin is None or df_fin.empty:
#                 logger.warning("   ⚠️ df_fin rỗng – các chỉ số đa kỳ sẽ là NaN")
#                 df_fin = None
#             else:
#                 logger.info(f"   ✅ df_fin: {len(df_fin):,} dòng, {df_fin['Ticker'].nunique()} tickers")
#         except Exception as e:
#             logger.warning(f"   ⚠️ Không load được df_fin: {e}")
#             df_fin = None

#         # Chạy chiến lược với lịch sử BCTC
#         df_result = run_strategy(df, strategy_id, df_fin=df_fin)

#         # Làm sạch trước khi serialize JSON
#         df_result = df_result.replace([float('inf'), float('-inf')], None)
#         safe_cols = []
#         for col in df_result.columns:
#             try:
#                 df_result[[col]].to_json()
#                 safe_cols.append(col)
#             except Exception:
#                 pass
#         df_result = df_result[safe_cols]

#         row_data = df_result.to_dict("records")
#         count    = len(row_data)

#         meta = STRATEGY_META.get(strategy_id, {})
#         name = meta.get("name", strategy_id)
#         icon = meta.get("icon", "📋")

#         result_msg = f"{icon} {name}: {count} mã phù hợp (/{total} mã)"
#         stats_msg  = (f"Chiến lược '{name}' | Lọc {count}/{total} mã "
#                       f"({count/total*100:.1f}%)" if total > 0 else "Không có dữ liệu")

#         logger.info(f"✅ {strategy_id}: {count}/{total} mã")
#         return row_data, result_msg, stats_msg

#     except Exception as e:
#         logger.error(f"❌ Lỗi apply_strategy_preset: {e}")
#         import traceback; traceback.print_exc()
#         return [], f"❌ Lỗi: {str(e)}", "Vui lòng thử lại"


#@app.callback(
#    Output("result-count-number", "children", allow_duplicate=True),
#    Input("strategy-preset-dropdown", "value"),
#    State("screener-table", "rowData"),
#    prevent_initial_call=True
#)
def sync_result_count_sidebar(strategy_id, current_row_data):
    if not strategy_id or current_row_data is None:
        return no_update
    return str(len(current_row_data))


@app.callback(
    Output("strategy-preset-dropdown", "value", allow_duplicate=True),
    Input("btn-reset-ui", "n_clicks"),
    prevent_initial_call=True
)
def reset_strategy_dropdown(n_clicks):
    return None if n_clicks else no_update

from src.components.sidebar import _STRATEGY_LABEL_MAP, _STRATEGY_GROUPS


# ── Bấm vào strategy item → cập nhật hidden dropdown + đóng popover ───────
@app.callback(
    Output("strategy-preset-dropdown",   "value",    allow_duplicate=True),
    Output("strategy-accordion-popover", "is_open",  allow_duplicate=True),
    Output("strategy-display-label",     "children", allow_duplicate=True),
    Input({"type": "strategy-item", "value": ALL}, "n_clicks"),
    prevent_initial_call=True,
)
def select_strategy_from_accordion(n_clicks_list):
    ctx = callback_context
    if not ctx.triggered or not any(n for n in (n_clicks_list or []) if n):
        return no_update, no_update, no_update
    try:
        strat_val   = json.loads(ctx.triggered[0]["prop_id"].split(".")[0])["value"]
        strat_label = _STRATEGY_LABEL_MAP.get(strat_val, strat_val)
        return strat_val, False, strat_label
    except Exception:
        return no_update, no_update, no_update


# ── Toggle từng group accordion ───────────────────────────────────────────
@app.callback(
    [Output(f"strategy-grp-collapse-{g['id']}", "is_open") for g in _STRATEGY_GROUPS]
    + [Output(f"strategy-grp-icon-{g['id']}", "className") for g in _STRATEGY_GROUPS],
    [Input(f"strategy-grp-hdr-{g['id']}", "n_clicks") for g in _STRATEGY_GROUPS],
    [State(f"strategy-grp-collapse-{g['id']}", "is_open") for g in _STRATEGY_GROUPS],
    prevent_initial_call=True,
)
def toggle_strategy_group(*args):
    n = len(_STRATEGY_GROUPS)
    n_clicks_list = args[:n]
    states        = args[n:]

    ctx = callback_context
    if not ctx.triggered:
        return [no_update] * (n * 2)

    triggered_id = ctx.triggered[0]["prop_id"].split(".")[0]

    new_opens = list(states)
    for i, group in enumerate(_STRATEGY_GROUPS):
        if triggered_id == f"strategy-grp-hdr-{group['id']}":
            new_opens[i] = not states[i]
            break

    icons = [
        "fas fa-minus" if is_open else "fas fa-plus"
        for is_open in new_opens
    ]
    icon_classes = [
        f"{icon} strategy-grp-icon"
        for icon in icons
    ]

    return new_opens + icon_classes


# ── Sync display label khi dropdown value thay đổi từ nguồn ngoài ─────────
@app.callback(
    Output("strategy-display-label", "children", allow_duplicate=True),
    Input("strategy-preset-dropdown", "value"),
    prevent_initial_call=True,
)
def sync_strategy_display_label(value):
    if not value:
        return "Chọn chiến lược đầu tư..."
    return _STRATEGY_LABEL_MAP.get(value, value)


# =============================================================================
# NOTIFICATION: Strategy Match — cập nhật card top-1 khi chọn trường phái
# =============================================================================
from src.app_instance import app as _app  # đã import app ở đầu file, dòng này để rõ nghĩa

@app.callback(
    Output("strategy-match-title",         "children"),
    Output("strategy-match-detail",        "children"),
    Output("strategy-match-date",          "children"),
    Output("strategy-match-note",          "children"),
    Output("strategy-match-ticker-store",  "data"),
    Output("notif-dot",                    "style", allow_duplicate=True),
    Output("strategy-match",               "style"),          # ← THÊM
    Output("strategy-match",               "data-dismissed"), # ← THÊM
    Input("strategy-preset-dropdown", "value"),
    State("trading-mode-store",       "data"),
    prevent_initial_call=True,
)
def update_strategy_match_notification(strategy_id, trading_mode):
    import datetime
    if not strategy_id:
        return no_update, no_update, no_update, no_update, no_update, no_update, {}, "0"

    _mode_label_map = {
        "all_market": "Toàn TT", "tich_san": "Tích sản",
    }
    mode_label = _mode_label_map.get(trading_mode, trading_mode or "Toàn TT")
    note = (f"Kết quả tính trên TOÀN BỘ thị trường, không phụ thuộc chế độ đang chọn "
            f"(hiện tại: {mode_label}).")

    try:
        records = get_latest_snapshot()
        if not records:
            raise ValueError("Không có snapshot")

        df = pd.DataFrame(records)
        try:
            df_fin = load_financial_data('yearly')
        except Exception:
            df_fin = None

        df_result = run_strategy(df, strategy_id, df_fin=df_fin)
        now_str = datetime.datetime.now().strftime("%d/%m/%Y · %H:%M")

        if df_result is None or df_result.empty:
            meta = STRATEGY_META.get(strategy_id, {})
            name = meta.get("name", strategy_id)
            return (f"Chưa có mã nào thỏa chiến lược {name}",
                    "Thử điều chỉnh lại bộ lọc hoặc chọn chiến lược khác.",
                    now_str, note, None, {"display": "block"}, {}, "0")

        if 'FSS_Smart_Rank' in df_result.columns:
            df_result = df_result.sort_values('FSS_Smart_Rank', ascending=False)

        top1 = df_result.iloc[0]
        ticker = str(top1.get('Ticker', '')).strip()
        vgm    = top1.get('VGM_Score_Pct', top1.get('FSS_Smart_Rank', 0))
        roe    = top1.get('ROE', None)
        growth = top1.get('Growth Score', '')

        meta = STRATEGY_META.get(strategy_id, {})
        strat_name = meta.get("name", strategy_id)

        title = f"{ticker} vừa thỏa chiến lược {strat_name}"
        detail_parts = [f"FSS Score {int(vgm)}" if vgm else None]
        if roe is not None:
            detail_parts.append(f"ROE {roe:.1f}%")
        if growth:
            detail_parts.append(f"Growth Score {growth}")
        detail = " · ".join(p for p in detail_parts if p)

        return title, detail, now_str, note, ticker, {"display": "block"}, {}, "0"

    except Exception as e:
        logger.error(f"❌ Lỗi update_strategy_match_notification: {e}")
        return no_update, no_update, no_update, no_update, no_update, no_update, {}, "0"


@app.callback(
    Output("detail-modal",           "is_open", allow_duplicate=True),
    Output("modal-title",            "children", allow_duplicate=True),
    Output("selected-stock-store",   "data",     allow_duplicate=True),
    Output("selected-ticker-store",  "data",     allow_duplicate=True),
    Input("strategy-match",  "n_clicks"),
    State("strategy-match-ticker-store", "data"),
    prevent_initial_call=True,
)
def open_ticker_from_strategy_match(n_clicks, ticker):
    if not n_clicks or not ticker:
        raise PreventUpdate

    records = get_latest_snapshot()
    if not records:
        raise PreventUpdate

    df = pd.DataFrame(records)
    match = df[df['Ticker'] == ticker]
    if match.empty:
        raise PreventUpdate

    stock = match.iloc[0].to_dict()
    company_name = stock.get('Company Common Name', '') or ticker
    title_text = f"Cổ phiếu {ticker} – {company_name}"

    return True, title_text, stock, ticker