"""Regresiones con widgets reales y datos desechables.

Ejecutar desde la raiz: python -m unittest discover -s tests -v
Se necesita Tk con una sesion grafica; las ventanas permanecen ocultas.
"""

import csv
from pathlib import Path
import tempfile
import tkinter as tk
from tkinter import messagebox
import unittest
from unittest.mock import patch

from PIL import Image

from mis_trapitos.data.database import Database
from mis_trapitos.ui import app as application
from mis_trapitos.ui import productos as ui_productos
from mis_trapitos.data.repositories import empleados as empleados_repo


def set_entry(entry, value):
    entry.delete(0, tk.END)
    entry.insert(0, str(value))


def fill_product(ui, **overrides):
    values = {
        "p_code": "BLUSA-M-AZUL",
        "p_name": "Blusa",
        "p_category": "Ropa",
        "p_size": "M",
        "p_color": "Azul",
        "p_purchase": "80.50",
        "p_sale": "150.75",
        "p_stock": "10",
        "p_supplier": "",
        "p_entry": "2026-09-10",
        "p_brand": "Marca de prueba",
        "p_season": "Otono",
        "p_image": "",
    }
    values.update(overrides)
    for name, value in values.items():
        set_entry(getattr(ui, name), value)


def inventory_rows(ui):
    columns = ui.products_tree["columns"]
    return {
        row["codigo"]: row
        for item in ui.products_tree.get_children()
        for row in [dict(zip(columns, ui.products_tree.item(item, "values")))]
    }


def select_product(ui, code):
    for item in ui.products_tree.get_children():
        if ui.products_tree.set(item, "codigo") == code:
            ui.products_tree.selection_set(item)
            ui.load_product_selected()
            return
    raise AssertionError(f"No se encontro {code} en el inventario")


class TemporaryInventoryTest(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory(prefix="trapitos-tests-")
        self.addCleanup(directory.cleanup)
        self.directory = Path(directory.name)
        self.start_patch(patch("mis_trapitos.data.database.seed_examples"))
        self.info = self.start_patch(patch.object(messagebox, "showinfo"))
        self.error = self.start_patch(patch.object(messagebox, "showerror"))
        self.warning = self.start_patch(patch.object(messagebox, "showwarning"))

    def start_patch(self, patcher):
        value = patcher.start()
        self.addCleanup(patcher.stop)
        return value


class ProductosUITest(TemporaryInventoryTest):
    def setUp(self):
        super().setUp()
        self.db = Database(str(self.directory / "inventario.db"))
        self.addCleanup(self.db.close)
        self.root = tk.Tk()
        self.root.withdraw()
        self.addCleanup(self.root.destroy)
        self.ui = ui_productos.ProductosUI(self.root, self.db)

    def add_product(self, **values):
        fill_product(self.ui, **values)
        self.ui.add_product_ui()
        self.error.assert_not_called()
        return self.ui.selected_product_id

    def test_alta_y_edicion_respetan_existencias_de_cada_variante(self):
        first_id = self.add_product()
        self.ui.clear_product_form()
        second_id = self.add_product(
            p_code="BLUSA-L-ROJA", p_size="L", p_color="Roja", p_stock="6"
        )
        self.assertNotEqual(first_id, second_id)
        self.assertEqual(len(inventory_rows(self.ui)), 2)

        select_product(self.ui, "BLUSA-M-AZUL")
        self.assertEqual(self.ui.p_size.get(), "M")
        self.assertEqual(self.ui.p_color.get(), "Azul")
        set_entry(self.ui.p_name, "Blusa de algodon")
        set_entry(self.ui.p_stock, 12)
        self.ui.edit_product_ui()

        rows = inventory_rows(self.ui)
        self.assertEqual(rows["BLUSA-M-AZUL"]["producto"], "Blusa de algodon")
        self.assertEqual(int(rows["BLUSA-M-AZUL"]["stock"]), 12)
        self.assertEqual(int(rows["BLUSA-L-ROJA"]["stock"]), 6)
        second = self.db.one("SELECT * FROM products WHERE id=?", (second_id,))
        self.assertEqual((second["name"], second["size"], second["color"]),
                         ("Blusa", "L", "Roja"))
        adjustment = self.db.one(
            "SELECT quantity FROM inventory_movements "
            "WHERE product_id=? AND movement_type='AJUSTE'", (first_id,)
        )
        self.assertEqual(adjustment["quantity"], 2)
        self.error.assert_not_called()

    def test_validaciones_no_modifican_producto_ni_movimientos(self):
        product_id = self.add_product()
        original = dict(self.db.one("SELECT * FROM products WHERE id=?", (product_id,)))
        movements = self.db.scalar("SELECT COUNT(*) FROM inventory_movements")
        invalid_values = [
            {field: " "} for field in
            ("p_code", "p_name", "p_category", "p_size", "p_color")
        ] + [
            {"p_purchase": "-1"}, {"p_sale": "-1"}, {"p_stock": "-1"},
            {"p_purchase": "abc"}, {"p_stock": "1.5"}, {"p_supplier": "9999"},
        ]
        for values in invalid_values:
            with self.subTest(values=values):
                self.error.reset_mock()
                fill_product(self.ui, **values)
                self.ui.edit_product_ui()
                self.error.assert_called_once()
                self.assertEqual(
                    dict(self.db.one("SELECT * FROM products WHERE id=?", (product_id,))),
                    original,
                )
                self.assertEqual(self.db.scalar("SELECT COUNT(*) FROM inventory_movements"),
                                 movements)

    def test_codigo_duplicado_no_crea_otra_variante(self):
        self.add_product()
        fill_product(self.ui, p_size="L", p_color="Roja")
        self.ui.add_product_ui()
        self.error.assert_called_once()
        self.assertEqual(self.db.scalar("SELECT COUNT(*) FROM products"), 1)
        self.assertEqual(self.db.scalar("SELECT COUNT(*) FROM inventory_movements"), 1)
        row = inventory_rows(self.ui)["BLUSA-M-AZUL"]
        self.assertEqual((row["talla"], row["color"]), ("M", "Azul"))

    def test_edicion_sin_seleccion_no_guarda_producto(self):
        fill_product(self.ui)
        self.ui.edit_product_ui()
        self.error.assert_called_once()
        self.assertEqual(self.db.scalar("SELECT COUNT(*) FROM products"), 0)

    def test_exportacion_csv_conserva_variantes_y_texto(self):
        self.add_product(p_name="Blusa, edición especial")
        self.add_product(p_code="BLUSA-L-ROJA", p_size="L", p_color="Roja", p_stock=6)
        output = self.directory / "inventario.csv"
        with patch.object(ui_productos.filedialog, "asksaveasfilename", return_value=str(output)):
            self.ui.export_inventory_csv()
        with output.open(newline="", encoding="utf-8") as stream:
            rows = {row["codigo"]: row for row in csv.DictReader(stream)}
        self.assertEqual(set(rows), {"BLUSA-M-AZUL", "BLUSA-L-ROJA"})
        self.assertEqual(rows["BLUSA-M-AZUL"]["producto"], "Blusa, edición especial")
        self.assertEqual(rows["BLUSA-L-ROJA"]["stock"], "6")
        self.assertEqual(rows["BLUSA-L-ROJA"]["talla"], "L")

    def test_imagen_se_copia_guarda_y_recupera_al_seleccionar(self):
        source = self.directory / "blusa azul.png"
        Image.new("RGB", (320, 400), "blue").save(source)
        destination = self.directory / "imagenes"
        fill_product(self.ui)
        with patch.object(ui_productos, "IMAGE_DIR", str(destination)), \
                patch.object(ui_productos.filedialog, "askopenfilename", return_value=str(source)):
            self.ui.choose_product_image()
        stored = Path(self.ui.p_image.get())
        self.assertEqual(stored.parent, destination)
        self.assertTrue(stored.is_file())
        self.assertNotEqual(stored, source)
        self.assertIsNotNone(self.ui.product_photo_ref)
        with Image.open(stored) as saved:
            self.assertEqual(saved.size, (320, 400))
            self.assertEqual(saved.getpixel((0, 0)), (0, 0, 255))
        self.ui.add_product_ui()
        product_id = self.ui.selected_product_id
        self.assertEqual(self.db.scalar("SELECT image_path FROM products WHERE id=?", (product_id,)),
                         str(stored))
        self.ui.clear_product_form()
        self.assertIsNone(self.ui.product_photo_ref)
        select_product(self.ui, "BLUSA-M-AZUL")
        self.assertEqual(self.ui.p_image.get(), str(stored))
        self.assertIsNotNone(self.ui.product_photo_ref)
        self.error.assert_not_called()

    def test_imagen_inexistente_muestra_estado_sin_romper_formulario(self):
        self.add_product(p_image=str(self.directory / "inexistente.png"))
        self.assertIsNone(self.ui.product_photo_ref)
        self.assertEqual(self.ui.product_image_label.cget("text"), "No se pudo mostrar la foto")
        self.assertEqual(len(inventory_rows(self.ui)), 1)

    def test_otro_componente_puede_recargar_el_inventario(self):
        product_id = self.add_product()
        self.db.execute("UPDATE products SET stock=4 WHERE id=?", (product_id,))
        self.ui.actualizar_inventario()
        self.assertEqual(int(inventory_rows(self.ui)["BLUSA-M-AZUL"]["stock"]), 4)
        self.ui.destroy()
        self.ui = ui_productos.ProductosUI(self.root, self.db)
        self.assertEqual(int(inventory_rows(self.ui)["BLUSA-M-AZUL"]["stock"]), 4)
        self.assertIsNone(self.ui.selected_product_id)

    def test_refrescar_sin_cambio_externo_conserva_edicion_pendiente(self):
        self.add_product()
        select_product(self.ui, "BLUSA-M-AZUL")
        self.root.update()
        set_entry(self.ui.p_name, "Nombre pendiente")
        set_entry(self.ui.p_stock, 14)
        self.ui.actualizar_inventario()
        self.root.update()
        self.assertEqual(self.ui.p_name.get(), "Nombre pendiente")
        self.assertEqual(self.ui.p_stock.get(), "14")
        self.assertEqual(int(inventory_rows(self.ui)["BLUSA-M-AZUL"]["stock"]), 10)

    def test_limpiar_no_restaura_seleccion_por_eventos_pendientes(self):
        self.add_product()
        select_product(self.ui, "BLUSA-M-AZUL")
        self.ui.clear_product_form()
        self.root.update()
        self.assertIsNone(self.ui.selected_product_id)
        self.assertEqual(self.ui.p_code.get(), "")
        self.assertEqual(self.ui.products_tree.selection(), ())
        self.assertIsNone(self.ui.product_photo_ref)


class ProductosAppIntegrationTest(TemporaryInventoryTest):
    def setUp(self):
        super().setUp()
        self.app = application.App(db_path=str(self.directory / "app.db"))
        self.app.withdraw()
        self.addCleanup(self.app.on_close)
        self.db = self.app.db
        employee_id = empleados_repo.guardar(self.db, None, "Prueba", "prueba", "prueba", "Administrador")
        set_entry(self.app.login_view.username_entry, "prueba")
        set_entry(self.app.login_view.password_entry, "prueba")
        self.app.login_view.submit()
        self.assertEqual(self.app.user["id"], employee_id)
        self.ui = self.app.productos_ui

    def assert_stock(self, code, expected):
        self.assertEqual(self.db.scalar("SELECT stock FROM products WHERE code=?", (code,)), expected)
        self.assertEqual(int(inventory_rows(self.ui)[code]["stock"]), expected)

    def test_venta_devolucion_y_cancelacion_actualizan_inventario_sin_recarga_manual(self):
        fill_product(self.ui)
        self.ui.add_product_ui()
        product_id = self.ui.selected_product_id
        fill_product(self.ui, p_code="BLUSA-L-ROJA", p_size="L", p_color="Roja", p_stock=6)
        self.ui.add_product_ui()
        select_product(self.ui, "BLUSA-M-AZUL")
        self.app.update()
        set_entry(self.ui.p_name, "Blusa de algodon")

        set_entry(self.app.ventas_ui.sale_product_code, "BLUSA-M-AZUL")
        set_entry(self.app.ventas_ui.sale_quantity, 3)
        self.app.ventas_ui.add_cart_item()
        self.app.ventas_ui.register_sale_ui()
        self.error.assert_not_called()
        sale_id = self.db.scalar("SELECT MAX(id) FROM sales")
        self.assertIsNotNone(sale_id)
        self.assert_stock("BLUSA-M-AZUL", 7)
        self.assert_stock("BLUSA-L-ROJA", 6)
        self.assertEqual(self.app.ventas_ui.servicio.cart, [])
        self.app.update()
        self.assertEqual(self.ui.p_stock.get(), "7")
        self.assertEqual(self.ui.p_name.get(), "Blusa de algodon")
        self.ui.edit_product_ui()
        self.assert_stock("BLUSA-M-AZUL", 7)
        self.assertEqual(self.db.scalar("SELECT name FROM products WHERE id=?", (product_id,)),
                         "Blusa de algodon")

        set_entry(self.app.devoluciones_ui.r_sale, sale_id)
        set_entry(self.app.devoluciones_ui.r_product, product_id)
        set_entry(self.app.devoluciones_ui.r_quantity, 1)
        set_entry(self.app.devoluciones_ui.r_reason, "Cambio de talla")
        self.app.devoluciones_ui.return_item_ui()
        self.error.assert_not_called()
        self.assert_stock("BLUSA-M-AZUL", 8)
        self.assert_stock("BLUSA-L-ROJA", 6)
        self.assertEqual(self.ui.p_stock.get(), "8")
        self.assertEqual(len(self.app.devoluciones_ui.returns_tree.get_children()), 1)

        set_entry(self.app.devoluciones_ui.cancel_sale_entry, sale_id)
        set_entry(self.app.devoluciones_ui.cancel_reason, "Cancelacion de prueba")
        self.app.devoluciones_ui.cancel_sale_ui()
        self.error.assert_not_called()
        self.assert_stock("BLUSA-M-AZUL", 10)
        self.assert_stock("BLUSA-L-ROJA", 6)
        self.assertEqual(self.ui.p_stock.get(), "10")
        self.assertEqual(self.db.scalar("SELECT status FROM sales WHERE id=?", (sale_id,)), "CANCELADA")
        self.assertEqual(len(self.app.devoluciones_ui.cancellations_tree.get_children()), 1)

    def test_reabrir_sesion_recrea_modulo_y_conserva_inventario(self):
        fill_product(self.ui)
        self.ui.add_product_ui()
        old_ui = self.ui
        self.app.show_login()
        self.assertIsNone(self.app.user)
        set_entry(self.app.login_view.username_entry, "prueba")
        set_entry(self.app.login_view.password_entry, "prueba")
        self.app.login_view.submit()
        self.ui = self.app.productos_ui
        self.assertIsNot(self.ui, old_ui)
        self.assertIsNone(self.ui.selected_product_id)
        self.assert_stock("BLUSA-M-AZUL", 10)
        self.error.assert_not_called()


if __name__ == "__main__":
    unittest.main()
