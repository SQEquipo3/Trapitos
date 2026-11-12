# Mis Trapitos

Sistema local de gestión de una tienda de ropa desarrollado en Python con Tkinter y SQLite. El prototipo actual se encuentra en `mis_trapitos_app_v7.py`.

## Módulo de productos

`ui_productos.py` contiene `ProductosUI`, una pestaña Tkinter que administra el formulario de productos y variantes por talla/color, sus validaciones, imágenes, inventario y exportación CSV. Recibe la instancia de `Database` de la aplicación; la persistencia y las transacciones permanecen en esa clase.

`App` incorpora la pestaña y delega `refresh_products()` a `ProductosUI.actualizar_inventario()`. Las altas, ediciones, ventas, devoluciones y cancelaciones exitosas actualizan las existencias en la tabla. Cuando cambia el stock del producto seleccionado, también se actualiza su formulario sin descartar las ediciones pendientes de otros campos. Esta actualización ocurre dentro de la aplicación local.

Para ejecutar la aplicación, conservar ambos archivos Python en la misma carpeta y utilizar `python mis_trapitos_app_v7.py` con Tkinter y Pillow disponibles.

### Fotos de productos y restauración

Las fotos seleccionadas se copian a `mis_trapitos_imagenes/`, en la raíz de la aplicación, con un UUID en el nombre. `products.image_path` guarda una ruta relativa a esa carpeta; la vista previa la resuelve desde la ubicación de la aplicación, independientemente del directorio desde el que se ejecute.

Al abrir una base existente se convierten las referencias recuperables: las fotos de la carpeta administrada conservan su archivo, y las fotos externas disponibles se copian dentro de ella. Las rutas antiguas de Windows y POSIX que contienen `mis_trapitos_imagenes` también se recuperan desde la carpeta restaurada. La migración puede repetirse sin duplicar las copias. Si falta el archivo o falla su importación, se conserva la referencia anterior para poder recuperarlo y se puede seguir consultando el producto.

Para trasladar o respaldar la instalación, cerrar la aplicación y copiar **la base SQLite y la carpeta completa `mis_trapitos_imagenes/`**. Al restaurar, colocar la carpeta de fotos en la raíz de la nueva instalación. Una copia de la base de datos por sí sola no incluye las imágenes. Las fotos externas aún no migradas deben recuperarse de su ubicación original o seleccionarse nuevamente.

## Pruebas de regresión

```sh
python -m unittest discover -s tests -v
```

Las pruebas utilizan widgets Tkinter reales con ventanas ocultas y bases SQLite temporales, sin cargar los datos de demostración. Requieren una sesión gráfica con Tk y Pillow. Cubren productos, variantes, validaciones, imágenes, CSV, selección, cambios de sesión y actualización del inventario después de ventas, devoluciones y cancelaciones.

## Documentación

El [índice y coordinación documental de la épica #3](docs/README.md) reúne SAD, SDD, Test Plan y Test Report, sus historias asociadas, dependencias y pendientes de trazabilidad.

- [Documento de Arquitectura de Software (SAD)](docs/SAD.md): decisiones tecnológicas, capas, patrones, distribución propuesta para 7 terminales y operación sin internet mediante una red local.
- [Documento de Diseño de Software (SDD)](docs/SDD.md): módulos y clases, interfaces Tkinter, modelo relacional y diccionario de datos SQLite, diagramas de secuencia, contratos propuestos para 7 terminales y trazabilidad de requisitos.

El SAD distingue la implementación actual de la arquitectura propuesta. El prototipo todavía no incluye el servicio LAN necesario para compartir de forma controlada una única base de datos entre las siete terminales.
