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

# ── Nhóm A — Sức khỏe & Định giá ─────────────
FEAR_OPTIONS_A = [
    {"label": "Sợ công ty cạn tiền, mất khả năng thanh toán các khoản nợ đến hạn", "value": "A1"},
    {"label": "Sợ doanh nghiệp đang vay nợ đầm đìa, rủi ro tài chính cao",          "value": "A2"},
    {"label": "Sợ hoạt động kinh doanh cốt lõi thực chất đang đi lùi",             "value": "A3"},
    {"label": "Sợ mức giá hiện tại chỉ là 'bong bóng' bơm thổi, vượt xa giá trị",  "value": "A4"},
]

# ── Nhóm B — Hiệu quả sinh lời & Tiền mặt ────────────────────
FEAR_OPTIONS_B = [
    {"label": "Sợ công ty làm ăn kém hiệu quả, 'to xác' nhưng biên lợi nhuận thấp", "value": "B1"},
    {"label": "Sợ két sắt công ty rỗng tuếch, không có 'bộ đệm' chống chọi khó khăn", "value": "B2"},
]

# ── Nhóm C — Biến động giá ngắn hạn ──
FEAR_OPTIONS_C = [
    {"label": "Giá đã giảm quá sâu, sợ mua vào là 'bắt dao rơi' không thấy đáy", "value": "C1"},
    {"label": "Biểu đồ giá trông có vẻ đã 'gãy' xu hướng, phân vân có nên cắt lỗ",      "value": "C2"},
]

# ── Nhóm D — FOMO ngược ──────────────────────────────────────
FEAR_OPTIONS_D = [
    {"label": "Thấy cổ phiếu tăng nóng, sợ mua vào bây giờ là thành 'người đu đỉnh'", "value": "D1"},
]

# ── Nhóm E — Thanh khoản & Biến động ─────────────────────────
FEAR_OPTIONS_E = [
    {"label": "Sợ thanh khoản lèo tèo, lúc thị trường sập muốn bán tháo cũng không ai mua", "value": "E1"},
    {"label": "Sợ mã này giao dịch quá sốc, giật lên xuống mạnh hơn hẳn thị trường chung", "value": "E2"},
]

# ── Nhóm F — Tăng trưởng & Cổ tức ────────────────────────────
FEAR_OPTIONS_F = [
    {"label": "Sợ doanh nghiệp đã qua thời hoàng kim, cạn kiệt động lực tăng trưởng", "value": "F1"},
    {"label": "Sợ ôm cổ phiếu mòn mỏi nhưng lãnh đạo 'ki bo', không chịu chia cổ tức tiền mặt", "value": "F2"},
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
    """Trả về nội dung tab TÂM LÝ — nhúng vào detail_tabs trong screener.py."""
    return html.Div(
        id="psy-clinic-panel",
        className="psy-clinic-panel",
        children=[
            # Chỉnh sửa phần Intro để hướng tới Khách hàng thay vì Môi giới
            html.P(
                "Khép lại những tin đồn trên diễn đàn, hãy để Dữ liệu lên tiếng. "
                "Chọn điều bạn đang lo ngại nhất về cổ phiếu này, hệ thống sẽ đối chiếu ngay lập tức "
                "với sức khỏe tài chính thực tế để giúp bạn ra quyết định khách quan.",
                className="psy-clinic-intro mb-4",
            ),

            dbc.Label("Mã cổ phiếu cần kiểm chứng", html_for="psy-clinic-ticker-input",
                      className="fw-bold psy-clinic-label text-primary"),
            dcc.Dropdown(
                id="psy-clinic-ticker-input",
                options=[],
                placeholder="Gõ để tìm mã hoặc tên công ty...",
                searchable=True,
                clearable=True,
                className="mb-4 psy-clinic-ticker-dropdown",
            ),

            # Đổi Subtitle từ các thuật ngữ hàn lâm (ROE, Beta, CAGR) thành ý nghĩa thực tế
            _fear_section(
                "1. Nền tảng sinh tồn & Định giá",
                "Hệ thống sẽ 'soi' cấu trúc nợ, dòng tiền tự do và định giá so với đối thủ",
                "psy-clinic-fear-checklist-a", FEAR_OPTIONS_A,
            ),
            _fear_section(
                "2. Năng lực kiếm tiền & Bộ đệm phòng thủ",
                "Đánh giá hiệu suất sinh lời thực tế và lượng tiền mặt tích lũy trong két",
                "psy-clinic-fear-checklist-b", FEAR_OPTIONS_B,
            ),
            _fear_section(
                "3. Áp lực tâm lý từ Bảng điện",
                "Đo lường mức độ hoảng loạn của dòng tiền và định vị lại xu hướng giá",
                "psy-clinic-fear-checklist-c", FEAR_OPTIONS_C,
            ),
            _fear_section(
                "4. Bẫy tâm lý FOMO (Sợ lỡ cơ hội)",
                "Đối chiếu sức nóng hiện tại với lịch sử định giá để tránh mua đuổi",
                "psy-clinic-fear-checklist-d", FEAR_OPTIONS_D,
            ),
            _fear_section(
                "5. Rủi ro kẹt hàng & Đội lái",
                "Phân tích dòng tiền giao dịch thực tế và biên độ trồi sụt của cổ phiếu",
                "psy-clinic-fear-checklist-e", FEAR_OPTIONS_E,
            ),
            _fear_section(
                "6. Động lực tương lai & Quyền lợi cổ đông",
                "Kiểm tra tính bền vững của tốc độ tăng trưởng và lịch sử chia tiền mặt",
                "psy-clinic-fear-checklist-f", FEAR_OPTIONS_F,
            ),

            # Sửa Text của Nút bấm cho "kêu" hơn, mang tính hành động cao
            dbc.Button(
                [html.I(className="fa-solid fa-stethoscope me-2"), "Kiểm chứng bằng Dữ liệu"],
                id="psy-clinic-submit-btn",
                color="primary",
                className="w-100 mb-3 psy-clinic-submit-btn mt-2",
                style={"fontWeight": "bold", "padding": "12px", "fontSize": "16px"},
                n_clicks=0,
            ),

            html.Div(
                id="psy-clinic-progress-text",
                className="psy-clinic-mindful-text text-center text-muted fst-italic",
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