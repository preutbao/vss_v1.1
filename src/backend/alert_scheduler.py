# src/backend/alert_scheduler.py
"""
AUDIT FIX (mục 9 - Alert Engine): trước audit, Alert Engine CHỈ chạy qua
`dcc.Interval` (src/callbacks/alert_callbacks.py) — nghĩa là:
  - Chỉ được đánh giá khi có ít nhất 1 trình duyệt đang mở tab của app.
  - Alert list nằm trong localStorage của browser đó — nếu người dùng đóng
    tab, không có gì được kiểm tra, dù server vẫn đang chạy.

File này thêm một scheduler THẬT chạy trong tiến trình backend (dùng
APScheduler), độc lập hoàn toàn với việc có browser mở hay không:
  - Đọc TẤT CẢ alert server-side (bảng `alerts` trong SQLite, xem
    src/backend/database.py) — không đọc localStorage (không thể, vì
    localStorage không tồn tại phía server).
  - Dùng LẠI y hệt logic đánh giá điều kiện trong src/backend/alert_engine.py
    (evaluate_alert) — không viết lại logic riêng, tránh lệch hành vi so
    với UI.
  - Đánh dấu triggered trong DB khi điều kiện thoả.

GIỚI HẠN CÒN LẠI (nêu rõ, không che giấu):
  - Alert do người dùng CHƯA đăng nhập tạo qua UI hiện tại vẫn chỉ lưu
    localStorage (client-side) như cũ — scheduler này KHÔNG thấy được các
    alert đó. Để scheduler thấy MỌI alert, cần bắt buộc đăng nhập trước khi
    tạo alert (thay đổi UX, ngoài phạm vecope của audit này) hoặc mirror
    alert client -> server ngay khi tạo (đã có sẵn create_alert() trong
    database.py cho việc này, nhưng CHƯA được gọi từ alert_callbacks.py —
    xem TODO trong add_alert()).
  - Khi phát hiện alert kích hoạt, hiện tại CHỈ ghi log + đánh dấu DB.
    Gửi thông báo thật (email/Telegram/push) khi user không mở tab cần
    thêm 1 kênh gửi tin — chưa có trong scope audit này vì cần quyết định
    kênh gửi (email SMTP? Telegram bot token? ...) — đây là quyết định
    sản phẩm cần người phụ trách xác nhận trước khi implement.

Cách khởi động: gọi `start_alert_scheduler()` MỘT LẦN khi app boot (đã wire
vào main.py). An toàn cho deployment hiện tại (Dockerfile chỉ định
`gunicorn --workers 1` — xem comment đầu Dockerfile) vì chỉ có 1 process,
không có rủi ro chạy trùng job. Nếu sau này scale lên nhiều worker/instance,
cần chuyển job này ra một worker riêng (không chạy trong mỗi web worker)
để tránh đánh giá trùng lặp nhiều lần.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

_scheduler = None  # module-level singleton, tránh khởi động 2 lần


def _run_alert_check_job():
    """Job chạy định kỳ: quét toàn bộ alert server-side chưa triggered,
    đối chiếu với snapshot dữ liệu mới nhất, đánh dấu triggered nếu thoả."""
    try:
        from src.backend.database import list_all_active_alerts, mark_alert_triggered
        from src.backend.alert_engine import evaluate_alert
        from src.backend.data_loader import get_snapshot_df

        alerts = list_all_active_alerts()
        if not alerts:
            return

        records = get_snapshot_df().to_dict("records")
        snap = {r["Ticker"]: r for r in (records or [])}

        n_triggered = 0
        for alert in alerts:
            rec = snap.get(alert["ticker"], {})
            if not rec:
                continue
            if evaluate_alert(alert, rec):
                mark_alert_triggered(alert["id"])
                n_triggered += 1
                logger.info(
                    f"🔔 [AlertScheduler] Alert #{alert['id']} kích hoạt: "
                    f"{alert['ticker']} — {alert['condition']} (owner={alert['owner_key']})"
                )

        logger.info(
            f"[AlertScheduler] Đã quét {len(alerts)} alert, {n_triggered} kích hoạt mới."
        )
    except Exception as e:
        # Không để job crash toàn bộ scheduler — log đầy đủ để debug.
        logger.error(f"[AlertScheduler] Lỗi khi chạy alert check job: {e}", exc_info=True)


def start_alert_scheduler(interval_minutes: int = 5):
    """Khởi động scheduler nền. Gọi 1 lần lúc app boot (main.py).
    Idempotent: gọi nhiều lần sẽ không tạo nhiều scheduler song song."""
    global _scheduler
    if _scheduler is not None:
        logger.info("[AlertScheduler] Đã khởi động trước đó — bỏ qua.")
        return _scheduler

    try:
        from apscheduler.schedulers.background import BackgroundScheduler
    except ImportError:
        logger.warning(
            "[AlertScheduler] Thiếu package 'apscheduler' — Alert Engine sẽ CHỈ chạy "
            "qua dcc.Interval phía client (hành vi cũ, không có backend scheduler). "
            "Chạy: pip install apscheduler"
        )
        return None

    _scheduler = BackgroundScheduler(daemon=True, timezone="Asia/Ho_Chi_Minh")
    _scheduler.add_job(
        _run_alert_check_job,
        trigger="interval",
        minutes=interval_minutes,
        id="alert_check_job",
        replace_existing=True,
        next_run_time=None,  # chờ đủ 1 interval trước lần chạy đầu, tránh chạy khi data chưa sẵn sàng lúc boot
    )
    _scheduler.start()
    logger.info(f"✅ [AlertScheduler] Backend scheduler khởi động — chu kỳ {interval_minutes} phút.")
    return _scheduler


def stop_alert_scheduler():
    """Dừng scheduler (dùng khi test hoặc shutdown sạch)."""
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
