from flask import Flask, render_template, request, redirect, session, flash, url_for,jsonify
import sqlite3
import os
import uuid   # add at top

from werkzeug.security import generate_password_hash, check_password_hash
app = Flask(__name__)
app.secret_key = "secret123"

DB_NAME = "database.db"

# ---------------- DB CONNECTION ----------------
def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

# ---------------- CREATE TABLES ----------------
def create_tables():
    db = get_db()
    cursor = db.cursor()

    # USERS
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT
    )
    """)

    # ADMIN
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS admin (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT
    )
    """)

    # PRODUCTS
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        price REAL,
        description TEXT,
        image TEXT,
        quantity INTEGER
    )
    """)

    # CART
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        product_id INTEGER,
        quantity INTEGER
    )
    """)

    # ORDER HISTORY
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS order_history (
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

    # DEFAULT ADMIN
    cursor.execute("SELECT * FROM admin WHERE username=?", ("admin",))
    if not cursor.fetchone():
        cursor.execute("INSERT INTO admin (username, password) VALUES (?, ?)",
                       ("admin", generate_password_hash("admin123")))
        db.commit()
        print("✅ Admin created: admin / admin123")
    else:
        print("✅ Admin already exists")

    db.close()

create_tables()

# ---------------- HOME ----------------
@app.route("/")
def home():
    return render_template("home.html")

# ---------------- ADMIN LOGIN ----------------
@app.route("/admin_login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        db = get_db()
        cursor = db.cursor()

        username = request.form["username"]
        password = request.form["password"]

        cursor.execute("SELECT * FROM admin WHERE username=?", (username,))
        admin = cursor.fetchone()

        if admin and check_password_hash(admin["password"], password):
            session["admin"] = admin["id"]
            return redirect("/admin_dashboard")
        else:
            flash("Invalid admin credentials")

    return render_template("admin_login.html")

# ---------------- ADMIN DASHBOARD ----------------
@app.route("/admin_dashboard")
def admin_dashboard():
    if 'admin' not in session:
        return redirect("/admin_login")

    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM products")
    products = cursor.fetchall()

    return render_template("admin_dashboard.html", products=products)
#-----------------Admin Orders---------------------
@app.route("/admin_orders")
def admin_orders():
    if 'admin' not in session:
        return redirect("/admin_login")

    filter_status = request.args.get('filter', 'All')  # get filter from URL, default to 'All'

    db = get_db()
    cursor = db.cursor()

    # Base query
    query = """
        SELECT oh.id, oh.order_number, u.username, p.name, p.image,
               oh.quantity, oh.price, oh.status,
               oh.payment_status, oh.created_at
        FROM order_history oh
        JOIN users u ON oh.user_id = u.id
        JOIN products p ON oh.product_id = p.id
    """

    # Apply filter if not 'All'
    if filter_status in ['Pending', 'Completed', 'Cancelled']:
        query += " WHERE oh.status = ?"
        cursor.execute(query + " ORDER BY oh.created_at DESC", (filter_status,))
    else:
        cursor.execute(query + " ORDER BY oh.created_at DESC")

    orders = cursor.fetchall()

    return render_template("admin_orders.html", orders=orders, filter_status=filter_status)
# ---------------- ADD PRODUCT ----------------
UPLOAD_FOLDER = "static/images"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@app.route("/add_product", methods=["POST"])
def add_product():
    if 'admin' not in session:
        return redirect("/admin_login")

    db = get_db()
    cursor = db.cursor()

    name = request.form["name"]
    price = request.form["price"]
    description = request.form["description"]
    quantity = request.form["quantity"]

    image = request.files["image"]
    filename = image.filename
    image.save(os.path.join(UPLOAD_FOLDER, filename))

    db_path = f"images/{filename}"

    cursor.execute("""
        INSERT INTO products (name, price, description, image, quantity)
        VALUES (?, ?, ?, ?, ?)
    """, (name, price, description, db_path, quantity))

    db.commit()
    return redirect("/admin_dashboard")

# ---------------- DELETE PRODUCT ----------------
@app.route("/delete_product/<int:id>")
def delete_product(id):
    if 'admin' not in session:
        return redirect("/admin_login")

    db = get_db()
    cursor = db.cursor()
    cursor.execute("DELETE FROM products WHERE id=?", (id,))
    db.commit()

    return redirect("/admin_dashboard")
#---------------------cancel Order---------------------

@app.route('/admin/update_order/<int:order_id>/<status>')
def update_order_status(order_id, status):
    db = get_db()
    cursor = db.cursor()

    cursor.execute("UPDATE order_history SET status=? WHERE id=?", (status, order_id))
    db.commit()

    return redirect(url_for('admin_orders'))



# ---------------- ADMIN LOGOUT ----------------
@app.route("/admin_logout")
def admin_logout():
    session.pop("admin", None)  # only remove admin
    return redirect("/admin_login")

# ---------------- USER REGISTER ----------------
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        db = get_db()
        cursor = db.cursor()

        username = request.form["username"]
        password = generate_password_hash(request.form["password"])

        try:
            cursor.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, password))
            db.commit()
            return redirect("/user_login")
        except:
            flash("Username already exists")

    return render_template("user_register.html")

# ---------------- USER LOGIN ----------------
@app.route("/user_login", methods=["GET", "POST"])
def user_login():
    if request.method == "POST":
        db = get_db()
        cursor = db.cursor()

        username = request.form["username"]
        password = request.form["password"]

        cursor.execute("SELECT * FROM users WHERE username=?", (username,))
        user = cursor.fetchone()

        if user and check_password_hash(user["password"], password):
            session["user"] = user["id"]
            return redirect("/user_dashboard")
        else:
            flash("Invalid credentials")

    return render_template("user_login.html")

# ---------------- USER DASHBOARD ----------------
@app.route("/user_dashboard")
def user_dashboard():
    if 'user' not in session:
        return redirect("/user_login")

    db = get_db()
    cursor = db.cursor()
    user_id = session['user']

    # Get search term from query parameter
    search = request.args.get('search', '').strip()

    if search:
        cursor.execute("SELECT * FROM products WHERE name LIKE ?", (f"%{search}%",))
    else:
        cursor.execute("SELECT * FROM products")
    products = cursor.fetchall()

    # Cart count
    cursor.execute("SELECT SUM(quantity) FROM orders WHERE user_id=?", (user_id,))
    cart_count = cursor.fetchone()[0] or 0

    # Order count
    cursor.execute("SELECT COUNT(*) FROM order_history WHERE user_id=?", (user_id,))
    order_count = cursor.fetchone()[0] or 0

    return render_template("user_dashboard.html",
                           products=products,
                           cart_count=cart_count,
                           order_count=order_count,
                           search=search)

# ---------------- ADD TO CART ----------------
@app.route("/add_to_cart/<int:product_id>", methods=["POST"])
def add_to_cart(product_id):
    if 'user' not in session:
        return jsonify({"success": False, "error": "Login required"})

    db = get_db()
    cursor = db.cursor()
    user_id = session['user']

    qty = int(request.form.get("qty", 1))

    # Check if already exists
    cursor.execute("SELECT * FROM orders WHERE user_id=? AND product_id=?", (user_id, product_id))
    existing = cursor.fetchone()

    if existing:
        cursor.execute(
            "UPDATE orders SET quantity = quantity + ? WHERE id=?",
            (qty, existing["id"])
        )
    else:
        cursor.execute(
            "INSERT INTO orders (user_id, product_id, quantity) VALUES (?, ?, ?)",
            (user_id, product_id, qty)
        )

    db.commit()

    # ✅ Get updated cart count
    cursor.execute("SELECT SUM(quantity) FROM orders WHERE user_id=?", (user_id,))
    cart_count = cursor.fetchone()[0] or 0

    return jsonify({
        "success": True,
        "cart_count": cart_count
    })
# ---------------- CART ----------------
@app.route("/cart")
def cart():
    if 'user' not in session:
        return redirect("/user_login")

    db = get_db()
    cursor = db.cursor()
    user_id = session['user']

    cursor.execute("""
        SELECT orders.id as order_id, products.name, products.price,
               products.image, orders.quantity
        FROM orders
        JOIN products ON orders.product_id = products.id
        WHERE orders.user_id=?
    """, (user_id,))

    items = cursor.fetchall()
    total = sum(item['price'] * item['quantity'] for item in items)

    return render_template("cart.html", items=items, total=total)

# ---------------- UPDATE CART ----------------
@app.route("/update_cart/<int:order_id>", methods=["POST"])
def update_cart(order_id):
    qty = int(request.form.get("qty", 1))

    db = get_db()
    cursor = db.cursor()
    cursor.execute("UPDATE orders SET quantity=? WHERE id=?", (qty, order_id))
    db.commit()

    return redirect("/cart")

# ---------------- REMOVE ITEM ----------------
@app.route("/remove_item/<int:order_id>")
def remove_item(order_id):
    db = get_db()
    cursor = db.cursor()
    cursor.execute("DELETE FROM orders WHERE id=?", (order_id,))
    db.commit()
    return redirect("/cart")

# ---------------- CHECKOUT ----------------

@app.route('/checkout')
def checkout():
    if 'user' not in session:
        return redirect('/user_login')

    db = get_db()
    cursor = db.cursor()
    user_id = session['user']

    cursor.execute("""
        SELECT orders.id as order_id, products.name, products.price,
               orders.quantity
        FROM orders
        JOIN products ON orders.product_id = products.id
        WHERE orders.user_id=?
    """, (user_id,))

    items = cursor.fetchall()

    if not items:
        return "<h3>Your cart is empty</h3>"

    total = sum(item['price'] * item['quantity'] for item in items)

    return render_template("checkout.html", items=items, total=total)

# ---------------- PLACE ORDER ----------------
@app.route("/place_order", methods=["POST"])
def place_order():
    user_id = session['user']
    db = get_db()
    cursor = db.cursor()

    cursor.execute("""
        SELECT products.name, products.price, orders.quantity
        FROM orders
        JOIN products ON orders.product_id = products.id
        WHERE orders.user_id=?
    """, (user_id,))

    items = cursor.fetchall()

    for item in items:
        cursor.execute("""
            INSERT INTO order_history (user_id, product_name, price, quantity)
            VALUES (?, ?, ?, ?)
        """, (user_id, item['name'], item['price'], item['quantity']))

    cursor.execute("DELETE FROM orders WHERE user_id=?", (user_id,))
    db.commit()

    return "<h2>✅ Order Placed Successfully</h2><a href='/user_dashboard'>Go Home</a>"
#--------------payment Root-----------------
@app.route('/payment')
def payment_page():
    if 'user' not in session:
        return redirect('/user_login')

    order_number = str(uuid.uuid4())[:8]
    return render_template("payment.html", order_number=order_number)
#-----------------payment Success Root--------------------
@app.route('/payment_success/<order_number>')
def payment_success(order_number):
    if 'user' not in session:
        return redirect('/user_login')

    user_id = session['user']
    db = get_db()
    cursor = db.cursor()

    # Get cart items
    cursor.execute("""
        SELECT orders.product_id, orders.quantity, products.price
        FROM orders
        JOIN products ON orders.product_id = products.id
        WHERE orders.user_id=?
    """, (user_id,))

    items = cursor.fetchall()

    if not items:
        return "<h3>No items in cart</h3>"

    # Insert into order_history
    for item in items:
        cursor.execute("""
            INSERT INTO order_history
            (order_number, user_id, product_id, quantity, price, status, payment_status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            order_number,
            user_id,
            item['product_id'],
            item['quantity'],
            item['price'],
            'Completed',
            'Paid'
        ))

    # Clear cart
    cursor.execute("DELETE FROM orders WHERE user_id=?", (user_id,))
    db.commit()

    flash(f"✅ Payment Successful! Order ID: {order_number}")

    return redirect('/my_orders')
#-------------------My Orders------------------
@app.route('/my_orders')
def my_orders():
    if 'user' not in session:
        return redirect('/user_login')

    db = get_db()
    cursor = db.cursor()
    user_id = session['user']

    cursor.execute("""
        SELECT oh.order_number, p.name, p.image,
               oh.quantity, oh.price, oh.status,
               oh.payment_status, oh.created_at
        FROM order_history oh
        JOIN products p ON oh.product_id = p.id
        WHERE oh.user_id=?
        ORDER BY oh.created_at DESC
    """, (user_id,))

    orders = cursor.fetchall()

    return render_template("my_orders.html", orders=orders)

# ---------------- USER LOGOUT ----------------
@app.route("/logout")
def logout():
    session.pop("user", None)  # only remove user
    return redirect("/")

# ---------------- RUN ----------------
if __name__ == "__main__":
    app.run(debug=True)