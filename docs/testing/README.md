# Pruebas y documentación de calidad — Mis Trapitos

## Flujo de equipo (3 personas)
1. **Issues:** pon los usuarios de GitHub en `docs/testing/meta.yml` (`personas`), revisa `docs/testing/historias.yml` (10 historias que agrupan los 64 TC, con puntos, sprint y persona) y corre `gh auth login` + `python tools/crear_issues.py --crear --proyecto "<nombre del Project>"`. Crea las historias con la plantilla de historia de usuario, las asigna, las mete al Project y las cuelga de #26/#4 (y de la épica #29). Agreguen sprint/puntos en el Project (vienen como etiquetas).
2. **Cada quien, en su rama:** crea/edita su ficha `docs/testing/tc/<ID>.yml` (una por TC, para no pisarse) y su prueba en `tests/`. PR con `Closes #N`.
3. **PR:** corre `tests.yml` (pytest + cobertura + junit). Sube el artefacto `test-reports`, que lee el colector de Grafana (cobertura, pruebas por módulo).
4. **Merge a main:** el CI regenera los Excel (artefacto `entregables-qa`).
5. **TC manuales:** quien lo ejecuta pone `manual_result: PASSED|FAILED` en su ficha, por PR.
6. **Defectos:** `docs/testing/defectos/DEF-xxx.yml` (plantilla de issue «Defecto»). Todo TC FAILED/BLOCKED debe tener uno.

## Estructura
```
docs/testing/meta.yml        equipo, proyecto, testers, owners, requisitos, niveles
docs/testing/tc/<ID>.yml     UNA ficha por caso de prueba (objetivo, pasos, esperado, tests: [...])
docs/testing/defectos/       un archivo por defecto  -> hoja «Bug report»
tests/                       pruebas pytest;  reports/ = resultados (no se versiona)
tools/generar_documentos.py  rellena las plantillas Excel del maestro
tools/crear_issues.py        crea las historias en GitHub (historias.yml)
```
Salidas en `entregables/`: `SW_Test_Plan_<Team>_<Proyecto>.xlsx`, `TC_Design_…xlsx`, `SWT_summary_report_…xlsx` y `diagramas/`.

## Comandos
```bash
pip install -r requirements-dev.txt
xvfb-run -a pytest --cov=mis_trapitos --cov-report=json:reports/coverage.json   # Windows/macOS: sin xvfb-run
python tools/generar_documentos.py
```

## Reglas
* Ficha con `tests:` ⇒ TC automatizado (estado = resultado de pytest). Sin `tests:` ⇒ Manual, «Not executed» hasta registrar `manual_result`.
* `blocked_by: DEF-xxx` ⇒ Blocked.
* `tests/test_catalogo.py` verifica en CI: ≥ 10 TC por nivel, todos los RF cubiertos, ids únicos, referencias válidas y ninguna prueba huérfana (toda prueba pertenece a un TC).
* Defectos conocidos (B-03, B-05) están como `xfail(strict=True)`: el CI no se rompe, el reporte los muestra FAILED.

## Antes de entregar
Pongan nombres reales en `meta.yml` (`testers`, `owners`), confirmen `team`/`project`, ejecuten los TC manuales, regeneren y agreguen su línea de revisión en la hoja `intro`.
