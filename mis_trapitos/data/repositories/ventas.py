"""Repositorio de ventas.

Todas las funciones reciben el objeto Database (data/database.py).
"""


def obtener_por_id(db, sale_id):
    return db.one("SELECT * FROM sales WHERE id=?", (sale_id,))


def obtener_fecha(db, sale_id):
    return db.scalar("SELECT sale_datetime FROM sales WHERE id=?", (sale_id,))


def partidas(db, sale_id):
    return db.query("SELECT * FROM sale_items WHERE sale_id=?", (sale_id,))


def cantidad_vendida(db, sale_id, product_id):
    return db.scalar(
        "SELECT COALESCE(SUM(quantity),0) FROM sale_items WHERE sale_id=? AND product_id=?",
        (sale_id, product_id),
    ) or 0


def insertar(db, fecha, customer_id, employee_id, metodo_pago, subtotal, descuento, monto, total):
    """Inserta la venta como ACTIVA. Regresa su id."""
    cur = db.execute(
        """INSERT INTO sales(sale_datetime, customer_id, employee_id, payment_method, subtotal,
                             sale_discount_percent, discount_amount, total, status)
           VALUES(?,?,?,?,?,?,?,?,?)""",
        (fecha, customer_id, employee_id, metodo_pago, subtotal, descuento, monto, total, "ACTIVA"),
    )
    return cur.lastrowid


def insertar_partida(db, sale_id, product_id, quantity, unit_price, promo, line_total):
    db.execute(
        """INSERT INTO sale_items(sale_id, product_id, quantity, unit_price,
                                  promo_discount_percent, line_total)
           VALUES(?,?,?,?,?,?)""",
        (sale_id, product_id, quantity, unit_price, promo, line_total),
    )


def marcar_cancelada(db, sale_id):
    db.execute("UPDATE sales SET status='CANCELADA' WHERE id=?", (sale_id,))
