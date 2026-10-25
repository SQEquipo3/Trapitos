"""Repositorio de productos y movimientos de inventario.

Todas las funciones reciben el objeto Database (data/database.py).
"""

from utils import now_text


def listar_inventario(db):
    """Filas para la tabla de inventario (el orden de columnas importa a la UI)."""
    return db.query(
        """SELECT p.id, p.code AS codigo, p.name AS producto, p.category AS categoria,
                  p.size AS talla, p.color, p.stock, p.sale_price AS precio,
                  COALESCE(s.name,'') AS proveedor
           FROM products p LEFT JOIN suppliers s ON s.id=p.supplier_id
           ORDER BY p.id DESC"""
    )


def obtener_por_id(db, product_id):
    return db.one("SELECT * FROM products WHERE id=?", (product_id,))


def con_mas_stock(db):
    return db.one("SELECT * FROM products ORDER BY stock DESC LIMIT 1")


def obtener_por_codigo(db, code):
    return db.one("SELECT * FROM products WHERE code=?", (code,))


def ajustar_stock(db, product_id, delta):
    """Suma `delta` (negativo para descontar) al stock del producto."""
    db.execute("UPDATE products SET stock = stock + ? WHERE id=?", (delta, product_id))


def registrar_movimiento(db, product_id, movement_type, quantity, reason, sale_id=None):
    db.execute(
        """INSERT INTO inventory_movements(product_id, movement_type, quantity, movement_datetime,
                                           reason, related_sale_id)
           VALUES(?,?,?,?,?,?)""",
        (product_id, movement_type, quantity, now_text(), reason, sale_id),
    )


def movimiento_de_venta(db, sale_id, movement_type):
    return db.one(
        "SELECT id FROM inventory_movements WHERE related_sale_id=? AND movement_type=?",
        (sale_id, movement_type),
    )


def proveedor_existe(db, supplier_id):
    return db.one("SELECT id FROM suppliers WHERE id=?", (supplier_id,)) is not None


def guardar(db, product_id, data):
    """Alta (product_id=None) o edición. Regresa el id del producto.

    El alta registra un movimiento ENTRADA y la edición un AJUSTE si cambió
    el stock, en la misma transacción que el producto.
    """
    with db.transaction():
        if product_id:
            old = db.one("SELECT stock FROM products WHERE id=?", (product_id,))
            db.execute(
                """UPDATE products SET code=?, name=?, category=?, size=?, color=?,
                          purchase_price=?, sale_price=?, stock=?, supplier_id=?, entry_date=?,
                          brand=?, season=?, image_path=?
                   WHERE id=?""",
                (*data, product_id),
            )
            if old and int(old["stock"]) != int(data[7]):
                registrar_movimiento(db, product_id, "AJUSTE", int(data[7]) - int(old["stock"]),
                                     "Actualizacion manual de inventario")
            return product_id
        cur = db.execute(
            """INSERT INTO products(code, name, category, size, color, purchase_price, sale_price,
                                    stock, supplier_id, entry_date, brand, season, image_path,
                                    created_at)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (*data, now_text()),
        )
        registrar_movimiento(db, cur.lastrowid, "ENTRADA", int(data[7]), "Alta inicial de producto")
        return cur.lastrowid