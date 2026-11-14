"""Cliente del servicio LAN que usan las terminales de venta (#56). Solo biblioteca estándar."""

import json
import urllib.error
import urllib.request
import uuid

from mis_trapitos.lan import API


class ErrorLAN(Exception):
    """Respuesta de error del servicio (código lógico del SDD 7.1) o falta de conexión."""

    def __init__(self, codigo, mensaje):
        super().__init__(mensaje)
        self.codigo = codigo
        self.mensaje = mensaje

    @property
    def incierto(self):
        """True si no se sabe si la venta se guardó: hay que reintentar con la MISMA clave."""
        return self.codigo in ("UNAVAILABLE", "BUSY", "INTERNAL")


def nueva_clave():
    return uuid.uuid4().hex


class ClienteLAN:
    def __init__(self, url, timeout=5):
        self.url = url.rstrip("/")
        self.timeout = timeout
        self.token = None
        self.empleado = None

    def _pedir(self, metodo, ruta, cuerpo=None):
        datos = None if cuerpo is None else json.dumps(cuerpo).encode("utf-8")
        solicitud = urllib.request.Request(f"{self.url}{API}{ruta}", data=datos, method=metodo)
        solicitud.add_header("Content-Type", "application/json")
        if self.token:
            solicitud.add_header("Authorization", f"Bearer {self.token}")
        try:
            with urllib.request.urlopen(solicitud, timeout=self.timeout) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            try:
                error = json.loads(e.read())
            except ValueError:
                error = {}
            raise ErrorLAN(error.get("codigo", "INTERNAL"), error.get("mensaje", f"Error HTTP {e.code}."))
        except (urllib.error.URLError, OSError) as e:
            raise ErrorLAN("UNAVAILABLE", f"Sin conexión con el servicio de la terminal principal ({e}).")

    def iniciar_sesion(self, usuario, contrasena):
        """Empleado (dict con id, name, role) o None si las credenciales no son válidas."""
        try:
            r = self._pedir("POST", "/sesion", {"usuario": usuario, "contrasena": contrasena})
        except ErrorLAN as e:
            if e.codigo == "UNAUTHENTICATED":
                return None
            raise
        self.token = r["token"]
        self.empleado = r["empleado"]
        return self.empleado

    def inventario(self):
        return self._pedir("GET", "/inventario")["productos"]

    def registrar_venta(self, clave, cliente_id, metodo_pago, descuento, carrito):
        return self._pedir("POST", "/ventas", {
            "clave": clave, "cliente_id": cliente_id, "metodo_pago": metodo_pago,
            "descuento": descuento, "carrito": carrito,
        })

    def consultar_venta(self, clave):
        return self._pedir("GET", f"/ventas/{clave}")
