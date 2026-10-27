"""Reportes RF-15 … RF-26 contra un conjunto de datos conocido."""
import pytest

from tests.conftest import dias
from mis_trapitos.services import devoluciones as devoluciones_srv
from mis_trapitos.services import ventas as ventas_srv
from mis_trapitos.data.repositories import clientes as clientes_repo
from mis_trapitos.data.repositories import promociones as promociones_repo
from mis_trapitos.data.repositories import proveedores as proveedores_repo
from mis_trapitos.data.repositories import reportes as reportes_repo
from tests.tc import tc


@pytest.fixture
def mundo(db, empleado, make_product):
    """Catálogo y ventas con fechas controladas; devuelve ids útiles."""
    prov = proveedores_repo.guardar(db, None, ("Textiles Norte", "555", "Av 1", "Ropa", dias(0)[:10]))
    blusa = make_product("BL", "Blusa", "Ropa", price=200, stock=10, supplier_id=prov)
    zapato = make_product("ZA", "Zapato", "Calzado", price=500, stock=4)
    bolsa = make_product("BO", "Bolsa", "Accesorios", price=150, stock=0)
    viejo = make_product("VI", "Abrigo", "Ropa", price=900, stock=3)
    cli = clientes_repo.guardar(db, None, ("Ana", "555-1", "a@x.com", "Calle", "Guadalajara", ""))
    cli2 = clientes_repo.guardar(db, None, ("Beto", "555-2", "b@x.com", "Calle", "Zapopan", ""))
    v1, *_ = ventas_srv.registrar(db, cli, empleado, "Efectivo", 0, [{"product_id": blusa, "quantity": 2}])
    v2, *_ = ventas_srv.registrar(db, cli, empleado, "Tarjeta de debito", 0, [{"product_id": blusa, "quantity": 1},
                                                                       {"product_id": zapato, "quantity": 1}])
    v3, *_ = ventas_srv.registrar(db, cli2, empleado, "Efectivo", 0, [{"product_id": zapato, "quantity": 1}])
    # venta vieja (hace 5 meses) del abrigo y una cancelada
    v4, *_ = ventas_srv.registrar(db, cli2, empleado, "Efectivo", 0, [{"product_id": viejo, "quantity": 1}])
    db.execute("UPDATE sales SET sale_datetime=? WHERE id=?", (dias(-150), v4))
    v5, *_ = ventas_srv.registrar(db, cli, empleado, "Tarjeta de credito", 0, [{"product_id": blusa, "quantity": 1}])
    devoluciones_srv.cancelar_venta(db, v5, "x")
    db.execute("UPDATE sales SET sale_datetime=? WHERE id=?", (dias(-2), v3))
    db.execute("UPDATE sales SET sale_datetime=? WHERE id=?", (dias(-20), v1))
    promociones_repo.guardar(db, None, blusa, 15, dias(-1)[:10], dias(5)[:10])
    promociones_repo.guardar(db, None, zapato, 30, dias(-1)[:10], dias(5)[:10])
    promociones_repo.guardar(db, None, viejo, 50, dias(-30)[:10], dias(-10)[:10])
    return dict(prov=prov, blusa=blusa, zapato=zapato, bolsa=bolsa, viejo=viejo, cli=cli, cli2=cli2)


def codigos(rows):
    return [r["codigo"] for r in rows]


@tc("ITS_REP_01", nivel="ITS", modulo="reportes", reqs=["RF-15", "RF-16", "RF-24"],
    nombre="Reportes de catálogo: disponibles por categoría, ofertas y mayor descuento")
def test_rf15_disponibles_por_categoria_excluye_sin_stock(db, mundo):
    """Los reportes filtran por stock>0, vigencia de promoción y devuelven solo el mayor descuento.

    Precondiciones: Conjunto de datos conocido (4 productos, 3 promociones, una vencida).
    Pasos:
    - Ejecutar disponibles por 'Ropa' y 'Accesorios'
    - Ejecutar sin categoría
    - Ejecutar ofertas y mayor descuento
    Esperado:
    - Solo productos con stock>0
    - ValueError al omitir categoría
    - La oferta vencida no aparece; el mayor descuento es 30 %
    """
    assert set(codigos(reportes_repo.ejecutar(db, "Productos disponibles por categoria", "Ropa"))) == {"BL", "VI"}
    assert reportes_repo.ejecutar(db, "Productos disponibles por categoria", "Accesorios") == []   # BO stock 0


@tc("ITS_REP_01")
def test_rf15_requiere_categoria(db, mundo):
    with pytest.raises(ValueError, match="categoria"):
        reportes_repo.ejecutar(db, "Productos disponibles por categoria", "")


@tc("ITS_REP_01")
def test_rf16_y_rf24_ofertas_vigentes_y_mayor_descuento(db, mundo):
    ofertas = reportes_repo.ejecutar(db, "Productos en oferta")
    assert codigos(ofertas) == ["ZA", "BL"]            # la del abrigo ya venció
    top = reportes_repo.ejecutar(db, "Producto con mayor descuento vigente")
    assert len(top) == 1 and top[0]["codigo"] == "ZA" and top[0]["descuento"] == 30


@tc("ITS_REP_02", nivel="ITS", modulo="reportes", reqs=["RF-17", "RF-25"],
    nombre="Reportes agrupados: métodos de pago y compras por región")
def test_rf17_metodos_de_pago_ignora_canceladas(db, mundo):
    """Las agrupaciones excluyen ventas canceladas y cuentan correctamente.

    Precondiciones: Conjunto de datos conocido con una venta cancelada.
    Pasos:
    - Ejecutar métodos de pago
    - Ejecutar compras por ciudad o región
    Esperado:
    - Efectivo 3, Tarjeta de débito 1 (la cancelada no cuenta)
    - Guadalajara 2 y Zapopan 2
    """
    filas = {r["metodo"]: r["ventas"] for r in reportes_repo.ejecutar(db, "Metodos de pago mas utilizados")}
    assert filas == {"Efectivo": 3, "Tarjeta de debito": 1}


@tc("ITS_REP_03", nivel="ITS", modulo="reportes", reqs=["RF-18", "RF-22"],
    nombre="Reportes con ventana de último mes")
def test_rf18_mas_vendidos_ultimo_mes_excluye_venta_vieja(db, mundo):
    """Solo cuentan ventas activas de los últimos 30 días.

    Precondiciones: Venta de hace 150 días y venta cancelada en el conjunto.
    Pasos:
    - Ejecutar más vendidos del último mes
    - Ejecutar vendidos por categoría 'Calzado' y 'Accesorios'
    Esperado:
    - BL=3 y ZA=2; el abrigo viejo no aparece
    - Calzado: ZA con 2 piezas; Accesorios vacío
    """
    filas = {r["codigo"]: r["piezas"] for r in reportes_repo.ejecutar(db, "Productos mas vendidos ultimo mes")}
    assert filas == {"BL": 3, "ZA": 2} and "VI" not in filas


@tc("ITS_REP_04", nivel="ITS", modulo="reportes", reqs=["RF-19"],
    nombre="Ventas de los últimos tres días")
def test_rf19_ventas_ultimos_tres_dias(db, mundo):
    """El reporte solo contiene ventas dentro de la ventana de tres días.

    Precondiciones: Ventas de hoy, hace 2 días y hace 20 días.
    Pasos:
    - Ejecutar el reporte
    - Revisar las fechas devueltas
    Esperado:
    - Todas las fechas >= hoy − 3 días
    - Al menos 2 ventas
    """
    ids = {r["venta"] for r in reportes_repo.ejecutar(db, "Ventas ultimos tres dias")}
    assert len(ids) >= 2          # v2 (hoy), v5 cancelada (hoy) y v3 (hace 2 días); v1 (hace 20) no
    assert all(r["fecha"] >= dias(-3)[:10] for r in reportes_repo.ejecutar(db, "Ventas ultimos tres dias"))


@tc("ITS_REP_05", nivel="ITS", modulo="reportes", reqs=["RF-20", "RF-21"],
    nombre="Reportes con parámetro: por proveedor y compras repetidas por cliente")
def test_rf20_productos_por_proveedor_por_id_y_por_nombre_parcial(db, mundo):
    """Aceptan id o nombre parcial y validan parámetros faltantes o no numéricos.

    Precondiciones: Proveedor 'Textiles Norte' y cliente con 3 piezas de BL en dos compras.
    Pasos:
    - Consultar por id de proveedor
    - Por nombre parcial 'norte'
    - Sin parámetro
    - Repetidos por cliente con id válido y con 'abc'
    Esperado:
    - Ambos regresan BL
    - ValueError sin parámetro
    - BL con 3 piezas; 'abc' levanta ValueError
    """
    assert codigos(reportes_repo.ejecutar(db, "Productos de proveedor especifico", str(mundo["prov"]))) == ["BL"]
    assert codigos(reportes_repo.ejecutar(db, "Productos de proveedor especifico", "norte")) == ["BL"]
    with pytest.raises(ValueError):
        reportes_repo.ejecutar(db, "Productos de proveedor especifico", "")


@tc("ITS_REP_05")
def test_rf21_productos_repetidos_por_cliente(db, mundo):
    filas = reportes_repo.ejecutar(db, "Productos comprados mas de una vez por cliente", str(mundo["cli"]))
    assert codigos(filas) == ["BL"] and filas[0]["piezas"] == 3
    with pytest.raises(ValueError):
        reportes_repo.ejecutar(db, "Productos comprados mas de una vez por cliente", "abc")


@tc("ITS_REP_03")
def test_rf22_vendidos_por_categoria_ultimo_mes(db, mundo):
    filas = reportes_repo.ejecutar(db, "Productos vendidos por categoria ultimo mes", "Calzado")
    assert codigos(filas) == ["ZA"] and filas[0]["piezas"] == 2
    assert reportes_repo.ejecutar(db, "Productos vendidos por categoria ultimo mes", "Accesorios") == []


@tc("ITS_REP_06", nivel="ITS", modulo="reportes", reqs=["RF-23", "RF-26", "RF-03"],
    nombre="Reportes de inventario: precio superior, sin ventas, stock bajo e inventario general")
def test_rf23_precio_superior_estricto_con_existencias(db, mundo):
    """Comparación estricta de precio, exclusión por ventana de 3 meses y reportes operativos.

    Precondiciones: Conjunto de datos conocido.
    Pasos:
    - Precio superior a 200 y a 900
    - Productos no vendidos en tres meses
    - Stock bajo (≤3)
    - Reporte inexistente
    Esperado:
    - Comparación estricta (>)
    - Solo BO y VI
    - BO, VI y ZA
    - ValueError 'Reporte no reconocido'
    """
    assert codigos(reportes_repo.ejecutar(db, "Productos con precio superior y existencias", "200")) == ["VI", "ZA"]
    assert codigos(reportes_repo.ejecutar(db, "Productos con precio superior y existencias", "900")) == []


@tc("ITS_REP_02")
def test_rf25_compras_por_region(db, mundo):
    filas = {r["region"]: r["compras"] for r in reportes_repo.ejecutar(db, "Compras por ciudad o region")}
    assert filas == {"Guadalajara": 2, "Zapopan": 2}


@tc("ITS_REP_06")
def test_rf26_sin_ventas_en_tres_meses(db, mundo):
    assert set(codigos(reportes_repo.ejecutar(db, "Productos no vendidos ultimos tres meses"))) == {"BO", "VI"}


@tc("ITS_REP_06")
def test_inventario_general_y_stock_bajo(db, mundo):
    assert len(reportes_repo.ejecutar(db, "Inventario general actualizado")) == 4
    assert set(codigos(reportes_repo.ejecutar(db, "Productos con stock bajo", "3"))) == {"BO", "VI", "ZA"}


@tc("ITS_REP_06")
def test_reporte_inexistente_levanta_error(db):
    with pytest.raises(ValueError, match="no reconocido"):
        reportes_repo.ejecutar(db, "Reporte fantasma")


@tc("ITS_CON_01")
def test_historial_de_cliente_incluye_estado_de_cada_venta(db, mundo):
    estados = {r["estado"] for r in clientes_repo.historial(db, mundo["cli"])}
    assert estados == {"ACTIVA", "CANCELADA"}


@tc("ITS_REP_06")
def test_ventas_por_empleado_y_resumen_de_utilidades(db, mundo):
    emp = reportes_repo.ejecutar(db, "Ventas por empleado")[0]
    assert emp["ventas"] == 4        # v1..v4 activas
    util = {r["codigo"]: r["utilidad"] for r in reportes_repo.ejecutar(db, "Resumen de utilidades")}
    assert util["ZA"] > 0
