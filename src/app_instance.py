# src/app_instance.py
import dash
import dash_bootstrap_components as dbc
import os
import logging
# THAY ĐỔI CÁCH IMPORT Ở 2 DÒNG NÀY:
from diskcache import Cache
from dash import DiskcacheManager

logger = logging.getLogger(__name__)

# Đường dẫn thư mục assets
ASSETS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'assets')

# Khởi tạo cache trực tiếp từ Class
cache = Cache(os.path.join(os.path.dirname(__file__), "..", "cache"))
background_callback_manager = DiskcacheManager(cache)

# Khởi tạo App với theme CYBORG (Dark theme) + Custom CSS & JS
app = dash.Dash(
    __name__,
    background_callback_manager=background_callback_manager,
    external_stylesheets=[
        dbc.themes.CYBORG,  # Dark theme chính
        "https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css",  # Icons
        # Google Fonts: Roboto Mono (số thẳng hàng) + Inter (UI) + Sora (heading)
        "https://fonts.googleapis.com/css2?family=Roboto+Mono:wght@400;500;600&family=Inter:wght@400;500;600;700&family=Sora:wght@600;700;800&family=Barlow+Semi+Condensed:wght@600;700&display=swap",
    ],
    title="FinSmartScreener - iBoard",
    update_title=None,                # 🚀 TẮT TÍNH NĂNG CHỚP NHÁY "UPDATING..." CỦA DASH
    meta_tags=[
        {"name": "viewport", "content": "width=device-width, initial-scale=1"}
    ],
    assets_folder=ASSETS_PATH,  # Thư mục chứa CSS/JS custom
    # 🟢 THÊM DÒNG NÀY ĐỂ KHÔNG BỊ CRASH KHI DÙNG TOUR GUIDE
    suppress_callback_exceptions=True
)

# Thêm SAU dòng khởi tạo app:
app.index_string = '''
<!DOCTYPE html>
<html>
    <head>
        {%metas%}
        <title>{%title%}</title>
        <link rel="icon" type="image/x-icon" href="/assets/favicon.ico">
        <link rel="shortcut icon" type="image/x-icon" href="/assets/favicon.ico">
        {%favicon%}
        {%css%}
    </head>
    <body>
        {%app_entry%}
        <footer>
            {%config%}
            {%scripts%}
            {%renderer%}
        </footer>
    </body>
</html>
'''

server = app.server

# AUDIT FIX (mục 15 - Security, CSRF): app KHÔNG dùng flask.session/cookie
# cho auth (đã xác nhận: không có SECRET_KEY, không có session ở bất kỳ
# đâu trong codebase) — auth-store nằm trong localStorage và được gửi rõ
# ràng qua Dash State, không phải cookie tự động đính kèm bởi trình duyệt.
# Vì vậy CSRF token kiểu truyền thống (bảo vệ cookie-based session) không
# phải lớp phòng vệ phù hợp nhất ở đây.
#
# Rủi ro thực tế còn lại: MỌI callback (login, redeem-code, filter...) đều
# POST vào CHUNG một endpoint `/_dash-update-component`. Không có gì ngăn
# một trang web bên ngoài (site độc hại) tạo request cross-origin tới
# endpoint này. Lớp phòng vệ tiêu chuẩn cho JSON API kiểu SPA không cookie
# là kiểm tra Origin/Referer — nếu request không đến từ chính domain của
# app, từ chối trước khi Dash xử lý callback.
_ALLOWED_ORIGINS_ENV = os.environ.get("FSS_ALLOWED_ORIGINS", "")
_ALLOWED_ORIGIN_HOSTS = {h.strip() for h in _ALLOWED_ORIGINS_ENV.split(",") if h.strip()}


def should_block_cross_origin(method: str, path: str, origin_header: str, request_host: str,
                                extra_allowed_hosts: set | None = None) -> bool:
    """
    Logic thuần (không phụ thuộc flask.request) cho CSRF-guard, tách riêng
    để unit test được mà không cần load toàn bộ app/dữ liệu (xem
    tests/test_csrf_guard.py).

    Trả về True nếu request PHẢI bị chặn (403).
    """
    if method != "POST" or not path.startswith("/_dash-update-component"):
        return False

    if not origin_header:
        # Không có Origin/Referer -> không chặn tuyệt đối (một số client hợp lệ
        # không gửi header này), chỉ log cảnh báo ở nơi gọi.
        return False

    from urllib.parse import urlparse
    origin_host = urlparse(origin_header).netloc
    if not origin_host:
        return False

    allowed_hosts = _ALLOWED_ORIGIN_HOSTS | {request_host} | (extra_allowed_hosts or set())
    return origin_host not in allowed_hosts


@server.before_request
def _verify_same_origin_for_dash_callbacks():
    from flask import request, abort

    origin = request.headers.get("Origin") or request.headers.get("Referer") or ""

    if request.method == "POST" and request.path.startswith("/_dash-update-component") and not origin:
        logger.warning("[CSRF-guard] POST tới /_dash-update-component không có Origin/Referer header.")
        return

    if should_block_cross_origin(request.method, request.path, origin, request.host):
        from urllib.parse import urlparse
        logger.warning(
            f"[CSRF-guard] CHẶN request cross-origin tới /_dash-update-component: "
            f"origin='{urlparse(origin).netloc}' != host='{request.host}'"
        )
        abort(403, description="Cross-origin request rejected.")

# Đảm bảo assets folder tồn tại
if not os.path.exists(ASSETS_PATH):
    os.makedirs(ASSETS_PATH)
    print(f"📁 Đã tạo thư mục assets: {ASSETS_PATH}")