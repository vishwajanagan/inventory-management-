# db.py
import mysql.connector
from mysql.connector import Error
import bcrypt
import datetime

DB_HOST = 'localhost'
DB_USER = 'root'
DB_PASSWORD = 'root'
DB_NAME = 'inventory_management'

def get_db_connection():
    try:
        conn = mysql.connector.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME
        )
        return conn
    except Error as e:
        print("DB connection error:", e)
        return None

def initialize_database():
    """Create database and required tables if they do not exist. Also create default admin."""
    try:
        conn = mysql.connector.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD
        )
        cur = conn.cursor()
        cur.execute(f"CREATE DATABASE IF NOT EXISTS {DB_NAME}")
        cur.execute(f"USE {DB_NAME}")

        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(255) NOT NULL UNIQUE,
                access_type ENUM('employee', 'manager', 'admin') NOT NULL,
                password VARCHAR(255) NOT NULL,
                sales FLOAT DEFAULT 0.0
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS products (
                product_id INT AUTO_INCREMENT PRIMARY KEY,
                description TEXT,
                category VARCHAR(255),
                cost_price FLOAT NOT NULL,
                selling_price FLOAT NOT NULL,
                profit FLOAT DEFAULT 0.0,
                number_in_stock INT NOT NULL,
                number_sold INT DEFAULT 0
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS bills (
                bill_id INT AUTO_INCREMENT PRIMARY KEY,
                time DATETIME NOT NULL,
                employee_id INT,
                cost FLOAT NOT NULL,
                product_name VARCHAR(255) NOT NULL,
                total_items INT NOT NULL,
                discount FLOAT DEFAULT 0.0,
                cgst FLOAT DEFAULT 0.0,
                sgst FLOAT DEFAULT 0.0,
                total_profit FLOAT DEFAULT 0.0,
                FOREIGN KEY (employee_id) REFERENCES users(user_id)
            )
        """)

        
        default_admin_password = 'admin123'
        hashed = bcrypt.hashpw(default_admin_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        cur.execute("SELECT user_id FROM users WHERE access_type = 'admin' LIMIT 1")
        if not cur.fetchone():
            cur.execute("INSERT INTO users (name, access_type, password) VALUES (%s, %s, %s)",
                        ('Admin', 'admin', hashed))
            conn.commit()

        cur.close()
        conn.close()
        print("Database initialized or verified.")
    except Error as e:
        print("Error during DB init:", e)
