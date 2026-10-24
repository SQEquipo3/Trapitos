import importlib.util
from pathlib import Path
import runpy
import sqlite3
import tempfile
import tkinter as tk
from tkinter import messagebox
import unittest
from unittest.mock import Mock, patch

from mis_trapitos.data.database import Database
from mis_trapitos.ui import app as application
from mis_trapitos.ui.login import Login


def set_entry(entry, value):
    entry.delete(0, tk.END)
    entry.insert(0, value)


class LoginTest(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory(prefix="trapitos-login-")
        self.addCleanup(directory.cleanup)
        with patch("mis_trapitos.data.database.seed_examples"):
            self.db = Database(str(Path(directory.name) / "login.db"))
        self.addCleanup(self.db.close)
        self.employee_id = self.db.save_employee(
            None, "Administrador", "admin", "1234", "Administrador"
        )
        self.root = tk.Tk()
        self.root.withdraw()
        self.addCleanup(self.root.destroy)
        self.authenticated = Mock()
        self.login = Login(
            self.root, authenticate=self.db.authenticate,
            on_authenticated=self.authenticated,
        )
        self.login.pack(fill="both", expand=True)
        patcher = patch.object(messagebox, "showerror")
        self.error = patcher.start()
        self.addCleanup(patcher.stop)

    def fill_credentials(self, username="admin", password="1234"):
        set_entry(self.login.username_entry, username)
        set_entry(self.login.password_entry, password)

    def test_credenciales_validas_entregan_usuario_autenticado(self):
        self.fill_credentials(" admin ", " 1234 ")
        self.login.submit()
        self.authenticated.assert_called_once()
        user = self.authenticated.call_args.args[0]
        self.assertEqual(user["id"], self.employee_id)
        self.assertEqual(user["username"], "admin")
        self.assertEqual(user["role"], "Administrador")
        self.error.assert_not_called()

    def test_credenciales_invalidas_permanecen_en_login(self):
        for username, password in (("admin", "incorrecta"), ("desconocido", "1234"), ("", "")):
            with self.subTest(username=username, password=password):
                self.error.reset_mock()
                self.fill_credentials(username, password)
                self.login.submit()
                self.authenticated.assert_not_called()
                self.error.assert_called_once()
                self.assertIs(self.error.call_args.kwargs["parent"], self.login)
                self.assertTrue(self.login.winfo_exists())
        self.fill_credentials()
        self.login.submit()
        self.authenticated.assert_called_once()

    def test_enter_en_contrasena_autentica_una_sola_vez(self):
        self.fill_credentials()
        self.root.geometry("480x360+-10000+-10000")
        self.root.deiconify()
        self.root.update()
        self.login.password_entry.focus_force()
        self.root.update()
        self.login.password_entry.event_generate("<Return>", when="tail")
        self.root.update()
        self.root.withdraw()
        self.authenticated.assert_called_once()
        self.error.assert_not_called()


class SessionTest(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory(prefix="trapitos-session-")
        self.addCleanup(directory.cleanup)
        self.path = str(Path(directory.name) / "app.db")
        with patch("mis_trapitos.data.database.seed_examples"):
            self.app = application.App(db_path=self.path)
        self.app.withdraw()
        self.addCleanup(self.close_app)
        self.db = self.app.db
        self.db.save_employee(None, "Administrador", "admin", "1234", "Administrador")
        self.db.save_employee(None, "Ventas", "ventas", "5678", "Ventas")

    def close_app(self):
        if self.app is not None:
            self.app.on_close()
            self.app = None

    def login(self, username="admin", password="1234"):
        set_entry(self.app.login_view.username_entry, username)
        set_entry(self.app.login_view.password_entry, password)
        self.app.login_view.submit()

    def test_login_y_modulos_comparten_conexion_y_raiz(self):
        self.assertIsNone(self.app.user)
        self.assertIs(self.app.login_view.winfo_toplevel(), self.app)
        with patch.object(application, "Database", side_effect=AssertionError("Conexion adicional")):
            self.login()
        self.assertEqual(self.app.user["username"], "admin")
        self.assertEqual(len(self.app.main_notebook.tabs()), 7)
        for module in (
            self.app.productos_ui, self.app.contactos_ui, self.app.ventas_ui,
            self.app.promociones_ui, self.app.devoluciones_ui,
        ):
            self.assertIs(module.db, self.db)
            self.assertIs(module.winfo_toplevel(), self.app)
        self.assertEqual(self.app.ventas_ui.user["id"], self.app.user["id"])

    def test_cerrar_y_reabrir_sesion_limpia_estado_y_conserva_inventario(self):
        self.login()
        product_id = self.db.save_product(None, (
            "PRUEBA-M", "Blusa", "Ropa", "M", "Azul", 80, 150, 10,
            None, "2026-10-07", "Marca", "Otono", "",
        ))
        self.app.refresh_products()
        self.app.ventas_ui.servicio.agregar_producto("PRUEBA-M", 2)
        old_products = self.app.productos_ui
        old_sales = self.app.ventas_ui
        old_promotions = self.app.promociones_ui
        old_returns = self.app.devoluciones_ui
        self.app.show_login()
        self.assertIsNone(self.app.user)
        self.assertIsNone(self.app.productos_ui)
        self.assertIsNone(self.app.contactos_ui)
        self.assertIsNone(self.app.ventas_ui)
        self.assertIsNone(self.app.promociones_ui)
        self.assertIsNone(self.app.devoluciones_ui)
        self.assertFalse(old_products.winfo_exists())
        self.assertFalse(old_sales.winfo_exists())
        self.assertFalse(old_promotions.winfo_exists())
        self.assertFalse(old_returns.winfo_exists())
        with patch.object(application, "Database", side_effect=AssertionError("Conexion adicional")):
            self.login("ventas", "5678")
        self.assertEqual(self.app.user["username"], "ventas")
        self.assertEqual(self.app.ventas_ui.user["username"], "ventas")
        self.assertIsNot(self.app.productos_ui, old_products)
        self.assertIsNot(self.app.ventas_ui, old_sales)
        self.assertIsNot(self.app.promociones_ui, old_promotions)
        self.assertIsNot(self.app.devoluciones_ui, old_returns)
        self.assertEqual(self.app.ventas_ui.servicio.cart, [])
        self.assertIsNone(self.app.productos_ui.selected_product_id)
        self.assertIs(self.app.db, self.db)
        self.assertEqual(self.db.scalar("SELECT stock FROM products WHERE id=?", (product_id,)), 10)
        self.assertEqual(len(self.app.productos_ui.products_tree.get_children()), 1)

    def test_cerrar_aplicacion_libera_la_conexion(self):
        with patch.object(self.db, "close", wraps=self.db.close) as close:
            self.close_app()
        close.assert_called_once()
        with self.assertRaises(sqlite3.ProgrammingError):
            self.db.scalar("SELECT 1")


class StartupTest(unittest.TestCase):
    def setUp(self):
        self.path = Path(__file__).resolve().parents[1] / "main.py"

    def test_importar_main_no_abre_ventana_conexion_ni_bucle(self):
        spec = importlib.util.spec_from_file_location("trapitos_main_import_test", self.path)
        module = importlib.util.module_from_spec(spec)
        with patch.object(application, "App") as app_class, \
                patch.object(tk, "Tk") as root_class, \
                patch.object(sqlite3, "connect") as connect:
            spec.loader.exec_module(module)
        app_class.assert_not_called()
        root_class.assert_not_called()
        connect.assert_not_called()
        self.assertTrue(callable(module.main))

    def test_ejecutar_main_arranca_una_aplicacion_y_un_bucle(self):
        with patch.object(application, "App") as app_class:
            runpy.run_path(str(self.path), run_name="__main__")
        app_class.assert_called_once_with()
        app_class.return_value.mainloop.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
