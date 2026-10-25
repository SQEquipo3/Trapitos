from pathlib import Path
import tempfile
import tkinter as tk
from tkinter import messagebox
import unittest
from unittest.mock import Mock, patch

from config import PAYMENT_METHODS
from mis_trapitos.data.database import Database
from utils import date_offset, today_text
from mis_trapitos.ui.app import App
from mis_trapitos.ui.devoluciones import DevolucionesUI
from mis_trapitos.ui.promociones import PromocionesUI
from mis_trapitos.services.ventas import ServicioVentas
from mis_trapitos.services import ventas as ventas_srv
from mis_trapitos.data.repositories import empleados as empleados_repo
from mis_trapitos.data.repositories import productos as productos_repo
from mis_trapitos.data.repositories import promociones as promociones_repo


def set_entry(entry, value):
    entry.delete(0, tk.END)
    entry.insert(0, str(value))


def add_product(db, code="BLUSA-M", stock=10):
    return productos_repo.guardar(db, None, (
        code, "Blusa", "Ropa", "M", "Azul", 80, 200, stock,
        None, today_text(), "Marca", "Temporada", "",
    ))


def fill_promotion(ui, product_id, discount=20):
    for entry, value in (
        (ui.pr_product, product_id), (ui.pr_discount, discount),
        (ui.pr_start, date_offset(-1)), (ui.pr_end, date_offset(30)),
    ):
        set_entry(entry, value)


def select_promotion(ui, promotion_id):
    for item in ui.promotions_tree.get_children():
        if int(ui.promotions_tree.set(item, "id")) == promotion_id:
            ui.promotions_tree.selection_set(item)
            ui.load_promotion_selected()
            return
    raise AssertionError(f"No se encontro la promocion {promotion_id}")


def database_state(db):
    tables = ("products", "promotions", "sales", "sale_items", "returns", "cancellations", "inventory_movements")
    return {table: [tuple(row) for row in db.query(f"SELECT * FROM {table} ORDER BY id")] for table in tables}


class TemporaryWorkflowTest(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory(prefix="trapitos-workflows-")
        self.addCleanup(directory.cleanup)
        self.path = str(Path(directory.name) / "test.db")
        self.start_patch(patch("mis_trapitos.data.database.seed_examples"))
        self.info = self.start_patch(patch.object(messagebox, "showinfo"))
        self.error = self.start_patch(patch.object(messagebox, "showerror"))

    def start_patch(self, patcher):
        value = patcher.start()
        self.addCleanup(patcher.stop)
        return value


class ModuleWidgetTest(TemporaryWorkflowTest):
    def setUp(self):
        super().setUp()
        self.db = Database(self.path)
        self.addCleanup(self.db.close)
        self.root = tk.Tk()
        self.root.withdraw()
        self.addCleanup(self.root.destroy)
        self.employee_id = empleados_repo.guardar(self.db, None, "Ventas", "ventas", "1234", "Ventas")
        self.product_id = add_product(self.db)


class PromocionesUITest(ModuleWidgetTest):
    def setUp(self):
        super().setUp()
        self.ui = PromocionesUI(self.root, self.db)

    def test_alta_edicion_limpieza_y_descuento_aplicado_en_venta(self):
        fill_promotion(self.ui, self.product_id)
        self.ui.save_promotion_ui()
        self.error.assert_not_called()
        promotion_id = self.ui.selected_promotion_id
        self.assertIsNotNone(promotion_id)
        self.assertEqual(len(self.ui.promotions_tree.get_children()), 1)
        self.ui.clear_promotion_form()
        select_promotion(self.ui, promotion_id)
        self.root.update()
        self.assertEqual(self.ui.pr_product.get(), str(self.product_id))
        self.assertEqual(float(self.ui.pr_discount.get()), 20)
        set_entry(self.ui.pr_discount, 25)
        self.ui.save_promotion_ui()
        self.assertEqual(self.ui.selected_promotion_id, promotion_id)
        self.assertEqual(self.db.scalar("SELECT COUNT(*) FROM promotions"), 1)
        self.assertEqual(self.db.scalar("SELECT discount_percent FROM promotions WHERE id=?", (promotion_id,)), 25)
        self.ui.clear_promotion_form()
        self.assertIsNone(self.ui.selected_promotion_id)
        self.assertEqual(self.ui.pr_product.get(), "")
        self.assertEqual(self.ui.pr_discount.get(), "")
        self.assertEqual(self.ui.pr_start.get(), today_text())
        self.assertEqual(self.ui.pr_end.get(), date_offset(30))
        sale = ServicioVentas(self.db)
        sale.agregar_producto("BLUSA-M", 2)
        result = sale.registrar_venta(None, self.employee_id, PAYMENT_METHODS[0], 10)
        self.assertAlmostEqual(result.subtotal, 300)
        self.assertAlmostEqual(result.descuento, 30)
        self.assertAlmostEqual(result.total, 270)
        line = self.db.one("SELECT * FROM sale_items WHERE sale_id=?", (result.sale_id,))
        self.assertEqual(line["promo_discount_percent"], 25)
        self.assertAlmostEqual(line["line_total"], 300)
        self.assertEqual(self.db.scalar("SELECT stock FROM products WHERE id=?", (self.product_id,)), 8)
        self.error.assert_not_called()

    def test_datos_invalidos_no_crean_ni_modifican_promociones(self):
        invalid_values = (("", 20), ("abc", 20), (99999, 20), (self.product_id, -1), (self.product_id, 101), (self.product_id, "abc"))
        for editing in (False, True):
            if editing:
                fill_promotion(self.ui, self.product_id)
                self.ui.save_promotion_ui()
            original = database_state(self.db)
            for product_id, discount in invalid_values:
                with self.subTest(editing=editing, product_id=product_id, discount=discount):
                    self.error.reset_mock()
                    fill_promotion(self.ui, product_id, discount)
                    self.ui.save_promotion_ui()
                    self.error.assert_called_once()
                    self.assertEqual(database_state(self.db), original)


class DevolucionesUITest(ModuleWidgetTest):
    def setUp(self):
        super().setUp()
        self.sale_id = ventas_srv.registrar(self.db, None, self.employee_id, PAYMENT_METHODS[0], 0, [
            {"product_id": self.product_id, "quantity": 5},
        ])[0]
        self.observed_stocks = []
        self.updated = Mock(side_effect=lambda: self.observed_stocks.append(self.stock()))
        self.ui = DevolucionesUI(self.root, self.db, on_inventario_actualizado=self.updated)

    def stock(self):
        return self.db.scalar("SELECT stock FROM products WHERE id=?", (self.product_id,))

    def fill_return(self, sale_id=None, product_id=None, quantity=1):
        for entry, value in (
            (self.ui.r_sale, self.sale_id if sale_id is None else sale_id),
            (self.ui.r_product, self.product_id if product_id is None else product_id),
            (self.ui.r_quantity, quantity), (self.ui.r_reason, "Cambio de talla"),
        ):
            set_entry(entry, value)

    def test_devoluciones_parciales_y_cancelacion_reponen_solo_lo_pendiente(self):
        self.assertEqual(self.stock(), 5)
        self.updated.assert_not_called()
        self.fill_return(quantity=2)
        self.ui.return_item_ui()
        self.assertEqual(self.stock(), 7)
        self.assertEqual(len(self.ui.returns_tree.get_children()), 1)
        self.fill_return(quantity=1)
        self.ui.return_item_ui()
        self.assertEqual(self.stock(), 8)
        self.assertEqual(len(self.ui.returns_tree.get_children()), 2)
        set_entry(self.ui.cancel_sale_entry, self.sale_id)
        set_entry(self.ui.cancel_reason, "Cancelacion del resto")
        self.ui.cancel_sale_ui()
        self.assertEqual(self.stock(), 10)
        self.assertEqual(self.db.scalar("SELECT status FROM sales WHERE id=?", (self.sale_id,)), "CANCELADA")
        self.assertEqual(len(self.ui.cancellations_tree.get_children()), 1)
        self.assertEqual(self.db.scalar("SELECT SUM(quantity) FROM inventory_movements WHERE related_sale_id=? AND movement_type='DEVOLUCION'", (self.sale_id,)), 3)
        self.assertEqual(self.db.scalar("SELECT SUM(quantity) FROM inventory_movements WHERE related_sale_id=? AND movement_type='CANCELACION'", (self.sale_id,)), 2)
        self.assertEqual(self.observed_stocks, [7, 8, 10])
        self.assertEqual(self.updated.call_count, 3)
        self.error.assert_not_called()
        original = database_state(self.db)
        self.updated.reset_mock()
        self.ui.cancel_sale_ui()
        self.error.assert_called_once()
        self.error.reset_mock()
        self.fill_return(quantity=1)
        self.ui.return_item_ui()
        self.error.assert_called_once()
        self.updated.assert_not_called()
        self.assertEqual(database_state(self.db), original)

    def test_devoluciones_invalidas_no_alteran_datos_ni_notifican_inventario(self):
        unsold_id = add_product(self.db, "OTRA-L")
        original = database_state(self.db)
        invalid_values = (
            ("abc", self.product_id, 1), (99999, self.product_id, 1),
            (self.sale_id, "abc", 1), (self.sale_id, unsold_id, 1),
            (self.sale_id, 99999, 1), (self.sale_id, self.product_id, "abc"),
            (self.sale_id, self.product_id, 0), (self.sale_id, self.product_id, -1),
            (self.sale_id, self.product_id, 6),
        )
        for sale_id, product_id, quantity in invalid_values:
            with self.subTest(sale_id=sale_id, product_id=product_id, quantity=quantity):
                self.error.reset_mock()
                self.fill_return(sale_id, product_id, quantity)
                self.ui.return_item_ui()
                self.error.assert_called_once()
                self.updated.assert_not_called()
                self.assertEqual(database_state(self.db), original)
                self.assertEqual(len(self.ui.returns_tree.get_children()), 0)

    def test_cancelaciones_invalidas_no_alteran_datos_ni_notifican_inventario(self):
        original = database_state(self.db)
        for sale_id in ("", "abc", 99999):
            with self.subTest(sale_id=sale_id):
                self.error.reset_mock()
                set_entry(self.ui.cancel_sale_entry, sale_id)
                set_entry(self.ui.cancel_reason, "Cancelacion")
                self.ui.cancel_sale_ui()
                self.error.assert_called_once()
                self.updated.assert_not_called()
                self.assertEqual(database_state(self.db), original)
                self.assertEqual(len(self.ui.cancellations_tree.get_children()), 0)


class PromocionesSessionTest(TemporaryWorkflowTest):
    def test_reabrir_sesion_conserva_promociones_y_reinicia_seleccion(self):
        app = App(db_path=self.path)
        app.withdraw()
        self.addCleanup(app.on_close)
        empleados_repo.guardar(app.db, None, "Administrador", "admin", "1234", "Administrador")

        def login():
            set_entry(app.login_view.username_entry, "admin")
            set_entry(app.login_view.password_entry, "1234")
            app.login_view.submit()

        login()
        product_id = add_product(app.db)
        fill_promotion(app.promociones_ui, product_id, 15)
        app.promociones_ui.save_promotion_ui()
        promotion_id = app.promociones_ui.selected_promotion_id
        select_promotion(app.promociones_ui, promotion_id)
        app.update()
        old_promotions = app.promociones_ui
        old_returns = app.devoluciones_ui
        app.show_login()
        self.assertIsNone(app.promociones_ui)
        self.assertIsNone(app.devoluciones_ui)
        login()
        self.assertIsNot(app.promociones_ui, old_promotions)
        self.assertIsNot(app.devoluciones_ui, old_returns)
        self.assertIs(app.promociones_ui.db, app.db)
        self.assertIs(app.devoluciones_ui.db, app.db)
        self.assertIsNone(app.promociones_ui.selected_promotion_id)
        self.assertEqual(app.promociones_ui.pr_product.get(), "")
        self.assertEqual(app.promociones_ui.promotions_tree.selection(), ())
        self.assertEqual(len(app.promociones_ui.promotions_tree.get_children()), 1)
        select_promotion(app.promociones_ui, promotion_id)
        self.assertEqual(float(app.promociones_ui.pr_discount.get()), 15)
        self.assertEqual(promociones_repo.porcentaje_vigente(app.db, product_id), 15)
        self.error.assert_not_called()


if __name__ == "__main__":
    unittest.main()
