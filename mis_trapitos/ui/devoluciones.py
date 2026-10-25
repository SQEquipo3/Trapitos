import tkinter as tk
from tkinter import messagebox, ttk

from mis_trapitos.services import devoluciones as devoluciones_srv
from mis_trapitos.ui.base import ActionBar, FormGrid, ScrollablePage, make_tree, tree_clear


class DevolucionesUI(ScrollablePage):
    def __init__(self, parent, db, on_inventario_actualizado=None):
        super().__init__(parent)
        self.db = db
        self.on_inventario_actualizado = on_inventario_actualizado
        self._build_widgets()

    def _build_widgets(self):
        form = ttk.LabelFrame(self.body, text="Registrar devolución", padding=(0, 12))
        form.pack(fill="x")
        fields = FormGrid(form, columns=4, min_column_width=180)
        fields.pack(fill="x")
        self.r_sale = fields.add_field("ID venta")
        self.r_product = fields.add_field("ID producto")
        self.r_quantity = fields.add_field("Cantidad", default="1")
        self.r_reason = fields.add_field("Motivo de devolución")
        actions = ActionBar(form)
        actions.pack(fill="x")
        actions.add("Registrar devolución", self.return_item_ui, "Accent.TButton")
        cancel = ttk.LabelFrame(self.body, text="Cancelar venta", padding=(0, 12))
        cancel.pack(fill="x", pady=(8, 0))
        cancel_fields = FormGrid(cancel, columns=2, min_column_width=200)
        cancel_fields.pack(fill="x")
        self.cancel_sale_entry = cancel_fields.add_field("ID venta a cancelar")
        self.cancel_reason = cancel_fields.add_field("Motivo de cancelación")
        cancel_actions = ActionBar(cancel)
        cancel_actions.pack(fill="x")
        cancel_actions.add("Cancelar venta", self.cancel_sale_ui, "Danger.TButton")
        history = ttk.Frame(self.body)
        history.pack(fill="both", expand=True, pady=(16, 0))
        history.columnconfigure(0, weight=1, uniform="history")
        history.columnconfigure(1, weight=1, uniform="history")
        history.rowconfigure(0, weight=1)
        returns_frame = ttk.LabelFrame(history, text="Devoluciones", padding=(0, 12, 0, 0))
        returns_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 16))
        self.returns_tree = make_tree(returns_frame, ("id", "venta", "producto", "cantidad", "fecha", "motivo"), height=5)
        cancellations_frame = ttk.LabelFrame(history, text="Cancelaciones", padding=(0, 12, 0, 0))
        cancellations_frame.grid(row=0, column=1, sticky="nsew")
        self.cancellations_tree = make_tree(cancellations_frame, ("id", "venta", "fecha", "motivo"), height=5)
        self.refresh_returns()

    def return_item_ui(self):
        try:
            devoluciones_srv.devolver(
                self.db,
                int(self.r_sale.get()),
                int(self.r_product.get()),
                int(self.r_quantity.get()),
                self.r_reason.get().strip(),
            )
            self.refresh_returns()
            if self.on_inventario_actualizado is not None:
                self.on_inventario_actualizado()
            messagebox.showinfo("Devolucion", "Devolucion registrada.")
        except Exception as e:
            messagebox.showerror("Devolucion", str(e))

    def cancel_sale_ui(self):
        try:
            devoluciones_srv.cancelar_venta(
                self.db, int(self.cancel_sale_entry.get()), self.cancel_reason.get().strip()
            )
            self.refresh_returns()
            if self.on_inventario_actualizado is not None:
                self.on_inventario_actualizado()
            messagebox.showinfo("Cancelacion", "Venta cancelada.")
        except Exception as e:
            messagebox.showerror("Cancelacion", str(e))

    def refresh_returns(self):
        rows = self.db.query(
            "SELECT r.id, r.sale_id AS venta, p.name AS producto, r.quantity AS "
            "cantidad, r.return_datetime AS fecha, r.reason AS motivo "
            "FROM returns r JOIN products p ON p.id=r.product_id ORDER BY r.id DESC"
        )
        tree_clear(self.returns_tree)
        for row in rows:
            self.returns_tree.insert("", tk.END, values=[row[key] for key in row.keys()])
        rows = self.db.query(
            "SELECT id, sale_id AS venta, cancel_datetime AS fecha, reason AS motivo "
            "FROM cancellations ORDER BY id DESC"
        )
        tree_clear(self.cancellations_tree)
        for row in rows:
            self.cancellations_tree.insert("", tk.END, values=[row[key] for key in row.keys()])
