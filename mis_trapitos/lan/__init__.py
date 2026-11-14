"""Servicio LAN mínimo (#56): una terminal principal guarda los datos y las demás venden a través de ella.

* servidor.py: servicio HTTP/JSON que corre en la terminal principal junto a la base SQLite.
* cliente.py: cliente que usan las terminales de venta (ui/terminal_lan.py).

Alcance: inventario y ventas (RNF-01, VD-08/09 del SAD). Pendiente del SDD sección 7: TLS,
permisos por operación en el servicio y generación de recuperación tras restaurar respaldos.
"""

API = "/api/v1"
PUERTO_PREDETERMINADO = 8765
