"""Repositorio de ventas."""


def registrar(db, customer_id, employee_id, metodo_pago, descuento, cart):
    """Guarda la venta, sus partidas, descuenta stock y registra movimientos.

    Delega en Database.register_sale, que lo hace todo en UNA transacción:
    si algo falla se revierte completo (no queda venta sin descontar stock).
    Regresa (sale_id, subtotal, monto_descuento, total).
    """
    return db.register_sale(customer_id, employee_id, metodo_pago, descuento, cart)


def obtener_fecha(db, sale_id):
    return db.scalar("SELECT sale_datetime FROM sales WHERE id=?", (sale_id,))


def cliente_existe(db, customer_id):
    # TODO: mover a repositories/clientes.py cuando se haga esa issue.
    return db.one("SELECT id FROM customers WHERE id=?", (customer_id,)) is not None