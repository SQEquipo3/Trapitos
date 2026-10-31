"""Pruebas de ventas, descuentos, devoluciones y cancelaciones (RF-04, 06, 07, 08, 10)."""
import sqlite3
from unittest.mock import patch

import pytest

from config import PAYMENT_METHODS
from mis_trapitos.data.repositories import ventas
from utils import today_text
from tests.conftest import dias, stock
from mis_trapitos.services import devoluciones as devoluciones_srv
from mis_trapitos.services import ventas as ventas_srv
from mis_trapitos.data.repositories import promociones as promociones_repo
from mis_trapitos.data.repositories import reportes as reportes_repo
from tests.tc import tc


def item(pid, qty):
    return {"product_id": pid, "quantity": qty}


# ---------- unitarias ----------
@tc("UTS_VEN_01", nivel="UTS", modulo="ventas", reqs=["RF-06"],
    nombre="Venta sin productos, producto inexistente o cantidad no positiva")
def test_venta_vacia_es_rechazada(db, empleado):
    """Validar las entradas de services.ventas.registrar antes de escribir en la base.

    Precondiciones: Un empleado y un producto con stock registrados.
    Pasos:
    - Registrar venta con carrito vacío
    - Registrar venta con id de producto inexistente
    - Registrar venta con cantidad 0 y -2
    Esperado:
    - ValueError 'La venta no tiene productos'
    - ValueError 'Producto no encontrado'
    - ValueError 'La cantidad debe ser mayor a cero'
    """
    with pytest.raises(ValueError, match="no tiene productos"):
        ventas_srv.registrar(db, None, empleado, "Efectivo", 0, [])


@tc("UTS_VEN_02", nivel="UTS", modulo="ventas", reqs=["RF-07"],
    nombre="Método de pago inválido es rechazado")
def test_metodo_de_pago_invalido_es_rechazado(db, empleado, make_product):
    """Solo se aceptan los métodos definidos en config.PAYMENT_METHODS.

    Precondiciones: Empleado y producto registrados.
    Pasos:
    - Registrar una venta con método 'Cheque'
    Esperado:
    - ValueError 'Metodo de pago no valido'
    - No se crea la venta
    """
    pid = make_product()
    with pytest.raises(ValueError, match="pago"):
        ventas_srv.registrar(db, None, empleado, "Cheque", 0, [item(pid, 1)])


@tc("UTS_VEN_03", nivel="UTS", modulo="ventas", reqs=["RF-07"],
    nombre="Los cuatro métodos de pago son aceptados")
@pytest.mark.parametrize("metodo", PAYMENT_METHODS)
def test_los_cuatro_metodos_de_pago_son_aceptados(db, empleado, make_product, metodo):
    """Cada método de pago configurado permite registrar una venta y se guarda tal cual.

    Precondiciones: Empleado y producto con stock 50.
    Pasos:
    - Para cada método (efectivo, crédito, débito, transferencia) registrar una venta
    - Leer sales.payment_method
    Esperado:
    - Las cuatro ventas se registran
    - El método guardado coincide con el elegido
    """
    pid = make_product(stock=50)
    sid, *_ = ventas_srv.registrar(db, None, empleado, metodo, 0, [item(pid, 1)])
    assert db.scalar("SELECT payment_method FROM sales WHERE id=?", (sid,)) == metodo


@tc("UTS_VEN_04", nivel="UTS", modulo="ventas", reqs=["RF-08"],
    nombre="Descuento general fuera de 0–100 % es rechazado")
@pytest.mark.parametrize("pct", [-1, 100.5, 101])
def test_descuento_general_fuera_de_rango_es_rechazado(db, empleado, make_product, pct):
    """Validar el rango del descuento general de la venta.

    Precondiciones: Empleado y producto registrados.
    Pasos:
    - Registrar venta con descuento -1
    - Con 100.5
    - Con 101
    Esperado:
    - ValueError 'El descuento debe estar entre 0 y 100' en los tres casos
    """
    pid = make_product()
    with pytest.raises(ValueError, match="0 y 100"):
        ventas_srv.registrar(db, None, empleado, "Efectivo", pct, [item(pid, 1)])


@tc("UTS_VEN_01")
@pytest.mark.parametrize("qty", [0, -2])
def test_cantidad_no_positiva_es_rechazada(db, empleado, make_product, qty):
    pid = make_product()
    with pytest.raises(ValueError, match="mayor a cero"):
        ventas_srv.registrar(db, None, empleado, "Efectivo", 0, [item(pid, qty)])


@tc("UTS_VEN_05", nivel="UTS", modulo="ventas", reqs=["RF-04"],
    nombre="Stock insuficiente rechaza la venta sin cambiar existencias")
def test_stock_insuficiente_es_rechazado_y_no_cambia_stock(db, empleado, make_product):
    """No se puede vender más de lo disponible.

    Precondiciones: Producto con stock 2.
    Pasos:
    - Intentar vender 3 piezas
    - Consultar el stock
    Esperado:
    - ValueError 'Stock insuficiente'
    - El stock sigue en 2
    """
    pid = make_product(stock=2)
    with pytest.raises(ValueError, match="Stock insuficiente"):
        ventas_srv.registrar(db, None, empleado, "Efectivo", 0, [item(pid, 3)])
    assert stock(db, pid) == 2


@tc("UTS_VEN_01")
def test_producto_inexistente_en_carrito_es_rechazado(db, empleado):
    with pytest.raises(ValueError, match="no encontrado"):
        ventas_srv.registrar(db, None, empleado, "Efectivo", 0, [item(999, 1)])


@tc("UTS_VEN_06", nivel="UTS", modulo="ventas", reqs=["RF-08"],
    nombre="Cálculo de subtotal, descuento y total")
def test_calculo_de_subtotal_descuento_y_total(db, empleado, make_product):
    """Verificar la fórmula total = subtotal − subtotal × descuento%.

    Precondiciones: Producto de $200 con stock 10.
    Pasos:
    - Vender 3 piezas con 10 % de descuento general
    Esperado:
    - Subtotal 600, descuento 60, total 540
    """
    pid = make_product(price=200, stock=10)
    _, subtotal, descuento, total = ventas_srv.registrar(db, None, empleado, "Efectivo", 10, [item(pid, 3)])
    assert (subtotal, descuento, total) == (600, 60, 540)


# ---------- integración ----------
@tc("ITS_VEN_01", nivel="ITS", modulo="ventas", reqs=["RF-04", "RF-06"],
    nombre="Venta descuenta stock y registra SALIDA (uno y varios productos)")
def test_venta_descuenta_stock_y_registra_salida(db, empleado, make_product):
    """services.ventas.registrar actualiza sales, sale_items, products e inventory_movements en
    conjunto.

    Precondiciones: Productos con stock y un empleado.
    Pasos:
    - Vender 4 piezas de un producto
    - Vender 2 + 1 piezas de dos productos
    Esperado:
    - Stock 6, movimiento SALIDA −4 ligado a la venta
    - Dos partidas y subtotal 250
    """
    pid = make_product(stock=10)
    sid, *_ = ventas_srv.registrar(db, None, empleado, "Efectivo", 0, [item(pid, 4)])
    mov = db.one("SELECT * FROM inventory_movements WHERE movement_type='SALIDA'")
    assert stock(db, pid) == 6 and mov["quantity"] == -4 and mov["related_sale_id"] == sid


@tc("ITS_VEN_01")
def test_venta_multiproducto_guarda_partidas(db, empleado, make_product):
    a, b = make_product(price=100), make_product(price=50)
    sid, subtotal, *_ = ventas_srv.registrar(db, None, empleado, "Tarjeta de debito", 0, [item(a, 2), item(b, 1)])
    assert subtotal == 250 and db.scalar("SELECT COUNT(*) FROM sale_items WHERE sale_id=?", (sid,)) == 2


@tc("ITS_VEN_02", nivel="ITS", modulo="ventas", reqs=["RF-04"],
    nombre="Atomicidad: si una partida falla no se guarda nada")
def test_venta_es_atomica_si_falla_un_producto(db, empleado, make_product):
    """La venta se revierte completa ante stock insuficiente en la segunda partida o si falla una
    escritura a la mitad de la transacción.

    Precondiciones: Dos productos: stock 5 y stock 1.
    Pasos:
    - Vender 2 del primero y 9 del segundo
    - Vender 2 piezas provocando un error controlado al guardar la partida
    Esperado:
    - ValueError
    - Stock del primero sigue en 5 y no existe venta
    - El error se propaga, el stock sigue en 5 y no existe venta
    """
    a, b = make_product(stock=5), make_product(stock=1)
    with pytest.raises(ValueError):
        ventas_srv.registrar(db, None, empleado, "Efectivo", 0, [item(a, 2), item(b, 9)])
    assert stock(db, a) == 5 and db.scalar("SELECT COUNT(*) FROM sales") == 0


@tc("ITS_VEN_02")
def test_venta_se_revierte_si_falla_una_escritura(db, empleado, make_product):
    pid = make_product(stock=5)
    with patch.object(ventas, "insertar_partida", side_effect=sqlite3.OperationalError("disco lleno")):
        with pytest.raises(sqlite3.OperationalError):
            ventas_srv.registrar(db, None, empleado, "Efectivo", 0, [item(pid, 2)])
    assert stock(db, pid) == 5 and db.scalar("SELECT COUNT(*) FROM sales") == 0


@tc("ITS_VEN_03", nivel="ITS", modulo="ventas", reqs=["RF-10"],
    nombre="Promoción vigente se aplica automáticamente en la venta")
def test_promocion_vigente_se_aplica_automaticamente(db, empleado, make_product):
    """El precio de la partida usa el descuento de la promoción vigente.

    Precondiciones: Producto de $200 con promoción de 25 %.
    Pasos:
    - Vender 2 piezas
    - Leer sale_items.promo_discount_percent
    Esperado:
    - Subtotal 300
    - Promo aplicada 25 %
    """
    pid = make_product(price=200)
    promociones_repo.guardar(db, None, pid, 25, dias(-1)[:10], dias(5)[:10])
    _, subtotal, *_ = ventas_srv.registrar(db, None, empleado, "Efectivo", 0, [item(pid, 2)])
    assert subtotal == 300
    assert db.scalar("SELECT promo_discount_percent FROM sale_items") == 25


@tc("UTS_VEN_07", nivel="UTS", modulo="ventas", reqs=["RF-09", "RF-10"],
    nombre="Vigencia de promociones (vencida y futura no aplican)")
def test_promocion_vencida_o_futura_no_se_aplica(db, empleado, make_product):
    """promociones.porcentaje_vigente solo considera promociones cuya vigencia incluye hoy.

    Precondiciones: Producto con una promoción vencida (50 %) y otra futura (40 %).
    Pasos:
    - Consultar active_promotion_percent del producto
    Esperado:
    - Regresa 0
    """
    pid = make_product(price=200)
    promociones_repo.guardar(db, None, pid, 50, dias(-10)[:10], dias(-2)[:10])
    promociones_repo.guardar(db, None, pid, 40, dias(3)[:10], dias(9)[:10])
    assert promociones_repo.porcentaje_vigente(db, pid) == 0


@tc("UTS_VEN_08", nivel="UTS", modulo="ventas", reqs=["RF-09", "RF-10"],
    nombre="Varias promociones vigentes: aplica la mayor; porcentaje inválido es rechazado")
def test_con_varias_promociones_vigentes_aplica_la_mayor(db, make_product):
    """Resolver traslapes de promoción y validar el porcentaje (0–100).

    Precondiciones: Un producto registrado.
    Pasos:
    - Crear promociones vigentes de 10 % y 30 %
    - Consultar el porcentaje activo
    - Intentar crear una promoción de 120 %
    Esperado:
    - El porcentaje activo es 30
    - La promoción de 120 % levanta IntegrityError
    """
    pid = make_product()
    promociones_repo.guardar(db, None, pid, 10, dias(-1)[:10], dias(5)[:10])
    promociones_repo.guardar(db, None, pid, 30, dias(-1)[:10], dias(5)[:10])
    assert promociones_repo.porcentaje_vigente(db, pid) == 30


@tc("UTS_VEN_08")
def test_promocion_con_porcentaje_invalido_es_rechazada(db, make_product):
    import sqlite3
    pid = make_product()
    with pytest.raises(sqlite3.IntegrityError):
        promociones_repo.guardar(db, None, pid, 120, dias(0)[:10], dias(5)[:10])


@tc("ITS_VEN_04", nivel="ITS", modulo="ventas", reqs=["RF-05"],
    nombre="Devolución parcial repone existencias")
def test_devolucion_parcial_repone_stock_y_registra_movimiento(db, empleado, make_product):
    """services.devoluciones.devolver suma al stock y registra movimiento DEVOLUCION.

    Precondiciones: Venta de 5 piezas (stock final 5).
    Pasos:
    - Devolver 2 piezas
    Esperado:
    - Stock 7
    - Movimiento DEVOLUCION con cantidad 2
    """
    pid = make_product(stock=10)
    sid, *_ = ventas_srv.registrar(db, None, empleado, "Efectivo", 0, [item(pid, 5)])
    devoluciones_srv.devolver(db, sid, pid, 2, "No le quedó")
    assert stock(db, pid) == 7
    assert db.scalar("SELECT quantity FROM inventory_movements WHERE movement_type='DEVOLUCION'") == 2


@tc("ITS_VEN_05", nivel="ITS", modulo="ventas", reqs=["RF-05"],
    nombre="Devoluciones inválidas no alteran datos")
@pytest.mark.parametrize("qty", [0, -1, 6])
def test_devolucion_invalida_no_altera_datos(db, empleado, make_product, qty):
    """Cantidad 0, negativa, mayor a la vendida o acumulada mayor a la vendida se rechaza.

    Precondiciones: Venta de 3–5 piezas.
    Pasos:
    - Devolver 0, −1 y 6 de una venta de 5
    - Devolver 2 y luego otras 2 de una venta de 3
    Esperado:
    - ValueError 'Cantidad de devolucion no valida'
    - Stock y tabla returns sin cambios
    """
    pid = make_product(stock=10)
    sid, *_ = ventas_srv.registrar(db, None, empleado, "Efectivo", 0, [item(pid, 5)])
    with pytest.raises(ValueError, match="no valida"):
        devoluciones_srv.devolver(db, sid, pid, qty, "x")
    assert stock(db, pid) == 5 and db.scalar("SELECT COUNT(*) FROM returns") == 0


@tc("ITS_VEN_05")
def test_no_se_puede_devolver_mas_de_lo_vendido_en_dos_devoluciones(db, empleado, make_product):
    pid = make_product(stock=10)
    sid, *_ = ventas_srv.registrar(db, None, empleado, "Efectivo", 0, [item(pid, 3)])
    devoluciones_srv.devolver(db, sid, pid, 2, "a")
    with pytest.raises(ValueError):
        devoluciones_srv.devolver(db, sid, pid, 2, "b")


@tc("ITS_VEN_06", nivel="ITS", modulo="ventas", reqs=["RF-05"],
    nombre="Cancelación repone todo y bloquea operaciones posteriores")
def test_cancelacion_repone_todo_y_marca_venta(db, empleado, make_product):
    """services.devoluciones.cancelar_venta restaura stock, marca CANCELADA y evita doble
    cancelación o devolución.

    Precondiciones: Venta de 4 piezas.
    Pasos:
    - Cancelar la venta
    - Cancelar de nuevo
    - Intentar devolver sobre la venta cancelada
    Esperado:
    - Stock restaurado, estado CANCELADA y 1 registro en cancellations
    - Ambos intentos posteriores levantan ValueError
    """
    pid = make_product(stock=10)
    sid, *_ = ventas_srv.registrar(db, None, empleado, "Efectivo", 0, [item(pid, 4)])
    devoluciones_srv.cancelar_venta(db, sid, "Error de captura")
    assert stock(db, pid) == 10
    assert db.scalar("SELECT status FROM sales WHERE id=?", (sid,)) == "CANCELADA"
    assert db.scalar("SELECT COUNT(*) FROM cancellations") == 1


@tc("ITS_VEN_06")
def test_cancelar_dos_veces_o_devolver_en_cancelada_es_rechazado(db, empleado, make_product):
    pid = make_product(stock=10)
    sid, *_ = ventas_srv.registrar(db, None, empleado, "Efectivo", 0, [item(pid, 4)])
    devoluciones_srv.cancelar_venta(db, sid, "x")
    with pytest.raises(ValueError, match="ya esta cancelada"):
        devoluciones_srv.cancelar_venta(db, sid, "x")
    with pytest.raises(ValueError, match="cancelada"):
        devoluciones_srv.devolver(db, sid, pid, 1, "x")
    assert stock(db, pid) == 10


@tc("ITS_VEN_07", nivel="ITS", modulo="ventas", reqs=["RF-05"],
    nombre="Cancelación tras devolución parcial repone solo el remanente")
def test_cancelacion_tras_devolucion_parcial_repone_solo_el_remanente(db, empleado, make_product):
    """Evitar reponer dos veces las piezas ya devueltas.

    Precondiciones: Venta de 5; devolución de 2.
    Pasos:
    - Cancelar la venta
    Esperado:
    - Stock final = 10 (ni más ni menos)
    """
    pid = make_product(stock=10)
    sid, *_ = ventas_srv.registrar(db, None, empleado, "Efectivo", 0, [item(pid, 5)])
    devoluciones_srv.devolver(db, sid, pid, 2, "x")
    devoluciones_srv.cancelar_venta(db, sid, "x")
    assert stock(db, pid) == 10


@tc("ITS_VEN_07")
def test_repositorio_ventas_registrar_y_obtener_fecha(db, empleado, make_product):
    pid = make_product()
    sid, *_ = ventas_srv.registrar(db, None, empleado, "Efectivo", 0, [item(pid, 1)])
    assert ventas.obtener_fecha(db, sid).startswith(today_text())


# ---------- defectos conocidos (B-03, B-05): el SDD los declara abiertos ----------
@tc("ITS_VEN_08", nivel="ITS", modulo="ventas", reqs=["RF-05"],
    nombre="Cancelación con líneas duplicadas por producto (brecha B-03)")
@pytest.mark.xfail(strict=True, reason="#53 (B-03): la cancelación presupone una sola línea por producto")
def test_cancelacion_con_lineas_duplicadas_repone_el_remanente_exacto(db, empleado, make_product):
    """Confirmar que la cancelación repone el remanente exacto cuando el carrito trae el mismo
    producto en dos líneas.

    Precondiciones: Producto stock 20; venta con líneas 2 y 3 del mismo producto; devolución de
    2.
    Pasos:
    - Cancelar la venta
    - Comparar stock final con 20
    Esperado:
    - Stock final = 20
    Comentarios: DEFECTO ABIERTO B-03 (SDD, sección 11): la cancelación calcula el remanente por línea y
    descuenta las devoluciones dos veces. La prueba está marcada xfail(strict) y se reporta como
    FAILED.
    """
    pid = make_product(stock=20)
    sid, *_ = ventas_srv.registrar(db, None, empleado, "Efectivo", 0, [item(pid, 2), item(pid, 3)])
    devoluciones_srv.devolver(db, sid, pid, 2, "x")
    devoluciones_srv.cancelar_venta(db, sid, "x")
    assert stock(db, pid) == 20


@tc("ITS_REP_07", nivel="ITS", modulo="reportes", reqs=["RF-17", "RF-18"],
    nombre="Reportes de ventas descuentan devoluciones (brecha B-05)")
@pytest.mark.xfail(strict=True, reason="#54 (B-05): los reportes de ventas no descuentan devoluciones")
def test_reporte_ventas_por_producto_descuenta_devoluciones(db, empleado, make_product):
    """Comprobar que 'Ventas por producto' refleje una devolución total.

    Precondiciones: Venta de 4 piezas devuelta completamente.
    Pasos:
    - Ejecutar 'Ventas por producto'
    Esperado:
    - La fila del producto desaparece o muestra 0 piezas
    Comentarios: DEFECTO ABIERTO B-05 (SDD, sección 11): los agregados no restan returns. Prueba
    xfail(strict), se reporta FAILED.
    """
    pid = make_product(price=100, stock=10)
    sid, *_ = ventas_srv.registrar(db, None, empleado, "Efectivo", 0, [item(pid, 4)])
    devoluciones_srv.devolver(db, sid, pid, 4, "x")
    fila = reportes_repo.ejecutar(db, "Ventas por producto")
    assert not fila or fila[0]["piezas"] == 0
