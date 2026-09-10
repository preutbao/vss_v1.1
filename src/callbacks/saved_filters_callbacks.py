from dash import Input, Output, State, ALL, MATCH, html, no_update, callback_context
from dash.exceptions import PreventUpdate
import json
from src.app_instance import app


# ── Mở/đóng modal Quản lý bộ lọc ──────────────────────────────────────────
@app.callback(
    Output("filter-manager-modal", "is_open", allow_duplicate=True),
    Input("btn-manage-filters", "n_clicks"),
    prevent_initial_call=True,
)
def open_filter_manager_modal(n_clicks):
    if not n_clicks:
        raise PreventUpdate
    return True


# ── Chuyển tab Cá nhân / Cộng đồng ─────────────────────────────────────────
@app.callback(
    Output("fm-tab-personal",  "className"),
    Output("fm-tab-community", "className"),
    Output("fm-panel-personal",  "style"),
    Output("fm-panel-community", "style"),
    Input("fm-tab-personal",  "n_clicks"),
    Input("fm-tab-community", "n_clicks"),
    prevent_initial_call=True,
)
def switch_filter_manager_tab(n1, n2):
    ctx = callback_context
    if not ctx.triggered:
        raise PreventUpdate
    trigger = ctx.triggered[0]["prop_id"]

    if "fm-tab-community" in trigger:
        return "fm-tab", "fm-tab is-active", {"display": "none"}, {"display": "flex", "flexDirection": "column", "gap": "6px", "position": "relative"}
    return "fm-tab is-active", "fm-tab", {"display": "flex", "flexDirection": "column", "gap": "6px"}, {"display": "none"}


# ── Toggle kebab menu từng dòng (đóng menu khác khi mở menu mới) ──────────
app.clientside_callback(
    """
    function(n_clicks_list) {
        var ctx = window.dash_clientside.callback_context;
        if (!ctx.triggered || !ctx.triggered.length) {
            return window.dash_clientside.no_update;
        }
        var triggered_id = ctx.triggered[0].prop_id.split('.')[0];
        try {
            var parsed = JSON.parse(triggered_id);
            var idStr = JSON.stringify(parsed);
            var btn = document.querySelector('[id=\\'' + idStr + '\\']');
            var menu = btn ? btn.parentElement.querySelector('.fm-kebab-menu') : null;

            // Đóng tất cả menu khác trước
            document.querySelectorAll('.fm-kebab-menu').forEach(function(m) {
                if (m !== menu) m.style.display = 'none';
            });

            if (menu) {
                menu.style.display = (menu.style.display === 'none' || !menu.style.display)
                    ? 'block' : 'none';
            }
        } catch (e) {}
        return window.dash_clientside.no_update;
    }
    """,
    Output("filter-manager-modal", "title"),   # output giả
    Input({"type": "fm-kebab-btn", "scope": ALL, "idx": ALL}, "n_clicks"),
    prevent_initial_call=True,
)


# ── Toggle popover filter Cộng đồng ────────────────────────────────────────
app.clientside_callback(
    """
    function(n_clicks) {
        if (!n_clicks) return window.dash_clientside.no_update;
        var panel = document.getElementById('fm-community-filter-panel');
        if (panel) {
            panel.style.display = (panel.style.display === 'none' || !panel.style.display)
                ? 'block' : 'none';
        }
        return window.dash_clientside.no_update;
    }
    """,
    Output("btn-fm-community-filter", "title"),   # output giả
    Input("btn-fm-community-filter",  "n_clicks"),
    prevent_initial_call=True,
)

from dash import Input, Output, State, ALL, MATCH, html, no_update, callback_context
from dash.exceptions import PreventUpdate
import json
from src.app_instance import app
from src.components.sidebar import MOCK_PERSONAL_FILTERS, MOCK_COMMUNITY_FILTERS

# Danh sách filter store id mà bất kỳ mock filter nào (personal/community) có thể ghi vào —
# hợp nhất từ tất cả filter_values dict ở trên. Output cố định, per-request chỉ điền các
# key thật sự nằm trong preset được click, còn lại trả no_update (giữ nguyên filter khác
# đang active — không reset toàn bộ sidebar).
_FM_WIRED_FILTER_IDS = [
    "filter-roe", "filter-pe", "filter-pb", "filter-de", "filter-div-yield",
    "filter-current-ratio", "filter-eps-growth-yoy", "filter-rev-growth-yoy",
    "filter-net-margin", "filter-rsi14", "filter-vol-vs-sma20", "filter-market-cap",
]


def _apply_filter_outputs(filter_values: dict) -> list:
    """Trả về list giá trị theo đúng thứ tự _FM_WIRED_FILTER_IDS —
    điền giá trị nếu preset có, còn lại no_update."""
    return [filter_values.get(fid, no_update) for fid in _FM_WIRED_FILTER_IDS]


@app.callback(
    [Output(fid, "data", allow_duplicate=True) for fid in _FM_WIRED_FILTER_IDS] +
    [Output("filter-manager-modal", "is_open", allow_duplicate=True),
     Output("login-modal", "is_open", allow_duplicate=True)],   # ← THÊM
    Input({"type": "fm-apply-filter", "scope": ALL, "idx": ALL}, "n_clicks"),
    Input({"type": "fm-copy-personal", "idx": ALL}, "n_clicks"),
    State("auth-store", "data"),   # ← THÊM
    prevent_initial_call=True,
)
def apply_saved_or_community_filter(apply_clicks, copy_clicks, auth_data):
    ctx = callback_context
    if not ctx.triggered or not any(
        c for c in (list(apply_clicks or []) + list(copy_clicks or [])) if c
    ):
        raise PreventUpdate

    trigger_id_str = ctx.triggered[0]["prop_id"].split(".")[0]
    try:
        trigger = json.loads(trigger_id_str)
    except Exception:
        raise PreventUpdate

    ttype = trigger.get("type")
    idx = trigger.get("idx")

    # ── LOGIN GATE (không cần VIP): "Lưu/theo dõi bộ lọc của người khác"
    # chỉ yêu cầu đã đăng nhập, theo đúng bảng phân quyền — khác VIP-only. ──
    is_logged_in = bool(auth_data and auth_data.get("logged_in"))

    if ttype == "fm-copy-personal" and not is_logged_in:
        no_filter_updates = [no_update] * len(_FM_WIRED_FILTER_IDS)
        return no_filter_updates + [no_update, True]   # mở login-modal, giữ nguyên filter-manager-modal

    if ttype == "fm-apply-filter":
        scope = trigger.get("scope")
        if scope == "personal":
            if idx == 0:
                raise PreventUpdate
            preset = MOCK_PERSONAL_FILTERS[idx]
        else:
            preset = MOCK_COMMUNITY_FILTERS[idx]
    elif ttype == "fm-copy-personal":
        preset = MOCK_COMMUNITY_FILTERS[idx]
    else:
        raise PreventUpdate

    outputs = _apply_filter_outputs(preset.get("filter_values", {}))
    return outputs + [False, no_update]   # đóng filter-manager-modal, không đụng login-modal

# Row "Bộ lọc mặc định" → giả lập click nút Reset có sẵn của sidebar (btn-reset),
# tận dụng logic reset đã có sẵn trong filter_interaction_callbacks.py thay vì
# đoán lại "giá trị rỗng" đúng của từng Store (rủi ro nếu đoán sai convention).
app.clientside_callback(
    """
    function(n_clicks) {
        if (!n_clicks) return window.dash_clientside.no_update;
        var resetBtn = document.getElementById('btn-reset');
        if (resetBtn) resetBtn.click();
        var modal = document.getElementById('filter-manager-modal');
        // Đóng modal bằng cách bấm nút close có sẵn của dbc.Modal (an toàn hơn set style tay)
        var closeBtn = modal ? modal.querySelector('.btn-close') : null;
        if (closeBtn) closeBtn.click();
        return window.dash_clientside.no_update;
    }
    """,
    Output({"type": "fm-apply-filter", "scope": "personal", "idx": 0}, "title"),  # output giả
    Input({"type": "fm-apply-filter", "scope": "personal", "idx": 0}, "n_clicks"),
    prevent_initial_call=True,
)

# ── Reset popover filter (Theo người dùng / Thời gian lọc) ────────────────
@app.callback(
    Output("fm-community-user-filter", "value"),
    Output("fm-community-time-filter", "value"),
    Input("btn-fm-filter-reset", "n_clicks"),
    prevent_initial_call=True,
)
def reset_community_filter_popover(n_clicks):
    if not n_clicks:
        raise PreventUpdate
    return None, None


# ── Áp dụng popover filter: lọc danh sách card cộng đồng theo tác giả ─────
app.clientside_callback(
    """
    function(n_clicks, selected_author) {
        if (!n_clicks) return window.dash_clientside.no_update;

        var rows = document.querySelectorAll('#fm-panel-community .fm-row');
        rows.forEach(function(row) {
            if (!selected_author) {
                row.style.display = '';
                return;
            }
            var authorEl = row.querySelector('.fm-row-author');
            var match = authorEl && authorEl.textContent.trim() === ('@' + selected_author);
            row.style.display = match ? '' : 'none';
        });

        // Đóng popover sau khi áp dụng
        var panel = document.getElementById('fm-community-filter-panel');
        if (panel) panel.style.display = 'none';

        return window.dash_clientside.no_update;
    }
    """,
    Output("btn-fm-filter-apply", "title"),   # output giả
    Input("btn-fm-filter-apply", "n_clicks"),
    State("fm-community-user-filter", "value"),
    prevent_initial_call=True,
)