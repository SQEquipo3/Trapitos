"""Repositorio de clientes.

Todas las funciones reciben el objeto Database (data/database.py).
"""


def listar(db):
    """Filas para la tabla de clientes (el orden de columnas importa a la UI)."""
    return db.query(
        """SELECT id, name AS nombre, phone AS telefono, email AS correo,
                  city_region AS region, preferences AS preferencias
           FROM customers ORDER BY id DESC"""
    )


def obtener_por_id(db, customer_id):
    return db.one("SELECT * FROM customers WHERE id=?", (customer_id,))


def existe(db, customer_id):
    return db.one("SELECT id FROM customers WHERE id=?", (customer_id,)) is not None


def guardar(db, customer_id, data):
    """Alta (customer_id=None) o edición. Regresa el id del cliente."""
    return db.save_customer(customer_id, data)


def eliminar(db, customer_id):
    """Borra el cliente. Falla (IntegrityError) si ya tiene ventas."""
    db.execute("DELETE FROM customers WHERE id=?", (customer_id,))


def historial(db, customer_id):
    return db.customer_history(customer_id)


def resumen_compras(db, customer_id):
    """Fila con compras, total acumulado y fecha de la última compra activa."""
    return db.one(
        """SELECT COUNT(*) AS compras, COALESCE(SUM(total),0) AS total, MAX(sale_datetime) AS ultima
           FROM sales WHERE customer_id=? AND status='ACTIVA'""",
        (customer_id,),
    )


def producto_favorito(db, customer_id):
    """Fila con el producto que más ha comprado el cliente (o None)."""
    return db.one(
        """SELECT p.name AS producto, SUM(si.quantity) AS piezas FROM sales s
           JOIN sale_items si ON si.sale_id=s.id JOIN products p ON p.id=si.product_id
           WHERE s.customer_id=? AND s.status='ACTIVA' GROUP BY p.id ORDER BY piezas DESC LIMIT 1""",
        (customer_id,),
    )