"""Interfaz modular de productos, variantes e inventario de Mis Trapitos.

Recibe la base de datos abierta por la aplicación. No crea conexiones ni
importa el punto de entrada; los datos se leen y guardan con los repositorios.
"""

import csv
import os
import tkinter as tk
from datetime import date, datetime
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageOps, ImageTk

from mis_trapitos.data.repositories import productos as productos_repo
from mis_trapitos.data.repositories import reportes as reportes_repo
from mis_trapitos.ui.base import ActionBar, FormGrid, ScrollablePage, make_tree


IMAGE_DIR = "mis_trapitos_imagenes"


class ProductosUI(ScrollablePage):
    """Pestaña de productos con estado propio y actualización explícita."""

    def __init__(self, parent, db):
        super().__init__(parent)
        self.db = db
        self.selected_product_id = None
        self.product_photo_ref = None
        self._loaded_stock = None
        self._build_widgets()
        self.actualizar_inventario()

    def _build_widgets(self):
        editor = ttk.Frame(self.body)
        editor.pack(fill="x")
        editor.columnconfigure(0, weight=1)
        form = ttk.LabelFrame(editor, text="Datos del producto", padding=(0, 12))
        form.grid(row=0, column=0, sticky="nsew")
        fields = FormGrid(form, columns=4, min_column_width=160)
        fields.pack(fill="x")
        self.p_code = fields.add_field("Código")
        self.p_name = fields.add_field("Nombre")
        self.p_category = fields.add_field("Categoría")
        self.p_size = fields.add_field("Talla")
        self.p_color = fields.add_field("Color")
        self.p_purchase = fields.add_field("Precio de compra")
        self.p_sale = fields.add_field("Precio de venta")
        self.p_stock = fields.add_field("Existencias")
        self.p_supplier = fields.add_field("ID proveedor")
        self.p_entry = fields.add_field("Fecha de ingreso", default=date.today().isoformat())
        self.p_brand = fields.add_field("Marca")
        self.p_season = fields.add_field("Temporada")
        photo_fields = FormGrid(form, columns=1)
        photo_fields.pack(fill="x")
        self.p_image = photo_fields.add_field("Archivo de imagen")
        preview = ttk.LabelFrame(editor, text="Vista previa", padding=(0, 12))
        preview.grid(row=0, column=1, sticky="n", padx=(20, 0))
        holder = ttk.Frame(preview, width=160, height=160, style="Surface.TFrame")
        holder.pack()
        holder.pack_propagate(False)
        self.product_image_label = tk.Label(
            holder, text="Sin imagen", wraplength=140, anchor="center",
            bg="#FFFFFF", fg="#53677E", font=("Segoe UI", 9), borderwidth=0,
        )
        self.product_image_label.pack(fill="both", expand=True)
        self.product_image_text = ttk.Label(preview, text="Selecciona un producto", wraplength=160,
                                            justify="left", style="Muted.TLabel")
        self.product_image_text.pack(fill="x", pady=(8, 8))
        ttk.Button(preview, text="Seleccionar foto", command=self.choose_product_image).pack(fill="x", pady=(0, 6))
        ttk.Button(preview, text="Ver foto", command=self.show_selected_product_image).pack(fill="x")
        actions = ActionBar(self.body)
        actions.pack(fill="x", pady=(0, 20))
        actions.add("Agregar producto", self.add_product_ui, "Accent.TButton")
        actions.add("Editar producto", self.edit_product_ui)
        actions.add("Limpiar", self.clear_product_form)
        actions.add("Exportar inventario", self.export_inventory_csv)
        table = ttk.LabelFrame(self.body, text="Inventario", padding=(0, 12, 0, 0))
        table.pack(fill="both", expand=True)
        self.products_tree = make_tree(
            table, ("id", "codigo", "producto", "categoria", "talla", "color", "stock", "precio", "proveedor"), height=5
        )
        self.products_tree.bind("<<TreeviewSelect>>", self.load_product_selected)

    def choose_product_image(self):
        path = filedialog.askopenfilename(
            parent=self,
            title="Seleccionar foto del producto",
            filetypes=[
                ("Imagenes", ("*.jpg", "*.jpeg", "*.png", "*.gif", "*.ppm", "*.pgm")),
                ("JPG", ("*.jpg", "*.jpeg")), ("PNG", "*.png"), ("Todos", "*.*"),
            ],
        )
        if not path:
            return
        try:
            stored_path = self.store_product_image(path)
            self.p_image.delete(0, tk.END)
            self.p_image.insert(0, stored_path)
            self.display_image(stored_path)
        except Exception as e:
            messagebox.showerror("Foto", str(e), parent=self)

    @staticmethod
    def resolve_image_path(path):
        if not path:
            return ""
        path = path.strip().strip('"')
        if os.path.exists(path):
            return path
        base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        alternative = os.path.join(base, path)
        return alternative if os.path.exists(alternative) else ""

    def store_product_image(self, source_path):
        source_path = self.resolve_image_path(source_path) or source_path
        if not os.path.exists(source_path):
            raise ValueError("No se encontro la imagen seleccionada.")
        base = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), IMAGE_DIR)
        os.makedirs(base, exist_ok=True)
        name, ext = os.path.splitext(os.path.basename(source_path))
        ext = ext.lower()
        if ext not in (".jpg", ".jpeg", ".png", ".gif", ".ppm", ".pgm"):
            ext = ".jpg"
        safe = "".join(ch for ch in name if ch.isalnum() or ch in ("_", "-")).strip() or "producto"
        target = os.path.join(base, f"{safe}_{datetime.now().strftime('%Y%m%d%H%M%S')}{ext}")
        with Image.open(source_path) as source:
            img = ImageOps.exif_transpose(source)
            if ext in (".jpg", ".jpeg"):
                img.convert("RGB").save(target, "JPEG", quality=92)
            elif ext == ".png":
                img.save(target, "PNG")
            else:
                img.save(target)
        return target

    def create_photo_image(self, path, size):
        resolved = self.resolve_image_path(path)
        if not resolved:
            raise ValueError("No hay archivo de imagen disponible.")
        with Image.open(resolved) as source:
            img = ImageOps.exif_transpose(source)
            try:
                resample = Image.Resampling.LANCZOS
            except AttributeError:
                resample = Image.LANCZOS
            img.thumbnail(size, resample)
            return ImageTk.PhotoImage(img, master=self), resolved

    def display_image(self, path):
        if not path:
            self.product_photo_ref = None
            self.product_image_label.configure(image="", text="Sin foto", bg="white")
            self.product_image_text.configure(text="No hay archivo de imagen disponible.")
            return
        try:
            photo, resolved = self.create_photo_image(path, (150, 150))
            self.product_photo_ref = photo
            self.product_image_label.configure(image=photo, text="", bg="white")
            self.product_image_text.configure(text=os.path.basename(resolved))
        except Exception as e:
            self.product_photo_ref = None
            self.product_image_label.configure(image="", text="No se pudo mostrar la foto", bg="white")
            self.product_image_text.configure(text=str(e))

    def show_selected_product_image(self):
        path = self.p_image.get().strip()
        if not path:
            messagebox.showwarning("Foto", "Primero selecciona una foto o un producto con foto.", parent=self)
            return
        self.display_image(path)
        try:
            photo, resolved = self.create_photo_image(path, (620, 620))
            window = tk.Toplevel(self)
            window.title(os.path.basename(resolved))
            window.geometry("700x700")
            frame = ttk.Frame(window, padding=12)
            frame.pack(fill="both", expand=True)
            label = tk.Label(frame, image=photo, bg="white")
            label.image = photo
            label.pack(expand=True)
            ttk.Label(frame, text=resolved, wraplength=650, justify="center").pack(pady=8)
        except Exception as e:
            messagebox.showerror("Foto", str(e), parent=self)

    def collect_product_data(self):
        data = (
            self.p_code.get().strip(),
            self.p_name.get().strip(),
            self.p_category.get().strip(),
            self.p_size.get().strip(),
            self.p_color.get().strip(),
            float(self.p_purchase.get() or 0),
            float(self.p_sale.get() or 0),
            int(self.p_stock.get() or 0),
            int(self.p_supplier.get()) if self.p_supplier.get().strip() else None,
            self.p_entry.get().strip() or date.today().isoformat(),
            self.p_brand.get().strip(),
            self.p_season.get().strip(),
            self.p_image.get().strip(),
        )
        if not all(data[:5]):
            raise ValueError("Codigo, nombre, categoria, talla y color son obligatorios.")
        if data[5] < 0 or data[6] < 0 or data[7] < 0:
            raise ValueError("Precios y stock no pueden ser negativos.")
        if data[8] is not None and not productos_repo.proveedor_existe(self.db, data[8]):
            raise ValueError(
                "El proveedor indicado no existe. Selecciona un ID de proveedor registrado o deja el campo vacio."
            )
        return data

    def add_product_ui(self):
        try:
            data = self.collect_product_data()
            self.selected_product_id = productos_repo.guardar(self.db, None, data)
            self.actualizar_inventario()
            self.products_tree.selection_set(str(self.selected_product_id))
            self.display_image(data[12])
            messagebox.showinfo("Productos", "Producto agregado.", parent=self)
        except Exception as e:
            messagebox.showerror("Productos", str(e), parent=self)

    def edit_product_ui(self):
        try:
            if not self.selected_product_id:
                raise ValueError("Selecciona un producto de la tabla antes de editarlo.")
            data = self.collect_product_data()
            productos_repo.guardar(self.db, self.selected_product_id, data)
            self.actualizar_inventario()
            self.display_image(data[12])
            messagebox.showinfo("Productos", "Producto editado correctamente.", parent=self)
        except Exception as e:
            messagebox.showerror("Productos", str(e), parent=self)

    def save_product_ui(self):
        if self.selected_product_id:
            self.edit_product_ui()
        else:
            self.add_product_ui()

    def actualizar_inventario(self):
        """Refresca existencias confirmadas sin perder selección ni otras ediciones.

        App llama este método después de ventas, devoluciones y cancelaciones.
        Solo se sustituye el stock del formulario si cambió en la base de datos.
        """
        rows = productos_repo.listar_inventario(self.db)
        stale_items = set(self.products_tree.get_children())
        selected_stock = None
        for index, row in enumerate(rows):
            item_id = str(row["id"])
            values = [row[key] for key in row.keys()]
            if self.products_tree.exists(item_id):
                self.products_tree.item(item_id, values=values)
                self.products_tree.move(item_id, "", index)
            else:
                self.products_tree.insert("", index, iid=item_id, values=values)
            stale_items.discard(item_id)
            if row["id"] == self.selected_product_id:
                selected_stock = int(row["stock"])
        for item_id in stale_items:
            self.products_tree.delete(item_id)
        if self.selected_product_id is not None:
            if selected_stock is None:
                self.clear_product_form()
            elif selected_stock != self._loaded_stock:
                self.p_stock.delete(0, tk.END)
                self.p_stock.insert(0, str(selected_stock))
                self._loaded_stock = selected_stock

    def load_product_selected(self, event=None):
        selection = self.products_tree.selection()
        if not selection:
            return
        product_id = self.products_tree.item(selection[0], "values")[0]
        row = productos_repo.obtener_por_id(self.db, product_id)
        if not row:
            return
        self.selected_product_id = row["id"]
        self._loaded_stock = int(row["stock"])
        values = [
            row["code"], row["name"], row["category"], row["size"], row["color"],
            row["purchase_price"], row["sale_price"], row["stock"], row["supplier_id"],
            row["entry_date"], row["brand"], row["season"], row["image_path"],
        ]
        for entry, value in zip(self._product_entries(), values):
            entry.delete(0, tk.END)
            entry.insert(0, "" if value is None else str(value))
        self.display_image(row["image_path"])

    def _product_entries(self):
        return (
            self.p_code, self.p_name, self.p_category, self.p_size, self.p_color,
            self.p_purchase, self.p_sale, self.p_stock, self.p_supplier,
            self.p_entry, self.p_brand, self.p_season, self.p_image,
        )

    def clear_product_form(self):
        self.selected_product_id = None
        self._loaded_stock = None
        self.products_tree.selection_remove(self.products_tree.selection())
        for entry in self._product_entries():
            entry.delete(0, tk.END)
        self.p_supplier.insert(0, "1")
        self.p_entry.insert(0, date.today().isoformat())
        self.display_image("")

    def export_inventory_csv(self):
        path = filedialog.asksaveasfilename(
            parent=self, defaultextension=".csv", filetypes=[("CSV", "*.csv")]
        )
        if not path:
            return
        rows = reportes_repo.ejecutar(self.db, "Inventario general actualizado")
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            if rows:
                writer.writerow(rows[0].keys())
                for row in rows:
                    writer.writerow([row[key] for key in row.keys()])
        messagebox.showinfo("Exportar", f"Inventario exportado en:\n{path}", parent=self)
