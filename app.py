from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
import mysql.connector
from datetime import datetime
import mysql.connector.pooling

app = Flask(__name__)
app.secret_key = "your_secret_key"  # Needed for flash messages
db_config = {
    'host': 'database-1.c92qa40ewdh5.us-east-1.rds.amazonaws.com', 
    'user': 'admin',  # Your DB username
    'password': 'Jayaprakash123',  # Your DB password
    'database': 'fresh'  # Your DB name
}
# Connection pool setup
cnxpool = mysql.connector.pooling.MySQLConnectionPool(
    pool_name="mypool",pool_size=5,
    **db_config)

# Function to establish a database connection
def get_db_connection():
    try:
        return cnxpool.get_connection()
    except mysql.connector.Error as err:
        print(f"Error: {err}")
        return None
@app.route('/')
def home():
    return render_template('home.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        # Fetch form data
        name = request.form.get('name')
        mobile = request.form.get('mobile')
        email = request.form.get('email')
        password = request.form.get('password')
        default_address = request.form.get('default_address')

        # Check for required fields
        if not default_address:
            flash('Default address is required!', 'error')
            return redirect(url_for('register'))

        try:
            # Connect to the database
            conn = get_db_connection()
            cursor = conn.cursor()

            # Insert user data into the database
            cursor.execute(
                """
                INSERT INTO users (name, mobile, email, password, address)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (name, mobile, email, password, default_address)
            )

            # Commit and close the connection
            conn.commit()
            cursor.close()
            conn.close()

            # Success message
            flash("Thank you for registering!", 'success')
            return redirect(url_for('login'))

        except Exception as e:
            # Handle database errors
            flash(f"An error occurred: {str(e)}", 'error')
            return redirect(url_for('register'))

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute('SELECT * FROM users WHERE email = %s AND password = %s', (email, password))
        user = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        if user:
            session['user_id'] = user['id']
            session['user_name'] = user['name']
            flash('Login successful!')
            return redirect(url_for('shop'))
        else:
            flash('Invalid email or password!')
    
    return render_template('login.html')
@app.route('/shop')
def shop():
    return render_template('shop.html')

# Route to add an item to the cart

@app.route('/add_to_cart', methods=['POST'])
def add_to_cart():
    item_data = request.get_json()
    item_name = item_data['name']
    item_price = item_data['price']
    item_quantity = item_data['quantity']
    
    # Retrieve current cart items from session
    cart_items = session.get('cart_items', [])
    
    # Check if the item is already in the cart
    item_found = False
    for item in cart_items:
        if item['name'] == item_name:
            item['quantity'] += item_quantity
            item_found = True
            break
    
    # If the item is not found, add it to the cart
    if not item_found:
        cart_items.append({
            'name': item_name,
            'price': item_price,
            'quantity': item_quantity
        })
    
    # Update the session with the updated cart
    session['cart_items'] = cart_items
    session.modified = True
    return jsonify(success=True)

# Route to display the cart page
@app.route('/cart', methods=['GET', 'POST'])
def cart():
    # Fetch cart items from session
    cart_items = session.get('cart_items', [])
    
    # Calculate the total amount
    total_amount = sum(item['price'] * item['quantity'] for item in cart_items)
    
    return render_template('cart.html', cart_items=cart_items, total_amount=total_amount)

@app.route("/items", methods=['GET', 'POST'])
def items():
    if request.method == 'POST':
        # Handle adding items to the cart in session
        item_name = request.form.get('name')
        item_price = float(request.form.get('price'))
        item_quantity = int(request.form.get('quantity'))
        
        cart_items = session.get('cart_items', [])
        
        # Check if the item already exists in the cart
        for item in cart_items:
            if item['name'] == item_name:
                item['quantity'] += item_quantity
                break
        else:
            cart_items.append({
                'name': item_name,
                'price': item_price,
                'quantity': item_quantity
            })
        
        session['cart_items'] = cart_items
        flash(f"{item_name} added to your cart!")
        return redirect(url_for('items'))
    
    # Fetch items from the database for display
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute('SELECT item_id, item_name, price FROM items')
    items = cursor.fetchall()
    cursor.close()
    conn.close()
    
    cart_items = session.get('cart_items', [])
    return render_template('items.html', items=items, cart_items=cart_items)
@app.route('/place_order', methods=['POST'])
def place_order():
    if 'user_id' not in session:
        return jsonify(success=False, message="User not logged in")
    
    data = request.get_json()
    delivery_address = data.get('address', 'Default Address')
    payment_method = data['payment_method']
    items = data['items']
    total_price = data['total_price']
    
    # Insert order into the database with error handling
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Insert order into orders table
        cursor.execute(
            '''INSERT INTO orders 
            (user_id, delivery_address, payment_method, status, order_date, total_price) 
            VALUES (%s, %s, %s, %s, %s, %s)''',
            (session['user_id'], delivery_address, payment_method, 'Yet to Ship', datetime.now(), total_price)
        )
        order_id = cursor.lastrowid
        
        # Insert each item into order_items table
        for item in items:
            cursor.execute(
                '''INSERT INTO order_items 
                (order_id, item_name, quantity, price) 
                VALUES (%s, %s, %s, %s)''',
                (order_id, item['name'], item['quantity'], item['price'])
            )
        
        conn.commit()  # Commit the transaction after all queries are successful
        cursor.close()
        conn.close()
        return jsonify(success=True)
    
    except Exception as e:
        conn.rollback()  # Rollback the transaction in case of error
        return jsonify(success=False, message=str(e))
@app.route('/user_dashboard')
def user_dashboard():
    if 'user_id' not in session:
        flash('You need to log in to access your dashboard!')
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Fetch the orders and order items for the current user
    cursor.execute(
        '''
        SELECT 
            o.id, 
            o.total_price, 
            o.status, 
            o.order_date,
            GROUP_CONCAT(CONCAT(oi.item_name, ' (x', oi.item_quantity, ')')) AS items
        FROM orders o
        JOIN order_items oi ON o.id = oi.order_id
        WHERE o.user_id = %s
        GROUP BY o.id
        ''', 
        (session['user_id'],)
    )
    
    orders = cursor.fetchall()  # Fetch all orders for the user
    
    cursor.close()
    conn.close()
    
    return render_template('user_dashboard.html', orders=orders)
@app.route('/admin_dashboard', methods=['GET', 'POST'])
def admin_dashboard():
    if request.method == 'POST':
        order_id = request.form['order_id']
        status = request.form['status']
        
        # Update order status in the database
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                'UPDATE orders SET status = %s WHERE id = %s',
                (status, order_id)
            )
            conn.commit()
            flash('Order status updated successfully!', 'success')
        except Exception as e:
            conn.rollback()
            flash(f'Error updating order status: {e}', 'danger')
        finally:
            cursor.close()
            conn.close()
    
    # Fetch orders with user details and items concatenated as a string
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        '''
        SELECT 
            o.id, 
            o.total_price, 
            o.status, 
            o.order_date, 
            u.name AS user_name, 
            GROUP_CONCAT(CONCAT(oi.item_name, ' (x', oi.item_quantity, ')') SEPARATOR ', ') AS items
        FROM orders o
        JOIN users u ON o.user_id = u.id
        JOIN order_items oi ON o.id = oi.order_id
        GROUP BY o.id
        '''
    )
    orders = cursor.fetchall()
    cursor.close()
    conn.close()
    
    return render_template('admin_dashboard.html', orders=orders)

if __name__ == "__main__":
    app.run(debug=True)
