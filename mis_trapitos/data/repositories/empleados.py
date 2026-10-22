"""Repositorio de empleados.

Todas las funciones reciben el objeto Database (data/database.py).
"""


def listar(db):
    """Filas para la tabla de empleados (el orden de columnas importa a la UI)."""
    return db.query(
        "SELECT id, name AS nombre, username AS usuario, role AS rol FROM employees ORDER BY id DESC"
    )


def obtener_por_id(db, employee_id):
    return db.one("SELECT * FROM employees WHERE id=?", (employee_id,))


def guardar(db, employee_id, name, username, password, role):
    """Alta (employee_id=None) o edición. Regresa el id del empleado.

    Si en edición el password viene vacío, no se cambia el que ya tenía.
    """
    return db.save_employee(employee_id, name, username, password, role)


def eliminar(db, employee_id):
    """Borra el empleado. Falla (IntegrityError) si ya registró ventas."""
    db.execute("DELETE FROM employees WHERE id=?", (employee_id,))