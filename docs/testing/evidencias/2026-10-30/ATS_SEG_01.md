# ATS_SEG_01 — Validación manual de permisos

## Registro de ejecución

| Dato | Registro |
| --- | --- |
| Caso | ATS_SEG_01 — Permisos por rol de empleado |
| Responsable de ejecución | Elizabeth Barajas |
| Estado de ejecución manual | Realizada |
| Equipo | PC externo utilizado para las pruebas |
| Rama de referencia | test/75-aceptacion-manual — PR #80 |
| Identificador exacto de la instalación | Pendiente de identificación |
| Fecha de ejecución | No consignada en este registro |
| Fecha de registro | 30 de octubre de 2026 |
| Resultado manual | Satisfactorio en la instalación evaluada |

## Comprobaciones realizadas

| Rol | Operación | Resultado observado |
| --- | --- | --- |
| Vendedor | Consultar la gestión de empleados | Acceso denegado |
| Vendedor | Crear empleados | Operación no permitida |
| Vendedor | Editar empleados | Operación no permitida |
| Administrador o Propietario | Crear empleados | Operación permitida |
| Administrador o Propietario | Editar empleados | Operación permitida |

**Resultado de la ejecución manual: satisfactorio.** La instalación evaluada aplicó las restricciones por rol y no permitió la edición de empleados sin los permisos correspondientes.

## Correspondencia de versión

El resultado manual corresponde a la instalación del PC externo. Su identificador exacto de código todavía no está disponible para cotejo.

La comprobación técnica del 30 de octubre de 2026 sobre el código `b93812dc4002aad9b35122d93d9cef462c244327`, publicado en el PR #80, permitió consultar, crear y editar empleados con el rol Vendedor. Esta comprobación utilizó una base de datos temporal y no modificó los datos de las sesiones manuales.

El resultado satisfactorio de la instalación externa queda registrado por separado de la comprobación del código publicado. El estado de #57 en esa versión se conserva hasta establecer la correspondencia entre ambas instalaciones.

[Registro estructurado](ATS_SEG_01.json) · [Defecto #57](https://github.com/SQEquipo3/Trapitos/issues/57) · [PR #80](https://github.com/SQEquipo3/Trapitos/pull/80) · [Corrección del PR #77](https://github.com/SQEquipo3/Trapitos/pull/77).
