from flask import Flask, flash, render_template, redirect, url_for, request, session, flash
import mysql.connector
from functools import wraps

app = Flask(__name__)

def role_required(allowed_roles): #step 6

    def decorator(f):

        @wraps(f)

        def wrapper(*args, **kwargs):

            # USER NOT LOGGED IN
            if 'user_id' not in session:

                return redirect('/login')

            # ROLE CHECK
            if session['role'] not in allowed_roles:

                return "Access Denied"

            return f(*args, **kwargs)

        return wrapper

    return decorator

app.secret_key = "smartloom_secret_key"
db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="password",
    database="smartloom"
)

cursor = db.cursor(dictionary=True)

# HOME PAGE
@app.route('/')
def home():
    return render_template('index.html')


# HANDLE /index
@app.route('/index')
def index():
    return redirect(url_for('home'))


# DASHBOARD PAGE
@app.route('/dashboard')
def dashboard():

    # SESSION SECURITY
    if 'user_id' not in session:

        return redirect('/login')

    # TOTAL PRODUCTS
    cursor.execute(
        "SELECT COUNT(*) AS total_products FROM products"
    )

    total_products = cursor.fetchone()['total_products']

    # TOTAL ORDERS
    cursor.execute(
        "SELECT COUNT(*) AS total_orders FROM orders"
    )

    total_orders = cursor.fetchone()['total_orders']

    # TOTAL USERS
    cursor.execute(
        "SELECT COUNT(*) AS total_users FROM users"
    )

    total_users = cursor.fetchone()['total_users']

    # TOTAL REVENUE
    cursor.execute(
        """
        SELECT SUM(total_price) AS revenue
        FROM orders
        """
    )

    revenue_result = cursor.fetchone()

    total_revenue = revenue_result['revenue']

    if total_revenue is None:
        total_revenue = 0

    # LOW STOCK PRODUCTS
    cursor.execute(
        """
        SELECT *
        FROM products
        WHERE stock < 10
        """
    )

    low_stock_products = cursor.fetchall()

    # RECENT ORDERS
    cursor.execute(
        """
        SELECT
            orders.order_id,
            products.product_name,
            orders.total_price,
            orders.order_status

        FROM orders

        JOIN products
        ON orders.product_id = products.product_id

        ORDER BY orders.order_date DESC

        LIMIT 5
        """
    )

    recent_orders = cursor.fetchall()

    return render_template(

        'dashboard.html',

        total_products=total_products,
        total_orders=total_orders,
        total_users=total_users,
        total_revenue=total_revenue,
        low_stock_products=low_stock_products,
        recent_orders=recent_orders

    )


# PRODUCTS PAGE
@app.route('/products')
@role_required(['Buyer', 'Weaver', 'Admin'])
def products():
    if 'user_id' not in session:

        return redirect('/login')
    if session['role'] not in ['Buyer', 'Weaver', 'Admin']:
        return redirect('/dashboard')
    query = "SELECT * FROM products"

    cursor.execute(query)

    all_products = cursor.fetchall()

    return render_template(
        'products.html',
        products=all_products
    )



# ORDERS PAGE
@app.route('/orders')

@role_required(['Buyer', 'Weaver', 'Admin'])

def orders():

    # BUYER
    if session['role'] == 'Buyer':

        query = """
        SELECT
            orders.order_id,
            products.product_name,
            orders.quantity,
            orders.total_price,
            orders.order_status,
            orders.order_date

        FROM orders

        JOIN products
        ON orders.product_id = products.product_id

        WHERE orders.user_id=%s

        ORDER BY orders.order_date DESC
        """

        cursor.execute(
            query,
            (session['user_id'],)
        )

    else:

        # WEAVER + ADMIN
        query = """
        SELECT
            orders.order_id,
            users.full_name,
            products.product_name,
            orders.quantity,
            orders.total_price,
            orders.order_status,
            orders.order_date

        FROM orders

        JOIN users
        ON orders.user_id = users.user_id

        JOIN products
        ON orders.product_id = products.product_id

        ORDER BY orders.order_date DESC
        """

        cursor.execute(query)

    all_orders = cursor.fetchall()

    return render_template(
        'orders.html',
        orders=all_orders
    )


# LOGIN PAGE
@app.route('/login')
def login_page():
    return render_template('login.html')


@app.route('/testdb')
def testdb():

    cursor.execute("SHOW TABLES")

    tables = cursor.fetchall()

    return str(tables)

@app.route('/add_product', methods=['POST'])
@role_required(['Weaver', 'Admin'])
def add_product():

    name = request.form['name']

    category = request.form['category']

    weaver = request.form['weaver']

    price = request.form['price']

    stock = request.form['stock']

    description = request.form['description']

    # FIRST INSERT WITHOUT PRODUCT CODE

    query = """
    INSERT INTO products
    (
        product_name,
        category,
        weaver_name,
        price,
        stock,
        description
    )

    VALUES(%s,%s,%s,%s,%s,%s)
    """

    values = (
        name,
        category,
        weaver,
        price,
        stock,
        description
    )

    cursor.execute(query, values)

    db.commit()


    # GET LAST INSERTED ID

    product_id = cursor.lastrowid

    # GENERATE PRODUCT CODE

    product_code = f"P-{1000 + product_id}"

    # UPDATE PRODUCT CODE

    update_query = """
    UPDATE products
    SET product_code=%s
    WHERE product_id=%s
    """

    cursor.execute(
        update_query,
        (product_code, product_id)
    )

    db.commit()
    flash('Product added successfully!', 'success')
    return redirect('/products')


@app.route('/register', methods=['POST'])
def register():

    full_name = request.form['name']

    email = request.form['email']

    phone = request.form['phone']

    password = request.form['password']

    location = request.form['location']

    role = request.form['role']

    # CHECK IF EMAIL EXISTS

    check_query = """
    SELECT * FROM users
    WHERE email=%s
    """

    cursor.execute(check_query, (email,))

    existing_user = cursor.fetchone()

    if existing_user:

        flash('Email already registered!', 'danger')

        return redirect('/login')

    # INSERT USER

    insert_query = """
    INSERT INTO users
    (
        full_name,
        email,
        phone,
        password,
        role,
        location
    )

    VALUES(%s,%s,%s,%s,%s,%s)
    """

    values = (
        full_name,
        email,
        phone,
        password,
        role,
        location
    )

    cursor.execute(insert_query, values)

    db.commit()

    return redirect('/login')
@app.route('/login', methods=['POST'])
def login():

    email = request.form['email']

    password = request.form['password']

    role = request.form['role']

    query = """
    SELECT * FROM users
    WHERE email=%s
    AND password=%s
    AND role=%s
    """

    values = (
        email,
        password,
        role
    )

    cursor.execute(query, values)

    user = cursor.fetchone()

    if user:

        session['user_id'] = user['user_id']

        session['user_name'] = user['full_name']

        session['role'] = user['role']

        return redirect('/dashboard')

    flash('Invalid email or password!', 'danger')
    return redirect('/login')

@app.route('/place_order', methods=['POST'])
@role_required(['Buyer'])
def place_order():

    # SESSION SECURITY
    if 'user_id' not in session:

        return redirect('/login')
    if session['role'] not in ['Buyer', 'Admin']:
        return redirect('/dashboard')

    user_id = session['user_id']

    product_id = request.form['product_id']

    # GET PRODUCT DETAILS
    query = """
    SELECT * FROM products
    WHERE product_id=%s
    """

    cursor.execute(query, (product_id,))

    product = cursor.fetchone()

    # OUT OF STOCK CHECK

    if product['stock'] <= 0:

       flash('Product is out of stock!', 'danger')

       return redirect('/products')
    # DEFAULT ORDER VALUES
    quantity = 1

    total_price = product['price'] * quantity

    # REDUCE STOCK
    new_stock = product['stock'] - 1

    update_query = """
    UPDATE products
    SET stock=%s
    WHERE product_id=%s
    """

    cursor.execute(
        update_query,
        (new_stock, product_id)
    )

    # INSERT ORDER
    insert_query = """
    INSERT INTO orders
    (
        user_id,
        product_id,
        quantity,
        total_price
    )

    VALUES(%s,%s,%s,%s)
    """

    values = (
        user_id,
        product_id,
        quantity,
        total_price
    )

    cursor.execute(insert_query, values)

    db.commit()
    flash('Order placed successfully!', 'success')
    return redirect('/orders')

@app.route('/update_order_status', methods=['POST'])

@role_required(['Weaver', 'Admin'])

def update_order_status():

    if session['role'] not in ['Weaver', 'Admin']:
        return redirect('/dashboard')
    order_id = request.form['order_id']

    status = request.form['status']

    query = """
    UPDATE orders
    SET order_status=%s
    WHERE order_id=%s
    """

    cursor.execute(
        query,
        (status, order_id)
    )

    db.commit()

    return redirect('/orders')

@app.route('/materials')
def materials():

    if 'user_id' not in session:
        return redirect('/login')

    if session['role'] not in ['Supplier', 'Admin']:
        return redirect('/dashboard')

    supplier_id = session['user_id']

    query = """
    SELECT * FROM materials
    WHERE supplier_id=%s
    """

    cursor.execute(query, (supplier_id,))

    materials = cursor.fetchall()

    return render_template(
        'materials.html',
        materials=materials
    )

@app.route('/add_material', methods=['POST'])
def add_material():

    if session['role'] != 'Supplier':
        return redirect('/dashboard')

    supplier_id = session['user_id']

    material_name = request.form['material_name']

    material_type = request.form['material_type']

    stock = request.form['stock']

    price = request.form['price']

    query = """
    INSERT INTO materials
    (
        supplier_id,
        material_name,
        material_type,
        stock,
        price
    )

    VALUES(%s,%s,%s,%s,%s)
    """

    values = (
        supplier_id,
        material_name,
        material_type,
        stock,
        price
    )

    cursor.execute(query, values)

    db.commit()

    return redirect('/materials')

@app.route('/delete_material/<int:id>')
def delete_material(id):

    if session['role'] != 'Supplier':
        return redirect('/dashboard')

    query = """
    DELETE FROM materials
    WHERE material_id=%s
    """

    cursor.execute(query, (id,))

    db.commit()

    return redirect('/materials')

@app.route('/material_requests')
def material_requests():

    if 'user_id' not in session:
        return redirect('/login')

    if session['role'] not in ['Weaver', 'Admin']:
        return redirect('/dashboard')

    query = """
    SELECT * FROM materials
    """

    cursor.execute(query)

    materials = cursor.fetchall()

    return render_template(
        'material_requests.html',
        materials=materials
    )

@app.route('/request_material', methods=['POST'])
def request_material():

    if session['role'] != 'Weaver':
        return redirect('/dashboard')
    if session['role'] not in ['Weaver', 'Admin']:
        return redirect('/dashboard')
    weaver_id = session['user_id']

    supplier_id = request.form['supplier_id']

    material_id = request.form['material_id']

    quantity = request.form['quantity']

    query = """
    INSERT INTO material_requests
    (
        weaver_id,
        supplier_id,
        material_id,
        quantity
    )

    VALUES(%s,%s,%s,%s)
    """

    values = (
        weaver_id,
        supplier_id,
        material_id,
        quantity
    )

    cursor.execute(query, values)

    db.commit()
    flash('Material request submitted successfully!', 'success')

    return redirect('/material_requests')

@app.route('/supplier_requests')
def supplier_requests():

    if 'user_id' not in session:
        return redirect('/login')

    if session['role'] not in ['Supplier', 'Admin']:
        return redirect('/dashboard')

    supplier_id = session['user_id']

    query = """
    SELECT
        material_requests.*,
        materials.material_name

    FROM material_requests

    JOIN materials
    ON material_requests.material_id =
    materials.material_id

    WHERE material_requests.supplier_id=%s
    """

    cursor.execute(query, (supplier_id,))

    requests = cursor.fetchall()

    return render_template(
        'supplier_requests.html',
        requests=requests
    )

@app.route('/update_material_status/<int:id>/<status>')
def update_material_status(id, status):

    if session['role'] not in ['Supplier', 'Admin']:
        return redirect('/dashboard')

    # GET REQUEST

    query = """
    SELECT * FROM material_requests
    WHERE request_id=%s
    """

    cursor.execute(query, (id,))

    request_data = cursor.fetchone()

    # UPDATE STATUS

    update_query = """
    UPDATE material_requests
    SET request_status=%s
    WHERE request_id=%s
    """

    cursor.execute(
        update_query,
        (status, id)
    )

    # REDUCE STOCK IF DELIVERED

    if status == 'Delivered':

        material_id = request_data['material_id']

        quantity = request_data['quantity']

        material_query = """
        SELECT * FROM materials
        WHERE material_id=%s
        """

        cursor.execute(
            material_query,
            (material_id,)
        )

        material = cursor.fetchone()

        new_stock = (
            material['stock'] - quantity
        )

        stock_query = """
        UPDATE materials
        SET stock=%s
        WHERE material_id=%s
        """

        cursor.execute(
            stock_query,
            (new_stock, material_id)
        )

    db.commit()
    flash('Material status updated successfully!', 'success')
    return redirect('/supplier_requests')

@app.route('/admin')
def admin():

    # LOGIN CHECK

    if 'user_id' not in session:

        return redirect('/login')

    # ROLE CHECK

    if session['role'] != 'Admin':

        return redirect('/dashboard')

    # TOTAL USERS

    cursor.execute(
        "SELECT COUNT(*) AS total FROM users"
    )

    total_users = cursor.fetchone()['total']

    # TOTAL PRODUCTS

    cursor.execute(
        "SELECT COUNT(*) AS total FROM products"
    )

    total_products = cursor.fetchone()['total']

    # TOTAL ORDERS

    cursor.execute(
        "SELECT COUNT(*) AS total FROM orders"
    )

    total_orders = cursor.fetchone()['total']

    # TOTAL REVENUE

    cursor.execute(
        """
        SELECT SUM(total_price) AS revenue
        FROM orders
        """
    )

    revenue = cursor.fetchone()['revenue']

    if revenue is None:
        revenue = 0

    # USERS

    cursor.execute(
        "SELECT * FROM users"
    )

    users = cursor.fetchall()

    # PRODUCTS

    cursor.execute(
        "SELECT * FROM products"
    )

    products = cursor.fetchall()

    # ORDERS

    query = """
    SELECT
        orders.*,
        products.product_name

    FROM orders

    JOIN products
    ON orders.product_id =
    products.product_id

    ORDER BY orders.order_id DESC
    """

    cursor.execute(query)

    orders = cursor.fetchall()

    return render_template(
        'admin.html',

        total_users=total_users,

        total_products=total_products,

        total_orders=total_orders,

        total_revenue=revenue,

        users=users,

        products=products,

        orders=orders
    )

@app.route('/delete_user/<int:id>')
def delete_user(id):

    if session['role'] != 'Admin':
        return redirect('/dashboard')

    query = """
    DELETE FROM users
    WHERE user_id=%s
    """

    cursor.execute(query, (id,))

    db.commit()

    return redirect('/admin')

@app.route('/admin_delete_product/<int:id>')
def admin_delete_product(id):

    if session['role'] != 'Admin':
        return redirect('/dashboard')

    query = """
    DELETE FROM products
    WHERE product_id=%s
    """

    cursor.execute(query, (id,))

    db.commit()

    return redirect('/admin')

# @app.route('/logout')
# def logout():

#     session.clear()

#     return redirect('/login')
@app.route('/logout')
def logout():

    session.clear()

    response = redirect('/login')

    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'

    return response
# OPTIONAL REDIRECTS FOR OLD .html LINKS

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
    return redirect(url_for('login'))


if __name__ == '__main__':
    app.run(debug=True)


# from flask import Flask, render_template, redirect, url_for

# app = Flask(__name__)

# # Pages
# @app.route('/')
# def home():
#     return render_template('index.html')

# @app.route('/dashboard')
# def dashboard():
#     return render_template('dashboard.html')

# @app.route('/products')
# def products():
#     return render_template('products.html')

# @app.route('/orders')
# def orders():
#     return render_template('orders.html')

# @app.route('/login')
# def login():
#     return render_template('login.html')

# # Redirects for old .html links
# redirects = {
#     "/index.html": "home",
#     "/dashboard.html": "dashboard",
#     "/products.html": "products",
#     "/orders.html": "orders",
#     "/login.html": "login"
# }

# for old, new in redirects.items():
#     app.add_url_rule(old, f"redirect_{new}", lambda new=new: redirect(url_for(new)))

# if __name__ == "__main__":
#     app.run(debug=True)
