"""Shared DB helpers for Smart Loom."""
from werkzeug.security import check_password_hash, generate_password_hash

PER_PAGE = 10


def hash_password(plain):
    return generate_password_hash(plain)


def verify_password(stored, plain):
    if not stored:
        return False
    if stored.startswith("pbkdf2:") or stored.startswith("scrypt:"):
        return check_password_hash(stored, plain)
    return stored == plain


def needs_rehash(stored):
    return not (stored.startswith("pbkdf2:") or stored.startswith("scrypt:"))


def log_activity(cursor, db, user_id, action, table_name=None, record_id=None, details=None):
    try:
        cursor.execute(
            """
            INSERT INTO activity_log (user_id, action, table_name, record_id, details)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (user_id, action, table_name, record_id, details),
        )
        db.commit()
    except Exception:
        pass


def add_notification(cursor, db, user_id, message):
    try:
        cursor.execute(
            """
            INSERT INTO notifications (user_id, message)
            VALUES (%s, %s)
            """,
            (user_id, message),
        )
        db.commit()
    except Exception:
        pass


def notify_low_stock(cursor, db, product):
    """Alert admin and product weaver when stock is low."""
    name = product.get("product_name", "Product")
    stock = product.get("stock", 0)
    if stock >= 10:
        return
    msg = f"Low stock: {name} has only {stock} units left."
    try:
        cursor.execute("SELECT user_id FROM users WHERE role = 'Admin'")
        for row in cursor.fetchall():
            add_notification(cursor, db, row["user_id"], msg)
        weaver_id = product.get("weaver_id")
        if weaver_id:
            add_notification(cursor, db, weaver_id, msg)
    except Exception:
        pass


def paginate(cursor, count_sql, data_sql, params, page, per_page=PER_PAGE):
    page = max(1, int(page or 1))
    cursor.execute(count_sql, params)
    total = cursor.fetchone()
    total_count = list(total.values())[0] if total else 0
    offset = (page - 1) * per_page
    cursor.execute(data_sql + " LIMIT %s OFFSET %s", params + (per_page, offset))
    rows = cursor.fetchall()
    total_pages = max(1, (total_count + per_page - 1) // per_page)
    return rows, page, total_pages, total_count


def db_error_message(exc):
    """User-friendly message from MySQL trigger/constraint errors."""
    if hasattr(exc, "msg") and exc.msg:
        return exc.msg
    text = str(exc)
    if "MESSAGE_TEXT" in text:
        return text.split("'")[1] if "'" in text else text
    return text


def pagination_context(page, total_pages, total_count, base_url, extra_args=None):
    extra_args = extra_args or {}
    q = "&".join(f"{k}={v}" for k, v in extra_args.items() if v)
    sep = "&" if q else ""
    prefix = f"{base_url}?{q}{sep}" if q else f"{base_url}?"
    return {
        "page": page,
        "total_pages": total_pages,
        "total_count": total_count,
        "has_prev": page > 1,
        "has_next": page < total_pages,
        "prev_url": f"{prefix}page={page - 1}" if page > 1 else None,
        "next_url": f"{prefix}page={page + 1}" if page < total_pages else None,
    }
