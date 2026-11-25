# Índice documental de Mis Trapitos

Equipo 3 · Calidad de Software · MT-DOC-001 · Versión 2.0 · 24 de noviembre de 2026

La línea base es [main en 276fcb5](https://github.com/SQEquipo3/Trapitos/commit/276fcb58a15929f27e1d7f751e03eae84d540041), aplicación 8.0. Los cuatro documentos de la [épica #3](https://github.com/SQEquipo3/Trapitos/issues/3) están disponibles para revisión.

| Documento e historia | Entrega | Estado |
| --- | --- | --- |
| Software Design Document · [#5](https://github.com/SQEquipo3/Trapitos/issues/5) | [SDD 2.0](SDD.md) · [DOCX](entregas/SDD_Equipo3_MisTrapitos_v2.0.docx) · [PDF](entregas/SDD_Equipo3_MisTrapitos_v2.0.pdf) | Disponible |
| Software Architecture Document · [#6](https://github.com/SQEquipo3/Trapitos/issues/6) | [SAD 2.0](SAD.md) · [DOCX](entregas/SAD_Equipo3_MisTrapitos_v2.0.docx) · [PDF](entregas/SAD_Equipo3_MisTrapitos_v2.0.pdf) | Disponible |
| SW Test Plan · [#4](https://github.com/SQEquipo3/Trapitos/issues/4) | [SW_Test_Plan_Team03_Trapitos.xlsx](https://github.com/SQEquipo3/Trapitos/releases/download/qa-latest/SW_Test_Plan_Team03_Trapitos.xlsx) y su anexo [TC_Design_Team03_Trapitos.xlsx](https://github.com/SQEquipo3/Trapitos/releases/download/qa-latest/TC_Design_Team03_Trapitos.xlsx) | Disponible |
| Test Report · [#1](https://github.com/SQEquipo3/Trapitos/issues/1) | [SWT_summary_report_Team03_Trapitos.xlsx](https://github.com/SQEquipo3/Trapitos/releases/download/qa-latest/SWT_summary_report_Team03_Trapitos.xlsx) | Disponible |

## Cómo seguir un requisito

Para RNF-01, la [sección 9 del SDD](SDD.md#9-trazabilidad-de-requisitos) identifica las pantallas y el servicio que actualizan el stock. En el [SAD](SAD.md#7-ejecución-concurrencia-y-confirmación-de-ventas), ADR-05 y ADR-08 explican quién confirma la venta y cómo evitamos duplicarla. En Matrix del SW Test Plan se localiza STS_LAN_02. Su ficha en TC Design describe el sondeo y el límite de 5 s. En Detailed status del Test Report, ese mismo ID tiene Pass. El manual ATS_VD_08 aparece por separado con Not executed.

## Procedencia y revisiones

[tools/generar_documentos.py](../tools/generar_documentos.py) genera los tres Excel desde las fichas de pruebas, los registros manuales y los defectos de GitHub. Para esta revisión usamos el artifact `entregables-qa` de la [corrida 75 de main](https://github.com/SQEquipo3/Trapitos/actions/runs/45336280390). El [release qa-latest](https://github.com/SQEquipo3/Trapitos/releases/tag/qa-latest) ofrece los libros vigentes y se reemplaza en cada publicación desde main. Para cotejar esta línea base en el futuro, utilícese la corrida identificada.

| Versión | Cambio |
| --- | --- |
| 1.0 | Reunimos las historias de diseño, arquitectura, plan y reporte en el inventario inicial. |
| 2.0 | Incorporamos los Excel disponibles y enlazamos el diseño de la aplicación 8.0 con sus casos, resultados y entregas formales. |
