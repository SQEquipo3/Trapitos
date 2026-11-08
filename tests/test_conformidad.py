"""Pruebas de conformidad (CTS): el comportamiento se ajusta a un estándar o a la especificación del SDD."""
import csv
import datetime as dt
import re
import sqlite3
import tkinter as tk
from unittest.mock import patch

import pytest

from config import DATE_FMT, DATETIME_FMT, PAYMENT_METHODS
from mis_trapitos.data.repositories import empleados as empleados_repo
from mis_trapitos.data.repositories import productos as productos_repo
from mis_trapitos.data.repositories import ventas as ventas_repo
from mis_trapitos.services import devoluciones as devoluciones_srv
from mis_trapitos.services import ventas as ventas_srv
from mis_trapitos.ui import productos as ui_productos
from mis_trapitos.ui import reportes as ui_reportes
from tests.tc import tc
from utils import date_offset, hash_password, now_text, today_text

# Vectores de prueba oficiales de SHA-256 (FIPS 180-4, ejemplos del NIST).
VECTORES_SHA256 = {
    "": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "abc": "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
    "abcdbcdecdefdefgefghfghighijhijkijkljklmklmnlmnomnopnopq":
        "248d6a61d20638b8e5c026930c3e6039a33ce45964ff2167f6ecedd419db06c1",
}
MOVIMIENTOS_SDD = {"ENTRADA", "SALIDA", "AJUSTE", "DEVOLUCION", "CANCELACION"}


def item(pid, qty):
    return {"product_id": pid, "quantity": qty}


@pytest.fixture
def raiz():
    root = tk.Tk()
    root.withdraw()
    yield root
    root.destroy()


@pytest.fixture
def operaciones(db, empleado, make_product):
    """Base con ventas, una devolución parcial, una cancelación y un ajuste de inventario."""
    a, b = make_product(stock=10), make_product(stock=8)
    s1, *_ = ventas_srv.registrar(db, None, empleado, "Efectivo", 0, [item(a, 3), item(b, 1)])
    s2, *_ = ventas_srv.registrar(db, None, empleado, "Tarjeta de debito", 10, [item(b, 2)])
    devoluciones_srv.devolver(db, s1, a, 1, "Talla")
    devoluciones_srv.cancelar_venta(db, s2, "Error de captura")
    producto = db.one("SELECT * FROM products WHERE id=?", (a,))
    datos = [producto[k] for k in ("code", "name", "category", "size", "color", "purchase_price", "sale_price")]
    productos_repo.guardar(db, a, (*datos, 15, None, today_text(), "Marca", "Todo", ""))
    return {"a": a, "b": b, "ventas": (s1, s2)}


# ---------- ISO 8601 ----------
@tc("CTS_FMT_01", nivel="CTS", modulo="ventas", reqs=["ISO-8601"],
    nombre="Fechas y horas de la aplicación en formato ISO 8601")
def test_fechas_generadas_cumplen_iso_8601():
    """Prueba de conformidad con ISO 8601: las funciones de fecha de utils.py (today_text(),
    date_offset(días) y now_text()) deben producir AAAA-MM-DD y AAAA-MM-DD hh:mm:ss, y los formatos
    DATE_FMT y DATETIME_FMT de config.py deben ser los de ISO. Todas las fechas que se guardan en la
    base salen de estas funciones.

    Precondiciones: Ninguna: funciones puras, no usa base de datos.
    Pasos:
    - Revisar config.DATE_FMT y config.DATETIME_FMT.
    - Para today_text(), date_offset(−30) y date_offset(400): comprobar el patrón \\d{4}-\\d{2}-\\d{2} e
      interpretarlas con datetime.date.fromisoformat().
    - Para now_text(): comprobar el patrón de fecha y hora e interpretarla con
      datetime.datetime.fromisoformat().
    Esperado:
    - DATE_FMT = '%Y-%m-%d' y DATETIME_FMT = '%Y-%m-%d %H:%M:%S'.
    - Todas las fechas cumplen el patrón y se interpretan sin error.
    """
    assert DATE_FMT == "%Y-%m-%d" and DATETIME_FMT == "%Y-%m-%d %H:%M:%S"
    for fecha in (today_text(), date_offset(-30), date_offset(400)):
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", fecha)
        dt.date.fromisoformat(fecha)
    ahora = now_text()
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", ahora)
    dt.datetime.fromisoformat(ahora)


@tc("CTS_FMT_02", nivel="CTS", modulo="ventas", reqs=["ISO-8601", "RF-19"],
    nombre="Las fechas guardadas se ordenan cronológicamente como texto")
def test_fechas_guardadas_iso_se_ordenan_como_texto(db, empleado, make_product):
    """Comprobar una consecuencia práctica de usar ISO 8601: como las fechas se guardan como texto en
    SQLite, ordenar alfabéticamente debe ser lo mismo que ordenar por tiempo. Los reportes con ventanas
    de fechas (por ejemplo 'Ventas ultimos tres dias', RF-19) dependen de esto.

    Precondiciones: Fixtures db, empleado y make_product(stock=10).
    Pasos:
    - Registrar tres ventas con ventas_srv.registrar() y fijarles con UPDATE las fechas 2025-12-31
      23:59:59, 2026-01-02 08:00:00 y 2026-10-01 12:30:00.
    - Leer sale_datetime de todas las ventas.
    - Comparar sorted() alfabético con el orden por datetime.fromisoformat, y ejecutar SELECT ... ORDER
      BY sale_datetime.
    Esperado:
    - Ambos ordenamientos coinciden.
    - ORDER BY sale_datetime regresa las fechas en orden cronológico.
    """
    pid = make_product(stock=10)
    fechas = ["2025-12-31 23:59:59", "2026-01-02 08:00:00", "2026-10-01 12:30:00"]
    for f in fechas:
        sid, *_ = ventas_srv.registrar(db, None, empleado, "Efectivo", 0, [item(pid, 1)])
        db.execute("UPDATE sales SET sale_datetime=? WHERE id=?", (f, sid))
    guardadas = [r["sale_datetime"] for r in db.query("SELECT sale_datetime FROM sales")]
    assert sorted(guardadas) == sorted(guardadas, key=dt.datetime.fromisoformat)
    assert [r[0] for r in db.query("SELECT sale_datetime FROM sales ORDER BY sale_datetime")] == fechas


# ---------- RFC 4180 ----------
@tc("CTS_CSV_01", nivel="CTS", modulo="productos", reqs=["RFC-4180", "RF-15"],
    nombre="Exportación de inventario conforme a RFC 4180")
def test_csv_de_inventario_cumple_rfc_4180(db, raiz, make_product, tmp_path):
    """Prueba de conformidad con RFC 4180 (formato CSV): el archivo que genera el botón de exportar
    inventario, ProductosUI.export_inventory_csv() de mis_trapitos/ui/productos.py, debe tener
    encabezado, terminar cada registro en CRLF, tener el mismo número de columnas en todas las filas y
    poner entre comillas los textos con comas, comillas dobles o saltos de línea. RF-15.

    Precondiciones: Fixtures db, make_product, tmp_path y raiz (ventana Tk oculta). Tres productos con
      nombres especiales: 'Blusa, edición especial', 'Vestido "Gala"' y 'Falda' + salto de línea +
      'larga'.
    Pasos:
    - Crear ProductosUI(raiz, db).
    - Parchear filedialog.asksaveasfilename para que regrese la ruta del archivo y messagebox.showinfo
      para que no abra diálogos; llamar ui.export_inventory_csv().
    - Leer el archivo en binario y con csv.reader(strict=True).
    Esperado:
    - El archivo termina en \\r\\n y la primera línea empieza con 'id,codigo,producto'.
    - Todas las filas tienen el mismo número de campos.
    - Los tres nombres se leen exactos y las comillas se escapan como ""Gala"".
    """
    make_product(code="P-COMA", name="Blusa, edición especial")
    make_product(code="P-COMILLAS", name='Vestido "Gala"')
    make_product(code="P-SALTO", name="Falda\nlarga")
    ui = ui_productos.ProductosUI(raiz, db)
    salida = tmp_path / "inventario.csv"
    with patch.object(ui_productos.filedialog, "asksaveasfilename", return_value=str(salida)), \
            patch.object(ui_productos.messagebox, "showinfo"):
        ui.export_inventory_csv()
    crudo = salida.read_bytes()
    assert crudo.endswith(b"\r\n") and crudo.split(b"\r\n")[0].startswith(b"id,codigo,producto")
    with salida.open(newline="", encoding="utf-8") as f:
        filas = list(csv.reader(f, strict=True))
    assert len({len(fila) for fila in filas}) == 1
    nombres = {fila[1]: fila[2] for fila in filas[1:]}
    assert nombres == {"P-COMA": "Blusa, edición especial", "P-COMILLAS": 'Vestido "Gala"', "P-SALTO": "Falda\nlarga"}
    assert b'"Vestido ""Gala"""' in crudo


@tc("CTS_CSV_02", nivel="CTS", modulo="reportes", reqs=["RFC-4180", "RF-17"],
    nombre="Exportación de reportes en CSV UTF-8 conforme a RFC 4180")
def test_csv_de_reporte_cumple_rfc_4180_y_utf8(db, raiz, empleado, make_product, tmp_path):
    """Prueba de conformidad RFC 4180 + UTF-8 para la exportación de reportes:
    ReportesUI.export_report_csv() de mis_trapitos/ui/reportes.py debe generar un CSV en UTF-8 válido
    (acentos y eñes legibles en Excel), con encabezado, CRLF y el mismo contenido que se ve en pantalla
    (ui.last_report_rows). RF-17.

    Precondiciones: Fixtures db, raiz, empleado, make_product y tmp_path. Producto 'Suéter de niño'
      vendido 2 veces con 'Tarjeta de credito'.
    Pasos:
    - Crear ReportesUI(raiz, db), elegir 'Ventas por metodo de pago' en ui.report_combo y llamar
      ui.run_report().
    - Parchear el diálogo de guardado y llamar ui.export_report_csv().
    - Decodificar el archivo con decode('utf-8', errors='strict') y separar por \\r\\n.
    - Leerlo con csv.reader(strict=True) y compararlo con ui.last_report_rows.
    Esperado:
    - El archivo es UTF-8 válido y cada registro termina en CRLF.
    - Hay encabezado + una línea por fila del reporte.
    - El encabezado y la primera columna coinciden con lo mostrado en pantalla.
    """
    pid = make_product(name="Suéter de niño")
    ventas_srv.registrar(db, None, empleado, "Tarjeta de credito", 0, [item(pid, 2)])
    ui = ui_reportes.ReportesUI(raiz, db)
    ui.report_combo.set("Ventas por metodo de pago")
    ui.run_report()
    salida = tmp_path / "reporte.csv"
    with patch.object(ui_reportes.filedialog, "asksaveasfilename", return_value=str(salida)), \
            patch.object(ui_reportes.messagebox, "showinfo"):
        ui.export_report_csv()
    texto = salida.read_bytes().decode("utf-8", errors="strict")
    registros = texto.split("\r\n")
    assert registros[-1] == "" and len(registros) == len(ui.last_report_rows) + 2
    with salida.open(newline="", encoding="utf-8") as f:
        filas = list(csv.reader(f, strict=True))
    assert filas[0] == list(ui.last_report_rows[0].keys())
    assert [fila[0] for fila in filas[1:]] == [str(r[0]) for r in ui.last_report_rows]


# ---------- FIPS 180-4 ----------
@tc("CTS_SEG_01", nivel="CTS", modulo="contactos", reqs=["FIPS-180-4", "SEG-01"],
    nombre="Hash de contraseñas conforme a SHA-256 (FIPS 180-4)")
def test_hash_de_contrasena_cumple_vectores_fips_180_4():
    """Prueba de conformidad con FIPS 180-4: hash_password() de utils.py debe producir exactamente el
    SHA-256 del estándar. Se compara contra los vectores de prueba oficiales publicados por el NIST
    (diccionario VECTORES_SHA256 del archivo). FIPS-180-4, SEG-01.

    Precondiciones: Ninguna.
    Pasos:
    - Llamar hash_password('') (mensaje vacío).
    - Llamar hash_password('abc').
    - Llamar hash_password('abcdbcdecdefdefgefghfghighijhijkijkljklmklmnlmnomnopnopq') (mensaje de dos
      bloques).
    Esperado:
    - Los tres resultados son iguales a los vectores publicados por el NIST.
    """
    for mensaje, esperado in VECTORES_SHA256.items():
        assert hash_password(mensaje) == esperado


@tc("CTS_SEG_02", nivel="CTS", modulo="contactos", reqs=["FIPS-180-4", "SEG-01"],
    nombre="Las contraseñas se guardan solo como hash SHA-256")
def test_contrasenas_se_guardan_solo_como_hash(db):
    """Verificar que las contraseñas nunca se guardan en texto plano: empleados_repo.guardar() solo escribe
    en employees.password_hash el SHA-256 hexadecimal de la contraseña. FIPS-180-4, SEG-01.

    Precondiciones: Fixture db (base temporal vacía).
    Pasos:
    - Llamar empleados_repo.guardar(db, None, 'Ana', 'ana', 'Secreta#2026', 'Ventas').
    - Leer todas las columnas del registro con db.one('SELECT * FROM employees WHERE id=?').
    Esperado:
    - password_hash tiene 64 caracteres hexadecimales en minúscula.
    - Ninguna columna contiene el texto 'Secreta#2026'.
    """
    eid = empleados_repo.guardar(db, None, "Ana", "ana", "Secreta#2026", "Ventas")
    fila = db.one("SELECT * FROM employees WHERE id=?", (eid,))
    assert re.fullmatch(r"[0-9a-f]{64}", fila["password_hash"])
    assert all("Secreta#2026" not in str(fila[k]) for k in fila.keys())


# ---------- integridad SQLite ----------
@tc("CTS_BD_01", nivel="CTS", modulo="ventas", reqs=["SQL-FK", "RF-05"],
    nombre="Integridad referencial tras ventas, devoluciones y cancelaciones")
def test_integridad_referencial_tras_operaciones(db, operaciones):
    """Comprobar la integridad referencial de la base después de un día de operaciones (ventas, devolución,
    cancelación y ajuste): las llaves foráneas están activas (Database.__init__ ejecuta PRAGMA
    foreign_keys = ON) y no hay referencias rotas. SQL-FK, RF-05.

    Precondiciones: Fixtures db, empleado, make_product y operaciones (tests/test_conformidad.py):
      productos A (stock 10) y B (stock 8); venta s1 con A×3 + B×1 en Efectivo; venta s2 con B×2 y 10 % de
      descuento en Débito; devolución de 1 pieza de A en s1; cancelación de s2; y ajuste del stock de A a
      15 con productos_repo.guardar().
    Pasos:
    - Ejecutar db.scalar('PRAGMA foreign_keys').
    - Ejecutar db.query('PRAGMA foreign_key_check').
    Esperado:
    - foreign_keys = 1.
    - foreign_key_check no regresa filas.
    """
    assert db.scalar("PRAGMA foreign_keys") == 1
    assert db.query("PRAGMA foreign_key_check") == []


@tc("CTS_BD_02", nivel="CTS", modulo="ventas", reqs=["SQL-FK"],
    nombre="La base pasa la verificación de integridad de SQLite")
def test_integridad_fisica_de_la_base(db, operaciones):
    """Comprobar que el archivo de la base queda íntegro según el propio SQLite después de las operaciones
    del día. SQL-FK.

    Precondiciones: Fixtures db, empleado, make_product y operaciones (tests/test_conformidad.py):
      productos A (stock 10) y B (stock 8); venta s1 con A×3 + B×1 en Efectivo; venta s2 con B×2 y 10 % de
      descuento en Débito; devolución de 1 pieza de A en s1; cancelación de s2; y ajuste del stock de A a
      15 con productos_repo.guardar().
    Pasos:
    - Ejecutar db.scalar('PRAGMA integrity_check').
    Esperado:
    - El resultado es 'ok'.
    """
    assert db.scalar("PRAGMA integrity_check") == "ok"


@tc("CTS_BD_03", nivel="CTS", modulo="ventas", reqs=["SQL-FK", "RF-06"],
    nombre="La base rechaza registros huérfanos")
def test_base_rechaza_registros_huerfanos(db, empleado, make_product):
    """Comprobar que la base rechaza registros huérfanos aunque alguien escriba SQL directo, saltándose los
    repositorios: partidas, movimientos o promociones que apuntan a productos o ventas que no existen.
    SQL-FK, RF-06.

    Precondiciones: Fixtures db, empleado y make_product. Un producto y una venta registrados con
      ventas_srv.registrar().
    Pasos:
    - Ejecutar con db.execute() un INSERT INTO sale_items con product_id = 9999.
    - Ejecutar un INSERT INTO inventory_movements con related_sale_id = 9999.
    - Ejecutar un INSERT INTO promotions con product_id = 9999.
    - Contar otra vez las filas de sale_items.
    Esperado:
    - Las tres inserciones levantan sqlite3.IntegrityError.
    - sale_items tiene las mismas filas que antes.
    """
    pid = make_product()
    sid, *_ = ventas_srv.registrar(db, None, empleado, "Efectivo", 0, [item(pid, 1)])
    antes = db.scalar("SELECT COUNT(*) FROM sale_items")
    for sql, params in (
        ("INSERT INTO sale_items(sale_id, product_id, quantity, unit_price, promo_discount_percent, line_total) "
         "VALUES(?,?,?,?,?,?)", (sid, 9999, 1, 10, 0, 10)),
        ("INSERT INTO inventory_movements(product_id, movement_type, quantity, movement_datetime, reason, "
         "related_sale_id) VALUES(?,?,?,?,?,?)", (pid, "SALIDA", -1, now_text(), "x", 9999)),
        ("INSERT INTO promotions(product_id, discount_percent, start_date, end_date, created_at) VALUES(?,?,?,?,?)",
         (9999, 10, today_text(), today_text(), now_text())),
    ):
        with pytest.raises(sqlite3.IntegrityError):
            db.execute(sql, params)
    assert db.scalar("SELECT COUNT(*) FROM sale_items") == antes


# ---------- especificación del SDD ----------
@tc("CTS_SDD_01", nivel="CTS", modulo="ventas", reqs=["SDD-CONTRATOS", "RF-06", "RF-08"],
    nombre="Registrar, devolver y cancelar cumplen el contrato del SDD")
def test_operaciones_de_venta_cumplen_contrato_del_sdd(db, empleado, make_product):
    """Prueba de conformidad con la tabla de contratos del SDD (sección 3.3): ventas_srv.registrar()
    regresa (sale_id entero, subtotal, monto de descuento, total) con total = subtotal − descuento y los
    mismos importes que guarda en sales; devoluciones_srv.devolver() y cancelar_venta() no regresan
    valor. SDD-CONTRATOS, RF-06, RF-08.

    Precondiciones: Fixtures db, empleado y make_product(price=200, stock=10).
    Pasos:
    - Llamar ventas_srv.registrar(db, None, empleado, 'Efectivo', 10, [3 piezas]).
    - Revisar que el resultado es una tupla de 4 y que sale_id es int.
    - Leer la venta con ventas_repo.obtener_por_id(db, sale_id).
    - Llamar devoluciones_srv.devolver(db, sale_id, pid, 1, 'x') y devoluciones_srv.cancelar_venta(db,
      sale_id, 'x').
    Esperado:
    - Resultado = (sale_id, 600, 60, 540).
    - La venta guardada tiene subtotal 600, discount_amount 60, total 540 y status 'ACTIVA'.
    - devolver() y cancelar_venta() regresan None.
    """
    pid = make_product(price=200, stock=10)
    resultado = ventas_srv.registrar(db, None, empleado, "Efectivo", 10, [item(pid, 3)])
    assert isinstance(resultado, tuple) and len(resultado) == 4
    sale_id, subtotal, descuento, total = resultado
    assert isinstance(sale_id, int)
    assert (subtotal, descuento, total) == pytest.approx((600, 60, 540))
    venta = ventas_repo.obtener_por_id(db, sale_id)
    assert (venta["subtotal"], venta["discount_amount"], venta["total"], venta["status"]) == (600, 60, 540, "ACTIVA")
    assert devoluciones_srv.devolver(db, sale_id, pid, 1, "x") is None
    assert devoluciones_srv.cancelar_venta(db, sale_id, "x") is None


@tc("CTS_SDD_02", nivel="CTS", modulo="productos", reqs=["SDD-CONTRATOS", "RF-05"],
    nombre="Los movimientos de inventario usan los tipos y signos del SDD")
def test_movimientos_usan_tipos_y_signos_del_sdd(db, operaciones):
    """Verificar que el kardex usa solo los tipos de movimiento definidos en el SDD (ENTRADA, SALIDA,
    AJUSTE, DEVOLUCION, CANCELACION; constante MOVIMIENTOS_SDD) y que el signo de cada cantidad
    corresponde a su efecto en el stock. SDD-CONTRATOS, RF-05.

    Precondiciones: Fixtures db, empleado, make_product y operaciones (tests/test_conformidad.py):
      productos A (stock 10) y B (stock 8); venta s1 con A×3 + B×1 en Efectivo; venta s2 con B×2 y 10 % de
      descuento en Débito; devolución de 1 pieza de A en s1; cancelación de s2; y ajuste del stock de A a
      15 con productos_repo.guardar().
    Pasos:
    - Leer todos los movimientos con SELECT product_id, movement_type, quantity FROM
      inventory_movements.
    - Revisar el conjunto de tipos y el signo de cada cantidad.
    - Sumar las cantidades por producto (A y B) y compararlas con su stock.
    Esperado:
    - Los tipos son exactamente los cinco del SDD.
    - SALIDA es negativa; ENTRADA, DEVOLUCION y CANCELACION son positivas (AJUSTE puede tener cualquier
      signo).
    - La suma de movimientos de cada producto es igual a su stock.
    """
    movimientos = db.query("SELECT product_id, movement_type, quantity FROM inventory_movements")
    assert {m["movement_type"] for m in movimientos} == MOVIMIENTOS_SDD
    for m in movimientos:
        if m["movement_type"] == "SALIDA":
            assert m["quantity"] < 0
        elif m["movement_type"] != "AJUSTE":
            assert m["quantity"] > 0
    for pid in (operaciones["a"], operaciones["b"]):
        suma = sum(m["quantity"] for m in movimientos if m["product_id"] == pid)
        assert suma == db.scalar("SELECT stock FROM products WHERE id=?", (pid,))


@tc("CTS_SDD_03", nivel="CTS", modulo="ventas", reqs=["SDD-CONTRATOS", "RF-07"],
    nombre="Los métodos de pago son exactamente los de RF-07")
def test_metodos_de_pago_son_los_de_rf_07(db, empleado, make_product):
    """Verificar que los métodos de pago son exactamente los que pide RF-07: efectivo, tarjeta de crédito,
    tarjeta de débito y transferencia. Se revisa la constante config.PAYMENT_METHODS (que alimenta el
    combo de la pantalla de Ventas) y que ventas_srv.registrar() rechaza cualquier otro. SDD-CONTRATOS,
    RF-07.

    Precondiciones: Fixtures db, empleado y make_product.
    Pasos:
    - Comparar PAYMENT_METHODS con ('Efectivo', 'Tarjeta de credito', 'Tarjeta de debito',
      'Transferencia bancaria').
    - Llamar ventas_srv.registrar(db, None, empleado, 'Vales de despensa', 0, [item]).
    - Contar las ventas.
    Esperado:
    - La tupla coincide en contenido y orden.
    - 'Vales de despensa' levanta ValueError y no se guarda ninguna venta.
    """
    assert PAYMENT_METHODS == ("Efectivo", "Tarjeta de credito", "Tarjeta de debito", "Transferencia bancaria")
    pid = make_product()
    with pytest.raises(ValueError):
        ventas_srv.registrar(db, None, empleado, "Vales de despensa", 0, [item(pid, 1)])
    assert db.scalar("SELECT COUNT(*) FROM sales") == 0
