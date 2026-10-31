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
    """Verificar tres reportes de catálogo de reportes_repo.ejecutar(db, nombre, parametro)
    (mis_trapitos/data/repositories/reportes.py): 'Productos disponibles por categoria' (RF-15, solo
    stock > 0 de la categoría pedida), 'Productos en oferta' (RF-16, solo promociones vigentes hoy) y
    'Producto con mayor descuento vigente' (RF-24, una sola fila con el mayor porcentaje).

    Precondiciones: Fixture mundo de tests/test_reportes.py: un conjunto de datos conocido. Proveedor
      'Textiles Norte'; productos BL Blusa (Ropa, $200, proveedor Textiles Norte), ZA Zapato (Calzado,
      $500), BO Bolsa (Accesorios, $150, stock 0) y VI Abrigo (Ropa, $900); clientes Ana (Guadalajara) y
      Beto (Zapopan); ventas v1 Ana BL×2 hace 20 días (Efectivo), v2 Ana BL×1 + ZA×1 hoy (Débito), v3 Beto
      ZA×1 hace 2 días (Efectivo), v4 Beto VI×1 hace 150 días (Efectivo) y v5 Ana BL×1 hoy (Crédito)
      CANCELADA; promociones vigentes BL 15 % y ZA 30 %, y una vencida de VI 50 %. Stock final: BL 7, ZA
      2, BO 0, VI 2.
    Pasos:
    - Llamar reportes_repo.ejecutar(db, 'Productos disponibles por categoria', 'Ropa') y con
      'Accesorios'.
    - En test_rf15_requiere_categoria: llamar el mismo reporte con parámetro vacío ''.
    - En test_rf16_y_rf24_ofertas_vigentes_y_mayor_descuento: ejecutar 'Productos en oferta' y 'Producto
      con mayor descuento vigente'.
    Esperado:
    - 'Ropa' regresa los códigos {BL, VI}; 'Accesorios' regresa [] porque BO tiene stock 0.
    - Sin categoría se levanta ValueError (mensaje con 'categoria').
    - 'Productos en oferta' regresa [ZA, BL] (la de VI ya venció); el mayor descuento es una sola fila:
      ZA con 30 %.
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
    """Verificar los reportes agrupados 'Metodos de pago mas utilizados' (RF-17) y 'Compras por ciudad o
    region' (RF-25) de reportes_repo.ejecutar(). Ambos deben contar solo ventas con status ACTIVA: una
    venta cancelada no es una compra real.

    Precondiciones: Fixture mundo de tests/test_reportes.py: un conjunto de datos conocido. Proveedor
      'Textiles Norte'; productos BL Blusa (Ropa, $200, proveedor Textiles Norte), ZA Zapato (Calzado,
      $500), BO Bolsa (Accesorios, $150, stock 0) y VI Abrigo (Ropa, $900); clientes Ana (Guadalajara) y
      Beto (Zapopan); ventas v1 Ana BL×2 hace 20 días (Efectivo), v2 Ana BL×1 + ZA×1 hoy (Débito), v3 Beto
      ZA×1 hace 2 días (Efectivo), v4 Beto VI×1 hace 150 días (Efectivo) y v5 Ana BL×1 hoy (Crédito)
      CANCELADA; promociones vigentes BL 15 % y ZA 30 %, y una vencida de VI 50 %. Stock final: BL 7, ZA
      2, BO 0, VI 2.
    Pasos:
    - Llamar reportes_repo.ejecutar(db, 'Metodos de pago mas utilizados') y armar {metodo: ventas}.
    - En test_rf25_compras_por_region: llamar ejecutar(db, 'Compras por ciudad o region') y armar
      {region: compras}.
    Esperado:
    - Métodos de pago = {Efectivo: 3, Tarjeta de debito: 1}; la v5 cancelada (Tarjeta de credito) no
      aparece.
    - Compras por región = {Guadalajara: 2, Zapopan: 2}.
    """
    filas = {r["metodo"]: r["ventas"] for r in reportes_repo.ejecutar(db, "Metodos de pago mas utilizados")}
    assert filas == {"Efectivo": 3, "Tarjeta de debito": 1}


@tc("ITS_REP_03", nivel="ITS", modulo="reportes", reqs=["RF-18", "RF-22"],
    nombre="Reportes con ventana de último mes")
def test_rf18_mas_vendidos_ultimo_mes_excluye_venta_vieja(db, mundo):
    """Verificar los reportes con ventana del último mes (30 días): 'Productos mas vendidos ultimo mes'
    (RF-18) y 'Productos vendidos por categoria ultimo mes' (RF-22). Solo deben contar ventas ACTIVAS
    dentro de la ventana; la venta de hace 150 días y la cancelada quedan fuera.

    Precondiciones: Fixture mundo de tests/test_reportes.py: un conjunto de datos conocido. Proveedor
      'Textiles Norte'; productos BL Blusa (Ropa, $200, proveedor Textiles Norte), ZA Zapato (Calzado,
      $500), BO Bolsa (Accesorios, $150, stock 0) y VI Abrigo (Ropa, $900); clientes Ana (Guadalajara) y
      Beto (Zapopan); ventas v1 Ana BL×2 hace 20 días (Efectivo), v2 Ana BL×1 + ZA×1 hoy (Débito), v3 Beto
      ZA×1 hace 2 días (Efectivo), v4 Beto VI×1 hace 150 días (Efectivo) y v5 Ana BL×1 hoy (Crédito)
      CANCELADA; promociones vigentes BL 15 % y ZA 30 %, y una vencida de VI 50 %. Stock final: BL 7, ZA
      2, BO 0, VI 2.
    Pasos:
    - Llamar reportes_repo.ejecutar(db, 'Productos mas vendidos ultimo mes') y armar {codigo: piezas}.
    - En test_rf22_vendidos_por_categoria_ultimo_mes: ejecutar 'Productos vendidos por categoria ultimo
      mes' con 'Calzado' y con 'Accesorios'.
    Esperado:
    - Más vendidos = {BL: 3, ZA: 2}; VI (vendido hace 150 días) no aparece.
    - Calzado regresa solo ZA con 2 piezas; Accesorios regresa [].
    """
    filas = {r["codigo"]: r["piezas"] for r in reportes_repo.ejecutar(db, "Productos mas vendidos ultimo mes")}
    assert filas == {"BL": 3, "ZA": 2} and "VI" not in filas


@tc("ITS_REP_04", nivel="ITS", modulo="reportes", reqs=["RF-19"],
    nombre="Ventas de los últimos tres días")
def test_rf19_ventas_ultimos_tres_dias(db, mundo):
    """Verificar el reporte 'Ventas ultimos tres dias' (RF-19) de reportes_repo.ejecutar(): debe traer solo
    ventas cuya fecha esté dentro de los últimos 3 días.

    Precondiciones: Fixture mundo de tests/test_reportes.py: un conjunto de datos conocido. Proveedor
      'Textiles Norte'; productos BL Blusa (Ropa, $200, proveedor Textiles Norte), ZA Zapato (Calzado,
      $500), BO Bolsa (Accesorios, $150, stock 0) y VI Abrigo (Ropa, $900); clientes Ana (Guadalajara) y
      Beto (Zapopan); ventas v1 Ana BL×2 hace 20 días (Efectivo), v2 Ana BL×1 + ZA×1 hoy (Débito), v3 Beto
      ZA×1 hace 2 días (Efectivo), v4 Beto VI×1 hace 150 días (Efectivo) y v5 Ana BL×1 hoy (Crédito)
      CANCELADA; promociones vigentes BL 15 % y ZA 30 %, y una vencida de VI 50 %. Stock final: BL 7, ZA
      2, BO 0, VI 2.
    Pasos:
    - Llamar reportes_repo.ejecutar(db, 'Ventas ultimos tres dias').
    - Juntar los ids de venta de la columna 'venta'.
    - Revisar que cada 'fecha' sea >= hoy − 3 días (dias(-3) de tests/conftest.py).
    Esperado:
    - Hay al menos 2 ventas (v2 de hoy y v3 de hace 2 días); v1 de hace 20 días no aparece.
    - Todas las fechas están dentro de la ventana de 3 días.
    Comentarios: El SDD (brecha B-05) señala que hoy este reporte también incluye ventas canceladas
      (v5); por eso la prueba pide 'al menos 2' en lugar de un número exacto, hasta que negocio defina el
      criterio.
    """
    ids = {r["venta"] for r in reportes_repo.ejecutar(db, "Ventas ultimos tres dias")}
    assert len(ids) >= 2          # v2 (hoy), v5 cancelada (hoy) y v3 (hace 2 días); v1 (hace 20) no
    assert all(r["fecha"] >= dias(-3)[:10] for r in reportes_repo.ejecutar(db, "Ventas ultimos tres dias"))


@tc("ITS_REP_05", nivel="ITS", modulo="reportes", reqs=["RF-20", "RF-21"],
    nombre="Reportes con parámetro: por proveedor y compras repetidas por cliente")
def test_rf20_productos_por_proveedor_por_id_y_por_nombre_parcial(db, mundo):
    """Verificar los dos reportes que reciben parámetro de búsqueda: 'Productos de proveedor especifico'
    (RF-20, acepta el id del proveedor o parte de su nombre) y 'Productos comprados mas de una vez por
    cliente' (RF-21, requiere el id numérico del cliente). Ambos validan el parámetro faltante o
    inválido con ValueError.

    Precondiciones: Fixture mundo de tests/test_reportes.py: un conjunto de datos conocido. Proveedor
      'Textiles Norte'; productos BL Blusa (Ropa, $200, proveedor Textiles Norte), ZA Zapato (Calzado,
      $500), BO Bolsa (Accesorios, $150, stock 0) y VI Abrigo (Ropa, $900); clientes Ana (Guadalajara) y
      Beto (Zapopan); ventas v1 Ana BL×2 hace 20 días (Efectivo), v2 Ana BL×1 + ZA×1 hoy (Débito), v3 Beto
      ZA×1 hace 2 días (Efectivo), v4 Beto VI×1 hace 150 días (Efectivo) y v5 Ana BL×1 hoy (Crédito)
      CANCELADA; promociones vigentes BL 15 % y ZA 30 %, y una vencida de VI 50 %. Stock final: BL 7, ZA
      2, BO 0, VI 2.
    Pasos:
    - Llamar reportes_repo.ejecutar(db, 'Productos de proveedor especifico', str(id_proveedor)).
    - Llamarlo con el nombre parcial 'norte' y luego con ''.
    - En test_rf21_productos_repetidos_por_cliente: ejecutar 'Productos comprados mas de una vez por
      cliente' con el id de Ana y luego con 'abc'.
    Esperado:
    - Por id y por 'norte' regresa [BL]; sin parámetro levanta ValueError.
    - Para Ana regresa [BL] con piezas = 3 (v1 + v2); con 'abc' levanta ValueError.
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
    """Verificar los reportes de inventario y operación de reportes_repo.ejecutar(): 'Productos con precio
    superior y existencias' (RF-23, comparación estricta >), 'Productos no vendidos ultimos tres meses'
    (RF-26), 'Inventario general actualizado' y 'Productos con stock bajo' (RF-03), 'Ventas por
    empleado', 'Resumen de utilidades' y el error para un nombre de reporte que no existe.

    Precondiciones: Fixture mundo de tests/test_reportes.py: un conjunto de datos conocido. Proveedor
      'Textiles Norte'; productos BL Blusa (Ropa, $200, proveedor Textiles Norte), ZA Zapato (Calzado,
      $500), BO Bolsa (Accesorios, $150, stock 0) y VI Abrigo (Ropa, $900); clientes Ana (Guadalajara) y
      Beto (Zapopan); ventas v1 Ana BL×2 hace 20 días (Efectivo), v2 Ana BL×1 + ZA×1 hoy (Débito), v3 Beto
      ZA×1 hace 2 días (Efectivo), v4 Beto VI×1 hace 150 días (Efectivo) y v5 Ana BL×1 hoy (Crédito)
      CANCELADA; promociones vigentes BL 15 % y ZA 30 %, y una vencida de VI 50 %. Stock final: BL 7, ZA
      2, BO 0, VI 2. Para el reporte inexistente basta la fixture db.
    Pasos:
    - Ejecutar 'Productos con precio superior y existencias' con '200' y con '900'.
    - En test_rf26_sin_ventas_en_tres_meses: ejecutar 'Productos no vendidos ultimos tres meses'.
    - En test_inventario_general_y_stock_bajo: ejecutar 'Inventario general actualizado' y 'Productos
      con stock bajo' con '3'.
    - En test_ventas_por_empleado_y_resumen_de_utilidades: ejecutar 'Ventas por empleado' y 'Resumen de
      utilidades'.
    - En test_reporte_inexistente_levanta_error: ejecutar 'Reporte fantasma'.
    Esperado:
    - Precio > 200 regresa [VI, ZA]; precio > 900 regresa [] (900 no es mayor que 900).
    - Sin ventas en tres meses: {BO, VI}.
    - Inventario general tiene 4 filas; stock ≤ 3: {BO, VI, ZA}.
    - El empleado tiene 4 ventas activas (v1 a v4) y la utilidad de ZA es > 0.
    - El reporte inexistente levanta ValueError 'Reporte no reconocido'.
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
