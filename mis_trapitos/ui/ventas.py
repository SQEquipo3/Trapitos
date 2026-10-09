import tkinter as tk
from tkinter import messagebox, ttk
from typing import NamedTuple

from config import PAYMENT_METHODS
from utils import dinero
from mis_trapitos.ui.base import (
    ActionBar,
    FormGrid,
    ScrollablePage,
    make_tree,
)


class ResultadoVenta(NamedTuple):
    sale_id: int
    fecha: str
    subtotal: float
    descuento: float
    total: float
    metodo_pago: str


class ServicioVentas:
    def __init__(self, db):
        self.db = db

        self.cart = []

    # ------------------------------------------------------------------ carrito
    def cantidad_en_carrito(self, product_id):
        return sum(int(i["quantity"]) for i in self.cart if int(i["product_id"]) == int(product_id))

    def agregar_producto(self, code, quantity=1):
        """Agrega al carrito validando existencia, cantidad y stock disponible."""
        code = (code or "").strip()
        try:
            qty = int(quantity)
        except (TypeError, ValueError):
            raise ValueError("Cantidad no valida.")
        product = self.db.one("SELECT * FROM products WHERE code=?", (code,))
        if not product:
            raise ValueError("No existe producto con ese codigo.")
        if qty <= 0:
            raise ValueError("Cantidad no valida.")
        if self.cantidad_en_carrito(product["id"]) + qty > int(product["stock"]):
            raise ValueError("Stock insuficiente.")
        for item in self.cart:
            if int(item["product_id"]) == int(product["id"]):
                item["quantity"] += qty
                break
        else:
            self.cart.append({"product_id": product["id"], "quantity": qty})

    def vaciar(self):
        self.cart = []

    def lineas(self):
        """Devuelve las partidas del carrito con promoción vigente y total de línea."""
        rows = []
        for item in self.cart:
            product = self.db.one("SELECT * FROM products WHERE id=?", (item["product_id"],))
            if not product:
                continue
            promo = self.db.active_promotion_percent(product["id"])
            qty = int(item["quantity"])
            line = float(product["sale_price"]) * qty * (1 - promo / 100)
            rows.append({
                "id": product["id"], "code": product["code"], "name": product["name"],
                "quantity": qty, "unit_price": float(product["sale_price"]),
                "promo": promo, "line_total": line,
            })
        return rows

    # ------------------------------------------------------------------ totales
    @staticmethod
    def parsear_descuento(valor):
        try:
            descuento = float(valor or 0)
        except (TypeError, ValueError):
            raise ValueError("El descuento debe ser un numero.")
        if descuento < 0 or descuento > 100:
            raise ValueError("El descuento debe estar entre 0 y 100.")
        return descuento

    def totales(self, descuento=0):
        """Regresa (subtotal con promociones, monto de descuento, total)."""
        descuento = self.parsear_descuento(descuento)
        subtotal = sum(line["line_total"] for line in self.lineas())
        monto = subtotal * descuento / 100
        return subtotal, monto, subtotal - monto

    # -------------------------------------------------------------------- venta
    def registrar_venta(self, customer_id, employee_id, metodo_pago, descuento=0):
        """Registra la venta del carrito y deja el inventario actualizado.

        Si algo falla, Database.register_sale revierte la transacción completa y
        el carrito se conserva para que el usuario pueda corregir y reintentar.
        El carrito solo se vacía cuando la venta quedó guardada.
        """
        if not self.cart:
            raise ValueError("La venta no tiene productos.")
        if metodo_pago not in PAYMENT_METHODS:
            raise ValueError("Metodo de pago no valido.")
        descuento = self.parsear_descuento(descuento)
        if customer_id is not None and not self.db.one("SELECT id FROM customers WHERE id=?", (customer_id,)):
            raise ValueError("Cliente no encontrado.")
        sale_id, subtotal, monto, total = self.db.register_sale(
            customer_id, employee_id, metodo_pago, descuento, self.cart
        )
        fecha = self.db.scalar("SELECT sale_datetime FROM sales WHERE id=?", (sale_id,))
        self.vaciar()
        return ResultadoVenta(sale_id, fecha, subtotal, monto, total, metodo_pago)


class VentasUI(ScrollablePage):
    """Pestaña de ventas. `on_venta_registrada` se invoca tras guardar una venta
    para que otras pestañas (p. ej. Productos) refresquen su inventario."""

    def __init__(self, parent, db, user, on_venta_registrada=None):
        super().__init__(parent)
        self.db = db
        self.user = user
        self.on_venta_registrada = on_venta_registrada
        self.servicio = ServicioVentas(db)
        self._build_widgets()

    def _build_widgets(self):
        form = ttk.LabelFrame(self.body, text="Nueva venta", padding=(0, 12))
        form.pack(fill="x")
        fields = FormGrid(form, columns=3, min_column_width=210)
        fields.pack(fill="x")
        self.sale_customer_id = fields.add_field("ID cliente")
        self.sale_payment = fields.add_combo("Método de pago", PAYMENT_METHODS)
        self.sale_payment.set(PAYMENT_METHODS[0])
        self.sale_discount = fields.add_field("Descuento de venta (%)", default="0")
        self.sale_product_code = fields.add_field("Código del producto")
        self.sale_quantity = fields.add_field("Cantidad", default="1")
        ttk.Label(form, text=f"Empleado: {self.user['name']} · ID {self.user['id']}",
                  style="Muted.TLabel").pack(anchor="w", pady=(0, 12))
        actions = ActionBar(form)
        actions.pack(fill="x")
        actions.add("Agregar al carrito", self.add_cart_item)
        actions.add("Registrar venta", self.register_sale_ui, "Accent.TButton")
        actions.add("Vaciar carrito", self.clear_cart, "Danger.TButton")
        summary = ttk.Frame(self.body)
        summary.pack(fill="both", expand=True, pady=(12, 0))
        summary.columnconfigure(0, weight=3, uniform="summary")
        summary.columnconfigure(1, weight=2, uniform="summary")
        summary.rowconfigure(0, weight=1)
        cart_frame = ttk.LabelFrame(summary, text="Carrito", padding=(0, 12, 0, 0))
        cart_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 18))
        self.cart_tree = make_tree(cart_frame, ("id", "codigo", "producto", "cantidad", "precio", "promo", "subtotal"), height=7)
        ticket_frame = ttk.LabelFrame(summary, text="Resumen y ticket", padding=(0, 12, 0, 0))
        ticket_frame.grid(row=0, column=1, sticky="nsew")
        ticket_frame.columnconfigure(0, weight=1)
        ticket_frame.rowconfigure(0, weight=1)
        self.ticket_text = tk.Text(ticket_frame, height=8, width=1, wrap="word",
                                   bg="#FFFFFF", fg="#223247", insertbackground="#147D73",
                                   relief="flat", borderwidth=0, padx=16, pady=14, font=("Segoe UI", 10))
        self.ticket_text.grid(row=0, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(ticket_frame, orient="vertical", command=self.ticket_text.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        self.ticket_text.configure(yscrollcommand=scroll.set)

    def add_cart_item(self):
        try:
            self.servicio.agregar_producto(self.sale_product_code.get(), self.sale_quantity.get() or 1)
            self.sale_product_code.delete(0, tk.END)
            self.sale_quantity.delete(0, tk.END)
            self.sale_quantity.insert(0, "1")
            self.refresh_cart()
        except Exception as e:
            messagebox.showerror("Carrito", str(e))

    def refresh_cart(self):
        for item in self.cart_tree.get_children():
            self.cart_tree.delete(item)
        for line in self.servicio.lineas():
            self.cart_tree.insert("", tk.END, values=(
                line["id"], line["code"], line["name"], line["quantity"],
                dinero(line["unit_price"]), f"{line['promo']:g}%", dinero(line["line_total"]),
            ))
        try:
            subtotal, _, total = self.servicio.totales(self.sale_discount.get())
            discount = float(self.sale_discount.get() or 0)
        except ValueError:
            subtotal, _, total = self.servicio.totales(0)
            discount = 0
        self.ticket_text.delete("1.0", tk.END)
        self.ticket_text.insert(tk.END, f"Subtotal con promociones: {dinero(subtotal)}\n")
        self.ticket_text.insert(tk.END, f"Descuento general: {discount:g}%\n")
        self.ticket_text.insert(tk.END, f"Total estimado: {dinero(total)}\n")

    def register_sale_ui(self):
        try:
            customer = self.sale_customer_id.get().strip()
            customer_id = int(customer) if customer else None
            r = self.servicio.registrar_venta(
                customer_id, int(self.user["id"]), self.sale_payment.get(), self.sale_discount.get()
            )
            self.ticket_text.delete("1.0", tk.END)
            self.ticket_text.insert(
                tk.END,
                f"VENTA REGISTRADA\nTicket: {r.sale_id}\nFecha: {r.fecha}\n"
                f"Subtotal: {dinero(r.subtotal)}\nDescuento: {dinero(r.descuento)}\n"
                f"Total: {dinero(r.total)}\nMetodo: {r.metodo_pago}\n",
            )
            self.clear_cart(keep_ticket=True)
            if self.on_venta_registrada:
                self.on_venta_registrada()
            messagebox.showinfo("Venta", f"Venta registrada con ticket {r.sale_id}.")
        except Exception as e:
            messagebox.showerror("Venta", str(e))

    def clear_cart(self, keep_ticket=False):
        self.servicio.vaciar()
        for item in self.cart_tree.get_children():
            self.cart_tree.delete(item)
        if not keep_ticket:
            self.ticket_text.delete("1.0", tk.END)
