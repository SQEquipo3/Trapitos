"""Decorador @tc: liga una prueba (o una clase de pruebas) a su caso de prueba (TC).

La prueba es la ficha del TC. Una sola prueba por TC lleva los datos completos
y su docstring describe el caso; las demás pruebas del mismo TC solo llevan el id:

    @tc("ITS_VEN_04", nivel="ITS", modulo="ventas", reqs=["RF-05"],
        nombre="Devolución suma al stock y registra movimiento")
    def test_devolucion_regresa_stock(db, empleado, make_product):
        \"\"\"Una devolución parcial regresa las piezas al inventario.

        Precondiciones: Producto con stock 10 y un empleado.
        Pasos:
        - Vender 5 piezas
        - Devolver 2
        Esperado:
        - Stock vuelve a 7
        - Movimiento DEVOLUCION +2 ligado a la venta
        Comentarios: opcional.
        \"\"\"

    @tc("ITS_VEN_04")
    def test_devolucion_mayor_a_lo_vendido_es_rechazada(...):
        ...

tools/generar_documentos.py lee estos datos del código fuente (sin ejecutarlo)
y tests/test_catalogo.py valida en cada PR que estén completos.
"""

NIVELES = ("UTS", "ITS", "STS", "ATS", "CTS")


def tc(tc_id, *, nivel=None, modulo=None, reqs=(), nombre=None):
    def marcar(objeto):
        objeto.tc_id = tc_id
        return objeto
    return marcar
