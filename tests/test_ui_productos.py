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
from tests.tc import tc


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

    @tc("STS_PRO_01", nivel="STS", modulo="productos", reqs=["RF-01", "RF-02"],
        nombre="Alta y edición de productos desde la interfaz respetan variantes")
    def test_alta_y_edicion_respetan_existencias_de_cada_variante(self):
        """Probar el alta y edición de productos desde la pantalla de Productos: add_product_ui() y
        edit_product_ui() de ProductosUI leen el formulario con collect_product_data(), guardan con
        productos_repo.guardar() y refrescan la tabla con actualizar_inventario(). Cada variante
        (talla/color) conserva su propio stock y no se puede repetir un código. RF-01, RF-02.

        Precondiciones: Ventana Tk real pero oculta (root.withdraw()); en CI corre bajo Xvfb. Base
          SQLite temporal sin datos de ejemplo (se parchea mis_trapitos.data.database.seed_examples).
          messagebox.showinfo/showerror se parchean con unittest.mock para revisar los mensajes sin abrir
          diálogos. Pantalla ProductosUI(root, db) de mis_trapitos/ui/productos.py. El helper
          fill_product() llena los 13 campos del formulario (p_code, p_name, ..., p_image) con
          BLUSA-M-AZUL, stock 10.
        Pasos:
        - Agregar BLUSA-M-AZUL (stock 10) con add_product_ui(); limpiar con clear_product_form() y
          agregar BLUSA-L-ROJA (stock 6).
        - Seleccionar BLUSA-M-AZUL en products_tree (helper select_product), cambiar nombre a 'Blusa de
          algodon' y stock a 12, y llamar edit_product_ui().
        - Leer la tabla con inventory_rows() y el movimiento AJUSTE del primer producto.
        - En test_codigo_duplicado_no_crea_otra_variante: agregar BLUSA-M-AZUL y volver a agregarlo con
          talla L / color Roja.
        Esperado:
        - Hay 2 productos distintos; BLUSA-M-AZUL queda con nombre editado y stock 12; BLUSA-L-ROJA
          conserva stock 6, nombre, talla y color.
        - Se registra un AJUSTE de +2 para el primer producto.
        - El código duplicado muestra un error y sigue habiendo 1 producto y 1 movimiento.
        """
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

    @tc("STS_PRO_02", nivel="STS", modulo="productos", reqs=["RF-01", "RF-03"],
        nombre="Validaciones del formulario no modifican datos")
    def test_validaciones_no_modifican_producto_ni_movimientos(self):
        """Comprobar que las validaciones del formulario de Productos impiden guardar datos inválidos:
        campos obligatorios vacíos, precios o stock negativos o no numéricos, stock decimal o un
        proveedor que no existe. Las reglas están en ProductosUI.collect_product_data(); si una falla,
        edit_product_ui() muestra el error y no llama productos_repo.guardar(). RF-01, RF-03.

        Precondiciones: Ventana Tk real pero oculta (root.withdraw()); en CI corre bajo Xvfb. Base
          SQLite temporal sin datos de ejemplo (se parchea mis_trapitos.data.database.seed_examples).
          messagebox.showinfo/showerror se parchean con unittest.mock para revisar los mensajes sin abrir
          diálogos. Pantalla ProductosUI(root, db) de mis_trapitos/ui/productos.py. El helper
          fill_product() llena los 13 campos del formulario (p_code, p_name, ..., p_image) con
          BLUSA-M-AZUL, stock 10. Un producto ya guardado y seleccionado.
        Pasos:
        - Para cada caso, llenar el formulario con fill_product() y llamar edit_product_ui(): código,
          nombre, categoría, talla o color en blanco; precio de compra −1; precio de venta −1; stock −1;
          precio 'abc'; stock '1.5'; proveedor 9999.
        - Después de cada intento comparar el producto en la base y el número de movimientos.
        - En test_edicion_sin_seleccion_no_guarda_producto: sin seleccionar nada, llenar el formulario y
          llamar edit_product_ui().
        Esperado:
        - Cada intento muestra exactamente un showerror.
        - El producto y la tabla inventory_movements quedan sin cambios.
        - La edición sin selección muestra error y no crea ningún producto.
        """
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

    @tc("STS_PRO_01")
    def test_codigo_duplicado_no_crea_otra_variante(self):
        self.add_product()
        fill_product(self.ui, p_size="L", p_color="Roja")
        self.ui.add_product_ui()
        self.error.assert_called_once()
        self.assertEqual(self.db.scalar("SELECT COUNT(*) FROM products"), 1)
        self.assertEqual(self.db.scalar("SELECT COUNT(*) FROM inventory_movements"), 1)
        row = inventory_rows(self.ui)["BLUSA-M-AZUL"]
        self.assertEqual((row["talla"], row["color"]), ("M", "Azul"))

    @tc("STS_PRO_02")
    def test_edicion_sin_seleccion_no_guarda_producto(self):
        fill_product(self.ui)
        self.ui.edit_product_ui()
        self.error.assert_called_once()
        self.assertEqual(self.db.scalar("SELECT COUNT(*) FROM products"), 0)

    @tc("STS_PRO_04", nivel="STS", modulo="productos", reqs=["RF-03"],
        nombre="Exportación del inventario a CSV")
    def test_exportacion_csv_conserva_variantes_y_texto(self):
        """Probar el botón Exportar CSV de la pantalla de Productos, ProductosUI.export_inventory_csv():
        debe escribir todas las variantes del inventario (lo obtiene con reportes_repo.ejecutar(db,
        'Inventario general actualizado')) sin perder texto con comas o acentos. RF-03.

        Precondiciones: Ventana Tk real pero oculta (root.withdraw()); en CI corre bajo Xvfb. Base
          SQLite temporal sin datos de ejemplo (se parchea mis_trapitos.data.database.seed_examples).
          messagebox.showinfo/showerror se parchean con unittest.mock para revisar los mensajes sin abrir
          diálogos. Pantalla ProductosUI(root, db) de mis_trapitos/ui/productos.py. El helper
          fill_product() llena los 13 campos del formulario (p_code, p_name, ..., p_image) con
          BLUSA-M-AZUL, stock 10. filedialog.asksaveasfilename parcheado para regresar la ruta del
          archivo.
        Pasos:
        - Agregar 'Blusa, edición especial' (BLUSA-M-AZUL) y BLUSA-L-ROJA con stock 6.
        - Llamar export_inventory_csv().
        - Leer el archivo con csv.DictReader.
        Esperado:
        - El CSV tiene exactamente los códigos BLUSA-M-AZUL y BLUSA-L-ROJA.
        - El nombre 'Blusa, edición especial' se conserva exacto; BLUSA-L-ROJA tiene stock '6' y talla
          'L'.
        """
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

    @tc("STS_PRO_03", nivel="STS", modulo="productos", reqs=["RF-01"],
        nombre="Imagen de producto: copia, recuperación y archivo inexistente")
    def test_imagen_se_copia_guarda_y_recupera_al_seleccionar(self):
        """Probar la foto del producto: ProductosUI.choose_product_image() copia la imagen elegida a la
        carpeta IMAGE_DIR (store_product_image), la muestra en la vista previa (display_image) y guarda
        la ruta en products.image_path; al volver a seleccionar el producto se recupera. Si la ruta no
        existe, se muestra un aviso sin romper el formulario. RF-01.

        Precondiciones: Ventana Tk real pero oculta (root.withdraw()); en CI corre bajo Xvfb. Base
          SQLite temporal sin datos de ejemplo (se parchea mis_trapitos.data.database.seed_examples).
          messagebox.showinfo/showerror se parchean con unittest.mock para revisar los mensajes sin abrir
          diálogos. Pantalla ProductosUI(root, db) de mis_trapitos/ui/productos.py. El helper
          fill_product() llena los 13 campos del formulario (p_code, p_name, ..., p_image) con
          BLUSA-M-AZUL, stock 10. Imagen PNG azul de 320×400 creada con Pillow en una carpeta temporal;
          IMAGE_DIR y filedialog.askopenfilename parcheados.
        Pasos:
        - Llenar el formulario y llamar choose_product_image().
        - Revisar el archivo copiado (carpeta, tamaño y color) y llamar add_product_ui().
        - Llamar clear_product_form() y volver a seleccionar el producto con select_product().
        - En test_imagen_inexistente_muestra_estado_sin_romper_formulario: agregar un producto con
          p_image apuntando a un archivo que no existe.
        Esperado:
        - La imagen se copia a IMAGE_DIR (ruta distinta al original) con el mismo tamaño y color, y hay
          vista previa.
        - products.image_path guarda la ruta copiada; al limpiar desaparece la vista previa y al
          reseleccionar se recupera.
        - Con archivo inexistente la etiqueta dice 'No se pudo mostrar la foto' y el producto se guarda
          igual.
        """
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

    @tc("STS_PRO_03")
    def test_imagen_inexistente_muestra_estado_sin_romper_formulario(self):
        self.add_product(p_image=str(self.directory / "inexistente.png"))
        self.assertIsNone(self.ui.product_photo_ref)
        self.assertEqual(self.ui.product_image_label.cget("text"), "No se pudo mostrar la foto")
        self.assertEqual(len(inventory_rows(self.ui)), 1)

    @tc("STS_PRO_05")
    def test_otro_componente_puede_recargar_el_inventario(self):
        product_id = self.add_product()
        self.db.execute("UPDATE products SET stock=4 WHERE id=?", (product_id,))
        self.ui.actualizar_inventario()
        self.assertEqual(int(inventory_rows(self.ui)["BLUSA-M-AZUL"]["stock"]), 4)
        self.ui.destroy()
        self.ui = ui_productos.ProductosUI(self.root, self.db)
        self.assertEqual(int(inventory_rows(self.ui)["BLUSA-M-AZUL"]["stock"]), 4)
        self.assertIsNone(self.ui.selected_product_id)

    @tc("STS_PRO_05")
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

    @tc("STS_PRO_05", nivel="STS", modulo="productos", reqs=["RNF-01"],
        nombre="Refresco y selección en la tabla de inventario")
    def test_limpiar_no_restaura_seleccion_por_eventos_pendientes(self):
        """Probar el refresco de la tabla de inventario, ProductosUI.actualizar_inventario(), que otras
        pantallas (ventas, devoluciones) llaman cuando cambian el stock: debe mostrar los datos nuevos
        sin pisar lo que el usuario está editando. También que clear_product_form() quita la selección
        sin que eventos pendientes de Tk la restauren. RNF-01.

        Precondiciones: Ventana Tk real pero oculta (root.withdraw()); en CI corre bajo Xvfb. Base
          SQLite temporal sin datos de ejemplo (se parchea mis_trapitos.data.database.seed_examples).
          messagebox.showinfo/showerror se parchean con unittest.mock para revisar los mensajes sin abrir
          diálogos. Pantalla ProductosUI(root, db) de mis_trapitos/ui/productos.py. El helper
          fill_product() llena los 13 campos del formulario (p_code, p_name, ..., p_image) con
          BLUSA-M-AZUL, stock 10.
        Pasos:
        - Agregar un producto, seleccionarlo y llamar clear_product_form(); procesar eventos con
          root.update().
        - En test_otro_componente_puede_recargar_el_inventario: cambiar el stock a 4 directo en la base
          y llamar actualizar_inventario(); destruir y recrear la pantalla.
        - En test_refrescar_sin_cambio_externo_conserva_edicion_pendiente: seleccionar el producto,
          escribir 'Nombre pendiente' y stock 14 sin guardar, y llamar actualizar_inventario().
        Esperado:
        - Después de limpiar no hay producto seleccionado, el código está vacío y no hay vista previa.
        - La tabla muestra stock 4 y la pantalla recreada también, sin selección.
        - La edición pendiente ('Nombre pendiente', 14) se conserva y la tabla sigue mostrando el stock
          real 10.
        """
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

    @tc("STS_PRO_06", nivel="STS", modulo="productos", reqs=["RF-04", "RNF-01"],
        nombre="Venta, devolución y cancelación actualizan el inventario sin recarga manual")
    def test_venta_devolucion_y_cancelacion_actualizan_inventario_sin_recarga_manual(self):
        """Prueba de extremo a extremo entre pantallas: una venta (VentasUI.add_cart_item() +
        register_sale_ui()), una devolución (DevolucionesUI.return_item_ui()) y una cancelación
        (cancel_sale_ui()) deben verse de inmediato en la tabla y el formulario de Productos, sin que el
        usuario recargue, y sin perder una edición pendiente de otro campo. App conecta las pantallas
        con App.refresh_products(). RF-04, RNF-01.

        Precondiciones: App completa (App(db_path=...)) con sesión iniciada y dos productos:
          BLUSA-M-AZUL (stock 10) y BLUSA-L-ROJA (stock 6).
        Pasos:
        - Seleccionar BLUSA-M-AZUL en Productos y escribir 'Blusa de algodon' en el nombre sin guardar.
        - En Ventas, capturar el código y cantidad 3, llamar add_cart_item() y register_sale_ui().
        - Guardar la edición pendiente con edit_product_ui().
        - En Devoluciones, devolver 1 pieza con return_item_ui().
        - Cancelar la venta con cancel_sale_ui().
        Esperado:
        - Tras la venta: stock 7 en base, tabla y formulario; el carrito queda vacío; el nombre
          pendiente se conserva y al guardarlo el stock sigue en 7.
        - Tras la devolución: stock 8 y 1 fila en la tabla de devoluciones.
        - Tras la cancelación: stock 10, venta CANCELADA y 1 fila en cancelaciones. BLUSA-L-ROJA sigue
          en 6 todo el tiempo.
        """
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

    @tc("STS_PRO_07", nivel="STS", modulo="productos", reqs=["RNF-01"],
        nombre="Reabrir sesión recrea el módulo y conserva inventario")
    def test_reabrir_sesion_recrea_modulo_y_conserva_inventario(self):
        """Comprobar que cerrar sesión (App.show_login()) y volver a entrar crea una pantalla de Productos
        nueva y limpia, pero el inventario guardado sigue ahí. RNF-01.

        Precondiciones: App completa con sesión iniciada como 'prueba'.
        Pasos:
        - Agregar BLUSA-M-AZUL (stock 10) con add_product_ui().
        - Llamar app.show_login(), escribir las credenciales y llamar login_view.submit().
        - Revisar la nueva app.productos_ui.
        Esperado:
        - Al cerrar sesión app.user es None.
        - La pantalla de Productos es un objeto nuevo y sin selección.
        - BLUSA-M-AZUL sigue con stock 10 en la base y en la tabla.
        """
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
