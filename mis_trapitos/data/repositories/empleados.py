"""Repositorio de empleados.

Todas las funciones reciben el objeto Database (data/database.py).
"""

from utils import hash_password, now_text


def listar(db):
    """Filas para la tabla de empleados (el orden de columnas importa a la UI)."""
    return db.query(
        "SELECT id, name AS nombre, username AS usuario, role AS rol FROM employees ORDER BY id DESC"
    )


def autenticar(db, username, password):
    """Fila del empleado si usuario y contraseña coinciden; None si no."""
    return db.one(
        "SELECT * FROM employees WHERE username=? AND password_hash=?",
        (username, hash_password(password)),
    )


def primero(db):
    return db.one("SELECT * FROM employees ORDER BY id LIMIT 1")


def obtener_por_id(db, employee_id):
    return db.one("SELECT * FROM employees WHERE id=?", (employee_id,))


def guardar(db, employee_id, name, username, password, role):
    """Alta (employee_id=None) o edición. Regresa el id del empleado.

    Si en edición el password viene vacío, no se cambia el que ya tenía.
    """
    if employee_id:
        if password:
            db.execute(
                "UPDATE employees SET name=?, username=?, password_hash=?, role=? WHERE id=?",
                (name, username, hash_password(password), role, employee_id),
            )
        else:
            db.execute(
                "UPDATE employees SET name=?, username=?, role=? WHERE id=?",
                (name, username, role, employee_id),
            )
        return employee_id
    cur = db.execute(
        "INSERT INTO employees(name, username, password_hash, role, created_at) VALUES(?,?,?,?,?)",
        (name, username, hash_password(password or "1234"), role, now_text()),
    )
    return cur.lastrowid


def eliminar(db, employee_id):
    """Borra el empleado. Falla (IntegrityError) si ya registró ventas."""
    db.execute("DELETE FROM employees WHERE id=?", (employee_id,))