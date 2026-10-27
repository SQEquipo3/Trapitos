from contextlib import contextmanager
from functools import partial
from itertools import combinations
from pathlib import Path
import os
import subprocess
import sys
import tempfile
import tkinter as tk
from tkinter import font, messagebox, ttk
import unittest
from unittest.mock import patch

from mis_trapitos.data.repositories import empleados as empleados_repo
from mis_trapitos.data.database import Database
from mis_trapitos.data.repositories import productos as productos_repo
from mis_trapitos.ui.app import App
from utils import today_text
from tests.tc import tc


SCREENS = (
    ("Productos", 0, None, "Agregar producto"),
    ("Ventas", 1, None, "Registrar venta"),
    ("Clientes", 2, 0, "Guardar cliente"),
    ("Proveedores", 2, 1, "Guardar proveedor"),
    ("Empleados", 2, 2, "Guardar empleado"),
    ("Promociones", 3, None, "Guardar promoción"),
    ("Devoluciones", 4, None, "Registrar devolución"),
    ("Reportes", 5, None, "Ejecutar reporte"),
    ("Rastreabilidad", 6, None, "Ejecutar pruebas básicas"),
)


def descendants(parent):
    for child in parent.winfo_children():
        yield child
        yield from descendants(child)


def rectangle(widget):
    left, top = widget.winfo_rootx(), widget.winfo_rooty()
    return left, top, left + widget.winfo_width(), top + widget.winfo_height()


def intersection(first, second):
    return (max(first[0], second[0]), max(first[1], second[1]),
            min(first[2], second[2]), min(first[3], second[3]))


def visible_rectangle(widget):
    bounds = rectangle(widget)
    ancestor = widget.master
    while ancestor is not None:
        bounds = intersection(bounds, rectangle(ancestor))
        ancestor = ancestor.master
    return bounds


def set_entry(entry, value):
    entry.delete(0, tk.END)
    entry.insert(0, value)


class LayoutTest(unittest.TestCase):
    def settle(self, app):
        previous = None
        for _ in range(12):
            app.update()
            current = tuple((str(widget), widget.winfo_width(), widget.winfo_height(),
                             widget.winfo_x(), widget.winfo_y())
                            for widget in descendants(app))
            if current == previous:
                return
            previous = current
        self.fail("La distribución no alcanza una geometría estable.")

    @contextmanager
    def application(self, scale, size):
        original_styles = App._configure_styles

        def configure(app):
            app.withdraw()
            app.tk.call("tk", "scaling", scale)
            original_styles(app)

        with tempfile.TemporaryDirectory(prefix="trapitos-layout-") as directory:
            with patch("mis_trapitos.ui.app.Database", side_effect=partial(Database, load_examples=False)), \
                    patch.object(App, "_configure_styles", configure), \
                    patch.object(messagebox, "showerror") as error:
                app = App(db_path=str(Path(directory) / "layout.db"))
                callback_errors = []
                app.report_callback_exception = lambda *args: callback_errors.append(args)
                try:
                    empleados_repo.guardar(app.db, None, "Administrador", "admin", "1234", "Propietario")
                    productos_repo.guardar(app.db, None, (
                        "LAYOUT-01", "Blusa de prueba", "Ropa", "M", "Azul",
                        80, 150, 20, None, today_text(), "Marca", "Temporada", "",
                    ))
                    app.geometry(f"{size[0]}x{size[1]}+20+20")
                    app.deiconify()
                    self.settle(app)
                    self.assertEqual((app.winfo_width(), app.winfo_height()), size)
                    yield app
                    error.assert_not_called()
                    self.assertEqual(callback_errors, [], "Error en un callback de Tkinter.")
                finally:
                    app.update_idletasks()
                    app.on_close()

    def login(self, app):
        set_entry(app.login_view.password_entry, "1234")
        app.login_view.submit_button.invoke()
        self.settle(app)
        self.assertEqual(app.user["username"], "admin")

    def select_screen(self, app, main_index, contact_index):
        app.navigation_buttons[main_index].invoke()
        if contact_index is None:
            notebook = app.main_notebook
        else:
            notebook = app.contactos_ui.notebook
            notebook.select(contact_index)
        self.settle(app)
        return app.nametowidget(notebook.select())

    def assert_visible(self, widget):
        self.assertTrue(widget.winfo_ismapped(), f"Control oculto: {widget}")
        actual, visible = rectangle(widget), visible_rectangle(widget)
        for edge, shown in zip(actual, visible):
            self.assertLessEqual(abs(edge - shown), 2, f"Control recortado: {widget}, {actual}, {visible}")

    def assert_legible(self, widget):
        self.assertGreaterEqual(widget.winfo_height() + 2, widget.winfo_reqheight(), str(widget))
        if isinstance(widget, (ttk.Button, ttk.Label)):
            self.assertGreaterEqual(widget.winfo_width() + 2, widget.winfo_reqwidth(), str(widget))
        if isinstance(widget, (ttk.Entry, ttk.Combobox)):
            field_font = font.Font(root=widget, font=widget.cget("font"))
            self.assertGreaterEqual(widget.winfo_width(), field_font.measure("0000000000"), str(widget))

    def assert_reachable(self, app, widget):
        widget.event_generate("<FocusIn>")
        self.settle(app)
        self.assert_visible(widget)
        self.assert_legible(widget)

    def assert_no_overlaps(self, controls):
        for first, second in combinations(controls, 2):
            left, top, right, bottom = intersection(rectangle(first), rectangle(second))
            self.assertFalse(right - left > 2 and bottom - top > 2,
                             f"Controles solapados: {first} y {second}")

    def assert_table_accessible(self, app, tree):
        rows = [tree.insert("", tk.END, values=tuple(f"Dato {i}" for _ in tree["columns"]))
                for i in range(30)]
        tree.xview_moveto(1)
        tree.yview_moveto(1)
        tree.event_generate("<FocusIn>")
        self.settle(app)
        left, top, right, bottom = visible_rectangle(tree)
        row_height = int(ttk.Style(tree).lookup("Treeview", "rowheight"))
        tree_font = font.Font(root=tree, font=ttk.Style(tree).lookup("Treeview", "font"))
        self.assertGreaterEqual(row_height, tree_font.metrics("linespace") + 6)
        self.assertGreaterEqual(right - left, 150, "Tabla sin ancho utilizable.")
        self.assertGreaterEqual(bottom - top, row_height * 3, "Tabla sin tres filas visibles.")
        self.assertAlmostEqual(tree.yview()[1], 1, places=3)
        self.assertAlmostEqual(tree.xview()[1], 1, places=3)
        last_cell = tree.bbox(rows[-1], tree["columns"][-1])
        self.assertTrue(last_cell, "La última fila no es alcanzable.")
        x, y, width, height = last_cell
        self.assertLess(x, tree.winfo_width())
        self.assertGreater(x + width, 0, "La última columna no es alcanzable.")
        self.assertLess(y, tree.winfo_height())
        self.assertGreater(y + height, 0)
        for scrollbar in tree.master.winfo_children():
            if isinstance(scrollbar, ttk.Scrollbar):
                scrollbar.event_generate("<FocusIn>")
                self.settle(app)
                self.assert_visible(scrollbar)
        tree.delete(*rows)

    def run_scenario(self, method, scale, size):
        program = (
            "import sys; sys.path.insert(0, 'tests'); "
            "from test_ui_layout import LayoutTest; "
            "getattr(LayoutTest(), sys.argv[1])(float(sys.argv[2]), "
            "(int(sys.argv[3]), int(sys.argv[4])))"
        )
        args = [sys.executable, "-X", "utf8", "-B", "-c", program,
                method, str(scale), str(size[0]), str(size[1])]
        with subprocess.Popen(args, cwd=Path(__file__).resolve().parents[1],
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                              text=True, encoding="utf-8") as process:
            try:
                output, _ = process.communicate(timeout=90)
            except subprocess.TimeoutExpired:
                if os.name == "nt":
                    subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                   check=False)
                else:
                    process.kill()
                output, _ = process.communicate()
                self.fail(f"El escenario excedió 90 segundos.\n{output}")
        self.assertEqual(process.returncode, 0, output)

    @tc("STS_UI_01", nivel="STS", modulo="interfaz", reqs=["RF-06", "RF-01"],
        nombre="Nueve pantallas accesibles en dos tamaños y escalas")
    def test_nueve_pantallas_accesibles_en_dos_tamanos_y_escalas(self):
        """Todas las pantallas se pueden abrir y sus controles son visibles en distintas
        resoluciones.

        Precondiciones: Aplicación completa.
        Pasos:
        - Recorrer las nueve pantallas en dos tamaños y escalas
        Esperado:
        - Sin controles recortados ni errores
        """
        for scale in (96 / 72, 144 / 72):
            for size in ((1060, 680), (1360, 840)):
                with self.subTest(scale=scale, size=size):
                    self.run_scenario("screen_scenario", scale, size)

    def screen_scenario(self, scale, size):
        with self.application(scale, size) as app:
            for widget in descendants(app.login_view):
                if isinstance(widget, (ttk.Button, ttk.Entry, ttk.Label)):
                    self.assert_visible(widget)
                    self.assert_legible(widget)
            self.login(app)
            logout = next(widget for widget in descendants(app)
                          if isinstance(widget, ttk.Button) and widget.cget("text") == "Cerrar sesión")
            for widget in (*app.navigation_buttons, logout):
                self.assert_visible(widget)
                self.assert_legible(widget)
            for name, main_index, contact_index, primary_action in SCREENS:
                with self.subTest(screen=name):
                    page = self.select_screen(app, main_index, contact_index)
                    controls = [widget for widget in descendants(page)
                                if isinstance(widget, (ttk.Button, ttk.Entry, ttk.Combobox, ttk.Label))]
                    self.assertIn(primary_action, [widget.cget("text") for widget in controls
                                                  if isinstance(widget, ttk.Button)])
                    self.assert_no_overlaps(controls)
                    for widget in controls:
                        self.assert_reachable(app, widget)
                    tables = [widget for widget in descendants(page) if isinstance(widget, ttk.Treeview)]
                    self.assertTrue(tables, f"Pantalla sin tabla: {name}")
                    for tree in tables:
                        self.assert_table_accessible(app, tree)

    @tc("STS_UI_02", nivel="STS", modulo="interfaz", reqs=["RF-06"],
        nombre="Redimensionar y navegar conserva captura, selección y carrito")
    def test_redimensionar_y_navegar_conserva_captura_seleccion_y_carrito(self):
        """El estado de captura sobrevive a cambios de tamaño y navegación.

        Precondiciones: Carrito con productos.
        Pasos:
        - Redimensionar la ventana
        - Cambiar de pantalla y volver
        Esperado:
        - Captura, selección y carrito intactos
        """
        for scale in (96 / 72, 144 / 72):
            with self.subTest(scale=scale):
                self.run_scenario("resize_scenario", scale, (1360, 840))

    def resize_scenario(self, scale, size):
        with self.application(scale, size) as app:
            self.login(app)
            products = app.productos_ui
            selected = products.products_tree.get_children()[0]
            products.products_tree.selection_set(selected)
            products.load_product_selected()
            self.settle(app)
            set_entry(products.p_name, "Edición pendiente")
            set_entry(app.contactos_ui.c_name, "Cliente sin guardar")
            set_entry(app.promociones_ui.pr_discount, "17")
            app.ventas_ui.servicio.agregar_producto("LAYOUT-01", 2)
            app.ventas_ui.refresh_cart()
            for size in ((1060, 680), (1360, 840), (1060, 680)):
                app.geometry(f"{size[0]}x{size[1]}+20+20")
                self.settle(app)
                for _, main_index, contact_index, _ in SCREENS:
                    self.select_screen(app, main_index, contact_index)
                self.assertEqual(products.p_name.get(), "Edición pendiente")
                self.assertEqual(products.products_tree.selection(), (selected,))
                self.assertEqual(app.contactos_ui.c_name.get(), "Cliente sin guardar")
                self.assertEqual(app.promociones_ui.pr_discount.get(), "17")
                self.assertEqual(app.ventas_ui.servicio.cart[0]["quantity"], 2)
            app.show_login()
            self.settle(app)
            self.assert_visible(app.login_view.submit_button)
            self.login(app)
            self.assertEqual(app.ventas_ui.servicio.cart, [])
            self.assertIsNone(app.productos_ui.selected_product_id)
            self.assertEqual(app.db.scalar("SELECT stock FROM products WHERE code='LAYOUT-01'"), 20)
            self.select_screen(app, 6, None)


if __name__ == "__main__":
    unittest.main()
