# src/callbacks/auth_callbacks.py
# ─────────────────────────────────────────────────────────────────────────────
# Xử lý toàn bộ luồng đăng nhập / đăng xuất + cập nhật premium gates
# ─────────────────────────────────────────────────────────────────────────────

import json
import os
import logging
from dash import dcc, Input, Output, State, callback_context, no_update, html, ALL
from dash.exceptions import PreventUpdate
import dash_bootstrap_components as dbc
from werkzeug.security import check_password_hash, generate_password_hash

from src.app_instance import app
from src.components.header import _get_avatar_color
from src.backend.rate_limiter import check_rate_limit, reset_rate_limit, get_client_ip

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


def require_entitlement(auth_data: dict | None, tier: str = "vip") -> bool:
    """
    AUDIT FIX (mục 4 - Authentication, Major Issue): hàm bảo vệ endpoint
    premium DÙNG CHUNG, thay cho việc mỗi callback (screener_callbacks.py,
    chatbot_callbacks.py...) tự viết lại y hệt đoạn code re-check server-side
    (dễ quên/viết sai khi thêm callback mới, đã từng lặp lại 2 lần trước khi
    có hàm này).

    KHÔNG bao giờ tin trực tiếp auth_data.tier gửi từ client — auth-store
    dùng storage_type='local' (localStorage trình duyệt), người dùng có thể
    tự sửa qua DevTools để giả tier='vip'. Hàm này luôn đối chiếu lại với
    users.json (nguồn xác thực thật phía server) trước khi trả về True.

    Dùng cho MỌI premium endpoint mới thay vì tự viết logic tương tự:
        from src.callbacks.auth_callbacks import require_entitlement
        if not require_entitlement(auth_data):
            ... trả về nội dung khoá/thông báo cần VIP ...
    """
    if not auth_data or not auth_data.get("logged_in"):
        return False
    username = auth_data.get("username", "")
    if not username:
        return False
    try:
        server_users = _load_users()
    except Exception as e:
        logger.warning(f"[require_entitlement] Không đọc được users.json: {e}")
        return False
    server_tier = server_users.get(username, {}).get("tier", "free")
    return server_tier == tier


def _verify_password(username: str, password: str, users: dict) -> bool:
    """
    Kiểm tra mật khẩu, tương thích ngược với dữ liệu cũ chưa hash.
    Nếu mật khẩu lưu dạng plaintext (chưa hash) mà khớp, tự động hash lại
    và ghi đè vào users.json ngay lập tức (migrate-on-login).
    """
    stored = users.get(username, {}).get('password', '')
    if not stored:
        return False

    # werkzeug hash luôn có dạng "method:salt$hash" (vd: "scrypt:32768:8:1$...")
    looks_hashed = ':' in stored and '$' in stored

    if looks_hashed:
        try:
            return check_password_hash(stored, password)
        except Exception:
            return False

    # Chưa hash (dữ liệu cũ) → so sánh plaintext, rồi migrate ngay nếu đúng
    if stored == password:
        users[username]['password'] = generate_password_hash(password)
        _save_users(users)
        logger.info(f"🔐 Đã tự động hash mật khẩu cho user '{username}' (migrate-on-login).")
        return True

    return False


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

    # AUDIT FIX (mục 15 - Security): chống brute-force đăng nhập.
    # Giới hạn theo IP (chặn quét nhiều username) VÀ theo cặp IP+username
    # (chặn kể cả khi kẻ tấn công đổi IP nhưng vẫn nhắm 1 tài khoản cụ thể
    # từ nhiều IP khác nhau thì lớp IP+username không giúp — đây là lớp
    # phòng vệ bổ sung, không thay thế WAF/CDN rate-limit ở tầng hạ tầng).
    client_ip = get_client_ip()
    allowed_ip, retry_ip = check_rate_limit(f"login:ip:{client_ip}", max_attempts=10, window_seconds=300)
    allowed_user, retry_user = check_rate_limit(f"login:user:{username}", max_attempts=5, window_seconds=300)
    if not allowed_ip or not allowed_user:
        retry_after = max(retry_ip, retry_user)
        logger.warning(f"🚫 Login bị chặn do rate limit — ip={client_ip}, username='{username}'")
        return (
            no_update,
            f"Quá nhiều lần thử đăng nhập. Vui lòng thử lại sau {retry_after}s.",
            _error_style_show,
            True,
        )

    users = _load_users()

    if username in users and _verify_password(username, password, users):
        # Đăng nhập đúng → reset counter để không phạt oan lần sau
        reset_rate_limit(f"login:user:{username}")
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
    Output('btn-login',         'style'),
    Output('btn-user-avatar',   'style'),
    Output('navbar-avatar-circle', 'children'),
    Output('navbar-avatar-circle', 'style'),
    Output('navbar-user-name',  'children'),
    Output('navbar-vip-badge',  'style'),
    Input('auth-store', 'data'),
)
def update_navbar_auth(auth_data):
    _hidden  = {"display": "none"}
    _btn_default_style = {
        "backgroundColor": "transparent",
        "border": "1px solid rgba(255,255,255,0.2)",
        "color": "rgba(255,255,255,0.85)",
        "fontSize": "13px", "fontWeight": "500",
        "padding": "6px 16px", "borderRadius": "6px",
    }

    if auth_data and auth_data.get('logged_in'):
        display_name = auth_data.get('display_name', auth_data.get('username', ''))
        tier         = auth_data.get('tier', 'free')
        initials = display_name.split()[-1][0].upper() if display_name else "?"
        bg_color     = _get_avatar_color(display_name)
        avatar_src   = auth_data.get('avatar', 'initials')

        # Circle content: initials hoặc ảnh template
        if avatar_src == 'initials' or not avatar_src:
            circle_children = initials
            circle_style = {
                "backgroundColor": bg_color,
                "color": "#fff",
                "display": "flex", "alignItems": "center",
                "justifyContent": "center",
            }
        else:
            circle_children = html.Img(
                src=f"/assets/avatar_templates/{avatar_src}.png",
                style={"width": "100%", "height": "100%",
                       "objectFit": "cover", "borderRadius": "50%"},
            )
            circle_style = {"backgroundColor": "transparent"}

        vip_style = {"display": "inline-block"} if tier == 'vip' else _hidden

        return (
            _hidden,                          # ẩn btn-login
            {"display": "flex", "alignItems": "center",
             "gap": "7px", "padding": "0"},  # hiện btn-user-avatar
            circle_children,
            circle_style,
            display_name,
            vip_style,
        )

    # Chưa đăng nhập
    return _btn_default_style, _hidden, "?", {}, [], _hidden


# =============================================================================
# 5. PREMIUM GATES — cập nhật className của tất cả wrapper
#    Danh sách premium-wrapper IDs:
#      pw-watchlist → Nút "Watchlist" trên navbar + trong heatmap
#      pw-compare   → Nút "So sánh"
#      pw-portfolio → Nút "Danh mục"
#      pw-alerts    → Nút "Cảnh báo"
#      pw-strategies → Dropdown trường phái
#      pw-momentum  → Nhóm "Hành vi thị trường" trong wizard
# =============================================================================
_PREMIUM_WRAPPERS = [
    "pw-screener-pdf",  # Báo cáo PDF trong screener
    "pw-watchlist",  # Watchlist — PREMIUM
    'pw-compare',
    'pw-portfolio',
    "pw-crisis",
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
    Output("chat-paywall", "style", allow_duplicate=True),
    Input("chat-paywall-close-btn", "n_clicks"),
    prevent_initial_call=True,
)
def close_paywall(n):
    if not n:
        return no_update
    return {"display": "none"}

@app.callback(
    Output("login-modal",           "is_open", allow_duplicate=True),
    Output("chat-paywall",          "style",   allow_duplicate=True),
    Input("chat-paywall-login-btn", "n_clicks"),
    prevent_initial_call=True,
)
def paywall_open_login(n):
    if not n:
        return no_update, no_update
    return True, {"display": "none"}

# =============================================================================
# 7. XỬ LÝ NHẬP MÃ KÍCH HOẠT (INVITE CODE → VIP)
# =============================================================================
@app.callback(
    Output("invite-code-msg",    "children"),
    Output("invite-code-msg",    "style"),
    Output("auth-store",         "data",    allow_duplicate=True),
    Output("invite-code-input",  "value"),
    Input("invite-code-submit-btn", "n_clicks"),
    State("invite-code-input",   "value"),
    State("auth-store",          "data"),
    State("user-phone-store",    "data"),
    prevent_initial_call=True,
)
def redeem_invite_code(n_clicks, code, auth_data, phone):
    if not n_clicks or not code:
        return no_update, no_update, no_update, no_update

    # AUDIT FIX (mục 15 - Security): mã VIP có không gian giá trị nhỏ
    # (vd "FSS-VIP-ALPHA") -> có thể bị dò/brute-force nếu không giới hạn
    # số lần thử theo IP. 8 lần / 10 phút là đủ rộng cho người dùng thật
    # gõ nhầm vài lần, nhưng chặn được script dò hàng loạt.
    client_ip = get_client_ip()
    allowed, retry_after = check_rate_limit(f"redeem:ip:{client_ip}", max_attempts=8, window_seconds=600)
    if not allowed:
        style_err = {"fontSize": "11px", "marginTop": "6px", "color": "#f85149"}
        logger.warning(f"🚫 Redeem invite code bị chặn do rate limit — ip={client_ip}")
        return f"Quá nhiều lần thử. Vui lòng thử lại sau {retry_after}s.", style_err, no_update, no_update

    from src.backend.database import validate_and_redeem_code, get_or_create_user

    identifier = phone or (auth_data or {}).get("username", "anonymous")

    # Tạo display_name thân thiện nếu chưa có
    _existing_name = (auth_data or {}).get("display_name", "")
    _display_name  = _existing_name if _existing_name else "Coupon Guest"

    get_or_create_user(
        phone=identifier,
        display_name=_display_name,
    )

    success, msg = validate_and_redeem_code(code, identifier)

    style_ok  = {"fontSize": "11px", "marginTop": "6px",
                 "color": "#00e676", "fontWeight": "600"}
    style_err = {"fontSize": "11px", "marginTop": "6px",
                 "color": "#f85149"}

    if success:
        reset_rate_limit(f"redeem:ip:{client_ip}")
        new_auth = {
            **(auth_data or {}),
            "tier":         "vip",
            "logged_in":    True,
            "display_name": _display_name,   # ← thêm dòng này
            "username":     identifier,       # ← đảm bảo có username
        }
        return msg, style_ok, new_auth, ""
    else:
        return msg, style_err, no_update, no_update

# =============================================================================
# 8. MỞ / ĐÓNG PROFILE MODAL
# =============================================================================
@app.callback(
    Output('profile-modal', 'is_open'),
    Input('btn-user-avatar',   'n_clicks'),
    Input('btn-close-profile', 'n_clicks'),
    Input('btn-logout',        'n_clicks'),
    State('profile-modal',     'is_open'),
    prevent_initial_call=True,
)
def toggle_profile_modal(open_n, close_n, logout_n, is_open):
    ctx = callback_context
    if not ctx.triggered:
        raise PreventUpdate
    trigger = ctx.triggered[0]['prop_id']
    if 'btn-user-avatar' in trigger:
        return True
    return False   # đóng khi bấm X, hoặc đăng xuất


# =============================================================================
# 9. LOAD DỮ LIỆU VÀO PROFILE MODAL KHI MỞ
# =============================================================================
@app.callback(
    Output('profile-display-name',          'children'),
    Output('profile-bio-input',             'value'),
    Output('profile-avatar-preview',        'children'),
    Output('profile-avatar-preview',        'style'),
    Output('profile-avatar-initials-opt',   'children'),
    Output('profile-avatar-initials-purple','children'),
    Output('profile-avatar-initials-red',   'children'),
    Output('profile-investor-tags',         'children'),
    Output('selected-avatar-store',         'data'),
    Input('profile-modal', 'is_open'),
    State('auth-store',              'data'),
    State('investor-profile-store',  'data'),
    prevent_initial_call=True,
)
def load_profile_modal(is_open, auth_data, investor_profile):
    if not is_open or not auth_data or not auth_data.get('logged_in'):
        raise PreventUpdate

    display_name = auth_data.get('display_name', auth_data.get('username', ''))
    initials = display_name.split()[-1][0].upper() if display_name else "?"
    bg_color     = _get_avatar_color(display_name)
    avatar_src   = auth_data.get('avatar', 'initials')

    # Load bio từ users.json
    users = _load_users()
    username = auth_data.get('username', '')
    bio = users.get(username, {}).get('bio', '')

    # Avatar preview
    if avatar_src == 'initials' or not avatar_src:
        preview_children = initials
        preview_style    = {"backgroundColor": bg_color, "color": "#fff",
                            "display": "flex", "alignItems": "center",
                            "justifyContent": "center", "fontSize": "32px",
                            "fontWeight": "700"}
    else:
        preview_children = html.Img(
            src=f"/assets/avatar_templates/{avatar_src}.png",
            style={"width": "100%", "height": "100%",
                   "objectFit": "cover", "borderRadius": "50%"},
        )
        preview_style = {"backgroundColor": "transparent", "overflow": "hidden"}

    # Investor profile tags
    _label_map = {
        "conservative": ("🛡", "Phòng thủ"),
        "moderate":     ("⚖️", "Cân bằng"),
        "growth":       ("📈", "Tăng trưởng"),
        "aggressive":   ("🚀", "Tấn công"),
        "speculative":  ("⚡", "Đầu cơ"),
    }
    _time_map = {"short": "Ngắn hạn", "medium": "Trung hạn", "long": "Dài hạn"}
    _liq_map  = {"high": "Thanh khoản cao", "medium": "Trung bình", "low": "Dài hạn"}

    if investor_profile:
        rp       = investor_profile.get('risk_profile', '')
        emoji, label = _label_map.get(rp, ("📊", rp))
        time     = _time_map.get(investor_profile.get('time_horizon', ''), '')
        liq      = _liq_map.get(investor_profile.get('liquidity', ''), '')

        # Thêm 2-3 thẻ định lượng
        t_ret    = investor_profile.get('target_return')
        drawdown = investor_profile.get('max_drawdown')
        will     = investor_profile.get('will_score')

        ret_str  = f"📈 {t_ret[0]}–{t_ret[1]}%/năm" if t_ret else None
        dd_str   = f"🛑 Max -{abs(drawdown)}%" if drawdown else None
        will_str = f"🧠 Tâm lý {int(will*100)}/100" if will is not None else None

        parts = [x for x in [
            f"{emoji} {label}", time, liq, ret_str, dd_str, will_str
        ] if x]

        tags = html.Div([
            html.Span(p, className="fss-profile-tag") for p in parts
        ], style={"display": "flex", "flexWrap": "wrap", "gap": "6px"})
    else:
        tags = html.Span("Chưa thiết lập hồ sơ",
                         style={"color": "#6b7280", "fontSize": "12px"})

    return (
        display_name,        # → profile-display-name
        bio,                 # → profile-bio-input
        preview_children,    # → profile-avatar-preview children
        preview_style,       # → profile-avatar-preview style
        initials,            # → profile-avatar-initials-opt
        initials,            # → profile-avatar-initials-purple
        initials,            # → profile-avatar-initials-red
        tags,                # → profile-investor-tags
        avatar_src,          # → selected-avatar-store
    )


# =============================================================================
# 10. CHỌN AVATAR TEMPLATE TRONG MODAL
# =============================================================================
@app.callback(
    Output('selected-avatar-store',  'data',     allow_duplicate=True),
    Output('profile-avatar-preview', 'children', allow_duplicate=True),
    Output('profile-avatar-preview', 'style',    allow_duplicate=True),
    Input({'type': 'avatar-opt', 'src': ALL}, 'n_clicks'),
    State('auth-store', 'data'),
    prevent_initial_call=True,
)
def select_avatar_template(n_clicks_list, auth_data):
    ctx = callback_context
    if not ctx.triggered or not any(n_clicks_list):
        raise PreventUpdate

    import json as _json
    triggered_id = _json.loads(ctx.triggered[0]['prop_id'].split('.')[0])
    src = triggered_id.get('src', 'initials')

    display_name = (auth_data or {}).get('display_name', '')
    initials = display_name.split()[-1][0].upper() if display_name else "?"
    bg_color     = _get_avatar_color(display_name)

    if src in ('initials', 'initials_purple', 'initials_red'):
        color_map = {
            'initials':        bg_color,
            'initials_purple': '#8b5cf6',
            'initials_red':    '#ef4444',
        }
        preview_children = initials
        preview_style    = {"backgroundColor": color_map[src], "color": "#fff",
                            "display": "flex", "alignItems": "center",
                            "justifyContent": "center", "fontSize": "32px",
                            "fontWeight": "700"}
    else:
        preview_children = html.Img(
            src=f"/assets/avatar_templates/{src}.png",
            style={"width": "100%", "height": "100%",
                   "objectFit": "cover", "borderRadius": "50%"},
        )
        preview_style = {"backgroundColor": "transparent", "overflow": "hidden"}

    return src, preview_children, preview_style


# =============================================================================
# 11. LƯU PROFILE (bio + avatar) VÀO users.json + auth-store
# =============================================================================
def _save_users(users: dict):
    try:
        with open(USERS_FILE, 'w', encoding='utf-8') as f:
            import json as _json
            _json.dump(users, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        logger.error(f"Không thể ghi users.json: {e}")
        return False


@app.callback(
    Output('auth-store',      'data',     allow_duplicate=True),
    Output('profile-save-msg', 'children'),
    Output('profile-modal',   'is_open',  allow_duplicate=True),
    Input('btn-save-profile', 'n_clicks'),
    State('profile-bio-input',    'value'),
    State('selected-avatar-store', 'data'),
    State('auth-store',           'data'),
    prevent_initial_call=True,
)
def save_profile(n_clicks, bio, avatar_src, auth_data):
    if not n_clicks or not auth_data or not auth_data.get('logged_in'):
        raise PreventUpdate

    username = auth_data.get('username', '')
    users    = _load_users()

    if username in users:
        users[username]['bio']    = bio or ''
        users[username]['avatar'] = avatar_src or 'initials'
        ok = _save_users(users)
    else:
        ok = False

    # Cập nhật auth-store để navbar avatar refresh ngay
    new_auth = {**auth_data, 'avatar': avatar_src or 'initials'}

    if ok:
        return new_auth, "", False   # đóng modal luôn
    else:
        return auth_data, "", True
    

# =============================================================================
# 12. NÚT TẢI PDF HỒ SƠ TRONG PROFILE MODAL
# =============================================================================
@app.callback(
    Output("ips-pdf-download-profile", "data"),
    Input("btn-profile-download-pdf",  "n_clicks"),
    State("investor-profile-store",    "data"),
    State("ips-goal-store",            "data"),
    State("ips-will-store",            "data"),
    State("ips-time-store",            "data"),
    prevent_initial_call=True,
)
def download_ips_pdf_from_profile(n_clicks, profile, goal, will, time_h):
    if not n_clicks or not profile:
        raise PreventUpdate
    from src.callbacks.ips_pdf_callback import generate_ips_pdf
    quiz_answers = {"goal": goal, "will": will, "time_h": time_h}
    pdf_bytes = generate_ips_pdf(profile, quiz_answers)
    return dcc.send_bytes(pdf_bytes, filename="bao_cao_ho_so_ndt.pdf")