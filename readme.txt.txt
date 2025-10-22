Requirements

Python 3.9+

MySQL Server

pip install -r requirements.txt​

Setup (fast)

Create venv and install:

python -m venv .venv

source .venv/bin/activate (Windows: .venv\Scripts\activate)

pip install -r requirements.txt​

Configure MySQL in db.py:

DB_HOST = 'localhost'

DB_USER = 'root'

DB_PASSWORD = 'root'

DB_NAME = 'inventory_management'
Change these to your MySQL values. User must have permission to create DB/tables.​

(Optional, recommended) Change Flask secret:

In app.py, change app.secret_key from "supersecretkey".​

Run

Ensure MySQL is running.

python app.py

Open http://localhost:5000​

First login

Username: Admin

Password: admin123

Go to Admin panel and change the password immediately.​

Basic usage

Products: add, restock, list.​

Billing: create bill, optional discount; GST from category splits into CGST/SGST; stock/sales/profit update automatically.​

Employee stats: view your sales and profit.​

Team sales (manager/admin): view employee sales.​

Pricing (manager/admin): update selling price.​

Admin: add/remove users, reset passwords.​

GST categories (edit in app.py)
electronics: 18, clothing: 12, groceries: 5, books: 0. Adjust as needed.​

Notes

Don’t commit real passwords/keys. Use env vars in production.

bcrypt is used for secure password storage.​

App auto-initializes DB on start via initialize_database(). "