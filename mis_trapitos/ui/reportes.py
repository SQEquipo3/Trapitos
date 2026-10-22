import csv
import tkinter as tk

from tkinter import filedialog, messagebox, ttk

from mis_trapitos.ui.base import (
    ActionBar,
    FormGrid,
    ScrollablePage,
    configure_tree_columns,
    make_tree,
)

from mis_trapitos.data.repositories import reportes as reportes_repo


REPORTS = [
    "Inventario general actualizado",
    "Productos con stock bajo",
    "Ventas diarias, semanales y mensuales",
    "Ventas por producto",
    "Ventas por metodo de pago",
    "Ventas por empleado",
    "Productos mas vendidos",
    "Productos menos vendidos",
    "Entradas de mercancia",
    "Clientes frecuentes",
    "Resumen de utilidades",
    "Productos devueltos o cancelados",
    "Productos disponibles por categoria",
    "Productos en oferta",
    "Metodos de pago mas utilizados",
    "Productos mas vendidos ultimo mes",
    "Ventas ultimos tres dias",
    "Productos de proveedor especifico",
    "Productos comprados mas de una vez por cliente",
    "Productos vendidos por categoria ultimo mes",
    "Productos con precio superior y existencias",
    "Producto con mayor descuento vigente",
    "Compras por ciudad o region",
    "Productos no vendidos ultimos tres meses",
]


class ReportesUI(ScrollablePage):

    def __init__(self, parent, db):
        super().__init__(parent)

        self.db = db
        self.last_report_rows = []

        self.make_reports_tab()

    def make_reports_tab(self):
        # Crear los controles de la pantalla.
        controls = ttk.LabelFrame(
            self.body,
            text="Consulta de reportes",
            padding=(0, 12),
        )
        controls.pack(fill="x")

        fields = FormGrid(
            controls,
            columns=2,
            min_column_width=290,
        )
        fields.pack(fill="x")

        self.report_combo = fields.add_combo(
            "Reporte",
            REPORTS,
        )
        self.report_combo.set(REPORTS[0])

        self.report_param = fields.add_field("Parámetro")

        self.report_hint = ttk.Label(
            controls,
            text=(
                "El parámetro se utiliza para filtrar por categoría, "
                "proveedor, cliente, precio o stock bajo."
            ),
            style="Muted.TLabel",
            wraplength=650,
        )
        self.report_hint.pack(fill="x", pady=(0, 14))

        controls.bind(
            "<Configure>",
            lambda event: self._wrap_label(
                self.report_hint,
                event.width,
            ),
        )

        # Botones de acciones.
        actions = ActionBar(controls)
        actions.pack(fill="x")

        actions.add(
            "Ejecutar reporte",
            self.run_report,
            "Accent.TButton",
        )
        actions.add(
            "Exportar CSV",
            self.export_report_csv,
        )

        # Tabla de resultados.
        table = ttk.LabelFrame(
            self.body,
            text="Resultados",
            padding=(0, 12, 0, 0),
        )
        table.pack(
            fill="both",
            expand=True,
            pady=(16, 0),
        )

        self.report_tree = make_tree(
            table,
            ("resultado",),
            height=8,
        )

        # Mostrar el reporte inicial.
        self.run_report()

    def run_report(self):
        try:
            rows = reportes_repo.ejecutar(
                self.db,
                self.report_combo.get(),
                self.report_param.get(),
            )

            self.last_report_rows = rows

            for item in self.report_tree.get_children():
                self.report_tree.delete(item)

            if not rows:
                configure_tree_columns(
                    self.report_tree,
                    ("mensaje",),
                )
                self.report_tree.insert(
                    "",
                    tk.END,
                    values=("Sin resultados",),
                )
                return

            columns = list(rows[0].keys())

            configure_tree_columns(
                self.report_tree,
                columns,
            )

            for row in rows:
                self.report_tree.insert(
                    "",
                    tk.END,
                    values=[row[col] for col in columns],
                )

        except Exception as e:
            messagebox.showerror("Reporte", str(e))

    def export_report_csv(self):
        rows = self.last_report_rows

        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv")],
        )

        if not path:
            return

        with open(
            path,
            "w",
            newline="",
            encoding="utf-8",
        ) as f:
            writer = csv.writer(f)

            if rows:
                writer.writerow(rows[0].keys())

                for row in rows:
                    writer.writerow(
                        [row[key] for key in row.keys()]
                    )

        messagebox.showinfo(
            "Exportar",
            f"Reporte exportado en:\n{path}",
        )

    def _wrap_label(self, label, width):
        # Conserva el comportamiento original de app.py.
        # Si ya tienes este helper en base.py, utiliza ese
        # helper compartido en lugar de duplicar el método.
        label.configure(wraplength=max(100, width - 20))