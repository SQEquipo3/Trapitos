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
    """Con el volumen de ventas de un año de la tienda, cada reporte responde en menos de 2 segundos.

    Precondiciones: 40 productos, 20 clientes y 1500 ventas registradas con el servicio de ventas.
    Pasos:
    - Registrar 1500 ventas repartidas entre productos, clientes y métodos de pago
    - Ejecutar cada reporte de la pantalla Reportes con su parámetro y medir el tiempo
    Esperado:
    - Ningún reporte tarda 2 s o más
    - El stock y el número de ventas quedan consistentes tras la carga
    Comentarios: 1500 ventas ≈ 5 ventas diarias durante un año. El límite de 2 s es el tiempo de respuesta
      aceptable para una consulta en mostrador.
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
    """Si la aplicación se cae mientras guarda una venta, al reabrirla la base conserva las ventas
    confirmadas y descarta la venta incompleta.

    Precondiciones: Base en disco con un producto de stock 10 y un empleado.
    Pasos:
    - En otro proceso, registrar una venta completa de 2 piezas
    - En ese mismo proceso, iniciar otra venta y terminar el proceso de golpe tras guardar el encabezado
    - Reabrir la base con la aplicación
    Esperado:
    - La primera venta existe completa y el stock es 8
    - La venta interrumpida no existe (ni encabezado, ni partidas, ni movimientos)
    - PRAGMA integrity_check es «ok» y no hay referencias rotas
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
