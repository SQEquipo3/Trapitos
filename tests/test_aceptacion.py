"""Escenarios de aceptación automatizables (VD-01 … VD-07 del SDD §10).

Cada prueba cuenta una historia completa del usuario usando solo la capa de
datos pública (repositorios y servicios), como lo haría la interfaz.
"""

from mis_trapitos.data.repositories import clientes, productos, promociones, reportes
from tests.conftest import dias, stock
from utils import today_text
from mis_trapitos.services import devoluciones as devoluciones_srv
from mis_trapitos.services import ventas as ventas_srv
from tests.tc import tc


def alta(db, code, price=200, stock_=10, category="Ropa"):
    return productos.guardar(db, None, (code, "Prenda " + code, category, "M", "Azul", 80, price,
                                        stock_, None, today_text(), "M", "T", ""))


@tc("ATS_VD_01", nivel="ATS", modulo="productos", reqs=["RF-01", "RF-02", "RF-14"],
    nombre="VD-01 Alta de variantes y consulta de inventario")
def test_vd01_alta_de_variantes_y_consulta_de_inventario(db):
    """La dueña registra un vestido en tres variantes y las consulta en inventario.

    Precondiciones: BD limpia.
    Pasos:
    - Registrar S/Rojo (2), M/Rojo (5) y M/Negro (7)
    - Abrir el inventario
    Esperado:
    - Tres filas con existencias 2, 5 y 7
    """
    for talla, color, n in (("S", "Rojo", 2), ("M", "Rojo", 5), ("M", "Negro", 7)):
        productos.guardar(db, None, (f"V-{talla}{color}", "Vestido", "Ropa", talla, color, 100, 300,
                                     n, None, today_text(), "M", "T", ""))
    inv = productos.listar_inventario(db)
    assert sorted(r["stock"] for r in inv) == [2, 5, 7]


@tc("ATS_VD_02", nivel="ATS", modulo="productos", reqs=["RF-03", "RF-05"],
    nombre="VD-02 Ajuste manual de inventario queda en kardex")
def test_vd02_ajuste_manual_queda_en_kardex(db):
    """Un ajuste de stock se refleja en el reporte de entradas de mercancía.

    Precondiciones: Producto con stock 10.
    Pasos:
    - Editar stock a 15
    - Ejecutar 'Entradas de mercancia'
    Esperado:
    - Aparecen entradas de 10 (alta) y 5 (ajuste)
    """
    pid = alta(db, "A1", stock_=10)
    productos.guardar(db, pid, ("A1", "Prenda A1", "Ropa", "M", "Azul", 80, 200, 15, None,
                                today_text(), "M", "T", ""))
    assert sorted(r["cantidad"] for r in reportes.ejecutar(db, "Entradas de mercancia")) == [5, 10]


@tc("ATS_VD_03", nivel="ATS", modulo="ventas", reqs=["RF-04", "RF-06", "RF-07", "RF-08", "RF-10"],
    nombre="VD-03 Día de venta con promoción y descuento general")
def test_vd03_dia_de_venta_con_promocion_y_descuento_general(db, empleado):
    """Venta real con promoción del 20 % y descuento general del 10 % pagada con tarjeta.

    Precondiciones: Producto de $1000, promoción 20 %, cliente registrado.
    Pasos:
    - Vender 2 piezas con 10 % de descuento general
    Esperado:
    - Subtotal 1600, descuento 160, total 1440; stock 8
    """
    pid = alta(db, "S1", price=1000, stock_=10)
    promociones.guardar(db, None, pid, 20, dias(-1)[:10], dias(3)[:10])
    cid = clientes.guardar(db, None, ("Ana", "1", "a@x", "c", "GDL", ""))
    _, sub, desc, total = ventas_srv.registrar(db, cid, empleado, "Tarjeta de credito", 10,
                                           [{"product_id": pid, "quantity": 2}])
    assert (sub, desc, total) == (1600, 160, 1440) and stock(db, pid) == 8


@tc("ATS_VD_04", nivel="ATS", modulo="ventas", reqs=["RF-05"],
    nombre="VD-04 Devolución parcial y cancelación posterior")
def test_vd04_devolucion_parcial_y_cancelacion_posterior(db, empleado):
    """El inventario queda exacto y el reporte de devueltos/cancelados lo muestra.

    Precondiciones: Venta de 6 piezas.
    Pasos:
    - Devolver 2
    - Cancelar la venta
    - Ejecutar 'Productos devueltos o cancelados'
    Esperado:
    - Stock 10
    - Un renglón DEVOLUCION y uno CANCELACION
    """
    pid = alta(db, "D1", stock_=10)
    sid, *_ = ventas_srv.registrar(db, None, empleado, "Efectivo", 0, [{"product_id": pid, "quantity": 6}])
    devoluciones_srv.devolver(db, sid, pid, 2, "Defecto")
    devoluciones_srv.cancelar_venta(db, sid, "Cliente se arrepintió")
    assert stock(db, pid) == 10
    tipos = [r["tipo"] for r in reportes.ejecutar(db, "Productos devueltos o cancelados")]
    assert sorted(tipos) == ["CANCELACION", "DEVOLUCION"]


@tc("ATS_VD_05", nivel="ATS", modulo="ventas", reqs=["RF-09", "RF-16"],
    nombre="VD-05 Promoción vencida deja de aplicar")
def test_vd05_promocion_deja_de_aplicar_al_vencer(db, empleado):
    """Una oferta fuera de vigencia no afecta el precio ni aparece en ofertas.

    Precondiciones: Promoción de 50 % vencida ayer.
    Pasos:
    - Vender 1 pieza
    - Ejecutar 'Productos en oferta'
    Esperado:
    - Subtotal sin descuento
    - Reporte vacío
    """
    pid = alta(db, "P1", price=100)
    promociones.guardar(db, None, pid, 50, dias(-5)[:10], dias(-1)[:10])
    _, sub, *_ = ventas_srv.registrar(db, None, empleado, "Efectivo", 0, [{"product_id": pid, "quantity": 1}])
    assert sub == 100 and reportes.ejecutar(db, "Productos en oferta") == []


@tc("ATS_VD_06", nivel="ATS", modulo="contactos", reqs=["RF-11", "RF-12"],
    nombre="VD-06 Historial de cliente refleja cancelaciones")
def test_vd06_historial_de_cliente_refleja_cancelaciones(db, empleado):
    """El resumen cuenta solo compras activas y el historial muestra ambas.

    Precondiciones: Cliente con dos compras, una cancelada.
    Pasos:
    - Consultar resumen e historial
    Esperado:
    - Resumen: 1 compra
    - Historial: estados ACTIVA y CANCELADA
    """
    pid = alta(db, "H1")
    cid = clientes.guardar(db, None, ("Beto", "1", "b@x", "c", "GDL", ""))
    s1, *_ = ventas_srv.registrar(db, cid, empleado, "Efectivo", 0, [{"product_id": pid, "quantity": 1}])
    ventas_srv.registrar(db, cid, empleado, "Efectivo", 0, [{"product_id": pid, "quantity": 2}])
    devoluciones_srv.cancelar_venta(db, s1, "x")
    assert clientes.resumen_compras(db, cid)["compras"] == 1
    assert {r["estado"] for r in clientes.historial(db, cid)} == {"ACTIVA", "CANCELADA"}


@tc("ATS_VD_07", nivel="ATS", modulo="reportes", reqs=["RF-15", "RF-16", "RF-17", "RF-18", "RF-19", "RF-20", "RF-21", "RF-22", "RF-23", "RF-24", "RF-25", "RF-26"],
    nombre="VD-07 Los reportes RF-15 a RF-26 se ejecutan sin error")
def test_vd07_todos_los_reportes_rf15_a_rf26_se_ejecutan_sin_error(db, empleado):
    """Cada uno de los doce reportes solicitados responde con datos reales.

    Precondiciones: Una venta registrada.
    Pasos:
    - Ejecutar cada reporte con su parámetro
    Esperado:
    - Ningún reporte lanza excepción
    """
    pid = alta(db, "R1")
    sid, *_ = ventas_srv.registrar(db, None, empleado, "Efectivo", 0, [{"product_id": pid, "quantity": 1}])
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
