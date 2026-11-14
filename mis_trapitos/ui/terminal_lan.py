"""Terminal de venta conectada al servicio LAN de la terminal principal (#56).

Se abre con «python main.py --terminal http://IP:8765». No usa base de datos local:
consulta el inventario y registra ventas en la terminal principal, y refresca las
existencias cada SONDEO_MS (RNF-01: visibilidad en ≤ 5 s). Los demás módulos
(productos, contactos, reportes...) se administran en la terminal principal.
"""

import queue
import threading
import tkinter as tk
from tkinter import messagebox, ttk

from config import APP_TITLE, APP_VERSION, PAYMENT_METHODS
from mis_trapitos.lan.cliente import ClienteLAN, ErrorLAN, nueva_clave
from mis_trapitos.services.ventas import parsear_descuento
from mis_trapitos.ui.base import ActionBar, FormGrid, ScrollablePage, make_tree
from mis_trapitos.ui.login import Login
from mis_trapitos.ui.styles import UI_COLORS, configure_styles
from utils import dinero

SONDEO_MS = 2000
COLUMNAS_INVENTARIO = ("id", "codigo", "producto", "categoria", "talla", "color", "stock", "precio", "proveedor")


class CarritoLAN:
    """Carrito de la terminal remota, independiente de Tk.

    Valida contra la última copia del inventario; la venta la confirma (y revalida) el servicio.
    Si una venta queda incierta (sin respuesta), conserva su clave y bloquea cambios al carrito
    hasta reintentar: el reintento con la misma clave nunca vende dos veces.
    """

    def __init__(self, cliente):
        self.cliente = cliente
        self.productos = {}
        self.cart = []
        self.pendiente = None

    def cargar_inventario(self, productos):
        self.productos = {p["id"]: p for p in productos}

    def _por_codigo(self, code):
        return next((p for p in self.productos.values() if p["codigo"] == code), None)

    def _exigir_sin_pendiente(self):
        if self.pendiente:
            raise ValueError("Hay una venta sin confirmar. Presiona «Registrar venta» para reintentarla.")

    def cantidad_en_carrito(self, product_id):
        return sum(i["quantity"] for i in self.cart if i["product_id"] == product_id)

    def agregar(self, code, quantity=1):
        self._exigir_sin_pendiente()
        try:
            qty = int(quantity)
        except (TypeError, ValueError):
            raise ValueError("Cantidad no valida.")
        producto = self._por_codigo((code or "").strip())
        if producto is None:
            raise ValueError("No existe producto con ese codigo.")
        if qty <= 0:
            raise ValueError("Cantidad no valida.")
        if self.cantidad_en_carrito(producto["id"]) + qty > int(producto["stock"]):
            raise ValueError("Stock insuficiente.")
        for item in self.cart:
            if item["product_id"] == producto["id"]:
                item["quantity"] += qty
                break
        else:
            self.cart.append({"product_id": producto["id"], "quantity": qty})

    def vaciar(self):
        self._exigir_sin_pendiente()
        self.cart = []

    def lineas(self):
        filas = []
        for item in self.cart:
            p = self.productos.get(item["product_id"])
            if p is None:
                continue
            total = float(p["precio"]) * item["quantity"] * (1 - float(p["promo"]) / 100)
            filas.append({"id": p["id"], "code": p["codigo"], "name": p["producto"],
                          "quantity": item["quantity"], "unit_price": float(p["precio"]),
                          "promo": float(p["promo"]), "line_total": total})
        return filas

    def totales(self, descuento=0):
        descuento = parsear_descuento(descuento)
        subtotal = sum(line["line_total"] for line in self.lineas())
        return subtotal, subtotal * descuento / 100, subtotal * (1 - descuento / 100)

    def registrar(self, cliente_id, metodo_pago, descuento):
        if not self.cart:
            raise ValueError("La venta no tiene productos.")
        clave = self.pendiente or nueva_clave()
        self.pendiente = clave
        try:
            r = self.cliente.registrar_venta(clave, cliente_id, metodo_pago, descuento, self.cart)
        except ErrorLAN as e:
            if not e.incierto:
                self.pendiente = None      # rechazo definitivo: el carrito se puede corregir
            raise
        self.pendiente = None
        self.cart = []
        for product_id, stock in r["stock"].items():
            if int(product_id) in self.productos:
                self.productos[int(product_id)]["stock"] = stock
        return r


class TerminalLAN(tk.Tk):
    def __init__(self, url, cliente=None):
        super().__init__()
        configure_styles(self)
        self.title(f"{APP_TITLE} v{APP_VERSION} · Terminal de venta")
        self.geometry(f"{min(1200, self.winfo_screenwidth()-60)}x{min(780, self.winfo_screenheight()-90)}")
        self.minsize(960, 640)
        self.configure(bg=UI_COLORS["background"])
        self.cliente = cliente or ClienteLAN(url)
        self.carrito = CarritoLAN(self.cliente)
        self.user = None
        self._respuestas = queue.Queue()
        self._consultando = False
        self._sondeo_id = None
        self.inventory_tree = None
        self.estado = tk.StringVar(self, value="")
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.show_login()

    def on_close(self):
        if self._sondeo_id is not None:
            self.after_cancel(self._sondeo_id)
        self.destroy()

    def _autenticar(self, usuario, contrasena):
        try:
            return self.cliente.iniciar_sesion(usuario, contrasena)
        except ErrorLAN as e:
            messagebox.showerror("Terminal de venta", e.mensaje, parent=self)
            return None

    def show_login(self):
        for child in self.winfo_children():
            child.destroy()
        self.login_view = Login(self, authenticate=self._autenticar, on_authenticated=self._on_authenticated)
        self.login_view.pack(expand=True)
        ttk.Label(self.login_view, text=f"Terminal de venta conectada a {self.cliente.url}",
                  style="Muted.TLabel").grid(row=5, column=0, columnspan=2, pady=(12, 0))
        self.login_view.password_entry.focus_set()

    def _on_authenticated(self, user):
        self.user = user
        self.show_main()

    # ------------------------------------------------------------------ pantalla principal
    def show_main(self):
        for child in self.winfo_children():
            child.destroy()
        page = ScrollablePage(self, padding=(24, 20))
        page.pack(fill="both", expand=True)
        body = page.body
        cabecera = ttk.Frame(body)
        cabecera.pack(fill="x", pady=(0, 12))
        ttk.Label(cabecera, text="Terminal de venta", style="WorkspaceTitle.TLabel").pack(anchor="w")
        ttk.Label(cabecera, text=f"{self.user['name']} · {self.user['role']} · servicio {self.cliente.url}",
                  style="Muted.TLabel").pack(anchor="w")
        ttk.Label(cabecera, textvariable=self.estado, style="Muted.TLabel").pack(anchor="w")

        form = ttk.LabelFrame(body, text="Nueva venta", padding=(0, 12))
        form.pack(fill="x")
        fields = FormGrid(form, columns=3, min_column_width=210)
        fields.pack(fill="x")
        self.sale_customer_id = fields.add_field("ID cliente")
        self.sale_payment = fields.add_combo("Método de pago", PAYMENT_METHODS)
        self.sale_payment.set(PAYMENT_METHODS[0])
        self.sale_discount = fields.add_field("Descuento de venta (%)", default="0")
        self.sale_product_code = fields.add_field("Código del producto")
        self.sale_quantity = fields.add_field("Cantidad", default="1")
        actions = ActionBar(form)
        actions.pack(fill="x")
        actions.add("Agregar al carrito", self.add_cart_item)
        actions.add("Registrar venta", self.register_sale_ui, "Accent.TButton")
        actions.add("Vaciar carrito", self.clear_cart, "Danger.TButton")

        resumen = ttk.Frame(body)
        resumen.pack(fill="both", expand=True, pady=(12, 0))
        resumen.columnconfigure(0, weight=3, uniform="r")
        resumen.columnconfigure(1, weight=2, uniform="r")
        cart_frame = ttk.LabelFrame(resumen, text="Carrito", padding=(0, 12, 0, 0))
        cart_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 18))
        self.cart_tree = make_tree(cart_frame, ("id", "codigo", "producto", "cantidad", "precio", "promo", "subtotal"), height=6)
        ticket_frame = ttk.LabelFrame(resumen, text="Resumen y ticket", padding=(0, 12, 0, 0))
        ticket_frame.grid(row=0, column=1, sticky="nsew")
        self.ticket_text = tk.Text(ticket_frame, height=7, width=1, wrap="word", bg="#FFFFFF", fg="#223247",
                                   relief="flat", borderwidth=0, padx=16, pady=14, font=("Segoe UI", 10))
        self.ticket_text.pack(fill="both", expand=True)

        inv = ttk.LabelFrame(body, text="Inventario de la tienda (se actualiza solo)", padding=(0, 12, 0, 0))
        inv.pack(fill="both", expand=True, pady=(12, 0))
        self.inventory_tree = make_tree(inv, COLUMNAS_INVENTARIO, height=10)
        self.sondear()
        self._recibir()

    # ------------------------------------------------------------------ sondeo de inventario
    def sondear(self):
        """Pide el inventario en un hilo (sin congelar la pantalla) y se reprograma cada SONDEO_MS."""
        if not self._consultando:
            self._consultando = True
            threading.Thread(target=self._consultar_inventario, daemon=True).start()
        self._sondeo_id = self.after(SONDEO_MS, self.sondear)

    def _consultar_inventario(self):
        try:
            self._respuestas.put(("ok", self.cliente.inventario()))
        except ErrorLAN as e:
            self._respuestas.put(("error", e))

    def _recibir(self):
        try:
            while True:
                tipo, dato = self._respuestas.get_nowait()
                self._consultando = False
                if tipo == "ok":
                    self.aplicar_inventario(dato)
                    self.estado.set("Conectada · inventario al día")
                elif dato.codigo == "UNAUTHENTICATED":
                    self.show_login()
                    return
                else:
                    self.estado.set(f"Sin conexión: {dato.mensaje}")
        except queue.Empty:
            pass
        self.after(100, self._recibir)

    def aplicar_inventario(self, productos):
        self.carrito.cargar_inventario(productos)
        if self.inventory_tree is None or not self.inventory_tree.winfo_exists():
            return
        visibles = set(self.inventory_tree.get_children())
        for index, p in enumerate(productos):
            iid = str(p["id"])
            valores = [p[c] for c in COLUMNAS_INVENTARIO]
            if self.inventory_tree.exists(iid):
                self.inventory_tree.item(iid, values=valores)
                self.inventory_tree.move(iid, "", index)
            else:
                self.inventory_tree.insert("", index, iid=iid, values=valores)
            visibles.discard(iid)
        for iid in visibles:
            self.inventory_tree.delete(iid)

    # ------------------------------------------------------------------------------ venta
    def add_cart_item(self):
        try:
            self.carrito.agregar(self.sale_product_code.get(), self.sale_quantity.get() or 1)
            self.sale_product_code.delete(0, tk.END)
            self.sale_quantity.delete(0, tk.END)
            self.sale_quantity.insert(0, "1")
            self.refresh_cart()
        except ValueError as e:
            messagebox.showerror("Carrito", str(e), parent=self)

    def refresh_cart(self):
        for item in self.cart_tree.get_children():
            self.cart_tree.delete(item)
        for line in self.carrito.lineas():
            self.cart_tree.insert("", tk.END, values=(
                line["id"], line["code"], line["name"], line["quantity"],
                dinero(line["unit_price"]), f"{line['promo']:g}%", dinero(line["line_total"])))
        try:
            subtotal, _, total = self.carrito.totales(self.sale_discount.get())
        except ValueError:
            subtotal, _, total = self.carrito.totales(0)
        self.ticket_text.delete("1.0", tk.END)
        self.ticket_text.insert(tk.END, f"Subtotal con promociones: {dinero(subtotal)}\n"
                                        f"Total estimado: {dinero(total)}\n")

    def register_sale_ui(self):
        try:
            customer = self.sale_customer_id.get().strip()
            r = self.carrito.registrar(int(customer) if customer else None,
                                       self.sale_payment.get(), self.sale_discount.get())
        except ValueError as e:
            messagebox.showerror("Venta", str(e), parent=self)
            return
        except ErrorLAN as e:
            if e.codigo == "UNAUTHENTICATED":
                messagebox.showerror("Venta", e.mensaje, parent=self)
                self.show_login()
                return
            aviso = (" No se sabe si la venta quedó guardada; vuelve a presionar «Registrar venta» "
                     "para confirmarla sin duplicarla.") if e.incierto else ""
            messagebox.showerror("Venta", e.mensaje + aviso, parent=self)
            return
        self.refresh_cart()
        self.ticket_text.delete("1.0", tk.END)
        self.ticket_text.insert(tk.END,
                                f"VENTA REGISTRADA\nTicket: {r['sale_id']}\nFecha: {r['fecha']}\n"
                                f"Subtotal: {dinero(r['subtotal'])}\nDescuento: {dinero(r['descuento'])}\n"
                                f"Total: {dinero(r['total'])}\nMetodo: {r['metodo_pago']}\n")
        self.aplicar_inventario(list(self.carrito.productos.values()))
        messagebox.showinfo("Venta", f"Venta registrada con ticket {r['sale_id']}.", parent=self)

    def clear_cart(self):
        try:
            self.carrito.vaciar()
        except ValueError as e:
            messagebox.showerror("Carrito", str(e), parent=self)
            return
        self.refresh_cart()
        self.ticket_text.delete("1.0", tk.END)
