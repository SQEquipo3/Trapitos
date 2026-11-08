"""Escenarios de aceptación automatizables (VD-01 … VD-07 del SDD, sección 10).

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
    """Escenario de aceptación VD-01 del SDD (sección 10), contado como lo vive la dueña de la tienda:
    registra un vestido en tres variantes de talla y color y las consulta en el inventario. Usa las
    mismas funciones que llama la pantalla de Productos: productos.guardar() y
    productos.listar_inventario(). RF-01, RF-02, RF-14.

    Precondiciones: Fixture db (base limpia).
    Pasos:
    - Llamar productos.guardar(db, None, (...)) tres veces para el Vestido: S/Rojo con stock 2, M/Rojo
      con 5 y M/Negro con 7.
    - Abrir el inventario con productos.listar_inventario(db).
    Esperado:
    - El inventario tiene tres filas con existencias 2, 5 y 7.
    """
    for talla, color, n in (("S", "Rojo", 2), ("M", "Rojo", 5), ("M", "Negro", 7)):
        productos.guardar(db, None, (f"V-{talla}{color}", "Vestido", "Ropa", talla, color, 100, 300,
                                     n, None, today_text(), "M", "T", ""))
    inv = productos.listar_inventario(db)
    assert sorted(r["stock"] for r in inv) == [2, 5, 7]


@tc("ATS_VD_02", nivel="ATS", modulo="productos", reqs=["RF-03", "RF-05"],
    nombre="VD-02 Ajuste manual de inventario queda en kardex")
def test_vd02_ajuste_manual_queda_en_kardex(db):
    """Escenario de aceptación VD-02: un ajuste manual de existencias debe quedar en el kardex y verse en
    el reporte 'Entradas de mercancia'. Funciones: productos.guardar() (alta y edición) y
    reportes.ejecutar(db, 'Entradas de mercancia'). RF-03, RF-05.

    Precondiciones: Fixture db. Producto A1 creado con stock 10 (helper alta() del archivo).
    Pasos:
    - Editar el producto A1 con productos.guardar(db, pid, (...)) cambiando el stock a 15.
    - Ejecutar reportes.ejecutar(db, 'Entradas de mercancia').
    Esperado:
    - El reporte muestra dos entradas: 10 (alta) y 5 (ajuste).
    """
    pid = alta(db, "A1", stock_=10)
    productos.guardar(db, pid, ("A1", "Prenda A1", "Ropa", "M", "Azul", 80, 200, 15, None,
                                today_text(), "M", "T", ""))
    assert sorted(r["cantidad"] for r in reportes.ejecutar(db, "Entradas de mercancia")) == [5, 10]


@tc("ATS_VD_03", nivel="ATS", modulo="ventas", reqs=["RF-04", "RF-06", "RF-07", "RF-08", "RF-10"],
    nombre="VD-03 Día de venta con promoción y descuento general")
def test_vd03_dia_de_venta_con_promocion_y_descuento_general(db, empleado):
    """Escenario de aceptación VD-03: un día normal de venta con una promoción del 20 % y además un
    descuento general del 10 %, pagado con tarjeta de crédito y a un cliente registrado. Recorre
    ventas_srv.registrar() de punta a punta. RF-04, RF-06, RF-07, RF-08, RF-10.

    Precondiciones: Fixtures db y empleado. Producto S1 de $1000 con stock 10, promoción de 20 % vigente
      (promociones.guardar) y cliente 'Ana' (clientes.guardar).
    Pasos:
    - Llamar ventas_srv.registrar(db, cid, empleado, 'Tarjeta de credito', 10, [{'product_id': pid,
      'quantity': 2}]).
    - Leer el stock con stock(db, pid).
    Esperado:
    - Subtotal = 1600 (2 × $1000 × 0.8), descuento = 160, total = 1440.
    - Stock = 8.
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
    """Escenario de aceptación VD-04: el cliente devuelve parte de su compra y después se cancela el resto.
    El inventario debe quedar exacto y el reporte 'Productos devueltos o cancelados' debe mostrar ambas
    operaciones. Funciones: ventas_srv.registrar(), devoluciones_srv.devolver(),
    devoluciones_srv.cancelar_venta() y reportes.ejecutar(). RF-05.

    Precondiciones: Fixtures db y empleado. Producto D1 con stock 10.
    Pasos:
    - Vender 6 piezas con ventas_srv.registrar() (stock 4).
    - Devolver 2 con devoluciones_srv.devolver(db, sale_id, pid, 2, 'Defecto') (stock 6).
    - Cancelar con devoluciones_srv.cancelar_venta(db, sale_id, 'Cliente se arrepintió').
    - Ejecutar reportes.ejecutar(db, 'Productos devueltos o cancelados').
    Esperado:
    - Stock final = 10.
    - El reporte tiene un renglón DEVOLUCION y uno CANCELACION.
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
    """Escenario de aceptación VD-05: una oferta que ya venció no debe cambiar el precio de venta ni
    aparecer en el reporte de ofertas. Funciones: promociones.guardar(), ventas_srv.registrar() y
    reportes.ejecutar(db, 'Productos en oferta'). RF-09, RF-16.

    Precondiciones: Fixtures db y empleado. Producto P1 de $100 con una promoción de 50 % que terminó
      ayer (hoy−5 a hoy−1).
    Pasos:
    - Vender 1 pieza con ventas_srv.registrar(db, None, empleado, 'Efectivo', 0, [...]).
    - Ejecutar reportes.ejecutar(db, 'Productos en oferta').
    Esperado:
    - Subtotal = 100 (sin descuento).
    - El reporte de ofertas regresa [].
    """
    pid = alta(db, "P1", price=100)
    promociones.guardar(db, None, pid, 50, dias(-5)[:10], dias(-1)[:10])
    _, sub, *_ = ventas_srv.registrar(db, None, empleado, "Efectivo", 0, [{"product_id": pid, "quantity": 1}])
    assert sub == 100 and reportes.ejecutar(db, "Productos en oferta") == []


@tc("ATS_VD_06", nivel="ATS", modulo="contactos", reqs=["RF-11", "RF-12"],
    nombre="VD-06 Historial de cliente refleja cancelaciones")
def test_vd06_historial_de_cliente_refleja_cancelaciones(db, empleado):
    """Escenario de aceptación VD-06: el historial de un cliente debe mostrar todas sus compras con su
    estado, pero el resumen solo cuenta las compras activas. Funciones: clientes.historial() y
    clientes.resumen_compras() de mis_trapitos/data/repositories/clientes.py. RF-11, RF-12.

    Precondiciones: Fixtures db y empleado. Producto H1 y cliente 'Beto'.
    Pasos:
    - Registrar dos ventas al cliente con ventas_srv.registrar() (1 y 2 piezas).
    - Cancelar la primera con devoluciones_srv.cancelar_venta(db, s1, 'x').
    - Llamar clientes.resumen_compras(db, cid) y clientes.historial(db, cid).
    Esperado:
    - resumen_compras()['compras'] = 1.
    - El historial contiene los estados ACTIVA y CANCELADA.
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
    """Escenario de aceptación VD-07: la dueña puede ejecutar cada uno de los doce reportes que pidió
    (RF-15 a RF-26) sin que la aplicación marque error. Solo verifica que responden; los resultados
    exactos se prueban en ITS_REP_01 a ITS_REP_06.

    Precondiciones: Fixtures db y empleado. Producto R1 y una venta de 1 pieza.
    Pasos:
    - Para cada uno de los 12 nombres de reporte, llamar reportes.ejecutar(db, nombre, parametro), con
      parámetro 'Ropa', '1' o '10' en los que lo necesitan.
    Esperado:
    - Ningún reporte lanza excepción.
    - Se ejecutaron los 12 reportes.
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
