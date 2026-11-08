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
    """Verificar el alta de productos (RF-01) en la capa de datos. productos.guardar(db, None, datos) de
    mis_trapitos/data/repositories/productos.py inserta el producto y regresa su id; obtener_por_id() y
    obtener_por_codigo() permiten recuperarlo. La tupla datos lleva 13 campos en orden: código, nombre,
    categoría, talla, color, precio de compra, precio de venta, stock, proveedor, fecha de ingreso,
    marca, temporada e imagen (helper datos() del archivo de prueba).

    Precondiciones: Fixture db (base SQLite temporal vacía).
    Pasos:
    - Llamar productos.guardar(db, None, datos()) para el producto BL-01 con stock 5 y precio de venta
      200.
    - Leer el producto con productos.obtener_por_id(db, pid).
    - En test_buscar_producto_por_codigo_y_producto_inexistente: guardar el producto BUSCA y llamar
      productos.obtener_por_codigo(db, 'BUSCA').
    - Llamar productos.obtener_por_codigo(db, 'NO-EXISTE').
    Esperado:
    - El producto leído tiene code = 'BL-01', stock = 5 y sale_price = 200.
    - La búsqueda por 'BUSCA' regresa el mismo id que regresó guardar().
    - El código inexistente regresa None.
    """
    pid = productos.guardar(db, None, datos())
    p = productos.obtener_por_id(db, pid)
    assert (p["code"], p["stock"], p["sale_price"]) == ("BL-01", 5, 200)


@tc("UTS_PRO_02", nivel="UTS", modulo="productos", reqs=["RF-01"],
    nombre="Código de producto duplicado es rechazado")
def test_codigo_duplicado_es_rechazado(db):
    """Garantizar que no puede haber dos productos con el mismo código (RF-01). La unicidad la impone la
    restricción UNIQUE de products.code en mis_trapitos/data/schema.py; productos.guardar() no la
    duplica en Python, así que la prueba confirma que SQLite la hace cumplir.

    Precondiciones: Fixture db (base temporal vacía).
    Pasos:
    - Llamar productos.guardar(db, None, datos('DUP')).
    - Llamar otra vez productos.guardar(db, None, datos('DUP')) y capturar la excepción.
    Esperado:
    - El segundo guardado levanta sqlite3.IntegrityError.
    - Solo existe un producto con código DUP.
    """
    productos.guardar(db, None, datos("DUP"))
    with pytest.raises(sqlite3.IntegrityError):
        productos.guardar(db, None, datos("DUP"))


@tc("UTS_PRO_03", nivel="UTS", modulo="productos", reqs=["RF-01", "RF-03"],
    nombre="Existencias, precio o costo negativos son rechazados")
@pytest.mark.parametrize("campo", ["stock", "precio", "costo"])
def test_valores_negativos_son_rechazados(db, campo):
    """Comprobar que la base rechaza existencias, precio de venta o costo negativos (RF-01, RF-03) mediante
    las restricciones CHECK (stock >= 0, sale_price >= 0, purchase_price >= 0) de la tabla products
    (mis_trapitos/data/schema.py). Es la última línea de defensa si la interfaz dejara pasar un valor
    inválido.

    Precondiciones: Fixture db. Prueba parametrizada con campo ∈ {stock, precio, costo}.
    Pasos:
    - Llamar productos.guardar(db, None, datos(stock_=−1)).
    - Llamar productos.guardar(db, None, datos(price=−5)).
    - Llamar productos.guardar(db, None, datos(purchase=−5)).
    Esperado:
    - Las tres llamadas levantan sqlite3.IntegrityError.
    - No se inserta ningún producto.
    """
    kw = {"stock": dict(stock_=-1), "precio": dict(price=-5), "costo": dict(purchase=-5)}[campo]
    with pytest.raises(sqlite3.IntegrityError):
        productos.guardar(db, None, datos(**kw))


@tc("UTS_PRO_04", nivel="UTS", modulo="productos", reqs=["RF-02"],
    nombre="Variantes talla/color con existencias propias")
def test_misma_prenda_distinta_talla_color_tiene_stock_propio(db):
    """Comprobar que la misma prenda en distinta talla o color es un producto (variante) independiente con
    su propio stock (RF-02). En Mis Trapitos cada variante es una fila de products con su propio código.

    Precondiciones: Fixture db (base temporal vacía).
    Pasos:
    - Llamar productos.guardar(db, None, datos('BL-M-AZ', 3, size='M', color='Azul')).
    - Llamar productos.guardar(db, None, datos('BL-L-RO', 7, size='L', color='Rojo')).
    - Leer el stock de cada una con productos.obtener_por_id().
    Esperado:
    - La variante M/Azul tiene stock 3.
    - La variante L/Rojo tiene stock 7.
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
    """Verificar el mecanismo de contraseñas: hash_password() de utils.py calcula SHA-256 hexadecimal de
    forma determinista, y empleados.autenticar(db, username, password) de
    mis_trapitos/data/repositories/ empleados.py compara contra employees.password_hash y solo regresa
    el empleado si usuario y contraseña coinciden (SEG-01).

    Precondiciones: Para la autenticación: fixtures db y empleado (usuario 'vende', contraseña '1234').
    Pasos:
    - Calcular hash_password('1234') dos veces y hash_password('1235').
    - En test_autenticacion_valida_e_invalida: llamar empleados_repo.autenticar(db, 'vende', '1234').
    - Llamar autenticar(db, 'vende', 'mala').
    - Llamar autenticar(db, 'fantasma', '1234').
    Esperado:
    - Los dos hashes de '1234' son iguales, tienen 64 caracteres y son distintos al de '1235'.
    - Las credenciales correctas regresan el registro del empleado.
    - Contraseña errónea y usuario inexistente regresan None.
    """
    assert hash_password("1234") == hash_password("1234")
    assert len(hash_password("1234")) == 64 and hash_password("1234") != hash_password("1235")


@tc("UTS_UTL_01", nivel="UTS", modulo="ventas", reqs=["RF-06"],
    nombre="Formato monetario")
def test_dinero_formatea_y_tolera_basura():
    """Verificar dinero(value) de utils.py, que da formato de moneda a los importes que se muestran en
    pantallas y tickets (RF-06). Si recibe algo que no es número no debe romper la interfaz.

    Precondiciones: Ninguna: es una función pura, no usa base de datos.
    Pasos:
    - Llamar dinero(1234.5).
    - Llamar dinero('abc').
    Esperado:
    - dinero(1234.5) regresa '$1,234.50'.
    - dinero('abc') regresa '$0.00' sin lanzar excepción.
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
    """Verificar que dar de alta un producto deja registrado su inventario inicial en el kardex (RF-03,
    RF-05). productos.guardar(db, None, datos) inserta en products y, en la misma transacción, llama
    registrar_movimiento(db, pid, 'ENTRADA', stock, ...).

    Precondiciones: Fixture db (base temporal vacía).
    Pasos:
    - Llamar productos.guardar(db, None, datos(stock_=9)).
    - Leer db.one('SELECT * FROM inventory_movements WHERE product_id=?', (pid,)).
    Esperado:
    - Existe un movimiento con movement_type = 'ENTRADA' y quantity = 9.
    """
    pid = productos.guardar(db, None, datos(stock_=9))
    mov = db.one("SELECT * FROM inventory_movements WHERE product_id=?", (pid,))
    assert (mov["movement_type"], mov["quantity"]) == ("ENTRADA", 9)


@tc("ITS_INV_02", nivel="ITS", modulo="productos", reqs=["RF-03", "RF-05"],
    nombre="Ajustes de stock generan movimiento por la diferencia")
def test_edicion_de_stock_registra_ajuste_con_diferencia(db):
    """Verificar que editar las existencias de un producto registra un movimiento AJUSTE por la diferencia
    (nuevo − anterior), y que editar otros campos sin tocar el stock no genera movimientos. La lógica
    está en la rama de edición de productos.guardar(db, product_id, datos). RF-03, RF-05.

    Precondiciones: Fixture db. Producto creado con stock 10 (genera su ENTRADA de 10).
    Pasos:
    - Llamar productos.guardar(db, pid, datos(stock_=14)).
    - Llamar productos.guardar(db, pid, datos(stock_=11)).
    - Leer las cantidades de los movimientos AJUSTE ordenados por id.
    - En test_edicion_sin_cambio_de_stock_no_genera_movimiento: crear otro producto con stock 10, editar
      solo el precio a 250 y contar los movimientos.
    Esperado:
    - Los ajustes son [+4, −3].
    - Al cambiar solo el precio sigue habiendo 1 movimiento (el ENTRADA del alta).
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
    """Conciliar el inventario: después de varias operaciones, el stock visible de products debe ser igual
    a la suma de todos sus movimientos en inventory_movements (el kardex). Es la garantía de que ninguna
    operación cambia el stock sin dejar rastro. RNF-01, RF-04.

    Precondiciones: Fixtures db y empleado. Producto creado con productos.guardar() y stock 10.
    Pasos:
    - Vender 4 piezas con ventas_srv.registrar(db, None, empleado, 'Efectivo', 0, [...]).
    - Devolver 1 con devoluciones_srv.devolver(db, 1, pid, 1, 'talla').
    - Ajustar el stock a 20 con productos.guardar(db, pid, datos(stock_=20)).
    - Sumar SELECT SUM(quantity) FROM inventory_movements WHERE product_id=pid.
    Esperado:
    - La suma del kardex = 20 = stock del producto (ENTRADA +10, SALIDA −4, DEVOLUCION +1, AJUSTE +13).
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
    """Verificar la relación producto → proveedor (RF-14). La columna products.supplier_id es llave foránea
    a suppliers (con PRAGMA foreign_keys = ON que activa Database.__init__);
    productos.listar_inventario() hace LEFT JOIN para mostrar el nombre del proveedor en la tabla de
    inventario.

    Precondiciones: Fixture db. Para el caso válido, proveedor 'Textiles SA' creado con
      proveedores_repo.guardar().
    Pasos:
    - Llamar productos.guardar(db, None, datos(supplier=999)) con un proveedor que no existe.
    - En test_producto_con_proveedor_existente_se_lista_con_su_nombre: crear 'Textiles SA' y guardar un
      producto con su id.
    - Llamar productos.listar_inventario(db).
    Esperado:
    - El producto con proveedor 999 levanta sqlite3.IntegrityError.
    - La primera fila del inventario tiene proveedor = 'Textiles SA'.
    """
    with pytest.raises(sqlite3.IntegrityError):
        productos.guardar(db, None, datos(supplier=999))


@tc("ITS_INV_04")
def test_producto_con_proveedor_existente_se_lista_con_su_nombre(db):
    sid = proveedores_repo.guardar(db, None, ("Textiles SA", "555", "Calle 1", "Blusas", today_text()))
    productos.guardar(db, None, datos(supplier=sid))
    assert productos.listar_inventario(db)[0]["proveedor"] == "Textiles SA"
