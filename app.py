from flask import Flask, render_template, request, redirect, session, flash, url_for
import sqlite3
import os
import uuid
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "secret123"

DB_NAME = "database.db"

UPLOAD_FOLDER = "static/images"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

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
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS admin(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS products(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        price REAL,
        description TEXT,
        image TEXT,
        quantity INTEGER
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS orders(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        product_id INTEGER,
        quantity INTEGER
    )
    """)

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
    )
    """)

    db.commit()

    # Default Admin
    cursor.execute("SELECT * FROM admin WHERE username=?", ("admin",))
    if not cursor.fetchone():
        cursor.execute(
            "INSERT INTO admin (username,password) VALUES (?,?)",
            ("admin", generate_password_hash("admin123"))
        )
        db.commit()

    db.close()

create_tables()

# HOME
@app.route("/")
def home():
    return render_template("home.html")

# ADMIN LOGIN
@app.route("/admin_login", methods=["GET", "POST"])
def admin_login():

    if request.method == "POST":

        username = request.form["username"]
        password = request.form["password"]

        db = get_db()
        cursor = db.cursor()

        cursor.execute("SELECT * FROM admin WHERE username=?", (username,))
        admin = cursor.fetchone()

        if admin and check_password_hash(admin["password"], password):

            session["admin"] = admin["id"]
            return redirect("/admin_dashboard")

        flash("Invalid credentials")

    return render_template("admin_login.html")

# ADMIN DASHBOARD
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

    cursor.execute("""
    SELECT SUM(price*quantity)
    FROM order_history
    WHERE payment_status='Paid'
    """)
    revenue = cursor.fetchone()[0] or 0

    # SALES GRAPH
    cursor.execute("""
    SELECT DATE(created_at), SUM(price*quantity)
    FROM order_history
    GROUP BY DATE(created_at)
    ORDER BY DATE(created_at)
    """)

    rows = cursor.fetchall()

    labels = [row[0] for row in rows]
    values = [row[1] for row in rows]

    return render_template(
        "admin_dashboard.html",
        products=products,
        revenue=revenue,
        total_orders=total_orders,
        total_users=total_users,
        total_products=total_products,
        labels=labels,
        values=values
    )
#ADMIN ORDERS 
@app.route("/admin_orders")
def admin_orders():

    if "admin" not in session:
        return redirect("/admin_login")

    filter_status = request.args.get("filter", "All")

    db = get_db()
    cursor = db.cursor()

    # ORDERS LIST
    if filter_status == "All":
        cursor.execute("""
        SELECT oh.id,oh.order_number,u.username,p.name,p.image,
        oh.quantity,oh.price,oh.status,oh.payment_status,oh.created_at
        FROM order_history oh
        JOIN users u ON oh.user_id=u.id
        JOIN products p ON oh.product_id=p.id
        ORDER BY oh.created_at DESC
        """)
    else:
        cursor.execute("""
        SELECT oh.id,oh.order_number,u.username,p.name,p.image,
        oh.quantity,oh.price,oh.status,oh.payment_status,oh.created_at
        FROM order_history oh
        JOIN users u ON oh.user_id=u.id
        JOIN products p ON oh.product_id=p.id
        WHERE oh.status=?
        ORDER BY oh.created_at DESC
        """, (filter_status,))

    orders = cursor.fetchall()

    # TOTAL ORDERS
    cursor.execute("SELECT COUNT(*) FROM order_history")
    total_orders = cursor.fetchone()[0]

    # PENDING ORDERS
    cursor.execute("SELECT COUNT(*) FROM order_history WHERE status='Pending'")
    pending_orders = cursor.fetchone()[0]

    # COMPLETED ORDERS
    cursor.execute("SELECT COUNT(*) FROM order_history WHERE status='Completed'")
    completed_orders = cursor.fetchone()[0]

    # TOTAL REVENUE
    cursor.execute("""
    SELECT SUM(price*quantity)
    FROM order_history
    WHERE payment_status='Paid'
    """)
    revenue = cursor.fetchone()[0] or 0

    return render_template(
        "admin_orders.html",
        orders=orders,
        total_orders=total_orders,
        pending_orders=pending_orders,
        completed_orders=completed_orders,
        revenue=revenue,
        filter_status=filter_status
    )
@app.route("/update_order_status/<int:order_id>/<status>")
def update_order_status(order_id, status):

    db = get_db()
    cursor = db.cursor()

    cursor.execute("""
    UPDATE order_history
    SET status=?
    WHERE id=?
    """, (status, order_id))

    db.commit()
    return redirect("/admin_orders")
    
@app.route("/update_tracking/<int:id>/<status>")
def update_tracking(id, status):

    if "admin" not in session:
        return redirect("/admin_login")

    db = get_db()
    cursor = db.cursor()

    cursor.execute("""
    UPDATE order_history
    SET status=?
    WHERE id=?
    """, (status, id))

    db.commit()
    return redirect("/admin_orders")

# USER REGISTER
@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        username = request.form["username"]
        password = generate_password_hash(request.form["password"])

        db = get_db()
        cursor = db.cursor()

        try:
            cursor.execute(
                "INSERT INTO users(username,password) VALUES(?,?)",
                (username, password)
            )
            db.commit()

            return redirect("/user_login")

        except:
            flash("Username exists")

    return render_template("user_register.html")

# USER LOGIN
@app.route("/user_login", methods=["GET", "POST"])
def user_login():

    if request.method == "POST":

        username = request.form["username"]
        password = request.form["password"]

        db = get_db()
        cursor = db.cursor()

        cursor.execute("SELECT * FROM users WHERE username=?", (username,))
        user = cursor.fetchone()

        if user and check_password_hash(user["password"], password):

            session["user"] = user["id"]
            return redirect("/user_dashboard")

        flash("Invalid login")

    return render_template("user_login.html")

# USER DASHBOARD
@app.route("/user_dashboard")
def user_dashboard():

    if "user" not in session:
        return redirect("/user_login")

    user_id = session["user"]

    db = get_db()
    cursor = db.cursor()

    # Get products
    cursor.execute("SELECT * FROM products")
    products = cursor.fetchall()

    # Count user orders
    cursor.execute("SELECT COUNT(*) FROM order_history WHERE user_id=?", (user_id,))
    order_count = cursor.fetchone()[0]

    # Calculate cart count
    cursor.execute("SELECT SUM(quantity) as cart_count FROM orders WHERE user_id=?", (user_id,))
    result = cursor.fetchone()
    cart_count = result["cart_count"] or 0  # default 0 if empty

    return render_template(
        "user_dashboard.html",
        products=products,
        order_count=order_count,
        cart_count=cart_count
    )

# ADD TO CART
@app.route("/add_to_cart/<int:product_id>", methods=["POST"])
def add_to_cart(product_id):
    if "user" not in session:
        return {"success": False, "error": "Login required"}, 401

    user_id = session["user"]
    qty = int(request.form.get("qty", 1))

    db = get_db()
    cursor = db.cursor()

    # Check if product already in cart
    cursor.execute("SELECT * FROM orders WHERE user_id=? AND product_id=?", (user_id, product_id))
    existing = cursor.fetchone()
    if existing:
        # Update quantity
        new_qty = existing["quantity"] + qty
        cursor.execute("UPDATE orders SET quantity=? WHERE id=?", (new_qty, existing["id"]))
    else:
        cursor.execute("INSERT INTO orders(user_id,product_id,quantity) VALUES(?,?,?)",
                       (user_id, product_id, qty))

    db.commit()

    # Calculate total cart items
    cursor.execute("SELECT SUM(quantity) as cart_count FROM orders WHERE user_id=?", (user_id,))
    cart_count = cursor.fetchone()["cart_count"] or 0

    return {"success": True, "cart_count": cart_count}

# CART
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

    # Total items count
    cart_count = sum(item["quantity"] for item in items)

    return render_template("cart.html", items=items, total=total, cart_count=cart_count)

# CHECKOUT PAGE
@app.route("/checkout")
def checkout():
    if "user" not in session:
        return redirect("/user_login")

    user_id = session["user"]
    db = get_db()
    cursor = db.cursor()

    # Get items in the cart
    cursor.execute("""
    SELECT orders.id as order_id, products.name, products.price,
           products.image, orders.quantity
    FROM orders
    JOIN products ON orders.product_id = products.id
    WHERE orders.user_id=?
    """, (user_id,))

    items = cursor.fetchall()
    total = sum(item["price"] * item["quantity"] for item in items)

    return render_template("checkout.html", items=items, total=total)

# PAYMENT
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
        flash("Your cart is empty.")
        return redirect("/cart")

    order_number = str(uuid.uuid4())[:8]

    if request.method == "POST":
        return redirect(url_for("payment_success", order_number=order_number))

    return render_template("payment.html", order_number=order_number, items=items)

# PAYMENT SUCCESS
@app.route("/payment_success/<order_number>")
def payment_success(order_number):

    if "user" not in session:
        return redirect("/user_login")

    user_id = session["user"]
    db = get_db()
    cursor = db.cursor()

    cursor.execute("""
    SELECT orders.product_id,orders.quantity,products.price
    FROM orders
    JOIN products ON orders.product_id=products.id
    WHERE orders.user_id=?
    """, (user_id,))

    items = cursor.fetchall()

    for item in items:
        cursor.execute("""
        INSERT INTO order_history
        (order_number,user_id,product_id,quantity,price,status,payment_status)
        VALUES(?,?,?,?,?,?,?)
        """, (
            order_number,
            user_id,
            item["product_id"],
            item["quantity"],
            item["price"],
            "Pending",
            "Paid"
        ))

    cursor.execute("DELETE FROM orders WHERE user_id=?", (user_id,))
    db.commit()

    return redirect("/my_orders")

# MY ORDERS
@app.route("/my_orders")
def my_orders():

    if "user" not in session:
        return redirect("/user_login")

    user_id = session["user"]

    db = get_db()
    cursor = db.cursor()

    cursor.execute("""
    SELECT 
        oh.id,
        oh.order_number,
        p.name,
        p.image,
        oh.quantity,
        oh.price,
        oh.status,
        oh.payment_status,
        oh.created_at
    FROM order_history oh
    JOIN products p ON oh.product_id = p.id
    WHERE oh.user_id = ?
    ORDER BY oh.created_at DESC
    """, (user_id,))

    orders = cursor.fetchall()

    return render_template("my_orders.html", orders=orders)
# TRACK ORDER
@app.route("/track_order/<int:order_id>")
def track_order(order_id):

    db = get_db()
    cursor = db.cursor()

    cursor.execute("""
    SELECT 
        oh.order_number,
        p.name,
        p.image,
        oh.quantity,
        oh.price,
        oh.status
    FROM order_history oh
    JOIN products p ON oh.product_id = p.id
    WHERE oh.id = ?
    """, (order_id,))

    order = cursor.fetchone()

    return render_template("track_order.html", order=order)

# LOGOUT
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

if __name__ == "__main__":
    app.run(debug=True)