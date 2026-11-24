

"""Creación y migraciones versionadas del esquema SQLite."""

# ============================================================
# CREACIÓN DE TABLAS
# ============================================================

def create_schema(db):
    """
    Crea todas las tablas de la aplicación si todavía no existen.

    Los importes monetarios se almacenan como INTEGER,
    representando centavos en lugar de pesos.
    """

    db.conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS suppliers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            phone TEXT,
            address TEXT,
            created_at TEXT NOT NULL,
            products_supplied TEXT,
            last_order_date TEXT
        );

        CREATE TABLE IF NOT EXISTS employees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT,
            email TEXT,
            address TEXT,
            city_region TEXT,
            preferences TEXT,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            size TEXT NOT NULL,
            color TEXT NOT NULL,
            purchase_price INTEGER NOT NULL
                CHECK(purchase_price >= 0),
            sale_price INTEGER NOT NULL
                CHECK(sale_price >= 0),
            stock INTEGER NOT NULL CHECK(stock >= 0),
            supplier_id INTEGER,
            entry_date TEXT NOT NULL,
            brand TEXT,
            season TEXT,
            image_path TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (supplier_id) REFERENCES suppliers(id)
        );

        CREATE TABLE IF NOT EXISTS promotions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL,
            discount_percent REAL NOT NULL
                CHECK(discount_percent >= 0 AND discount_percent <= 100),
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (product_id) REFERENCES products(id)
        );

        CREATE TABLE IF NOT EXISTS sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sale_datetime TEXT NOT NULL,
            customer_id INTEGER,
            employee_id INTEGER NOT NULL,
            payment_method TEXT NOT NULL,
            subtotal INTEGER NOT NULL,
            sale_discount_percent REAL NOT NULL DEFAULT 0,
            discount_amount INTEGER NOT NULL,
            total INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'ACTIVA',
            FOREIGN KEY (customer_id) REFERENCES customers(id),
            FOREIGN KEY (employee_id) REFERENCES employees(id)
        );

        CREATE TABLE IF NOT EXISTS sale_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sale_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL CHECK(quantity > 0),
            unit_price INTEGER NOT NULL,
            promo_discount_percent REAL NOT NULL DEFAULT 0,
            line_total INTEGER NOT NULL,
            FOREIGN KEY (sale_id) REFERENCES sales(id),
            FOREIGN KEY (product_id) REFERENCES products(id)
        );

        CREATE TABLE IF NOT EXISTS inventory_movements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL,
            movement_type TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            movement_datetime TEXT NOT NULL,
            reason TEXT NOT NULL,
            related_sale_id INTEGER,
            FOREIGN KEY (product_id) REFERENCES products(id),
            FOREIGN KEY (related_sale_id) REFERENCES sales(id)
        );

        CREATE TABLE IF NOT EXISTS returns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sale_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL CHECK(quantity > 0),
            return_datetime TEXT NOT NULL,
            reason TEXT,
            FOREIGN KEY (sale_id) REFERENCES sales(id),
            FOREIGN KEY (product_id) REFERENCES products(id)
        );

        CREATE TABLE IF NOT EXISTS cancellations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sale_id INTEGER NOT NULL,
            cancel_datetime TEXT NOT NULL,
            reason TEXT,
            FOREIGN KEY (sale_id) REFERENCES sales(id)
        );

        CREATE TABLE IF NOT EXISTS lan_requests (
            request_key TEXT PRIMARY KEY,
            fingerprint TEXT NOT NULL,
            sale_id INTEGER NOT NULL REFERENCES sales(id),
            employee_id INTEGER NOT NULL,
            created_at TEXT NOT NULL
        );
        """
    )

    db.conn.commit()


# ============================================================
# MIGRACIÓN 1
# ============================================================

def migracion_1(db):
    """
    Migración 1:
    Agrega products_supplied y last_order_date a suppliers.

    Comprueba las columnas existentes para evitar duplicarlas.
    """

    columnas = [
        fila[1]
        for fila in db.query("PRAGMA table_info(suppliers)")
    ]

    if "products_supplied" not in columnas:
        db.execute(
            "ALTER TABLE suppliers ADD COLUMN products_supplied TEXT"
        )

    if "last_order_date" not in columnas:
        db.execute(
            "ALTER TABLE suppliers ADD COLUMN last_order_date TEXT"
        )


# ============================================================
# MIGRACIÓN 2
# ============================================================

def migracion_2(db):
    """
    Migración 2:
    Convierte los importes monetarios de pesos a centavos.

    Conserva los identificadores, datos y relaciones de las tablas.
    Esta migración se ejecuta una sola vez.
    """

    # --------------------------------------------------------
    # 1. Crear tabla products con precios en centavos.
    # --------------------------------------------------------

    db.conn.execute("""
        CREATE TABLE products_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            size TEXT NOT NULL,
            color TEXT NOT NULL,
            purchase_price INTEGER NOT NULL
                CHECK(purchase_price >= 0),
            sale_price INTEGER NOT NULL
                CHECK(sale_price >= 0),
            stock INTEGER NOT NULL CHECK(stock >= 0),
            supplier_id INTEGER,
            entry_date TEXT NOT NULL,
            brand TEXT,
            season TEXT,
            image_path TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (supplier_id) REFERENCES suppliers(id)
        )
    """)

    db.conn.execute("""
        INSERT INTO products_new (
            id, code, name, category, size, color,
            purchase_price, sale_price, stock, supplier_id,
            entry_date, brand, season, image_path, created_at
        )
        SELECT
            id, code, name, category, size, color,
            CAST(ROUND(purchase_price * 100) AS INTEGER),
            CAST(ROUND(sale_price * 100) AS INTEGER),
            stock, supplier_id, entry_date, brand, season,
            image_path, created_at
        FROM products
    """)

    # --------------------------------------------------------
    # 2. Crear tabla sales con importes en centavos.
    # --------------------------------------------------------

    db.conn.execute("""
        CREATE TABLE sales_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sale_datetime TEXT NOT NULL,
            customer_id INTEGER,
            employee_id INTEGER NOT NULL,
            payment_method TEXT NOT NULL,
            subtotal INTEGER NOT NULL,
            sale_discount_percent REAL NOT NULL DEFAULT 0,
            discount_amount INTEGER NOT NULL,
            total INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'ACTIVA',
            FOREIGN KEY (customer_id) REFERENCES customers(id),
            FOREIGN KEY (employee_id) REFERENCES employees(id)
        )
    """)

    db.conn.execute("""
        INSERT INTO sales_new (
            id, sale_datetime, customer_id, employee_id,
            payment_method, subtotal, sale_discount_percent,
            discount_amount, total, status
        )
        SELECT
            id, sale_datetime, customer_id, employee_id,
            payment_method,
            CAST(ROUND(subtotal * 100) AS INTEGER),
            sale_discount_percent,
            CAST(ROUND(discount_amount * 100) AS INTEGER),
            CAST(ROUND(total * 100) AS INTEGER),
            status
        FROM sales
    """)

    # --------------------------------------------------------
    # 3. Crear tabla sale_items con importes en centavos.
    # --------------------------------------------------------

    db.conn.execute("""
        CREATE TABLE sale_items_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sale_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL CHECK(quantity > 0),
            unit_price INTEGER NOT NULL,
            promo_discount_percent REAL NOT NULL DEFAULT 0,
            line_total INTEGER NOT NULL,
            FOREIGN KEY (sale_id) REFERENCES sales(id),
            FOREIGN KEY (product_id) REFERENCES products(id)
        )
    """)

    db.conn.execute("""
        INSERT INTO sale_items_new (
            id, sale_id, product_id, quantity,
            unit_price, promo_discount_percent, line_total
        )
        SELECT
            id, sale_id, product_id, quantity,
            CAST(ROUND(unit_price * 100) AS INTEGER),
            promo_discount_percent,
            CAST(ROUND(line_total * 100) AS INTEGER)
        FROM sale_items
    """)

    # --------------------------------------------------------
    # 4. Reemplazar las tablas anteriores.
    # --------------------------------------------------------

    # Se eliminan primero las tablas que dependen de las otras.
    db.conn.execute("DROP TABLE sale_items")
    db.conn.execute("DROP TABLE sales")
    db.conn.execute("DROP TABLE products")

    # Se asignan los nombres originales a las tablas nuevas.
    db.conn.execute(
        "ALTER TABLE products_new RENAME TO products"
    )

    db.conn.execute(
        "ALTER TABLE sales_new RENAME TO sales"
    )

    db.conn.execute(
        "ALTER TABLE sale_items_new RENAME TO sale_items"
    )


# ============================================================
# REGISTRO DE MIGRACIONES
# ============================================================

MIGRACIONES = [
    (1, migracion_1),
    (2, migracion_2),
]


# ============================================================
# EJECUCIÓN DE MIGRACIONES
# ============================================================

def migrate_schema(db):
    """
    Ejecuta las migraciones pendientes en orden ascendente.

    La conversión de tablas se realiza con las claves foráneas
    temporalmente desactivadas. Antes de confirmar la transacción
    se comprueba que no existan relaciones inválidas.
    """

    version_actual = db.scalar("PRAGMA user_version")

    if version_actual is None:
        version_actual = 0

    ultima_version = MIGRACIONES[-1][0] if MIGRACIONES else 0

    if version_actual > ultima_version:
        raise RuntimeError(
            f"La base de datos tiene la versión {version_actual}, "
            f"pero esta aplicación solo admite hasta la versión "
            f"{ultima_version}."
        )

    pendientes = [
        (numero, funcion)
        for numero, funcion in MIGRACIONES
        if numero > version_actual
    ]

    if not pendientes:
        return

    # Debe ejecutarse antes de comenzar la transacción.
    db.conn.execute("PRAGMA foreign_keys = OFF")

    try:
        db.conn.execute("BEGIN IMMEDIATE")

        for numero, funcion in pendientes:
            funcion(db)

            db.conn.execute(
                f"PRAGMA user_version = {numero}"
            )

        # Comprueba las relaciones antes de confirmar.
        errores = db.query("PRAGMA foreign_key_check")

        if errores:
            raise RuntimeError(
                "La migración produjo errores en las claves foráneas. "
                f"Detalles: {errores}"
            )

        db.conn.commit()

    except Exception:
        db.conn.rollback()
        raise

    finally:
        # Se vuelven a activar las claves foráneas.
        db.conn.execute("PRAGMA foreign_keys = ON")

    # Comprueba que las claves foráneas estén activas.
    estado_fk = db.scalar("PRAGMA foreign_keys")

    if estado_fk != 1:
        raise RuntimeError(
            "No fue posible activar las claves foráneas."
        )
