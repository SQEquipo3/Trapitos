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


def item(pid, qty):
    return {"product_id": pid, "quantity": qty}


# ---------- unitarias ----------
def test_venta_vacia_es_rechazada(db, empleado):
    with pytest.raises(ValueError, match="no tiene productos"):
        ventas_srv.registrar(db, None, empleado, "Efectivo", 0, [])


def test_metodo_de_pago_invalido_es_rechazado(db, empleado, make_product):
    pid = make_product()
    with pytest.raises(ValueError, match="pago"):
        ventas_srv.registrar(db, None, empleado, "Cheque", 0, [item(pid, 1)])


@pytest.mark.parametrize("metodo", PAYMENT_METHODS)
def test_los_cuatro_metodos_de_pago_son_aceptados(db, empleado, make_product, metodo):
    pid = make_product(stock=50)
    sid, *_ = ventas_srv.registrar(db, None, empleado, metodo, 0, [item(pid, 1)])
    assert db.scalar("SELECT payment_method FROM sales WHERE id=?", (sid,)) == metodo


@pytest.mark.parametrize("pct", [-1, 100.5, 101])
def test_descuento_general_fuera_de_rango_es_rechazado(db, empleado, make_product, pct):
    pid = make_product()
    with pytest.raises(ValueError, match="0 y 100"):
        ventas_srv.registrar(db, None, empleado, "Efectivo", pct, [item(pid, 1)])


@pytest.mark.parametrize("qty", [0, -2])
def test_cantidad_no_positiva_es_rechazada(db, empleado, make_product, qty):
    pid = make_product()
    with pytest.raises(ValueError, match="mayor a cero"):
        ventas_srv.registrar(db, None, empleado, "Efectivo", 0, [item(pid, qty)])


def test_stock_insuficiente_es_rechazado_y_no_cambia_stock(db, empleado, make_product):
    pid = make_product(stock=2)
    with pytest.raises(ValueError, match="Stock insuficiente"):
        ventas_srv.registrar(db, None, empleado, "Efectivo", 0, [item(pid, 3)])
    assert stock(db, pid) == 2


def test_producto_inexistente_en_carrito_es_rechazado(db, empleado):
    with pytest.raises(ValueError, match="no encontrado"):
        ventas_srv.registrar(db, None, empleado, "Efectivo", 0, [item(999, 1)])


def test_calculo_de_subtotal_descuento_y_total(db, empleado, make_product):
    pid = make_product(price=200, stock=10)
    _, subtotal, descuento, total = ventas_srv.registrar(db, None, empleado, "Efectivo", 10, [item(pid, 3)])
    assert (subtotal, descuento, total) == (600, 60, 540)


# ---------- integración ----------
def test_venta_descuenta_stock_y_registra_salida(db, empleado, make_product):
    pid = make_product(stock=10)
    sid, *_ = ventas_srv.registrar(db, None, empleado, "Efectivo", 0, [item(pid, 4)])
    mov = db.one("SELECT * FROM inventory_movements WHERE movement_type='SALIDA'")
    assert stock(db, pid) == 6 and mov["quantity"] == -4 and mov["related_sale_id"] == sid


def test_venta_multiproducto_guarda_partidas(db, empleado, make_product):
    a, b = make_product(price=100), make_product(price=50)
    sid, subtotal, *_ = ventas_srv.registrar(db, None, empleado, "Tarjeta de debito", 0, [item(a, 2), item(b, 1)])
    assert subtotal == 250 and db.scalar("SELECT COUNT(*) FROM sale_items WHERE sale_id=?", (sid,)) == 2


def test_venta_es_atomica_si_falla_un_producto(db, empleado, make_product):
    a, b = make_product(stock=5), make_product(stock=1)
    with pytest.raises(ValueError):
        ventas_srv.registrar(db, None, empleado, "Efectivo", 0, [item(a, 2), item(b, 9)])
    assert stock(db, a) == 5 and db.scalar("SELECT COUNT(*) FROM sales") == 0


def test_venta_se_revierte_si_falla_una_escritura(db, empleado, make_product):
    pid = make_product(stock=5)
    with patch.object(ventas, "insertar_partida", side_effect=sqlite3.OperationalError("disco lleno")):
        with pytest.raises(sqlite3.OperationalError):
            ventas_srv.registrar(db, None, empleado, "Efectivo", 0, [item(pid, 2)])
    assert stock(db, pid) == 5 and db.scalar("SELECT COUNT(*) FROM sales") == 0


def test_promocion_vigente_se_aplica_automaticamente(db, empleado, make_product):
    pid = make_product(price=200)
    promociones_repo.guardar(db, None, pid, 25, dias(-1)[:10], dias(5)[:10])
    _, subtotal, *_ = ventas_srv.registrar(db, None, empleado, "Efectivo", 0, [item(pid, 2)])
    assert subtotal == 300
    assert db.scalar("SELECT promo_discount_percent FROM sale_items") == 25


def test_promocion_vencida_o_futura_no_se_aplica(db, empleado, make_product):
    pid = make_product(price=200)
    promociones_repo.guardar(db, None, pid, 50, dias(-10)[:10], dias(-2)[:10])
    promociones_repo.guardar(db, None, pid, 40, dias(3)[:10], dias(9)[:10])
    assert promociones_repo.porcentaje_vigente(db, pid) == 0


def test_con_varias_promociones_vigentes_aplica_la_mayor(db, make_product):
    pid = make_product()
    promociones_repo.guardar(db, None, pid, 10, dias(-1)[:10], dias(5)[:10])
    promociones_repo.guardar(db, None, pid, 30, dias(-1)[:10], dias(5)[:10])
    assert promociones_repo.porcentaje_vigente(db, pid) == 30


def test_promocion_con_porcentaje_invalido_es_rechazada(db, make_product):
    import sqlite3
    pid = make_product()
    with pytest.raises(sqlite3.IntegrityError):
        promociones_repo.guardar(db, None, pid, 120, dias(0)[:10], dias(5)[:10])


def test_devolucion_parcial_repone_stock_y_registra_movimiento(db, empleado, make_product):
    pid = make_product(stock=10)
    sid, *_ = ventas_srv.registrar(db, None, empleado, "Efectivo", 0, [item(pid, 5)])
    devoluciones_srv.devolver(db, sid, pid, 2, "No le quedó")
    assert stock(db, pid) == 7
    assert db.scalar("SELECT quantity FROM inventory_movements WHERE movement_type='DEVOLUCION'") == 2


@pytest.mark.parametrize("qty", [0, -1, 6])
def test_devolucion_invalida_no_altera_datos(db, empleado, make_product, qty):
    pid = make_product(stock=10)
    sid, *_ = ventas_srv.registrar(db, None, empleado, "Efectivo", 0, [item(pid, 5)])
    with pytest.raises(ValueError, match="no valida"):
        devoluciones_srv.devolver(db, sid, pid, qty, "x")
    assert stock(db, pid) == 5 and db.scalar("SELECT COUNT(*) FROM returns") == 0


def test_no_se_puede_devolver_mas_de_lo_vendido_en_dos_devoluciones(db, empleado, make_product):
    pid = make_product(stock=10)
    sid, *_ = ventas_srv.registrar(db, None, empleado, "Efectivo", 0, [item(pid, 3)])
    devoluciones_srv.devolver(db, sid, pid, 2, "a")
    with pytest.raises(ValueError):
        devoluciones_srv.devolver(db, sid, pid, 2, "b")


def test_cancelacion_repone_todo_y_marca_venta(db, empleado, make_product):
    pid = make_product(stock=10)
    sid, *_ = ventas_srv.registrar(db, None, empleado, "Efectivo", 0, [item(pid, 4)])
    devoluciones_srv.cancelar_venta(db, sid, "Error de captura")
    assert stock(db, pid) == 10
    assert db.scalar("SELECT status FROM sales WHERE id=?", (sid,)) == "CANCELADA"
    assert db.scalar("SELECT COUNT(*) FROM cancellations") == 1


def test_cancelar_dos_veces_o_devolver_en_cancelada_es_rechazado(db, empleado, make_product):
    pid = make_product(stock=10)
    sid, *_ = ventas_srv.registrar(db, None, empleado, "Efectivo", 0, [item(pid, 4)])
    devoluciones_srv.cancelar_venta(db, sid, "x")
    with pytest.raises(ValueError, match="ya esta cancelada"):
        devoluciones_srv.cancelar_venta(db, sid, "x")
    with pytest.raises(ValueError, match="cancelada"):
        devoluciones_srv.devolver(db, sid, pid, 1, "x")
    assert stock(db, pid) == 10


def test_cancelacion_tras_devolucion_parcial_repone_solo_el_remanente(db, empleado, make_product):
    pid = make_product(stock=10)
    sid, *_ = ventas_srv.registrar(db, None, empleado, "Efectivo", 0, [item(pid, 5)])
    devoluciones_srv.devolver(db, sid, pid, 2, "x")
    devoluciones_srv.cancelar_venta(db, sid, "x")
    assert stock(db, pid) == 10


def test_repositorio_ventas_registrar_y_obtener_fecha(db, empleado, make_product):
    pid = make_product()
    sid, *_ = ventas_srv.registrar(db, None, empleado, "Efectivo", 0, [item(pid, 1)])
    assert ventas.obtener_fecha(db, sid).startswith(today_text())


# ---------- defectos conocidos (B-03, B-05): el SDD los declara abiertos ----------
@pytest.mark.xfail(strict=True, reason="B-03: la cancelación presupone una sola línea por producto")
def test_cancelacion_con_lineas_duplicadas_repone_el_remanente_exacto(db, empleado, make_product):
    pid = make_product(stock=20)
    sid, *_ = ventas_srv.registrar(db, None, empleado, "Efectivo", 0, [item(pid, 2), item(pid, 3)])
    devoluciones_srv.devolver(db, sid, pid, 2, "x")
    devoluciones_srv.cancelar_venta(db, sid, "x")
    assert stock(db, pid) == 20


@pytest.mark.xfail(strict=True, reason="B-05: los reportes de ventas no descuentan devoluciones")
def test_reporte_ventas_por_producto_descuenta_devoluciones(db, empleado, make_product):
    pid = make_product(price=100, stock=10)
    sid, *_ = ventas_srv.registrar(db, None, empleado, "Efectivo", 0, [item(pid, 4)])
    devoluciones_srv.devolver(db, sid, pid, 4, "x")
    fila = reportes_repo.ejecutar(db, "Ventas por producto")
    assert not fila or fila[0]["piezas"] == 0
