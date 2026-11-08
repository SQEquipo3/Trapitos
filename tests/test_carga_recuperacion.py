"""Pruebas de sistema no funcionales: carga (volumen de datos) y recuperación ante una caída."""
import subprocess
import sys
import textwrap
import time
from pathlib import Path

from mis_trapitos.data.database import Database
from mis_trapitos.data.repositories import clientes as clientes_repo
from mis_trapitos.data.repositories import proveedores as proveedores_repo
from mis_trapitos.data.repositories import reportes as reportes_repo
from mis_trapitos.services import ventas as ventas_srv
from mis_trapitos.ui.reportes import REPORTS
from tests.conftest import stock
from tests.tc import tc
from utils import today_text

ROOT = Path(__file__).resolve().parent.parent
VENTAS_CARGA = 1500
LIMITE_REPORTE_S = 2.0
PARAMETROS = {"Productos con stock bajo": "5", "Productos disponibles por categoria": "Ropa",
              "Productos de proveedor especifico": "1", "Productos comprados mas de una vez por cliente": "1",
              "Productos vendidos por categoria ultimo mes": "Ropa",
              "Productos con precio superior y existencias": "100"}


@tc("STS_CAR_01", nivel="STS", modulo="reportes", reqs=["RF-15", "RF-17", "RF-18", "RF-19", "RF-25", "RNF-01"],
    nombre="Carga: reportes con un año de ventas responden en menos de 2 s")
def test_reportes_responden_con_volumen_de_un_ano(db, empleado, make_product):
    """Prueba de carga: con el volumen de ventas de un año de la tienda, cada reporte de la pantalla
    Reportes (la lista REPORTS de mis_trapitos/ui/reportes.py) debe responder en menos de 2 segundos,
    que es lo aceptable para una consulta en mostrador. También confirma que, tras la carga, stock y
    ventas siguen cuadrando. RNF-01, RF-15, RF-17, RF-18, RF-19, RF-25.

    Precondiciones: Fixtures db, empleado y make_product. Se crean 1 proveedor, 40 productos con stock
      500 y 20 clientes en 5 regiones.
    Pasos:
    - Registrar 1500 ventas de 1 pieza con ventas_srv.registrar(), rotando producto, cliente y los 4
      métodos de pago.
    - Para cada nombre en REPORTS, medir con time.perf_counter() cuánto tarda reportes_repo.ejecutar(db,
      nombre, parametro).
    - Contar las ventas y sumar el stock de los 40 productos.
    Esperado:
    - Ningún reporte tarda 2 s o más (si alguno sí, el mensaje de la prueba dice cuál y cuánto).
    - Hay 1500 ventas y el stock total es 40 × 500 − 1500 = 18 500.
    Comentarios: 1500 ventas ≈ 5 ventas diarias durante un año. Las constantes VENTAS_CARGA y
      LIMITE_REPORTE_S están al inicio de tests/test_carga_recuperacion.py.
    """
    proveedores_repo.guardar(db, None, ("Textiles Norte", "555", "Av 1", "Ropa", today_text()))
    productos = [make_product(code=f"C-{i:03d}", category="Ropa" if i % 2 else "Calzado",
                              price=50 + i * 10, stock=500, supplier_id=1) for i in range(40)]
    clientes = [clientes_repo.guardar(db, None, (f"Cliente {i}", "555", "c@x.com", "Calle", f"Region {i % 5}", ""))
                for i in range(20)]
    metodos = ("Efectivo", "Tarjeta de credito", "Tarjeta de debito", "Transferencia bancaria")
    for i in range(VENTAS_CARGA):
        ventas_srv.registrar(db, clientes[i % 20], empleado, metodos[i % 4], 0,
                             [{"product_id": productos[i % 40], "quantity": 1}])
    tiempos = {}
    for nombre in REPORTS:
        inicio = time.perf_counter()
        reportes_repo.ejecutar(db, nombre, PARAMETROS.get(nombre, ""))
        tiempos[nombre] = time.perf_counter() - inicio
    lentos = {n: round(t, 2) for n, t in tiempos.items() if t >= LIMITE_REPORTE_S}
    assert not lentos, lentos
    assert db.scalar("SELECT COUNT(*) FROM sales") == VENTAS_CARGA
    assert sum(stock(db, p) for p in productos) == 40 * 500 - VENTAS_CARGA


@tc("STS_REC_01", nivel="STS", modulo="ventas", reqs=["RF-04", "RF-06", "SQL-FK"],
    nombre="Recuperación: una caída a mitad de una venta no deja datos a medias")
def test_caida_a_mitad_de_venta_se_recupera_al_reabrir(tmp_path):
    """Prueba de recuperación: si la aplicación se cae (corte de luz, proceso terminado) a mitad de guardar
    una venta, al reabrirla la base debe conservar las ventas ya confirmadas y no dejar rastro de la
    venta incompleta. Lo garantiza el db.transaction() de ventas_srv.registrar(). RF-04, RF-06, SQL-FK.

    Precondiciones: Base en disco en tmp_path (fixture de pytest). Un proceso Python aparte crea un
      empleado y un producto P-1 con stock 10.
    Pasos:
    - En el proceso aparte, registrar una venta completa de 2 piezas con ventas.registrar().
    - En el mismo proceso, reemplazar ventas_repo.insertar_partida por una función que hace os._exit(9)
      e iniciar otra venta de 3 piezas: el proceso muere después de insertar el encabezado.
    - Comprobar que el proceso terminó con código 9.
    - Reabrir la base con Database(ruta, load_examples=False) y consultar sales, sale_items, movimientos
      SALIDA, stock, PRAGMA integrity_check y PRAGMA foreign_key_check.
    Esperado:
    - Existe 1 venta, 1 partida y 1 movimiento SALIDA; el stock es 8.
    - La venta interrumpida no existe (ni encabezado, ni partidas, ni movimientos).
    - integrity_check = 'ok' y foreign_key_check no regresa filas.
    """
    ruta = tmp_path / "tienda.db"
    script = textwrap.dedent(f"""
        import os, sys
        sys.path.insert(0, {str(ROOT)!r})
        from mis_trapitos.data.database import Database
        from mis_trapitos.data.repositories import empleados, productos, ventas as ventas_repo
        from mis_trapitos.services import ventas
        db = Database({str(ruta)!r}, load_examples=False)
        emp = empleados.guardar(db, None, "Ana", "ana", "1234", "Ventas")
        pid = productos.guardar(db, None, ("P-1", "Blusa", "Ropa", "M", "Azul", 80, 200, 10, None,
                                           "2026-01-01", "Marca", "Todo", ""))
        ventas.registrar(db, None, emp, "Efectivo", 0, [{{"product_id": pid, "quantity": 2}}])
        ventas_repo.insertar_partida = lambda *a, **k: os._exit(9)   # caída tras guardar el encabezado
        ventas.registrar(db, None, emp, "Efectivo", 0, [{{"product_id": pid, "quantity": 3}}])
    """)
    proceso = subprocess.run([sys.executable, "-c", script], cwd=ROOT, capture_output=True, text=True, timeout=60)
    assert proceso.returncode == 9, proceso.stderr
    db = Database(str(ruta), load_examples=False)
    try:
        assert db.scalar("SELECT COUNT(*) FROM sales") == 1
        assert db.scalar("SELECT COUNT(*) FROM sale_items") == 1
        assert db.scalar("SELECT COUNT(*) FROM inventory_movements WHERE movement_type='SALIDA'") == 1
        assert db.scalar("SELECT stock FROM products") == 8
        assert db.scalar("PRAGMA integrity_check") == "ok"
        assert db.query("PRAGMA foreign_key_check") == []
    finally:
        db.close()
