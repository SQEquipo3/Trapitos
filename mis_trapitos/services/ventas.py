"""Reglas de negocio de ventas: carrito, totales y registro de la venta.

Las funciones reciben el objeto Database (data/database.py) y acceden a los
datos solo a través de los repositorios.
"""

from typing import NamedTuple

from config import PAYMENT_METHODS
from utils import now_text
from mis_trapitos.data.repositories import clientes as clientes_repo
from mis_trapitos.data.repositories import productos as productos_repo
from mis_trapitos.data.repositories import promociones as promociones_repo
from mis_trapitos.data.repositories import ventas as ventas_repo


class ResultadoVenta(NamedTuple):
    sale_id: int
    fecha: str
    subtotal: float
    descuento: float
    total: float
    metodo_pago: str


def parsear_descuento(valor):
    try:
        descuento = float(valor or 0)
    except (TypeError, ValueError):
        raise ValueError("El descuento debe ser un numero.")
    if descuento < 0 or descuento > 100:
        raise ValueError("El descuento debe estar entre 0 y 100.")
    return descuento


def registrar(db, customer_id, employee_id, metodo_pago, descuento, cart):
    """Guarda la venta, sus partidas, descuenta stock y registra movimientos.

    Todo ocurre en UNA transacción: si algo falla se revierte completo
    (no queda venta sin descontar stock).
    Regresa (sale_id, subtotal, monto_descuento, total).
    """
    if not cart:
        raise ValueError("La venta no tiene productos.")
    descuento = float(descuento or 0)
    if descuento < 0 or descuento > 100:
        raise ValueError("El descuento debe estar entre 0 y 100.")
    if metodo_pago not in PAYMENT_METHODS:
        raise ValueError("Metodo de pago no valido.")
    with db.transaction():
        subtotal = 0.0
        prepared = []
        for item in cart:
            product_id = int(item["product_id"])
            qty = int(item["quantity"])
            product = productos_repo.obtener_por_id(db, product_id)
            if not product:
                raise ValueError("Producto no encontrado.")
            if qty <= 0:
                raise ValueError("La cantidad debe ser mayor a cero.")
            if int(product["stock"]) < qty:
                raise ValueError(f"Stock insuficiente para {product['code']} - {product['name']}.")
            promo = promociones_repo.porcentaje_vigente(db, product_id)
            unit_price = float(product["sale_price"])
            line_total = unit_price * qty * (1 - promo / 100)
            subtotal += line_total
            prepared.append((product_id, qty, unit_price, promo, line_total))
        monto = subtotal * descuento / 100
        total = subtotal - monto
        sale_id = ventas_repo.insertar(db, now_text(), customer_id or None, employee_id,
                                       metodo_pago, subtotal, descuento, monto, total)
        for product_id, qty, unit_price, promo, line_total in prepared:
            ventas_repo.insertar_partida(db, sale_id, product_id, qty, unit_price, promo, line_total)
            productos_repo.ajustar_stock(db, product_id, -qty)
            productos_repo.registrar_movimiento(db, product_id, "SALIDA", -qty, "Venta registrada", sale_id)
        return sale_id, subtotal, monto, total


class ServicioVentas:
    """Carrito de una venta en captura, independiente de la interfaz."""

    def __init__(self, db):
        self.db = db
        self.cart = []

    # ------------------------------------------------------------------ carrito
    def cantidad_en_carrito(self, product_id):
        return sum(int(i["quantity"]) for i in self.cart if int(i["product_id"]) == int(product_id))

    def agregar_producto(self, code, quantity=1):
        """Agrega al carrito validando existencia, cantidad y stock disponible."""
        code = (code or "").strip()
        try:
            qty = int(quantity)
        except (TypeError, ValueError):
            raise ValueError("Cantidad no valida.")
        product = productos_repo.obtener_por_codigo(self.db, code)
        if not product:
            raise ValueError("No existe producto con ese codigo.")
        if qty <= 0:
            raise ValueError("Cantidad no valida.")
        if self.cantidad_en_carrito(product["id"]) + qty > int(product["stock"]):
            raise ValueError("Stock insuficiente.")
        for item in self.cart:
            if int(item["product_id"]) == int(product["id"]):
                item["quantity"] += qty
                break
        else:
            self.cart.append({"product_id": product["id"], "quantity": qty})

    def vaciar(self):
        self.cart = []

    def lineas(self):
        """Devuelve las partidas del carrito con promoción vigente y total de línea."""
        rows = []
        for item in self.cart:
            product = productos_repo.obtener_por_id(self.db, item["product_id"])
            if not product:
                continue
            promo = promociones_repo.porcentaje_vigente(self.db, product["id"])
            qty = int(item["quantity"])
            line = float(product["sale_price"]) * qty * (1 - promo / 100)
            rows.append({
                "id": product["id"], "code": product["code"], "name": product["name"],
                "quantity": qty, "unit_price": float(product["sale_price"]),
                "promo": promo, "line_total": line,
            })
        return rows

    # ------------------------------------------------------------------ totales
    @staticmethod
    def parsear_descuento(valor):
        return parsear_descuento(valor)

    def totales(self, descuento=0):
        """Regresa (subtotal con promociones, monto de descuento, total)."""
        descuento = parsear_descuento(descuento)
        subtotal = sum(line["line_total"] for line in self.lineas())
        monto = subtotal * descuento / 100
        return subtotal, monto, subtotal - monto

    # -------------------------------------------------------------------- venta
    def registrar_venta(self, customer_id, employee_id, metodo_pago, descuento=0):
        """Registra la venta del carrito y deja el inventario actualizado.

        Si algo falla, registrar() revierte la transacción completa y el
        carrito se conserva para que el usuario pueda corregir y reintentar.
        El carrito solo se vacía cuando la venta quedó guardada.
        """
        if not self.cart:
            raise ValueError("La venta no tiene productos.")
        if metodo_pago not in PAYMENT_METHODS:
            raise ValueError("Metodo de pago no valido.")
        descuento = parsear_descuento(descuento)
        if customer_id is not None and not clientes_repo.existe(self.db, customer_id):
            raise ValueError("Cliente no encontrado.")
        sale_id, subtotal, monto, total = registrar(
            self.db, customer_id, employee_id, metodo_pago, descuento, self.cart
        )
        fecha = ventas_repo.obtener_fecha(self.db, sale_id)
        self.vaciar()
        return ResultadoVenta(sale_id, fecha, subtotal, monto, total, metodo_pago)
