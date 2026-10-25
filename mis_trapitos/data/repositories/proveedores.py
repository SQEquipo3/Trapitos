"""Repositorio de proveedores.

Todas las funciones reciben el objeto Database (data/database.py).
"""

from utils import now_text


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
    if supplier_id:
        db.execute(
            "UPDATE suppliers SET name=?, phone=?, address=?, products_supplied=?, last_order_date=? WHERE id=?",
            (*data, supplier_id),
        )
        return supplier_id
    cur = db.execute(
        """INSERT INTO suppliers(name, phone, address, products_supplied, last_order_date, created_at)
           VALUES(?,?,?,?,?,?)""",
        (*data, now_text()),
    )
    return cur.lastrowid


def eliminar(db, supplier_id):
    """Borra el proveedor. Falla (IntegrityError) si tiene productos."""
    db.execute("DELETE FROM suppliers WHERE id=?", (supplier_id,))