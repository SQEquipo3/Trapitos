# Guion de aceptación manual

Preparación de los cinco casos de [#75](https://github.com/SQEquipo3/Trapitos/issues/75) y de la sesión con el cliente de [#60](https://github.com/SQEquipo3/Trapitos/issues/60). Las fichas que alimentan los Excel son [manuales.yml](manuales.yml). Este guion y la [plantilla de registro](REGISTRO_ACEPTACION.md) no constituyen evidencia de ejecución.

## Estado de partida

Línea base de esta preparación: `main`, commit `5f8738e44a7707e079aa887bb8c3b0b438c35bd2`. Los estados siguientes corresponden a esa versión.

| Caso | Estado registrado | Condición para ejecutarlo |
| --- | --- | --- |
| ATS_INS_01 | Not executed | Equipo limpio, Python 3.12 con Tkinter, código y dependencias disponibles sin internet. |
| ATS_UX_01 | Not executed | Cliente presente y datos preparados para una sesión de menos de cinco minutos. |
| ATS_SEG_01 | Blocked por #57 | Probar una versión con la corrección de permisos. El [PR #77](https://github.com/SQEquipo3/Trapitos/pull/77) está pendiente de integración. |
| ATS_VD_08 | Blocked por #56 | Servicio LAN funcional y dos terminales conectadas a los mismos datos de prueba. |
| ATS_VD_09 | Blocked por #56 | La misma infraestructura LAN y un producto con una sola unidad. |

Verificar el estado de [#57](https://github.com/SQEquipo3/Trapitos/issues/57) y [#56](https://github.com/SQEquipo3/Trapitos/issues/56) antes de la sesión. La existencia de un PR no acredita su integración ni la ejecución manual. Si se evalúa una rama de corrección, registrar su SHA; el resultado corresponde a esa versión.

## Preparar la versión y los datos

Trabajar en una copia descartable del código, fuera del directorio de operación y sin copiar `mis_trapitos.db`. Registrar SHA, sistema operativo, versión de Python y dependencias. Cada caso debe empezar con sus propias precondiciones, sin aprovechar el stock modificado por otro caso.

Hay una diferencia entre las instrucciones de las incidencias: #75 menciona `load_examples=False`, mientras que #60 pide `python main.py` y datos de ejemplo. El arranque actual de `main.py` abre `Database` con ejemplos habilitados. Este guion conserva ese arranque para ATS_INS_01 y prepara datos controlados para ATS_UX_01 en una copia descartable. No se declara cumplida la condición `load_examples=False` para esos arranques; su aplicación a la ejecución manual queda pendiente de revisión del equipo. Las pruebas automatizadas sí pueden usar esa opción.

## ATS_INS_01: instalación sin internet

En un equipo con internet y el mismo sistema, arquitectura y Python 3.12 que el equipo de destino, preparar:

```powershell
git rev-parse HEAD
git archive --format=zip --output="$env:TEMP\trapitos-aceptacion-codigo.zip" HEAD
py -3.12 -m pip download --only-binary=:all: --dest "$env:TEMP\trapitos-wheelhouse" -r requirements.txt
```

Anotar el SHA junto al ZIP, que no incluye el directorio `.git`, y conservar los nombres de los paquetes descargados. Copiar el ZIP y el wheelhouse al equipo limpio. Extraer el código en una carpeta nueva y colocar las dependencias en su subcarpeta `wheelhouse`. Python 3.12 y Tcl/Tk deben estar instalados previamente, como establece la precondición del caso.

Desconectar el acceso a internet antes de instalar las dependencias. Desde la carpeta extraída:

```powershell
py -3.12 --version
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --no-index --find-links .\wheelhouse -r requirements.txt
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m pip freeze
.\.venv\Scripts\python.exe -m tkinter
.\.venv\Scripts\python.exe main.py
```

Cerrar la ventana de comprobación de Tkinter antes de abrir la aplicación. El cliente inicia sesión con la cuenta de demostración `admin` / `1234`, abre Productos, cierra la aplicación y repite el arranque sin reconectar internet.

**Aprobación:** dependencias instaladas sin descargas externas, login y Productos operativos en ambos arranques, y BD creada exclusivamente en la carpeta de prueba. Guardar salida de instalación, versiones, comprobación de desconexión y capturas de ambos arranques. Una ejecución en el equipo habitual con dependencias ya instaladas no acredita este caso.

## ATS_UX_01: recorrido con el cliente

El facilitador prepara, antes de iniciar el cronómetro:

- Sesión iniciada y una copia descartable con datos de prueba.
- Producto `ACEP-PROMO-01`: Blusa de prueba, categoría Ropa, talla M, color Azul, costo 80, precio 200 y stock 10. Puede dejarse el proveedor vacío.
- Promoción del 25% para ese producto, vigente desde el día de la sesión hasta siete días después.
- Ausencia del código `ACEP-NUEVO-01`, carrito vacío y descuento general en 0.

Entregar al cliente únicamente esta tarjeta, sin indicarle qué botones o menús debe usar:

> Registra una prenda con código ACEP-NUEVO-01, nombre Blusa nueva, categoría Ropa, talla M, color Rojo, costo 80, precio de venta 200 y stock 5. Después vende dos unidades de ACEP-PROMO-01 en efectivo, aplicando su promoción vigente y sin descuento general.

Iniciar el cronómetro antes de la primera acción y detenerlo cuando aparezca el ticket de la venta. El observador registra dudas, errores e intervenciones. Si el cliente necesita instrucciones adicionales para completar la tarea, registrar la asistencia y no aprobar el criterio de autonomía.

**Aprobación:** ambas tareas terminadas sin asistencia en menos de 300 segundos, producto nuevo con stock 5, promoción del 25% aplicada, total 300 y stock final 8 para `ACEP-PROMO-01`. Conservar el tiempo exacto, ticket y capturas de los dos productos. El producto registrado y el vendido son distintos para que la promoción pueda prepararse antes del recorrido.

## ATS_SEG_01: permisos

Mantener el bloqueo de #57 mientras la versión evaluada no incluya la corrección. Cuando esté disponible, preparar usuarios con roles Administrador o Propietario y Vendedor en la copia de prueba.

1. Entrar como Administrador o Propietario y comprobar que puede crear y editar un empleado de prueba.
2. Cerrar sesión y entrar como Vendedor.
3. Abrir Contactos → Empleados e intentar acceder al alta o edición.
4. Comprobar que aparece acceso denegado y no se muestra el formulario ni el listado de empleados.
5. Volver a entrar como administrador y comprobar que los datos de empleados permanecen intactos.

Guardar versión, roles utilizados, acceso permitido, acceso denegado y comprobación de datos. Retirar `blocked_by: '#57'` únicamente cuando la versión permita ejecutar el caso. Si el comportamiento esperado falla, registrar el resultado real y referenciar #57. Las pruebas automáticas del PR #77 no acreditan la aceptación manual.

## ATS_VD_08: inventario entre terminales

Ejecutar únicamente después de resolver #56 para la versión evaluada. A y B deben usar el servicio LAN y los mismos datos de prueba; dos copias independientes de SQLite no satisfacen esta precondición.

1. Preparar `ACEP-LAN-01` con stock 10 y abrir su inventario en ambas terminales.
2. Vender una unidad en A mientras B conserva abierto el inventario.
3. Medir desde la confirmación de venta en A hasta que B muestra el cambio, sin pulsar actualizar ni reabrir la pantalla.
4. Verificar stock final 9 en A y B y un tiempo máximo de 5 segundos.

Conservar una grabación que permita relacionar ambos eventos o un registro de tiempo equivalente, junto con la identificación de las terminales. La prueba necesita red local; desconectar internet no debe interrumpir la LAN.

## ATS_VD_09: última unidad

Con la misma infraestructura validada para #56, preparar `ACEP-ULTIMO-01` con stock 1 y sin ventas previas de ese producto.

1. Capturar una unidad en el carrito de A y en el de B antes de confirmar.
2. Confirmar ambas ventas a una señal acordada.
3. Guardar las respuestas de las dos terminales, el único ticket emitido y el inventario final.
4. Comprobar una sola venta registrada, rechazo de la otra por stock insuficiente, un movimiento de salida de una unidad y stock final 0 en ambas terminales.

No aprobar si se registran dos ventas, si ambas se rechazan o si el stock queda negativo. Si no se logra una ejecución simultánea, anotar la limitación y repetir con el stock inicial restablecido en los datos de prueba.

## Registrar resultados y entregar

Copiar [REGISTRO_ACEPTACION.md](REGISTRO_ACEPTACION.md) por caso ejecutado en `docs/testing/evidencias/<fecha>/<TC>.md` y completar observaciones y enlaces a evidencia. Después actualizar el caso correspondiente en `manuales.yml`:

| Campo | Valor que se registra |
| --- | --- |
| `manual_result` | `PASSED` si cumple todos los resultados esperados; `FAILED` si se ejecutó y no los cumple. |
| `executed_by` | Persona que ejecutó realmente el caso; en #60, el cliente o su representante. |
| `executed_on` | Fecha real en formato `AAAA-MM-DD`. |
| `comments` | SHA, resultado observado, duración cuando aplique y ruta de evidencia. |
| `blocked_by` | Issue existente que impide ejecutar. Retirarlo cuando deje de impedir la ejecución; no combinar un bloqueo vigente con una aprobación. |

Antes de ejecutar, omitir los tres campos de resultado, persona y fecha. No llenar esos campos al preparar la sesión ni copiar la fecha planeada como fecha real. Un bloqueo se conserva como `Blocked`; un caso disponible sin ejecución permanece `Not executed`.

Vincular los defectos únicamente con issues existentes que describan el problema. Si una observación no corresponde a ninguno, anotarla en la evidencia y dejar pendiente su revisión y trazabilidad, sin inventar un número ni crear un issue nuevo. El generador exige un defecto asociado para resultados fallidos; no declarar conformidad documental mientras esa asociación falte.

Incorporar los registros a la rama, ejecutar el catálogo y revisar la nueva corrida de Tests. En el artefacto `entregables-qa`, comprobar los cinco casos en `Detailed status` y sus fichas en Test Plan y TC Design. Los resultados manuales se registran en `manuales.yml`, no en `reports/results.json`, que se regenera con pytest.

La preparación del guion no completa #60 ni sustituye la revisión individual y entrega de [#61](https://github.com/SQEquipo3/Trapitos/issues/61). Mantener el PR en draft mientras falten las ejecuciones y decisiones señaladas.
