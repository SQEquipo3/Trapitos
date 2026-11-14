"""Servicio LAN de la terminal principal (#56).

Expone por HTTP/JSON el inventario y el registro de ventas sobre la misma base SQLite
que usa la aplicación de escritorio de esa terminal:

    POST /api/v1/sesion           {usuario, contrasena}              -> {token, empleado}
    GET  /api/v1/inventario                                          -> {productos: [...]}
    POST /api/v1/ventas           {clave, cliente_id, metodo_pago,
                                   descuento, carrito: [{product_id, quantity}]}
    GET  /api/v1/ventas/<clave>                                      -> resultado ya confirmado

Las rutas, salvo /sesion, exigen la cabecera «Authorization: Bearer <token>». El empleado de la
venta sale de la sesión, no de la solicitud. Todas las operaciones se ejecutan en UN solo hilo
trabajador con su propia conexión (SDD 7.2), y cada venta va en una transacción BEGIN IMMEDIATE
con descuento de stock condicionado: de dos ventas de la última pieza solo una se confirma.

La «clave» es de idempotencia: reenviar la misma venta con la misma clave devuelve el resultado
original sin vender otra vez; la misma clave con otro contenido se rechaza (SDD 7.1 y 7.4).
"""

import hashlib
import json
import logging
import secrets
import sqlite3
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from mis_trapitos.data.database import Database
from mis_trapitos.data.repositories import clientes as clientes_repo
from mis_trapitos.data.repositories import empleados as empleados_repo
from mis_trapitos.data.repositories import productos as productos_repo
from mis_trapitos.data.repositories import promociones as promociones_repo
from mis_trapitos.data.repositories import ventas as ventas_repo
from mis_trapitos.lan import API, PUERTO_PREDETERMINADO
from mis_trapitos.services import ventas as ventas_srv
from utils import now_text

log = logging.getLogger(__name__)

DURACION_SESION_S = 12 * 60 * 60
MAX_CUERPO = 64 * 1024


class ErrorServicio(Exception):
    """Error con código lógico estable (SDD 7.1) y estado HTTP."""

    def __init__(self, codigo, mensaje, estado):
        super().__init__(mensaje)
        self.codigo = codigo
        self.mensaje = mensaje
        self.estado = estado


def _validacion(mensaje):
    return ErrorServicio("VALIDATION_ERROR", mensaje, 400)


# ---------------------------------------------------------------- operaciones (hilo trabajador)
def inventario(db):
    """Productos con stock, precio y promoción vigente, para la pantalla de la terminal de venta."""
    productos = []
    for row in productos_repo.listar_inventario(db):
        p = dict(row)
        p["promo"] = promociones_repo.porcentaje_vigente(db, p["id"])
        productos.append(p)
    return {"productos": productos}


def _consolidar(carrito):
    """Suma las cantidades por producto; valida tipos y cantidades positivas."""
    if not isinstance(carrito, list) or not carrito:
        raise _validacion("La venta no tiene productos.")
    cantidades = {}
    for item in carrito:
        try:
            product_id = int(item["product_id"])
            qty = int(item["quantity"])
        except (KeyError, TypeError, ValueError):
            raise _validacion("Partida de carrito no valida.")
        if qty <= 0:
            raise _validacion("La cantidad debe ser mayor a cero.")
        cantidades[product_id] = cantidades.get(product_id, 0) + qty
    return [{"product_id": pid, "quantity": qty} for pid, qty in sorted(cantidades.items())]


def _huella(employee_id, cliente_id, metodo_pago, descuento, carrito):
    contenido = json.dumps([employee_id, cliente_id, metodo_pago, descuento, carrito], sort_keys=True)
    return hashlib.sha256(contenido.encode("utf-8")).hexdigest()


def _resultado(db, sale_id):
    venta = ventas_repo.obtener_por_id(db, sale_id)
    stock = {str(p["product_id"]): productos_repo.obtener_por_id(db, p["product_id"])["stock"]
             for p in ventas_repo.partidas(db, sale_id)}
    return {"sale_id": sale_id, "fecha": venta["sale_datetime"], "subtotal": venta["subtotal"],
            "descuento": venta["discount_amount"], "total": venta["total"],
            "metodo_pago": venta["payment_method"], "stock": stock}


def registrar_venta(db, employee_id, solicitud):
    """Registra la venta de una terminal remota de forma idempotente (una sola transacción)."""
    clave = solicitud.get("clave")
    if not isinstance(clave, str) or not 8 <= len(clave) <= 64:
        raise _validacion("Clave de solicitud no valida.")
    cliente_id = solicitud.get("cliente_id")
    if cliente_id in ("", None):
        cliente_id = None
    else:
        try:
            cliente_id = int(cliente_id)
        except (TypeError, ValueError):
            raise _validacion("ID de cliente no valido.")
    metodo_pago = solicitud.get("metodo_pago")
    try:
        descuento = ventas_srv.parsear_descuento(solicitud.get("descuento"))
    except ValueError as e:
        raise _validacion(str(e))
    carrito = _consolidar(solicitud.get("carrito"))
    huella = _huella(employee_id, cliente_id, metodo_pago, descuento, carrito)

    with db.transaction():
        previa = db.one("SELECT fingerprint, sale_id FROM lan_requests WHERE request_key=?", (clave,))
        if previa is not None:
            if previa["fingerprint"] != huella:
                raise ErrorServicio("IDEMPOTENCY_CONFLICT",
                                    "La clave ya se uso con otra venta.", 409)
            return {**_resultado(db, previa["sale_id"]), "repetida": True}
        if cliente_id is not None and not clientes_repo.existe(db, cliente_id):
            raise ErrorServicio("NOT_FOUND", "Cliente no encontrado.", 404)
        try:
            sale_id, _, _, _ = ventas_srv.registrar(db, cliente_id, employee_id, metodo_pago,
                                                    descuento, carrito)
        except ValueError as e:
            if str(e).startswith("Stock insuficiente"):
                raise ErrorServicio("INSUFFICIENT_STOCK", str(e), 409)
            raise _validacion(str(e))
        db.execute("""INSERT INTO lan_requests(request_key, fingerprint, sale_id, employee_id, created_at)
                      VALUES(?,?,?,?,?)""", (clave, huella, sale_id, employee_id, now_text()))
        return {**_resultado(db, sale_id), "repetida": False}


def consultar_venta(db, employee_id, clave):
    """Resultado ya confirmado de una clave (para recuperar una respuesta perdida)."""
    previa = db.one("SELECT sale_id, employee_id FROM lan_requests WHERE request_key=?", (clave,))
    if previa is None or previa["employee_id"] != employee_id:
        raise ErrorServicio("NOT_FOUND", "No hay una venta confirmada con esa clave.", 404)
    return {**_resultado(db, previa["sale_id"]), "repetida": True}


# ---------------------------------------------------------------------------------- servicio
class ServidorLAN:
    """Servicio HTTP de la terminal principal. `iniciar()` lo deja escuchando en segundo plano."""

    def __init__(self, db_path, host="0.0.0.0", puerto=PUERTO_PREDETERMINADO):
        self.db_path = db_path
        self.host = host
        self.puerto = puerto
        self._sesiones = {}
        self._lock = threading.Lock()
        self._local = threading.local()
        self._trabajador = None
        self._http = None
        self._hilo_http = None

    # -- hilo trabajador: dueño único de su conexión SQLite
    def _abrir_bd(self):
        self._local.db = Database(self.db_path, load_examples=False, wal=True)

    def ejecutar(self, funcion, *args):
        """Ejecuta funcion(db, *args) en el hilo trabajador y espera el resultado."""
        return self._trabajador.submit(lambda: funcion(self._local.db, *args)).result()

    # -- sesiones en memoria
    def iniciar_sesion(self, usuario, contrasena):
        empleado = self.ejecutar(empleados_repo.autenticar, usuario or "", contrasena or "")
        if empleado is None:
            raise ErrorServicio("UNAUTHENTICATED", "Usuario o contraseña incorrectos.", 401)
        token = secrets.token_urlsafe(32)
        datos = {"id": empleado["id"], "name": empleado["name"], "role": empleado["role"]}
        with self._lock:
            self._sesiones[token] = (datos, time.monotonic() + DURACION_SESION_S)
        return {"token": token, "empleado": datos}

    def empleado_de(self, token):
        with self._lock:
            sesion = self._sesiones.get(token or "")
            if sesion is None or sesion[1] < time.monotonic():
                self._sesiones.pop(token or "", None)
                raise ErrorServicio("UNAUTHENTICATED", "Sesión no valida; inicia sesión de nuevo.", 401)
            return sesion[0]

    # -- ciclo de vida
    def iniciar(self):
        self._trabajador = ThreadPoolExecutor(max_workers=1, thread_name_prefix="lan-bd",
                                              initializer=self._abrir_bd)
        self.ejecutar(lambda db: None)          # abre la base ya, para fallar al arrancar y no después
        servidor = self

        class Manejador(_Manejador):
            pass
        Manejador.servidor = servidor
        self._http = ThreadingHTTPServer((self.host, self.puerto), Manejador)
        self._http.daemon_threads = True
        self.puerto = self._http.server_address[1]
        self._hilo_http = threading.Thread(target=self._http.serve_forever, name="lan-http", daemon=True)
        self._hilo_http.start()
        log.info("Servicio LAN escuchando en %s:%s", self.host, self.puerto)
        return self

    def detener(self):
        if self._http is not None:
            self._http.shutdown()
            self._http.server_close()
            self._http = None
        if self._trabajador is not None:
            self._trabajador.submit(lambda: self._local.db.close()).result()
            self._trabajador.shutdown()
            self._trabajador = None

    @property
    def url(self):
        host = "127.0.0.1" if self.host in ("0.0.0.0", "") else self.host
        return f"http://{host}:{self.puerto}"


class _Manejador(BaseHTTPRequestHandler):
    servidor = None          # ServidorLAN; se asigna en una subclase por instancia
    protocol_version = "HTTP/1.1"

    def log_message(self, formato, *args):
        log.debug("%s - %s", self.address_string(), formato % args)

    def _responder(self, estado, cuerpo):
        datos = json.dumps(cuerpo, ensure_ascii=False).encode("utf-8")
        self.send_response(estado)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(datos)))
        self.end_headers()
        self.wfile.write(datos)

    def _leer_json(self):
        largo = int(self.headers.get("Content-Length") or 0)
        if largo > MAX_CUERPO:
            raise _validacion("Solicitud demasiado grande.")
        try:
            cuerpo = json.loads(self.rfile.read(largo) or b"{}")
        except (ValueError, UnicodeDecodeError):
            raise _validacion("JSON no valido.")
        if not isinstance(cuerpo, dict):
            raise _validacion("JSON no valido.")
        return cuerpo

    def _empleado(self):
        encabezado = self.headers.get("Authorization", "")
        token = encabezado[len("Bearer "):] if encabezado.startswith("Bearer ") else ""
        return self.servidor.empleado_de(token)

    def _atender(self, metodo):
        s = self.servidor
        ruta = self.path.split("?", 1)[0].rstrip("/")
        try:
            if metodo == "POST" and ruta == f"{API}/sesion":
                cuerpo = self._leer_json()
                return self._responder(200, s.iniciar_sesion(cuerpo.get("usuario"), cuerpo.get("contrasena")))
            if metodo == "GET" and ruta == f"{API}/inventario":
                self._empleado()
                return self._responder(200, s.ejecutar(inventario))
            if metodo == "POST" and ruta == f"{API}/ventas":
                empleado = self._empleado()
                cuerpo = self._leer_json()
                return self._responder(200, s.ejecutar(registrar_venta, empleado["id"], cuerpo))
            if metodo == "GET" and ruta.startswith(f"{API}/ventas/"):
                empleado = self._empleado()
                clave = ruta[len(f"{API}/ventas/"):]
                return self._responder(200, s.ejecutar(consultar_venta, empleado["id"], clave))
            raise ErrorServicio("NOT_FOUND", "Ruta no encontrada.", 404)
        except ErrorServicio as e:
            self._responder(e.estado, {"codigo": e.codigo, "mensaje": e.mensaje})
        except sqlite3.OperationalError as e:
            correlacion = uuid.uuid4().hex[:12]
            log.warning("BUSY %s: %s", correlacion, e)
            self._responder(503, {"codigo": "BUSY", "correlacion": correlacion,
                                  "mensaje": "La base de datos esta ocupada; intenta de nuevo."})
        except Exception:
            correlacion = uuid.uuid4().hex[:12]
            log.exception("Error interno %s", correlacion)
            self._responder(500, {"codigo": "INTERNAL", "correlacion": correlacion,
                                  "mensaje": "Error interno del servicio."})

    def do_GET(self):
        self._atender("GET")

    def do_POST(self):
        self._atender("POST")
