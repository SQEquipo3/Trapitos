"""Repositorio de productos. """


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


def obtener_por_codigo(db, code):
    return db.one("SELECT * FROM products WHERE code=?", (code,))


def proveedor_existe(db, supplier_id):
    return db.one("SELECT id FROM suppliers WHERE id=?", (supplier_id,)) is not None


def guardar(db, product_id, data):
    """Alta (product_id=None) o edición. Regresa el id del producto.

    Delega en Database.save_product, que también registra el movimiento de
    inventario. Así el comportamiento es idéntico al de antes.
    """
    return db.save_product(product_id, data)