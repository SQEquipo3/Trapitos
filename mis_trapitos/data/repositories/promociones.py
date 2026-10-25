"""Repositorio de promociones.

Todas las funciones reciben el objeto Database (data/database.py).
"""

from utils import now_text, today_text


def listar(db):
    """Filas para la tabla de promociones (el orden de columnas importa a la UI)."""
    return db.query(
        "SELECT pr.id, pr.product_id AS producto_id, p.code AS codigo, p.name "
        "AS producto, pr.discount_percent AS descuento, pr.start_date AS inicio, "
        "pr.end_date AS fin FROM promotions pr JOIN products p ON p.id=pr.product_id "
        "ORDER BY pr.id DESC"
    )


def obtener_por_id(db, promotion_id):
    return db.one("SELECT * FROM promotions WHERE id=?", (promotion_id,))


def guardar(db, promotion_id, product_id, discount_percent, start_date, end_date):
    """Alta (promotion_id=None) o edición. Regresa el id de la promoción."""
    if promotion_id:
        db.execute(
            "UPDATE promotions SET product_id=?, discount_percent=?, start_date=?, end_date=? WHERE id=?",
            (product_id, discount_percent, start_date, end_date, promotion_id),
        )
        return promotion_id
    cur = db.execute(
        """INSERT INTO promotions(product_id, discount_percent, start_date, end_date, created_at)
           VALUES(?,?,?,?,?)""",
        (product_id, discount_percent, start_date, end_date, now_text()),
    )
    return cur.lastrowid


def porcentaje_vigente(db, product_id):
    """Mayor descuento de las promociones vigentes hoy para el producto (0 si no hay)."""
    row = db.one(
        """SELECT MAX(discount_percent) AS discount FROM promotions
           WHERE product_id=? AND date(?) BETWEEN date(start_date) AND date(end_date)""",
        (product_id, today_text()),
    )
    return float(row["discount"] or 0)
