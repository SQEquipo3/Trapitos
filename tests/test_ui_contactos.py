"""Pruebas de la pantalla de contactos con Tk real y SQLite temporal (#91)."""

from types import SimpleNamespace
import tkinter as tk
from tkinter import ttk
from unittest.mock import Mock
from urllib.parse import parse_qs, unquote, urlsplit

import pytest

from mis_trapitos.data.repositories import clientes, empleados, proveedores
from mis_trapitos.services import devoluciones, ventas
from mis_trapitos.ui import contactos
from tests.tc import tc
from utils import today_text


@pytest.fixture
def screen(db, monkeypatch, contacts_root):
    """Aísla diálogos, navegador y portapapeles; conserva widgets y persistencia reales."""
    admin_id = empleados.guardar(db, None, "Administradora", "admin", "clave", "Propietario")
    root = contacts_root
    state = SimpleNamespace(root=root, db=db, user=empleados.obtener_por_id(db, admin_id),
                            errors=Mock(), info=Mock(), browser=Mock(return_value=True),
                            clipboard_clear=Mock(), clipboard_append=Mock(), windows=[], callbacks=[])
    monkeypatch.setattr(root, "report_callback_exception", lambda *args: state.callbacks.append(args))
    original_toplevel = tk.Toplevel

    def hidden_window(*args, **kwargs):
        window = original_toplevel(*args, **kwargs)
        window.withdraw()
        state.windows.append(window)
        return window

    monkeypatch.setattr(contactos.tk, "Toplevel", hidden_window)
    monkeypatch.setattr(contactos.messagebox, "showerror", state.errors)
    monkeypatch.setattr(contactos.messagebox, "showinfo", state.info)
    monkeypatch.setattr(contactos.webbrowser, "open", state.browser)
    try:
        state.ui = contactos.ContactosUI(root, db, lambda: state.user)
        state.ui.pack(fill="both", expand=True)
        monkeypatch.setattr(state.ui, "clipboard_clear", state.clipboard_clear)
        monkeypatch.setattr(state.ui, "clipboard_append", state.clipboard_append)
        yield state
        assert state.callbacks == [], "Falló un callback de la pantalla de contactos."
    finally:
        if hasattr(state, "ui"):
            state.ui.destroy()
        root.update_idletasks()


@pytest.fixture(scope="module")
def contacts_root():
    """Un intérprete Tk; cada caso recibe una pantalla y una base independientes."""
    root = tk.Tk()
    root.withdraw()
    try:
        yield root
    finally:
        root.destroy()


def descendants(parent):
    for child in parent.winfo_children():
        yield child
        yield from descendants(child)


def click(parent, caption):
    button = next(widget for widget in descendants(parent)
                  if isinstance(widget, ttk.Button) and widget.cget("text") == caption)
    button.invoke()


def tab(screen, index):
    return screen.ui.nametowidget(screen.ui.notebook.tabs()[index])


def fill(screen, **values):
    for name, value in values.items():
        entry = getattr(screen.ui, name)
        entry.delete(0, tk.END)
        entry.insert(0, value)


def select(screen, tree, record_id):
    item = next(item for item in tree.get_children() if int(tree.item(item, "values")[0]) == record_id)
    tree.selection_set(item)
    screen.root.update()  # Dispara el enlace real <<TreeviewSelect>>.


def snapshot(db, table):
    return [dict(row) for row in db.query(f"SELECT * FROM {table} ORDER BY id")]


def text_widget(window):
    return next(widget for widget in descendants(window) if isinstance(widget, tk.Text))


@tc("STS_CON_01", nivel="STS", modulo="contactos", reqs=["RF-11", "RF-12"],
    nombre="Alta, selección, edición y limpieza de clientes desde la pantalla")
def test_cliente_se_guarda_carga_edita_y_limpia(screen):
    """El formulario y la tabla de clientes reflejan los datos persistidos.

    Precondiciones: ContactosUI con widgets Tk reales y base temporal sin ejemplos.
    Pasos:
    - Guardar un cliente con todos sus campos y espacios alrededor del nombre.
    - Limpiar, seleccionar su fila y editar nombre y preferencias.
    - Limpiar de nuevo y registrar otro cliente.
    Esperado:
    - Los campos se recortan y persisten; la selección recupera la ficha completa.
    - La edición conserva el ID y refresca la tabla sin duplicados.
    - Limpiar vacía los campos y permite crear otro cliente sin alterar el anterior.
    """
    ui = screen.ui
    fill(screen, c_name="  Ana López  ", c_phone="555-0101", c_email="ana@example.test",
         c_address="Calle 1", c_region="Guadalajara", c_preferences="Vestidos")
    click(tab(screen, 0), "Guardar cliente")
    customer_id = ui.selected_customer_id
    saved = clientes.obtener_por_id(screen.db, customer_id)
    assert tuple(saved[key] for key in ("name", "phone", "email", "address", "city_region", "preferences")) == (
        "Ana López", "555-0101", "ana@example.test", "Calle 1", "Guadalajara", "Vestidos")
    click(tab(screen, 0), "Limpiar")
    fields = (ui.c_name, ui.c_phone, ui.c_email, ui.c_address, ui.c_region, ui.c_preferences)
    assert ui.selected_customer_id is None
    assert [entry.get() for entry in fields] == [""] * 6
    select(screen, ui.customers_tree, customer_id)
    assert ui.selected_customer_id == customer_id
    assert [entry.get() for entry in fields] == [
        "Ana López", "555-0101", "ana@example.test", "Calle 1", "Guadalajara", "Vestidos"]
    fill(screen, c_name="Ana Pérez", c_preferences="Blusas")
    click(tab(screen, 0), "Guardar cliente")
    assert screen.db.scalar("SELECT COUNT(*) FROM customers") == 1
    assert clientes.obtener_por_id(screen.db, customer_id)["preferences"] == "Blusas"
    assert ui.customers_tree.item(ui.customers_tree.get_children()[0], "values")[1] == "Ana Pérez"
    click(tab(screen, 0), "Limpiar")
    fill(screen, c_name="Beatriz")
    click(tab(screen, 0), "Guardar cliente")
    assert ui.selected_customer_id != customer_id
    assert len(ui.customers_tree.get_children()) == screen.db.scalar("SELECT COUNT(*) FROM customers") == 2
    assert clientes.obtener_por_id(screen.db, customer_id)["name"] == "Ana Pérez"
    screen.errors.assert_not_called()


@tc("STS_CON_02", nivel="STS", modulo="contactos", reqs=["RF-13", "RF-14"],
    nombre="Alta, edición y limpieza de proveedores desde la pantalla")
def test_proveedor_se_guarda_edita_y_restablece_fecha(screen):
    """La pantalla guarda y recupera proveedores, con fecha predeterminada al limpiar.

    Precondiciones: ContactosUI y base temporal; no hay proveedores.
    Pasos:
    - Guardar un proveedor con datos completos y fecha vacía.
    - Limpiar y seleccionar la fila para recuperar todos sus datos.
    - Editar dirección, productos y fecha; limpiar y registrar otro proveedor.
    Esperado:
    - La fecha vacía usa el día actual; la selección carga la ficha completa.
    - Se actualiza el mismo ID y la tabla muestra los cambios.
    - Limpiar quita la selección y los datos y restablece la fecha de hoy.
    """
    ui = screen.ui
    fill(screen, s_name="  Textiles Águila  ", s_phone="555-0202", s_address="Av. 2",
         s_products="Blusas", s_last_order="")
    click(tab(screen, 1), "Guardar proveedor")
    supplier_id = ui.selected_supplier_id
    saved = proveedores.obtener_por_id(screen.db, supplier_id)
    assert tuple(saved[key] for key in ("name", "phone", "address", "products_supplied", "last_order_date")) == (
        "Textiles Águila", "555-0202", "Av. 2", "Blusas", today_text())
    click(tab(screen, 1), "Limpiar")
    assert ui.selected_supplier_id is None
    assert [entry.get() for entry in (ui.s_name, ui.s_phone, ui.s_address, ui.s_products)] == [""] * 4
    assert ui.s_last_order.get() == today_text()
    select(screen, ui.suppliers_tree, supplier_id)
    assert ui.selected_supplier_id == supplier_id
    assert [entry.get() for entry in (ui.s_name, ui.s_phone, ui.s_address, ui.s_products, ui.s_last_order)] == [
        "Textiles Águila", "555-0202", "Av. 2", "Blusas", today_text()]
    fill(screen, s_address="Av. 3", s_products="Vestidos", s_last_order="2026-10-15")
    click(tab(screen, 1), "Guardar proveedor")
    assert screen.db.scalar("SELECT COUNT(*) FROM suppliers") == 1
    assert proveedores.obtener_por_id(screen.db, supplier_id)["address"] == "Av. 3"
    row = ui.suppliers_tree.item(ui.suppliers_tree.get_children()[0], "values")
    assert row[3:] == ("Av. 3", "Vestidos", "2026-10-15")
    click(tab(screen, 1), "Limpiar")
    fill(screen, s_name="Otro proveedor")
    click(tab(screen, 1), "Guardar proveedor")
    assert ui.selected_supplier_id != supplier_id
    assert len(ui.suppliers_tree.get_children()) == 2
    screen.errors.assert_not_called()


@tc("STS_CON_03", nivel="STS", modulo="contactos", reqs=["SEG-01"],
    nombre="Alta y edición de empleados sin exponer ni perder la contraseña")
def test_empleado_se_crea_edita_y_cambia_contrasena(screen):
    """Un propietario administra empleados desde los controles reales de Contactos.

    Precondiciones: Sesión de Propietario en una base temporal.
    Pasos:
    - Crear un empleado con contraseña explícita y rol vacío.
    - Limpiar, seleccionar la fila y editar el nombre con contraseña vacía.
    - Cambiar la contraseña y el rol, y limpiar el formulario.
    Esperado:
    - El rol predeterminado es Ventas; la selección no muestra la contraseña ni su hash.
    - La edición sin contraseña conserva la anterior y el mismo ID.
    - La contraseña nueva autentica y la antigua deja de funcionar; limpiar vacía la ficha.
    """
    ui = screen.ui
    fill(screen, e_name="  Luz García  ", e_username="  luz  ", e_password="inicial", e_role="")
    click(tab(screen, 2), "Guardar empleado")
    employee_id = ui.selected_employee_id
    assert empleados.autenticar(screen.db, "luz", "inicial")["role"] == "Ventas"
    click(tab(screen, 2), "Limpiar")
    select(screen, ui.employees_tree, employee_id)
    assert ui.selected_employee_id == employee_id
    assert [entry.get() for entry in (ui.e_name, ui.e_username, ui.e_password, ui.e_role)] == [
        "Luz García", "luz", "", "Ventas"]
    fill(screen, e_name="Luz Pérez")
    click(tab(screen, 2), "Guardar empleado")
    assert empleados.autenticar(screen.db, "luz", "inicial")["name"] == "Luz Pérez"
    fill(screen, e_password="renovada", e_role="Inventario")
    click(tab(screen, 2), "Guardar empleado")
    assert empleados.autenticar(screen.db, "luz", "inicial") is None
    assert empleados.autenticar(screen.db, "luz", "renovada")["role"] == "Inventario"
    assert ui.selected_employee_id == employee_id
    assert len(ui.employees_tree.get_children()) == screen.db.scalar("SELECT COUNT(*) FROM employees") == 2
    click(tab(screen, 2), "Limpiar")
    assert ui.selected_employee_id is None
    assert [entry.get() for entry in (ui.e_name, ui.e_username, ui.e_password, ui.e_role)] == [""] * 4
    screen.errors.assert_not_called()


@tc("STS_CON_04", nivel="STS", modulo="contactos", reqs=["RF-11", "RF-13", "SEG-01"],
    nombre="Validaciones de contactos preservan registros y permiten corregir la captura")
@pytest.mark.parametrize("index, caption, fields, table_name, message", [
    (0, "Guardar cliente", {"c_name": "  "}, "customers", "El nombre es obligatorio."),
    (1, "Guardar proveedor", {"s_name": "  "}, "suppliers", "El nombre es obligatorio."),
    (2, "Guardar empleado", {"e_name": "  ", "e_username": "nuevo"}, "employees",
     "Nombre y usuario son obligatorios."),
    (2, "Guardar empleado", {"e_name": "Nueva", "e_username": "  "}, "employees",
     "Nombre y usuario son obligatorios."),
])
def test_campos_obligatorios_no_guardan_registros(screen, index, caption, fields, table_name, message):
    """Las validaciones del formulario muestran el error y conservan la base.

    Precondiciones: Pantalla real con sesión de Propietario y base temporal.
    Pasos:
    - Capturar un nombre vacío o, para empleados, un usuario vacío y pulsar Guardar.
    - En los casos de duplicados, intentar repetir un proveedor o usuario existente.
    - En edición de cliente, borrar el nombre y tratar de guardar.
    Esperado:
    - Se muestra el error correspondiente sin confirmación de guardado.
    - Los registros existentes no cambian y no se insertan registros inválidos.
    - El formulario conserva los datos capturados para poder corregirlos.
    """
    before = snapshot(screen.db, table_name)
    fill(screen, **fields)
    click(tab(screen, index), caption)
    screen.errors.assert_called_once()
    assert screen.errors.call_args.args[1] == message
    screen.info.assert_not_called()
    assert snapshot(screen.db, table_name) == before
    assert {name: getattr(screen.ui, name).get() for name in fields} == fields


@tc("STS_CON_04")
def test_cliente_invalido_no_sobrescribe_edicion_anterior(screen):
    """Un nombre vacío al editar conserva el cliente y el ID seleccionado."""
    customer_id = clientes.guardar(screen.db, None, ("Ana", "555", "a@example.test", "Calle", "GDL", "Blusas"))
    screen.ui.refresh_customers()
    select(screen, screen.ui.customers_tree, customer_id)
    before = snapshot(screen.db, "customers")
    fill(screen, c_name="  ", c_phone="otro teléfono")
    click(tab(screen, 0), "Guardar cliente")
    assert screen.errors.call_args.args[1] == "El nombre es obligatorio."
    assert screen.ui.selected_customer_id == customer_id
    assert snapshot(screen.db, "customers") == before
    screen.info.assert_not_called()


@tc("STS_CON_04")
@pytest.mark.parametrize("entity", ["proveedor", "empleado"])
def test_duplicado_no_reemplaza_registro_existente(screen, entity):
    """Repetir una clave única muestra el error sin alterar el registro anterior."""
    if entity == "proveedor":
        proveedores.guardar(screen.db, None, ("Textiles", "original", "Calle", "Blusas", today_text()))
        table_name, index, caption = "suppliers", 1, "Guardar proveedor"
        fill(screen, s_name="Textiles", s_phone="nuevo teléfono")
    else:
        table_name, index, caption = "employees", 2, "Guardar empleado"
        fill(screen, e_name="Otra persona", e_username="admin", e_password="otra clave", e_role="Ventas")
    before = snapshot(screen.db, table_name)
    click(tab(screen, index), caption)
    assert "UNIQUE" in screen.errors.call_args.args[1]
    screen.info.assert_not_called()
    assert snapshot(screen.db, table_name) == before


@tc("STS_CON_04")
@pytest.mark.parametrize("entity", ["cliente", "proveedor", "empleado"])
def test_seleccion_vacia_o_fila_eliminada_conserva_formulario(screen, entity):
    """No se descarta la captura si la selección desaparece o su registro ya no existe."""
    ui = screen.ui
    tree, loader, field, selected = {
        "cliente": (ui.customers_tree, ui.load_customer_selected, "c_name", "selected_customer_id"),
        "proveedor": (ui.suppliers_tree, ui.load_supplier_selected, "s_name", "selected_supplier_id"),
        "empleado": (ui.employees_tree, ui.load_employee_selected, "e_name", "selected_employee_id"),
    }[entity]
    fill(screen, **{field: "Captura pendiente"})
    loader()
    assert getattr(ui, field).get() == "Captura pendiente"
    tree.insert("", tk.END, values=(99999, "Registro eliminado"))
    select(screen, tree, 99999)
    assert getattr(ui, selected) is None
    assert getattr(ui, field).get() == "Captura pendiente"
    screen.errors.assert_not_called()


@tc("STS_CON_04")
@pytest.mark.parametrize("entity", ["cliente", "proveedor"])
def test_campos_opcionales_nulos_se_cargan_vacios(screen, entity):
    """Los datos opcionales NULL de una base anterior no se muestran como 'None'."""
    ui = screen.ui
    if entity == "cliente":
        record_id = clientes.guardar(screen.db, None, ("Ana", None, None, None, None, None))
        ui.refresh_customers()
        select(screen, ui.customers_tree, record_id)
        fields = (ui.c_phone, ui.c_email, ui.c_address, ui.c_region, ui.c_preferences)
    else:
        record_id = proveedores.guardar(screen.db, None, ("Textiles", None, None, None, None))
        ui.refresh_suppliers()
        select(screen, ui.suppliers_tree, record_id)
        fields = (ui.s_phone, ui.s_address, ui.s_products, ui.s_last_order)
    assert all(entry.get() == "" for entry in fields)
    screen.errors.assert_not_called()


@pytest.fixture
def customer_history(screen, make_product):
    customer_id = clientes.guardar(screen.db, None, (
        "Ana López", "555", "ana+compras@example.test", "Calle 1", "GDL", "Lino & algodón"))
    other_id = clientes.guardar(screen.db, None, ("Beatriz", "", "", "", "", ""))
    blue = make_product(code="BLUSA", name="Blusa azul", price=150)
    red = make_product(code="FALDA", name="Falda roja", price=220)
    active_id, *_ = ventas.registrar(screen.db, customer_id, screen.user["id"], "Efectivo", 0,
                                     [{"product_id": blue, "quantity": 2}])
    cancelled_id, *_ = ventas.registrar(screen.db, customer_id, screen.user["id"], "Efectivo", 0,
                                        [{"product_id": red, "quantity": 3}])
    devoluciones.cancelar_venta(screen.db, cancelled_id, "Cambio de opinión")
    other_sale_id, *_ = ventas.registrar(screen.db, other_id, screen.user["id"], "Efectivo", 0,
                                         [{"product_id": red, "quantity": 1}])
    screen.ui.refresh_customers()
    select(screen, screen.ui.customers_tree, customer_id)
    return SimpleNamespace(customer_id=customer_id, active=active_id, cancelled=cancelled_id, other=other_sale_id)


@tc("STS_CON_05", nivel="STS", modulo="contactos", reqs=["RF-11", "RF-12"],
    nombre="Historial y correo del cliente muestran sus compras y validan la selección")
def test_historial_muestra_solo_compras_del_cliente_y_sus_estados(screen, customer_history):
    """Historial y correo usan las compras del cliente seleccionado sin enviar mensajes reales.

    Precondiciones: Widgets y base temporal reales; Ana tiene una venta activa y una cancelada,
      Beatriz tiene otra venta. Navegador y portapapeles están sustituidos por dobles de prueba.
    Pasos:
    - Abrir el historial de Ana desde el botón y leer la ventana de texto.
    - Abrir su correo; revisar resumen, producto favorito y preferencias.
    - Editar asunto y cuerpo, copiar y abrir el cliente de correo con el navegador simulado.
    - Repetir sin compras, sin correo y sin cliente seleccionado.
    Esperado:
    - El historial contiene las ventas de Ana con estado y cantidades, y excluye las de Beatriz.
    - El correo resume solo ventas activas y respeta el texto editado al copiar y crear el mailto.
    - Los datos ausentes producen mensajes claros; no se abre un navegador ni se envían correos reales.
    """
    click(tab(screen, 0), "Ver historial")
    window = screen.windows[-1]
    assert window.title() == "Historial de cliente"
    content = text_widget(window).get("1.0", "end-1c")
    lines = content.splitlines()
    assert len(lines) == 2
    active = next(line for line in lines if f"Venta {customer_history.active} |" in line)
    cancelled = next(line for line in lines if f"Venta {customer_history.cancelled} |" in line)
    assert "Blusa azul | Cantidad 2 | Linea $300.00 | Total venta $300.00 | ACTIVA" in active
    assert "Falda roja | Cantidad 3 | Linea $660.00 | Total venta $660.00 | CANCELADA" in cancelled
    assert f"Venta {customer_history.other} |" not in content
    screen.errors.assert_not_called()


@tc("STS_CON_05")
def test_historial_sin_compras_informa_estado_vacio(screen):
    """Un cliente nuevo tiene un historial vacío explícito."""
    customer_id = clientes.guardar(screen.db, None, ("Nueva", "", "", "", "", ""))
    screen.ui.refresh_customers()
    select(screen, screen.ui.customers_tree, customer_id)
    click(tab(screen, 0), "Ver historial")
    assert text_widget(screen.windows[-1]).get("1.0", "end-1c") == "Sin compras registradas."
    screen.errors.assert_not_called()


@tc("STS_CON_05")
@pytest.mark.parametrize("caption", ["Ver historial", "Correo profesional"])
def test_consultas_sin_cliente_muestran_error_sin_abrir_ventana(screen, caption):
    """La pantalla exige seleccionar un cliente antes de consultar sus datos."""
    click(tab(screen, 0), caption)
    assert screen.errors.call_args.args[1] == "Selecciona un cliente."
    assert screen.windows == []
    screen.browser.assert_not_called()


@tc("STS_CON_05")
def test_correo_de_cliente_eliminado_informa_error(screen):
    """Una selección obsoleta no abre un correo para un cliente que ya no existe."""
    screen.ui.selected_customer_id = 99999
    click(tab(screen, 0), "Correo profesional")
    assert screen.errors.call_args.args[1] == "Cliente no encontrado."
    assert screen.windows == []


@tc("STS_CON_05")
def test_correo_resume_ventas_activas_y_respeta_ediciones(screen, customer_history):
    """La vista previa usa solo compras activas y sus botones conservan caracteres especiales."""
    click(tab(screen, 0), "Correo profesional")
    window = screen.windows[-1]
    assert window.title() == "Correo profesional para cliente"
    text = text_widget(window)
    content = text.get("1.0", "end-1c")
    assert "Estimado/a Ana:" in content
    assert "1 compra(s)" in content and "$300.00" in content
    assert "Blusa azul" in content and "Falda roja" not in content
    assert "Lino & algodón" in content
    latest = screen.db.scalar("SELECT sale_datetime FROM sales WHERE id=?", (customer_history.active,))
    assert latest in content
    screen.browser.assert_not_called()

    subject = next(widget for widget in descendants(window) if isinstance(widget, ttk.Entry))
    edited_subject = "Promoción: tallas M & L #2"
    edited_body = "Hola, Ana:\n¿Prefieres lino & algodón? + envío"
    subject.delete(0, tk.END)
    subject.insert(0, edited_subject)
    text.delete("1.0", tk.END)
    text.insert("1.0", edited_body)
    click(window, "Copiar correo")
    screen.clipboard_clear.assert_called_once_with()
    screen.clipboard_append.assert_called_once_with(f"Asunto: {edited_subject}\n\n{edited_body}")
    assert screen.info.call_args.args[1] == "Correo copiado al portapapeles."
    click(window, "Abrir en correo")
    screen.browser.assert_called_once()
    mailto = urlsplit(screen.browser.call_args.args[0])
    assert mailto.scheme == "mailto"
    assert unquote(mailto.path) == "ana+compras@example.test"
    assert parse_qs(mailto.query) == {"subject": [edited_subject], "body": [edited_body]}
    click(window, "Cerrar")
    assert not window.winfo_exists()
    screen.errors.assert_not_called()


@tc("STS_CON_05")
def test_cliente_sin_compras_ni_correo_puede_previsualizar_pero_no_abrir_correo(screen):
    """La falta de dirección no impide la vista previa y evita abrir un mailto incompleto."""
    customer_id = clientes.guardar(screen.db, None, ("Ana", "", None, "", "", None))
    screen.ui.refresh_customers()
    select(screen, screen.ui.customers_tree, customer_id)
    click(tab(screen, 0), "Correo profesional")
    window = screen.windows[-1]
    labels = [widget.cget("text") for widget in descendants(window) if isinstance(widget, ttk.Label)]
    assert "Para: Sin correo registrado" in labels
    content = text_widget(window).get("1.0", "end-1c")
    assert "Estimado/a Ana:" in content
    assert "compra(s)" not in content and "preferencias registradas" not in content
    click(window, "Abrir en correo")
    assert screen.errors.call_args.args[1] == "El cliente no tiene correo registrado."
    screen.browser.assert_not_called()


@tc("STS_CON_05")
def test_fallo_al_abrir_cliente_de_correo_se_muestra_sin_cerrar_editor(screen):
    """Un fallo del navegador deja el mensaje editable y muestra un error controlado."""
    customer_id = clientes.guardar(screen.db, None, ("Ana", "", "ana@example.test", "", "", ""))
    screen.ui.refresh_customers()
    select(screen, screen.ui.customers_tree, customer_id)
    click(tab(screen, 0), "Correo profesional")
    window = screen.windows[-1]
    screen.browser.side_effect = OSError("Cliente de correo no disponible")
    click(window, "Abrir en correo")
    assert screen.errors.call_args.args[1] == "Cliente de correo no disponible"
    assert window.winfo_exists()
    assert "Estimado/a Ana:" in text_widget(window).get("1.0", "end-1c")
