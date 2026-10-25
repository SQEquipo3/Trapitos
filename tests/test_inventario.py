"""Pruebas de productos e inventario (RF-01, RF-02, RF-03, RF-05, RF-14, RNF-01)."""
import sqlite3

import pytest

from mis_trapitos.data.repositories import productos
from utils import dinero, hash_password, today_text
from tests.conftest import stock
from mis_trapitos.services import devoluciones as devoluciones_srv
from mis_trapitos.services import ventas as ventas_srv
from mis_trapitos.data.repositories import empleados as empleados_repo
from mis_trapitos.data.repositories import proveedores as proveedores_repo


def datos(code="BL-01", stock_=5, price=200, purchase=80, size="M", color="Azul", supplier=None):
    return (code, "Blusa", "Ropa", size, color, purchase, price, stock_, supplier,
            today_text(), "Marca", "Todo", "")


# ---------- unitarias ----------
def test_alta_producto_guarda_datos(db):
    pid = productos.guardar(db, None, datos())
    p = productos.obtener_por_id(db, pid)
    assert (p["code"], p["stock"], p["sale_price"]) == ("BL-01", 5, 200)


def test_codigo_duplicado_es_rechazado(db):
    productos.guardar(db, None, datos("DUP"))
    with pytest.raises(sqlite3.IntegrityError):
        productos.guardar(db, None, datos("DUP"))


@pytest.mark.parametrize("campo", ["stock", "precio", "costo"])
def test_valores_negativos_son_rechazados(db, campo):
    kw = {"stock": dict(stock_=-1), "precio": dict(price=-5), "costo": dict(purchase=-5)}[campo]
    with pytest.raises(sqlite3.IntegrityError):
        productos.guardar(db, None, datos(**kw))


def test_misma_prenda_distinta_talla_color_tiene_stock_propio(db):
    a = productos.guardar(db, None, datos("BL-M-AZ", 3, size="M", color="Azul"))
    b = productos.guardar(db, None, datos("BL-L-RO", 7, size="L", color="Rojo"))
    assert (productos.obtener_por_id(db, a)["stock"], productos.obtener_por_id(db, b)["stock"]) == (3, 7)


def test_buscar_producto_por_codigo_y_producto_inexistente(db):
    pid = productos.guardar(db, None, datos("BUSCA"))
    assert productos.obtener_por_codigo(db, "BUSCA")["id"] == pid
    assert productos.obtener_por_codigo(db, "NO-EXISTE") is None


def test_hash_password_es_sha256_determinista():
    assert hash_password("1234") == hash_password("1234")
    assert len(hash_password("1234")) == 64 and hash_password("1234") != hash_password("1235")


def test_dinero_formatea_y_tolera_basura():
    assert dinero(1234.5) == "$1,234.50"
    assert dinero("abc") == "$0.00"


def test_autenticacion_valida_e_invalida(db, empleado):
    assert empleados_repo.autenticar(db, "vende", "1234") is not None
    assert empleados_repo.autenticar(db, "vende", "mala") is None
    assert empleados_repo.autenticar(db, "fantasma", "1234") is None


# ---------- integración ----------
def test_alta_registra_movimiento_de_entrada(db):
    pid = productos.guardar(db, None, datos(stock_=9))
    mov = db.one("SELECT * FROM inventory_movements WHERE product_id=?", (pid,))
    assert (mov["movement_type"], mov["quantity"]) == ("ENTRADA", 9)


def test_edicion_de_stock_registra_ajuste_con_diferencia(db):
    pid = productos.guardar(db, None, datos(stock_=10))
    productos.guardar(db, pid, datos(stock_=14))
    productos.guardar(db, pid, datos(stock_=11))
    ajustes = [r["quantity"] for r in db.query(
        "SELECT quantity FROM inventory_movements WHERE movement_type='AJUSTE' ORDER BY id")]
    assert ajustes == [4, -3]


def test_edicion_sin_cambio_de_stock_no_genera_movimiento(db):
    pid = productos.guardar(db, None, datos(stock_=10))
    productos.guardar(db, pid, datos(stock_=10, price=250))
    assert db.scalar("SELECT COUNT(*) FROM inventory_movements") == 1


def test_stock_es_suma_de_movimientos(db, empleado):
    """RNF-01: el stock visible siempre concilia con el kardex."""
    pid = productos.guardar(db, None, datos(stock_=10))
    ventas_srv.registrar(db, None, empleado, "Efectivo", 0, [{"product_id": pid, "quantity": 4}])
    devoluciones_srv.devolver(db, 1, pid, 1, "talla")
    productos.guardar(db, pid, datos(stock_=20))
    kardex = db.scalar("SELECT SUM(quantity) FROM inventory_movements WHERE product_id=?", (pid,))
    assert kardex == stock(db, pid) == 20


def test_producto_con_proveedor_inexistente_es_rechazado(db):
    """RF-14: la FK impide ligar un producto a un proveedor que no existe."""
    with pytest.raises(sqlite3.IntegrityError):
        productos.guardar(db, None, datos(supplier=999))


def test_producto_con_proveedor_existente_se_lista_con_su_nombre(db):
    sid = proveedores_repo.guardar(db, None, ("Textiles SA", "555", "Calle 1", "Blusas", today_text()))
    productos.guardar(db, None, datos(supplier=sid))
    assert productos.listar_inventario(db)[0]["proveedor"] == "Textiles SA"
