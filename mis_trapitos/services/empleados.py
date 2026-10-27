"""Administración de empleados autorizada por el usuario de la sesión."""

from mis_trapitos.data.repositories import empleados as empleados_repo


ACCESO_DENEGADO = "Acceso denegado. Solo Administrador o Propietario puede administrar empleados."


def puede_administrar(db, usuario):
    if usuario is None:
        return False
    empleado = empleados_repo.obtener_por_id(db, usuario["id"])
    return empleado is not None and (empleado["role"] or "").strip().casefold() in {
        "administrador", "propietario",
    }


def exigir_permiso(db, usuario):
    if not puede_administrar(db, usuario):
        raise PermissionError(ACCESO_DENEGADO)


def listar(db, usuario):
    exigir_permiso(db, usuario)
    return empleados_repo.listar(db)


def obtener_por_id(db, usuario, employee_id):
    exigir_permiso(db, usuario)
    return empleados_repo.obtener_por_id(db, employee_id)


def guardar(db, usuario, employee_id, name, username, password, role):
    exigir_permiso(db, usuario)
    return empleados_repo.guardar(db, employee_id, name, username, password, role)
