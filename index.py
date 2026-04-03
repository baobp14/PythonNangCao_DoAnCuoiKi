from flask import Flask, request, render_template, redirect, url_for, session, jsonify, flash
from flask_bcrypt import Bcrypt
import mysql.connector
import json
from payos import PayOS, WebhookError
from payos.types import CreatePaymentLinkRequest
from pyngrok import ngrok
from datetime import timedelta
db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': '14072005',
    'database': 'banhang_db'
}
def calculate_total_from_items(conn, cart_items_list):
    total_price = 0
    if not cart_items_list:
        return 0
            
    cursor = None
    try:
        cursor = conn.cursor(dictionary=True) 
        for item in cart_items_list:
            product_id = item['id']
            quantity = int(item['quantity']) 
            
            sql_product = "SELECT price FROM product WHERE id = %s"
            cursor.execute(sql_product, (product_id,))
            product_data = cursor.fetchone()
            
            if product_data and quantity > 0:
                total_price += product_data['price'] * quantity
        
        cursor.close()
        return total_price
            
    except Exception as e:
        print(f"Lỗi calculate_total_from_items: {e}")
        if cursor: cursor.close()
        return 0
def get_db_connection():
    try:
        conn = mysql.connector.connect(**db_config)
        return conn
    except Exception as e:
        print(f"Lỗi kết nối database: {e}")
        return None

app = Flask(__name__)
app.secret_key = 'super_secret_key_for_cart_session_14072005'
bcrypt = Bcrypt(app)

PAYOS_CLIENT_ID = "56333fc8-ad77-47fc-b3ec-c3152846e246"
PAYOS_API_KEY = "6db90c0c-7cb1-4981-aa5a-cf09824b3b47"
PAYOS_CHECKSUM_KEY = "30296ef88f65a6eab145e97c71464de448aec92f5fe59b38ff0bf27be12d9129"

payos = PayOS(client_id=PAYOS_CLIENT_ID, api_key=PAYOS_API_KEY, checksum_key=PAYOS_CHECKSUM_KEY)

@app.route('/')
def home_page():
    conn = get_db_connection()
    products = []
    user_info = None

    category_filter = request.args.get('category')
    search_query = request.args.get('q')

    if conn is None:
        return render_template('index.html', products=products, user=user_info, search_query=search_query)

    user_cursor = None 
    cursor = None    

    try:
        if 'user_id' in session:
            user_cursor = conn.cursor(dictionary=True)
            user_sql = "SELECT full_name, user_role, phone_number FROM user WHERE id = %s"
            user_cursor.execute(user_sql, (session['user_id'],))
            user_info = user_cursor.fetchone()

        cursor = conn.cursor()

        sql_params = []
        product_sql = """SELECT id, base_name, color, storage, price, stock_quantity, 
                               description, main_image_url
                           FROM product"""

        where_clauses = []

        if category_filter:
            where_clauses.append("category_name = %s")
            sql_params.append(category_filter)

        if search_query:
            where_clauses.append("(base_name LIKE %s OR description LIKE %s OR brand_name LIKE %s)")
            search_term = f"%{search_query}%"
            sql_params.extend([search_term, search_term, search_term])

        if where_clauses:
            product_sql += " WHERE " + " AND ".join(where_clauses)

        product_sql += " ORDER BY id DESC"

        cursor.execute(product_sql, sql_params)
        products = cursor.fetchall()

    except Exception as e:
        print(f"Lỗi khi truy vấn: {e}")

    finally:
        if user_cursor: user_cursor.close()
        if cursor: cursor.close()
        if conn: conn.close()

    return render_template('index.html', products=products, user=user_info, search_query=search_query)


@app.route('/register', methods=['GET', 'POST'])
def register_page():
    
    if request.method == 'GET':
        return render_template('login_register.html', error=None, active_tab='register')

    if request.method == 'POST':
        conn = None
        cursor = None
        try:
            data = request.get_json()
            if not data:
                return jsonify({"success": False, "message": "Không có dữ liệu"}), 400

            full_name = data.get('name')
            phone_number = data.get('phone')
            password = data.get('password')

            if not phone_number or not password:
                return jsonify({"success": False, "message": "Thiếu SĐT hoặc Mật khẩu"}), 400

            conn = get_db_connection()
            if conn is None:
                return jsonify({"success": False, "message": "Lỗi kết nối DB"}), 500

            cursor = conn.cursor()
            hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
            sql_user = "INSERT INTO user (phone_number, password_hash, full_name) VALUES (%s, %s, %s)"
            cursor.execute(sql_user, (phone_number, hashed_password, full_name))
            user_id = cursor.lastrowid

            sql_cart = "INSERT INTO cart (user_id, cart_content) VALUES (%s, %s)"
            cursor.execute(sql_cart, (user_id, '[]'))

            conn.commit()
            
            return jsonify({"success": True, "message": "Đăng ký thành công!"})

        except mysql.connector.Error as err:
            if conn: conn.rollback()
            if err.errno == 1062:
                return jsonify({"success": False, "message": "Số điện thoại này đã được đăng ký!"}), 400
            else:
                return jsonify({"success": False, "message": f"Lỗi DB: {err}"}), 500
        
        except Exception as e:
            if conn: conn.rollback()
            return jsonify({"success": False, "message": f"Lỗi server: {e}"}), 500

        finally:
            if cursor: cursor.close()
            if conn: conn.close()

@app.route('/forgot-password', methods=['GET'])
def forgot_password_page():
    return render_template('forgot_password.html')

@app.route('/reset-password', methods=['POST'])
def reset_password():
    conn = None
    cursor = None
    try:
        data = request.get_json()
        phone_number = data.get('phone')
        new_password = data.get('password')

        if not phone_number or not new_password:
            return jsonify({"success": False, "message": "Thiếu thông tin."}), 400

        hashed_password = bcrypt.generate_password_hash(new_password).decode('utf-8')
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        sql_update = "UPDATE user SET password_hash = %s WHERE phone_number = %s"
        cursor.execute(sql_update, (hashed_password, phone_number))
        
        if cursor.rowcount == 0:
            return jsonify({"success": False, "message": "Số điện thoại này không tồn tại."}), 404
            
        conn.commit()
        return jsonify({"success": True, "message": "Mật khẩu đã được cập nhật!"})
        
    except Exception as e:
        if conn: conn.rollback()
        print(f"Lỗi reset password: {e}")
        return jsonify({"success": False, "message": f"Lỗi server: {e}"}), 500
    finally:
        if cursor: cursor.close()
        if conn: conn.close()
@app.route('/login', methods=['GET', 'POST'])
def login_page():
    error_message = None

    if request.method == 'POST':
        phone_number = request.form.get('phone')
        password = request.form.get('password')

        if not phone_number or not password:
            error_message = "Vui lòng nhập đầy đủ Số điện thoại và Mật khẩu."
            return render_template('login_register.html', error=error_message, active_tab='login')

        conn = get_db_connection()
        if conn is None:
            error_message = "Lỗi kết nối database."
            return render_template('login_register.html', error=error_message, active_tab='login'), 500

        cursor = conn.cursor(dictionary=True)
        try:
            sql = "SELECT id, password_hash FROM user WHERE phone_number = %s"
            cursor.execute(sql, (phone_number,))
            user = cursor.fetchone()

            if user and bcrypt.check_password_hash(user['password_hash'], password):
                session['user_id'] = user['id']
                return redirect(url_for('home_page'))
            else:
                error_message = "Số điện thoại hoặc Mật khẩu không đúng. Vui lòng thử lại."
        except Exception as e:
            error_message = f"Có lỗi nghiêm trọng xảy ra: {e}"
        finally:
            cursor.close()
            conn.close()
            
        return render_template('login_register.html', error=error_message, active_tab='login')

    return render_template('login_register.html', error=error_message, active_tab='login')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('home_page'))


@app.route('/dashboard')
def admin_page():
    conn = None
    cursor = None 
    all_users = []
    all_orders = [] 

    try:
        if 'user_id' not in session:
            flash('Vui lòng đăng nhập để truy cập.', 'error')
            return redirect(url_for('login_page'))

        current_user_id = session['user_id']
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        sql = "SELECT user_role FROM user WHERE id = %s"
        cursor.execute(sql, (current_user_id,))
        user = cursor.fetchone()

        if user and user['user_role'] == 'admin':
            all_users_sql = "SELECT id, full_name, phone_number, user_role FROM user ORDER BY id"
            cursor.execute(all_users_sql)
            all_users = cursor.fetchall()
            
            all_orders_sql = """
                SELECT o.id, o.created_at, o.amount, o.status, o.fulfillment_status, o.shipping_address, u.full_name 
                FROM orders o
                JOIN user u ON o.user_id = u.id
                WHERE o.status = 'success' OR o.status = 'cod'
                ORDER BY o.created_at DESC
            """
            cursor.execute(all_orders_sql)
            all_orders = cursor.fetchall()
            
            return render_template('dashboard.html', 
                                   all_users=all_users, 
                                   all_orders=all_orders, 
                                   current_admin_id=current_user_id)
        else:
            flash('Bạn không có quyền truy cập trang quản trị!', 'error')
            return redirect(url_for('home_page'))

    except Exception as e:
        print(f"Lỗi kiểm tra admin: {e}")
        return redirect(url_for('home_page'))

    finally:
        if cursor: cursor.close()
        if conn: conn.close()
@app.route('/compare')
def compare_page():
    user_info = None
    all_products_list = [] 
    conn = None
    cursor = None
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        if 'user_id' in session:
            user_sql = "SELECT full_name, user_role, phone_number FROM user WHERE id = %s"
            cursor.execute(user_sql, (session['user_id'],))
            user_info = cursor.fetchone()
            
        products_sql = "SELECT id, base_name, storage FROM product ORDER BY base_name"
        cursor.execute(products_sql)
        all_products_list = cursor.fetchall()
        

    except Exception as e:
        print(f"Lỗi tải /compare: {e}")
        all_products_list = [] 
    finally:
        if cursor: cursor.close()
        if conn: conn.close()
        
    return render_template('compare.html', user=user_info, all_products_list=all_products_list)
@app.route('/get-product-spec/<int:product_id>')
def get_product_spec(product_id):
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        sql = """
            SELECT id, base_name, main_image_url, price, specs, storage 
            FROM product 
            WHERE id = %s
        """
        cursor.execute(sql, (product_id,))
        product = cursor.fetchone()
        
        if not product:
            return jsonify({"success": False, "message": "Không tìm thấy SP"}), 404

        if product['specs']:
            try:
                product['specs'] = json.loads(product['specs'])
            except json.JSONDecodeError:
                product['specs'] = {"Lỗi": "Không thể đọc specs"}
        else:
            product['specs'] = {}
        
        if 'Dung lượng' not in product['specs']:
             product['specs']['Dung lượng'] = product.get('storage', 'N/A')

        return jsonify({"success": True, "product": product})

    except Exception as e:
        print(f"Lỗi /get-product-spec: {e}")
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        if cursor: cursor.close()
        if conn: conn.close()
@app.route('/update-order-status', methods=['POST'])
def update_order_status():
    
    if 'user_id' not in session:
        return jsonify({"success": False, "message": "Chưa đăng nhập"}), 401
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        sql_admin_check = "SELECT user_role FROM user WHERE id = %s"
        cursor.execute(sql_admin_check, (session['user_id'],))
        admin_user = cursor.fetchone()

        if not (admin_user and admin_user['user_role'] == 'admin'):
            return jsonify({"success": False, "message": "Không có quyền truy cập"}), 403

        data = request.get_json()
        order_id = data.get('order_id')
        new_status = data.get('new_status')
        
        sql_update = "UPDATE orders SET fulfillment_status = %s WHERE id = %s"
        
        write_cursor = conn.cursor()
        write_cursor.execute(sql_update, (new_status, order_id))
        conn.commit()
        write_cursor.close()

        return jsonify({"success": True, "message": "Cập nhật trạng thái thành công"})
    
    except Exception as e:
        if conn: conn.rollback()
        print(f"Lỗi khi cập nhật status: {e}")
        return jsonify({"success": False, "message": str(e)}), 500
    
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

@app.route('/update-role', methods=['POST'])
def update_role():

    if 'user_id' not in session:
        return jsonify({"success": False, "message": "Chưa đăng nhập"}), 401

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        sql_admin_check = "SELECT user_role FROM user WHERE id = %s"
        cursor.execute(sql_admin_check, (session['user_id'],))
        admin_user = cursor.fetchone()

        if not (admin_user and admin_user['user_role'] == 'admin'):
            return jsonify({"success": False, "message": "Không có quyền truy cập"}), 403

        data = request.get_json()
        user_id_to_update = data.get('user_id')
        new_role = data.get('new_role')

        if not user_id_to_update or new_role not in ['admin', 'user']:
            return jsonify({"success": False, "message": "Dữ liệu không hợp lệ"}), 400

        sql_update = "UPDATE user SET user_role = %s WHERE id = %s"
        cursor.execute(sql_update, (new_role, user_id_to_update))
        conn.commit()

        return jsonify({"success": True, "message": "Cập nhật vai trò thành công"})

    except Exception as e:
        if conn: conn.rollback()
        print(f"Lỗi khi cập nhật vai trò: {e}")
        return jsonify({"success": False, "message": "Lỗi server"}), 500

    finally:
        if cursor: cursor.close()
        if conn: conn.close()

@app.route('/add', methods=['POST'])
def add_product():
    conn = None
    cursor = None
    try:
        base_name = request.form.get('base_name')
        color = request.form.get('color')
        storage = request.form.get('storage')
        price = request.form.get('price')
        stock_quantity = request.form.get('stock_quantity')
        description = request.form.get('description')
        main_image_url = request.form.get('main_image_url')
        category_name = request.form.get('category_name')
        brand_name = request.form.get('brand_name')
        specs_json_string = request.form.get('specs')

        conn = get_db_connection()
        if conn is None:
            return "Lỗi kết nối database.", 500

        cursor = conn.cursor()

        sql_query = """
        INSERT INTO product 
        (base_name, color, storage, price, stock_quantity, 
         description, main_image_url, category_name, brand_name, specs)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """

        values = (
            base_name, color, storage, price, stock_quantity,
            description, main_image_url, category_name, brand_name, specs_json_string
        )

        cursor.execute(sql_query, values)

        conn.commit()

        print("ĐÃ THÊM SẢN PHẨM THÀNH CÔNG VÀO DB!")

        return redirect(url_for('home_page'))

    except Exception as e:
        if conn:
            conn.rollback()
        print(f"Lỗi khi thêm vào DB: {e}")
        return f"Đã xảy ra lỗi khi thêm sản phẩm: {e}", 500

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@app.route('/product/<int:product_id>')
def product_detail(product_id):
    conn = get_db_connection()
    product = None
    user_info = None
    reviews_list = [] 
    cursor = None 

    if conn is None:
        return "Lỗi kết nối database.", 500

    try:
        cursor = conn.cursor(dictionary=True)

        if 'user_id' in session:
            user_sql = "SELECT full_name, user_role, phone_number FROM user WHERE id = %s"
            cursor.execute(user_sql, (session['user_id'],))
            user_info = cursor.fetchone()

        sql_product = """SELECT id, base_name, color, storage, price, stock_quantity, 
                                description, main_image_url, category_name, brand_name, specs 
                         FROM product WHERE id = %s"""
        cursor.execute(sql_product, (product_id,))
        product = cursor.fetchone()
        
        if product and product['specs']:
            try:
                product['specs'] = json.loads(product['specs'])
            except json.JSONDecodeError:
                product['specs'] = None
        
        sql_reviews = """
            SELECT r.rating, r.comment, r.created_at, u.full_name 
            FROM product_reviews r
            JOIN user u ON r.user_id = u.id
            WHERE r.product_id = %s
            ORDER BY r.created_at DESC
        """
        cursor.execute(sql_reviews, (product_id,))
        reviews_list = cursor.fetchall()

    except Exception as e:
        print(f"Lỗi khi truy vấn chi tiết sản phẩm hoặc review: {e}")

    finally:
        if cursor: cursor.close()
        if conn: conn.close()

    if product is None:
        return "Không tìm thấy sản phẩm!", 404

    return render_template('product_detail.html', product=product, user=user_info, reviews=reviews_list)


@app.route('/submit-review', methods=['POST'])
def submit_review():
    
    if 'user_id' not in session:
        return jsonify({"success": False, "message": "Vui lòng đăng nhập để đánh giá."}), 401
        
    conn = None
    cursor = None
    try:
        data = request.get_json()
        user_id = session['user_id']
        product_id = data.get('product_id')
        rating = data.get('rating')
        comment = data.get('comment')

        if not product_id or not rating:
            return jsonify({"success": False, "message": "Thiếu thông tin."}), 400

        conn = get_db_connection()
        cursor = conn.cursor()
        sql = """
            INSERT INTO product_reviews (product_id, user_id, rating, comment)
            VALUES (%s, %s, %s, %s)
        """
        cursor.execute(sql, (product_id, user_id, rating, comment))
        conn.commit()

        return jsonify({"success": True, "message": "Đánh giá của bạn đã được gửi!"})

    except Exception as e:
        if conn: conn.rollback()
        print(f"Lỗi khi gửi đánh giá: {e}")
        return jsonify({"success": False, "message": "Lỗi server."}), 500
    
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


@app.route('/update-cart-quantity', methods=['POST'])
def update_cart_quantity():

    if 'user_id' not in session:
        return jsonify({"success": False, "message": "Vui lòng đăng nhập"}), 401

    conn = None
    cursor = None 
    try:
        data = request.get_json()
        product_id = data.get('product_id')
        new_quantity = data.get('new_quantity')

        if product_id is None or new_quantity is None:
            return jsonify({"success": False, "message": "Thiếu dữ liệu"}), 400

        try:
            new_quantity_int = int(new_quantity)
        except ValueError:
            return jsonify({"success": False, "message": "Số lượng không hợp lệ"}), 400


        user_id = session['user_id']
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        sql_get_cart = "SELECT cart_content FROM cart WHERE user_id = %s"
        cursor.execute(sql_get_cart, (user_id,))
        cart_result = cursor.fetchone()

        cart_list = []
        if cart_result and cart_result['cart_content']:
            cart_list = json.loads(cart_result['cart_content'])

        new_cart_list = []
        item_updated = False

        for item in cart_list:
            if item['id'] == product_id:
                if new_quantity_int > 0:
                    item['quantity'] = new_quantity_int 
                    new_cart_list.append(item)
                item_updated = True
            else:
                new_cart_list.append(item)

        if not item_updated and new_quantity_int > 0:
             pass 

        new_cart_json = json.dumps(new_cart_list)

        sql_update_cart = "UPDATE cart SET cart_content = %s WHERE user_id = %s"
        cursor.execute(sql_update_cart, (new_cart_json, user_id))
        conn.commit()

        return jsonify({"success": True, "message": "Cập nhật thành công"})

    except Exception as e:
        if conn: conn.rollback()
        print(f"Lỗi khi cập nhật giỏ hàng: {e}")
        return jsonify({"success": False, "message": "Lỗi server"}), 500

    finally:
        if cursor: cursor.close()
        if conn: conn.close()

@app.route('/cart')
def view_cart():
    if 'user_id' not in session:
        flash('Vui lòng đăng nhập để xem giỏ hàng của bạn.', 'error')
        return redirect(url_for('login_page'))

    user_info = None
    cart_items_data = []
    conn = None
    cursor = None 
    subtotal = 0

    try:
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor(dictionary=True)

            user_sql = "SELECT full_name, user_role, phone_number FROM user WHERE id = %s"
            cursor.execute(user_sql, (session['user_id'],))
            user_info = cursor.fetchone()

            sql_get_cart = "SELECT cart_content FROM cart WHERE user_id = %s"
            cursor.execute(sql_get_cart, (session['user_id'],))
            cart_result = cursor.fetchone()

            if cart_result and cart_result['cart_content']:
                cart_list = json.loads(cart_result['cart_content'])

                for item in cart_list:
                    product_id_from_json = item['id']
                    quantity_from_json = item['quantity']

                    sql_product = """SELECT id, base_name, storage, price, main_image_url, color 
                                       FROM product 
                                       WHERE id = %s"""
                    cursor.execute(sql_product, (product_id_from_json,))
                    product_data = cursor.fetchone()

                    if product_data:
                        item_total_price = product_data['price'] * quantity_from_json
                        subtotal += item_total_price

                        cart_items_data.append({
                            'id': product_data['id'],
                            'name': f"{product_data['base_name']} {product_data['storage']}",
                            'price': product_data['price'],
                            'img': product_data['main_image_url'],
                            'quantity': quantity_from_json,
                            'item_total': item_total_price,
                            'color': product_data['color']
                        })

            if cursor: cursor.close()

    except Exception as e:
        print(f"Lỗi khi tải trang giỏ hàng: {e}")

    finally:
        if conn: conn.close()

    return render_template('cart.html', user=user_info, cart_items=cart_items_data, subtotal=subtotal)

@app.route('/add-to-cart', methods=['POST'])
def add_to_cart():

    if 'user_id' not in session:
        return jsonify({"success": False, "message": "Vui lòng đăng nhập"}), 401

    conn = None
    cursor = None 
    try:
        data = request.get_json()
        product_id = data.get('product_id')
        quantity_to_add = data.get('quantity', 1)

        if not product_id:
            return jsonify({"success": False, "message": "Thiếu ID sản phẩm"}), 400

        user_id = session['user_id']
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        sql_get_cart = "SELECT cart_content FROM cart WHERE user_id = %s"
        cursor.execute(sql_get_cart, (user_id,))
        cart_result = cursor.fetchone()

        cart_list = []
        if cart_result and cart_result['cart_content']:
            cart_list = json.loads(cart_result['cart_content'])

        found = False
        for item in cart_list:
            if item['id'] == product_id:
                item['quantity'] += quantity_to_add
                found = True
                break

        if not found:
            cart_list.append({'id': product_id, 'quantity': quantity_to_add})

        new_cart_json = json.dumps(cart_list)

        sql_upsert_cart = """
        INSERT INTO cart (user_id, cart_content) 
        VALUES (%s, %s)
        ON DUPLICATE KEY UPDATE cart_content = %s
        """
        cursor.execute(sql_upsert_cart, (user_id, new_cart_json, new_cart_json))

        conn.commit()

        return jsonify({"success": True, "message": "Đã thêm vào giỏ hàng"})

    except Exception as e:
        if conn: conn.rollback()
        print(f"Lỗi khi thêm vào giỏ hàng: {e}")
        return jsonify({"success": False, "message": "Lỗi server"}), 500

    finally:
        if cursor: cursor.close()
        if conn: conn.close()


@app.route('/remove-from-cart', methods=['POST'])
def remove_from_cart():

    if 'user_id' not in session:
        return jsonify({"success": False, "message": "Vui lòng đăng nhập"}), 401

    conn = None
    cursor = None
    try:
        data = request.get_json()
        product_id = data.get('product_id') 

        if not product_id:
            return jsonify({"success": False, "message": "Thiếu ID sản phẩm"}), 400

        user_id = session['user_id']
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        sql_get_cart = "SELECT cart_content FROM cart WHERE user_id = %s"
        cursor.execute(sql_get_cart, (user_id,))
        cart_result = cursor.fetchone()

        cart_list = []
        if cart_result and cart_result['cart_content']:
            cart_list = json.loads(cart_result['cart_content'])

        new_cart_list = []
        for item in cart_list:
            if item['id'] != product_id:
                new_cart_list.append(item)

        new_cart_json = json.dumps(new_cart_list)

        sql_update_cart = "UPDATE cart SET cart_content = %s WHERE user_id = %s"
        cursor.execute(sql_update_cart, (new_cart_json, user_id))
        conn.commit()

        return jsonify({"success": True, "message": "Đã xóa sản phẩm"})

    except Exception as e:
        if conn: conn.rollback()
        print(f"Lỗi khi xóa sản phẩm: {e}")
        return jsonify({"success": False, "message": "Lỗi server"}), 500

    finally:
        if cursor: cursor.close()
        if conn: conn.close()

@app.route('/create-payment-qr', methods=['POST'])
def create_payment_qr():
    if 'user_id' not in session:
        return jsonify({"success": False, "message": "Vui lòng đăng nhập"}), 401

    conn = None
    cursor = None
    try:
        data = request.get_json()
        user_id = session['user_id']
        conn = get_db_connection()
        items_list = data.get('items')
        shipping_address = data.get('shipping_address', 'Không có')
        payment_type = data.get('payment_type', 'cart') 

        if not items_list:
            if payment_type == 'buy_now':
                product_id = data.get('product_id')
                if not product_id:
                    return jsonify({"success": False, "message": "Thiếu ID sản phẩm (buy_now)"}), 400
                items_list = [{'id': str(product_id), 'quantity': 1}]
            else:
                return jsonify({"success": False, "message": "Không có sản phẩm nào được chọn."}), 400

        total_price = calculate_total_from_items(conn, items_list)
        if total_price <= 0:
            return jsonify({"success": False, "message": "Tổng tiền không hợp lệ."}), 400

        cart_json_string = json.dumps(items_list)

        sql_insert_order = """
        INSERT INTO orders (user_id, amount, status, fulfillment_status, shipping_address, order_content) 
        VALUES (%s, %s, 'pending', 'preparing', %s, %s)
        """
        cursor = conn.cursor() 
        cursor.execute(sql_insert_order, (user_id, total_price, shipping_address, cart_json_string))
        order_id = cursor.lastrowid
        conn.commit()

        payment_data_request = CreatePaymentLinkRequest(
            orderCode=order_id,
            amount=int(total_price), 
            description=f"Thanh toan don hang {order_id}",
            returnUrl="http://127.0.0.1:5000/order-history",
            cancelUrl="http://127.0.0.1:5000/cart"
        )
        payos_response = payos.payment_requests.create(payment_data_request)

        return jsonify({
            "success": True,
            "qr_link": payos_response.qr_code,
            "checkout_url": payos_response.checkout_url,
            "amount": total_price, 
            "memo": str(order_id),
            "order_id": order_id
        })

    except Exception as e:
        if conn: conn.rollback()
        print(f"Lỗi khi tạo QR PayOS: {e}")
        return jsonify({"success": False, "message": f"Lỗi server: {e}"}), 500

    finally:
        if cursor: cursor.close()
        if conn: conn.close()
    
@app.route('/check-order-status/<int:order_id>', methods=['GET'])
def check_order_status(order_id):
    
    if 'user_id' not in session:
        return jsonify({"success": False, "message": "Vui lòng đăng nhập"}), 401
    
    conn = None
    try:
        user_id = session['user_id']
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        sql = "SELECT status FROM orders WHERE id = %s AND user_id = %s"
        cursor.execute(sql, (order_id, user_id))
        order = cursor.fetchone()
        
        if order:
            return jsonify({"success": True, "status": order['status']})
        else:
            return jsonify({"success": False, "message": "Không tìm thấy đơn hàng"}), 404
            
    except Exception as e:
        print(f"Lỗi khi kiểm tra status: {e}")
        return jsonify({"success": False, "message": "Lỗi server"}), 500
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

@app.route('/clear-cart', methods=['POST'])
def clear_cart():
    
    if 'user_id' not in session:
        return jsonify({"success": False, "message": "Vui lòng đăng nhập"}), 401
        
    conn = None
    try:
        user_id = session['user_id']
        conn = get_db_connection()
        cursor = conn.cursor()
        
        sql_update_cart = "UPDATE cart SET cart_content = '[]' WHERE user_id = %s"
        cursor.execute(sql_update_cart, (user_id,))
        conn.commit()
        
        return jsonify({"success": True, "message": "Đã xóa giỏ hàng"})

    except Exception as e:
        if conn: conn.rollback()
        print(f"Lỗi khi xóa giỏ hàng: {e}")
        return jsonify({"success": False, "message": "Lỗi server"}), 500
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

@app.route('/payment-webhook', methods=['POST'])
def payment_webhook():
    
    conn = None
    cursor = None
    
    try:
        raw_data = request.get_data()
        
        webhook_data = payos.webhooks.verify(raw_data)
        order_code = webhook_data.order_code
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        sql_update = "UPDATE orders SET status = 'success' WHERE id = %s AND status = 'pending'"
        cursor.execute(sql_update, (order_code,))
        conn.commit()
        
        print(f"--- PAYOS WEBHOOK: THANH TOÁN THÀNH CÔNG CHO ĐƠN HÀNG: {order_code} ---")
        
        return jsonify({"success": True}), 200

    except WebhookError as e:
        print(f"Lỗi WebhookError: {e}")
        return jsonify({"success": False, "message": "Lỗi xác thực Webhook"}), 400
    
    except Exception as e:
        if conn: conn.rollback()
        print(f"Lỗi Webhook: {e}") 
        return jsonify({"success": False}), 500
    
    finally:
        if cursor: cursor.close()
        if conn: conn.close()
@app.route('/order-history')
def order_history_page():
    
    if 'user_id' not in session:
        flash('Vui lòng đăng nhập để xem lịch sử đơn hàng.', 'error')
        return redirect(url_for('login_page'))

    user_info = None
    orders_list = [] 
    conn = None
    cursor = None

    try:
        user_id = session['user_id']
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        user_sql = "SELECT full_name, user_role, phone_number FROM user WHERE id = %s"
        cursor.execute(user_sql, (user_id,))
        user_info = cursor.fetchone()

        orders_sql = """
            SELECT id, amount, status, fulfillment_status, shipping_address, created_at, order_content 
            FROM orders 
            WHERE user_id = %s
            AND (status = 'success' OR status = 'cod') -- ⚠️ THÊM DÒNG NÀY
            ORDER BY created_at DESC
        """
        cursor.execute(orders_sql, (user_id,))
        orders_list = cursor.fetchall()

        for order in orders_list:
            
            if order['created_at']:
                 order['created_at'] = order['created_at'] + timedelta(hours=7)
            
            detailed_items_list = []
            if order['order_content']:
                try:
                    cart_items = json.loads(order['order_content']) 
                    
                    for item in cart_items:
                        product_id = item['id']
                        quantity = item['quantity']
                        
                        sql_product = """SELECT id, base_name, storage, price, 
                                            main_image_url, color 
                                         FROM product WHERE id = %s"""
                        cursor.execute(sql_product, (product_id,))
                        product_data = cursor.fetchone()
                        
                        if product_data:
                            product_data['quantity'] = quantity
                            product_data['item_total'] = product_data['price'] * quantity
                            detailed_items_list.append(product_data)
                        
                except Exception as e:
                    if isinstance(order['order_content'], list):
                        cart_items = order['order_content']
                    else:
                        print(f"Lỗi giải mã JSON order_content: {e}")
            
            order['order_content'] = detailed_items_list

    except Exception as e:
        print(f"Lỗi khi tải lịch sử đơn hàng: {e}")
        flash('Không thể tải lịch sử đơn hàng.', 'error')
    
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

    return render_template('order_history.html', user=user_info, orders_list=orders_list)

@app.route('/create-cod-order', methods=['POST'])
def create_cod_order():
    if 'user_id' not in session:
        return jsonify({"success": False, "message": "Vui lòng đăng nhập"}), 401
    
    conn = None
    cursor = None
    try:
        data = request.get_json()
        user_id = session['user_id']
        conn = get_db_connection()

        items_list = data.get('items')
        shipping_address = data.get('shipping_address', 'Không có')
        payment_type = data.get('payment_type', 'cod_cart') 

        if not items_list:
            if payment_type == 'cod_buy_now':
                product_id = data.get('product_id')
                if not product_id:
                    return jsonify({"success": False, "message": "Thiếu ID sản phẩm (buy_now)"}), 400
                items_list = [{'id': str(product_id), 'quantity': 1}]
            else:
                 return jsonify({"success": False, "message": "Không có sản phẩm nào được chọn."}), 400
        
        total_price = calculate_total_from_items(conn, items_list)
        if total_price <= 0:
            return jsonify({"success": False, "message": "Tổng tiền không hợp lệ."}), 400

        cart_json_string = json.dumps(items_list)

        sql_insert_order = """
        INSERT INTO orders (user_id, amount, status, fulfillment_status, shipping_address, order_content) 
        VALUES (%s, %s, 'cod', 'preparing', %s, %s)
        """
        cursor = conn.cursor() 
        cursor.execute(sql_insert_order, (user_id, total_price, shipping_address, cart_json_string))
        conn.commit()
        return jsonify({"success": True, "message": "Tạo đơn COD thành công"})

    except Exception as e:
        if conn: conn.rollback()
        print(f"Lỗi khi tạo đơn COD: {e}")
        return jsonify({"success": False, "message": f"Lỗi server: {e}"}), 500

    finally:
        if cursor: cursor.close()
        if conn: conn.close()

if __name__ == '__main__':
    
    NGROK_AUTHTOKEN = "1yTLPFPTm3OQHhbichXOyrVhbTs_459S5rE89iYuY2kg6dPmZ" 
    ngrok.set_auth_token(NGROK_AUTHTOKEN)
    MY_NGROK_DOMAIN = "cindi-nonconciliating-gillian.ngrok-free.dev"
    public_url = ngrok.connect(5000, domain=MY_NGROK_DOMAIN)
    print(f"✅ Đồ án của bạn đang chạy tại: http://127.0.0.1:5000")
    app.run(debug=True, use_reloader=False)