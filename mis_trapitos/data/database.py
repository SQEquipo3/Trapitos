"""Conexión SQLite y operaciones de la aplicación Mis trapitos."""

import sqlite3

from config import DB_NAME, PAYMENT_METHODS
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
        create_schema(self)
        migrate_schema(self)
        if load_examples:
            seed_examples(self)

    def close(self):
        self.conn.close()

    def execute(self, sql, params=()):
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

    def register_sale(self, customer_id, employee_id, payment_method, sale_discount_percent, cart):
        if not cart:
            raise ValueError("La venta no tiene productos.")
        sale_discount_percent = float(sale_discount_percent or 0)
        if sale_discount_percent < 0 or sale_discount_percent > 100:
            raise ValueError("El descuento debe estar entre 0 y 100.")
        if payment_method not in PAYMENT_METHODS:
            raise ValueError("Metodo de pago no valido."              )
        with self.conn:
            subtotal = 0.0
            prepared = []
            for item in cart:
                product_id = int(item["product_id"])
                qty = int(item["quantity"])
                product = self.one("SELECT * FROM products WHERE id=?", (product_id,))
                if not product:
                    raise ValueError("Producto no encontrado.")
                if qty <= 0:
                    raise ValueError("La cantidad debe ser mayor a cero."                  )
                if int(product["stock"]) < qty:
                    raise ValueError(f"Stock insuficiente para {product['code']} - {product['name']}.")
                promo = self.active_promotion_percent             (product_id)
                unit_price = float(product["sale_price"])
                line_total = unit_price * qty * (1 - promo / 100)
                subtotal += line_total
                prepared.append((product_id, qty, unit_price, promo, line_total))
            discount_amount = subtotal * sale_discount_percent / 100
            total = subtotal - discount_amount
            cur = self.conn.execute("""INSERT INTO sales(sale_datetime, customer_id, employee_id,
payment_method, subtotal, sale_discount_percent, discount_amount, total, status)
VALUES(?,?,?,?,?,?,?,?,?)""", (now_text(), customer_id or None, employee_id, payment_method,
subtotal, sale_discount_percent, discount_amount, total, "ACTIVA"))
            sale_id = cur.lastrowid
            for product_id, qty, unit_price, promo, line_total in prepared:
                self.conn.execute("INSERT INTO sale_items(sale_id, product_id, quantity, unit_price, promo_discount_percent, line_total) VALUES(?,?,?,?,?,?)"              , (sale_id, product_id, qty, unit_price,
promo, line_total))
                self.conn.execute("UPDATE products SET stock = stock                  - ? WHERE id=?", (qty,
product_id))
                self.conn.execute("INSERT INTO inventory_movements(product_id, movement_type, quantity, movement_datetime, reason, related_sale_id) VALUES(?,?,?,?,?,?)", (product_id, "SALIDA", - qty, now_text(), "Venta registrada"        , sale_id))
            return sale_id, subtotal, discount_amount, total

    def return_item(self, sale_id, product_id, quantity, reason):
        sale = self.one("SELECT * FROM sales WHERE id=?"              , (sale_id,))
        if not sale:
            raise ValueError("Venta no encontrada.")
        if sale["status"] == "CANCELADA":
            raise ValueError("No se puede devolver sobre una venta cancelada."                   )
        sold_qty = self.scalar("SELECT COALESCE(SUM(quantity),0) FROM sale_items WHERE sale_id=? AND product_id=?", (sale_id, product_id)) or 0
        returned_qty = self.scalar("SELECT COALESCE(SUM(quantity),0) FROM returns WHERE sale_id=? AND product_id=?", (sale_id, product_id)) or 0
        quantity = int(quantity)
        if quantity <= 0 or quantity > sold_qty - returned_qty:
            raise ValueError("Cantidad de devolucion no valida.")
        with self.conn:
            self.conn.execute("INSERT INTO returns(sale_id, product_id, quantity, return_datetime, reason) VALUES(?,?,?,?,?)", (sale_id, product_id, quantity, now_text(), reason))
            self.conn.execute("UPDATE products SET stock = stock + ? WHERE id=?", (quantity,
product_id))
            self.conn.execute("INSERT INTO inventory_movements(product_id, movement_type, quantity, movement_datetime, reason, related_sale_id) VALUES(?,?,?,?,?,?)", (product_id, "DEVOLUCION",
quantity, now_text(), reason or "Devolucion", sale_id))

    def cancel_sale(self, sale_id, reason):
        sale = self.one("SELECT * FROM sales WHERE id=?", (sale_id,))
        if not sale:
            raise ValueError("Venta no encontrada.")
        if sale["status"] == "CANCELADA":
            raise ValueError("La venta ya esta cancelada."              )
        items = self.query("SELECT * FROM sale_items WHERE sale_id=?"                 , (sale_id,))
        with self.conn:
            for item in items:
                returned_qty = self.scalar("SELECT COALESCE(SUM(quantity),0) FROM returns WHERE sale_id=? AND product_id=?", (sale_id, item["product_id"])) or 0
                restore_qty = max(0, int(item["quantity"]) - int(returned_qty))
                if restore_qty > 0:
                    self.conn.execute("UPDATE products SET stock = stock + ? WHERE id=?",
(restore_qty, item["product_id"]))
                    self.conn.execute("INSERT INTO inventory_movements(product_id, movement_type, quantity, movement_datetime, reason, related_sale_id) VALUES(?,?,?,?,?,?)", (item["product_id"],
"CANCELACION", restore_qty, now_text(), reason or "Cancelacion", sale_id))
            self.conn.execute("UPDATE sales SET status='CANCELADA' WHERE id=?", (sale_id,))
            self.conn.execute("INSERT INTO cancellations(sale_id, cancel_datetime, reason) VALUES(?,?,?)", (sale_id, now_text(), reason or "Cancelacion"))

    def customer_history(self, customer_id):
        return self.query("""SELECT s.id AS venta, s.sale_datetime AS fecha, p.code AS codigo,
p.name AS producto, si.quantity AS cantidad, si.line_total AS total_linea, s.total AS total_venta,
s.status AS estado FROM sales s JOIN sale_items si ON si.sale_id=s.id JOIN products p ON
p.id=si.product_id WHERE s.customer_id=? ORDER BY s.sale_datetime DESC"""                  , (customer_id,))

    def report(self, name, param=""):
        return reportes_repo.ejecutar(self, name, param)

