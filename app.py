import eventlet
eventlet.monkey_patch()  # <- MUST be first

from flask import Flask, render_template, request, redirect, session, flash, url_for, jsonify
import sqlite3
import os
import uuid
from werkzeug.security import generate_password_hash, check_password_hash
from flask_mail import Mail, Message
import random
from flask_socketio import SocketIO, emit
import requests

import os
from werkzeug.utils import secure_filename



app = Flask(__name__)
app.secret_key = os.urandom(24)
socketio = SocketIO(app)
DB_NAME = "database.db"
UPLOAD_FOLDER = "static/images"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

PROFILE_UPLOAD_FOLDER = "static/profile_pics"
os.makedirs(PROFILE_UPLOAD_FOLDER, exist_ok=True)

app.config['UPLOAD_FOLDER'] = PROFILE_UPLOAD_FOLDER

# FLASK MAIL CONFIG
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'erp@zoihospitals.com'
app.config['MAIL_PASSWORD'] = "twqowggcievrehbl"
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

    # USERS
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        email TEXT UNIQUE,latitude REAL,longitude REAL,address text,
        password TEXT,phoneno TEXT,profile_pic TEXT
    )
    """)

    # ADMIN
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS admin(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT
    )
    """)

    # PRODUCTS
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS products(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        price REAL,
        description TEXT,
        image TEXT,
        quantity INTEGER,category TEXT
    )
    """)
	# CART TABLE
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS cart(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        product_id INTEGER,
        product_name TEXT,
        price REAL,
        image TEXT,
        quantity INTEGER,
        status TEXT
    )
    """)

    # CART ORDERS
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS orders(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        product_id INTEGER,customer_lat REAL,customer_lng REAL,
        quantity INTEGER
    )
    """)

    # ORDER HISTORY
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS order_history(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_number TEXT,
        user_id INTEGER,
        product_id INTEGER,
        quantity INTEGER,
        price REAL,
        address_id INTEGER,
        customer_lat REAL,
        customer_lng REAL,
        customer_address TEXT,
        pickup_lat REAL,
        pickup_lng REAL,
        pickup_address TEXT,
        rider_id INTEGER,
        rider_status TEXT,
        status TEXT,
        delivery_otp TEXT,
        payment_status TEXT,
        is_otp_verified INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # RIDERS
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS riders(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        phone TEXT UNIQUE,
        vehicle TEXT,
        password TEXT,
        status TEXT DEFAULT 'Pending'
    )
    """)

    # RIDER LOCATION
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS rider_location(
        rider_id INTEGER,
        latitude REAL,
        longitude REAL,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # USER ADDRESSES
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS addresses(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        street TEXT,
        house_no TEXT,
        landmark TEXT,
        latitude REAL,
        longitude REAL,
        full_address TEXT
    )
    """)

    # DEFAULT ADMIN
    cursor.execute("SELECT * FROM admin WHERE username=?", ("admin",))
    if not cursor.fetchone():
        cursor.execute(
            "INSERT INTO admin(username,password) VALUES(?,?)",
            ("admin", generate_password_hash("admin123"))
        )

    db.commit()
    db.close()
create_tables()

# ----------------- ROUTES -----------------
@app.route("/")
def home():
    return render_template("home.html")
	
	
	
#-------------------------REGISTER FOR USER-------------------------------------- 


@app.route('/register', methods=['GET', 'POST'])
def user_register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = generate_password_hash(request.form['password'])

        try:
            conn = sqlite3.connect(DB_NAME)
            cursor = conn.cursor()

            cursor.execute('''
                INSERT INTO users (username, email, password)
                VALUES (?, ?, ?)
            ''', (username, email, password))

            conn.commit()
            conn.close()

            flash("User registered successfully!", "success")
            return redirect(url_for('user_register'))

        except Exception as e:
            flash(f"Error registering user: {e}", "error")
            return redirect(url_for('user_register'))

    return render_template('user_register.html')
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

    cursor.execute("SELECT SUM(price*quantity) FROM order_history WHERE payment_status='paid'")
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
						 

#-----------------Add Product---------------------
@app.route("/add_product", methods=["POST"])
def add_product():

    name = request.form["name"]
    price = request.form["price"]
    quantity = request.form["quantity"]
    description = request.form["description"]
    category = request.form["category"]

    image = request.files["image"]

    filename = secure_filename(str(uuid.uuid4()) + "_" + image.filename)
    image_path = "images/" + filename
    image.save("static/" + image_path)

    db = get_db()
    cursor = db.cursor()

    cursor.execute("""
        INSERT INTO products(name,price,quantity,description,image,category)
        VALUES(?,?,?,?,?,?)
    """, (name, price, quantity, description, image_path, category))

    db.commit()

    return redirect("/admin_dashboard")
	
#-------------------ADMIN ORDERS---------------------------------------
@app.route('/admin_orders')
def admin_orders():
    db = get_db()
    cursor = db.cursor()

    # Fetch orders with user and product info
    cursor.execute("""
        SELECT 
            o.id,
            o.order_number,
            o.quantity,
            o.price,
            o.status,
            o.payment_status,
            o.created_at,
            o.rider_id,
            u.username,
            p.name ,
            p.image,o.payment_status 
        FROM order_history o
        JOIN users u ON o.user_id = u.id
        JOIN products p ON o.product_id = p.id
        ORDER BY o.created_at DESC
    """)
    orders = cursor.fetchall()

    # Stats
    cursor.execute("SELECT COUNT(*) FROM order_history")
    total_orders = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM order_history WHERE status='Pending'")
    pending_orders = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM order_history WHERE status='Completed'")
    completed_orders = cursor.fetchone()[0]

    cursor.execute("SELECT SUM(price*quantity) FROM order_history WHERE payment_status='Paid'")
    revenue = cursor.fetchone()[0] or 0

    # Fetch riders for assignment dropdown
    cursor.execute("SELECT * FROM riders")
    riders = cursor.fetchall()

    db.close()

    filter_status = request.args.get('filter', 'All')

    return render_template('admin_orders.html', orders=orders, riders=riders,
                           total_orders=total_orders, pending_orders=pending_orders,
                           completed_orders=completed_orders, revenue=revenue,
                           filter_status=filter_status)
	
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
#Assign Order	
@app.route("/assign_rider", methods=["POST"])
def assign_rider():
    order_id = request.form.get("order_id")
    rider_id = request.form.get("rider_id")

    if order_id and rider_id:
        db = sqlite3.connect("database.db")
        cursor = db.cursor()

        cursor.execute("""
            UPDATE order_history
            SET rider_id = ?, rider_status = 'Assigned', status = 'Assigned'
            WHERE id = ?
        """, (rider_id, order_id))

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

    # CHECK LOGIN
    if "user" not in session:
        return redirect("/user_login")

    user_id = session["user"]

    search = request.args.get("search")
    category = request.args.get("category")

    db = get_db()
    cursor = db.cursor()

    # -----------------------------
    # PRODUCTS QUERY
    # -----------------------------
    query = "SELECT * FROM products WHERE 1=1"
    params = []

    # SEARCH FILTER
    if search:
        query += " AND (name LIKE ? OR description LIKE ?)"
        params.append('%' + search + '%')
        params.append('%' + search + '%')

    # CATEGORY FILTER
    if category:
        query += " AND LOWER(category)=LOWER(?)"
        params.append(category)

    cursor.execute(query, params)
    products = cursor.fetchall()

    # -----------------------------
    # ORDER COUNT
    # -----------------------------
    cursor.execute(
        "SELECT COUNT(*) FROM order_history WHERE user_id=?",
        (user_id,)
    )
    order_count = cursor.fetchone()[0]

    # -----------------------------
    # CART COUNT (FIXED)
    # -----------------------------
    cursor.execute("""
        SELECT COALESCE(SUM(quantity),0) AS cart_count
        FROM cart
        WHERE user_id=? AND status='Cart'
    """, (user_id,))

    cart_count = cursor.fetchone()["cart_count"]

    # -----------------------------
    # USER PROFILE
    # -----------------------------
    cursor.execute(
        "SELECT * FROM users WHERE id=?",
        (user_id,)
    )
    user = cursor.fetchone()

    db.close()

    return render_template(
        "user_dashboard.html",
        products=products,
        order_count=order_count,
        cart_count=cart_count,
        user=user
    )
	#--------------------user Profile---------------------	


def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

@app.route("/profile", methods=["GET"])
def profile():
    if "user" not in session:
        return redirect("/user_login")

    user_id = session["user"]

    conn = get_db_connection()
    user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()

    return render_template("profile.html", user=user)

@app.route("/update_profile", methods=["POST"])
def update_profile():
    if "user" not in session:
        return redirect("/user_login")

    user_id = session["user"]

    username = request.form.get("username")
    email = request.form.get("email")
    phoneno = request.form.get("phoneno")

    # Handle profile picture
    file = request.files.get("profile_pic")
    profile_pic = None
    if file and file.filename != "":
        filename = secure_filename(file.filename)
        profile_pic = f"profile_pics/{filename}"
        file.save(filepath)
        profile_pic = f"uploads/{filename}"

    conn = get_db_connection()
    if profile_pic:
        conn.execute("""
            UPDATE users 
            SET username = ?, email = ?, phoneno = ?, profile_pic = ? 
            WHERE id = ?
        """, (username, email, phoneno, profile_pic, user_id))
    else:
        conn.execute("""
            UPDATE users 
            SET username = ?, email = ?, phoneno = ? 
            WHERE id = ?
        """, (username, email, phoneno, user_id))
    conn.commit()
    conn.close()

    return redirect(url_for("profile"))
# ---------------- CART ROUTES ----------------
@app.route("/add_to_cart/<int:product_id>", methods=["POST"])
def add_to_cart(product_id):

    user_id = session["user"]
    qty = int(request.form.get("qty",1))

    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # get product
    cursor.execute("SELECT * FROM products WHERE id=?", (product_id,))
    product = cursor.fetchone()

    # check stock
    if product["quantity"] < qty:
        return jsonify({"success":False,"error":"Not enough stock"})

    # check existing cart item
    cursor.execute(
        "SELECT * FROM cart WHERE user_id=? AND product_id=?",
        (user_id, product_id)
    )
    item = cursor.fetchone()

    if item:
        # update quantity
        cursor.execute(
            "UPDATE cart SET quantity = quantity + ?, status='Cart' WHERE id=?",
            (qty, item["id"])
        )
    else:
        # insert new cart item
        cursor.execute("""
        INSERT INTO cart (user_id,product_id,product_name,price,quantity,image,status)
        VALUES (?,?,?,?,?,?,'Cart')
        """,(user_id,product_id,product["name"],product["price"],qty,product["image"]))

    # reduce stock
    cursor.execute(
        "UPDATE products SET quantity = quantity - ? WHERE id=?",
        (qty,product_id)
    )

    conn.commit()

    # cart count
    cursor.execute("SELECT COALESCE(SUM(quantity),0) FROM cart WHERE user_id=? AND status='Cart'", (user_id,))
    cart_count = cursor.fetchone()[0]

    conn.close()

    return jsonify({"success":True,"cart_count":cart_count})
#------------------CART--------------------------------
@app.route("/cart")
def view_cart():

    if "user" not in session:
        return redirect("/user_login")

    user_id = session["user"]

    db = get_db()
    cursor = db.cursor()

    cursor.execute("""
        SELECT 
            c.id,
            c.product_name as name,c.product_id,
            c.price,
            c.image,
            c.quantity
        FROM cart c join products p on p.id=c.product_id 
        WHERE user_id=? AND status='Cart'
    """, (user_id,))

    items = cursor.fetchall()

    total = 0
    for item in items:
        total += item["price"] * item["quantity"]

    db.close()

    return render_template(
        "cart.html",
        items=items,
        total=total
    )
#--------------------Update Quantity--------------------------
@app.route("/update_cart/<int:product_id>", methods=["POST"])
def update_cart(product_id):
    if "user" not in session:
        return redirect("/user_login")

    qty = int(request.form.get("qty", 1))
    user_id = session["user"]

    db = get_db()
    cursor = db.cursor()

    # Check if item exists in cart
    cursor.execute("SELECT id FROM cart WHERE user_id=? AND product_id=? AND status='Cart'", (user_id, product_id))
    existing = cursor.fetchone()

    if existing:
        # Update quantity
        cursor.execute("UPDATE cart SET quantity=? WHERE id=?", (qty, existing["id"]))
    else:
        # Insert new
        cursor.execute("INSERT INTO cart(user_id, product_id, product_name, price, image, quantity, status) VALUES (?,?,?,?,?,?,?)",
                       (user_id, product_id, "Product Name Placeholder", 0, "default.jpg", qty, "Cart"))  # Adjust product info as needed

    db.commit()
    db.close()
    return redirect("/cart")
#---------------------------remove item-------------------------
@app.route("/remove_item/<int:item_id>")
def remove_item(item_id):

    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Get cart item
    cursor.execute("SELECT * FROM cart WHERE id=?", (item_id,))
    item = cursor.fetchone()

    # Return stock
    cursor.execute(
        "UPDATE products SET quantity = quantity + ? WHERE id=?",
        (item["quantity"], item["product_id"])
    )

    # Delete from cart
    cursor.execute("DELETE FROM cart WHERE id=?", (item_id,))

    conn.commit()
    conn.close()

    return redirect("/cart")
# ---------------- CHECKOUT PAGE ----------------
@app.route("/checkout", methods=["GET", "POST"])
@app.route("/checkout/<int:address_id>", methods=["GET", "POST"])
def checkout_page(address_id=None):

    if "user" not in session:
        return redirect("/user_login")

    user_id = session["user"]

    db = get_db()
    cursor = db.cursor()

    # DEBUG
    print("SESSION USER:", user_id)

    cursor.execute("SELECT * FROM addresses")
    print("ALL ADDRESSES:", cursor.fetchall())

    # If user clicked Deliver Here
    if address_id:
        session["selected_address"] = address_id
        return redirect(url_for("payment"))

    if request.method == "POST":
        address_id = request.form.get("address_id")

        if not address_id:
            flash("Please select an address", "error")
            return redirect(url_for("checkout_page"))

        session["selected_address"] = address_id
        return redirect(url_for("payment"))

    # CART ITEMS
    cursor.execute("""
        SELECT orders.id as order_id, products.name, products.price, orders.quantity
        FROM orders
        JOIN products ON orders.product_id = products.id
        WHERE orders.user_id=?
    """, (user_id,))
    
    items = cursor.fetchall()

    total = sum(item["price"] * item["quantity"] for item in items)

    cursor.execute("SELECT * FROM addresses WHERE user_id=?", (user_id,))
    saved_addresses = cursor.fetchall()

    print("FILTERED ADDRESSES:", saved_addresses)

    db.close()

    return render_template(
        "addresses.html",
        items=items,
        total=total,
        saved_addresses=saved_addresses
    )


# ---------------- SAVE ADDRESS ----------------
@app.route("/save_address", methods=["POST"])
def save_address():
    if "user" not in session:
        return redirect("/user_login")

    user_id = session["user"]
    street = request.form["street"]
    house_no = request.form["house_no"]
    landmark = request.form["landmark"]
    latitude = request.form["latitude"]
    longitude = request.form["longitude"]
    full_address = request.form["full_address"]

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO addresses (user_id, street, house_no, landmark, latitude, longitude, full_address)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (user_id, street, house_no, landmark, latitude, longitude, full_address))
    conn.commit()
    conn.close()

    return redirect("/addresses")


# ---------------- SHOW ADDRESSES ----------------
@app.route("/addresses")
def addresses():
    if "user" not in session:
        return redirect("/user_login")

    user_id = session["user"]

    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM addresses WHERE user_id=?", (user_id,))
    saved_addresses = cursor.fetchall()
    conn.close()

    return render_template("addresses.html", saved_addresses=saved_addresses)
#----------------------Edit Address-----------------------------
@app.route('/edit_address/<int:address_id>', methods=['GET', 'POST'])
def edit_address(address_id):
    if "user" not in session:
        return redirect("/user_login")

    user_id = session["user"]
    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Fetch address
    cursor.execute("SELECT * FROM addresses WHERE id=? AND user_id=?", (address_id, user_id))
    address = cursor.fetchone()

    if not address:
        conn.close()
        return "Address not found or you don't have permission."

    if request.method == "POST":
        street = request.form["street"]
        house_no = request.form["house_no"]
        landmark = request.form["landmark"]
        latitude = request.form["latitude"]
        longitude = request.form["longitude"]
        full_address = request.form["full_address"]

        cursor.execute("""
            UPDATE addresses
            SET street=?, house_no=?, landmark=?, latitude=?, longitude=?, full_address=?
            WHERE id=? AND user_id=?
        """, (street, house_no, landmark, latitude, longitude, full_address, address_id, user_id))
        conn.commit()
        conn.close()
        return redirect("/addresses")

    conn.close()
    return render_template("edit_address.html", address=address)
#------------------------Delete Address----------------------
@app.route('/delete_address/<int:address_id>')
def delete_address(address_id):
    if "user" not in session:
        return redirect("/user_login")

    user_id = session["user"]

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM addresses WHERE id=? AND user_id=?", (address_id, user_id))
    conn.commit()
    conn.close()

    return redirect("/addresses")
# ---------------- GENERATE ORDER NUMBER ----------------
def generate_order_number():
    return uuid.uuid4().hex[:8].upper()


# ---------------- GENERATE DELIVERY OTP ----------------
def generate_delivery_otp():
    return str(random.randint(100000, 999999))


# ---------------- PAYMENT ROUTE ----------------
@app.route("/payment", methods=["GET", "POST"])
def payment():

    if "user" not in session:
        return redirect("/user_login")

    user_id = session["user"]

    address_id = session.get("selected_address")
    if not address_id:
        flash("Please select an address first", "error")
        return redirect("/addresses")

    db = get_db()
    cursor = db.cursor()

    # GET CART ITEMS
    cursor.execute("""
        SELECT cart.id as order_id,
               products.id as product_id,
               products.name,
               products.price,
               cart.quantity
        FROM cart 
        JOIN products ON cart.product_id = products.id
        WHERE cart.user_id=?
    """, (user_id,))

    items = cursor.fetchall()

    total = sum(item["price"] * item["quantity"] for item in items)

    if not items:
        flash("Your cart is empty", "error")
        return redirect("/user_dashboard")

    # ---------------- GET REQUEST ----------------
    if request.method == "GET":

        order_number = generate_order_number()
        delivery_otp = generate_delivery_otp()

        session["temp_order_number"] = order_number
        session["temp_delivery_otp"] = delivery_otp

        cursor.execute("SELECT email, username FROM users WHERE id=?", (user_id,))
        user = cursor.fetchone()

        if user and user["email"]:
            try:
                with app.app_context():

                    msg = Message(
                        subject="Your Delivery OTP - Ravi Mart",
                        recipients=[user["email"]]
                    )

                    msg.body = f"""
Hello {user['username']}

Your Delivery OTP : {delivery_otp}

Order Number : {order_number}

Thank you for shopping with Ravi Mart
"""

                    mail.send(msg)

                    flash("Delivery OTP sent to your email", "success")

            except Exception as e:
                print("Email error:", e)

        return render_template(
            "payment.html",
            items=items,
            total=total,
            order_number=order_number,
            delivery_otp=delivery_otp
        )

    # ---------------- POST REQUEST ----------------

    order_number = session.get("temp_order_number")
    delivery_otp = session.get("temp_delivery_otp")

    if not order_number:
        flash("Order error", "error")
        return redirect("/cart")

    # GET ADDRESS LOCATION
    cursor.execute("""
    SELECT latitude, longitude, full_address
    FROM addresses
    WHERE id=? AND user_id=?
    """, (address_id, user_id))

    addr = cursor.fetchone()

    customer_lat = addr["latitude"]
    customer_lng = addr["longitude"]
    customer_address = addr["full_address"]

    # STORE PICKUP LOCATION
    pickup_lat = 17.440894
    pickup_lng = 78.444348
    pickup_address = "Ravi Mart Store"

    # INSERT ORDER
    for item in items:

        cursor.execute("""
        INSERT INTO order_history
        (order_number, user_id, product_id, quantity, price, address_id,
        customer_lat, customer_lng, customer_address,
        pickup_lat, pickup_lng, pickup_address,
        status, delivery_otp, payment_status)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            order_number,
            user_id,
            item["product_id"],
            item["quantity"],
            item["price"],
            address_id,
            customer_lat,
            customer_lng,
            customer_address,
            pickup_lat,
            pickup_lng,
            pickup_address,
            "Pending",
            delivery_otp,
            "paid"
        ))

    # CLEAR CART
    cursor.execute("DELETE FROM cart WHERE user_id=?", (user_id,))

    db.commit()
    db.close()

    session.pop("temp_order_number")
    session.pop("temp_delivery_otp")

    return redirect(url_for("payment_success", order_number=order_number))


# ---------------- PAYMENT SUCCESS ----------------
@app.route("/payment_success/")
@app.route("/payment_success/<order_number>")
def payment_success(order_number=None):

    if "user" not in session:
        return redirect("/user_login")

    if not order_number:
        return redirect("/user_dashboard")

    user_id = session["user"]
    address_id = session.get("selected_address")

    db = get_db()
    cursor = db.cursor()

    # ✅ Clear cart (mark items ordered)
    cursor.execute("DELETE FROM cart WHERE user_id=?", (user_id,))

    db.commit()

    # ✅ Fetch order details
    cursor.execute("""
        SELECT oh.*, p.name, p.image
        FROM order_history oh
        JOIN products p ON oh.product_id = p.id
        WHERE oh.order_number=?
    """, (order_number,))

    order_details = cursor.fetchall()

    db.close()

    # Clear session address
    session.pop("selected_address", None)

    if not order_details:
        return redirect("/user_dashboard")

    return render_template(
        "payment_success.html",
        order_number=order_number,
        order=order_details
    )

# ---------------- MY ORDERS ----------------

	
@app.route("/my_orders")
def my_orders():
    if "user" not in session:
        return redirect("/user_login")
    user_id = session["user"]
    db = get_db()
    cursor = db.cursor()

    # Fetch order info including pickup/customer coordinates
    cursor.execute("""
        SELECT oh.id, oh.order_number, p.name, p.image, oh.quantity, oh.price, 
               oh.status, oh.payment_status, oh.created_at,
               oh.pickup_lat, oh.pickup_lng, oh.customer_lat, oh.customer_lng,
               oh.pickup_address, oh.customer_address
        FROM order_history oh
        JOIN products p ON oh.product_id = p.id
        WHERE oh.user_id = ?
        ORDER BY oh.created_at DESC
    """, (user_id,))
    orders = cursor.fetchall()
    db.close()

    return render_template("my_orders.html", orders=orders)

# API route for JS map to fetch orders as JSON
@app.route("/get_customer_orders")
def get_customer_orders():
    if "user" not in session:
        return jsonify([])  # empty for not logged in
    user_id = session["user"]
    db = get_db()
    cursor = db.cursor()
    cursor.execute("""
        SELECT oh.id, oh.order_number, p.name, p.image, oh.quantity, oh.price, 
               oh.status, oh.payment_status, oh.created_at,
               oh.pickup_lat, oh.pickup_lng, oh.customer_lat, oh.customer_lng,
               oh.pickup_address, oh.customer_address
        FROM order_history oh
        JOIN products p ON oh.product_id = p.id
        WHERE oh.user_id = ?
        ORDER BY oh.created_at DESC
    """, (user_id,))
    orders = [dict(row) for row in cursor.fetchall()]
    db.close()
    return jsonify(orders)
# ---------------- TRACK ORDER ----------------
@app.route("/track_order/<int:order_id>")
def track_order(order_id):
    if "user" not in session: return redirect("/user_login")

    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM order_history WHERE id=?", (order_id,))
    order = cursor.fetchone()
    conn.close()
    if not order: return "Order not found", 404

    order = dict(order)
    return render_template("track_order.html", order=order)
#--------RIDER REGISTRATION--------------------
@app.route("/rider_register", methods=["GET","POST"])
def rider_register():

    if request.method == "POST":

        name = request.form["name"]
        phone = request.form["phone"]
        vehicle = request.form["vehicle"]
        password = request.form["password"]

        hashed_password = generate_password_hash(password)

        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()

        cursor.execute("""
        INSERT INTO riders (name, phone, vehicle, password)
        VALUES (?, ?, ?, ?)
        """, (name, phone, vehicle, hashed_password))

        conn.commit()
        conn.close()

        return redirect("/rider_login")

    return render_template("rider_register.html")
#-----------------------RIDER LOGIN-----------------------------------
from werkzeug.security import check_password_hash

@app.route("/rider_login", methods=["GET","POST"])
def rider_login():

    if request.method == "POST":

        phone = request.form["phone"]
        password = request.form["password"]

        conn = sqlite3.connect("database.db")
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM riders WHERE phone=? AND status='Approved'", (phone,))
        rider = cursor.fetchone()

        if rider and check_password_hash(rider["password"], password):
            session["rider"] = rider["id"]
            return redirect("/rider_dashboard")
        else:
            return "Invalid phone or password"

    return render_template("rider_login.html")
#-----------------ADMIN  RIDER-------------------------
@app.route("/admin_riders")
def admin_riders():

    db = sqlite3.connect("database.db")
    db.row_factory = sqlite3.Row
    cursor = db.cursor()

    cursor.execute("SELECT * FROM riders")
    riders = cursor.fetchall()

    db.close()

    return render_template("admin_riders.html", riders=riders)
#---------------------RIDER APPROVE-----------------------
@app.route("/approve_rider/<int:id>")
def approve_rider(id):

    db = sqlite3.connect("database.db")
    cursor = db.cursor()

    cursor.execute("UPDATE riders SET status='Approved' WHERE id=?", (id,))
    db.commit()

    db.close()

    return redirect("/admin_riders")
	
	
def fetchall_as_dict(cursor):
    return [dict(row) for row in cursor.fetchall()]
#----------------------------RIDER DASHBOARD-----------------------------------------	

@app.route('/rider_dashboard')
def rider_dashboard():

    if "rider" not in session:
        return redirect("/rider_login")

    rider_id = session["rider"]

    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT oh.*, 
               p.name AS product_name,
               u.username AS customer_name,
               u.address AS customer_address,
               u.latitude AS customer_lat,
               u.longitude AS customer_lng
        FROM order_history oh
        LEFT JOIN products p ON oh.product_id = p.id
        JOIN users u ON u.id = oh.user_id
        WHERE (oh.rider_id = ? OR oh.rider_id IS NULL)
        AND oh.rider_status IN ('Assigned','Accepted','Picked')
        ORDER BY oh.id DESC
    """,(rider_id,))

    orders = [dict(row) for row in cursor.fetchall()]
    conn.close()

    for o in orders:
        o['customer_lat'] = float(o['customer_lat']) if o['customer_lat'] else None
        o['customer_lng'] = float(o['customer_lng']) if o['customer_lng'] else None
        o['pickup_lat'] = float(o['pickup_lat']) if o['pickup_lat'] else None
        o['pickup_lng'] = float(o['pickup_lng']) if o['pickup_lng'] else None

    return render_template("rider_dashboard.html", orders=orders)
#--------------ACCEPT ORDER-------------------------
# Accept order
@app.route('/accept_order/<int:order_id>')
def accept_order(order_id):
    if "rider" not in session:
        return redirect("/rider_login")
    rider_id = session["rider"]
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE order_history
        SET rider_status='Accepted', rider_id=?
        WHERE id=?
    """, (rider_id, order_id))
    conn.commit()
    conn.close()
    return redirect("/rider_dashboard")


# Pickup order
@app.route('/pickup_order/<int:order_id>')
def pickup_order(order_id):
    if "rider" not in session:
        return redirect("/rider_login")

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE order_history
        SET rider_status='Picked'
        WHERE id=?
    """, (order_id,))

    conn.commit()
    conn.close()

    return redirect("/rider_dashboard")


	
	
	
#---------------UPFDATE RIDER LOCATION--------------------
@app.route("/update_rider_location", methods=["POST"])
def update_rider_location():

    if "rider" not in session:
        return {"status": "error"}

    rider_id = session["rider"]
    lat = request.json.get("lat")
    lng = request.json.get("lng")

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    # check if rider exists
    cursor.execute("SELECT rider_id FROM rider_location WHERE rider_id=?", (rider_id,))
    existing = cursor.fetchone()

    if existing:
        cursor.execute("""
            UPDATE rider_location
            SET latitude=?, longitude=?, updated_at=CURRENT_TIMESTAMP
            WHERE rider_id=?
        """, (lat, lng, rider_id))
    else:
        cursor.execute("""
            INSERT INTO rider_location (rider_id, latitude, longitude)
            VALUES (?, ?, ?)
        """, (rider_id, lat, lng))

    conn.commit()
    conn.close()

    return {"status": "success"}
#----------- GET RIDER LOCATION-----------------------------
@app.route("/get_rider_locations")
def get_rider_locations():
    try:
        conn = sqlite3.connect("database.db")
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT rider_id as id, latitude as lat, longitude as lng FROM rider_location")
        rows = cursor.fetchall()
        data = [{"id": r["id"], "lat": r["lat"], "lng": r["lng"]} for r in rows]
        conn.close()
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
#------------------RIDER MAP--------------------------
@app.route("/admin_rider_map")
def admin_rider_map():
    return render_template("admin_rider_map.html")
#RIDER TRACKING
@app.route("/rider_tracking")
def rider_tracking():

    if "rider" not in session:
        return redirect("/rider_login")

    return render_template("rider_tracking.html")
	
#----------------DELIVERY ROUTE--------------------------
@app.route("/get_delivery_route/<int:order_id>")
def get_delivery_route(order_id):
    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Get order info including assigned rider
    cursor.execute("""
        SELECT o.customer_lat, o.customer_lng, o.rider_id AS assigned_rider
        FROM order_history o
        WHERE o.id=?
    """, (order_id,))
    order = cursor.fetchone()
    if not order:
        conn.close()
        return jsonify({"error":"Order not found"}), 404
    order = dict(order)

    # Get all riders with their live location
    cursor.execute("""
        SELECT r.id, r.name, l.latitude, l.longitude
        FROM riders r
        LEFT JOIN rider_location l ON r.id = l.rider_id
        WHERE r.status='Approved'
    """)
    riders = [dict(r) for r in cursor.fetchall()]
    conn.close()

    return jsonify({
        "customer_lat": order["customer_lat"],
        "customer_lng": order["customer_lng"],
        "assigned_rider": order["assigned_rider"],
        "riders": riders
    })	

# ------------------Verify OTP / Delivery-------------------------------------
@app.route('/verify_delivery/<int:order_id>', methods=['GET','POST'])
def verify_delivery(order_id):
    if "rider" not in session:
        return redirect("/rider_login")
    
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    
    if request.method == 'POST':
        otp_entered = request.form.get('otp')
        cursor.execute("SELECT delivery_otp FROM order_history WHERE id=?", (order_id,))
        otp_actual = cursor.fetchone()[0]
        
        if otp_entered == otp_actual:
            # Update rider_status and mark OTP verified
            cursor.execute("""
                UPDATE order_history
                SET rider_status='Delivered',
                    status='Delivered',
                    is_otp_verified=1
                WHERE id=?
            """, (order_id,))
            conn.commit()
            conn.close()
            flash("Order delivered successfully!", "success")
            return redirect("/rider_dashboard")
        else:
            flash("Invalid OTP", "danger")
    
    else:
        cursor.execute("SELECT delivery_otp FROM order_history WHERE id=?", (order_id,))
        otp = cursor.fetchone()[0]
    
    conn.close()
    return render_template('verify_otp.html', order_id=order_id)
	
@app.route("/get_order_rider/<int:order_id>")
def get_order_rider(order_id):

    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
    SELECT 
        oh.pickup_lat,
        oh.pickup_lng,
        oh.customer_lat,
        oh.customer_lng,
        rl.latitude,
        rl.longitude
    FROM order_history oh
    LEFT JOIN rider_location rl 
        ON rl.rider_id = oh.rider_id
    WHERE oh.id = ?
    """,(order_id,))

    row = cursor.fetchone()
    conn.close()

    if row:
        return jsonify({
            "store_lat": row["pickup_lat"],
            "store_lng": row["pickup_lng"],
            "cust_lat": row["customer_lat"],
            "cust_lng": row["customer_lng"],
            "rider_lat": row["latitude"],
            "rider_lng": row["longitude"]
        })

    return jsonify({})
	

# ---------------- LOGOUT ----------------
@app.route("/logout")
def logout():
    session.pop("user", None)
    flash("User logged out successfully", "success")
    return redirect("/")



@socketio.on('message')
def handle_message(msg):
    print('Message received:', msg)
    emit('response', f'Server received: {msg}')

if __name__ == '__main__':
    socketio.run(app, host="0.0.0.0", port=5000, debug=True)
#if __name__ == '__main__':
#    socketio.run(app, debug=True)
