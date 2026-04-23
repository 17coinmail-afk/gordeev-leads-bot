import sqlite3
from datetime import datetime, timedelta

DB_PATH = "freelance_aggregator.db"


def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            keywords TEXT DEFAULT "",
            min_budget INTEGER DEFAULT 0,
            is_subscribed INTEGER DEFAULT 1,
            template TEXT DEFAULT "",
            referral_code TEXT DEFAULT "",
            referred_by INTEGER,
            is_pro INTEGER DEFAULT 0,
            pro_until TEXT,
            is_banned INTEGER DEFAULT 0,
            created_at TEXT
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            link TEXT PRIMARY KEY,
            title TEXT,
            description TEXT,
            budget TEXT,
            source TEXT,
            published_at TEXT,
            created_at TEXT
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS sent_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            project_link TEXT,
            sent_at TEXT
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS processed_payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount INTEGER,
            source TEXT,
            processed_at TEXT
        )
    """)

    conn.commit()
    conn.close()


def get_user(user_id: int):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
    row = c.fetchone()
    conn.close()
    return row


def add_user(user_id: int):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    code = f"ref{user_id}"
    c.execute(
        "INSERT OR IGNORE INTO users (user_id, keywords, min_budget, is_subscribed, referral_code, created_at) VALUES (?, ?, 0, 1, ?, ?)",
        (user_id, "", code, datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()


def set_keywords(user_id: int, keywords: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE users SET keywords=? WHERE user_id=?", (keywords, user_id))
    if c.rowcount == 0:
        code = f"ref{user_id}"
        c.execute(
            "INSERT INTO users (user_id, keywords, min_budget, is_subscribed, referral_code, created_at) VALUES (?, ?, 0, 1, ?, ?)",
            (user_id, keywords, code, datetime.now().isoformat()),
        )
    conn.commit()
    conn.close()


def set_budget(user_id: int, budget: int):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE users SET min_budget=? WHERE user_id=?", (budget, user_id))
    if c.rowcount == 0:
        code = f"ref{user_id}"
        c.execute(
            "INSERT INTO users (user_id, keywords, min_budget, is_subscribed, referral_code, created_at) VALUES (?, '', ?, 1, ?, ?)",
            (user_id, budget, code, datetime.now().isoformat()),
        )
    conn.commit()
    conn.close()


def set_subscription(user_id: int, status: bool):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE users SET is_subscribed=? WHERE user_id=?", (1 if status else 0, user_id))
    if c.rowcount == 0:
        code = f"ref{user_id}"
        c.execute(
            "INSERT INTO users (user_id, keywords, min_budget, is_subscribed, referral_code, created_at) VALUES (?, '', 0, ?, ?, ?)",
            (user_id, 1 if status else 0, code, datetime.now().isoformat()),
        )
    conn.commit()
    conn.close()


def set_template(user_id: int, template: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE users SET template=? WHERE user_id=?", (template, user_id))
    if c.rowcount == 0:
        code = f"ref{user_id}"
        c.execute(
            "INSERT INTO users (user_id, keywords, min_budget, is_subscribed, template, referral_code, created_at) VALUES (?, '', 0, 1, ?, ?, ?)",
            (user_id, template, code, datetime.now().isoformat()),
        )
    conn.commit()
    conn.close()


def get_template(user_id: int) -> str:
    user = get_user(user_id)
    return user[4] if user else ""


def ban_user(user_id: int):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE users SET is_banned=1 WHERE user_id=?", (user_id,))
    if c.rowcount == 0:
        code = f"ref{user_id}"
        c.execute(
            "INSERT INTO users (user_id, keywords, min_budget, is_subscribed, referral_code, is_banned, created_at) VALUES (?, '', 0, 1, ?, 1, ?)",
            (user_id, code, datetime.now().isoformat()),
        )
    conn.commit()
    conn.close()


def unban_user(user_id: int):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE users SET is_banned=0 WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()


def is_banned(user_id: int) -> bool:
    user = get_user(user_id)
    return bool(user[9]) if user else False


def activate_pro(user_id: int, days: int):
    until = (datetime.now() + timedelta(days=days)).isoformat()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE users SET is_pro=1, pro_until=? WHERE user_id=?", (until, user_id))
    if c.rowcount == 0:
        code = f"ref{user_id}"
        c.execute(
            "INSERT INTO users (user_id, keywords, min_budget, is_subscribed, referral_code, is_pro, pro_until, created_at) VALUES (?, '', 0, 1, ?, 1, ?, ?)",
            (user_id, code, until, datetime.now().isoformat()),
        )
    conn.commit()
    conn.close()


def check_and_reset_pro(user_id: int) -> bool:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT is_pro, pro_until FROM users WHERE user_id=?", (user_id,))
    row = c.fetchone()
    if not row:
        conn.close()
        return False
    is_pro, pro_until = row
    if is_pro and pro_until:
        try:
            until_dt = datetime.fromisoformat(pro_until)
            if datetime.now() > until_dt:
                c.execute("UPDATE users SET is_pro=0, pro_until=NULL WHERE user_id=?", (user_id,))
                conn.commit()
                conn.close()
                return False
            conn.close()
            return True
        except Exception:
            conn.close()
            return bool(is_pro)
    conn.close()
    return bool(is_pro)


def get_all_subscribed_users():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE is_subscribed=1 AND is_banned=0")
    rows = c.fetchall()
    conn.close()
    return rows


def get_all_users():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT user_id FROM users WHERE is_banned=0")
    rows = c.fetchall()
    conn.close()
    return [r[0] for r in rows]


def get_users_with_expiring_pro(days: int = 3):
    """Возвращает пользователей, у которых Pro истекает через N дней."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    target = (datetime.now() + timedelta(days=days)).isoformat()[:10]
    c.execute(
        "SELECT user_id FROM users WHERE is_pro=1 AND date(pro_until)=?",
        (target,),
    )
    rows = c.fetchall()
    conn.close()
    return [r[0] for r in rows]


def project_exists(link: str) -> bool:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT 1 FROM projects WHERE link=?", (link,))
    exists = c.fetchone() is not None
    conn.close()
    return exists


def add_project(link: str, title: str, description: str, budget: str, source: str, published_at: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        """
        INSERT OR IGNORE INTO projects (link, title, description, budget, source, published_at, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (link, title, description, budget, source, published_at, datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()


def log_sent(user_id: int, project_link: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "INSERT INTO sent_log (user_id, project_link, sent_at) VALUES (?, ?, ?)",
        (user_id, project_link, datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()


def get_user_stats(user_id: int):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM sent_log WHERE user_id=?", (user_id,))
    total_sent = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM sent_log WHERE user_id=? AND date(sent_at)=date('now')", (user_id,))
    sent_today = c.fetchone()[0]
    conn.close()
    return total_sent, sent_today


def get_admin_stats():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users")
    total_users = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM users WHERE is_subscribed=1 AND is_banned=0")
    active_users = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM users WHERE is_pro=1")
    pro_users = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM users WHERE is_banned=1")
    banned_users = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM projects")
    total_projects = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM sent_log WHERE date(sent_at)=date('now')")
    sent_today = c.fetchone()[0]
    conn.close()
    return total_users, active_users, pro_users, banned_users, total_projects, sent_today


def get_last_sent_time(user_id: int):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "SELECT sent_at FROM sent_log WHERE user_id=? ORDER BY sent_at DESC LIMIT 1",
        (user_id,),
    )
    row = c.fetchone()
    conn.close()
    return row[0] if row else None


def payment_already_processed(user_id: int, amount: int) -> bool:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "SELECT 1 FROM processed_payments WHERE user_id=? AND amount=? AND date(processed_at)=date('now')",
        (user_id, amount),
    )
    exists = c.fetchone() is not None
    conn.close()
    return exists


def mark_payment_processed(user_id: int, amount: int, source: str = "email"):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "INSERT INTO processed_payments (user_id, amount, source, processed_at) VALUES (?, ?, ?, ?)",
        (user_id, amount, source, datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()


def cleanup_old_data():
    """Очищает проекты старше 30 дней и логи старше 90 дней."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM projects WHERE date(created_at) < date('now', '-30 days')")
    projects_deleted = c.rowcount
    c.execute("DELETE FROM sent_log WHERE date(sent_at) < date('now', '-90 days')")
    logs_deleted = c.rowcount
    conn.commit()
    conn.close()
    return projects_deleted, logs_deleted
