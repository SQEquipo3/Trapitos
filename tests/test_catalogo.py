"""Meta-prueba: el catálogo de TC es congruente con los tests reales (rúbrica: congruencia de la información).

Los TC automatizados se leen del decorador @tc de cada prueba (tests/tc.py) y los
manuales de docs/testing/manuales.yml. Si una de estas pruebas falla en tu PR, el
mensaje dice qué TC o qué prueba hay que completar.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from generar_documentos import cargar_catalogo, pruebas_del_codigo  # noqa: E402

CAT = cargar_catalogo()
MANUALES = [c for c in CAT["cases"] if not c.get("tests")]


def test_fichas_completas_en_el_codigo():
    """Cada @tc trae nivel, módulo, requisitos, nombre y un docstring con objetivo, precondiciones,
    pasos y esperado; un TC se define en una sola prueba y su id no se repite."""
    assert not CAT["errores"], "\n".join(CAT["errores"])


def test_al_menos_10_tc_por_nivel():
    for nivel in CAT["meta"]["levels"]:
        assert sum(c["level"] == nivel for c in CAT["cases"]) >= 10, nivel


def test_ids_validos_como_hoja_de_excel():
    for c in CAT["cases"]:
        assert len(c["id"]) <= 31 and c["id"].replace("_", "").isalnum(), c["id"]
        assert c["id"].startswith(c["level"] + "_"), f"{c['id']}: el id debe empezar con su nivel ({c['level']})"


def test_todos_los_requisitos_tienen_al_menos_un_tc():
    cubiertos = {r for c in CAT["cases"] for r in c["reqs"]}
    assert not set(CAT["meta"]["requirements"]) - cubiertos


def test_requisitos_citados_existen():
    conocidos = set(CAT["meta"]["requirements"]) | set(CAT["meta"].get("other_ids", {}))
    desconocidos = {f"{c['id']}: {r}" for c in CAT["cases"] for r in c["reqs"] if r not in conocidos}
    assert not desconocidos, desconocidos


def test_no_hay_pruebas_huerfanas():
    """Toda prueba de pytest pertenece a algún TC: lleva @tc o su clase lo lleva."""
    huerfanas = [nodeid for nodeid, nodo, deco, deco_clase in pruebas_del_codigo()
                 if not nodeid.startswith("tests/test_catalogo.py") and deco is None and deco_clase is None
                 and nodo.name.startswith("test")]
    assert not huerfanas, "Agrega @tc a: " + ", ".join(huerfanas)


def test_tc_manuales_completos():
    for c in MANUALES:
        assert c.get("manual_result") in (None, "PASSED", "FAILED"), c["id"]
        if c.get("manual_result"):
            assert c.get("executed_by") and c.get("executed_on"), f"{c['id']}: falta executed_by o executed_on"
        if c.get("blocked_by"):
            assert re.fullmatch(r"#\d+", c["blocked_by"]), f"{c['id']}: blocked_by debe ser el número de un issue, p. ej. \"#56\""
