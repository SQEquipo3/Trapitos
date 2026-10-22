"""Repositorio de promociones.

Todas las funciones reciben el objeto Database (data/database.py).
"""


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
    return db.save_promotion(promotion_id, product_id, discount_percent, start_date, end_date)
