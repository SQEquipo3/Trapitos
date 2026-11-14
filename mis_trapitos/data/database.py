"""Conexión SQLite de la aplicación Mis trapitos.

El SQL de cada entidad vive en data/repositories/ y las reglas de negocio
en services/; aquí solo se abre la conexión y se ejecutan consultas.
"""

import sqlite3
from contextlib import contextmanager

from config import DB_NAME
from mis_trapitos.data.schema import create_schema, migrate_schema
from mis_trapitos.data.seed import seed_examples


class Database:
    def __init__(self, path=DB_NAME, load_examples=True, wal=False):
        self.path = path
        # timeout: espera acotada si otra conexión (p. ej. el servicio LAN) tiene el bloqueo de escritura.
        self.conn = sqlite3.connect(self.path, timeout=5)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        if wal:
            # WAL: lectores simultáneos con un escritor (servicio LAN + aplicación de la terminal principal).
            self.conn.execute("PRAGMA journal_mode = WAL")
        self._tx_depth = 0
        create_schema(self)
        migrate_schema(self)
        if load_examples:
            seed_examples(self)

    def close(self):
        self.conn.close()

    @contextmanager
    def transaction(self):
        """Agrupa varias escrituras: commit al final o rollback completo si algo falla.

        Admite anidarse; solo la transacción más externa hace commit.
        La externa abre con BEGIN IMMEDIATE: toma el bloqueo de escritura antes de
        leer, así dos conexiones no validan el mismo stock a la vez (SDD 7.2, #56).
        """
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
        """Cambia cada vez que OTRA conexión confirma escrituras en la base (PRAGMA data_version)."""
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
