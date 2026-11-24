
import sqlite3

from mis_trapitos.data.database import Database
from mis_trapitos.data.schema import MIGRACIONES, migrate_schema
from tests.tc import tc

ULTIMA_VERSION = MIGRACIONES[-1][0]


@tc("ITS_MIG_01", nivel="ITS", modulo="contactos", reqs=["BD-MIG", "SQL-FK"],
    nombre="Migraciones versionadas del esquema conservan los datos")
def test_base_nueva_aplica_migracion(tmp_path):
    """Verificar que Database() de mis_trapitos/data/database.py aplica migrate_schema() de
    mis_trapitos/data/schema.py: lleva la base a la última versión (PRAGMA user_version), agrega a
    suppliers las columnas products_supplied y last_order_date, conserva los datos de una base antigua
    sin versión y no repite cambios si se migra otra vez. BD-MIG, SQL-FK.

    Precondiciones: Directorio temporal (tmp_path) sin bases previas.
    Pasos:
    - Abrir Database() sobre un archivo nuevo y leer PRAGMA user_version y PRAGMA table_info(suppliers).
    - En test_base_antigua_conserva_datos: crear con sqlite3 una tabla suppliers antigua con un
      proveedor, abrirla con Database() y leer el proveedor.
    - En test_migraciones_idempotentes: llamar migrate_schema(db) dos veces más.
    Esperado:
    - user_version queda en la versión de la última migración registrada.
    - suppliers tiene products_supplied y last_order_date, cada una una sola vez.
    - El proveedor antiguo sigue existiendo con su teléfono '1234567890'.
    """

    ruta = tmp_path / "nueva.db"

    db = Database(str(ruta), load_examples=False)

    version = db.scalar("PRAGMA user_version")

    columnas = [
        fila[1]
        for fila in db.query("PRAGMA table_info(suppliers)")
    ]

    assert version == ULTIMA_VERSION
    assert "products_supplied" in columnas
    assert "last_order_date" in columnas

    db.close()


@tc("ITS_MIG_01")
def test_base_antigua_conserva_datos(tmp_path):
    """Una base antigua sin versión debe conservar sus datos."""

    ruta = tmp_path / "antigua.db"

    # Simula una base antigua que todavía no tiene
    # las columnas agregadas por la migración 1.
    conexion = sqlite3.connect(ruta)

    conexion.execute("""
        CREATE TABLE suppliers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            phone TEXT,
            address TEXT,
            created_at TEXT NOT NULL
        )
    """)

    conexion.execute("""
        INSERT INTO suppliers
        (name, phone, address, created_at)
        VALUES (?, ?, ?, ?)
    """, ("Proveedor antiguo", "1234567890", "Centro", "2026-01-01"))

    conexion.commit()
    conexion.close()

    # Al abrir la base, Database debe aplicar la migración.
    db = Database(str(ruta), load_examples=False)

    proveedor = db.one(
        "SELECT * FROM suppliers WHERE name = ?",
        ("Proveedor antiguo",)
    )

    columnas = [
        fila[1]
        for fila in db.query("PRAGMA table_info(suppliers)")
    ]

    assert db.scalar("PRAGMA user_version") == ULTIMA_VERSION
    assert proveedor is not None
    assert proveedor["phone"] == "1234567890"
    assert "products_supplied" in columnas
    assert "last_order_date" in columnas

    db.close()


@tc("ITS_MIG_01")
def test_migraciones_idempotentes(tmp_path):
    """Ejecutar las migraciones dos veces no debe duplicar cambios."""

    ruta = tmp_path / "idempotencia.db"

    db = Database(str(ruta), load_examples=False)

    migrate_schema(db)
    migrate_schema(db)

    version = db.scalar("PRAGMA user_version")

    columnas = [
        fila[1]
        for fila in db.query("PRAGMA table_info(suppliers)")
    ]

    assert version == ULTIMA_VERSION
    assert columnas.count("products_supplied") == 1
    assert columnas.count("last_order_date") == 1

    db.close()
