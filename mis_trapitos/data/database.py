
"""Conexión SQLite de la aplicación Mis trapitos.

El SQL de cada entidad vive en data/repositories/ y las reglas de negocio
en services/; aquí solo se abre la conexión y se ejecutan consultas.
"""

import sqlite3
from contextlib import contextmanager

from config import DB_NAME
from mis_trapitos.data.product_images import migrate_product_image_paths
from mis_trapitos.data.schema import create_schema, migrate_schema
from mis_trapitos.data.seed import seed_examples


class Database:
    def __init__(self, path=DB_NAME, load_examples=False, wal=False):
        self.path = path

        # Espera si otra conexión tiene bloqueada la base de datos.
        self.conn = sqlite3.connect(self.path, timeout=5)

        # Permite acceder a las columnas por nombre.
        self.conn.row_factory = sqlite3.Row

        # Activa las restricciones de claves foráneas.
        self.conn.execute("PRAGMA foreign_keys = ON")

        if wal:
            # Permite lectores simultáneos con un escritor.
            self.conn.execute("PRAGMA journal_mode = WAL")

        # Controla el nivel de anidamiento de las transacciones.
        self._tx_depth = 0

        # Crea las tablas y aplica las migraciones.
        create_schema(self)
        migrate_schema(self)
        migrate_product_image_paths(self)

        # Carga datos de ejemplo solamente si se solicita.
        if load_examples:
            seed_examples(self)

    def close(self):
        self.conn.close()

    @contextmanager
    def transaction(self):
        """Agrupa varias escrituras en una transacción."""

        if self._tx_depth:
            self._tx_depth += 1
            try:
                yield
            finally:
                self._tx_depth -= 1
            return

        self._tx_depth = 1

        try:
            with self.conn:
                if not self.conn.in_transaction:
                    self.conn.execute("BEGIN IMMEDIATE")
                yield
        finally:
            self._tx_depth = 0

    def execute(self, sql, params=()):
        if self._tx_depth:
            return self.conn.execute(sql, params)

        with self.conn:
            return self.conn.execute(sql, params)

    def version_datos(self):
        """Obtiene la versión de datos de la conexión."""
        return self.scalar("PRAGMA data_version")

    def query(self, sql, params=()):
        return self.conn.execute(sql, params).fetchall()

    def one(self, sql, params=()):
        return self.conn.execute(sql, params).fetchone()

    def scalar(self, sql, params=()):
        row = self.one(sql, params)

        if row is None:
            return None

        return row[0]
