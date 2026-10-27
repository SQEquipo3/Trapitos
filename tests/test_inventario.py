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
from tests.tc import tc


def datos(code="BL-01", stock_=5, price=200, purchase=80, size="M", color="Azul", supplier=None):
    return (code, "Blusa", "Ropa", size, color, purchase, price, stock_, supplier,
            today_text(), "Marca", "Todo", "")


# ---------- unitarias ----------
@tc("UTS_PRO_01", nivel="UTS", modulo="productos", reqs=["RF-01"],
    nombre="Alta de producto y búsqueda por código")
def test_alta_producto_guarda_datos(db):
    """Verificar que productos.guardar persiste todos los campos del producto y que se puede
    recuperar por código; un código inexistente regresa None.

    Precondiciones: BD SQLite temporal vacía.
    Pasos:
    - Crear Database temporal
    - Guardar el producto BL-01 (stock 5, precio 200)
    - Consultar por id y por código
    - Consultar un código inexistente
    Esperado:
    - El producto se guarda con código, stock y precio capturados
    - La búsqueda por código regresa el mismo id
    - El código inexistente regresa None
    """
    pid = productos.guardar(db, None, datos())
    p = productos.obtener_por_id(db, pid)
    assert (p["code"], p["stock"], p["sale_price"]) == ("BL-01", 5, 200)


@tc("UTS_PRO_02", nivel="UTS", modulo="productos", reqs=["RF-01"],
    nombre="Código de producto duplicado es rechazado")
def test_codigo_duplicado_es_rechazado(db):
    """Garantizar la unicidad del código de producto (restricción UNIQUE).

    Precondiciones: Existe un producto con código DUP.
    Pasos:
    - Guardar producto DUP
    - Intentar guardar otro producto con el mismo código
    Esperado:
    - Se levanta IntegrityError
    - No se crea la segunda fila
    """
    productos.guardar(db, None, datos("DUP"))
    with pytest.raises(sqlite3.IntegrityError):
        productos.guardar(db, None, datos("DUP"))


@tc("UTS_PRO_03", nivel="UTS", modulo="productos", reqs=["RF-01", "RF-03"],
    nombre="Existencias, precio o costo negativos son rechazados")
@pytest.mark.parametrize("campo", ["stock", "precio", "costo"])
def test_valores_negativos_son_rechazados(db, campo):
    """Verificar las restricciones CHECK (stock>=0, precios>=0) del esquema.

    Precondiciones: BD temporal vacía.
    Pasos:
    - Intentar guardar producto con stock -1
    - Intentar guardar con precio de venta -5
    - Intentar guardar con costo -5
    Esperado:
    - Las tres operaciones levantan IntegrityError
    - No se inserta ningún producto
    """
    kw = {"stock": dict(stock_=-1), "precio": dict(price=-5), "costo": dict(purchase=-5)}[campo]
    with pytest.raises(sqlite3.IntegrityError):
        productos.guardar(db, None, datos(**kw))


@tc("UTS_PRO_04", nivel="UTS", modulo="productos", reqs=["RF-02"],
    nombre="Variantes talla/color con existencias propias")
def test_misma_prenda_distinta_talla_color_tiene_stock_propio(db):
    """Comprobar que la misma prenda en distinta talla o color maneja stock independiente.

    Precondiciones: BD temporal vacía.
    Pasos:
    - Guardar blusa M/Azul con stock 3
    - Guardar blusa L/Rojo con stock 7
    - Consultar el stock de cada variante
    Esperado:
    - La variante M/Azul tiene 3
    - La variante L/Rojo tiene 7
    """
    a = productos.guardar(db, None, datos("BL-M-AZ", 3, size="M", color="Azul"))
    b = productos.guardar(db, None, datos("BL-L-RO", 7, size="L", color="Rojo"))
    assert (productos.obtener_por_id(db, a)["stock"], productos.obtener_por_id(db, b)["stock"]) == (3, 7)


@tc("UTS_PRO_01")
def test_buscar_producto_por_codigo_y_producto_inexistente(db):
    pid = productos.guardar(db, None, datos("BUSCA"))
    assert productos.obtener_por_codigo(db, "BUSCA")["id"] == pid
    assert productos.obtener_por_codigo(db, "NO-EXISTE") is None


@tc("UTS_SEG_01", nivel="UTS", modulo="contactos", reqs=["SEG-01"],
    nombre="Hash de contraseña y autenticación")
def test_hash_password_es_sha256_determinista():
    """Verificar SHA-256 determinista y que empleados.autenticar solo acepta credenciales
    correctas.

    Precondiciones: Empleado 'vende' con contraseña 1234.
    Pasos:
    - Calcular hash dos veces
    - Autenticar con credenciales correctas
    - Con contraseña errónea
    - Con usuario inexistente
    Esperado:
    - Hash de 64 caracteres y estable
    - Credenciales correctas regresan el empleado
    - Las otras dos regresan None
    """
    assert hash_password("1234") == hash_password("1234")
    assert len(hash_password("1234")) == 64 and hash_password("1234") != hash_password("1235")


@tc("UTS_UTL_01", nivel="UTS", modulo="ventas", reqs=["RF-06"],
    nombre="Formato monetario")
def test_dinero_formatea_y_tolera_basura():
    """La función dinero() formatea importes y tolera valores no numéricos.

    Precondiciones: N/A
    Pasos:
    - dinero(1234.5)
    - dinero('abc')
    Esperado:
    - '$1,234.50'
    - '$0.00'
    """
    assert dinero(1234.5) == "$1,234.50"
    assert dinero("abc") == "$0.00"


@tc("UTS_SEG_01")
def test_autenticacion_valida_e_invalida(db, empleado):
    assert empleados_repo.autenticar(db, "vende", "1234") is not None
    assert empleados_repo.autenticar(db, "vende", "mala") is None
    assert empleados_repo.autenticar(db, "fantasma", "1234") is None


# ---------- integración ----------
@tc("ITS_INV_01", nivel="ITS", modulo="productos", reqs=["RF-03", "RF-05"],
    nombre="El alta de producto registra su movimiento de ENTRADA")
def test_alta_registra_movimiento_de_entrada(db):
    """Producto e inventory_movements se mantienen consistentes en el alta.

    Precondiciones: BD temporal vacía.
    Pasos:
    - Guardar producto con stock 9
    - Leer inventory_movements
    Esperado:
    - Existe un movimiento ENTRADA con cantidad 9
    """
    pid = productos.guardar(db, None, datos(stock_=9))
    mov = db.one("SELECT * FROM inventory_movements WHERE product_id=?", (pid,))
    assert (mov["movement_type"], mov["quantity"]) == ("ENTRADA", 9)


@tc("ITS_INV_02", nivel="ITS", modulo="productos", reqs=["RF-03", "RF-05"],
    nombre="Ajustes de stock generan movimiento por la diferencia")
def test_edicion_de_stock_registra_ajuste_con_diferencia(db):
    """Editar stock registra AJUSTE ±diferencia; editar sin cambiar stock no genera movimiento.

    Precondiciones: Producto con stock 10.
    Pasos:
    - Editar stock a 14, luego a 11
    - Editar solo el precio
    Esperado:
    - Ajustes +4 y −3
    - No se agregan movimientos al cambiar solo el precio
    """
    pid = productos.guardar(db, None, datos(stock_=10))
    productos.guardar(db, pid, datos(stock_=14))
    productos.guardar(db, pid, datos(stock_=11))
    ajustes = [r["quantity"] for r in db.query(
        "SELECT quantity FROM inventory_movements WHERE movement_type='AJUSTE' ORDER BY id")]
    assert ajustes == [4, -3]


@tc("ITS_INV_02")
def test_edicion_sin_cambio_de_stock_no_genera_movimiento(db):
    pid = productos.guardar(db, None, datos(stock_=10))
    productos.guardar(db, pid, datos(stock_=10, price=250))
    assert db.scalar("SELECT COUNT(*) FROM inventory_movements") == 1


@tc("ITS_INV_03", nivel="ITS", modulo="productos", reqs=["RNF-01", "RF-04"],
    nombre="Conciliación stock = suma de movimientos")
def test_stock_es_suma_de_movimientos(db, empleado):
    """Tras venta, devolución y ajuste, el stock visible coincide con el kardex.

    Precondiciones: Producto con stock 10 y un empleado.
    Pasos:
    - Vender 4
    - Devolver 1
    - Ajustar el stock a 20
    - Sumar inventory_movements del producto
    Esperado:
    - La suma de movimientos = 20 = stock del producto
    """
    pid = productos.guardar(db, None, datos(stock_=10))
    ventas_srv.registrar(db, None, empleado, "Efectivo", 0, [{"product_id": pid, "quantity": 4}])
    devoluciones_srv.devolver(db, 1, pid, 1, "talla")
    productos.guardar(db, pid, datos(stock_=20))
    kardex = db.scalar("SELECT SUM(quantity) FROM inventory_movements WHERE product_id=?", (pid,))
    assert kardex == stock(db, pid) == 20


@tc("ITS_INV_04", nivel="ITS", modulo="productos", reqs=["RF-14"],
    nombre="Producto ligado a proveedor (llave foránea)")
def test_producto_con_proveedor_inexistente_es_rechazado(db):
    """Un producto solo puede ligarse a un proveedor existente y el inventario muestra su nombre.

    Precondiciones: Proveedor 'Textiles SA' registrado.
    Pasos:
    - Guardar producto con proveedor 999
    - Guardar producto con el proveedor existente
    - Listar inventario
    Esperado:
    - El primero levanta IntegrityError
    - El inventario muestra 'Textiles SA'
    """
    with pytest.raises(sqlite3.IntegrityError):
        productos.guardar(db, None, datos(supplier=999))


@tc("ITS_INV_04")
def test_producto_con_proveedor_existente_se_lista_con_su_nombre(db):
    sid = proveedores_repo.guardar(db, None, ("Textiles SA", "555", "Calle 1", "Blusas", today_text()))
    productos.guardar(db, None, datos(supplier=sid))
    assert productos.listar_inventario(db)[0]["proveedor"] == "Textiles SA"
