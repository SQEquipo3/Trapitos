"""Repositorio de proveedores.

Todas las funciones reciben el objeto Database (data/database.py).
"""


def listar(db):
    """Filas para la tabla de proveedores (el orden de columnas importa a la UI)."""
    return db.query(
        """SELECT id, name AS nombre, phone AS telefono, address AS direccion,
                  products_supplied AS suministra, last_order_date AS ultimo_pedido
           FROM suppliers ORDER BY id DESC"""
    )


def obtener_por_id(db, supplier_id):
    return db.one("SELECT * FROM suppliers WHERE id=?", (supplier_id,))


def existe(db, supplier_id):
    return db.one("SELECT id FROM suppliers WHERE id=?", (supplier_id,)) is not None


def guardar(db, supplier_id, data):
    """Alta (supplier_id=None) o edición. Regresa el id del proveedor."""
    return db.save_supplier(supplier_id, data)


def eliminar(db, supplier_id):
    """Borra el proveedor. Falla (IntegrityError) si tiene productos."""
    db.execute("DELETE FROM suppliers WHERE id=?", (supplier_id,))