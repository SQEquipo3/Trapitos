""" Login page"""

from tkinter import messagebox, ttk


class Login(ttk.Frame):
    def __init__(self, parent, authenticate, on_authenticated):
        super().__init__(parent, style="Login.TFrame", padding=35)
        self._authenticate = authenticate
        self._on_authenticated = on_authenticated
        self.columnconfigure(1, weight=1)
        ttk.Label(self, text="Mis trapitos", style="Brand.TLabel").grid(
            row=0, column=0, columnspan=2, pady=(0, 3)
        )
        ttk.Label(
            self,
            text="Gestión local de inventario y ventas",
            style="Muted.TLabel",
        ).grid(row=1, column=0, columnspan=2, pady=(0, 22))
        card = ttk.LabelFrame(self, text="Acceso al sistema", padding=22)
        card.grid(row=2, column=0, columnspan=2, sticky="ew")
        card.columnconfigure(1, weight=1)
        ttk.Label(card, text="Usuario").grid(
            row=0, column=0, sticky="e", padx=(0, 10), pady=7
        )
        self.username_entry = ttk.Entry(card, width=30)
        self.username_entry.grid(row=0, column=1, sticky="ew", padx=(0, 2), pady=7)
        self.username_entry.insert(0, "admin")
        ttk.Label(card, text="Contraseña").grid(
            row=1, column=0, sticky="e", padx=(0, 10), pady=7
        )
        self.password_entry = ttk.Entry(card, width=30, show="*")
        self.password_entry.grid(row=1, column=1, sticky="ew", padx=(0, 2), pady=7)
        ttk.Label(
            self,
            text="Las credenciales se validan en la base local.",
            style="Muted.TLabel",
        ).grid(row=3, column=0, columnspan=2, pady=(12, 8))
        self.submit_button = ttk.Button(
            self, text="Entrar", style="Accent.TButton", command=self.submit
        )
        self.submit_button.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(2, 0))
        self.username_entry.bind("<Return>", self.submit)
        self.password_entry.bind("<Return>", self.submit)

    def submit(self, event=None):
        user = self._authenticate(
            self.username_entry.get().strip(), self.password_entry.get().strip()
        )
        if not user:
            messagebox.showerror(
                "Acceso", "Usuario o contraseña incorrectos.", parent=self
            )
            self.password_entry.focus_set()
            self.password_entry.selection_range(0, "end")
            return "break"
        self._on_authenticated(user)
        return "break"
