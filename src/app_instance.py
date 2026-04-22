# src/app_instance.py
import dash
import dash_bootstrap_components as dbc
import os

# Đường dẫn thư mục assets
ASSETS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'assets')

# Khởi tạo App với theme CYBORG (Dark theme) + Custom CSS & JS
app = dash.Dash(
    __name__, 
    external_stylesheets=[
        dbc.themes.CYBORG,  # Dark theme chính
        "https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css",  # Icons
        # Google Fonts: Roboto Mono (số thẳng hàng) + Inter (UI) + Sora (heading)
        "https://fonts.googleapis.com/css2?family=Roboto+Mono:wght@400;500;600&family=Inter:wght@400;500;600;700&family=Sora:wght@600;700;800&family=Barlow+Semi+Condensed:wght@600;700&display=swap",
    ],
    title="Vietcap Screener - iBoard",
    meta_tags=[
        {"name": "viewport", "content": "width=device-width, initial-scale=1"}
    ],
    assets_folder=ASSETS_PATH,  # Thư mục chứa CSS/JS custom
    # 🟢 THÊM DÒNG NÀY ĐỂ KHÔNG BỊ CRASH KHI DÙNG TOUR GUIDE
    suppress_callback_exceptions=True
)

server = app.server

# Đảm bảo assets folder tồn tại
if not os.path.exists(ASSETS_PATH):
    os.makedirs(ASSETS_PATH)
    print(f"📁 Đã tạo thư mục assets: {ASSETS_PATH}")