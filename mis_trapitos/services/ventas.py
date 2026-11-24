"""Reglas de negocio de ventas usando centavos enteros."""

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import NamedTuple

from config import PAYMENT_METHODS
from utils import now_text
from mis_trapitos.data.repositories import clientes as clientes_repo
from mis_trapitos.data.repositories import productos as productos_repo
from mis_trapitos.data.repositories import promociones as promociones_repo
from mis_trapitos.data.repositories import ventas as ventas_repo


def redondear(valor):
    """Redondea un resultado monetario a centavos enteros."""
    return int(
        Decimal(valor).quantize(
            Decimal("1"),
            rounding=ROUND_HALF_UP
        )
    )


def porcentaje_decimal(valor):
    """Convierte un porcentaje a Decimal sin introducir errores float."""
    try:
        resultado = Decimal(str(valor or 0))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError("El descuento debe ser un numero.")

    if not resultado.is_finite() or resultado < 0 or resultado > 100:
        raise ValueError("El descuento debe estar entre 0 y 100.")

    return resultado


class ResultadoVenta(NamedTuple):
    sale_id: int
    fecha: str
    subtotal: int
    descuento: int
    total: int
    metodo_pago: str


def parsear_descuento(valor):
    return porcentaje_decimal(valor)


def calcular_linea(precio_centavos, cantidad, promocion):
    """Calcula el total de una partida en centavos enteros."""

    precio = Decimal(int(precio_centavos))
    qty = Decimal(int(cantidad))
    descuento = Decimal(str(promocion or 0))

    factor = Decimal("1") - descuento / Decimal("100")

    return redondear(precio * qty * factor)


def calcular_descuento(subtotal_centavos, porcentaje):
    """Calcula el descuento general en centavos."""
    return redondear(
        Decimal(int(subtotal_centavos))
        * Decimal(str(porcentaje))
        / Decimal("100")
    )


def registrar(db, customer_id, employee_id, metodo_pago, descuento, cart):
    """Registra la venta y descuenta el inventario en una transacción."""

    if not cart:
        raise ValueError("La venta no tiene productos.")

    descuento = porcentaje_decimal(descuento)

    if metodo_pago not in PAYMENT_METHODS:
        raise ValueError("Metodo de pago no valido.")

    with db.transaction():
        subtotal = 0
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
                raise ValueError(
                    f"Stock insuficiente para {product['code']} - "
                    f"{product['name']}."
                )

            promo = promociones_repo.porcentaje_vigente(db, product_id)

            # El precio de la base de datos ya está almacenado en centavos.
            unit_price = int(product["sale_price"])

            line_total = calcular_linea(unit_price, qty, promo)
            subtotal += line_total

            prepared.append(
                (product_id, qty, unit_price, promo, line_total)
            )

        monto = calcular_descuento(subtotal, descuento)
        total = subtotal - monto

        sale_id = ventas_repo.insertar(
            db,
            now_text(),
            customer_id or None,
            employee_id,
            metodo_pago,
            subtotal,
            descuento,
            monto,
            total,
        )

        for product_id, qty, unit_price, promo, line_total in prepared:
            ventas_repo.insertar_partida(
                db,
                sale_id,
                product_id,
                qty,
                unit_price,
                promo,
                line_total,
            )

            productos_repo.ajustar_stock(db, product_id, -qty)

            productos_repo.registrar_movimiento(
                db,
                product_id,
                "SALIDA",
                -qty,
                "Venta registrada",
                sale_id,
            )

        return sale_id, subtotal, monto, total


class ServicioVentas:
    """Carrito de venta independiente de la interfaz."""

    def __init__(self, db):
        self.db = db
        self.cart = []

    def cantidad_en_carrito(self, product_id):
        return sum(
            int(i["quantity"])
            for i in self.cart
            if int(i["product_id"]) == int(product_id)
        )

    def agregar_producto(self, code, quantity=1):
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
            self.cart.append({
                "product_id": product["id"],
                "quantity": qty,
            })

    def vaciar(self):
        self.cart = []

    def lineas(self):
        """Devuelve precios y totales en centavos."""

        rows = []

        for item in self.cart:
            product = productos_repo.obtener_por_id(
                self.db,
                item["product_id"]
            )

            if not product:
                continue

            promo = promociones_repo.porcentaje_vigente(
                self.db,
                product["id"]
            )

            qty = int(item["quantity"])
            unit_price = int(product["sale_price"])
            line_total = calcular_linea(unit_price, qty, promo)

            rows.append({
                "id": product["id"],
                "code": product["code"],
                "name": product["name"],
                "quantity": qty,
                "unit_price": unit_price,
                "promo": promo,
                "line_total": line_total,
            })

        return rows

    @staticmethod
    def parsear_descuento(valor):
        return parsear_descuento(valor)

    def totales(self, descuento=0):
        """Devuelve subtotal, descuento y total en centavos."""

        porcentaje = porcentaje_decimal(descuento)

        subtotal = sum(
            int(line["line_total"])
            for line in self.lineas()
        )

        monto = calcular_descuento(subtotal, porcentaje)

        return subtotal, monto, subtotal - monto

    def registrar_venta(self, customer_id, employee_id,
                        metodo_pago, descuento=0):
        if not self.cart:
            raise ValueError("La venta no tiene productos.")

        if metodo_pago not in PAYMENT_METHODS:
            raise ValueError("Metodo de pago no valido.")

        descuento = porcentaje_decimal(descuento)

        if customer_id is not None and not clientes_repo.existe(
            self.db,
            customer_id
        ):
            raise ValueError("Cliente no encontrado.")

        sale_id, subtotal, monto, total = registrar(
            self.db,
            customer_id,
            employee_id,
            metodo_pago,
            descuento,
            self.cart,
        )

        fecha = ventas_repo.obtener_fecha(self.db, sale_id)

        self.vaciar()

        return ResultadoVenta(
            sale_id,
            fecha,
            subtotal,
            monto,
            total,
            metodo_pago,
        )