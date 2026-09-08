from dash import Input, Output, State, ALL, MATCH, html, no_update, callback_context
from dash.exceptions import PreventUpdate
import json
from src.app_instance import app


# ── Mở/đóng modal Quản lý bộ lọc ──────────────────────────────────────────
@app.callback(
    Output("filter-manager-modal", "is_open"),
    Input("btn-manage-filters",        "n_clicks"),
    Input("btn-close-filter-manager",  "n_clicks"),
    State("filter-manager-modal",      "is_open"),
    prevent_initial_call=True,
)
def toggle_filter_manager_modal(n_open, n_close, is_open):
    ctx = callback_context
    if not ctx.triggered:
        raise PreventUpdate
    trigger = ctx.triggered[0]["prop_id"]
    if "btn-manage-filters" in trigger:
        return True
    return False


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