# src/backend/database.py
"""
SQLite database layer cho FSS authentication.
Tables:
  - users(id, phone, display_name, role, created_at)
  - access_codes(id, code_string, status, assigned_to, used_at)
"""
import sqlite3
import os
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

DB_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), '..', '..', 'data', 'fss.db'
)


def get_conn():
    """Trả về connection đến SQLite, tạo DB nếu chưa có."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row   # truy cập cột theo tên
    return conn


def init_db():
    """Khởi tạo bảng nếu chưa tồn tại. Gọi 1 lần khi app start."""
    conn = get_conn()
    cur  = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            phone        TEXT    UNIQUE NOT NULL,
            display_name TEXT,
            role         TEXT    NOT NULL DEFAULT 'basic',
            created_at   TEXT    NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS access_codes (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            code_string TEXT    UNIQUE NOT NULL,
            status      TEXT    NOT NULL DEFAULT 'active',
            assigned_to TEXT,
            used_at     TEXT
        )
    """)

    # AUDIT FIX (mục 9 - Alert Engine): trước đây alert-store chỉ nằm trong
    # localStorage của trình duyệt (dcc.Store storage_type="local") -> KHÔNG
    # backend process nào (kể cả scheduler) có thể đọc được, vì localStorage
    # chỉ tồn tại trong browser của người dùng, không gửi lên server ngoài
    # phạm vi 1 request Dash cụ thể. Bảng này lưu alert ở server để một
    # scheduler chạy nền (không cần tab trình duyệt mở) có thể đánh giá được.
    # owner_key = username (chỉ áp dụng cho user đã đăng nhập — người dùng ẩn
    # danh vẫn dùng localStorage như cũ, không đổi hành vi hiện tại của họ).
    cur.execute("""
        CREATE TABLE IF NOT EXISTS alerts (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            owner_key    TEXT    NOT NULL,
            ticker       TEXT    NOT NULL,
            condition    TEXT    NOT NULL,
            value        REAL,
            triggered    INTEGER NOT NULL DEFAULT 0,
            created_at   TEXT    NOT NULL,
            triggered_at TEXT
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_alerts_owner ON alerts(owner_key)")

    conn.commit()
    conn.close()
    logger.info("✅ SQLite DB khởi tạo xong.")


# ── ALERTS (server-side, dùng cho backend scheduler) ────────────────────────

def create_alert(owner_key: str, ticker: str, condition: str, value=None) -> int:
    """Tạo 1 alert server-side, trả về id vừa tạo."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO alerts (owner_key, ticker, condition, value, triggered, created_at) "
        "VALUES (?, ?, ?, ?, 0, ?)",
        (owner_key, ticker, condition, value, datetime.now().isoformat()),
    )
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return new_id


def delete_alert(alert_id: int, owner_key: str) -> bool:
    """Xoá alert, chỉ nếu đúng owner_key (không cho xoá alert của người khác)."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM alerts WHERE id=? AND owner_key=?", (alert_id, owner_key))
    conn.commit()
    deleted = cur.rowcount > 0
    conn.close()
    return deleted


def list_alerts_for_owner(owner_key: str) -> list[dict]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM alerts WHERE owner_key=? ORDER BY created_at DESC", (owner_key,))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def list_all_active_alerts() -> list[dict]:
    """Trả về TẤT CẢ alert chưa triggered của MỌI user — dùng bởi scheduler
    chạy nền để quét 1 lần cho tất cả thay vì query theo từng user."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM alerts WHERE triggered=0")
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def mark_alert_triggered(alert_id: int) -> None:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "UPDATE alerts SET triggered=1, triggered_at=? WHERE id=?",
        (datetime.now().isoformat(), alert_id),
    )
    conn.commit()
    conn.close()


# ── USERS ────────────────────────────────────────────────────────────────────

def get_or_create_user(phone: str, display_name: str = "") -> dict:
    """
    Lấy user theo phone. Nếu chưa có thì tạo mới với role='basic'.
    Trả về dict {id, phone, display_name, role}.
    """
    conn = get_conn()
    cur  = conn.cursor()
    cur.execute("SELECT * FROM users WHERE phone = ?", (phone,))
    row = cur.fetchone()
    if row:
        user = dict(row)
    else:
        cur.execute(
            "INSERT INTO users (phone, display_name, role, created_at) "
            "VALUES (?, ?, 'basic', ?)",
            (phone, display_name or phone, datetime.now().isoformat())
        )
        conn.commit()
        cur.execute("SELECT * FROM users WHERE phone = ?", (phone,))
        user = dict(cur.fetchone())
    conn.close()
    return user


def get_user_role(phone: str) -> str:
    """Trả về role hiện tại của user ('basic' hoặc 'vip')."""
    conn = get_conn()
    cur  = conn.cursor()
    cur.execute("SELECT role FROM users WHERE phone = ?", (phone,))
    row = cur.fetchone()
    conn.close()
    return row["role"] if row else "basic"


def upgrade_user_to_vip(phone: str) -> bool:
    """Nâng role user lên 'vip'. Trả về True nếu thành công."""
    conn = get_conn()
    cur  = conn.cursor()
    cur.execute(
        "UPDATE users SET role = 'vip' WHERE phone = ?", (phone,)
    )
    success = cur.rowcount > 0
    conn.commit()
    conn.close()
    return success


# ── ACCESS CODES ─────────────────────────────────────────────────────────────

def validate_and_redeem_code(code: str, phone: str) -> tuple[bool, str]:
    """
    Kiểm tra mã kích hoạt và đổi thành VIP nếu hợp lệ.
    Trả về (success: bool, message: str).
    """
    conn = get_conn()
    cur  = conn.cursor()

    cur.execute(
        "SELECT * FROM access_codes WHERE code_string = ?",
        (code.strip().upper(),)
    )
    row = cur.fetchone()

    if not row:
        conn.close()
        return False, "Mã kích hoạt không tồn tại."

    if row["status"] != "active":
        conn.close()
        return False, "Mã này đã được sử dụng hoặc đã hết hạn."

    # Mã hợp lệ → đánh dấu 'used' + nâng cấp user
    cur.execute(
        "UPDATE access_codes SET status='used', assigned_to=?, used_at=? "
        "WHERE code_string=?",
        (phone, datetime.now().isoformat(), code.strip().upper())
    )
    cur.execute(
        "UPDATE users SET role='vip' WHERE phone=?", (phone,)
    )
    conn.commit()
    conn.close()

    logger.info(f"✅ Code '{code}' redeemed by '{phone}' → VIP")
    return True, "Kích hoạt thành công! Chào mừng bạn lên VIP 🎉"


def seed_demo_codes():
    """
    Tạo sẵn một số mã demo nếu bảng đang trống.
    Gọi sau init_db() khi development.
    """
    demo_codes = [
        "FSS-DEMO-2026",
        "FSS-VIP-ALPHA",
        "FSS-VIP-BETA1",
        "FSS-VIETCAP-01",
    ]
    conn = get_conn()
    cur  = conn.cursor()
    for code in demo_codes:
        cur.execute(
            "INSERT OR IGNORE INTO access_codes (code_string, status) VALUES (?, 'active')",
            (code,)
        )
    conn.commit()
    conn.close()
    logger.info(f"✅ Seeded {len(demo_codes)} demo access codes.")