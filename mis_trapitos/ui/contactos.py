"""Interfaz modular de contactos y usuarios de Mis Trapitos.

Agrupa Clientes, Proveedores y Empleados en un solo módulo, siguiendo el
mismo patrón que ui_productos.py: recibe la base de datos ya abierta por
la aplicación y no crea conexiones ni importa el punto de entrada. Las
transacciones siguen a cargo de Database.
"""

import urllib.parse
import webbrowser
from tkinter import messagebox, ttk
import tkinter as tk
from utils import dinero, today_text
from mis_trapitos.ui.base import ActionBar, FormGrid, ScrollablePage, make_tree





def dinero(value):
    try:
        return f"${float(value):,.2f}"
    except Exception:
        return "$0.00"


class ContactosUI(ttk.Frame):
    """Pestaña de contactos y usuarios con estado propio y actualización explícita."""

    def __init__(self, parent, db):
        super().__init__(parent, padding=0)
        self.db = db
        self.selected_customer_id = None
        self.selected_supplier_id = None
        self.selected_employee_id = None
        self._build_widgets()

    _make_tree = staticmethod(make_tree)

    @staticmethod
    def _tree_clear(tree):
        for item in tree.get_children():
            tree.delete(item)

    @staticmethod
    def _set_entries(entries, values):
        for entry, value in zip(entries, values):
            entry.delete(0, tk.END)
            entry.insert(0, "" if value is None else str(value))

    def _build_widgets(self):
        self.notebook = ttk.Notebook(self)
        nb = self.notebook
        nb.pack(fill="both", expand=True)
        self._build_customers_tab(nb)
        self._build_suppliers_tab(nb)
        self._build_employees_tab(nb)

    # ---------------------------- Clientes ----------------------------

    def _build_customers_tab(self, nb):
        tab = ScrollablePage(nb, padding=0)
        nb.add(tab, text="Clientes")
        form = ttk.LabelFrame(tab.body, text="Datos del cliente", padding=(0, 10))
        form.pack(fill="x")
        fields = FormGrid(form, columns=2, min_column_width=220)
        fields.pack(fill="x")
        self.c_name = fields.add_field("Nombre")
        self.c_phone = fields.add_field("Teléfono")
        self.c_email = fields.add_field("Correo")
        self.c_address = fields.add_field("Dirección")
        self.c_region = fields.add_field("Ciudad / región")
        self.c_preferences = fields.add_field("Preferencias")
        actions = ActionBar(form)
        actions.pack(fill="x", pady=(10, 0))
        actions.add("Guardar cliente", self.save_customer_ui, style="Accent.TButton")
        actions.add("Limpiar", self.clear_customer_form)
        actions.add("Ver historial", self.show_customer_history)
        actions.add("Correo profesional", self.show_customer_email)
        table = ttk.LabelFrame(tab.body, text="Clientes registrados", padding=(0, 10))
        table.pack(fill="both", expand=True, pady=(12, 0))
        self.customers_tree = self._make_tree(
            table, ("id", "nombre", "telefono", "correo", "region", "preferencias"), height=6
        )
        self.customers_tree.bind("<<TreeviewSelect>>", self.load_customer_selected)
        self.refresh_customers()

    def save_customer_ui(self):
        try:
            if not self.c_name.get().strip():
                raise ValueError("El nombre es obligatorio.")
            data = (
                self.c_name.get().strip(), self.c_phone.get().strip(),
                self.c_email.get().strip(), self.c_address.get().strip(),
                self.c_region.get().strip(), self.c_preferences.get().strip(),
            )
            self.selected_customer_id = self.db.save_customer(self.selected_customer_id, data)
            self.refresh_customers()
            messagebox.showinfo("Clientes", "Cliente guardado.", parent=self)
        except Exception as e:
            messagebox.showerror("Clientes", str(e), parent=self)

    def refresh_customers(self):
        rows = self.db.query(
            """SELECT id, name AS nombre, phone AS telefono, email AS correo,
                      city_region AS region, preferences AS preferencias
               FROM customers ORDER BY id DESC"""
        )
        self._tree_clear(self.customers_tree)
        for row in rows:
            self.customers_tree.insert("", tk.END, values=[row[key] for key in row.keys()])

    def load_customer_selected(self, event=None):
        sel = self.customers_tree.selection()
        if not sel:
            return
        customer_id = self.customers_tree.item(sel[0], "values")[0]
        row = self.db.one("SELECT * FROM customers WHERE id=?", (customer_id,))
        if not row:
            return
        self.selected_customer_id = row["id"]
        self._set_entries(
            [self.c_name, self.c_phone, self.c_email, self.c_address, self.c_region, self.c_preferences],
            [row["name"], row["phone"], row["email"], row["address"], row["city_region"], row["preferences"]],
        )

    def clear_customer_form(self):
        self.selected_customer_id = None
        for entry in [self.c_name, self.c_phone, self.c_email, self.c_address, self.c_region, self.c_preferences]:
            entry.delete(0, tk.END)

    def show_customer_history(self):
        try:
            if not self.selected_customer_id:
                raise ValueError("Selecciona un cliente.")
            rows = self.db.customer_history(self.selected_customer_id)
            win = tk.Toplevel(self)
            win.title("Historial de cliente")
            win.geometry("960x600")
            win.minsize(560, 360)
            frame = ttk.Frame(win, padding=18)
            frame.pack(fill="both", expand=True)
            frame.rowconfigure(0, weight=1)
            frame.columnconfigure(0, weight=1)
            text = tk.Text(
                frame, width=1, height=1, wrap="word", bg="#FFFFFF", fg="#263445",
                font=("Segoe UI", 10), relief="flat", borderwidth=0,
                highlightthickness=0, padx=12, pady=12,
            )
            scrollbar = ttk.Scrollbar(frame, orient="vertical", command=text.yview)
            text.configure(yscrollcommand=scrollbar.set)
            text.grid(row=0, column=0, sticky="nsew")
            scrollbar.grid(row=0, column=1, sticky="ns")
            if not rows:
                text.insert(tk.END, "Sin compras registradas.")
            for row in rows:
                text.insert(
                    tk.END,
                    f"Venta {row['venta']} | {row['fecha']} | {row['codigo']} {row['producto']} | "
                    f"Cantidad {row['cantidad']} | Linea {dinero(row['total_linea'])} | "
                    f"Total venta {dinero(row['total_venta'])} | {row['estado']}\n",
                )
        except Exception as e:
            messagebox.showerror("Historial", str(e), parent=self)

    def build_customer_email_content(self, customer_id):
        customer = self.db.one("SELECT * FROM customers WHERE id=?", (customer_id,))
        if not customer:
            raise ValueError("Cliente no encontrado.")
        stats = self.db.one(
            """SELECT COUNT(*) AS compras, COALESCE(SUM(total),0) AS total, MAX(sale_datetime) AS ultima
               FROM sales WHERE customer_id=? AND status='ACTIVA'""",
            (customer_id,),
        )
        favorite = self.db.one(
            """SELECT p.name AS producto, SUM(si.quantity) AS piezas FROM sales s
               JOIN sale_items si ON si.sale_id=s.id JOIN products p ON p.id=si.product_id
               WHERE s.customer_id=? AND s.status='ACTIVA' GROUP BY p.id ORDER BY piezas DESC LIMIT 1""",
            (customer_id,),
        )
        name = customer["name"] or "cliente"
        first_name = name.split()[0] if name.split() else name
        preferences = customer["preferences"] or ""
        compras = int(stats["compras"] or 0) if stats else 0
        total = float(stats["total"] or 0) if stats else 0
        ultima = stats["ultima"] if stats else ""
        subject = "Gracias por su preferencia en Mis trapitos"
        lines = []
        lines.append(f"Estimado/a {first_name}:")
        lines.append("")
        lines.append(
            "Esperamos que se encuentre muy bien. En Mis trapitos queremos agradecerle sinceramente "
            "su preferencia y la confianza que ha depositado en nuestra tienda."
        )
        if compras > 0:
            lines.append(
                f"De acuerdo con su historial, contamos con {compras} compra(s) registrada(s) a su "
                f"nombre, por un total acumulado de {dinero(total)}."
            )
            if ultima:
                lines.append(f"Su compra mas reciente fue registrada el {ultima}.")
        if favorite:
            lines.append(f"Tambien identificamos que uno de los productos que mas ha adquirido es: {favorite['producto']}.")
        if preferences:
            lines.append(f"Tomaremos en cuenta sus preferencias registradas: {preferences}.")
        lines.append(
            "Queremos invitarle a visitarnos nuevamente para conocer nuestras prendas disponibles, "
            "promociones vigentes y nuevas opciones de temporada."
        )
        lines.append(
            "Si desea consultar disponibilidad, tallas, colores o recibir atencion personalizada, "
            "con gusto podemos apoyarle por este mismo medio."
        )
        lines.append("")
        lines.append("Quedamos atentos a cualquier duda o solicitud.")
        lines.append("")
        lines.append("Atentamente,")
        lines.append("Mis trapitos")
        lines.append("Tienda de ropa")
        return customer, subject, "\n".join(lines)

    def show_customer_email(self):
        try:
            if not self.selected_customer_id:
                raise ValueError("Selecciona un cliente.")
            customer, subject, body = self.build_customer_email_content(self.selected_customer_id)
            win = tk.Toplevel(self)
            win.title("Correo profesional para cliente")
            win.geometry("820x560")
            win.minsize(560, 400)
            frame = ttk.Frame(win, padding=18)
            frame.pack(fill="both", expand=True)
            ttk.Label(
                frame, text=f"Para: {customer['email'] or 'Sin correo registrado'}",
                font=("Segoe UI", 11, "bold"),
            ).pack(anchor="w", pady=(0, 14))
            ttk.Label(frame, text="Asunto").pack(anchor="w", pady=(0, 4))
            subject_entry = ttk.Entry(frame)
            subject_entry.pack(fill="x", pady=(0, 12))
            subject_entry.insert(0, subject)
            ttk.Label(frame, text="Mensaje").pack(anchor="w", pady=(0, 4))
            message_frame = ttk.Frame(frame)
            message_frame.pack(fill="both", expand=True)
            message_frame.rowconfigure(0, weight=1)
            message_frame.columnconfigure(0, weight=1)
            text = tk.Text(
                message_frame, width=1, height=12, wrap="word", bg="#FFFFFF", fg="#263445",
                font=("Segoe UI", 10), relief="flat", borderwidth=0,
                highlightthickness=0, padx=12, pady=12,
            )
            scrollbar = ttk.Scrollbar(message_frame, orient="vertical", command=text.yview)
            text.configure(yscrollcommand=scrollbar.set)
            text.grid(row=0, column=0, sticky="nsew")
            scrollbar.grid(row=0, column=1, sticky="ns")
            text.insert(tk.END, body)
            buttons = ActionBar(frame)
            buttons.pack(fill="x", pady=(14, 0))

            def copy_email():
                content = f"Asunto: {subject_entry.get().strip()}\n\n{text.get('1.0', tk.END).strip()}"
                self.clipboard_clear()
                self.clipboard_append(content)
                messagebox.showinfo("Correo", "Correo copiado al portapapeles.", parent=win)

            def open_email_client():
                email = customer["email"] or ""
                if not email.strip():
                    raise ValueError("El cliente no tiene correo registrado.")
                mailto = (
                    "mailto:" + urllib.parse.quote(email.strip())
                    + "?subject=" + urllib.parse.quote(subject_entry.get().strip())
                    + "&body=" + urllib.parse.quote(text.get("1.0", tk.END).strip())
                )
                webbrowser.open(mailto)

            def open_email_client_safe():
                try:
                    open_email_client()
                except Exception as e:
                    messagebox.showerror("Correo", str(e), parent=win)

            buttons.add("Abrir en correo", open_email_client_safe, style="Accent.TButton")
            buttons.add("Copiar correo", copy_email)
            buttons.add("Cerrar", win.destroy)
        except Exception as e:
            messagebox.showerror("Correo", str(e), parent=self)

    # ---------------------------- Proveedores ----------------------------

    def _build_suppliers_tab(self, nb):
        tab = ScrollablePage(nb, padding=0)
        nb.add(tab, text="Proveedores")
        form = ttk.LabelFrame(tab.body, text="Datos del proveedor", padding=(0, 10))
        form.pack(fill="x")
        fields = FormGrid(form, columns=2, min_column_width=220)
        fields.pack(fill="x")
        self.s_name = fields.add_field("Nombre")
        self.s_phone = fields.add_field("Teléfono")
        self.s_address = fields.add_field("Dirección")
        self.s_products = fields.add_field("Productos suministrados")
        self.s_last_order = fields.add_field("Último pedido", default=today_text())
        actions = ActionBar(form)
        actions.pack(fill="x", pady=(10, 0))
        actions.add("Guardar proveedor", self.save_supplier_ui, style="Accent.TButton")
        actions.add("Limpiar", self.clear_supplier_form)
        table = ttk.LabelFrame(tab.body, text="Proveedores registrados", padding=(0, 10))
        table.pack(fill="both", expand=True, pady=(12, 0))
        self.suppliers_tree = self._make_tree(
            table, ("id", "nombre", "telefono", "direccion", "suministra", "ultimo_pedido"), height=6
        )
        self.suppliers_tree.bind("<<TreeviewSelect>>", self.load_supplier_selected)
        self.refresh_suppliers()

    def save_supplier_ui(self):
        try:
            if not self.s_name.get().strip():
                raise ValueError("El nombre es obligatorio.")
            data = (
                self.s_name.get().strip(), self.s_phone.get().strip(),
                self.s_address.get().strip(), self.s_products.get().strip(),
                self.s_last_order.get().strip() or today_text(),
            )
            self.selected_supplier_id = self.db.save_supplier(self.selected_supplier_id, data)
            self.refresh_suppliers()
            messagebox.showinfo("Proveedores", "Proveedor guardado.", parent=self)
        except Exception as e:
            messagebox.showerror("Proveedores", str(e), parent=self)

    def refresh_suppliers(self):
        rows = self.db.query(
            """SELECT id, name AS nombre, phone AS telefono, address AS direccion,
                      products_supplied AS suministra, last_order_date AS ultimo_pedido
               FROM suppliers ORDER BY id DESC"""
        )
        self._tree_clear(self.suppliers_tree)
        for row in rows:
            self.suppliers_tree.insert("", tk.END, values=[row[key] for key in row.keys()])

    def load_supplier_selected(self, event=None):
        sel = self.suppliers_tree.selection()
        if not sel:
            return
        supplier_id = self.suppliers_tree.item(sel[0], "values")[0]
        row = self.db.one("SELECT * FROM suppliers WHERE id=?", (supplier_id,))
        if not row:
            return
        self.selected_supplier_id = row["id"]
        self._set_entries(
            [self.s_name, self.s_phone, self.s_address, self.s_products, self.s_last_order],
            [row["name"], row["phone"], row["address"], row["products_supplied"], row["last_order_date"]],
        )

    def clear_supplier_form(self):
        self.selected_supplier_id = None
        for entry in [self.s_name, self.s_phone, self.s_address, self.s_products, self.s_last_order]:
            entry.delete(0, tk.END)
        self.s_last_order.insert(0, today_text())

    # ---------------------------- Empleados ----------------------------

    def _build_employees_tab(self, nb):
        tab = ScrollablePage(nb, padding=0)
        nb.add(tab, text="Empleados")
        form = ttk.LabelFrame(tab.body, text="Datos del empleado", padding=(0, 10))
        form.pack(fill="x")
        fields = FormGrid(form, columns=2, min_column_width=220)
        fields.pack(fill="x")
        self.e_name = fields.add_field("Nombre")
        self.e_username = fields.add_field("Usuario")
        self.e_password = fields.add_field("Contraseña")
        self.e_role = fields.add_field("Rol")
        actions = ActionBar(form)
        actions.pack(fill="x", pady=(10, 0))
        actions.add("Guardar empleado", self.save_employee_ui, style="Accent.TButton")
        actions.add("Limpiar", self.clear_employee_form)
        table = ttk.LabelFrame(tab.body, text="Empleados registrados", padding=(0, 10))
        table.pack(fill="both", expand=True, pady=(12, 0))
        self.employees_tree = self._make_tree(table, ("id", "nombre", "usuario", "rol"), height=6)
        self.employees_tree.bind("<<TreeviewSelect>>", self.load_employee_selected)
        self.refresh_employees()

    def save_employee_ui(self):
        try:
            if not self.e_name.get().strip() or not self.e_username.get().strip():
                raise ValueError("Nombre y usuario son obligatorios.")
            self.selected_employee_id = self.db.save_employee(
                self.selected_employee_id,
                self.e_name.get().strip(),
                self.e_username.get().strip(),
                self.e_password.get().strip(),
                self.e_role.get().strip() or "Ventas",
            )
            self.refresh_employees()
            messagebox.showinfo("Empleados", "Empleado guardado.", parent=self)
        except Exception as e:
            messagebox.showerror("Empleados", str(e), parent=self)

    def refresh_employees(self):
        rows = self.db.query(
            "SELECT id, name AS nombre, username AS usuario, role AS rol FROM employees ORDER BY id DESC"
        )
        self._tree_clear(self.employees_tree)
        for row in rows:
            self.employees_tree.insert("", tk.END, values=[row[key] for key in row.keys()])

    def load_employee_selected(self, event=None):
        sel = self.employees_tree.selection()
        if not sel:
            return
        employee_id = self.employees_tree.item(sel[0], "values")[0]
        row = self.db.one("SELECT * FROM employees WHERE id=?", (employee_id,))
        if not row:
            return
        self.selected_employee_id = row["id"]
        self._set_entries(
            [self.e_name, self.e_username, self.e_password, self.e_role],
            [row["name"], row["username"], "", row["role"]],
        )

    def clear_employee_form(self):
        self.selected_employee_id = None
        for entry in [self.e_name, self.e_username, self.e_password, self.e_role]:
            entry.delete(0, tk.END)
