"""Datos de demostración opcionales para Mis trapitos."""

import os
from datetime import date, datetime, timedelta
from PIL import Image, ImageDraw

from config import DATE_FMT, DATETIME_FMT, PAYMENT_METHODS
from utils import hash_password, now_text

def date_offset(days):
    return (date.today() + timedelta(days=days)).strftime(DATE_FMT)

def create_sample_images(db):
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


def seed_examples(db):
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
        if not db.one("SELECT id FROM suppliers WHERE name=?", (row[0],)):
            db.execute("INSERT INTO suppliers(name, phone, address, products_supplied, last_order_date, created_at) VALUES(?,?,?,?,?,?)", (*row, now_text()))
    employees = [
        ("Administrador", "admin", "1234", "Propietario"),
        ("Ana Lopez", "ana", "1234", "Ventas"),
        ("Luis Perez", "luis", "1234", "Ventas"),
        ("Marta Ruiz", "marta", "1234", "Inventario"),
        ("Carla Diaz", "carla", "1234", "Contabilidad"),
    ]
    for name, username, password, role in employees:
        row = db.one("SELECT id FROM employees WHERE username=?", (username,))
        if not row:
            db.execute("INSERT INTO employees(name, username, password_hash, role, created_at) VALUES(?,?,?,?,?)", (name, username, hash_password(password), role, now_text()))
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
"Faldas y ofertas"),]
    for row in customers:
        if not db.one("SELECT id FROM customers WHERE email=?", (row[2],)):
            db.execute("INSERT INTO customers(name, phone, email, address, city_region, preferences, created_at) VALUES(?,?,?,?,?,?,?)", (*row, now_text()))
    supplier_ids = {row["name"]: row["id"] for row in db.query("SELECT id, name FROM suppliers")}
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
        existing = db.one("SELECT id FROM products WHERE code=?", (row[0],))
        if not existing:
            cur = db.execute("""INSERT INTO products(code, name, category, size, color,
purchase_price, sale_price, stock, supplier_id, entry_date, brand, season, image_path, created_at)
VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)"""         , (*row, now_text()))
            db.register_movement(cur.lastrowid, "ENTRADA", row[7], "Alta inicial de ejemplo"                        ,
None)
        else:
            default_image_names = ("camisa_roja.jpg", "pantalon_azul.jpg", "vestido_negro.jpg",
"falda_verde.jpg", "chamarra_cafe.jpg"         )
            current = db.one("SELECT image_path FROM products WHERE code=?", (row[0],))
            current_path = current["image_path"] if current else ""
            if current_path and os.path.basename(current_path) in default_image_names:
                db.execute("UPDATE products SET image_path='' WHERE code=?", (row[0],))
    product_ids = {row["code"]: row["id"] for row in db.query("SELECT id, code FROM products")}
    promo_defs = [("MT001", 10), ("MT002", 5), ("MT003", 15), ("MT004", 12), ("MT005", 8)]
    for code, discount in promo_defs:
        pid = product_ids.get(code)
        if pid and not db.one("SELECT id FROM promotions WHERE product_id=? AND discount_percent=?", (pid, discount)):
            db.execute("INSERT INTO promotions(product_id, discount_percent, start_date, end_date, created_at) VALUES(?,?,?,?,?)", (pid, discount, date_offset(-5), date_offset(30),
now_text()))
    if db.scalar("SELECT COUNT(*) FROM sales WHERE sale_datetime LIKE '2026-05-22 %' OR sale_datetime IS NOT NULL") < 5:
        seed_sales(db, product_ids, cancelled=False, count=5)
    if db.scalar("SELECT COUNT(*) FROM returns") < 5:
        seed_returns(db)
    if db.scalar("SELECT COUNT(*) FROM cancellations") < 5:
        seed_sales(db, product_ids, cancelled=True, count=5)


def seed_sales(db, product_ids, cancelled, count):
    customers = [row["id"] for row in db.query("SELECT id FROM customers ORDER BY id LIMIT 5")]
    employees = [row["id"] for row in db.query("SELECT id FROM employees ORDER BY id LIMIT 5")]
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
        sale_id, subtotal, discount_amount, total = db.register_sale(customer_id, employee_id,
PAYMENT_METHODS[i % len(PAYMENT_METHODS)], i * 2, cart)
        db.execute("UPDATE sales SET sale_datetime=? WHERE id=?", ((datetime.now() - timedelta(days=i)).strftime(DATETIME_FMT), sale_id))
        if cancelled:
            db.cancel_sale(sale_id, "Producto en buenas condiciones")


def seed_returns(db):
    candidates = db.query(
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
        returned = db.scalar("SELECT COALESCE(SUM(quantity),0) FROM returns WHERE sale_id=? AND product_id=?", (row["sale_id"], row["product_id"])) or 0
        if sold - returned > 0:
            db.return_item(row["sale_id"], row["product_id"], 1, "Producto Dañado")
            used += 1

