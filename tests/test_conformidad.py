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
    """Las funciones de fecha producen AAAA-MM-DD y AAAA-MM-DD hh:mm:ss (ISO 8601, perfil RFC 3339
    con espacio como separador).

    Precondiciones: Ninguna.
    Pasos:
    - Obtener today_text(), date_offset(-30) y now_text()
    - Interpretarlas con datetime.date/datetime.fromisoformat
    Esperado:
    - Coinciden con el patrón ISO 8601 y se interpretan sin error
    - DATE_FMT y DATETIME_FMT son los formatos ISO configurados
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
    """Al guardarse en ISO 8601, ordenar por texto equivale a ordenar por tiempo (lo usan los reportes).

    Precondiciones: Producto con stock y un empleado.
    Pasos:
    - Registrar tres ventas y fijarles fechas de distintos días, meses y años
    - Leer sale_datetime de la base
    Esperado:
    - Cada fecha guardada es ISO 8601 válida
    - El orden alfabético coincide con el orden cronológico
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
    """El CSV del inventario sigue RFC 4180: encabezado, CRLF, mismas columnas y comillas
    para comas, comillas dobles y saltos de línea.

    Precondiciones: Productos con coma, comillas y salto de línea en el nombre.
    Pasos:
    - Exportar el inventario desde la pantalla de Productos
    - Leer el archivo en binario y con el lector csv en modo estricto
    Esperado:
    - Cada registro termina en CRLF y la primera línea es el encabezado
    - Todos los registros tienen el mismo número de campos
    - Los textos especiales se conservan exactos
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
    """Un reporte exportado es CSV RFC 4180 en UTF-8: acentos y eñes legibles, encabezado y CRLF.

    Precondiciones: Una venta registrada con «Tarjeta de crédito».
    Pasos:
    - Ejecutar el reporte «Ventas por metodo de pago» y exportarlo
    - Decodificar el archivo como UTF-8 estricto
    Esperado:
    - El archivo es UTF-8 válido, termina cada registro en CRLF y empieza con encabezado
    - El reporte exportado coincide con lo que se ve en pantalla
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
    """hash_password produce el SHA-256 de FIPS 180-4 para los vectores oficiales del NIST.

    Precondiciones: Ninguna.
    Pasos:
    - Calcular hash_password del mensaje vacío, de «abc» y del mensaje de dos bloques
    Esperado:
    - Los tres resultados coinciden con los vectores publicados
    """
    for mensaje, esperado in VECTORES_SHA256.items():
        assert hash_password(mensaje) == esperado


@tc("CTS_SEG_02", nivel="CTS", modulo="contactos", reqs=["FIPS-180-4", "SEG-01"],
    nombre="Las contraseñas se guardan solo como hash SHA-256")
def test_contrasenas_se_guardan_solo_como_hash(db):
    """La tabla de empleados guarda un hash SHA-256 hexadecimal (64 caracteres) y nunca el texto plano.

    Precondiciones: BD temporal vacía.
    Pasos:
    - Registrar un empleado con contraseña «Secreta#2026»
    - Leer todas las columnas de su registro
    Esperado:
    - password_hash tiene 64 caracteres hexadecimales en minúscula
    - Ninguna columna contiene la contraseña en texto plano
    """
    eid = empleados_repo.guardar(db, None, "Ana", "ana", "Secreta#2026", "Ventas")
    fila = db.one("SELECT * FROM employees WHERE id=?", (eid,))
    assert re.fullmatch(r"[0-9a-f]{64}", fila["password_hash"])
    assert all("Secreta#2026" not in str(fila[k]) for k in fila.keys())


# ---------- integridad SQLite ----------
@tc("CTS_BD_01", nivel="CTS", modulo="ventas", reqs=["SQL-FK", "RF-05"],
    nombre="Integridad referencial tras ventas, devoluciones y cancelaciones")
def test_integridad_referencial_tras_operaciones(db, operaciones):
    """Después de operar, la base no tiene referencias rotas y las llaves foráneas están activas.

    Precondiciones: Ventas, devolución parcial, cancelación y ajuste registrados.
    Pasos:
    - Consultar PRAGMA foreign_keys
    - Ejecutar PRAGMA foreign_key_check
    Esperado:
    - foreign_keys = 1
    - foreign_key_check no reporta filas
    """
    assert db.scalar("PRAGMA foreign_keys") == 1
    assert db.query("PRAGMA foreign_key_check") == []


@tc("CTS_BD_02", nivel="CTS", modulo="ventas", reqs=["SQL-FK"],
    nombre="La base pasa la verificación de integridad de SQLite")
def test_integridad_fisica_de_la_base(db, operaciones):
    """El archivo de base de datos es íntegro según SQLite tras las operaciones del día.

    Precondiciones: Ventas, devolución parcial, cancelación y ajuste registrados.
    Pasos:
    - Ejecutar PRAGMA integrity_check
    Esperado:
    - El resultado es «ok»
    """
    assert db.scalar("PRAGMA integrity_check") == "ok"


@tc("CTS_BD_03", nivel="CTS", modulo="ventas", reqs=["SQL-FK", "RF-06"],
    nombre="La base rechaza registros huérfanos")
def test_base_rechaza_registros_huerfanos(db, empleado, make_product):
    """Las llaves foráneas impiden partidas, movimientos o promociones de productos o ventas inexistentes.

    Precondiciones: Un producto y una venta registrados.
    Pasos:
    - Insertar una partida con producto inexistente
    - Insertar un movimiento ligado a una venta inexistente
    - Insertar una promoción de un producto inexistente
    Esperado:
    - Las tres inserciones fallan con IntegrityError
    - La base queda sin cambios
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
    """Las firmas y resultados de las operaciones coinciden con la tabla de contratos del SDD (§3.3).

    Precondiciones: Producto de $200 con stock 10.
    Pasos:
    - Registrar una venta de 3 piezas con 10 % de descuento general
    - Devolver 1 pieza y cancelar la venta
    Esperado:
    - Registrar regresa (id entero, subtotal, monto de descuento, total) con total = subtotal − descuento
    - El monto de descuento es subtotal × 10 / 100 y la venta guardada tiene esos importes
    - Devolver y cancelar no regresan valor
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
    """Cada movimiento es de un tipo definido en el SDD (RF-05) y su signo corresponde al efecto en el stock.

    Precondiciones: Ventas, devolución parcial, cancelación y ajuste registrados.
    Pasos:
    - Leer todos los movimientos de inventario
    - Sumar las cantidades por producto
    Esperado:
    - Solo hay tipos ENTRADA, SALIDA, AJUSTE, DEVOLUCION y CANCELACION
    - SALIDA es negativa; ENTRADA, DEVOLUCION y CANCELACION son positivas
    - La suma de movimientos de cada producto es igual a su stock
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
    """La aplicación ofrece y acepta solo efectivo, tarjeta de crédito, tarjeta de débito y transferencia.

    Precondiciones: Producto con stock y un empleado.
    Pasos:
    - Comparar PAYMENT_METHODS con la lista de RF-07
    - Registrar una venta con un método fuera de la lista
    Esperado:
    - La lista coincide en contenido y orden
    - El método fuera de la lista se rechaza y no se guarda la venta
    """
    assert PAYMENT_METHODS == ("Efectivo", "Tarjeta de credito", "Tarjeta de debito", "Transferencia bancaria")
    pid = make_product()
    with pytest.raises(ValueError):
        ventas_srv.registrar(db, None, empleado, "Vales de despensa", 0, [item(pid, 1)])
    assert db.scalar("SELECT COUNT(*) FROM sales") == 0
