from flask import Flask, render_template, redirect, url_for

app = Flask(__name__)


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
    return render_template('products.html')


# ORDERS PAGE
@app.route('/orders')
def orders():
    return render_template('orders.html')


# LOGIN PAGE
@app.route('/login')
def login():
    return render_template('login.html')


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