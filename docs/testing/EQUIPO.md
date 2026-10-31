# Pruebas de Trapitos: qué cambió y qué le toca a cada quien

## 1. Qué cambió en el código (ya está en `main`)

- Ahora el proyecto va por capas: **UI → services → repositories → Database**.
- La UI ya no tiene SQL:
  - Las ventas, devoluciones y cancelaciones están en `mis_trapitos/services/`.
  - Todas las consultas están en `mis_trapitos/data/repositories/`.
- `Database` solo maneja la conexión y las transacciones.
- Si van a tocar algo, hagan primero `git pull`.

## 2. El nuevo mecanismo de pruebas (PR #58)

Ya no se llenan los Excel a mano: **la prueba en Python es la ficha del caso de prueba.**
Cada test lleva un decorador `@tc` y un docstring con la ficha:

```python
@tc("CTS_FMT_01", nivel="CTS", modulo="ventas", reqs=["ISO-8601"],
    nombre="Fechas en formato ISO 8601")
def test_fechas_iso():
    """Objetivo de la prueba.

    Precondiciones: Ninguna.
    Pasos:
    - Paso 1
    - Paso 2
    Esperado:
    - Resultado esperado
    """
    assert ...
```

- Cuando hacen push, GitHub Actions corre las pruebas y **genera solo** el Test Plan, el TC Design y el Test Report en Excel, con resultados, cobertura y gráficas.
- La última versión de los Excel (de `main`) está en **Releases → `qa-latest`**. Los de un PR se descargan en **Actions → la ejecución → Artifacts → `entregables-qa`**.
- Niveles:
  - UTS: unitarias
  - ITS: integración
  - STS: sistema
  - ATS: aceptación
  - CTS: conformidad
- Ya tenemos 78 TC, con 10 o más por nivel.
- Si a una prueba le falta algo en la ficha, el CI falla y dice qué falta.

### Bugs

- Los bugs ahora son **issues de GitHub**. Se crean con *New issue → plantilla "Defecto"*, que pone la label `bug` en automático, y el Test Report los jala solo.
- Si arreglan un bug que ya tiene prueba con `xfail`, la prueba empieza a pasar y el CI falla a propósito. En ese caso borran el `xfail` en ese mismo PR.

### Pruebas manuales

- Las pruebas que no se pueden automatizar están en `docs/testing/manuales.yml`.
- Ahí se llenan `manual_result`, `executed_by` y `executed_on`.

## 3. Qué le toca a cada quien (en este orden)

1. ~~**Juan:** revisar y aprobar el **PR #58** y hacer el merge.~~ Hecho.
2. **Todos:** `git pull` después del merge.
3. ~~**Kelly:** #59, poner los nombres reales del equipo en `docs/testing/meta.yml`.~~ Hecho.
4. **Elizabeth:** #60 y #75, hacer con el cliente las pruebas de aceptación manuales y registrar los resultados en `manuales.yml`.
5. **Bugs (opcional, si da tiempo):**
   - Juan: #53 y #54
   - Kelly: #56
   - Elizabeth: #57

   Si no se arreglan, no pasa nada: salen en el reporte como defectos abiertos, y eso también cuenta.
6. **Al final los tres vamos a:** #61, descargar los Excel del último CI en `main`, revisarlos, aprobarlos y subirlos

### Historias de prueba (#64 a #75)

Cada historia agrupa TC y está asignada a quien escribió esas pruebas (sale de `docs/testing/historias.yml`):

- **Elizabeth:** #71, pruebas de sistema de la interfaz (login, productos, promociones, devoluciones y layout), y #75, aceptación manual.
- **Kelly:** #64 a #70, #72, #73 y #74: unitarias, integración, carga y recuperación, conformidad y aceptación automatizada.

El detalle está en `docs/testing/README.md`.
