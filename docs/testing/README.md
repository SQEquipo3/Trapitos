# Pruebas y documentación de calidad — Mis Trapitos

Los tres entregables (**SW Test Plan**, **TC Design** y **Test Report**) se generan solos. El equipo solo:

1. **Escribe pruebas** en `tests/` con el decorador `@tc`.
2. **Reporta bugs** como issues con la plantilla «Defecto».
3. **Registra los TC manuales** en `docs/testing/manuales.yml` cuando los ejecuta.

En cada Pull Request, `tests.yml` corre pytest, genera los Excel y los sube como artefacto **`entregables-qa`** (pestaña *Actions* → la corrida → *Artifacts*).

En cada push a `main` los Excel además se publican en el release **`qa-latest`** (pestaña *Releases*), reemplazando los anteriores: ahí siempre está la última versión, sin descargar artefactos. Incluye los 3 `.xlsx` y `entregables-qa.zip` con las gráficas.

## 1. Escribir una prueba (TC automatizado)

```python
from tests.tc import tc

@tc("ITS_VEN_04", nivel="ITS", modulo="ventas", reqs=["RF-05"],
    nombre="Devolución suma al stock y registra movimiento DEVOLUCION")
def test_devolucion_suma_al_stock(db, empleado, make_product):
    """Una devolución parcial regresa las piezas al inventario.

    Precondiciones: Producto con stock 10 y un empleado.
    Pasos:
    - Vender 5 piezas
    - Devolver 2
    Esperado:
    - Stock vuelve a 7
    - Movimiento DEVOLUCION +2 ligado a la venta
    Comentarios: opcional.
    """
    ...
```

### Cómo escribir la ficha para que la entienda alguien nuevo

La ficha es lo que leen el maestro y cualquier persona que llegue al proyecto, así que debe entenderse sin abrir el código:

* **Objetivo:** qué regla de negocio se comprueba, por qué importa y qué función se prueba, con su archivo. Ejemplo: «`devolver()` de `mis_trapitos/services/devoluciones.py` suma al stock y registra un movimiento DEVOLUCION».
* **Precondiciones:** qué fixtures usa (`db`, `empleado`, `make_product`, `mundo`…) y con qué datos (stock, precios, fechas).
* **Pasos:** una acción por línea, nombrando la función que se llama y sus argumentos clave: «Llamar `devoluciones_srv.devolver(db, sale_id, pid, 2, 'x')`». Si el TC tiene varias pruebas, indica qué paso hace cada una («En `test_…`: …»).
* **Esperado:** valores exactos (stock 7, total 540, el mensaje de error textual), no «funciona bien».
* **Comentarios:** bugs o brechas relacionadas y cualquier dato que ayude a mantener la prueba.
* No empieces una línea de continuación con `- ` ni con `Pasos:`/`Esperado:`: el lector las toma como un paso o una sección nueva.

El generador agrega solo, en el campo *Comments* de cada hoja, el archivo donde está la ficha, las pruebas que implementan el TC y el comando para correrlo.

### Reglas

* **Una sola prueba por TC** lleva los datos (`nivel`, `modulo`, `reqs`, `nombre`) y el docstring. Las demás pruebas del mismo TC solo llevan `@tc("ITS_VEN_04")`.
* El docstring es la ficha del Excel. La primera parte es el **objetivo**, después vienen `Precondiciones:`, `Pasos:`, `Esperado:` y, opcional, `Comentarios:`.
* `@tc` también va sobre una clase de `unittest` y cubre todos sus métodos `test*`.
* **Niveles:** `UTS` unitarias, `ITS` integración, `STS` sistema, `ATS` aceptación y `CTS` conformidad. El id empieza con su nivel: `NIVEL_MODULO_NN`.
* **Requisitos:** los `RF-xx` y `RNF-01` del SDD, y los ids extra de `meta.yml` (`other_ids`), como `SEG-01` o `RFC-4180`.
* Usa la base temporal (fixture `db`, `load_examples=False`): nunca toques `mis_trapitos.db`.

`tests/test_catalogo.py` revisa todo esto en tu PR y te dice qué falta: al menos 10 TC por nivel, todos los RF cubiertos, ninguna prueba sin `@tc` y fichas completas.

## 2. Reportar un bug

Abre un issue con la plantilla **«Defecto (bug)»**. Pon la label `bug`, el TC que lo detectó, los pasos, la severidad y el esperado vs. real.

* Aparece solo en la hoja **«Bug report»**. Quien abre el issue queda como *Found by*, el assignee como *Assigned to*, y el estado sale de si el issue está abierto o cerrado.
* Si dejas una prueba que falla a propósito mientras se corrige, márcala con `@pytest.mark.xfail(strict=True, reason="#<issue>: ...")`.
* Todo TC *Failed* o *Blocked* debe tener su issue de bug. Si falta, el generador lo marca como error.
* Los nombres reales para *Found by* y *Assigned to* se toman de `nombres` en `meta.yml` (usuario de GitHub → nombre).

## 3. TC manuales

Son los que ejecuta una persona, como el cliente en las pruebas de aceptación, o los que necesitan varias máquinas. Viven en `docs/testing/manuales.yml` con los mismos campos que el docstring. Al ejecutarlos, llenen `manual_result` (`PASSED`/`FAILED`), `executed_by` y `executed_on`. Si un bug impide ejecutarlo, pongan `blocked_by: "#<issue>"`.

## Estructura

```
tests/tc.py                  decorador @tc (formato de la ficha)
tests/test_*.py              pruebas = casos de prueba automatizados
docs/testing/meta.yml        equipo, proyecto, testers, nombres, requisitos y niveles
docs/testing/manuales.yml    TC manuales y su resultado
docs/testing/plantillas/     plantillas Excel del maestro (no se editan)
tools/generar_documentos.py  llena las plantillas
tools/crear_issues.py        crea las historias de prueba en GitHub (historias.yml)
```

Los archivos generados se llaman `SW_Test_Plan_<Team>_<Proyecto>.xlsx`, `TC_Design_…xlsx` y `SWT_summary_report_…xlsx`, y se guardan con las gráficas en `entregables/`.

## Generarlos en tu computadora

```bash
pip install -r requirements-dev.txt
xvfb-run -a pytest --cov=mis_trapitos --cov-report=json:reports/coverage.json   # Windows/macOS: sin xvfb-run
python tools/generar_documentos.py            # lee los bugs con tu sesión de `gh auth login`
python tools/generar_documentos.py --sin-github   # sin conexión: el Bug report sale vacío
```

## Antes de entregar

* Pongan nombres reales en `meta.yml`: `testers` y `nombres`.
* Cada integrante agrega su línea en `revisiones` de `meta.yml` (sale en la hoja `intro`).
* Ejecuten los TC manuales y registren su resultado.
* Descarguen el artefacto `entregables-qa` de la última corrida en `main`.
