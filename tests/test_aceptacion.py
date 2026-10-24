"""Escenarios de aceptación automatizables (VD-01 … VD-07 del SDD §10).

Cada prueba cuenta una historia completa del usuario usando solo la capa de
datos pública (repositorios), como lo haría la interfaz.
"""
import pytest

from mis_trapitos.data.repositories import clientes, productos, promociones, reportes, ventas
from tests.conftest import dias, stock
from utils import today_text


def alta(db, code, price=200, stock_=10, category="Ropa"):
    return productos.guardar(db, None, (code, "Prenda " + code, category, "M", "Azul", 80, price,
                                        stock_, None, today_text(), "M", "T", ""))


def test_vd01_alta_de_variantes_y_consulta_de_inventario(db):
    for talla, color, n in (("S", "Rojo", 2), ("M", "Rojo", 5), ("M", "Negro", 7)):
        productos.guardar(db, None, (f"V-{talla}{color}", "Vestido", "Ropa", talla, color, 100, 300,
                                     n, None, today_text(), "M", "T", ""))
    inv = productos.listar_inventario(db)
    assert sorted(r["stock"] for r in inv) == [2, 5, 7]


def test_vd02_ajuste_manual_queda_en_kardex(db):
    pid = alta(db, "A1", stock_=10)
    productos.guardar(db, pid, ("A1", "Prenda A1", "Ropa", "M", "Azul", 80, 200, 15, None,
                                today_text(), "M", "T", ""))
    assert sorted(r["cantidad"] for r in db.report("Entradas de mercancia")) == [5, 10]


def test_vd03_dia_de_venta_con_promocion_y_descuento_general(db, empleado):
    pid = alta(db, "S1", price=1000, stock_=10)
    promociones.guardar(db, None, pid, 20, dias(-1)[:10], dias(3)[:10])
    cid = clientes.guardar(db, None, ("Ana", "1", "a@x", "c", "GDL", ""))
    _, sub, desc, total = ventas.registrar(db, cid, empleado, "Tarjeta de credito", 10,
                                           [{"product_id": pid, "quantity": 2}])
    assert (sub, desc, total) == (1600, 160, 1440) and stock(db, pid) == 8


def test_vd04_devolucion_parcial_y_cancelacion_posterior(db, empleado):
    pid = alta(db, "D1", stock_=10)
    sid, *_ = ventas.registrar(db, None, empleado, "Efectivo", 0, [{"product_id": pid, "quantity": 6}])
    db.return_item(sid, pid, 2, "Defecto")
    db.cancel_sale(sid, "Cliente se arrepintió")
    assert stock(db, pid) == 10
    tipos = [r["tipo"] for r in db.report("Productos devueltos o cancelados")]
    assert sorted(tipos) == ["CANCELACION", "DEVOLUCION"]


def test_vd05_promocion_deja_de_aplicar_al_vencer(db, empleado):
    pid = alta(db, "P1", price=100)
    promociones.guardar(db, None, pid, 50, dias(-5)[:10], dias(-1)[:10])
    _, sub, *_ = ventas.registrar(db, None, empleado, "Efectivo", 0, [{"product_id": pid, "quantity": 1}])
    assert sub == 100 and db.report("Productos en oferta") == []


def test_vd06_historial_de_cliente_refleja_cancelaciones(db, empleado):
    pid = alta(db, "H1")
    cid = clientes.guardar(db, None, ("Beto", "1", "b@x", "c", "GDL", ""))
    s1, *_ = ventas.registrar(db, cid, empleado, "Efectivo", 0, [{"product_id": pid, "quantity": 1}])
    ventas.registrar(db, cid, empleado, "Efectivo", 0, [{"product_id": pid, "quantity": 2}])
    db.cancel_sale(s1, "x")
    assert clientes.resumen_compras(db, cid)["compras"] == 1
    assert {r["estado"] for r in clientes.historial(db, cid)} == {"ACTIVA", "CANCELADA"}


def test_vd07_todos_los_reportes_rf15_a_rf26_se_ejecutan_sin_error(db, empleado):
    pid = alta(db, "R1")
    sid, *_ = ventas.registrar(db, None, empleado, "Efectivo", 0, [{"product_id": pid, "quantity": 1}])
    parametros = {"Productos disponibles por categoria": "Ropa", "Productos de proveedor especifico": "1",
                  "Productos comprados mas de una vez por cliente": "1",
                  "Productos vendidos por categoria ultimo mes": "Ropa",
                  "Productos con precio superior y existencias": "10"}
    nombres = ["Productos disponibles por categoria", "Productos en oferta", "Metodos de pago mas utilizados",
               "Productos mas vendidos ultimo mes", "Ventas ultimos tres dias",
               "Productos de proveedor especifico", "Productos comprados mas de una vez por cliente",
               "Productos vendidos por categoria ultimo mes", "Productos con precio superior y existencias",
               "Producto con mayor descuento vigente", "Compras por ciudad o region",
               "Productos no vendidos ultimos tres meses"]
    for n in nombres:
        reportes.ejecutar(db, n, parametros.get(n, ""))          # no debe lanzar excepción
    assert len(nombres) == 12
