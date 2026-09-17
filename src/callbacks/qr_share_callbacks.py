# src/callbacks/qr_share_callbacks.py
# Tính năng "Mở trên điện thoại" — sinh QR code trỏ tới URL hiện tại của app
# để người dùng quét bằng camera điện thoại, mở thẳng bản mobile-responsive.
#
# Toàn bộ logic chạy CLIENTSIDE (JS trong trình duyệt), vì:
#   1. Cần window.location.href thật (origin công khai) — backend đứng sau
#      reverse proxy / Hugging Face Spaces không biết chắc hostname public.
#   2. Không cần round-trip server cho một thao tác thuần UI.
#
# QR ảnh được render qua API ảnh tĩnh (api.qrserver.com) — không cần bundle
# thêm thư viện JS, không tốn thêm request tới backend của chính app.

from dash import Input, Output, State

from src.app_instance import app

# ── Mở / đóng modal ─────────────────────────────────────────────────────────
# Dùng app.clientside_callback (bound method) thay vì clientside_callback rời
# (dash.clientside_callback) — bản rời đăng ký vào GLOBAL_CALLBACK_LIST/MAP
# toàn cục thay vì thẳng vào app.callback_map của instance, nên tránh dùng
# để không phụ thuộc vào thời điểm/đường merge nội bộ của Dash.
app.clientside_callback(
    """
    function(n_open, n_close, is_open) {
        const ctx = dash_clientside.callback_context;
        if (!ctx || !ctx.triggered || !ctx.triggered.length) {
            return false;
        }
        const triggeredId = ctx.triggered[0].prop_id.split('.')[0];
        if (triggeredId === 'btn-open-qr-modal') {
            return true;
        }
        if (triggeredId === 'btn-close-qr-modal') {
            return false;
        }
        return is_open;
    }
    """,
    Output("qr-share-modal", "is_open"),
    Input("btn-open-qr-modal", "n_clicks"),
    Input("btn-close-qr-modal", "n_clicks"),
    State("qr-share-modal", "is_open"),
    prevent_initial_call=True,
)

# ── Khi modal mở: build QR image + điền URL hiện tại ────────────────────────
app.clientside_callback(
    """
    function(is_open) {
        if (!is_open) {
            return [dash_clientside.no_update, dash_clientside.no_update, ""];
        }
        const currentUrl = window.location.href;
        const qrSrc = "https://api.qrserver.com/v1/create-qr-code/?size=240x240&margin=8&data="
            + encodeURIComponent(currentUrl);
        return [qrSrc, currentUrl, ""];
    }
    """,
    Output("qr-share-img", "src"),
    Output("qr-share-url-input", "value"),
    Output("qr-copy-feedback", "children"),
    Input("qr-share-modal", "is_open"),
    prevent_initial_call=True,
)

# ── Copy link vào clipboard ─────────────────────────────────────────────────
app.clientside_callback(
    """
    function(n_clicks, url) {
        if (!n_clicks || !url) {
            return dash_clientside.no_update;
        }
        try {
            navigator.clipboard.writeText(url);
        } catch (e) {
            // Fallback cho trình duyệt/context không hỗ trợ Clipboard API
            const tmp = document.createElement('textarea');
            tmp.value = url;
            document.body.appendChild(tmp);
            tmp.select();
            document.execCommand('copy');
            document.body.removeChild(tmp);
        }
        return "Đã copy link!";
    }
    """,
    Output("qr-copy-feedback", "children", allow_duplicate=True),
    Input("btn-copy-qr-url", "n_clicks"),
    State("qr-share-url-input", "value"),
    prevent_initial_call=True,
)
