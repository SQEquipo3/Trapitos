# Cómo replicar la documentación de pruebas automática en NutriMaker

Esta guía explica el sistema que usa **Trapitos** para generar solo los tres entregables de la actividad de pruebas, y qué hay que cambiar para usarlo en **NutriMaker** (Java + Maven). Se puede leer como persona o dar completa a una IA junto con el repo de NutriMaker.

> **Contexto para una IA:** el proyecto de referencia es `SQEquipo3/Trapitos` (Python, pytest). El proyecto destino es `SQEquipo3/NutriMaker` (Java, Maven, JavaFX, JUnit). Hay que reutilizar el generador de Trapitos y cambiar solo las dos partes que dependen del lenguaje (sección 4). No reescribas el llenado de Excel: ya funciona con las plantillas del maestro.

---

## 1. Qué pide la actividad y qué resuelve el sistema

La actividad pide tres documentos llenados con las plantillas del maestro:

| Entregable | Archivo | Plantilla |
|---|---|---|
| SW Test Plan | `SW_Test_Plan_<Team>_<Proyecto>.xlsx` | `SW_Test_Plan_[Team0X]_[ProjectName].xlsx` |
| TC Design (≥ 10 TC por nivel) | `TC_Design_<Team>_<Proyecto>.xlsx` | la misma del Test Plan (solo hojas de TC) |
| Test Report | `SWT_summary_report_<Team>_<Proyecto>.xlsx` | `SWT_summary_report_[Team0X]_[ProjectName].xlsx` |

Rúbrica: considerar todas las funcionalidades, incluir diagramas en el Test Report, campos debidamente llenados, información congruente y nombres de archivo con el formato.

Niveles vistos en clase (presentación *09-Concepts types and testing levels*): **Unitarias/Módulo, Integración, Sistema, Aceptación** y, aparte, **Conformidad**. En Trapitos se usan los cinco como niveles, cada uno con al menos 10 TC: `UTS`, `ITS`, `STS`, `ATS` y `CTS`.

**La idea:** el equipo solo escribe pruebas y reporta bugs; el CI corre las pruebas y llena los Excel con los resultados reales en cada Pull Request.

```
Prueba con anotación + comentario   ─┐
Resultados de las pruebas (CI)       ├─►  tools/generar_documentos.py  ─►  3 Excel + gráficas
Issues de GitHub con label «bug»     │                                       (artefacto «entregables-qa»)
meta.yml + manuales.yml              ─┘
```

---

## 2. Cómo funciona en Trapitos

### 2.1 Cada prueba es la ficha de su TC

```python
@tc("ITS_VEN_04", nivel="ITS", modulo="ventas", reqs=["RF-05"],
    nombre="Devolución suma al stock y registra movimiento DEVOLUCION")
def test_devolucion_suma_al_stock(db, empleado, make_product):
    """Una devolución parcial regresa las piezas al inventario.      ← objetivo

    Precondiciones: Producto con stock 10 y un empleado.
    Pasos:
    - Vender 5 piezas
    - Devolver 2
    Esperado:
    - Stock vuelve a 7
    - Movimiento DEVOLUCION +2 ligado a la venta
    Comentarios: opcional.
    """
```

Reglas:
* Una sola prueba por TC lleva los datos (`nivel`, `modulo`, `reqs`, `nombre`) y el comentario. Las demás pruebas del mismo TC solo llevan el id: `@tc("ITS_VEN_04")`.
* La anotación también puede ir sobre una clase y cubre todos sus métodos de prueba.
* Id: `NIVEL_MODULO_NN`, de máximo 31 caracteres, porque es el nombre de una hoja de Excel.
* `reqs` usa los requisitos del SDD (`RF-xx`, `RNF-xx`) o ids extra declarados en `meta.yml`, como `ISO-8601` o `SEG-01`.
* El generador lee esto **del código fuente sin ejecutarlo**: en Python, con el módulo `ast`.

### 2.2 Archivos de configuración (`docs/testing/`)

* **`meta.yml`**: `team`, `project`, `project_title`, `repo`, `release`, `milestone`, `department`, `testers`, `planned_date`, `environment`, `references`, `requirements` (lista de RF), `other_ids`, `levels` (código → nombre), `nombres` (usuario de GitHub → nombre real) y `revisiones` (fecha, quién, descripción; salen en la hoja *intro*).
* **`manuales.yml`**: los TC que ejecuta una persona (el cliente en aceptación) o que necesitan varias máquinas. Llevan los mismos campos que la ficha, más `manual_result` (`PASSED`/`FAILED`), `executed_by`, `executed_on` y `blocked_by: "#<issue>"`.
* **`plantillas/`**: las dos plantillas del maestro, sin editar.

### 2.3 Bugs = issues de GitHub

* Plantilla de issue **«Defecto»** (`.github/ISSUE_TEMPLATE/defecto.yml`) con label **`bug`**. Campos: *TC que lo detectó*, *Pasos para reproducir*, *Severidad* (`1- High`/`2- Medium`/`3- Low`) y *Esperado vs. real*.
* El generador los lee con la API de GitHub y llena la hoja **«Bug report»**:
  * Defect ID: `#número`
  * Found by: quien abrió el issue
  * Assigned to: el assignee
  * State: si el issue está abierto o cerrado
* Todo TC *Failed* o *Blocked* debe tener su issue de bug; si no, el generador termina con error.
* Una prueba que falla por un bug conocido se deja marcada como «falla esperada» con el número del issue en el motivo. En pytest es `xfail(strict=True, reason="#53: ...")`; en el Excel sale *Fail* ligado al bug, pero el CI sigue en verde.

### 2.4 El generador (`tools/generar_documentos.py`)

Funciones principales:

| Función | Qué hace | ¿Depende del lenguaje? |
|---|---|---|
| `pruebas_del_codigo`, `leer_tc_del_codigo`, `leer_docstring` | Lee las anotaciones y comentarios de las pruebas | **Sí** |
| `cargar` (parte de resultados) | Lee los resultados de la corrida | **Sí** |
| `coincide` | Liga un resultado con la prueba que lo produjo | **Sí** (formato del id) |
| `cargar_catalogo` | Junta meta.yml + TC del código + manuales.yml | No |
| `cargar_bugs`, `leer_formulario`, `defecto_desde_issue` | Bugs desde GitHub | No |
| `evaluar`, `validar`, `conteos` | Estado de cada TC, consistencia y conteos | No |
| `graficas` | 6 diagramas (matplotlib) | No |
| `construir_plan`, `construir_strategy`, `construir_tc_design`, `construir_reporte` | Llenan las plantillas | No |

**Contrato interno.** Si tus funciones de lectura entregan esto, todo lo demás funciona igual:

```python
# Cada TC (automatizado o manual)
caso = {
    "id": "ITS_VEN_04", "level": "ITS", "module": "ventas", "reqs": ["RF-05"],
    "name": "...", "objective": "...", "pre": "...",
    "steps": ["...", "..."], "expected": ["...", "..."], "comments": "",
    "tests": ["<id de prueba 1>", "<id de prueba 2>"],   # vacío si es manual
}

# Resultados de la corrida: {id_de_prueba: {"outcome": ..., "reason": ...}}
# outcome ∈ passed | failed | error | skipped | xfailed (falla esperada) | xpassed
resultados = {"tests/test_ventas.py::test_devolucion_suma_al_stock": {"outcome": "passed", "reason": ""}}

# Cobertura (opcional), mismo formato que el JSON de pytest-cov
cobertura = {"totals": {"percent_covered": 87.5},
             "files": {"ruta/Archivo": {"summary": {"percent_covered": 90.0}}}}
```

### 2.5 CI (`.github/workflows/tests.yml`)

Se ejecuta en cada Pull Request y en `main`:
1. Corre las pruebas con cobertura.
2. Sube los reportes (`test-reports`).
3. Corre `python tools/generar_documentos.py` con `GITHUB_TOKEN`.
4. Sube los Excel y las gráficas como artefacto **`entregables-qa`**.

Necesita `permissions: issues: read` para leer los bugs. Si a un TC le falta algo, el CI sale en rojo y dice qué falta.

---

## 3. Qué copiar de Trapitos tal cual

```
docs/testing/plantillas/                  (las 2 plantillas del maestro)
tools/generar_documentos.py               (el generador; se adapta en la sección 4)
.github/ISSUE_TEMPLATE/defecto.yml        (plantilla de bug con label «bug»)
.github/ISSUE_TEMPLATE/caso-de-prueba.yml (opcional)
.github/pull_request_template.md          (opcional)
docs/testing/meta.yml                     (ajustar: team, project, repo, requisitos, módulos, testers…)
docs/testing/manuales.yml                 (reemplazar por los TC manuales de NutriMaker)
docs/testing/README.md                    (ajustar ejemplos a Java)
```

---

## 4. Qué cambia para Java (NutriMaker)

### 4.1 Anotación `@TC` en lugar del decorador

```java
// src/test/java/com/javafx/nutrimaker/tc/TC.java
package com.javafx.nutrimaker.tc;

import java.lang.annotation.*;

/** Liga una prueba (o una clase de pruebas) a su caso de prueba. Ver docs/testing/README.md. */
@Retention(RetentionPolicy.SOURCE)
@Target({ElementType.METHOD, ElementType.TYPE})
public @interface TC {
    String value();                 // id, p. ej. "ITS_REC_01"
    String nivel() default "";
    String modulo() default "";
    String[] reqs() default {};
    String nombre() default "";
}
```

La ficha va en el **Javadoc** del método, con las mismas secciones:

```java
/**
 * Al guardar una receta se calculan las calorías totales de sus ingredientes.
 *
 * Precondiciones: Dos ingredientes con calorías registradas.
 * Pasos:
 * - Crear una receta con 100 g de cada ingrediente
 * - Guardarla
 * Esperado:
 * - Calorías totales = suma de ambos ingredientes
 */
@Test
@TC(value = "ITS_REC_01", nivel = "ITS", modulo = "recetas", reqs = {"RF-03"},
    nombre = "Guardar receta calcula sus calorías")
void guardarRecetaCalculaCalorias() { ... }

@Test
@TC("ITS_REC_01")   // otra prueba del mismo TC
void recetaSinIngredientesNoSeGuarda() { ... }
```

### 4.2 Leer los TC del código Java

Reemplazar `pruebas_del_codigo` y `leer_tc_del_codigo` por una versión que recorra `src/test/java/**/*Test.java`. Basta con expresiones regulares; no hace falta un parser de Java:
* Por cada método con `@Test`, o cada clase con `@TC`, tomar la anotación `@TC(...)` y el Javadoc `/** ... */` inmediatamente anterior.
* Quitar los `*` iniciales del Javadoc y pasar el texto a `leer_docstring`, que no cambia.
* **Id de prueba:** usar `paquete.Clase#metodo`, igual al que sale en los reportes de Surefire (`classname` + `#` + `name`). Si `@TC` está en la clase, el id es `paquete.Clase`.
* Ajustar `coincide`: un resultado `paquete.Clase#metodo` pertenece a la prueba `paquete.Clase#metodo`, a la clase `paquete.Clase`, o a `paquete.Clase#metodo(...)` o `[n]` si es parametrizada.

### 4.3 Leer los resultados de Maven Surefire

En lugar de `reports/results.json` (lo escribe el `conftest.py` de pytest), leer `target/surefire-reports/TEST-*.xml`, que tiene formato JUnit XML:

| En el XML (`<testcase classname="…" name="…">`) | outcome |
|---|---|
| sin hijos | `passed` |
| `<failure>` | `failed` |
| `<error>` | `error` |
| `<skipped message="#53: …">` (motivo empieza con `#`) | `xfailed`: falla esperada por un bug conocido |
| `<skipped>` (otro motivo) | `skipped` |

Para un bug conocido en JUnit 5, deshabilitar la prueba con el número del issue: `@Disabled("#53: la cancelación no repone el stock exacto")`. El generador la mostrará como *Fail* ligada al bug #53, y el CI seguirá en verde.

### 4.4 Cobertura con JaCoCo

Agregar el plugin `jacoco-maven-plugin` al `pom.xml` (`prepare-agent` + `report`). Después, convertir `target/site/jacoco/jacoco.xml` al formato de la sección 2.4: `percent_covered = covered / (covered + missed) × 100` del contador `LINE`, total y por clase. En la gráfica de cobertura del generador cambiar `"mis_trapitos/"` por el prefijo del paquete.

### 4.5 Workflow de CI

githubMetrics ya trae una base: `SQEquipo3/githubMetrics` → `templates/github/workflows/tests-java.yml`. Lo que debe hacer:

```yaml
permissions: {contents: read, issues: read}
# … checkout, setup-java (la versión del pom.xml), cache de Maven
- run: xvfb-run -a mvn -B verify          # JavaFX necesita pantalla virtual si hay pruebas de interfaz
- uses: actions/setup-python@v5
  with: {python-version: "3.12"}
- run: pip install openpyxl pyyaml matplotlib
- name: Generar SW Test Plan, TC Design y Test Report
  if: always()
  env: {GITHUB_TOKEN: "${{ secrets.GITHUB_TOKEN }}"}
  run: python tools/generar_documentos.py
- uses: actions/upload-artifact@v4
  if: always()
  with: {name: entregables-qa, path: entregables/}
```

### 4.6 Validación del catálogo

En Trapitos, `tests/test_catalogo.py` valida lo siguiente en cada PR:
* al menos 10 TC por nivel
* todos los RF tienen al menos un TC
* ids únicos y de máximo 31 caracteres
* ninguna prueba sin `@TC`
* fichas completas
* `blocked_by` con formato `#número`

En NutriMaker basta con que el generador termine con error cuando `validar()` encuentra problemas (ya lo hace) y que corra en el CI. Si quieren el aviso dentro de `mvn verify`, se puede agregar al generador una opción que solo valide (hoy no existe) y llamarla desde una prueba JUnit.

---

## 5. Pasos sugeridos para NutriMaker

1. Copiar los archivos de la sección 3 y ajustar `meta.yml` con los RF de NutriMaker, sus módulos, el equipo y `repo: SQEquipo3/NutriMaker`.
2. Crear la label `bug` (si no existe) y la plantilla «Defecto».
3. Crear la anotación `@TC` (4.1) y adaptar el generador (4.2 y 4.3).
4. Configurar JaCoCo y el workflow (4.4 y 4.5).
5. **Escribir las pruebas**: es lo que más trabajo lleva. Hoy NutriMaker tiene un archivo de pruebas, y se necesitan **al menos 10 TC por cada uno de los 5 niveles** que cubran **todos los RF**:
   * Unitarias: clases de modelo y servicio aisladas.
   * Integración: servicio + repositorio + base de datos de prueba.
   * Sistema: flujos completos e interfaz JavaFX (TestFX), además de una prueba de carga y una de recuperación.
   * Aceptación: escenarios del cliente; algunos manuales en `manuales.yml`, ejecutados por el cliente.
   * Conformidad: estándares que use la app (formatos de fecha, CSV/JSON, hash de contraseñas, integridad de la base) y contratos de su documento de diseño.
6. Reportar como issues con label `bug` los defectos que encuentren las pruebas.
7. Antes de entregar: nombres reales en `meta.yml`, TC manuales ejecutados, `revisiones` de cada integrante, y descargar `entregables-qa` de la última corrida en `main`.

---

## 6. Errores que ya nos pasaron (para no repetirlos)

* **Label equivocada:** la plantilla de bug ponía `defect`, una label que no existía; el dashboard de githubMetrics cuenta `bug`.
* **Fallos que salían como Pass:** una subprueba fallida quedaba como *passed* porque el resultado final de su prueba la sobrescribía. Al leer resultados, un fallo nunca se debe sobrescribir con un *passed*.
* **Revisiones que se borraban:** si se escriben a mano en el Excel, desaparecen al regenerar; deben vivir en `meta.yml`.
* **Bugs de una sola fecha:** githubMetrics cuenta cada bug en el sprint en que se creó el issue. Si se reportan todos el mismo día, el Defect Density de ese sprint sube de golpe.
* **Fallos según la máquina:** las pruebas de interfaz pueden fallar en una máquina con escalado de pantalla y pasar en CI (Xvfb). Para la entrega, la fuente de verdad es el CI.
* **Nombres de hoja:** los ids de TC son nombres de hoja de Excel: máximo 31 caracteres, solo letras, números y `_`.

---

## 7. Prompt sugerido para la IA de NutriMaker

> Te paso el repo de NutriMaker (Java, Maven, JavaFX) y la guía `REPLICAR.md` del proyecto Trapitos, junto con sus archivos `tools/generar_documentos.py`, `docs/testing/plantillas/`, `docs/testing/meta.yml`, `docs/testing/manuales.yml` y `.github/ISSUE_TEMPLATE/defecto.yml`.
> Quiero el mismo sistema en NutriMaker: que el CI genere el SW Test Plan, el TC Design y el Test Report desde las pruebas JUnit (anotación `@TC` + Javadoc), los resultados de Surefire, la cobertura de JaCoCo y los issues con label `bug`.
> Reutiliza el generador y cambia solo la lectura de TC, resultados y cobertura (sección 4). No modifiques las plantillas. Empieza por revisar qué RF tiene NutriMaker y proponme el reparto de al menos 10 TC por nivel (UTS, ITS, STS, ATS, CTS) antes de escribir pruebas.
