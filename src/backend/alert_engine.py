# src/backend/alert_engine.py
"""
AUDIT FIX (mục 9 - Alert Engine): logic đánh giá điều kiện alert (SMA20/SMA200,
RSI, volume spike, VGM, CANSLIM...) trước đây nằm chìm bên trong callback Dash
`render_and_check_alerts()` (src/callbacks/alert_callbacks.py), không thể tái
sử dụng cho một scheduler chạy độc lập với browser.

File này tách phần "tính toán thuần" (không phụ thuộc Dash, không phụ thuộc
UI) ra một hàm duy nhất `evaluate_alert()`, để:
  1. `alert_callbacks.py` (UI, chạy khi có client mở tab) dùng lại y hệt logic này.
  2. `alert_scheduler.py` (APScheduler, chạy nền, không cần browser mở) cũng
     dùng lại y hệt logic này.
=> Không còn 2 bản sao logic có thể lệch nhau theo thời gian.

QUAN TRỌNG: giữ nguyên 100% logic gốc, bao gồm cả lưu ý về suy ngược SMA từ
Price_vs_SMA{n} (%) vì cột "_sma20"/"_sma200" thô đã bị xoá khỏi snapshot.
"""
from __future__ import annotations


def _derive_sma(rec: dict, price: float, pct_field: str) -> float:
    """Suy ngược giá trị SMA từ % lệch giá (Price_vs_SMA{n}), vì cột SMA thô
    không còn tồn tại trong snapshot cuối (technical_indicators.py xoá mọi
    cột bắt đầu bằng "_" trước khi trả về)."""
    pct = rec.get(pct_field)
    if pct is None or price <= 0:
        return price  # thiếu dữ liệu -> coi như bằng giá (an toàn, không false-trigger)
    try:
        pct = float(pct)
        denom = 1 + pct / 100
        return price / denom if denom != 0 else price
    except (TypeError, ValueError):
        return price


def evaluate_alert(alert: dict, rec: dict) -> bool:
    """
    Đánh giá MỘT alert dựa trên MỘT record snapshot (dict theo Ticker).
    Trả về True nếu điều kiện đang được thoả (hit), False nếu không hoặc
    thiếu dữ liệu.

    `alert` cần có: {"condition": str, "value": float|None}
    `rec` là 1 dòng snapshot dict (vd {"Price Close": ..., "RSI_14": ..., ...})
    """
    if not rec:
        return False

    cond = alert.get("condition")
    val = alert.get("value")

    price = float(rec.get("Price Close") or 0)
    rsi = float(rec.get("RSI_14") or 50)
    vol_r = float(rec.get("Vol_vs_SMA20") or 1)
    sma20 = _derive_sma(rec, price, "Price_vs_SMA20")
    sma200 = _derive_sma(rec, price, "Price_vs_SMA200")
    vgm = rec.get("VGM Score", "")
    canslim = float(rec.get("CANSLIM Score") or 0)
    p1w = float(rec.get("Perf_1W") or 0)

    if cond == "price_above" and val and price >= val:
        return True
    if cond == "price_below" and val and price <= val:
        return True
    if cond == "rsi_oversold" and rsi < 30:
        return True
    if cond == "rsi_overbought" and rsi > 70:
        return True
    if cond == "price_cross_sma20" and price > sma20:
        return True
    if cond == "price_below_sma20" and price < sma20:
        return True
    if cond == "price_cross_sma200" and price > sma200:
        return True
    if cond == "volume_spike" and vol_r >= 3:
        return True
    if cond == "vgm_a" and vgm == "A":
        return True
    if cond == "canslim_5" and canslim >= 5:
        return True
    if cond == "perf_1w_above" and val and p1w >= val:
        return True

    return False


def evaluate_all(alerts: list[dict], snapshot_by_ticker: dict) -> list[dict]:
    """Chạy evaluate_alert() cho một danh sách alert, trả về danh sách các
    alert VỪA chuyển sang trạng thái triggered (chưa triggered trước đó).
    Không mutate `alerts` gốc — trả về list bản sao đã cập nhật để caller
    (Dash callback hoặc scheduler) tự quyết định cách lưu lại."""
    newly_triggered = []
    for alert in alerts:
        if alert.get("triggered"):
            continue
        rec = snapshot_by_ticker.get(alert.get("ticker"), {})
        if evaluate_alert(alert, rec):
            newly_triggered.append(alert)
    return newly_triggered
