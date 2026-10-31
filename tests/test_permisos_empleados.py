from unittest.mock import patch

import pytest

from mis_trapitos.data.database import Database
from mis_trapitos.data.repositories import empleados as empleados_repo
from mis_trapitos.services import empleados as empleados_srv
from mis_trapitos.ui.app import App
from tests.tc import tc


@pytest.fixture
def app(tmp_path):
    with patch("mis_trapitos.ui.app.Database", side_effect=lambda path: Database(path, load_examples=False)):
        application = App(db_path=str(tmp_path / "permisos.db"))
    application.withdraw()
    try:
        with patch("mis_trapitos.ui.contactos.messagebox.showerror") as error, \
                patch("mis_trapitos.ui.contactos.messagebox.showinfo"):
            yield application, error
    finally:
        application.update_idletasks()
        application.on_close()


def login(app, username, role):
    employee_id = empleados_repo.guardar(app.db, None, username, username, "1234", role)
    app.login_view.username_entry.delete(0, "end")
    app.login_view.username_entry.insert(0, username)
    app.login_view.password_entry.delete(0, "end")
    app.login_view.password_entry.insert(0, "1234")
    app.login_view.submit()
    assert app.user["id"] == employee_id
    return employee_id


def employees(db):
    return [dict(row) for row in db.query("SELECT * FROM employees ORDER BY id")]


@tc("ITS_SEG_01", nivel="ITS", modulo="interfaz", reqs=["SEG-01"],
    nombre="Autorización de consultas, altas y ediciones de empleados")
@pytest.mark.parametrize("role", ["Vendedor", "Ventas", "Inventario", "Contabilidad", "", "Desconocido", None])
def test_servicio_rechaza_consultas_altas_y_ediciones_sin_permiso(db, role):
    """El servicio impide administrar empleados aunque se invoque sin pasar por la interfaz.

    Precondiciones: BD temporal con un administrador y una sesión sin permisos o inexistente.
    Pasos:
    - Consultar empleados e intentar crear y editar cuentas directamente desde el servicio
    - Repetir con roles sin permiso y sin sesión
    Esperado:
    - Todas las operaciones lanzan PermissionError
    - Los datos y credenciales de empleados permanecen intactos
    """
    target_id = empleados_repo.guardar(db, None, "Administrador", "admin", "clave", "Administrador")
    user = None
    if role is not None:
        user_id = empleados_repo.guardar(db, None, "Empleado", "empleado", "clave", role)
        user = dict(empleados_repo.obtener_por_id(db, user_id))
        user["role"] = "Administrador"
    before = employees(db)
    operations = (
        lambda: empleados_srv.listar(db, user),
        lambda: empleados_srv.obtener_por_id(db, user, target_id),
        lambda: empleados_srv.guardar(db, user, None, "Intruso", "intruso", "otra", "Administrador"),
        lambda: empleados_srv.guardar(db, user, target_id, "Intruso", "admin", "otra", "Vendedor"),
    )
    for operation in operations:
        with pytest.raises(PermissionError, match="Acceso denegado"):
            operation()
        assert employees(db) == before


@tc("ITS_SEG_01")
@pytest.mark.parametrize("role", ["Administrador", "Propietario", " administrador ", "PROPIETARIO"])
def test_servicio_permite_administrar_y_conserva_contrasena_al_editar(db, role):
    user_id = empleados_repo.guardar(db, None, "Admin", "admin", "clave", role)
    user = empleados_repo.obtener_por_id(db, user_id)
    employee_id = empleados_srv.guardar(db, user, None, "Ana", "ana", "secreta", "Ventas")
    empleados_srv.guardar(db, user, employee_id, "Ana López", "ana", "", "Vendedor")
    assert empleados_srv.obtener_por_id(db, user, employee_id)["name"] == "Ana López"
    assert empleados_repo.autenticar(db, "ana", "secreta")["role"] == "Vendedor"
    assert len(empleados_srv.listar(db, user)) == 2


@tc("ITS_SEG_01")
@pytest.mark.parametrize("revoke", ["rol", "eliminado"])
def test_servicio_revalida_el_usuario_de_una_sesion_anterior(db, revoke):
    user_id = empleados_repo.guardar(db, None, "Admin", "admin", "clave", "Administrador")
    user = empleados_repo.obtener_por_id(db, user_id)
    if revoke == "rol":
        db.execute("UPDATE employees SET role='Vendedor' WHERE id=?", (user_id,))
    else:
        empleados_repo.eliminar(db, user_id)
    before = employees(db)
    with pytest.raises(PermissionError, match="Acceso denegado"):
        empleados_srv.guardar(db, user, None, "Nuevo", "nuevo", "clave", "Administrador")
    assert employees(db) == before


@tc("STS_SEG_01", nivel="STS", modulo="interfaz", reqs=["SEG-01"],
    nombre="Gestión de empleados restringida por sesión y rol")
@pytest.mark.parametrize("role", ["Vendedor", "Ventas", "Inventario", "Contabilidad", "", "Desconocido"])
def test_usuario_sin_permiso_no_accede_ni_guarda_empleados(app, role):
    """La gestión de empleados rechaza a los usuarios sin permisos administrativos.

    Precondiciones: Aplicación con BD temporal y un empleado sin permisos administrativos.
    Pasos:
    - Iniciar sesión y abrir Contactos, Empleados
    - Invocar directamente las acciones de consulta y guardado
    Esperado:
    - Se muestra acceso denegado sin formulario ni listado de empleados
    - Las acciones no alteran la base de datos
    """
    application, error = app
    login(application, "empleado", role)
    ui = application.contactos_ui
    application._select_module(2)
    ui.notebook.select(2)
    tab = ui.nametowidget(ui.notebook.tabs()[2])
    assert any("Acceso denegado" in child.cget("text") for child in tab.body.winfo_children())
    assert not hasattr(ui, "e_name")
    assert not hasattr(ui, "employees_tree")
    before = employees(application.db)
    for action in (ui.save_employee_ui, ui.refresh_employees, ui.load_employee_selected, ui.clear_employee_form):
        error.reset_mock()
        action()
        assert "Acceso denegado" in error.call_args.args[1]
    assert employees(application.db) == before
    assert hasattr(ui, "c_name") and hasattr(ui, "s_name")


@tc("STS_SEG_01")
@pytest.mark.parametrize("role", ["Administrador", "Propietario"])
def test_administrador_crea_y_edita_empleados(app, role):
    application, error = app
    login(application, "admin", role)
    ui = application.contactos_ui
    for entry, value in ((ui.e_name, "Ana"), (ui.e_username, "ana"),
                         (ui.e_password, "clave"), (ui.e_role, "Vendedor")):
        entry.insert(0, value)
    ui.save_employee_ui()
    employee_id = ui.selected_employee_id
    assert employee_id is not None
    row_id = next(item for item in ui.employees_tree.get_children()
                  if int(ui.employees_tree.item(item, "values")[0]) == employee_id)
    ui.employees_tree.selection_set(row_id)
    ui.load_employee_selected()
    ui.e_name.delete(0, "end")
    ui.e_name.insert(0, "Ana López")
    ui.save_employee_ui()
    employee = empleados_repo.autenticar(application.db, "ana", "clave")
    assert employee["name"] == "Ana López"
    assert employee["role"] == "Vendedor"
    error.assert_not_called()


@tc("STS_SEG_01")
def test_cambiar_a_vendedor_no_conserva_acceso_de_administrador(app):
    application, error = app
    login(application, "admin", "Administrador")
    assert hasattr(application.contactos_ui, "e_name")
    application.show_login()
    login(application, "vendedor", "Vendedor")
    before = employees(application.db)
    application.contactos_ui.save_employee_ui()
    assert "Acceso denegado" in error.call_args.args[1]
    assert employees(application.db) == before
    assert not hasattr(application.contactos_ui, "e_name")


@tc("STS_SEG_01")
@pytest.mark.parametrize("revoke", ["rol", "sesion"])
def test_formulario_abierto_revalida_permiso_antes_de_guardar(app, revoke):
    application, error = app
    admin_id = login(application, "admin", "Administrador")
    ui = application.contactos_ui
    ui.e_name.insert(0, "Nuevo")
    ui.e_username.insert(0, "nuevo")
    if revoke == "rol":
        application.db.execute("UPDATE employees SET role='Vendedor' WHERE id=?", (admin_id,))
    else:
        application.user = None
    before = employees(application.db)
    ui.save_employee_ui()
    assert "Acceso denegado" in error.call_args.args[1]
    assert employees(application.db) == before
