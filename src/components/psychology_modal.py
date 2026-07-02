# src/components/psychology_modal.py
"""
Trạm Cứu Viện Tâm Lý — Rumor Check Modal.
Bám sát Framework 4 Trụ Cột (Vi mô): Cơ cấu vốn, Cơ cấu cổ đông,
Mô hình kinh doanh, Định giá — mở rộng thêm Nhóm B (Hiệu quả & Tiền mặt)
và Nhóm C (Biến động giá ngắn hạn) để bám sát hơn các tình huống hoảng loạn
thực tế khi khách hàng nhìn bảng điện đỏ lửa.

Chỉ chứa UI Layout — không state, không xử lý số liệu (xem
src/backend/psychology_engine.py và src/callbacks/psychology_callbacks.py).

GHI CHÚ FIX BUG (so với bản trước):
- KHÔNG dùng scrollable=True trên dbc.Modal nữa. Lý do: scrollable=True làm
  Bootstrap set overflow-y:auto/hidden cho .modal-body, dẫn tới menu gợi ý
  (popup) của dcc.Dropdown bị CẮT MẤT khi nó tràn ra ngoài khung — đây chính
  là lý do bạn gõ mã mà không thấy gợi ý nào hiện ra. Bỏ scrollable đi thì
  modal sẽ tự giãn theo nội dung và trang ngoài cuộn, dropdown không bị cắt.
- Thêm className "psy-clinic-modal" + các id để file CSS đi kèm
  (assets/psychology_clinic.css) style riêng, có theme sáng/tối.
"""
from dash import html, dcc
import dash_bootstrap_components as dbc

# ── Nhóm A — Sức khỏe & Định giá (Vi mô / Framework 4 Trụ gốc) ─────────────
FEAR_OPTIONS_A = [
    {"label": "Sợ công ty vỡ nợ / mất khả năng thanh toán ngắn hạn", "value": "A1"},
    {"label": "Sợ doanh nghiệp nợ vay đầm đìa, rủi ro cao",          "value": "A2"},
    {"label": "Sợ kinh doanh cốt lõi đang đi lùi",                   "value": "A3"},
    {"label": "Sợ giá này đang là bong bóng so với giá trị thực",    "value": "A4"},
]

# ── Nhóm B — Hiệu quả sinh lời & Tiền mặt (mở rộng mới) ────────────────────
FEAR_OPTIONS_B = [
    {"label": "Sợ doanh nghiệp làm ăn không hiệu quả (ROE/ROA thấp)", "value": "B1"},
    {"label": "Sợ công ty hết tiền mặt, không đủ sức chống chọi khó khăn", "value": "B2"},
]

# ── Nhóm C — Biến động giá ngắn hạn (mở rộng mới — trực diện tâm lý hoảng loạn) ──
FEAR_OPTIONS_C = [
    {"label": "Sợ giá đã giảm quá sâu, không biết đáy ở đâu", "value": "C1"},
    {"label": "Sợ xu hướng giá đã gãy, phải cắt lỗ ngay",      "value": "C2"},
]

# ── Nhóm D — FOMO ngược (đổi tên từ "Nhóm F" — chặn lệnh MUA sai cũng quan
# trọng không kém chặn lệnh bán tháo) ──────────────────────────────────────
FEAR_OPTIONS_D = [
    {"label": "Thấy người ta lãi mã này nhiều quá, sợ mua bây giờ là đu đỉnh", "value": "D1"},
]

# ── Nhóm E — Thanh khoản & Biến động (mở rộng mới) ─────────────────────────
FEAR_OPTIONS_E = [
    {"label": "Sợ cổ phiếu thanh khoản thấp, lỡ mua thì khó bán ra", "value": "E1"},
    {"label": "Sợ cổ phiếu này biến động mạnh hơn hẳn thị trường chung", "value": "E2"},
]

# ── Nhóm F — Tăng trưởng & Cổ tức (mở rộng mới) ────────────────────────────
FEAR_OPTIONS_F = [
    {"label": "Sợ doanh nghiệp tăng trưởng ì ạch, hết động lực dài hạn", "value": "F1"},
    {"label": "Sợ nắm giữ mà không có cổ tức, chẳng được gì ngoài chênh lệch giá", "value": "F2"},
]


def _fear_section(title: str, subtitle: str, checklist_id: str, options: list) -> html.Div:
    """Block 1 nhóm câu hỏi, có tiêu đề + mô tả ngắn, dùng chung style."""
    return html.Div(className="psy-clinic-section", children=[
        html.Div(className="psy-clinic-section-head", children=[
            html.Span(title, className="psy-clinic-section-title"),
            html.Span(subtitle, className="psy-clinic-section-subtitle"),
        ]),
        dbc.Checklist(
            id=checklist_id,
            options=options,
            value=[],
            switch=True,
            className="psy-clinic-checklist mb-3",
        ),
    ])

def create_psychology_tab_content() -> html.Div:
    """Trả về nội dung tab TÂM LÝ — nhúng vào detail_tabs trong screener.py.
    Không còn là Modal riêng — giờ sống chung trong popup chi tiết mã."""
    return html.Div(
        id="psy-clinic-panel",
        className="psy-clinic-panel",
        children=[
            html.P(
                "Chọn nỗi sợ khách hàng đang gặp phải với mã cổ phiếu này. "
                "Hệ thống sẽ truy xuất dữ liệu cứng để phản bác tin đồn "
                "ngay trong phiên giao dịch.",
                className="psy-clinic-intro mb-3",
            ),

            dbc.Label("Mã cổ phiếu", html_for="psy-clinic-ticker-input",
                      className="fw-bold psy-clinic-label"),
            dcc.Dropdown(
                id="psy-clinic-ticker-input",
                options=[],
                placeholder="Gõ để tìm mã hoặc tên công ty...",
                searchable=True,
                clearable=True,
                className="mb-4 psy-clinic-ticker-dropdown",
            ),

            _fear_section(
                "Nhóm A · Sức khỏe & Định giá",
                "Cơ cấu vốn, thanh khoản, định giá so với ngành",
                "psy-clinic-fear-checklist-a", FEAR_OPTIONS_A,
            ),
            _fear_section(
                "Nhóm B · Hiệu quả sinh lời & Tiền mặt",
                "ROE/ROA so với ngành, vị thế tiền mặt ròng",
                "psy-clinic-fear-checklist-b", FEAR_OPTIONS_B,
            ),
            _fear_section(
                "Nhóm C · Biến động giá ngắn hạn",
                "Mức điều chỉnh so với đỉnh/đáy 1 năm, xu hướng MA",
                "psy-clinic-fear-checklist-c", FEAR_OPTIONS_C,
            ),
            _fear_section(
                "Nhóm D · FOMO ngược — sợ mua đu đỉnh",
                "RSI, hiệu suất gần đây, định giá so với ngành",
                "psy-clinic-fear-checklist-d", FEAR_OPTIONS_D,
            ),
            _fear_section(
                "Nhóm E · Thanh khoản & Biến động",
                "Giá trị giao dịch bình quân, Beta so với thị trường",
                "psy-clinic-fear-checklist-e", FEAR_OPTIONS_E,
            ),
            _fear_section(
                "Nhóm F · Tăng trưởng & Cổ tức",
                "EPS CAGR 5 năm so với ngành, tỷ suất cổ tức",
                "psy-clinic-fear-checklist-f", FEAR_OPTIONS_F,
            ),

            dbc.Button(
                [html.I(className="fa-solid fa-magnifying-glass-chart me-2"), "Kiểm chứng ngay"],
                id="psy-clinic-submit-btn",
                color="primary",
                className="w-100 mb-3 psy-clinic-submit-btn",
                n_clicks=0,
            ),

            html.Div(
                id="psy-clinic-progress-text",
                className="psy-clinic-mindful-text",
                style={"display": "none"},
            ),

            dcc.Loading(
                id="psy-clinic-loading",
                type="circle",
                children=html.Div(id="psy-clinic-result"),
            ),
        ],
    )


# Instance dùng chung — import thẳng vào screener.py làm children của dbc.Tab
psychology_tab_content = create_psychology_tab_content()