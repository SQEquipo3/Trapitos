"""Conexión SQLite y operaciones de la aplicación Mis trapitos."""

import sqlite3
from contextlib import contextmanager

from config import DB_NAME
from utils import hash_password, now_text, today_text
from mis_trapitos.data.repositories import reportes as reportes_repo
from mis_trapitos.data.schema import create_schema, migrate_schema
from mis_trapitos.data.seed import seed_examples


class Database:
    def __init__(self, path=DB_NAME, load_examples=True):
        self.path = path
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self._tx_depth = 0
        create_schema(self)
        migrate_schema(self)
        if load_examples:
            seed_examples(self)

    def close(self):
        self.conn.close()

    @contextmanager
    def transaction(self):
        """Agrupa varias escrituras: commit al final o rollback completo si algo falla.

        Admite anidarse; solo la transacción más externa hace commit.
        """
        if self._tx_depth:
            self._tx_depth += 1
            try:
                yield
            finally:
                self._tx_depth -= 1
            return
        self._tx_depth = 1
        try:
            with self.conn:
                yield
        finally:
            self._tx_depth = 0

    def execute(self, sql, params=()):
        if self._tx_depth:
            return self.conn.execute(sql, params)
        with self.conn:
            return self.conn.execute(sql, params)

    def query(self, sql, params=()):
        return self.conn.execute(sql, params).fetchall()

    def one(self, sql, params=()):
        return self.conn.execute(sql, params).fetchone()

    def scalar(self, sql, params=()):
        row = self.one(sql, params)
        if row is None:
            return None
        return row[0]

    def authenticate(self, username, password):
        return self.one("SELECT * FROM employees WHERE username=? AND password_hash=?", (username,
hash_password(password)))

    def register_movement(self, product_id, movement_type, quantity, reason, sale_id=None):
        self.execute("INSERT INTO inventory_movements(product_id, movement_type, quantity, movement_datetime, reason, related_sale_id) VALUES(?,?,?,?,?,?)", (product_id, movement_type,
quantity, now_text(), reason, sale_id))

    def save_supplier(self, supplier_id, data):
        if supplier_id:
            self.execute("UPDATE suppliers SET name=?, phone=?, address=?, products_supplied=?, last_order_date=? WHERE id=?", (*data, supplier_id))
            return supplier_id
        cur = self.execute("INSERT INTO suppliers(name, phone, address, products_supplied, last_order_date, created_at) VALUES(?,?,?,?,?,?)"            , (*data, now_text()))
        return cur.lastrowid

    def save_employee(self, employee_id, name, username, password, role):
        if employee_id:
            if password:
                self.execute("UPDATE employees SET name=?, username=?, password_hash=?, role=? WHERE id=?", (name, username, hash_password(password), role, employee_id))
            else:
                self.execute("UPDATE employees SET name=?, username=?, role=? WHERE id=?"                      , (name,
username, role, employee_id))
            return employee_id
        cur = self.execute("INSERT INTO employees(name, username, password_hash, role, created_at) VALUES(?,?,?,?,?)", (name, username, hash_password(password or "1234"), role, now_text()))
        return cur.lastrowid

    def save_customer(self, customer_id, data):
        if customer_id:
            self.execute("UPDATE customers SET name=?, phone=?, email=?, address=?, city_region=?, preferences=? WHERE id=?", (*data, customer_id))
            return customer_id
        cur = self.execute("INSERT INTO customers(name, phone, email, address, city_region, preferences, created_at) VALUES(?,?,?,?,?,?,?)", (*data, now_text()))
        return cur.lastrowid

    def save_product(self, product_id, data):
        if product_id:
            old = self.one("SELECT stock FROM products WHERE id=?", (product_id,))
            self.execute("""UPDATE products SET code=?, name=?, category=?, size=?, color=?,
purchase_price=?, sale_price=?, stock=?, supplier_id=?, entry_date=?, brand=?, season=?,
image_path=? WHERE id=?""", (*data, product_id))
            if old and int(old["stock"]) != int(data[7]):
                self.register_movement(product_id, "AJUSTE", int(data[7]) - int(old["stock"]),
"Actualizacion manual de inventario", None)
            return product_id
        cur = self.execute("""INSERT INTO products(code, name, category, size, color,
purchase_price, sale_price, stock, supplier_id, entry_date, brand, season, image_path, created_at)
VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)"""         , (*data, now_text()))
        self.register_movement(cur.lastrowid, "ENTRADA", int(data[7]), "Alta inicial de producto",
None)
        return cur.lastrowid

    def save_promotion(self, promotion_id, product_id, discount_percent, start_date, end_date):
        if promotion_id:
            self.execute("UPDATE promotions SET product_id=?, discount_percent=?, start_date=?, end_date=? WHERE id=?", (product_id, discount_percent, start_date, end_date, promotion_id))
            return promotion_id
        cur = self.execute("INSERT INTO promotions(product_id, discount_percent, start_date, end_date, created_at) VALUES(?,?,?,?,?)", (product_id, discount_percent, start_date, end_date,
now_text()))
        return cur.lastrowid

    def active_promotion_percent(self, product_id):
        row = self.one("SELECT MAX(discount_percent) AS discount FROM promotions WHERE product_id=? AND date(?) BETWEEN date(start_date) AND date(end_date)", (product_id, today_text()))
        return float(row["discount"] or 0)

    def customer_history(self, customer_id):
        return self.query("""SELECT s.id AS venta, s.sale_datetime AS fecha, p.code AS codigo,
p.name AS producto, si.quantity AS cantidad, si.line_total AS total_linea, s.total AS total_venta,
s.status AS estado FROM sales s JOIN sale_items si ON si.sale_id=s.id JOIN products p ON
p.id=si.product_id WHERE s.customer_id=? ORDER BY s.sale_datetime DESC"""                  , (customer_id,))

    def report(self, name, param=""):
        return reportes_repo.ejecutar(self, name, param)

