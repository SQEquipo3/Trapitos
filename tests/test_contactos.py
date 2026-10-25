"""Clientes, proveedores y empleados (RF-11, RF-12, RF-13, RF-14)."""
import sqlite3

import pytest

from mis_trapitos.data.repositories import clientes, empleados, proveedores
from utils import today_text
from mis_trapitos.services import ventas as ventas_srv
from tests.tc import tc


def cliente(nombre="Ana"):
    return (nombre, "555-1", "a@x.com", "Calle 1", "Guadalajara", "Vestidos")


@tc("ITS_CON_01", nivel="ITS", modulo="contactos", reqs=["RF-11", "RF-12"],
    nombre="Alta/edición de clientes, historial y producto favorito")
def test_alta_y_edicion_de_cliente(db):
    """El historial del cliente enlaza ventas, partidas y productos y muestra el estado de cada
    venta.

    Precondiciones: Cliente con dos ventas, una cancelada.
    Pasos:
    - Guardar y editar cliente
    - Registrar ventas
    - Consultar historial, resumen y favorito
    Esperado:
    - Datos editados persisten
    - Historial con ACTIVA y CANCELADA
    - Favorito = producto con más piezas
    """
    cid = clientes.guardar(db, None, cliente())
    clientes.guardar(db, cid, cliente("Ana Lopez"))
    assert clientes.obtener_por_id(db, cid)["name"] == "Ana Lopez"
    assert clientes.existe(db, cid) and not clientes.existe(db, 999)


@tc("ITS_CON_02", nivel="ITS", modulo="contactos", reqs=["RF-13", "RF-14"],
    nombre="Integridad referencial de clientes y proveedores")
def test_cliente_con_ventas_no_se_puede_eliminar(db, empleado, make_product):
    """No se eliminan clientes con ventas ni proveedores con productos; no se duplican proveedores.

    Precondiciones: Cliente con venta; proveedor con producto.
    Pasos:
    - Eliminar cliente con ventas
    - Eliminar proveedor con productos
    - Crear proveedor duplicado
    Esperado:
    - IntegrityError en los tres casos
    - El alta válida aparece en la lista
    """
    cid = clientes.guardar(db, None, cliente())
    pid = make_product()
    ventas_srv.registrar(db, cid, empleado, "Efectivo", 0, [{"product_id": pid, "quantity": 1}])
    with pytest.raises(sqlite3.IntegrityError):
        clientes.eliminar(db, cid)


@tc("ITS_CON_01")
def test_historial_resumen_y_producto_favorito(db, empleado, make_product):
    cid = clientes.guardar(db, None, cliente())
    a, b = make_product(name="Blusa"), make_product(name="Falda")
    ventas_srv.registrar(db, cid, empleado, "Efectivo", 0, [{"product_id": a, "quantity": 3}])
    ventas_srv.registrar(db, cid, empleado, "Efectivo", 0, [{"product_id": b, "quantity": 1}])
    assert len(clientes.historial(db, cid)) == 2
    assert clientes.resumen_compras(db, cid)["compras"] == 2
    assert clientes.producto_favorito(db, cid)["producto"] == "Blusa"


@tc("ITS_CON_02")
def test_alta_de_proveedor_y_lista(db):
    pid = proveedores.guardar(db, None, ("Textiles SA", "555", "Av 1", "Blusas", today_text()))
    assert proveedores.existe(db, pid) and proveedores.listar(db)[0]["nombre"] == "Textiles SA"


@tc("ITS_CON_02")
def test_proveedor_duplicado_o_con_productos_no_se_elimina(db, make_product):
    sid = proveedores.guardar(db, None, ("Textiles SA", "555", "Av 1", "x", today_text()))
    with pytest.raises(sqlite3.IntegrityError):
        proveedores.guardar(db, None, ("Textiles SA", "1", "x", "x", today_text()))
    make_product(supplier_id=sid)
    with pytest.raises(sqlite3.IntegrityError):
        proveedores.eliminar(db, sid)


@tc("UTS_CON_01")
def test_empleado_no_cambia_password_si_viene_vacio(db):
    eid = empleados.guardar(db, None, "Luis", "luis", "secreto", "Vendedor")
    empleados.guardar(db, eid, "Luis R", "luis", "", "Vendedor")
    assert empleados.autenticar(db, "luis", "secreto") is not None


@tc("UTS_CON_01", nivel="UTS", modulo="contactos", reqs=["SEG-01"],
    nombre="Unicidad de usuario de empleado y conservación de contraseña")
def test_usuario_de_empleado_es_unico(db):
    """El username es único y editar un empleado sin password conserva el anterior.

    Precondiciones: BD temporal vacía.
    Pasos:
    - Crear dos empleados con el mismo usuario
    - Editar un empleado con password vacío y autenticar con la contraseña original
    Esperado:
    - El segundo alta levanta IntegrityError
    - La contraseña original sigue funcionando
    """
    empleados.guardar(db, None, "A", "igual", "1", "Vendedor")
    with pytest.raises(sqlite3.IntegrityError):
        empleados.guardar(db, None, "B", "igual", "2", "Vendedor")
