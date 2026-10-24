"""Reportes RF-15 … RF-26 contra un conjunto de datos conocido."""
import pytest

from tests.conftest import dias


@pytest.fixture
def mundo(db, empleado, make_product):
    """Catálogo y ventas con fechas controladas; devuelve ids útiles."""
    prov = db.save_supplier(None, ("Textiles Norte", "555", "Av 1", "Ropa", dias(0)[:10]))
    blusa = make_product("BL", "Blusa", "Ropa", price=200, stock=10, supplier_id=prov)
    zapato = make_product("ZA", "Zapato", "Calzado", price=500, stock=4)
    bolsa = make_product("BO", "Bolsa", "Accesorios", price=150, stock=0)
    viejo = make_product("VI", "Abrigo", "Ropa", price=900, stock=3)
    cli = db.save_customer(None, ("Ana", "555-1", "a@x.com", "Calle", "Guadalajara", ""))
    cli2 = db.save_customer(None, ("Beto", "555-2", "b@x.com", "Calle", "Zapopan", ""))
    v1, *_ = db.register_sale(cli, empleado, "Efectivo", 0, [{"product_id": blusa, "quantity": 2}])
    v2, *_ = db.register_sale(cli, empleado, "Tarjeta de debito", 0, [{"product_id": blusa, "quantity": 1},
                                                                       {"product_id": zapato, "quantity": 1}])
    v3, *_ = db.register_sale(cli2, empleado, "Efectivo", 0, [{"product_id": zapato, "quantity": 1}])
    # venta vieja (hace 5 meses) del abrigo y una cancelada
    v4, *_ = db.register_sale(cli2, empleado, "Efectivo", 0, [{"product_id": viejo, "quantity": 1}])
    db.execute("UPDATE sales SET sale_datetime=? WHERE id=?", (dias(-150), v4))
    v5, *_ = db.register_sale(cli, empleado, "Tarjeta de credito", 0, [{"product_id": blusa, "quantity": 1}])
    db.cancel_sale(v5, "x")
    db.execute("UPDATE sales SET sale_datetime=? WHERE id=?", (dias(-2), v3))
    db.execute("UPDATE sales SET sale_datetime=? WHERE id=?", (dias(-20), v1))
    db.save_promotion(None, blusa, 15, dias(-1)[:10], dias(5)[:10])
    db.save_promotion(None, zapato, 30, dias(-1)[:10], dias(5)[:10])
    db.save_promotion(None, viejo, 50, dias(-30)[:10], dias(-10)[:10])
    return dict(prov=prov, blusa=blusa, zapato=zapato, bolsa=bolsa, viejo=viejo, cli=cli, cli2=cli2)


def codigos(rows):
    return [r["codigo"] for r in rows]


def test_rf15_disponibles_por_categoria_excluye_sin_stock(db, mundo):
    assert set(codigos(db.report("Productos disponibles por categoria", "Ropa"))) == {"BL", "VI"}
    assert db.report("Productos disponibles por categoria", "Accesorios") == []   # BO stock 0


def test_rf15_requiere_categoria(db, mundo):
    with pytest.raises(ValueError, match="categoria"):
        db.report("Productos disponibles por categoria", "")


def test_rf16_y_rf24_ofertas_vigentes_y_mayor_descuento(db, mundo):
    ofertas = db.report("Productos en oferta")
    assert codigos(ofertas) == ["ZA", "BL"]            # la del abrigo ya venció
    top = db.report("Producto con mayor descuento vigente")
    assert len(top) == 1 and top[0]["codigo"] == "ZA" and top[0]["descuento"] == 30


def test_rf17_metodos_de_pago_ignora_canceladas(db, mundo):
    filas = {r["metodo"]: r["ventas"] for r in db.report("Metodos de pago mas utilizados")}
    assert filas == {"Efectivo": 3, "Tarjeta de debito": 1}


def test_rf18_mas_vendidos_ultimo_mes_excluye_venta_vieja(db, mundo):
    filas = {r["codigo"]: r["piezas"] for r in db.report("Productos mas vendidos ultimo mes")}
    assert filas == {"BL": 3, "ZA": 2} and "VI" not in filas


def test_rf19_ventas_ultimos_tres_dias(db, mundo):
    ids = {r["venta"] for r in db.report("Ventas ultimos tres dias")}
    assert len(ids) >= 2          # v2 (hoy), v5 cancelada (hoy) y v3 (hace 2 días); v1 (hace 20) no
    assert all(r["fecha"] >= dias(-3)[:10] for r in db.report("Ventas ultimos tres dias"))


def test_rf20_productos_por_proveedor_por_id_y_por_nombre_parcial(db, mundo):
    assert codigos(db.report("Productos de proveedor especifico", str(mundo["prov"]))) == ["BL"]
    assert codigos(db.report("Productos de proveedor especifico", "norte")) == ["BL"]
    with pytest.raises(ValueError):
        db.report("Productos de proveedor especifico", "")


def test_rf21_productos_repetidos_por_cliente(db, mundo):
    filas = db.report("Productos comprados mas de una vez por cliente", str(mundo["cli"]))
    assert codigos(filas) == ["BL"] and filas[0]["piezas"] == 3
    with pytest.raises(ValueError):
        db.report("Productos comprados mas de una vez por cliente", "abc")


def test_rf22_vendidos_por_categoria_ultimo_mes(db, mundo):
    filas = db.report("Productos vendidos por categoria ultimo mes", "Calzado")
    assert codigos(filas) == ["ZA"] and filas[0]["piezas"] == 2
    assert db.report("Productos vendidos por categoria ultimo mes", "Accesorios") == []


def test_rf23_precio_superior_estricto_con_existencias(db, mundo):
    assert codigos(db.report("Productos con precio superior y existencias", "200")) == ["VI", "ZA"]
    assert codigos(db.report("Productos con precio superior y existencias", "900")) == []


def test_rf25_compras_por_region(db, mundo):
    filas = {r["region"]: r["compras"] for r in db.report("Compras por ciudad o region")}
    assert filas == {"Guadalajara": 2, "Zapopan": 2}


def test_rf26_sin_ventas_en_tres_meses(db, mundo):
    assert set(codigos(db.report("Productos no vendidos ultimos tres meses"))) == {"BO", "VI"}


def test_inventario_general_y_stock_bajo(db, mundo):
    assert len(db.report("Inventario general actualizado")) == 4
    assert set(codigos(db.report("Productos con stock bajo", "3"))) == {"BO", "VI", "ZA"}


def test_reporte_inexistente_levanta_error(db):
    with pytest.raises(ValueError, match="no reconocido"):
        db.report("Reporte fantasma")


def test_historial_de_cliente_incluye_estado_de_cada_venta(db, mundo):
    estados = {r["estado"] for r in db.customer_history(mundo["cli"])}
    assert estados == {"ACTIVA", "CANCELADA"}


def test_ventas_por_empleado_y_resumen_de_utilidades(db, mundo):
    emp = db.report("Ventas por empleado")[0]
    assert emp["ventas"] == 4        # v1..v4 activas
    util = {r["codigo"]: r["utilidad"] for r in db.report("Resumen de utilidades")}
    assert util["ZA"] > 0
