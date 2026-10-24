"""Meta-prueba: el catálogo de TC es congruente con los tests reales (rúbrica: congruencia de la información)."""
import ast
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from generar_documentos import cargar_catalogo  # noqa: E402

CAT = cargar_catalogo()


def _nodeids():
    """node-id (sin parámetros) de todas las pruebas, leídos del código fuente con ast."""
    ids = set()
    for f in (ROOT / "tests").glob("test_*.py"):
        tree = ast.parse(f.read_text(encoding="utf-8"))
        for node in tree.body:
            if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
                ids.add(f"tests/{f.name}::{node.name}")
            elif isinstance(node, ast.ClassDef):
                for sub in node.body:
                    if isinstance(sub, ast.FunctionDef) and sub.name.startswith("test"):
                        ids.add(f"tests/{f.name}::{node.name}::{sub.name}")
    return ids


def test_al_menos_10_tc_por_nivel():
    for nivel in CAT["meta"]["levels"]:
        assert sum(c["level"] == nivel for c in CAT["cases"]) >= 10, nivel


def test_ids_unicos_y_hojas_validas():
    ids = [c["id"] for c in CAT["cases"]]
    assert len(ids) == len(set(ids))
    assert all(len(i) <= 31 and i.replace("_", "").isalnum() for i in ids)   # nombre de hoja Excel


def test_todos_los_requisitos_tienen_al_menos_un_tc():
    cubiertos = {r for c in CAT["cases"] for r in c["reqs"]}
    assert not set(CAT["meta"]["requirements"]) - cubiertos


def test_cada_referencia_a_pytest_existe():
    existentes = _nodeids()
    for c in CAT["cases"]:
        for ref in c.get("tests", []):
            assert any(n.startswith(ref) for n in existentes), f"{c['id']}: '{ref}' no existe"


def test_no_hay_pruebas_huerfanas():
    """Toda prueba de pytest debe pertenecer a algún TC del catálogo."""
    refs = [r for c in CAT["cases"] for r in c.get("tests", [])]
    huerfanas = [n for n in _nodeids() if n != "tests/test_catalogo.py" and not n.startswith("tests/test_catalogo.py")
                 and not any(n.startswith(r) for r in refs)]
    assert not huerfanas, huerfanas


def test_defectos_referencian_tc_existentes():
    ids = {c["id"] for c in CAT["cases"]}
    assert all(d["tc"] in ids for d in CAT["defects"])
    assert all(c["blocked_by"] in {d["id"] for d in CAT["defects"]} for c in CAT["cases"] if c.get("blocked_by"))
