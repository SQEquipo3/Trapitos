"Promociones"

import tkinter as tk
from datetime import date
from tkinter import messagebox, ttk

from utils import date_offset, today_text
from mis_trapitos.ui.base import ActionBar, FormGrid, ScrollablePage, make_tree, tree_clear, set_entries
from mis_trapitos.data.repositories import promociones as promociones_repo
from mis_trapitos.data.repositories import productos as productos_repo


class PromocionesUI(ScrollablePage):
    def __init__(self, parent, db):
        super().__init__(parent)
        self.db = db
        self.selected_promotion_id = None
        self._build_widgets()

    def _build_widgets(self):
        form = ttk.LabelFrame(self.body, text="Datos de la promoción", padding=(0, 12))
        form.pack(fill="x")
        fields = FormGrid(form, columns=4, min_column_width=180)
        fields.pack(fill="x")
        self.pr_product = fields.add_field("ID producto")
        self.pr_discount = fields.add_field("Descuento (%)")
        self.pr_start = fields.add_field("Fecha de inicio", default=today_text())
        self.pr_end = fields.add_field("Fecha de fin", default=date_offset(30))
        actions = ActionBar(form)
        actions.pack(fill="x")
        actions.add("Guardar promoción", self.save_promotion_ui, "Accent.TButton")
        actions.add("Limpiar", self.clear_promotion_form)
        table = ttk.LabelFrame(self.body, text="Promociones registradas", padding=(0, 12, 0, 0))
        table.pack(fill="both", expand=True, pady=(16, 0))
        self.promotions_tree = make_tree(table, ("id", "producto_id", "codigo", "producto", "descuento", "inicio", "fin"), height=8)
        self.promotions_tree.bind("<<TreeviewSelect>>", self.load_promotion_selected)
        self.refresh_promotions()

    def save_promotion_ui(self):
        try:
            product_id = int(self.pr_product.get())
            discount = float(self.pr_discount.get() or 0)
            if discount < 0 or discount > 100:
                raise ValueError("Descuento no valido.")
            if not productos_repo.obtener_por_id(self.db, product_id):
                raise ValueError("Producto no encontrado.")
            start_text = self.pr_start.get().strip() or today_text()
            end_text = self.pr_end.get().strip() or today_text()
            try:
                start_date = date.fromisoformat(start_text)
                end_date = date.fromisoformat(end_text)
                if start_date.isoformat() != start_text or end_date.isoformat() != end_text:
                    raise ValueError
            except ValueError:
                raise ValueError("Las fechas deben ser válidas y usar el formato AAAA-MM-DD.") from None
            if end_date < start_date:
                raise ValueError("La fecha de fin no puede ser anterior a la fecha de inicio.")
            self.selected_promotion_id = promociones_repo.guardar(
                self.db,
                self.selected_promotion_id,
                product_id,
                discount,
                start_text,
                end_text,
            )
            self.refresh_promotions()
            messagebox.showinfo("Promociones", "Promocion guardada.")
        except Exception as e:
            messagebox.showerror("Promociones", str(e))

    def refresh_promotions(self):
        rows = promociones_repo.listar(self.db)
        tree_clear(self.promotions_tree)
        for row in rows:
            self.promotions_tree.insert("", tk.END, values=[row[key] for key in row.keys()])

    def load_promotion_selected(self, event=None):
        sel = self.promotions_tree.selection()
        if not sel:
            return
        promotion_id = self.promotions_tree.item(sel[0], "values")[0]
        row = promociones_repo.obtener_por_id(self.db, promotion_id)
        if not row:
            return
        self.selected_promotion_id = row["id"]
        set_entries(
            [self.pr_product, self.pr_discount, self.pr_start, self.pr_end],
            [row["product_id"], row["discount_percent"], row["start_date"], row["end_date"]],
        )

    def clear_promotion_form(self):
        self.selected_promotion_id = None
        for entry in [self.pr_product, self.pr_discount, self.pr_start, self.pr_end]:
            entry.delete(0, tk.END)
        self.pr_start.insert(0, today_text())
        self.pr_end.insert(0, date_offset(30))
