# src/callbacks/strategy_callbacks.py
from dash import Input, Output, State, html, no_update
import pandas as pd
from src.app_instance import app
from src.backend.data_loader import get_latest_snapshot, load_financial_data
from src.backend.quant_engine_strategies import run_strategy, STRATEGY_META
import logging

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