"""Capa de acceso a datos SQLite para Mis trapitos.

Este módulo concentra conexión, esquema, migraciones, datos de ejemplo y
operaciones/consultas de inventario, ventas, clientes y reportes.
No depende de Tkinter ni de la interfaz gráfica.
"""
import os
import sqlite3
from datetime import date, datetime, timedelta
from PIL import Image, ImageDraw

from config import DATE_FMT, DB_NAME, DATETIME_FMT, PAYMENT_METHODS
from utils import hash_password, now_text, today_text


def date_offset(days):
    return (date.today() + timedelta(days=days)).strftime(DATE_FMT)

class Database:
    def __init__(self, path=DB_NAME):
        self.path = path
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.create_schema()
        self.migrate_schema()
        self.seed_examples()

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

    def create_schema(self):
        self.conn.executescript(
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
        self.conn.commit()

    def migrate_schema(self):
        columns = [row[1] for row in self.query("PRAGMA table_info(suppliers)")]
        if "products_supplied" not in columns:
            self.execute("ALTER TABLE suppliers ADD COLUMN products_supplied TEXT")
        if "last_order_date" not in columns:
            self.execute("ALTER TABLE suppliers ADD COLUMN last_order_date TEXT"                   )
        self.conn.commit()

    def create_sample_images(self):
        from mis_trapitos.ui.productos import IMAGE_DIR
        base = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), IMAGE_DIR)
        os.makedirs(base, exist_ok=True)
        specs = [
            ("camisa_roja.jpg", (210, 70, 70), (245, 210, 210), "Camisa"),
            ("pantalon_azul.jpg", (55, 90, 170), (210, 225, 250), "Pantalon"),
            ("vestido_negro.jpg", (30, 30, 35), (225, 225, 230), "Vestido"),
            ("falda_verde.jpg"       , (60, 150, 100), (215, 245, 225), "Falda"),
            ("chamarra_cafe.jpg", (130, 85, 55), (245, 225, 205), "Chamarra"),
        ]
        paths = []
        for filename, main, back, label in specs:
            path = os.path.join(base, filename)
            if not os.path.exists(path):
                img = Image.new("RGB", (260, 260), (248, 248, 248))
                draw = ImageDraw.Draw(img)
                draw.rounded_rectangle((35, 35, 225, 225), radius=18, fill=back, outline=(180, 180,
180), width=2)
                if label == "Camisa":
                    draw.polygon([(75, 70), (110, 55), (130, 75), (150, 55), (185, 70), (168, 115),
(160, 205), (100, 205), (92, 115)], fill=main)
                    draw.polygon([(110, 55), (130, 80), (150, 55)], fill=back)
                elif label == "Pantalon":
                    draw.rectangle((95, 55, 165, 115), fill=main)
                    draw.polygon([(95, 115), (128, 115), (118, 215), (82, 215)], fill=main)
                    draw.polygon([(132, 115), (165, 115), (178, 215), (142, 215)], fill=main)
                elif label == "Vestido":
                    draw.polygon([(115, 55), (145, 55), (165, 125), (205, 215), (55, 215), (95,
125)], fill=main)
                    draw.ellipse((118, 58, 142, 82), fill=back)
                elif label == "Falda":
                    draw.rectangle((90, 70, 170, 95), fill=main)
                    draw.polygon([(90, 95), (170, 95), (205, 215), (55, 215)], fill=main)
                    for x in range(80, 190, 22):
                        draw.line((x, 98, x - 18, 215), fill=back, width=2)
                else:
                    draw.rounded_rectangle((78, 60, 182, 215), radius=16, fill=main)
                    draw.rectangle((100, 90, 160, 215), fill=back)
                    draw.line((130, 85, 130, 215), fill=(90, 55, 40), width=3)
                draw.text((85, 232), label, fill=(60, 60, 60))
                img.save(path, "JPEG", quality=92)
            paths.append(path)
        return paths

    def seed_examples(self):
        suppliers = [
            ("Moda Centro", "3331001001", "Av. Juarez 120, Guadalajara", "Camisas y blusas",
date_offset(-18)),
            ("Textiles Luna", "3331001002", "Calle Industria 45, Zapopan"                  , "Pantalones y mezclilla",
date_offset(-15)),
            ("Distribuidora Sol", "3331001003", "Av. Mexico 880, Guadalajara", "Vestidos y faldas",
date_offset(-10)),
            ("Ropa Norte", "3331001004", "Calle Hidalgo 210, Tlaquepaque"                  , "Chamarras y sudaderas",
date_offset(-8)),
            ("Accesorios Viva"       , "3331001005", "Mercado Libertad Local 54"           , "Accesorios y temporada",
date_offset(-3)),
        ]
        for row in suppliers:
            if not self.one("SELECT id FROM suppliers WHERE name=?", (row[0],)):
                self.execute("INSERT INTO suppliers(name, phone, address, products_supplied, last_order_date, created_at) VALUES(?,?,?,?,?,?)", (*row, now_text()))
        employees = [
            ("Administrador", "admin", "1234", "Propietario"),
            ("Ana Lopez", "ana", "1234", "Ventas"),
            ("Luis Perez", "luis", "1234", "Ventas"),
            ("Marta Ruiz", "marta", "1234", "Inventario"),
            ("Carla Diaz", "carla", "1234", "Contabilidad"),
        ]
        for name, username, password, role in employees:
            row = self.one("SELECT id FROM employees WHERE username=?", (username,))
            if not row:
                self.execute("INSERT INTO employees(name, username, password_hash, role, created_at) VALUES(?,?,?,?,?)", (name, username, hash_password(password), role, now_text()))
        customers = [
            ("Sofia Martinez", "3311110001", "sofia@gmail.com", "Calle Roble 10", "Guadalajara",
"Camisas casuales"),
            ("Diego Hernandez", "3311110002", "diego@gmail.com", "Av. Patria 200", "Zapopan",
"Pantalones de mezclilla"),
            ("Valeria Torres", "3311110003", "valeria@hotmail.com", "Calle Naranjo 33",
"Tlaquepaque", "Vestidos negros"),
            ("Miguel Chavez", "3311110004", "miguel@outlook.com", "Av. Central 77", "Tonalá",
"Chamarras"),
            ("Lucia Ramirez", "3311110005", "lucia@gmail.com", "Calle Reforma 91", "Guadalajara",
"Faldas y ofertas"),
        ]
        for row in customers:
            if not self.one("SELECT id FROM customers WHERE email=?", (row[2],)):
                self.execute("INSERT INTO customers(name, phone, email, address, city_region, preferences, created_at) VALUES(?,?,?,?,?,?,?)", (*row, now_text()))
        supplier_ids = {row["name"]: row["id"] for row in self.query("SELECT id, name FROM suppliers")}
        products = [
            ("MT001", "Camisa casual roja", "Camisa", "M", "Rojo", 120, 249, 35,
supplier_ids.get("Moda Centro"), date_offset(-20), "Urbana", "Primavera", ""),
            ("MT002", "Pantalon mezclilla azul", "Pantalon", "32", "Azul", 210, 449, 28,
supplier_ids.get("Textiles Luna"), date_offset(-18), "Denim Pro", "Todo el año", ""),
            ("MT003", "Vestido negro corto"          , "Vestido", "S", "Negro", 250, 599, 22,
supplier_ids.get("Distribuidora Sol"), date_offset(-14), "Noche", "Verano", ""),
            ("MT004", "Falda verde plisada"          , "Falda", "M", "Verde", 140, 329, 30,
supplier_ids.get("Distribuidora Sol"), date_offset(-9), "Fresh", "Primavera", ""),
            ("MT005", "Chamarra cafe ligera", "Chamarra", "L", "Cafe", 310, 699, 18,
supplier_ids.get("Ropa Norte"), date_offset(-7), "Abrigo MX", "Invierno", ""),
        ]
        for row in products:
            existing = self.one("SELECT id FROM products WHERE code=?", (row[0],))
            if not existing:
                cur = self.execute("""INSERT INTO products(code, name, category, size, color,
purchase_price, sale_price, stock, supplier_id, entry_date, brand, season, image_path, created_at)
VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)"""         , (*row, now_text()))
                self.register_movement(cur.lastrowid, "ENTRADA", row[7], "Alta inicial de ejemplo"                        ,
None)
            else:
                default_image_names = ("camisa_roja.jpg", "pantalon_azul.jpg", "vestido_negro.jpg",
"falda_verde.jpg", "chamarra_cafe.jpg"         )
                current = self.one("SELECT image_path FROM products WHERE code=?", (row[0],))
                current_path = current["image_path"] if current else ""
                if current_path and os.path.basename(current_path) in default_image_names:
                    self.execute("UPDATE products SET image_path='' WHERE code=?", (row[0],))
        product_ids = {row["code"]: row["id"] for row in self.query("SELECT id, code FROM products")}
        promo_defs = [("MT001", 10), ("MT002", 5), ("MT003", 15), ("MT004", 12), ("MT005", 8)]
        for code, discount in promo_defs:
            pid = product_ids.get(code)
            if pid and not self.one("SELECT id FROM promotions WHERE product_id=? AND discount_percent=?", (pid, discount)):
                self.execute("INSERT INTO promotions(product_id, discount_percent, start_date, end_date, created_at) VALUES(?,?,?,?,?)", (pid, discount, date_offset(-5), date_offset(30),
now_text()))
        if self.scalar("SELECT COUNT(*) FROM sales WHERE sale_datetime LIKE '2026-05-22 %' OR sale_datetime IS NOT NULL") < 5:
            self.seed_sales(product_ids, cancelled=False, count=5)
        if self.scalar("SELECT COUNT(*) FROM returns") < 5:
            self.seed_returns()
        if self.scalar("SELECT COUNT(*) FROM cancellations") < 5:
            self.seed_sales(product_ids, cancelled=True, count=5)

    def seed_sales(self, product_ids, cancelled, count):
        customers = [row["id"] for row in self.query("SELECT id FROM customers ORDER BY id LIMIT 5")]
        employees = [row["id"] for row in self.query("SELECT id FROM employees ORDER BY id LIMIT 5")]
        codes = ["MT001", "MT002", "MT003", "MT004", "MT005"]
        for i in range(count):
            code_a = codes[i % len(codes)]
            code_b = codes[(i + 1) % len(codes)]
            cart = [
                {"product_id": product_ids[code_a], "quantity": 2},
                {"product_id": product_ids[code_b], "quantity": 1},
            ]
            customer_id = customers[i % len(customers)] if customers else None
            employee_id = employees[i % len(employees)] if employees else 1
            sale_id, subtotal, discount_amount, total = self.register_sale(customer_id, employee_id,
PAYMENT_METHODS[i % len(PAYMENT_METHODS)], i * 2, cart)
            self.execute("UPDATE sales SET sale_datetime=? WHERE id=?", ((datetime.now() - timedelta(days=i)).strftime(DATETIME_FMT), sale_id))
            if cancelled:
                self.cancel_sale(sale_id, "Producto en buenas condiciones")

    def seed_returns(self):
        candidates = self.query(
            """
            SELECT s.id AS sale_id, si.product_id, si.quantity
            FROM sales s JOIN sale_items si ON si.sale_id=s.id
            WHERE s.status='ACTIVA'
            ORDER BY s.id, si.id
            """
        )
        used = 0
        for row in candidates:
            if used >= 5:
                break
            sold = int(row["quantity"])
            returned = self.scalar("SELECT COALESCE(SUM(quantity),0) FROM returns WHERE sale_id=? AND product_id=?", (row["sale_id"], row["product_id"])) or 0
            if sold - returned > 0:
                self.return_item(row["sale_id"], row["product_id"], 1, "Producto Dañado")
                used += 1

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
        param = (param or "").strip()
        if name == "Inventario general actualizado":
            return self.query("""SELECT p.id, p.code AS codigo, p.name AS producto, p.category AS
categoria, p.size AS talla, p.color, p.stock, p.sale_price AS precio, COALESCE(s.name,'') AS
proveedor FROM products p LEFT JOIN suppliers s ON s.id=p.supplier_id ORDER BY p.category,
p.name""")
        if name == "Productos con stock bajo":
            limit = int(param or 5)
            return self.query("SELECT code AS codigo, name AS producto, category AS categoria, size AS talla, color, stock FROM products WHERE stock <= ? ORDER BY stock ASC"                  , (limit,))
        if name == "Ventas diarias, semanales y mensuales":
            return self.query("""SELECT 'Dia actual' AS periodo, COALESCE(SUM(total),0) AS total
FROM sales WHERE status='ACTIVA' AND date(sale_datetime)=date('now') UNION ALL SELECT 'Ultimos 7 dias', COALESCE(SUM(total),0) FROM sales WHERE status='ACTIVA' AND
date(sale_datetime)>=date('now','-6 day') UNION ALL SELECT 'Mes actual', COALESCE(SUM(total),0) FROM
sales WHERE status='ACTIVA' AND strftime('%Y-%m',sale_datetime)=strftime('%Y-%m','now')""")
        if name == "Ventas por producto":
            return self.query("""SELECT p.code AS codigo, p.name AS producto, SUM(si.quantity) AS
piezas, SUM(si.line_total) AS ventas FROM sale_items si JOIN products p ON p.id=si.product_id JOIN
sales s ON s.id=si.sale_id WHERE s.status='ACTIVA' GROUP BY p.id ORDER BY piezas DESC""")
        if name == "Ventas por metodo de pago":
            return self.query("SELECT payment_method AS metodo, COUNT(*) AS ventas, SUM(total) AS total FROM sales WHERE status='ACTIVA' GROUP BY payment_method ORDER BY ventas DESC")
        if name == "Ventas por empleado":
            return self.query("""SELECT e.name AS empleado, COUNT(s.id) AS ventas,
COALESCE(SUM(s.total),0) AS total FROM employees e LEFT JOIN sales s ON s.employee_id=e.id AND
s.status='ACTIVA' GROUP BY e.id ORDER BY total DESC""")
        if name == "Productos mas vendidos":
            return self.query("""SELECT p.code AS codigo, p.name AS producto, SUM(si.quantity) AS
piezas FROM sale_items si JOIN products p ON p.id=si.product_id JOIN sales s ON s.id=si.sale_id
WHERE s.status='ACTIVA' GROUP BY p.id ORDER BY piezas DESC LIMIT 20""")
        if name == "Productos menos vendidos":
            return self.query("""SELECT p.code AS codigo, p.name AS producto, COALESCE(SUM(CASE WHEN
s.status='ACTIVA' THEN si.quantity ELSE 0 END),0) AS piezas FROM products p LEFT JOIN sale_items si
ON si.product_id=p.id LEFT JOIN sales s ON s.id=si.sale_id GROUP BY p.id ORDER BY piezas ASC LIMIT
20""")
        if name == "Entradas de mercancia":
            return self.query("""SELECT im.movement_datetime AS fecha, p.code AS codigo, p.name AS
producto, im.quantity AS cantidad, im.reason AS motivo FROM inventory_movements im JOIN products p
ON p.id=im.product_id WHERE im.movement_type IN ('ENTRADA','AJUSTE') AND im.quantity > 0 ORDER BY
im.movement_datetime DESC""")
        if name == "Clientes frecuentes":
            return self.query("""SELECT c.name AS cliente, c.phone AS telefono, COUNT(s.id) AS
compras, COALESCE(SUM(s.total),0) AS total FROM customers c LEFT JOIN sales s ON s.customer_id=c.id
AND s.status='ACTIVA' GROUP BY c.id ORDER BY compras DESC, total DESC""")
        if name == "Resumen de utilidades":
            return self.query("""SELECT p.code AS codigo, p.name AS producto, SUM(si.quantity) AS
piezas, SUM(si.line_total) AS ventas, SUM(si.quantity * p.purchase_price) AS costo,
SUM(si.line_total - si.quantity * p.purchase_price) AS utilidad FROM sale_items si JOIN products p
ON p.id=si.product_id JOIN sales s ON s.id=si.sale_id WHERE s.status='ACTIVA' GROUP BY p.id ORDER BY
utilidad DESC""")
        if name == "Productos devueltos o cancelados":
            return self.query("""SELECT im.movement_datetime AS fecha, im.movement_type AS tipo,
p.code AS codigo, p.name AS producto, im.quantity AS cantidad, im.reason AS motivo,
im.related_sale_id AS venta FROM inventory_movements im JOIN products p ON p.id=im.product_id WHERE
im.movement_type IN ('DEVOLUCION','CANCELACION') ORDER BY im.movement_datetime DESC""")
        if name == "Productos disponibles por categoria":
            if not param:
                raise ValueError("Escribe una categoria.")
            return self.query("SELECT code AS codigo, name AS producto, category AS categoria, size AS talla, color, stock, sale_price AS precio FROM products WHERE category LIKE ? AND stock > 0 ORDER BY name", (f"%{param}%",))
        if name == "Productos en oferta":
            return self.query("""SELECT p.code AS codigo, p.name AS producto, pr.discount_percent AS
descuento, pr.start_date AS inicio, pr.end_date AS fin FROM promotions pr JOIN products p ON
p.id=pr.product_id WHERE date('now') BETWEEN date(pr.start_date) AND date(pr.end_date) ORDER BY
pr.discount_percent DESC""")
        if name == "Metodos de pago mas utilizados":
            return self.report("Ventas por metodo de pago", param)
        if name == "Productos mas vendidos ultimo mes":
            return self.query("""SELECT p.code AS codigo, p.name AS producto, SUM(si.quantity) AS
piezas FROM sale_items si JOIN products p ON p.id=si.product_id JOIN sales s ON s.id=si.sale_id
WHERE s.status='ACTIVA' AND date(s.sale_datetime)>=date('now','-1 month') GROUP BY p.id ORDER BY
piezas DESC""")
        if name == "Ventas ultimos tres dias":
            return self.query("""SELECT s.id AS venta, s.sale_datetime AS fecha, COALESCE(c.name,'')
AS cliente, e.name AS empleado, s.payment_method AS metodo, s.total, s.status AS estado FROM sales s
LEFT JOIN customers c ON c.id=s.customer_id JOIN employees e ON e.id=s.employee_id WHERE
date(s.sale_datetime)>=date('now','-3 day') ORDER BY s.sale_datetime DESC""")
        if name == "Productos de proveedor especifico":
            if not param:
                raise ValueError("Escribe ID o nombre del proveedor."                 )
            if param.isdigit():
                return self.query("""SELECT p.code AS codigo, p.name AS producto, p.category AS
categoria, p.size AS talla, p.color, p.stock, s.name AS proveedor FROM products p JOIN suppliers s
ON s.id=p.supplier_id WHERE s.id=?""", (int(param),))
            return self.query("""SELECT p.code AS codigo, p.name AS producto, p.category AS
categoria, p.size AS talla, p.color, p.stock, s.name AS proveedor FROM products p JOIN suppliers s
ON s.id=p.supplier_id WHERE s.name LIKE ?""", (f"%{param}%",))
        if name == "Productos comprados mas de una vez por cliente":
            if not param or not param.isdigit():
                raise ValueError("Escribe el ID del cliente.")
            return self.query("""SELECT p.code AS codigo, p.name AS producto, SUM(si.quantity) AS
piezas, COUNT(DISTINCT s.id) AS compras FROM sales s JOIN sale_items si ON si.sale_id=s.id JOIN
products p ON p.id=si.product_id WHERE s.status='ACTIVA' AND s.customer_id=? GROUP BY p.id HAVING
COUNT(DISTINCT s.id)>1 OR SUM(si.quantity)>1 ORDER BY piezas DESC""", (int(param),))
        if name == "Productos vendidos por categoria ultimo mes":
            if not param:
                raise ValueError("Escribe una categoria.")
            return self.query("""SELECT p.category AS categoria, p.code AS codigo, p.name AS
producto, SUM(si.quantity) AS piezas, SUM(si.line_total) AS total FROM sale_items si JOIN products p
ON p.id=si.product_id JOIN sales s ON s.id=si.sale_id WHERE s.status='ACTIVA' AND
date(s.sale_datetime)>=date('now','        -1 month') AND p.category LIKE ? GROUP BY p.id ORDER BY piezas
DESC""", (f"%{param}%",))
        if name == "Productos con precio superior y existencias":
            value = float(param or 0)
            return self.query("SELECT code AS codigo, name AS producto, category AS categoria, sale_price AS precio, stock FROM products WHERE sale_price > ? AND stock > 0 ORDER BY sale_price DESC", (value,))
        if name == "Producto con mayor descuento vigente":
            return self.query("""SELECT p.code AS codigo, p.name AS producto, pr.discount_percent AS
descuento, pr.start_date AS inicio, pr.end_date AS fin FROM promotions pr JOIN products p ON
p.id=pr.product_id WHERE date('now') BETWEEN date(pr.start_date) AND date(pr.end_date) ORDER BY
pr.discount_percent DESC LIMIT 1""")
        if name == "Compras por ciudad o region":
            return self.query("""SELECT COALESCE(c.city_region,'Sin region') AS region, COUNT(s.id)
AS compras, SUM(s.total) AS total FROM sales s LEFT JOIN customers c ON c.id=s.customer_id WHERE
s.status='ACTIVA' GROUP BY c.city_region ORDER BY compras DESC""")
        if name == "Productos no vendidos ultimos tres meses":
            return self.query("""SELECT p.code AS codigo, p.name AS producto, p.category AS
categoria, p.stock FROM products p WHERE p.id NOT IN (SELECT DISTINCT si.product_id FROM sale_items
si JOIN sales s ON s.id=si.sale_id WHERE s.status='ACTIVA' AND date(s.sale_datetime)>=date('now','-3 month')) ORDER BY p.name""")
        raise ValueError("Reporte no reconocido.")
