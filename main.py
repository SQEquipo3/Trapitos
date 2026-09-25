import tkinter as tk
from tkinter import ttk, messagebox

from mis_trapitos_app_v7 import App, Database, DB_NAME


def iniciar_sesion():
    nombre = entrada_usuario.get().strip()
    clave = entrada_contrasena.get().strip()

    # Comprobar los datos usando la base de datos del sistema.
    db = Database(DB_NAME)
    try:
        usuario = db.authenticate(nombre, clave)
    finally:
        db.close()

    if not usuario:
        messagebox.showerror(
            "Acceso",
            "Usuario o contraseña incorrectos.",
            parent=ventana_login
        )
        return

    # Si los datos son correctos, cerrar el login y abrir la aplicación.
    ventana_login.destroy()

    app = App()
    app.user = usuario
    app.show_main()
    app.mainloop()


ventana_login = tk.Tk()
ventana_login.title("Mis trapitos - Inicio de sesión")
ventana_login.geometry("420x300")
ventana_login.resizable(False, False)

contenedor = ttk.Frame(ventana_login, padding=25)
contenedor.pack(expand=True)

ttk.Label(
    contenedor,
    text="Mis trapitos",
    font=("Arial", 22, "bold")
).grid(row=0, column=0, columnspan=2, pady=(0, 10))

ttk.Label(
    contenedor,
    text="Ingresa tus credenciales"
).grid(row=1, column=0, columnspan=2, pady=(0, 15))

ttk.Label(contenedor, text="Usuario").grid(
    row=2, column=0, sticky="e", padx=8, pady=5
)
entrada_usuario = ttk.Entry(contenedor, width=25)
entrada_usuario.grid(row=2, column=1, pady=5)
entrada_usuario.insert(0, "admin")

ttk.Label(contenedor, text="Contraseña").grid(
    row=3, column=0, sticky="e", padx=8, pady=5
)
entrada_contrasena = ttk.Entry(contenedor, width=25, show="*")
entrada_contrasena.grid(row=3, column=1, pady=5)

ttk.Button(
    contenedor,
    text="Entrar",
    command=iniciar_sesion
).grid(row=4, column=0, columnspan=2, pady=18)

ventana_login.bind("<Return>", lambda event: iniciar_sesion())
ventana_login.mainloop()
