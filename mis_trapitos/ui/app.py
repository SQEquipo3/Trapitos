""" Interfaz y orquestador"""

import functools
import tkinter as tk
from tkinter import ttk

from config import APP_TITLE, APP_VERSION, DB_NAME
from mis_trapitos.data.database import Database
from mis_trapitos.data.repositories import empleados as empleados_repo
from mis_trapitos.ui.base import handle_page_event
from mis_trapitos.ui.contactos import ContactosUI
from mis_trapitos.ui.devoluciones import DevolucionesUI
from mis_trapitos.ui.login import Login
from mis_trapitos.ui.productos import ProductosUI
from mis_trapitos.ui.promociones import PromocionesUI
from mis_trapitos.ui.ventas import VentasUI
from mis_trapitos.ui.styles import UI_COLORS, configure_styles
from mis_trapitos.ui.reportes import ReportesUI
from mis_trapitos.ui.rastreabilidad import RastreabilidadUI


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
            authenticate=functools.partial(empleados_repo.autenticar, self.db),
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
        self.contactos_ui = ContactosUI(nb, self.db, get_user=lambda: self.user)
        nb.add(self.contactos_ui, text="Contactos y usuarios")
        self.promociones_ui = PromocionesUI(nb, self.db)
        nb.add(self.promociones_ui, text="Promociones")
        self.devoluciones_ui = DevolucionesUI(
            nb, self.db, on_inventario_actualizado=self.refresh_products
        )
        nb.add(self.devoluciones_ui, text="Devoluciones y cancelaciones")
        self.reportes_ui = ReportesUI(nb, self.db)
        nb.add(self.reportes_ui, text="Reportes")
        self.rastreabilidad_ui = RastreabilidadUI(
            nb,
            self.db,
            self.refresh_products
        )
        nb.add(self.rastreabilidad_ui, text="Rastreabilidad")
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

    
    
