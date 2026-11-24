import sqlite3

from mis_trapitos.data.database import Database

from tests.tc import tc

@tc(
    "ITS_MIG_02",
    nivel="ITS",
    modulo="migraciones",
    reqs=["RF-06", "RF-08"],
    nombre="La migración convierte importes a centavos"
)
def test_migracion_convierte_importes_a_centavos(tmp_path):
    """
    Objetivo: Verificar que la migración convierta los importes monetarios
    del esquema anterior de pesos a centavos enteros.

    Precondiciones:
    - Tener SQLite disponible.
    - Crear una base de datos con la estructura anterior.
    - Contar con productos y ventas que tengan importes en pesos.

    Pasos:
    - Crear una base de datos con la estructura anterior.
    - Insertar un producto con precio de 0.10 pesos.
    - Insertar una venta con total de 0.30 pesos.
    - Abrir la base con Database para ejecutar la migración.
    - Consultar los importes de products, sales y sale_items.
    - Consultar la versión del esquema.

    Esperado:
    - El precio de compra y venta del producto debe ser 10 centavos.
    - El total de la venta debe ser 30 centavos.
    - El precio unitario debe ser 10 centavos.
    - La versión de la base de datos debe ser 2.
    """
    ruta = tmp_path / "anterior.db"

    # Crear una base con la estructura anterior y datos en pesos.
    conn = sqlite3.connect(ruta)

    conn.executescript("""
        CREATE TABLE suppliers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            phone TEXT,
            address TEXT,
            created_at TEXT NOT NULL,
            products_supplied TEXT,
            last_order_date TEXT
        );

        CREATE TABLE employees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT,
            email TEXT,
            address TEXT,
            city_region TEXT,
            preferences TEXT,
            created_at TEXT NOT NULL
        );

        INSERT INTO employees
        (id, name, username, password_hash, role, created_at)
        VALUES (1, 'Prueba', 'prueba', 'hash', 'Administrador', '2026-01-01');

        CREATE TABLE products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            size TEXT NOT NULL,
            color TEXT NOT NULL,
            purchase_price REAL NOT NULL,
            sale_price REAL NOT NULL,
            stock INTEGER NOT NULL,
            supplier_id INTEGER,
            entry_date TEXT NOT NULL,
            brand TEXT,
            season TEXT,
            image_path TEXT,
            created_at TEXT NOT NULL
        );

        INSERT INTO products VALUES
        (1, 'P001', 'Blusa', 'Ropa', 'M', 'Azul',
         0.10, 0.10, 10, NULL, '2026-01-01',
         'Marca', 'Todo', '', '2026-01-01');

        CREATE TABLE sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sale_datetime TEXT NOT NULL,
            customer_id INTEGER,
            employee_id INTEGER NOT NULL,
            payment_method TEXT NOT NULL,
            subtotal REAL NOT NULL,
            sale_discount_percent REAL NOT NULL DEFAULT 0,
            discount_amount REAL NOT NULL,
            total REAL NOT NULL,
            status TEXT NOT NULL DEFAULT 'ACTIVA'
        );

        INSERT INTO sales VALUES
        (1, '2026-01-01', NULL, 1, 'Efectivo',
         0.30, 0, 0, 0.30, 'ACTIVA');

        CREATE TABLE sale_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sale_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL,
            unit_price REAL NOT NULL,
            promo_discount_percent REAL NOT NULL DEFAULT 0,
            line_total REAL NOT NULL
        );

        INSERT INTO sale_items VALUES
        (1, 1, 1, 3, 0.10, 0, 0.30);

        CREATE TABLE promotions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL,
            discount_percent REAL NOT NULL,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE inventory_movements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL,
            movement_type TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            movement_datetime TEXT NOT NULL,
            reason TEXT NOT NULL,
            related_sale_id INTEGER
        );

        CREATE TABLE returns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sale_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL,
            return_datetime TEXT NOT NULL,
            reason TEXT
        );

        CREATE TABLE cancellations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sale_id INTEGER NOT NULL,
            cancel_datetime TEXT NOT NULL,
            reason TEXT
        );

        CREATE TABLE lan_requests (
            request_key TEXT PRIMARY KEY,
            fingerprint TEXT NOT NULL,
            sale_id INTEGER NOT NULL,
            employee_id INTEGER NOT NULL,
            created_at TEXT NOT NULL
        );

        PRAGMA user_version = 1;
    """)

    conn.commit()
    conn.close()

    # Abrir con la aplicación ejecuta la migración 2.
    db = Database(str(ruta), load_examples=False)

    assert db.scalar(
        "SELECT purchase_price FROM products WHERE id=1"
    ) == 10

    assert db.scalar(
        "SELECT sale_price FROM products WHERE id=1"
    ) == 10

    assert db.scalar(
        "SELECT total FROM sales WHERE id=1"
    ) == 30

    assert db.scalar(
        "SELECT unit_price FROM sale_items WHERE id=1"
    ) == 10

    assert db.scalar("PRAGMA user_version") == 2

    db.close()