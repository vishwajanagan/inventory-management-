# app.py
from flask import Flask, render_template, request, redirect, session, url_for, flash
from db import get_db_connection, initialize_database
from utils import hash_password, verify_password
import datetime

app = Flask(__name__)
app.secret_key = "supersecretkey"  # change for production

# GST rates by category (you can edit)
GST_RATES = {
    'electronics': 18.0,
    'clothing': 12.0,
    'groceries': 5.0,
    'books': 0.0,
}

# Initialize DB on startup
initialize_database()

# ---------------------------
# Helpers
# ---------------------------
def login_required(fn):
    from functools import wraps
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            return redirect('/login')
        return fn(*args, **kwargs)
    return wrapper

def role_allowed(roles):
    def decorator(fn):
        from functools import wraps
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if session.get('role') not in roles:
                flash("Access denied.", "danger")
                return redirect('/dashboard')
            return fn(*args, **kwargs)
        return wrapper
    return decorator

# ---------------------------
# Routes
# ---------------------------
@app.route('/')
def home():
    return redirect('/login')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        name = request.form['username'].strip()
        password = request.form['password']
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT user_id, access_type, password FROM users WHERE name = %s", (name,))
        user = cur.fetchone()
        cur.close()
        conn.close()
        if user and verify_password(password, user[2]):
            session['user_id'] = user[0]
            session['role'] = user[1]
            session['username'] = name
            flash("Login successful!", "success")
            return redirect('/dashboard')
        flash("Invalid username or password.", "danger")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash("Logged out.", "info")
    return redirect('/login')

@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html', role=session.get('role'), username=session.get('username'))

# --- PRODUCTS ---
@app.route('/products')
@login_required
def products():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT product_id, description, category, cost_price, selling_price, number_in_stock, number_sold FROM products ORDER BY product_id")
    products = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('products.html', products=products)

@app.route('/add_product', methods=['GET', 'POST'])
@login_required
@role_allowed(['employee', 'manager', 'admin'])
def add_product():
    if request.method == 'POST':
        desc = request.form['description']
        category = request.form['category']
        cost = float(request.form['cost'])
        sell = float(request.form['selling'])
        stock = int(request.form['stock'])
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO products (description, category, cost_price, selling_price, number_in_stock)
            VALUES (%s, %s, %s, %s, %s)
        """, (desc, category, cost, sell, stock))
        conn.commit()
        cur.close()
        conn.close()
        flash("Product added.", "success")
        return redirect('/products')
    return render_template('add_product.html')

@app.route('/restock', methods=['GET', 'POST'])
@login_required
@role_allowed(['employee', 'manager', 'admin'])
def restock():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT product_id, description, number_in_stock FROM products ORDER BY product_id")
    items = cur.fetchall()

    if request.method == 'POST':
        product_id = int(request.form['product_id'])
        quantity = int(request.form['quantity'])
        cur.execute("UPDATE products SET number_in_stock = number_in_stock + %s WHERE product_id = %s", (quantity, product_id))
        conn.commit()
        cur.close()
        conn.close()
        flash("Stock updated.", "success")
        return redirect('/products')

    cur.close()
    conn.close()
    return render_template('restock.html', products=items)

# --- CREATE BILL ---
@app.route('/create_bill', methods=['GET', 'POST'])
@login_required
@role_allowed(['employee', 'manager', 'admin'])
def create_bill():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT product_id, description, category, cost_price, selling_price, number_in_stock FROM products ORDER BY product_id")
    products = cur.fetchall()

    if request.method == 'POST':
        product_id = int(request.form['product_id'])
        quantity = int(request.form['quantity'])
        discount_percent = float(request.form.get('discount', 0.0))

        # fetch product
        cur.execute("SELECT description, category, cost_price, selling_price, number_in_stock FROM products WHERE product_id = %s", (product_id,))
        prod = cur.fetchone()
        if not prod:
            flash("Product not found.", "danger")
            cur.close()
            conn.close()
            return redirect('/create_bill')

        desc, category, cost_price, selling_price, stock = prod
        if quantity > stock:
            flash("Insufficient stock.", "danger")
            cur.close()
            conn.close()
            return redirect('/create_bill')

        gst_rate = GST_RATES.get(category.lower(), 0.0) / 100.0
        cgst_rate = gst_rate / 2.0
        sgst_rate = gst_rate / 2.0

        total_cost = selling_price * quantity * (1 - discount_percent / 100.0)
        cgst_amount = total_cost * cgst_rate
        sgst_amount = total_cost * sgst_rate
        total_with_gst = total_cost + cgst_amount + sgst_amount
        profit = (selling_price - cost_price) * quantity

        # insert bill
        cur.execute("""
            INSERT INTO bills (time, employee_id, cost, product_name, total_items, discount, cgst, sgst, total_profit)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (datetime.datetime.now(), session['user_id'], total_with_gst, desc, quantity, discount_percent, cgst_amount, sgst_amount, profit))

        # update product
        cur.execute("UPDATE products SET number_in_stock = number_in_stock - %s, number_sold = number_sold + %s WHERE product_id = %s", (quantity, quantity, product_id))
        cur.execute("UPDATE products SET profit = (selling_price - cost_price) * number_sold WHERE product_id = %s", (product_id,))

        # update user sales
        cur.execute("UPDATE users SET sales = sales + %s WHERE user_id = %s", (total_with_gst, session['user_id']))

        conn.commit()
        cur.close()
        conn.close()
        flash("Bill created successfully.", "success")
        return redirect('/products')

    cur.close()
    conn.close()
    return render_template('create_bill.html', products=products)

# --- Employee stats ---
@app.route('/employee_stats')
@login_required
@role_allowed(['employee', 'manager', 'admin'])
def employee_stats():
    user_id = session['user_id']
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT sales FROM users WHERE user_id = %s", (user_id,))
    sales_row = cur.fetchone()
    sales = sales_row[0] if sales_row else 0.0

    cur.execute("SELECT SUM(total_profit) FROM bills WHERE employee_id = %s", (user_id,))
    profit_row = cur.fetchone()
    profit = profit_row[0] if profit_row and profit_row[0] is not None else 0.0

    cur.close()
    conn.close()
    return render_template('employee_stats.html', sales=sales, profit=profit)

# --- Team sales (manager/admin) ---
@app.route('/team_sales')
@login_required
@role_allowed(['manager', 'admin'])
def team_sales():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT name, sales FROM users WHERE access_type = 'employee' ORDER BY name")
    employees = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('team_sales.html', employees=employees)

# --- Adjust pricing (manager/admin) ---
@app.route('/adjust_pricing', methods=['GET', 'POST'])
@login_required
@role_allowed(['manager', 'admin'])
def adjust_pricing():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT product_id, description, selling_price FROM products ORDER BY product_id")
    products = cur.fetchall()

    if request.method == 'POST':
        product_id = int(request.form['product_id'])
        new_price = float(request.form['new_price'])
        cur.execute("UPDATE products SET selling_price = %s WHERE product_id = %s", (new_price, product_id))
        conn.commit()
        cur.close()
        conn.close()
        flash("Price updated.", "success")
        return redirect('/products')

    cur.close()
    conn.close()
    return render_template('adjust_pricing.html', products=products)

# --- Admin functions ---
@app.route('/admin', methods=['GET'])
@login_required
@role_allowed(['admin'])
def admin_panel():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT user_id, name, access_type, sales FROM users ORDER BY user_id")
    users = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('admin.html', users=users)

@app.route('/admin/add_user', methods=['POST'])
@login_required
@role_allowed(['admin'])
def admin_add_user():
    name = request.form['name'].strip()
    role = request.form['role']
    password = request.form['password']
    hashed = hash_password(password)
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("INSERT INTO users (name, access_type, password) VALUES (%s, %s, %s)", (name, role, hashed))
        conn.commit()
        flash("User added.", "success")
    except Exception as e:
        flash("Error adding user: " + str(e), "danger")
    finally:
        cur.close()
        conn.close()
    return redirect('/admin')

@app.route('/admin/remove_user', methods=['POST'])
@login_required
@role_allowed(['admin'])
def admin_remove_user():
    user_id = int(request.form['user_id'])
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM users WHERE user_id = %s", (user_id,))
    conn.commit()
    cur.close()
    conn.close()
    flash("User removed.", "success")
    return redirect('/admin')

@app.route('/admin/reset_password', methods=['POST'])
@login_required
@role_allowed(['admin'])
def admin_reset_password():
    user_id = int(request.form['user_id'])
    new_password = request.form['new_password']
    hashed = hash_password(new_password)
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("UPDATE users SET password = %s WHERE user_id = %s", (hashed, user_id))
    conn.commit()
    cur.close()
    conn.close()
    flash("Password reset.", "success")
    return redirect('/admin')

# ---------------------------
# Run
# ---------------------------
if __name__ == "__main__":
    app.run(debug=True)
