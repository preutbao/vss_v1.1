# src/callbacks/auth_callbacks.py
# ─────────────────────────────────────────────────────────────────────────────
# Xử lý toàn bộ luồng đăng nhập / đăng xuất + cập nhật premium gates
# ─────────────────────────────────────────────────────────────────────────────

import json
import os
import logging
from dash import Input, Output, State, callback_context, no_update, html, ALL
from dash.exceptions import PreventUpdate
import dash_bootstrap_components as dbc

from src.app_instance import app

logger = logging.getLogger(__name__)

# ── Đường dẫn file users.json ────────────────────────────────────────────────
_BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
USERS_FILE = os.path.join(_BASE_DIR, '..', '..', 'data', 'users.json')


def _load_users() -> dict:
    """Đọc danh sách users từ file JSON."""
    try:
        with open(USERS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Không thể đọc users.json: {e}")
        return {}


def _is_vip(auth_data: dict | None) -> bool:
    """Trả về True nếu user đã đăng nhập và có tier vip."""
    return bool(
        auth_data
        and auth_data.get('logged_in')
        and auth_data.get('tier') == 'vip'
    )


# =============================================================================
# 1. MỞ / ĐÓNG LOGIN MODAL
#    Trigger: nút "Đăng nhập" trên navbar hoặc click premium overlay
# =============================================================================
@app.callback(
    Output('login-modal', 'is_open'),
    [
        Input('btn-login', 'n_clicks'),
        Input('btn-close-login', 'n_clicks'),
        Input('login-submit-btn', 'n_clicks'),
        Input({'type': 'premium-overlay-btn', 'section': ALL}, 'n_clicks'),
    ],
    [State('login-modal', 'is_open'),
     State('auth-store', 'data')],
    prevent_initial_call=True,
)
def toggle_login_modal(open_n, close_n, submit_n, overlay_clicks, is_open, auth_data):
    ctx = callback_context
    if not ctx.triggered:
        raise PreventUpdate

    trigger_id = ctx.triggered[0]['prop_id']

    # Nếu đã đăng nhập → click btn-login sẽ mở user dropdown (xử lý ở callback khác)
    # Ở đây chỉ đóng modal khi đã đăng nhập
    if 'btn-login' in trigger_id:
        if auth_data and auth_data.get('logged_in'):
            return False
        return True

    if 'btn-close-login' in trigger_id:
        return False

    if 'login-submit-btn' in trigger_id:
        # Đóng modal — kết quả thành công / thất bại xử lý ở callback xác thực
        return False

    # Click vào bất kỳ premium overlay nào
    if 'premium-overlay-btn' in trigger_id:
        any_clicked = any(c and c > 0 for c in (overlay_clicks or []))
        if any_clicked:
            return True

    return is_open


# =============================================================================
# 2. XỬ LÝ ĐĂNG NHẬP (validate + cập nhật auth-store)
# =============================================================================
@app.callback(
    [
        Output('auth-store', 'data'),
        Output('login-error-msg', 'children'),
        Output('login-error-msg', 'style'),
        Output('login-modal', 'is_open', allow_duplicate=True),
    ],
    Input('login-submit-btn', 'n_clicks'),
    [
        State('login-username', 'value'),
        State('login-password', 'value'),
    ],
    prevent_initial_call=True,
)
def handle_login(n_clicks, username, password):
    if not n_clicks:
        raise PreventUpdate

    _error_style_show = {
        "display": "block",
        "color": "#f85149",
        "fontSize": "12px",
        "marginTop": "8px",
        "padding": "8px 12px",
        "background": "rgba(248,81,73,0.08)",
        "border": "1px solid rgba(248,81,73,0.25)",
        "borderRadius": "6px",
    }
    _error_style_hide = {"display": "none"}

    if not username or not password:
        return no_update, "Vui lòng nhập đầy đủ tên đăng nhập và mật khẩu.", _error_style_show, True

    users = _load_users()

    if username in users and users[username]['password'] == password:
        auth_data = {
            "logged_in": True,
            "username": username,
            "tier": users[username].get('tier', 'free'),
            "display_name": users[username].get('display_name', username),
        }
        logger.info(f"✅ Đăng nhập thành công: {username} ({auth_data['tier']})")
        return auth_data, "", _error_style_hide, False  # đóng modal khi login OK
    else:
        return no_update, "Tên đăng nhập hoặc mật khẩu không chính xác.", _error_style_show, True


# =============================================================================
# 3. ĐĂNG XUẤT
# =============================================================================
@app.callback(
    Output('auth-store', 'data', allow_duplicate=True),
    Input('btn-logout', 'n_clicks'),
    prevent_initial_call=True,
)
def handle_logout(n_clicks):
    if not n_clicks:
        raise PreventUpdate
    logger.info("🚪 Người dùng đã đăng xuất.")
    return {"logged_in": False}


# =============================================================================
# 4. CẬP NHẬT NÚT TRÊN NAVBAR (Đăng nhập ↔ Tên user)
# =============================================================================
@app.callback(
    [
        Output('btn-login', 'children'),
        Output('btn-login', 'className'),
        Output('navbar-user-menu', 'style'),
        Output('navbar-user-name', 'children'),
    ],
    Input('auth-store', 'data'),
)
def update_navbar_auth(auth_data):
    if auth_data and auth_data.get('logged_in'):
        display_name = auth_data.get('display_name', auth_data.get('username', ''))
        tier         = auth_data.get('tier', 'free')

        # Nút: ẩn đi (user đã đăng nhập thì hiện user-menu thay thế)
        btn_children  = [html.I(className="fas fa-user-circle",
                                style={"marginRight": "5px"}), display_name]
        btn_class     = "vietcap-nav-user-btn"

        # Hiện user menu
        menu_style = {"display": "flex", "alignItems": "center", "gap": "8px"}

        # Badge VIP
        badge = html.Span("VIP", className="vip-badge") if tier == 'vip' else None
        user_label = [
            html.I(className="fas fa-user-circle",
                   style={"color": "#00a651", "fontSize": "14px"}),
            html.Span(display_name,
                      style={"fontSize": "12px", "color": "#c9d1d9", "fontWeight": "600"}),
        ]
        if badge:
            user_label.append(badge)

        return btn_children, btn_class, {"display": "none"}, user_label

    # Chưa đăng nhập
    btn_children = [html.I(className="fas fa-sign-in-alt",
                           style={"marginRight": "5px"}), "Đăng nhập"]
    btn_class    = "vietcap-nav-login-btn"
    return btn_children, btn_class, {"display": "none"}, []


# =============================================================================
# 5. PREMIUM GATES — cập nhật className của tất cả wrapper
#    Danh sách premium-wrapper IDs:
#      pw-compare   → Nút "So sánh"
#      pw-portfolio → Nút "Danh mục"
#      pw-alerts    → Nút "Cảnh báo"
#      pw-strategies → Dropdown trường phái
#      pw-momentum  → Nhóm "Hành vi thị trường" trong wizard
# =============================================================================
_PREMIUM_WRAPPERS = [
    'pw-compare',
    'pw-portfolio',
    'pw-alerts',
    'pw-strategies',
    'pw-momentum',
]

@app.callback(
    [Output(pw_id, 'className') for pw_id in _PREMIUM_WRAPPERS],
    Input('auth-store', 'data'),
)
def update_premium_gates(auth_data):
    unlocked = 'premium-wrapper premium-unlocked'
    locked   = 'premium-wrapper premium-locked'
    state    = unlocked if _is_vip(auth_data) else locked
    return [state] * len(_PREMIUM_WRAPPERS)


# =============================================================================
# 6. HIỆN / ẨN NÚT "ĐĂNG NHẬP" vs "ĐĂNG XUẤT" trên navbar
# =============================================================================
@app.callback(
    [
        Output('btn-login', 'style'),
        Output('btn-logout-wrap', 'style'),
    ],
    Input('auth-store', 'data'),
)
def toggle_auth_buttons(auth_data):
    logged_in = auth_data and auth_data.get('logged_in')
    if logged_in:
        return {"display": "none"}, {"display": "flex", "alignItems": "center", "gap": "8px"}
    return {}, {"display": "none"}
