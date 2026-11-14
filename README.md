# Mis Trapitos

Sistema local de gestión de una tienda de ropa desarrollado en Python con Tkinter y SQLite. El prototipo actual se encuentra en `mis_trapitos_app_v7.py`.

## Módulo de productos

`ui_productos.py` contiene `ProductosUI`, una pestaña Tkinter que administra el formulario de productos y variantes por talla/color, sus validaciones, imágenes, inventario y exportación CSV. Recibe la instancia de `Database` de la aplicación; la persistencia y las transacciones permanecen en esa clase.

`App` incorpora la pestaña y delega `refresh_products()` a `ProductosUI.actualizar_inventario()`. Las altas, ediciones, ventas, devoluciones y cancelaciones exitosas actualizan las existencias en la tabla. Cuando cambia el stock del producto seleccionado, también se actualiza su formulario sin descartar las ediciones pendientes de otros campos. Esta actualización ocurre dentro de la aplicación local.

Para ejecutar la aplicación, conservar ambos archivos Python en la misma carpeta y utilizar `python mis_trapitos_app_v7.py` con Tkinter y Pillow disponibles.

## Varias terminales en la LAN (#56)

```sh
python main.py                                  # una sola terminal, como siempre
python main.py --servidor [--puerto 8765]       # terminal principal: aplicación + servicio LAN
python main.py --terminal http://<IP>:8765      # terminal de venta conectada a la principal
```

La terminal principal guarda la única base SQLite y atiende por HTTP/JSON (`mis_trapitos/lan/servidor.py`) el inventario y el registro de ventas. Las terminales de venta (`mis_trapitos/ui/terminal_lan.py`) inician sesión con un usuario de esa base, venden y ven el inventario actualizado cada 2 s; la principal también refresca su tabla de productos cuando otra terminal vende (RNF-01, ≤ 5 s). Cada venta lleva una clave de idempotencia: si se pierde la respuesta, reintentar no la duplica. El stock se descuenta de forma condicionada dentro de una transacción `BEGIN IMMEDIATE`, así que de dos ventas simultáneas de la última pieza solo una se confirma.

Alcance mínimo: sin TLS (usar solo en la red local de la tienda), sesiones en memoria y solo ventas e inventario en las terminales remotas; los demás módulos se administran en la principal.

## Pruebas de regresión

```sh
python -m unittest discover -s tests -v
```

Las pruebas utilizan widgets Tkinter reales con ventanas ocultas y bases SQLite temporales, sin cargar los datos de demostración. Requieren una sesión gráfica con Tk y Pillow. Cubren productos, variantes, validaciones, imágenes, CSV, selección, cambios de sesión y actualización del inventario después de ventas, devoluciones y cancelaciones.

## Documentación

El [índice y coordinación documental de la épica #3](docs/README.md) reúne SAD, SDD, Test Plan y Test Report, sus historias asociadas, dependencias y pendientes de trazabilidad.

- [Documento de Arquitectura de Software (SAD)](docs/SAD.md): decisiones tecnológicas, capas, patrones, distribución propuesta para 7 terminales y operación sin internet mediante una red local.
- [Documento de Diseño de Software (SDD)](docs/SDD.md): módulos y clases, interfaces Tkinter, modelo relacional y diccionario de datos SQLite, diagramas de secuencia, contratos propuestos para 7 terminales y trazabilidad de requisitos.

El SAD distingue la implementación actual de la arquitectura propuesta. El servicio LAN mínimo (ventas e inventario) ya existe; TLS, permisos por operación en el servicio y la generación de recuperación del SDD sección 7 siguen pendientes.
