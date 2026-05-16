from flask import Flask, render_template, redirect, url_for, request
import mysql.connector

app = Flask(__name__)
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
    return render_template('dashboard.html')


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
def login():
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
