"""Fixtures compartidos y registro de resultados por caso de prueba.

* ``db``: base SQLite TEMPORAL y vacía (load_examples=False); nunca toca mis_trapitos.db.
* Al terminar la corrida se escribe ``reports/results.json`` (nodeid -> resultado),
  que ``tools/generar_documentos.py`` cruza con ``docs/testing/tc/*.yml``.
"""
import json
import os
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mis_trapitos.data.database import Database  # noqa: E402
from mis_trapitos.data.repositories import empleados as empleados_repo  # noqa: E402
from mis_trapitos.data.repositories import productos as productos_repo  # noqa: E402
from utils import today_text  # noqa: E402

_RESULTS = {}


@pytest.fixture
def db(tmp_path):
    database = Database(str(tmp_path / "test.db"), load_examples=False)
    yield database
    database.close()


@pytest.fixture
def empleado(db):
    return empleados_repo.guardar(db, None, "Vendedora Prueba", "vende", "1234", "Vendedor")


@pytest.fixture
def make_product(db):
    counter = {"n": 0}

    def _make(code=None, name="Blusa", category="Ropa", size="M", color="Azul",
              purchase=80, price=200, stock=10, supplier_id=None):
        counter["n"] += 1
        code = code or f"P-{counter['n']:03d}"
        return productos_repo.guardar(db, None, (code, name, category, size, color, purchase, price,
                                      stock, supplier_id, today_text(), "Marca", "Todo", ""))
    return _make


def dias(n):
    """Fecha 'YYYY-MM-DD HH:MM:SS' desplazada n días respecto a hoy."""
    return (date.today() + timedelta(days=n)).strftime("%Y-%m-%d") + " 12:00:00"


def stock(db, product_id):
    return db.scalar("SELECT stock FROM products WHERE id=?", (product_id,))


def pytest_runtest_logreport(report):
    if report.when == "call" or (report.when == "setup" and report.outcome != "passed"):
        if report.skipped and hasattr(report, "wasxfail"):
            outcome = "xfailed"
        elif report.passed and hasattr(report, "wasxfail"):
            outcome = "xpassed"
        else:
            outcome = report.outcome
        _RESULTS[report.nodeid] = {"outcome": outcome,
                                   "reason": getattr(report, "wasxfail", "") or ""}


def pytest_sessionfinish(session, exitstatus):
    out = ROOT / "reports"
    out.mkdir(exist_ok=True)
    (out / "results.json").write_text(json.dumps(_RESULTS, indent=1, ensure_ascii=False), encoding="utf-8")
