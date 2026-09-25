import csv
import hashlib
import os
import sqlite3
import tkinter as tk
import urllib.parse
import webbrowser
from datetime import date, datetime, timedelta
from tkinter import filedialog, messagebox, ttk
from PIL import Image, ImageDraw

from ui_productos import IMAGE_DIR, ProductosUI

APP_TITLE = "Mis trapitos - Sistema local"
APP_VERSION = "7.0"
DB_NAME = "mis_trapitos.db"
DATE_FMT = "%Y-%m-%d"
DATETIME_FMT = "%Y-%m-%d %H:%M:%S"
PAYMENT_METHODS = ("Efectivo", "Tarjeta de credito", "Tarjeta de debito", "Transferencia bancaria")

CONFIG_ITEMS = [
    ("CI-01", "Codigo fuente principal"        , "mis_trapitos_app_v7.py", "Controlado"),
    ("CI-02", "Base de datos local"        , "mis_trapitos.db", "Controlado"),
    ("CI-03", "Version de aplicacion", APP_VERSION, "Controlado"),
    ("CI-04", "Operacion sin Internet"         , "SQLite local y Tkinter", "Controlado"),
    ("CI-05", "Usuario inicial", "admin / 1234", "Controlado"),
    ("CI-06", "Modulo de productos", "ui_productos.py", "Controlado"),
]

TRACEABILITY = [
    ("RF-01", "Registrar productos con categoria, descripcion, precio, talla y color"                     , "Productos",
"Guardar producto y verificar en inventario"           ),
    ("RF-02", "Manejar variaciones de talla y color con existencias"                 , "Productos", "Registrar mismo producto con otra talla o color"),
    ("RF-03", "Agregar productos y actualizar cantidades de inventario"                  , "Productos", "Modificar stock y revisar movimiento"),
    ("RF-04", "Actualizar inventario automaticamente al registrar venta"                  , "Ventas", "Vender producto y comprobar disminucion"),
    ("RF-05", "Registrar movimientos de inventario"             , "Inventario", "Consultar movimientos de entrada, salida, ajuste, devolucion y cancelacion"),
    ("RF-06", "Registrar ventas con productos, cantidades y metodo de pago"                   , "Ventas", "Registrar venta con carrito"),
    ("RF-07", "Registrar pagos en efectivo, tarjeta y transferencia"                 , "Ventas", "Seleccionar metodo de pago"),
    ("RF-08", "Aplicar descuentos a ventas"          , "Ventas", "Capturar descuento general"           ),
    ("RF-09", "Registrar promociones con porcentaje y duracion"                , "Promociones", "Crear promocion vigente"),
    ("RF-10", "Aplicar descuentos automaticos segun condiciones"                , "Promociones y Ventas", "Venta aplica promocion vigente"),
    ("RF-11", "Registrar clientes con nombre, direccion, correo y telefono"                   , "Clientes", "Guardar cliente"),
    ("RF-12", "Almacenar y consultar historial de compras de cada cliente"                   , "Clientes y Reportes",
"Consultar historial"),
    ("RF-13", "Registrar proveedores e informacion de contacto"                , "Proveedores", "Guardar proveedor"),
    ("RF-14", "Relacionar proveedor con productos que suministra"                , "Productos y Proveedores",
"Consultar productos por proveedor"),
    ("RF-15", "Consultar productos disponibles e inventario por categoria"                   , "Reportes", "Reporte por categoria"),
    ("RF-16", "Consultar productos en oferta y descuentos"               , "Reportes", "Reporte de productos en oferta"),
    ("RF-17", "Consultar metodos de pago mas utilizados"              , "Reportes", "Reporte de metodos de pago"),
    ("RF-18", "Consultar productos mas vendidos en el ultimo mes"                , "Reportes", "Reporte mensual"),
    ("RF-19", "Consultar ventas realizadas en los ultimos tres dias"                 , "Reportes", "Reporte de ultimos tres dias"),
    ("RF-20", "Consultar productos de un proveedor especifico"                , "Reportes", "Parametro de proveedor"),
    ("RF-21", "Consultar productos comprados mas de una vez por un cliente"                   , "Reportes", "Parametro de cliente"),
    ("RF-22", "Consultar productos vendidos por categoria en el ultimo mes"                   , "Reportes", "Parametro de categoria"),
    ("RF-23", "Consultar productos con precio superior a cierto valor y existencias"                     , "Reportes",
"Parametro de precio"),
    ("RF-24", "Consultar producto con mayor descuento vigente"                , "Reportes", "Promociones vigentes"         ),
    ("RF-25", "Consultar compras por ciudad o region del cliente"                , "Reportes", "Agrupar por region"),
    ("RF-26", "Consultar productos no vendidos en los ultimos tres meses"                  , "Reportes", "Reporte sin ventas recientes"),
    ("RNF-01", "Reflejar en tiempo real la disminucion del inventario", "Ventas e Inventario",
"Validar stock inmediatamente despues de vender"            ),
]

REPORTS = [
    "Inventario general actualizado",
    "Productos con stock bajo",
    "Ventas diarias, semanales y mensuales",
    "Ventas por producto",
    "Ventas por metodo de pago",
    "Ventas por empleado",
    "Productos mas vendidos",
    "Productos menos vendidos",
    "Entradas de mercancia",
    "Clientes frecuentes",
    "Resumen de utilidades",
    "Productos devueltos o cancelados",
    "Productos disponibles por categoria",
    "Productos en oferta",
    "Metodos de pago mas utilizados",
    "Productos mas vendidos ultimo mes",
    "Ventas ultimos tres dias",
    "Productos de proveedor especifico",
    "Productos comprados mas de una vez por cliente",
    "Productos vendidos por categoria ultimo mes",
    "Productos con precio superior y existencias",
    "Producto con mayor descuento vigente",
    "Compras por ciudad o region",
    "Productos no vendidos ultimos tres meses",
]



def now_text():
    return datetime.now().strftime(DATETIME_FMT)



def today_text():
    return date.today().strftime(DATE_FMT)



def date_offset(days):
    return (date.today() + timedelta(days=days)).strftime(DATE_FMT)



def hash_password(password):
    return hashlib.sha256(password.encode("utf-8")).hexdigest()



def money(value):
    try:
        return f"${float(value):,.2f}"
    except Exception:
        return "$0.00"



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
        base = os.path.join(os.path.dirname(os.path.abspath(__file__)), IMAGE_DIR)
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



class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"{APP_TITLE} v{APP_VERSION}")
        self.geometry("1280x780")
        self.minsize(1120, 680)
        self.db = Database(DB_NAME)
        self.user = None
        self.productos_ui = None
        self.selected_customer_id = None
        self.selected_supplier_id = None
        self.selected_employee_id = None
        self.selected_promotion_id = None
        self.cart = []
        self.protocol("WM_DELETE_WINDOW"          , self.on_close)


    def on_close(self):
        try:
            self.db.close()
        finally:
            self.destroy()

   
    def show_main(self):
        self.clear_window()
        top = ttk.Frame(self, padding=(10, 8))
        top.pack(fill="x")
        ttk.Label(top, text=f"Mis trapitos | Usuario: {self.user['name']} | Rol: {self.user['role']}", font=("Arial", 12, "bold")).pack(side="left")
        ttk.Button(top, text="Salir", command=self.show_login).pack(side="right")
        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=10, pady=10)
        self.make_products_tab(nb)
        self.make_sales_tab(nb)
        self.make_customers_tab(nb)
        self.make_suppliers_tab(nb)
        self.make_employees_tab(nb)
        self.make_promotions_tab(nb)
        self.make_returns_tab(nb)
        self.make_reports_tab(nb)
        self.make_traceability_tab(nb)

    def clear_window(self):
        for child in self.winfo_children():
            child.destroy()
        self.productos_ui = None

    def add_labeled_entry(self, parent, text, row, column, width=26, default=""):
        ttk.Label(parent, text=text).grid(row=row, column=column, sticky="e", padx=4, pady=3)
        entry = ttk.Entry(parent, width=width)
        entry.grid(row=row, column=column + 1, sticky="w", padx=4, pady=3)
        if default:
            entry.insert(0, default)
        return entry

    def make_tree(self, parent, columns, height=12):
        container = ttk.Frame(parent)
        container.pack(fill="both", expand=True)
        tree = ttk.Treeview(container, columns=columns, show="headings", height=height)
        yscroll = ttk.Scrollbar(container, orient="vertical", command=tree.yview)
        xscroll = ttk.Scrollbar(container, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
        tree.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")
        xscroll.grid(row=1, column=0, sticky="ew")
        container.rowconfigure(0, weight=1)
        container.columnconfigure(0, weight=1)
        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=130, anchor="w")
        return tree
    def tree_clear(self, tree):
        for item in tree.get_children():
            tree.delete(item)

    def set_entries(self, entries, values):
        for entry, value in zip(entries, values):
            entry.delete(0, tk.END)
            entry.insert(0, "" if value is None else str(value))

    def make_products_tab(self, nb):
        self.productos_ui = ProductosUI(nb, self.db)
        nb.add(self.productos_ui, text="Productos")

    def refresh_products(self):
        """Actualiza productos tras una venta, devolucion o cancelacion."""
        if self.productos_ui is not None:
            self.productos_ui.actualizar_inventario()

    def make_sales_tab(self, nb):
        tab = ttk.Frame(nb, padding=10)
        nb.add(tab, text="Ventas")
        form = ttk.LabelFrame(tab, text="Nueva venta", padding=10)
        form.pack(fill="x")
        self.sale_customer_id = self.add_labeled_entry(form, "ID cliente", 0, 0)
        ttk.Label(form, text=f"Empleado: {self.user['name']} (ID {self.user['id']})").grid(row=0,
column=2, columnspan=2, sticky="w")
        ttk.Label(form, text="Metodo de pago").grid(row=1, column=0, sticky="e", padx=4, pady=3)
        self.sale_payment = ttk.Combobox(form, values=PAYMENT_METHODS, state="readonly", width=24)
        self.sale_payment.grid(row=1, column=1, sticky="w", padx=4, pady=3)
        self.sale_payment.set(PAYMENT_METHODS[0])
        self.sale_discount = self.add_labeled_entry(form, "Descuento venta %", 1, 2, default="0")
        self.sale_product_code = self.add_labeled_entry(form, "Codigo producto", 2, 0)
        self.sale_quantity = self.add_labeled_entry(form, "Cantidad", 2, 2, default="1")
        ttk.Button(form, text="Agregar al carrito"            , command=self.add_cart_item).grid(row=3,
column=0, pady=8)
        ttk.Button(form, text="Registrar venta", command=self.register_sale_ui).grid(row=3,
column=1, pady=8)
        ttk.Button(form, text="Vaciar carrito", command=self.clear_cart).grid(row=3, column=2,
pady=8)
        body = ttk.Frame(tab)
        body.pack(fill="both", expand=True, pady=8)
        cart_frame = ttk.LabelFrame(body, text="Carrito", padding=5)
        cart_frame.pack(side="left", fill="both", expand=True, padx=(0, 5))
        self.cart_tree = self.make_tree(cart_frame, ("id", "codigo", "producto", "cantidad",
"precio", "promo", "subtotal"), height=14)
        ticket_frame = ttk.LabelFrame(body, text="Ticket", padding=5)
        ticket_frame.pack(side="right", fill="both", expand=True, padx=(5, 0))
        self.ticket_text = tk.Text(ticket_frame, height=16, wrap="word")
        self.ticket_text.pack(fill="both", expand=True)

    def add_cart_item(self):
        try:
            code = self.sale_product_code.get().strip()
            qty = int(self.sale_quantity.get() or 1)
            product = self.db.one("SELECT * FROM products WHERE code=?", (code,))
            if not product:
                raise ValueError("No existe producto con ese codigo."                 )
            if qty <= 0:
                raise ValueError("Cantidad no valida.")
            current = sum(int(item["quantity"]) for item in self.cart if int(item["product_id"]) == int(product["id"]))
            if current + qty > int(product["stock"]):
                raise ValueError("Stock insuficiente.")
            for item in self.cart:
                if int(item["product_id"]) == int(product["id"]):
                    item["quantity"] += qty
                    break
            else:
                self.cart.append({"product_id": product["id"], "quantity": qty})
            self.sale_product_code.delete(0, tk.END)
            self.sale_quantity.delete(0, tk.END)
            self.sale_quantity.insert(0, "1")
            self.refresh_cart()
        except Exception as e:
            messagebox.showerror("Carrito", str(e))

    def refresh_cart(self):
        self.tree_clear(self.cart_tree)
        subtotal = 0.0
        for item in self.cart:
            product = self.db.one("SELECT * FROM products WHERE id=?", (item["product_id"],))
            if not product:
                continue
            promo = self.db.active_promotion_percent(product["id"])
            line = float(product["sale_price"]) * int(item["quantity"]) * (1 - promo / 100)
            subtotal += line
            self.cart_tree.insert("", tk.END, values=(product["id"], product["code"],
product["name"], item["quantity"], money(product["sale_price"]), f"{promo:g}%", money(line)))
        try:
            discount = float(self.sale_discount.get() or 0)
        except Exception:
            discount = 0
        total = subtotal * (1 - discount / 100)
        self.ticket_text.delete("1.0", tk.END)
        self.ticket_text.insert(tk.END, f"Subtotal con promociones: {money(subtotal)}\n")
        self.ticket_text.insert(tk.END, f"Descuento general: {discount:g}%\n")
        self.ticket_text.insert(tk.END, f"Total estimado: {money(total)}\n")

    def register_sale_ui(self):
        try:
            customer = self.sale_customer_id.get().strip()
            customer_id = int(customer) if customer else None
            sale_id, subtotal, discount_amount, total = self.db.register_sale(customer_id,
int(self.user["id"]), self.sale_payment.get(), float(self.sale_discount.get() or 0), self.cart)
            self.ticket_text.delete("1.0", tk.END)
            self.ticket_text.insert(tk.END, f"VENTA REGISTRADA\nTicket: {sale_id}\nFecha: {now_text()}\nSubtotal: {money(subtotal)}\nDescuento: {money(discount_amount)}\nTotal: {money(total)}\nMetodo: {self.sale_payment.get()}\n")
            self.clear_cart(True)
            self.refresh_products()
            messagebox.showinfo("Venta", f"Venta registrada con ticket                  {sale_id}.")
        except Exception as e:
            messagebox.showerror("Venta", str(e))

    def clear_cart(self, keep_ticket=False):
        self.cart = []
        self.tree_clear(self.cart_tree)
        if not keep_ticket:
            self.ticket_text.delete("1.0", tk.END)

    def make_customers_tab(self, nb):
        tab = ttk.Frame(nb, padding=10)
        nb.add(tab, text="Clientes")
        form = ttk.LabelFrame(tab, text="Cliente", padding=10)
        form.pack(fill="x")
        self.c_name = self.add_labeled_entry(form, "Nombre", 0, 0)
        self.c_phone = self.add_labeled_entry(form, "Telefono", 0, 2)
        self.c_email = self.add_labeled_entry(form, "Correo", 1, 0)
        self.c_address = self.add_labeled_entry(form, "Direccion", 1, 2)
        self.c_region = self.add_labeled_entry(form, "Ciudad/region", 2, 0)
        self.c_preferences = self.add_labeled_entry(form, "Preferencias", 2, 2)
        ttk.Button(form, text="Guardar cliente", command=self.save_customer_ui).grid(row=3,
column=0, pady=8)
        ttk.Button(form, text="Limpiar", command=self.clear_customer_form                  ).grid(row=3, column=1,
pady=8)
        ttk.Button(form, text="Ver historial", command=self.show_customer_history).grid(row=3,
column=2, pady=8)
        ttk.Button(form, text="Correo profesional"            , command=self.show_customer_email).grid(row=3,
column=3, pady=8)
        table = ttk.LabelFrame(tab, text="Clientes registrados", padding=5)
        table.pack(fill="both", expand=True, pady=8)
        self.customers_tree = self.make_tree(table, ("id", "nombre", "telefono", "correo", "region",
"preferencias"), height=16)
        self.customers_tree.bind("<<TreeviewSelect>>", self.load_customer_selected)
        self.refresh_customers       ()

    def save_customer_ui(self):
        try:
            if not self.c_name.get().strip():
                raise ValueError("El nombre es obligatorio.")
            data = (self.c_name.get().strip(), self.c_phone.get().strip(),
self.c_email.get().strip(), self.c_address.get().strip(), self.c_region.get().strip(),
self.c_preferences.get().strip())
            self.selected_customer_id = self.db.save_customer(self.selected_customer_id, data)
            self.refresh_customers()
            messagebox.showinfo("Clientes", "Cliente guardado.")
        except Exception as e:
            messagebox.showerror("Clientes", str(e))

    def refresh_customers(self):
        rows = self.db.query("SELECT id, name AS nombre, phone AS telefono, email AS correo, city_region AS region, preferences AS preferencias FROM customers ORDER BY id DESC"                     )
        self.tree_clear(self.customers_tree)
        for row in rows:
            self.customers_tree.insert("", tk.END, values=[row[key] for key in row.keys()])

    def load_customer_selected(self, event=None):
        sel = self.customers_tree.selection()
        if not sel:
            return
        customer_id = self.customers_tree.item(sel[0], "values")[0]
        row = self.db.one("SELECT * FROM customers WHERE id=?", (customer_id,))
        if not row:
            return
        self.selected_customer_id = row["id"]
        self.set_entries([self.c_name, self.c_phone, self.c_email, self.c_address, self.c_region,
self.c_preferences], [row["name"], row["phone"], row["email"], row["address"], row["city_region"],
row["preferences"]])

    def clear_customer_form(self):
        self.selected_customer_id = None
        for entry in [self.c_name, self.c_phone, self.c_email, self.c_address, self.c_region,
self.c_preferences]:
            entry.delete(0, tk.END)

    def show_customer_history(self):
        try:
            if not self.selected_customer_id:
                raise ValueError("Selecciona un cliente.")
            rows = self.db.customer_history(self.selected_customer_id)
            win = tk.Toplevel(self)
            win.title("Historial de cliente")
            text = tk.Text(win, width=105, height=28)
            text.pack(fill="both", expand=True, padx=10, pady=10)
            if not rows:
                text.insert(tk.END, "Sin compras registradas.")
            for row in rows:
                text.insert(tk.END, f"Venta {row['venta']} | {row['fecha']} | {row['codigo']} {row['producto']} | Cantidad {row['cantidad']} | Linea {money(row['total_linea'])} | Total venta {money(row['total_venta'])} | {row['estado']}\n")
        except Exception as e:
            messagebox.showerror("Historial", str(e))

    def build_customer_email_content(self, customer_id):
        customer = self.db.one("SELECT * FROM customers WHERE id=?", (customer_id,))
        if not customer:
            raise ValueError("Cliente no encontrado.")
        stats = self.db.one("SELECT COUNT(*) AS compras, COALESCE(SUM(total),0) AS total, MAX(sale_datetime) AS ultima FROM sales WHERE customer_id=? AND status='ACTIVA'", (customer_id,))
        favorite = self.db.one("""SELECT p.name AS producto, SUM(si.quantity) AS piezas FROM sales s
JOIN sale_items si ON si.sale_id=s.id JOIN products p ON p.id=si.product_id WHERE s.customer_id=?
AND s.status='ACTIVA' GROUP BY p.id ORDER BY piezas DESC LIMIT 1""", (customer_id,))
        name = customer["name"] or "cliente"
        first_name = name.split()[0] if name.split() else name
        preferences = customer["preferences"] or ""
        compras = int(stats["compras"] or 0) if stats else 0
        total = float(stats["total"] or 0) if stats else 0
        ultima = stats["ultima"] if stats else ""
        subject = "Gracias por su preferencia en Mis trapitos"
        lines = []
        lines.append(f"Estimado/a {first_name}:")
        lines.append("")
        lines.append("Esperamos que se encuentre muy bien. En Mis trapitos queremos agradecerle sinceramente su preferencia y la confianza que ha depositado en nuestra tienda.")
        if compras > 0:
            lines.append(f"De acuerdo con su historial, contamos con {compras} compra(s) registrada(s) a su nombre, por un total acumulado de {money(total)}.")
            if ultima:
                lines.append(f"Su compra mas reciente fue registrada el                   {ultima}.")
        if favorite:
            lines.append(f"Tambien identificamos que uno de los productos que mas ha adquirido es: {favorite['producto']}.")
        if preferences:
            lines.append(f"Tomaremos en cuenta sus preferencias registradas: {preferences}.")
        lines.append("Queremos invitarle a visitarnos nuevamente para conocer nuestras prendas disponibles, promociones vigentes y nuevas opciones de temporada."                )
        lines.append("Si desea consultar disponibilidad, tallas, colores o recibir atencion personalizada, con gusto podemos apoyarle por este mismo medio."                )
        lines.append("")
        lines.append("Quedamos atentos a cualquier duda o solicitud.")
        lines.append("")
        lines.append("Atentamente,")
        lines.append("Mis trapitos")
        lines.append("Tienda de ropa")
        return customer, subject, "\n".join(lines)

    def show_customer_email(self):
        try:
            if not self.selected_customer_id:
                raise ValueError("Selecciona un cliente.")
            customer, subject, body = self.build_customer_email_content(self.selected_customer_id)
            win = tk.Toplevel(self)
            win.title("Correo profesional para cliente")
            win.geometry("820x560")
            frame = ttk.Frame(win, padding=10)
            frame.pack(fill="both", expand=True)
            ttk.Label(frame, text=f"Para: {customer['email'] or 'Sin correo registrado'}",
font=("Arial", 10, "bold")).pack(anchor="w", pady=(0, 5))
            ttk.Label(frame, text="Asunto").pack(anchor="w")
            subject_entry = ttk.Entry(frame)
            subject_entry.pack(fill="x", pady=(0, 8))
            subject_entry.insert(0, subject)
            ttk.Label(frame, text="Mensaje").pack(anchor="w")
            text = tk.Text(frame, height=22, wrap="word")
            text.pack(fill="both", expand=True)
            text.insert(tk.END, body)
            buttons = ttk.Frame(frame)
            buttons.pack(fill="x", pady=8)

            def copy_email():
                content = f"Asunto: {subject_entry.get().strip()}\n\n{text.get('1.0', tk.END).strip()}"
                self.clipboard_clear()
                self.clipboard_append(content)
                messagebox.showinfo("Correo", "Correo copiado al portapapeles."                   )

            def open_email_client():
                email = customer["email"] or ""
                if not email.strip():
                    raise ValueError("El cliente no tiene correo registrado.")
                mailto = "mailto:" + urllib.parse.quote(email.strip()) + "?subject=" + urllib.parse.quote(subject_entry.get().strip()) + "&body=" + urllib.parse.quote(text.get("1.0",
tk.END).strip())
                webbrowser.open(mailto)

            def open_email_client_safe():
                try:
                    open_email_client()
                except Exception as e:
                    messagebox.showerror("Correo", str(e))

            ttk.Button(buttons, text="Copiar correo", command=copy_email).pack(side="left", padx=4)
            ttk.Button(buttons, text="Abrir en correo",
command=open_email_client_safe).pack(side="left", padx=4)
            ttk.Button(buttons, text="Cerrar", command=win.destroy).pack(side="right", padx=4)
        except Exception as e:
            messagebox.showerror("Correo", str(e))

    def make_suppliers_tab(self, nb):
        tab = ttk.Frame(nb, padding=10)
        nb.add(tab, text="Proveedores")
        form = ttk.LabelFrame(tab, text="Proveedor", padding=10)
        form.pack(fill="x")
        self.s_name = self.add_labeled_entry(form, "Nombre", 0, 0)
        self.s_phone = self.add_labeled_entry(form, "Telefono", 0, 2)
        self.s_address = self.add_labeled_entry(form, "Direccion", 1, 0)
        self.s_products = self.add_labeled_entry(form, "Productos suministrados"                    , 1, 2)
        self.s_last_order = self.add_labeled_entry(form, "Ultimo pedido", 2, 0,
default=today_text())
        ttk.Button(form, text="Guardar proveedor", command=self.save_supplier_ui).grid(row=3,
column=0, pady=8)
        ttk.Button(form, text="Limpiar", command=self.clear_supplier_form                  ).grid(row=3, column=1,
pady=8)
        table = ttk.LabelFrame(tab, text="Proveedores registrados", padding=5)
        table.pack(fill="both", expand=True, pady=8)
        self.suppliers_tree = self.make_tree(table, ("id", "nombre", "telefono", "direccion",
"suministra", "ultimo_pedido"), height=16)
        self.suppliers_tree.bind("<<TreeviewSelect>>"             , self.load_supplier_selected)
        self.refresh_suppliers       ()

    def save_supplier_ui(self):
        try:
            if not self.s_name.get().strip():
                raise ValueError("El nombre es obligatorio.")
            data = (self.s_name.get().strip(), self.s_phone.get().strip(),
self.s_address.get().strip(), self.s_products.get().strip(), self.s_last_order.get().strip() or
today_text())
            self.selected_supplier_id = self.db.save_supplier(self.selected_supplier_id, data)
            self.refresh_suppliers()
            messagebox.showinfo("Proveedores", "Proveedor guardado.")
        except Exception as e:
            messagebox.showerror("Proveedores", str(e))

    def refresh_suppliers(self):
        rows = self.db.query("SELECT id, name AS nombre, phone AS telefono, address AS direccion, products_supplied AS suministra, last_order_date AS ultimo_pedido FROM suppliers ORDER BY id DESC"                        )
        self.tree_clear(self.suppliers_tree)
        for row in rows:
            self.suppliers_tree.insert("", tk.END, values=[row[key] for key in row.keys()])

    def load_supplier_selected(self, event=None):
        sel = self.suppliers_tree.selection()
        if not sel:
            return
        supplier_id = self.suppliers_tree.item(sel[0], "values")[0]
        row = self.db.one("SELECT * FROM suppliers WHERE id=?", (supplier_id,))
        if not row:
            return
        self.selected_supplier_id = row["id"]
        self.set_entries([self.s_name, self.s_phone, self.s_address, self.s_products,
self.s_last_order], [row["name"], row["phone"], row["address"], row["products_supplied"],
row["last_order_date"]])

    def clear_supplier_form(self):
        self.selected_supplier_id = None
        for entry in [self.s_name, self.s_phone, self.s_address, self.s_products,
self.s_last_order]:
            entry.delete(0, tk.END)
        self.s_last_order.insert(0, today_text())

    def make_employees_tab(self, nb):
        tab = ttk.Frame(nb, padding=10)
        nb.add(tab, text="Empleados")
        form = ttk.LabelFrame(tab, text="Empleado", padding=10)
        form.pack(fill="x")
        self.e_name = self.add_labeled_entry(form, "Nombre", 0, 0)
        self.e_username = self.add_labeled_entry(form, "Usuario", 0, 2)
        self.e_password = self.add_labeled_entry(form, "Contraseña", 1, 0)
        self.e_role = self.add_labeled_entry(form, "Rol", 1, 2)
        ttk.Button(form, text="Guardar empleado", command=self.save_employee_ui).grid(row=2,
column=0, pady=8)
        ttk.Button(form, text="Limpiar", command=self.clear_employee_form                  ).grid(row=2, column=1,
pady=8)
        table = ttk.LabelFrame(tab, text="Empleados registrados", padding=5)
        table.pack(fill="both", expand=True, pady=8)
        self.employees_tree = self.make_tree(table, ("id", "nombre", "usuario", "rol"), height=16)
        self.employees_tree.bind("<<TreeviewSelect>>", self.load_employee_selected)
        self.refresh_employees       ()

    def save_employee_ui(self):
        try:
            if not self.e_name.get().strip() or not self.e_username.get().strip():
                raise ValueError("Nombre y usuario son obligatorios.")
            self.selected_employee_id = self.db.save_employee(self.selected_employee_id,
self.e_name.get().strip(), self.e_username.get().strip(), self.e_password.get().strip(),
self.e_role.get().strip() or "Ventas")
            self.refresh_employees()
            messagebox.showinfo("Empleados", "Empleado guardado.")
        except Exception as e:
            messagebox.showerror("Empleados", str(e))

    def refresh_employees(self):
        rows = self.db.query("SELECT id, name AS nombre, username AS usuario, role AS rol FROM employees ORDER BY id DESC")
        self.tree_clear(self.employees_tree)
        for row in rows:
            self.employees_tree.insert("", tk.END, values=[row[key] for key in row.keys()])

    def load_employee_selected(self, event=None):
        sel = self.employees_tree.selection()
        if not sel:
            return
        employee_id = self.employees_tree.item(sel[0], "values")[0]
        row = self.db.one("SELECT * FROM employees WHERE id=?", (employee_id,))
        if not row:
            return
        self.selected_employee_id = row["id"]
        self.set_entries([self.e_name, self.e_username, self.e_password, self.e_role], [row["name"],
row["username"], "", row["role"]])

    def clear_employee_form(self):
        self.selected_employee_id = None
        for entry in [self.e_name, self.e_username, self.e_password, self.e_role]:
            entry.delete(0, tk.END)

    def make_promotions_tab(self, nb):
        tab = ttk.Frame(nb, padding=10)
        nb.add(tab, text="Promociones")
        form = ttk.LabelFrame(tab, text="Promocion", padding=10)
        form.pack(fill="x")
        self.pr_product = self.add_labeled_entry(form, "ID producto", 0, 0)
        self.pr_discount = self.add_labeled_entry(form, "Descuento %", 0, 2)
        self.pr_start = self.add_labeled_entry(form, "Inicio", 1, 0, default=today_text())
        self.pr_end = self.add_labeled_entry(form, "Fin", 1, 2, default=date_offset(30))
        ttk.Button(form, text="Guardar promocion", command=self.save_promotion_ui).grid(row=2,
column=0, pady=8)
        ttk.Button(form, text="Limpiar", command=self.clear_promotion_form).grid(row=2, column=1,
pady=8)
        table = ttk.LabelFrame(tab, text="Promociones registradas", padding=5)
        table.pack(fill="both", expand=True, pady=8)
        self.promotions_tree = self.make_tree(table, ("id", "producto_id", "codigo", "producto",
"descuento", "inicio", "fin"), height=16)
        self.promotions_tree.bind("<<TreeviewSelect>>", self.load_promotion_selected)
        self.refresh_promotions()
    def save_promotion_ui(self):
        try:
            product_id = int(self.pr_product.get())
            discount = float(self.pr_discount.get() or 0)
            if discount < 0 or discount > 100:
                raise ValueError("Descuento no valido.")
            if not self.db.one("SELECT id FROM products WHERE id=?", (product_id,)):
                raise ValueError("Producto no encontrado.")
            self.selected_promotion_id = self.db.save_promotion(self.selected_promotion_id,
product_id, discount, self.pr_start.get().strip() or today_text(), self.pr_end.get().strip() or
today_text())
            self.refresh_promotions()
            messagebox.showinfo("Promociones", "Promocion guardada.")
        except Exception as e:
            messagebox.showerror("Promociones", str(e))

    def refresh_promotions(self):
        rows = self.db.query("""SELECT pr.id, pr.product_id AS producto_id, p.code AS codigo, p.name
AS producto, pr.discount_percent AS descuento, pr.start_date AS inicio, pr.end_date AS fin FROM
promotions pr JOIN products p ON p.id=pr.product_id ORDER BY pr.id DESC"""                  )
        self.tree_clear(self.promotions_tree)
        for row in rows:
            self.promotions_tree.insert("", tk.END, values=[row[key] for key in row.keys()])

    def load_promotion_selected(self, event=None):
        sel = self.promotions_tree.selection()
        if not sel:
            return
        promotion_id = self.promotions_tree.item(sel[0], "values")[0]
        row = self.db.one("SELECT * FROM promotions WHERE id=?", (promotion_id,))
        if not row:
            return
        self.selected_promotion_id = row["id"]
        self.set_entries([self.pr_product, self.pr_discount, self.pr_start, self.pr_end],
[row["product_id"], row["discount_percent"], row["start_date"], row["end_date"]])

    def clear_promotion_form(self):
        self.selected_promotion_id = None
        for entry in [self.pr_product, self.pr_discount, self.pr_start, self.pr_end]:
            entry.delete(0, tk.END)
        self.pr_start.insert(0, today_text())
        self.pr_end.insert(0, date_offset(30))

    def make_returns_tab(self, nb):
        tab = ttk.Frame(nb, padding=10)
        nb.add(tab, text="Devoluciones y cancelaciones")
        form = ttk.LabelFrame(tab, text="Registro", padding=10)
        form.pack(fill="x")
        self.r_sale = self.add_labeled_entry(form, "Venta para devolucion", 0, 0)
        self.r_product = self.add_labeled_entry(form, "ID producto", 0, 2)
        self.r_quantity = self.add_labeled_entry(form, "Cantidad", 1, 0, default="1")
        self.r_reason = self.add_labeled_entry(form, "Motivo devolucion", 1, 2)
        ttk.Button(form, text="Registrar devolucion", command=self.return_item_ui).grid(row=2,
column=0, pady=8)
        self.cancel_sale_entry = self.add_labeled_entry(form, "Venta a cancelar"                    , 3, 0)
        self.cancel_reason = self.add_labeled_entry(form, "Motivo cancelacion", 3, 2)
        ttk.Button(form, text="Cancelar venta", command=self.cancel_sale_ui).grid(row=4, column=0,
pady=8)
        body = ttk.Frame(tab)
        body.pack(fill="both", expand=True, pady=8)
        returns_frame = ttk.LabelFrame(body, text="Devoluciones", padding=5)
        returns_frame.pack(side="left", fill="both", expand=True, padx=(0, 5))
        self.returns_tree = self.make_tree(returns_frame, ("id", "venta", "producto", "cantidad",
"fecha", "motivo"), height=14)
        cancellations_frame = ttk.LabelFrame(body, text="Cancelaciones", padding=5)
        cancellations_frame.pack(side="right", fill="both", expand=True, padx=(5, 0))
        self.cancellations_tree = self.make_tree(cancellations_frame, ("id", "venta", "fecha",
"motivo"), height=14)
        self.refresh_returns()

    def return_item_ui(self):
        try:
            self.db.return_item(int(self.r_sale.get()), int(self.r_product.get()),
int(self.r_quantity.get()), self.r_reason.get().strip())
            self.refresh_returns()
            self.refresh_products()
            messagebox.showinfo("Devolucion", "Devolucion registrada."                 )
        except Exception as e:
            messagebox.showerror("Devolucion", str(e))

    def cancel_sale_ui(self):
        try:
            self.db.cancel_sale(int(self.cancel_sale_entry.get()), self.cancel_reason.get().strip())
            self.refresh_returns()
            self.refresh_products()
            messagebox.showinfo("Cancelacion", "Venta cancelada.")
        except Exception as e:
            messagebox.showerror("Cancelacion", str(e))

    def refresh_returns(self):
        rows = self.db.query("""SELECT r.id, r.sale_id AS venta, p.name AS producto, r.quantity AS
cantidad, r.return_datetime AS fecha, r.reason AS motivo FROM returns r JOIN products p ON
p.id=r.product_id ORDER BY r.id DESC"""         )
        self.tree_clear(self.returns_tree)
        for row in rows:
            self.returns_tree.insert("", tk.END, values=[row[key] for key in row.keys()])
        rows = self.db.query("SELECT id, sale_id AS venta, cancel_datetime AS fecha, reason AS motivo FROM cancellations ORDER BY id DESC"          )
        self.tree_clear(self.cancellations_tree)
        for row in rows:
            self.cancellations_tree.insert("", tk.END, values=[row[key] for key in row.keys()])

    def make_reports_tab(self, nb):
        tab = ttk.Frame(nb, padding=10)
        nb.add(tab, text="Reportes")
        controls = ttk.LabelFrame(tab, text="Consulta", padding=10)
        controls.pack(fill="x")
        ttk.Label(controls, text="Reporte").grid(row=0, column=0, padx=4, pady=4, sticky="e")
        self.report_combo = ttk.Combobox(controls, values=REPORTS, state="readonly", width=48)
        self.report_combo.grid(row=0, column=1, padx=4, pady=4, sticky="w")
        self.report_combo.set(REPORTS[0])
        self.report_param = self.add_labeled_entry            (controls, "Parametro", 0, 2, width=30)
        ttk.Button(controls, text="Ejecutar", command=self.run_report).grid(row=0, column=4, padx=4,
pady=4)
        ttk.Button(controls, text="Exportar CSV", command=self.export_report_csv).grid(row=0,
column=5, padx=4, pady=4)
        self.report_hint = ttk.Label(controls, text="Parametro se usa en reportes por categoria, proveedor, cliente, precio o stock bajo.")
        self.report_hint.grid(row=1, column=0, columnspan=6, sticky="w", padx=4)
        table = ttk.LabelFrame(tab, text="Resultado", padding=5)
        table.pack(fill="both", expand=True, pady=8)
        self.report_tree = self.make_tree(table, ("resultado",), height=18)
        self.last_report_rows = []
        self.run_report()

    def run_report(self):
        try:
            rows = self.db.report(self.report_combo.get(), self.report_param.get())
            self.last_report_rows = rows
            for item in self.report_tree.get_children():
                self.report_tree.delete(item)
            if not rows:
                self.report_tree["columns"] = ("mensaje",)
                self.report_tree.heading("mensaje", text="mensaje")
                self.report_tree.column("mensaje", width=900)
                self.report_tree.insert("", tk.END, values=("Sin resultados",))
                return
            columns = list(rows[0].keys())
            self.report_tree["columns"] = columns
            for col in columns:
                self.report_tree.heading(col, text=col)
                self.report_tree.column(col, width=140, anchor="w")
            for row in rows:
                self.report_tree.insert("", tk.END, values=[row[col] for col in columns])
        except Exception as e:
            messagebox.showerror("Reporte", str(e))

    def export_report_csv(self):
        rows = self.last_report_rows
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")])
        if not path:
            return
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            if rows:
                writer.writerow(rows[0].keys())
                for row in rows:
                    writer.writerow([row[key] for key in row.keys()])
        messagebox.showinfo("Exportar", f"Reporte exportado en:\n{path}")

    def make_traceability_tab(self, nb):
        tab = ttk.Frame(nb, padding=10)
        nb.add(tab, text="Rastreabilidad")
        upper = ttk.LabelFrame(tab, text="Administracion de configuracion", padding=5)
        upper.pack(fill="x")
        config_tree = self.make_tree(upper, ("id", "elemento", "valor", "estado"), height=5)
        for item in CONFIG_ITEMS:
            config_tree.insert("", tk.END, values=item)
        lower = ttk.LabelFrame(tab, text="Matriz de rastreabilidad", padding=5)
        lower.pack(fill="both", expand=True, pady=8)
        trace_tree = self.make_tree(lower, ("id", "requerimiento", "modulo", "prueba"), height=18)
        for item in TRACEABILITY:
            trace_tree.insert("", tk.END, values=item)
        ttk.Button(tab, text="Ejecutar pruebas basicas",
command=self.run_basic_tests).pack(anchor="w", pady=5)

    def run_basic_tests(self):
        try:
            product = self.db.one("SELECT * FROM products ORDER BY stock DESC LIMIT 1")
            employee = self.db.one("SELECT * FROM employees ORDER BY id LIMIT 1")
            customer = self.db.one("SELECT * FROM customers ORDER BY id LIMIT 1")
            if not product or not employee:
                raise ValueError("Faltan productos o empleados para probar.")
            initial_stock = int(product["stock"])
            if initial_stock < 1:
                raise ValueError("No hay stock suficiente para la prueba."                  )
            sale_id, subtotal, discount_amount, total = self.db.register_sale(customer["id"] if
customer else None, employee["id"], PAYMENT_METHODS[0], 0, [{"product_id": product["id"],
"quantity": 1}])
            after = self.db.scalar("SELECT stock FROM products WHERE id=?", (product["id"],))
            movement = self.db.one("SELECT id FROM inventory_movements WHERE related_sale_id=? AND movement_type='SALIDA'", (sale_id,))
            if after != initial_stock - 1 or not movement:
                raise ValueError("La prueba de inventario no paso.")
            self.refresh_products()
            messagebox.showinfo("Pruebas", f"Pruebas correctas. Venta de prueba: {sale_id}. Stock {initial_stock} -> {after}.")
        except Exception as e:
            messagebox.showerror("Pruebas", str(e))




if __name__ == "__main__":
    app = App()
    app.mainloop()

