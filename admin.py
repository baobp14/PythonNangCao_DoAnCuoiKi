import mysql.connector
from flask import Flask
from flask_bcrypt import Bcrypt
import sys 

ADMIN_NAME = "Admin"
ADMIN_PHONE = "0123456789"  
ADMIN_PASS = "123"    

db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': '14072005', 
    'database': 'banhang_db'
}

def get_db_connection():
    try:
        conn = mysql.connector.connect(**db_config)
        return conn
    except Exception as e:
        print(f"Lỗi kết nối database: {e}")
        return None

app = Flask(__name__)
bcrypt = Bcrypt(app)

def create_admin_account():
    print(f"--- Đang tạo tài khoản Admin cho: {ADMIN_PHONE} ---")
    hashed_password = bcrypt.generate_password_hash(ADMIN_PASS).decode('utf-8')

    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        if conn is None:
            sys.exit(1) 

        cursor = conn.cursor()

        sql_user = """
            INSERT INTO user (phone_number, password_hash, full_name, user_role) 
            VALUES (%s, %s, %s, 'admin')
        """
        cursor.execute(sql_user, (ADMIN_PHONE, hashed_password, ADMIN_NAME))
        user_id = cursor.lastrowid

        sql_cart = "INSERT INTO cart (user_id, cart_content) VALUES (%s, %s)"
        cursor.execute(sql_cart, (user_id, '[]'))

        conn.commit()
        print(f"\n✅ Tạo Admin '{ADMIN_NAME}' (ID: {user_id}) thành công!")

    except mysql.connector.Error as err:
        if conn: conn.rollback()
        if err.errno == 1062:
            print(f"\n❌ LỖI: Số điện thoại '{ADMIN_PHONE}' đã tồn tại!")
        else:
            print(f"\n LỖI DB: {err}")
            
    except Exception as e:
        if conn: conn.rollback()
        print(f"\nLỖI KHÔNG XÁC ĐỊNH: {e}")

    finally:
        if cursor: cursor.close()
        if conn: conn.close()

if __name__ == "__main__":
    create_admin_account()