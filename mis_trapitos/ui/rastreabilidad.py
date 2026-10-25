# mis_trapitos/ui/rastreabilidad.py

import tkinter as tk

from tkinter import messagebox, ttk

from mis_trapitos.ui.base import (
    ActionBar,
    ScrollablePage,
    make_tree,
)

from mis_trapitos.data.repositories import clientes as clientes_repo
from mis_trapitos.data.repositories import empleados as empleados_repo
from mis_trapitos.data.repositories import productos as productos_repo
from mis_trapitos.services.ventas import ServicioVentas
from config import APP_VERSION, PAYMENT_METHODS

CONFIG_ITEMS = [
    ("CI-01", "Codigo fuente principal", "main.py", "Controlado"),
    ("CI-02", "Base de datos local", "mis_trapitos.db", "Controlado"),
    ("CI-03", "Version de aplicacion", APP_VERSION, "Controlado"),
    ("CI-04", "Operacion sin Internet", "SQLite local y Tkinter", "Controlado"),
    ("CI-05", "Usuario inicial", "admin / 1234", "Controlado"),
    ("CI-06", "Modulo de productos", "mis_trapitos/ui/productos.py", "Controlado"),
    ("CI-07", "Modulo de contactos y usuarios", "mis_trapitos/ui/contactos.py", "Controlado"),
    ("CI-08", "Modulo de ventas", "mis_trapitos/ui/ventas.py", "Controlado"),
]

TRACEABILITY = [
    ("RF-01", "Registrar productos con categoria, descripcion, precio, talla y color", "Productos",
"Guardar producto y verificar en inventario"),
    ("RF-02", "Manejar variaciones de talla y color con existencias", "Productos", "Registrar mismo producto con otra talla o color"),
    ("RF-03", "Agregar productos y actualizar cantidades de inventario", "Productos", "Modificar stock y revisar movimiento"),
    ("RF-04", "Actualizar inventario automaticamente al registrar venta", "Ventas", "Vender producto y comprobar disminucion"),
    ("RF-05", "Registrar movimientos de inventario", "Inventario", "Consultar movimientos de entrada, salida, ajuste, devolucion y cancelacion"),
    ("RF-06", "Registrar ventas con productos, cantidades y metodo de pago", "Ventas", "Registrar venta con carrito"),
    ("RF-07", "Registrar pagos en efectivo, tarjeta y transferencia", "Ventas", "Seleccionar metodo de pago"),
    ("RF-08", "Aplicar descuentos a ventas", "Ventas", "Capturar descuento general"),
    ("RF-09", "Registrar promociones con porcentaje y duracion", "Promociones", "Crear promocion vigente"),
    ("RF-10", "Aplicar descuentos automaticos segun condiciones", "Promociones y Ventas", "Venta aplica promocion vigente"),
    ("RF-11", "Registrar clientes con nombre, direccion, correo y telefono", "Clientes", "Guardar cliente"),
    ("RF-12", "Almacenar y consultar historial de compras de cada cliente", "Clientes y Reportes", "Consultar historial"),
    ("RF-13", "Registrar proveedores e informacion de contacto", "Proveedores", "Guardar proveedor"),
    ("RF-14", "Relacionar proveedor con productos que suministra", "Productos y Proveedores", "Consultar productos por proveedor"),
    ("RF-15", "Consultar productos disponibles e inventario por categoria", "Reportes", "Reporte por categoria"),
    ("RF-16", "Consultar productos en oferta y descuentos", "Reportes", "Reporte de productos en oferta"),
    ("RF-17", "Consultar metodos de pago mas utilizados", "Reportes", "Reporte de metodos de pago"),
    ("RF-18", "Consultar productos mas vendidos en el ultimo mes", "Reportes", "Reporte mensual"),
    ("RF-19", "Consultar ventas realizadas en los ultimos tres dias", "Reportes", "Reporte de ultimos tres dias"),
    ("RF-20", "Consultar productos de un proveedor especifico", "Reportes", "Parametro de proveedor"),
    ("RF-21", "Consultar productos comprados mas de una vez por un cliente", "Reportes", "Parametro de cliente"),
    ("RF-22", "Consultar productos vendidos por categoria en el ultimo mes", "Reportes", "Parametro de categoria"),
    ("RF-23", "Consultar productos con precio superior a cierto valor y existencias", "Reportes", "Parametro de precio"),
    ("RF-24", "Consultar producto con mayor descuento vigente", "Reportes", "Promociones vigentes"),
    ("RF-25", "Consultar compras por ciudad o region del cliente", "Reportes", "Agrupar por region"),
    ("RF-26", "Consultar productos no vendidos en los ultimos tres meses", "Reportes", "Reporte sin ventas recientes"),
    ("RNF-01", "Reflejar en tiempo real la disminucion del inventario", "Ventas e Inventario", "Validar stock inmediatamente despues de vender"),
]

class RastreabilidadUI(ScrollablePage):

    def __init__(self, parent, db, refresh_products):
        super().__init__(parent)

        self.db = db
        self.refresh_products = refresh_products

        self.make_traceability_tab()

    def make_traceability_tab(self):
        tab = self

        actions = ActionBar(tab.body)
        actions.pack(fill="x", pady=(0, 18))
        actions.add(
            "Ejecutar pruebas básicas",
            self.run_basic_tests
        )

        upper = ttk.LabelFrame(
            tab.body,
            text="Administración de configuración",
            padding=(0, 12, 0, 0)
        )
        upper.pack(fill="x")

        config_tree = make_tree(
            upper,
            ("id", "elemento", "valor", "estado"),
            height=4
        )

        for item in CONFIG_ITEMS:
            config_tree.insert("", tk.END, values=item)

        lower = ttk.LabelFrame(
            tab.body,
            text="Matriz de rastreabilidad",
            padding=(0, 12, 0, 0)
        )
        lower.pack(fill="both", expand=True, pady=(20, 0))

        trace_tree = make_tree(
            lower,
            ("id", "requerimiento", "modulo", "prueba"),
            height=6
        )

        for item in TRACEABILITY:
            trace_tree.insert("", tk.END, values=item)

    def run_basic_tests(self):
        try:
            product = productos_repo.con_mas_stock(self.db)
            employee = empleados_repo.primero(self.db)
            customer = clientes_repo.primero(self.db)

            if not product or not employee:
                raise ValueError(
                    "Faltan productos o empleados para probar."
                )

            initial_stock = int(product["stock"])

            if initial_stock < 1:
                raise ValueError(
                    "No hay stock suficiente para la prueba."
                )

            servicio = ServicioVentas(self.db)
            servicio.agregar_producto(product["code"], 1)

            sale_id = servicio.registrar_venta(
                customer["id"] if customer else None,
                employee["id"],
                PAYMENT_METHODS[0],
                0
            ).sale_id

            after = int(productos_repo.obtener_por_id(self.db, product["id"])["stock"])

            movement = productos_repo.movimiento_de_venta(self.db, sale_id, "SALIDA")

            if after != initial_stock - 1 or not movement:
                raise ValueError(
                    "La prueba de inventario no pasó."
                )

            self.refresh_products()

            messagebox.showinfo(
                "Pruebas",
                f"Pruebas correctas. Venta de prueba: {sale_id}. "
                f"Stock {initial_stock} -> {after}."
            )

        except Exception as e:
            messagebox.showerror("Pruebas", str(e))