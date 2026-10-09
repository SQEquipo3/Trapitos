import csv
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from config import APP_TITLE, APP_VERSION, DB_NAME, PAYMENT_METHODS
from mis_trapitos.data.database import Database
from mis_trapitos.ui.base import (
    ActionBar, FormGrid, ScrollablePage, configure_tree_columns,
    handle_page_event, make_tree,
)
from mis_trapitos.ui.contactos import ContactosUI
from mis_trapitos.ui.devoluciones import DevolucionesUI
from mis_trapitos.ui.login import Login
from mis_trapitos.ui.productos import ProductosUI
from mis_trapitos.ui.promociones import PromocionesUI
from mis_trapitos.ui.ventas import VentasUI, ServicioVentas
from mis_trapitos.ui.styles import UI_COLORS, configure_styles



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

REPORTS = [
    "Inventario general actualizado",
    "Productos con stock bajo",
    "Ventas diarias, semanales y mensuales",
    "Ventas por producto",
    "Ventas por metodo de pago",
    "Ventas por empleado",
    "Productos mas vendidos",
    "Productos menos vendidos",
    "Entradas de mercancia",
    "Clientes frecuentes",
    "Resumen de utilidades",
    "Productos devueltos o cancelados",
    "Productos disponibles por categoria",
    "Productos en oferta",
    "Metodos de pago mas utilizados",
    "Productos mas vendidos ultimo mes",
    "Ventas ultimos tres dias",
    "Productos de proveedor especifico",
    "Productos comprados mas de una vez por cliente",
    "Productos vendidos por categoria ultimo mes",
    "Productos con precio superior y existencias",
    "Producto con mayor descuento vigente",
    "Compras por ciudad o region",
    "Productos no vendidos ultimos tres meses",
]


class App(tk.Tk):
    def __init__(self, db_path=None):
        super().__init__()
        self._configure_styles()
        self.title(f"{APP_TITLE} v{APP_VERSION}")
        self.geometry(f"{min(1360, self.winfo_screenwidth()-60)}x{min(840, self.winfo_screenheight()-90)}")
        self.minsize(1060, 680)
        self.configure(bg=UI_COLORS["background"])
        try:
            self.db = Database(DB_NAME if db_path is None else db_path)
        except Exception:
            self.destroy()
            raise
        self.user = None
        self.login_view = None
        self.productos_ui = None
        self.contactos_ui = None
        self.ventas_ui = None
        self.main_notebook = None
        self.navigation_buttons = []
        self.module_title = tk.StringVar(self, value="Productos")
        self.promociones_ui = None
        self.devoluciones_ui = None
        self.bind("<MouseWheel>", handle_page_event, add="+")
        self.bind("<FocusIn>", handle_page_event, add="+")
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.show_login()

    def _configure_styles(self):
        configure_styles(self)

    @staticmethod
    def _wrap_label(label, width):
        width = max(200, width)
        if int(label.cget("wraplength") or 0) != width:
            label.configure(wraplength=width)

    def on_close(self):
        try:
            self.db.close()
        finally:
            self.destroy()

    def show_login(self):
        self.clear_window()
        self.user = None
        self.login_view = Login(
            self,
            authenticate=self.db.authenticate,
            on_authenticated=self._on_authenticated,
        )
        self.login_view.pack(expand=True)
        self.login_view.password_entry.focus_set()

    def _on_authenticated(self, user):
        self.user = user
        self.show_main()

    def show_main(self):
        if self.user is None:
            self.show_login()
            return
        self.clear_window()
        shell = ttk.Frame(self, style="Workspace.TFrame")
        shell.pack(fill="both", expand=True)
        sidebar_width = int(204 * min(1.25, self.winfo_fpixels("1i") / 96))
        sidebar = ttk.Frame(shell, style="Sidebar.TFrame", width=sidebar_width, padding=(14, 16))
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)
        ttk.Label(sidebar, text="MIS TRAPITOS", style="SidebarBrand.TLabel").pack(anchor="w")
        ttk.Label(sidebar, text="Gestión de tienda", style="SidebarMuted.TLabel").pack(anchor="w", pady=(2, 14))
        ttk.Separator(sidebar, orient="horizontal", style="Sidebar.TSeparator").pack(fill="x", pady=(0, 12))
        ttk.Label(sidebar, text="MÓDULOS", style="SidebarSection.TLabel").pack(anchor="w", pady=(0, 8))
        navigation = ttk.Frame(sidebar, style="Sidebar.TFrame")
        navigation.pack(fill="x")
        modules = (
            ("Productos", "Productos"),
            ("Ventas", "Ventas"),
            ("Contactos", "Contactos y usuarios"),
            ("Promociones", "Promociones"),
            ("Devoluciones", "Devoluciones y cancelaciones"),
            ("Reportes", "Reportes"),
            ("Rastreabilidad", "Rastreabilidad"),
        )
        self.navigation_buttons = []
        for index, (label, _) in enumerate(modules):
            button = ttk.Button(
                navigation,
                text=label,
                style="SidebarActive.TButton" if index == 0 else "Sidebar.TButton",
                command=lambda tab_index=index: self._select_module(tab_index),
            )
            button.pack(fill="x", pady=1)
            self.navigation_buttons.append(button)
        sidebar_footer = ttk.Frame(sidebar, style="Sidebar.TFrame")
        sidebar_footer.pack(side="bottom", fill="x", pady=(12, 0))
        ttk.Separator(sidebar_footer, orient="horizontal", style="Sidebar.TSeparator").pack(fill="x", pady=(0, 10))
        ttk.Label(sidebar_footer, text="SESIÓN ACTIVA", style="SidebarSection.TLabel").pack(anchor="w")
        ttk.Label(sidebar_footer, text=self.user["name"], style="SidebarUser.TLabel", wraplength=sidebar_width-32).pack(anchor="w", pady=(5, 0))
        ttk.Label(sidebar_footer, text=self.user["role"], style="SidebarMuted.TLabel", wraplength=sidebar_width-32).pack(anchor="w")
        ttk.Button(
            sidebar_footer,
            text="Cerrar sesión",
            style="SidebarLogout.TButton",
            command=self.show_login,
        ).pack(fill="x", pady=(8, 0))

        workspace = ttk.Frame(shell, style="Workspace.TFrame")
        workspace.pack(side="left", fill="both", expand=True)
        workspace_header = ttk.Frame(workspace, style="WorkspaceHeader.TFrame", padding=(24, 15))
        workspace_header.pack(fill="x")
        heading = ttk.Label(workspace_header, textvariable=self.module_title, style="WorkspaceTitle.TLabel")
        heading.pack(anchor="w")
        workspace_header.bind("<Configure>", lambda event: self._wrap_label(heading, event.width - 48))
        ttk.Label(workspace_header, text="Administración de tienda", style="WorkspaceMuted.TLabel").pack(anchor="w", pady=(2, 0))
        content = ttk.Frame(workspace, style="Content.TFrame", padding=(24, 20, 24, 20))
        content.pack(fill="both", expand=True)
        nb = ttk.Notebook(content, style="Hidden.TNotebook")
        nb.pack(fill="both", expand=True)
        self.main_notebook = nb
        self.make_products_tab(nb)
        self.ventas_ui = VentasUI(nb, self.db, self.user, on_venta_registrada=self.refresh_products)
        nb.add(self.ventas_ui, text="Ventas")
        self.contactos_ui = ContactosUI(nb, self.db)
        nb.add(self.contactos_ui, text="Contactos y usuarios")
        self.promociones_ui = PromocionesUI(nb, self.db)
        nb.add(self.promociones_ui, text="Promociones")
        self.devoluciones_ui = DevolucionesUI(
            nb, self.db, on_inventario_actualizado=self.refresh_products
        )
        nb.add(self.devoluciones_ui, text="Devoluciones y cancelaciones")
        self.make_reports_tab(nb)
        self.make_traceability_tab(nb)
        nb.bind("<<NotebookTabChanged>>", self._on_module_changed)
        self._select_module(0)

    def _select_module(self, tab_index):
        if self.main_notebook is None:
            return
        self.main_notebook.select(tab_index)
        self._on_module_changed()

    def _on_module_changed(self, event=None):
        if self.main_notebook is None:
            return
        selected = self.main_notebook.index(self.main_notebook.select())
        titles = (
            "Productos",
            "Ventas",
            "Contactos y usuarios",
            "Promociones",
            "Devoluciones y cancelaciones",
            "Reportes",
            "Rastreabilidad",
        )
        if 0 <= selected < len(titles):
            self.module_title.set(titles[selected])
        for index, button in enumerate(self.navigation_buttons):
            button.configure(style="SidebarActive.TButton" if index == selected else "Sidebar.TButton")

    def clear_window(self):
        for child in self.winfo_children():
            child.destroy()
        self.productos_ui = None
        self.contactos_ui = None
        self.main_notebook = None
        self.navigation_buttons = []
        self.login_view = None
        self.ventas_ui = None
        self.promociones_ui = None
        self.devoluciones_ui = None

    def make_products_tab(self, nb):
        self.productos_ui = ProductosUI(nb, self.db)
        nb.add(self.productos_ui, text="Productos")

    def refresh_products(self):
        """Actualiza productos tras una venta, devolucion o cancelacion."""
        if self.productos_ui is not None:
            self.productos_ui.actualizar_inventario()

    def make_reports_tab(self, nb):
        tab = ScrollablePage(nb)
        nb.add(tab, text="Reportes")
        controls = ttk.LabelFrame(tab.body, text="Consulta de reportes", padding=(0, 12))
        controls.pack(fill="x")
        fields = FormGrid(controls, columns=2, min_column_width=290)
        fields.pack(fill="x")
        self.report_combo = fields.add_combo("Reporte", REPORTS)
        self.report_combo.set(REPORTS[0])
        self.report_param = fields.add_field("Parámetro")
        self.report_hint = ttk.Label(controls, text="El parámetro se utiliza para filtrar por categoría, proveedor, cliente, precio o stock bajo.", style="Muted.TLabel", wraplength=650)
        self.report_hint.pack(fill="x", pady=(0, 14))
        controls.bind("<Configure>", lambda event: self._wrap_label(self.report_hint, event.width))
        actions = ActionBar(controls)
        actions.pack(fill="x")
        actions.add("Ejecutar reporte", self.run_report, "Accent.TButton")
        actions.add("Exportar CSV", self.export_report_csv)
        table = ttk.LabelFrame(tab.body, text="Resultados", padding=(0, 12, 0, 0))
        table.pack(fill="both", expand=True, pady=(16, 0))
        self.report_tree = make_tree(table, ("resultado",), height=8)
        self.last_report_rows = []
        self.run_report()

    def run_report(self):
        try:
            rows = self.db.report(self.report_combo.get(), self.report_param.get())
            self.last_report_rows = rows
            for item in self.report_tree.get_children():
                self.report_tree.delete(item)
            if not rows:
                configure_tree_columns(self.report_tree, ("mensaje",))
                self.report_tree.insert("", tk.END, values=("Sin resultados",))
                return
            columns = list(rows[0].keys())
            configure_tree_columns(self.report_tree, columns)
            for row in rows:
                self.report_tree.insert("", tk.END, values=[row[col] for col in columns])
        except Exception as e:
            messagebox.showerror("Reporte", str(e))

    def export_report_csv(self):
        rows = self.last_report_rows
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")])
        if not path:
            return
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            if rows:
                writer.writerow(rows[0].keys())
                for row in rows:
                    writer.writerow([row[key] for key in row.keys()])
        messagebox.showinfo("Exportar", f"Reporte exportado en:\n{path}")

    def make_traceability_tab(self, nb):
        tab = ScrollablePage(nb)
        nb.add(tab, text="Rastreabilidad")
        actions = ActionBar(tab.body)
        actions.pack(fill="x", pady=(0, 18))
        actions.add("Ejecutar pruebas básicas", self.run_basic_tests)
        upper = ttk.LabelFrame(tab.body, text="Administración de configuración", padding=(0, 12, 0, 0))
        upper.pack(fill="x")
        config_tree = make_tree(upper, ("id", "elemento", "valor", "estado"), height=4)
        for item in CONFIG_ITEMS:
            config_tree.insert("", tk.END, values=item)
        lower = ttk.LabelFrame(tab.body, text="Matriz de rastreabilidad", padding=(0, 12, 0, 0))
        lower.pack(fill="both", expand=True, pady=(20, 0))
        trace_tree = make_tree(lower, ("id", "requerimiento", "modulo", "prueba"), height=6)
        for item in TRACEABILITY:
            trace_tree.insert("", tk.END, values=item)

    def run_basic_tests(self):
        try:
            product = self.db.one("SELECT * FROM products ORDER BY stock DESC LIMIT 1")
            employee = self.db.one("SELECT * FROM employees ORDER BY id LIMIT 1")
            customer = self.db.one("SELECT * FROM customers ORDER BY id LIMIT 1")
            if not product or not employee:
                raise ValueError("Faltan productos o empleados para probar.")
            initial_stock = int(product["stock"])
            if initial_stock < 1:
                raise ValueError("No hay stock suficiente para la prueba.")
            servicio = ServicioVentas(self.db)
            servicio.agregar_producto(product["code"], 1)
            sale_id = servicio.registrar_venta(customer["id"] if customer else None, employee["id"], PAYMENT_METHODS[0], 0).sale_id
            after = self.db.scalar("SELECT stock FROM products WHERE id=?", (product["id"],))
            movement = self.db.one("SELECT id FROM inventory_movements WHERE related_sale_id=? AND movement_type='SALIDA'", (sale_id,))
            if after != initial_stock - 1 or not movement:
                raise ValueError("La prueba de inventario no paso.")
            self.refresh_products()
            messagebox.showinfo("Pruebas", f"Pruebas correctas. Venta de prueba: {sale_id}. Stock {initial_stock} -> {after}.")
        except Exception as e:
            messagebox.showerror("Pruebas", str(e))
