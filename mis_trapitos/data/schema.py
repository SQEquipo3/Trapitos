"""Creación y migraciones del esquema SQLite."""

def create_schema(db):
    db.conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS suppliers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            phone TEXT,
            address TEXT,
            products_supplied TEXT,
            last_order_date TEXT,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS employees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT,
            email TEXT,
            address TEXT,
            city_region TEXT,
            preferences TEXT,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            size TEXT NOT NULL,
            color TEXT NOT NULL,
            purchase_price REAL NOT NULL CHECK(purchase_price >= 0),
            sale_price REAL NOT NULL CHECK(sale_price >= 0),
            stock INTEGER NOT NULL CHECK(stock >= 0),
            supplier_id INTEGER,
            entry_date TEXT NOT NULL,
            brand TEXT,
            season TEXT,
            image_path TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (supplier_id) REFERENCES suppliers(id)
        );
        CREATE TABLE IF NOT EXISTS promotions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL,
            discount_percent REAL NOT NULL CHECK(discount_percent >= 0 AND discount_percent <= 100),
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (product_id) REFERENCES products(id)
        );
        CREATE TABLE IF NOT EXISTS sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sale_datetime TEXT NOT NULL,
            customer_id INTEGER,
            employee_id INTEGER NOT NULL,
            payment_method TEXT NOT NULL,
            subtotal REAL NOT NULL,
            sale_discount_percent REAL NOT NULL DEFAULT 0,
            discount_amount REAL NOT NULL,
            total REAL NOT NULL,
            status TEXT NOT NULL DEFAULT 'ACTIVA',
            FOREIGN KEY (customer_id) REFERENCES customers(id),
            FOREIGN KEY (employee_id) REFERENCES employees(id)
        );
        CREATE TABLE IF NOT EXISTS sale_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sale_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL CHECK(quantity > 0),
            unit_price REAL NOT NULL,
            promo_discount_percent REAL NOT NULL DEFAULT 0,
            line_total REAL NOT NULL,
            FOREIGN KEY (sale_id) REFERENCES sales(id),
            FOREIGN KEY (product_id) REFERENCES products(id)
        );
        CREATE TABLE IF NOT EXISTS inventory_movements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL,
            movement_type TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            movement_datetime TEXT NOT NULL,
            reason TEXT NOT NULL,
            related_sale_id INTEGER,
            FOREIGN KEY (product_id) REFERENCES products(id),
            FOREIGN KEY (related_sale_id) REFERENCES sales(id)
        );
        CREATE TABLE IF NOT EXISTS returns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sale_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL CHECK(quantity > 0),
            return_datetime TEXT NOT NULL,
            reason TEXT,
            FOREIGN KEY (sale_id) REFERENCES sales(id),
            FOREIGN KEY (product_id) REFERENCES products(id)
        );
        CREATE TABLE IF NOT EXISTS cancellations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sale_id INTEGER NOT NULL,
            cancel_datetime TEXT NOT NULL,
            reason TEXT,
            FOREIGN KEY (sale_id) REFERENCES sales(id)
        );
        """
    )
    db.conn.commit()


def migrate_schema(db):
    columns = [row[1] for row in db.query("PRAGMA table_info(suppliers)")]
    if "products_supplied" not in columns:
        db.execute("ALTER TABLE suppliers ADD COLUMN products_supplied TEXT")
    if "last_order_date" not in columns:
        db.execute("ALTER TABLE suppliers ADD COLUMN last_order_date TEXT"                   )
    db.conn.commit()
