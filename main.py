"""Punto de entrada de Mis trapitos.

    python main.py                          aplicación local (como siempre)
    python main.py --servidor [--puerto N]  terminal principal: aplicación + servicio LAN
    python main.py --terminal http://IP:N   terminal de venta conectada a la principal (#56)
"""

import argparse

from config import DB_NAME
from mis_trapitos.lan import PUERTO_PREDETERMINADO


def main(argv=None):
    parser = argparse.ArgumentParser(description="Mis trapitos")
    modo = parser.add_mutually_exclusive_group()
    modo.add_argument("--servidor", action="store_true",
                      help="abrir la aplicación y atender a las terminales de venta de la LAN")
    modo.add_argument("--terminal", metavar="URL",
                      help="terminal de venta; URL del servicio, p. ej. http://192.168.1.10:8765")
    parser.add_argument("--host", default="0.0.0.0", help="interfaz donde escucha el servicio (--servidor)")
    parser.add_argument("--puerto", type=int, default=PUERTO_PREDETERMINADO, help="puerto del servicio (--servidor)")
    args = parser.parse_args(argv)

    if args.terminal:
        from mis_trapitos.ui.terminal_lan import TerminalLAN
        TerminalLAN(args.terminal).mainloop()
        return

    from mis_trapitos.ui.app import App
    servicio = None
    if args.servidor:
        from mis_trapitos.data.database import Database
        from mis_trapitos.lan.servidor import ServidorLAN
        Database(DB_NAME).close()   # crea esquema y ejemplos antes de que el servicio abra la base
        servicio = ServidorLAN(DB_NAME, host=args.host, puerto=args.puerto).iniciar()
        print(f"Servicio LAN activo en el puerto {servicio.puerto}. "
              f"Terminales: python main.py --terminal http://<IP de este equipo>:{servicio.puerto}")
    try:
        App().mainloop()
    finally:
        if servicio is not None:
            servicio.detener()


if __name__ == "__main__":
    main()
