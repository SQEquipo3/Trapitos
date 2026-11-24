"""Reglas de negocio de devoluciones y cancelaciones de ventas.

Las funciones reciben el objeto Database (data/database.py) y acceden a los
datos solo a través de los repositorios.
"""

from utils import now_text
from mis_trapitos.data.repositories import devoluciones as devoluciones_repo
from mis_trapitos.data.repositories import productos as productos_repo
from mis_trapitos.data.repositories import ventas as ventas_repo


def devolver(db, sale_id, product_id, quantity, reason):
    """Regresa al inventario piezas de una venta activa sin exceder lo vendido."""
    sale = ventas_repo.obtener_por_id(db, sale_id)
    if not sale:
        raise ValueError("Venta no encontrada.")
    if sale["status"] == "CANCELADA":
        raise ValueError("No se puede devolver sobre una venta cancelada.")
    sold_qty = ventas_repo.cantidad_vendida(db, sale_id, product_id)
    returned_qty = devoluciones_repo.cantidad_devuelta(db, sale_id, product_id)
    quantity = int(quantity)
    if quantity <= 0 or quantity > sold_qty - returned_qty:
        raise ValueError("Cantidad de devolucion no valida.")
    with db.transaction():
        devoluciones_repo.insertar_devolucion(db, sale_id, product_id, quantity, now_text(), reason)
        productos_repo.ajustar_stock(db, product_id, quantity)
        productos_repo.registrar_movimiento(db, product_id, "DEVOLUCION", quantity,
                                            reason or "Devolucion", sale_id)



def cancelar_venta(db, sale_id, reason):
    """Cancela la venta y repone solo las piezas que no se habían devuelto."""

    sale = ventas_repo.obtener_por_id(db, sale_id)

    if not sale:
        raise ValueError("Venta no encontrada.")

    if sale["status"] == "CANCELADA":
        raise ValueError("La venta ya esta cancelada.")

    # Agrupar las cantidades vendidas por producto.
    cantidades_vendidas = {}

    for item in ventas_repo.partidas(db, sale_id):
        product_id = int(item["product_id"])
        quantity = int(item["quantity"])

        cantidades_vendidas[product_id] = (
            cantidades_vendidas.get(product_id, 0) + quantity
        )

    with db.transaction():
        # Cada producto se procesa una sola vez.
        for product_id, sold_qty in cantidades_vendidas.items():

            returned_qty = int(
                devoluciones_repo.cantidad_devuelta(
                    db, sale_id, product_id
                )
            )

            # Reponer únicamente las piezas que todavía no se devolvieron.
            restore_qty = max(0, sold_qty - returned_qty)

            if restore_qty > 0:
                productos_repo.ajustar_stock(
                    db, product_id, restore_qty
                )

                productos_repo.registrar_movimiento(
                    db,
                    product_id,
                    "CANCELACION",
                    restore_qty,
                    reason or "Cancelacion",
                    sale_id,
                )

        ventas_repo.marcar_cancelada(db, sale_id)

        devoluciones_repo.insertar_cancelacion(
            db, sale_id, now_text(), reason or "Cancelacion"
        )
