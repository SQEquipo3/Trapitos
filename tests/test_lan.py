"""Servicio LAN entre terminales (#56): inventario compartido, ventas idempotentes y concurrencia.

El servicio corre de verdad (HTTP en 127.0.0.1, puerto libre) sobre una base temporal; cada
ClienteLAN hace el papel de una terminal de venta distinta.
"""
import threading
import time
import tkinter as tk
from unittest.mock import patch

import pytest

from mis_trapitos.data.database import Database
from mis_trapitos.data.repositories import empleados as empleados_repo
from mis_trapitos.data.repositories import productos as productos_repo
from mis_trapitos.lan.cliente import ClienteLAN, ErrorLAN, nueva_clave
from mis_trapitos.lan.servidor import ServidorLAN
from mis_trapitos.services import ventas as ventas_srv
from mis_trapitos.ui import terminal_lan
from mis_trapitos.ui.terminal_lan import CarritoLAN, TerminalLAN
from tests.conftest import stock
from tests.tc import tc
from utils import today_text


def producto(db, code, stock_inicial, price=200):
    return productos_repo.guardar(db, None, (code, "Blusa", "Ropa", "M", "Azul", 80, price, stock_inicial,
                                             None, today_text(), "Marca", "Todo", ""))


@pytest.fixture
def servicio(db):
    """Servicio LAN sobre la misma base que el fixture db (que hace de terminal principal)."""
    empleados_repo.guardar(db, None, "Vendedora A", "ventaA", "clave-a", "Vendedor")
    empleados_repo.guardar(db, None, "Vendedor B", "ventaB", "clave-b", "Vendedor")
    s = ServidorLAN(db.path, host="127.0.0.1", puerto=0).iniciar()
    yield s
    s.detener()


def terminal(servicio, usuario="ventaA", contrasena="clave-a"):
    c = ClienteLAN(servicio.url)
    assert c.iniciar_sesion(usuario, contrasena) is not None
    return c


def venta(c, pid, qty=1, clave=None):
    return c.registrar_venta(clave or nueva_clave(), None, "Efectivo", 0, [{"product_id": pid, "quantity": qty}])


@tc("UTS_LAN_01", nivel="UTS", modulo="productos", reqs=["RF-04", "RNF-01"],
    nombre="El descuento de stock es condicionado y nunca deja existencias negativas")
def test_descuento_condicionado_no_deja_stock_negativo(db, make_product):
    """Comprobar que productos_repo.ajustar_stock() solo descuenta si alcanza el stock vigente en la base
    (UPDATE ... WHERE stock + delta >= 0). Es la defensa de #56: aunque dos terminales validen el mismo
    stock, solo una puede descontar la última pieza. Las entradas (delta positivo) siempre se aplican.

    Precondiciones: Fixtures db y make_product(stock=2).
    Pasos:
    - Descontar 2 piezas con ajustar_stock(db, pid, -2).
    - Intentar descontar 1 pieza más.
    - Sumar 3 piezas con ajustar_stock(db, pid, 3).
    Esperado:
    - El primer descuento deja stock 0.
    - El segundo levanta ValueError 'Stock insuficiente.' y el stock sigue en 0.
    - La entrada deja stock 3.
    """
    pid = make_product(stock=2)
    productos_repo.ajustar_stock(db, pid, -2)
    assert stock(db, pid) == 0
    with pytest.raises(ValueError, match="Stock insuficiente"):
        productos_repo.ajustar_stock(db, pid, -1)
    assert stock(db, pid) == 0
    productos_repo.ajustar_stock(db, pid, 3)
    assert stock(db, pid) == 3


@tc("UTS_LAN_01")
def test_transaccion_toma_el_bloqueo_de_escritura_al_iniciar(db, make_product):
    pid = make_product(stock=5)
    otra = Database(db.path, load_examples=False)
    otra.conn.execute("PRAGMA busy_timeout = 0")
    try:
        with db.transaction():
            productos_repo.obtener_por_id(db, pid)        # solo lectura, pero ya con BEGIN IMMEDIATE
            with pytest.raises(Exception, match="locked"):
                otra.conn.execute("BEGIN IMMEDIATE")
    finally:
        otra.close()


@tc("UTS_LAN_02", nivel="UTS", modulo="ventas", reqs=["RNF-01", "RF-04"],
    nombre="Terminal de venta: carrito remoto y reintento seguro con la misma clave")
def test_carrito_remoto_reintenta_con_la_misma_clave():
    """Probar CarritoLAN (lógica de la terminal de venta, sin Tk) con un cliente simulado: valida
    contra la copia del inventario, y si la venta se queda sin respuesta conserva la clave y bloquea el
    carrito hasta reintentar, de modo que el reintento no puede duplicar la venta.

    Precondiciones: Cliente simulado cuyo registrar_venta falla la primera vez con ErrorLAN('UNAVAILABLE')
      y la segunda devuelve una venta con stock 4. Inventario con el producto C-1 (id 1, stock 5).
    Pasos:
    - Agregar 6 piezas de C-1 (más que el stock) y luego 1 pieza.
    - Registrar la venta (falla sin respuesta); intentar agregar otra pieza y vaciar el carrito.
    - Registrar de nuevo.
    Esperado:
    - Agregar 6 piezas se rechaza con 'Stock insuficiente.'.
    - Tras la falla, agregar y vaciar se rechazan con 'venta sin confirmar'.
    - El segundo envío usa la misma clave que el primero; el carrito queda vacío y el stock local en 4.
    """
    claves = []

    class ClienteFalso:
        def registrar_venta(self, clave, cliente_id, metodo, descuento, carrito):
            claves.append(clave)
            if len(claves) == 1:
                raise ErrorLAN("UNAVAILABLE", "sin red")
            return {"sale_id": 1, "stock": {"1": 4}}

    c = CarritoLAN(ClienteFalso())
    c.cargar_inventario([{"id": 1, "codigo": "C-1", "producto": "Blusa", "stock": 5, "precio": 100, "promo": 10}])
    with pytest.raises(ValueError, match="Stock insuficiente"):
        c.agregar("C-1", 6)
    c.agregar("C-1", 1)
    assert c.totales(0) == pytest.approx((90, 0, 90))
    with pytest.raises(ErrorLAN):
        c.registrar(None, "Efectivo", 0)
    for accion in (lambda: c.agregar("C-1", 1), c.vaciar):
        with pytest.raises(ValueError, match="venta sin confirmar"):
            accion()
    c.registrar(None, "Efectivo", 0)
    assert claves[0] == claves[1]
    assert c.cart == [] and c.pendiente is None and c.productos[1]["stock"] == 4


@tc("UTS_LAN_02")
def test_rechazo_definitivo_libera_el_carrito():
    class ClienteFalso:
        def registrar_venta(self, *args):
            raise ErrorLAN("INSUFFICIENT_STOCK", "Stock insuficiente.")

    c = CarritoLAN(ClienteFalso())
    c.cargar_inventario([{"id": 1, "codigo": "C-1", "producto": "Blusa", "stock": 5, "precio": 100, "promo": 0}])
    c.agregar("C-1", 1)
    with pytest.raises(ErrorLAN):
        c.registrar(None, "Efectivo", 0)
    assert c.pendiente is None
    c.vaciar()


@tc("ITS_LAN_01", nivel="ITS", modulo="ventas", reqs=["RNF-01", "RF-04", "RF-06"],
    nombre="Venta de una terminal LAN descuenta stock y las demás terminales lo ven")
def test_venta_remota_descuenta_stock_y_otra_terminal_lo_ve(db, servicio):
    """Integración servicio LAN + base: una venta registrada desde la terminal A por HTTP descuenta el
    stock en la base de la terminal principal, deja venta, partida y movimiento SALIDA, y la terminal B
    ve el stock nuevo en su siguiente consulta. La aplicación de la terminal principal lo detecta con
    db.version_datos() (PRAGMA data_version), que es lo que App.sondear_cambios revisa cada 2 s.

    Precondiciones: Fixture servicio (ServidorLAN en 127.0.0.1 sobre la base del fixture db) con dos
      vendedores. Producto ACEP-LAN-01 con stock 10. Terminales A y B con sesión iniciada.
    Pasos:
    - Leer el inventario en B y guardar db.version_datos().
    - Vender 1 pieza de ACEP-LAN-01 desde A.
    - Leer el inventario en B y la base de la terminal principal.
    Esperado:
    - A recibe sale_id y el stock confirmado 9 en la respuesta.
    - B ve stock 9; la base tiene stock 9, una venta del empleado de la sesión de A y un movimiento SALIDA −1.
    - db.version_datos() cambió, así que la terminal principal refresca su inventario.
    """
    pid = producto(db, "ACEP-LAN-01", 10)
    a, b = terminal(servicio), terminal(servicio, "ventaB", "clave-b")
    assert {p["codigo"]: p["stock"] for p in b.inventario()}["ACEP-LAN-01"] == 10
    version = db.version_datos()
    r = venta(a, pid)
    assert r["stock"] == {str(pid): 9} and r["sale_id"] > 0
    assert {p["codigo"]: p["stock"] for p in b.inventario()}["ACEP-LAN-01"] == 9
    assert stock(db, pid) == 9
    assert db.scalar("SELECT employee_id FROM sales WHERE id=?", (r["sale_id"],)) == a.empleado["id"]
    assert db.scalar("SELECT quantity FROM inventory_movements WHERE related_sale_id=? AND movement_type='SALIDA'",
                     (r["sale_id"],)) == -1
    assert db.version_datos() != version


@tc("ITS_LAN_01")
def test_venta_en_la_principal_se_ve_en_la_terminal(db, servicio):
    pid = producto(db, "P-1", 5)
    b = terminal(servicio, "ventaB", "clave-b")
    ventas_srv.registrar(db, None, 1, "Efectivo", 0, [{"product_id": pid, "quantity": 2}])
    assert b.inventario()[0]["stock"] == 3


@tc("ITS_LAN_01")
def test_partidas_repetidas_se_consolidan_y_se_validan_juntas(db, servicio):
    pid = producto(db, "P-1", 4)
    a = terminal(servicio)
    with pytest.raises(ErrorLAN) as e:
        a.registrar_venta(nueva_clave(), None, "Efectivo", 0,
                          [{"product_id": pid, "quantity": 3}, {"product_id": pid, "quantity": 2}])
    assert e.value.codigo == "INSUFFICIENT_STOCK"
    assert stock(db, pid) == 4
    a.registrar_venta(nueva_clave(), None, "Efectivo", 0,
                      [{"product_id": pid, "quantity": 2}, {"product_id": pid, "quantity": 2}])
    assert stock(db, pid) == 0
    assert db.scalar("SELECT COUNT(*) FROM sale_items") == 1


@tc("ITS_LAN_02", nivel="ITS", modulo="ventas", reqs=["RNF-01", "SDD-CONTRATOS"],
    nombre="Reenviar una venta con la misma clave no la duplica")
def test_misma_clave_no_duplica_la_venta(db, servicio):
    """Contrato de idempotencia del SDD 7.1/7.4: si la terminal no recibió la respuesta y reenvía la
    venta con la MISMA clave, el servicio devuelve el resultado original sin volver a descontar; la
    misma clave con otro contenido se rechaza con IDEMPOTENCY_CONFLICT; y la clave se puede consultar
    con GET /ventas/<clave> para recuperar el ticket.

    Precondiciones: Fixture servicio; producto P-1 con stock 5; terminal A con sesión.
    Pasos:
    - Vender 2 piezas con la clave K desde A.
    - Reenviar exactamente la misma venta con la clave K.
    - Enviar con la clave K una venta de 1 pieza.
    - Consultar la clave K con consultar_venta() y una clave inexistente.
    Esperado:
    - El reenvío devuelve el mismo sale_id con repetida=True; hay 1 venta y el stock es 3.
    - El contenido distinto se rechaza con código IDEMPOTENCY_CONFLICT y el stock sigue en 3.
    - La consulta de K devuelve el mismo sale_id; la clave inexistente responde NOT_FOUND.
    """
    pid = producto(db, "P-1", 5)
    a = terminal(servicio)
    clave = nueva_clave()
    primera = venta(a, pid, 2, clave)
    repetida = venta(a, pid, 2, clave)
    assert repetida["sale_id"] == primera["sale_id"] and repetida["repetida"] is True
    assert db.scalar("SELECT COUNT(*) FROM sales") == 1 and stock(db, pid) == 3
    with pytest.raises(ErrorLAN) as e:
        venta(a, pid, 1, clave)
    assert e.value.codigo == "IDEMPOTENCY_CONFLICT" and stock(db, pid) == 3
    assert a.consultar_venta(clave)["sale_id"] == primera["sale_id"]
    with pytest.raises(ErrorLAN) as e:
        a.consultar_venta(nueva_clave())
    assert e.value.codigo == "NOT_FOUND"


@tc("ITS_LAN_02")
@pytest.mark.parametrize("solicitud, codigo", [
    ({"clave": "corta"}, "VALIDATION_ERROR"),
    ({"metodo_pago": "Cheque"}, "VALIDATION_ERROR"),
    ({"descuento": 150}, "VALIDATION_ERROR"),
    ({"carrito": []}, "VALIDATION_ERROR"),
    ({"carrito": [{"product_id": 999, "quantity": 1}]}, "VALIDATION_ERROR"),
    ({"cliente_id": 999}, "NOT_FOUND"),
])
def test_solicitudes_invalidas_se_rechazan_sin_escribir(db, servicio, solicitud, codigo):
    pid = producto(db, "P-1", 5)
    a = terminal(servicio)
    datos = {"clave": nueva_clave(), "cliente_id": None, "metodo_pago": "Efectivo", "descuento": 0,
             "carrito": [{"product_id": pid, "quantity": 1}], **solicitud}
    with pytest.raises(ErrorLAN) as e:
        a.registrar_venta(datos["clave"], datos["cliente_id"], datos["metodo_pago"], datos["descuento"],
                          datos["carrito"])
    assert e.value.codigo == codigo
    assert stock(db, pid) == 5 and db.scalar("SELECT COUNT(*) FROM sales") == 0


@tc("ITS_LAN_03", nivel="ITS", modulo="ventas", reqs=["SEG-01", "RNF-01"],
    nombre="El servicio LAN exige sesión y toma el empleado de la sesión")
def test_servicio_exige_sesion(db, servicio):
    """Seguridad mínima del servicio LAN: sin sesión no se puede consultar ni vender, las credenciales
    incorrectas no abren sesión, y el empleado registrado en la venta es el de la sesión (el cliente no
    lo puede elegir). SEG-01.

    Precondiciones: Fixture servicio con los usuarios ventaA y ventaB; producto P-1 con stock 5.
    Pasos:
    - Iniciar sesión con ventaA y una contraseña incorrecta.
    - Con un cliente sin sesión, pedir el inventario y registrar una venta.
    - Con un token inventado, pedir el inventario.
    - Iniciar sesión como ventaB y vender 1 pieza.
    Esperado:
    - La contraseña incorrecta regresa None (sin token).
    - Las peticiones sin sesión o con token inventado responden UNAUTHENTICATED y no cambian el stock.
    - La venta de B queda con employee_id de ventaB.
    """
    pid = producto(db, "P-1", 5)
    anonimo = ClienteLAN(servicio.url)
    assert anonimo.iniciar_sesion("ventaA", "incorrecta") is None
    for accion in (anonimo.inventario, lambda: venta(anonimo, pid)):
        with pytest.raises(ErrorLAN) as e:
            accion()
        assert e.value.codigo == "UNAUTHENTICATED"
    anonimo.token = "inventado"
    with pytest.raises(ErrorLAN) as e:
        anonimo.inventario()
    assert e.value.codigo == "UNAUTHENTICATED" and stock(db, pid) == 5
    b = terminal(servicio, "ventaB", "clave-b")
    r = venta(b, pid)
    assert db.scalar("SELECT e.username FROM sales s JOIN employees e ON e.id=s.employee_id WHERE s.id=?",
                     (r["sale_id"],)) == "ventaB"


@tc("ITS_LAN_03")
def test_sin_servicio_la_terminal_recibe_unavailable():
    c = ClienteLAN("http://127.0.0.1:9", timeout=1)
    with pytest.raises(ErrorLAN) as e:
        c.iniciar_sesion("a", "b")
    assert e.value.codigo == "UNAVAILABLE" and e.value.incierto


@tc("STS_LAN_01", nivel="STS", modulo="ventas", reqs=["RNF-01", "RF-04"],
    nombre="Dos terminales venden a la vez la última pieza: solo una venta se concreta")
def test_dos_terminales_venden_la_ultima_pieza_a_la_vez(db, servicio):
    """Prueba de sistema de concurrencia (VD-09 automatizado): dos terminales envían al mismo tiempo la
    venta de la única pieza de un producto, mientras la terminal principal también intenta venderla
    directo en la base. Solo una venta se confirma; las demás se rechazan por stock y el stock nunca
    queda negativo. También se repite con 8 terminales sobre 5 piezas.

    Precondiciones: Fixture servicio; producto ACEP-ULTIMO-01 con stock 1; terminales A y B con sesión;
      threading.Barrier para soltar las ventas a la vez.
    Pasos:
    - Lanzar en hilos la venta de A, la de B y una venta local con ventas_srv.registrar() en otra conexión.
    - Contar ventas confirmadas y rechazadas; leer stock y movimientos SALIDA.
    - Repetir con un producto de stock 5 y 8 terminales que venden 1 pieza cada una.
    Esperado:
    - Exactamente 1 venta confirmada y 2 rechazos por stock insuficiente; stock final 0; 1 movimiento SALIDA.
    - Con 8 terminales: exactamente 5 ventas confirmadas, 3 rechazos y stock final 0.
    """
    def carrera(pid, terminales, con_local):
        barrera = threading.Barrier(len(terminales) + con_local)
        resultados = []

        def remota(c):
            barrera.wait()
            try:
                venta(c, pid)
                resultados.append("ok")
            except ErrorLAN as e:
                resultados.append(e.codigo)

        def local():
            principal = Database(db.path, load_examples=False)
            barrera.wait()
            try:
                ventas_srv.registrar(principal, None, 1, "Efectivo", 0, [{"product_id": pid, "quantity": 1}])
                resultados.append("ok")
            except ValueError:
                resultados.append("INSUFFICIENT_STOCK")
            finally:
                principal.close()

        hilos = [threading.Thread(target=remota, args=(c,)) for c in terminales]
        if con_local:
            hilos.append(threading.Thread(target=local))
        for h in hilos:
            h.start()
        for h in hilos:
            h.join(timeout=30)
        return resultados

    pid = producto(db, "ACEP-ULTIMO-01", 1)
    a, b = terminal(servicio), terminal(servicio, "ventaB", "clave-b")
    r = carrera(pid, [a, b], con_local=1)
    assert sorted(r) == ["INSUFFICIENT_STOCK", "INSUFFICIENT_STOCK", "ok"]
    assert stock(db, pid) == 0
    assert db.scalar("SELECT COUNT(*) FROM inventory_movements WHERE product_id=? AND movement_type='SALIDA'",
                     (pid,)) == 1

    pid5 = producto(db, "P-5", 5)
    r = carrera(pid5, [terminal(servicio) for _ in range(8)], con_local=0)
    assert r.count("ok") == 5 and r.count("INSUFFICIENT_STOCK") == 3
    assert stock(db, pid5) == 0


@tc("STS_LAN_02", nivel="STS", modulo="interfaz", reqs=["RNF-01"],
    nombre="La pantalla de la terminal de venta muestra el stock nuevo en ≤ 5 s")
def test_pantalla_de_terminal_se_actualiza_sola(db, servicio):
    """Prueba de sistema con la ventana real de la terminal de venta (ui/terminal_lan.py, VD-08
    automatizado): con el inventario a la vista y sin recargar a mano, una venta hecha en la terminal
    principal aparece en la tabla de la terminal en un máximo de 5 segundos (RNF-01). Después se vende
    desde la propia terminal con sus botones.

    Precondiciones: Fixture servicio; producto ACEP-LAN-01 con stock 10. TerminalLAN abierta (ventana
      oculta) con sesión de ventaA; messagebox parcheado.
    Pasos:
    - Esperar a que la tabla de inventario muestre stock 10.
    - Registrar 1 pieza en la terminal principal con ventas_srv.registrar() y medir hasta que la tabla
      muestre 9, solo procesando eventos de Tk.
    - En la terminal, capturar el código, «Agregar al carrito» y «Registrar venta».
    Esperado:
    - La tabla pasa de 10 a 9 en menos de 5 s sin acción del usuario.
    - La venta de la terminal se confirma (ticket en pantalla) y la tabla muestra 8; la base también.
    """
    pid = producto(db, "ACEP-LAN-01", 10)
    try:
        app = TerminalLAN(servicio.url)
    except tk.TclError as e:
        pytest.skip(f"Sin pantalla para Tk: {e}")
    app.withdraw()

    def stock_en_tabla():
        valores = app.inventory_tree.item(str(pid), "values") if app.inventory_tree.exists(str(pid)) else None
        return int(valores[6]) if valores else None

    def esperar(condicion, limite):
        inicio = time.monotonic()
        while time.monotonic() - inicio < limite:
            app.update()
            if condicion():
                return time.monotonic() - inicio
            time.sleep(0.02)
        return None

    try:
        with patch.object(terminal_lan.messagebox, "showinfo"), \
                patch.object(terminal_lan.messagebox, "showerror") as error:
            app.login_view.username_entry.delete(0, tk.END)
            app.login_view.username_entry.insert(0, "ventaA")
            app.login_view.password_entry.insert(0, "clave-a")
            app.login_view.submit()
            assert esperar(lambda: stock_en_tabla() == 10, 5) is not None
            ventas_srv.registrar(db, None, 1, "Efectivo", 0, [{"product_id": pid, "quantity": 1}])
            tardanza = esperar(lambda: stock_en_tabla() == 9, 5)
            assert tardanza is not None and tardanza <= 5
            app.sale_product_code.insert(0, "ACEP-LAN-01")
            app.add_cart_item()
            app.register_sale_ui()
            error.assert_not_called()
            assert "VENTA REGISTRADA" in app.ticket_text.get("1.0", tk.END)
            assert stock_en_tabla() == 8 and stock(db, pid) == 8
    finally:
        app.on_close()
