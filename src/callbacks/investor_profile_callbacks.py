# src/callbacks/investor_profile_callbacks.py
# ─────────────────────────────────────────────────────────────────────────────
# IPS Wizard — Toàn bộ callback logic (CFA Level 3 framework)
#
# Callbacks trong file này:
#   1. navigate_wizard()          — Điều hướng Prev/Next, validate từng step
#   2. render_step_visibility()   — Hiện/ẩn đúng step content + update progress bar
#   3. render_profile_preview()   — Tính risk profile và render step 4
#   4. render_final_summary()     — Render step 5 summary
#   5. apply_ips_profile()        — Lưu profile + set filter stores + active-filters-store
#                                   → set profile-setup-done=True → main.py tự chuyển trang
#   6. select_goal/will/time/liq  — Highlight card được chọn
#
# NOTE: Callbacks auto_open_wizard và open_wizard_from_header đã bị xoá.
#       Logic chuyển trang onboarding ↔ main app được xử lý trong main.py:
#         - toggle_pages()      — dựa trên profile-setup-done store
#         - reopen_onboarding() — khi user click nút "Hồ sơ" ở header
# ─────────────────────────────────────────────────────────────────────────────

import logging
from dash import Input, Output, State, html, dcc, no_update, callback_context, clientside_callback, ALL
from dash.exceptions import PreventUpdate
import dash_bootstrap_components as dbc
from matplotlib.pyplot import step
from src.app_instance import app
logger = logging.getLogger(__name__)

# ────────────────────────────────────────────────────────────────────────────
# CONSTANTS
# ────────────────────────────────────────────────────────────────────────────
_BG_CARD    = "#0d1d36"
_BG_CARD2   = "#112340"
_BORDER     = "#1a3a60"
_TEXT_PRI   = "#e8f4ff"
_TEXT_SEC   = "#7aafcc"
_TEXT_MUT   = "#3d6a8a"
_BLUE       = "#0090ff"
_GREEN      = "#00e676"
_AMBER      = "#ffb703"
_RED        = "#ff3d57"
_PURPLE     = "#8b5cf6"
_CYAN       = "#00e5ff"
_FONT_SORA  = "'Be Vietnam Pro', 'DM Sans', sans-serif"
_FONT_INTER = "'DM Sans', sans-serif"
_FONT_MONO  = "'DM Mono', monospace"

TOTAL_STEPS = 5


# ────────────────────────────────────────────────────────────────────────────
# HELPER: Tính Risk Profile từ IPS inputs (CFA L3 framework)
# ────────────────────────────────────────────────────────────────────────────
def compute_risk_profile(goal: str, will: str, pct_savings: int,
                         emergency_months: int, time_horizon: str,
                         liquidity: str) -> dict:
    # ── Willingness Score (Hệ số tâm lý) ───────────────────────────────────
    # Áp dụng logic Loss Aversion
    will_map = {"panic": 0.15, "worry": 0.40, "hold": 0.70, "buy": 0.95}
    will_score = will_map.get(will or "worry", 0.40)

    # ── Ability Score (Năng lực tài chính) ─────────────────────────────────
    # Trọng số: Time Horizon (40%), Liquidity (30%), Buffer (20%), Savings (10%)
    
    # 1. Savings Rate (Thặng dư)
    pct = pct_savings or 30
    pct_score = min(pct / 60.0, 1.0) # >60% là tối đa điểm

    # 2. Emergency Buffer (Đệm thanh khoản)
    emg = emergency_months or 0
    if emg < 3: emg_score = 0.20
    elif emg < 6: emg_score = 0.60
    else: emg_score = 0.95

    # 3. Time Horizon
    time_map = {"short": 0.20, "mid": 0.60, "long": 0.95}
    time_score = time_map.get(time_horizon or "long", 0.60)
    
    # 4. Liquidity Constraint (Penalty nặng nhất)
    liq_map = {"high": 0.20, "mid": 0.60, "low": 0.95}
    liq_score = liq_map.get(liquidity or "low", 0.60)

    ability_score = (0.40 * time_score) + (0.30 * liq_score) + (0.20 * emg_score) + (0.10 * pct_score)

    # ── Quy tắc định tuyến CFA L3 (Min Rule) ──────────────────────────────
    # Tổng hợp rủi ro thực tế bị giới hạn bởi yếu tố yếu nhất.
    final_score = min(will_score, ability_score)

    # Penalty thêm nếu mục tiêu là Bảo toàn vốn nhưng hệ số rủi ro ra quá cao
    if goal == "preserve":
        final_score = min(final_score, 0.30)

    # ── Phân loại Risk Profile ─────────────────────────────────────────────
    if final_score < 0.40:
        risk_profile   = "conservative"
        risk_label_vi  = "Thận trọng (Conservative)"
        risk_color     = _GREEN
        risk_icon      = "fas fa-shield-check"
        target_return  = (7, 10)
        max_drawdown   = -8
        num_stocks     = (15, 25)
    elif final_score < 0.70:
        risk_profile   = "moderate"
        risk_label_vi  = "Cân bằng (Moderate)"
        risk_color     = _BLUE
        risk_icon      = "fas fa-chart-pie"
        target_return  = (12, 16)
        max_drawdown   = -15
        num_stocks     = (10, 18)
    else:
        risk_profile   = "aggressive"
        risk_label_vi  = "Tăng trưởng (Aggressive)"
        risk_color     = _RED
        risk_icon      = "fas fa-chart-network"
        target_return  = (18, 25)
        max_drawdown   = -25
        num_stocks     = (6, 12)

    # ── Core-Satellite Strategy Mapping ───────────────────────────────────
    # Dựa trên Smart Beta và Factor Investing
    goal_strat_map = {
        "preserve": {
            "core":      ["STRAT_QUALITY", "STRAT_DIVIDEND"],
            "satellite": ["STRAT_VALUE"],
        },
        "income": {
            "core":      ["STRAT_DIVIDEND", "STRAT_QUALITY"],
            "satellite": ["STRAT_VALUE", "STRAT_PIOTROSKI"],
        },
        "growth": {
            "core":      ["STRAT_GARP", "STRAT_PIOTROSKI", "STRAT_QUALITY"],
            "satellite": ["STRAT_CANSLIM", "STRAT_MAGIC"],
        },
        "speculate": {
            "core":      ["STRAT_CANSLIM", "STRAT_GROWTH", "STRAT_TURNAROUND"],
            "satellite": ["STRAT_MAGIC"],
        },
    }
    strat = goal_strat_map.get(goal or "growth", goal_strat_map["growth"])

    # ── Bucket allocation (Mô hình phân bổ 3 rổ tài sản) ──────────────────
    bucket_map = {
        "conservative": {"safe": 75, "growth": 20, "speculative": 5},
        "moderate":     {"safe": 40, "growth": 45, "speculative": 15},
        "aggressive":   {"safe": 15, "growth": 50, "speculative": 35},
    }
    bucket_alloc = bucket_map[risk_profile]

    # auto_filters cho screener hard-filter block
    auto_filters_map = {
        "conservative": {"min_vol": 100_000,  "min_cap": 1_000_000_000_000, "min_price": 10_000}, # Siết thanh khoản chặt hơn
        "moderate":     {"min_vol": 50_000,   "min_cap": 500_000_000_000,   "min_price": 5_000},
        "aggressive":   {"min_vol": 20_000,   "min_cap": 100_000_000_000,   "min_price": 2_000},
    }
    auto_filters = auto_filters_map[risk_profile]

    return {
        "risk_profile":          risk_profile,
        "risk_label_vi":         risk_label_vi,
        "risk_color":            risk_color,
        "risk_icon":             risk_icon,
        "will_score":            round(will_score, 3),
        "ability_score":         round(ability_score, 3),
        "final_score":           round(final_score, 3),
        "target_return":         target_return,
        "max_drawdown":          max_drawdown,
        "num_stocks":            num_stocks,
        "core_strategies":       strat["core"],
        "satellite_strategies":  strat["satellite"],
        "bucket_alloc":          bucket_alloc,
        "auto_filters":          auto_filters,
    }


# ────────────────────────────────────────────────────────────────────────────
# HELPER: Build IPS filter settings để cập nhật filter stores
# ────────────────────────────────────────────────────────────────────────────
def build_ips_filter_settings(risk_profile: str, goal: str,
                               prefer_dividend: bool,
                               avoid_bank_re: bool) -> dict:
    """
    Trả về dict mapping filter_store_id → new_value
    để callback apply_ips_profile() cập nhật từng store.

    Key phải khớp chính xác với IDs trong sidebar.py.
    """
    settings = {}

    if risk_profile == "conservative":
        settings.update({
            "filter-roe":           [10,  100],
            "filter-pe":            [0,   15],
            "filter-pb":            [0,   2.0],
            "filter-de":            [0,   1.0],
            "filter-current-ratio": [1.5, 10],
            "filter-net-margin":    [0,   50],
            # Grades: giữ chất lượng cao
            "filter-vgm-score":     ["A", "B", "C"],
            "filter-value-score":   ["A", "B", "C"],
        })
        if prefer_dividend:
            settings["filter-div-yield"] = [4.0, 20]

    elif risk_profile == "moderate":
        settings.update({
            "filter-roe":           [15,  100],
            "filter-pe":            [0,   18],
            "filter-de":            [0,   1.5],
            "filter-current-ratio": [1.2, 10],
            "filter-canslim":       [5,   7],     # Piotroski proxy qua canslim range
            # Grades: B hoặc tốt hơn
            "filter-vgm-score":     ["A", "B"],
            "filter-growth-score":  ["A", "B"],
        })
        if prefer_dividend:
            settings["filter-div-yield"] = [3.0, 20]

    elif risk_profile == "aggressive":
        settings.update({
            "filter-roe":              [12, 100],
            "filter-pe":               [0,  30],
            "filter-rev-growth-yoy":   [10, 200],
            "filter-eps-growth-yoy":   [5,  300],
            "filter-rs-3m":            [0,  100],
            # Grades: A hoặc B momentum
            "filter-momentum-score":   ["A", "B"],
            "filter-vgm-score":        ["A", "B"],
        })

    return settings


# ────────────────────────────────────────────────────────────────────────────
# HELPER: Build active-filters-store dict từ filter settings
# ────────────────────────────────────────────────────────────────────────────
def build_active_filters(filter_settings: dict, existing_af: dict) -> dict:
    af = existing_af.copy() if existing_af else {}
    for filter_id, rng in filter_settings.items():
        # Store with value so screener can read it
        label = filter_id.replace("filter-", "").replace("-", " ").title()
        af[filter_id] = {"label": label, "type": "range", "value": rng}
    return af


# ────────────────────────────────────────────────────────────────────────────
# HELPER: Render risk profile badge
# ────────────────────────────────────────────────────────────────────────────
def _risk_badge(label: str, color: str, icon: str):
    bg_map = {
        _GREEN: "#071e12", _BLUE: "#071628", _RED: "#1a0308",
    }
    border_map = {
        _GREEN: "#065f46", _BLUE: "#0e4f7a", _RED: "#7f1d1d",
    }
    return html.Div([
        html.I(className=icon,
               style={"fontSize": "28px", "color": color,
                      "marginBottom": "8px", "display": "block"}),
        html.Div(label,
                 style={"fontSize": "22px", "fontWeight": "800",
                        "color": color, "fontFamily": _FONT_SORA,
                        "letterSpacing": "0.5px"}),
    ], style={
        "textAlign": "center", "padding": "20px",
        "backgroundColor": bg_map.get(color, _BG_CARD2),
        "border": f"1px solid {border_map.get(color, _BORDER)}",
        "borderRadius": "8px",
    })


# ────────────────────────────────────────────────────────────────────────────
# HELPER: Strategy label map
# ────────────────────────────────────────────────────────────────────────────
_STRAT_META = {
    "STRAT_QUALITY":    {"name": "Quality (Munger)",        "icon": "fas fa-gem",      "color": _BLUE},
    "STRAT_GARP":       {"name": "GARP (Peter Lynch)",      "icon": "fas fa-chart-bar", "color": _GREEN},
    "STRAT_PIOTROSKI":  {"name": "Piotroski F-Score ≥ 7",  "icon": "fas fa-heartbeat", "color": _PURPLE},
    "STRAT_DIVIDEND":   {"name": "Cổ tức (John Neff)",     "icon": "fas fa-coins",    "color": _AMBER},
    "STRAT_VALUE":      {"name": "Giá trị (B. Graham)",    "icon": "fas fa-balance-scale", "color": _CYAN},
    "STRAT_MAGIC":      {"name": "Magic Formula (Greenblatt)", "icon": "fas fa-magic", "color": _AMBER},
    "STRAT_TURNAROUND": {"name": "Turnaround (Templeton)",  "icon": "fas fa-sync-alt", "color": _RED},
    "STRAT_CANSLIM":    {"name": "CANSLIM (O'Neil)",        "icon": "fas fa-bolt",     "color": _RED},
    "STRAT_GROWTH":     {"name": "Growth (Philip Fisher)",  "icon": "fas fa-seedling", "color": _GREEN},
    "STRAT_NCN":        {"name": "Vietcap Khuyến nghị",    "icon": "fas fa-star",     "color": _BLUE},
}

_MATCH_SCORE = {
    "STRAT_QUALITY": 95, "STRAT_GARP": 88, "STRAT_PIOTROSKI": 84,
    "STRAT_DIVIDEND": 90, "STRAT_VALUE": 82, "STRAT_MAGIC": 75,
    "STRAT_TURNAROUND": 68, "STRAT_CANSLIM": 72, "STRAT_GROWTH": 78,
    "STRAT_NCN": 85,
}


def _strategy_row(strat_id: str, is_core: bool = True):
    meta  = _STRAT_META.get(strat_id, {"name": strat_id, "icon": "fas fa-circle", "color": _BLUE})
    score = _MATCH_SCORE.get(strat_id, 70)
    tag_color = "rgba(59,130,246,0.15)" if is_core else "rgba(245,158,11,0.15)"
    tag_border = _BLUE if is_core else _AMBER
    tag_text   = "CORE" if is_core else "SATELLITE"

    return html.Div([
        # Match score circle
        html.Div(f"{score}%", style={
            "width": "40px", "height": "40px",
            "borderRadius": "50%",
            "backgroundColor": f"{meta['color']}20",
            "border": f"1px solid {meta['color']}50",
            "display": "flex", "alignItems": "center",
            "justifyContent": "center",
            "fontSize": "11px", "fontWeight": "700",
            "color": meta["color"],
            "flexShrink": "0",
        }),
        # Name + icon
        html.Div([
            html.I(className=meta["icon"],
                   style={"color": meta["color"],
                          "marginRight": "6px", "fontSize": "11px"}),
            html.Span(meta["name"],
                      style={"fontSize": "13px", "fontWeight": "700",
                             "color": _TEXT_PRI, "fontFamily": _FONT_SORA}),
        ], style={"flex": "1"}),
        # Core/Satellite badge
        html.Span(tag_text, style={
            "fontSize": "10px", "fontWeight": "700",
            "color": tag_border,
            "backgroundColor": tag_color,
            "border": f"1px solid {tag_border}50",
            "padding": "2px 8px", "borderRadius": "10px",
            "fontFamily": _FONT_MONO, "letterSpacing": "0.5px",
        }),
        # Strat code
        html.Span(strat_id, style={
            "fontSize": "10px", "color": _TEXT_MUT,
            "fontFamily": _FONT_MONO, "marginLeft": "6px",
        }),
    ], style={
        "display": "flex", "alignItems": "center", "gap": "10px",
        "padding": "9px 12px",
        "borderBottom": f"1px solid {_BORDER}",
        "cursor": "pointer",
        "transition": "background .15s",
    }, className="strategy-row-hover")


def _metric_card(label: str, value: str, color: str = _TEXT_PRI):
    return html.Div([
        html.Div(label, style={"fontSize": "11px", "color": _TEXT_SEC,
                               "marginBottom": "4px", "fontFamily": _FONT_INTER}),
        html.Div(value, style={"fontSize": "18px", "fontWeight": "800",
                               "color": color, "fontFamily": _FONT_SORA}),
    ], style={
        "backgroundColor": _BG_CARD2,
        "border": f"1px solid {_BORDER}",
        "borderRadius": "8px", "padding": "12px 14px",
        "textAlign": "center",
    })


# ════════════════════════════════════════════════════════════════════════════
# CALLBACK 1: Điều hướng wizard (Prev / Next) - Đã sửa gộp 3 bước
# ════════════════════════════════════════════════════════════════════════════
@app.callback(
    Output("ips-current-step", "data"),
    Output("ips-step1-error",  "children"),
    Output("ips-step2-error",  "children"),
    Output("ips-step3-error",  "children"),
    Input("ips-btn-next", "n_clicks"),
    Input("ips-btn-prev", "n_clicks"),
    State("ips-current-step",       "data"),
    State("ips-goal-store",          "data"),
    State("ips-will-store",          "data"),
    State("ips-time-store",          "data"),
    State("ips-liq-store",           "data"),
    prevent_initial_call=True,
)
def navigate_wizard(next_clicks, prev_clicks, current_step, goal, will, time_h, liq):
    ctx = callback_context
    if not ctx.triggered: raise PreventUpdate
    triggered = ctx.triggered[0]["prop_id"].split(".")[0]
    step = current_step or 1

    if triggered == "ips-btn-prev":
        # Từ bước 4 hoặc 5 → quay về bước 3 (hiện cùng 1,2,3)
        if step >= 4:
            return 3, "", "", ""
        # Bước 1,2,3 đang hiện cùng nhau → không có "trước" nữa
        return step, "", "", ""

    if triggered == "ips-btn-next":
        if step <= 3:
            e1 = "⚠ Vui lòng chọn mục tiêu đầu tư." if not goal else ""
            e2 = "⚠ Vui lòng chọn phản ứng rủi ro." if not will else ""
            e3 = ("⚠ Vui lòng chọn đủ thời gian & thanh khoản."
                  if not time_h or not liq else "")
            if e1 or e2 or e3:
                return step, e1, e2, e3
            # Đủ hết → sang bước 4+5 cùng lúc
            return 4, "", "", ""
        else:
            # step >= 4 → apply_ips_profile callback tự xử lý
            return step, "", "", ""
    raise PreventUpdate


# ════════════════════════════════════════════════════════════════════════════
# CALLBACK 2: Hiện/ẩn đúng step - Đã sửa gộp 3 bước
# ════════════════════════════════════════════════════════════════════════════
@app.callback(
    Output("ips-step-1",      "style"),
    Output("ips-step-2",      "style"),
    Output("ips-step-3",      "style"),
    Output("ips-step-4",      "style"),
    Output("ips-step-5",      "style"),
    Output("ips-progress-bar","children"),
    Output("ips-btn-prev",    "disabled"),
    Output("ips-btn-prev",    "style"),
    Output("ips-btn-next",    "children"),
    Output("ips-step-counter","children"),
    Input("ips-current-step", "data"),
)
def render_step_visibility(current_step):
    step = current_step or 1
    show = {"display": "block"}
    hide = {"display": "none"}

    if step <= 3:
        s1, s2, s3, s4, s5 = show, show, show, hide, hide
        d_step = 1
    else:
        # Bước 4 và 5 hiện cùng lúc khi người dùng bấm Tiếp tục từ bước 3
        s1, s2, s3, s4, s5 = hide, hide, hide, show, show
        d_step = 4

    # Cập nhật thanh Progress bar
    labels = ["Mục tiêu", "Rủi ro", "Ràng buộc", "Chiến lược", "Xác nhận"]
    badges = []
    for i, label in enumerate(labels):
        n = i + 1
        done   = n < d_step
        active = (n <= 3 and d_step == 1) or (n >= 4 and d_step == 4)
        
        if done:
            bg, color, icon_html = "#0f3d22", "#10b981", html.I(className="fas fa-check", style={"marginRight": "4px"})
            bc = "#065f46"
        elif active:
            bg, color, icon_html = "#0d2137", "#3b82f6", html.Span(f"{n}", style={"marginRight": "4px", "fontWeight": "700"})
            bc = "#1d4ed8"
        else:
            bg, color, icon_html = "#161b22", "#484f58", html.Span(f"{n}", style={"marginRight": "4px"})
            bc = "#21262d"

        badges.append(html.Div([icon_html, html.Span(label)], style={
            "display": "flex", "alignItems": "center", "padding": "5px 9px", "borderRadius": "6px",
            "backgroundColor": bg, "border": f"1px solid {bc}", "fontSize": "11px", "color": color
        }))
        if i < 4:
            badges.append(html.Div("→", style={"color": "#484f58", "fontSize": "12px", "flexShrink": "0"}))

    progress = html.Div(badges, style={"display": "flex", "alignItems": "center", "gap": "6px", "overflowX": "auto", "paddingBottom": "4px", "marginBottom": "20px"})
    
    # Nút bấm — disabled khi đang ở nhóm bước 1-3 (không có step trước)
    prev_dis = (d_step == 1)
    prev_st = {
        "backgroundColor": "#161b22", "border": "1px solid #21262d",
        "color": "#484f58" if prev_dis else "#8b949e",
        "borderRadius": "6px", "fontSize": "12px",
        "opacity": "0.4" if prev_dis else "1",
    }
    nxt_btn = (
        [html.I(className="fas fa-check", style={"marginRight": "6px"}), "Lưu & Áp dụng"]
        if d_step == 4   # bước 4+5 hiện cùng lúc, nút này là nút cuối
        else ["Tiếp theo ", html.I(className="fas fa-arrow-right", style={"marginLeft": "6px"})]
    )
    counter = "Bước 1–3 / 5" if d_step == 1 else "Bước 4–5 / 5"

    return s1, s2, s3, s4, s5, progress, prev_dis, prev_st, nxt_btn, counter

# ════════════════════════════════════════════════════════════════════════════
# CALLBACK 3: Render step 4 — Profile Preview (chạy khi vào step 4)
# ════════════════════════════════════════════════════════════════════════════
@app.callback(
    Output("ips-profile-preview", "children"),
    Input("ips-current-step",    "data"),
    State("ips-goal-store",       "data"),
    State("ips-will-store",       "data"),
    State("ips-pct-savings-slider","value"),
    State("ips-emergency-slider", "value"),
    State("ips-time-store",       "data"),
    State("ips-liq-store",        "data"),
    State("ips-unique-checklist", "value"),
    prevent_initial_call=True,
)
def render_profile_preview(step, goal, will, pct_savings, emergency,
                           time_h, liq, unique_flags):
    if step < 4:
        raise PreventUpdate

    unique_flags = unique_flags or []
    profile = compute_risk_profile(
        goal=goal, will=will,
        pct_savings=pct_savings or 30,
        emergency_months=emergency or 4,
        time_horizon=time_h or "mid",
        liquidity=liq or "low",
    )
    rp = profile["risk_profile"]
    prefer_dividend = "prefer_dividend" in unique_flags

    tmin, tmax = profile["target_return"]
    nmin, nmax = profile["num_stocks"]

    # ── Layout step 4 ──────────────────────────────────────────────────────
    return html.Div([

        # Risk profile hero
        html.Div([
            _risk_badge(profile["risk_label_vi"], profile["risk_color"], profile["risk_icon"]),
        ], style={"marginBottom": "14px"}),

        # Score breakdown
        html.Div([
            html.Div([
                html.Div("Willingness (tâm lý)",
                         style={"fontSize": "11px", "color": _TEXT_SEC,
                                "marginBottom": "6px"}),
                html.Div(style={
                    "height": "6px", "borderRadius": "3px",
                    "backgroundColor": "#1e2d3d",
                    "overflow": "hidden", "marginBottom": "4px",
                }, children=[
                    html.Div(style={
                        "height": "100%", "borderRadius": "3px",
                        "width": f"{int(profile['will_score']*100)}%",
                        "backgroundColor": _BLUE,
                    }),
                ]),
                html.Div(f"{profile['will_score']*100:.0f} / 100",
                         style={"fontSize": "10px", "color": _TEXT_MUT,
                                "fontFamily": _FONT_MONO}),
            ], style={"flex": "1"}),
            html.Div([
                html.Div("Ability (tài chính)",
                         style={"fontSize": "11px", "color": _TEXT_SEC,
                                "marginBottom": "6px"}),
                html.Div(style={
                    "height": "6px", "borderRadius": "3px",
                    "backgroundColor": "#1e2d3d",
                    "overflow": "hidden", "marginBottom": "4px",
                }, children=[
                    html.Div(style={
                        "height": "100%", "borderRadius": "3px",
                        "width": f"{int(profile['ability_score']*100)}%",
                        "backgroundColor": _GREEN,
                    }),
                ]),
                html.Div(f"{profile['ability_score']*100:.0f} / 100",
                         style={"fontSize": "10px", "color": _TEXT_MUT,
                                "fontFamily": _FONT_MONO}),
            ], style={"flex": "1"}),
        ], style={"display": "flex", "gap": "16px", "marginBottom": "14px",
                  "padding": "12px", "backgroundColor": _BG_CARD2,
                  "border": f"1px solid {_BORDER}", "borderRadius": "8px"}),

        # Key metrics
        html.Div([
            _metric_card("Lợi nhuận kỳ vọng/năm",
                         f"{tmin}–{tmax}%", _GREEN),
            _metric_card("Max Drawdown cho phép",
                         f"{profile['max_drawdown']}%", _RED),
            _metric_card("Số CP tối ưu",
                         f"{nmin}–{nmax} mã", _BLUE),
        ], style={"display": "grid", "gridTemplateColumns": "1fr 1fr 1fr",
                  "gap": "8px", "marginBottom": "14px"}),

        # Strategies
        html.Div([
            html.Div([
                html.Span("CORE — 70% danh mục",
                          style={"fontSize": "11px", "color": _TEXT_MUT,
                                 "fontFamily": _FONT_MONO,
                                 "display": "block", "marginBottom": "8px"}),
                *[_strategy_row(s, is_core=True)
                  for s in profile["core_strategies"]],

                html.Div(style={"height": "1px", "backgroundColor": _BORDER,
                                "margin": "10px 0"}),

                html.Span("SATELLITE — 30% danh mục",
                          style={"fontSize": "11px", "color": _TEXT_MUT,
                                 "fontFamily": _FONT_MONO,
                                 "display": "block", "marginBottom": "8px"}),
                *[_strategy_row(s, is_core=False)
                  for s in profile["satellite_strategies"]],
            ]),
        ], style={
            "backgroundColor": _BG_CARD,
            "border": f"1px solid {_BORDER}",
            "borderRadius": "8px", "overflow": "hidden",
            "marginBottom": "14px",
        }),

        # Bucket allocation
        html.Div([
            html.Div("Chiến lược 3 rổ (Bucket Strategy)",
                     style={"fontSize": "12px", "fontWeight": "700",
                            "color": _TEXT_SEC, "marginBottom": "10px",
                            "fontFamily": _FONT_SORA}),
            html.Div([
                _bucket_mini("An Toàn",    profile["bucket_alloc"]["safe"],        _GREEN),
                _bucket_mini("Tăng Trưởng", profile["bucket_alloc"]["growth"],    _BLUE),
                _bucket_mini("Cơ Hội",     profile["bucket_alloc"]["speculative"], _AMBER),
            ], style={"display": "grid", "gridTemplateColumns": "1fr 1fr 1fr",
                      "gap": "8px"}),
        ], style={
            "backgroundColor": _BG_CARD2,
            "border": f"1px solid {_BORDER}",
            "borderRadius": "8px", "padding": "12px",
        }),
    ])


def _bucket_mini(label: str, pct: int, color: str):
    bg_map = {_GREEN: "#071e12", _BLUE: "#071628", _AMBER: "#0c0a00"}
    return html.Div([
        html.Div(f"{pct}%",
                 style={"fontSize": "22px", "fontWeight": "800",
                        "color": color, "fontFamily": _FONT_SORA}),
        html.Div(label,
                 style={"fontSize": "12px", "color": _TEXT_SEC,
                        "marginTop": "4px", "fontFamily": _FONT_INTER}),
    ], style={
        "textAlign": "center", "padding": "14px",
        "backgroundColor": bg_map.get(color, _BG_CARD2),
        "border": f"1px solid {color}30",
        "borderRadius": "8px",
    })


# ════════════════════════════════════════════════════════════════════════════
# CALLBACK 4: Render step 5 — Final Summary
# ════════════════════════════════════════════════════════════════════════════
@app.callback(
    Output("ips-final-summary", "children"),
    Input("ips-current-step",    "data"),
    State("ips-goal-store",       "data"),
    State("ips-will-store",       "data"),
    State("ips-pct-savings-slider","value"),
    State("ips-emergency-slider", "value"),
    State("ips-time-store",       "data"),
    State("ips-liq-store",        "data"),
    State("ips-unique-checklist", "value"),
    prevent_initial_call=True,
)
def render_final_summary(step, goal, will, pct_savings, emergency,
                         time_h, liq, unique_flags):
    if step < 4:
        raise PreventUpdate

    unique_flags = unique_flags or []
    profile = compute_risk_profile(
        goal=goal, will=will,
        pct_savings=pct_savings or 30,
        emergency_months=emergency or 4,
        time_horizon=time_h or "mid",
        liquidity=liq or "low",
    )

    goal_label_map = {
        "preserve":  "Bảo toàn vốn",
        "income":    "Thu nhập thụ động",
        "growth":    "Tăng trưởng tài sản",
        "speculate": "Tối đa hóa lợi nhuận",
    }
    will_label_map = {
        "panic": "Bán hết (Panic sell)",
        "worry": "Lo lắng, chờ đợi",
        "hold":  "Giữ theo kế hoạch",
        "buy":   "Mua thêm vào đáy",
    }
    time_label_map = {
        "short": "Dưới 1 năm",
        "mid":   "1 – 3 năm",
        "long":  "Trên 3 năm",
    }

    def summary_row(label, value, color=_TEXT_PRI):
        return html.Div([
            html.Span(label, style={"fontSize": "12px", "color": _TEXT_SEC,
                                    "flex": "1", "fontFamily": _FONT_INTER}),
            html.Span(value, style={"fontSize": "12px", "fontWeight": "700",
                                    "color": color, "fontFamily": _FONT_SORA}),
        ], style={"display": "flex", "alignItems": "center",
                  "padding": "7px 0",
                  "borderBottom": f"1px solid {_BORDER}"})

    tmin, tmax = profile["target_return"]

    # Filter preview tags
    filter_settings = build_ips_filter_settings(
        profile["risk_profile"], goal,
        "prefer_dividend" in unique_flags,
        "avoid_bank_re" in unique_flags,
    )
    filter_tags = [
        html.Span(fid.replace("filter-", "").upper() + ": " + str(v),
                  style={
                      "fontSize": "10px", "fontWeight": "600",
                      "color": _BLUE,
                      "backgroundColor": "rgba(59,130,246,0.12)",
                      "border": "1px solid rgba(59,130,246,0.25)",
                      "padding": "3px 8px", "borderRadius": "10px",
                      "fontFamily": _FONT_MONO,
                  })
        for fid, v in list(filter_settings.items())[:8]   # chỉ show 8 filters đầu
    ]

    return html.Div([
        # Profile header
        html.Div([
            html.I(className=profile["risk_icon"],
                   style={"color": profile["risk_color"],
                          "fontSize": "16px", "marginRight": "10px"}),
            html.Span(f"Hồ sơ: {profile['risk_label_vi']}",
                      style={"fontSize": "16px", "fontWeight": "800",
                             "color": profile["risk_color"],
                             "fontFamily": _FONT_SORA}),
        ], style={"marginBottom": "14px", "display": "flex",
                  "alignItems": "center"}),

        # Summary rows
        html.Div([
            summary_row("Mục tiêu đầu tư",
                        goal_label_map.get(goal, goal), _TEXT_PRI),
            summary_row("Phản ứng với biến động",
                        will_label_map.get(will, will), _TEXT_PRI),
            summary_row("Thời gian đầu tư",
                        time_label_map.get(time_h, time_h), _TEXT_PRI),
            summary_row("Lợi nhuận kỳ vọng",
                        f"{tmin}–{tmax}%/năm", _GREEN),
            summary_row("Max drawdown cho phép",
                        f"{profile['max_drawdown']}%", _RED),
            summary_row("Chiến lược core",
                        " · ".join(profile["core_strategies"]), _BLUE),
        ], style={"marginBottom": "14px",
                  "backgroundColor": _BG_CARD2,
                  "border": f"1px solid {_BORDER}",
                  "borderRadius": "8px", "padding": "12px"}),

        # Filters preview
        html.Div([
            html.Div([
                html.I(className="fas fa-filter",
                       style={"color": _BLUE, "marginRight": "6px",
                              "fontSize": "11px"}),
                html.Span("Bộ lọc sẽ được áp dụng vào Screener:",
                          style={"fontSize": "12px", "color": _TEXT_SEC,
                                 "fontFamily": _FONT_INTER}),
            ], style={"marginBottom": "8px"}),
            html.Div(filter_tags, style={
                "display": "flex", "flexWrap": "wrap", "gap": "6px",
            }),
            html.Span("+ các tiêu chí ngành và cấu trúc vốn riêng",
                      style={"fontSize": "11px", "color": _TEXT_MUT,
                             "display": "block", "marginTop": "6px"}),
        ], style={
            "backgroundColor": "rgba(59,130,246,0.05)",
            "border": "1px solid rgba(59,130,246,0.2)",
            "borderRadius": "8px", "padding": "12px",
        }),
    ])


# ════════════════════════════════════════════════════════════════════════════
# CALLBACK 5: APPLY — Lưu profile + cập nhật tất cả filter stores
# ════════════════════════════════════════════════════════════════════════════
@app.callback(
    # Stores cần update
    Output("investor-profile-store",   "data"),
    Output("profile-setup-done",       "data"),
    Output("active-filters-store",     "data"),
    Output("selected-filters-container", "children", allow_duplicate=True),  # ADD THIS
    # Individual filter stores (range)
    Output("filter-roe",               "data"),
    Output("filter-pe",                "data"),
    Output("filter-pb",                "data"),
    Output("filter-de",                "data"),
    Output("filter-current-ratio",     "data"),
    Output("filter-div-yield",         "data"),
    Output("filter-rev-growth-yoy",    "data"),
    Output("filter-eps-growth-yoy",    "data"),
    Output("filter-rs-3m",             "data"),
    Output("filter-net-margin",        "data"),
    # Grade stores
    Output("filter-vgm-score",         "data"),
    Output("filter-value-score",       "data"),
    Output("filter-growth-score",      "data"),
    Output("filter-momentum-score",    "data"),
    Output("filter-canslim",           "data"),
    # Status message
    Output("ips-apply-status",         "children"),

    Input("ips-btn-next",              "n_clicks"),
    State("ips-current-step",          "data"),
    State("ips-goal-store",            "data"),
    State("ips-will-store",            "data"),
    State("ips-pct-savings-slider",    "value"),
    State("ips-emergency-slider",      "value"),
    State("ips-time-store",            "data"),
    State("ips-liq-store",             "data"),
    State("ips-unique-checklist",      "value"),
    State("ips-apply-options",         "value"),
    State("active-filters-store",      "data"),
    # Existing filter states (giữ lại nếu IPS không override)
    State("filter-roe",                "data"),
    State("filter-pe",                 "data"),
    State("filter-pb",                 "data"),
    State("filter-de",                 "data"),
    State("filter-current-ratio",      "data"),
    State("filter-div-yield",          "data"),
    State("filter-rev-growth-yoy",     "data"),
    State("filter-eps-growth-yoy",     "data"),
    State("filter-rs-3m",              "data"),
    State("filter-net-margin",         "data"),
    State("filter-vgm-score",          "data"),
    State("filter-value-score",        "data"),
    State("filter-growth-score",       "data"),
    State("filter-momentum-score",     "data"),
    State("filter-canslim",            "data"),
    prevent_initial_call=True,
)
def apply_ips_profile(
    next_clicks, current_step,
    goal, will, pct_savings, emergency, time_h, liq, unique_flags, apply_options,
    existing_af,
    ex_roe, ex_pe, ex_pb, ex_de, ex_cr, ex_div,
    ex_rev, ex_eps, ex_rs3m, ex_net_margin,
    ex_vgm, ex_val, ex_gro, ex_mom, ex_canslim,
):
    """
    Chỉ chạy khi user bấm Next ở step cuối (step 5).
    Tính profile, build filters, lưu vào stores.

    Sau khi profile-setup-done = True, callback toggle_pages() trong main.py
    tự động ẩn trang onboarding và hiện giao diện screener chính.
    """
    # Chạy khi user bấm Next ở bước 5 (current_step == 5)
    if (current_step or 0) < 4 or not next_clicks:
        raise PreventUpdate

    unique_flags  = unique_flags  or []
    apply_options = apply_options or []

    # ── 1. Tính risk profile ──────────────────────────────────────────────
    profile = compute_risk_profile(
        goal=goal or "growth",
        will=will or "hold",
        pct_savings=pct_savings or 30,
        emergency_months=emergency or 4,
        time_horizon=time_h or "mid",
        liquidity=liq or "low",
    )

    prefer_dividend = "prefer_dividend" in unique_flags
    avoid_bank_re   = "avoid_bank_re"   in unique_flags
    beginner        = "beginner"        in unique_flags

    # ── 2. Build full profile dict (lưu vào investor-profile-store) ───────
    full_profile = {
        # IPS inputs
        "goal":             goal,
        "will":             will,
        "pct_savings":      pct_savings or 30,
        "emergency_months": emergency  or 4,
        "time_horizon":     time_h     or "mid",
        "liquidity":        liq        or "low",
        "prefer_dividend":  prefer_dividend,
        "avoid_bank_re":    avoid_bank_re,
        "beginner":         beginner,
        "prefer_esg":       "prefer_esg" in unique_flags,
        "apply_options":    apply_options,
        # Computed
        **profile,
        # auto_filters đã có trong profile dict — override lại rõ ràng
        "auto_filters": profile["auto_filters"],
        "version": 2,
    }

    # ── 3. Build filter settings ──────────────────────────────────────────
    apply_filters = "apply_filters" in apply_options
    filter_settings = {}
    if apply_filters:
        filter_settings = build_ips_filter_settings(
            profile["risk_profile"], goal, prefer_dividend, avoid_bank_re
        )

    # ── 4. Cập nhật active-filters-store ─────────────────────────────────
    new_af = build_active_filters(filter_settings, existing_af) if apply_filters else (existing_af or {})

    # ── 5. Lấy giá trị mới từng store (dùng existing nếu IPS không override) ──
    def _get(key, existing):
        return filter_settings.get(key, existing)

    new_roe     = _get("filter-roe",           ex_roe)
    new_pe      = _get("filter-pe",            ex_pe)
    new_pb      = _get("filter-pb",            ex_pb)
    new_de      = _get("filter-de",            ex_de)
    new_cr      = _get("filter-current-ratio", ex_cr)
    new_div     = _get("filter-div-yield",     ex_div)
    new_rev     = _get("filter-rev-growth-yoy", ex_rev)
    new_eps_g   = _get("filter-eps-growth-yoy", ex_eps)
    new_rs3m    = _get("filter-rs-3m",         ex_rs3m)
    new_nm      = _get("filter-net-margin",    ex_net_margin)
    new_vgm     = _get("filter-vgm-score",     ex_vgm)
    new_val     = _get("filter-value-score",   ex_val)
    new_gro     = _get("filter-growth-score",  ex_gro)
    new_mom     = _get("filter-momentum-score", ex_mom)
    new_canslim = _get("filter-canslim",       ex_canslim)

    # ── 6. Status message ─────────────────────────────────────────────────
    status = html.Div([
        html.I(className="fas fa-check-circle",
               style={"color": _GREEN, "marginRight": "6px"}),
        html.Span(
            f"Hồ sơ {profile['risk_label_vi']} đã lưu! "
            f"{'Bộ lọc IPS đã áp dụng vào Screener.' if apply_filters else ''}",
            style={"fontSize": "12px", "color": _GREEN,
                   "fontFamily": _FONT_INTER},
        ),
    ])

    logger.info(
        f"[IPS Apply] Profile={profile['risk_profile']} "
        f"Goal={goal} Will={will} "
        f"Filters={'YES' if apply_filters else 'NO'} "
        f"Active filters count={len(new_af)}"
    )

    # Find the end of apply_ips_profile where it returns. Before the return, add this code to build slider cards
    # Build slider UI cards for IPS filters
    ips_slider_cards = []
    if apply_filters and filter_settings:
        from src.callbacks.filter_interaction_callbacks import create_range_filter_ui, get_filter_ranges, CRITERIA_CONFIG
        ranges = get_filter_ranges()
        
        # Label map for IPS filter IDs
        ips_label_map = {
            "filter-roe":            "ROE (%)",
            "filter-pe":             "P/E Ratio",
            "filter-pb":             "P/B Ratio",
            "filter-de":             "D/E (Nợ / VCSH)",
            "filter-current-ratio":  "Thanh toán hiện hành",
            "filter-div-yield":      "Tỷ suất Cổ tức (%)",
            "filter-rev-growth-yoy": "% Tăng trưởng DT 1 năm",
            "filter-eps-growth-yoy": "% Tăng trưởng EPS 1 năm",
            "filter-rs-3m":          "RS 3 tháng",
            "filter-net-margin":     "Biên LN ròng (%)",
        }
        
        for fid, rng in filter_settings.items():
            # FIX Lỗi 1: ValueError - VGM/VALUE score là string ['A','B','C'] nhưng code cố convert sang float
            # Thêm guard: bỏ qua nếu không phải range numeric [lo, hi]
            if not isinstance(rng, list) or len(rng) != 2:
                continue
            try:
                lo, hi = float(rng[0]), float(rng[1])
            except (TypeError, ValueError):
                continue  # Bỏ qua grade filters như ['A','B','C']
            
            if not isinstance(rng, list) or len(rng) != 2:
                continue
            label = ips_label_map.get(fid, fid.replace("filter-", "").replace("-", " ").title())
            if fid in ranges:
                actual_min, actual_max = ranges[fid]
            else:
                actual_min, actual_max = float(rng[0]), float(rng[1])
            ips_slider_cards.append(
                create_range_filter_ui(fid, label, actual_min, actual_max, rng)
            )

    return (
        full_profile,     # investor-profile-store
        True,             # profile-setup-done
        new_af,           # active-filters-store
        ips_slider_cards if apply_filters else [],  # selected-filters-container  ← ADD
        # Range filters
        new_roe, new_pe, new_pb, new_de, new_cr, new_div,
        new_rev, new_eps_g, new_rs3m, new_nm,
        # Grade filters
        new_vgm, new_val, new_gro, new_mom, new_canslim,
        # UI
        status,
    )


# ════════════════════════════════════════════════════════════════════════════
# CALLBACK 6: Xử lý click chọn thẻ (Python Callbacks)
# ════════════════════════════════════════════════════════════════════════════

_BASE_CLASS   = "vss-choice-card"
_ACTIVE_CLASS = "vss-choice-card selected"


# 1. Goal cards (Bước 1 - Mục tiêu)
# ── select_goal ───────────────────────────────────────────────────────────────
# TÌM toàn bộ decorator + hàm select_goal, THAY BẰNG:
 
@app.callback(
    Output("ips-goal-store", "data"),
    Output("ips-step1-error", "children", allow_duplicate=True),
    Output({"type": "ips-choice", "id": "goal-preserve"}, "className"),   # ← "className"
    Output({"type": "ips-choice", "id": "goal-income"},   "className"),
    Output({"type": "ips-choice", "id": "goal-growth"},   "className"),
    Output({"type": "ips-choice", "id": "goal-speculate"},"className"),
    Input({"type": "ips-choice", "id": "goal-preserve"}, "n_clicks"),
    Input({"type": "ips-choice", "id": "goal-income"},   "n_clicks"),
    Input({"type": "ips-choice", "id": "goal-growth"},   "n_clicks"),
    Input({"type": "ips-choice", "id": "goal-speculate"},"n_clicks"),
    prevent_initial_call=True
)
def select_goal(n1, n2, n3, n4):
    ctx = callback_context
    if not ctx.triggered:
        return no_update
    prop_id = ctx.triggered[0]["prop_id"]

    classes = [_BASE_CLASS] * 4          # ← dùng class string

    if "goal-preserve" in prop_id:
        classes[0] = _ACTIVE_CLASS
        return "preserve", "", *classes
    elif "goal-income" in prop_id:
        classes[1] = _ACTIVE_CLASS
        return "income", "", *classes
    elif "goal-growth" in prop_id:
        classes[2] = _ACTIVE_CLASS
        return "growth", "", *classes
    elif "goal-speculate" in prop_id:
        classes[3] = _ACTIVE_CLASS
        return "speculate", "", *classes

    return no_update


# 2. Willingness cards (Bước 2 - Tâm lý)
@app.callback(
    Output("ips-will-store", "data"),
    Output("ips-step2-error", "children", allow_duplicate=True),
    Output({"type": "ips-choice", "id": "will-panic"}, "className"),
    Output({"type": "ips-choice", "id": "will-worry"}, "className"),
    Output({"type": "ips-choice", "id": "will-hold"},  "className"),
    Output({"type": "ips-choice", "id": "will-buy"},   "className"),
    Input({"type": "ips-choice", "id": "will-panic"}, "n_clicks"),
    Input({"type": "ips-choice", "id": "will-worry"}, "n_clicks"),
    Input({"type": "ips-choice", "id": "will-hold"},  "n_clicks"),
    Input({"type": "ips-choice", "id": "will-buy"},   "n_clicks"),
    prevent_initial_call=True
)
def select_will(n1, n2, n3, n4):
    ctx = callback_context
    if not ctx.triggered:
        return no_update
    prop_id = ctx.triggered[0]["prop_id"]

    classes = [_BASE_CLASS] * 4

    if "will-panic" in prop_id:
        classes[0] = _ACTIVE_CLASS
        return "panic", "", *classes
    elif "will-worry" in prop_id:
        classes[1] = _ACTIVE_CLASS
        return "worry", "", *classes
    elif "will-hold" in prop_id:
        classes[2] = _ACTIVE_CLASS
        return "hold", "", *classes
    elif "will-buy" in prop_id:
        classes[3] = _ACTIVE_CLASS
        return "buy", "", *classes

    return no_update


# 3. Time Horizon cards (Bước 3 - Thời gian)
@app.callback(
    Output("ips-time-store", "data"),
    Output({"type": "ips-choice", "id": "time-short"}, "className"),
    Output({"type": "ips-choice", "id": "time-mid"},   "className"),
    Output({"type": "ips-choice", "id": "time-long"},  "className"),
    Input({"type": "ips-choice", "id": "time-short"}, "n_clicks"),
    Input({"type": "ips-choice", "id": "time-mid"},   "n_clicks"),
    Input({"type": "ips-choice", "id": "time-long"},  "n_clicks"),
    prevent_initial_call=True
)
def select_time(n1, n2, n3):
    ctx = callback_context
    if not ctx.triggered:
        return no_update
    prop_id = ctx.triggered[0]["prop_id"]

    classes = [_BASE_CLASS] * 3

    if "time-short" in prop_id:
        classes[0] = _ACTIVE_CLASS
        return "short", *classes
    elif "time-mid" in prop_id:
        classes[1] = _ACTIVE_CLASS
        return "mid", *classes
    elif "time-long" in prop_id:
        classes[2] = _ACTIVE_CLASS
        return "long", *classes

    return no_update


# 4. Liquidity cards (Bước 3 - Thanh khoản)
@app.callback(
    Output("ips-liq-store", "data"),
    Output({"type": "ips-choice", "id": "liq-high"}, "className"),
    Output({"type": "ips-choice", "id": "liq-mid"},  "className"),
    Output({"type": "ips-choice", "id": "liq-low"},  "className"),
    Input({"type": "ips-choice", "id": "liq-high"}, "n_clicks"),
    Input({"type": "ips-choice", "id": "liq-mid"},  "n_clicks"),
    Input({"type": "ips-choice", "id": "liq-low"},  "n_clicks"),
    prevent_initial_call=True
)
def select_liq(n1, n2, n3):
    ctx = callback_context
    if not ctx.triggered:
        return no_update
    prop_id = ctx.triggered[0]["prop_id"]

    classes = [_BASE_CLASS] * 3

    if "liq-high" in prop_id:
        classes[0] = _ACTIVE_CLASS
        return "high", *classes
    elif "liq-mid" in prop_id:
        classes[1] = _ACTIVE_CLASS
        return "mid", *classes
    elif "liq-low" in prop_id:
        classes[2] = _ACTIVE_CLASS
        return "low", *classes

    return no_update

# ════════════════════════════════════════════════════════════════════════════
# CALLBACK: BỎ QUA KHẢO SÁT → vào thẳng screener với Toàn thị trường
# ════════════════════════════════════════════════════════════════════════════
@app.callback(
    Output("profile-setup-done",   "data",  allow_duplicate=True),
    Output("trading-mode-store",   "data",  allow_duplicate=True),
    Output("investor-profile-store","data", allow_duplicate=True),
    Input("btn-skip-onboarding",   "n_clicks"),
    prevent_initial_call=True,
)
def skip_onboarding(n_clicks):
    if not n_clicks:
        raise PreventUpdate
    # Profile tối thiểu để hệ thống không hỏi lại
    minimal_profile = {
        "risk_profile": "moderate",
        "auto_filters": {"min_vol": 0, "min_cap": 0, "min_price": 0},
        "skipped": True,
        "version": 2,
    }
    return True, "all_market", minimal_profile