"""Repositorio de devoluciones y cancelaciones.

Todas las funciones reciben el objeto Database (data/database.py).
"""


def listar_devoluciones(db):
    """Filas para la tabla de devoluciones (el orden de columnas importa a la UI)."""
    return db.query(
        "SELECT r.id, r.sale_id AS venta, p.name AS producto, r.quantity AS "
        "cantidad, r.return_datetime AS fecha, r.reason AS motivo "
        "FROM returns r JOIN products p ON p.id=r.product_id ORDER BY r.id DESC"
    )


def listar_cancelaciones(db):
    """Filas para la tabla de cancelaciones (el orden de columnas importa a la UI)."""
    return db.query(
        "SELECT id, sale_id AS venta, cancel_datetime AS fecha, reason AS motivo "
        "FROM cancellations ORDER BY id DESC"
    )


def cantidad_devuelta(db, sale_id, product_id):
    return db.scalar(
        "SELECT COALESCE(SUM(quantity),0) FROM returns WHERE sale_id=? AND product_id=?",
        (sale_id, product_id),
    ) or 0


def insertar_devolucion(db, sale_id, product_id, quantity, fecha, reason):
    db.execute(
        "INSERT INTO returns(sale_id, product_id, quantity, return_datetime, reason) VALUES(?,?,?,?,?)",
        (sale_id, product_id, quantity, fecha, reason),
    )


def insertar_cancelacion(db, sale_id, fecha, reason):
    db.execute(
        "INSERT INTO cancellations(sale_id, cancel_datetime, reason) VALUES(?,?,?)",
        (sale_id, fecha, reason),
    )
