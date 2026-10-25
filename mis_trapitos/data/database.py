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
    def __init__(self, path=DB_NAME, load_examples=True):
        self.path = path
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
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
                yield
        finally:
            self._tx_depth = 0

    def execute(self, sql, params=()):
        if self._tx_depth:
            return self.conn.execute(sql, params)
        with self.conn:
            return self.conn.execute(sql, params)

    def query(self, sql, params=()):
        return self.conn.execute(sql, params).fetchall()

    def one(self, sql, params=()):
        return self.conn.execute(sql, params).fetchone()

    def scalar(self, sql, params=()):
        row = self.one(sql, params)
        if row is None:
            return None
        return row[0]
