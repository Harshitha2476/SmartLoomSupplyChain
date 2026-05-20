from flask import (
    Flask, flash, render_template, redirect, url_for,
    request, session, jsonify,
)
import mysql.connector
from functools import wraps

from helpers import (
    PER_PAGE, hash_password, verify_password, needs_rehash,
    log_activity, add_notification, notify_low_stock,
    paginate, pagination_context, db_error_message,
)

app = Flask(__name__)
app.secret_key = "smartloom_secret_key"

db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="password",
    database="smartloom",
)
cursor = db.cursor(dictionary=True)


@app.before_request
def reset_db_transaction():
    """Clear any leftover transaction from the shared connection."""
    try:
        db.rollback()
    except Exception:
        pass


def role_required(allowed_roles):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if 'user_id' not in session:
                return redirect('/login')
            if session['role'] not in allowed_roles:
                return "Access Denied"
            return f(*args, **kwargs)
        return wrapper
    return decorator


def get_unread_notifications(user_id):
    try:
        cursor.execute(
            """
            SELECT COUNT(*) AS cnt FROM notifications
            WHERE user_id = %s AND is_read = 0
            """,
            (user_id,),
        )
        return cursor.fetchone()['cnt']
    except Exception:
        return 0


def nav_context():
    if 'user_id' not in session:
        return {}
    return {'unread_notifications': get_unread_notifications(session['user_id'])}


# ─── HOME ───────────────────────────────────────────────────────────────────

@app.route('/')
def home():
    return render_template('index.html', **nav_context())


@app.route('/index')
def index():
    return redirect(url_for('home'))


# ─── DASHBOARD (charts + notifications) ─────────────────────────────────────

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect('/login')

    cursor.execute("SELECT COUNT(*) AS total_products FROM products")
    total_products = cursor.fetchone()['total_products']

    cursor.execute("SELECT COUNT(*) AS total_orders FROM orders")
    total_orders = cursor.fetchone()['total_orders']

    cursor.execute("SELECT COUNT(*) AS total_users FROM users")
    total_users = cursor.fetchone()['total_users']

    cursor.execute("SELECT SUM(total_price) AS revenue FROM orders")
    revenue_result = cursor.fetchone()
    total_revenue = revenue_result['revenue'] or 0

    cursor.execute("SELECT * FROM products WHERE stock < 10")
    low_stock_products = cursor.fetchall()

    for product in low_stock_products:
        notify_low_stock(cursor, db, product)

    cursor.execute(
        """
        SELECT orders.order_id, products.product_name,
               orders.total_price, orders.order_status
        FROM orders
        JOIN products ON orders.product_id = products.product_id
        ORDER BY orders.order_date DESC
        LIMIT 5
        """
    )
    recent_orders = cursor.fetchall()

    # Chart: revenue by month (last 6 months)
    cursor.execute(
        """
        SELECT DATE_FORMAT(order_date, '%%Y-%%m') AS month,
               SUM(total_price) AS revenue
        FROM orders
        WHERE order_date >= DATE_SUB(CURDATE(), INTERVAL 6 MONTH)
        GROUP BY DATE_FORMAT(order_date, '%%Y-%%m')
        ORDER BY month
        """
    )
    revenue_by_month = cursor.fetchall()

    # Chart: orders by status
    cursor.execute(
        """
        SELECT order_status AS status, COUNT(*) AS count
        FROM orders
        GROUP BY order_status
        """
    )
    orders_by_status = cursor.fetchall()

    notifications = []
    try:
        cursor.execute(
            """
            SELECT * FROM notifications
            WHERE user_id = %s
            ORDER BY created_at DESC
            LIMIT 5
            """,
            (session['user_id'],),
        )
        notifications = cursor.fetchall()
    except Exception:
        pass

    return render_template(
        'dashboard.html',
        total_products=total_products,
        total_orders=total_orders,
        total_users=total_users,
        total_revenue=total_revenue,
        low_stock_products=low_stock_products,
        recent_orders=recent_orders,
        revenue_by_month=revenue_by_month,
        orders_by_status=orders_by_status,
        notifications=notifications,
        **nav_context(),
    )


@app.route('/notifications')
def notifications_page():
    if 'user_id' not in session:
        return redirect('/login')
    try:
        cursor.execute(
            """
            SELECT * FROM notifications
            WHERE user_id = %s
            ORDER BY created_at DESC
            """,
            (session['user_id'],),
        )
        items = cursor.fetchall()
        cursor.execute(
            "UPDATE notifications SET is_read = 1 WHERE user_id = %s",
            (session['user_id'],),
        )
        db.commit()
    except Exception:
        items = []
        flash('Run database/upgrade_tier1_tier2.sql to enable notifications.', 'warning')
    return render_template('notifications.html', notifications=items, **nav_context())


# ─── PRODUCTS (pagination, filters, edit) ───────────────────────────────────

@app.route('/products')
@role_required(['Buyer', 'Weaver', 'Admin'])
def products():
    category = request.args.get('category', '').strip()
    sort = request.args.get('sort', 'newest')
    page = request.args.get('page', 1, type=int)

    where = " WHERE 1=1"
    params = []
    if category:
        where += " AND category = %s"
        params.append(category)

    order = " ORDER BY product_id DESC"
    if sort == 'price_asc':
        order = " ORDER BY price ASC"
    elif sort == 'price_desc':
        order = " ORDER BY price DESC"
    elif sort == 'stock':
        order = " ORDER BY stock ASC"

    count_sql = f"SELECT COUNT(*) AS c FROM products{where}"
    data_sql = f"SELECT * FROM products{where}{order}"

    rows, page, total_pages, total_count = paginate(
        cursor, count_sql, data_sql, tuple(params), page
    )

    cursor.execute("SELECT DISTINCT category FROM products ORDER BY category")
    categories = [r['category'] for r in cursor.fetchall()]

    return render_template(
        'products.html',
        products=rows,
        categories=categories,
        filter_category=category,
        filter_sort=sort,
        pagination=pagination_context(
            page, total_pages, total_count, '/products',
            {'category': category, 'sort': sort},
        ),
        **nav_context(),
    )


@app.route('/add_product', methods=['POST'])
@role_required(['Weaver', 'Admin'])
def add_product():
    name = request.form['name']
    category = request.form['category']
    price = request.form['price']
    stock = request.form['stock']
    description = request.form['description']

    weaver_id = session['user_id'] if session['role'] == 'Weaver' else None
    weaver_name = session['user_name'] if session['role'] == 'Weaver' else request.form.get('weaver', '')

    if session['role'] == 'Admin' and request.form.get('weaver'):
        weaver_name = request.form['weaver']

    try:
        # product_code: trg_products_before_insert sets it; Python fallback uses real product_id
        cursor.execute(
            """
            INSERT INTO products
            (product_name, category, weaver_name, weaver_id, price, stock, description)
            VALUES (%s,%s,%s,%s,%s,%s,%s)
            """,
            (name, category, weaver_name, weaver_id, price, stock, description),
        )
        product_id = cursor.lastrowid
        cursor.execute(
            "SELECT product_code FROM products WHERE product_id=%s",
            (product_id,),
        )
        row = cursor.fetchone()
        if not row or not row.get('product_code'):
            product_code = f"P-{1000 + product_id}"
            cursor.execute(
                "UPDATE products SET product_code=%s WHERE product_id=%s",
                (product_code, product_id),
            )
        db.commit()
        log_activity(cursor, db, session['user_id'], 'ADD_PRODUCT', 'products', product_id)
        flash('Product added successfully!', 'success')
    except Exception as e:
        db.rollback()
        if 'weaver_id' in str(e).lower() or 'unknown column' in str(e).lower():
            try:
                cursor.execute(
                    """
                    INSERT INTO products
                    (product_name, category, weaver_name, price, stock, description)
                    VALUES (%s,%s,%s,%s,%s,%s)
                    """,
                    (name, category, weaver_name, price, stock, description),
                )
                product_id = cursor.lastrowid
                product_code = f"P-{1000 + product_id}"
                cursor.execute(
                    "UPDATE products SET product_code=%s WHERE product_id=%s",
                    (product_code, product_id),
                )
                db.commit()
                flash('Product added successfully!', 'success')
                return redirect('/products')
            except Exception as e2:
                db.rollback()
                flash(f'Error adding product: {db_error_message(e2)}', 'danger')
        else:
            flash(f'Error adding product: {db_error_message(e)}', 'danger')
    return redirect('/products')


@app.route('/edit_product/<int:product_id>', methods=['GET', 'POST'])
@role_required(['Weaver', 'Admin'])
def edit_product(product_id):
    cursor.execute("SELECT * FROM products WHERE product_id=%s", (product_id,))
    product = cursor.fetchone()
    if not product:
        flash('Product not found.', 'danger')
        return redirect('/products')

    if session['role'] == 'Weaver' and product.get('weaver_id') != session['user_id']:
        if product.get('weaver_name') != session['user_name']:
            return "Access Denied"

    if request.method == 'POST':
        cursor.execute(
            """
            UPDATE products SET
                product_name=%s, category=%s, weaver_name=%s,
                price=%s, stock=%s, description=%s
            WHERE product_id=%s
            """,
            (
                request.form['name'],
                request.form['category'],
                request.form.get('weaver', product['weaver_name']),
                request.form['price'],
                request.form['stock'],
                request.form['description'],
                product_id,
            ),
        )
        db.commit()
        log_activity(cursor, db, session['user_id'], 'EDIT_PRODUCT', 'products', product_id)
        flash('Product updated.', 'success')
        return redirect('/products')

    return render_template('edit_product.html', product=product, **nav_context())


# ─── ORDERS (quantity, cancel, filters, pagination) ─────────────────────────

@app.route('/orders')
@role_required(['Buyer', 'Weaver', 'Admin'])
def orders():
    status_filter = request.args.get('status', '').strip()
    days = request.args.get('days', '').strip()
    page = request.args.get('page', 1, type=int)

    where = ""
    params = []

    if session['role'] == 'Buyer':
        base_from = """
            FROM orders
            JOIN products ON orders.product_id = products.product_id
            WHERE orders.user_id = %s
        """
        params = [session['user_id']]
        select_cols = """
            orders.order_id, products.product_name, orders.quantity,
            orders.total_price, orders.order_status, orders.order_date,
            orders.product_id
        """
    else:
        base_from = """
            FROM orders
            JOIN users ON orders.user_id = users.user_id
            JOIN products ON orders.product_id = products.product_id
            WHERE 1=1
        """
        select_cols = """
            orders.order_id, users.full_name, products.product_name,
            orders.quantity, orders.total_price, orders.order_status,
            orders.order_date, orders.product_id
        """

    if status_filter:
        where += " AND orders.order_status = %s"
        params.append(status_filter)

    if days == '7':
        where += " AND orders.order_date >= DATE_SUB(CURDATE(), INTERVAL 7 DAY)"
    elif days == '30':
        where += " AND orders.order_date >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)"
    elif days == '365':
        where += " AND orders.order_date >= DATE_SUB(CURDATE(), INTERVAL 1 YEAR)"

    count_sql = f"SELECT COUNT(*) AS c {base_from}{where}"
    data_sql = f"SELECT {select_cols} {base_from}{where} ORDER BY orders.order_date DESC"

    rows, page, total_pages, total_count = paginate(
        cursor, count_sql, data_sql, tuple(params), page
    )

    cursor.execute(
        """
        SELECT order_status, COUNT(*) AS count FROM orders
        GROUP BY order_status
        """
    )
    status_counts = {r['order_status']: r['count'] for r in cursor.fetchall()}

    return render_template(
        'orders.html',
        orders=rows,
        status_counts=status_counts,
        filter_status=status_filter,
        filter_days=days,
        pagination=pagination_context(
            page, total_pages, total_count, '/orders',
            {'status': status_filter, 'days': days},
        ),
        **nav_context(),
    )


@app.route('/place_order', methods=['POST'])
@role_required(['Buyer'])
def place_order():
    user_id = session['user_id']
    product_id = request.form['product_id']
    quantity = int(request.form.get('quantity', 1))
    if quantity < 1:
        flash('Invalid quantity.', 'danger')
        return redirect('/products')

    try:
        # Stock check, price, and stock reduction handled by DB triggers
        cursor.execute(
            """
            INSERT INTO orders (user_id, product_id, quantity, total_price)
            VALUES (%s,%s,%s,0)
            """,
            (user_id, product_id, quantity),
        )
        order_id = cursor.lastrowid
        db.commit()

        cursor.execute("SELECT * FROM products WHERE product_id=%s", (product_id,))
        product = cursor.fetchone()
        if product:
            notify_low_stock(cursor, db, product)
        log_activity(cursor, db, user_id, 'PLACE_ORDER', 'orders', order_id,
                     f"qty={quantity}")
        flash('Order placed successfully!', 'success')
    except Exception as e:
        db.rollback()
        flash(f'Order failed: {db_error_message(e)}', 'danger')
    return redirect('/orders')


@app.route('/cancel_order/<int:order_id>', methods=['POST'])
@role_required(['Buyer', 'Admin'])
def cancel_order(order_id):
    try:
        cursor.execute("SELECT * FROM orders WHERE order_id=%s", (order_id,))
        order = cursor.fetchone()

        if not order:
            db.rollback()
            flash('Order not found.', 'danger')
            return redirect('/orders')

        if session['role'] == 'Buyer' and order['user_id'] != session['user_id']:
            db.rollback()
            return "Access Denied"

        current = order['order_status'] or 'Pending'
        if current == 'Cancelled':
            db.rollback()
            flash('Order already cancelled.', 'info')
            return redirect('/orders')

        if current != 'Pending':
            db.rollback()
            flash('Only pending orders can be cancelled.', 'warning')
            return redirect('/orders')

        # Stock restore handled by trg_orders_after_update
        cursor.execute(
            "UPDATE orders SET order_status='Cancelled' WHERE order_id=%s",
            (order_id,),
        )
        db.commit()
        log_activity(cursor, db, session['user_id'], 'CANCEL_ORDER', 'orders', order_id)
        flash('Order cancelled and stock restored.', 'success')
    except Exception as e:
        db.rollback()
        flash(f'Cancel failed: {db_error_message(e)}', 'danger')
    return redirect('/orders')


@app.route('/update_order_status', methods=['POST'])
@role_required(['Weaver', 'Admin'])
def update_order_status():
    order_id = request.form['order_id']
    status = request.form['status']
    old_status = None

    try:
        cursor.execute("SELECT * FROM orders WHERE order_id=%s", (order_id,))
        order = cursor.fetchone()
        if not order:
            db.rollback()
            return redirect('/orders')

        old_status = order['order_status']

        # Stock restore on cancel handled by trg_orders_after_update
        cursor.execute(
            "UPDATE orders SET order_status=%s WHERE order_id=%s",
            (status, order_id),
        )
        db.commit()
        log_activity(cursor, db, session['user_id'], 'UPDATE_ORDER_STATUS', 'orders',
                     order_id, f"{old_status}->{status}")
    except Exception as e:
        db.rollback()
        flash(f'Update failed: {db_error_message(e)}', 'danger')
    return redirect('/orders')


# ─── AUTH ───────────────────────────────────────────────────────────────────

@app.route('/login')
def login_page():
    return render_template('login.html', **nav_context())


@app.route('/register', methods=['POST'])
def register():
    full_name = request.form['name']
    email = request.form['email']
    phone = request.form['phone']
    password = hash_password(request.form['password'])
    location = request.form['location']
    role = request.form['role']

    cursor.execute("SELECT * FROM users WHERE email=%s", (email,))
    if cursor.fetchone():
        flash('Email already registered!', 'danger')
        return redirect('/login')

    cursor.execute(
        """
        INSERT INTO users (full_name, email, phone, password, role, location)
        VALUES (%s,%s,%s,%s,%s,%s)
        """,
        (full_name, email, phone, password, role, location),
    )
    db.commit()
    log_activity(cursor, db, cursor.lastrowid, 'REGISTER', 'users', cursor.lastrowid)
    flash('Registration successful. Please login.', 'success')
    return redirect('/login')


@app.route('/login', methods=['POST'])
def login():
    email = request.form['email']
    password = request.form['password']
    role = request.form['role']

    cursor.execute(
        "SELECT * FROM users WHERE email=%s AND role=%s",
        (email, role),
    )
    user = cursor.fetchone()

    if user and verify_password(user['password'], password):
        if needs_rehash(user['password']):
            cursor.execute(
                "UPDATE users SET password=%s WHERE user_id=%s",
                (hash_password(password), user['user_id']),
            )
            db.commit()
        session['user_id'] = user['user_id']
        session['user_name'] = user['full_name']
        session['role'] = user['role']
        log_activity(cursor, db, user['user_id'], 'LOGIN', 'users', user['user_id'])
        return redirect('/dashboard')

    flash('Invalid email or password!', 'danger')
    return redirect('/login')


# ─── MATERIALS ──────────────────────────────────────────────────────────────

@app.route('/materials')
@role_required(['Supplier', 'Admin'])
def materials():
    supplier_id = session['user_id']
    page = request.args.get('page', 1, type=int)
    mtype = request.args.get('type', '').strip()

    where = " WHERE supplier_id = %s"
    params = [supplier_id]
    if mtype:
        where += " AND material_type = %s"
        params.append(mtype)

    count_sql = f"SELECT COUNT(*) AS c FROM materials{where}"
    data_sql = f"SELECT * FROM materials{where} ORDER BY material_id DESC"

    rows, page, total_pages, total_count = paginate(
        cursor, count_sql, data_sql, tuple(params), page
    )

    return render_template(
        'materials.html',
        materials=rows,
        filter_type=mtype,
        pagination=pagination_context(page, total_pages, total_count, '/materials', {'type': mtype}),
        **nav_context(),
    )


@app.route('/add_material', methods=['POST'])
@role_required(['Supplier'])
def add_material():
    cursor.execute(
        """
        INSERT INTO materials (supplier_id, material_name, material_type, stock, price)
        VALUES (%s,%s,%s,%s,%s)
        """,
        (
            session['user_id'],
            request.form['material_name'],
            request.form['material_type'],
            request.form['stock'],
            request.form['price'],
        ),
    )
    db.commit()
    log_activity(cursor, db, session['user_id'], 'ADD_MATERIAL', 'materials', cursor.lastrowid)
    return redirect('/materials')


@app.route('/delete_material/<int:id>')
@role_required(['Supplier'])
def delete_material(id):
    cursor.execute("DELETE FROM materials WHERE material_id=%s", (id,))
    db.commit()
    log_activity(cursor, db, session['user_id'], 'DELETE_MATERIAL', 'materials', id)
    return redirect('/materials')


@app.route('/material_requests')
@role_required(['Weaver', 'Admin'])
def material_requests():
    cursor.execute(
        """
        SELECT m.*, u.full_name AS supplier_name
        FROM materials m
        JOIN users u ON m.supplier_id = u.user_id
        ORDER BY m.material_name
        """
    )
    materials = cursor.fetchall()

    weaver_id = session['user_id']
    if session['role'] == 'Admin':
        weaver_id = request.args.get('weaver_id', type=int) or session['user_id']

    my_requests = []
    try:
        cursor.execute(
            """
            SELECT mr.*, m.material_name, m.material_type, u.full_name AS supplier_name,
                   sr.rating AS user_rating, sr.comment AS user_comment
            FROM material_requests mr
            JOIN materials m ON mr.material_id = m.material_id
            JOIN users u ON mr.supplier_id = u.user_id
            LEFT JOIN supplier_ratings sr
                ON sr.material_request_id = mr.request_id
                AND sr.rated_by = %s
            WHERE mr.weaver_id = %s
            ORDER BY mr.request_id DESC
            """,
            (session['user_id'], weaver_id),
        )
        my_requests = cursor.fetchall()
    except Exception:
        try:
            cursor.execute(
                """
                SELECT mr.*, m.material_name, m.material_type, u.full_name AS supplier_name
                FROM material_requests mr
                JOIN materials m ON mr.material_id = m.material_id
                JOIN users u ON mr.supplier_id = u.user_id
                WHERE mr.weaver_id = %s
                ORDER BY mr.request_id DESC
                """,
                (weaver_id,),
            )
            my_requests = cursor.fetchall()
        except Exception:
            my_requests = []

    return render_template(
        'material_requests.html',
        materials=materials,
        my_requests=my_requests,
        **nav_context(),
    )


@app.route('/request_material', methods=['POST'])
@role_required(['Weaver', 'Admin'])
def request_material():
    if session['role'] != 'Weaver':
        flash('Only weavers can submit material requests.', 'warning')
        return redirect('/material_requests')

    try:
        quantity = int(request.form['quantity'])
        if quantity < 1:
            raise ValueError('invalid quantity')
        cursor.execute(
            """
            INSERT INTO material_requests (weaver_id, supplier_id, material_id, quantity)
            VALUES (%s,%s,%s,%s)
            """,
            (
                session['user_id'],
                request.form['supplier_id'],
                request.form['material_id'],
                quantity,
            ),
        )
        db.commit()
        log_activity(cursor, db, session['user_id'], 'REQUEST_MATERIAL',
                     'material_requests', cursor.lastrowid)
        flash('Material request submitted successfully!', 'success')
    except Exception as e:
        db.rollback()
        flash(f'Could not submit request: {e}', 'danger')
    return redirect('/material_requests')


@app.route('/supplier_requests')
@role_required(['Supplier', 'Admin'])
def supplier_requests():
    supplier_id = session['user_id']
    cursor.execute(
        """
        SELECT material_requests.*, materials.material_name
        FROM material_requests
        JOIN materials ON material_requests.material_id = materials.material_id
        WHERE material_requests.supplier_id = %s
        ORDER BY material_requests.request_id DESC
        """,
        (supplier_id,),
    )
    requests_list = cursor.fetchall()

    def bucket(status):
        s = status or 'Pending'
        if s == 'Approved':
            return 'approved'
        if s == 'Delivered':
            return 'delivered'
        if s == 'Rejected':
            return 'rejected'
        return 'pending'

    pending_requests = []
    approved_requests = []
    delivered_requests = []
    rejected_requests = []
    for req in requests_list:
        b = bucket(req.get('request_status'))
        if b == 'approved':
            approved_requests.append(req)
        elif b == 'delivered':
            delivered_requests.append(req)
        elif b == 'rejected':
            rejected_requests.append(req)
        else:
            pending_requests.append(req)

    cursor.execute(
        """
        SELECT supplier_id, AVG(rating) AS avg_rating, COUNT(*) AS rating_count
        FROM supplier_ratings
        WHERE supplier_id = %s
        GROUP BY supplier_id
        """,
        (supplier_id,),
    )
    rating_summary = cursor.fetchone()

    return render_template(
        'supplier_requests.html',
        pending_requests=pending_requests,
        approved_requests=approved_requests,
        delivered_requests=delivered_requests,
        rejected_requests=rejected_requests,
        rating_summary=rating_summary,
        **nav_context(),
    )


@app.route('/update_material_status/<int:request_id>/<status>', methods=['GET', 'POST'])
@role_required(['Supplier', 'Admin'])
def update_material_status(request_id, status):
    if session['role'] not in ['Supplier', 'Admin']:
        return jsonify({"success": False, "message": "Unauthorized"})

    try:
        cursor.execute(
            "SELECT * FROM material_requests WHERE request_id=%s",
            (request_id,),
        )
        request_data = cursor.fetchone()

        if not request_data:
            db.rollback()
            return jsonify({"success": False, "message": "Request not found"})

        current = request_data['request_status'] or 'Pending'

        if current in ('Delivered', 'Rejected'):
            db.rollback()
            return jsonify({
                "success": False,
                "message": f"Request is already {current}",
            })

        if current == 'Approved' and status != 'Delivered':
            db.rollback()
            return jsonify({
                "success": False,
                "message": "Approved requests can only be marked as Delivered",
            })

        if current == 'Pending' and status not in ('Approved', 'Delivered', 'Rejected'):
            db.rollback()
            return jsonify({"success": False, "message": "Invalid status"})

        # Delivery stock check/reduction handled by material_requests triggers
        cursor.execute(
            "UPDATE material_requests SET request_status=%s WHERE request_id=%s",
            (status, request_id),
        )
        db.commit()
        log_activity(cursor, db, session['user_id'], 'MATERIAL_STATUS',
                     'material_requests', request_id, status)
        return jsonify({
            "success": True,
            "message": f"Request {status} successfully",
            "status": status,
            "request_id": request_id,
        })
    except Exception as e:
        db.rollback()
        return jsonify({"success": False, "message": db_error_message(e)})


@app.route('/rate_supplier', methods=['POST'])
@role_required(['Weaver', 'Buyer', 'Admin'])
def rate_supplier():
    supplier_id = request.form['supplier_id']
    rating = int(request.form['rating'])
    comment = request.form.get('comment', '')
    request_id = request.form.get('material_request_id') or None

    if rating < 1 or rating > 5:
        flash('Rating must be between 1 and 5.', 'danger')
        return redirect(request.referrer or '/material_requests')

    if request_id:
        cursor.execute(
            """
            SELECT rating_id FROM supplier_ratings
            WHERE material_request_id = %s AND rated_by = %s
            """,
            (request_id, session['user_id']),
        )
        if cursor.fetchone():
            flash('You have already rated this delivery.', 'info')
            return redirect(request.referrer or '/material_requests')

    try:
        cursor.execute(
            """
            INSERT INTO supplier_ratings
            (supplier_id, rated_by, material_request_id, rating, comment)
            VALUES (%s,%s,%s,%s,%s)
            """,
            (supplier_id, session['user_id'], request_id, rating, comment),
        )
        db.commit()
        log_activity(cursor, db, session['user_id'], 'RATE_SUPPLIER',
                     'supplier_ratings', cursor.lastrowid)
        flash('Thank you for your rating!', 'success')
    except Exception as e:
        flash(f'Rating failed. Run database upgrade script. ({e})', 'danger')
    return redirect(request.referrer or '/material_requests')


# ─── ADMIN & REPORTS ────────────────────────────────────────────────────────

@app.route('/reports')
@role_required(['Admin'])
def reports():
    cursor.execute(
        """
        SELECT DATE_FORMAT(order_date, '%%Y-%%m') AS month,
               SUM(total_price) AS revenue,
               COUNT(*) AS order_count
        FROM orders
        GROUP BY DATE_FORMAT(order_date, '%%Y-%%m')
        ORDER BY month DESC
        LIMIT 12
        """
    )
    monthly_revenue = cursor.fetchall()

    cursor.execute(
        """
        SELECT order_status, COUNT(*) AS count,
               SUM(total_price) AS total
        FROM orders
        GROUP BY order_status
        """
    )
    orders_by_status = cursor.fetchall()

    cursor.execute(
        """
        SELECT p.product_name, p.product_code,
               SUM(o.quantity) AS units_sold,
               SUM(o.total_price) AS revenue
        FROM orders o
        JOIN products p ON o.product_id = p.product_id
        WHERE o.order_status != 'Cancelled'
        GROUP BY p.product_id
        ORDER BY revenue DESC
        LIMIT 10
        """
    )
    top_products = cursor.fetchall()

    try:
        cursor.execute(
            """
            SELECT u.full_name, AVG(sr.rating) AS avg_rating, COUNT(*) AS ratings
            FROM supplier_ratings sr
            JOIN users u ON sr.supplier_id = u.user_id
            GROUP BY sr.supplier_id
            ORDER BY avg_rating DESC
            """
        )
        supplier_ratings_report = cursor.fetchall()
    except Exception:
        supplier_ratings_report = []

    try:
        cursor.execute(
            """
            SELECT al.*, u.full_name
            FROM activity_log al
            LEFT JOIN users u ON al.user_id = u.user_id
            ORDER BY al.created_at DESC
            LIMIT 50
            """
        )
        audit_log = cursor.fetchall()
    except Exception:
        audit_log = []

    return render_template(
        'reports.html',
        monthly_revenue=monthly_revenue,
        orders_by_status=orders_by_status,
        top_products=top_products,
        supplier_ratings_report=supplier_ratings_report,
        audit_log=audit_log,
        **nav_context(),
    )


@app.route('/admin')
@role_required(['Admin'])
def admin():
    page = request.args.get('page', 1, type=int)

    cursor.execute("SELECT COUNT(*) AS total FROM users")
    total_users = cursor.fetchone()['total']
    cursor.execute("SELECT COUNT(*) AS total FROM products")
    total_products = cursor.fetchone()['total']
    cursor.execute("SELECT COUNT(*) AS total FROM orders")
    total_orders = cursor.fetchone()['total']
    cursor.execute("SELECT SUM(total_price) AS revenue FROM orders")
    revenue = cursor.fetchone()['revenue'] or 0

    users, up, utp, uc = paginate(
        cursor,
        "SELECT COUNT(*) AS c FROM users",
        "SELECT * FROM users ORDER BY user_id DESC",
        (),
        page,
    )

    cursor.execute("SELECT * FROM products ORDER BY product_id DESC LIMIT 20")
    products = cursor.fetchall()

    cursor.execute(
        """
        SELECT orders.*, products.product_name
        FROM orders
        JOIN products ON orders.product_id = products.product_id
        ORDER BY orders.order_id DESC
        LIMIT 20
        """
    )
    orders = cursor.fetchall()

    return render_template(
        'admin.html',
        total_users=total_users,
        total_products=total_products,
        total_orders=total_orders,
        total_revenue=revenue,
        users=users,
        products=products,
        orders=orders,
        pagination=pagination_context(up, utp, uc, '/admin', {}),
        **nav_context(),
    )


@app.route('/delete_user/<int:id>')
@role_required(['Admin'])
def delete_user(id):
    cursor.execute("DELETE FROM users WHERE user_id=%s", (id,))
    db.commit()
    log_activity(cursor, db, session['user_id'], 'DELETE_USER', 'users', id)
    return redirect('/admin')


@app.route('/admin_delete_product/<int:id>')
@role_required(['Admin'])
def delete_product_admin(id):
    cursor.execute("DELETE FROM products WHERE product_id=%s", (id,))
    db.commit()
    log_activity(cursor, db, session['user_id'], 'DELETE_PRODUCT', 'products', id)
    return redirect(url_for('admin'))


@app.route('/testdb')
def testdb():
    cursor.execute("SHOW TABLES")
    return str(cursor.fetchall())


@app.route('/logout')
def logout():
    if 'user_id' in session:
        log_activity(cursor, db, session['user_id'], 'LOGOUT', 'users', session['user_id'])
    session.clear()
    response = redirect('/login')
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    return response


# Legacy redirects
@app.route('/index.html')
def old_index():
    return redirect(url_for('home'))


@app.route('/dashboard.html')
def old_dashboard():
    return redirect(url_for('dashboard'))


@app.route('/products.html')
def old_products():
    return redirect(url_for('products'))


@app.route('/orders.html')
def old_orders():
    return redirect(url_for('orders'))


@app.route('/login.html')
def old_login():
    return redirect(url_for('login_page'))


if __name__ == '__main__':
    app.run(debug=True)
