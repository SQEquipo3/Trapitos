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
from tests.tc import tc


def item(pid, qty):
    return {"product_id": pid, "quantity": qty}


# ---------- unitarias ----------
@tc("UTS_VEN_01", nivel="UTS", modulo="ventas", reqs=["RF-06"],
    nombre="Venta sin productos, producto inexistente o cantidad no positiva")
def test_venta_vacia_es_rechazada(db, empleado):
    """Comprobar que la regla de negocio de ventas rechaza un carrito inválido ANTES de escribir en la
    base. La función bajo prueba es registrar() de mis_trapitos/services/ventas.py, que es la única
    puerta para guardar una venta: valida el carrito, calcula importes y guarda todo en una transacción.
    Si estas validaciones fallaran se guardarían ventas vacías o con cantidades absurdas.

    Precondiciones: Fixtures de tests/conftest.py: db (base SQLite temporal y vacía, Database(...,
      load_examples=False)), empleado (empleado 'vende' creado con empleados_repo.guardar) y make_product
      (producto P-001 con stock 10 y precio $200, creado con productos_repo.guardar).
    Pasos:
    - Llamar ventas_srv.registrar(db, None, empleado, 'Efectivo', 0, []) con el carrito vacío (prueba
      test_venta_vacia_es_rechazada).
    - Llamar registrar(...) con el carrito [{'product_id': 999, 'quantity': 1}], un id que no existe
      (prueba test_producto_inexistente_en_carrito_es_rechazado).
    - Crear un producto con make_product() y llamar registrar(...) con quantity=0 y luego con
      quantity=−2 (prueba parametrizada test_cantidad_no_positiva_es_rechazada).
    - En cada caso capturar la excepción con pytest.raises(ValueError, match=...).
    Esperado:
    - Carrito vacío: ValueError con el mensaje 'La venta no tiene productos.'
    - Producto inexistente: ValueError 'Producto no encontrado.'
    - Cantidad 0 o negativa: ValueError 'La cantidad debe ser mayor a cero.'
    - En ningún caso se crea una fila en la tabla sales.
    Comentarios: Las validaciones están al inicio de registrar() y dentro del ciclo que recorre el
      carrito, antes de ventas_repo.insertar(). Si cambian los mensajes de error, actualizar el match= de
      las pruebas.
    """
    with pytest.raises(ValueError, match="no tiene productos"):
        ventas_srv.registrar(db, None, empleado, "Efectivo", 0, [])


@tc("UTS_VEN_02", nivel="UTS", modulo="ventas", reqs=["RF-07"],
    nombre="Método de pago inválido es rechazado")
def test_metodo_de_pago_invalido_es_rechazado(db, empleado, make_product):
    """Verificar que solo se aceptan los métodos de pago configurados en config.PAYMENT_METHODS (RF-07). La
    validación vive en ventas_srv.registrar() (mis_trapitos/services/ventas.py): si el método no está en
    la tupla, la venta se rechaza antes de abrir la transacción.

    Precondiciones: Fixtures db, empleado y make_product (producto con stock 10).
    Pasos:
    - Crear un producto con make_product().
    - Llamar ventas_srv.registrar(db, None, empleado, 'Cheque', 0, [{'product_id': pid, 'quantity':
      1}]).
    - Capturar la excepción con pytest.raises(ValueError, match='pago').
    Esperado:
    - Se levanta ValueError con el mensaje 'Metodo de pago no valido.'
    - No se crea la venta y el stock del producto no cambia.
    """
    pid = make_product()
    with pytest.raises(ValueError, match="pago"):
        ventas_srv.registrar(db, None, empleado, "Cheque", 0, [item(pid, 1)])


@tc("UTS_VEN_03", nivel="UTS", modulo="ventas", reqs=["RF-07"],
    nombre="Los cuatro métodos de pago son aceptados")
@pytest.mark.parametrize("metodo", PAYMENT_METHODS)
def test_los_cuatro_metodos_de_pago_son_aceptados(db, empleado, make_product, metodo):
    """Confirmar que cada uno de los cuatro métodos de pago de config.PAYMENT_METHODS (Efectivo, Tarjeta de
    credito, Tarjeta de debito, Transferencia bancaria) permite registrar una venta y queda guardado tal
    cual en la columna sales.payment_method (RF-07).

    Precondiciones: Fixtures db, empleado y make_product(stock=50). La prueba está parametrizada con
      @pytest.mark.parametrize('metodo', PAYMENT_METHODS): corre una vez por método.
    Pasos:
    - Crear un producto con stock 50.
    - Llamar ventas_srv.registrar(db, None, empleado, metodo, 0, [{'product_id': pid, 'quantity': 1}]) y
      guardar el sale_id que regresa.
    - Leer db.scalar('SELECT payment_method FROM sales WHERE id=?', (sale_id,)).
    Esperado:
    - Las cuatro ejecuciones registran la venta sin error.
    - El valor guardado en sales.payment_method es exactamente el método usado.
    """
    pid = make_product(stock=50)
    sid, *_ = ventas_srv.registrar(db, None, empleado, metodo, 0, [item(pid, 1)])
    assert db.scalar("SELECT payment_method FROM sales WHERE id=?", (sid,)) == metodo


@tc("UTS_VEN_04", nivel="UTS", modulo="ventas", reqs=["RF-08"],
    nombre="Descuento general fuera de 0–100 % es rechazado")
@pytest.mark.parametrize("pct", [-1, 100.5, 101])
def test_descuento_general_fuera_de_rango_es_rechazado(db, empleado, make_product, pct):
    """Validar el rango del descuento general de la venta (RF-08). ventas_srv.registrar() solo acepta un
    porcentaje entre 0 y 100; fuera de ese rango se produciría un total negativo o un descuento sin
    sentido.

    Precondiciones: Fixtures db, empleado y make_product. Prueba parametrizada con pct ∈ {−1, 100.5,
      101}.
    Pasos:
    - Crear un producto con make_product().
    - Llamar ventas_srv.registrar(db, None, empleado, 'Efectivo', pct, [item]) con pct = −1.
    - Repetir con pct = 100.5 y con pct = 101.
    Esperado:
    - Las tres llamadas levantan ValueError 'El descuento debe estar entre 0 y 100.'
    - No se guarda ninguna venta.
    """
    pid = make_product()
    with pytest.raises(ValueError, match="0 y 100"):
        ventas_srv.registrar(db, None, empleado, "Efectivo", pct, [item(pid, 1)])


@tc("UTS_VEN_01")
@pytest.mark.parametrize("qty", [0, -2])
def test_cantidad_no_positiva_es_rechazada(db, empleado, make_product, qty):
    pid = make_product()
    with pytest.raises(ValueError, match="mayor a cero"):
        ventas_srv.registrar(db, None, empleado, "Efectivo", 0, [item(pid, qty)])


@tc("UTS_VEN_05", nivel="UTS", modulo="ventas", reqs=["RF-04"],
    nombre="Stock insuficiente rechaza la venta sin cambiar existencias")
def test_stock_insuficiente_es_rechazado_y_no_cambia_stock(db, empleado, make_product):
    """Asegurar que no se puede vender más piezas de las que hay en existencia (RF-04) y que, al
    rechazarse, el stock no se modifica. La revisión int(product['stock']) < qty está dentro de
    ventas_srv.registrar(), antes de descontar con productos_repo.ajustar_stock().

    Precondiciones: Fixtures db, empleado y make_product(stock=2): un producto con solo 2 piezas.
    Pasos:
    - Llamar ventas_srv.registrar(db, None, empleado, 'Efectivo', 0, [{'product_id': pid, 'quantity':
      3}]).
    - Capturar la excepción con pytest.raises(ValueError, match='Stock insuficiente').
    - Leer el stock con el helper stock(db, pid) de tests/conftest.py.
    Esperado:
    - ValueError 'Stock insuficiente para P-001 − Blusa.'
    - El stock sigue en 2.
    """
    pid = make_product(stock=2)
    with pytest.raises(ValueError, match="Stock insuficiente"):
        ventas_srv.registrar(db, None, empleado, "Efectivo", 0, [item(pid, 3)])
    assert stock(db, pid) == 2


@tc("UTS_VEN_01")
def test_producto_inexistente_en_carrito_es_rechazado(db, empleado):
    with pytest.raises(ValueError, match="no encontrado"):
        ventas_srv.registrar(db, None, empleado, "Efectivo", 0, [item(999, 1)])


@tc("UTS_VEN_06", nivel="UTS", modulo="ventas", reqs=["RF-08"],
    nombre="Cálculo de subtotal, descuento y total")
def test_calculo_de_subtotal_descuento_y_total(db, empleado, make_product):
    """Verificar la fórmula de importes de una venta (RF-08): subtotal = Σ precio × cantidad (con promoción
    si hay), monto de descuento = subtotal × descuento / 100 y total = subtotal − monto. La fórmula está
    en ventas_srv.registrar(), que regresa la tupla (sale_id, subtotal, monto_descuento, total).

    Precondiciones: Fixtures db, empleado y make_product(price=200, stock=10). El producto no tiene
      promoción.
    Pasos:
    - Crear el producto de $200.
    - Llamar ventas_srv.registrar(db, None, empleado, 'Efectivo', 10, [{'product_id': pid, 'quantity':
      3}]).
    - Desempaquetar el resultado como (_, subtotal, descuento, total).
    Esperado:
    - subtotal = 600 (3 × $200)
    - descuento = 60 (10 % de 600)
    - total = 540
    """
    pid = make_product(price=200, stock=10)
    _, subtotal, descuento, total = ventas_srv.registrar(db, None, empleado, "Efectivo", 10, [item(pid, 3)])
    assert (subtotal, descuento, total) == (600, 60, 540)


# ---------- integración ----------
@tc("ITS_VEN_01", nivel="ITS", modulo="ventas", reqs=["RF-04", "RF-06"],
    nombre="Venta descuenta stock y registra SALIDA (uno y varios productos)")
def test_venta_descuenta_stock_y_registra_salida(db, empleado, make_product):
    """Prueba de integración de una venta completa (RF-04, RF-06): ventas_srv.registrar() debe escribir en
    cuatro tablas de forma coherente: sales (encabezado), sale_items (una partida por producto),
    products (descuenta stock con productos_repo.ajustar_stock) e inventory_movements (movimiento SALIDA
    con productos_repo.registrar_movimiento, ligado a la venta por related_sale_id).

    Precondiciones: Fixtures db, empleado y make_product. Producto de stock 10; para la venta de dos
      productos, uno de $100 y otro de $50.
    Pasos:
    - Llamar ventas_srv.registrar(db, None, empleado, 'Efectivo', 0, [{'product_id': pid, 'quantity':
      4}]).
    - Leer el stock con stock(db, pid) y el movimiento con db.one("SELECT * FROM inventory_movements
      WHERE movement_type='SALIDA'").
    - En test_venta_multiproducto_guarda_partidas: registrar una venta con 2 piezas del producto de $100
      y 1 del de $50, pagada con 'Tarjeta de debito'.
    - Contar las filas de sale_items de esa venta.
    Esperado:
    - Stock del producto = 6 (10 − 4).
    - Existe un movimiento SALIDA con quantity = −4 y related_sale_id = id de la venta.
    - La venta de dos productos tiene 2 partidas y subtotal = 250.
    """
    pid = make_product(stock=10)
    sid, *_ = ventas_srv.registrar(db, None, empleado, "Efectivo", 0, [item(pid, 4)])
    mov = db.one("SELECT * FROM inventory_movements WHERE movement_type='SALIDA'")
    assert stock(db, pid) == 6 and mov["quantity"] == -4 and mov["related_sale_id"] == sid


@tc("ITS_VEN_01")
def test_venta_multiproducto_guarda_partidas(db, empleado, make_product):
    a, b = make_product(price=100), make_product(price=50)
    sid, subtotal, *_ = ventas_srv.registrar(db, None, empleado, "Tarjeta de debito", 0, [item(a, 2), item(b, 1)])
    assert subtotal == 250 and db.scalar("SELECT COUNT(*) FROM sale_items WHERE sale_id=?", (sid,)) == 2


@tc("ITS_VEN_02", nivel="ITS", modulo="ventas", reqs=["RF-04"],
    nombre="Atomicidad: si una partida falla no se guarda nada")
def test_venta_es_atomica_si_falla_un_producto(db, empleado, make_product):
    """Verificar la atomicidad de la venta (RF-04): todo lo que hace ventas_srv.registrar() ocurre dentro
    de un solo db.transaction() (mis_trapitos/data/database.py). Si falla cualquier partida o cualquier
    escritura, se revierte todo: no debe quedar una venta guardada sin su descuento de stock, ni stock
    descontado sin venta.

    Precondiciones: Fixtures db, empleado y make_product. Producto A con stock 5 y producto B con stock
      1. Para simular la falla de escritura se usa unittest.mock.patch.object sobre
      ventas_repo.insertar_partida.
    Pasos:
    - Llamar registrar(...) con el carrito [A × 2, B × 9]: la segunda partida no tiene stock suficiente.
    - Revisar el stock de A y contar las filas de sales.
    - En test_venta_se_revierte_si_falla_una_escritura: parchear ventas.insertar_partida para que lance
      sqlite3.OperationalError('disco lleno') y registrar una venta de 2 piezas.
    - Revisar otra vez el stock y la tabla sales.
    Esperado:
    - El primer intento levanta ValueError; el stock de A sigue en 5 y no existe ninguna venta.
    - El segundo intento propaga el OperationalError; el stock sigue en 5 y sales está vacía (se hizo
      rollback del encabezado ya insertado).
    """
    a, b = make_product(stock=5), make_product(stock=1)
    with pytest.raises(ValueError):
        ventas_srv.registrar(db, None, empleado, "Efectivo", 0, [item(a, 2), item(b, 9)])
    assert stock(db, a) == 5 and db.scalar("SELECT COUNT(*) FROM sales") == 0


@tc("ITS_VEN_02")
def test_venta_se_revierte_si_falla_una_escritura(db, empleado, make_product):
    pid = make_product(stock=5)
    with patch.object(ventas, "insertar_partida", side_effect=sqlite3.OperationalError("disco lleno")):
        with pytest.raises(sqlite3.OperationalError):
            ventas_srv.registrar(db, None, empleado, "Efectivo", 0, [item(pid, 2)])
    assert stock(db, pid) == 5 and db.scalar("SELECT COUNT(*) FROM sales") == 0


@tc("ITS_VEN_03", nivel="ITS", modulo="ventas", reqs=["RF-10"],
    nombre="Promoción vigente se aplica automáticamente en la venta")
def test_promocion_vigente_se_aplica_automaticamente(db, empleado, make_product):
    """Comprobar que una promoción vigente se aplica sola al vender, sin que el vendedor haga nada (RF-10).
    Dentro de ventas_srv.registrar(), cada partida consulta promociones_repo.porcentaje_vigente() y
    calcula line_total = precio × cantidad × (1 − promo/100); el porcentaje aplicado se guarda en
    sale_items.promo_discount_percent.

    Precondiciones: Fixtures db, empleado y make_product(price=200). Promoción de 25 % vigente de hoy−1
      a hoy+5, creada con promociones_repo.guardar().
    Pasos:
    - Crear el producto de $200 y su promoción de 25 %.
    - Llamar ventas_srv.registrar(db, None, empleado, 'Efectivo', 0, [{'product_id': pid, 'quantity':
      2}]).
    - Leer el subtotal regresado y db.scalar('SELECT promo_discount_percent FROM sale_items').
    Esperado:
    - Subtotal = 300 (2 × $200 × 0.75).
    - sale_items.promo_discount_percent = 25.
    """
    pid = make_product(price=200)
    promociones_repo.guardar(db, None, pid, 25, dias(-1)[:10], dias(5)[:10])
    _, subtotal, *_ = ventas_srv.registrar(db, None, empleado, "Efectivo", 0, [item(pid, 2)])
    assert subtotal == 300
    assert db.scalar("SELECT promo_discount_percent FROM sale_items") == 25


@tc("UTS_VEN_07", nivel="UTS", modulo="ventas", reqs=["RF-09", "RF-10"],
    nombre="Vigencia de promociones (vencida y futura no aplican)")
def test_promocion_vencida_o_futura_no_se_aplica(db, empleado, make_product):
    """Comprobar que promociones_repo.porcentaje_vigente(db, product_id) (mis_trapitos/data/repositories/
    promociones.py) solo toma en cuenta promociones cuya vigencia incluye el día de hoy (RF-09, RF-10).
    Esta función la usa ventas_srv.registrar() para aplicar la promoción a cada partida.

    Precondiciones: Fixtures db y make_product(price=200). Las fechas se calculan relativas a hoy con el
      helper dias(n) de tests/conftest.py, para que la prueba no dependa de la fecha en que se ejecute.
    Pasos:
    - Crear el producto.
    - Registrar con promociones_repo.guardar(db, None, pid, 50, hoy−10, hoy−2) una promoción ya vencida.
    - Registrar con promociones_repo.guardar(db, None, pid, 40, hoy+3, hoy+9) una promoción que todavía
      no empieza.
    - Llamar promociones_repo.porcentaje_vigente(db, pid).
    Esperado:
    - Regresa 0: ninguna de las dos promociones está vigente hoy.
    """
    pid = make_product(price=200)
    promociones_repo.guardar(db, None, pid, 50, dias(-10)[:10], dias(-2)[:10])
    promociones_repo.guardar(db, None, pid, 40, dias(3)[:10], dias(9)[:10])
    assert promociones_repo.porcentaje_vigente(db, pid) == 0


@tc("UTS_VEN_08", nivel="UTS", modulo="ventas", reqs=["RF-09", "RF-10"],
    nombre="Varias promociones vigentes: aplica la mayor; porcentaje inválido es rechazado")
def test_con_varias_promociones_vigentes_aplica_la_mayor(db, make_product):
    """Definir qué pasa cuando un producto tiene varias promociones vigentes al mismo tiempo (se aplica la
    mayor, por el MAX() de porcentaje_vigente) y que la base rechaza porcentajes fuera de 0–100 con la
    restricción CHECK de la tabla promotions (mis_trapitos/data/schema.py). RF-09 y RF-10.

    Precondiciones: Fixtures db y make_product. Fechas relativas a hoy con dias(n).
    Pasos:
    - Crear un producto y dos promociones vigentes (hoy−1 a hoy+5) de 10 % y 30 % con
      promociones_repo.guardar().
    - Llamar promociones_repo.porcentaje_vigente(db, pid).
    - En la prueba test_promocion_con_porcentaje_invalido_es_rechazada, intentar
      promociones_repo.guardar(db, None, pid, 120, hoy, hoy+5).
    Esperado:
    - porcentaje_vigente regresa 30.
    - Guardar la promoción de 120 % levanta sqlite3.IntegrityError y no se inserta.
    """
    pid = make_product()
    promociones_repo.guardar(db, None, pid, 10, dias(-1)[:10], dias(5)[:10])
    promociones_repo.guardar(db, None, pid, 30, dias(-1)[:10], dias(5)[:10])
    assert promociones_repo.porcentaje_vigente(db, pid) == 30


@tc("UTS_VEN_08")
def test_promocion_con_porcentaje_invalido_es_rechazada(db, make_product):
    import sqlite3
    pid = make_product()
    with pytest.raises(sqlite3.IntegrityError):
        promociones_repo.guardar(db, None, pid, 120, dias(0)[:10], dias(5)[:10])


@tc("ITS_VEN_04", nivel="ITS", modulo="ventas", reqs=["RF-05"],
    nombre="Devolución parcial repone existencias")
def test_devolucion_parcial_repone_stock_y_registra_movimiento(db, empleado, make_product):
    """Verificar que una devolución parcial regresa las piezas al inventario y deja rastro en el kardex
    (RF-05). La función bajo prueba es devolver(db, sale_id, product_id, quantity, reason) de
    mis_trapitos/services/devoluciones.py: inserta en returns, suma al stock con
    productos_repo.ajustar_stock y registra un movimiento DEVOLUCION.

    Precondiciones: Fixtures db, empleado y make_product(stock=10). Se registra antes una venta de 5
      piezas con ventas_srv.registrar(), así que el stock queda en 5.
    Pasos:
    - Vender 5 piezas con ventas_srv.registrar(...) y guardar el sale_id.
    - Llamar devoluciones_srv.devolver(db, sale_id, pid, 2, 'No le quedó').
    - Leer el stock con stock(db, pid) y el movimiento con db.scalar("SELECT quantity FROM
      inventory_movements WHERE movement_type='DEVOLUCION'").
    Esperado:
    - Stock = 7 (5 + 2).
    - Existe un movimiento DEVOLUCION con quantity = +2.
    """
    pid = make_product(stock=10)
    sid, *_ = ventas_srv.registrar(db, None, empleado, "Efectivo", 0, [item(pid, 5)])
    devoluciones_srv.devolver(db, sid, pid, 2, "No le quedó")
    assert stock(db, pid) == 7
    assert db.scalar("SELECT quantity FROM inventory_movements WHERE movement_type='DEVOLUCION'") == 2


@tc("ITS_VEN_05", nivel="ITS", modulo="ventas", reqs=["RF-05"],
    nombre="Devoluciones inválidas no alteran datos")
@pytest.mark.parametrize("qty", [0, -1, 6])
def test_devolucion_invalida_no_altera_datos(db, empleado, make_product, qty):
    """Asegurar que devolver() (mis_trapitos/services/devoluciones.py) rechaza cantidades imposibles: cero,
    negativas, mayores a lo vendido o que, sumadas a devoluciones anteriores, superan lo vendido. La
    regla es 0 < cantidad ≤ vendido − ya devuelto (usa ventas_repo.cantidad_vendida y
    devoluciones_repo.cantidad_devuelta). RF-05.

    Precondiciones: Fixtures db, empleado y make_product(stock=10). Prueba parametrizada con qty ∈ {0,
      −1, 6} sobre una venta de 5 piezas.
    Pasos:
    - Vender 5 piezas con ventas_srv.registrar().
    - Llamar devoluciones_srv.devolver(db, sale_id, pid, qty, 'x') con qty = 0, −1 y 6.
    - Revisar el stock y contar las filas de returns.
    - En test_no_se_puede_devolver_mas_de_lo_vendido_en_dos_devoluciones: vender 3, devolver 2 y luego
      intentar devolver otras 2.
    Esperado:
    - Cada intento inválido levanta ValueError 'Cantidad de devolucion no valida.'
    - El stock sigue en 5 y la tabla returns queda vacía.
    - La segunda devolución de 2 (total 4 > 3 vendidas) también se rechaza.
    """
    pid = make_product(stock=10)
    sid, *_ = ventas_srv.registrar(db, None, empleado, "Efectivo", 0, [item(pid, 5)])
    with pytest.raises(ValueError, match="no valida"):
        devoluciones_srv.devolver(db, sid, pid, qty, "x")
    assert stock(db, pid) == 5 and db.scalar("SELECT COUNT(*) FROM returns") == 0


@tc("ITS_VEN_05")
def test_no_se_puede_devolver_mas_de_lo_vendido_en_dos_devoluciones(db, empleado, make_product):
    pid = make_product(stock=10)
    sid, *_ = ventas_srv.registrar(db, None, empleado, "Efectivo", 0, [item(pid, 3)])
    devoluciones_srv.devolver(db, sid, pid, 2, "a")
    with pytest.raises(ValueError):
        devoluciones_srv.devolver(db, sid, pid, 2, "b")


@tc("ITS_VEN_06", nivel="ITS", modulo="ventas", reqs=["RF-05"],
    nombre="Cancelación repone todo y bloquea operaciones posteriores")
def test_cancelacion_repone_todo_y_marca_venta(db, empleado, make_product):
    """Verificar la cancelación de una venta (RF-05). cancelar_venta(db, sale_id, reason) de
    mis_trapitos/services/devoluciones.py regresa al stock todas las piezas no devueltas, marca la venta
    como CANCELADA (ventas_repo.marcar_cancelada) y guarda un registro en cancellations. Una venta
    cancelada ya no admite otra cancelación ni devoluciones.

    Precondiciones: Fixtures db, empleado y make_product(stock=10). Venta de 4 piezas registrada con
      ventas_srv.registrar() (stock queda en 6).
    Pasos:
    - Llamar devoluciones_srv.cancelar_venta(db, sale_id, 'Error de captura').
    - Revisar stock, sales.status y el número de filas de cancellations.
    - En test_cancelar_dos_veces_o_devolver_en_cancelada_es_rechazado: llamar otra vez
      cancelar_venta(...) sobre la misma venta.
    - Llamar devoluciones_srv.devolver(db, sale_id, pid, 1, 'x') sobre la venta cancelada.
    Esperado:
    - Stock vuelve a 10, sales.status = 'CANCELADA' y hay 1 fila en cancellations.
    - La segunda cancelación levanta ValueError 'La venta ya esta cancelada.'
    - La devolución levanta ValueError 'No se puede devolver sobre una venta cancelada.' y el stock
      sigue en 10.
    """
    pid = make_product(stock=10)
    sid, *_ = ventas_srv.registrar(db, None, empleado, "Efectivo", 0, [item(pid, 4)])
    devoluciones_srv.cancelar_venta(db, sid, "Error de captura")
    assert stock(db, pid) == 10
    assert db.scalar("SELECT status FROM sales WHERE id=?", (sid,)) == "CANCELADA"
    assert db.scalar("SELECT COUNT(*) FROM cancellations") == 1


@tc("ITS_VEN_06")
def test_cancelar_dos_veces_o_devolver_en_cancelada_es_rechazado(db, empleado, make_product):
    pid = make_product(stock=10)
    sid, *_ = ventas_srv.registrar(db, None, empleado, "Efectivo", 0, [item(pid, 4)])
    devoluciones_srv.cancelar_venta(db, sid, "x")
    with pytest.raises(ValueError, match="ya esta cancelada"):
        devoluciones_srv.cancelar_venta(db, sid, "x")
    with pytest.raises(ValueError, match="cancelada"):
        devoluciones_srv.devolver(db, sid, pid, 1, "x")
    assert stock(db, pid) == 10


@tc("ITS_VEN_07", nivel="ITS", modulo="ventas", reqs=["RF-05"],
    nombre="Cancelación tras devolución parcial repone solo el remanente")
def test_cancelacion_tras_devolucion_parcial_repone_solo_el_remanente(db, empleado, make_product):
    """Evitar que se repongan dos veces las mismas piezas: si una venta ya tuvo una devolución parcial, al
    cancelarla cancelar_venta() solo debe regresar el remanente (vendido − devuelto). También se
    verifica que ventas_repo.obtener_fecha() regresa la fecha de la venta en formato de hoy. RF-05.

    Precondiciones: Fixtures db, empleado y make_product(stock=10).
    Pasos:
    - Vender 5 piezas con ventas_srv.registrar() (stock 5).
    - Devolver 2 con devoluciones_srv.devolver(db, sale_id, pid, 2, 'x') (stock 7).
    - Cancelar la venta con devoluciones_srv.cancelar_venta(db, sale_id, 'x').
    - En test_repositorio_ventas_registrar_y_obtener_fecha: registrar una venta y llamar
      ventas.obtener_fecha(db, sale_id).
    Esperado:
    - Stock final = 10 exacto: la cancelación repone solo las 3 piezas pendientes.
    - obtener_fecha regresa un texto que empieza con today_text() (AAAA-MM-DD de hoy).
    """
    pid = make_product(stock=10)
    sid, *_ = ventas_srv.registrar(db, None, empleado, "Efectivo", 0, [item(pid, 5)])
    devoluciones_srv.devolver(db, sid, pid, 2, "x")
    devoluciones_srv.cancelar_venta(db, sid, "x")
    assert stock(db, pid) == 10


@tc("ITS_VEN_07")
def test_repositorio_ventas_registrar_y_obtener_fecha(db, empleado, make_product):
    pid = make_product()
    sid, *_ = ventas_srv.registrar(db, None, empleado, "Efectivo", 0, [item(pid, 1)])
    assert ventas.obtener_fecha(db, sid).startswith(today_text())


# ---------- defectos conocidos (B-03, B-05): el SDD los declara abiertos ----------
@tc("ITS_VEN_08", nivel="ITS", modulo="ventas", reqs=["RF-05"],
    nombre="Cancelación con líneas duplicadas por producto (brecha B-03)")
@pytest.mark.xfail(strict=True, reason="#53 (B-03): la cancelación presupone una sola línea por producto")
def test_cancelacion_con_lineas_duplicadas_repone_el_remanente_exacto(db, empleado, make_product):
    """Detectar el defecto B-03 del SDD: cuando el carrito trae el mismo producto en dos líneas,
    cancelar_venta() calcula el remanente por línea y resta la devolución en cada una, así que repone
    menos piezas de las que debería. Esta prueba describe el comportamiento CORRECTO y hoy falla a
    propósito.

    Precondiciones: Fixtures db, empleado y make_product(stock=20). Venta con dos líneas del mismo
      producto (2 y 3 piezas) y una devolución de 2.
    Pasos:
    - Llamar ventas_srv.registrar(...) con el carrito [{pid, 2}, {pid, 3}] (stock 15).
    - Devolver 2 piezas con devoluciones_srv.devolver(db, sale_id, pid, 2, 'x') (stock 17).
    - Cancelar con devoluciones_srv.cancelar_venta(db, sale_id, 'x').
    - Comparar stock(db, pid) con 20.
    Esperado:
    - Stock final = 20 (se reponen exactamente las 3 piezas pendientes).
    Comentarios: DEFECTO ABIERTO B-03 (SDD, sección 11), issue #53. La prueba está marcada
      @pytest.mark.xfail(strict=True): el CI sigue en verde mientras el bug exista y el Excel la reporta
      como Failed ligada al #53. Cuando se corrija cancelar_venta() (agrupar las cantidades por producto),
      quitar el xfail.
    """
    pid = make_product(stock=20)
    sid, *_ = ventas_srv.registrar(db, None, empleado, "Efectivo", 0, [item(pid, 2), item(pid, 3)])
    devoluciones_srv.devolver(db, sid, pid, 2, "x")
    devoluciones_srv.cancelar_venta(db, sid, "x")
    assert stock(db, pid) == 20


@tc("ITS_REP_07", nivel="ITS", modulo="reportes", reqs=["RF-17", "RF-18"],
    nombre="Reportes de ventas descuentan devoluciones (brecha B-05)")
@pytest.mark.xfail(strict=True, reason="#54 (B-05): los reportes de ventas no descuentan devoluciones")
def test_reporte_ventas_por_producto_descuenta_devoluciones(db, empleado, make_product):
    """Detectar el defecto B-05 del SDD: el reporte 'Ventas por producto' de reportes_repo.ejecutar()
    (mis_trapitos/data/repositories/reportes.py) suma sale_items sin restar las devoluciones, así que
    una venta devuelta completa sigue contando como vendida. La prueba describe el comportamiento
    CORRECTO y hoy falla a propósito.

    Precondiciones: Fixtures db, empleado y make_product(price=100, stock=10).
    Pasos:
    - Vender 4 piezas con ventas_srv.registrar().
    - Devolver las 4 con devoluciones_srv.devolver(db, sale_id, pid, 4, 'x').
    - Ejecutar reportes_repo.ejecutar(db, 'Ventas por producto').
    Esperado:
    - El reporte no muestra el producto, o lo muestra con piezas = 0.
    Comentarios: DEFECTO ABIERTO B-05 (SDD, sección 11), issue #54. Prueba marcada xfail(strict=True);
      en el Excel sale Failed ligada al #54. Al corregir la consulta (restar returns), quitar el xfail.
    """
    pid = make_product(price=100, stock=10)
    sid, *_ = ventas_srv.registrar(db, None, empleado, "Efectivo", 0, [item(pid, 4)])
    devoluciones_srv.devolver(db, sid, pid, 4, "x")
    fila = reportes_repo.ejecutar(db, "Ventas por producto")
    assert not fila or fila[0]["piezas"] == 0
