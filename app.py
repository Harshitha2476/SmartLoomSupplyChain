from flask import Flask, render_template, redirect, url_for, request, session
import mysql.connector

app = Flask(__name__)
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

    if 'user_id' not in session:

        return redirect('/login')

    return render_template(
        'dashboard.html',
        user_name=session['user_name'],
        role=session['role']
    )


# PRODUCTS PAGE
@app.route('/products')
def products():

    query = "SELECT * FROM products"

    cursor.execute(query)

    all_products = cursor.fetchall()

    return render_template(
        'products.html',
        products=all_products
    )



# ORDERS PAGE
@app.route('/orders')
def orders():
    return render_template('orders.html')


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

        return "Email already exists"

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

    return "Invalid Email or Password"

@app.route('/logout')
def logout():

    session.clear()

    return redirect('/login')
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
