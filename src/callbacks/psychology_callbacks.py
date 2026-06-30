# src/callbacks/psychology_callbacks.py
"""
callbacks cho tính năng trạm cứu viện tâm lý

CẬP NHẬT MỚI:
- Thêm Nhóm F (FOMO ngược) vào danh sách nỗi sợ được gom lại.
- Callback "Kiểm chứng ngay" chuyển sang BACKGROUND CALLBACK (dùng sẵn
  background_callback_manager đã cấu hình trong app_instance.py) để tạo
  hiệu ứng "Chánh niệm tài chính" (Mindful Delay): vài thông điệp xoay vòng
  trong ~2-3 giây trước khi hiện kết quả — đủ để khách hàng/môi giới kịp hít
  một hơi thay vì đọc-quyết định trong tích tắc. Đây KHÔNG phải sleep() chặn
  server, vì DiskcacheManager chạy callback trong worker riêng.
- Render thêm 2 "wow factor" trả về từ analyze_fear(): peer_context (Đồng
  cảnh ngộ — so hiệu suất 1 tuần với trung vị ngành) và stress_test (Kịch
  bản chống chịu — số tháng cầm cự bằng đệm tiền mặt ròng).
"""
import time
from dash import Input, Output, State, html, no_update
import dash_bootstrap_components as dbc
from datetime import datetime

from src.app_instance import app, background_callback_manager
from src.backend.psychology_engine import analyze_fear
from src.backend.data_loader import get_ticker_list

verdict_style = {
    "safe":    {"color": "success",   "icon": "fa-solid fa-shield-heart",          "label": "an toàn"},
    "watch":   {"color": "warning",   "icon": "fa-solid fa-eye",                   "label": "cần theo dõi"},
    "risk":    {"color": "danger",    "icon": "fa-solid fa-triangle-exclamation",  "label": "rủi ro thật"},
    "neutral": {"color": "secondary", "icon": "fa-solid fa-circle-question",       "label": "chưa đủ dữ liệu"},
}

# Thông điệp xoay vòng cho hiệu ứng "Chánh niệm tài chính" (Mindful Delay)
MINDFUL_MESSAGES = [
    "🔍 Đang thu thập dữ liệu...",
    "📊 Đang đối chiếu lịch sử & trung vị ngành...",
    "🧘 Hãy hít một hơi thật sâu trước khi đọc kết quả...",
]


@app.callback(
    Output("psy-clinic-modal", "is_open"),
    Input("btn-open-psy-clinic", "n_clicks"),
    Input("psy-clinic-close-btn", "n_clicks"),
    State("psy-clinic-modal", "is_open"),
    prevent_initial_call=True,
)
def toggle_psy_clinic_modal(n_open, n_close, is_open):
    return not is_open


@app.callback(
    Output("psy-clinic-ticker-input", "options"),
    Input("psy-clinic-modal", "is_open"),
    prevent_initial_call=True,
)
def load_psy_clinic_ticker_options(is_open):
    if not is_open:
        return no_update
    return get_ticker_list() or []


# ─────────────────────────────────────────────────────────────────────────
# Render helpers cho 2 wow-factor mới
# ─────────────────────────────────────────────────────────────────────────
def _render_peer_context(peer_context):
    if not peer_context:
        return None
    is_reassure = peer_context["tone"] == "reassure"
    color = "info" if is_reassure else "warning"
    icon = "fa-solid fa-people-group" if is_reassure else "fa-solid fa-magnifying-glass-chart"
    return dbc.Alert(
        [
            html.I(className=f"{icon} me-2"),
            html.Strong("Đồng cảnh ngộ — "),
            peer_context["message"],
        ],
        color=color, className="mb-3 psy-peer-context fst-italic",
    )


def _render_stress_test(stress_test):
    if not stress_test:
        return None
    icon = html.I(className="fa-solid fa-heart-pulse me-2")
    title = html.Span("Kịch bản chống chịu (doanh thu giảm 50%)", className="fw-bold")

    if not stress_test["applicable"]:
        body = [
            html.Div([icon, title], className="d-flex align-items-center mb-2"),
            html.P(stress_test["message"], className="mb-0 small psy-text-main"),
        ]
        return dbc.Card(dbc.CardBody(body), color="secondary", outline=True, className="mb-2")

    if stress_test["still_profitable"]:
        body = [
            html.Div([
                icon, title,
                dbc.Badge("Vững vàng", color="success", className="ms-auto"),
            ], className="d-flex align-items-center mb-2"),
            html.P(stress_test["message"], className="mb-0 small psy-text-main"),
        ]
        return dbc.Card(dbc.CardBody(body), color="success", outline=True, className="mb-2")

    months = stress_test["runway_months"] or 0
    pct = min(100, round(months / 24 * 100))  # cap thanh progress ở mốc 24 tháng cho dễ nhìn
    bar_color = "success" if months >= 12 else ("warning" if months >= 6 else "danger")

    body = [
        html.Div([
            icon, title,
            dbc.Badge(f"~{months} tháng", color=bar_color, className="ms-auto"),
        ], className="d-flex align-items-center mb-2"),
        dbc.Progress(value=pct, color=bar_color, className="mb-2", style={"height": "10px"}),
        html.P(stress_test["message"], className="mb-0 small psy-text-main"),
    ]
    return dbc.Card(dbc.CardBody(body), color=bar_color, outline=True, className="mb-2")


# ─────────────────────────────────────────────────────────────────────────
# Callback chính — BACKGROUND CALLBACK (xem ghi chú đầu file)
# ─────────────────────────────────────────────────────────────────────────
@app.callback(
    Output("psy-clinic-result", "children"),
    Output("psy-history-store", "data"),
    Input("psy-clinic-submit-btn", "n_clicks"),
    State("psy-clinic-ticker-input", "value"),
    State("psy-clinic-fear-checklist-a", "value"),
    State("psy-clinic-fear-checklist-b", "value"),
    State("psy-clinic-fear-checklist-c", "value"),
    State("psy-clinic-fear-checklist-d", "value"),
    State("psy-clinic-fear-checklist-e", "value"),
    State("psy-clinic-fear-checklist-f", "value"),
    State("investor-profile-store", "data"),
    State("psy-history-store", "data"),
    background=True,
    manager=background_callback_manager,
    progress=[Output("psy-clinic-progress-text", "children")],
    running=[
        (Output("psy-clinic-submit-btn", "disabled"), True, False),
        (Output("psy-clinic-progress-text", "style"), {"display": "block"}, {"display": "none"}),
    ],
    prevent_initial_call=True,
)
def run_psy_clinic_check(set_progress, n_clicks, ticker, fears_a, fears_b, fears_c, fears_d, fears_e, fears_f, profile_data, history_data):
    history_data = history_data or []
    selected_fears = [
        *(fears_a or []), *(fears_b or []), *(fears_c or []),
        *(fears_d or []), *(fears_e or []), *(fears_f or []),
    ]

    if not ticker:
        return dbc.Alert("vui lòng chọn mã cổ phiếu trước khi kiểm chứng.", color="warning", className="mb-0"), history_data
    if not selected_fears:
        return dbc.Alert("vui lòng chọn ít nhất 1 nỗi sợ trong các nhóm.", color="warning", className="mb-0"), history_data

    # "Chánh niệm tài chính" — tạm dừng có chủ đích, không chặn server vì
    # đây là background callback chạy ở worker riêng (DiskcacheManager).
    for msg in MINDFUL_MESSAGES:
        set_progress(msg)
        time.sleep(0.9)

    result = analyze_fear(ticker, selected_fears, profile_data)

    if result["status"] == "not_found":
        return dbc.Alert(f"không tìm thấy dữ liệu cho mã '{result['ticker']}'.", color="danger", className="mb-0"), history_data
    if result["status"] == "error":
        return dbc.Alert("có lỗi khi truy xuất dữ liệu, thử lại sau.", color="danger", className="mb-0"), history_data
    if result["status"] != "ok" or not result["results"]:
        return dbc.Alert("không có kết quả để hiển thị.", color="secondary", className="mb-0"), history_data

    # logic tài chính hành vi
    behavioral_msg = None
    past_records = [r for r in history_data if r['ticker'] == ticker]

    if past_records:
        last_record = past_records[-1]
        try:
            last_date = datetime.fromisoformat(last_record['date'])
            seconds_ago = (datetime.now() - last_date).total_seconds()

            if seconds_ago > 5:
                behavioral_msg = dbc.Alert(
                    [
                        html.I(className="fa-solid fa-clock-rotate-left me-2"),
                        f"hệ thống ghi nhận bạn đã từng kiểm chứng mã {ticker} gần đây. ",
                        "hãy bình tĩnh nhìn vào số liệu nền tảng hiện tại thay vì bán tháo theo đám đông nhé."
                    ],
                    color="info",
                    className="mb-3 fst-italic shadow-sm",
                )
        except Exception:
            pass

    history_data.append({
        'ticker': ticker,
        'date': datetime.now().isoformat()
    })

    # xử lý nhãn hồ sơ rủi ro
    profile_str = str(profile_data).lower() if profile_data else ""
    if any(k in profile_str for k in ["bảo thủ", "an toàn", "thấp", "low"]):
        risk_label, badge_color = "bảo thủ", "success"
    elif any(k in profile_str for k in ["mạo hiểm", "tăng trưởng", "cao", "high"]):
        risk_label, badge_color = "mạo hiểm", "danger"
    else:
        risk_label, badge_color = "cân bằng / mặc định", "info"

    # tạo phần header kết quả
    header = html.Div([
        html.Div([
            html.Span(result["ticker"], className="fw-bold fs-5 me-2 psy-text-main"),
            html.Span(result.get("company") or "", className="psy-text-muted small"),
        ]),
        html.Div([
            html.Span("phân tích được tinh chỉnh theo hồ sơ:", className="psy-text-muted small fst-italic"),
            dbc.Badge(risk_label, color=badge_color, className="ms-1", pill=True)
        ], className="mt-1 d-flex align-items-center")
    ], className="mb-4")

    cards = [header]
    if behavioral_msg:
        cards.append(behavioral_msg)

    # Wow factor 1: Đồng cảnh ngộ (peer context) — hiện ngay sau header, trước
    # các thẻ chi tiết, vì đây là context tổng quan giúp định hình tâm lý
    peer_card = _render_peer_context(result.get("peer_context"))
    if peer_card:
        cards.append(peer_card)

    # tạo các thẻ chi tiết nỗi sợ
    for item in result["results"]:
        style = verdict_style.get(item["verdict"], verdict_style["neutral"])
        metrics_badges = [
            dbc.Badge(f"{name}: {value}", color="light", text_color="dark", className="me-2 mb-1")
            for name, value in item.get("metrics", [])
        ]

        card_children = [
            html.Div([
                html.I(className=f"{style['icon']} me-2"),
                html.Span(item["title"], className="fw-bold"),
                dbc.Badge(style["label"], color=style["color"], className="ms-auto"),
            ], className="d-flex align-items-center mb-2"),
        ]

        if metrics_badges:
            card_children.append(html.Div(metrics_badges, className="mb-2"))

        card_children.append(html.P(item["conclusion"], className="mb-0 small psy-text-main"))

        cards.append(dbc.Card(dbc.CardBody(card_children), color=style["color"], outline=True, className="mb-2"))

    # Wow factor 2: Kịch bản chống chịu (stress test) — hiện sau cùng, như
    # một "kết luận tổng hợp" về sức bền của doanh nghiệp
    stress_card = _render_stress_test(result.get("stress_test"))
    if stress_card:
        cards.append(stress_card)

    return html.Div(cards), history_data