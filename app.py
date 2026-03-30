from flask import Flask, render_template, request, redirect, session, flash, url_for, jsonify
import sqlite3
import os
import uuid
from werkzeug.security import generate_password_hash, check_password_hash
from flask_mail import Mail, Message
import random

app = Flask(__name__)
app.secret_key = "secret123"

DB_NAME = "database.db"
UPLOAD_FOLDER = "static/images"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# FLASK MAIL CONFIG
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'erp@zoihospitals.com'
app.config['MAIL_PASSWORD'] = 'twqowggcievrehbl'  # no spaces
app.config['MAIL_DEFAULT_SENDER'] = 'erp@zoihospitals.com'

mail = Mail(app)

# DATABASE CONNECTION
def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

# CREATE TABLES
def create_tables():
    db = get_db()
    cursor = db.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT
    )""")
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS admin(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT
    )""")
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS products(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        price REAL,
        description TEXT,
        image TEXT,
        quantity INTEGER
    )""")
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS orders(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        product_id INTEGER,
        quantity INTEGER
    )""")
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS order_history(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_number TEXT,
        user_id INTEGER,
        product_id INTEGER,
        quantity INTEGER,
        price REAL,
        status TEXT,
        payment_status TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")

    # Default admin
    cursor.execute("SELECT * FROM admin WHERE username=?", ("admin",))
    if not cursor.fetchone():
        cursor.execute("INSERT INTO admin(username,password) VALUES(?,?)",
                       ("admin", generate_password_hash("admin123")))

    db.commit()
    db.close()

create_tables()

# ----------------- ROUTES -----------------
@app.route("/")
def home():
    return render_template("home.html")
#REGISTER FOR USER 
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        email = request.form["email"]  # collect email
        password = generate_password_hash(request.form["password"])
        db = get_db()
        cursor = db.cursor()
        try:
            cursor.execute(
                "INSERT INTO users(username,email,password) VALUES(?,?,?)",
                (username, email, password)
            )
            db.commit()
            flash("Registration successful! Please login.", "success")
        except sqlite3.IntegrityError:
            flash("Username or Email already exists", "danger")
        finally:
            db.close()
        return redirect("/user_login")
    return render_template("user_register.html")
# ---------------- ADMIN ROUTES ----------------
@app.route("/admin_login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT * FROM admin WHERE username=?", (username,))
        admin = cursor.fetchone()
        db.close()

        if admin and check_password_hash(admin["password"], password):
            session["admin"] = admin["id"]
            return redirect("/admin_dashboard")
        flash("Invalid credentials", "danger")
    return render_template("admin_login.html")
#ADMIN DASHBOARD
@app.route("/admin_dashboard")
def admin_dashboard():
    if "admin" not in session:
        return redirect("/admin_login")
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM products")
    products = cursor.fetchall()

    cursor.execute("SELECT COUNT(*) FROM order_history")
    total_orders = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM users")
    total_users = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM products")
    total_products = cursor.fetchone()[0]

    cursor.execute("SELECT SUM(price*quantity) FROM order_history WHERE payment_status='Paid'")
    revenue = cursor.fetchone()[0] or 0

    cursor.execute("""
    SELECT DATE(created_at) as date, SUM(price*quantity) as total
    FROM order_history
    GROUP BY DATE(created_at)
    ORDER BY DATE(created_at)
    """)
    rows = cursor.fetchall()
    labels = [row["date"] for row in rows]
    values = [row["total"] for row in rows]
    db.close()

    return render_template("admin_dashboard.html",
                           products=products, revenue=revenue,
                           total_orders=total_orders, total_users=total_users,
                           total_products=total_products, labels=labels, values=values)

#ADMIN ORDERS
@app.route("/admin_orders")
def admin_orders():
    if "admin" not in session:
        return redirect("/admin_login")

    filter_status = request.args.get("filter", "All")
    db = get_db()
    cursor = db.cursor()

    if filter_status == "All":
        cursor.execute("""
        SELECT oh.id, oh.order_number, u.username, p.name, p.image,
               oh.quantity, oh.price, oh.status, oh.payment_status, oh.created_at
        FROM order_history oh
        JOIN users u ON oh.user_id=u.id
        JOIN products p ON oh.product_id=p.id
        ORDER BY oh.created_at DESC
        """)
    else:
        cursor.execute("""
        SELECT oh.id, oh.order_number, u.username, p.name, p.image,
               oh.quantity, oh.price, oh.status, oh.payment_status, oh.created_at
        FROM order_history oh
        JOIN users u ON oh.user_id=u.id
        JOIN products p ON oh.product_id=p.id
        WHERE oh.status=?
        ORDER BY oh.created_at DESC
        """, (filter_status,))
    orders = cursor.fetchall()

    cursor.execute("SELECT COUNT(*) FROM order_history")
    total_orders = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM order_history WHERE status='Pending'")
    pending_orders = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM order_history WHERE status='Completed'")
    completed_orders = cursor.fetchone()[0]

    cursor.execute("SELECT SUM(price*quantity) FROM order_history WHERE payment_status='Paid'")
    revenue = cursor.fetchone()[0] or 0
    db.close()

    return render_template("admin_orders.html",
                           orders=orders, total_orders=total_orders,
                           pending_orders=pending_orders, completed_orders=completed_orders,
                           revenue=revenue, filter_status=filter_status)
#UPDATE ORDER STATUS
@app.route("/update_order_status/<int:order_id>/<status>")
def update_order_status(order_id, status):
    db = get_db()
    cursor = db.cursor()
    cursor.execute("UPDATE order_history SET status=? WHERE id=?", (status, order_id))
    db.commit()
    db.close()
    return redirect("/admin_orders")
#UPDATE TRACKING
@app.route("/update_tracking/<int:id>/<status>")
def update_tracking(id, status):
    if "admin" not in session:
        return redirect("/admin_login")
    db = get_db()
    cursor = db.cursor()
    cursor.execute("UPDATE order_history SET status=? WHERE id=?", (status, id))
    db.commit()
    db.close()
    return redirect("/admin_orders")
#ADMIN LOGOUT
@app.route("/admin_logout")
def admin_logout():
    session.pop("admin", None)
    flash("Admin logged out successfully", "success")
    return redirect("/")

# ---------------- USER ROUTES ----------------

#USER LOGIN
@app.route("/user_login", methods=["GET", "POST"])
def user_login():
    if request.method == "POST":
        username_or_email = request.form["username"]  # user enters username OR email
        password = request.form["password"]
        db = get_db()
        cursor = db.cursor()
        cursor.execute(
            "SELECT * FROM users WHERE username=? OR email=?", 
            (username_or_email, username_or_email)
        )
        user = cursor.fetchone()
        db.close()

        if user and check_password_hash(user["password"], password):
            otp = str(random.randint(100000, 999999))
            session['otp'] = otp
            session['otp_user'] = user['id']

            try:
                # Use app context to ensure Flask-Mail works
                with app.app_context():
                    msg = Message(
                        "OTP for Ravi Mart Login",
                        recipients=[user['email']]  # send to registered email
                    )
                    msg.body = f"Hello {user['username']}! Your OTP is {otp}"
                    mail.send(msg)
                flash("OTP sent to your email", "success")
                return redirect("/verify_otp")
            except Exception as e:
                print("Email error:", e)
                flash("Failed to send OTP. Check email config", "danger")
        else:
            flash("Invalid username or password", "danger")
    return render_template("user_login.html")
#OTP LOGIN
@app.route("/otp_login", methods=["GET", "POST"])
def otp_login():
    if request.method == "POST":
        username_or_email = request.form["username"]
        db = get_db()
        cursor = db.cursor()
        cursor.execute(
            "SELECT * FROM users WHERE username=? OR email=?", 
            (username_or_email, username_or_email)
        )
        user = cursor.fetchone()
        db.close()
        if user:
            otp = str(random.randint(100000, 999999))
            session['otp'] = otp
            session['otp_user'] = user['id']
            try:
                with app.app_context():
                    msg = Message(
                        "OTP for Ravi Mart Login",
                        recipients=[user['email']]
                    )
                    msg.body = f"Hello {user['username']}! Your OTP is {otp}"
                    mail.send(msg)
                flash("OTP sent to your email", "success")
                return redirect("/verify_otp")
            except Exception as e:
                print("Email error:", e)
                flash("Failed to send OTP. Check email config", "danger")
        else:
            flash("User not found", "danger")
    return render_template("otp_login.html")
#VERIFY OTP
@app.route("/verify_otp", methods=["GET", "POST"])
def verify_otp():
    if request.method == "POST":
        entered_otp = request.form["otp"]
        if 'otp' in session and entered_otp == session['otp']:
            session["user"] = session['otp_user']
            session.pop('otp')
            session.pop('otp_user')
            flash("OTP verified! Logged in successfully", "success")
            return redirect("/user_dashboard")
        else:
            flash("Invalid OTP", "danger")
    return render_template("verify_otp.html")

# ---------------- USER DASHBOARD ----------------
@app.route("/user_dashboard")
def user_dashboard():
    if "user" not in session:
        return redirect("/user_login")

    user_id = session["user"]
    search = request.args.get("search", "")
    db = get_db()
    cursor = db.cursor()
    if search:
        cursor.execute("SELECT * FROM products WHERE name LIKE ? OR description LIKE ?",
                       ('%' + search + '%', '%' + search + '%'))
    else:
        cursor.execute("SELECT * FROM products")
    products = cursor.fetchall()
    cursor.execute("SELECT COUNT(*) FROM order_history WHERE user_id=?", (user_id,))
    order_count = cursor.fetchone()[0]
    cursor.execute("SELECT SUM(quantity) as cart_count FROM orders WHERE user_id=?", (user_id,))
    cart_count = cursor.fetchone()["cart_count"] or 0
    db.close()
    return render_template("user_dashboard.html", products=products,
                           order_count=order_count, cart_count=cart_count)

# ---------------- CART ROUTES ----------------
@app.route("/add_to_cart/<int:product_id>", methods=["POST"])
def add_to_cart(product_id):
    if "user" not in session:
        return jsonify({"success": False, "error": "Login required"}), 401

    user_id = session["user"]
    qty = int(request.form.get("qty", 1))
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM orders WHERE user_id=? AND product_id=?", (user_id, product_id))
    existing = cursor.fetchone()
    if existing:
        new_qty = existing["quantity"] + qty
        cursor.execute("UPDATE orders SET quantity=? WHERE id=?", (new_qty, existing["id"]))
    else:
        cursor.execute("INSERT INTO orders(user_id, product_id, quantity) VALUES(?,?,?)", (user_id, product_id, qty))
    db.commit()
    cursor.execute("SELECT SUM(quantity) as cart_count FROM orders WHERE user_id=?", (user_id,))
    cart_count = cursor.fetchone()["cart_count"] or 0
    db.close()
    return jsonify({"success": True, "cart_count": cart_count})
#CART
@app.route("/cart")
def cart():
    if "user" not in session:
        return redirect("/user_login")
    user_id = session["user"]
    db = get_db()
    cursor = db.cursor()
    cursor.execute("""
    SELECT orders.id as order_id, products.name, products.price,
           products.image, orders.quantity
    FROM orders
    JOIN products ON orders.product_id = products.id
    WHERE orders.user_id=?
    """, (user_id,))
    items = cursor.fetchall()
    total = sum(item["price"] * item["quantity"] for item in items)
    cart_count = sum(item["quantity"] for item in items)
    db.close()
    return render_template("cart.html", items=items, total=total, cart_count=cart_count)

# ---------------- CHECKOUT & PAYMENT ----------------
@app.route("/checkout")
def checkout():
    if "user" not in session:
        return redirect("/user_login")
    user_id = session["user"]
    db = get_db()
    cursor = db.cursor()
    cursor.execute("""
    SELECT orders.id as order_id, products.name, products.price,
           products.image, orders.quantity
    FROM orders
    JOIN products ON orders.product_id = products.id
    WHERE orders.user_id=?
    """, (user_id,))
    items = cursor.fetchall()
    total = sum(item["price"] * item["quantity"] for item in items)
    db.close()
    return render_template("checkout.html", items=items, total=total)
#PAYMENT
@app.route("/payment", methods=["GET", "POST"])
def payment():
    if "user" not in session:
        return redirect("/user_login")
    user_id = session["user"]
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM orders WHERE user_id=?", (user_id,))
    items = cursor.fetchall()
    if not items:
        flash("Your cart is empty.", "danger")
        db.close()
        return redirect("/cart")
    order_number = str(uuid.uuid4())[:8]
    if request.method == "POST":
        db.close()
        return redirect(url_for("payment_success", order_number=order_number))
    db.close()
    return render_template("payment.html", order_number=order_number, items=items)
#PAYMENT STATUS
@app.route("/payment_success/<order_number>")
def payment_success(order_number):
    if "user" not in session:
        return redirect("/user_login")
    user_id = session["user"]
    db = get_db()
    cursor = db.cursor()
    cursor.execute("""
    SELECT orders.product_id, orders.quantity, products.price
    FROM orders
    JOIN products ON orders.product_id=products.id
    WHERE orders.user_id=?
    """, (user_id,))
    items = cursor.fetchall()
    for item in items:
        cursor.execute("""
        INSERT INTO order_history(order_number,user_id,product_id,quantity,price,status,payment_status)
        VALUES(?,?,?,?,?,?,?)
        """, (order_number, user_id, item["product_id"], item["quantity"], item["price"], "Pending", "Paid"))
    cursor.execute("DELETE FROM orders WHERE user_id=?", (user_id,))
    db.commit()
    db.close()
    return redirect("/my_orders")

# ---------------- MY ORDERS ----------------
@app.route("/my_orders")
def my_orders():
    if "user" not in session:
        return redirect("/user_login")
    user_id = session["user"]
    db = get_db()
    cursor = db.cursor()
    cursor.execute("""
    SELECT oh.id, oh.order_number, p.name, p.image, oh.quantity,
           oh.price, oh.status, oh.payment_status, oh.created_at
    FROM order_history oh
    JOIN products p ON oh.product_id=p.id
    WHERE oh.user_id=?
    ORDER BY oh.created_at DESC
    """, (user_id,))
    orders = cursor.fetchall()
    db.close()
    return render_template("my_orders.html", orders=orders)

# ---------------- TRACK ORDER ----------------
@app.route("/track_order/<int:order_id>")
def track_order(order_id):
    db = get_db()
    cursor = db.cursor()
    cursor.execute("""
    SELECT oh.order_number, p.name, p.image, oh.quantity, oh.price, oh.status
    FROM order_history oh
    JOIN products p ON oh.product_id=p.id
    WHERE oh.id=?
    """, (order_id,))
    order = cursor.fetchone()
    db.close()
    return render_template("track_order.html", order=order)

# ---------------- LOGOUT ----------------
@app.route("/logout")
def logout():
    session.pop("user", None)
    flash("User logged out successfully", "success")
    return redirect("/")

if __name__ == "__main__":
    app.run(debug=True)