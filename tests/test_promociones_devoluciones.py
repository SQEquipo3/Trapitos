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
from tests.tc import tc


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

    @tc("STS_PRM_01", nivel="STS", modulo="ventas", reqs=["RF-09", "RF-10"],
        nombre="Promociones: alta, edición y descuento aplicado en venta")
    def test_alta_edicion_limpieza_y_descuento_aplicado_en_venta(self):
        """Probar la pantalla de Promociones, PromocionesUI de mis_trapitos/ui/promociones.py, y que la
        promoción capturada ahí se aplique en una venta real. Métodos de la pantalla:
        save_promotion_ui() (alta o edición según selected_promotion_id), load_promotion_selected() y
        clear_promotion_form(). La venta se hace con ServicioVentas.agregar_producto() y
        registrar_venta() de mis_trapitos/services/ventas.py. RF-09, RF-10.

        Precondiciones: Ventana Tk real pero oculta (root.withdraw()); en CI corre bajo Xvfb. Base
          SQLite temporal sin datos de ejemplo (se parchea mis_trapitos.data.database.seed_examples).
          messagebox.showinfo/showerror se parchean con unittest.mock para revisar los mensajes sin abrir
          diálogos. Producto BLUSA-M ($200, stock 10) y un empleado.
        Pasos:
        - Llenar pr_product, pr_discount = 20 y fechas (ayer a +30 días) con el helper fill_promotion()
          y llamar save_promotion_ui().
        - Limpiar con clear_promotion_form(), seleccionar la promoción en promotions_tree (helper
          select_promotion), cambiar el descuento a 25 y volver a guardar.
        - Llamar clear_promotion_form() y revisar los campos.
        - Crear ServicioVentas(db), agregar_producto('BLUSA-M', 2) y registrar_venta(None, empleado,
          'Efectivo', 10).
        - En PromocionesSessionTest: con App completa, crear una promoción de 15 %, cerrar sesión con
          app.show_login() y volver a entrar.
        Esperado:
        - Se crea 1 promoción; al editar se actualiza la misma (sigue habiendo 1, ahora con 25 %).
        - Al limpiar, selected_promotion_id es None y las fechas vuelven a hoy y hoy+30.
        - Venta: subtotal 300 (2 × 200 × 0.75), descuento 30, total 270;
          sale_items.promo_discount_percent = 25; stock 8.
        - Al reabrir sesión la pantalla es nueva, sin selección, y la promoción de 15 % sigue en la
          tabla y vigente.
        """
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

    @tc("STS_PRM_02", nivel="STS", modulo="ventas", reqs=["RF-09"],
        nombre="Promociones con datos inválidos no se guardan")
    def test_datos_invalidos_no_crean_ni_modifican_promociones(self):
        """Comprobar que PromocionesUI.save_promotion_ui() rechaza datos inválidos mostrando un error y sin
        tocar la base, tanto al crear como al editar una promoción existente. RF-09.

        Precondiciones: Ventana Tk real pero oculta (root.withdraw()); en CI corre bajo Xvfb. Base
          SQLite temporal sin datos de ejemplo (se parchea mis_trapitos.data.database.seed_examples).
          messagebox.showinfo/showerror se parchean con unittest.mock para revisar los mensajes sin abrir
          diálogos. Producto registrado. El helper database_state() toma una foto de las tablas products,
          promotions, sales, sale_items, returns, cancellations e inventory_movements.
        Pasos:
        - Para alta y para edición, tomar database_state() antes de empezar.
        - Probar con fill_promotion() + save_promotion_ui() cada combinación: producto '', 'abc' o 99999
          (inexistente); descuento −1, 101 o 'abc'.
        - Después de cada intento comparar database_state() con la foto original.
        Esperado:
        - Cada intento muestra exactamente un messagebox.showerror.
        - La base queda idéntica: no se crea ni se modifica ninguna promoción.
        """
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

    @tc("STS_DEV_01", nivel="STS", modulo="ventas", reqs=["RF-05"],
        nombre="Devoluciones parciales y cancelación reponen solo lo pendiente")
    def test_devoluciones_parciales_y_cancelacion_reponen_solo_lo_pendiente(self):
        """Probar el flujo completo de la pantalla Devoluciones y cancelaciones, DevolucionesUI de
        mis_trapitos/ui/devoluciones.py: return_item_ui() llama devoluciones_srv.devolver() y
        cancel_sale_ui() llama devoluciones_srv.cancelar_venta(); después de cada operación exitosa se
        llama on_inventario_actualizado para que la pestaña de Productos se refresque. RF-05.

        Precondiciones: Ventana Tk real pero oculta (root.withdraw()); en CI corre bajo Xvfb. Base
          SQLite temporal sin datos de ejemplo (se parchea mis_trapitos.data.database.seed_examples).
          messagebox.showinfo/showerror se parchean con unittest.mock para revisar los mensajes sin abrir
          diálogos. Producto con stock 10, venta de 5 piezas (stock 5) y on_inventario_actualizado como
          Mock que anota el stock en cada llamada.
        Pasos:
        - Capturar en r_sale, r_product, r_quantity, r_reason una devolución de 2 y llamar
          return_item_ui().
        - Devolver 1 más con return_item_ui().
        - Capturar la venta en cancel_sale_entry y llamar cancel_sale_ui().
        - Volver a llamar cancel_sale_ui() y return_item_ui() sobre la venta ya cancelada.
        Esperado:
        - El stock pasa 5 → 7 → 8 → 10; returns_tree tiene 2 filas y cancellations_tree 1.
        - Movimientos de la venta: DEVOLUCION suma 3 y CANCELACION suma 2 (no hay doble reposición); la
          venta queda CANCELADA.
        - on_inventario_actualizado se llamó 3 veces viendo stock 7, 8 y 10.
        - Los intentos sobre la venta cancelada muestran un error cada uno, no notifican y no cambian la
          base.
        """
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

    @tc("STS_DEV_02", nivel="STS", modulo="ventas", reqs=["RF-05"],
        nombre="Devoluciones y cancelaciones inválidas no alteran datos")
    def test_devoluciones_invalidas_no_alteran_datos_ni_notifican_inventario(self):
        """Comprobar que la pantalla de Devoluciones rechaza capturas inválidas con un mensaje, sin cambiar
        datos y sin avisar al inventario (on_inventario_actualizado no se llama). Cubre return_item_ui()
        y cancel_sale_ui() de DevolucionesUI. RF-05.

        Precondiciones: Ventana Tk real pero oculta (root.withdraw()); en CI corre bajo Xvfb. Base
          SQLite temporal sin datos de ejemplo (se parchea mis_trapitos.data.database.seed_examples).
          messagebox.showinfo/showerror se parchean con unittest.mock para revisar los mensajes sin abrir
          diálogos. Venta de 5 piezas y otro producto OTRA-L que no se vendió. Se compara con
          database_state().
        Pasos:
        - Con fill_return() + return_item_ui() probar: venta 'abc' o 99999; producto 'abc', OTRA-L (no
          vendido) o 99999; cantidad 'abc', 0, −1 o 6 (más de lo vendido).
        - En test_cancelaciones_invalidas_no_alteran_datos_ni_notifican_inventario: escribir '', 'abc' o
          99999 en cancel_sale_entry y llamar cancel_sale_ui().
        Esperado:
        - Cada intento muestra exactamente un showerror.
        - on_inventario_actualizado no se llama.
        - La base queda idéntica y las tablas de devoluciones y cancelaciones siguen vacías.
        """
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

    @tc("STS_DEV_02")
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


@tc("STS_PRM_01")
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
